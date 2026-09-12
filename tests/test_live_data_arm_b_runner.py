"""Arm B: forward, decisive, and blind until its window has closed.

A synthetic store as for arm A, but with the forward window ``[T0, T0+56d]``:
mids polled every five minutes, fills inside the window, and sweep coverage
rows certifying it. The runner must refuse before the ledger certifies the
window, price on mids, apply the decision rule, and report the survivorship
inflation against an arm A file.
"""

from __future__ import annotations

import contextlib
import json
import tempfile
import unittest
from pathlib import Path

from research.wallet_copyability.live_data_collector import arm_b_runner as runner
from research.wallet_copyability.live_data_collector import l2_arm_report as report
from research.wallet_copyability.live_data_collector import l2_arm_runner as core
from research.wallet_copyability.live_data_collector import l2_arm_statistics as stats
from src.copyability.cohort import cohort_hash
from src.copyability.loader import coverage_snapshot
from src.live_data.models import Fill, parse_funding
from src.live_data.storage import RUN_STATUS_COMPLETED, LiveDataStore

DAY = core.MILLISECONDS_PER_DAY
HOUR = 3_600_000
FIVE_MIN = 300_000
T0 = 2_000_000_000_000
PLAN = "1833f34"
COHORT = ["0x" + "11" * 20, "0x" + "22" * 20, "0x" + "33" * 20]
POOL_ONLY = ["0x" + "44" * 20, "0x" + "55" * 20]
START, END = runner.evaluation_window(T0)
C_START, C_END = core.characterisation_window(T0)


def _fill(wallet: str, tid: int, t: int, *, coin: str = "BTC", side: str = "B") -> tuple[Fill, dict]:
    payload = {
        "coin": coin, "px": "64000", "sz": "0.01", "side": side, "time": t, "startPosition": "0",
        "dir": "Open Long", "closedPnl": "0", "hash": "0x" + "cd" * 32, "oid": tid,
        "crossed": True, "fee": "0.05", "tid": tid, "feeToken": "USDC",
    }
    return Fill.parse(payload, wallet), payload


def _round_trips(wallet: str, start_ms: int, count: int, *, spacing_ms: int, tid_base: int, held_ms: int = HOUR):
    rows = []
    for i in range(count):
        base = start_ms + i * spacing_ms
        rows.append(_fill(wallet, tid_base + 2 * i, base))
        rows.append(_fill(wallet, tid_base + 2 * i + 1, base + held_ms, side="A"))
    return rows


def _funding(wallet: str, t: int, *, coin: str = "BTC"):
    payload = {"time": t, "delta": {"type": "funding", "coin": coin, "usdc": "-0.01",
                                     "szi": "0.01", "fundingRate": "0.0001"}}
    (delta,) = parse_funding([payload], wallet)
    return delta, payload


def _write_mids(store: LiveDataStore, start_ms: int, end_ms: int) -> None:
    """A mid every five minutes with a drifting level, so timing matters.

    Written in one transaction: 16k rows through ``write_mids`` is 16k commits.
    """
    rows = []
    t, index = start_ms, 0
    while t <= end_ms:
        mid = f"{64000 + (index % 500) * 0.4 + (index // 500) * 2:.2f}"
        rows.append(("BTC", t, mid, json.dumps({"BTC": mid}), t))
        t += FIVE_MIN
        index += 1
    with store.connection:
        store.connection.executemany(
            "INSERT INTO mids (coin, observed_at_ms, mid, raw_payload, ingested_at_ms) VALUES (?, ?, ?, ?, ?)", rows
        )


def _backfill(store: LiveDataStore, run_id: str, wallet: str) -> None:
    store.start_run(run_id, mode="backfill_wallet", started_at_ms=T0, wallet_address=wallet)
    store.finish_run(
        run_id, finished_at_ms=T0, status=RUN_STATUS_COMPLETED, records_seen=1, records_written=1,
        coverage={"window": {"start_time_ms": C_START - DAY, "end_time_ms": T0},
                  "fills": {"attempted": True, "completed": True, "truncated_at_page_cap": False, "covered_until_ms": T0},
                  "funding": {"attempted": True, "completed": True, "truncated_at_response_cap": False}},
    )


def _sweep(store: LiveDataStore, run_id: str, wallet: str, *, from_ms: int, until_ms: int) -> None:
    """A sweep_wallet row in the shape sweep.py writes, certifying [from, until]."""
    store.start_run(run_id, mode="sweep_wallet", started_at_ms=until_ms, wallet_address=wallet)
    store.finish_run(
        run_id, finished_at_ms=until_ms, status=RUN_STATUS_COMPLETED, records_seen=1, records_written=1,
        coverage={"window": {"start_time_ms": from_ms, "end_time_ms": until_ms},
                  "fills": {"attempted": True, "completed": True, "truncated_at_page_cap": False, "covered_until_ms": until_ms},
                  "funding": {"attempted": True, "completed": True, "truncated_at_response_cap": False}},
    )


class ArmBStoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.db = self.root / "live.sqlite3"
        patterns = {
            COHORT[0]: dict(start=START + DAY, count=20, spacing=2 * DAY, held=HOUR),
            COHORT[1]: dict(start=START + DAY + 9 * HOUR, count=20, spacing=2 * DAY, held=5 * HOUR),
            COHORT[2]: dict(start=START + 2 * DAY, count=24, spacing=2 * DAY, held=2 * HOUR),
            POOL_ONLY[0]: dict(start=START + DAY + 3 * HOUR, count=20, spacing=2 * DAY, held=3 * HOUR),
            POOL_ONLY[1]: dict(start=START + 3 * DAY, count=22, spacing=2 * DAY, held=HOUR),
        }
        with LiveDataStore(self.db) as store:
            _write_mids(store, T0, END + HOUR)
            for index, (wallet, p) in enumerate(patterns.items()):
                store.upsert_wallet(wallet, observed_at_ms=T0)
                rows = _round_trips(wallet, C_START + index * HOUR, 30, spacing_ms=DAY, tid_base=1000 * index)
                rows += _round_trips(wallet, p["start"], p["count"], spacing_ms=p["spacing"],
                                     tid_base=1000 * index + 100, held_ms=p["held"])
                store.write_fills(rows, source="test", ingested_at_ms=END)
                # Funding before T0 fixes the frozen scope; funding inside the
                # window is what the forward simulation actually pays.
                store.write_funding([_funding(wallet, C_START + i * HOUR) for i in range(1, 4)]
                                    + [_funding(wallet, START + i * HOUR) for i in range(1, 4)], ingested_at_ms=END)
                _backfill(store, f"backfill-{index}", wallet)
                self.certify(store, wallet, index, until_ms=END + HOUR)
        self.candles_json = self.root / "L2_ARM_A_CANDLES_001.json"
        self.candles_json.write_text(json.dumps({"per_coin": [{"coin": "BTC", "complete": True}]}), encoding="utf-8")
        self.cohort_json = self.root / "L2_COHORT_T0.json"
        self.cohort_json.write_text(json.dumps(self.record(COHORT)), encoding="utf-8")
        self.out = self.root / "L2_ARM_B_001.json"

    @staticmethod
    def certify(store: LiveDataStore, wallet: str, index: int, *, until_ms: int) -> None:
        # Two sweeps per wallet, [T0, mid] and [mid+1, until]: the shape sweep.py
        # writes when it resumes at latest_fill + 1 behind a page-cap cut.
        mid = T0 + 30 * DAY
        _sweep(store, f"sweep-{index}-1", wallet, from_ms=T0, until_ms=mid)
        _sweep(store, f"sweep-{index}-2", wallet, from_ms=mid + 1, until_ms=until_ms)

    def snapshot(self) -> dict:
        with LiveDataStore(self.db) as store:
            return coverage_snapshot(store, modes=core.L2_LEDGER_MODES, finished_by_ms=T0)

    def record(self, wallets, *, hard_stop: bool = False) -> dict:
        cohort = [] if hard_stop else sorted(w.lower() for w in wallets)
        return {
            "ledger_snapshot": self.snapshot(),
            "t0_ms": T0, "cohort": cohort, "cohort_sha256": cohort_hash(cohort), "plan_commit": PLAN,
            "hard_stop": hard_stop, "minimum_evaluable": 200,
            "stage_counts": {"discovered": 5, "evaluable": len(cohort)}, "per_wallet_reason": {"EVALUABLE": len(cohort)},
            "pool": sorted(w.lower() for w in COHORT + POOL_ONLY),
            "pool_sha256": cohort_hash(sorted(w.lower() for w in COHORT + POOL_ONLY)),
            "characterisation_window": {"start_ms": C_START, "end_ms": C_END, "days": 30.0},
            "scope": {"funding_coins": 1, "candle_complete_coins": 1, "excluded": [], "sources": {}},
        }

    def argv(self, *, arm_a: Path | None = None) -> list[str]:
        argv = ["--db", str(self.db), "--cohort", str(self.cohort_json), "--candles-json", str(self.candles_json),
                "--plan-commit", PLAN, "--out", str(self.out), "--overwrite", "--allow-underpowered-dry-run"]
        return argv + (["--arm-a-json", str(arm_a)] if arm_a else [])

    def run_main(self, argv=None):
        logged: list[str] = []
        return runner.main(argv or self.argv(), log=logged.append), logged

    def run_ok(self, argv=None) -> dict:
        code, logged = self.run_main(argv)
        self.assertEqual(code, 0, logged)
        return json.loads(self.out.read_text(encoding="utf-8"))


