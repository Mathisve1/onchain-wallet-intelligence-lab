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
R7_ROOT = ROOT / "research/archive_inventory/r7"
R4_ROOT = ROOT / "research/archive_inventory/r4"
if str(R4_ROOT) not in sys.path:
    sys.path.insert(0, str(R4_ROOT))
from lz4_frame import LZ4_FRAME_MAGIC, LZ4FrameError, LZ4FrameLimit, iter_lz4_frame

PREREGISTRATION = R7_ROOT / "WALLET_INDEX_RECONSTRUCTION_R7_CONTRACT.json"
IMPLEMENTATION = R7_ROOT / "R7_IMPLEMENTATION_CONTRACT.json"
APPROVAL_JSON = R7_ROOT / "approvals/APPROVE_HL_ARCHIVE_WALLET_INDEX_RECONSTRUCTION_R7_001.json"
APPROVAL_TEXT = R7_ROOT / "approvals/APPROVE_HL_ARCHIVE_WALLET_INDEX_RECONSTRUCTION_R7_001.txt"
ROLE_REUSE = R7_ROOT / "R7_AWS_ROLE_REUSE_ANALYSIS.json"

PILOT_ID = "HL-ARCHIVE-WALLET-INDEX-RECONSTRUCTION-R7-001"
PREREGISTRATION_COMMIT = "795281b2992466785ba48314d59feb61ac0b3aef"
APPROVAL_MERGE_COMMIT = "65a7b53796231b3aaea4c1dc1b41aa847b4ea3ba"
APPROVAL_ID = "APPROVE_HL_ARCHIVE_WALLET_INDEX_RECONSTRUCTION_R7_001"
APPROVAL_TEXT_SHA256 = "43f32634859eb39e4b1e464276f9721ed4ef8bcc30161f1f301f82e0312042a6"
TARGET_BUCKET = "hl-mainnet-node-data"
SIGNING_REGION = "ap-northeast-1"
REGIONAL_ENDPOINT = f"{TARGET_BUCKET}.s3.{SIGNING_REGION}.amazonaws.com"
SERVICE = "s3"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"
OBJECT_KEY = "node_fills/hourly/20250727/8.lz4"
EXPECTED_SIZE_BYTES = 12_726_384
EXPECTED_ETAG = '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"'
EXPECTED_COMPRESSED_SHA256 = "f12d33da9733dbb71f02f9910fc187b9dd4b8f9dae1102b7dfe7690094542622"
EXPECTED_DECOMPRESSED_BYTES = 62_169_139
EXPECTED_NONEMPTY_RECORDS = 162_815
MAX_REQUESTS = 1
MAX_TOTAL_COMPRESSED_BYTES = 12_726_384
MAX_TOTAL_DECOMPRESSED_BYTES = 134_217_728
MAX_RUNTIME_SECONDS = 120
MAX_RECORD_BYTES = 16_777_216
MAX_RECORDS = 5_000_000
MAX_WALLET_INDEX_ENTRIES = 162_815
MAX_WALLET_INDEX_BYTES = 16_777_216
EMPTY_PAYLOAD_SHA256 = hashlib.sha256(b"").hexdigest()
ADDRESS_RE = re.compile(r"^0x[0-9a-f]{40}$")
ALLOWED_RESEARCH_CONCLUSIONS = {
    "WALLET_INDEX_RECONSTRUCTION_COMPLETE",
    "WALLET_INDEX_RECONSTRUCTION_UNRESOLVED",
    "R7_TRANSPORT_OR_INTEGRITY_FAIL",
}


class R7ContractError(RuntimeError):
    pass


class R7TransportError(RuntimeError):
    pass


class R7ReconstructionUnresolved(RuntimeError):
    pass


class R7JSONError(ValueError):
    pass


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise R7ContractError(f"JSON root must be object: {path}")
    return value


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def signing_now() -> datetime:
    return datetime.now(timezone.utc)


