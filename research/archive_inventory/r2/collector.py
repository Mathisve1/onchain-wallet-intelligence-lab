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
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[3]
R2_ROOT = ROOT / "research/archive_inventory/r2"
PREREGISTRATION = R2_ROOT / "NODEDATA_METADATA_CANARY_R2_CONTRACT.json"
IMPLEMENTATION = R2_ROOT / "R2_IMPLEMENTATION_CONTRACT.json"
APPROVAL_JSON = R2_ROOT / "approvals/APPROVE_HL_ARCHIVE_NODEDATA_CANARY_R2_001.json"
APPROVAL_TEXT = R2_ROOT / "approvals/APPROVE_HL_ARCHIVE_NODEDATA_CANARY_R2_001.txt"

CANARY_ID = "HL-ARCHIVE-NODEDATA-METADATA-CANARY-R2-001"
APPROVAL_ID = "APPROVE_HL_ARCHIVE_NODEDATA_CANARY_R2_001"
APPROVAL_REVIEWED_COMMIT = "39b40cccc7e9a3fdbc439d06fb188e946d9da2aa"
APPROVAL_MERGE_COMMIT = "151e08f54037ca7d3a0a9c17d3bdfb84d707a66e"
APPROVAL_TEXT_SHA256 = "728f4e21c045eb10e883bdf0f2e970686f0e6b6cc4dc67a4f214a882cf1831c6"

TARGET_BUCKET = "hl-mainnet-node-data"
SIGNING_REGION = "ap-northeast-1"
REGIONAL_ENDPOINT = f"{TARGET_BUCKET}.s3.{SIGNING_REGION}.amazonaws.com"
SERVICE = "s3"
MAX_REQUESTS = 5
MAX_KEYS = 25
MAX_ENTRIES = 125
MAX_RESPONSE_BYTES = 8_388_608
MAX_RUNTIME_SECONDS = 120
EMPTY_PAYLOAD_SHA256 = hashlib.sha256(b"").hexdigest()

EXPECTED_DATASETS = (
    ("node_fills_by_block", "node_fills_by_block/"),
    ("node_fills", "node_fills/"),
    ("node_trades", "node_trades/"),
    ("explorer_blocks", "explorer_blocks/"),
    ("replica_cmds", "replica_cmds/"),
)

KNOWN_S3_ERROR_CODES = {
    "AccessDenied",
    "AllAccessDisabled",
    "AuthorizationHeaderMalformed",
    "ExpiredToken",
    "InvalidAccessKeyId",
    "InvalidRequest",
    "NoSuchBucket",
    "PermanentRedirect",
    "Redirect",
    "RequestTimeout",
    "SignatureDoesNotMatch",
    "SlowDown",
}


class R2ContractError(RuntimeError):
    pass


class R2TransportError(RuntimeError):
    pass


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise R2ContractError("json root must be object")
    return value


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def signing_now() -> datetime:
    return datetime.now(timezone.utc)


