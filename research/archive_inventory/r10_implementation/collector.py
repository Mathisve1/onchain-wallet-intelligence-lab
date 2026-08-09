from __future__ import annotations

import argparse
import hashlib
import hmac
import http.client
import json
import os
import re
import ssl
import time
import urllib.parse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, Iterable

from research.archive_inventory.r4.lz4_frame import LZ4FrameError, LZ4FrameLimit, iter_lz4_frame

ROOT = Path(__file__).resolve().parents[3]
R10 = ROOT / "research/archive_inventory/r10"
R10_APPROVAL = ROOT / "research/archive_inventory/r10_approval"
IMPL = ROOT / "research/archive_inventory/r10_implementation"
PREREGISTRATION = R10 / "POST_BOUNDARY_MULTI_HOUR_FEATURE_R10_CONTRACT.json"
APPROVAL_JSON = R10_APPROVAL / "APPROVE_HL_ARCHIVE_POST_BOUNDARY_MULTI_HOUR_FEATURE_R10_001.json"
APPROVAL_TEXT = R10_APPROVAL / "APPROVE_HL_ARCHIVE_POST_BOUNDARY_MULTI_HOUR_FEATURE_R10_001.txt"
IMPLEMENTATION = IMPL / "R10_IMPLEMENTATION_CONTRACT.json"