def validate_static_inputs() -> dict:
    prereg = load_json(PREREGISTRATION)
    approval = load_json(APPROVAL_JSON)
    impl = load_json(IMPLEMENTATION)
    role_reuse = load_json(ROLE_REUSE)

    if sha256_bytes(APPROVAL_TEXT.read_bytes()) != APPROVAL_TEXT_SHA256:
        raise R7ContractError("approval text hash drift")
    if prereg.get("pilot_id") != PILOT_ID or prereg.get("status") != "PREREGISTERED_NO_EXECUTION":
        raise R7ContractError("preregistration identity/status drift")
    if prereg.get("parent_r6a_evidence_commit") != "6b7dcd85e6d0f82b63ab8c4dd50d56ef8dc72a57":
        raise R7ContractError("parent R6A evidence binding drift")
    if approval.get("approval_id") != APPROVAL_ID or approval.get("reviewed_commit") != PREREGISTRATION_COMMIT:
        raise R7ContractError("approval identity drift")
    if approval.get("exact_approval_text_sha256") != APPROVAL_TEXT_SHA256:
        raise R7ContractError("approval hash drift")
    if not all(value is False for value in approval.get("current_runtime_authority", {}).values()):
        raise R7ContractError("approval snapshot self-opens runtime")
    if impl.get("pilot_id") != PILOT_ID or impl.get("status") != "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION":
        raise R7ContractError("implementation identity/status drift")
    if impl.get("preregistration_commit") != PREREGISTRATION_COMMIT:
        raise R7ContractError("implementation preregistration drift")
    if impl.get("approval_merge_commit") != APPROVAL_MERGE_COMMIT or impl.get("approval_text_sha256") != APPROVAL_TEXT_SHA256:
        raise R7ContractError("implementation approval binding drift")
    if not all(value is False for value in impl.get("current_runtime_authority", {}).values()):
        raise R7ContractError("implementation snapshot self-opens runtime")

    target = prereg.get("exact_future_network_target", {})
    expected_target = {
        "bucket": TARGET_BUCKET,
        "signing_region": SIGNING_REGION,
        "key": OBJECT_KEY,
        "expected_size_bytes": EXPECTED_SIZE_BYTES,
        "expected_etag": EXPECTED_ETAG,
        "expected_compressed_sha256": EXPECTED_COMPRESSED_SHA256,
        "expected_decompressed_byte_count": EXPECTED_DECOMPRESSED_BYTES,
        "expected_nonempty_record_count": EXPECTED_NONEMPTY_RECORDS,
        "required_top_level_record_type": "array",
        "required_array_arity": 2,
        "required_ordered_element_types": ["string", "object"],
        "required_leading_string_pattern": "^0x[0-9a-f]{40}$",
    }
    if target != expected_target:
        raise R7ContractError("preregistration target drift")
    obj = impl.get("object", {})
    for name, expected in {
        "key": OBJECT_KEY,
        "expected_size_bytes": EXPECTED_SIZE_BYTES,
        "expected_etag": EXPECTED_ETAG,
        "expected_compressed_sha256": EXPECTED_COMPRESSED_SHA256,
        "expected_decompressed_byte_count": EXPECTED_DECOMPRESSED_BYTES,
        "expected_nonempty_record_count": EXPECTED_NONEMPTY_RECORDS,
        "required_leading_string_regex": "^0x[0-9a-f]{40}$",
    }.items():
        if obj.get(name) != expected:
            raise R7ContractError(f"implementation object drift: {name}")

    envelope = prereg.get("proposed_future_request_envelope", {})
    for name, expected in {
        "maximum_one_time_budget_eur": 0.1,
        "maximum_monthly_budget_eur": 0,
        "maximum_get_object_requests": MAX_REQUESTS,
        "maximum_requests_per_object": 1,
        "maximum_total_compressed_bytes": MAX_TOTAL_COMPRESSED_BYTES,
        "maximum_total_decompressed_bytes": MAX_TOTAL_DECOMPRESSED_BYTES,
        "maximum_runtime_seconds": MAX_RUNTIME_SECONDS,
        "maximum_retries_per_request": 0,
        "maximum_record_bytes": MAX_RECORD_BYTES,
        "maximum_records_parsed": MAX_RECORDS,
    }.items():
        if approval.get(name) != expected or impl.get(name) != expected or envelope.get(name) != expected:
            raise R7ContractError(f"execution envelope drift: {name}")
    for name in (
        "requester_pays_authorized_for_later_release",
        "get_object_authorized_for_later_release",
        "decompression_authorized_for_later_release",
    ):
        if approval.get(name) is not True:
            raise R7ContractError(f"approved future capability missing: {name}")
    for name in (
        "if_match_etag_required",
        "exact_content_length_required",
        "exact_compressed_sha256_required",
        "exact_decompressed_byte_count_required",
        "lz4_frame_stream_only",
        "strict_utf8_decode",
        "strict_json_duplicate_keys_rejected",
        "strict_json_nonfinite_constants_rejected",
    ):
        if approval.get(name) is not True or impl.get(name) is not True or envelope.get(name) is not True:
            raise R7ContractError(f"required guard drift: {name}")
    for name in (
        "head_object_authorized",
        "range_get_authorized",
        "list_objects_v2_authorized",
        "list_object_versions_authorized",
        "list_all_my_buckets_authorized",
        "http_redirect_following_authorized",
        "alternate_decompressor_fallback_authorized",
    ):
        if approval.get(name) is not False or impl.get(name) is not False or envelope.get(name) is not False:
            raise R7ContractError(f"forbidden transport capability opened: {name}")

    retention = prereg.get("proposed_future_retention_boundary", {})
    future = approval.get("future_retention_authorizations", {})
    impl_future = impl.get("future_release_retention_authorizations", {})
    if future != {
        "wallet_address": True,
        "leading_string_value": True,
        "per_wallet_fill_count": True,
        "unique_wallet_count": True,
        "wallet_address_normalization": "LOWERCASE_EXACT_0X40HEX",
        "wallet_index_entry_cap": MAX_WALLET_INDEX_ENTRIES,
        "wallet_index_output_byte_cap": MAX_WALLET_INDEX_BYTES,
        "retained_wallet_index_fields_only": ["wallet_address", "fill_count"],
    }:
        raise R7ContractError("approval future retention boundary drift")
    if impl_future != {
        "wallet_address": True,
        "leading_string_value": True,
        "per_wallet_fill_count": True,
        "unique_wallet_count": True,
    }:
        raise R7ContractError("implementation future retention boundary drift")
    if retention.get("normalization") != "LOWERCASE_EXACT_0X40HEX":
        raise R7ContractError("wallet normalization drift")
    if retention.get("wallet_index_entry_cap") != MAX_WALLET_INDEX_ENTRIES:
        raise R7ContractError("wallet index entry cap drift")
    if retention.get("wallet_index_output_byte_cap") != MAX_WALLET_INDEX_BYTES:
        raise R7ContractError("wallet index byte cap drift")
    if retention.get("retained_wallet_index_fields_only") != ["wallet_address", "fill_count"]:
        raise R7ContractError("wallet index field scope drift")
    if not all(value is False for value in approval.get("forbidden_retention_authorizations", {}).values()):
        raise R7ContractError("approval forbidden retention opened")
    if not all(value is False for value in impl.get("forbidden_retention_authorizations", {}).values()):
        raise R7ContractError("implementation forbidden retention opened")
    if not all(value is False for value in approval.get("downstream_authorizations", {}).values()):
        raise R7ContractError("approval downstream authority opened")
    if not all(value is False for value in approval.get("trading_authorizations", {}).values()):
        raise R7ContractError("approval trading authority opened")
    if not all(value is False for value in impl.get("downstream_authorizations", {}).values()):
        raise R7ContractError("implementation downstream authority opened")
    if not all(value is False for value in impl.get("trading_authorizations", {}).values()):
        raise R7ContractError("implementation trading authority opened")

    if impl.get("execution_release_present") is not False:
        raise R7ContractError("implementation snapshot contains a release")
    if impl.get("expected_canonical_implementation_commit") != "PENDING_CANONICAL_IMPLEMENTATION_MERGE":
        raise R7ContractError("implementation must remain pending")
    if impl.get("s3_requests_executed") != 0 or impl.get("wallet_addresses_retained") != 0:
        raise R7ContractError("implementation snapshot contains execution evidence")
    if impl.get("empirical_result") is not None:
        raise R7ContractError("implementation snapshot contains empirical result")

    if impl.get("reused_dedicated_role_arn") != ROLE_ARN:
        raise R7ContractError("role reuse ARN drift")
    if impl.get("aws_role_mutation_required") is not False or impl.get("aws_role_mutation_authorized") is not False:
        raise R7ContractError("role mutation boundary drift")
    if impl.get("session_s3_policy") != "ALLOW_GETOBJECT_EXACT_R5_BOUND_LEGACY_OBJECT_ONLY":
        raise R7ContractError("session policy drift")
    if impl.get("session_policy_strict_subset_of_persistent_role") is not True:
        raise R7ContractError("session subset proof drift")
    if role_reuse.get("reused_role_arn") != ROLE_ARN or role_reuse.get("aws_iam_mutation_performed") is not False:
        raise R7ContractError("role reuse evidence drift")
    if role_reuse.get("new_sts_preflight_required") is not False:
        raise R7ContractError("unexpected new STS preflight requirement")
    if role_reuse.get("r7_session_scope", {}).get("allowed_object_arns") != [f"arn:aws:s3:::{TARGET_BUCKET}/{OBJECT_KEY}"]:
        raise R7ContractError("role reuse session scope drift")

    return expected_target


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
        raise R7ContractError("temporary AWS credentials missing")
    if request_time.tzinfo is None:
        raise R7ContractError("signing time must be timezone-aware")

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
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256",
        amz_date,
        scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])
    k_date = _sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _sign(k_date, SIGNING_REGION)
    k_service = _sign(k_region, SERVICE)
    k_signing = _sign(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{scope},"
        f"SignedHeaders={signed_headers},Signature={signature}"
    )
    return REGIONAL_ENDPOINT, canonical_uri, {
        "Host": REGIONAL_ENDPOINT,
        "If-Match": EXPECTED_ETAG,
        "Authorization": authorization,
        "x-amz-content-sha256": EMPTY_PAYLOAD_SHA256,
        "x-amz-date": amz_date,
        "x-amz-request-payer": "requester",
        "x-amz-security-token": session_token,
    }


