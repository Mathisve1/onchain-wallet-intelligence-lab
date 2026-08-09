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
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[3]
R6A_ROOT = ROOT / "research/archive_inventory/r6a"
R4_ROOT = ROOT / "research/archive_inventory/r4"
if str(R4_ROOT) not in sys.path:
    sys.path.insert(0, str(R4_ROOT))
from lz4_frame import LZ4_FRAME_MAGIC, LZ4FrameError, LZ4FrameLimit, iter_lz4_frame

PREREGISTRATION = R6A_ROOT / "LEGACY_USER_KEY_LEXICAL_R6A_CONTRACT.json"
IMPLEMENTATION = R6A_ROOT / "R6A_IMPLEMENTATION_CONTRACT.json"
APPROVAL_JSON = R6A_ROOT / "approvals/APPROVE_HL_ARCHIVE_LEGACY_USER_KEY_LEXICAL_R6A_001.json"
APPROVAL_TEXT = R6A_ROOT / "approvals/APPROVE_HL_ARCHIVE_LEGACY_USER_KEY_LEXICAL_R6A_001.txt"
ROLE_REUSE = R6A_ROOT / "R6A_AWS_ROLE_REUSE_ANALYSIS.json"

PILOT_ID = "HL-ARCHIVE-LEGACY-USER-KEY-LEXICAL-R6A-001"
PREREGISTRATION_COMMIT = "870fdf3e10a761d6c4589d43def8e436f3a129b5"
APPROVAL_MERGE_COMMIT = "06c0086f80cdbc3d058bdeea64b618da276e95ec"
APPROVAL_ID = "APPROVE_HL_ARCHIVE_LEGACY_USER_KEY_LEXICAL_R6A_001"
APPROVAL_TEXT_SHA256 = "b24c67f527a320e533408fd821d10b5e2ea01d020c837e87ae5e5bbd386c94ed"
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
EMPTY_PAYLOAD_SHA256 = hashlib.sha256(b"").hexdigest()
ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
LOWERCASE_ADDRESS_RE = re.compile(r"^0x[0-9a-f]{40}$")
ALLOWED_RESEARCH_CONCLUSIONS = {
    "ALL_LEADING_STRINGS_MATCH_HYPERLIQUID_ADDRESS_SHAPE",
    "SOME_LEADING_STRINGS_DO_NOT_MATCH_HYPERLIQUID_ADDRESS_SHAPE",
    "R6A_LEXICAL_SHAPE_UNRESOLVED",
    "R6A_TRANSPORT_OR_INTEGRITY_FAIL",
}


class R6AContractError(RuntimeError):
    pass


class R6ATransportError(RuntimeError):
    pass


class R6ALexicalUnresolved(RuntimeError):
    pass


