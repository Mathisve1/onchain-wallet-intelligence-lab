"""Tests for the L2 cohort pipeline collector scripts (phase 5).

No network: the tape session is a fake runner, the backfill is a fake
orchestrator that records its calls, and the freeze reads a temporary
:class:`~src.live_data.storage.LiveDataStore` populated through its own write
methods. Nothing here reaches the venue and nothing here scores a wallet.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from research.wallet_copyability.live_data_collector.cohort_pipeline import (
    MILLISECONDS_PER_DAY,
    UNMEASURED_COINS,
    characterise,
    covered_wallets,
    main,
)
from research.wallet_copyability.live_data_collector.cohort_pipeline_freeze import (
    FreezeInputError,
    MINIMUM_EVALUABLE,
    build_scope,
    candle_complete_coins,
    characterisation_window,
    freeze,
    funding_coins_in_db,
)
from src.live_data.models import Fill, FundingDelta, parse_funding
from src.copyability.cohort import cohort_hash
from src.live_data.storage import RUN_STATUS_COMPLETED, LiveDataStore

D = Decimal
DAY = MILLISECONDS_PER_DAY
T0 = 2_000_000_000_000

EVAL_WALLET = "0x" + "11" * 20
MAKER_WALLET = "0x" + "22" * 20
QUIET_WALLET = "0x" + "33" * 20


def _silent(_message: str) -> None:
    """Swallow the progress lines the commands print."""


class RecordingSleep:
    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


class FakeBackfillResult:
    """The subset of ``WalletBackfillResult`` the pipeline reads."""

    def __init__(self, wallet: str, *, fills: int = 10, funding: int = 4) -> None:
        self.run_id = f"run-{wallet[-4:]}"
        self.wallet_address = wallet
        self.pages = 1
        self.fills_seen = fills
        self.fills_written = fills
        self.funding_seen = funding
        self.funding_written = funding
        self.snapshot_taken = True
        self.window_exhausted = True
        self.covered_until_ms = T0
        self.funding_exhausted = False


class FakeOrchestrator:
    """Records every ``backfill_wallet`` call and answers from a script."""

    def __init__(self, *, raise_for: set[str] = frozenset()) -> None:
        self.calls: list[tuple[str, int]] = []
        self._raise_for = raise_for
        self.consumed_weight = 0

    def backfill_wallet(self, wallet: str, days: int) -> FakeBackfillResult:
        self.calls.append((wallet, days))
        self.consumed_weight += 20
        if wallet in self._raise_for:
            raise RuntimeError(f"HTTP 429 for {wallet}")
        return FakeBackfillResult(wallet)


class CharacteriseTests(unittest.TestCase):
    def test_it_pauses_between_wallets_but_not_before_the_first(self) -> None:
        sleep = RecordingSleep()
        orchestrator = FakeOrchestrator()
        wallets = [EVAL_WALLET, MAKER_WALLET, QUIET_WALLET]
        report = characterise(
            orchestrator, wallets, days=90, pause_seconds=1.0, sleep=sleep, log=_silent
        )
        self.assertEqual(sleep.calls, [1.0, 1.0], "expected one pause fewer than wallets")
        self.assertEqual([call[1] for call in orchestrator.calls], [90, 90, 90])
        self.assertEqual(report["totals"]["attempted"], 3)
        self.assertEqual(report["totals"]["consumed_weight"], 60)
        self.assertEqual(report["totals"]["funding_truncated"], 3)

    def test_one_failing_wallet_does_not_stop_the_pass(self) -> None:
        orchestrator = FakeOrchestrator(raise_for={MAKER_WALLET})
        report = characterise(
            orchestrator,
            [EVAL_WALLET, MAKER_WALLET, QUIET_WALLET],
            sleep=RecordingSleep(),
            log=_silent,
        )
        statuses = [row["status"] for row in report["wallets"]]
        self.assertEqual(statuses, ["completed", "failed", "completed"])
        self.assertIn("RuntimeError: HTTP 429", report["wallets"][1]["error"])
        self.assertEqual(report["totals"]["failed"], 1)
        self.assertEqual(report["totals"]["completed"], 2)

    def test_resume_skips_a_wallet_and_spends_no_pause_on_it(self) -> None:
        sleep = RecordingSleep()
        orchestrator = FakeOrchestrator()
        report = characterise(
            orchestrator,
            [EVAL_WALLET, MAKER_WALLET],
            skip={EVAL_WALLET},
            sleep=sleep,
            log=_silent,
        )
        self.assertEqual([call[0] for call in orchestrator.calls], [MAKER_WALLET])
        self.assertEqual(sleep.calls, [], "a skipped wallet must not consume a pause")
        self.assertEqual(report["wallets"][0]["status"], "skipped")
        self.assertEqual(report["totals"]["skipped"], 1)


def _fill(wallet: str, tid: int, t: int, *, coin: str = "BTC", crossed: bool = True,
          fee: str = "0.05", pnl: str = "1", side: str = "B") -> tuple[Fill, dict]:
    payload = {
        "coin": coin, "px": "100", "sz": "1", "side": side, "time": t, "startPosition": "0",
        "dir": "Open Long", "closedPnl": pnl, "hash": "0x" + "cd" * 32, "oid": tid,
        "crossed": crossed, "fee": fee, "tid": tid, "feeToken": "USDC",
    }
    return Fill.parse(payload, wallet), payload


def _funding(wallet: str, t: int, coin: str) -> tuple[FundingDelta, dict]:
    payload = {
        "time": t,
        "delta": {"type": "funding", "coin": coin, "usdc": "-0.1", "szi": "1",
                  "fundingRate": "0.0001"},
    }
    (delta,) = parse_funding([payload], wallet)
    return delta, payload


def _directional(wallet: str, start: int, *, coin: str = "BTC") -> list[tuple[Fill, dict]]:
    """Twenty taker round trips held half an hour each: plainly directional."""
    rows: list[tuple[Fill, dict]] = []
    for i in range(20):
        base = start + i * 3_600_000
        rows.append(_fill(wallet, 2 * i, base, coin=coin, pnl="0"))
        rows.append(_fill(wallet, 2 * i + 1, base + 1_800_000, coin=coin, side="A", pnl="1"))
    return rows


def _resting(wallet: str, start: int) -> list[tuple[Fill, dict]]:
    """Resting, two-sided, ten-second holds: a probable market maker."""
    rows: list[tuple[Fill, dict]] = []
    for i in range(20):
        base = start + i * 60_000
        rows.append(_fill(wallet, 1000 + 2 * i, base, crossed=False, pnl="0"))
        rows.append(
            _fill(wallet, 1000 + 2 * i + 1, base + 10_000, crossed=False, side="A", pnl="1")
        )
    return rows


CANDLE_POST_CHECK = {
    "per_coin": [
        {"coin": "BTC", "rows": 4992, "max_gap_ms": 900_000, "complete": True},
        {"coin": "DOGE", "rows": 12, "max_gap_ms": 3_600_000, "complete": False},
    ],
    "out_of_scope": ["DOGE"],
}


class FreezeWindowTests(unittest.TestCase):
    def test_the_window_is_the_oldest_thirty_days_of_the_backfill(self) -> None:
        start, end = characterisation_window(T0, backfill_days=90, characterisation_days=30)
        self.assertEqual(start, T0 - 90 * DAY)
        self.assertEqual(end, T0 - 60 * DAY)
        self.assertEqual(start, 1_992_224_000_000)
        self.assertEqual(end, 1_994_816_000_000)

    def test_the_hard_stop_minimum_is_the_plan_minimum(self) -> None:
        self.assertEqual(MINIMUM_EVALUABLE, 200)


class FreezeStoreTestCase(unittest.TestCase):
    """A temporary store holding one directional and one resting wallet."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.db = self.root / "live.sqlite3"
        self.window = characterisation_window(T0)
        start = self.window[0] + 1_000

        with LiveDataStore(self.db) as store:
            store.write_fills(_directional(EVAL_WALLET, start), source="test", ingested_at_ms=T0)
            store.write_fills(_resting(MAKER_WALLET, start), source="test", ingested_at_ms=T0)
            store.write_funding(
                [_funding(EVAL_WALLET, start, "BTC"), _funding(EVAL_WALLET, start + 1, "DOGE")],
                ingested_at_ms=T0,
            )
            # What a real store holds beside the fills: one completed backfill
            # per candidate covering the whole characterisation window. The
            # freeze reads the coverage ledger, and a candidate with no
            # certified window is excluded before it is characterised.
            for index, wallet in enumerate((EVAL_WALLET, MAKER_WALLET, QUIET_WALLET)):
                self._record_backfill(store, f"backfill-{index}", wallet, covered_until_ms=T0)
            # The mids poller runs before the freeze: arm B's first quote must
            # sit within the freshness bound of T0 and cannot be collected
            # afterwards, so the freeze refuses a T0 the poller has not reached.
            store.write_mids({"BTC": "64000"}, {"BTC": "64000"}, observed_at_ms=T0 - 60_000,
                             ingested_at_ms=T0 - 60_000)

        self.candles_json = self.root / "L2_ARM_A_CANDLES_001.json"
        self.candles_json.write_text(json.dumps(CANDLE_POST_CHECK), encoding="utf-8")

        self.candidates_json = self.root / "L2_DISCOVERY_001.json"
        self.candidates_json.write_text(
            json.dumps({"candidates": [EVAL_WALLET, MAKER_WALLET, QUIET_WALLET]}),
            encoding="utf-8",
        )

    def _record_backfill(
        self, store: LiveDataStore, run_id: str, wallet: str, *, covered_until_ms: int
    ) -> None:
        """A completed backfill_wallet run in the shape the collector writes."""
        start_ms = self.window[0] - DAY
        complete = covered_until_ms >= T0
        store.start_run(run_id, mode="backfill_wallet", started_at_ms=T0, wallet_address=wallet)
        store.finish_run(
            run_id, finished_at_ms=T0, status=RUN_STATUS_COMPLETED,
            records_seen=1, records_written=1,
            coverage={
                "window": {"start_time_ms": start_ms, "end_time_ms": T0},
                "fills": {"attempted": True, "completed": complete,
                          "truncated_at_page_cap": not complete,
                          "covered_until_ms": covered_until_ms},
            },
        )

    def freeze_argv(self, out: Path, *, minimum: int | None = None) -> list[str]:
        argv = [
            "freeze",
            "--db", str(self.db),
            "--t0-ms", str(T0),
            "--plan-commit", "1833f34",
            "--characterisation-days", "30",
            "--candidates", str(self.candidates_json),
            "--candles-json", str(self.candles_json),
            "--funding-coins-from-db",
            "--out", str(out),
        ]
        if minimum is not None:
            argv += ["--minimum", str(minimum)]
        return argv


