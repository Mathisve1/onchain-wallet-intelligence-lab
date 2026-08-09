from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.archive_inventory.r4.lz4_frame import LZ4FrameError, LZ4FrameLimit, iter_lz4_frame
from research.archive_inventory.r8 import collector as r8a_transport

R9_ROOT = ROOT / "research/archive_inventory/r9"
PREREGISTRATION = R9_ROOT / "MODERN_WALLET_FEATURE_PILOT_R9_CONTRACT.json"
APPROVAL_JSON = R9_ROOT / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_FEATURE_PILOT_R9_001.json"
APPROVAL_TEXT = R9_ROOT / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_FEATURE_PILOT_R9_001.txt"
IMPLEMENTATION = R9_ROOT / "R9_IMPLEMENTATION_CONTRACT.json"
ROLE_REUSE = R9_ROOT / "R9_AWS_ROLE_REUSE_ANALYSIS.json"

PILOT_ID = "HL-ARCHIVE-MODERN-WALLET-FEATURE-PILOT-R9-001"
PREREGISTRATION_MERGE = "62ce0009c3c4aad70d2a91f242a690cd26ace355"
APPROVAL_MERGE = "332aa535b0de19a18befb8529450ae88acf35762"
APPROVAL_ID = "APPROVE_HL_ARCHIVE_MODERN_WALLET_FEATURE_PILOT_R9_001"
APPROVAL_SHA = "1e4642ef2eef660f7971c2632864cf78894340e3408f15d15597e4eb12a04330"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"
TARGET_BUCKET = "hl-mainnet-node-data"
SIGNING_REGION = "ap-northeast-1"
OBJECT_KEY = "node_fills_by_block/hourly/20250727/8.lz4"
OBJECT_ARN = f"arn:aws:s3:::{TARGET_BUCKET}/{OBJECT_KEY}"
EXPECTED_SIZE = 1_517_603
EXPECTED_ETAG = '"60d4c1277f76651b5f04666bbe8d7594"'
EXPECTED_COMPRESSED_SHA = "928e1cd6bd7d69ad7243c263bacee48e53e4762ae9e99ef75f45007f6c0e6105"
EXPECTED_DECOMPRESSED_BYTES = 7_380_378
EXPECTED_BLOCK_COUNT = 4_345
EXPECTED_EVENT_PAIR_COUNT = 17_516
MAX_DECOMPRESSED_BYTES = 16_777_216
MAX_RECORD_BYTES = 16_777_216
MAX_BLOCKS = 1_000_000
MAX_EVENTS = 5_000_000
MAX_ROWS = 1_000_000
MAX_OUTPUT_BYTES = 33_554_432
MAX_RUNTIME_SECONDS = 120
MAX_NUMERIC_CHARS = 128
ADDRESS_RE = re.compile(r"^0x[0-9a-f]{40}$")
OUTPUT_FIELDS = [
    "wallet_address",
    "fill_count",
    "first_fill_time",
    "last_fill_time",
    "distinct_coin_count",
    "side_a_count",
    "side_b_count",
    "crossed_true_count",
    "liquidation_associated_fill_count",
    "duplicate_tid_count",
    "sum_abs_px_times_sz_notional_proxy",
    "sum_closed_pnl_fill_statistic",
]
SELECTED_FIELDS = ["coin", "side", "time", "px", "sz", "closedPnl", "tid", "crossed", "liquidation"]


class R9ContractError(RuntimeError):
    pass


class R9TransportIntegrityError(RuntimeError):
    pass


class R9FeatureUnresolved(RuntimeError):
    pass


class R9JSONError(ValueError):
    pass


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise R9ContractError(f"JSON root must be object: {path}")
    return value


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _strict_object(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise R9JSONError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_nonfinite(_token: str) -> object:
    raise R9JSONError("non-finite JSON constant")


def strict_loads(text: str) -> object:
    try:
        return json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_float=Decimal,
            parse_constant=_reject_nonfinite,
        )
    except (json.JSONDecodeError, InvalidOperation) as exc:
        raise R9JSONError(str(exc)) from exc