class R6AJSONError(ValueError):
    pass


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise R6AContractError(f"JSON root must be object: {path}")
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
        raise R6AContractError("approval text hash drift")
    if prereg.get("pilot_id") != PILOT_ID or prereg.get("status") != "PREREGISTERED_STATIC_NO_EXECUTION":
        raise R6AContractError("preregistration identity/status drift")
    if approval.get("approval_id") != APPROVAL_ID or approval.get("reviewed_commit") != PREREGISTRATION_COMMIT:
        raise R6AContractError("approval identity drift")
    if approval.get("exact_approval_text_sha256") != APPROVAL_TEXT_SHA256:
        raise R6AContractError("approval hash drift")
    if impl.get("pilot_id") != PILOT_ID or impl.get("status") != "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION":
        raise R6AContractError("implementation identity/status drift")
    if impl.get("preregistration_commit") != PREREGISTRATION_COMMIT:
        raise R6AContractError("implementation preregistration drift")
    if impl.get("approval_merge_commit") != APPROVAL_MERGE_COMMIT or impl.get("approval_text_sha256") != APPROVAL_TEXT_SHA256:
        raise R6AContractError("implementation approval binding drift")

    target = prereg.get("exact_future_network_target")
    expected_target = {
        "bucket": TARGET_BUCKET,
        "signing_region": SIGNING_REGION,
        "regional_virtual_hosted_endpoint": REGIONAL_ENDPOINT,
        "key": OBJECT_KEY,
        "expected_size_bytes": EXPECTED_SIZE_BYTES,
        "expected_etag": EXPECTED_ETAG,
        "expected_compressed_sha256": EXPECTED_COMPRESSED_SHA256,
        "expected_decompressed_byte_count": EXPECTED_DECOMPRESSED_BYTES,
    }
    if target != expected_target:
        raise R6AContractError("preregistration target drift")
    if impl.get("object") != {k: v for k, v in expected_target.items() if k not in {"bucket", "signing_region", "regional_virtual_hosted_endpoint"}}:
        raise R6AContractError("implementation object drift")

    envelope = prereg.get("proposed_future_execution_envelope", {})
    for name, expected in {
        "maximum_one_time_budget_eur": 0.1,
        "maximum_monthly_budget_eur": 0,
        "maximum_get_object_requests": MAX_REQUESTS,
        "maximum_requests_per_object": 1,
        "maximum_total_compressed_bytes": MAX_TOTAL_COMPRESSED_BYTES,
        "maximum_total_decompressed_bytes": MAX_TOTAL_DECOMPRESSED_BYTES,
        "maximum_runtime_seconds": MAX_RUNTIME_SECONDS,
        "maximum_retries_per_request": 0,
    }.items():
        if approval.get(name) != expected or impl.get(name) != expected or envelope.get(name) != expected:
            raise R6AContractError(f"execution envelope drift: {name}")

    classifier = prereg.get("proposed_streaming_lexical_classifier", {})
    for name, expected in {
        "maximum_record_bytes": MAX_RECORD_BYTES,
        "maximum_records_parsed": MAX_RECORDS,
        "expected_nonempty_record_count": EXPECTED_NONEMPTY_RECORDS,
    }.items():
        if approval.get(name) != expected or impl.get(name) != expected or classifier.get(name) != expected:
            raise R6AContractError(f"classifier cap drift: {name}")
    if classifier.get("required_top_level_record_type") != "array" or impl.get("required_top_level_record_type") != "array":
        raise R6AContractError("record root requirement drift")
    if classifier.get("required_array_arity") != 2 or impl.get("required_array_arity") != 2:
        raise R6AContractError("array arity requirement drift")
    if classifier.get("required_ordered_element_types") != ["string", "object"] or impl.get("required_ordered_element_types") != ["string", "object"]:
        raise R6AContractError("ordered element type requirement drift")

    if approval.get("target_bucket") != TARGET_BUCKET or approval.get("signing_region") != SIGNING_REGION:
        raise R6AContractError("approval target drift")
    if approval.get("object_key") != OBJECT_KEY or approval.get("object_size_bytes") != EXPECTED_SIZE_BYTES:
        raise R6AContractError("approval object drift")
    if approval.get("object_etag") != EXPECTED_ETAG:
        raise R6AContractError("approval etag drift")
    if approval.get("expected_compressed_sha256") != EXPECTED_COMPRESSED_SHA256:
        raise R6AContractError("approval compressed hash drift")
    if approval.get("expected_decompressed_byte_count") != EXPECTED_DECOMPRESSED_BYTES:
        raise R6AContractError("approval decompressed byte count drift")

    for name in (
        "requester_pays_authorized_for_later_release",
        "get_object_authorized_for_later_release",
        "decompression_authorized_for_later_release",
        "lexical_classification_authorized_for_later_release",
    ):
        if approval.get(name) is not True:
            raise R6AContractError(f"approved future capability missing: {name}")
    if not all(value is True for value in approval.get("lexical_count_authorizations", {}).values()):
        raise R6AContractError("lexical count scope drift")
    if not all(value is False for value in approval.get("retention_authorizations", {}).values()):
        raise R6AContractError("approval retention authority opened")
    if not all(value is False for value in approval.get("downstream_authorizations", {}).values()):
        raise R6AContractError("approval downstream authority opened")
    if not all(value is False for value in approval.get("trading_authorizations", {}).values()):
        raise R6AContractError("approval trading authority opened")
    if not all(value is False for value in approval.get("current_runtime_authority", {}).values()):
        raise R6AContractError("approval snapshot self-opens runtime")

    for name in (
        "execution_authorized",
        "paid_request_authorized",
        "requester_pays_authorized",
        "get_object_authorized",
        "object_body_download_authorized",
        "decompression_authorized",
        "lexical_classification_authorized",
    ):
        if impl.get(name) is not False:
            raise R6AContractError(f"implementation current authority opened: {name}")
    if impl.get("execution_release_present") is not False:
        raise R6AContractError("implementation snapshot contains a release")
    if impl.get("expected_canonical_implementation_commit") != "PENDING_CANONICAL_IMPLEMENTATION_MERGE":
        raise R6AContractError("implementation must remain pending")
    if impl.get("s3_requests_executed") != 0 or impl.get("compressed_bytes_downloaded") != 0 or impl.get("decompressed_bytes_processed") != 0:
        raise R6AContractError("implementation snapshot contains execution")
    if impl.get("empirical_result") is not None:
        raise R6AContractError("implementation snapshot contains empirical result")
    for name in (
        "raw_compressed_object_retention_authorized",
        "raw_decompressed_payload_retention_authorized",
        "record_payload_retention_authorized",
        "payload_values_in_evidence_authorized",
        "string_values_in_evidence_authorized",
        "numeric_values_in_evidence_authorized",
        "leading_string_retention_authorized",
        "wallet_address_retention_authorized",
        "leading_string_hash_retention_authorized",
        "distinct_address_set_retention_authorized",
        "wallet_reconstruction_authorized",
        "entity_clustering_authorized",
        "copyability_analysis_authorized",
        "pnl_or_alpha_analysis_authorized",
        "market_data_ingestion_authorized",
    ):
        if impl.get(name) is not False:
            raise R6AContractError(f"forbidden implementation capability opened: {name}")
    if not all(value is False for value in impl.get("trading_authorizations", {}).values()):
        raise R6AContractError("implementation trading authority opened")

    if impl.get("reused_dedicated_role_arn") != ROLE_ARN:
        raise R6AContractError("role reuse ARN drift")
    if impl.get("aws_role_mutation_required") is not False or impl.get("aws_role_mutation_authorized") is not False:
        raise R6AContractError("role mutation boundary drift")
    if impl.get("session_s3_policy") != "ALLOW_GETOBJECT_EXACT_R5_BOUND_LEGACY_OBJECT_ONLY":
        raise R6AContractError("session policy drift")
    if impl.get("session_policy_strict_subset_of_persistent_role") is not True:
        raise R6AContractError("session subset proof drift")
    if role_reuse.get("reused_role_arn") != ROLE_ARN or role_reuse.get("aws_iam_mutation_performed") is not False:
        raise R6AContractError("role reuse evidence drift")
    if role_reuse.get("new_sts_preflight_required") is not False:
        raise R6AContractError("unexpected new STS preflight requirement")
    if role_reuse.get("r6a_session_scope", {}).get("allowed_object_arns") != [f"arn:aws:s3:::{TARGET_BUCKET}/{OBJECT_KEY}"]:
        raise R6AContractError("role reuse session scope drift")

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
        raise R6AContractError("temporary AWS credentials missing")
    if request_time.tzinfo is None:
        raise R6AContractError("signing time must be timezone-aware")

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
            raise R6AJSONError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_nonfinite(_token: str) -> object:
    raise R6AJSONError("non-finite JSON constant")