class FreezeScopeTests(FreezeStoreTestCase):
    def test_the_funding_set_comes_from_the_rows_actually_collected(self) -> None:
        with LiveDataStore(self.db, create=False) as store:
            self.assertEqual(funding_coins_in_db(store), frozenset({"BTC", "DOGE"}))

    def test_only_coins_the_post_check_marked_complete_are_candle_complete(self) -> None:
        self.assertEqual(candle_complete_coins(CANDLE_POST_CHECK), frozenset({"BTC"}))

    def test_a_coin_needs_funding_and_candles_and_no_exclusion(self) -> None:
        scope, record = build_scope(
            funding={"BTC", "DOGE"},
            candles={"BTC"},
            excluded=UNMEASURED_COINS,
            funding_source="database:funding rows",
            candle_source="post_check:file",
        )
        self.assertTrue(scope.in_scope("BTC"))
        self.assertFalse(scope.in_scope("DOGE"), "no complete candle series")
        self.assertFalse(scope.in_scope("xyz:CRWV"))
        self.assertEqual(record["funding_coins"], 2)
        self.assertEqual(record["candle_complete_coins"], 1)
        self.assertEqual(record["excluded"], sorted(UNMEASURED_COINS))
        self.assertEqual(record["sources"]["funding"], "database:funding rows")