PILOT_ID = "HL-ARCHIVE-POST-BOUNDARY-MULTI-HOUR-FEATURE-R10-001"
PREREGISTRATION_MERGE = "37e4486a7f68982feafcb361bd40dffd546def05"
APPROVAL_MERGE = "92761986d8dc6bf818eebf7dc0411d24649a27df"
APPROVAL_ID = "APPROVE_HL_ARCHIVE_POST_BOUNDARY_MULTI_HOUR_FEATURE_R10_001"
APPROVAL_SHA = "ec631e7e6d40cb63383afd012a989419f97cd603ff144e4c5dfb90c18ff90882"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
TARGET_BUCKET = "hl-mainnet-node-data"
SIGNING_REGION = "ap-northeast-1"
REGIONAL_ENDPOINT = f"{TARGET_BUCKET}.s3.{SIGNING_REGION}.amazonaws.com"
SERVICE = "s3"
EMPTY_PAYLOAD_SHA256 = hashlib.sha256(b"").hexdigest()
MAX_REQUESTS = 6
MAX_TOTAL_COMPRESSED_BYTES = 120_999_698
MAX_INDIVIDUAL_COMPRESSED_BYTES = 21_672_141
MAX_TOTAL_DECOMPRESSED_BYTES = 1_073_741_824
MAX_INDIVIDUAL_DECOMPRESSED_BYTES = 268_435_456
MAX_RUNTIME_SECONDS = 300
MAX_RECORD_BYTES = 16_777_216
MAX_BLOCKS = 500_000
MAX_EVENTS = 2_000_000
MAX_ROWS = 1_000_000
MAX_OUTPUT_BYTES = 67_108_864
MAX_NUMERIC_CHARS = 128
ADDRESS_RE = re.compile(r"^0x[0-9a-f]{40}$")
SELECTED_FIELDS = ["coin", "side", "time", "px", "sz", "closedPnl", "tid", "crossed", "liquidation"]
OUTPUT_FIELDS = [
    "wallet_address",
    "fill_count",
    "active_hour_count",
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
TARGETS = [
    {"path_hour_utc": "2025-07-27T09:00:00Z", "key": "node_fills_by_block/hourly/20250727/9.lz4", "size": 18_147_822, "etag": '"5a9941a240118a57f77a4c3ee95b8430-3"'},
    {"path_hour_utc": "2025-07-27T10:00:00Z", "key": "node_fills_by_block/hourly/20250727/10.lz4", "size": 21_349_239, "etag": '"cb25fba5dc3be80fd8c46dde03144655-3"'},
    {"path_hour_utc": "2025-07-27T11:00:00Z", "key": "node_fills_by_block/hourly/20250727/11.lz4", "size": 17_582_600, "etag": '"758da733bb2d3913d0fdd8088b6fb63d-3"'},
    {"path_hour_utc": "2025-07-27T12:00:00Z", "key": "node_fills_by_block/hourly/20250727/12.lz4", "size": 21_672_141, "etag": '"d6ee46b1bdfad4026e21d4285ed0cbc5-3"'},
    {"path_hour_utc": "2025-07-27T13:00:00Z", "key": "node_fills_by_block/hourly/20250727/13.lz4", "size": 20_840_630, "etag": '"c3c9db0101ff278b5ced13ab278a2b85-3"'},
    {"path_hour_utc": "2025-07-27T14:00:00Z", "key": "node_fills_by_block/hourly/20250727/14.lz4", "size": 21_407_266, "etag": '"3c6ab944be1ed8bd12932eb390267a21-3"'},
]


class R10ContractError(RuntimeError):
    pass


class R10TransportIntegrityError(RuntimeError):
    pass


class R10FeatureUnresolved(RuntimeError):
    pass


class R10JSONError(ValueError):
    pass


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise R10ContractError(f"JSON root must be object: {path}")
    return value


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _strict_object(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise R10JSONError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_nonfinite(_token: str) -> object:
    raise R10JSONError("non-finite JSON constant")


def strict_loads(text: str) -> object:
    try:
        return json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_float=Decimal,
            parse_constant=_reject_nonfinite,
        )
    except (json.JSONDecodeError, InvalidOperation) as exc:
        raise R10JSONError(str(exc)) from exc


def _decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise R10FeatureUnresolved(f"{field} is not decimal-compatible")
    if isinstance(value, Decimal):
        token = str(value)
    elif isinstance(value, int):
        token = str(value)
    elif isinstance(value, str):
        token = value.strip()
    else:
        raise R10FeatureUnresolved(f"{field} has unsupported numeric type")
    if not token or len(token) > MAX_NUMERIC_CHARS:
        raise R10FeatureUnresolved(f"{field} token length invalid")
    try:
        parsed = Decimal(token)
    except InvalidOperation as exc:
        raise R10FeatureUnresolved(f"{field} invalid decimal") from exc
    if not parsed.is_finite():
        raise R10FeatureUnresolved(f"{field} non-finite decimal")
    return parsed


def canonical_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise R10FeatureUnresolved("non-finite aggregate")
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in {"", "-0", "+0"}:
        return "0"
    return text


def _tid_key(value: object) -> tuple[str, str]:
    if isinstance(value, bool) or value is None or isinstance(value, (dict, list)):
        raise R10FeatureUnresolved("tid has unsupported type")
    if isinstance(value, Decimal):
        if value != value.to_integral_value():
            raise R10FeatureUnresolved("tid decimal must be integral")
        return ("int", canonical_decimal(value))
    if isinstance(value, int):
        return ("int", str(value))
    if isinstance(value, str):
        if not value or len(value) > MAX_NUMERIC_CHARS:
            raise R10FeatureUnresolved("tid string invalid")
        return ("str", value)
    raise R10FeatureUnresolved("tid has unsupported type")


def validate_static_inputs() -> None:
    prereg = load_json(PREREGISTRATION)
    approval = load_json(APPROVAL_JSON)
    impl = load_json(IMPLEMENTATION)
    if sha256_bytes(APPROVAL_TEXT.read_bytes()) != APPROVAL_SHA:
        raise R10ContractError("approval text hash drift")
    if prereg.get("pilot_id") != PILOT_ID or prereg.get("status") != "PREREGISTERED_NO_EXECUTION":
        raise R10ContractError("preregistration drift")
    if prereg.get("parent_r9_evidence_commit") != "bdbcb94305670beda4cf5629951ee8c9e41c7495":
        raise R10ContractError("R9 lineage drift")
    if approval.get("approval_id") != APPROVAL_ID or approval.get("reviewed_commit") != PREREGISTRATION_MERGE:
        raise R10ContractError("approval identity drift")
    if approval.get("exact_approval_text_sha256") != APPROVAL_SHA:
        raise R10ContractError("approval hash drift")
    if approval.get("execution_authorized_by_this_approval") is not False:
        raise R10ContractError("approval self-opens execution")
    if not all(value is False for value in approval.get("current_runtime_authority", {}).values()):
        raise R10ContractError("approval self-opens runtime")
    if impl.get("pilot_id") != PILOT_ID or impl.get("status") != "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION":
        raise R10ContractError("implementation identity drift")
    if impl.get("r10_preregistration_merge_commit") != PREREGISTRATION_MERGE:
        raise R10ContractError("implementation preregistration binding drift")
    if impl.get("r10_approval_merge_commit") != APPROVAL_MERGE or impl.get("approval_text_sha256") != APPROVAL_SHA:
        raise R10ContractError("implementation approval binding drift")
    if impl.get("dedicated_role_arn") != ROLE_ARN:
        raise R10ContractError("dedicated role binding drift")
    if impl.get("expected_canonical_implementation_commit") != "PENDING_CANONICAL_IMPLEMENTATION_MERGE":
        raise R10ContractError("implementation snapshot must remain pre-release")
    if impl.get("role_creation_performed") is not False or impl.get("sts_preflight_completed") is not False:
        raise R10ContractError("implementation contains operator/runtime evidence")
    if not all(value is False for value in impl.get("current_runtime_authority", {}).values()):
        raise R10ContractError("implementation self-opens runtime")
    if not all(value is False for value in impl.get("downstream_authorizations", {}).values()):
        raise R10ContractError("implementation opens downstream authority")
    if not all(value is False for value in impl.get("trading_authorizations", {}).values()):
        raise R10ContractError("implementation opens trading authority")

    targets = prereg.get("exact_future_network_targets")
    approved = approval.get("approved_future_objects")
    installed = impl.get("exact_network_targets")
    if not isinstance(targets, list) or not isinstance(approved, list) or not isinstance(installed, list):
        raise R10ContractError("target arrays absent")
    if len(targets) != len(approved) != len(installed):
        raise R10ContractError("target count drift")
    if len(targets) != MAX_REQUESTS:
        raise R10ContractError("target count must be six")
    for index, frozen in enumerate(TARGETS):
        p = targets[index]
        a = approved[index]
        i = installed[index]
        if p.get("path_hour_utc") != frozen["path_hour_utc"] or p.get("key") != frozen["key"]:
            raise R10ContractError("preregistered target drift")
        if p.get("expected_size_bytes") != frozen["size"] or p.get("expected_etag") != frozen["etag"]:
            raise R10ContractError("preregistered object identity drift")
        if a != {"key": frozen["key"], "size_bytes": frozen["size"], "etag": frozen["etag"]}:
            raise R10ContractError("approved target drift")
        if i != {"path_hour_utc": frozen["path_hour_utc"], "key": frozen["key"], "expected_size_bytes": frozen["size"], "expected_etag": frozen["etag"]}:
            raise R10ContractError("implementation target drift")

    envelope = impl.get("execution_envelope", {})
    expected_envelope = {
        "maximum_one_time_budget_eur": 0.10,
        "maximum_monthly_budget_eur": 0,
        "maximum_get_object_requests": 6,
        "maximum_requests_per_object": 1,
        "maximum_total_compressed_bytes": MAX_TOTAL_COMPRESSED_BYTES,
        "maximum_individual_compressed_bytes": MAX_INDIVIDUAL_COMPRESSED_BYTES,
        "maximum_total_decompressed_bytes": MAX_TOTAL_DECOMPRESSED_BYTES,
        "maximum_individual_decompressed_bytes": MAX_INDIVIDUAL_DECOMPRESSED_BYTES,
        "maximum_runtime_seconds": MAX_RUNTIME_SECONDS,
        "maximum_retries_per_request": 0,
        "request_order": "PATH_HOUR_ASCENDING",
        "stop_after_first_failed_or_mismatched_object": True,
        "requester_pays_required": True,
        "if_match_etag_required": True,
        "exact_content_length_required": True,
        "exact_response_etag_required": True,
        "compressed_sha256_computed_and_retained_per_object": True,
        "http_redirect_following_authorized": False,
        "head_object_authorized": False,
        "range_get_authorized": False,
        "list_objects_v2_authorized": False,
        "list_object_versions_authorized": False,
        "list_all_my_buckets_authorized": False,
        "get_object_attributes_authorized": False,
        "get_object_version_authorized": False,
    }
    if envelope != expected_envelope:
        raise R10ContractError("implementation execution envelope drift")


def _aws_quote_path(key: str) -> str:
    return "/" + urllib.parse.quote(key, safe="/-_.~")


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def build_signed_request(target: dict, request_time: datetime, env: dict[str, str] | None = None) -> tuple[str, str, dict[str, str]]:
    source = os.environ if env is None else env
    access_key = source.get("AWS_ACCESS_KEY_ID")
    secret_key = source.get("AWS_SECRET_ACCESS_KEY")
    session_token = source.get("AWS_SESSION_TOKEN")
    if not access_key or not secret_key or not session_token:
        raise R10ContractError("temporary AWS credentials missing")
    if request_time.tzinfo is None:
        raise R10ContractError("signing time must be timezone-aware")
    stamp = request_time.astimezone(timezone.utc)
    amz_date = stamp.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = stamp.strftime("%Y%m%d")
    canonical_uri = _aws_quote_path(target["key"])
    canonical_headers = (
        f"host:{REGIONAL_ENDPOINT}\n"
        f"if-match:{target['etag']}\n"
        f"x-amz-content-sha256:{EMPTY_PAYLOAD_SHA256}\n"
        f"x-amz-date:{amz_date}\n"
        "x-amz-request-payer:requester\n"
        f"x-amz-security-token:{session_token}\n"
    )
    signed_headers = "host;if-match;x-amz-content-sha256;x-amz-date;x-amz-request-payer;x-amz-security-token"
    canonical_request = "\n".join(["GET", canonical_uri, "", canonical_headers, signed_headers, EMPTY_PAYLOAD_SHA256])
    scope = f"{date_stamp}/{SIGNING_REGION}/{SERVICE}/aws4_request"
    string_to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical_request.encode()).hexdigest()])
    k_date = _sign(("AWS4" + secret_key).encode(), date_stamp)
    k_region = _sign(k_date, SIGNING_REGION)
    k_service = _sign(k_region, SERVICE)
    k_signing = _sign(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()
    authorization = f"AWS4-HMAC-SHA256 Credential={access_key}/{scope},SignedHeaders={signed_headers},Signature={signature}"
    return REGIONAL_ENDPOINT, canonical_uri, {
        "Host": REGIONAL_ENDPOINT,
        "If-Match": target["etag"],
        "Authorization": authorization,
        "x-amz-content-sha256": EMPTY_PAYLOAD_SHA256,
        "x-amz-date": amz_date,
        "x-amz-request-payer": "requester",
        "x-amz-security-token": session_token,
    }


def https_transport(host: str, path: str, headers: dict[str, str], expected_size: int, timeout_seconds: float) -> tuple[int, dict[str, str], bytes]:
    connection = http.client.HTTPSConnection(host, timeout=timeout_seconds, context=ssl.create_default_context())
    try:
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        response_headers = {name.lower(): value.strip() for name, value in response.getheaders()}
        if response.status != 200:
            return response.status, response_headers, b""
        return response.status, response_headers, response.read(expected_size + 1)
    finally:
        connection.close()


def _new_wallet_state() -> dict:
    return {
        "fill_count": 0,
        "active_hours": set(),
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


class MultiHourAggregator:
    def __init__(self) -> None:
        self.states: dict[str, dict] = defaultdict(_new_wallet_state)
        self.total_blocks = 0
        self.total_events = 0
        self.total_duplicates = 0

    def add_line(self, raw_line: bytes, target: dict, per_hour: dict) -> None:
        if raw_line.endswith(b"\r"):
            raw_line = raw_line[:-1]
        if not raw_line.strip():
            return
        if len(raw_line) > MAX_RECORD_BYTES:
            raise R10FeatureUnresolved("block record byte cap exceeded")
        try:
            block = strict_loads(raw_line.decode("utf-8", errors="strict"))
        except (UnicodeDecodeError, R10JSONError) as exc:
            raise R10FeatureUnresolved("strict modern block parse failed") from exc
        if not isinstance(block, dict):
            raise R10FeatureUnresolved("top-level record is not object")
        required = {"local_time": str, "block_time": str, "block_number": int, "events": list}
        for key, expected_type in required.items():
            field = block.get(key)
            if expected_type is int:
                if isinstance(field, bool) or not isinstance(field, int):
                    raise R10FeatureUnresolved(f"block field type mismatch: {key}")
            elif not isinstance(field, expected_type):
                raise R10FeatureUnresolved(f"block field type mismatch: {key}")
        self.total_blocks += 1
        per_hour["block_record_count"] += 1
        if self.total_blocks > MAX_BLOCKS:
            raise R10FeatureUnresolved("global block cap exceeded")

        start = parse_utc(target["path_hour_utc"])
        start_ms = int(start.timestamp() * 1000)
        end_ms = int((start + timedelta(hours=1)).timestamp() * 1000)
        for pair in block["events"]:
            self.total_events += 1
            per_hour["event_pair_count"] += 1
            if self.total_events > MAX_EVENTS:
                raise R10FeatureUnresolved("global event-pair cap exceeded")
            if not (isinstance(pair, list) and len(pair) == 2 and isinstance(pair[0], str) and isinstance(pair[1], dict)):
                raise R10FeatureUnresolved("event differs from [string, object] contract")
            address, fill = pair
            if ADDRESS_RE.fullmatch(address) is None:
                raise R10FeatureUnresolved("leading string violates lowercase address contract")
            for required_field in ("coin", "side", "time", "px", "sz", "closedPnl", "tid", "crossed"):
                if required_field not in fill:
                    raise R10FeatureUnresolved(f"required selected field absent: {required_field}")
            coin = fill["coin"]
            side = fill["side"]
            fill_time = fill["time"]
            crossed = fill["crossed"]
            if not isinstance(coin, str) or not coin:
                raise R10FeatureUnresolved("coin must be nonempty string")
            if side not in {"A", "B"}:
                raise R10FeatureUnresolved("side must be A or B")
            if isinstance(fill_time, bool) or not isinstance(fill_time, int) or fill_time < 0:
                raise R10FeatureUnresolved("fill time must be nonnegative integer")
            if not (start_ms <= fill_time < end_ms):
                per_hour["path_hour_alignment_violation_count"] += 1
                raise R10FeatureUnresolved("fill time lies outside source path hour")
            if not isinstance(crossed, bool):
                raise R10FeatureUnresolved("crossed must be boolean")
            px = _decimal(fill["px"], "px")
            sz = _decimal(fill["sz"], "sz")
            closed_pnl = _decimal(fill["closedPnl"], "closedPnl")
            tid = _tid_key(fill["tid"])

            state = self.states[address]
            state["fill_count"] += 1
            state["active_hours"].add(target["path_hour_utc"])
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
                self.total_duplicates += 1
            else:
                state["tids"].add(tid)
            state["sum_notional"] += abs(px * sz)
            state["sum_closed_pnl"] += closed_pnl
            if len(self.states) > MAX_ROWS:
                raise R10FeatureUnresolved("wallet row cap exceeded")

    def render(self) -> tuple[bytes, dict]:
        if self.total_events < 1 or not self.states:
            raise R10FeatureUnresolved("multi-hour aggregate is empty")
        if self.total_duplicates != 0:
            raise R10FeatureUnresolved("duplicate wallet+tid observations require investigation; blind deduplication forbidden")
        output = bytearray()
        sum_fill_count = 0
        sum_side_count = 0
        for address in sorted(self.states):
            state = self.states[address]
            fill_count = state["fill_count"]
            side_count = state["side_a_count"] + state["side_b_count"]
            if fill_count <= 0 or side_count != fill_count:
                raise R10FeatureUnresolved("per-wallet fill/side conservation failed")
            first_fill = state["first_fill_time"]
            last_fill = state["last_fill_time"]
            if first_fill is None or last_fill is None or first_fill > last_fill:
                raise R10FeatureUnresolved("per-wallet time range invalid")
            active_hours = len(state["active_hours"])
            if not 1 <= active_hours <= MAX_REQUESTS:
                raise R10FeatureUnresolved("active-hour count outside approved range")
            row = {
                "wallet_address": address,
                "fill_count": fill_count,
                "active_hour_count": active_hours,
                "first_fill_time": first_fill,
                "last_fill_time": last_fill,
                "distinct_coin_count": len(state["coins"]),
                "side_a_count": state["side_a_count"],
                "side_b_count": state["side_b_count"],
                "crossed_true_count": state["crossed_true_count"],
                "liquidation_associated_fill_count": state["liquidation_associated_fill_count"],
                "duplicate_tid_count": state["duplicate_tid_count"],
                "sum_abs_px_times_sz_notional_proxy": canonical_decimal(state["sum_notional"]),
                "sum_closed_pnl_fill_statistic": canonical_decimal(state["sum_closed_pnl"]),
            }
            if list(row.keys()) != OUTPUT_FIELDS:
                raise R10ContractError("output field order drift")
            encoded = (json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
            if len(output) + len(encoded) > MAX_OUTPUT_BYTES:
                raise R10FeatureUnresolved("wallet feature output byte cap exceeded")
            output.extend(encoded)
            sum_fill_count += fill_count
            sum_side_count += side_count
        if sum_fill_count != self.total_events or sum_side_count != self.total_events:
            raise R10FeatureUnresolved("global fill/side conservation failed")
        rendered = bytes(output)
        return rendered, {
            "wallet_feature_row_count": len(self.states),
            "sum_fill_count": sum_fill_count,
            "sum_side_count": sum_side_count,
            "duplicate_wallet_tid_count": self.total_duplicates,
            "wallet_feature_sha256": sha256_bytes(rendered),
            "wallet_feature_bytes": len(rendered),
            "wallet_feature_fields_only": OUTPUT_FIELDS,
            "wallet_feature_format": "UTF8_NDJSON",
            "wallet_feature_sort_order": "WALLET_ADDRESS_LEXICOGRAPHIC_ASCENDING",
            "decimal_output_encoding": "CANONICAL_BASE10_STRING_NO_EXPONENT",
        }


def aggregate_lz4_object(compressed: bytes, target: dict, aggregate: MultiHourAggregator) -> dict:
    per_hour = {
        "path_hour_utc": target["path_hour_utc"],
        "object_key": target["key"],
        "expected_etag": target["etag"],
        "expected_content_length": target["size"],
        "observed_content_length": len(compressed),
        "compressed_sha256": sha256_bytes(compressed),
        "decompressed_byte_count": 0,
        "block_record_count": 0,
        "event_pair_count": 0,
        "path_hour_alignment_violation_count": 0,
    }
    pending = bytearray()
    try:
        chunks: Iterable[bytes] = iter_lz4_frame(compressed, MAX_INDIVIDUAL_DECOMPRESSED_BYTES)
        for chunk in chunks:
            per_hour["decompressed_byte_count"] += len(chunk)
            if per_hour["decompressed_byte_count"] > MAX_INDIVIDUAL_DECOMPRESSED_BYTES:
                raise R10TransportIntegrityError("individual decompressed byte cap exceeded")
            pending.extend(chunk)
            while True:
                newline = pending.find(b"\n")
                if newline < 0:
                    break
                line = bytes(pending[:newline])
                del pending[: newline + 1]
                aggregate.add_line(line, target, per_hour)
            if len(pending) > MAX_RECORD_BYTES:
                raise R10FeatureUnresolved("record byte cap exceeded before newline")
        if pending:
            aggregate.add_line(bytes(pending), target, per_hour)
    except LZ4FrameLimit as exc:
        raise R10TransportIntegrityError(exc.status) from exc
    except LZ4FrameError as exc:
        raise R10TransportIntegrityError(str(exc)) from exc
    if per_hour["path_hour_alignment_violation_count"] != 0:
        raise R10FeatureUnresolved("path-hour alignment violations observed")
    if per_hour["block_record_count"] < 1 or per_hour["event_pair_count"] < 1:
        raise R10FeatureUnresolved("hour has no parsed blocks or events")
    return per_hour


def _base_result() -> dict:
    return {
        "schema_version": "1.0",
        "pilot_id": PILOT_ID,
        "observed_at_utc": None,
        "terminal_status": None,
        "technical_result": None,
        "research_conclusion": None,
        "request_attempt_count": 0,
        "s3_http_request_count": 0,
        "successful_request_count": 0,
        "failed_request_count": 0,
        "retries_used": 0,
        "http_redirects_followed": False,
        "requester_pays_requested": True,
        "completed_hour_count": 0,
        "per_hour_summaries": [],
        "total_compressed_bytes": 0,
        "total_decompressed_bytes": 0,
        "aggregate_wallet_feature_summary": None,
        "wallet_feature_retained": False,
        "raw_compressed_objects_retained": False,
        "raw_decompressed_payloads_retained": False,
        "raw_block_records_retained": False,
        "raw_event_pairs_retained": False,
        "raw_fill_objects_retained": False,
        "individual_selected_values_retained": False,
        "historical_window_beyond_six_hours_performed": False,
        "full_population_historical_ingestion_performed": False,
        "legacy_modern_merged_history_performed": False,
        "public_api_enrichment_performed": False,
        "entity_clustering_performed": False,
        "wallet_ranking_performed": False,
        "candidate_shortlisting_performed": False,
        "pnl_or_alpha_analysis_performed": False,
        "copyability_analysis_performed": False,
        "market_data_ingested": False,
        "strategy_inference_performed": False,
        "sum_closed_pnl_interpreted_as_exact_account_return": False,
        "sum_closed_pnl_used_as_wallet_ranking_score": False,
        "notional_proxy_interpreted_as_copyable_notional": False,
        "active_hour_count_interpreted_as_wallet_quality_score": False,
        "failure_class": None,
        "runtime_seconds": None,
    }


def execute(
    transport: Callable[[str, str, dict[str, str], int, float], tuple[int, dict[str, str], bytes]] = https_transport,
    request_time: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    env: dict[str, str] | None = None,
) -> tuple[int, dict, bytes]:
    validate_static_inputs()
    started = time.monotonic()
    result = _base_result()
    aggregate = MultiHourAggregator()
    output = b""
    try:
        for target in TARGETS:
            if result["request_attempt_count"] >= MAX_REQUESTS:
                raise R10TransportIntegrityError("request cap reached")
            if time.monotonic() - started >= MAX_RUNTIME_SECONDS:
                raise R10TransportIntegrityError("runtime cap reached before next object")
            host, path, headers = build_signed_request(target, request_time(), env)
            if host != REGIONAL_ENDPOINT or path != _aws_quote_path(target["key"]):
                raise R10ContractError("signed transport target drift")
            if headers.get("If-Match") != target["etag"] or headers.get("x-amz-request-payer") != "requester":
                raise R10ContractError("signed request guard drift")
            result["request_attempt_count"] += 1
            result["s3_http_request_count"] += 1
            remaining = max(1.0, MAX_RUNTIME_SECONDS - (time.monotonic() - started))
            status, response_headers, compressed = transport(host, path, headers, target["size"], remaining)
            if status != 200:
                result["failed_request_count"] += 1
                raise R10TransportIntegrityError(f"S3 HTTP status {status}")
            if response_headers.get("x-amz-request-charged", "").lower() != "requester":
                result["failed_request_count"] += 1
                raise R10TransportIntegrityError("missing requester-charged response header")
            if response_headers.get("etag") != target["etag"]:
                result["failed_request_count"] += 1
                raise R10TransportIntegrityError("response ETag mismatch")
            try:
                content_length = int(response_headers.get("content-length", ""))
            except ValueError as exc:
                result["failed_request_count"] += 1
                raise R10TransportIntegrityError("invalid response content-length") from exc
            if content_length != target["size"] or len(compressed) != target["size"]:
                result["failed_request_count"] += 1
                raise R10TransportIntegrityError("compressed content length mismatch")
            if len(compressed) > MAX_INDIVIDUAL_COMPRESSED_BYTES:
                raise R10TransportIntegrityError("individual compressed byte cap exceeded")
            if result["total_compressed_bytes"] + len(compressed) > MAX_TOTAL_COMPRESSED_BYTES:
                raise R10TransportIntegrityError("total compressed byte cap exceeded")
            result["successful_request_count"] += 1
            result["total_compressed_bytes"] += len(compressed)
            per_hour = aggregate_lz4_object(compressed, target, aggregate)
            if result["total_decompressed_bytes"] + per_hour["decompressed_byte_count"] > MAX_TOTAL_DECOMPRESSED_BYTES:
                raise R10TransportIntegrityError("total decompressed byte cap exceeded")
            result["total_decompressed_bytes"] += per_hour["decompressed_byte_count"]
            result["per_hour_summaries"].append(per_hour)
            result["completed_hour_count"] += 1
            compressed = b""

        if result["completed_hour_count"] != MAX_REQUESTS:
            raise R10TransportIntegrityError("not all six exact hours completed")
        output, summary = aggregate.render()
        result["aggregate_wallet_feature_summary"] = summary
        result["wallet_feature_retained"] = True
        result["terminal_status"] = "R10_MULTI_HOUR_FEATURE_STUDY_COMPLETE"
        result["technical_result"] = "MULTI_HOUR_FEATURE_PIPELINE_COMPLETE"
        result["research_conclusion"] = "MULTI_HOUR_FEATURE_PIPELINE_COMPLETE"
        rc = 0
    except R10FeatureUnresolved as exc:
        output = b""
        result["wallet_feature_retained"] = False
        result["aggregate_wallet_feature_summary"] = None
        result["terminal_status"] = "R10_MULTI_HOUR_FEATURE_STUDY_COMPLETE"
        result["technical_result"] = "MULTI_HOUR_FEATURE_PIPELINE_UNRESOLVED"
        result["research_conclusion"] = "MULTI_HOUR_FEATURE_PIPELINE_UNRESOLVED"
        result["failure_class"] = str(exc)
        rc = 0
    except (R10TransportIntegrityError, R10ContractError) as exc:
        output = b""
        result["wallet_feature_retained"] = False
        result["aggregate_wallet_feature_summary"] = None
        result["terminal_status"] = "R10_TRANSPORT_OR_INTEGRITY_FAIL"
        result["technical_result"] = "R10_TRANSPORT_OR_INTEGRITY_FAIL"
        result["research_conclusion"] = "R10_TRANSPORT_OR_INTEGRITY_FAIL"
        result["failure_class"] = str(exc)
        rc = 83
    result["observed_at_utc"] = utc_now()
    result["runtime_seconds"] = round(time.monotonic() - started, 6)
    return rc, result, output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-output", required=True)
    parser.add_argument("--wallet-feature-output", required=True)
    args = parser.parse_args(argv)
    rc, result, output = execute()
    Path(args.result_output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    Path(args.wallet_feature_output).write_bytes(output)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
