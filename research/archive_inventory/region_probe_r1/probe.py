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
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[3]
PROBE_ROOT = ROOT / "research/archive_inventory/region_probe_r1"
PREREGISTRATION = PROBE_ROOT / "REGION_PROBE_CONTRACT.json"
APPROVAL_TEXT = PROBE_ROOT / "approvals/APPROVE_HL_ARCHIVE_REGION_PROBE_R1_001.txt"
APPROVAL_JSON = PROBE_ROOT / "approvals/APPROVE_HL_ARCHIVE_REGION_PROBE_R1_001.json"
IMPLEMENTATION_CONTRACT = PROBE_ROOT / "REGION_PROBE_IMPLEMENTATION_CONTRACT.json"

PROBE_ID = "HL-ARCHIVE-REGION-PROBE-R1-001"
APPROVAL_ID = "APPROVE_HL_ARCHIVE_REGION_PROBE_R1_001"
APPROVAL_COMMIT = "910997423f5e008f3c7bca65fd739d6aa14d25a7"
APPROVAL_TEXT_SHA256 = "56c8d01396b12d0dd783dbc1646ebbca947e51a024bb5c8f091cd0b7a889c541"
TARGET_BUCKET = "hl-mainnet-node-data"
HOST = f"{TARGET_BUCKET}.s3.amazonaws.com"
SIGNING_REGION = "us-east-1"
SERVICE = "s3"
MAX_REQUESTS = 1
MAX_RUNTIME_SECONDS = 30
REGION_RE = re.compile(r"^[a-z0-9-]{1,20}$")
EMPTY_PAYLOAD_SHA256 = hashlib.sha256(b"").hexdigest()


class RegionProbeContractError(RuntimeError):
    pass


class RegionProbeTransportError(RuntimeError):
    pass


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RegionProbeContractError(f"json root must be object: {path}")
    return value


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def signing_now() -> datetime:
    return datetime.now(timezone.utc)


