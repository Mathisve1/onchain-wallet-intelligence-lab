from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import hmac
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Final

from .pricing import BudgetGuard
from .runtime import ExecutionEvidenceState, RuntimeGuard, RuntimeTarget
from .storage import ReservedBinaryWriter, WorkspaceMeter

_REGION: Final[str] = "ap-northeast-1"
_SERVICE: Final[str] = "s3"
_BUCKET: Final[str] = "hl-mainnet-node-data"
_CHUNK_BYTES: Final[int] = 1 << 20


class TransportError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True, slots=True)
class AWSCredentials:
    access_key_id: str
    secret_access_key: str
    session_token: str

    @classmethod
    def from_environment(cls) -> "AWSCredentials":
        values = {
            "access_key_id": os.environ.get("AWS_ACCESS_KEY_ID", ""),
            "secret_access_key": os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
            "session_token": os.environ.get("AWS_SESSION_TOKEN", ""),
        }
        if not all(values.values()):
            raise TransportError("temporary AWS credentials are incomplete")
        return cls(**values)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def _canonical_uri(object_key: str) -> str:
    if not object_key or object_key.startswith("/") or ".." in object_key.split("/"):
        raise TransportError("unsafe object key")
    return "/" + "/".join(
        urllib.parse.quote(segment, safe="-_.~") for segment in object_key.split("/")
    )


def build_signed_request(
    target: RuntimeTarget,
    credentials: AWSCredentials,
    *,
    now: dt.datetime | None = None,
) -> urllib.request.Request:
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None:
        raise TransportError("SigV4 time must be timezone aware")
    current = current.astimezone(dt.timezone.utc)
    amz_date = current.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = current.strftime("%Y%m%d")
    host = f"{_BUCKET}.s3.{_REGION}.amazonaws.com"
    canonical_uri = _canonical_uri(target.object_key)
    headers = {
        "host": host,
        "if-match": target.expected_etag,
        "x-amz-content-sha256": "UNSIGNED-PAYLOAD",
        "x-amz-date": amz_date,
        "x-amz-request-payer": "requester",
        "x-amz-security-token": credentials.session_token,
    }
    signed_header_names = ";".join(sorted(headers))
    canonical_headers = "".join(f"{name}:{headers[name].strip()}\n" for name in sorted(headers))
    canonical_request = "\n".join(
        [
            "GET",
            canonical_uri,
            "",
            canonical_headers,
            signed_header_names,
            "UNSIGNED-PAYLOAD",
        ]
    )
    scope = f"{date_stamp}/{_REGION}/{_SERVICE}/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    date_key = _sign(("AWS4" + credentials.secret_access_key).encode("utf-8"), date_stamp)
    region_key = _sign(date_key, _REGION)
    service_key = _sign(region_key, _SERVICE)
    signing_key = _sign(service_key, "aws4_request")
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = (
        "AWS4-HMAC-SHA256 "
        f"Credential={credentials.access_key_id}/{scope},"
        f"SignedHeaders={signed_header_names},Signature={signature}"
    )
    request_headers = {name: value for name, value in headers.items() if name != "host"}
    request_headers["Authorization"] = authorization
    return urllib.request.Request(
        f"https://{host}{canonical_uri}",
        method="GET",
        headers=request_headers,
    )


def _header(response, name: str) -> str | None:  # type: ignore[no-untyped-def]
    value = response.headers.get(name)
    return None if value is None else value.strip()


def _parse_content_length(value: str | None) -> int | None:
    if value is None or re.fullmatch(r"0|[1-9][0-9]*", value) is None:
        return None
    return int(value, 10)


def download_exact_object(
    *,
    target: RuntimeTarget,
    destination: Path,
    credentials: AWSCredentials,
    state: ExecutionEvidenceState,
    meter: WorkspaceMeter,
    runtime_guard: RuntimeGuard,
    budget_guard: BudgetGuard,
    opener: urllib.request.OpenerDirector | None = None,
) -> Path:
    budget_guard.authorize_request(
        request_ordinal_zero_based=state.network_request_count,
        expected_response_bytes=target.expected_size_bytes,
    )
    writer = ReservedBinaryWriter(
        destination,
        meter,
        maximum_bytes=target.expected_size_bytes,
        label=f"compressed object {target.object_ordinal_zero_based}",
    )
    state.request_sent(target.object_ordinal_zero_based)
    request = build_signed_request(target, credentials)
    client = opener or urllib.request.build_opener(_NoRedirect())
    try:
        runtime_guard.check_scientific_phase("before exact S3 GetObject")
        response = client.open(request, timeout=120)
        status = int(getattr(response, "status", response.getcode()))
        response_etag = _header(response, "ETag")
        content_length = _parse_content_length(_header(response, "Content-Length"))
        requester_charged = _header(response, "x-amz-request-charged")
        state.response_metadata(
            target.object_ordinal_zero_based,
            http_status=status,
            etag=response_etag,
            content_length=content_length,
            requester_charged=requester_charged,
        )
        # Every transport and identity field is validated before body.read().
        if status != 200:
            raise TransportError(f"unexpected S3 HTTP status: {status}")
        if response_etag != target.expected_etag:
            raise TransportError("response ETag differs from frozen object identity")
        if content_length != target.expected_size_bytes:
            raise TransportError("response Content-Length differs from frozen size")
        if requester_charged != "requester":
            raise TransportError("successful Requester Pays response lacks requester charge proof")

        digest = hashlib.sha256()
        received = 0
        while True:
            runtime_guard.check_scientific_phase("stream exact S3 object body")
            chunk = response.read(_CHUNK_BYTES)
            if not chunk:
                break
            received += len(chunk)
            if received > target.expected_size_bytes:
                raise TransportError("response body exceeds verified Content-Length")
            writer.write(chunk)
            digest.update(chunk)
            state.body_progress(target.object_ordinal_zero_based, received)
        if received != target.expected_size_bytes:
            raise TransportError("response body ended before verified Content-Length")
        observed_sha = digest.hexdigest()
        if observed_sha != target.expected_compressed_sha256:
            raise TransportError("downloaded compressed SHA-256 mismatch")
        state.body_complete(target.object_ordinal_zero_based, observed_sha)
        writer.close()
        return destination
    except Exception as exc:
        try:
            writer.abort()
        except Exception as cleanup_exc:
            raise TransportError("transport failure and partial-file cleanup failure") from cleanup_exc
        if isinstance(exc, TransportError):
            raise
        if isinstance(exc, urllib.error.HTTPError):
            raise TransportError(f"S3 HTTP failure without retry: {exc.code}") from exc
        if isinstance(exc, urllib.error.URLError):
            raise TransportError("S3 transport failure without retry") from exc
        raise TransportError("unexpected exact-object transport failure") from exc