class FreezeSelectionTests(FreezeStoreTestCase):
    def _freeze(self, minimum: int) -> dict:
        scope, scope_record = build_scope(
            funding={"BTC", "DOGE"}, candles={"BTC"}, excluded=UNMEASURED_COINS,
            funding_source="database:funding rows", candle_source="post_check:file",
        )
        with LiveDataStore(self.db, create=False) as store:
            record, selection = freeze(
                store,
                t0_ms=T0,
                plan_commit="1833f34",
                scope=scope,
                scope_record=scope_record,
                window=self.window,
                candidates=[EVAL_WALLET, MAKER_WALLET, QUIET_WALLET],
                minimum=minimum,
            )
        self.assertEqual(selection.evaluable, (EVAL_WALLET,))
        return record

    def test_the_record_carries_the_window_the_counts_and_the_reasons(self) -> None:
        record = self._freeze(minimum=1)
        self.assertEqual(record["characterisation_window"]["start_ms"], T0 - 90 * DAY)
        self.assertEqual(record["characterisation_window"]["end_ms"], T0 - 60 * DAY)
        self.assertEqual(record["stage_counts"]["discovered"], 3)
        self.assertEqual(record["stage_counts"]["probable_market_maker"], 1)
        self.assertEqual(record["stage_counts"]["insufficient_fills"], 1)
        self.assertEqual(record["stage_counts"]["evaluable"], 1)
        self.assertEqual(record["per_wallet_reason"]["EVALUABLE"], 1)
        self.assertEqual(record["cohort"], [EVAL_WALLET])
        self.assertFalse(record["hard_stop"])

    def test_a_candidate_with_no_fills_is_still_counted_as_discovered(self) -> None:
        record = self._freeze(minimum=1)
        self.assertEqual(record["per_wallet_reason"]["INSUFFICIENT_FILLS"], 1)

    def test_below_the_minimum_the_record_hard_stops_with_an_empty_cohort(self) -> None:
        record = self._freeze(minimum=200)
        self.assertTrue(record["hard_stop"])
        self.assertEqual(record["cohort"], [])
        self.assertEqual(record["evaluable_count"], 1)