def validate_static_inputs() -> None:
    prereg = _load_json(PREREGISTRATION)
    approval = _load_json(APPROVAL_JSON)
    implementation = _load_json(IMPLEMENTATION_CONTRACT)

    if prereg.get("probe_id") != PROBE_ID or prereg.get("status") != "PREREGISTERED_NOT_AUTHORIZED":
        raise RegionProbeContractError("preregistration identity/status drift")
    if prereg.get("target_bucket") != TARGET_BUCKET or prereg.get("operation") != "HeadBucket":
        raise RegionProbeContractError("preregistration target/operation drift")
    if prereg.get("http_method") != "HEAD" or prereg.get("request_path") != "/":
        raise RegionProbeContractError("preregistration HTTP shape drift")
    if prereg.get("maximum_s3_http_requests") != MAX_REQUESTS:
        raise RegionProbeContractError("preregistration request cap drift")
    if prereg.get("maximum_runtime_seconds") != MAX_RUNTIME_SECONDS or prereg.get("maximum_retries") != 0:
        raise RegionProbeContractError("preregistration runtime/retry drift")
    if prereg.get("http_redirect_following_authorized") is not False:
        raise RegionProbeContractError("redirect following opened")
    if prereg.get("request_body_authorized") is not False or prereg.get("response_body_authorized") is not False:
        raise RegionProbeContractError("body access opened")
    for key in (
        "list_objects_v2_authorized",
        "get_object_authorized",
        "head_object_authorized",
        "get_object_attributes_authorized",
        "range_get_authorized",
        "object_body_download_authorized",
        "pagination_authorized",
        "decompression_authorized",
        "market_data_ingestion_authorized",
        "larger_300_request_inventory_authorized",
    ):
        if prereg.get(key) is not False:
            raise RegionProbeContractError(f"forbidden preregistration capability opened: {key}")

    if _sha256_bytes(APPROVAL_TEXT.read_bytes()) != APPROVAL_TEXT_SHA256:
        raise RegionProbeContractError("approval text hash drift")
    if approval.get("approval_id") != APPROVAL_ID:
        raise RegionProbeContractError("approval ID drift")
    if approval.get("reviewed_commit") != APPROVAL_COMMIT:
        raise RegionProbeContractError("approval reviewed commit drift")
    if approval.get("exact_approval_text_sha256") != APPROVAL_TEXT_SHA256:
        raise RegionProbeContractError("approval hash binding drift")
    if approval.get("approval_status") != "APPROVED_SCOPE_AND_BUDGET_AWAITING_IMPLEMENTATION":
        raise RegionProbeContractError("approval status drift")
    if approval.get("maximum_one_time_budget_eur") != 0.10 or approval.get("maximum_monthly_budget_eur") != 0:
        raise RegionProbeContractError("approval budget drift")
    if approval.get("maximum_head_bucket_requests") != MAX_REQUESTS:
        raise RegionProbeContractError("approval request cap drift")
    if approval.get("maximum_runtime_seconds") != MAX_RUNTIME_SECONDS or approval.get("maximum_retries") != 0:
        raise RegionProbeContractError("approval runtime/retry drift")
    if approval.get("http_redirect_following_authorized") is not False:
        raise RegionProbeContractError("approval redirect drift")
    if approval.get("target_bucket") != TARGET_BUCKET:
        raise RegionProbeContractError("approval target drift")
    if approval.get("head_bucket_scope_approved") is not True:
        raise RegionProbeContractError("HeadBucket scope not approved")
    if approval.get("requester_pays_acknowledgement_scope_approved") is not True:
        raise RegionProbeContractError("Requester Pays acknowledgement not approved")
    for key in (
        "list_objects_v2_authorized",
        "get_object_authorized",
        "head_object_authorized",
        "object_body_download_authorized",
        "market_data_ingestion_authorized",
        "larger_300_request_inventory_authorized",
        "execution_authorized",
        "fresh_paid_attempt_authorized",
    ):
        if approval.get(key) is not False:
            raise RegionProbeContractError(f"approval opened forbidden capability: {key}")

    if implementation.get("probe_id") != PROBE_ID:
        raise RegionProbeContractError("implementation probe ID drift")
    if implementation.get("status") != "IMPLEMENTATION_CANDIDATE_REQUIRES_SEPARATE_EXECUTION_RELEASE":
        raise RegionProbeContractError("implementation status drift")
    if implementation.get("preregistration_commit") != APPROVAL_COMMIT:
        raise RegionProbeContractError("implementation preregistration binding drift")
    if implementation.get("approval_text_sha256") != APPROVAL_TEXT_SHA256:
        raise RegionProbeContractError("implementation approval hash drift")
    if implementation.get("target_bucket") != TARGET_BUCKET or implementation.get("operation") != "HeadBucket":
        raise RegionProbeContractError("implementation target/operation drift")
    if implementation.get("maximum_s3_http_requests") != MAX_REQUESTS:
        raise RegionProbeContractError("implementation request cap drift")
    if implementation.get("maximum_runtime_seconds") != MAX_RUNTIME_SECONDS or implementation.get("maximum_retries") != 0:
        raise RegionProbeContractError("implementation runtime/retry drift")
    if implementation.get("transport") != "DIRECT_SIGV4_HTTPS_HEAD_NO_REDIRECT_NO_BODY":
        raise RegionProbeContractError("implementation transport drift")
    if implementation.get("session_s3_policy") != "EXPLICIT_DENY_ALL_S3":
        raise RegionProbeContractError("implementation session-policy drift")
    if implementation.get("separate_execution_release_required") is not True:
        raise RegionProbeContractError("separate execution release disabled")
    if implementation.get("implementation_self_releases_execution") is not False:
        raise RegionProbeContractError("implementation self-releases execution")
    if implementation.get("execution_authorized") is not False:
        raise RegionProbeContractError("implementation execution opened")


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def build_signed_head_request(
    request_time: datetime,
    env: dict[str, str] | None = None,
) -> tuple[str, str, dict[str, str]]:
    source = os.environ if env is None else env
    access_key = source.get("AWS_ACCESS_KEY_ID")
    secret_key = source.get("AWS_SECRET_ACCESS_KEY")
    session_token = source.get("AWS_SESSION_TOKEN")
    if not access_key or not secret_key or not session_token:
        raise RegionProbeContractError("temporary AWS credentials missing")
    if request_time.tzinfo is None:
        raise RegionProbeContractError("signing time must be timezone-aware")

    stamp = request_time.astimezone(timezone.utc)
    amz_date = stamp.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = stamp.strftime("%Y%m%d")
    canonical_headers = (
        f"host:{HOST}\n"
        f"x-amz-content-sha256:{EMPTY_PAYLOAD_SHA256}\n"
        f"x-amz-date:{amz_date}\n"
        "x-amz-request-payer:requester\n"
        f"x-amz-security-token:{session_token}\n"
    )
    signed_headers = "host;x-amz-content-sha256;x-amz-date;x-amz-request-payer;x-amz-security-token"
    canonical_request = "\n".join(
        ["HEAD", "/", "", canonical_headers, signed_headers, EMPTY_PAYLOAD_SHA256]
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
        "Host": HOST,
        "Authorization": authorization,
        "x-amz-content-sha256": EMPTY_PAYLOAD_SHA256,
        "x-amz-date": amz_date,
        "x-amz-request-payer": "requester",
        "x-amz-security-token": session_token,
    }
    return HOST, "/", headers