def https_transport(
    host: str,
    path: str,
    headers: dict[str, str],
    expected_size: int,
    timeout_seconds: float,
) -> tuple[int, dict[str, str], bytes]:
    context = ssl.create_default_context()
    connection = http.client.HTTPSConnection(host, timeout=timeout_seconds, context=context)
    try:
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        response_headers = {name.lower(): value.strip() for name, value in response.getheaders()}
        if response.status != 200:
            return response.status, response_headers, b""
        body = response.read(expected_size + 1)
        return response.status, response_headers, body
    finally:
        connection.close()


def _strict_object(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise R7JSONError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_nonfinite(_token: str) -> object:
    raise R7JSONError("non-finite JSON constant")


def _strict_loads(text: str) -> object:
    try:
        return json.loads(text, object_pairs_hook=_strict_object, parse_constant=_reject_nonfinite)
    except (json.JSONDecodeError, R7JSONError) as exc:
        raise R7JSONError("strict JSON parse failed") from exc


class WalletIndexAggregator:
    def __init__(self) -> None:
        self.nonempty_record_count = 0
        self.pair_string_object_record_count = 0
        self.counts: dict[str, int] = defaultdict(int)

    def add_line(self, line: bytes) -> None:
        if line.endswith(b"\r"):
            line = line[:-1]
        if not line.strip():
            return
        if len(line) > MAX_RECORD_BYTES:
            raise R7ReconstructionUnresolved("record byte limit exceeded")
        try:
            text = line.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise R7ReconstructionUnresolved("non-UTF8 record") from exc
        try:
            value = _strict_loads(text)
        except R7JSONError as exc:
            raise R7ReconstructionUnresolved("strict JSON record parse failed") from exc

        self.nonempty_record_count += 1
        if self.nonempty_record_count > MAX_RECORDS:
            raise R7ReconstructionUnresolved("record count limit exceeded")
        if not (
            isinstance(value, list)
            and len(value) == 2
            and isinstance(value[0], str)
            and isinstance(value[1], dict)
        ):
            del value
            raise R7ReconstructionUnresolved("record shape differs from frozen [string, object] contract")
        self.pair_string_object_record_count += 1
        address = value[0]
        if ADDRESS_RE.fullmatch(address) is None:
            del value
            raise R7ReconstructionUnresolved("leading string violates frozen lowercase address shape")
        self.counts[address] += 1
        if len(self.counts) > MAX_WALLET_INDEX_ENTRIES:
            raise R7ReconstructionUnresolved("wallet index entry cap exceeded")
        del address
        del value

    def render(self) -> tuple[bytes, dict]:
        if self.nonempty_record_count != EXPECTED_NONEMPTY_RECORDS:
            raise R7ReconstructionUnresolved("nonempty record count mismatch")
        if self.pair_string_object_record_count != EXPECTED_NONEMPTY_RECORDS:
            raise R7ReconstructionUnresolved("pair record count mismatch")
        if not self.counts:
            raise R7ReconstructionUnresolved("wallet index is empty")
        total = sum(self.counts.values())
        if total != EXPECTED_NONEMPTY_RECORDS:
            raise R7ReconstructionUnresolved("wallet fill-count conservation mismatch")
        output = bytearray()
        for address in sorted(self.counts):
            row = {"wallet_address": address, "fill_count": self.counts[address]}
            encoded = (json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
            if len(output) + len(encoded) > MAX_WALLET_INDEX_BYTES:
                raise R7ReconstructionUnresolved("wallet index output byte cap exceeded")
            output.extend(encoded)
        rendered = bytes(output)
        summary = {
            "nonempty_record_count": self.nonempty_record_count,
            "pair_string_object_record_count": self.pair_string_object_record_count,
            "unique_wallet_count": len(self.counts),
            "sum_fill_count": total,
            "wallet_index_bytes": len(rendered),
            "wallet_index_sha256": sha256_bytes(rendered),
            "wallet_index_format": "UTF8_NDJSON",
            "wallet_index_fields_only": ["wallet_address", "fill_count"],
            "wallet_index_sort_order": "LEXICOGRAPHIC_ASCENDING",
        }
        return rendered, summary


def aggregate_decompressed_chunks(chunks: Iterable[bytes]) -> tuple[int, bytes, dict]:
    aggregate = WalletIndexAggregator()
    pending = bytearray()
    decompressed_bytes = 0
    for chunk in chunks:
        decompressed_bytes += len(chunk)
        if decompressed_bytes > MAX_TOTAL_DECOMPRESSED_BYTES:
            raise R7TransportError("decompressed byte cap exceeded")
        pending.extend(chunk)
        while True:
            newline = pending.find(b"\n")
            if newline < 0:
                break
            line = bytes(pending[:newline])
            del pending[: newline + 1]
            aggregate.add_line(line)
        if len(pending) > MAX_RECORD_BYTES:
            raise R7ReconstructionUnresolved("record byte limit exceeded before newline")
    if pending:
        aggregate.add_line(bytes(pending))
        pending.clear()
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
        "expected_nonempty_record_count": EXPECTED_NONEMPTY_RECORDS,
        "compressed_bytes": 0,
        "decompressed_bytes": 0,
        "compressed_sha256": None,
        "wallet_index_summary": None,
        "wallet_index_retained": False,
        "wallet_addresses_retained": False,
        "leading_string_values_retained": False,
        "per_wallet_fill_counts_retained": False,
        "raw_compressed_object_persisted": False,
        "raw_decompressed_payload_retained": False,
        "record_payload_retained": False,
        "fill_object_retained": False,
        "payload_values_retained": False,
        "coin_values_retained": False,
        "price_values_retained": False,
        "size_values_retained": False,
        "side_values_retained": False,
        "time_values_retained": False,
        "closed_pnl_values_retained": False,
        "fee_values_retained": False,
        "transaction_hashes_retained": False,
        "order_ids_retained": False,
        "trade_ids_retained": False,
        "client_order_ids_retained": False,
        "entity_clustering_performed": False,
        "copyability_analysis_performed": False,
        "pnl_or_alpha_analysis_performed": False,
        "market_data_ingested": False,
        "historical_multi_hour_ingestion_performed": False,
        "strategy_inference_performed": False,
        "runtime_seconds": None,
        "failure_class": None,
    }
    try:
        if time.monotonic() - started > MAX_RUNTIME_SECONDS:
            raise R7TransportError("runtime limit reached before request")
        host, path, headers = build_signed_request(request_time(), env)
        attempts += 1
        result["request_attempt_count"] = attempts
        result["s3_http_request_count"] = attempts
        if attempts > MAX_REQUESTS:
            raise R7TransportError("request cap exceeded")
        remaining = max(1.0, MAX_RUNTIME_SECONDS - (time.monotonic() - started))
        status, response_headers, body = transport(host, path, headers, EXPECTED_SIZE_BYTES, remaining)
        if status != 200:
            result["failed_request_count"] = 1
            raise R7TransportError("non-200 S3 response")
        result["successful_request_count"] = 1

        content_length_text = response_headers.get("content-length")
        try:
            observed_content_length = int(content_length_text) if content_length_text is not None else None
        except ValueError as exc:
            raise R7TransportError("invalid Content-Length") from exc
        if observed_content_length != EXPECTED_SIZE_BYTES or len(body) != EXPECTED_SIZE_BYTES:
            raise R7TransportError("Content-Length or body-size mismatch")
        if response_headers.get("etag") != EXPECTED_ETAG:
            raise R7TransportError("ETag mismatch")
        if response_headers.get("x-amz-request-charged") != "requester":
            raise R7TransportError("Requester Pays charge acknowledgement missing")
        if len(body) > MAX_TOTAL_COMPRESSED_BYTES:
            raise R7TransportError("compressed byte cap exceeded")
        compressed_sha = sha256_bytes(body)
        if compressed_sha != EXPECTED_COMPRESSED_SHA256:
            raise R7TransportError("compressed object SHA-256 mismatch")
        result["compressed_bytes"] = len(body)
        result["compressed_sha256"] = compressed_sha
        if not body.startswith(LZ4_FRAME_MAGIC):
            raise R7TransportError("unrecognized LZ4 frame")

        try:
            decompressed_bytes, wallet_index, summary = aggregate_decompressed_chunks(
                iter_lz4_frame(body, MAX_TOTAL_DECOMPRESSED_BYTES)
            )
        except (LZ4FrameError, LZ4FrameLimit) as exc:
            raise R7TransportError("LZ4 decompression failed") from exc
        del body
        if decompressed_bytes != EXPECTED_DECOMPRESSED_BYTES:
            raise R7TransportError("decompressed byte count mismatch")
        result["decompressed_bytes"] = decompressed_bytes
        result["wallet_index_summary"] = summary
        result["wallet_index_retained"] = True
        result["wallet_addresses_retained"] = True
        result["leading_string_values_retained"] = True
        result["per_wallet_fill_counts_retained"] = True
        result["research_conclusion"] = "WALLET_INDEX_RECONSTRUCTION_COMPLETE"
        result["technical_result"] = "WALLET_INDEX_RECONSTRUCTION_COMPLETE"
        result["terminal_status"] = "R7_WALLET_INDEX_STUDY_COMPLETE"
        result["runtime_seconds"] = round(time.monotonic() - started, 6)
        return 0, result, wallet_index
    except R7ReconstructionUnresolved as exc:
        result["terminal_status"] = "R7_WALLET_INDEX_STUDY_COMPLETE"
        result["technical_result"] = "WALLET_INDEX_RECONSTRUCTION_UNRESOLVED"
        result["research_conclusion"] = "WALLET_INDEX_RECONSTRUCTION_UNRESOLVED"
        result["failure_class"] = type(exc).__name__
        result["runtime_seconds"] = round(time.monotonic() - started, 6)
        return 0, result, b""
    except (R7ContractError, R7TransportError, R7JSONError) as exc:
        result["terminal_status"] = "R7_TRANSPORT_OR_INTEGRITY_FAIL"
        result["technical_result"] = "R7_TRANSPORT_OR_INTEGRITY_FAIL"
        result["research_conclusion"] = "R7_TRANSPORT_OR_INTEGRITY_FAIL"
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
