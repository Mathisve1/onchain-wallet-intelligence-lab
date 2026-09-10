"""Arm B collection: one operator-started sweep over the frozen cohort.

Split out of :mod:`.ingest` to keep both modules inside the 500-line cap the
read-only guard enforces. The mixin is composed into
:class:`~.ingest.IngestOrchestrator`, so ``sweep`` and ``poll_mids`` are
methods on the orchestrator like every other collection entry point and share
its store, REST client, clock and run-id factory.

Cadence, from ``L2_ANALYSIS_PLAN.md`` arm B and phase 4 of the build plan:

- Copy latency is *simulated* from the venue's own fill timestamps, never from
  how quickly this code noticed a fill. A sweep therefore does not have to run
  at copy speed: every few hours is enough for fills and funding, because a
  fill fetched six hours late carries the same ``time`` field it would have
  carried six seconds late.
- Prices are the one series that must be sampled in real time, since a mid is
  only observable while it is the mid. That is ``poll_mids``, weight 2, which
  the plan wants roughly every five minutes and which is deliberately
  independent of the fill sweep.
- Neither loop lives here. This module contains no scheduler, no sleep and no
  repeating loop over time: a sweep walks the cohort once and returns, and the
  operator starts each one. An unattended loop under ``src/`` would be a
  process that keeps reaching the venue with nobody watching it, which is what
  the owner's constraint forbids.

Coverage shape: a sweep writes one summary ``sweep`` run row carrying the
totals and the per-wallet digest, plus one ``sweep_wallet`` row per wallet in
the shape ``backfill_wallet`` uses. The summary alone would be unreadable to
everything downstream: the coverage ledger
(:func:`src.copyability.loader.load_coverage`) and the health script both key
on ``wallet_address`` and on ``coverage["window"]``, so a sweep that wrote only
the summary would certify no interval at all and would look, to the ledger,
like a window nobody ever observed.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Sequence

from .candles import DEFAULT_MAX_PAGES
from .config import normalize_coin, normalize_wallet_address
from .hyperliquid_rest import HyperliquidRestClient
from .models import parse_all_mids
from .storage import COVERAGE_FILLS_BOUND_RULE, RUN_STATUS_COMPLETED, RUN_STATUS_FAILED, LiveDataStore
from .watch import IngestError

#: How many wallets of the caller-ordered cohort get a position snapshot. The
#: owner's rule is the top ten only: ``clearinghouseState`` has no history, so
#: a snapshot is worth taking for the wallets whose positions will actually be
#: inspected, and taking 600 of them per sweep would spend weight on state
#: nobody reads.
DEFAULT_SNAPSHOT_TOP = 10

#: Errors kept in the run's ``notes``. The full per-wallet detail is in the
#: coverage block; notes only has to make a failure visible in ``status``.
MAX_NOTED_ERRORS = 5


class SweepMixin:
    """``poll_mids`` and ``sweep`` for the ingest orchestrator.

    The attributes below are provided by the orchestrator this mixin is
    composed into; they are declared so the module reads on its own and type
    checking does not have to guess at them.
    """

    _rest: HyperliquidRestClient
    _store: LiveDataStore
    _clock_ms: Callable[[], int]
    _run_id_factory: Callable[[], str]
    #: Supplied by the orchestrator: request cost so far, for the run record.
    _requests_coverage: Callable[[], dict[str, int]]
    #: Supplied by the orchestrator: the paging walks and the snapshot write.
    _collect_fills: Callable[..., tuple[int, int, int, int, bool, int]]
    _collect_funding: Callable[..., tuple[int, int, bool, int]]
    _write_snapshot: Callable[[str], tuple[Any, int]]

    def poll_mids(self, coins: Sequence[str]) -> dict[str, Any]:
        """Sample ``allMids`` once and store the mids for ``coins``.

        One request, weight 2, dict-shaped so it carries no row surcharge.
        Only the requested coins are written: the venue answers with every
        listed asset, and storing all of them would fill the price series with
        coins outside the study's scope.

        Returns the ``mids`` coverage block with the run id added.
        """
        requested = tuple(normalize_coin(coin) for coin in coins)
        if not requested:
            raise IngestError("poll_mids requires at least one coin")

        run_id = self._run_id_factory()
        started_at = self._clock_ms()
        self._store.start_run(run_id, mode="mids", started_at_ms=started_at)
        try:
            payload = self._rest.request("allMids")
            mids = parse_all_mids(payload)
            selected = {coin: mids[coin] for coin in requested if coin in mids}
            missing = sorted(coin for coin in requested if coin not in mids)
            observed_at = self._clock_ms()
            result = self._store.write_mids(
                selected, payload, observed_at_ms=observed_at, ingested_at_ms=observed_at
            )
        except Exception as exc:
            self._store.finish_run(
                run_id,
                finished_at_ms=self._clock_ms(),
                status=RUN_STATUS_FAILED,
                records_seen=0,
                records_written=0,
                error_count=1,
                notes=f"{type(exc).__name__}: {exc}",
                coverage={
                    "mids": {"coins_requested": len(requested), "coins_written": 0, "missing": []},
                    "requests": self._requests_coverage(),
                },
            )
            raise

        block = {
            "coins_requested": len(requested),
            "coins_written": result.written,
            "missing": missing,
        }
        self._store.finish_run(
            run_id,
            finished_at_ms=self._clock_ms(),
            status=RUN_STATUS_COMPLETED,
            records_seen=result.seen,
            records_written=result.written,
            coverage={"mids": block, "requests": self._requests_coverage()},
        )
        return {"run_id": run_id, **block}

    def _sweep_wallet(
        self, address: str, *, t0_ms: int, end_time_ms: int, max_pages: int
    ) -> tuple[dict[str, Any], dict[str, Any], tuple[int, int], tuple[int, int, int]]:
        """Collect one wallet's new fills and funding.

        Both walks resume from what is already stored and fall back to the
        cohort's T0 for a wallet with nothing stored yet, so a sweep asks only
        for the window it does not already hold. Returns the wallet's summary
        entry, the coverage block for its own ``sweep_wallet`` run row, its
        ``(fills_seen, fills_written)`` and its
        ``(funding_seen, funding_written, funding_pages)``.
        """
        latest_fill = self._store.latest_fill_time_ms(address)
        covered = self._latest_fills_covered_until_ms(address)
        # Resume from the earlier of the newest stored fill and the last
        # millisecond a completed walk proved observed. A fill another source
        # wrote (a watch session) must not carry the resume past a range no
        # walk requested, and a walk cut at the page cap is proven only to
        # the millisecond before its last fill, so that millisecond is asked
        # for again. Idempotent writes absorb the overlap either way.
        resume_points = [bound + 1 for bound in (latest_fill, covered) if bound is not None]
        # Never past the window's own end: a wallet already covered through it
        # has nothing new to ask for, and a start after the end is a request
        # the venue refuses, which would fail the wallet for the whole sweep.
        fills_from = min(t0_ms if not resume_points else min(resume_points), end_time_ms)
        (
            fills_pages,
            fills_seen,
            fills_written,
            forced,
            fills_exhausted,
            covered_until_ms,
        ) = self._collect_fills(
            address, start_time_ms=fills_from, end_time_ms=end_time_ms, max_pages=max_pages
        )

        latest_funding = self._store.latest_funding_time_ms(address)
        funding_from = t0_ms if latest_funding is None else latest_funding + 1
        funding_seen, funding_written, funding_exhausted, funding_pages = self._collect_funding(
            address, start_time_ms=funding_from, max_pages=max_pages
        )

        entry = {
            "fills_from_ms": fills_from,
            "fills_seen": fills_seen,
            "fills_exhausted": fills_exhausted,
            "funding_from_ms": funding_from,
            "funding_seen": funding_seen,
            "funding_exhausted": funding_exhausted,
            "status": "ok",
        }
        # The same shape ``backfill_wallet`` writes, so the coverage ledger and
        # the health script can read a sweep without knowing it was one. In
        # particular ``covered_until_ms`` is kept rather than discarded: a walk
        # the page cap stopped covers only its prefix, and dropping the bound
        # would let the uncovered tail read as a period with no trading.
        coverage = {
            "window": {"start_time_ms": fills_from, "end_time_ms": end_time_ms},
            "fills": {
                "attempted": True,
                "completed": fills_exhausted,
                "truncated_at_page_cap": not fills_exhausted,
                "covered_until_ms": covered_until_ms,
                "forced_cursor_advances": forced,
                "bound_rule": COVERAGE_FILLS_BOUND_RULE,
                "pages": fills_pages,
                "seen": fills_seen,
                "written": fills_written,
            },
            "funding": {
                "attempted": True,
                "completed": funding_exhausted,
                "truncated_at_response_cap": not funding_exhausted,
                "pages": funding_pages,
                "seen": funding_seen,
                "written": funding_written,
                "start_time_ms": funding_from,
            },
        }
        return (
            entry,
            coverage,
            (fills_seen, fills_written),
            (funding_seen, funding_written, funding_pages),
        )

    def _latest_fills_covered_until_ms(self, address: str) -> int | None:
        """The furthest millisecond a completed walk proved observed for the wallet."""
        best: int | None = None
        for run in self._store.connection.execute(
            "SELECT coverage FROM ingest_runs WHERE wallet_address = ? AND status = ? "
            "AND mode IN ('backfill_wallet', 'sweep_wallet')",
            (address, RUN_STATUS_COMPLETED),
        ):
            if not run["coverage"]:
                continue
            coverage = json.loads(run["coverage"])
            fills = coverage.get("fills", {})
            bound = fills.get("covered_until_ms")
            if bound is None and fills.get("completed"):
                bound = coverage.get("window", {}).get("end_time_ms")
            if bound is not None and (best is None or int(bound) > best):
                best = int(bound)
        return best

    def _run_sweep_wallet(
        self, address: str, *, t0_ms: int, end_time_ms: int, max_pages: int
    ) -> tuple[dict[str, Any], tuple[int, int], tuple[int, int, int]]:
        """Sweep one wallet under its own ``sweep_wallet`` run row.

        The row is closed either way: completed with the coverage block, or
        failed with the error in its notes, and the exception is re-raised for
        the caller to count. A wallet whose failure left no row at all would be
        indistinguishable downstream from a wallet nobody swept.
        """
        run_id = self._run_id_factory()
        started_ms = self._clock_ms()
        self._store.start_run(
            run_id, mode="sweep_wallet", started_at_ms=started_ms, wallet_address=address
        )
        try:
            entry, coverage, fills, funding = self._sweep_wallet(
                address, t0_ms=t0_ms, end_time_ms=end_time_ms, max_pages=max_pages
            )
        except Exception as exc:
            self._store.finish_run(
                run_id,
                finished_at_ms=self._clock_ms(),
                status=RUN_STATUS_FAILED,
                records_seen=0,
                records_written=0,
                error_count=1,
                notes=f"{type(exc).__name__}: {exc}",
                coverage={
                    "window": {"start_time_ms": t0_ms, "end_time_ms": end_time_ms},
                    "fills": {"attempted": True, "completed": False},
                    "requests": self._requests_coverage(),
                },
            )
            raise
        coverage["requests"] = self._requests_coverage()
        self._store.finish_run(
            run_id,
            finished_at_ms=self._clock_ms(),
            status=RUN_STATUS_COMPLETED,
            records_seen=fills[0] + funding[0],
            records_written=fills[1] + funding[1],
            coverage=coverage,
        )
        entry["run_id"] = run_id
        return entry, fills, funding

    def sweep(
        self,
        wallets: Sequence[str],
        coins: Sequence[str],
        *,
        t0_ms: int,
        snapshot_top: int = DEFAULT_SNAPSHOT_TOP,
        max_pages: int = DEFAULT_MAX_PAGES,
    ) -> dict[str, Any]:
        """One bounded arm B pass: mids once, then every wallet in order.

        A wallet that fails is counted and skipped, not raised: one address
        that the venue refuses must not cost the sweep the other 599, and the
        failure is recorded per wallet so the gap is visible later instead of
        looking like a wallet that stopped trading.

        Position snapshots are taken in a second pass over the first
        ``snapshot_top`` wallets of the list the caller supplied. The caller
        owns the order, so "top" means whatever the cohort file says it means.
        """
        addresses = [normalize_wallet_address(wallet) for wallet in wallets]
        if not addresses:
            raise IngestError("sweep requires at least one wallet")
        if len(set(addresses)) != len(addresses):
            raise IngestError("sweep requires distinct wallets")
        if t0_ms <= 0:
            raise IngestError("t0_ms must be a positive millisecond timestamp")
        if max_pages <= 0:
            raise IngestError("max_pages must be positive")
        if snapshot_top < 0:
            raise IngestError("snapshot_top must not be negative")
        requested_coins = tuple(normalize_coin(coin) for coin in coins)
        if not requested_coins:
            raise IngestError("sweep requires at least one coin for the mid sample")

        run_id = self._run_id_factory()
        started_ms = self._clock_ms()
        self._store.start_run(run_id, mode="sweep", started_at_ms=started_ms)
        summary: dict[str, Any] = {
            "t0_ms": t0_ms,
            "wallets": len(addresses),
            "wallets_failed": 0,
            "fills_seen": 0,
            "fills_written": 0,
            "funding_seen": 0,
            "funding_written": 0,
            "funding_pages": 0,
            "snapshots": 0,
            "started_ms": started_ms,
            "finished_ms": None,
        }
        per_wallet: dict[str, Any] = {}
        try:
            mids = self.poll_mids(requested_coins)
        except Exception as exc:
            summary["finished_ms"] = self._clock_ms()
            self._store.finish_run(
                run_id,
                finished_at_ms=summary["finished_ms"],
                status=RUN_STATUS_FAILED,
                records_seen=0,
                records_written=0,
                error_count=1,
                notes=f"mids: {type(exc).__name__}: {exc}",
                coverage={
                    "sweep": summary,
                    "per_wallet": per_wallet,
                    "requests": self._requests_coverage(),
                },
            )
            raise

        failed: list[str] = []
        for address in addresses:
            self._store.upsert_wallet(address, observed_at_ms=self._clock_ms())
            try:
                entry, fills, funding = self._run_sweep_wallet(
                    address, t0_ms=t0_ms, end_time_ms=started_ms, max_pages=max_pages
                )
            except Exception as exc:
                failed.append(f"{address}: {type(exc).__name__}: {exc}")
                per_wallet[address] = {"status": f"{type(exc).__name__}: {exc}"}
                continue
            summary["fills_seen"] += fills[0]
            summary["fills_written"] += fills[1]
            summary["funding_seen"] += funding[0]
            summary["funding_written"] += funding[1]
            summary["funding_pages"] += funding[2]
            per_wallet[address] = entry

        for address in addresses[:snapshot_top]:
            try:
                self._write_snapshot(address)
            except Exception as exc:
                note = f"{address}: snapshot: {type(exc).__name__}: {exc}"
                failed.append(note)
                entry = per_wallet.setdefault(address, {})
                entry["status"] = f"snapshot: {type(exc).__name__}: {exc}"
                continue
            summary["snapshots"] += 1

        failed_addresses = {note.split(":", 1)[0] for note in failed}
        summary["wallets_failed"] = len(failed_addresses)
        summary["finished_ms"] = self._clock_ms()
        notes = None if not failed else "; ".join(failed[:MAX_NOTED_ERRORS])
        self._store.finish_run(
            run_id,
            finished_at_ms=summary["finished_ms"],
            status=RUN_STATUS_COMPLETED,
            records_seen=summary["fills_seen"] + summary["funding_seen"],
            records_written=summary["fills_written"] + summary["funding_written"],
            error_count=len(failed_addresses),
            notes=notes,
            coverage={
                "sweep": summary,
                "per_wallet": per_wallet,
                "requests": self._requests_coverage(),
            },
        )
        return {"run_id": run_id, "mids": mids, "sweep": summary, "per_wallet": per_wallet}
