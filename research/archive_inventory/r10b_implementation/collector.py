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
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[3]
from research.archive_inventory.r4.lz4_frame import LZ4FrameError, LZ4FrameLimit, iter_lz4_frame

PREREG = ROOT / "research/archive_inventory/r10b/R10B_BATCH_METADATA_LEXICAL_PREREGISTRATION.json"
APPROVAL_JSON = ROOT / "research/archive_inventory/r10b_approval/APPROVE_HL_ARCHIVE_R10B_BATCH_METADATA_LEXICAL_DIAGNOSTIC_001.json"
APPROVAL_TEXT = ROOT / "research/archive_inventory/r10b_approval/APPROVE_HL_ARCHIVE_R10B_BATCH_METADATA_LEXICAL_DIAGNOSTIC_001.txt"
IMPLEMENTATION = ROOT / "research/archive_inventory/r10b_implementation/R10B_IMPLEMENTATION_CONTRACT.json"

DIAGNOSTIC_ID = "HL-ARCHIVE-R10B-BATCH-METADATA-LEXICAL-DIAGNOSTIC-001"
PREREG_MERGE = "8ba7b0928ac45c66dd6df756491928fddbe2a060"
APPROVAL_MERGE = "0ca8bc4da2dbb3cda073a41c45a72e5f051419cc"
APPROVAL_SHA = "981b9277b652117c2a3648fa3870015d3efe590a595e84bcba22cf0b3f8f8061"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
TARGET = {
    "bucket": "hl-mainnet-node-data",
    "region": "ap-northeast-1",
    "key": "node_fills_by_block/hourly/20250727/9.lz4",
    "size": 18_147_822,
    "etag": '"5a9941a240118a57f77a4c3ee95b8430-3"',
    "compressed_sha256": "42fa96f9d693eb93d184c24a830483cea2e4aa526fc2ffb999619d24e41cc339",
}
REGIONAL_ENDPOINT = f"{TARGET['bucket']}.s3.{TARGET['region']}.amazonaws.com"
EMPTY_PAYLOAD_SHA256 = hashlib.sha256(b"").hexdigest()
MAX_COMPRESSED = TARGET["size"]
MAX_DECOMPRESSED = 268_435_456
MAX_RUNTIME_SECONDS = 120
MAX_RECORD_BYTES = 16_777_216
MAX_BLOCKS = 500_000
MAX_METADATA_STRING_BYTES = 128

CLASS_ORDER = [
    "ISO8601_Z_FRACTION",
    "ISO8601_Z_SECONDS",
    "ISO8601_OFFSET_FRACTION",
    "ISO8601_OFFSET_SECONDS",
    "ISO8601_NAIVE_FRACTION",
    "ISO8601_NAIVE_SECONDS",
    "DECIMAL_INTEGER_STRING",
    "OTHER",
]
CLASS_REGEX_TEXT = {
    "ISO8601_Z_FRACTION": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{1,9}Z$",
    "ISO8601_Z_SECONDS": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
    "ISO8601_OFFSET_FRACTION": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{1,9}[+-]\d{2}:\d{2}$",
    "ISO8601_OFFSET_SECONDS": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$",
    "ISO8601_NAIVE_FRACTION": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{1,9}$",
    "ISO8601_NAIVE_SECONDS": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$",
    "DECIMAL_INTEGER_STRING": r"^\d+$",
    "OTHER": "CATCH_ALL",
}
CLASS_REGEX = {name: re.compile(pattern) for name, pattern in CLASS_REGEX_TEXT.items() if name != "OTHER"}
PREFIX_ORDER = [
    "MATCHES_PATH_DATE_HOUR_PREFIX",
    "MATCHES_PREVIOUS_DATE_HOUR_PREFIX",
    "MATCHES_NEXT_DATE_HOUR_PREFIX",
    "OTHER_PREFIX",
]
PATH_PREFIX = "2025-07-27T09:"
PREVIOUS_PREFIX = "2025-07-27T08:"
NEXT_PREFIX = "2025-07-27T10:"


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


def classify_lexical(value: str) -> str:
    for name in CLASS_ORDER[:-1]:
        if CLASS_REGEX[name].fullmatch(value) is not None:
            return name
    return "OTHER"