@contextlib.contextmanager
def patched_minimum(minimum: int):
    original = core.MINIMUM_EVALUATED
    core.MINIMUM_EVALUATED = minimum
    try:
        yield
    finally:
        core.MINIMUM_EVALUATED = original


class ArmBRunnerTests(ArmBStoreTestCase):
    def test_it_prices_on_mids_over_the_forward_window_and_applies_the_decision_rule(self) -> None:
        code, logged = self.run_main()
        self.assertEqual(code, 0, logged)
        r = json.loads(self.out.read_text(encoding="utf-8"))
        self.assertEqual((r["run_id"], r["arm"], r["variant"]), ("L2-ARM-B-001", "B", "B-56"))
        self.assertEqual(r["evaluation_window"], {"start_ms": T0, "end_ms": T0 + 56 * DAY, "days": "56"})
        self.assertEqual(r["price_source"]["kind"], "mids")
        self.assertEqual(r["price_source"]["max_age_ms"], 900_000)
        self.assertIn("polled allMids alone", r["price_source"]["deviation_from_plan_wording"])
        self.assertEqual(r["price_provenance"]["kind"], "mids")
        self.assertEqual(r["price_provenance"]["sweeps"]["completed"], 0)  # cohort sweep summaries, not the per-wallet rows
        btc = r["price_provenance"]["sampled_by_coin"]["BTC"]
        self.assertGreater(btc["rows_in_window"], 16_000)
        self.assertEqual((btc["mean_spacing_ms"], btc["max_gap_ms"], btc["gaps_over_max_age"]), (FIVE_MIN, FIVE_MIN, 0))
        self.assertEqual(btc["unpriced_ms"], 0)
        self.assertTrue(any("a quote no older than 15 min stood behind every instant" in n
                            for n in r["sample_limitations_disclosure"]), r["sample_limitations_disclosure"])
        self.assertTrue(r["price_series_span_by_coin"]["BTC"]["spans_window"])
        self.assertEqual(r["counts"], {"wallets": 3, "scored": 3, "refused": 0, "in_primary": 3})
        self.assertEqual(r["pool"]["size"], 5)
        self.assertEqual(r["pool"]["ledger_modes"], ["backfill_wallet", "sweep_wallet"])
        self.assertEqual(r["ledger_snapshot"]["max_finished_at_ms"], END + HOUR)
        self.assertTrue(r["closure"]["closed"])
        self.assertEqual(r["closure"]["wallets_without_closing_sweep"], [])
        self.assertEqual(r["closure"]["earliest_closing_sweep_ms"], END + HOUR)
        for wallet, peers in r["matched_peers_by_wallet"].items():
            self.assertEqual(set(peers["contributed"]), set(COHORT + POOL_ONLY) - {wallet})
            self.assertEqual(peers["latency_ms"], 30_000)
        self.assertNotEqual(r["primary"]["sd"], 0.0)
        # Under the minimum the arm is a case study: it decides nothing even
        # though it is the decisive arm.
        self.assertTrue(r["primary"]["case_study"])
        # The decisive arm's file carries no arm A reading label: its verdict
        # is the decision, and here there is none.
        self.assertIsNone(r["primary"]["reading"])
        self.assertEqual(r["primary"]["verdict_field"], "decision")
        self.assertIsNone(r["decision"])
        self.assertEqual(r["empirical_result_status"], "DRY_RUN_UNDERPOWERED")
        self.assertEqual(r["decisive_arm"], "B")
        self.assertIn("Decision rule", r["reading_rule"])
        self.assertTrue(any("out of sample" in s for s in r["sample_limitations_disclosure"]))
        # No arm A file: the block says so rather than going missing.
        self.assertEqual(r["survivorship_inflation"],
                         {"available": False, "arm_a_file": None, "reason": "no arm A file given"})
        self.assertRegex(logged[-1], r"^L2-ARM-B-001: wallets=3 scored=3 refused=0 in_primary=3 status=DRY_RUN_UNDERPOWERED file_sha256=[0-9a-f]{64}$")

    def test_it_refuses_before_the_window_is_certified_closed(self) -> None:
        with LiveDataStore(self.db) as store:
            store.connection.execute("DELETE FROM ingest_runs WHERE mode = 'sweep_wallet'")
            store.connection.commit()
            for index, wallet in enumerate(COHORT + POOL_ONLY):
                _sweep(store, f"early-{index}", wallet, from_ms=T0, until_ms=T0 + 30 * DAY)
        code, logged = self.run_main()
        self.assertEqual(code, 2)
        self.assertFalse(self.out.exists())
        self.assertIn("not closed", logged[0])

    def test_a_cohort_wallet_whose_closing_sweep_failed_is_excluded_not_a_wall(self) -> None:
        # The plan excludes and counts a wallet the ledger cannot certify. A
        # wallet the closing pass reached and could not collect is that case,
        # not a reason to withhold the decisive arm from the other 299.
        with LiveDataStore(self.db) as store:
            store.connection.execute(
                "DELETE FROM ingest_runs WHERE wallet_address = ? AND mode = 'sweep_wallet'", (COHORT[1],)
            )
            store.connection.commit()
            _sweep(store, "closing-ok-1", COHORT[1], from_ms=T0, until_ms=T0 + 30 * DAY)
            store.start_run("closing-failed-1", mode="sweep_wallet", started_at_ms=END + HOUR,
                            wallet_address=COHORT[1])
            store.finish_run("closing-failed-1", finished_at_ms=END + HOUR, status="failed",
                             records_seen=0, records_written=0, error_count=1, notes="RestError: 500")
        r = self.run_ok()
        self.assertTrue(r["closure"]["closed"])
        self.assertEqual(r["closure"]["wallets_whose_closing_sweep_failed"], [COHORT[1]])
        self.assertEqual(r["counts"], {"wallets": 3, "scored": 2, "refused": 1, "in_primary": 2})
        self.assertIn("not fully observed", r["refusals"][COHORT[1]])

    def test_the_closing_grace_is_an_input_and_is_recorded(self) -> None:
        with LiveDataStore(self.db) as store:  # the closing sweep finished five days late
            store.connection.execute(
                "UPDATE ingest_runs SET finished_at_ms = ? WHERE mode = 'sweep_wallet' AND finished_at_ms > ?",
                (END + 5 * DAY, END),
            )
            store.connection.commit()
        code, logged = self.run_main()
        self.assertEqual(code, 2)
        self.assertIn("closing grace", logged[0])
        self.assertIn("--closing-grace-days", logged[0])
        r = self.run_ok(self.argv() + ["--closing-grace-days", "7"])
        self.assertEqual(r["closure"]["closing_grace_days"], 7)
        self.assertEqual(r["pool"]["ledger_finished_by_ms"], END + 7 * DAY)

    def test_the_file_records_the_pool_the_freeze_named(self) -> None:
        r = self.run_ok()
        self.assertEqual(r["pool_record"], {"sha256": cohort_hash(sorted(w.lower() for w in COHORT + POOL_ONLY)),
                                            "size": 5})

    def test_a_cohort_wallet_without_a_closing_sweep_stops_the_read(self) -> None:
        # The pool-only wallets are closed, one cohort wallet is not: the
        # collection is still running, so nothing may be computed.
        with LiveDataStore(self.db) as store:
            store.connection.execute("DELETE FROM ingest_runs WHERE wallet_address = ? AND mode = 'sweep_wallet'",
                                     (COHORT[1],))
            store.connection.commit()
            _sweep(store, "partial-1", COHORT[1], from_ms=T0, until_ms=T0 + 30 * DAY)
        code, logged = self.run_main()
        self.assertEqual(code, 2)
        self.assertFalse(self.out.exists())
        self.assertIn("1 of 3 cohort wallets were not reached by a sweep", logged[0])

    def test_a_closed_sweep_that_could_not_certify_a_wallet_refuses_that_wallet_only(self) -> None:
        # Closed for every wallet, but one wallet's coverage has a hole: it is
        # refused and counted, and the arm is still read on the rest.
        with LiveDataStore(self.db) as store:
            store.connection.execute("DELETE FROM ingest_runs WHERE wallet_address = ? AND mode = 'sweep_wallet'",
                                     (COHORT[1],))
            store.connection.commit()
            _sweep(store, "holed-1", COHORT[1], from_ms=T0 + 2 * DAY, until_ms=END + HOUR)
        r = self.run_ok()
        self.assertEqual(r["counts"], {"wallets": 3, "scored": 2, "refused": 1, "in_primary": 2})
        self.assertIn("not fully observed", r["refusals"][COHORT[1]])
        self.assertTrue(r["closure"]["closed"])

    def test_funding_written_inside_the_forward_window_does_not_move_the_frozen_scope(self) -> None:
        before = self.run_ok()
        with LiveDataStore(self.db) as store:
            store.write_funding([_funding(COHORT[0], T0 + HOUR, coin="ETH")], ingested_at_ms=END)
        after = self.run_ok()
        self.assertEqual(after["scope"]["funding_coins"], ["BTC"])
        self.assertEqual(after["primary"]["d_by_wallet"], before["primary"]["d_by_wallet"])

    def test_the_span_rule_admits_the_freshness_bound_at_both_edges(self) -> None:
        self.assertEqual(self.run_ok()["price_series_span_rule"],
                         {"tolerance_ms": 900_000, "end_tolerance_ms": 900_000,
                          "rule": "first quote less than tolerance_ms after the window start, "
                                  "last quote at most end_tolerance_ms before the window end"})
        with LiveDataStore(self.db) as store:  # the last poll falls 10 minutes short of the end
            store.connection.execute("DELETE FROM mids WHERE observed_at_ms > ?", (END - 10 * 60_000,))
            store.connection.commit()
        self.assertTrue(self.run_ok()["price_series_span_by_coin"]["BTC"]["spans_window"])
        with LiveDataStore(self.db) as store:  # ... and 20 minutes short: outside the bound
            store.connection.execute("DELETE FROM mids WHERE observed_at_ms > ?", (END - 20 * 60_000,))
            store.connection.commit()
        code, logged = self.run_main()
        self.assertEqual(code, 2)
        self.assertIn("benchmark coin BTC has no price series spanning the window", logged[0])

    def arm_a_file(self, **overrides) -> Path:
        payload = {"arm": "A", "cohort_sha256": cohort_hash(sorted(w.lower() for w in COHORT)),
                   "plan_commit": PLAN, "empirical_result_status": "ARM_A_EARLY_READ_ONLY",
                   "primary": {"mean": 0.9, "reading": "ARM_A_NEGATIVE"}}
        payload.update(overrides)
        path = self.root / "L2_ARM_A_001.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_it_reports_the_survivorship_inflation_against_arm_a(self) -> None:
        code, logged = self.run_main(self.argv(arm_a=self.arm_a_file()))
        self.assertEqual(code, 0, logged)
        r = json.loads(self.out.read_text(encoding="utf-8"))
        inflation = r["survivorship_inflation"]
        self.assertTrue(inflation["available"])
        self.assertEqual(inflation["mean_d_a"], 0.9)
        self.assertEqual(inflation["arm_a_status"], "ARM_A_EARLY_READ_ONLY")
        self.assertAlmostEqual(inflation["inflation_points_per_14d"], round(0.9 - r["primary"]["mean"], 4), places=4)
        self.assertFalse(inflation["a_negative_b_positive"])  # a case study decides nothing

    def test_an_arm_a_file_that_is_not_this_cohorts_early_read_is_not_subtracted(self) -> None:
        cases = {
            "cohort_sha256 differs from arm B's": {"cohort_sha256": "0" * 64},
            "plan_commit differs from arm B's": {"plan_commit": "deadbeef"},
            "arm A status 'DRY_RUN_UNDERPOWERED' is not an early read of this cohort":
                {"empirical_result_status": "DRY_RUN_UNDERPOWERED"},
            "arm A status 'BROKE_SEE_WHAT_BROKE' is not an early read of this cohort":
                {"empirical_result_status": "BROKE_SEE_WHAT_BROKE"},
            "a checkpoint, not an evidence file": {"checkpoint": True},
            "not an arm A evidence file": {"arm": "B"},
        }
        for reason, overrides in cases.items():
            with self.subTest(reason=reason):
                code, logged = self.run_main(self.argv(arm_a=self.arm_a_file(**overrides)))
                self.assertEqual(code, 0, logged)
                inflation = json.loads(self.out.read_text(encoding="utf-8"))["survivorship_inflation"]
                self.assertFalse(inflation["available"])
                self.assertEqual(inflation["reason"], reason)

    def test_over_the_minimum_arm_b_writes_the_decision_the_rule_gives(self) -> None:
        # The decisive path: without this every arm B run in the suite is a
        # case study, and a wiring regression that never decides would pass.
        with patched_minimum(3):
            r = self.run_ok(self.argv(arm_a=self.arm_a_file()))
        self.assertFalse(r["primary"]["case_study"])
        self.assertEqual(r["empirical_result_status"], "ARM_B_DECIDED")
        self.assertIn(r["decision"], {"GO_TO_ENTITY_CLUSTER_RESEARCH", "NO_GO_NO_COPYABLE_ALPHA", "REPAIR_AND_RERUN"})
        self.assertEqual(r["decision"], stats.decision_for(r["primary"]))
        self.assertIsNone(r["primary"]["reading"])
        inflation = r["survivorship_inflation"]
        self.assertEqual(inflation["a_negative_b_positive"],
                         r["decision"] == "GO_TO_ENTITY_CLUSTER_RESEARCH")

    def test_a_pool_that_is_only_the_cohort_breaks_the_measure_and_decides_nothing(self) -> None:
        # What a sweep over the cohort alone would produce: peers drawn from
        # the cohort, so mean d cancels the cohort's common return.
        with LiveDataStore(self.db) as store:
            store.connection.execute(
                "DELETE FROM ingest_runs WHERE wallet_address IN (?, ?)", (POOL_ONLY[0], POOL_ONLY[1])
            )
            store.connection.commit()
        with patched_minimum(3):
            code, logged = self.run_main()
        self.assertEqual(code, 3, logged)
        r = json.loads(self.out.read_text(encoding="utf-8"))
        self.assertEqual((r["pool"]["size"], r["pool"]["non_cohort_wallets_in_pool"]), (3, 0))
        self.assertEqual(r["empirical_result_status"], "BROKE_SEE_WHAT_BROKE")
        self.assertIsNone(r["decision"])
        self.assertIn("the peer pool is the cohort itself", r["what_broke"][0])

    def test_arm_b_has_no_candle_provenance_and_arm_a_has_no_decision(self) -> None:
        self.run_main()
        r = json.loads(self.out.read_text(encoding="utf-8"))
        self.assertNotIn("fetch_runs", r["price_provenance"])
        self.assertEqual(r["price_source"]["kind"], "mids")


