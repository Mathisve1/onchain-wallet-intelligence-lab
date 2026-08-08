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
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = ROOT / "research/archive_inventory"
R0_ROOT = ARCHIVE / "r0"
DATASET_REGISTER = ARCHIVE / "DATASET_REGISTER.json"
R0_CONTRACT = ARCHIVE / "METADATA_CANARY_R0_CONTRACT.json"
IMPLEMENTATION_CONTRACT = R0_ROOT / "R0_IMPLEMENTATION_CONTRACT.json"
APPROVAL_JSON = ARCHIVE / "approvals/APPROVE_HL_ARCHIVE_METADATA_CANARY_R0_001.json"
APPROVAL_TEXT = ARCHIVE / "approvals/APPROVE_HL_ARCHIVE_METADATA_CANARY_R0_001.txt"

CANARY_ID = "HL-ARCHIVE-METADATA-CANARY-R0-001"
APPROVAL_ID = "APPROVE_HL_ARCHIVE_METADATA_CANARY_R0_001"
APPROVAL_COMMIT = "9af4b21863e47fb3bb2997ce77b9940eecf4597f"
APPROVAL_TEXT_SHA256 = "d70008eac7521b324f61161bcc0075e28cc3a116dd30f0c52b48d8cf5eb6ed46"
MAX_REQUESTS = 7
MAX_KEYS = 25
MAX_ENTRIES = 175
MAX_RESPONSE_BYTES = 8_388_608
MAX_RUNTIME_SECONDS = 180
SIGNING_REGION = "us-east-1"
SERVICE = "s3"
EMPTY_PAYLOAD_SHA256 = hashlib.sha256(b"").hexdigest()

