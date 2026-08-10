from __future__ import annotations

import argparse
import hashlib
import hmac
import http.client
import json
import os
import ssl
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[3]
from research.archive_inventory.r4.lz4_frame import LZ4FrameError, LZ4FrameLimit, iter_lz4_frame

PREREG = ROOT / "research/archive_inventory/r10c/R10C_BOUNDARY_RECORD_CORRELATION_PREREGISTRATION.json"
APPROVAL_JSON = ROOT / "research/archive_inventory/r10c_approval/APPROVE_HL_ARCHIVE_R10C_BOUNDARY_RECORD_CORRELATION_001.json"
APPROVAL_TEXT = ROOT / "research/archive_inventory/r10c_approval/APPROVE_HL_ARCHIVE_R10C_BOUNDARY_RECORD_CORRELATION_001.txt"
IMPLEMENTATION = ROOT / "research/archive_inventory/r10c_implementation/R10C_IMPLEMENTATION_CONTRACT.json"

DIAGNOSTIC_ID = "HL-ARCHIVE-R10C-BOUNDARY-RECORD-CORRELATION-001"
PREREG_MERGE = "a812f7d5b67203c801f856c85b046af8e136c8f3"
APPROVAL_MERGE = "00dbe69b5c17df8ef42a9b573589add290e559d8"
APPROVAL_SHA = "3bea842b40837f791f1c2799822382adbab4f256185a59287b2f635cbaa4bdbe"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
TARGET = {
    "bucket": "hl-mainnet-node-data",
    "region": "ap-northeast-1",
    "key": "node_fills_by_block/hourly/20250727/9.lz4",
    "size": 18_147_822,
    "etag": '"5a9941a240118a57f77a4c3ee95b8430-3"',
    "compressed_sha256": "42fa96f9d693eb93d184c24a830483cea2e4aa526fc2ffb999619d24e41cc339",
    "path_hour_start_ms": 1_753_606_800_000,
    "path_hour_end_ms": 1_753_610_400_000,
}
REGIONAL_ENDPOINT = f"{TARGET['bucket']}.s3.{TARGET['region']}.amazonaws.com"
EMPTY_PAYLOAD_SHA256 = hashlib.sha256(b"").hexdigest()
MAX_COMPRESSED = TARGET["size"]
MAX_DECOMPRESSED = 268_435_456
MAX_RUNTIME_SECONDS = 120
MAX_RECORD_BYTES = 16_777_216
MAX_BLOCKS = 500_000
MAX_EVENTS = 2_000_000
MAX_METADATA_STRING_BYTES = 128

PREFIX_BUCKETS = [
    "MATCHES_PATH_DATE_HOUR_PREFIX",
    "MATCHES_PREVIOUS_DATE_HOUR_PREFIX",
    "MATCHES_NEXT_DATE_HOUR_PREFIX",
    "OTHER_PREFIX",
]
FILL_PARTITIONS = ["BEFORE_PATH_HOUR", "INSIDE_PATH_HOUR", "AFTER_PATH_HOUR"]
PATH_PREFIX = "2025-07-27T09:"
PREVIOUS_PREFIX = "2025-07-27T08:"
NEXT_PREFIX = "2025-07-27T10:"
PARENT_EXPECTED = {
    "block_record_count": 36_029,
    "fill_time_count": 223_950,
    "fill_time_before_path_hour_count": 2,
    "fill_time_inside_path_hour_count": 223_948,
    "fill_time_after_path_hour_count": 0,
    "local_time_path_prefix_count": 36_029,
    "block_time_path_prefix_count": 36_028,
    "block_time_previous_prefix_count": 1,
}

POSITIVE = "EXACT_TWO_PRE_HOUR_FILLS_COLOCATE_WITH_SINGLE_PREVIOUS_BLOCK_TIME_RECORD"
NEGATIVE = "PRE_HOUR_FILLS_DO_NOT_EXACTLY_COLOCATE_WITH_SINGLE_PREVIOUS_BLOCK_TIME_RECORD"
UNRESOLVED = "BOUNDARY_RECORD_CORRELATION_UNRESOLVED"