class FreezeMidsPreconditionTests(FreezeStoreTestCase):
    """Arm B's first quote is a T0-day precondition, not a day-56 discovery."""

    def test_a_t0_the_mids_poller_has_not_reached_is_refused(self) -> None:
        with LiveDataStore(self.db) as store:
            store.connection.execute("DELETE FROM mids")
            store.connection.commit()
        out = self.root / "freeze.json"
        logged: list[str] = []
        with self.assertRaises(FreezeInputError) as caught:
            main(self.freeze_argv(out, minimum=1), log=logged.append)
        self.assertIn("start the mids poll before freezing", str(caught.exception))
        self.assertFalse(out.exists())

    def test_a_mid_after_t0_does_not_satisfy_it(self) -> None:
        with LiveDataStore(self.db) as store:
            store.connection.execute("DELETE FROM mids")
            store.write_mids({"BTC": "64000"}, {"BTC": "64000"}, observed_at_ms=T0 + 1,
                             ingested_at_ms=T0 + 1)
        with self.assertRaises(FreezeInputError):
            main(self.freeze_argv(self.root / "freeze.json", minimum=1), log=_silent)

    def test_the_record_carries_the_characterised_pool_and_the_first_mid(self) -> None:
        out = self.root / "freeze.json"
        main(self.freeze_argv(out, minimum=1), log=_silent)
        record = json.loads(out.read_text(encoding="utf-8"))
        # Every candidate the freeze judged, cohort member or not: only a
        # swept wallet can be certified over arm B's window, and the sweep
        # needs the list at T0.
        self.assertEqual(record["pool"], sorted([EVAL_WALLET, MAKER_WALLET, QUIET_WALLET]))
        self.assertEqual(record["pool_sha256"], cohort_hash(record["pool"]))
        self.assertGreaterEqual(len(record["pool"]), len(record["cohort"]))
        self.assertEqual(record["benchmark_first_mid_ms"], T0 - 60_000)


