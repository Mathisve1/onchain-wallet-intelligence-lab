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
from typing import Any, Iterable, Sequence

from src.live_data.ingest import MAX_FUNDING_PER_RESPONSE
from src.live_data.storage import LiveDataStore

from .coverage import CoverageLedger, ObservedInterval
# Re-exported: it moved next to the simulator that consumes it, but the
# loader is where callers building study inputs expect to find it.
from .execution import replay_positions  # noqa: F401
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

    Records that carry ``truncated_at_response_cap`` are believed: since
    ``_collect_funding`` gained pagination, ``seen`` is the sum across every
    page, so a wallet with 500 or more funding rows collected *completely*
    would otherwise be disclosed as truncated in every result it appears in.

    Only records predating that flag fall back to the size test, where a
    response at exactly the cap was the only evidence of truncation there was.
    A truncated wallet's funding cost is a lower bound and every result for it
    must say so.
    """
    truncated: dict[str, bool] = {}
    for run in store.connection.execute(
        "SELECT wallet_address, coverage FROM ingest_runs WHERE mode = 'backfill_wallet' AND status = 'completed'"
    ):
        if not run["coverage"]:
            continue
        funding = json.loads(run["coverage"]).get("funding", {})
        if "truncated_at_response_cap" in funding:
            hit_cap = bool(funding["truncated_at_response_cap"])
        else:
            hit_cap = funding.get("seen", 0) >= MAX_FUNDING_PER_RESPONSE
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


def load_fill_prices(
    store: LiveDataStore, coins: Iterable[str], *, exclude_wallet: str | None = None
) -> dict[str, PriceSeries]:
    """Price series per coin from retained fills, whoever's they were.

    The public tape only exists while a session was connected, but backfilled
    fills reach back through the whole window and each one is a real traded
    price at a real time. Pooled across wallets they form a point-in-time
    series that covers the backfill period. The last fill in a millisecond wins.

    ``exclude_wallet`` leaves the scored wallet's own fills out. With them in,
    a copy of a fill on a coin nobody else traded would be priced at the
    source's own fill price at every latency, and the latency grid would
    measure nothing. A series built this way is still not independent of the
    sample as a whole; only a polled tape is, and L2 uses one.
    """
    series: dict[str, PriceSeries] = {}
    for coin in sorted(set(coins)):
        last: dict[int, Decimal] = {}
        query = "SELECT event_time_ms, price FROM fills WHERE coin = ?"
        params: tuple[Any, ...] = (coin,)
        if exclude_wallet is not None:
            query += " AND wallet_address != ?"
            params = (coin, exclude_wallet)
        for r in store.connection.execute(query + " ORDER BY event_time_ms, trade_id", params):
            last[r["event_time_ms"]] = Decimal(r["price"])
        series[coin] = PriceSeries(coin, last.items())
    return series


def load_candle_prices(
    store: LiveDataStore, coins: Iterable[str], *, interval: str = "15m"
) -> dict[str, PriceSeries]:
    """Close series per coin from the ``candles`` table, at each candle's close.

    A candle's close is only known once the candle has closed, so the point is
    stamped at ``close_time_ms``. Stamping it at the open would let a decision
    inside the candle read a price the market had not yet printed.
    """
    series: dict[str, PriceSeries] = {}
    for coin in sorted(set(coins)):
        rows = store.connection.execute(
            "SELECT close_time_ms, close FROM candles WHERE coin = ? AND interval = ? "
            "ORDER BY open_time_ms",
            (coin, interval),
        ).fetchall()
        series[coin] = PriceSeries(coin, ((r["close_time_ms"], Decimal(r["close"])) for r in rows))
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
            # A walk stopped by the page cap still collected every fill up to
            # covered_until_ms, so that prefix is fully observed and certifiable;
            # only the tail beyond it is unknown. A record with neither a
            # completion flag nor a covered-until bound proves nothing.
            start = window["start_time_ms"]
            end = fills.get("covered_until_ms", window.get("end_time_ms") if fills.get("completed") else None)
            # A forced cursor advance skipped fills at one exact millisecond,
            # so the walk has a hole it can name. Newer records already bound
            # covered_until_ms before the first one; records written before
            # that fix carry the over-claiming bound, and certifying them
            # would hand the simulator an interval with a known gap in it --
            # precisely what this ledger exists to prevent.
            if end is not None and fills.get("forced_cursor_advances", 0) and fills.get("completed"):
                end = None
            if end is not None and end < start:
                # The bound falls before the window even opened: nothing here
                # was observed contiguously, so record no interval at all.
                continue
            observed.append(ObservedInterval(
                wallet=run["wallet_address"], start_ms=start,
                end_ms=end if end is not None else start,
                complete=end is not None, source=f"backfill:{run['run_id']}",
            ))
        elif run["mode"] == "watch" and run["finished_at_ms"]:
            # A session that reconnected has unobserved gaps it did not time;
            # its interval is therefore not complete. Reconnect counts live in
            # the notes of older records and in coverage for newer ones.
            reconnected = _reconnects(run, coverage) > 0
            for wallet in _watched_wallets(coverage):
                observed.append(ObservedInterval(
                    wallet=wallet, start_ms=run["started_at_ms"], end_ms=run["finished_at_ms"],
                    complete=not reconnected, source=f"watch:{run['run_id']}",
                ))
    return CoverageLedger(observed)


def _watched_wallets(coverage: dict) -> list[str]:
    """Wallets a watch session subscribed to, from its own coverage record.

    Only the tracked list counts. Inferring from snapshots written during the
    run would credit a wallet whose backfill happened to run at the same time
    with coverage the websocket never gave it.
    """
    tracked = coverage.get("positions", {}).get("tracked_wallets")
    return list(tracked) if isinstance(tracked, list) else []


def _reconnects(run: Any, coverage: dict) -> int:
    recorded = coverage.get("connection", {}).get("reconnects")
    if isinstance(recorded, int):
        return recorded
    notes = run["notes"] or ""
    marker = "reconnects: "
    if marker in notes:
        try:
            return int(notes.split(marker, 1)[1].split(";")[0].strip())
        except ValueError:
            return 1
    return 0


PRICE_SOURCES = {
    "fills": load_fill_prices, "trades": load_trade_prices, "mids": load_prices,
    "candles": load_candle_prices,
}


def build_market(
    store: LiveDataStore, coins: Iterable[str], liquidity: dict[str, LiquidityProfile], *,
    price_source: str = "fills", exclude_wallet: str | None = None,
    candle_interval: str = "15m",
) -> MarketData:
    """Assemble market data from one price source.

    ``fills`` is the default because it is the only source that spans the
    backfill window; ``trades`` and ``mids`` exist only while a session was
    connected. ``candles`` spans the window too and is independent of every
    wallet in the sample. ``exclude_wallet`` applies to the fills source only
    and should name the wallet being scored; it is ignored elsewhere.

    ``candle_interval`` picks which candle series the ``candles`` source reads,
    and is ignored by every other source. A coarser interval leaves longer
    stretches with no fresh quote, so a catch-up entry or a copy can land far
    from the price that actually traded; a finer one only exists if it was
    ingested.
    """
    if price_source not in PRICE_SOURCES:
        raise ValueError(f"price_source must be one of {sorted(PRICE_SOURCES)}")
    coins = sorted(set(coins))
    if price_source == "fills":
        prices = load_fill_prices(store, coins, exclude_wallet=exclude_wallet)
    elif price_source == "candles":
        prices = load_candle_prices(store, coins, interval=candle_interval)
    else:
        prices = PRICE_SOURCES[price_source](store, coins)
    return MarketData(prices=prices, funding=load_funding_rates(store, coins), liquidity=liquidity)


def open_store(path: Path | str) -> LiveDataStore:
    return LiveDataStore(path, create=False)
