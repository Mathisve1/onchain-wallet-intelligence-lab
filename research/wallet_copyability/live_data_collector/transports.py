"""Concrete network transports for the live data pipeline.

These are the only network-touching pieces of the pipeline, which is why they
live under ``research/`` alongside the other collectors rather than under
``src/``. They implement the transport protocols defined by the deterministic
core and are injected into it; the core has no way to build one itself.
"""

from __future__ import annotations

import urllib.error
import urllib.request

from src.live_data.hyperliquid_rest import HttpRequest, HttpResponse, Transport
from src.live_data.hyperliquid_ws import Connection, ConnectionFactory, WebSocketError


def build_urllib_transport() -> Transport:
    """Stdlib HTTP transport. Read-only: it can only issue the POST it is given.

    The request is fully constructed by the core, including its URL, so this
    function adds no capability of its own beyond performing the send.
    """

    def transport(request: HttpRequest) -> HttpResponse:
        raw = urllib.request.Request(  # noqa: S310 - scheme is validated in LiveDataConfig
            request.url,
            data=request.body.encode("utf-8"),
            headers=dict(request.headers),
            method=request.method,
        )
        try:
            with urllib.request.urlopen(raw, timeout=request.timeout_seconds) as response:
                return HttpResponse(
                    status_code=response.status, body=response.read().decode("utf-8")
                )
        except urllib.error.HTTPError as exc:  # status-bearing failure: let the retry policy decide
            return HttpResponse(status_code=exc.code, body=exc.read().decode("utf-8", "replace"))

    return transport


def build_default_connection_factory() -> ConnectionFactory:
    """Lazily bind the optional ``websockets`` package as the real transport.

    The dependency is deliberately not required by the project: tests inject a
    fake factory, and the import error surfaces only when a live socket is
    actually needed.
    """

    def factory(url: str) -> Connection:
        try:
            from websockets.sync.client import connect  # noqa: PLC0415 - optional dependency
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise WebSocketError(
                "no websocket transport available: install 'websockets' "
                "or pass connection_factory=..."
            ) from exc
        return connect(url)  # pragma: no cover - requires a live socket

    return factory