def validate_static_inputs() -> list[dict]:
    approval = load_json(APPROVAL_JSON)
    prereg = load_json(PREREGISTRATION)
    implementation = load_json(IMPLEMENTATION)

    if sha256_bytes(APPROVAL_TEXT.read_bytes()) != APPROVAL_TEXT_SHA256:
        raise R2ContractError("approval text hash drift")
    if approval.get("approval_id") != APPROVAL_ID:
        raise R2ContractError("approval id drift")
    if approval.get("approval_status") != "APPROVED_SCOPE_AND_BUDGET_AWAITING_IMPLEMENTATION":
        raise R2ContractError("approval status drift")
    if approval.get("reviewed_commit") != APPROVAL_REVIEWED_COMMIT:
        raise R2ContractError("approval reviewed commit drift")
    if approval.get("exact_approval_text_sha256") != APPROVAL_TEXT_SHA256:
        raise R2ContractError("approval hash drift")
    if approval.get("target_bucket") != TARGET_BUCKET or approval.get("signing_region") != SIGNING_REGION:
        raise R2ContractError("approval target/region drift")
    if approval.get("maximum_one_time_budget_eur") != 0.10 or approval.get("maximum_monthly_budget_eur") != 0:
        raise R2ContractError("approval budget drift")
    if approval.get("maximum_list_requests") != MAX_REQUESTS:
        raise R2ContractError("approval request cap drift")
    if approval.get("maximum_keys_per_request") != MAX_KEYS:
        raise R2ContractError("approval max-keys drift")
    if approval.get("maximum_total_entries") != MAX_ENTRIES:
        raise R2ContractError("approval entry cap drift")
    if approval.get("maximum_total_response_bytes") != MAX_RESPONSE_BYTES:
        raise R2ContractError("approval response-byte cap drift")
    if approval.get("maximum_runtime_seconds") != MAX_RUNTIME_SECONDS:
        raise R2ContractError("approval runtime cap drift")
    if approval.get("maximum_retries_per_request") != 0:
        raise R2ContractError("approval retries opened")
    if approval.get("pagination_authorized") is not False:
        raise R2ContractError("approval pagination opened")
    if approval.get("http_redirect_following_authorized") is not False:
        raise R2ContractError("approval redirect following opened")
    if approval.get("requester_pays_scope_approved") is not True:
        raise R2ContractError("requester pays scope not approved")
    if approval.get("list_objects_v2_scope_approved") is not True:
        raise R2ContractError("ListObjectsV2 scope not approved")
    forbidden = approval.get("forbidden_capabilities")
    if not isinstance(forbidden, dict) or not forbidden or not all(value is True for value in forbidden.values()):
        raise R2ContractError("approval forbidden capability drift")

    if prereg.get("canary_id") != CANARY_ID:
        raise R2ContractError("preregistration identity drift")
    if prereg.get("target_bucket") != TARGET_BUCKET or prereg.get("signing_region") != SIGNING_REGION:
        raise R2ContractError("preregistration target/region drift")
    if prereg.get("operation") != "ListObjectsV2" or prereg.get("request_payer") != "requester":
        raise R2ContractError("preregistration operation drift")
    if prereg.get("dataset_family_count") != MAX_REQUESTS:
        raise R2ContractError("preregistration family count drift")
    expected = [{"dataset_family_id": family, "prefix": prefix} for family, prefix in EXPECTED_DATASETS]
    if prereg.get("dataset_families") != expected:
        raise R2ContractError("preregistration dataset scope/order drift")
    if prereg.get("maximum_total_list_requests") != MAX_REQUESTS:
        raise R2ContractError("preregistration request cap drift")
    if prereg.get("maximum_keys_per_request") != MAX_KEYS:
        raise R2ContractError("preregistration max-keys drift")
    if prereg.get("maximum_total_entries") != MAX_ENTRIES:
        raise R2ContractError("preregistration entry cap drift")
    if prereg.get("maximum_total_response_bytes") != MAX_RESPONSE_BYTES:
        raise R2ContractError("preregistration response-byte cap drift")
    if prereg.get("maximum_runtime_seconds") != MAX_RUNTIME_SECONDS:
        raise R2ContractError("preregistration runtime cap drift")
    if prereg.get("maximum_retries_per_request") != 0:
        raise R2ContractError("preregistration retries opened")
    if prereg.get("pagination_authorized") is not False:
        raise R2ContractError("preregistration pagination opened")
    if prereg.get("continuation_token_follow_authorized") is not False:
        raise R2ContractError("preregistration continuation follow opened")
    if prereg.get("http_redirect_following_authorized") is not False:
        raise R2ContractError("preregistration redirect following opened")

    if implementation.get("canary_id") != CANARY_ID:
        raise R2ContractError("implementation identity drift")
    if implementation.get("status") != "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION":
        raise R2ContractError("implementation status drift")
    if implementation.get("preregistration_commit") != APPROVAL_REVIEWED_COMMIT:
        raise R2ContractError("implementation preregistration binding drift")
    if implementation.get("approval_merge_commit") != APPROVAL_MERGE_COMMIT:
        raise R2ContractError("implementation approval merge binding drift")
    if implementation.get("human_approval_text_sha256") != APPROVAL_TEXT_SHA256:
        raise R2ContractError("implementation approval hash drift")
    if implementation.get("target_bucket") != TARGET_BUCKET:
        raise R2ContractError("implementation bucket drift")
    if implementation.get("signing_region") != SIGNING_REGION:
        raise R2ContractError("implementation signing region drift")
    if implementation.get("regional_virtual_hosted_endpoint") != REGIONAL_ENDPOINT:
        raise R2ContractError("implementation endpoint drift")
    if implementation.get("dataset_families") != expected:
        raise R2ContractError("implementation dataset scope/order drift")
    if implementation.get("maximum_list_requests") != MAX_REQUESTS:
        raise R2ContractError("implementation request cap drift")
    if implementation.get("maximum_keys_per_request") != MAX_KEYS:
        raise R2ContractError("implementation max-keys drift")
    if implementation.get("maximum_total_entries") != MAX_ENTRIES:
        raise R2ContractError("implementation entry cap drift")
    if implementation.get("maximum_total_response_bytes") != MAX_RESPONSE_BYTES:
        raise R2ContractError("implementation response-byte cap drift")
    if implementation.get("maximum_runtime_seconds") != MAX_RUNTIME_SECONDS:
        raise R2ContractError("implementation runtime cap drift")
    if implementation.get("maximum_retries_per_request") != 0:
        raise R2ContractError("implementation retries opened")
    if implementation.get("pagination_authorized") is not False:
        raise R2ContractError("implementation pagination opened")
    if implementation.get("continuation_token_follow_authorized") is not False:
        raise R2ContractError("implementation continuation follow opened")
    if implementation.get("http_redirect_following_authorized") is not False:
        raise R2ContractError("implementation redirect following opened")
    if implementation.get("s3_transport") != "DIRECT_SIGV4_HTTPS_REGIONAL_ENDPOINT_NO_REDIRECT_FOLLOW":
        raise R2ContractError("implementation transport drift")
    if implementation.get("execution_release_required") is not True:
        raise R2ContractError("execution release requirement drift")
    if implementation.get("expected_canonical_implementation_commit") != "PENDING_CANONICAL_IMPLEMENTATION_MERGE":
        raise R2ContractError("implementation must remain pending during review")
    for key in (
        "execution_release_present",
        "execution_authorized",
        "paid_request_authorized",
        "requester_pays_authorized",
        "list_objects_v2_authorized",
        "get_object_authorized",
        "head_object_authorized",
        "get_object_attributes_authorized",
        "range_get_authorized",
        "list_object_versions_authorized",
        "list_all_my_buckets_authorized",
        "object_body_download_authorized",
        "decompression_authorized",
        "market_data_ingestion_authorized",
        "larger_300_request_inventory_authorized",
    ):
        if implementation.get(key) is not False:
            raise R2ContractError(f"implementation authorization opened: {key}")
    if not all(value is False for value in implementation.get("trading_authorizations", {}).values()):
        raise R2ContractError("implementation trading authorization opened")

    return [
        {"dataset_family_id": family, "bucket": TARGET_BUCKET, "prefix": prefix}
        for family, prefix in EXPECTED_DATASETS
    ]


