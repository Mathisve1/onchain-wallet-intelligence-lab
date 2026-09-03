"""Typed venue payloads and their strict parsers.

Parsing fails closed. A missing key, a wrong JSON type or an out-of-range
value raises :class:`PayloadError` instead of producing a partially populated
record. Numeric strings stay :class:`~decimal.Decimal` so that no float
rounding is introduced between the venue and the ledger.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from .config import normalize_coin, normalize_wallet_address

#: The archive identity gates document trade ids as strict JSON uint50.
MAX_TID = (1 << 50) - 1

#: Venue side encoding: ``B`` is the bid (buy) side, ``A`` the ask (sell) side.
SIDE_BUY = "B"
SIDE_SELL = "A"
_SIDES = {SIDE_BUY, SIDE_SELL}


class PayloadError(ValueError):
    """Raised when a venue payload does not match its documented shape."""


def require_mapping(payload: object, context: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise PayloadError(f"{context}: expected object, got {type(payload).__name__}")
    return payload


def require_list(payload: object, context: str) -> list[Any]:
    if not isinstance(payload, list):
        raise PayloadError(f"{context}: expected array, got {type(payload).__name__}")
    return payload


def require_str(payload: Mapping[str, Any], key: str, context: str) -> str:
    if key not in payload:
        raise PayloadError(f"{context}: missing field {key!r}")
    value = payload[key]
    if not isinstance(value, str):
        raise PayloadError(f"{context}.{key}: expected string, got {type(value).__name__}")
    return value


def require_int(payload: Mapping[str, Any], key: str, context: str) -> int:
    if key not in payload:
        raise PayloadError(f"{context}: missing field {key!r}")
    value = payload[key]
    # bool is an int subclass; a boolean in a numeric slot is malformed input.
    if isinstance(value, bool) or not isinstance(value, int):
        raise PayloadError(f"{context}.{key}: expected integer, got {type(value).__name__}")
    return value


def require_bool(payload: Mapping[str, Any], key: str, context: str) -> bool:
    if key not in payload:
        raise PayloadError(f"{context}: missing field {key!r}")
    value = payload[key]
    if not isinstance(value, bool):
        raise PayloadError(f"{context}.{key}: expected boolean, got {type(value).__name__}")
    return value


def to_decimal(value: object, context: str) -> Decimal:
    """Convert a venue numeric string to Decimal without accepting floats.

    Floats are rejected on purpose: the venue sends decimal strings and
    accepting a float here would silently import binary rounding error.
    """
    if isinstance(value, bool) or isinstance(value, float):
        raise PayloadError(f"{context}: expected decimal string, got {type(value).__name__}")
    if isinstance(value, int):
        return Decimal(value)
    if not isinstance(value, str) or not value:
        raise PayloadError(f"{context}: expected decimal string, got {type(value).__name__}")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise PayloadError(f"{context}: undecodable decimal {value!r}") from exc
    if not parsed.is_finite():
        raise PayloadError(f"{context}: non-finite decimal {value!r}")
    return parsed


def require_decimal(payload: Mapping[str, Any], key: str, context: str) -> Decimal:
    if key not in payload:
        raise PayloadError(f"{context}: missing field {key!r}")
    return to_decimal(payload[key], f"{context}.{key}")


def optional_decimal(payload: Mapping[str, Any], key: str, context: str) -> Decimal | None:
    value = payload.get(key)
    if value is None:
        return None
    return to_decimal(value, f"{context}.{key}")


def require_event_time_ms(payload: Mapping[str, Any], key: str, context: str) -> int:
    value = require_int(payload, key, context)
    if value <= 0:
        raise PayloadError(f"{context}.{key}: event time must be positive")
    return value


@dataclass(frozen=True, slots=True)
class AssetMeta:
    """One perpetual listed in the ``meta`` universe."""

    name: str
    size_decimals: int
    max_leverage: int
    is_delisted: bool

    @classmethod
    def parse(cls, payload: object) -> AssetMeta:
        row = require_mapping(payload, "meta.universe[]")
        size_decimals = require_int(row, "szDecimals", "meta.universe[]")
        max_leverage = require_int(row, "maxLeverage", "meta.universe[]")
        if size_decimals < 0:
            raise PayloadError("meta.universe[].szDecimals must be nonnegative")
        if max_leverage <= 0:
            raise PayloadError("meta.universe[].maxLeverage must be positive")
        delisted = row.get("isDelisted", False)
        if not isinstance(delisted, bool):
            raise PayloadError("meta.universe[].isDelisted must be a boolean")
        return cls(
            name=normalize_coin(require_str(row, "name", "meta.universe[]")),
            size_decimals=size_decimals,
            max_leverage=max_leverage,
            is_delisted=delisted,
        )


@dataclass(frozen=True, slots=True)
class Meta:
    """Parsed ``meta`` response."""

    universe: tuple[AssetMeta, ...]

    @classmethod
    def parse(cls, payload: object) -> Meta:
        body = require_mapping(payload, "meta")
        rows = require_list(body.get("universe"), "meta.universe")
        universe = tuple(AssetMeta.parse(row) for row in rows)
        names = [asset.name for asset in universe]
        if len(set(names)) != len(names):
            raise PayloadError("meta.universe contains duplicate asset names")
        return cls(universe=universe)


def parse_all_mids(payload: object) -> dict[str, Decimal]:
    """Parse the ``allMids`` map of coin symbol to mid price."""
    body = require_mapping(payload, "allMids")
    # Newer responses may wrap the map under a "mids" key.
    inner = body.get("mids", body)
    mids_map = require_mapping(inner, "allMids.mids")
    mids: dict[str, Decimal] = {}
    for coin, raw in mids_map.items():
        symbol = normalize_coin(coin)
        price = to_decimal(raw, f"allMids.{symbol}")
        if price <= 0:
            raise PayloadError(f"allMids.{symbol}: mid price must be positive")
        mids[symbol] = price
    return mids


@dataclass(frozen=True, slots=True)
class Fill:
    """One wallet side of a matched trade.

    ``(wallet_address, coin, trade_id, event_time_ms)`` is the natural key used
    for idempotent persistence, matching the wallet-user-fill identity layer in
    SYSTEM_ARCHITECTURE.md.
    """

    wallet_address: str
    coin: str
    trade_id: int
    event_time_ms: int
    side: str
    price: Decimal
    size: Decimal
    fee: Decimal
    closed_pnl: Decimal
    start_position: Decimal
    direction: str
    order_id: int
    crossed: bool
    tx_hash: str
    fee_token: str | None

    @property
    def natural_key(self) -> tuple[str, str, int, int]:
        return (self.wallet_address, self.coin, self.trade_id, self.event_time_ms)

    @classmethod
    def parse(cls, payload: object, wallet_address: str) -> Fill:
        row = require_mapping(payload, "fill")
        trade_id = require_int(row, "tid", "fill")
        if not 0 <= trade_id <= MAX_TID:
            raise PayloadError(f"fill.tid outside uint50 range: {trade_id}")
        order_id = require_int(row, "oid", "fill")
        if order_id < 0:
            raise PayloadError("fill.oid must be nonnegative")
        side = require_str(row, "side", "fill")
        if side not in _SIDES:
            raise PayloadError(f"fill.side must be one of {sorted(_SIDES)}, got {side!r}")
        price = require_decimal(row, "px", "fill")
        size = require_decimal(row, "sz", "fill")
        if price <= 0 or size <= 0:
            raise PayloadError("fill price and size must be positive")
        fee_token = row.get("feeToken")
        if fee_token is not None and not isinstance(fee_token, str):
            raise PayloadError("fill.feeToken must be a string when present")
        return cls(
            wallet_address=normalize_wallet_address(wallet_address),
            coin=normalize_coin(require_str(row, "coin", "fill")),
            trade_id=trade_id,
            event_time_ms=require_event_time_ms(row, "time", "fill"),
            side=side,
            price=price,
            size=size,
            fee=require_decimal(row, "fee", "fill"),
            closed_pnl=require_decimal(row, "closedPnl", "fill"),
            start_position=require_decimal(row, "startPosition", "fill"),
            direction=require_str(row, "dir", "fill"),
            order_id=order_id,
            crossed=require_bool(row, "crossed", "fill"),
            tx_hash=require_str(row, "hash", "fill"),
            fee_token=fee_token,
        )


def parse_fills(payload: object, wallet_address: str) -> tuple[Fill, ...]:
    rows = require_list(payload, "fills")
    return tuple(Fill.parse(row, wallet_address) for row in rows)


@dataclass(frozen=True, slots=True)
class AssetPosition:
    """One open perpetual position inside a clearinghouse snapshot."""

    coin: str
    signed_size: Decimal
    entry_price: Decimal | None
    position_value: Decimal
    unrealized_pnl: Decimal
    margin_used: Decimal
    liquidation_price: Decimal | None

    @classmethod
    def parse(cls, payload: object) -> AssetPosition:
        wrapper = require_mapping(payload, "assetPositions[]")
        position = require_mapping(wrapper.get("position"), "assetPositions[].position")
        return cls(
            coin=normalize_coin(require_str(position, "coin", "position")),
            signed_size=require_decimal(position, "szi", "position"),
            entry_price=optional_decimal(position, "entryPx", "position"),
            position_value=require_decimal(position, "positionValue", "position"),
            unrealized_pnl=require_decimal(position, "unrealizedPnl", "position"),
            margin_used=require_decimal(position, "marginUsed", "position"),
            liquidation_price=optional_decimal(position, "liquidationPx", "position"),
        )


@dataclass(frozen=True, slots=True)
class MarginSummary:
    account_value: Decimal
    total_notional_position: Decimal
    total_raw_usd: Decimal
    total_margin_used: Decimal

    @classmethod
    def parse(cls, payload: object, context: str) -> MarginSummary:
        row = require_mapping(payload, context)
        return cls(
            account_value=require_decimal(row, "accountValue", context),
            total_notional_position=require_decimal(row, "totalNtlPos", context),
            total_raw_usd=require_decimal(row, "totalRawUsd", context),
            total_margin_used=require_decimal(row, "totalMarginUsed", context),
        )


@dataclass(frozen=True, slots=True)
class ClearinghouseState:
    """Parsed ``clearinghouseState`` snapshot for one wallet."""

    wallet_address: str
    snapshot_time_ms: int
    margin_summary: MarginSummary
    cross_margin_summary: MarginSummary
    withdrawable: Decimal
    positions: tuple[AssetPosition, ...]

    @classmethod
    def parse(cls, payload: object, wallet_address: str) -> ClearinghouseState:
        body = require_mapping(payload, "clearinghouseState")
        rows = require_list(body.get("assetPositions"), "clearinghouseState.assetPositions")
        return cls(
            wallet_address=normalize_wallet_address(wallet_address),
            snapshot_time_ms=require_event_time_ms(body, "time", "clearinghouseState"),
            margin_summary=MarginSummary.parse(
                body.get("marginSummary"), "clearinghouseState.marginSummary"
            ),
            cross_margin_summary=MarginSummary.parse(
                body.get("crossMarginSummary"), "clearinghouseState.crossMarginSummary"
            ),
            withdrawable=require_decimal(body, "withdrawable", "clearinghouseState"),
            positions=tuple(AssetPosition.parse(row) for row in rows),
        )


@dataclass(frozen=True, slots=True)
class FundingDelta:
    """One funding payment applied to a wallet."""

    wallet_address: str
    coin: str
    event_time_ms: int
    usdc: Decimal
    funding_rate: Decimal
    signed_size: Decimal

    @classmethod
    def parse(cls, payload: object, wallet_address: str) -> FundingDelta:
        row = require_mapping(payload, "userFunding[]")
        delta = require_mapping(row.get("delta"), "userFunding[].delta")
        kind = require_str(delta, "type", "userFunding[].delta")
        if kind != "funding":
            raise PayloadError(f"userFunding[].delta.type must be 'funding', got {kind!r}")
        return cls(
            wallet_address=normalize_wallet_address(wallet_address),
            coin=normalize_coin(require_str(delta, "coin", "userFunding[].delta")),
            event_time_ms=require_event_time_ms(row, "time", "userFunding[]"),
            usdc=require_decimal(delta, "usdc", "userFunding[].delta"),
            funding_rate=require_decimal(delta, "fundingRate", "userFunding[].delta"),
            signed_size=require_decimal(delta, "szi", "userFunding[].delta"),
        )


def parse_funding(payload: object, wallet_address: str) -> tuple[FundingDelta, ...]:
    rows = require_list(payload, "userFunding")
    return tuple(FundingDelta.parse(row, wallet_address) for row in rows)


@dataclass(frozen=True, slots=True)
class OpenOrder:
    """One resting order. Observation only; this package never places orders."""

    wallet_address: str
    coin: str
    order_id: int
    side: str
    limit_price: Decimal
    size: Decimal
    placed_at_ms: int

    @classmethod
    def parse(cls, payload: object, wallet_address: str) -> OpenOrder:
        row = require_mapping(payload, "openOrders[]")
        side = require_str(row, "side", "openOrders[]")
        if side not in _SIDES:
            raise PayloadError(f"openOrders[].side must be one of {sorted(_SIDES)}, got {side!r}")
        return cls(
            wallet_address=normalize_wallet_address(wallet_address),
            coin=normalize_coin(require_str(row, "coin", "openOrders[]")),
            order_id=require_int(row, "oid", "openOrders[]"),
            side=side,
            limit_price=require_decimal(row, "limitPx", "openOrders[]"),
            size=require_decimal(row, "sz", "openOrders[]"),
            placed_at_ms=require_event_time_ms(row, "timestamp", "openOrders[]"),
        )


def parse_open_orders(payload: object, wallet_address: str) -> tuple[OpenOrder, ...]:
    rows = require_list(payload, "openOrders")
    return tuple(OpenOrder.parse(row, wallet_address) for row in rows)
