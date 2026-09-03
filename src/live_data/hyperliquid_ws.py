"""Read-only Hyperliquid websocket client.

Subscribes to public and per-wallet observation channels, keeps the socket
alive with the documented ``{"method": "ping"}`` heartbeat, and reconnects
with exponential backoff while automatically restoring every subscription.

The connection factory is injected, so subscription, heartbeat, dispatch and
reconnect sequences are all testable without a socket.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from .config import LiveDataConfig, normalize_coin, normalize_wallet_address

#: Subscription types this client is allowed to open, and the fields each needs.
SUBSCRIPTION_TYPES: dict[str, frozenset[str]] = {
    "allMids": frozenset(),
    "trades": frozenset({"coin"}),
    "l2Book": frozenset({"coin"}),
    "userFills": frozenset({"user"}),
    "userEvents": frozenset({"user"}),
}

#: Inbound channel name per subscription type. ``userEvents`` is the documented
#: exception: its messages arrive on channel ``user``.
CHANNEL_BY_SUBSCRIPTION: dict[str, str] = {
    "allMids": "allMids",
    "trades": "trades",
    "l2Book": "l2Book",
    "userFills": "userFills",
    "userEvents": "user",
}

PING_MESSAGE = {"method": "ping"}
PONG_CHANNEL = "pong"
SUBSCRIPTION_RESPONSE_CHANNEL = "subscriptionResponse"
ERROR_CHANNEL = "error"


class WebSocketError(RuntimeError):
    """Raised on malformed subscriptions or malformed inbound frames."""


class Connection(Protocol):
    """Minimal duck type of a text websocket connection."""

    def send(self, message: str) -> None: ...

    def recv(self) -> str: ...

    def close(self) -> None: ...


ConnectionFactory = Callable[[str], Connection]
Handler = Callable[[dict[str, Any]], None]


@dataclass(frozen=True, slots=True)
class Subscription:
    """One validated subscription request."""

    type: str
    coin: str | None = None
    user: str | None = None

    def __post_init__(self) -> None:
        if self.type not in SUBSCRIPTION_TYPES:
            raise WebSocketError(f"unsupported subscription type: {self.type!r}")
        required = SUBSCRIPTION_TYPES[self.type]
        if "coin" in required:
            if self.coin is None:
                raise WebSocketError(f"{self.type} requires a coin")
            object.__setattr__(self, "coin", normalize_coin(self.coin))
        elif self.coin is not None:
            raise WebSocketError(f"{self.type} does not take a coin")
        if "user" in required:
            if self.user is None:
                raise WebSocketError(f"{self.type} requires a user")
            object.__setattr__(self, "user", normalize_wallet_address(self.user))
        elif self.user is not None:
            raise WebSocketError(f"{self.type} does not take a user")

    @property
    def channel(self) -> str:
        return CHANNEL_BY_SUBSCRIPTION[self.type]

    def as_payload(self) -> dict[str, str]:
        payload: dict[str, str] = {"type": self.type}
        if self.coin is not None:
            payload["coin"] = self.coin
        if self.user is not None:
            payload["user"] = self.user
        return payload


def build_subscribe_message(subscription: Subscription) -> dict[str, Any]:
    return {"method": "subscribe", "subscription": subscription.as_payload()}


def build_unsubscribe_message(subscription: Subscription) -> dict[str, Any]:
    return {"method": "unsubscribe", "subscription": subscription.as_payload()}


def build_default_connection_factory() -> ConnectionFactory:
    """Lazily bind the optional ``websockets`` package as the real transport.

    The dependency is deliberately not required: tests inject a fake factory
    and the import error is raised only when a live socket is actually needed.
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


