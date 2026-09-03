"""Input types for the copyability simulator.

Everything the simulator consumes is one of these plain, validated values.
Nothing here knows where the data came from: a loader turns a live-data store
into these, a test builds them by hand, and the simulator cannot tell the
difference. That is what keeps it deterministic and network-free.

Times are integer milliseconds. Prices and sizes are ``Decimal``: the venue's
numbers are decimal strings and binary floats would quietly change them.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Sequence

SIDE_BUY = "B"
SIDE_SELL = "A"
SIDES = frozenset({SIDE_BUY, SIDE_SELL})


class InputError(ValueError):
    """Raised when an input value is malformed."""


def _positive_ms(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise InputError(f"{name} must be a positive millisecond timestamp, got {value!r}")
    return value


def _decimal(value: object, name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (Decimal, int, str)):
        raise InputError(f"{name} must be a Decimal, int or decimal string, got {type(value).__name__}")
    try:
        result = Decimal(value)
    except ArithmeticError as exc:
        raise InputError(f"{name} is not a valid decimal: {value!r}") from exc
    if not result.is_finite():
        raise InputError(f"{name} must be finite, got {value!r}")
    return result


@dataclass(frozen=True, slots=True)
class SourceFill:
    """One fill of the wallet being copied, as the venue reported it.

    ``fee`` and ``closed_pnl`` are the source wallet's own economics. They are
    carried so the source ledger can be built; the follower never uses them.
    """

    wallet: str
    coin: str
    time_ms: int
    side: str
    price: Decimal
    size: Decimal
    fee: Decimal
    closed_pnl: Decimal
    trade_id: int
    #: True when the fill crossed the spread (taker), False when it rested
    #: (maker), None when the source did not say. Used only to characterise
    #: the wallet; the follower is always a taker.
    crossed: bool | None = None

    def __post_init__(self) -> None:
        if not self.wallet or not self.coin:
            raise InputError("fill needs a wallet and a coin")
        if self.crossed is not None and not isinstance(self.crossed, bool):
            raise InputError("crossed must be a bool or None")
        if self.side not in SIDES:
            raise InputError(f"fill side must be one of {sorted(SIDES)}, got {self.side!r}")
        object.__setattr__(self, "time_ms", _positive_ms(self.time_ms, "time_ms"))
        object.__setattr__(self, "price", _decimal(self.price, "price"))
        object.__setattr__(self, "size", _decimal(self.size, "size"))
        object.__setattr__(self, "fee", _decimal(self.fee, "fee"))
        object.__setattr__(self, "closed_pnl", _decimal(self.closed_pnl, "closed_pnl"))
        if self.price <= 0 or self.size <= 0:
            raise InputError("fill price and size must be positive")

    @property
    def signed_size(self) -> Decimal:
        return self.size if self.side == SIDE_BUY else -self.size

    @property
    def notional(self) -> Decimal:
        return self.price * self.size


@dataclass(frozen=True, slots=True)
class PricePoint:
    time_ms: int
    price: Decimal


class PriceSeries:
    """Sorted mid prices for one coin with strictly point-in-time lookup."""

    __slots__ = ("coin", "_times", "_prices")

    def __init__(self, coin: str, points: Iterable[tuple[int, Decimal | str | int]]) -> None:
        if not coin:
            raise InputError("price series needs a coin")
        self.coin = coin
        rows = sorted((_positive_ms(t, "time_ms"), _decimal(p, "price")) for t, p in points)
        for _, price in rows:
            if price <= 0:
                raise InputError("prices must be positive")
        times = [t for t, _ in rows]
        if len(set(times)) != len(times):
            raise InputError(f"duplicate price timestamp in {coin}")
        self._times = times
        self._prices = [p for _, p in rows]

    def __len__(self) -> int:
        return len(self._times)

    @property
    def first_time_ms(self) -> int | None:
        return self._times[0] if self._times else None

    @property
    def last_time_ms(self) -> int | None:
        return self._times[-1] if self._times else None

    def at_or_before(self, time_ms: int) -> PricePoint | None:
        """Latest point observed at or before ``time_ms``; never a later one."""
        index = bisect_right(self._times, time_ms)
        if index == 0:
            return None
        return PricePoint(self._times[index - 1], self._prices[index - 1])

    def at_or_after(self, time_ms: int) -> PricePoint | None:
        """Earliest point observed at or after ``time_ms``.

        For a baseline that needs an entry: the first quote inside a window
        is a price a participant could actually have acted on. It is never
        used to price a decision made before it.
        """
        index = bisect_left(self._times, time_ms)
        if index >= len(self._times):
            return None
        return PricePoint(self._times[index], self._prices[index])

    def points(self) -> Sequence[PricePoint]:
        return [PricePoint(t, p) for t, p in zip(self._times, self._prices, strict=True)]


@dataclass(frozen=True, slots=True)
class FundingEvent:
    """One funding rate application for a coin: rate per unit notional held."""

    coin: str
    time_ms: int
    rate: Decimal

    def __post_init__(self) -> None:
        if not self.coin:
            raise InputError("funding event needs a coin")
        object.__setattr__(self, "time_ms", _positive_ms(self.time_ms, "time_ms"))
        object.__setattr__(self, "rate", _decimal(self.rate, "rate"))


class FundingSchedule:
    """Funding events per coin, sorted, point-in-time addressable.

    Constructed explicitly even when empty. A simulation that "forgot" funding
    should have to say so by passing an empty schedule, not by omission.
    """

    __slots__ = ("_events",)

    def __init__(self, events: Iterable[FundingEvent]) -> None:
        by_coin: dict[str, list[FundingEvent]] = {}
        for event in events:
            if not isinstance(event, FundingEvent):
                raise InputError(f"expected FundingEvent, got {type(event).__name__}")
            by_coin.setdefault(event.coin, []).append(event)
        self._events = {coin: sorted(rows, key=lambda e: e.time_ms) for coin, rows in by_coin.items()}

    def between(self, coin: str, start_ms: int, end_ms: int) -> list[FundingEvent]:
        """Events with ``start_ms < time_ms <= end_ms``."""
        return [e for e in self._events.get(coin, []) if start_ms < e.time_ms <= end_ms]

    def coins(self) -> frozenset[str]:
        return frozenset(self._events)


@dataclass(frozen=True, slots=True)
class LiquidityProfile:
    """What it costs to cross the book in one coin, from the follower's side.

    ``half_spread_bps`` is paid on every taker fill. ``depth_notional`` is the
    notional resting near the touch; an order's impact scales with the share
    of it the order consumes, times ``impact_bps_per_depth``. All three are
    required and positive: a zero here is a claim about the market, not a
    default, and has to be stated.
    """

    coin: str
    half_spread_bps: Decimal
    depth_notional: Decimal
    impact_bps_per_depth: Decimal

    def __post_init__(self) -> None:
        if not self.coin:
            raise InputError("liquidity profile needs a coin")
        for name in ("half_spread_bps", "depth_notional", "impact_bps_per_depth"):
            value = _decimal(getattr(self, name), name)
            if value <= 0:
                raise InputError(f"liquidity {name} must be positive for {self.coin}")
            object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True)
class MarketData:
    """Everything about the market the follower is allowed to know."""

    prices: dict[str, PriceSeries]
    funding: FundingSchedule
    liquidity: dict[str, LiquidityProfile]

    def __post_init__(self) -> None:
        for coin, series in self.prices.items():
            if series.coin != coin:
                raise InputError(f"price series keyed {coin!r} is for {series.coin!r}")
        for coin, profile in self.liquidity.items():
            if profile.coin != coin:
                raise InputError(f"liquidity keyed {coin!r} is for {profile.coin!r}")

    def require_coin(self, coin: str) -> tuple[PriceSeries, LiquidityProfile]:
        if coin not in self.prices:
            raise InputError(f"no price series for {coin}")
        if coin not in self.liquidity:
            raise InputError(f"no liquidity profile for {coin}: spread and depth must be stated")
        return self.prices[coin], self.liquidity[coin]
