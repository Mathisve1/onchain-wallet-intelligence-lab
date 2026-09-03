"""Build simulator inputs from a live-data store.

This is the only module in the package that knows about SQLite or the
live-data schema, and it depends on ``src.live_data`` alone: still
deterministic, still network-free. It turns rows into the plain input types
and, just as importantly, turns ``ingest_runs`` coverage records into the
observed intervals the coverage ledger certifies from.

A run's coverage is trusted exactly as far as it goes. A backfill whose fills
were truncated at the page cap contributes an interval that ends at
``covered_until_ms``; a failed run contributes nothing; a watch session covers
its tracked wallets for the time it was connected.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from src.live_data.storage import LiveDataStore

from .coverage import CoverageLedger, ObservedInterval
from .inputs import (
    FundingEvent,
    FundingSchedule,
    LiquidityProfile,
    MarketData,
    PriceSeries,
    SourceFill,
)


def load_fills(store: LiveDataStore, wallets: Iterable[str] | None = None) -> dict[str, list[SourceFill]]:
    query = (
        "SELECT wallet_address, coin, trade_id, event_time_ms, side, price, size, fee, closed_pnl, crossed "
        "FROM fills"
    )
    params: tuple[Any, ...] = ()
    if wallets is not None:
        chosen = sorted(set(wallets))
        query += " WHERE wallet_address IN (%s)" % ",".join("?" * len(chosen))
        params = tuple(chosen)
    query += " ORDER BY event_time_ms, trade_id"
    result: dict[str, list[SourceFill]] = {}
    for row in store.connection.execute(query, params):
        fill = SourceFill(
            wallet=row["wallet_address"], coin=row["coin"], time_ms=row["event_time_ms"],
            side=row["side"], price=Decimal(row["price"]), size=Decimal(row["size"]),
            fee=Decimal(row["fee"]), closed_pnl=Decimal(row["closed_pnl"]), trade_id=row["trade_id"],
            crossed=None if row["crossed"] is None else bool(row["crossed"]),
        )
        result.setdefault(fill.wallet, []).append(fill)
    return result


def load_funding_truncation(store: LiveDataStore) -> dict[str, bool]:
    """Per wallet: did any completed backfill hit the venue's funding cap?

    Older run records predate the ``truncated_at_response_cap`` flag and say
    ``completed`` even when they received exactly the cap, so a full response
    is treated as truncated whichever way the record phrases it. A truncated
    wallet's funding cost is a lower bound and every result for it must say so.
    """
    truncated: dict[str, bool] = {}
    for run in store.connection.execute(
        "SELECT wallet_address, coverage FROM ingest_runs WHERE mode = 'backfill_wallet' AND status = 'completed'"
    ):
        if not run["coverage"]:
            continue
        funding = json.loads(run["coverage"]).get("funding", {})
        hit_cap = bool(funding.get("truncated_at_response_cap")) or funding.get("seen", 0) >= 500
        wallet = run["wallet_address"]
        truncated[wallet] = truncated.get(wallet, False) or hit_cap
    return truncated


def load_prices(store: LiveDataStore, coins: Iterable[str]) -> dict[str, PriceSeries]:
    """Mid series per coin from the ``mids`` table, keyed by observation time."""
    series: dict[str, PriceSeries] = {}
    for coin in sorted(set(coins)):
        rows = store.connection.execute(
            "SELECT observed_at_ms, mid FROM mids WHERE coin = ? ORDER BY observed_at_ms", (coin,)
        ).fetchall()
        series[coin] = PriceSeries(coin, ((r["observed_at_ms"], Decimal(r["mid"])) for r in rows))
    return series


def load_trade_prices(store: LiveDataStore, coins: Iterable[str]) -> dict[str, PriceSeries]:
    """Last-trade series per coin from the public tape; denser than mids.

    Several trades can share a millisecond; the last one in id order wins,
    which is the price a taker would have seen at that instant.
    """
    series: dict[str, PriceSeries] = {}
    for coin in sorted(set(coins)):
        last: dict[int, Decimal] = {}
        for r in store.connection.execute(
            "SELECT event_time_ms, price FROM trades WHERE coin = ? ORDER BY event_time_ms, trade_id",
            (coin,),
        ):
            last[r["event_time_ms"]] = Decimal(r["price"])
        series[coin] = PriceSeries(coin, last.items())
    return series


def load_fill_prices(store: LiveDataStore, coins: Iterable[str]) -> dict[str, PriceSeries]:
    """Price series per coin from every retained fill, whoever's it was.

    The public tape only exists while a session was connected, but backfilled
    fills reach back through the whole window and each one is a real traded
    price at a real time. Pooled across wallets they form a point-in-time
    series that covers the backfill period, which is what lets that period be
    scored at all. The last fill in a millisecond wins.
    """
    series: dict[str, PriceSeries] = {}
    for coin in sorted(set(coins)):
        last: dict[int, Decimal] = {}
        for r in store.connection.execute(
            "SELECT event_time_ms, price FROM fills WHERE coin = ? ORDER BY event_time_ms, trade_id",
            (coin,),
        ):
            last[r["event_time_ms"]] = Decimal(r["price"])
        series[coin] = PriceSeries(coin, last.items())
    return series


def load_funding_rates(store: LiveDataStore, coins: Iterable[str]) -> FundingSchedule:
    """Funding rates per coin, taken from any wallet's funding rows.

    The rate is a venue-wide fact per coin per hour, so one observation of it
    from any wallet is the rate every position paid or received.
    """
    wanted = set(coins)
    seen: dict[tuple[str, int], Decimal] = {}
    for r in store.connection.execute("SELECT coin, event_time_ms, funding_rate FROM funding"):
        if r["coin"] in wanted:
            seen[(r["coin"], r["event_time_ms"])] = Decimal(r["funding_rate"])
    return FundingSchedule(FundingEvent(coin, t, rate) for (coin, t), rate in seen.items())


def load_coverage(store: LiveDataStore) -> CoverageLedger:
    observed: list[ObservedInterval] = []
    for run in store.connection.execute("SELECT * FROM ingest_runs"):
        if run["status"] != "completed" or not run["coverage"]:
            continue
        coverage = json.loads(run["coverage"])
        if run["mode"] == "backfill_wallet":
            fills = coverage.get("fills", {})
            window = coverage.get("window", {})
            if not fills.get("attempted") or "start_time_ms" not in window:
                continue
            end = fills.get("covered_until_ms", window.get("end_time_ms"))
            complete = bool(fills.get("completed")) and end is not None
            observed.append(ObservedInterval(
                wallet=run["wallet_address"], start_ms=window["start_time_ms"],
                end_ms=end if end is not None else window["start_time_ms"],
                complete=complete, source=f"backfill:{run['run_id']}",
            ))
        elif run["mode"] == "watch" and run["finished_at_ms"]:
            for wallet in _watched_wallets(store, run):
                observed.append(ObservedInterval(
                    wallet=wallet, start_ms=run["started_at_ms"], end_ms=run["finished_at_ms"],
                    complete=True, source=f"watch:{run['run_id']}",
                ))
    return CoverageLedger(observed)


def _watched_wallets(store: LiveDataStore, run: Any) -> list[str]:
    """Wallets a watch session tracked: those it snapshotted during the run."""
    rows = store.connection.execute(
        "SELECT DISTINCT wallet_address FROM positions_snapshot WHERE ingested_at_ms BETWEEN ? AND ?",
        (run["started_at_ms"], run["finished_at_ms"]),
    ).fetchall()
    return [r["wallet_address"] for r in rows]


PRICE_SOURCES = {"fills": load_fill_prices, "trades": load_trade_prices, "mids": load_prices}


def build_market(
    store: LiveDataStore, coins: Iterable[str], liquidity: dict[str, LiquidityProfile], *,
    price_source: str = "fills",
) -> MarketData:
    """Assemble market data from one price source.

    ``fills`` is the default because it is the only source that spans the
    backfill window; ``trades`` and ``mids`` exist only while a session was
    connected.
    """
    if price_source not in PRICE_SOURCES:
        raise ValueError(f"price_source must be one of {sorted(PRICE_SOURCES)}")
    coins = sorted(set(coins))
    prices = PRICE_SOURCES[price_source](store, coins)
    return MarketData(prices=prices, funding=load_funding_rates(store, coins), liquidity=liquidity)


def open_store(path: Path | str) -> LiveDataStore:
    return LiveDataStore(path, create=False)
