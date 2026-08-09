from __future__ import annotations

import argparse
import hashlib
import hmac
import http.client
import json
import os
import re
import ssl
import sys
import time
import urllib.parse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[3]
R8_ROOT = ROOT / "research/archive_inventory/r8"
R4_ROOT = ROOT / "research/archive_inventory/r4"
if str(R4_ROOT) not in sys.path:
    sys.path.insert(0, str(R4_ROOT))
from lz4_frame import LZ4_FRAME_MAGIC, LZ4FrameError, LZ4FrameLimit, iter_lz4_frame

PREREGISTRATION = R8_ROOT / "MODERN_WALLET_INDEX_BRIDGE_R8A_CONTRACT.json"
IMPLEMENTATION = R8_ROOT / "R8A_IMPLEMENTATION_CONTRACT.json"
APPROVAL_JSON = R8_ROOT / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_INDEX_BRIDGE_R8A_001.json"
APPROVAL_TEXT = R8_ROOT / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_INDEX_BRIDGE_R8A_001.txt"
ROLE_REUSE = R8_ROOT / "R8A_AWS_ROLE_REUSE_ANALYSIS.json"

PILOT_ID = "HL-ARCHIVE-MODERN-WALLET-INDEX-BRIDGE-R8A-001"
R8_STATIC_DESIGN_COMMIT = "526f92cf3666c8bb616ecb61b6f9881387c1d7ed"
APPROVAL_MERGE_COMMIT = "6c011cb604dec1f169d42b02de4ae67f3f8f8395"
APPROVAL_ID = "APPROVE_HL_ARCHIVE_MODERN_WALLET_INDEX_BRIDGE_R8A_001"
APPROVAL_TEXT_SHA256 = "cb39246e2e5f345b14f87c15ac2c4d6aa993bcc9fbd28076f5f57eff94420e64"
TARGET_BUCKET = "hl-mainnet-node-data"
SIGNING_REGION = "ap-northeast-1"
REGIONAL_ENDPOINT = f"{TARGET_BUCKET}.s3.{SIGNING_REGION}.amazonaws.com"
SERVICE = "s3"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"
OBJECT_KEY = "node_fills_by_block/hourly/20250727/8.lz4"
OBJECT_ARN = f"arn:aws:s3:::{TARGET_BUCKET}/{OBJECT_KEY}"
EXPECTED_SIZE_BYTES = 1_517_603
EXPECTED_ETAG = '"60d4c1277f76651b5f04666bbe8d7594"'
EXPECTED_COMPRESSED_SHA256 = "928e1cd6bd7d69ad7243c263bacee48e53e4762ae9e99ef75f45007f6c0e6105"
EXPECTED_DECOMPRESSED_BYTES = 7_380_378
EXPECTED_BLOCK_RECORDS = 4_345
MAX_REQUESTS = 1
MAX_TOTAL_COMPRESSED_BYTES = 1_517_603
MAX_TOTAL_DECOMPRESSED_BYTES = 16_777_216
MAX_RUNTIME_SECONDS = 120
MAX_RECORD_BYTES = 16_777_216
MAX_BLOCK_RECORDS = 1_000_000
MAX_EVENT_PAIRS = 5_000_000
MAX_WALLET_INDEX_ENTRIES = 1_000_000
MAX_WALLET_INDEX_BYTES = 16_777_216
EMPTY_PAYLOAD_SHA256 = hashlib.sha256(b"").hexdigest()
ADDRESS_RE = re.compile(r"^0x[0-9a-f]{40}$")


class R8AContractError(RuntimeError):
    pass


class R8ATransportError(RuntimeError):
    pass


class R8ABridgeUnresolved(RuntimeError):
    pass


class R8AJSONError(ValueError):
    pass


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise R8AContractError(f"JSON root must be object: {path}")
    return value


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def signing_now() -> datetime:
    return datetime.now(timezone.utc)


