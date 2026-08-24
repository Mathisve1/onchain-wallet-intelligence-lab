from __future__ import annotations

import argparse
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

from .canonical import FrozenObject, NumberToken, strict_json_loads
from .pricing import BudgetGuard
from .runtime import ExecutionEvidenceState, RuntimeGuard, RuntimeTarget
from .storage_r7 import (
    CleanupBoundaryError,
    ReservedBinaryWriter,
    WorkspaceMeter,
)

_REGION = "ap-northeast-1"
_SERVICE = "s3"
_BUCKET = "hl-mainnet-node-data"
_CHUNK_BYTES = 1 << 20
_GITHUB_RESPONSE_CAP = 1 << 20
_FATAL_CLEANUP_EXIT_CODE = 70


class TransportBoundaryError(RuntimeError):
    pass


class TransportCleanupError(TransportBoundaryError, CleanupBoundaryError):
    """A transport resource cleanup failure is fatal to terminal recovery."""


@dataclasses.dataclass(frozen=True, slots=True)
class AWSCredentials:
    access_key_id: str
    secret_access_key: str
    session_token: str

    @classmethod
    def from_environment(cls) -> "AWSCredentials":
        values = (
            os.environ.get("AWS_ACCESS_KEY_ID", ""),
            os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
            os.environ.get("AWS_SESSION_TOKEN", ""),
        )
        if not all(values):
            raise TransportBoundaryError("temporary AWS credentials are incomplete")
        return cls(*values)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def _opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_NoRedirect())


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def _canonical_uri(object_key: str) -> str:
    if not object_key or object_key.startswith("/") or ".." in object_key.split("/"):
        raise TransportBoundaryError("unsafe object key")
    return "/" + "/".join(
        urllib.parse.quote(segment, safe="-_.~") for segment in object_key.split("/")
    )


def build_signed_request(
    target: RuntimeTarget,
    credentials: AWSCredentials,
    *,
    now: dt.datetime | None = None,
) -> urllib.request.Request:
    current = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    amz_date = current.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = current.strftime("%Y%m%d")
    host = f"{_BUCKET}.s3.{_REGION}.amazonaws.com"
    uri = _canonical_uri(target.object_key)
    headers = {
        "host": host,
        "if-match": target.expected_etag,
        "x-amz-content-sha256": "UNSIGNED-PAYLOAD",
        "x-amz-date": amz_date,
        "x-amz-request-payer": "requester",
        "x-amz-security-token": credentials.session_token,
    }
    signed_names = ";".join(sorted(headers))
    canonical_headers = "".join(f"{name}:{headers[name].strip()}\n" for name in sorted(headers))
    canonical_request = "\n".join(
        ["GET", uri, "", canonical_headers, signed_names, "UNSIGNED-PAYLOAD"]
    )
    scope = f"{date_stamp}/{_REGION}/{_SERVICE}/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        ]
    )
    date_key = _sign(("AWS4" + credentials.secret_access_key).encode(), date_stamp)
    region_key = _sign(date_key, _REGION)
    service_key = _sign(region_key, _SERVICE)
    signing_key = _sign(service_key, "aws4_request")
    signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
    authorization = (
        "AWS4-HMAC-SHA256 "
        f"Credential={credentials.access_key_id}/{scope},"
        f"SignedHeaders={signed_names},Signature={signature}"
    )
    request_headers = {name: value for name, value in headers.items() if name != "host"}
    request_headers["Authorization"] = authorization
    return urllib.request.Request(
        f"https://{host}{uri}",
        method="GET",
        headers=request_headers,
    )


def _header(response, name: str) -> str | None:  # type: ignore[no-untyped-def]
    value = response.headers.get(name)
    return None if value is None else value.strip()


def _content_length(value: str | None) -> int | None:
    if value is None or re.fullmatch(r"0|[1-9][0-9]*", value) is None:
        return None
    return int(value)


def _append_transport_owner(owners: list[object], owner: object | None) -> None:
    if owner is not None and all(owner is not current for current in owners):
        owners.append(owner)


def _close_transport_owners(
    owners: list[object],
) -> list[BaseException]:
    errors: list[BaseException] = []
    for owner in reversed(owners):
        try:
            owner.close()  # type: ignore[attr-defined]
        except BaseException as exc:
            errors.append(exc)
    return errors