def prefix_bucket(value: str) -> str:
    if value.startswith(PATH_PREFIX):
        return "MATCHES_PATH_DATE_HOUR_PREFIX"
    if value.startswith(PREVIOUS_PREFIX):
        return "MATCHES_PREVIOUS_DATE_HOUR_PREFIX"
    if value.startswith(NEXT_PREFIX):
        return "MATCHES_NEXT_DATE_HOUR_PREFIX"
    return "OTHER_PREFIX"


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
    if impl.get("r10b_preregistration_merge_commit") != PREREG_MERGE or impl.get("r10b_approval_merge_commit") != APPROVAL_MERGE:
        raise ContractError("implementation lineage drift")
    if impl.get("approval_text_sha256") != APPROVAL_SHA or impl.get("role_arn") != ROLE_ARN:
        raise ContractError("implementation approval/role drift")
    if impl.get("role_reused_without_mutation") is not True or impl.get("new_role_created") is not False:
        raise ContractError("role boundary drift")
    target = impl.get("exact_network_target", {})
    if target != {
        "bucket": TARGET["bucket"],
        "region": TARGET["region"],
        "key": TARGET["key"],
        "expected_size_bytes": TARGET["size"],
        "expected_etag": TARGET["etag"],
        "expected_compressed_sha256": TARGET["compressed_sha256"],
        "storage_class": "STANDARD",
    }:
        raise ContractError("target drift")
    rules = impl.get("lexical_rules", {})
    if rules.get("class_precedence") != CLASS_ORDER or rules.get("regexes") != CLASS_REGEX_TEXT:
        raise ContractError("lexical class drift")
    if rules.get("prefix_buckets") != PREFIX_ORDER:
        raise ContractError("prefix bucket drift")
    if rules.get("path_date_hour_prefix") != PATH_PREFIX or rules.get("previous_date_hour_prefix") != PREVIOUS_PREFIX or rules.get("next_date_hour_prefix") != NEXT_PREFIX:
        raise ContractError("prefix drift")
    processing = impl.get("processing_contract", {})
    if processing.get("metadata_lexical_processing") is not True or processing.get("aggregate_lexical_retention") is not True:
        raise ContractError("approved lexical processing missing")
    for key in (
        "timezone_parsing", "timezone_inference", "datetime_conversion_of_metadata",
        "individual_metadata_value_retention", "event_array_contents_inspection",
        "event_pair_count_retention", "block_number_value_retention",
        "individual_fill_time_processing", "wallet_address_retention", "wallet_aggregation",
        "economic_fill_field_processing", "raw_object_retention", "raw_block_event_fill_retention",
    ):
        if processing.get(key) is not False:
            raise ContractError(f"forbidden processing opened: {key}")
    for key in (
        "execution_release_present", "canonical_activation_present", "single_workflow_dispatch_authorized",
        "aws_oidc_authorized_now", "requester_pays_authorized_now", "get_object_authorized_now",
        "object_body_download_authorized_now", "decompression_authorized_now",
        "metadata_lexical_processing_authorized_now", "aggregate_lexical_retention_authorized_now",
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
    string_to_sign = "\n".join(
        ["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()]
    )
    k_date = _sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _sign(k_date, TARGET["region"])
    k_service = _sign(k_region, "s3")
    k_signing = _sign(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{scope},"
        f"SignedHeaders={signed_headers},Signature={signature}"
    )
    return REGIONAL_ENDPOINT, canonical_uri, {
        "Host": REGIONAL_ENDPOINT,
        "If-Match": TARGET["etag"],
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


def _zero_counts(keys: list[str]) -> dict[str, int]:
    return {key: 0 for key in keys}


def new_summary(observed_etag: str, compressed: bytes) -> dict:
    return {
        "object_key": TARGET["key"],
        "expected_etag": TARGET["etag"],
        "observed_etag": observed_etag,
        "compressed_bytes": len(compressed),
        "compressed_sha256": sha256_bytes(compressed),
        "decompressed_bytes": 0,
        "block_record_count": 0,
        "local_time_lexical_class_counts": _zero_counts(CLASS_ORDER),
        "block_time_lexical_class_counts": _zero_counts(CLASS_ORDER),
        "local_time_prefix_bucket_counts": _zero_counts(PREFIX_ORDER),
        "block_time_prefix_bucket_counts": _zero_counts(PREFIX_ORDER),
        "local_time_equals_block_time_count": 0,
        "local_time_differs_from_block_time_count": 0,
        "metadata_string_length_min_local_time": None,
        "metadata_string_length_max_local_time": None,
        "metadata_string_length_min_block_time": None,
        "metadata_string_length_max_block_time": None,
        "lexical_diagnostic_classification": None,
    }


class MetadataLexicalAggregator:
    def __init__(self, summary: dict) -> None:
        self.summary = summary

    @staticmethod
    def _byte_length(value: str) -> int:
        return len(value.encode("utf-8"))

    def _add_length(self, field: str, value: str) -> None:
        length = self._byte_length(value)
        if length > MAX_METADATA_STRING_BYTES:
            raise DiagnosticUnresolved(f"{field} metadata string byte cap exceeded")
        min_key = f"metadata_string_length_min_{field}"
        max_key = f"metadata_string_length_max_{field}"
        current_min = self.summary[min_key]
        current_max = self.summary[max_key]
        self.summary[min_key] = length if current_min is None else min(current_min, length)
        self.summary[max_key] = length if current_max is None else max(current_max, length)

    def add_block(self, block: dict) -> None:
        if not isinstance(block, dict):
            raise DiagnosticUnresolved("top-level record is not object")
        for key, expected in (("local_time", str), ("block_time", str), ("block_number", int), ("events", list)):
            value = block.get(key)
            if expected is int:
                if isinstance(value, bool) or not isinstance(value, int):
                    raise DiagnosticUnresolved(f"block field type mismatch: {key}")
            elif not isinstance(value, expected):
                raise DiagnosticUnresolved(f"block field type mismatch: {key}")

        # Contract boundary: the events value is type-checked as an array but is never iterated,
        # counted, indexed, copied, serialized, hashed, or otherwise inspected.
        local_time = block["local_time"]
        block_time = block["block_time"]

        self.summary["block_record_count"] += 1
        if self.summary["block_record_count"] > MAX_BLOCKS:
            raise DiagnosticUnresolved("block record cap exceeded")

        self._add_length("local_time", local_time)
        self._add_length("block_time", block_time)
        self.summary["local_time_lexical_class_counts"][classify_lexical(local_time)] += 1
        self.summary["block_time_lexical_class_counts"][classify_lexical(block_time)] += 1
        self.summary["local_time_prefix_bucket_counts"][prefix_bucket(local_time)] += 1
        self.summary["block_time_prefix_bucket_counts"][prefix_bucket(block_time)] += 1
        if local_time == block_time:
            self.summary["local_time_equals_block_time_count"] += 1
        else:
            self.summary["local_time_differs_from_block_time_count"] += 1

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
        self.add_block(block)

    def finalize(self) -> dict:
        s = self.summary
        count = s["block_record_count"]
        if count < 1:
            raise DiagnosticUnresolved("diagnostic has no parsed block records")
        for key in ("local_time_lexical_class_counts", "block_time_lexical_class_counts"):
            if sum(s[key].values()) != count:
                raise DiagnosticUnresolved(f"{key} conservation failed")
        for key in ("local_time_prefix_bucket_counts", "block_time_prefix_bucket_counts"):
            if sum(s[key].values()) != count:
                raise DiagnosticUnresolved(f"{key} conservation failed")
        if s["local_time_equals_block_time_count"] + s["local_time_differs_from_block_time_count"] != count:
            raise DiagnosticUnresolved("metadata equality conservation failed")

        local_prefixes = s["local_time_prefix_bucket_counts"]
        block_prefixes = s["block_time_prefix_bucket_counts"]
        if (
            local_prefixes["MATCHES_PATH_DATE_HOUR_PREFIX"] == count
            and block_prefixes["MATCHES_PATH_DATE_HOUR_PREFIX"] == count
        ):
            classification = "BATCH_METADATA_LEXICALLY_PATH_HOUR_CONSISTENT"
        elif (
            local_prefixes["MATCHES_PREVIOUS_DATE_HOUR_PREFIX"]
            or local_prefixes["MATCHES_NEXT_DATE_HOUR_PREFIX"]
            or block_prefixes["MATCHES_PREVIOUS_DATE_HOUR_PREFIX"]
            or block_prefixes["MATCHES_NEXT_DATE_HOUR_PREFIX"]
        ):
            classification = "BATCH_METADATA_LEXICALLY_CROSSES_PATH_HOUR"
        else:
            classification = "BATCH_METADATA_LEXICAL_FORMAT_UNRESOLVED"
        s["lexical_diagnostic_classification"] = classification
        return s


def aggregate_lz4_object(compressed: bytes, observed_etag: str) -> dict:
    if len(compressed) != TARGET["size"]:
        raise TransportIntegrityError("compressed object size mismatch before decompression")
    if sha256_bytes(compressed) != TARGET["compressed_sha256"]:
        raise TransportIntegrityError("compressed SHA256 mismatch")
    summary = new_summary(observed_etag, compressed)
    aggregate = MetadataLexicalAggregator(summary)
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
        "schema_version": "1.0",
        "diagnostic_id": DIAGNOSTIC_ID,
        "observed_at_utc": None,
        "terminal_status": None,
        "technical_result": None,
        "research_conclusion": None,
        "failure_class": None,
        "request_attempt_count": 0,
        "s3_http_request_count": 0,
        "successful_request_count": 0,
        "failed_request_count": 0,
        "retries_used": 0,
        "http_redirects_followed": False,
        "requester_pays_requested": True,
        "total_compressed_bytes": 0,
        "total_decompressed_bytes": 0,
        "diagnostic_summary": None,
        "raw_object_retained": False,
        "raw_block_event_fill_retained": False,
        "individual_metadata_value_retained": False,
        "event_array_contents_inspected": False,
        "event_pair_count_retained": False,
        "block_number_value_retained": False,
        "wallet_address_retained": False,
        "wallet_aggregation_performed": False,
        "economic_fill_field_processing_performed": False,
        "individual_fill_time_processing_performed": False,
        "timezone_parsing_performed": False,
        "timezone_inference_performed": False,
        "datetime_conversion_of_metadata_performed": False,
        "r10_rule_amendment_performed": False,
        "r10_rerun_performed": False,
        "six_hour_execution_performed": False,
        "wallet_ranking_performed": False,
        "candidate_shortlisting_performed": False,
        "pnl_or_alpha_analysis_performed": False,
        "copyability_analysis_performed": False,
        "market_data_ingested": False,
        "strategy_inference_performed": False,
        "runtime_seconds": None,
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
        status, response_headers, compressed = transport(
            host,
            path,
            headers,
            TARGET["size"],
            max(1.0, MAX_RUNTIME_SECONDS - (time.monotonic() - started)),
        )
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
            raise TransportIntegrityError("compressed SHA256 mismatch")

        result["successful_request_count"] = 1
        result["total_compressed_bytes"] = len(compressed)
        summary = aggregate_lz4_object(compressed, response_headers["etag"])
        result["total_decompressed_bytes"] = summary["decompressed_bytes"]
        result["diagnostic_summary"] = summary
        result["terminal_status"] = "R10B_BATCH_METADATA_LEXICAL_DIAGNOSTIC_COMPLETE"
        result["technical_result"] = summary["lexical_diagnostic_classification"]
        result["research_conclusion"] = summary["lexical_diagnostic_classification"]
        rc = 0
    except DiagnosticUnresolved as exc:
        result["terminal_status"] = "R10B_BATCH_METADATA_LEXICAL_DIAGNOSTIC_COMPLETE"
        result["technical_result"] = "BATCH_METADATA_LEXICAL_FORMAT_UNRESOLVED"
        result["research_conclusion"] = "BATCH_METADATA_LEXICAL_FORMAT_UNRESOLVED"
        result["failure_class"] = str(exc)
        result["diagnostic_summary"] = None
        rc = 0
    except (TransportIntegrityError, ContractError) as exc:
        result["terminal_status"] = "R10B_TRANSPORT_OR_INTEGRITY_FAIL"
        result["technical_result"] = "R10B_TRANSPORT_OR_INTEGRITY_FAIL"
        result["research_conclusion"] = "R10B_TRANSPORT_OR_INTEGRITY_FAIL"
        result["failure_class"] = str(exc)
        result["diagnostic_summary"] = None
        rc = 84
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
