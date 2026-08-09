from __future__ import annotations

import hashlib
import hmac
import http.client
import json
import os
import ssl
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from lz4_frame import LZ4_FRAME_MAGIC, LZ4FrameError, LZ4FrameLimit, iter_lz4_frame

ROOT = Path(__file__).resolve().parents[3]
R4_ROOT = ROOT / "research/archive_inventory/r4"
PREREGISTRATION = R4_ROOT / "HOURLY_BODY_SCHEMA_PILOT_R4_CONTRACT.json"
IMPLEMENTATION = R4_ROOT / "R4_IMPLEMENTATION_CONTRACT.json"
APPROVAL_JSON = R4_ROOT / "approvals/APPROVE_HL_ARCHIVE_HOURLY_BODY_SCHEMA_PILOT_R4_001.json"
APPROVAL_TEXT = R4_ROOT / "approvals/APPROVE_HL_ARCHIVE_HOURLY_BODY_SCHEMA_PILOT_R4_001.txt"
PARENT_IAM_POLICY = ROOT / "research/archive_inventory/IAM_POLICY_TEMPLATE.json"

PILOT_ID = "HL-ARCHIVE-HOURLY-BODY-SCHEMA-PILOT-R4-001"
PREREGISTRATION_COMMIT = "25a1f621d15cb708a485893025f03b991628aae1"
APPROVAL_MERGE_COMMIT = "0191350683c6c943d3538c8c51db176cd1d58211"
APPROVAL_ID = "APPROVE_HL_ARCHIVE_HOURLY_BODY_SCHEMA_PILOT_R4_001"
APPROVAL_TEXT_SHA256 = "e52399feb7a0d36959089f556dd9f55062eb91d52feaa4c5af680d3c4e557264"
TARGET_BUCKET = "hl-mainnet-node-data"
SIGNING_REGION = "ap-northeast-1"
REGIONAL_ENDPOINT = f"{TARGET_BUCKET}.s3.{SIGNING_REGION}.amazonaws.com"
SERVICE = "s3"
MAX_REQUESTS = 2
MAX_TOTAL_COMPRESSED_BYTES = 14_243_987
MAX_TOTAL_DECOMPRESSED_BYTES = 536_870_912
MAX_DECOMPRESSED_BYTES_PER_OBJECT = 268_435_456
MAX_RUNTIME_SECONDS = 180
MAX_RECORD_BYTES = 16_777_216
MAX_RECORDS_PER_OBJECT = 5_000_000
MAX_SCHEMA_DEPTH = 16
MAX_UNIQUE_FIELD_PATHS = 4096
EMPTY_PAYLOAD_SHA256 = hashlib.sha256(b"").hexdigest()
EXPECTED_OBJECTS = (
    {
        "role": "LEGACY_BOUNDARY_OBJECT",
        "dataset_family_id": "node_fills",
        "key": "node_fills/hourly/20250727/8.lz4",
        "expected_size_bytes": 12_726_384,
        "expected_etag": '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"',
    },
    {
        "role": "MODERN_BOUNDARY_OBJECT",
        "dataset_family_id": "node_fills_by_block",
        "key": "node_fills_by_block/hourly/20250727/8.lz4",
        "expected_size_bytes": 1_517_603,
        "expected_etag": '"60d4c1277f76651b5f04666bbe8d7594"',
    },
)


class R4ContractError(RuntimeError):
    pass


class SchemaFormatError(RuntimeError):
    pass


class SchemaCensored(RuntimeError):
    def __init__(self, status: str):
        super().__init__(status)
        self.status = status


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise R4ContractError(f"JSON root must be object: {path}")
    return value


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def signing_now() -> datetime:
    return datetime.now(timezone.utc)


def _approval_objects(rows: object) -> list[dict]:
    if not isinstance(rows, list):
        raise R4ContractError("approval selected object list missing")
    result: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            raise R4ContractError("approval selected object row invalid")
        result.append({
            "key": row.get("key"),
            "expected_size_bytes": row.get("size_bytes"),
            "expected_etag": row.get("etag"),
        })
    return result