def _decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise R9FeatureUnresolved(f"{field} is not a decimal token")
    if isinstance(value, Decimal):
        token = str(value)
    elif isinstance(value, int):
        token = str(value)
    elif isinstance(value, str):
        token = value.strip()
    else:
        raise R9FeatureUnresolved(f"{field} has unsupported numeric type")
    if not token or len(token) > MAX_NUMERIC_CHARS:
        raise R9FeatureUnresolved(f"{field} numeric token length invalid")
    try:
        parsed = Decimal(token)
    except InvalidOperation as exc:
        raise R9FeatureUnresolved(f"{field} invalid decimal") from exc
    if not parsed.is_finite():
        raise R9FeatureUnresolved(f"{field} non-finite decimal")
    return parsed


def canonical_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise R9FeatureUnresolved("non-finite aggregate")
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in {"", "-0", "+0"}:
        return "0"
    return text


def validate_static_inputs() -> None:
    prereg = load_json(PREREGISTRATION)
    approval = load_json(APPROVAL_JSON)
    impl = load_json(IMPLEMENTATION)
    reuse = load_json(ROLE_REUSE)

    if sha256_bytes(APPROVAL_TEXT.read_bytes()) != APPROVAL_SHA:
        raise R9ContractError("approval text hash drift")
    if prereg.get("pilot_id") != PILOT_ID or prereg.get("status") != "PREREGISTERED_NO_EXECUTION":
        raise R9ContractError("preregistration drift")
    if approval.get("approval_id") != APPROVAL_ID or approval.get("reviewed_commit") != PREREGISTRATION_MERGE:
        raise R9ContractError("approval identity drift")
    if approval.get("exact_approval_text_sha256") != APPROVAL_SHA:
        raise R9ContractError("approval hash drift")
    if not all(value is False for value in approval.get("current_runtime_authority", {}).values()):
        raise R9ContractError("approval self-opens runtime")
    if impl.get("pilot_id") != PILOT_ID or impl.get("status") != "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION":
        raise R9ContractError("implementation identity drift")
    if impl.get("r9_preregistration_merge_commit") != PREREGISTRATION_MERGE:
        raise R9ContractError("implementation preregistration binding drift")
    if impl.get("approval_merge_commit") != APPROVAL_MERGE or impl.get("approval_text_sha256") != APPROVAL_SHA:
        raise R9ContractError("implementation approval binding drift")
    if impl.get("expected_canonical_implementation_commit") != "PENDING_CANONICAL_IMPLEMENTATION_MERGE":
        raise R9ContractError("implementation must remain pre-release snapshot")
    if impl.get("execution_release_present") is not False or impl.get("canonical_activation_present") is not False:
        raise R9ContractError("implementation snapshot contains later-stage authority")
    if not all(value is False for value in impl.get("current_runtime_authority", {}).values()):
        raise R9ContractError("implementation self-opens runtime")

    target = prereg.get("exact_future_network_target", {})
    exact_target = {
        "bucket": TARGET_BUCKET,
        "signing_region": SIGNING_REGION,
        "key": OBJECT_KEY,
        "expected_size_bytes": EXPECTED_SIZE,
        "expected_etag": EXPECTED_ETAG,
        "expected_compressed_sha256": EXPECTED_COMPRESSED_SHA,
        "expected_decompressed_byte_count": EXPECTED_DECOMPRESSED_BYTES,
        "expected_top_level_block_record_count": EXPECTED_BLOCK_COUNT,
        "expected_valid_event_pair_count": EXPECTED_EVENT_PAIR_COUNT,
    }
    if target != exact_target:
        raise R9ContractError("preregistered target drift")
    obj = impl.get("object", {})
    for key, expected in {
        "key": OBJECT_KEY,
        "expected_size_bytes": EXPECTED_SIZE,
        "expected_etag": EXPECTED_ETAG,
        "expected_compressed_sha256": EXPECTED_COMPRESSED_SHA,
        "expected_decompressed_byte_count": EXPECTED_DECOMPRESSED_BYTES,
        "expected_top_level_block_record_count": EXPECTED_BLOCK_COUNT,
        "expected_valid_event_pair_count": EXPECTED_EVENT_PAIR_COUNT,
        "required_leading_string_regex": "^0x[0-9a-f]{40}$",
    }.items():
        if obj.get(key) != expected:
            raise R9ContractError(f"implementation target drift: {key}")

    for source in (approval, impl):
        for key, expected in {
            "maximum_one_time_budget_eur": 0.10,
            "maximum_monthly_budget_eur": 0,
            "maximum_get_object_requests": 1,
            "maximum_requests_per_object": 1,
            "maximum_total_compressed_bytes": EXPECTED_SIZE,
            "maximum_total_decompressed_bytes": MAX_DECOMPRESSED_BYTES,
            "maximum_runtime_seconds": MAX_RUNTIME_SECONDS,
            "maximum_retries_per_request": 0,
        }.items():
            if source.get(key) != expected:
                raise R9ContractError(f"approved envelope drift: {key}")

    if impl.get("boundary_fixture_role") != "SERIALIZER_AND_FEATURE_PIPELINE_FIXTURE_ONLY":
        raise R9ContractError("fixture role drift")
    if impl.get("boundary_fixture_historical_representativeness_authorized") is not False:
        raise R9ContractError("fixture representativeness opened")
    if impl.get("canonical_cross_format_history_use_authorized") is not False:
        raise R9ContractError("canonical history use opened")
    if impl.get("selected_fill_fields_processed_transiently") != SELECTED_FIELDS:
        raise R9ContractError("selected field set drift")
    if impl.get("wallet_feature_fields_only") != OUTPUT_FIELDS:
        raise R9ContractError("output field set drift")
    if impl.get("wallet_address_normalization") != "LOWERCASE_EXACT_0X40HEX":
        raise R9ContractError("wallet normalization drift")
    if impl.get("decimal_output_encoding") != "CANONICAL_BASE10_STRING_NO_EXPONENT":
        raise R9ContractError("decimal encoding drift")
    if impl.get("wallet_feature_entry_cap") != MAX_ROWS or impl.get("wallet_feature_output_byte_cap") != MAX_OUTPUT_BYTES:
        raise R9ContractError("feature output cap drift")
    rules = impl.get("selected_field_rules", {})
    if rules.get("exact_decimal_arithmetic_required") is not True or rules.get("floating_point_aggregation_authorized") is not False:
        raise R9ContractError("decimal arithmetic drift")
    if rules.get("maximum_numeric_token_characters") != MAX_NUMERIC_CHARS:
        raise R9ContractError("numeric token cap drift")
    if not all(value is False for value in impl.get("forbidden_retention_authorizations", {}).values()):
        raise R9ContractError("forbidden retention opened")
    if not all(value is False for value in impl.get("semantic_boundaries", {}).values()):
        raise R9ContractError("semantic overclaim opened")
    if not all(value is False for value in impl.get("downstream_authorizations", {}).values()):
        raise R9ContractError("downstream authority opened")
    if not all(value is False for value in impl.get("trading_authorizations", {}).values()):
        raise R9ContractError("trading authority opened")
    if impl.get("s3_requests_executed") != 0 or impl.get("wallet_feature_rows_created") != 0 or impl.get("empirical_result") is not None:
        raise R9ContractError("implementation contains empirical result")

    if reuse.get("reused_role_arn") != ROLE_ARN or reuse.get("aws_iam_mutation_performed") is not False:
        raise R9ContractError("role reuse drift")
    session = reuse.get("r9_session_scope", {})
    if session.get("allowed_actions") != ["s3:GetObject"] or session.get("allowed_object_arns") != [OBJECT_ARN]:
        raise R9ContractError("R9 session scope drift")
    if reuse.get("current_runtime_authority") and not all(value is False for value in reuse["current_runtime_authority"].values()):
        raise R9ContractError("role reuse analysis self-opens runtime")