def validate_static_inputs() -> None:
    prereg = load_json(PREREGISTRATION)
    approval = load_json(APPROVAL_JSON)
    impl = load_json(IMPLEMENTATION)
    reuse = load_json(ROLE_REUSE)
    if sha256_bytes(APPROVAL_TEXT.read_bytes()) != APPROVAL_TEXT_SHA256:
        raise R8AContractError("approval text hash drift")
    if prereg.get("pilot_id") != PILOT_ID or prereg.get("status") != "PREREGISTERED_NO_EXECUTION":
        raise R8AContractError("preregistration drift")
    if approval.get("approval_id") != APPROVAL_ID or approval.get("reviewed_commit") != R8_STATIC_DESIGN_COMMIT:
        raise R8AContractError("approval identity drift")
    if approval.get("exact_approval_text_sha256") != APPROVAL_TEXT_SHA256:
        raise R8AContractError("approval hash drift")
    if not all(value is False for value in approval.get("current_runtime_authority", {}).values()):
        raise R8AContractError("approval snapshot self-opens runtime")
    if impl.get("pilot_id") != PILOT_ID or impl.get("status") != "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION":
        raise R8AContractError("implementation drift")
    if impl.get("r8_static_design_commit") != R8_STATIC_DESIGN_COMMIT:
        raise R8AContractError("implementation R8 binding drift")
    if impl.get("approval_merge_commit") != APPROVAL_MERGE_COMMIT or impl.get("approval_text_sha256") != APPROVAL_TEXT_SHA256:
        raise R8AContractError("implementation approval binding drift")
    if not all(value is False for value in impl.get("current_runtime_authority", {}).values()):
        raise R8AContractError("implementation snapshot self-opens runtime")

    target = prereg.get("exact_future_network_target", {})
    expected_target = {
        "bucket": TARGET_BUCKET,
        "signing_region": SIGNING_REGION,
        "key": OBJECT_KEY,
        "expected_size_bytes": EXPECTED_SIZE_BYTES,
        "expected_etag": EXPECTED_ETAG,
        "expected_compressed_sha256": EXPECTED_COMPRESSED_SHA256,
        "expected_decompressed_byte_count": EXPECTED_DECOMPRESSED_BYTES,
        "expected_top_level_block_record_count": EXPECTED_BLOCK_RECORDS,
    }
    if target != expected_target:
        raise R8AContractError("target drift")
    obj = impl.get("object", {})
    for key, expected in {
        "key": OBJECT_KEY,
        "expected_size_bytes": EXPECTED_SIZE_BYTES,
        "expected_etag": EXPECTED_ETAG,
        "expected_compressed_sha256": EXPECTED_COMPRESSED_SHA256,
        "expected_decompressed_byte_count": EXPECTED_DECOMPRESSED_BYTES,
        "expected_top_level_block_record_count": EXPECTED_BLOCK_RECORDS,
        "required_leading_string_regex": "^0x[0-9a-f]{40}$",
    }.items():
        if obj.get(key) != expected:
            raise R8AContractError(f"implementation object drift: {key}")

    envelope = prereg.get("proposed_future_request_envelope", {})
    for key, expected in {
        "maximum_one_time_budget_eur": 0.1,
        "maximum_monthly_budget_eur": 0,
        "maximum_get_object_requests": MAX_REQUESTS,
        "maximum_requests_per_object": 1,
        "maximum_total_compressed_bytes": MAX_TOTAL_COMPRESSED_BYTES,
        "maximum_total_decompressed_bytes": MAX_TOTAL_DECOMPRESSED_BYTES,
        "maximum_runtime_seconds": MAX_RUNTIME_SECONDS,
        "maximum_retries_per_request": 0,
        "maximum_record_bytes": MAX_RECORD_BYTES,
        "maximum_block_records_parsed": MAX_BLOCK_RECORDS,
        "maximum_event_pairs_parsed": MAX_EVENT_PAIRS,
    }.items():
        if approval.get(key) != expected or impl.get(key) != expected or envelope.get(key) != expected:
            raise R8AContractError(f"envelope drift: {key}")
    for key in (
        "if_match_etag_required", "exact_content_length_required", "exact_response_etag_required",
        "exact_compressed_sha256_required", "exact_decompressed_byte_count_required", "lz4_frame_stream_only",
        "strict_utf8_decode", "strict_json_duplicate_keys_rejected", "strict_json_nonfinite_constants_rejected",
    ):
        if approval.get(key) is not True or impl.get(key) is not True or envelope.get(key) is not True:
            raise R8AContractError(f"required guard drift: {key}")
    for key in (
        "head_object_authorized", "range_get_authorized", "list_objects_v2_authorized",
        "list_object_versions_authorized", "list_all_my_buckets_authorized",
        "http_redirect_following_authorized", "alternate_decompressor_fallback_authorized",
    ):
        if approval.get(key) is not False or impl.get(key) is not False or envelope.get(key) is not False:
            raise R8AContractError(f"forbidden transport capability opened: {key}")

    shape = prereg.get("required_modern_block_shape", {})
    if shape.get("required_fields") != {"local_time": "string", "block_time": "string", "block_number": "integer", "events": "array"}:
        raise R8AContractError("modern block field contract drift")
    if shape.get("event_pair_required_arity") != 2 or shape.get("event_pair_required_ordered_element_types") != ["string", "object"]:
        raise R8AContractError("event-pair contract drift")
    if shape.get("required_leading_string_pattern") != "^0x[0-9a-f]{40}$":
        raise R8AContractError("address-shape contract drift")

    future = approval.get("future_retention_authorizations", {})
    if future.get("retained_wallet_index_fields_only") != ["wallet_address", "fill_count"]:
        raise R8AContractError("approval output field drift")
    if future.get("wallet_address_normalization") != "LOWERCASE_EXACT_0X40HEX":
        raise R8AContractError("approval normalization drift")
    if not all(value is False for value in approval.get("forbidden_retention_authorizations", {}).values()):
        raise R8AContractError("forbidden retention opened")
    if not all(value is False for value in impl.get("forbidden_retention_authorizations", {}).values()):
        raise R8AContractError("implementation forbidden retention opened")
    if not all(value is False for value in approval.get("downstream_authorizations", {}).values()):
        raise R8AContractError("downstream approval opened")
    if not all(value is False for value in approval.get("trading_authorizations", {}).values()):
        raise R8AContractError("trading approval opened")
    if not all(value is False for value in impl.get("downstream_authorizations", {}).values()):
        raise R8AContractError("implementation downstream opened")
    if not all(value is False for value in impl.get("trading_authorizations", {}).values()):
        raise R8AContractError("implementation trading opened")

    if impl.get("execution_release_present") is not False or impl.get("expected_canonical_implementation_commit") != "PENDING_CANONICAL_IMPLEMENTATION_MERGE":
        raise R8AContractError("implementation release state drift")
    if impl.get("s3_requests_executed") != 0 or impl.get("wallet_addresses_retained") != 0 or impl.get("empirical_result") is not None:
        raise R8AContractError("implementation contains execution evidence")
    if impl.get("reused_dedicated_role_arn") != ROLE_ARN or impl.get("session_s3_policy") != "ALLOW_GETOBJECT_EXACT_R8A_MODERN_BOUNDARY_OBJECT_ONLY":
        raise R8AContractError("role/session binding drift")
    if reuse.get("reused_role_arn") != ROLE_ARN or reuse.get("aws_iam_mutation_performed") is not False:
        raise R8AContractError("role reuse evidence drift")
    if reuse.get("r8a_session_scope", {}).get("allowed_object_arns") != [OBJECT_ARN]:
        raise R8AContractError("R8A session object scope drift")