def _prereg_objects(rows: object) -> list[dict]:
    if not isinstance(rows, list):
        raise R4ContractError("preregistration selected object list missing")
    result: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            raise R4ContractError("preregistration selected object row invalid")
        result.append({
            "role": row.get("role"),
            "dataset_family_id": row.get("dataset_family_id"),
            "key": row.get("key"),
            "expected_size_bytes": row.get("r3_observed_size_bytes"),
            "expected_etag": row.get("r3_observed_etag"),
        })
    return result


def validate_static_inputs() -> list[dict]:
    prereg = load_json(PREREGISTRATION)
    approval = load_json(APPROVAL_JSON)
    impl = load_json(IMPLEMENTATION)
    parent_iam = load_json(PARENT_IAM_POLICY)

    if sha256_bytes(APPROVAL_TEXT.read_bytes()) != APPROVAL_TEXT_SHA256:
        raise R4ContractError("approval text hash drift")
    if prereg.get("pilot_id") != PILOT_ID:
        raise R4ContractError("preregistration identity drift")
    if approval.get("approval_id") != APPROVAL_ID or approval.get("reviewed_commit") != PREREGISTRATION_COMMIT:
        raise R4ContractError("approval identity drift")
    if approval.get("exact_approval_text_sha256") != APPROVAL_TEXT_SHA256:
        raise R4ContractError("approval hash drift")
    if impl.get("pilot_id") != PILOT_ID or impl.get("status") != "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION":
        raise R4ContractError("implementation identity/status drift")
    if impl.get("preregistration_commit") != PREREGISTRATION_COMMIT:
        raise R4ContractError("implementation preregistration drift")
    if impl.get("approval_merge_commit") != APPROVAL_MERGE_COMMIT or impl.get("approval_text_sha256") != APPROVAL_TEXT_SHA256:
        raise R4ContractError("implementation approval binding drift")

    expected = [dict(row) for row in EXPECTED_OBJECTS]
    if _prereg_objects(prereg.get("selected_objects")) != expected:
        raise R4ContractError("preregistration object scope drift")
    if _approval_objects(approval.get("selected_objects")) != [
        {"key": row["key"], "expected_size_bytes": row["expected_size_bytes"], "expected_etag": row["expected_etag"]}
        for row in expected
    ]:
        raise R4ContractError("approval object scope drift")
    if impl.get("selected_objects") != expected:
        raise R4ContractError("implementation object scope drift")

    common = {
        "maximum_get_object_requests": MAX_REQUESTS,
        "maximum_requests_per_object": 1,
        "maximum_total_compressed_bytes": MAX_TOTAL_COMPRESSED_BYTES,
        "maximum_total_decompressed_bytes": MAX_TOTAL_DECOMPRESSED_BYTES,
        "maximum_decompressed_bytes_per_object": MAX_DECOMPRESSED_BYTES_PER_OBJECT,
        "maximum_runtime_seconds": MAX_RUNTIME_SECONDS,
        "maximum_retries_per_request": 0,
        "maximum_record_bytes": MAX_RECORD_BYTES,
        "maximum_records_parsed_per_object": MAX_RECORDS_PER_OBJECT,
        "maximum_schema_nesting_depth": MAX_SCHEMA_DEPTH,
        "maximum_unique_field_paths": MAX_UNIQUE_FIELD_PATHS,
    }
    for name, expected_value in common.items():
        if approval.get(name) != expected_value:
            raise R4ContractError(f"approval cap drift: {name}")
        if impl.get(name) != expected_value:
            raise R4ContractError(f"implementation cap drift: {name}")

    if approval.get("target_bucket") != TARGET_BUCKET or approval.get("signing_region") != SIGNING_REGION:
        raise R4ContractError("approval target drift")
    if impl.get("target_bucket") != TARGET_BUCKET or impl.get("signing_region") != SIGNING_REGION:
        raise R4ContractError("implementation target drift")
    if impl.get("regional_virtual_hosted_endpoint") != REGIONAL_ENDPOINT:
        raise R4ContractError("implementation endpoint drift")
    if not approval.get("requester_pays_scope_approved") or not approval.get("get_object_scope_approved") or not approval.get("decompression_scope_approved"):
        raise R4ContractError("approved implementation scope is not open")
    if not all(value is True for value in approval.get("forbidden_capabilities", {}).values()):
        raise R4ContractError("approval forbidden capability drift")
    if not all(value is False for value in approval.get("trading_authorizations", {}).values()):
        raise R4ContractError("approval trading authorization opened")

    for name in (
        "execution_authorized", "paid_request_authorized", "requester_pays_authorized",
        "get_object_authorized", "object_body_download_authorized", "decompression_authorized",
    ):
        if impl.get(name) is not False:
            raise R4ContractError(f"implementation current authority opened: {name}")
    if impl.get("execution_release_present") is not False:
        raise R4ContractError("implementation snapshot contains a release")
    if impl.get("expected_canonical_implementation_commit") != "PENDING_CANONICAL_IMPLEMENTATION_MERGE":
        raise R4ContractError("implementation snapshot must remain pending")
    if not all(value is False for value in impl.get("trading_authorizations", {}).values()):
        raise R4ContractError("implementation trading authorization opened")
    if impl.get("s3_requests_executed") != 0 or impl.get("compressed_bytes_downloaded") != 0 or impl.get("decompressed_bytes_processed") != 0:
        raise R4ContractError("implementation snapshot contains execution")
    if impl.get("empirical_result") is not None:
        raise R4ContractError("implementation snapshot contains empirical result")

    explicit_get_deny = False
    for statement in parent_iam.get("Statement", []):
        actions = statement.get("Action", [])
        actions = actions if isinstance(actions, list) else [actions]
        if statement.get("Effect") == "Deny" and "s3:GetObject" in actions:
            explicit_get_deny = True
    if not explicit_get_deny:
        raise R4ContractError("parent metadata IAM no longer proves the R4 dedicated-role requirement")
    if impl.get("current_metadata_role_usable_for_r4") is not False or impl.get("dedicated_r4_role_required") is not True:
        raise R4ContractError("dedicated-role boundary drift")

    return expected


