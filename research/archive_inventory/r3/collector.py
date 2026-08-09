from __future__ import annotations

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
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[3]
R3_ROOT = ROOT / "research/archive_inventory/r3"
PREREGISTRATION = R3_ROOT / "HOURLY_METADATA_INVENTORY_R3_CONTRACT.json"
IMPLEMENTATION = R3_ROOT / "R3_IMPLEMENTATION_CONTRACT.json"
APPROVAL_JSON = R3_ROOT / "approvals/APPROVE_HL_ARCHIVE_HOURLY_METADATA_INVENTORY_R3_001.json"
APPROVAL_TEXT = R3_ROOT / "approvals/APPROVE_HL_ARCHIVE_HOURLY_METADATA_INVENTORY_R3_001.txt"

INVENTORY_ID = "HL-ARCHIVE-HOURLY-METADATA-INVENTORY-R3-001"
APPROVAL_ID = "APPROVE_HL_ARCHIVE_HOURLY_METADATA_INVENTORY_R3_001"
PREREGISTRATION_COMMIT = "ab4d42be02fe49d7f90f933317ef856f0322fd85"
APPROVAL_MERGE_COMMIT = "e562f3fbd8f1dac1b4d7e93eed2f5ee6b77c5da6"
APPROVAL_TEXT_SHA256 = "3c3931133fb8b0dd322d7a296b7b70fca65dd341401a6eda2b6372938ed6cd10"
TARGET_BUCKET = "hl-mainnet-node-data"
SIGNING_REGION = "ap-northeast-1"
REGIONAL_ENDPOINT = f"{TARGET_BUCKET}.s3.{SIGNING_REGION}.amazonaws.com"
SERVICE = "s3"
MAX_KEYS = 1000
MAX_PAGES_PER_FAMILY = 16
MAX_REQUESTS = 48
MAX_ENTRIES = 48_000
MAX_RESPONSE_BYTES = 33_554_432
MAX_RUNTIME_SECONDS = 300
EMPTY_PAYLOAD_SHA256 = hashlib.sha256(b"").hexdigest()
EXPECTED_DATASETS = (
    ("node_fills_by_block", "node_fills_by_block/hourly/"),
    ("node_fills", "node_fills/hourly/"),
    ("node_trades", "node_trades/hourly/"),
)
KEY_PATTERNS = {
    family: re.compile(rf"^{re.escape(prefix)}(?P<date>[0-9]{{8}})/(?P<hour>[0-9]|1[0-9]|2[0-3])\.lz4$")
    for family, prefix in EXPECTED_DATASETS
}
KNOWN_S3_ERROR_CODES = {
    "AccessDenied", "AllAccessDisabled", "AuthorizationHeaderMalformed", "ExpiredToken",
    "InvalidAccessKeyId", "InvalidRequest", "NoSuchBucket", "PermanentRedirect", "Redirect",
    "RequestTimeout", "SignatureDoesNotMatch", "SlowDown",
}


class R3ContractError(RuntimeError):
    pass


class R3LayoutError(R3ContractError):
    pass


class R3TransportError(RuntimeError):
    pass


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise R3ContractError("json root must be object")
    return value


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def signing_now() -> datetime:
    return datetime.now(timezone.utc)