def _raise_transport_cleanup(
    errors: list[BaseException],
    *,
    label: str,
    original_failure: BaseException | None,
) -> None:
    if not errors:
        return
    tail = original_failure
    for error in reversed(errors):
        if tail is not None and error is not tail and error.__context__ is None:
            error.__context__ = tail
        tail = error
    failure = TransportCleanupError(f"{label} cleanup failed")
    if original_failure is not None:
        # Keep the processing failure independently reachable even when a
        # cleanup implementation arrived with its own cause/context chain.
        failure.__context__ = original_failure
    raise failure from errors[0]


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
    response = None
    response_owners: list[object] = []
    failure: BaseException | None = None
    try:
        state.request_sent(target.object_ordinal_zero_based)
        request = build_signed_request(target, credentials)
        client = opener or _opener()
        runtime_guard.check_scientific_phase("before exact S3 GetObject")
        response = client.open(request, timeout=120)
        _append_transport_owner(response_owners, response)
        status = int(getattr(response, "status", response.getcode()))
        etag = _header(response, "ETag")
        length = _content_length(_header(response, "Content-Length"))
        charged = _header(response, "x-amz-request-charged")
        state.response_metadata(
            target.object_ordinal_zero_based,
            http_status=status,
            etag=etag,
            content_length=length,
            requester_charged=charged,
        )
        if status != 200:
            raise TransportBoundaryError(f"unexpected S3 status: {status}")
        if etag != target.expected_etag:
            raise TransportBoundaryError("response ETag differs from frozen identity")
        if length != target.expected_size_bytes:
            raise TransportBoundaryError("response Content-Length differs from frozen size")
        if charged != "requester":
            raise TransportBoundaryError("Requester Pays response proof missing")
        digest = hashlib.sha256()
        received = 0
        while True:
            runtime_guard.check_scientific_phase("stream exact S3 body")
            chunk = response.read(_CHUNK_BYTES)
            if not chunk:
                break
            received += len(chunk)
            if received > target.expected_size_bytes:
                raise TransportBoundaryError("body exceeds verified Content-Length")
            writer.write(chunk)
            digest.update(chunk)
            state.body_progress(target.object_ordinal_zero_based, received)
        if received != target.expected_size_bytes:
            raise TransportBoundaryError("body ended before verified Content-Length")
        observed = digest.hexdigest()
        if observed != target.expected_compressed_sha256:
            raise TransportBoundaryError("compressed SHA-256 mismatch")
        state.body_complete(target.object_ordinal_zero_based, observed)
        writer.close()
    except BaseException as exc:
        if isinstance(exc, urllib.error.HTTPError):
            _append_transport_owner(response_owners, exc)
        failure = exc

    cleanup_errors: list[BaseException] = []
    cleanup_errors.extend(_close_transport_owners(response_owners))
    if failure is not None:
        try:
            writer.abort()
        except BaseException as exc:
            cleanup_errors.append(exc)
    _raise_transport_cleanup(
        cleanup_errors,
        label="S3 transport",
        original_failure=failure,
    )
    if failure is not None:
        if isinstance(failure, CleanupBoundaryError):
            raise failure
        if isinstance(failure, TransportBoundaryError):
            raise failure
        if isinstance(failure, urllib.error.HTTPError):
            raise TransportBoundaryError(
                f"S3 HTTP failure without retry: {failure.code}"
            ) from failure
        if isinstance(failure, urllib.error.URLError):
            raise TransportBoundaryError(
                "S3 transport failure without retry"
            ) from failure
        if not isinstance(failure, Exception):
            raise failure
        raise TransportBoundaryError("unexpected S3 transport failure") from failure
    return destination


def _object(value: object, label: str) -> FrozenObject:
    if not isinstance(value, FrozenObject):
        raise TransportBoundaryError(f"{label} must be object")
    return value


def _integer(value: object, label: str) -> int:
    if isinstance(value, NumberToken) and value.is_integer_token:
        return int(value.token)
    raise TransportBoundaryError(f"{label} must be exact integer")


