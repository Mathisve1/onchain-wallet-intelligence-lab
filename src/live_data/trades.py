"""Public trade tape and the wallet discovery it enables.

The venue's ``trades`` websocket channel names both counterparties of every
public trade. That is the only place in the read-only surface where wallets
appear without being asked for by address, so it is how a session discovers
wallets it did not already know about. Each trade is retained as well: the
tape is the liquidity and price stream the copyability work has to model
against, and dropping it to keep only the addresses would throw away the
evidence for why an address was worth following.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable, Mapping

from .config import normalize_coin, normalize_wallet_address
from .models import (
    PayloadError,
    require_decimal,
    require_event_time_ms,
    require_int,
    require_list,
    require_mapping,
    require_str,
)

#: Every public trade names exactly a buyer and a seller, in that order.
TRADE_USER_COUNT = 2
TRADE_SIDES = frozenset({"A", "B"})


@dataclass(frozen=True, slots=True)
class Trade:
    """One public trade as broadcast on the ``trades`` channel."""

    coin: str
    trade_id: int
    event_time_ms: int
    side: str
    price: Decimal
    size: Decimal
    tx_hash: str
    buyer: str
    seller: str

    @classmethod
    def parse(cls, row: object) -> Trade:
        payload = require_mapping(row, "ws.trades.row")
        context = "ws.trades"
        side = require_str(payload, "side", context)
        if side not in TRADE_SIDES:
            raise PayloadError(f"{context}.side must be one of {sorted(TRADE_SIDES)}, got {side!r}")
        users = require_list(payload.get("users"), f"{context}.users")
        if len(users) != TRADE_USER_COUNT:
            raise PayloadError(f"{context}.users must name exactly {TRADE_USER_COUNT} wallets")
        return cls(
            coin=normalize_coin(require_str(payload, "coin", context)),
            trade_id=require_int(payload, "tid", context),
            event_time_ms=require_event_time_ms(payload, "time", context),
            side=side,
            price=require_decimal(payload, "px", context),
            size=require_decimal(payload, "sz", context),
            tx_hash=require_str(payload, "hash", context),
            buyer=normalize_wallet_address(users[0]),
            seller=normalize_wallet_address(users[1]),
        )

    @property
    def wallets(self) -> tuple[str, str]:
        return (self.buyer, self.seller)


def parse_trades(payload: object) -> tuple[Trade, ...]:
    """Parse the ``data`` array of one ``trades`` frame."""
    return tuple(Trade.parse(row) for row in require_list(payload, "ws.trades.data"))


#: Provenance label written on wallets that entered the store through the tape
#: rather than by being named on the command line.
DISCOVERY_LABEL = "discovered:ws:trades"

TradeSink = Callable[[list[tuple[Trade, Any]]], int]
WalletSink = Callable[[str], None]


def make_trades_handler(
    *,
    write_trades: TradeSink,
    observe_wallet: WalletSink,
    on_trades: Callable[[int, int, int], None],
) -> Callable[[Mapping[str, Any]], None]:
    """Build a frame handler that persists the tape and surfaces new wallets.

    ``on_trades`` receives ``(seen, written, newly_discovered)`` per frame so
    the caller can keep session totals without this module knowing about
    result objects. Discovery is counted on first sight within the handler's
    lifetime: a wallet that appears in a hundred trades is discovered once.
    """
    known: set[str] = set()

    def handle(message: Mapping[str, Any]) -> None:
        trades = parse_trades(message.get("data"))
        rows = require_list(message.get("data"), "ws.trades.data")
        written = write_trades(list(zip(trades, rows, strict=True)))
        discovered = 0
        for trade in trades:
            for wallet in trade.wallets:
                observe_wallet(wallet)
                if wallet not in known:
                    known.add(wallet)
                    discovered += 1
        on_trades(len(trades), written, discovered)

    return handle