class ContractError(RuntimeError):
    pass


class TransportIntegrityError(RuntimeError):
    pass


class DiagnosticUnresolved(RuntimeError):
    pass


class StrictJSONError(ValueError):
    pass


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ContractError(f"JSON root must be object: {path}")
    return value


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _strict_object(pairs: list[tuple[str, object]]) -> dict:
    out: dict = {}
    for key, value in pairs:
        if key in out:
            raise StrictJSONError("duplicate JSON object key")
        out[key] = value
    return out


def _reject_nonfinite(_token: str) -> object:
    raise StrictJSONError("non-finite JSON constant")


def strict_loads(text: str) -> object:
    try:
        return json.loads(text, object_pairs_hook=_strict_object, parse_constant=_reject_nonfinite)
    except json.JSONDecodeError as exc:
        raise StrictJSONError(str(exc)) from exc


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def prefix_bucket(value: str) -> str:
    if value.startswith(PATH_PREFIX):
        return "MATCHES_PATH_DATE_HOUR_PREFIX"
    if value.startswith(PREVIOUS_PREFIX):
        return "MATCHES_PREVIOUS_DATE_HOUR_PREFIX"
    if value.startswith(NEXT_PREFIX):
        return "MATCHES_NEXT_DATE_HOUR_PREFIX"
    return "OTHER_PREFIX"


def fill_partition(value_ms: int) -> str:
    if value_ms < TARGET["path_hour_start_ms"]:
        return "BEFORE_PATH_HOUR"
    if value_ms >= TARGET["path_hour_end_ms"]:
        return "AFTER_PATH_HOUR"
    return "INSIDE_PATH_HOUR"