def _aws_quote(value: str) -> str:
    return urllib.parse.quote(value, safe="-_.~")


def canonical_query(prefix: str) -> str:
    params = (("list-type", "2"), ("max-keys", str(MAX_KEYS)), ("prefix", prefix))
    return "&".join(f"{_aws_quote(key)}={_aws_quote(value)}" for key, value in sorted(params))


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def build_signed_request(
    bucket: str,
    prefix: str,
    request_time: datetime,
    env: dict[str, str] | None = None,
) -> tuple[str, str, dict[str, str]]:
    if bucket != TARGET_BUCKET or prefix not in {item[1] for item in EXPECTED_DATASETS}:
        raise R2ContractError("unregistered bucket/prefix")
    source = os.environ if env is None else env
    access_key = source.get("AWS_ACCESS_KEY_ID")
    secret_key = source.get("AWS_SECRET_ACCESS_KEY")
    session_token = source.get("AWS_SESSION_TOKEN")
    if not access_key or not secret_key or not session_token:
        raise R2ContractError("temporary AWS credentials missing")
    if request_time.tzinfo is None:
        raise R2ContractError("signing time must be timezone-aware")

    stamp = request_time.astimezone(timezone.utc)
    amz_date = stamp.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = stamp.strftime("%Y%m%d")
    host = REGIONAL_ENDPOINT
    query = canonical_query(prefix)
    target = f"/?{query}"
    canonical_headers = (
        f"host:{host}\n"
        f"x-amz-content-sha256:{EMPTY_PAYLOAD_SHA256}\n"
        f"x-amz-date:{amz_date}\n"
        "x-amz-request-payer:requester\n"
        f"x-amz-security-token:{session_token}\n"
    )
    signed_headers = "host;x-amz-content-sha256;x-amz-date;x-amz-request-payer;x-amz-security-token"
    canonical_request = "\n".join(
        ["GET", "/", query, canonical_headers, signed_headers, EMPTY_PAYLOAD_SHA256]
    )
    scope = f"{date_stamp}/{SIGNING_REGION}/{SERVICE}/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    k_date = _sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _sign(k_date, SIGNING_REGION)
    k_service = _sign(k_region, SERVICE)
    k_signing = _sign(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{scope},"
        f"SignedHeaders={signed_headers},Signature={signature}"
    )
    headers = {
        "Host": host,
        "Authorization": authorization,
        "x-amz-content-sha256": EMPTY_PAYLOAD_SHA256,
        "x-amz-date": amz_date,
        "x-amz-request-payer": "requester",
        "x-amz-security-token": session_token,
    }
    return host, target, headers