class FreezeCoverageTests(FreezeStoreTestCase):
    """The freeze reads the coverage ledger before it characterises anyone."""

    def test_a_backfill_that_stopped_inside_the_window_excludes_the_wallet(self) -> None:
        """Regression: the freeze never consulted the ledger, so a wallet whose
        backfill was cut by the page cap partway through the characterisation
        window was classified on the fragment that had been collected."""
        halfway = (self.window[0] + self.window[1]) // 2
        with LiveDataStore(self.db) as store:
            store.connection.execute(
                "DELETE FROM ingest_runs WHERE wallet_address = ?", (EVAL_WALLET,)
            )
            store.connection.commit()
            self._record_backfill(store, "truncated", EVAL_WALLET, covered_until_ms=halfway)

        out = self.root / "freeze.json"
        code = main(self.freeze_argv(out, minimum=1), log=_silent)
        record = json.loads(out.read_text(encoding="utf-8"))
        # The only evaluable wallet is now unobserved, so the freeze hard-stops
        # - and says why in the counts rather than reporting it as idle.
        self.assertEqual(code, 2)
        self.assertTrue(record["hard_stop"])
        self.assertEqual(record["stage_counts"]["window_unobserved"], 1)
        self.assertEqual(record["stage_counts"]["insufficient_fills"], 1)  # QUIET_WALLET, as before
        self.assertEqual(record["evaluable_count"], 0)


class FreezeCommandTests(FreezeStoreTestCase):
    def test_it_exits_zero_and_writes_the_record_when_the_cohort_is_large_enough(self) -> None:
        out = self.root / "L2_COHORT_T0.json"
        lines: list[str] = []
        code = main(self.freeze_argv(out, minimum=1), log=lines.append)
        self.assertEqual(code, 0)
        record = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(record["cohort"], [EVAL_WALLET])
        self.assertEqual(record["plan_commit"], "1833f34")
        self.assertEqual(record["scope"]["sources"]["funding"], "database:funding rows")
        self.assertIn(f"cohort_sha256: {record['cohort_sha256']}", lines)
        self.assertIn("plan_commit: 1833f34", lines)

    def test_it_exits_two_on_the_hard_stop_and_still_writes_the_file(self) -> None:
        out = self.root / "L2_COHORT_T0.json"
        lines: list[str] = []
        code = main(self.freeze_argv(out), log=lines.append)
        self.assertEqual(code, 2)
        self.assertTrue(out.exists(), "the counts must survive a hard stop")
        record = json.loads(out.read_text(encoding="utf-8"))
        self.assertTrue(record["hard_stop"])
        self.assertIn("HARD_STOP: 1 evaluable wallets, minimum 200", lines)

    def test_a_missing_post_check_falls_back_to_the_named_coins_and_says_so(self) -> None:
        out = self.root / "L2_COHORT_T0.json"
        argv = self.freeze_argv(out, minimum=1)
        argv[argv.index("--candles-json") + 1] = str(self.root / "absent.json")
        argv += ["--candle-complete-coins", "BTC"]
        self.assertEqual(main(argv, log=_silent), 0)
        record = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(record["scope"]["sources"]["candles"],
                         "argument:--candle-complete-coins (post-check file absent.json absent)")
        self.assertEqual(record["cohort"], [EVAL_WALLET])

    def test_the_evidence_file_is_byte_stable_across_two_runs(self) -> None:
        first = self.root / "first.json"
        second = self.root / "second.json"
        self.assertEqual(main(self.freeze_argv(first, minimum=1), log=_silent), 0)
        self.assertEqual(main(self.freeze_argv(second, minimum=1), log=_silent), 0)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertTrue(first.read_bytes().endswith(b"\n"))


class ResumeCoverageTests(unittest.TestCase):
    def test_only_a_completed_backfill_covering_the_window_lets_a_wallet_be_skipped(self) -> None:
        now = T0
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "live.sqlite3"
            with LiveDataStore(db) as store:
                coverage = {
                    "window": {"start_time_ms": now - 95 * DAY, "end_time_ms": now - DAY,
                               "days": 90},
                    "fills": {"attempted": True, "completed": True,
                              "truncated_at_page_cap": False, "covered_until_ms": now - DAY},
                }
                store.start_run("covered", mode="backfill_wallet",
                                started_at_ms=now - DAY, wallet_address=EVAL_WALLET)
                store.finish_run("covered", finished_at_ms=now - DAY,
                                 status=RUN_STATUS_COMPLETED, records_seen=1,
                                 records_written=1, coverage=coverage)
                skip = covered_wallets(
                    store,
                    [EVAL_WALLET, MAKER_WALLET],
                    now_ms=now,
                    days=90,
                    grace_ms=2 * DAY,
                )
        self.assertEqual(skip, {EVAL_WALLET})


if __name__ == "__main__":
    unittest.main()
