from __future__ import annotations

import hashlib
import http.client
import os
import socket
import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from . import schema


class R11ANetworkError(ValueError):
    """Raised for the single non-retried bounded HTTPS object request."""


@dataclass(frozen=True, slots=True)
class ResponseMetadata:
    status: int
    etag: str | None
    content_length: int | None
    request_charged: str | None


@dataclass(frozen=True, slots=True)
class DownloadResult:
    metadata: ResponseMetadata
    body_bytes_received: int
    body_sha256: str | None
    complete: bool


def _content_length(headers: Mapping[str, str]) -> int | None:
    raw = headers.get("content-length")
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise R11ANetworkError("response Content-Length is not an integer") from exc
    if value < 0:
        raise R11ANetworkError("response Content-Length is negative")
    return value


def https_get_to_file(
    *,
    host: str,
    request_path: str,
    request_headers: Mapping[str, str],
    destination: Path,
    expected_etag: str,
    expected_content_length: int,
    maximum_body_bytes: int,
    timeout_seconds: float,
    on_metadata: Callable[[ResponseMetadata], None] | None = None,
    on_progress: Callable[[int], None] | None = None,
    connection_factory: Callable[..., http.client.HTTPSConnection] = http.client.HTTPSConnection,
) -> DownloadResult:
    if type(host) is not str or not host or "/" in host:
        raise R11ANetworkError("unsafe HTTPS host")
    if type(request_path) is not str or not request_path.startswith("/"):
        raise R11ANetworkError("unsafe request path")
    if type(expected_content_length) is not int or expected_content_length < 0:
        raise R11ANetworkError("invalid expected content length")
    if type(maximum_body_bytes) is not int or maximum_body_bytes < expected_content_length:
        raise R11ANetworkError("body cap is below expected content length")
    if timeout_seconds <= 0:
        raise R11ANetworkError("timeout must be positive")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".partial")
    temporary.unlink(missing_ok=True)
    connection = connection_factory(
        host,
        timeout=timeout_seconds,
        context=ssl.create_default_context(),
    )
    received = 0
    digest = hashlib.sha256()
    metadata: ResponseMetadata | None = None
    try:
        connection.request("GET", request_path, headers=dict(request_headers))
        response = connection.getresponse()
        headers = {key.lower(): value for key, value in response.getheaders()}
        metadata = ResponseMetadata(
            status=response.status,
            etag=headers.get("etag"),
            content_length=_content_length(headers),
            request_charged=headers.get("x-amz-request-charged"),
        )
        if on_metadata is not None:
            on_metadata(metadata)
        if metadata.status != 200:
            raise R11ANetworkError(f"S3 HTTP status {metadata.status}")
        if (metadata.request_charged or "").lower() != "requester":
            raise R11ANetworkError("Requester Pays acknowledgement absent")
        if metadata.etag != expected_etag:
            raise R11ANetworkError("response ETag mismatch")
        if metadata.content_length != expected_content_length:
            raise R11ANetworkError("response Content-Length metadata mismatch")
        with temporary.open("xb") as handle:
            while True:
                chunk = response.read(min(1024 * 1024, maximum_body_bytes - received + 1))
                if not chunk:
                    break
                received += len(chunk)
                if received > maximum_body_bytes or received > expected_content_length:
                    raise R11ANetworkError("response body exceeded frozen byte cap")
                handle.write(chunk)
                digest.update(chunk)
                if on_progress is not None:
                    on_progress(received)
            handle.flush()
            os.fsync(handle.fileno())
        if received != expected_content_length:
            raise R11ANetworkError("response body ended before Content-Length")
        os.replace(temporary, destination)
        return DownloadResult(metadata, received, digest.hexdigest(), True)
    except (OSError, socket.timeout, http.client.HTTPException, ssl.SSLError) as exc:
        raise R11ANetworkError(f"HTTPS transport failure: {type(exc).__name__}") from exc
    finally:
        connection.close()
        if temporary.exists():
            temporary.unlink()


def load_complete_download(path: Path, expected_size: int, expected_sha256: str) -> bytes:
    data = path.read_bytes()
    if len(data) != expected_size:
        raise R11ANetworkError("retained compressed body size drift")
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise R11ANetworkError("retained compressed body SHA-256 drift")
    return data
