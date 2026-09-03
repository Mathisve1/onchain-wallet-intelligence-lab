"""Configuration for the read-only Hyperliquid live data pipeline.

This package observes public venue state. It never authenticates, never signs
and never reaches a write endpoint. The authorization flags below mirror
RISK_POLICY.md and exist so that any drift is a loud, testable failure rather
than a silent capability.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from pathlib import Path

DEFAULT_REST_BASE_URL = "https://api.hyperliquid.xyz"
DEFAULT_WS_URL = "wss://api.hyperliquid.xyz/ws"

#: The only REST path this package is allowed to build. Write paths are absent
#: from the codebase entirely, not merely disabled.
INFO_PATH = "/info"
READ_ONLY_REST_PATHS = frozenset({INFO_PATH})

#: Documented aggregated IP budget for REST requests: 1200 weight per minute.
DEFAULT_WEIGHT_PER_MINUTE = 1200

#: The server closes a websocket that has been silent for 60 seconds, so the
#: client heartbeat has to fire comfortably inside that window.
DEFAULT_WS_HEARTBEAT_SECONDS = 50.0
WS_SERVER_TIMEOUT_SECONDS = 60.0

_ADDRESS_PATTERN = re.compile(r"^0x[0-9a-f]{40}$")


class ConfigError(ValueError):
    """Raised when configuration input is malformed."""


def normalize_wallet_address(value: object) -> str:
    """Return the canonical lowercase form of a 20-byte hex wallet address.

    Case is normalized because EIP-55 checksum casing is a display concern, not
    an identity one. Anything that is not exactly ``0x`` plus 40 hex digits is
    rejected; no other coercion happens.
    """
    if not isinstance(value, str):
        raise ConfigError(f"wallet address must be a string, got {type(value).__name__}")
    candidate = value.lower()
    if not _ADDRESS_PATTERN.match(candidate):
        raise ConfigError(f"invalid wallet address: {value!r}")
    return candidate


def normalize_coin(value: object) -> str:
    """Return a validated venue coin symbol."""
    if not isinstance(value, str):
        raise ConfigError(f"coin must be a string, got {type(value).__name__}")
    if not value or value.strip() != value:
        raise ConfigError(f"invalid coin symbol: {value!r}")
    if len(value) > 32:
        raise ConfigError(f"coin symbol too long: {value!r}")
    return value


@dataclass(frozen=True, slots=True)
class TradingAuthorizations:
    """Mirror of the RISK_POLICY.md authorization table.

    Every flag is ``False`` by default and this package contains no code path
    that sets one to ``True``. :meth:`assert_read_only` is called on every
    config construction so an externally supplied ``True`` fails closed.
    """

    integration_authorized: bool = False
    paper_authorized: bool = False
    shadow_authorized: bool = False
    live_authorized: bool = False
    leverage_authorized: bool = False
    capital_allocation_authorized: bool = False

    def as_dict(self) -> dict[str, bool]:
        return {
            "integration_authorized": self.integration_authorized,
            "paper_authorized": self.paper_authorized,
            "shadow_authorized": self.shadow_authorized,
            "live_authorized": self.live_authorized,
            "leverage_authorized": self.leverage_authorized,
            "capital_allocation_authorized": self.capital_allocation_authorized,
        }

    def assert_read_only(self) -> None:
        opened = sorted(name for name, state in self.as_dict().items() if state)
        if opened:
            raise ConfigError(f"trading authorization opened: {', '.join(opened)}")

    def __post_init__(self) -> None:
        for name, state in self.as_dict().items():
            if not isinstance(state, bool):
                raise ConfigError(f"authorization {name} must be a bool")


@dataclass(frozen=True, slots=True)
class LiveDataConfig:
    """Immutable settings for one observation session."""

    rest_base_url: str = DEFAULT_REST_BASE_URL
    ws_url: str = DEFAULT_WS_URL
    tracked_coins: tuple[str, ...] = ()
    tracked_wallets: tuple[str, ...] = ()
    database_path: Path = Path("research/live_data/hyperliquid_live.sqlite3")
    weight_per_minute: int = DEFAULT_WEIGHT_PER_MINUTE
    request_timeout_seconds: float = 10.0
    max_retries: int = 3
    ws_heartbeat_seconds: float = DEFAULT_WS_HEARTBEAT_SECONDS
    authorizations: TradingAuthorizations = field(default_factory=TradingAuthorizations)

    def __post_init__(self) -> None:
        if not self.rest_base_url.startswith("https://"):
            raise ConfigError("REST base URL must use https")
        if self.rest_base_url.endswith("/"):
            raise ConfigError("REST base URL must not have a trailing slash")
        if not self.ws_url.startswith("wss://"):
            raise ConfigError("websocket URL must use wss")
        if self.weight_per_minute <= 0:
            raise ConfigError("weight budget must be positive")
        if self.request_timeout_seconds <= 0:
            raise ConfigError("request timeout must be positive")
        if self.max_retries < 0:
            raise ConfigError("max retries must be nonnegative")
        if not 0 < self.ws_heartbeat_seconds < WS_SERVER_TIMEOUT_SECONDS:
            raise ConfigError("heartbeat must be positive and below the 60s server timeout")
        object.__setattr__(self, "tracked_coins", tuple(normalize_coin(c) for c in self.tracked_coins))
        object.__setattr__(
            self, "tracked_wallets", tuple(normalize_wallet_address(w) for w in self.tracked_wallets)
        )
        if len(set(self.tracked_coins)) != len(self.tracked_coins):
            raise ConfigError("duplicate tracked coin")
        if len(set(self.tracked_wallets)) != len(self.tracked_wallets):
            raise ConfigError("duplicate tracked wallet")
        object.__setattr__(self, "database_path", Path(self.database_path))
        self.authorizations.assert_read_only()

    @property
    def info_url(self) -> str:
        """Full URL of the only endpoint this package contacts."""
        return f"{self.rest_base_url}{INFO_PATH}"

    def with_wallets(self, wallets: tuple[str, ...]) -> LiveDataConfig:
        return replace(self, tracked_wallets=wallets)