def _new_wallet_state() -> dict:
    return {
        "fill_count": 0,
        "first_fill_time": None,
        "last_fill_time": None,
        "coins": set(),
        "side_a_count": 0,
        "side_b_count": 0,
        "crossed_true_count": 0,
        "liquidation_associated_fill_count": 0,
        "tids": set(),
        "duplicate_tid_count": 0,
        "sum_notional": Decimal(0),
        "sum_closed_pnl": Decimal(0),
    }


def _tid_key(value: object) -> tuple[str, str]:
    if isinstance(value, bool) or value is None or isinstance(value, (dict, list)):
        raise R9FeatureUnresolved("tid has unsupported type")
    if isinstance(value, Decimal):
        if value != value.to_integral_value():
            raise R9FeatureUnresolved("tid decimal must be integral")
        return ("int", canonical_decimal(value))
    if isinstance(value, int):
        return ("int", str(value))
    if isinstance(value, str):
        if not value or len(value) > MAX_NUMERIC_CHARS:
            raise R9FeatureUnresolved("tid string invalid")
        return ("str", value)
    raise R9FeatureUnresolved("tid has unsupported type")


def aggregate_decompressed(payload: bytes) -> tuple[bytes, dict]:
    states: dict[str, dict] = defaultdict(_new_wallet_state)
    block_count = 0
    event_count = 0

    for raw_line in payload.splitlines():
        if not raw_line.strip():
            continue
        block_count += 1
        if block_count > MAX_BLOCKS:
            raise R9TransportIntegrityError("block record cap exceeded")
        if len(raw_line) > MAX_RECORD_BYTES:
            raise R9TransportIntegrityError("block record byte cap exceeded")
        try:
            text = raw_line.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise R9FeatureUnresolved("strict UTF-8 decode failed") from exc
        try:
            block = strict_loads(text)
        except R9JSONError as exc:
            raise R9FeatureUnresolved("strict JSON parse failed") from exc
        if not isinstance(block, dict):
            raise R9FeatureUnresolved("top-level block record is not object")
        for key, expected_type in (("local_time", str), ("block_time", str), ("events", list)):
            if not isinstance(block.get(key), expected_type):
                raise R9FeatureUnresolved(f"block field {key} has wrong type")
        number = block.get("block_number")
        if isinstance(number, bool) or not isinstance(number, int):
            raise R9FeatureUnresolved("block_number is not integer")

        events = block["events"]
        for pair in events:
            event_count += 1
            if event_count > MAX_EVENTS:
                raise R9TransportIntegrityError("event pair cap exceeded")
            if not isinstance(pair, list) or len(pair) != 2:
                raise R9FeatureUnresolved("event is not a two-element array")
            address, fill = pair
            if not isinstance(address, str) or ADDRESS_RE.fullmatch(address) is None:
                raise R9FeatureUnresolved("leading address fails lowercase 0x40hex contract")
            if not isinstance(fill, dict):
                raise R9FeatureUnresolved("fill payload is not object")

            for required in ("coin", "side", "time", "px", "sz", "closedPnl", "tid", "crossed"):
                if required not in fill:
                    raise R9FeatureUnresolved(f"required selected field absent: {required}")

            coin = fill["coin"]
            side = fill["side"]
            fill_time = fill["time"]
            crossed = fill["crossed"]
            if not isinstance(coin, str) or not coin:
                raise R9FeatureUnresolved("coin must be nonempty string")
            if side not in {"A", "B"}:
                raise R9FeatureUnresolved("side must be A or B")
            if isinstance(fill_time, bool) or not isinstance(fill_time, int) or fill_time < 0:
                raise R9FeatureUnresolved("time must be nonnegative integer")
            if not isinstance(crossed, bool):
                raise R9FeatureUnresolved("crossed must be boolean")

            px = _decimal(fill["px"], "px")
            sz = _decimal(fill["sz"], "sz")
            closed_pnl = _decimal(fill["closedPnl"], "closedPnl")
            tid = _tid_key(fill["tid"])

            state = states[address]
            state["fill_count"] += 1
            if state["first_fill_time"] is None or fill_time < state["first_fill_time"]:
                state["first_fill_time"] = fill_time
            if state["last_fill_time"] is None or fill_time > state["last_fill_time"]:
                state["last_fill_time"] = fill_time
            state["coins"].add(coin)
            if side == "A":
                state["side_a_count"] += 1
            else:
                state["side_b_count"] += 1
            if crossed:
                state["crossed_true_count"] += 1
            if fill.get("liquidation") is not None:
                state["liquidation_associated_fill_count"] += 1
            if tid in state["tids"]:
                state["duplicate_tid_count"] += 1
            else:
                state["tids"].add(tid)
            state["sum_notional"] += abs(px * sz)
            state["sum_closed_pnl"] += closed_pnl

    if block_count != EXPECTED_BLOCK_COUNT:
        raise R9TransportIntegrityError(f"top-level block count mismatch: {block_count}")
    if event_count != EXPECTED_EVENT_PAIR_COUNT:
        raise R9TransportIntegrityError(f"valid event pair count mismatch: {event_count}")
    if len(states) == 0 or len(states) > MAX_ROWS:
        raise R9TransportIntegrityError("wallet feature row count outside cap")

    rows: list[bytes] = []
    sum_fill_count = 0
    sum_side_count = 0
    for address in sorted(states):
        state = states[address]
        fill_count = state["fill_count"]
        side_count = state["side_a_count"] + state["side_b_count"]
        if fill_count <= 0 or side_count != fill_count:
            raise R9FeatureUnresolved("per-wallet fill/side conservation failed")
        first_fill = state["first_fill_time"]
        last_fill = state["last_fill_time"]
        if first_fill is None or last_fill is None or first_fill > last_fill:
            raise R9FeatureUnresolved("per-wallet time range invalid")
        notional = state["sum_notional"]
        if notional < 0:
            raise R9FeatureUnresolved("notional proxy became negative")
        row = {
            "wallet_address": address,
            "fill_count": fill_count,
            "first_fill_time": first_fill,
            "last_fill_time": last_fill,
            "distinct_coin_count": len(state["coins"]),
            "side_a_count": state["side_a_count"],
            "side_b_count": state["side_b_count"],
            "crossed_true_count": state["crossed_true_count"],
            "liquidation_associated_fill_count": state["liquidation_associated_fill_count"],
            "duplicate_tid_count": state["duplicate_tid_count"],
            "sum_abs_px_times_sz_notional_proxy": canonical_decimal(notional),
            "sum_closed_pnl_fill_statistic": canonical_decimal(state["sum_closed_pnl"]),
        }
        if list(row.keys()) != OUTPUT_FIELDS:
            raise R9ContractError("output field order drift")
        encoded = json.dumps(row, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"
        rows.append(encoded)
        sum_fill_count += fill_count
        sum_side_count += side_count

    output = b"".join(rows)
    if len(output) > MAX_OUTPUT_BYTES:
        raise R9TransportIntegrityError("wallet feature output byte cap exceeded")
    if sum_fill_count != EXPECTED_EVENT_PAIR_COUNT or sum_side_count != EXPECTED_EVENT_PAIR_COUNT:
        raise R9FeatureUnresolved("global conservation failed")

    return output, {
        "top_level_block_record_count": block_count,
        "valid_event_pair_count": event_count,
        "wallet_feature_row_count": len(states),
        "sum_fill_count": sum_fill_count,
        "sum_side_count": sum_side_count,
        "wallet_feature_fields_only": OUTPUT_FIELDS,
        "wallet_feature_format": "UTF8_NDJSON",
        "wallet_feature_sort_order": "WALLET_ADDRESS_LEXICOGRAPHIC_ASCENDING",
        "wallet_feature_bytes": len(output),
        "wallet_feature_sha256": sha256_bytes(output),
        "decimal_output_encoding": "CANONICAL_BASE10_STRING_NO_EXPONENT",
    }


def decompress_lz4(raw: bytes) -> bytes:
    try:
        return b"".join(iter_lz4_frame(raw, MAX_DECOMPRESSED_BYTES))
    except LZ4FrameLimit as exc:
        raise R9TransportIntegrityError(exc.status) from exc
    except LZ4FrameError as exc:
        raise R9TransportIntegrityError(str(exc)) from exc


def _base_result() -> dict:
    return {
        "schema_version": "1.0",
        "pilot_id": PILOT_ID,
        "object_key": OBJECT_KEY,
        "expected_content_length": EXPECTED_SIZE,
        "expected_etag": EXPECTED_ETAG,
        "expected_compressed_sha256": EXPECTED_COMPRESSED_SHA,
        "expected_decompressed_byte_count": EXPECTED_DECOMPRESSED_BYTES,
        "expected_top_level_block_record_count": EXPECTED_BLOCK_COUNT,
        "expected_valid_event_pair_count": EXPECTED_EVENT_PAIR_COUNT,
        "boundary_fixture_role": "SERIALIZER_AND_FEATURE_PIPELINE_FIXTURE_ONLY",
        "boundary_fixture_historical_representativeness_inferred": False,
        "canonical_cross_format_history_used": False,
        "request_attempt_count": 0,
        "s3_http_request_count": 0,
        "successful_request_count": 0,
        "failed_request_count": 0,
        "retries_used": 0,
        "http_redirects_followed": False,
        "requester_pays_requested": False,
        "compressed_bytes": 0,
        "compressed_sha256": None,
        "decompressed_bytes": 0,
        "wallet_feature_retained": False,
        "wallet_feature_summary": None,
        "selected_fill_fields_processed": SELECTED_FIELDS,
        "raw_compressed_object_persisted": False,
        "raw_decompressed_payload_retained": False,
        "raw_block_records_retained": False,
        "raw_event_pairs_retained": False,
        "raw_fill_objects_retained": False,
        "coin_values_retained": False,
        "side_values_retained": False,
        "individual_time_values_retained": False,
        "individual_price_values_retained": False,
        "individual_size_values_retained": False,
        "individual_closed_pnl_values_retained": False,
        "trade_id_values_retained": False,
        "crossed_values_retained": False,
        "liquidation_payload_values_retained": False,
        "fee_values_processed": False,
        "fee_token_values_processed": False,
        "dir_values_processed": False,
        "start_position_values_processed": False,
        "transaction_hashes_processed": False,
        "order_ids_processed": False,
        "client_order_ids_processed": False,
        "historical_multi_hour_ingestion_performed": False,
        "legacy_modern_merged_history_performed": False,
        "public_api_enrichment_performed": False,
        "entity_clustering_performed": False,
        "wallet_ranking_performed": False,
        "candidate_shortlisting_performed": False,
        "copyability_analysis_performed": False,
        "pnl_or_alpha_analysis_performed": False,
        "market_data_ingested": False,
        "strategy_inference_performed": False,
        "sum_closed_pnl_interpreted_as_exact_account_return": False,
        "sum_closed_pnl_used_as_wallet_ranking_score": False,
        "notional_proxy_interpreted_as_copyable_notional": False,
        "failure_class": None,
        "observed_at_utc": None,
        "runtime_seconds": None,
        "terminal_status": None,
        "technical_result": None,
        "research_conclusion": None,
    }


def execute(
    transport: Callable[[str, str, dict[str, str], int, float], tuple[int, dict[str, str], bytes]] = r8a_transport.https_transport,
    decompressor: Callable[[bytes], bytes] = decompress_lz4,
    env: dict[str, str] | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> tuple[dict, bytes, int]:
    started = time.monotonic()
    result = _base_result()
    features = b""
    try:
        validate_static_inputs()
        request_time = now()
        host, path, headers = r8a_transport.build_signed_request(request_time, env)
        if host != "hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com":
            raise R9ContractError("transport host drift")
        if path != "/node_fills_by_block/hourly/20250727/8.lz4":
            raise R9ContractError("transport path drift")
        if headers.get("If-Match") != EXPECTED_ETAG or headers.get("x-amz-request-payer") != "requester":
            raise R9ContractError("signed request guard drift")

        result["request_attempt_count"] = 1
        result["s3_http_request_count"] = 1
        result["requester_pays_requested"] = True
        remaining = max(1.0, MAX_RUNTIME_SECONDS - (time.monotonic() - started))
        status, response_headers, compressed = transport(host, path, headers, EXPECTED_SIZE, remaining)
        if status != 200:
            result["failed_request_count"] = 1
            raise R9TransportIntegrityError(f"S3 HTTP status {status}")
        result["successful_request_count"] = 1

        if response_headers.get("x-amz-request-charged", "").lower() != "requester":
            raise R9TransportIntegrityError("missing requester-charged response header")
        if response_headers.get("etag") != EXPECTED_ETAG:
            raise R9TransportIntegrityError("response ETag mismatch")
        try:
            content_length = int(response_headers.get("content-length", ""))
        except ValueError as exc:
            raise R9TransportIntegrityError("invalid response content-length") from exc
        if content_length != EXPECTED_SIZE or len(compressed) != EXPECTED_SIZE:
            raise R9TransportIntegrityError("compressed content length mismatch")
        result["compressed_bytes"] = len(compressed)
        result["compressed_sha256"] = sha256_bytes(compressed)
        if result["compressed_sha256"] != EXPECTED_COMPRESSED_SHA:
            raise R9TransportIntegrityError("compressed SHA-256 mismatch")

        decompressed = decompressor(compressed)
        result["decompressed_bytes"] = len(decompressed)
        if len(decompressed) != EXPECTED_DECOMPRESSED_BYTES:
            raise R9TransportIntegrityError("decompressed byte count mismatch")

        try:
            features, summary = aggregate_decompressed(decompressed)
        except R9FeatureUnresolved as exc:
            features = b""
            result["failure_class"] = str(exc)
            result["terminal_status"] = "R9_MODERN_WALLET_FEATURE_STUDY_COMPLETE"
            result["technical_result"] = "MODERN_WALLET_FEATURE_PIPELINE_UNRESOLVED"
            result["research_conclusion"] = "MODERN_WALLET_FEATURE_PIPELINE_UNRESOLVED"
            result["observed_at_utc"] = utc_now()
            result["runtime_seconds"] = round(time.monotonic() - started, 6)
            return result, features, 0

        result["wallet_feature_retained"] = True
        result["wallet_feature_summary"] = summary
        result["terminal_status"] = "R9_MODERN_WALLET_FEATURE_STUDY_COMPLETE"
        result["technical_result"] = "MODERN_WALLET_FEATURE_PIPELINE_COMPLETE"
        result["research_conclusion"] = "MODERN_WALLET_FEATURE_PIPELINE_COMPLETE"
        result["observed_at_utc"] = utc_now()
        result["runtime_seconds"] = round(time.monotonic() - started, 6)
        return result, features, 0
    except (R9ContractError, R9TransportIntegrityError) as exc:
        features = b""
        result["failure_class"] = str(exc)
        if result["request_attempt_count"] and not result["successful_request_count"]:
            result["failed_request_count"] = 1
        result["terminal_status"] = "R9_TRANSPORT_OR_INTEGRITY_FAIL"
        result["technical_result"] = "R9_TRANSPORT_OR_INTEGRITY_FAIL"
        result["research_conclusion"] = "R9_TRANSPORT_OR_INTEGRITY_FAIL"
        result["observed_at_utc"] = utc_now()
        result["runtime_seconds"] = round(time.monotonic() - started, 6)
        return result, features, 83


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-output", required=True)
    parser.add_argument("--wallet-feature-output", required=True)
    args = parser.parse_args(argv)
    result, features, rc = execute()
    Path(args.result_output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    Path(args.wallet_feature_output).write_bytes(features)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