def _dataset_pairs(rows: object) -> list[tuple[str, str]]:
    if not isinstance(rows, list):
        raise R3ContractError("dataset family list missing")
    result: list[tuple[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise R3ContractError("dataset family row invalid")
        family, prefix = row.get("dataset_family_id"), row.get("prefix")
        if not isinstance(family, str) or not isinstance(prefix, str):
            raise R3ContractError("dataset family identity invalid")
        result.append((family, prefix))
    return result


def validate_static_inputs() -> list[dict]:
    approval = load_json(APPROVAL_JSON)
    prereg = load_json(PREREGISTRATION)
    impl = load_json(IMPLEMENTATION)
    if sha256_bytes(APPROVAL_TEXT.read_bytes()) != APPROVAL_TEXT_SHA256:
        raise R3ContractError("approval text hash drift")
    if approval.get("approval_id") != APPROVAL_ID or approval.get("reviewed_commit") != PREREGISTRATION_COMMIT:
        raise R3ContractError("approval identity drift")
    if approval.get("exact_approval_text_sha256") != APPROVAL_TEXT_SHA256:
        raise R3ContractError("approval hash drift")
    if approval.get("target_bucket") != TARGET_BUCKET or approval.get("signing_region") != SIGNING_REGION:
        raise R3ContractError("approval target drift")
    if approval.get("prefixes") != [prefix for _, prefix in EXPECTED_DATASETS]:
        raise R3ContractError("approval prefix drift")
    expected_approval = {
        "maximum_one_time_budget_eur": 0.10, "maximum_monthly_budget_eur": 0,
        "maximum_list_requests": MAX_REQUESTS, "maximum_pages_per_family": MAX_PAGES_PER_FAMILY,
        "maximum_keys_per_request": MAX_KEYS, "maximum_total_entries": MAX_ENTRIES,
        "maximum_total_response_bytes": MAX_RESPONSE_BYTES, "maximum_runtime_seconds": MAX_RUNTIME_SECONDS,
        "maximum_retries_per_request": 0, "pagination_authorized": True,
        "continuation_token_follow_authorized": True, "continuation_token_values_retained": False,
        "repeated_continuation_token_fails_closed": True, "http_redirect_following_authorized": False,
        "start_after_authorized": False, "delimiter_authorized": False,
        "requester_pays_scope_approved": True, "list_objects_v2_scope_approved": True,
    }
    for name, expected in expected_approval.items():
        if approval.get(name) != expected:
            raise R3ContractError(f"approval drift: {name}")
    if not all(value is True for value in approval.get("forbidden_capabilities", {}).values()):
        raise R3ContractError("approval forbidden capability drift")
    if not all(value is False for value in approval.get("trading_authorizations", {}).values()):
        raise R3ContractError("approval trading authorization opened")

    if prereg.get("inventory_id") != INVENTORY_ID:
        raise R3ContractError("preregistration identity drift")
    if prereg.get("target_bucket") != TARGET_BUCKET or prereg.get("signing_region") != SIGNING_REGION:
        raise R3ContractError("preregistration target drift")
    if prereg.get("regional_virtual_hosted_endpoint") != REGIONAL_ENDPOINT:
        raise R3ContractError("preregistration endpoint drift")
    if _dataset_pairs(prereg.get("dataset_families")) != list(EXPECTED_DATASETS):
        raise R3ContractError("preregistration dataset drift")
    listing = prereg.get("listing_envelope", {})
    expected_listing = {
        "maximum_keys_per_request": MAX_KEYS, "maximum_pages_per_family": MAX_PAGES_PER_FAMILY,
        "maximum_total_list_requests": MAX_REQUESTS, "maximum_total_entries": MAX_ENTRIES,
        "maximum_total_response_bytes": MAX_RESPONSE_BYTES, "maximum_runtime_seconds": MAX_RUNTIME_SECONDS,
        "maximum_retries_per_request": 0, "pagination_authorized_after_separate_approval": True,
        "continuation_token_follow_authorized_after_separate_approval": True,
        "continuation_token_values_may_be_retained": False, "repeated_continuation_token_fails_closed": True,
        "http_redirect_following_authorized": False, "start_after_authorized": False,
        "delimiter_authorized": False, "fetch_owner": False,
    }
    for name, expected in expected_listing.items():
        if listing.get(name) != expected:
            raise R3ContractError(f"preregistration listing drift: {name}")

    if impl.get("inventory_id") != INVENTORY_ID or impl.get("status") != "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION":
        raise R3ContractError("implementation identity/status drift")
    if impl.get("preregistration_commit") != PREREGISTRATION_COMMIT:
        raise R3ContractError("implementation preregistration drift")
    if impl.get("approval_merge_commit") != APPROVAL_MERGE_COMMIT or impl.get("approval_text_sha256") != APPROVAL_TEXT_SHA256:
        raise R3ContractError("implementation approval binding drift")
    if impl.get("target_bucket") != TARGET_BUCKET or impl.get("signing_region") != SIGNING_REGION:
        raise R3ContractError("implementation target drift")
    if impl.get("regional_virtual_hosted_endpoint") != REGIONAL_ENDPOINT:
        raise R3ContractError("implementation endpoint drift")
    if _dataset_pairs(impl.get("dataset_families")) != list(EXPECTED_DATASETS):
        raise R3ContractError("implementation dataset drift")
    expected_impl = {
        "maximum_keys_per_request": MAX_KEYS, "maximum_pages_per_family": MAX_PAGES_PER_FAMILY,
        "maximum_list_requests": MAX_REQUESTS, "maximum_total_entries": MAX_ENTRIES,
        "maximum_total_response_bytes": MAX_RESPONSE_BYTES, "maximum_runtime_seconds": MAX_RUNTIME_SECONDS,
        "maximum_retries_per_request": 0, "pagination_authorized": True,
        "continuation_token_follow_authorized": True, "continuation_token_values_retained": False,
        "repeated_continuation_token_fails_closed": True, "duplicate_key_fails_closed": True,
        "http_redirect_following_authorized": False, "start_after_authorized": False,
        "delimiter_authorized": False, "fetch_owner": False, "request_counter_incremented_before_transport": True,
        "maximum_one_time_budget_eur": 0.10, "maximum_monthly_budget_eur": 0,
        "execution_release_required": True, "execution_release_present": False, "execution_authorized": False,
        "paid_request_authorized": False, "requester_pays_authorized": False, "list_objects_v2_authorized": False,
    }
    for name, expected in expected_impl.items():
        if impl.get(name) != expected:
            raise R3ContractError(f"implementation drift: {name}")
    if impl.get("s3_transport") != "DIRECT_SIGV4_HTTPS_REGIONAL_ENDPOINT_NO_REDIRECT_FOLLOW":
        raise R3ContractError("transport drift")
    if impl.get("session_s3_policy") != "ALLOW_LISTBUCKET_EXACT_THREE_HOURLY_PREFIXES_MAX1000_ONLY":
        raise R3ContractError("session policy drift")
    if impl.get("expected_canonical_implementation_commit") != "PENDING_CANONICAL_IMPLEMENTATION_MERGE":
        raise R3ContractError("implementation snapshot must remain pending")
    for name in (
        "get_object_authorized", "head_object_authorized", "get_object_attributes_authorized",
        "range_get_authorized", "list_object_versions_authorized", "list_all_my_buckets_authorized",
        "object_body_download_authorized", "decompression_authorized", "explorer_blocks_inventory_authorized",
        "replica_cmds_inventory_authorized", "market_data_ingestion_authorized", "larger_300_request_inventory_authorized",
    ):
        if impl.get(name) is not False:
            raise R3ContractError(f"implementation capability opened: {name}")
    if not all(value is False for value in impl.get("trading_authorizations", {}).values()):
        raise R3ContractError("implementation trading authorization opened")
    return [{"dataset_family_id": f, "bucket": TARGET_BUCKET, "prefix": p} for f, p in EXPECTED_DATASETS]


def _aws_quote(value: str) -> str:
    return urllib.parse.quote(value, safe="-_.~")


def canonical_query(prefix: str, continuation_token: str | None = None) -> str:
    if prefix not in {p for _, p in EXPECTED_DATASETS}:
        raise R3ContractError("unregistered prefix")
    params = [("list-type", "2"), ("max-keys", str(MAX_KEYS)), ("prefix", prefix)]
    if continuation_token is not None:
        if not continuation_token:
            raise R3ContractError("empty continuation token")
        params.append(("continuation-token", continuation_token))
    return "&".join(f"{_aws_quote(k)}={_aws_quote(v)}" for k, v in sorted(params))


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode(), hashlib.sha256).digest()


def build_signed_request(bucket: str, prefix: str, continuation_token: str | None, request_time: datetime, env: dict[str, str] | None = None) -> tuple[str, str, dict[str, str]]:
    if bucket != TARGET_BUCKET or prefix not in {p for _, p in EXPECTED_DATASETS}:
        raise R3ContractError("unregistered bucket/prefix")
    source = os.environ if env is None else env
    access_key, secret_key, session_token = source.get("AWS_ACCESS_KEY_ID"), source.get("AWS_SECRET_ACCESS_KEY"), source.get("AWS_SESSION_TOKEN")
    if not access_key or not secret_key or not session_token:
        raise R3ContractError("temporary AWS credentials missing")
    if request_time.tzinfo is None:
        raise R3ContractError("signing time must be timezone-aware")
    stamp = request_time.astimezone(timezone.utc)
    amz_date, date_stamp = stamp.strftime("%Y%m%dT%H%M%SZ"), stamp.strftime("%Y%m%d")
    query = canonical_query(prefix, continuation_token)
    headers_block = (
        f"host:{REGIONAL_ENDPOINT}\n"
        f"x-amz-content-sha256:{EMPTY_PAYLOAD_SHA256}\n"
        f"x-amz-date:{amz_date}\n"
        "x-amz-request-payer:requester\n"
        f"x-amz-security-token:{session_token}\n"
    )
    signed = "host;x-amz-content-sha256;x-amz-date;x-amz-request-payer;x-amz-security-token"
    canonical = "\n".join(["GET", "/", query, headers_block, signed, EMPTY_PAYLOAD_SHA256])
    scope = f"{date_stamp}/{SIGNING_REGION}/{SERVICE}/aws4_request"
    string_to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    k_date = _sign(("AWS4" + secret_key).encode(), date_stamp)
    k_region, k_service = _sign(k_date, SIGNING_REGION), _sign(_sign(k_date, SIGNING_REGION), SERVICE)
    k_signing = _sign(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()
    authorization = f"AWS4-HMAC-SHA256 Credential={access_key}/{scope},SignedHeaders={signed},Signature={signature}"
    return REGIONAL_ENDPOINT, f"/?{query}", {
        "Host": REGIONAL_ENDPOINT,
        "Authorization": authorization,
        "x-amz-content-sha256": EMPTY_PAYLOAD_SHA256,
        "x-amz-date": amz_date,
        "x-amz-request-payer": "requester",
        "x-amz-security-token": session_token,
    }


def perform_single_list_request(bucket: str, prefix: str, continuation_token: str | None, timeout_seconds: float, maximum_body_bytes: int, request_time: datetime | None = None) -> tuple[int, dict[str, str], bytes]:
    if maximum_body_bytes < 0:
        raise R3ContractError("negative response-byte allowance")
    host, target, headers = build_signed_request(bucket, prefix, continuation_token, request_time or signing_now())
    connection = http.client.HTTPSConnection(host, timeout=timeout_seconds, context=ssl.create_default_context())
    try:
        connection.request("GET", target, body=None, headers=headers)
        response = connection.getresponse()
        normalized = {k.lower(): v for k, v in response.getheaders()}
        if "content-length" in normalized:
            try:
                length = int(normalized["content-length"])
            except ValueError as exc:
                raise R3ContractError("invalid Content-Length") from exc
            if length < 0 or length > maximum_body_bytes:
                raise R3ContractError("response Content-Length exceeds remaining byte cap")
        body = response.read(maximum_body_bytes + 1)
        if len(body) > maximum_body_bytes:
            raise R3ContractError("response body exceeds remaining byte cap")
        return response.status, normalized, body
    except R3ContractError:
        raise
    except (OSError, http.client.HTTPException, ssl.SSLError) as exc:
        raise R3TransportError(type(exc).__name__) from exc
    finally:
        connection.close()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in list(element) if _local_name(child.tag) == name]


def _child_text(element: ET.Element, name: str, required: bool = True) -> str | None:
    matches = _children(element, name)
    if len(matches) > 1:
        raise R3ContractError(f"duplicate XML field: {name}")
    if not matches:
        if required:
            raise R3ContractError(f"missing XML field: {name}")
        return None
    return matches[0].text or ""


def parse_success_xml(body: bytes, family: str, bucket: str, prefix: str, request_index: int, page_ordinal: int, headers: dict[str, str], observed_at: str) -> tuple[dict, int, str | None]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise R3ContractError("invalid success XML") from exc
    if _local_name(root.tag) != "ListBucketResult" or _child_text(root, "Name") != bucket or _child_text(root, "Prefix") != prefix:
        raise R3ContractError("response identity mismatch")
    try:
        max_keys, key_count = int(_child_text(root, "MaxKeys") or ""), int(_child_text(root, "KeyCount") or "")
    except ValueError as exc:
        raise R3ContractError("invalid numeric response field") from exc
    if max_keys != MAX_KEYS or not 0 <= key_count <= MAX_KEYS:
        raise R3ContractError("response key limits invalid")
    truncated_text = (_child_text(root, "IsTruncated") or "").lower()
    if truncated_text not in {"true", "false"}:
        raise R3ContractError("response IsTruncated invalid")
    contents = _children(root, "Contents")
    if len(contents) != key_count:
        raise R3ContractError("KeyCount/Contents mismatch")
    if headers.get("x-amz-request-charged") != "requester":
        raise R3ContractError("successful Requester Pays response missing request-charged header")
    entries = []
    for ordinal, item in enumerate(contents, 1):
        object_key = _child_text(item, "Key")
        if not isinstance(object_key, str) or not object_key.startswith(prefix):
            raise R3ContractError("object key escaped prefix")
        try:
            size = int(_child_text(item, "Size") or "")
        except ValueError as exc:
            raise R3ContractError("object size invalid") from exc
        if size < 0:
            raise R3ContractError("object size invalid")
        entries.append({
            "entry_ordinal": ordinal, "key": object_key, "size_bytes": size,
            "last_modified": _child_text(item, "LastModified", False),
            "etag": _child_text(item, "ETag", False), "storage_class": _child_text(item, "StorageClass", False),
        })
    token = _child_text(root, "NextContinuationToken", False)
    truncated = truncated_text == "true"
    if truncated and not token:
        raise R3ContractError("truncated page missing continuation token")
    if not truncated and token:
        raise R3ContractError("terminal page unexpectedly returned continuation token")
    observation = {
        "dataset_family_id": family, "bucket": bucket, "prefix": prefix,
        "page_ordinal": page_ordinal, "request_index": request_index,
        "http_or_sdk_status_class": "SUCCESS", "request_charged": "requester",
        "key_count": key_count, "is_truncated": truncated,
        "next_continuation_token_present": bool(token), "response_bytes": len(body),
        "observed_at_utc": observed_at, "entries": entries,
    }
    return observation, len(entries), token


def classify_error(status: int, body: bytes) -> str:
    code = None
    try:
        root = ET.fromstring(body)
        if _local_name(root.tag) == "Error":
            code = _child_text(root, "Code", False)
    except (ET.ParseError, R3ContractError):
        pass
    if code in KNOWN_S3_ERROR_CODES:
        return f"S3_{code}"
    if 300 <= status < 400:
        return f"HTTP_{status}_REDIRECT_NOT_FOLLOWED"
    return f"HTTP_{status}"


def failure_observation(family: str, prefix: str, request_index: int, page_ordinal: int, status_class: str, response_bytes: int, observed_at: str) -> dict:
    return {
        "dataset_family_id": family, "bucket": TARGET_BUCKET, "prefix": prefix,
        "page_ordinal": page_ordinal, "request_index": request_index,
        "http_or_sdk_status_class": status_class, "request_charged": None,
        "key_count": 0, "is_truncated": False, "next_continuation_token_present": False,
        "response_bytes": response_bytes, "observed_at_utc": observed_at, "entries": [],
    }


def parse_hour_key(family: str, object_key: str) -> datetime:
    pattern = KEY_PATTERNS.get(family)
    match = pattern.fullmatch(object_key) if pattern else None
    if match is None:
        raise R3LayoutError("invalid hourly key grammar")
    try:
        date = datetime.strptime(match.group("date"), "%Y%m%d").date()
        hour = int(match.group("hour"))
    except (ValueError, TypeError) as exc:
        raise R3LayoutError("invalid hourly key timestamp") from exc
    return datetime(date.year, date.month, date.day, hour, tzinfo=timezone.utc)


def summarize_family(family: str, prefix: str, family_status: str, page_observations: list[dict], timestamps: list[datetime]) -> dict:
    summary = {
        "dataset_family_id": family, "prefix": prefix, "family_status": family_status,
        "page_count": len(page_observations),
        "entry_count": sum(int(row["key_count"]) for row in page_observations),
        "response_bytes": sum(int(row["response_bytes"]) for row in page_observations),
        "earliest_path_hour_utc": None, "latest_path_hour_utc": None,
        "gap_status": "NO_GAP_CLAIM", "missing_internal_hour_count": 0, "missing_internal_hours_utc": [],
    }
    if timestamps:
        ordered = sorted(timestamps)
        summary["earliest_path_hour_utc"] = ordered[0].isoformat().replace("+00:00", "Z")
        summary["latest_path_hour_utc"] = ordered[-1].isoformat().replace("+00:00", "Z")
    if family_status == "CENSORED_BY_LIMIT":
        summary["gap_status"] = "CENSORED_BY_LIMIT"
        return summary
    if family_status != "COMPLETE":
        summary["gap_status"] = family_status
        return summary
    if not timestamps:
        return summary
    hours_by_date: dict = {}
    for stamp in timestamps:
        hours_by_date.setdefault(stamp.date(), set()).add(stamp.hour)
    earliest_date, latest_date = min(hours_by_date), max(hours_by_date)
    missing: list[str] = []
    cursor = earliest_date + timedelta(days=1)
    while cursor < latest_date:
        for hour in range(24):
            if hour not in hours_by_date.get(cursor, set()):
                missing.append(datetime(cursor.year, cursor.month, cursor.day, hour, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"))
        cursor += timedelta(days=1)
    if missing:
        summary["gap_status"] = "PROVEN_KEY_GAP"
        summary["missing_internal_hour_count"] = len(missing)
        summary["missing_internal_hours_utc"] = missing
    return summary


def build_transition_analysis(family_summaries: list[dict]) -> dict:
    by_family = {row["dataset_family_id"]: row for row in family_summaries}
    legacy, modern = by_family.get("node_fills"), by_family.get("node_fills_by_block")
    result = {
        "status": "UNRESOLVED_DUE_TO_INCOMPLETE_ENUMERATION",
        "legacy_node_fills_latest_path_hour_utc": legacy.get("latest_path_hour_utc") if legacy else None,
        "modern_node_fills_by_block_earliest_path_hour_utc": modern.get("earliest_path_hour_utc") if modern else None,
        "delta_hours_modern_start_minus_legacy_end": None, "relation": None,
        "schema_or_body_continuity_inferred": False,
    }
    if not legacy or not modern or legacy.get("family_status") != "COMPLETE" or modern.get("family_status") != "COMPLETE":
        return result
    if not legacy.get("latest_path_hour_utc") or not modern.get("earliest_path_hour_utc"):
        return result
    legacy_end = datetime.fromisoformat(legacy["latest_path_hour_utc"].replace("Z", "+00:00"))
    modern_start = datetime.fromisoformat(modern["earliest_path_hour_utc"].replace("Z", "+00:00"))
    delta = int((modern_start - legacy_end).total_seconds() // 3600)
    relation = "METADATA_GAP_BETWEEN_FAMILIES" if delta > 1 else "METADATA_CONTIGUOUS_HOURLY_BOUNDARY" if delta == 1 else "METADATA_OVERLAP_OR_REVERSED_BOUNDARY"
    result.update({"status": "COMPLETE_METADATA_BOUNDARY_COMPARISON", "delta_hours_modern_start_minus_legacy_end": delta, "relation": relation})
    return result


def execute_inventory(output_path: Path, transport: Callable[[str, str, str | None, float, int], tuple[int, dict[str, str], bytes]] = perform_single_list_request, monotonic: Callable[[], float] = time.monotonic, now: Callable[[], str] = utc_now) -> dict:
    datasets = validate_static_inputs()
    started = monotonic()
    observations: list[dict] = []
    summaries: list[dict] = []
    attempts = successes = total_entries = total_bytes = continuation_requests = 0
    hard_failure = False
    failure_status: str | None = None

    for row in datasets:
        if hard_failure:
            break
        family, bucket, prefix = row["dataset_family_id"], row["bucket"], row["prefix"]
        pages: list[dict] = []
        timestamps: list[datetime] = []
        seen_keys: set[str] = set()
        seen_tokens: set[str] = set()
        continuation: str | None = None
        family_status = "INCOMPLETE_DUE_TO_FAILURE"

        for page_ordinal in range(1, MAX_PAGES_PER_FAMILY + 1):
            elapsed = monotonic() - started
            if elapsed >= MAX_RUNTIME_SECONDS:
                hard_failure, failure_status = True, "RUNTIME_CAP_EXCEEDED"
                break
            if attempts >= MAX_REQUESTS:
                hard_failure, failure_status = True, "REQUEST_CAP_EXCEEDED"
                break
            remaining = MAX_RESPONSE_BYTES - total_bytes
            if remaining <= 0:
                hard_failure, failure_status = True, "RESPONSE_BYTE_CAP_EXCEEDED"
                break
            attempts += 1
            if continuation is not None:
                continuation_requests += 1
            observed_at = now()
            try:
                status, headers, body = transport(bucket, prefix, continuation, max(1.0, min(20.0, MAX_RUNTIME_SECONDS - elapsed)), remaining)
                response_bytes = len(body)
                total_bytes += response_bytes
                if response_bytes > remaining or total_bytes > MAX_RESPONSE_BYTES:
                    failure = failure_observation(family, prefix, attempts, page_ordinal, "RESPONSE_BYTE_CAP_EXCEEDED", response_bytes, observed_at)
                    observations.append(failure); pages.append(failure)
                    hard_failure, failure_status = True, "RESPONSE_BYTE_CAP_EXCEEDED"
                    break
                if status != 200:
                    failure = failure_observation(family, prefix, attempts, page_ordinal, classify_error(status, body), response_bytes, observed_at)
                    observations.append(failure); pages.append(failure)
                    hard_failure, failure_status = True, "INCOMPLETE_DUE_TO_FAILURE"
                    break

                observation, count, next_token = parse_success_xml(body, family, bucket, prefix, attempts, page_ordinal, {k.lower(): v for k, v in headers.items()}, observed_at)
                page_keys: set[str] = set()
                page_timestamps: list[datetime] = []
                for entry in observation["entries"]:
                    object_key = entry["key"]
                    if object_key in seen_keys or object_key in page_keys:
                        raise R3ContractError("duplicate object key across pages")
                    page_keys.add(object_key)
                    page_timestamps.append(parse_hour_key(family, object_key))
                if observation["is_truncated"]:
                    if next_token is None:
                        raise R3ContractError("truncated page token missing after validation")
                    if next_token in seen_tokens:
                        raise R3ContractError("repeated continuation token")

                if total_entries + count > MAX_ENTRIES:
                    raise R3ContractError("entry cap exceeded")
                total_entries += count
                seen_keys.update(page_keys)
                timestamps.extend(page_timestamps)
                observations.append(observation); pages.append(observation); successes += 1

                if not observation["is_truncated"]:
                    family_status, continuation = "COMPLETE", None
                    break
                if page_ordinal == MAX_PAGES_PER_FAMILY:
                    family_status, continuation = "CENSORED_BY_LIMIT", None
                    break
                seen_tokens.add(next_token)
                continuation = next_token

            except R3LayoutError:
                failure = failure_observation(family, prefix, attempts, page_ordinal, "UNRESOLVED_LAYOUT", 0, observed_at)
                observations.append(failure); pages.append(failure)
                family_status, hard_failure, failure_status = "UNRESOLVED_LAYOUT", True, "UNRESOLVED_LAYOUT"
                break
            except R3TransportError as exc:
                failure = failure_observation(family, prefix, attempts, page_ordinal, f"HTTPS_TRANSPORT_{exc}", 0, observed_at)
                observations.append(failure); pages.append(failure)
                hard_failure, failure_status = True, "INCOMPLETE_DUE_TO_FAILURE"
                break
            except R3ContractError as exc:
                text = str(exc).lower()
                status_class = "CONTINUATION_TOKEN_CYCLE" if "repeated continuation token" in text else "ENTRY_CAP_EXCEEDED" if "entry cap" in text else "INVALID_OR_OVERSIZE_LIST_RESPONSE"
                failure = failure_observation(family, prefix, attempts, page_ordinal, status_class, 0, observed_at)
                observations.append(failure); pages.append(failure)
                hard_failure, failure_status = True, status_class
                break

        summaries.append(summarize_family(family, prefix, family_status, pages, timestamps))

    runtime = monotonic() - started
    if runtime > MAX_RUNTIME_SECONDS:
        hard_failure, failure_status = True, failure_status or "RUNTIME_CAP_EXCEEDED"
    failed_requests = attempts - successes
    valid_statuses = {"COMPLETE", "CENSORED_BY_LIMIT"}
    research_pass = (
        not hard_failure and len(summaries) == 3 and all(row["family_status"] in valid_statuses for row in summaries)
        and failed_requests == 0 and attempts <= MAX_REQUESTS and total_entries <= MAX_ENTRIES
        and total_bytes <= MAX_RESPONSE_BYTES and runtime <= MAX_RUNTIME_SECONDS
    )
    all_complete = research_pass and all(row["family_status"] == "COMPLETE" for row in summaries)
    technical = "THREE_HOURLY_FAMILIES_COMPLETE" if all_complete else "THREE_HOURLY_FAMILIES_COMPLETE_OR_CENSORED" if research_pass else "R3_HOURLY_METADATA_INVENTORY_FAILED"
    result = {
        "schema_version": "1.0", "inventory_id": INVENTORY_ID,
        "terminal_status": "R3_HOURLY_METADATA_INVENTORY_PASS" if research_pass else "R3_HOURLY_METADATA_INVENTORY_FAIL",
        "technical_result": technical, "terminal_failure_status": failure_status,
        "request_attempt_count": attempts, "s3_http_request_count": attempts,
        "successful_request_count": successes, "failed_request_count": failed_requests,
        "continuation_request_count": continuation_requests,
        "total_entries": total_entries, "total_response_bytes": total_bytes, "runtime_seconds": round(runtime, 6),
        "maximum_list_requests": MAX_REQUESTS, "maximum_pages_per_family": MAX_PAGES_PER_FAMILY,
        "maximum_keys_per_request": MAX_KEYS, "maximum_total_entries": MAX_ENTRIES,
        "maximum_total_response_bytes": MAX_RESPONSE_BYTES, "maximum_runtime_seconds": MAX_RUNTIME_SECONDS,
        "retries_used": 0, "pagination_followed": continuation_requests > 0,
        "continuation_token_values_retained": False, "repeated_continuation_token_fails_closed": True,
        "http_redirects_followed": False, "start_after_used": False, "delimiter_used": False,
        "signing_region": SIGNING_REGION, "regional_endpoint": REGIONAL_ENDPOINT,
        "requester_pays_requested": attempts > 0, "object_body_requested": False,
        "decompression_used": False, "market_data_ingested": False, "empirical_result": None,
        "family_summaries": summaries, "transition_analysis": build_transition_analysis(summaries), "observations": observations,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def write_pre_network_failure(output_path: Path) -> None:
    result = {
        "schema_version": "1.0", "inventory_id": INVENTORY_ID,
        "terminal_status": "R3_PRE_NETWORK_CONTRACT_FAIL", "technical_result": None,
        "terminal_failure_status": "STATIC_CONTRACT_FAILURE", "request_attempt_count": 0,
        "s3_http_request_count": 0, "successful_request_count": 0, "failed_request_count": 0,
        "continuation_request_count": 0, "total_entries": 0, "total_response_bytes": 0,
        "runtime_seconds": 0.0, "maximum_list_requests": MAX_REQUESTS,
        "maximum_pages_per_family": MAX_PAGES_PER_FAMILY, "maximum_keys_per_request": MAX_KEYS,
        "maximum_total_entries": MAX_ENTRIES, "maximum_total_response_bytes": MAX_RESPONSE_BYTES,
        "maximum_runtime_seconds": MAX_RUNTIME_SECONDS, "retries_used": 0, "pagination_followed": False,
        "continuation_token_values_retained": False, "repeated_continuation_token_fails_closed": True,
        "http_redirects_followed": False, "start_after_used": False, "delimiter_used": False,
        "signing_region": SIGNING_REGION, "regional_endpoint": REGIONAL_ENDPOINT,
        "requester_pays_requested": False, "object_body_requested": False,
        "decompression_used": False, "market_data_ingested": False, "empirical_result": None,
        "family_summaries": [], "transition_analysis": {"status": "NOT_EXECUTED", "schema_or_body_continuity_inferred": False},
        "observations": [],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    output = Path(sys.argv[1])
    try:
        result = execute_inventory(output)
    except R3ContractError:
        write_pre_network_failure(output)
        return 3
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