class HyperliquidWebSocketClient:
    """Subscription registry, heartbeat and reconnect loop over one connection."""

    def __init__(
        self,
        config: LiveDataConfig,
        *,
        connection_factory: ConnectionFactory | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
        backoff_base_seconds: float = 1.0,
        max_backoff_seconds: float = 60.0,
        max_reconnects: int | None = None,
    ) -> None:
        config.authorizations.assert_read_only()
        self._config = config
        self._factory = connection_factory or build_default_connection_factory()
        self._clock = clock
        self._sleeper = sleeper
        self._backoff_base_seconds = backoff_base_seconds
        self._max_backoff_seconds = max_backoff_seconds
        self._max_reconnects = max_reconnects
        self._connection: Connection | None = None
        self._subscriptions: dict[Subscription, list[Handler]] = {}
        self._last_send_at: float = 0.0
        self.sent_messages: list[dict[str, Any]] = []
        self.pings_sent = 0
        self.pongs_received = 0
        self.acknowledged_subscriptions = 0
        self.unrouted_messages = 0
        self.handler_errors: list[str] = []
        self.connect_attempts = 0
        self.reconnects = 0

    @property
    def is_connected(self) -> bool:
        return self._connection is not None

    @property
    def subscriptions(self) -> tuple[Subscription, ...]:
        return tuple(self._subscriptions)

    # -- connection lifecycle -------------------------------------------------------

    def connect(self) -> None:
        """Open the socket and (re)send every registered subscription."""
        if self._connection is not None:
            return
        self.connect_attempts += 1
        self._connection = self._factory(self._config.ws_url)
        self._last_send_at = self._clock()
        for subscription in self._subscriptions:
            self._send(build_subscribe_message(subscription))

    def close(self) -> None:
        connection, self._connection = self._connection, None
        if connection is not None:
            connection.close()

    def _send(self, message: dict[str, Any]) -> None:
        if self._connection is None:
            raise WebSocketError("cannot send on a closed connection")
        self._connection.send(json.dumps(message, separators=(",", ":"), sort_keys=True))
        self.sent_messages.append(message)
        self._last_send_at = self._clock()

    # -- subscriptions --------------------------------------------------------------

    def subscribe(self, subscription: Subscription, handler: Handler) -> None:
        """Register a handler and, if connected, send the subscribe frame."""
        is_new = subscription not in self._subscriptions
        self._subscriptions.setdefault(subscription, []).append(handler)
        if is_new and self._connection is not None:
            self._send(build_subscribe_message(subscription))

    def unsubscribe(self, subscription: Subscription) -> None:
        """Drop a subscription and its handlers, sending the unsubscribe frame."""
        if subscription not in self._subscriptions:
            raise WebSocketError(f"not subscribed: {subscription.as_payload()}")
        del self._subscriptions[subscription]
        if self._connection is not None:
            self._send(build_unsubscribe_message(subscription))

    # -- heartbeat ------------------------------------------------------------------

    def heartbeat_if_due(self) -> bool:
        """Send a ping when the socket has been silent for the heartbeat window."""
        if self._connection is None:
            return False
        if self._clock() - self._last_send_at < self._config.ws_heartbeat_seconds:
            return False
        self._send(dict(PING_MESSAGE))
        self.pings_sent += 1
        return True

    # -- inbound ---------------------------------------------------------------------

    def dispatch(self, raw: str) -> str:
        """Validate one inbound frame and route it. Returns the channel name."""
        try:
            message = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise WebSocketError("inbound frame was not valid JSON") from exc
        if not isinstance(message, dict):
            raise WebSocketError(f"inbound frame must be an object, got {type(message).__name__}")
        channel = message.get("channel")
        if not isinstance(channel, str) or not channel:
            raise WebSocketError("inbound frame is missing a string 'channel'")
        if channel == PONG_CHANNEL:
            self.pongs_received += 1
            return channel
        if channel == SUBSCRIPTION_RESPONSE_CHANNEL:
            self.acknowledged_subscriptions += 1
            return channel
        if channel == ERROR_CHANNEL:
            raise WebSocketError(f"venue error frame: {message.get('data')!r}")
        handlers = [
            handler
            for subscription, registered in self._subscriptions.items()
            if subscription.channel == channel
            for handler in registered
        ]
        if not handlers:
            self.unrouted_messages += 1
            return channel
        for handler in handlers:
            try:
                handler(message)
            except Exception as exc:  # a bad handler must not silently drop the feed
                self.handler_errors.append(f"{channel}: {exc}")
        return channel

    def poll_once(self) -> bool:
        """Read and dispatch one frame, reconnecting if the socket dropped."""
        if self._connection is None:
            self.connect()
        assert self._connection is not None
        try:
            raw = self._connection.recv()
        except Exception:
            self._reconnect()
            return False
        self.dispatch(raw)
        return True

    def _reconnect(self) -> None:
        self.close()
        attempt = 0
        while True:
            if self._max_reconnects is not None and self.reconnects >= self._max_reconnects:
                raise WebSocketError("reconnect budget exhausted")
            delay = min(
                self._max_backoff_seconds, self._backoff_base_seconds * (2**attempt)
            )
            self._sleeper(delay)
            self.reconnects += 1
            try:
                self.connect()
            except Exception:
                self.close()
                attempt += 1
                continue
            return

    def run(self, *, max_iterations: int, stop: Callable[[], bool] | None = None) -> int:
        """Pump the socket for a bounded number of iterations.

        Bounded on purpose: an unbounded loop is untestable and, in a research
        lab, an unattended process that nobody can reason about.
        """
        if max_iterations < 0:
            raise WebSocketError("max_iterations must be nonnegative")
        dispatched = 0
        for _ in range(max_iterations):
            if stop is not None and stop():
                break
            self.heartbeat_if_due()
            if self.poll_once():
                dispatched += 1
        return dispatched