def _aws_quote_path(key: str) -> str:
    return "/" + urllib.parse.quote(key, safe="/-_.~")


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def build_signed_request(object_spec: dict, request_time: datetime, env: dict[str, str] | None = None) -> tuple[str, str, dict[str, str]]:
    if object_spec not in EXPECTED_OBJECTS:
        raise R4ContractError("unregistered object")
    source = os.environ if env is None else env
    access_key = source.get("AWS_ACCESS_KEY_ID")
    secret_key = source.get("AWS_SECRET_ACCESS_KEY")
    session_token = source.get("AWS_SESSION_TOKEN")
    if not access_key or not secret_key or not session_token:
        raise R4ContractError("temporary AWS credentials missing")
    if request_time.tzinfo is None:
        raise R4ContractError("signing time must be timezone-aware")

    stamp = request_time.astimezone(timezone.utc)
    amz_date = stamp.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = stamp.strftime("%Y%m%d")
    canonical_uri = _aws_quote_path(object_spec["key"])
    canonical_headers = (
        f"host:{REGIONAL_ENDPOINT}\n"
        f"if-match:{object_spec['expected_etag']}\n"
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
        "If-Match": object_spec["expected_etag"],
        "Authorization": authorization,
        "x-amz-content-sha256": EMPTY_PAYLOAD_SHA256,
        "x-amz-date": amz_date,
        "x-amz-request-payer": "requester",
        "x-amz-security-token": session_token,
    }


def https_transport(host: str, path: str, headers: dict[str, str], expected_size: int, timeout_seconds: float) -> tuple[int, dict[str, str], bytes]:
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
            raise SchemaFormatError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_nonfinite(token: str) -> object:
    raise SchemaFormatError(f"non-finite JSON constant: {token}")


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
    raise SchemaFormatError("unsupported JSON value type")


def _escape_pointer_key(key: str) -> str:
    return key.replace("~", "~0").replace("/", "~1")