class UnpricedTimeTests(unittest.TestCase):
    """What the window's unpriced time is, in the file and in the note.

    The figure is the evidence file's own: measured from the ``mids`` table
    the database holds, never from the session logs the collecting script
    keeps outside the repository. It is wall-clock time inside the window
    with no quote young enough to price a copy, the head and the tail of the
    window included, because the span check cannot cover those: it reads the
    whole series, rows on either side of the window included.
    """

    BOUND = 900_000
    WINDOW = (1_000_000_000_000, 1_000_000_000_000 + 56 * DAY)

    def unpriced(self, times, *, last_before=None, window=None) -> int:
        return report.unpriced_ms(times, window=window or self.WINDOW, max_age_ms=self.BOUND, last_before=last_before)

    def provenance(self, **by_coin) -> dict:
        start, end = self.WINDOW
        return {"kind": "mids", "max_age_ms": self.BOUND, "window_ms": end - start,
                "sampled_by_coin": {coin: {"unpriced_ms": unpriced, "rows_in_window": rows,
                                           "gaps_over_max_age": 0, "max_gap_ms": None}
                                    for coin, (unpriced, rows) in by_coin.items()},
                "polls": {}, "sweeps": {}}

    def note(self, summary, *, stale: int = 0, catch_up: int = 0, of_n: int = 3) -> str:
        notes = report.limitations(
            arm="B", survivorship_block={"stopped": 0, "cohort": 3, "faded": 0, "faded_judged": 3},
            disclosures={"of_n": of_n, "liquidity_assumed": 0, "funding_incomplete": 0,
                         "stale_price_skips_present": stale, "catch_up_fills_present": catch_up},
            pool_size=5, pool_cohort=3, cohort_size=3, unpriced=summary,
        )
        coverage = [n for n in notes if n.startswith("Price coverage")]
        self.assertEqual(len(coverage), 1, notes)
        return coverage[0]

    def test_a_quote_prices_the_bound_after_it_and_a_hole_costs_what_it_exceeds(self) -> None:
        start, end = self.WINDOW
        grid = list(range(start, end + 1, FIVE_MIN))
        self.assertEqual(self.unpriced(grid), 0)
        # One 20-minute hole in an otherwise dense series leaves 5 minutes;
        # a hole of exactly the bound leaves none.
        holed = [t for t in grid if not start < t < start + 20 * 60_000]
        self.assertEqual(self.unpriced(holed), 5 * 60_000)
        self.assertEqual(self.unpriced([t for t in grid if not start < t < start + self.BOUND]), 0)

    def test_the_head_and_the_tail_of_the_window_are_measured(self) -> None:
        start, end = self.WINDOW
        self.assertEqual(self.unpriced(list(range(start + 3 * DAY, end + 1, FIVE_MIN))), 3 * DAY)
        self.assertEqual(
            self.unpriced(list(range(start + 3 * DAY, end + 1, FIVE_MIN)), last_before=start - 60_000),
            3 * DAY - (self.BOUND - 60_000))
        self.assertEqual(self.unpriced(list(range(start, end - 2 * DAY, FIVE_MIN))),
                         2 * DAY + FIVE_MIN - self.BOUND)
        self.assertEqual(self.unpriced([]), end - start)
        self.assertEqual(self.unpriced([], last_before=start - 60_000), (end - start) - (self.BOUND - 60_000))

    def test_rows_outside_the_window_do_not_hide_a_blackout_inside_it(self) -> None:
        # The shape the verification found: a series that stops before the window
        # ends and resumes after it satisfies the span check, which reads the
        # whole table. The coverage figure must see the blackout anyway.
        start, end = self.WINDOW
        with contextlib.closing(LiveDataStore(":memory:")) as store:
            rows = [("BTC", t, "1", "{}", t) for t in range(start - HOUR, end - 3 * DAY, FIVE_MIN)]
            rows += [("BTC", t, "1", "{}", t) for t in range(end + HOUR, end + 2 * HOUR, FIVE_MIN)]
            with store.connection:
                store.connection.executemany(
                    "INSERT INTO mids (coin, observed_at_ms, mid, raw_payload, ingested_at_ms) VALUES (?, ?, ?, ?, ?)",
                    rows)
            provenance = report.mids_provenance(store, ["BTC"], window=self.WINDOW, max_age_ms=self.BOUND)
        btc = provenance["sampled_by_coin"]["BTC"]
        self.assertEqual(btc["unpriced_ms"], 3 * DAY + FIVE_MIN - self.BOUND)
        self.assertEqual(btc["last_observed_before_window_ms"], start - FIVE_MIN)
        self.assertEqual(provenance["window_ms"], end - start)
        self.assertIn("Worst: BTC", self.note(report.unpriced_summary(provenance, benchmark_coin="BTC")))

    def test_an_empty_or_one_row_series_is_never_read_as_full_coverage(self) -> None:
        start, _ = self.WINDOW
        for label, times in (("empty", []), ("one row", [start + DAY])):
            with self.subTest(series=label):
                summary = report.unpriced_summary(self.provenance(BTC=(self.unpriced(times), len(times))),
                                                  benchmark_coin="BTC")
                note = self.note(summary, stale=3, of_n=3)
                self.assertIn("had time inside the", note)
                self.assertNotIn("stood behind every instant", note)
                self.assertGreater(summary["worst_coin_unpriced_ms"], 50 * DAY)

    def test_the_clean_note_is_only_earned_when_no_coin_has_unpriced_time(self) -> None:
        summary = report.unpriced_summary(self.provenance(BTC=(0, 16_000), ETH=(0, 16_000)), benchmark_coin="BTC")
        note = self.note(summary, stale=1, catch_up=2, of_n=3)
        self.assertIn("over the whole 1344.0 h window, and on every one of the 2 coins evaluated", note)
        self.assertIn("a quote no older than 15 min stood behind every instant", note)
        self.assertIn("priced from a quote inside the bound at its own action time", note)
        self.assertIn("1 of 3 in the primary had a copy or an end-of-window mark resting on a stale quote", note)
        self.assertIn("2 had a catch-up fill", note)

    def test_the_note_reports_per_coin_wall_clock_time_and_never_a_cross_coin_sum(self) -> None:
        summary = report.unpriced_summary(
            self.provenance(**{f"C{i:02d}": (9 * HOUR, 16_000) for i in range(24)}), benchmark_coin="C00")
        self.assertTrue(summary["coins_share_one_figure"])
        note = self.note(summary)
        self.assertIn("24 coins of 24 evaluated had time inside the 1344.0 h window", note)
        self.assertIn("Worst: C00, 9.0 h, 0.67 percent of the window", note)
        self.assertIn("Every coin with unpriced time carries the same figure", note)
        self.assertIn("not added across coins", note)
        self.assertNotIn("216.0 h", note)
        self.assertNotIn("unpriced_ms_total", str(summary))

    def test_the_benchmark_is_named_with_its_share_and_its_degenerate_cases_do_not_raise(self) -> None:
        summary = report.unpriced_summary(self.provenance(BTC=(3 * HOUR, 16_000), ETH=(9 * HOUR, 16_000)),
                                          benchmark_coin="BTC")
        self.assertIn("the benchmark BTC carries 3.0 h, 0.22 percent of the window", self.note(summary))
        summary = report.unpriced_summary(self.provenance(BTC=(50 * DAY, 0), ETH=(9 * HOUR, 16_000)),
                                          benchmark_coin="BTC")
        self.assertIn("the benchmark BTC has no quote inside the window at all", self.note(summary))
        summary = report.unpriced_summary(self.provenance(ETH=(9 * HOUR, 16_000)), benchmark_coin="BTC")
        self.assertFalse(summary["benchmark_in_scope"])
        self.assertIn("the benchmark BTC is not among the coins evaluated", self.note(summary))

    def test_the_note_states_what_an_unpriced_fill_does_and_that_funding_is_invisible(self) -> None:
        note = self.note(report.unpriced_summary(self.provenance(BTC=(3 * HOUR, 16_000)), benchmark_coin="BTC"))
        self.assertIn("re-aligns at the next priced fill as a catch-up trade", note)
        self.assertIn("round trip the source completed inside it is missed entirely", note)
        self.assertIn("average entry price and counted as priced, so it does not appear in the funding "
                      "disclosure below", note)
        # Two claims the verification refuted: the span check does not cover the
        # edges, and the runner cannot observe how the data was collected.
        self.assertNotIn("span check", note)
        self.assertNotIn("operator-started", note)

    def test_durations_are_rounded_before_the_unit_is_chosen(self) -> None:
        self.assertEqual([report._hours(ms) for ms in (0, 1, 59_999, 60_000, 3_599_999, 3_600_000)],
                         ["0", "under a minute", "under a minute", "1 min", "1.0 h", "1.0 h"])
        self.assertEqual(report._hours(self.BOUND), "15 min")

    def test_arm_a_carries_no_price_coverage_note(self) -> None:
        self.assertIsNone(report.unpriced_summary({"kind": "candles"}, benchmark_coin="BTC"))
        notes = report.limitations(
            arm="A", survivorship_block={"stopped": 1, "cohort": 3, "faded": 0, "faded_judged": 3},
            disclosures={"of_n": 3, "liquidity_assumed": 0, "funding_incomplete": 0,
                         "stale_price_skips_present": 0, "catch_up_fills_present": 0},
            pool_size=5, pool_cohort=3, cohort_size=3, unpriced=None)
        self.assertFalse([n for n in notes if n.startswith("Price coverage")], notes)


