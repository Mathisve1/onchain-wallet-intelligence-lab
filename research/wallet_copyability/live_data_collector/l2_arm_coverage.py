"""How well the price series covered the window, and what it cost when it did not.

Arm B prices every copy from the last ``allMids`` quote no older than the
study's 15-minute bound, so a stretch of the window with no quote young enough
is a stretch in which no copy could be priced. Collection is operator-started
and bounded, so such stretches exist by construction; this module measures them
from the ``mids`` table the evidence file hashes, which is the only witness the
runner has. It never reads the session logs the collecting script keeps outside
the repository.

Two things it deliberately does not do. It does not sum unpriced time across
coins: one stretch with no poll leaves the same wall-clock hole in every coin at
once, so a sum would scale with the number of coins and could exceed the window.
And it does not lean on the span check, which reads the whole series including
rows on either side of the window and so cannot see a blackout inside it.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from src.live_data.storage import LiveDataStore


def mids_provenance(store: LiveDataStore, coins: Iterable[str], *, window: tuple[int, int], max_age_ms: int) -> dict:
    """How densely each coin's mid was sampled over the window, where the
    series has holes wider than the freshness bound, and by how many polls
    and sweeps."""
    start_ms, end_ms = window
    per_coin: dict[str, dict] = {}
    for coin in sorted(coins):
        times = [int(r["observed_at_ms"]) for r in store.connection.execute(
            "SELECT observed_at_ms FROM mids WHERE coin = ? AND observed_at_ms BETWEEN ? AND ? ORDER BY observed_at_ms",
            (coin, start_ms, end_ms),
        )]
        gaps = [later - earlier for earlier, later in zip(times, times[1:])]
        # The last quote before the window still prices the copies the window
        # opens with, for as long as the bound allows; without it the head of
        # the window would read as unpriced whenever polling began earlier.
        before = store.connection.execute(
            "SELECT MAX(observed_at_ms) AS t FROM mids WHERE coin = ? AND observed_at_ms < ?", (coin, start_ms)
        ).fetchone()["t"]
        per_coin[coin] = {
            "rows_in_window": len(times),
            "first_observed_ms": times[0] if times else None, "last_observed_ms": times[-1] if times else None,
            "last_observed_before_window_ms": int(before) if before is not None else None,
            "mean_spacing_ms": None if len(times) < 2 else int((times[-1] - times[0]) / (len(times) - 1)),
            "max_gap_ms": max(gaps) if gaps else None,
            "gaps_over_max_age": sum(1 for gap in gaps if gap > max_age_ms),
            "unpriced_ms": unpriced_ms(times, window=window, max_age_ms=max_age_ms, last_before=before),
        }

    def runs(mode: str) -> dict:
        row = store.connection.execute(
            "SELECT COUNT(*) AS n, MIN(started_at_ms) AS first, MAX(finished_at_ms) AS last "
            "FROM ingest_runs WHERE mode = ? AND status = 'completed'", (mode,)
        ).fetchone()
        return {"completed": int(row["n"]), "first_started_ms": row["first"], "last_finished_ms": row["last"]}

    return {"kind": "mids", "max_age_ms": max_age_ms, "window_ms": end_ms - start_ms, "sampled_by_coin": per_coin,
            "polls": runs("mids"), "sweeps": runs("sweep")}


def unpriced_ms(
    times: Sequence[int], *, window: tuple[int, int], max_age_ms: int, last_before: int | None = None
) -> int:
    """Wall-clock time inside the window with no quote fresh enough to price a copy.

    A quote at ``t`` prices every copy in ``[t, t + max_age_ms]``, so the
    priced part of the window is the union of those spans clipped to it, and
    what is left is unpriced. This measures the window's head and tail as
    well as the holes between two quotes: a series that stops days before the
    window ends is unpriced for those days, and one with no quote at all is
    unpriced throughout. The span check does not cover that, and cannot: it
    reads the whole series, including rows on either side of the window.
    """
    start_ms, end_ms = window
    if end_ms <= start_ms:
        return 0
    priced = 0
    cursor = start_ms
    for t in ([last_before] if last_before is not None else []) + [t for t in times if t <= end_ms]:
        covers_to = min(t + max_age_ms, end_ms)
        if covers_to > cursor:
            priced += covers_to - max(t, cursor)
            cursor = covers_to
        if cursor >= end_ms:
            break
    return (end_ms - start_ms) - priced


def unpriced_summary(provenance: Mapping[str, Any], *, benchmark_coin: str) -> dict | None:
    """What the window's unpriced time comes to, rolled up for the disclosure.

    ``None`` for a candle-priced arm: a candle series is fetched in one run
    after the fact, so a hole in it is a missing fetch, not unpriced time.

    There is no cross-coin total. One stretch with no poll leaves the same
    wall-clock hole in every coin at once, so a sum over coins would scale
    with the number of coins and could exceed the window itself. The figures
    that mean something are per coin: the benchmark's, and the worst.
    """
    if provenance.get("kind") != "mids":
        return None
    per_coin: Mapping[str, Mapping[str, Any]] = provenance["sampled_by_coin"]
    window_ms = provenance["window_ms"]
    affected = {coin: row for coin, row in per_coin.items() if row["unpriced_ms"] > 0}
    worst = max(sorted(affected), key=lambda coin: affected[coin]["unpriced_ms"], default=None)
    worst_ms = affected[worst]["unpriced_ms"] if worst is not None else 0
    benchmark = per_coin.get(benchmark_coin)
    return {
        "max_age_ms": provenance["max_age_ms"],
        "window_ms": window_ms,
        "coins": len(per_coin),
        "coins_with_unpriced_time": len(affected),
        "coins_share_one_figure": len(affected) > 1 and len({row["unpriced_ms"] for row in affected.values()}) == 1,
        "gaps_over_max_age_total": sum(row["gaps_over_max_age"] for row in per_coin.values()),
        "worst_coin": worst,
        "worst_coin_unpriced_ms": worst_ms,
        "worst_coin_share": _percent(worst_ms, window_ms),
        "benchmark_coin": benchmark_coin,
        "benchmark_in_scope": benchmark is not None,
        "benchmark_unpriced_ms": benchmark["unpriced_ms"] if benchmark is not None else None,
        "benchmark_share": _percent(benchmark["unpriced_ms"], window_ms) if benchmark is not None else None,
        "benchmark_rows_in_window": benchmark["rows_in_window"] if benchmark is not None else None,
    }


def _percent(part_ms: int, whole_ms: int) -> float | None:
    """Per cent of the window, to two places. Named apart from _share below,
    which formats a count against a count and would shadow this one."""
    return None if whole_ms <= 0 else round(100 * part_ms / whole_ms, 2)


def _hours(ms: int) -> str:
    """Milliseconds as the operator reads them, rounded before the unit is chosen."""
    if ms < 60_000:
        return "under a minute" if ms > 0 else "0"
    if round(ms / 60_000) < 60:
        return f"{round(ms / 60_000)} min"
    return f"{ms / 3_600_000:.1f} h"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"