class SchemaAggregator:
    def __init__(self) -> None:
        self.buffer = bytearray()
        self.record_count = 0
        self.field_types: dict[str, set[str]] = {}
        self.field_presence: dict[str, int] = {}
        self.maximum_observed_nesting_depth = 0
        self.censored_status: str | None = None
        self.format_status: str | None = None

    def _visit(self, value: object, path: str, depth: int, seen: set[str]) -> None:
        if depth > MAX_SCHEMA_DEPTH:
            raise SchemaCensored("SCHEMA_CENSORED_BY_NESTING_DEPTH")
        self.maximum_observed_nesting_depth = max(self.maximum_observed_nesting_depth, depth)
        if path:
            if path not in self.field_types and len(self.field_types) >= MAX_UNIQUE_FIELD_PATHS:
                raise SchemaCensored("SCHEMA_CENSORED_BY_FIELD_PATH_LIMIT")
            self.field_types.setdefault(path, set()).add(_json_type(value))
            seen.add(path)
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}/{_escape_pointer_key(key)}" if path else f"/{_escape_pointer_key(key)}"
                self._visit(child, child_path, depth + 1, seen)
        elif isinstance(value, list):
            for child in value:
                child_path = f"{path}/*" if path else "/*"
                self._visit(child, child_path, depth + 1, seen)

    def _process_record(self, line: bytes) -> None:
        if self.censored_status is not None or self.format_status is not None:
            return
        if len(line) > MAX_RECORD_BYTES:
            self.censored_status = "SCHEMA_CENSORED_BY_RECORD_SIZE_LIMIT"
            return
        if not line:
            self.format_status = "BODY_READABLE_SCHEMA_UNRESOLVED"
            return
        if self.record_count >= MAX_RECORDS_PER_OBJECT:
            self.censored_status = "SCHEMA_CENSORED_BY_RECORD_LIMIT"
            return
        try:
            decoded = line.decode("utf-8", errors="strict")
            value = json.loads(decoded, object_pairs_hook=_strict_object, parse_constant=_reject_nonfinite)
            if not isinstance(value, dict):
                raise SchemaFormatError("NDJSON top-level value is not an object")
            seen: set[str] = set()
            self._visit(value, "", 0, seen)
        except (UnicodeDecodeError, json.JSONDecodeError, SchemaFormatError):
            self.format_status = "BODY_READABLE_SCHEMA_UNRESOLVED"
            return
        except SchemaCensored as exc:
            self.censored_status = exc.status
            return
        self.record_count += 1
        for path in seen:
            self.field_presence[path] = self.field_presence.get(path, 0) + 1

    def feed(self, data: bytes) -> None:
        if self.censored_status is not None or self.format_status is not None:
            return
        self.buffer.extend(data)
        while True:
            newline = self.buffer.find(b"\n")
            if newline < 0:
                if len(self.buffer) > MAX_RECORD_BYTES:
                    self.censored_status = "SCHEMA_CENSORED_BY_RECORD_SIZE_LIMIT"
                    self.buffer.clear()
                return
            line = bytes(self.buffer[:newline])
            del self.buffer[: newline + 1]
            if line.endswith(b"\r"):
                line = line[:-1]
            self._process_record(line)
            if self.censored_status is not None or self.format_status is not None:
                self.buffer.clear()
                return

    def finish(self) -> None:
        if self.censored_status is not None or self.format_status is not None:
            self.buffer.clear()
            return
        if self.buffer:
            line = bytes(self.buffer)
            self.buffer.clear()
            if line.endswith(b"\r"):
                line = line[:-1]
            self._process_record(line)

    def result(self) -> dict:
        field_names = sorted(self.field_types)
        return {
            "record_count": self.record_count,
            "top_level_json_type": "object" if self.record_count > 0 else None,
            "field_path_names": field_names,
            "field_path_type_sets": {path: sorted(self.field_types[path]) for path in field_names},
            "field_path_presence_counts": {path: self.field_presence.get(path, 0) for path in field_names},
            "maximum_observed_nesting_depth": self.maximum_observed_nesting_depth,
            "schema_status": self.censored_status or self.format_status or "FULL_SCHEMA_PARSED",
        }