def perform_single_list_request(
    bucket: str,
    prefix: str,
    timeout_seconds: float,
    maximum_body_bytes: int,
    request_time: datetime | None = None,
) -> tuple[int, dict[str, str], bytes]:
    if maximum_body_bytes < 0:
        raise R2ContractError("negative response-byte allowance")
    host, target, headers = build_signed_request(bucket, prefix, request_time or signing_now())
    connection = http.client.HTTPSConnection(
        host,
        timeout=timeout_seconds,
        context=ssl.create_default_context(),
    )
    try:
        connection.request("GET", target, body=None, headers=headers)
        response = connection.getresponse()
        normalized_headers = {key.lower(): value for key, value in response.getheaders()}
        length = normalized_headers.get("content-length")
        if length is not None:
            try:
                content_length = int(length)
            except ValueError as exc:
                raise R2ContractError("invalid Content-Length") from exc
            if content_length < 0 or content_length > maximum_body_bytes:
                raise R2ContractError("response Content-Length exceeds remaining byte cap")
        body = response.read(maximum_body_bytes)
        return response.status, normalized_headers, body
    except R2ContractError:
        raise
    except (OSError, http.client.HTTPException, ssl.SSLError) as exc:
        raise R2TransportError(type(exc).__name__) from exc
    finally:
        connection.close()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in list(element) if _local_name(child.tag) == name]


def _child_text(element: ET.Element, name: str, required: bool = True) -> str | None:
    matches = _children(element, name)
    if len(matches) > 1:
        raise R2ContractError(f"duplicate XML field: {name}")
    if not matches:
        if required:
            raise R2ContractError(f"missing XML field: {name}")
        return None
    return matches[0].text or ""


def parse_success_xml(
    body: bytes,
    family: str,
    bucket: str,
    prefix: str,
    request_index: int,
    headers: dict[str, str],
    observed_at: str,
) -> tuple[dict, int]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise R2ContractError("invalid success XML") from exc
    if _local_name(root.tag) != "ListBucketResult":
        raise R2ContractError("unexpected success XML root")
    if _child_text(root, "Name") != bucket:
        raise R2ContractError("response bucket mismatch")
    if _child_text(root, "Prefix") != prefix:
        raise R2ContractError("response prefix mismatch")
    try:
        max_keys = int(_child_text(root, "MaxKeys") or "")
        key_count = int(_child_text(root, "KeyCount") or "")
    except ValueError as exc:
        raise R2ContractError("invalid numeric response field") from exc
    if max_keys != MAX_KEYS:
        raise R2ContractError("response MaxKeys mismatch")
    if not 0 <= key_count <= MAX_KEYS:
        raise R2ContractError("response KeyCount invalid")
    truncated_text = (_child_text(root, "IsTruncated") or "").lower()
    if truncated_text not in {"true", "false"}:
        raise R2ContractError("response IsTruncated invalid")
    contents = _children(root, "Contents")
    if len(contents) != key_count or len(contents) > MAX_KEYS:
        raise R2ContractError("KeyCount/Contents mismatch")
    if headers.get("x-amz-request-charged") != "requester":
        raise R2ContractError("successful Requester Pays response missing request-charged header")

    entries: list[dict] = []
    for item in contents:
        key = _child_text(item, "Key")
        if not isinstance(key, str) or not key.startswith(prefix):
            raise R2ContractError("object key escaped prefix")
        try:
            size = int(_child_text(item, "Size") or "")
        except ValueError as exc:
            raise R2ContractError("object size invalid") from exc
        if size < 0:
            raise R2ContractError("object size invalid")
        entries.append(
            {
                "key": key,
                "size_bytes": size,
                "last_modified": _child_text(item, "LastModified", required=False),
                "etag": _child_text(item, "ETag", required=False),
                "storage_class": _child_text(item, "StorageClass", required=False),
            }
        )
    entries.sort(key=lambda row: row["key"])
    token = _child_text(root, "NextContinuationToken", required=False)
    observation = {
        "dataset_family_id": family,
        "bucket": bucket,
        "prefix": prefix,
        "signing_region": SIGNING_REGION,
        "request_index": request_index,
        "http_or_sdk_status_class": "SUCCESS",
        "request_charged": "requester",
        "key_count": key_count,
        "is_truncated": truncated_text == "true",
        "next_continuation_token_present": bool(token),
        "response_bytes": len(body),
        "observed_at_utc": observed_at,
        "entries": entries,
    }
    return observation, len(entries)


