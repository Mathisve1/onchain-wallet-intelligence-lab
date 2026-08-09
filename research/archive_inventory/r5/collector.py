from __future__ import annotations

import argparse
import hashlib
import hmac
import http.client
import json
import os
import ssl
import sys
import time
import urllib.parse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[3]
R5_ROOT = ROOT / "research/archive_inventory/r5"
R4_ROOT = ROOT / "research/archive_inventory/r4"
if str(R4_ROOT) not in sys.path:
    sys.path.insert(0, str(R4_ROOT))
from lz4_frame import LZ4_FRAME_MAGIC, LZ4FrameError, LZ4FrameLimit, iter_lz4_frame

PREREGISTRATION = R5_ROOT / "LEGACY_FORMAT_FINGERPRINT_R5_CONTRACT.json"
IMPLEMENTATION = R5_ROOT / "R5_IMPLEMENTATION_CONTRACT.json"
APPROVAL_JSON = R5_ROOT / "approvals/APPROVE_HL_ARCHIVE_LEGACY_FORMAT_FINGERPRINT_R5_001.json"
APPROVAL_TEXT = R5_ROOT / "approvals/APPROVE_HL_ARCHIVE_LEGACY_FORMAT_FINGERPRINT_R5_001.txt"
ROLE_REUSE = R5_ROOT / "R5_AWS_ROLE_REUSE_ANALYSIS.json"

PILOT_ID = "HL-ARCHIVE-LEGACY-FORMAT-FINGERPRINT-R5-001"
PREREGISTRATION_COMMIT = "58f724d7f0208a43f7462abd80e1e69d995acff9"
APPROVAL_MERGE_COMMIT = "c22e28074ba2e95e1fe88912c364124e01eb0ff7"
APPROVAL_ID = "APPROVE_HL_ARCHIVE_LEGACY_FORMAT_FINGERPRINT_R5_001"
APPROVAL_TEXT_SHA256 = "667f94a66ea07296162ae0627a9cf7fc5b439b3f8312c8617ece923159f5ddc8"
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
MAX_REQUESTS = 1
MAX_TOTAL_COMPRESSED_BYTES = 12_726_384
MAX_TOTAL_DECOMPRESSED_BYTES = 134_217_728
MAX_RUNTIME_SECONDS = 120
MAX_RECORD_BYTES = 16_777_216
MAX_RECORDS = 5_000_000
MAX_SCHEMA_DEPTH = 16
MAX_UNIQUE_FIELD_PATHS = 4096
MAX_UNIQUE_STRUCTURAL_SIGNATURES = 256
EMPTY_PAYLOAD_SHA256 = hashlib.sha256(b"").hexdigest()
CLASSIFIER_PRECEDENCE = [
    "UTF8_NDJSON_PAIR_STRING_OBJECT",
    "UTF8_NDJSON_PAIR_OBJECT_STRING",
    "UTF8_NDJSON_ARRAY_OTHER",
    "UTF8_NDJSON_OBJECT_STREAM",
    "UTF8_NDJSON_MIXED_JSON_ROOTS",
    "UTF8_SINGLE_JSON_ARRAY_DOCUMENT",
    "UTF8_SINGLE_JSON_OBJECT_DOCUMENT",
    "UTF8_CONCATENATED_JSON_VALUES",
    "UTF8_NONJSON_OR_UNRESOLVED",
    "NON_UTF8_OR_UNRESOLVED",
]


class R5ContractError(RuntimeError):
    pass


class R5TransportError(RuntimeError):
    pass


class R5FormatLimit(RuntimeError):
    def __init__(self, status: str):
        super().__init__(status)
        self.status = status