def analyze_compressed_object(raw: bytes) -> dict:
    base = {
        "lz4_frame_recognized": raw.startswith(LZ4_FRAME_MAGIC),
        "decompression_status": None,
        "decompressed_byte_count": 0,
        "record_count": 0,
        "top_level_json_type": None,
        "field_path_names": [],
        "field_path_type_sets": {},
        "field_path_presence_counts": {},
        "maximum_observed_nesting_depth": 0,
        "schema_status": "SCHEMA_UNRESOLVED",
        "failure_class": None,
    }
    if not base["lz4_frame_recognized"]:
        base["decompression_status"] = "UNRECOGNIZED_LZ4_FRAME"
        base["failure_class"] = "LZ4_FRAME_UNRECOGNIZED"
        return base
    aggregator = SchemaAggregator()
    decompressed = 0
    try:
        for chunk in iter_lz4_frame(raw, MAX_DECOMPRESSED_BYTES_PER_OBJECT):
            decompressed += len(chunk)
            aggregator.feed(chunk)
        aggregator.finish()
    except LZ4FrameLimit as exc:
        base["decompression_status"] = exc.status
        base["decompressed_byte_count"] = decompressed
        base["schema_status"] = exc.status
        return base
    except LZ4FrameError:
        base["decompression_status"] = "LZ4_FRAME_VALIDATION_FAILED"
        base["decompressed_byte_count"] = decompressed
        base["failure_class"] = "LZ4_FRAME_VALIDATION_FAILED"
        return base
    schema = aggregator.result()
    base.update(schema)
    base["decompressed_byte_count"] = decompressed
    base["decompression_status"] = schema["schema_status"] if schema["schema_status"].startswith("SCHEMA_CENSORED") else "LZ4_FRAME_DECOMPRESSED"
    if schema["schema_status"] == "BODY_READABLE_SCHEMA_UNRESOLVED":
        base["failure_class"] = "UTF8_NDJSON_OBJECT_SCHEMA_UNRESOLVED"
    return base


def compare_schemas(legacy: dict, modern: dict) -> tuple[str, str]:
    statuses = [legacy["schema_status"], modern["schema_status"]]
    if any(status.startswith("SCHEMA_CENSORED") for status in statuses):
        return "SCHEMA_UNRESOLVED", "TWO_OBJECT_SCHEMA_CENSORED"
    if any(status != "FULL_SCHEMA_PARSED" for status in statuses):
        return "SCHEMA_UNRESOLVED", "TWO_OBJECT_BODY_FORMAT_UNRESOLVED"
    legacy_schema = {path: set(types) for path, types in legacy["field_path_type_sets"].items()}
    modern_schema = {path: set(types) for path, types in modern["field_path_type_sets"].items()}
    if legacy_schema == modern_schema:
        return "IDENTICAL_OBSERVED_SCHEMA", "TWO_OBJECT_SCHEMA_COMPARISON_RESOLVED"
    legacy_subset = all(path in modern_schema and types <= modern_schema[path] for path, types in legacy_schema.items())
    modern_subset = all(path in legacy_schema and types <= legacy_schema[path] for path, types in modern_schema.items())
    if legacy_subset:
        return "LEGACY_SCHEMA_SUBSET_OF_MODERN", "TWO_OBJECT_SCHEMA_COMPARISON_RESOLVED"
    if modern_subset:
        return "MODERN_SCHEMA_SUBSET_OF_LEGACY", "TWO_OBJECT_SCHEMA_COMPARISON_RESOLVED"
    if set(legacy_schema).intersection(modern_schema):
        return "OVERLAPPING_BUT_DIFFERENT_SCHEMA", "TWO_OBJECT_SCHEMA_COMPARISON_RESOLVED"
    return "DISJOINT_OR_INCOMPATIBLE_SCHEMA", "TWO_OBJECT_SCHEMA_COMPARISON_RESOLVED"