def validate_static_inputs() -> None:
    prereg = load_json(PREREG)
    approval = load_json(APPROVAL_JSON)
    impl = load_json(IMPLEMENTATION)
    if sha256_bytes(APPROVAL_TEXT.read_bytes()) != APPROVAL_SHA:
        raise ContractError("approval text hash drift")
    if prereg.get("diagnostic_id") != DIAGNOSTIC_ID or prereg.get("status") != "PREREGISTERED_NO_EXECUTION":
        raise ContractError("preregistration drift")
    if approval.get("diagnostic_id") != DIAGNOSTIC_ID or approval.get("reviewed_commit") != PREREG_MERGE:
        raise ContractError("approval identity drift")
    if approval.get("exact_approval_text_sha256") != APPROVAL_SHA:
        raise ContractError("approval hash drift")
    if approval.get("execution_authorized_by_this_approval") is not False:
        raise ContractError("approval self-opens execution")
    if impl.get("diagnostic_id") != DIAGNOSTIC_ID or impl.get("status") != "IMPLEMENTED_AWAITING_SEPARATE_EXECUTION_RELEASE":
        raise ContractError("implementation identity drift")
    if impl.get("r10c_preregistration_merge_commit") != PREREG_MERGE or impl.get("r10c_approval_merge_commit") != APPROVAL_MERGE:
        raise ContractError("implementation lineage drift")
    if impl.get("approval_text_sha256") != APPROVAL_SHA or impl.get("role_arn") != ROLE_ARN:
        raise ContractError("implementation approval/role drift")
    if impl.get("role_reused_without_mutation") is not True or impl.get("new_role_created") is not False:
        raise ContractError("role boundary drift")
    target = impl.get("exact_network_target", {})
    expected_target = {
        "bucket": TARGET["bucket"], "region": TARGET["region"], "key": TARGET["key"],
        "expected_size_bytes": TARGET["size"], "expected_etag": TARGET["etag"],
        "expected_compressed_sha256": TARGET["compressed_sha256"],
        "path_hour_start_ms": TARGET["path_hour_start_ms"],
        "path_hour_end_ms_exclusive": TARGET["path_hour_end_ms"],
        "path_date_hour_prefix": PATH_PREFIX, "previous_path_date_hour_prefix": PREVIOUS_PREFIX,
        "next_path_date_hour_prefix": NEXT_PREFIX, "storage_class": "STANDARD",
    }
    if target != expected_target:
        raise ContractError("target drift")
    if impl.get("parent_aggregate_preconditions") != PARENT_EXPECTED:
        raise ContractError("parent aggregate precondition drift")
    processing = impl.get("processing_contract", {})
    for key in (
        "decompression", "metadata_prefix_processing", "event_array_contents_inspection",
        "event_pair_shape_inspection", "fill_time_integer_milliseconds_processing",
        "aggregate_boundary_correlation_retention",
    ):
        if processing.get(key) is not True:
            raise ContractError(f"approved processing missing: {key}")
    if processing.get("event_array_contents_inspection_scope") != "PAIR_SHAPE_AND_FILL_TIME_ONLY":
        raise ContractError("event inspection scope drift")
    if processing.get("fill_object_field_allowlist") != ["time"]:
        raise ContractError("fill field allowlist drift")
    for key in (
        "metadata_timezone_parsing", "metadata_timezone_inference", "metadata_datetime_conversion",
        "individual_metadata_value_retention", "leading_event_string_value_retention",
        "leading_event_string_wallet_semantics", "individual_fill_time_retention",
        "economic_fill_field_processing", "block_number_value_retention", "per_block_identity_retention",
        "per_wallet_processing", "wallet_address_retention", "raw_compressed_object_retention",
        "raw_decompressed_object_retention", "raw_block_record_retention", "raw_event_pair_retention",
    ):
        if processing.get(key) is not False:
            raise ContractError(f"forbidden processing opened: {key}")
    for key in (
        "execution_release_present", "canonical_activation_present", "single_workflow_dispatch_authorized",
        "aws_oidc_authorized_now", "requester_pays_authorized_now", "get_object_authorized_now",
        "object_body_download_authorized_now", "decompression_authorized_now",
        "metadata_prefix_processing_authorized_now", "event_time_processing_authorized_now",
        "aggregate_boundary_correlation_retention_authorized_now",
    ):
        if impl.get(key) is not False:
            raise ContractError(f"implementation self-opens runtime: {key}")
    if impl.get("network_requests_executed") != 0 or impl.get("aws_iam_mutations_executed") != 0 or impl.get("empirical_result") is not None:
        raise ContractError("implementation contains runtime evidence")
    if not all(v is False for v in impl.get("interpretation_boundaries", {}).values()):
        raise ContractError("semantic boundary opened")
    if not all(v is False for v in impl.get("downstream_authorizations", {}).values()):
        raise ContractError("downstream authority opened")
    if not all(v is False for v in impl.get("trading_authorizations", {}).values()):
        raise ContractError("trading authority opened")


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
        raise ContractError("temporary AWS credentials missing")
    if request_time.tzinfo is None:
        raise ContractError("signing time must be timezone-aware")
    stamp = request_time.astimezone(timezone.utc)
    amz_date = stamp.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = stamp.strftime("%Y%m%d")
    canonical_uri = _aws_quote_path(TARGET["key"])
    canonical_headers = (
        f"host:{REGIONAL_ENDPOINT}\n"
        f"if-match:{TARGET['etag']}\n"
        f"x-amz-content-sha256:{EMPTY_PAYLOAD_SHA256}\n"
        f"x-amz-date:{amz_date}\n"
        "x-amz-request-payer:requester\n"
        f"x-amz-security-token:{session_token}\n"
    )
    signed_headers = "host;if-match;x-amz-content-sha256;x-amz-date;x-amz-request-payer;x-amz-security-token"
    canonical_request = "\n".join(["GET", canonical_uri, "", canonical_headers, signed_headers, EMPTY_PAYLOAD_SHA256])
    scope = f"{date_stamp}/{TARGET['region']}/s3/aws4_request"
    string_to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical_request.encode()).hexdigest()])
    k_date = _sign(("AWS4" + secret_key).encode(), date_stamp)
    k_region = _sign(k_date, TARGET["region"])
    k_service = _sign(k_region, "s3")
    k_signing = _sign(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()
    authorization = f"AWS4-HMAC-SHA256 Credential={access_key}/{scope},SignedHeaders={signed_headers},Signature={signature}"
    return REGIONAL_ENDPOINT, canonical_uri, {
        "Host": REGIONAL_ENDPOINT,
        "If-Match": TARGET["etag"],
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


def block_pair_key(local_bucket: str, block_bucket: str) -> str:
    return f"{local_bucket}|{block_bucket}"


def fill_key(local_bucket: str, block_bucket: str, partition: str) -> str:
    return f"{local_bucket}|{block_bucket}|{partition}"


def new_summary(observed_etag: str, compressed: bytes) -> dict:
    block_counts = {block_pair_key(local, block): 0 for local in PREFIX_BUCKETS for block in PREFIX_BUCKETS}
    fill_counts = {fill_key(local, block, part): 0 for local in PREFIX_BUCKETS for block in PREFIX_BUCKETS for part in FILL_PARTITIONS}
    before_blocks = {block_pair_key(local, block): 0 for local in PREFIX_BUCKETS for block in PREFIX_BUCKETS}
    return {
        "object_key": TARGET["key"], "expected_etag": TARGET["etag"], "observed_etag": observed_etag,
        "compressed_bytes": len(compressed), "compressed_sha256": sha256_bytes(compressed), "decompressed_bytes": 0,
        "block_record_count": 0, "event_pair_count": 0, "fill_time_count": 0,
        "fill_time_before_path_hour_count": 0, "fill_time_inside_path_hour_count": 0,
        "fill_time_after_path_hour_count": 0,
        "block_record_counts_by_local_prefix_and_block_prefix": block_counts,
        "fill_counts_by_local_prefix_block_prefix_and_fill_partition": fill_counts,
        "block_records_with_before_fill_by_local_prefix_and_block_prefix": before_blocks,
        "block_record_count_with_any_before_fill": 0,
        "boundary_record_correlation_classification": None,
    }


class BoundaryCorrelationAggregator:
    def __init__(self, summary: dict) -> None:
        self.summary = summary

    def add_line(self, raw_line: bytes) -> None:
        if raw_line.endswith(b"\r"):
            raw_line = raw_line[:-1]
        if not raw_line.strip():
            return
        if len(raw_line) > MAX_RECORD_BYTES:
            raise DiagnosticUnresolved("block record byte cap exceeded")
        try:
            block = strict_loads(raw_line.decode("utf-8", errors="strict"))
        except (UnicodeDecodeError, StrictJSONError) as exc:
            raise DiagnosticUnresolved("strict block parse failed") from exc
        if not isinstance(block, dict):
            raise DiagnosticUnresolved("top-level record is not object")
        local_time = block.get("local_time")
        block_time = block.get("block_time")
        block_number = block.get("block_number")
        events = block.get("events")
        if not isinstance(local_time, str) or not isinstance(block_time, str):
            raise DiagnosticUnresolved("metadata field type mismatch")
        if isinstance(block_number, bool) or not isinstance(block_number, int):
            raise DiagnosticUnresolved("block_number field type mismatch")
        if not isinstance(events, list):
            raise DiagnosticUnresolved("events field type mismatch")
        if len(local_time.encode("utf-8")) > MAX_METADATA_STRING_BYTES or len(block_time.encode("utf-8")) > MAX_METADATA_STRING_BYTES:
            raise DiagnosticUnresolved("metadata string byte cap exceeded")

        local_bucket = prefix_bucket(local_time)
        block_bucket = prefix_bucket(block_time)
        pair_key = block_pair_key(local_bucket, block_bucket)
        self.summary["block_record_count"] += 1
        if self.summary["block_record_count"] > MAX_BLOCKS:
            raise DiagnosticUnresolved("block record cap exceeded")
        self.summary["block_record_counts_by_local_prefix_and_block_prefix"][pair_key] += 1

        before_in_record = 0
        for pair in events:
            self.summary["event_pair_count"] += 1
            if self.summary["event_pair_count"] > MAX_EVENTS:
                raise DiagnosticUnresolved("event pair cap exceeded")
            if not (isinstance(pair, list) and len(pair) == 2 and isinstance(pair[0], str) and isinstance(pair[1], dict)):
                raise DiagnosticUnresolved("event differs from [string, object] contract")
            fill = pair[1]
            fill_time = fill.get("time")
            if isinstance(fill_time, bool) or not isinstance(fill_time, int) or fill_time < 0:
                raise DiagnosticUnresolved("fill time must be nonnegative integer milliseconds")
            partition = fill_partition(fill_time)
            self.summary["fill_time_count"] += 1
            self.summary[f"fill_time_{partition.lower()}_count"] += 1
            self.summary["fill_counts_by_local_prefix_block_prefix_and_fill_partition"][fill_key(local_bucket, block_bucket, partition)] += 1
            if partition == "BEFORE_PATH_HOUR":
                before_in_record += 1

        if before_in_record:
            self.summary["block_record_count_with_any_before_fill"] += 1
            self.summary["block_records_with_before_fill_by_local_prefix_and_block_prefix"][pair_key] += 1

    def finalize(self) -> dict:
        classify_correlation(self.summary)
        return self.summary


def _sum_block_prefix(summary: dict, *, local: str | None = None, block: str | None = None) -> int:
    total = 0
    for local_bucket in PREFIX_BUCKETS:
        for block_bucket in PREFIX_BUCKETS:
            if local is not None and local_bucket != local:
                continue
            if block is not None and block_bucket != block:
                continue
            total += summary["block_record_counts_by_local_prefix_and_block_prefix"][block_pair_key(local_bucket, block_bucket)]
    return total


def classify_correlation(summary: dict, expected: dict[str, int] | None = None) -> str:
    expected = PARENT_EXPECTED if expected is None else expected
    required = {
        "block_record_count": summary["block_record_count"],
        "fill_time_count": summary["fill_time_count"],
        "fill_time_before_path_hour_count": summary["fill_time_before_path_hour_count"],
        "fill_time_inside_path_hour_count": summary["fill_time_inside_path_hour_count"],
        "fill_time_after_path_hour_count": summary["fill_time_after_path_hour_count"],
        "local_time_path_prefix_count": _sum_block_prefix(summary, local="MATCHES_PATH_DATE_HOUR_PREFIX"),
        "block_time_path_prefix_count": _sum_block_prefix(summary, block="MATCHES_PATH_DATE_HOUR_PREFIX"),
        "block_time_previous_prefix_count": _sum_block_prefix(summary, block="MATCHES_PREVIOUS_DATE_HOUR_PREFIX"),
    }
    if required != expected:
        raise DiagnosticUnresolved(f"parent aggregate precondition mismatch: {required}")
    if sum(summary["fill_counts_by_local_prefix_block_prefix_and_fill_partition"].values()) != summary["fill_time_count"]:
        raise DiagnosticUnresolved("fill aggregate conservation failed")
    if sum(summary["block_record_counts_by_local_prefix_and_block_prefix"].values()) != summary["block_record_count"]:
        raise DiagnosticUnresolved("block aggregate conservation failed")
    partition_total = (
        summary["fill_time_before_path_hour_count"] + summary["fill_time_inside_path_hour_count"] + summary["fill_time_after_path_hour_count"]
    )
    if partition_total != summary["fill_time_count"]:
        raise DiagnosticUnresolved("fill partition conservation failed")

    target_pair = block_pair_key("MATCHES_PATH_DATE_HOUR_PREFIX", "MATCHES_PREVIOUS_DATE_HOUR_PREFIX")
    target_before = fill_key("MATCHES_PATH_DATE_HOUR_PREFIX", "MATCHES_PREVIOUS_DATE_HOUR_PREFIX", "BEFORE_PATH_HOUR")
    positive = (
        summary["block_record_counts_by_local_prefix_and_block_prefix"][target_pair] == 1
        and summary["fill_counts_by_local_prefix_block_prefix_and_fill_partition"][target_before] == 2
        and summary["block_records_with_before_fill_by_local_prefix_and_block_prefix"][target_pair] == 1
        and summary["block_record_count_with_any_before_fill"] == 1
    )
    classification = POSITIVE if positive else NEGATIVE
    summary["boundary_record_correlation_classification"] = classification
    return classification


def aggregate_lz4_object(compressed: bytes, observed_etag: str) -> dict:
    summary = new_summary(observed_etag, compressed)
    aggregate = BoundaryCorrelationAggregator(summary)
    pending = bytearray()
    try:
        chunks: Iterable[bytes] = iter_lz4_frame(compressed, MAX_DECOMPRESSED)
        for chunk in chunks:
            summary["decompressed_bytes"] += len(chunk)
            if summary["decompressed_bytes"] > MAX_DECOMPRESSED:
                raise TransportIntegrityError("decompressed byte cap exceeded")
            pending.extend(chunk)
            while True:
                newline = pending.find(b"\n")
                if newline < 0:
                    break
                line = bytes(pending[:newline])
                del pending[: newline + 1]
                aggregate.add_line(line)
            if len(pending) > MAX_RECORD_BYTES:
                raise DiagnosticUnresolved("record byte cap exceeded before newline")
        if pending:
            aggregate.add_line(bytes(pending))
    except LZ4FrameLimit as exc:
        raise TransportIntegrityError(exc.status) from exc
    except LZ4FrameError as exc:
        raise TransportIntegrityError(str(exc)) from exc
    return aggregate.finalize()


def base_result() -> dict:
    return {
        "schema_version": "1.0", "diagnostic_id": DIAGNOSTIC_ID, "observed_at_utc": None,
        "terminal_status": None, "technical_result": None, "research_conclusion": None, "failure_class": None,
        "request_attempt_count": 0, "s3_http_request_count": 0, "successful_request_count": 0,
        "failed_request_count": 0, "retries_used": 0, "http_redirects_followed": False,
        "requester_pays_requested": True, "total_compressed_bytes": 0, "total_decompressed_bytes": 0,
        "diagnostic_summary": None,
        "metadata_prefix_processing_performed": False, "event_array_contents_inspected": False,
        "event_pair_shape_inspection_performed": False, "fill_time_processing_performed": False,
        "aggregate_boundary_correlation_retained": False,
        "metadata_timezone_parsing_performed": False, "metadata_timezone_inference_performed": False,
        "metadata_datetime_conversion_performed": False, "individual_metadata_value_retained": False,
        "individual_fill_time_retained": False, "leading_event_string_value_retained": False,
        "leading_event_string_wallet_semantics_performed": False, "wallet_address_retained": False,
        "wallet_aggregation_performed": False, "economic_fill_field_processing_performed": False,
        "block_number_value_retained": False, "per_block_identity_retained": False,
        "raw_compressed_object_retained": False, "raw_decompressed_object_retained": False,
        "raw_block_record_retained": False, "raw_event_pair_retained": False,
        "r10_rule_amendment_performed": False, "r10_rerun_performed": False,
        "six_hour_execution_performed": False, "wallet_ranking_performed": False,
        "candidate_shortlisting_performed": False, "pnl_or_alpha_analysis_performed": False,
        "copyability_analysis_performed": False, "market_data_ingested": False,
        "strategy_inference_performed": False, "runtime_seconds": None,
    }


def execute(
    transport: Callable[[str, str, dict[str, str], int, float], tuple[int, dict[str, str], bytes]] = https_transport,
    request_time: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    env: dict[str, str] | None = None,
) -> tuple[int, dict]:
    validate_static_inputs()
    started = time.monotonic()
    result = base_result()
    try:
        host, path, headers = build_signed_request(request_time(), env)
        if host != REGIONAL_ENDPOINT or path != _aws_quote_path(TARGET["key"]):
            raise ContractError("signed target drift")
        if headers.get("If-Match") != TARGET["etag"] or headers.get("x-amz-request-payer") != "requester":
            raise ContractError("signed request guard drift")
        result["request_attempt_count"] = 1
        result["s3_http_request_count"] = 1
        status, response_headers, compressed = transport(host, path, headers, TARGET["size"], max(1.0, MAX_RUNTIME_SECONDS - (time.monotonic() - started)))
        if status != 200:
            result["failed_request_count"] = 1
            raise TransportIntegrityError(f"S3 HTTP status {status}")
        if response_headers.get("x-amz-request-charged", "").lower() != "requester":
            result["failed_request_count"] = 1
            raise TransportIntegrityError("missing requester-charged response header")
        if response_headers.get("etag") != TARGET["etag"]:
            result["failed_request_count"] = 1
            raise TransportIntegrityError("response ETag mismatch")
        try:
            content_length = int(response_headers.get("content-length", ""))
        except ValueError as exc:
            result["failed_request_count"] = 1
            raise TransportIntegrityError("invalid content-length") from exc
        if content_length != TARGET["size"] or len(compressed) != TARGET["size"] or len(compressed) > MAX_COMPRESSED:
            result["failed_request_count"] = 1
            raise TransportIntegrityError("compressed content length mismatch")
        if sha256_bytes(compressed) != TARGET["compressed_sha256"]:
            result["failed_request_count"] = 1
            raise TransportIntegrityError("compressed SHA-256 mismatch")
        result["successful_request_count"] = 1
        result["total_compressed_bytes"] = len(compressed)
        summary = aggregate_lz4_object(compressed, response_headers["etag"])
        result["total_decompressed_bytes"] = summary["decompressed_bytes"]
        result["diagnostic_summary"] = summary
        result["terminal_status"] = "R10C_BOUNDARY_RECORD_CORRELATION_COMPLETE"
        result["technical_result"] = summary["boundary_record_correlation_classification"]
        result["research_conclusion"] = summary["boundary_record_correlation_classification"]
        result["metadata_prefix_processing_performed"] = True
        result["event_array_contents_inspected"] = True
        result["event_pair_shape_inspection_performed"] = True
        result["fill_time_processing_performed"] = True
        result["aggregate_boundary_correlation_retained"] = True
        rc = 0
    except DiagnosticUnresolved as exc:
        result["terminal_status"] = "R10C_BOUNDARY_RECORD_CORRELATION_COMPLETE"
        result["technical_result"] = UNRESOLVED
        result["research_conclusion"] = UNRESOLVED
        result["failure_class"] = str(exc)
        result["diagnostic_summary"] = None
        rc = 0
    except (TransportIntegrityError, ContractError) as exc:
        result["terminal_status"] = "R10C_TRANSPORT_OR_INTEGRITY_FAIL"
        result["technical_result"] = "R10C_TRANSPORT_OR_INTEGRITY_FAIL"
        result["research_conclusion"] = "R10C_TRANSPORT_OR_INTEGRITY_FAIL"
        result["failure_class"] = str(exc)
        result["diagnostic_summary"] = None
        rc = 85
    result["observed_at_utc"] = utc_now()
    result["runtime_seconds"] = round(time.monotonic() - started, 6)
    return rc, result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-output", required=True)
    args = parser.parse_args(argv)
    rc, result = execute()
    Path(args.result_output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
