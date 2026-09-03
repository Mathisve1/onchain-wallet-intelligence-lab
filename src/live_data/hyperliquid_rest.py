"""Read-only client for the Hyperliquid ``POST /info`` endpoint.

The client builds request bodies for a fixed allowlist of informational
request types. It has no notion of an order, a credential or a cryptographic
authorization, and the only URL it can construct is the ``/info`` path from
:mod:`.config`.

The HTTP transport is injected, so the whole request/response/retry path is
exercised offline in tests.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from .config import INFO_PATH, READ_ONLY_REST_PATHS, LiveDataConfig, normalize_wallet_address
from .models import (
    ClearinghouseState,
    Fill,
    Meta,
    OpenOrder,
    parse_all_mids,
    parse_fills,
    parse_funding,
    parse_open_orders,
    FundingDelta,
)
from .rate_limit import Sleeper, TokenBucket

#: Documented per-request weights. Anything not listed here costs 20.
INFO_REQUEST_WEIGHTS: dict[str, int] = {
    "allMids": 2,
    "clearinghouseState": 2,
    "l2Book": 2,
    "meta": 20,
    "userFills": 20,
    "userFillsByTime": 20,
    "userFunding": 20,
    "openOrders": 20,
}
DEFAULT_REQUEST_WEIGHT = 20

#: The venue returns at most this many rows per time-ranged fills response.
MAX_FILLS_PER_RESPONSE = 500

SUPPORTED_REQUEST_TYPES = frozenset(INFO_REQUEST_WEIGHTS) - {"l2Book"}

RETRYABLE_STATUSES = frozenset({429})


class RestError(RuntimeError):
    """Raised when a request is malformed or the venue answers with an error."""


class RestHttpError(RestError):
    """Raised when the venue returns a non-2xx status after all retries."""

    def __init__(self, status_code: int, body: str) -> None:
        super().__init__(f"HTTP {status_code}: {body[:200]}")
        self.status_code = status_code
        self.body = body


@dataclass(frozen=True, slots=True)
class HttpRequest:
    url: str
    body: str
    headers: Mapping[str, str] = field(default_factory=lambda: {"Content-Type": "application/json"})
    method: str = "POST"
    timeout_seconds: float = 10.0


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status_code: int
    body: str


Transport = Callable[[HttpRequest], HttpResponse]


def is_retryable(status_code: int) -> bool:
    """Only rate limiting and server-side faults justify a retry."""
    return status_code in RETRYABLE_STATUSES or 500 <= status_code <= 599


def request_weight(request_type: str) -> int:
    return INFO_REQUEST_WEIGHTS.get(request_type, DEFAULT_REQUEST_WEIGHT)


def _optional_bool(params: Mapping[str, Any], key: str) -> bool | None:
    value = params.get(key)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise RestError(f"{key} must be a boolean")
    return value


def _optional_dex(params: Mapping[str, Any]) -> str | None:
    value = params.get("dex")
    if value is None:
        return None
    if not isinstance(value, str):
        raise RestError("dex must be a string")
    return value


def _positive_time(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RestError(f"{name} must be an integer millisecond timestamp")
    if value < 0:
        raise RestError(f"{name} must be nonnegative")
    return value


def build_info_body(request_type: str, **params: Any) -> dict[str, Any]:
    """Build a validated ``/info`` request body.

    Unknown request types and unknown parameters are rejected rather than
    forwarded, so a typo cannot silently become a different query.
    """
    if request_type not in SUPPORTED_REQUEST_TYPES:
        raise RestError(f"unsupported info request type: {request_type!r}")

    body: dict[str, Any] = {"type": request_type}
    allowed: set[str]

    if request_type == "meta":
        allowed = set()
    elif request_type == "allMids":
        allowed = {"dex"}
        dex = _optional_dex(params)
        if dex is not None:
            body["dex"] = dex
    elif request_type in {"clearinghouseState", "userFunding"}:
        allowed = {"user", "start_time", "end_time"} if request_type == "userFunding" else {"user"}
        body["user"] = normalize_wallet_address(params.get("user"))
        if request_type == "userFunding":
            if "start_time" in params and params["start_time"] is not None:
                body["startTime"] = _positive_time(params["start_time"], "start_time")
            if "end_time" in params and params["end_time"] is not None:
                body["endTime"] = _positive_time(params["end_time"], "end_time")
    elif request_type == "userFills":
        allowed = {"user", "aggregate_by_time"}
        body["user"] = normalize_wallet_address(params.get("user"))
        aggregate = _optional_bool(params, "aggregate_by_time")
        if aggregate is not None:
            body["aggregateByTime"] = aggregate
    elif request_type == "userFillsByTime":
        allowed = {"user", "start_time", "end_time", "aggregate_by_time"}
        body["user"] = normalize_wallet_address(params.get("user"))
        if "start_time" not in params:
            raise RestError("userFillsByTime requires start_time")
        start_time = _positive_time(params["start_time"], "start_time")
        body["startTime"] = start_time
        end_time = params.get("end_time")
        if end_time is not None:
            end_value = _positive_time(end_time, "end_time")
            if end_value < start_time:
                raise RestError("end_time must not precede start_time")
            body["endTime"] = end_value
        aggregate = _optional_bool(params, "aggregate_by_time")
        if aggregate is not None:
            body["aggregateByTime"] = aggregate
    elif request_type == "openOrders":
        allowed = {"user", "dex"}
        body["user"] = normalize_wallet_address(params.get("user"))
        dex = _optional_dex(params)
        if dex is not None:
            body["dex"] = dex
    else:  # pragma: no cover - guarded by SUPPORTED_REQUEST_TYPES
        raise RestError(f"unhandled request type: {request_type!r}")

    unexpected = sorted(set(params) - allowed)
    if unexpected:
        raise RestError(f"unexpected parameters for {request_type}: {', '.join(unexpected)}")
    return body


def build_urllib_transport() -> Transport:
    """Default stdlib transport. Read-only: it can only issue the POST it is given.

    The HTTP stack is imported here rather than at module scope so that
    importing this package loads no network machinery at all. Governance
    tooling asserts that ``src/archive_inventory`` carries no network imports;
    meeting the same standard here costs nothing, because the transport is
    injected and the stdlib one is built only when a caller actually wants it.
    """
    import urllib.error  # noqa: PLC0415 - deferred on purpose, see docstring
    import urllib.request  # noqa: PLC0415

    def transport(request: HttpRequest) -> HttpResponse:
        raw = urllib.request.Request(  # noqa: S310 - scheme is validated in LiveDataConfig
            request.url,
            data=request.body.encode("utf-8"),
            headers=dict(request.headers),
            method=request.method,
        )
        try:
            with urllib.request.urlopen(raw, timeout=request.timeout_seconds) as response:
                return HttpResponse(status_code=response.status, body=response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:  # status-bearing failure, let the retry policy decide
            return HttpResponse(status_code=exc.code, body=exc.read().decode("utf-8", "replace"))

    return transport


class HyperliquidRestClient:
    """Weight-budgeted, retrying, read-only ``/info`` client."""

    def __init__(
        self,
        config: LiveDataConfig,
        *,
        transport: Transport | None = None,
        bucket: TokenBucket | None = None,
        sleeper: Sleeper = time.sleep,
        backoff_base_seconds: float = 0.5,
    ) -> None:
        config.authorizations.assert_read_only()
        if INFO_PATH not in READ_ONLY_REST_PATHS:  # pragma: no cover - constant guard
            raise RestError("read-only path allowlist drift")
        self._config = config
        self._transport = transport or build_urllib_transport()
        self._bucket = bucket or TokenBucket.from_config(config, sleeper=sleeper)
        self._sleeper = sleeper
        self._backoff_base_seconds = backoff_base_seconds
        self.attempted_requests = 0
        self.retried_requests = 0

    @property
    def config(self) -> LiveDataConfig:
        return self._config

    def request(self, request_type: str, **params: Any) -> Any:
        """Issue one validated ``/info`` request and return the decoded JSON."""
        body = build_info_body(request_type, **params)
        payload = json.dumps(body, separators=(",", ":"), sort_keys=True)
        weight = request_weight(request_type)

        attempt = 0
        while True:
            # Charged per attempt, not per logical request: a retry is a real
            # request against the venue's IP budget and costs the same weight.
            # Spending it only once would under-report our own consumption by
            # up to max_retries + 1 times, exactly while we are being throttled.
            self._bucket.acquire(weight)
            self.attempted_requests += 1
            response = self._transport(
                HttpRequest(
                    url=self._config.info_url,
                    body=payload,
                    timeout_seconds=self._config.request_timeout_seconds,
                )
            )
            if 200 <= response.status_code < 300:
                try:
                    return json.loads(response.body)
                except json.JSONDecodeError as exc:
                    raise RestError(f"{request_type}: response was not valid JSON") from exc
            if not is_retryable(response.status_code) or attempt >= self._config.max_retries:
                raise RestHttpError(response.status_code, response.body)
            self._sleeper(self._backoff_base_seconds * (2**attempt))
            self.retried_requests += 1
            attempt += 1

    # -- typed convenience wrappers -------------------------------------------------

    def meta(self) -> Meta:
        return Meta.parse(self.request("meta"))

    def all_mids(self) -> dict[str, Any]:
        return parse_all_mids(self.request("allMids"))

    def clearinghouse_state(self, user: str) -> ClearinghouseState:
        return ClearinghouseState.parse(self.request("clearinghouseState", user=user), user)

    def user_fills(self, user: str, *, aggregate_by_time: bool | None = None) -> tuple[Fill, ...]:
        payload = self.request("userFills", user=user, aggregate_by_time=aggregate_by_time)
        return parse_fills(payload, user)

    def user_fills_by_time(
        self,
        user: str,
        *,
        start_time: int,
        end_time: int | None = None,
        aggregate_by_time: bool | None = None,
    ) -> tuple[Fill, ...]:
        payload = self.request(
            "userFillsByTime",
            user=user,
            start_time=start_time,
            end_time=end_time,
            aggregate_by_time=aggregate_by_time,
        )
        return parse_fills(payload, user)

    def user_funding(
        self, user: str, *, start_time: int | None = None, end_time: int | None = None
    ) -> tuple[FundingDelta, ...]:
        payload = self.request("userFunding", user=user, start_time=start_time, end_time=end_time)
        return parse_funding(payload, user)

    def open_orders(self, user: str) -> tuple[OpenOrder, ...]:
        return parse_open_orders(self.request("openOrders", user=user), user)