def _strict_loads(text: str) -> object:
    try:
        return json.loads(text, object_pairs_hook=_strict_object, parse_constant=_reject_nonfinite)
    except (json.JSONDecodeError, R6AJSONError) as exc:
        raise R6AJSONError("strict JSON parse failed") from exc


class LexicalAggregator:
    def __init__(self) -> None:
        self.nonempty_record_count = 0
        self.pair_string_object_record_count = 0
        self.leading_string_count = 0
        self.leading_string_length_42_count = 0
        self.leading_string_0x40hex_count = 0
        self.leading_string_lowercase_0x40hex_count = 0

    def add_line(self, line: bytes) -> None:
        if line.endswith(b"\r"):
            line = line[:-1]
        if not line.strip():
            return
        if len(line) > MAX_RECORD_BYTES:
            raise R6ALexicalUnresolved("record byte limit exceeded")
        try:
            text = line.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise R6ALexicalUnresolved("non-UTF8 record") from exc
        try:
            value = _strict_loads(text)
        except R6AJSONError as exc:
            raise R6ALexicalUnresolved("strict JSON record parse failed") from exc

        self.nonempty_record_count += 1
        if self.nonempty_record_count > MAX_RECORDS:
            raise R6ALexicalUnresolved("record count limit exceeded")
        if not (
            isinstance(value, list)
            and len(value) == 2
            and isinstance(value[0], str)
            and isinstance(value[1], dict)
        ):
            del value
            return

        self.pair_string_object_record_count += 1
        leading = value[0]
        self.leading_string_count += 1
        if len(leading) == 42:
            self.leading_string_length_42_count += 1
        if ADDRESS_RE.fullmatch(leading) is not None:
            self.leading_string_0x40hex_count += 1
        if LOWERCASE_ADDRESS_RE.fullmatch(leading) is not None:
            self.leading_string_lowercase_0x40hex_count += 1
        del leading
        del value

    def evidence(self) -> dict:
        return {
            "nonempty_record_count": self.nonempty_record_count,
            "pair_string_object_record_count": self.pair_string_object_record_count,
            "leading_string_count": self.leading_string_count,
            "leading_string_length_42_count": self.leading_string_length_42_count,
            "leading_string_0x40hex_count": self.leading_string_0x40hex_count,
            "leading_string_lowercase_0x40hex_count": self.leading_string_lowercase_0x40hex_count,
            "leading_string_non_0x40hex_count": self.leading_string_count - self.leading_string_0x40hex_count,
        }