def _aws_quote_path(key: str) -> str:
    return "/" + urllib.parse.quote(key, safe="/-_.~")


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def build_signed_request(request_time: datetime, env: dict[str, str] | None = None) -> tuple[str, str, dict[str, str]]:
    source = os.environ if env is None else env
    access_key = source.get("AWS_ACCESS_KEY_ID")
    secret_key = source.get("AWS_SECRET_ACCESS_KEY")
    session_token = source.get("AWS_SESSION_TOKEN")
    if not access_key or not secret_key or not session_token:
        raise R8AContractError("temporary AWS credentials missing")
    if request_time.tzinfo is None:
        raise R8AContractError("signing time must be timezone-aware")
    stamp = request_time.astimezone(timezone.utc)
    amz_date = stamp.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = stamp.strftime("%Y%m%d")
    canonical_uri = _aws_quote_path(OBJECT_KEY)
    canonical_headers = (
        f"host:{REGIONAL_ENDPOINT}\n"
        f"if-match:{EXPECTED_ETAG}\n"
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
        "If-Match": EXPECTED_ETAG,
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


def _strict_object(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise R8AJSONError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_nonfinite(_token: str) -> object:
    raise R8AJSONError("non-finite JSON constant")


def _strict_loads(text: str) -> object:
    try:
        return json.loads(text, object_pairs_hook=_strict_object, parse_constant=_reject_nonfinite)
    except (json.JSONDecodeError, R8AJSONError) as exc:
        raise R8AJSONError("strict JSON parse failed") from exc


class ModernWalletIndexAggregator:
    def __init__(self) -> None:
        self.block_record_count = 0
        self.valid_event_pair_count = 0
        self.counts: dict[str, int] = defaultdict(int)

    def add_line(self, line: bytes) -> None:
        if line.endswith(b"\r"):
            line = line[:-1]
        if not line.strip():
            return
        if len(line) > MAX_RECORD_BYTES:
            raise R8ABridgeUnresolved("block record byte limit exceeded")
        try:
            value = _strict_loads(line.decode("utf-8", errors="strict"))
        except (UnicodeDecodeError, R8AJSONError) as exc:
            raise R8ABridgeUnresolved("strict modern block parse failed") from exc
        self.block_record_count += 1
        if self.block_record_count > MAX_BLOCK_RECORDS:
            raise R8ABridgeUnresolved("block record count cap exceeded")
        if not isinstance(value, dict):
            raise R8ABridgeUnresolved("top-level modern record is not object")
        required = {
            "local_time": str,
            "block_time": str,
            "block_number": int,
            "events": list,
        }
        for key, expected_type in required.items():
            field = value.get(key)
            if expected_type is int:
                if not isinstance(field, int) or isinstance(field, bool):
                    raise R8ABridgeUnresolved(f"modern block field type mismatch: {key}")
            elif not isinstance(field, expected_type):
                raise R8ABridgeUnresolved(f"modern block field type mismatch: {key}")
        events = value["events"]
        for pair in events:
            self.valid_event_pair_count += 1
            if self.valid_event_pair_count > MAX_EVENT_PAIRS:
                raise R8ABridgeUnresolved("event-pair cap exceeded")
            if not (isinstance(pair, list) and len(pair) == 2 and isinstance(pair[0], str) and isinstance(pair[1], dict)):
                raise R8ABridgeUnresolved("event differs from frozen [string, object] pair contract")
            address = pair[0]
            if ADDRESS_RE.fullmatch(address) is None:
                raise R8ABridgeUnresolved("event leading string violates lowercase address shape")
            self.counts[address] += 1
            if len(self.counts) > MAX_WALLET_INDEX_ENTRIES:
                raise R8ABridgeUnresolved("wallet index entry cap exceeded")
        del value

    def render(self) -> tuple[bytes, dict]:
        if self.block_record_count != EXPECTED_BLOCK_RECORDS:
            raise R8ABridgeUnresolved("top-level block record count mismatch")
        if self.valid_event_pair_count < 1:
            raise R8ABridgeUnresolved("no valid event pairs observed")
        if not self.counts:
            raise R8ABridgeUnresolved("wallet index is empty")
        total = sum(self.counts.values())
        if total != self.valid_event_pair_count:
            raise R8ABridgeUnresolved("event-pair conservation mismatch")
        output = bytearray()
        for address in sorted(self.counts):
            encoded = (json.dumps({"wallet_address": address, "fill_count": self.counts[address]}, separators=(",", ":")) + "\n").encode()
            if len(output) + len(encoded) > MAX_WALLET_INDEX_BYTES:
                raise R8ABridgeUnresolved("wallet index output byte cap exceeded")
            output.extend(encoded)
        rendered = bytes(output)
        return rendered, {
            "top_level_block_record_count": self.block_record_count,
            "valid_event_pair_count": self.valid_event_pair_count,
            "unique_wallet_count": len(self.counts),
            "sum_fill_count": total,
            "wallet_index_bytes": len(rendered),
            "wallet_index_sha256": sha256_bytes(rendered),
            "wallet_index_format": "UTF8_NDJSON",
            "wallet_index_fields_only": ["wallet_address", "fill_count"],
            "wallet_index_sort_order": "LEXICOGRAPHIC_ASCENDING",
        }


def aggregate_decompressed_chunks(chunks: Iterable[bytes]) -> tuple[int, bytes, dict]:
    aggregate = ModernWalletIndexAggregator()
    pending = bytearray()
    decompressed_bytes = 0
    for chunk in chunks:
        decompressed_bytes += len(chunk)
        if decompressed_bytes > MAX_TOTAL_DECOMPRESSED_BYTES:
            raise R8ATransportError("decompressed byte cap exceeded")
        pending.extend(chunk)
        while True:
            newline = pending.find(b"\n")
            if newline < 0:
                break
            line = bytes(pending[:newline])
            del pending[: newline + 1]
            aggregate.add_line(line)
        if len(pending) > MAX_RECORD_BYTES:
            raise R8ABridgeUnresolved("block record byte limit exceeded before newline")
    if pending:
        aggregate.add_line(bytes(pending))
    wallet_index, summary = aggregate.render()
    return decompressed_bytes, wallet_index, summary


def execute(
    transport: Callable[[str, str, dict[str, str], int, float], tuple[int, dict[str, str], bytes]] = https_transport,
    request_time: Callable[[], datetime] = signing_now,
    env: dict[str, str] | None = None,
) -> tuple[int, dict, bytes]:
    validate_static_inputs()
    started = time.monotonic()
    attempts = 0
    result = {
        "schema_version": "1.0",
        "pilot_id": PILOT_ID,
        "observed_at_utc": utc_now(),
        "terminal_status": "PENDING",
        "technical_result": None,
        "research_conclusion": None,
        "request_attempt_count": 0,
        "s3_http_request_count": 0,
        "successful_request_count": 0,
        "failed_request_count": 0,
        "retries_used": 0,
        "http_redirects_followed": False,
        "requester_pays_requested": True,
        "object_key": OBJECT_KEY,
        "expected_content_length": EXPECTED_SIZE_BYTES,
        "expected_etag": EXPECTED_ETAG,
        "expected_compressed_sha256": EXPECTED_COMPRESSED_SHA256,
        "expected_decompressed_byte_count": EXPECTED_DECOMPRESSED_BYTES,
        "expected_top_level_block_record_count": EXPECTED_BLOCK_RECORDS,
        "compressed_bytes": 0,
        "decompressed_bytes": 0,
        "compressed_sha256": None,
        "wallet_index_summary": None,
        "wallet_index_retained": False,
        "wallet_addresses_retained": False,
        "leading_string_values_retained": False,
        "per_wallet_fill_counts_retained": False,
        "unique_wallet_count_retained": False,
        "valid_event_pair_count_retained": False,
        "block_number_values_retained": False,
        "local_time_values_retained": False,
        "block_time_values_retained": False,
        "raw_compressed_object_persisted": False,
        "raw_decompressed_payload_retained": False,
        "record_payload_retained": False,
        "fill_object_retained": False,
        "payload_values_retained": False,
        "performance_field_values_retained": False,
        "coin_values_retained": False,
        "price_values_retained": False,
        "size_values_retained": False,
        "side_values_retained": False,
        "time_values_retained": False,
        "dir_values_retained": False,
        "closed_pnl_values_retained": False,
        "fee_values_retained": False,
        "fee_token_values_retained": False,
        "start_position_values_retained": False,
        "crossed_values_retained": False,
        "liquidation_values_retained": False,
        "transaction_hashes_retained": False,
        "order_ids_retained": False,
        "trade_ids_retained": False,
        "client_order_ids_retained": False,
        "historical_multi_hour_ingestion_performed": False,
        "public_api_enrichment_performed": False,
        "entity_clustering_performed": False,
        "wallet_ranking_performed": False,
        "copyability_analysis_performed": False,
        "pnl_or_alpha_analysis_performed": False,
        "market_data_ingested": False,
        "strategy_inference_performed": False,
        "runtime_seconds": None,
        "failure_class": None,
    }
    try:
        if time.monotonic() - started > MAX_RUNTIME_SECONDS:
            raise R8ATransportError("runtime cap reached before request")
        host, path, headers = build_signed_request(request_time(), env)
        attempts += 1
        result["request_attempt_count"] = attempts
        result["s3_http_request_count"] = attempts
        if attempts > MAX_REQUESTS:
            raise R8ATransportError("request cap exceeded")
        remaining = max(1.0, MAX_RUNTIME_SECONDS - (time.monotonic() - started))
        status, response_headers, body = transport(host, path, headers, EXPECTED_SIZE_BYTES, remaining)
        if status != 200:
            result["failed_request_count"] = 1
            raise R8ATransportError("non-200 S3 response")
        result["successful_request_count"] = 1
        try:
            content_length = int(response_headers.get("content-length", ""))
        except ValueError as exc:
            raise R8ATransportError("invalid Content-Length") from exc
        if content_length != EXPECTED_SIZE_BYTES or len(body) != EXPECTED_SIZE_BYTES:
            raise R8ATransportError("Content-Length or body-size mismatch")
        if response_headers.get("etag") != EXPECTED_ETAG:
            raise R8ATransportError("ETag mismatch")
        if response_headers.get("x-amz-request-charged") != "requester":
            raise R8ATransportError("Requester Pays acknowledgement missing")
        if len(body) > MAX_TOTAL_COMPRESSED_BYTES:
            raise R8ATransportError("compressed byte cap exceeded")
        compressed_sha = sha256_bytes(body)
        if compressed_sha != EXPECTED_COMPRESSED_SHA256:
            raise R8ATransportError("compressed SHA-256 mismatch")
        result["compressed_bytes"] = len(body)
        result["compressed_sha256"] = compressed_sha
        if not body.startswith(LZ4_FRAME_MAGIC):
            raise R8ATransportError("unrecognized LZ4 frame")
        try:
            decompressed_bytes, wallet_index, summary = aggregate_decompressed_chunks(iter_lz4_frame(body, MAX_TOTAL_DECOMPRESSED_BYTES))
        except (LZ4FrameError, LZ4FrameLimit) as exc:
            raise R8ATransportError("LZ4 decompression failed") from exc
        del body
        if decompressed_bytes != EXPECTED_DECOMPRESSED_BYTES:
            raise R8ATransportError("decompressed byte-count mismatch")
        result["decompressed_bytes"] = decompressed_bytes
        result["wallet_index_summary"] = summary
        result["wallet_index_retained"] = True
        result["wallet_addresses_retained"] = True
        result["leading_string_values_retained"] = True
        result["per_wallet_fill_counts_retained"] = True
        result["unique_wallet_count_retained"] = True
        result["valid_event_pair_count_retained"] = True
        result["research_conclusion"] = "MODERN_WALLET_INDEX_BRIDGE_COMPLETE"
        result["technical_result"] = "MODERN_WALLET_INDEX_BRIDGE_COMPLETE"
        result["terminal_status"] = "R8A_MODERN_WALLET_INDEX_STUDY_COMPLETE"
        result["runtime_seconds"] = round(time.monotonic() - started, 6)
        return 0, result, wallet_index
    except R8ABridgeUnresolved as exc:
        result["terminal_status"] = "R8A_MODERN_WALLET_INDEX_STUDY_COMPLETE"
        result["technical_result"] = "MODERN_WALLET_INDEX_BRIDGE_UNRESOLVED"
        result["research_conclusion"] = "MODERN_WALLET_INDEX_BRIDGE_UNRESOLVED"
        result["failure_class"] = type(exc).__name__
        result["runtime_seconds"] = round(time.monotonic() - started, 6)
        return 0, result, b""
    except (R8AContractError, R8ATransportError, R8AJSONError) as exc:
        result["terminal_status"] = "R8A_TRANSPORT_OR_INTEGRITY_FAIL"
        result["technical_result"] = "R8A_TRANSPORT_OR_INTEGRITY_FAIL"
        result["research_conclusion"] = "R8A_TRANSPORT_OR_INTEGRITY_FAIL"
        result["failure_class"] = type(exc).__name__
        result["runtime_seconds"] = round(time.monotonic() - started, 6)
        return 1, result, b""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-output", required=True)
    parser.add_argument("--wallet-index-output", required=True)
    args = parser.parse_args(argv)
    rc, result, wallet_index = execute()
    Path(args.result_output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    Path(args.wallet_index_output).write_bytes(wallet_index)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