class R5JSONError(ValueError):
    pass


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise R5ContractError(f"JSON root must be object: {path}")
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
        raise R5ContractError("approval text hash drift")
    if prereg.get("pilot_id") != PILOT_ID or prereg.get("status") != "PREREGISTERED_STATIC_NO_EXECUTION":
        raise R5ContractError("preregistration identity/status drift")
    if approval.get("approval_id") != APPROVAL_ID or approval.get("reviewed_commit") != PREREGISTRATION_COMMIT:
        raise R5ContractError("approval identity drift")
    if approval.get("exact_approval_text_sha256") != APPROVAL_TEXT_SHA256:
        raise R5ContractError("approval hash drift")
    if impl.get("pilot_id") != PILOT_ID or impl.get("status") != "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION":
        raise R5ContractError("implementation identity/status drift")
    if impl.get("preregistration_commit") != PREREGISTRATION_COMMIT:
        raise R5ContractError("implementation preregistration drift")
    if impl.get("approval_merge_commit") != APPROVAL_MERGE_COMMIT or impl.get("approval_text_sha256") != APPROVAL_TEXT_SHA256:
        raise R5ContractError("implementation approval binding drift")

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
        raise R5ContractError("preregistration target drift")
    if impl.get("object") != {k: v for k, v in expected_target.items() if k not in {"bucket", "signing_region", "regional_virtual_hosted_endpoint"}}:
        raise R5ContractError("implementation object drift")

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
            raise R5ContractError(f"execution envelope drift: {name}")

    classifier = prereg.get("proposed_format_classifier", {})
    for name, expected in {
        "maximum_record_bytes": MAX_RECORD_BYTES,
        "maximum_records_parsed": MAX_RECORDS,
        "maximum_schema_nesting_depth": MAX_SCHEMA_DEPTH,
        "maximum_unique_field_paths": MAX_UNIQUE_FIELD_PATHS,
        "maximum_unique_structural_signatures": MAX_UNIQUE_STRUCTURAL_SIGNATURES,
    }.items():
        if approval.get(name) != expected or impl.get(name) != expected or classifier.get(name) != expected:
            raise R5ContractError(f"classifier cap drift: {name}")
    if classifier.get("classifier_precedence") != CLASSIFIER_PRECEDENCE or impl.get("classifier_precedence") != CLASSIFIER_PRECEDENCE:
        raise R5ContractError("classifier precedence drift")

    if approval.get("target_bucket") != TARGET_BUCKET or approval.get("signing_region") != SIGNING_REGION:
        raise R5ContractError("approval target drift")
    if approval.get("object_key") != OBJECT_KEY or approval.get("object_size_bytes") != EXPECTED_SIZE_BYTES:
        raise R5ContractError("approval object drift")
    if approval.get("object_etag") != EXPECTED_ETAG:
        raise R5ContractError("approval etag drift")
    if approval.get("expected_compressed_sha256") != EXPECTED_COMPRESSED_SHA256:
        raise R5ContractError("approval compressed hash drift")
    if approval.get("expected_decompressed_byte_count") != EXPECTED_DECOMPRESSED_BYTES:
        raise R5ContractError("approval decompressed byte count drift")

    if approval.get("requester_pays_authorized_for_later_release") is not True:
        raise R5ContractError("approval requester-pays scope closed")
    if approval.get("get_object_authorized_for_later_release") is not True:
        raise R5ContractError("approval GetObject scope closed")
    if approval.get("decompression_authorized_for_later_release") is not True:
        raise R5ContractError("approval decompression scope closed")
    if approval.get("format_classification_authorized_for_later_release") is not True:
        raise R5ContractError("approval classification scope closed")
    if not all(v is False for v in approval.get("current_runtime_authority", {}).values()):
        raise R5ContractError("approval snapshot self-opens runtime")
    if not all(v is False for v in approval.get("retention_authorizations", {}).values()):
        raise R5ContractError("approval retention authority opened")
    if not all(v is False for v in approval.get("inference_authorizations", {}).values()):
        raise R5ContractError("approval inference authority opened")
    if not all(v is False for v in approval.get("trading_authorizations", {}).values()):
        raise R5ContractError("approval trading authority opened")

    for name in (
        "execution_authorized", "paid_request_authorized", "requester_pays_authorized",
        "get_object_authorized", "object_body_download_authorized", "decompression_authorized",
        "format_classification_authorized",
    ):
        if impl.get(name) is not False:
            raise R5ContractError(f"implementation current authority opened: {name}")
    if impl.get("execution_release_present") is not False:
        raise R5ContractError("implementation snapshot contains a release")
    if impl.get("expected_canonical_implementation_commit") != "PENDING_CANONICAL_IMPLEMENTATION_MERGE":
        raise R5ContractError("implementation must remain pending")
    if impl.get("s3_requests_executed") != 0 or impl.get("compressed_bytes_downloaded") != 0 or impl.get("decompressed_bytes_processed") != 0:
        raise R5ContractError("implementation snapshot contains execution")
    if impl.get("empirical_result") is not None:
        raise R5ContractError("implementation snapshot contains empirical result")
    if not all(v is False for v in impl.get("trading_authorizations", {}).values()):
        raise R5ContractError("implementation trading authority opened")

    if impl.get("reused_dedicated_role_arn") != ROLE_ARN:
        raise R5ContractError("role reuse ARN drift")
    if impl.get("aws_role_mutation_required") is not False or impl.get("aws_role_mutation_authorized") is not False:
        raise R5ContractError("role mutation boundary drift")
    if impl.get("session_s3_policy") != "ALLOW_GETOBJECT_EXACT_LEGACY_OBJECT_ONLY":
        raise R5ContractError("session policy drift")
    if impl.get("session_policy_strict_subset_of_persistent_role") is not True:
        raise R5ContractError("session subset proof drift")
    if role_reuse.get("reused_role_arn") != ROLE_ARN or role_reuse.get("aws_iam_mutation_performed") is not False:
        raise R5ContractError("role reuse evidence drift")
    if role_reuse.get("r5_session_scope", {}).get("allowed_object_arns") != [
        f"arn:aws:s3:::{TARGET_BUCKET}/{OBJECT_KEY}"
    ]:
        raise R5ContractError("role reuse session scope drift")

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
        raise R5ContractError("temporary AWS credentials missing")
    if request_time.tzinfo is None:
        raise R5ContractError("signing time must be timezone-aware")

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
        "AWS4-HMAC-SHA256", amz_date, scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])
    k_date = _sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _sign(k_date, SIGNING_REGION)
    k_service = _sign(k_region, SERVICE)
    k_signing = _sign(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
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
            raise R5JSONError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_nonfinite(_token: str) -> object:
    raise R5JSONError("non-finite JSON constant")


STRICT_DECODER = json.JSONDecoder(object_pairs_hook=_strict_object, parse_constant=_reject_nonfinite)


def _json_type(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    raise R5JSONError("unsupported JSON type")


def _escape_pointer_key(key: str) -> str:
    return key.replace("~", "~0").replace("/", "~1")


def _structural_signature(value: object, depth: int = 1) -> str:
    if depth > MAX_SCHEMA_DEPTH:
        raise R5FormatLimit("FORMAT_CENSORED_BY_SCHEMA_DEPTH_LIMIT")
    kind = _json_type(value)
    if kind == "object":
        items = []
        assert isinstance(value, dict)
        for key in sorted(value):
            items.append(f"{_escape_pointer_key(key)}:{_structural_signature(value[key], depth + 1)}")
        return "O{" + ",".join(items) + "}"
    if kind == "array":
        assert isinstance(value, list)
        member_types = ",".join(_json_type(item) for item in value)
        return f"A[{member_types}]"
    return kind


class StructuralAggregator:
    def __init__(self) -> None:
        self.nonempty_record_count = 0
        self.json_root_type_counts: Counter[str] = Counter()
        self.array_arity_histogram: Counter[str] = Counter()
        self.array_element_type_signature_counts: Counter[str] = Counter()
        self.object_field_path_type_sets: dict[str, set[str]] = {}
        self.object_field_path_presence_counts: Counter[str] = Counter()
        self.maximum_observed_nesting_depth = 0
        self.structural_signature_hash_counts: Counter[str] = Counter()

    def add(self, value: object) -> None:
        self.nonempty_record_count += 1
        if self.nonempty_record_count > MAX_RECORDS:
            raise R5FormatLimit("FORMAT_CENSORED_BY_RECORD_COUNT_LIMIT")
        root_type = _json_type(value)
        self.json_root_type_counts[root_type] += 1
        if isinstance(value, list):
            self.array_arity_histogram[str(len(value))] += 1
            signature = ",".join(_json_type(item) for item in value)
            self.array_element_type_signature_counts[signature] += 1

        signature = _structural_signature(value)
        digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()
        if digest not in self.structural_signature_hash_counts and len(self.structural_signature_hash_counts) >= MAX_UNIQUE_STRUCTURAL_SIGNATURES:
            raise R5FormatLimit("FORMAT_CENSORED_BY_STRUCTURAL_SIGNATURE_LIMIT")
        self.structural_signature_hash_counts[digest] += 1
        self._visit(value, "", 1)

    def _visit(self, value: object, path: str, depth: int) -> None:
        if depth > MAX_SCHEMA_DEPTH:
            raise R5FormatLimit("FORMAT_CENSORED_BY_SCHEMA_DEPTH_LIMIT")
        self.maximum_observed_nesting_depth = max(self.maximum_observed_nesting_depth, depth)
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}/{_escape_pointer_key(key)}"
                self._record_path(child_path, child)
                self._visit(child, child_path, depth + 1)
        elif isinstance(value, list):
            for child in value:
                child_path = f"{path}/*"
                self._record_path(child_path, child)
                self._visit(child, child_path, depth + 1)

    def _record_path(self, path: str, value: object) -> None:
        if path not in self.object_field_path_type_sets and len(self.object_field_path_type_sets) >= MAX_UNIQUE_FIELD_PATHS:
            raise R5FormatLimit("FORMAT_CENSORED_BY_FIELD_PATH_LIMIT")
        self.object_field_path_type_sets.setdefault(path, set()).add(_json_type(value))
        self.object_field_path_presence_counts[path] += 1

    def evidence(self) -> dict:
        return {
            "nonempty_record_count": self.nonempty_record_count,
            "json_root_type_counts": dict(sorted(self.json_root_type_counts.items())),
            "array_arity_histogram": dict(sorted(self.array_arity_histogram.items(), key=lambda kv: int(kv[0]))),
            "array_element_type_signature_counts": dict(sorted(self.array_element_type_signature_counts.items())),
            "object_field_path_names": sorted(self.object_field_path_type_sets),
            "object_field_path_type_sets": {
                key: sorted(values) for key, values in sorted(self.object_field_path_type_sets.items())
            },
            "object_field_path_presence_counts": dict(sorted(self.object_field_path_presence_counts.items())),
            "maximum_observed_nesting_depth": self.maximum_observed_nesting_depth,
            "structural_signature_hash_counts": dict(sorted(self.structural_signature_hash_counts.items())),
        }


def _iter_lines(raw: bytes):
    start = 0
    length = len(raw)
    while start <= length:
        end = raw.find(b"\n", start)
        if end < 0:
            end = length
        line = raw[start:end]
        if line.endswith(b"\r"):
            line = line[:-1]
        yield line
        if end == length:
            break
        start = end + 1


def _strict_loads(text: str) -> object:
    try:
        return json.loads(text, object_pairs_hook=_strict_object, parse_constant=_reject_nonfinite)
    except (json.JSONDecodeError, R5JSONError) as exc:
        raise R5JSONError("strict JSON parse failed") from exc


def _try_ndjson(raw: bytes) -> tuple[str, StructuralAggregator] | None:
    aggregate = StructuralAggregator()
    root_types: set[str] = set()
    all_pair_string_object = True
    all_pair_object_string = True
    seen = 0
    for line in _iter_lines(raw):
        if not line.strip():
            continue
        if len(line) > MAX_RECORD_BYTES:
            raise R5FormatLimit("FORMAT_CENSORED_BY_RECORD_BYTE_LIMIT")
        try:
            text = line.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise R5JSONError("non-UTF8 payload") from exc
        try:
            value = _strict_loads(text)
        except R5JSONError:
            return None
        seen += 1
        root_types.add(_json_type(value))
        all_pair_string_object = all_pair_string_object and (
            isinstance(value, list)
            and len(value) == 2
            and _json_type(value[0]) == "string"
            and _json_type(value[1]) == "object"
        )
        all_pair_object_string = all_pair_object_string and (
            isinstance(value, list)
            and len(value) == 2
            and _json_type(value[0]) == "object"
            and _json_type(value[1]) == "string"
        )
        aggregate.add(value)
        del value
    if seen == 0:
        return None
    if root_types == {"array"}:
        if all_pair_string_object:
            return "UTF8_NDJSON_PAIR_STRING_OBJECT", aggregate
        if all_pair_object_string:
            return "UTF8_NDJSON_PAIR_OBJECT_STRING", aggregate
        return "UTF8_NDJSON_ARRAY_OTHER", aggregate
    if root_types == {"object"}:
        return "UTF8_NDJSON_OBJECT_STREAM", aggregate
    return "UTF8_NDJSON_MIXED_JSON_ROOTS", aggregate


def _skip_ws(text: str, position: int) -> int:
    while position < len(text) and text[position] in " \t\r\n":
        position += 1
    return position


def _try_whole_document(raw: bytes) -> tuple[str, StructuralAggregator]:
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return "NON_UTF8_OR_UNRESOLVED", StructuralAggregator()
    position = _skip_ws(text, 0)
    if position == len(text):
        return "UTF8_NONJSON_OR_UNRESOLVED", StructuralAggregator()

    aggregate = StructuralAggregator()
    value_count = 0
    first_root_type: str | None = None
    while position < len(text):
        try:
            value, end = STRICT_DECODER.raw_decode(text, position)
        except (json.JSONDecodeError, R5JSONError):
            return "UTF8_NONJSON_OR_UNRESOLVED", StructuralAggregator()
        if len(text[position:end].encode("utf-8")) > MAX_RECORD_BYTES:
            raise R5FormatLimit("FORMAT_CENSORED_BY_RECORD_BYTE_LIMIT")
        value_count += 1
        if first_root_type is None:
            first_root_type = _json_type(value)
        aggregate.add(value)
        del value
        position = _skip_ws(text, end)
        if position == len(text):
            break

    if value_count == 1:
        if first_root_type == "array":
            return "UTF8_SINGLE_JSON_ARRAY_DOCUMENT", aggregate
        if first_root_type == "object":
            return "UTF8_SINGLE_JSON_OBJECT_DOCUMENT", aggregate
        return "UTF8_NONJSON_OR_UNRESOLVED", aggregate
    if value_count >= 2:
        return "UTF8_CONCATENATED_JSON_VALUES", aggregate
    return "UTF8_NONJSON_OR_UNRESOLVED", aggregate


def classify_decompressed_payload(raw: bytes) -> dict:
    try:
        raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        classification = "NON_UTF8_OR_UNRESOLVED"
        aggregate = StructuralAggregator()
    else:
        ndjson = _try_ndjson(raw)
        if ndjson is not None:
            classification, aggregate = ndjson
        else:
            classification, aggregate = _try_whole_document(raw)

    if classification not in CLASSIFIER_PRECEDENCE:
        raise R5ContractError("classifier emitted undeclared class")
    evidence = aggregate.evidence()
    evidence["resolved_format_class"] = classification
    if classification == "UTF8_NDJSON_PAIR_STRING_OBJECT":
        conclusion = "LEGACY_FORMAT_RESOLVED_AS_NDJSON_PAIR_STRING_OBJECT"
    elif classification == "UTF8_NDJSON_PAIR_OBJECT_STRING":
        conclusion = "LEGACY_FORMAT_RESOLVED_AS_NDJSON_PAIR_OBJECT_STRING"
    elif classification in {
        "UTF8_NDJSON_ARRAY_OTHER", "UTF8_NDJSON_OBJECT_STREAM", "UTF8_NDJSON_MIXED_JSON_ROOTS",
        "UTF8_SINGLE_JSON_ARRAY_DOCUMENT", "UTF8_SINGLE_JSON_OBJECT_DOCUMENT",
        "UTF8_CONCATENATED_JSON_VALUES",
    }:
        conclusion = "LEGACY_FORMAT_RESOLVED_AS_OTHER_DECLARED_JSON_CLASS"
    else:
        conclusion = "LEGACY_FORMAT_UNRESOLVED"
    return {
        "format_class": classification,
        "research_conclusion": conclusion,
        "structural_evidence": evidence,
        "payload_values_retained": False,
        "string_values_retained": False,
        "numeric_values_retained": False,
        "wallet_addresses_retained": False,
        "record_payload_retained": False,
    }


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
        "compressed_bytes": 0,
        "decompressed_bytes": 0,
        "compressed_sha256": None,
        "format_class": None,
        "research_conclusion": None,
        "structural_evidence": None,
        "raw_compressed_object_persisted": False,
        "raw_decompressed_payload_retained": False,
        "record_payload_retained": False,
        "wallet_addresses_retained_from_body": False,
        "payload_values_retained": False,
        "string_values_retained": False,
        "numeric_values_retained": False,
        "semantic_wallet_or_user_label_inferred": False,
        "schema_equivalence_inferred": False,
        "semantic_equivalence_inferred": False,
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
            raise R5TransportError("runtime limit reached before request")
        host, path, headers = build_signed_request(request_time(), env)
        attempts += 1
        result["request_attempt_count"] = attempts
        result["s3_http_request_count"] = attempts
        if attempts > MAX_REQUESTS:
            raise R5TransportError("request cap exceeded")
        remaining = max(1.0, MAX_RUNTIME_SECONDS - (time.monotonic() - started))
        status, response_headers, body = transport(host, path, headers, EXPECTED_SIZE_BYTES, remaining)
        if status != 200:
            result["failed_request_count"] = 1
            raise R5TransportError("non-200 S3 response")
        result["successful_request_count"] = 1

        content_length_text = response_headers.get("content-length")
        try:
            observed_content_length = int(content_length_text) if content_length_text is not None else None
        except ValueError as exc:
            raise R5TransportError("invalid Content-Length") from exc
        if observed_content_length != EXPECTED_SIZE_BYTES or len(body) != EXPECTED_SIZE_BYTES:
            raise R5TransportError("Content-Length or body-size mismatch")
        if response_headers.get("etag") != EXPECTED_ETAG:
            raise R5TransportError("ETag mismatch")
        if response_headers.get("x-amz-request-charged") != "requester":
            raise R5TransportError("Requester Pays charge acknowledgement missing")
        if len(body) > MAX_TOTAL_COMPRESSED_BYTES:
            raise R5TransportError("compressed byte cap exceeded")
        compressed_sha = sha256_bytes(body)
        if compressed_sha != EXPECTED_COMPRESSED_SHA256:
            raise R5TransportError("compressed object SHA-256 mismatch")
        result["compressed_bytes"] = len(body)
        result["compressed_sha256"] = compressed_sha
        if not body.startswith(LZ4_FRAME_MAGIC):
            raise R5TransportError("unrecognized LZ4 frame")

        decompressed = bytearray()
        try:
            for chunk in iter_lz4_frame(body, MAX_TOTAL_DECOMPRESSED_BYTES):
                decompressed.extend(chunk)
        except (LZ4FrameError, LZ4FrameLimit) as exc:
            raise R5TransportError("LZ4 decompression failed") from exc
        if len(decompressed) != EXPECTED_DECOMPRESSED_BYTES:
            raise R5TransportError("decompressed byte count mismatch")
        result["decompressed_bytes"] = len(decompressed)
        classification = classify_decompressed_payload(bytes(decompressed))
        decompressed.clear()

        result["format_class"] = classification["format_class"]
        result["research_conclusion"] = classification["research_conclusion"]
        result["structural_evidence"] = classification["structural_evidence"]
        result["technical_result"] = classification["research_conclusion"]
        result["terminal_status"] = "R5_LEGACY_FORMAT_FINGERPRINT_COMPLETE"
        result["runtime_seconds"] = round(time.monotonic() - started, 6)
        return 0, result
    except R5FormatLimit as exc:
        result["terminal_status"] = "R5_LEGACY_FORMAT_FINGERPRINT_COMPLETE"
        result["technical_result"] = "LEGACY_FORMAT_UNRESOLVED"
        result["research_conclusion"] = "LEGACY_FORMAT_UNRESOLVED"
        result["format_class"] = "UTF8_NONJSON_OR_UNRESOLVED"
        result["failure_class"] = exc.status
        result["runtime_seconds"] = round(time.monotonic() - started, 6)
        return 0, result
    except (R5ContractError, R5TransportError, R5JSONError) as exc:
        result["terminal_status"] = "R5_TRANSPORT_OR_INTEGRITY_FAIL"
        result["technical_result"] = "R5_TRANSPORT_OR_INTEGRITY_FAIL"
        result["research_conclusion"] = None
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