def aggregate_decompressed_chunks(chunks: Iterable[bytes]) -> tuple[int, dict]:
    aggregate = LexicalAggregator()
    pending = bytearray()
    decompressed_bytes = 0
    for chunk in chunks:
        decompressed_bytes += len(chunk)
        if decompressed_bytes > MAX_TOTAL_DECOMPRESSED_BYTES:
            raise R6ATransportError("decompressed byte cap exceeded")
        pending.extend(chunk)
        while True:
            newline = pending.find(b"\n")
            if newline < 0:
                break
            line = bytes(pending[:newline])
            del pending[: newline + 1]
            aggregate.add_line(line)
        if len(pending) > MAX_RECORD_BYTES:
            raise R6ALexicalUnresolved("record byte limit exceeded before newline")
    if pending:
        aggregate.add_line(bytes(pending))
        pending.clear()
    return decompressed_bytes, aggregate.evidence()


def classify_lexical_evidence(evidence: dict) -> str:
    if evidence.get("nonempty_record_count") != EXPECTED_NONEMPTY_RECORDS:
        return "R6A_LEXICAL_SHAPE_UNRESOLVED"
    if evidence.get("pair_string_object_record_count") != EXPECTED_NONEMPTY_RECORDS:
        return "R6A_LEXICAL_SHAPE_UNRESOLVED"
    if evidence.get("leading_string_count") != EXPECTED_NONEMPTY_RECORDS:
        return "R6A_LEXICAL_SHAPE_UNRESOLVED"
    if evidence.get("leading_string_0x40hex_count") == EXPECTED_NONEMPTY_RECORDS:
        return "ALL_LEADING_STRINGS_MATCH_HYPERLIQUID_ADDRESS_SHAPE"
    return "SOME_LEADING_STRINGS_DO_NOT_MATCH_HYPERLIQUID_ADDRESS_SHAPE"