Transport = Callable[[str, str, dict[str, str], int, float], tuple[int, dict[str, str], bytes]]


def _http_failure_class(status: int) -> str:
    if status == 412:
        return "HTTP_412_ETAG_PRECONDITION_FAILED"
    if status in {401, 403}:
        return "HTTP_AUTHORIZATION_FAILURE"
    if 300 <= status < 400:
        return "HTTP_REDIRECT_REJECTED"
    return "HTTP_NON_200"


def execute_pilot(transport: Transport = https_transport, clock: Callable[[], float] = time.monotonic, now: Callable[[], datetime] = signing_now) -> dict:
    object_specs = validate_static_inputs()
    started = clock()
    attempts = 0
    http_requests = 0
    successful = 0
    failed = 0
    total_compressed = 0
    total_decompressed = 0
    observations: list[dict] = []

    for spec in object_specs:
        elapsed = clock() - started
        if elapsed >= MAX_RUNTIME_SECONDS or attempts >= MAX_REQUESTS or total_compressed + spec["expected_size_bytes"] > MAX_TOTAL_COMPRESSED_BYTES:
            failed += 1
            break
        host, path, headers = build_signed_request(spec, now())
        attempts += 1
        timeout = max(1.0, min(30.0, MAX_RUNTIME_SECONDS - elapsed))
        try:
            status, response_headers, body = transport(host, path, headers, spec["expected_size_bytes"], timeout)
            http_requests += 1
        except Exception:
            failed += 1
            observations.append({
                "role": spec["role"], "dataset_family_id": spec["dataset_family_id"], "key": spec["key"],
                "request_index": attempts, "status": "TRANSPORT_FAILURE", "failure_class": "TRANSPORT_FAILURE",
            })
            break
        normalized = {str(name).lower(): str(value).strip() for name, value in response_headers.items()}
        if status != 200:
            failed += 1
            observations.append({
                "role": spec["role"], "dataset_family_id": spec["dataset_family_id"], "key": spec["key"],
                "request_index": attempts, "http_status": status, "status": "REQUEST_FAILED",
                "failure_class": _http_failure_class(status),
            })
            break
        if normalized.get("x-amz-request-charged") != "requester":
            failed += 1
            observations.append({
                "role": spec["role"], "dataset_family_id": spec["dataset_family_id"], "key": spec["key"],
                "request_index": attempts, "http_status": status, "status": "INTEGRITY_FAILURE",
                "failure_class": "REQUESTER_PAYS_CHARGE_HEADER_MISMATCH",
            })
            break
        if normalized.get("etag") != spec["expected_etag"]:
            failed += 1
            observations.append({
                "role": spec["role"], "dataset_family_id": spec["dataset_family_id"], "key": spec["key"],
                "request_index": attempts, "http_status": status, "status": "INTEGRITY_FAILURE",
                "failure_class": "RESPONSE_ETAG_MISMATCH",
            })
            break
        try:
            observed_length = int(normalized.get("content-length", ""))
        except ValueError:
            observed_length = -1
        if observed_length != spec["expected_size_bytes"] or len(body) != spec["expected_size_bytes"]:
            failed += 1
            observations.append({
                "role": spec["role"], "dataset_family_id": spec["dataset_family_id"], "key": spec["key"],
                "request_index": attempts, "http_status": status, "status": "INTEGRITY_FAILURE",
                "failure_class": "CONTENT_LENGTH_MISMATCH", "observed_content_length": observed_length,
                "observed_body_bytes": len(body),
            })
            break
        compressed_sha = sha256_bytes(body)
        analysis = analyze_compressed_object(body)
        total_compressed += len(body)
        total_decompressed += analysis["decompressed_byte_count"]
        if total_decompressed > MAX_TOTAL_DECOMPRESSED_BYTES:
            failed += 1
            observations.append({
                "role": spec["role"], "dataset_family_id": spec["dataset_family_id"], "key": spec["key"],
                "request_index": attempts, "http_status": status, "status": "INTEGRITY_FAILURE",
                "failure_class": "TOTAL_DECOMPRESSED_BYTE_CAP_BREACH",
            })
            break
        observations.append({
            "role": spec["role"], "dataset_family_id": spec["dataset_family_id"], "key": spec["key"],
            "request_index": attempts, "http_status": status, "status": "OBJECT_PROCESSED",
            "request_charged": "requester", "expected_etag": spec["expected_etag"],
            "observed_etag": normalized["etag"], "expected_content_length": spec["expected_size_bytes"],
            "observed_content_length": observed_length, "compressed_object_size_bytes": len(body),
            "compressed_object_sha256": compressed_sha, **analysis,
        })
        successful += 1

    runtime = round(clock() - started, 6)
    complete_transport = (
        attempts == MAX_REQUESTS and http_requests == MAX_REQUESTS and successful == MAX_REQUESTS and failed == 0
        and len(observations) == MAX_REQUESTS and total_compressed == MAX_TOTAL_COMPRESSED_BYTES
        and runtime <= MAX_RUNTIME_SECONDS
    )
    schema_class = "SCHEMA_UNRESOLVED"
    technical_result = "INTEGRITY_OR_TRANSPORT_FAILURE"
    terminal_status = "R4_BODY_SCHEMA_PILOT_FAIL"
    if complete_transport:
        schema_class, technical_result = compare_schemas(observations[0], observations[1])
        terminal_status = "R4_BODY_SCHEMA_PILOT_COMPLETE"
    return {
        "schema_version": "1.0", "pilot_id": PILOT_ID, "terminal_status": terminal_status,
        "technical_result": technical_result, "schema_comparison_class": schema_class,
        "request_attempt_count": attempts, "s3_http_request_count": http_requests,
        "successful_request_count": successful, "failed_request_count": failed,
        "total_compressed_bytes": total_compressed, "total_decompressed_bytes": total_decompressed,
        "runtime_seconds": runtime, "retries_used": 0, "http_redirects_followed": False,
        "requester_pays_requested": True, "if_match_etag_required": True,
        "exact_content_length_required": True, "raw_compressed_object_persisted": False,
        "raw_decompressed_payload_retained": False, "record_payload_retained": False,
        "wallet_addresses_retained_from_body": False, "payload_values_retained": False,
        "semantic_equivalence_inferred": False, "wallet_reconstruction_performed": False,
        "entity_clustering_performed": False, "copyability_analysis_performed": False,
        "pnl_or_alpha_analysis_performed": False, "market_data_ingested": False,
        "observations": observations, "empirical_result": None, "observed_at_utc": utc_now(),
    }