EXPECTED_DATASETS = (
    ("node_fills_by_block", "hl-mainnet-node-data", "node_fills_by_block/"),
    ("node_fills_legacy", "hl-mainnet-node-data", "node_fills/"),
    ("node_trades_legacy", "hl-mainnet-node-data", "node_trades/"),
    ("explorer_blocks", "hl-mainnet-node-data", "explorer_blocks/"),
    ("replica_cmds", "hl-mainnet-node-data", "replica_cmds/"),
    ("market_data", "hyperliquid-archive", "market_data/"),
    ("asset_ctxs", "hyperliquid-archive", "asset_ctxs/"),
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


class R0ContractError(RuntimeError):
    pass


class R0TransportError(RuntimeError):
    pass


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise R0ContractError("json root must be object")
    return value


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def signing_now() -> datetime:
    return datetime.now(timezone.utc)


def validate_static_inputs() -> list[dict]:
    approval_raw = APPROVAL_TEXT.read_bytes()
    approval = load_json(APPROVAL_JSON)
    contract = load_json(R0_CONTRACT)
    implementation = load_json(IMPLEMENTATION_CONTRACT)
    register = load_json(DATASET_REGISTER)

    if sha256_bytes(approval_raw) != APPROVAL_TEXT_SHA256:
        raise R0ContractError("approval text hash drift")
    if approval.get("approval_id") != APPROVAL_ID:
        raise R0ContractError("approval id drift")
    if approval.get("reviewed_commit") != APPROVAL_COMMIT:
        raise R0ContractError("approval commit drift")
    if approval.get("exact_approval_text_sha256") != APPROVAL_TEXT_SHA256:
        raise R0ContractError("approval record hash drift")
    if approval.get("approval_status") != "APPROVED_SCOPE_AND_BUDGET_AWAITING_IMPLEMENTATION":
        raise R0ContractError("approval status drift")
    if approval.get("maximum_one_time_budget_eur") != 1.0 or approval.get("maximum_monthly_budget_eur") != 0:
        raise R0ContractError("approval budget drift")
    if approval.get("maximum_list_requests") != MAX_REQUESTS:
        raise R0ContractError("approval request cap drift")
    if approval.get("maximum_keys_per_request") != MAX_KEYS:
        raise R0ContractError("approval max keys drift")
    if approval.get("maximum_total_entries") != MAX_ENTRIES:
        raise R0ContractError("approval entry cap drift")
    if approval.get("maximum_total_response_bytes") != MAX_RESPONSE_BYTES:
        raise R0ContractError("approval response-byte cap drift")
    if approval.get("maximum_runtime_seconds") != MAX_RUNTIME_SECONDS:
        raise R0ContractError("approval runtime cap drift")
    if approval.get("maximum_retries_per_request") != 0 or approval.get("pagination_authorized") is not False:
        raise R0ContractError("approval retry/pagination drift")
    if approval.get("requester_pays_scope_approved") is not True or approval.get("list_objects_v2_scope_approved") is not True:
        raise R0ContractError("approval list scope not approved")
    if not all(approval.get("forbidden_capabilities", {}).values()):
        raise R0ContractError("approval forbidden capability drift")

    if contract.get("canary_id") != CANARY_ID or contract.get("operation") != "ListObjectsV2":
        raise R0ContractError("R0 contract identity drift")
    if contract.get("request_payer") != "requester":
        raise R0ContractError("R0 request payer drift")
    if contract.get("dataset_family_count") != MAX_REQUESTS:
        raise R0ContractError("R0 family count drift")
    if contract.get("max_keys_per_request") != MAX_KEYS:
        raise R0ContractError("R0 contract max keys drift")
    if contract.get("max_total_list_requests") != MAX_REQUESTS:
        raise R0ContractError("R0 contract request cap drift")
    if contract.get("max_total_entries") != MAX_ENTRIES:
        raise R0ContractError("R0 contract entry cap drift")
    if contract.get("max_total_response_bytes") != MAX_RESPONSE_BYTES:
        raise R0ContractError("R0 contract response-byte cap drift")
    if contract.get("max_runtime_seconds") != MAX_RUNTIME_SECONDS:
        raise R0ContractError("R0 contract runtime drift")
    if contract.get("max_retries_per_request") != 0:
        raise R0ContractError("R0 retries opened")
    if contract.get("pagination_allowed") is not False or contract.get("continuation_token_follow_allowed") is not False:
        raise R0ContractError("R0 pagination opened")

    if implementation.get("canary_id") != CANARY_ID:
        raise R0ContractError("implementation canary drift")
    if implementation.get("human_approval_text_sha256") != APPROVAL_TEXT_SHA256:
        raise R0ContractError("implementation approval binding drift")
    if implementation.get("maximum_list_requests") != MAX_REQUESTS:
        raise R0ContractError("implementation request cap drift")
    if implementation.get("maximum_keys_per_request") != MAX_KEYS:
        raise R0ContractError("implementation max keys drift")
    if implementation.get("s3_http_request_cap") != MAX_REQUESTS:
        raise R0ContractError("implementation HTTP request cap drift")
    if implementation.get("s3_transport") != "DIRECT_SIGV4_HTTPS_NO_REDIRECT_FOLLOW":
        raise R0ContractError("implementation transport drift")
    if implementation.get("http_redirect_following_authorized") is not False:
        raise R0ContractError("implementation redirect following opened")
    if implementation.get("maximum_retries_per_request") != 0:
        raise R0ContractError("implementation retry setting drift")
    if implementation.get("pagination_authorized") is not False:
        raise R0ContractError("implementation pagination opened")
    if implementation.get("market_data_ingestion_authorized") is not False:
        raise R0ContractError("implementation market-data gate opened")
    if not all(value is False for value in implementation.get("authorizations", {}).values()):
        raise R0ContractError("implementation trading authorization opened")

    rows = register.get("datasets")
    if not isinstance(rows, list) or len(rows) != MAX_REQUESTS:
        raise R0ContractError("dataset register count drift")
    observed = [(row.get("family"), row.get("bucket"), row.get("prefix")) for row in rows]
    if tuple(observed) != EXPECTED_DATASETS:
        raise R0ContractError("dataset order/scope drift")
    return rows


def _aws_quote(value: str) -> str:
    return urllib.parse.quote(value, safe="-_.~")


def canonical_query(prefix: str) -> str:
    params = (("list-type", "2"), ("max-keys", str(MAX_KEYS)), ("prefix", prefix))
    return "&".join(f"{_aws_quote(key)}={_aws_quote(value)}" for key, value in sorted(params))


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def build_signed_request(bucket: str, prefix: str, request_time: datetime, env: dict[str, str] | None = None) -> tuple[str, str, dict[str, str]]:
    allowed = {(bucket_name, prefix_name) for _, bucket_name, prefix_name in EXPECTED_DATASETS}
    if (bucket, prefix) not in allowed:
        raise R0ContractError("unregistered bucket/prefix")
    source = os.environ if env is None else env
    access_key = source.get("AWS_ACCESS_KEY_ID")
    secret_key = source.get("AWS_SECRET_ACCESS_KEY")
    session_token = source.get("AWS_SESSION_TOKEN")
    if not access_key or not secret_key or not session_token:
        raise R0ContractError("temporary AWS credentials missing")
    if request_time.tzinfo is None:
        raise R0ContractError("signing time must be timezone-aware")
    stamp = request_time.astimezone(timezone.utc)
    amz_date = stamp.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = stamp.strftime("%Y%m%d")
    host = f"{bucket}.s3.amazonaws.com"
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
        raise R0ContractError("negative response-byte allowance")
    host, target, headers = build_signed_request(bucket, prefix, request_time or signing_now())
    connection = http.client.HTTPSConnection(host, timeout=timeout_seconds, context=ssl.create_default_context())
    try:
        connection.request("GET", target, body=None, headers=headers)
        response = connection.getresponse()
        normalized_headers = {key.lower(): value for key, value in response.getheaders()}
        body = response.read(maximum_body_bytes + 1)
        return response.status, normalized_headers, body
    except (OSError, http.client.HTTPException, ssl.SSLError) as exc:
        raise R0TransportError(type(exc).__name__) from exc
    finally:
        connection.close()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in list(element) if _local_name(child.tag) == name]