def validate_single_use_history(
    *,
    repository: str,
    workflow_file: str,
    current_run_id: int,
    current_run_attempt: int,
    single_use_window_start_utc: str,
    token: str,
    opener: urllib.request.OpenerDirector | None = None,
) -> None:
    if repository != "Mathisve1/onchain-wallet-intelligence-lab":
        raise TransportBoundaryError("repository identity drift")
    if workflow_file != "hyperliquid-archive-r11a-identity-boundary-diagnostic.yml":
        raise TransportBoundaryError("workflow history target drift")
    if current_run_id <= 0 or current_run_attempt != 1:
        raise TransportBoundaryError("R11A history gate requires attempt one")
    try:
        start = dt.datetime.fromisoformat(single_use_window_start_utc.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TransportBoundaryError("single-use window timestamp malformed") from exc
    query = urllib.parse.urlencode(
        {"event": "workflow_dispatch", "branch": "main", "per_page": "100"}
    )
    url = (
        f"https://api.github.com/repos/{repository}/actions/workflows/"
        f"{workflow_file}/runs?{query}"
    )
    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "r11a-single-use-history-gate",
        },
    )
    response = None
    response_owners: list[object] = []
    failure: BaseException | None = None
    try:
        response = (opener or _opener()).open(request, timeout=10)
        _append_transport_owner(response_owners, response)
        if int(getattr(response, "status", response.getcode())) != 200:
            raise TransportBoundaryError("GitHub history request was not HTTP 200")
        length = _content_length(_header(response, "Content-Length"))
        if length is not None and length > _GITHUB_RESPONSE_CAP:
            raise TransportBoundaryError("GitHub history response exceeds cap")
        raw = response.read(_GITHUB_RESPONSE_CAP + 1)
        if len(raw) > _GITHUB_RESPONSE_CAP:
            raise TransportBoundaryError("GitHub history response exceeds cap")
        root = _object(strict_json_loads(raw), "GitHub history")
        runs = root["workflow_runs"]
        if not isinstance(runs, tuple) or len(runs) >= 100:
            raise TransportBoundaryError("GitHub history is truncated or malformed")
        eligible: list[int] = []
        for value in runs:
            row = _object(value, "workflow run")
            created = row["created_at"]
            if not isinstance(created, str):
                raise TransportBoundaryError("workflow run created_at malformed")
            observed_time = dt.datetime.fromisoformat(created.replace("Z", "+00:00"))
            if observed_time >= start:
                eligible.append(_integer(row["id"], "workflow run ID"))
        if eligible != [current_run_id]:
            raise TransportBoundaryError("single-use R11A workflow history gate failed")
    except BaseException as exc:
        if isinstance(exc, urllib.error.HTTPError):
            _append_transport_owner(response_owners, exc)
        failure = exc

    _raise_transport_cleanup(
        _close_transport_owners(response_owners),
        label="GitHub history response",
        original_failure=failure,
    )
    if failure is not None:
        if isinstance(failure, CleanupBoundaryError):
            raise failure
        if isinstance(failure, urllib.error.HTTPError):
            raise TransportBoundaryError(
                "GitHub history HTTP failure without retry"
            ) from failure
        if isinstance(failure, urllib.error.URLError):
            raise TransportBoundaryError(
                "GitHub history transport failure without retry"
            ) from failure
        raise failure


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sealed R11A network boundary")
    sub = parser.add_subparsers(dest="command", required=True)
    history = sub.add_parser("verify-history")
    history.add_argument("--repository", required=True)
    history.add_argument("--workflow-file", required=True)
    history.add_argument("--current-run-id", required=True, type=int)
    history.add_argument("--current-run-attempt", required=True, type=int)
    history.add_argument("--window-start", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.command == "verify-history":
        token = os.environ.get("GH_TOKEN", "")
        if not token:
            raise SystemExit("GH_TOKEN is required for bounded history validation")
        try:
            validate_single_use_history(
                repository=arguments.repository,
                workflow_file=arguments.workflow_file,
                current_run_id=arguments.current_run_id,
                current_run_attempt=arguments.current_run_attempt,
                single_use_window_start_utc=arguments.window_start,
                token=token,
            )
        except CleanupBoundaryError:
            return _FATAL_CLEANUP_EXIT_CODE
        print("R11A_SINGLE_USE_HISTORY_VALID")
        return 0
    raise SystemExit("unsupported network command")


if __name__ == "__main__":
    raise SystemExit(main())