def perform_single_head_request(
    timeout_seconds: float,
    request_time: datetime | None = None,
) -> tuple[int, str | None, str | None]:
    host, target, headers = build_signed_head_request(request_time or signing_now())
    connection = http.client.HTTPSConnection(host, timeout=timeout_seconds, context=ssl.create_default_context())
    try:
        connection.request("HEAD", target, body=None, headers=headers)
        response = connection.getresponse()
        region: str | None = None
        charged: str | None = None
        for key, value in response.getheaders():
            lower = key.lower()
            if lower == "x-amz-bucket-region":
                region = value.strip()
            elif lower == "x-amz-request-charged":
                charged = value.strip()
        return response.status, region, charged
    except (OSError, http.client.HTTPException, ssl.SSLError) as exc:
        raise RegionProbeTransportError(type(exc).__name__) from exc
    finally:
        connection.close()


def _status_class(status: int | None) -> str | None:
    if status is None:
        return None
    return f"{status // 100}xx"


def run_probe(
    output_path: Path,
    transport: Callable[[float, datetime | None], tuple[int, str | None, str | None]] = perform_single_head_request,
) -> int:
    validate_static_inputs()
    started = time.monotonic()
    observed_at = utc_now()
    result: dict = {
        "schema_version": "1.0",
        "probe_id": PROBE_ID,
        "target_bucket": TARGET_BUCKET,
        "terminal_status": "REGION_PROBE_R1_FAIL",
        "request_attempt_count": 1,
        "s3_http_request_count": 1,
        "http_method": "HEAD",
        "http_status": None,
        "http_status_class": None,
        "x_amz_bucket_region": None,
        "x_amz_request_charged": None,
        "observed_at_utc": observed_at,
        "runtime_seconds": None,
        "retries_used": 0,
        "http_redirects_followed": False,
        "requester_pays_requested": True,
        "request_body_requested": False,
        "response_body_read": False,
        "list_objects_v2_requested": False,
        "object_body_requested": False,
        "market_data_ingested": False,
        "empirical_result": None,
        "technical_result": None,
        "failure_class": None,
    }
    try:
        status, region, charged = transport(float(MAX_RUNTIME_SECONDS), None)
        result["http_status"] = int(status)
        result["http_status_class"] = _status_class(int(status))
        result["x_amz_request_charged"] = charged if charged in {None, "requester"} else None
        if not isinstance(region, str) or not REGION_RE.fullmatch(region):
            result["failure_class"] = "MISSING_OR_INVALID_BUCKET_REGION_HEADER"
        else:
            result["x_amz_bucket_region"] = region
            result["technical_result"] = "BUCKET_REGION_OBSERVED"
            result["terminal_status"] = "REGION_PROBE_R1_PASS"
    except RegionProbeTransportError as exc:
        result["failure_class"] = f"TRANSPORT_{exc}"
    finally:
        result["runtime_seconds"] = round(time.monotonic() - started, 6)
        output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if result["terminal_status"] == "REGION_PROBE_R1_PASS" else 1


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        raise SystemExit("usage: probe.py OUTPUT_JSON")
    return run_probe(Path(args[0]))


if __name__ == "__main__":
    raise SystemExit(main())