def _child_text(element: ET.Element, name: str, required: bool = True) -> str | None:
    matches = _children(element, name)
    if len(matches) > 1:
        raise R0ContractError(f"duplicate XML field: {name}")
    if not matches:
        if required:
            raise R0ContractError(f"missing XML field: {name}")
        return None
    return matches[0].text or ""


def parse_success_xml(body: bytes, family: str, bucket: str, prefix: str, request_index: int, headers: dict[str, str], observed_at: str) -> tuple[dict, int]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise R0ContractError("invalid success XML") from exc
    if _local_name(root.tag) != "ListBucketResult":
        raise R0ContractError("unexpected success XML root")
    if _child_text(root, "Name") != bucket:
        raise R0ContractError("response bucket mismatch")
    if _child_text(root, "Prefix") != prefix:
        raise R0ContractError("response prefix mismatch")
    try:
        max_keys = int(_child_text(root, "MaxKeys") or "")
        key_count = int(_child_text(root, "KeyCount") or "")
    except ValueError as exc:
        raise R0ContractError("invalid numeric response field") from exc
    if max_keys != MAX_KEYS:
        raise R0ContractError("response MaxKeys mismatch")
    if not 0 <= key_count <= MAX_KEYS:
        raise R0ContractError("response KeyCount invalid")
    truncated_text = (_child_text(root, "IsTruncated") or "").lower()
    if truncated_text not in {"true", "false"}:
        raise R0ContractError("response IsTruncated invalid")
    contents = _children(root, "Contents")
    if len(contents) != key_count or len(contents) > MAX_KEYS:
        raise R0ContractError("KeyCount/Contents mismatch")
    if headers.get("x-amz-request-charged") != "requester":
        raise R0ContractError("successful Requester Pays response missing request-charged header")

    entries: list[dict] = []
    for item in contents:
        key = _child_text(item, "Key")
        if not isinstance(key, str) or not key.startswith(prefix):
            raise R0ContractError("object key escaped prefix")
        try:
            size = int(_child_text(item, "Size") or "")
        except ValueError as exc:
            raise R0ContractError("object size invalid") from exc
        if size < 0:
            raise R0ContractError("object size invalid")
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
    except (ET.ParseError, R0ContractError):
        code = None
    if code in KNOWN_S3_ERROR_CODES:
        return f"S3_{code}"
    if 300 <= status < 400:
        return f"HTTP_{status}_REDIRECT_NOT_FOLLOWED"
    return f"HTTP_{status}"


def failure_observation(family: str, bucket: str, prefix: str, request_index: int, status_class: str, response_bytes: int, observed_at: str) -> dict:
    return {
        "dataset_family_id": family,
        "bucket": bucket,
        "prefix": prefix,
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
        family = row["family"]
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
                        bucket,
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
                        bucket,
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
        except R0TransportError as exc:
            observations.append(
                failure_observation(
                    family,
                    bucket,
                    prefix,
                    request_attempt_count,
                    f"HTTPS_TRANSPORT_{str(exc)}",
                    0,
                    observed_at,
                )
            )
        except R0ContractError:
            observations.append(
                failure_observation(
                    family,
                    bucket,
                    prefix,
                    request_attempt_count,
                    "INVALID_SUCCESS_RESPONSE",
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
        "terminal_status": "R0_METADATA_CANARY_PASS" if passed else "R0_METADATA_CANARY_FAIL",
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
        "signing_region_initial": SIGNING_REGION,
        "requester_pays_requested": True,
        "continuation_token_values_retained": False,
        "object_body_requested": False,
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
        "terminal_status": "R0_PRE_NETWORK_CONTRACT_FAIL",
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
        "signing_region_initial": SIGNING_REGION,
        "requester_pays_requested": False,
        "continuation_token_values_retained": False,
        "object_body_requested": False,
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
    except R0ContractError:
        write_pre_network_failure(output_path)
        return 0
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