def classify_error(status: int, body: bytes) -> str:
    code: str | None = None
    try:
        root = ET.fromstring(body)
        if _local_name(root.tag) == "Error":
            code = _child_text(root, "Code", required=False)
    except (ET.ParseError, R2ContractError):
        code = None
    if code in KNOWN_S3_ERROR_CODES:
        return f"S3_{code}"
    if 300 <= status < 400:
        return f"HTTP_{status}_REDIRECT_NOT_FOLLOWED"
    return f"HTTP_{status}"


def failure_observation(
    family: str,
    prefix: str,
    request_index: int,
    status_class: str,
    response_bytes: int,
    observed_at: str,
) -> dict:
    return {
        "dataset_family_id": family,
        "bucket": TARGET_BUCKET,
        "prefix": prefix,
        "signing_region": SIGNING_REGION,
        "request_index": request_index,
        "http_or_sdk_status_class": status_class,
        "request_charged": None,
        "key_count": 0,
        "is_truncated": False,
        "next_continuation_token_present": False,
        "response_bytes": response_bytes,
        "observed_at_utc": observed_at,
        "entries": [],
    }


def execute_canary(
    output_path: Path,
    transport: Callable[[str, str, float, int], tuple[int, dict[str, str], bytes]] = perform_single_list_request,
    monotonic: Callable[[], float] = time.monotonic,
    now: Callable[[], str] = utc_now,
) -> dict:
    datasets = validate_static_inputs()
    started = monotonic()
    observations: list[dict] = []
    request_attempt_count = 0
    successful_request_count = 0
    total_entries = 0
    total_response_bytes = 0
    hard_failure = False

    for row in datasets:
        elapsed = monotonic() - started
        if elapsed >= MAX_RUNTIME_SECONDS or request_attempt_count >= MAX_REQUESTS:
            hard_failure = True
            break

        family = row["dataset_family_id"]
        bucket = row["bucket"]
        prefix = row["prefix"]

        request_attempt_count += 1
        remaining_runtime = MAX_RUNTIME_SECONDS - elapsed
        timeout_seconds = max(1.0, min(20.0, remaining_runtime))
        remaining_bytes = MAX_RESPONSE_BYTES - total_response_bytes
        observed_at = now()

        try:
            status, headers, body = transport(bucket, prefix, timeout_seconds, remaining_bytes)
            response_bytes = len(body)
            total_response_bytes += response_bytes
            if response_bytes > remaining_bytes or total_response_bytes > MAX_RESPONSE_BYTES:
                observations.append(
                    failure_observation(
                        family,
                        prefix,
                        request_attempt_count,
                        "RESPONSE_BYTE_CAP_EXCEEDED",
                        response_bytes,
                        observed_at,
                    )
                )
                hard_failure = True
                break
            if status != 200:
                observations.append(
                    failure_observation(
                        family,
                        prefix,
                        request_attempt_count,
                        classify_error(status, body),
                        response_bytes,
                        observed_at,
                    )
                )
                continue

            observation, entry_count = parse_success_xml(
                body,
                family,
                bucket,
                prefix,
                request_attempt_count,
                {key.lower(): value for key, value in headers.items()},
                observed_at,
            )
            total_entries += entry_count
            if total_entries > MAX_ENTRIES:
                observation["http_or_sdk_status_class"] = "ENTRY_CAP_EXCEEDED"
                observations.append(observation)
                hard_failure = True
                break
            observations.append(observation)
            successful_request_count += 1
        except R2TransportError as exc:
            observations.append(
                failure_observation(
                    family,
                    prefix,
                    request_attempt_count,
                    f"HTTPS_TRANSPORT_{str(exc)}",
                    0,
                    observed_at,
                )
            )
        except R2ContractError:
            observations.append(
                failure_observation(
                    family,
                    prefix,
                    request_attempt_count,
                    "INVALID_OR_OVERSIZE_LIST_RESPONSE",
                    0,
                    observed_at,
                )
            )
            hard_failure = True
            break

    runtime_seconds = monotonic() - started
    if runtime_seconds > MAX_RUNTIME_SECONDS:
        hard_failure = True
    failed_request_count = request_attempt_count - successful_request_count
    passed = (
        not hard_failure
        and request_attempt_count == MAX_REQUESTS
        and successful_request_count == MAX_REQUESTS
        and failed_request_count == 0
        and total_entries <= MAX_ENTRIES
        and total_response_bytes <= MAX_RESPONSE_BYTES
        and runtime_seconds <= MAX_RUNTIME_SECONDS
    )
    result = {
        "schema_version": "1.0",
        "canary_id": CANARY_ID,
        "terminal_status": "R2_NODEDATA_METADATA_CANARY_PASS" if passed else "R2_NODEDATA_METADATA_CANARY_FAIL",
        "technical_result": "FIVE_PREFIX_METADATA_LISTABLE" if passed else "FIVE_PREFIX_METADATA_NOT_FULLY_LISTABLE",
        "request_attempt_count": request_attempt_count,
        "s3_http_request_count": request_attempt_count,
        "successful_request_count": successful_request_count,
        "failed_request_count": failed_request_count,
        "total_entries": total_entries,
        "total_response_bytes": total_response_bytes,
        "runtime_seconds": round(runtime_seconds, 6),
        "maximum_list_requests": MAX_REQUESTS,
        "maximum_keys_per_request": MAX_KEYS,
        "maximum_total_entries": MAX_ENTRIES,
        "maximum_total_response_bytes": MAX_RESPONSE_BYTES,
        "maximum_runtime_seconds": MAX_RUNTIME_SECONDS,
        "retries_used": 0,
        "pagination_followed": False,
        "http_redirects_followed": False,
        "signing_region": SIGNING_REGION,
        "regional_endpoint": REGIONAL_ENDPOINT,
        "requester_pays_requested": True,
        "continuation_token_values_retained": False,
        "object_body_requested": False,
        "decompression_used": False,
        "market_data_ingested": False,
        "empirical_result": None,
        "observations": observations,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def write_pre_network_failure(output_path: Path) -> None:
    result = {
        "schema_version": "1.0",
        "canary_id": CANARY_ID,
        "terminal_status": "R2_PRE_NETWORK_CONTRACT_FAIL",
        "technical_result": None,
        "request_attempt_count": 0,
        "s3_http_request_count": 0,
        "successful_request_count": 0,
        "failed_request_count": 0,
        "total_entries": 0,
        "total_response_bytes": 0,
        "runtime_seconds": 0.0,
        "maximum_list_requests": MAX_REQUESTS,
        "maximum_keys_per_request": MAX_KEYS,
        "maximum_total_entries": MAX_ENTRIES,
        "maximum_total_response_bytes": MAX_RESPONSE_BYTES,
        "maximum_runtime_seconds": MAX_RUNTIME_SECONDS,
        "retries_used": 0,
        "pagination_followed": False,
        "http_redirects_followed": False,
        "signing_region": SIGNING_REGION,
        "regional_endpoint": REGIONAL_ENDPOINT,
        "requester_pays_requested": False,
        "continuation_token_values_retained": False,
        "object_body_requested": False,
        "decompression_used": False,
        "market_data_ingested": False,
        "empirical_result": None,
        "observations": [],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    output_path = Path(sys.argv[1])
    try:
        result = execute_canary(output_path)
    except R2ContractError:
        write_pre_network_failure(output_path)
        return 3
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