class DecisionRuleTests(unittest.TestCase):
    @staticmethod
    def _primary(lower, upper, *, case_study=False, measurable=True):
        return {"ci95": [lower, upper], "case_study": case_study, "measurable": measurable}

    def test_b_decides_by_the_frozen_rule(self) -> None:
        self.assertEqual(stats.decision_for(self._primary(0.5, 1.2)), "GO_TO_ENTITY_CLUSTER_RESEARCH")
        self.assertEqual(stats.decision_for(self._primary(0.51, 1.2)), "GO_TO_ENTITY_CLUSTER_RESEARCH")
        self.assertEqual(stats.decision_for(self._primary(-0.3, 0.49)), "NO_GO_NO_COPYABLE_ALPHA")
        self.assertEqual(stats.decision_for(self._primary(0.1, 0.9)), "REPAIR_AND_RERUN")
        self.assertEqual(stats.decision_for(self._primary(-0.3, 0.5)), "REPAIR_AND_RERUN")

    def test_a_case_study_or_an_unmeasurable_primary_decides_nothing(self) -> None:
        self.assertIsNone(stats.decision_for(self._primary(0.6, 1.0, case_study=True)))
        self.assertIsNone(stats.decision_for({"ci95": None, "case_study": False, "measurable": False}))
        # Zero variance: the bounds coincide and the interval means nothing.
        self.assertIsNone(stats.decision_for(self._primary(0.7, 0.7, measurable=False)))
        self.assertEqual(stats.MINIMUM_EVALUATED, 200)

    def test_the_inflation_names_a_negative_b_positive_from_the_reading_and_the_decision(self) -> None:
        negative = {"arm": "A", "primary": {"mean": -0.2, "reading": "ARM_A_NEGATIVE"}}
        go = {"mean": 0.8, "ci95": [0.55, 1.05], "case_study": False, "measurable": True}
        out = stats.inflation_block(negative, None, go, "GO_TO_ENTITY_CLUSTER_RESEARCH", file_name="a.json")
        self.assertTrue(out["a_negative_b_positive"])
        self.assertEqual(out["inflation_points_per_14d"], -1.0)
        # The flag follows the written reading and the written decision, never
        # the two point estimates: B positive but not a GO is not the case.
        repair = stats.inflation_block(negative, None, go, "REPAIR_AND_RERUN", file_name="a.json")
        self.assertFalse(repair["a_negative_b_positive"])
        inconclusive = {"arm": "A", "primary": {"mean": 0.1, "reading": "ARM_A_INCONCLUSIVE"}}
        self.assertFalse(stats.inflation_block(inconclusive, None, go, "GO_TO_ENTITY_CLUSTER_RESEARCH",
                                               file_name="a.json")["a_negative_b_positive"])


if __name__ == "__main__":
    unittest.main()