def execute(
    transport: Callable[[str, str, dict[str, str], int, float], tuple[int, dict[str, str], bytes]] = https_transport,
    request_time: Callable[[], datetime] = signing_now,
    env: dict[str, str] | None = None,
) -> tuple[int, dict]:
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
        "lexical_aggregates": None,
        "raw_compressed_object_persisted": False,
        "raw_decompressed_payload_retained": False,
        "record_payload_retained": False,
        "payload_values_retained": False,
        "string_values_retained": False,
        "numeric_values_retained": False,
        "leading_string_values_retained": False,
        "wallet_addresses_retained": False,
        "leading_string_hashes_retained": False,
        "distinct_address_set_retained": False,
        "wallet_reconstruction_performed": False,
        "entity_clustering_performed": False,
        "copyability_analysis_performed": False,
        "pnl_or_alpha_analysis_performed": False,
        "market_data_ingested": False,
        "runtime_seconds": None,
        "failure_class": None,
    }
    try:
        if time.monotonic() - started > MAX_RUNTIME_SECONDS:
            raise R6ATransportError("runtime limit reached before request")
        host, path, headers = build_signed_request(request_time(), env)
        attempts += 1
        result["request_attempt_count"] = attempts
        result["s3_http_request_count"] = attempts
        if attempts > MAX_REQUESTS:
            raise R6ATransportError("request cap exceeded")
        remaining = max(1.0, MAX_RUNTIME_SECONDS - (time.monotonic() - started))
        status, response_headers, body = transport(host, path, headers, EXPECTED_SIZE_BYTES, remaining)
        if status != 200:
            result["failed_request_count"] = 1
            raise R6ATransportError("non-200 S3 response")
        result["successful_request_count"] = 1

        content_length_text = response_headers.get("content-length")
        try:
            observed_content_length = int(content_length_text) if content_length_text is not None else None
        except ValueError as exc:
            raise R6ATransportError("invalid Content-Length") from exc
        if observed_content_length != EXPECTED_SIZE_BYTES or len(body) != EXPECTED_SIZE_BYTES:
            raise R6ATransportError("Content-Length or body-size mismatch")
        if response_headers.get("etag") != EXPECTED_ETAG:
            raise R6ATransportError("ETag mismatch")
        if response_headers.get("x-amz-request-charged") != "requester":
            raise R6ATransportError("Requester Pays charge acknowledgement missing")
        if len(body) > MAX_TOTAL_COMPRESSED_BYTES:
            raise R6ATransportError("compressed byte cap exceeded")
        compressed_sha = sha256_bytes(body)
        if compressed_sha != EXPECTED_COMPRESSED_SHA256:
            raise R6ATransportError("compressed object SHA-256 mismatch")
        result["compressed_bytes"] = len(body)
        result["compressed_sha256"] = compressed_sha
        if not body.startswith(LZ4_FRAME_MAGIC):
            raise R6ATransportError("unrecognized LZ4 frame")

        try:
            decompressed_bytes, evidence = aggregate_decompressed_chunks(
                iter_lz4_frame(body, MAX_TOTAL_DECOMPRESSED_BYTES)
            )
        except (LZ4FrameError, LZ4FrameLimit) as exc:
            raise R6ATransportError("LZ4 decompression failed") from exc
        del body
        if decompressed_bytes != EXPECTED_DECOMPRESSED_BYTES:
            raise R6ATransportError("decompressed byte count mismatch")
        result["decompressed_bytes"] = decompressed_bytes
        result["lexical_aggregates"] = evidence
        conclusion = classify_lexical_evidence(evidence)
        if conclusion not in ALLOWED_RESEARCH_CONCLUSIONS:
            raise R6AContractError("classifier emitted undeclared research conclusion")
        result["research_conclusion"] = conclusion
        result["technical_result"] = conclusion
        result["terminal_status"] = "R6A_LEXICAL_CONFIRMATION_COMPLETE"
        result["runtime_seconds"] = round(time.monotonic() - started, 6)
        return 0, result
    except R6ALexicalUnresolved as exc:
        result["terminal_status"] = "R6A_LEXICAL_CONFIRMATION_COMPLETE"
        result["technical_result"] = "R6A_LEXICAL_SHAPE_UNRESOLVED"
        result["research_conclusion"] = "R6A_LEXICAL_SHAPE_UNRESOLVED"
        result["failure_class"] = type(exc).__name__
        result["runtime_seconds"] = round(time.monotonic() - started, 6)
        return 0, result
    except (R6AContractError, R6ATransportError, R6AJSONError) as exc:
        result["terminal_status"] = "R6A_TRANSPORT_OR_INTEGRITY_FAIL"
        result["technical_result"] = "R6A_TRANSPORT_OR_INTEGRITY_FAIL"
        result["research_conclusion"] = "R6A_TRANSPORT_OR_INTEGRITY_FAIL"
        result["failure_class"] = type(exc).__name__
        result["runtime_seconds"] = round(time.monotonic() - started, 6)
        return 1, result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    rc, result = execute()
    output = Path(args.output)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