def write_result(path: Path, result: dict) -> None:
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: collector.py OUTPUT_JSON", file=sys.stderr)
        return 64
    output = Path(argv[1])
    try:
        result = execute_pilot()
    except Exception:
        result = {
            "schema_version": "1.0", "pilot_id": PILOT_ID, "terminal_status": "R4_BODY_SCHEMA_PILOT_FAIL",
            "technical_result": "PRE_NETWORK_OR_UNHANDLED_FAILURE", "schema_comparison_class": "SCHEMA_UNRESOLVED",
            "request_attempt_count": 0, "s3_http_request_count": 0, "successful_request_count": 0,
            "failed_request_count": 1, "total_compressed_bytes": 0, "total_decompressed_bytes": 0,
            "runtime_seconds": 0, "retries_used": 0, "http_redirects_followed": False,
            "requester_pays_requested": False, "if_match_etag_required": True,
            "exact_content_length_required": True, "raw_compressed_object_persisted": False,
            "raw_decompressed_payload_retained": False, "record_payload_retained": False,
            "wallet_addresses_retained_from_body": False, "payload_values_retained": False,
            "semantic_equivalence_inferred": False, "wallet_reconstruction_performed": False,
            "entity_clustering_performed": False, "copyability_analysis_performed": False,
            "pnl_or_alpha_analysis_performed": False, "market_data_ingested": False,
            "observations": [], "empirical_result": None, "observed_at_utc": utc_now(),
        }
    write_result(output, result)
    return 0 if result["terminal_status"] == "R4_BODY_SCHEMA_PILOT_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
