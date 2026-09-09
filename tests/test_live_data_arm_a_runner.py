"""The arm A runner scores a frozen cohort on candles and reads itself by the fixed rule.

Everything here is synthetic and offline: a temporary store holding three
cohort wallets with distinguishable activity, two more characterised wallets
that are only in the peer pool, one coin with a complete 15-minute candle
series over the arm A window, funding rows, and the backfill coverage a real
store carries. The runner must verify the freeze record, refuse an
underpowered cohort unless told this is a dry run, write the evidence file,
decide nothing, and print counts only.
"""

from __future__ import annotations

import json
import math
import statistics
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from research.wallet_copyability.live_data_collector import l2_arm_report as report
from research.wallet_copyability.live_data_collector import arm_a_runner as runner
from research.wallet_copyability.live_data_collector import l2_arm_runner as core
from research.wallet_copyability.live_data_collector import l2_arm_statistics as stats
from src.copyability.cohort import cohort_hash
from src.copyability.inputs import SourceFill
from src.live_data.models import Candle, Fill, parse_funding
from src.live_data.storage import RUN_STATUS_COMPLETED, LiveDataStore

DAY = runner.MILLISECONDS_PER_DAY
HOUR = 3_600_000
FIFTEEN_MIN = 900_000
T0 = 2_000_000_000_000
PLAN = "1833f34"
COHORT = ["0x" + "11" * 20, "0x" + "22" * 20, "0x" + "33" * 20]
POOL_ONLY = ["0x" + "44" * 20, "0x" + "55" * 20]
START, END = runner.evaluation_window(T0)
C_START, C_END = runner.characterisation_window(T0)


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


def _candles(start_ms: int, end_ms: int, *, coin: str = "BTC"):
    """A complete 15-minute series whose close drifts, so timing matters."""
    rows, t, index = [], start_ms, 0
    while t <= end_ms:
        close = f"{64000 + (index % 400) * 0.5 + (index // 400) * 3:.2f}"
        payload = {"t": t, "T": t + FIFTEEN_MIN - 1, "s": coin, "i": "15m", "o": close,
                   "h": close, "l": close, "c": close, "v": "1", "n": 1}
        rows.append((Candle.parse(payload), payload))
        t += FIFTEEN_MIN
        index += 1
    return rows


def _funding(wallet: str, t: int, *, coin: str = "BTC"):
    payload = {"time": t, "delta": {"type": "funding", "coin": coin, "usdc": "-0.01",
                                     "szi": "0.01", "fundingRate": "0.0001"}}
    (delta,) = parse_funding([payload], wallet)
    return delta, payload


def _coverage(store: LiveDataStore, run_id: str, wallet: str, *, covered_until_ms: int) -> None:
    complete = covered_until_ms >= T0
    store.start_run(run_id, mode="backfill_wallet", started_at_ms=T0, wallet_address=wallet)
    store.finish_run(
        run_id, finished_at_ms=T0, status=RUN_STATUS_COMPLETED, records_seen=1, records_written=1,
        coverage={
            "window": {"start_time_ms": C_START - DAY, "end_time_ms": T0, "days": 91},
            "fills": {"attempted": True, "completed": complete, "truncated_at_page_cap": not complete,
                      "covered_until_ms": covered_until_ms, "forced_cursor_advances": 0},
            "funding": {"attempted": True, "completed": True, "truncated_at_response_cap": False,
                        "seen": 3, "pages": 1},
        },
    )


class ArmARunnerStoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.db = self.root / "live.sqlite3"
        # Distinguishable activity: different starts, spacings and holds, all
        # inside the +/-50 percent fill-count band so every wallet has peers.
        patterns = {
            COHORT[0]: dict(start=START + DAY, count=20, spacing=2 * DAY, held=HOUR),
            COHORT[1]: dict(start=START + DAY + 9 * HOUR, count=20, spacing=2 * DAY, held=5 * HOUR),
            COHORT[2]: dict(start=START + 2 * DAY, count=24, spacing=DAY + 12 * HOUR, held=2 * HOUR),
            POOL_ONLY[0]: dict(start=START + DAY + 3 * HOUR, count=20, spacing=2 * DAY, held=3 * HOUR),
            POOL_ONLY[1]: dict(start=START + 3 * DAY, count=22, spacing=DAY + 20 * HOUR, held=HOUR),
        }
        with LiveDataStore(self.db) as store:
            store.write_candles(_candles(START - DAY, T0), ingested_at_ms=T0)
            store.start_run("candles-btc", mode="fetch_candles", started_at_ms=T0)
            store.finish_run("candles-btc", finished_at_ms=T0, status=RUN_STATUS_COMPLETED, records_seen=1,
                             records_written=1, coverage={"candles": {"coin": "BTC", "interval": "15m", "rows": 1, "exhausted": True}})
            for index, (wallet, p) in enumerate(patterns.items()):
                store.upsert_wallet(wallet, observed_at_ms=T0)
                rows = _round_trips(wallet, C_START + index * HOUR, 30, spacing_ms=DAY, tid_base=1000 * index)
                rows += _round_trips(wallet, p["start"], p["count"], spacing_ms=p["spacing"],
                                     tid_base=1000 * index + 100, held_ms=p["held"])
                store.write_fills(rows, source="test", ingested_at_ms=T0)
                store.write_funding([_funding(wallet, START + i * HOUR) for i in range(1, 4)], ingested_at_ms=T0)
                _coverage(store, f"backfill-{index}", wallet, covered_until_ms=T0)
        self.candles_json = self.root / "L2_ARM_A_CANDLES_001.json"
        self.candles_json.write_text(json.dumps({"per_coin": [{"coin": "BTC", "complete": True}]}), encoding="utf-8")
        self.cohort_json = self.root / "L2_COHORT_T0.json"
        self.cohort_json.write_text(json.dumps(self.record(COHORT)), encoding="utf-8")
        self.out = self.root / "L2_ARM_A_001.json"

    @staticmethod
    def record(wallets, *, hard_stop: bool = False, plan: str = PLAN, funding_coins: int = 1,
               candle_complete: int = 1, excluded=()) -> dict:
        cohort = [] if hard_stop else sorted(w.lower() for w in wallets)
        return {
            "t0_ms": T0, "cohort": cohort, "cohort_sha256": cohort_hash(cohort), "plan_commit": plan,
            "hard_stop": hard_stop, "minimum_evaluable": 200,
            "stage_counts": {"discovered": 5, "evaluable": len(cohort)},
            "per_wallet_reason": {"EVALUABLE": len(cohort)},
            "characterisation_window": {"start_ms": C_START, "end_ms": C_END, "days": 30.0},
            "scope": {"funding_coins": funding_coins, "candle_complete_coins": candle_complete,
                      "excluded": sorted(excluded), "sources": {"funding": "db", "candles": "post-check"}},
        }

    def write_record(self, rec: dict, name: str = "record.json") -> Path:
        path = self.root / name
        path.write_text(json.dumps(rec), encoding="utf-8")
        return path

    def argv(self, cohort: Path | None = None, plan: str = PLAN, dry_run: bool = True) -> list[str]:
        argv = ["--db", str(self.db), "--cohort", str(cohort or self.cohort_json),
                "--candles-json", str(self.candles_json), "--plan-commit", plan, "--out", str(self.out)]
        return argv + (["--allow-underpowered-dry-run"] if dry_run else [])

    def run_main(self, argv=None):
        logged: list[str] = []
        code = runner.main(argv or self.argv(), log=logged.append)
        return code, logged

    def run_ok(self, argv=None) -> dict:
        code, logged = self.run_main(argv)
        self.assertEqual(code, 0, logged)
        return json.loads(self.out.read_text(encoding="utf-8"))

    def add_second_coin(self, *, candles_until: int = T0, pool_peer_trades_it: bool = False) -> None:
        """ETH in scope: funding before T0, a candle table, the post-check and the freeze counting it."""
        with LiveDataStore(self.db) as store:
            store.write_candles(_candles(START - DAY, candles_until, coin="ETH"), ingested_at_ms=T0)
            store.write_funding([_funding(COHORT[0], START + HOUR, coin="ETH")], ingested_at_ms=T0)
            if pool_peer_trades_it:
                store.write_fills([_fill(POOL_ONLY[0], 9_501, START + 5 * DAY, coin="ETH"),
                                   _fill(POOL_ONLY[0], 9_502, START + 5 * DAY + HOUR, coin="ETH", side="A")],
                                  source="test", ingested_at_ms=T0)
        self.candles_json.write_text(json.dumps({"per_coin": [
            {"coin": "BTC", "complete": True}, {"coin": "ETH", "complete": True},
        ]}), encoding="utf-8")
        self.cohort_json.write_text(json.dumps(self.record(COHORT, funding_coins=2, candle_complete=2)), encoding="utf-8")


class ArmARunnerTests(ArmARunnerStoreTestCase):
    def test_it_scores_the_cohort_against_a_wider_pool_and_decides_nothing(self) -> None:
        code, logged = self.run_main()
        self.assertEqual(code, 0, logged)
        r = json.loads(self.out.read_text(encoding="utf-8"))
        self.assertEqual(r["run_id"], "L2-ARM-A-001")
        self.assertEqual(r["counts"], {"wallets": 3, "scored": 3, "refused": 0, "in_primary": 3})
        # The pool is every certified wallet, not the cohort; its hash and its
        # composition are recorded, and every eligible peer actually served.
        self.assertEqual(r["pool"]["size"], 5)
        self.assertEqual(r["pool"]["sha256"], cohort_hash(COHORT + POOL_ONLY))
        self.assertEqual((r["pool"]["cohort_wallets_in_pool"], r["pool"]["non_cohort_wallets_in_pool"]), (3, 2))
        self.assertEqual(r["pool"]["mean_cohort_share_of_peers"], 0.5)
        self.assertEqual(r["pool"]["ledger_modes"], ["backfill_wallet"])
        self.assertEqual(set(r["matched_peers_by_wallet"]), set(COHORT))
        for wallet, peers in r["matched_peers_by_wallet"].items():
            self.assertEqual(set(peers["contributed"]), set(COHORT + POOL_ONLY) - {wallet})
            self.assertEqual((peers["count"], peers["dropped"], peers["cohort_share"]), (4, {}, 0.5))
        self.assertEqual(r["ledger_snapshot"]["modes"], ["backfill_wallet"])
        self.assertEqual((r["ledger_snapshot"]["runs_consulted"], r["ledger_snapshot"]["max_finished_at_ms"]), (5, T0))
        self.assertRegex(r["ledger_snapshot"]["run_ids_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(r["price_series_span_rule"]["tolerance_ms"], 2 * FIFTEEN_MIN)
        p = r["primary"]
        self.assertEqual(p["latency_ms"], 30_000)
        self.assertEqual(p["n"], 3, p["excluded"])
        self.assertNotEqual(p["sd"], 0.0, "the fixture must not be degenerate")
        self.assertTrue(p["case_study"])
        self.assertEqual(p["reading"], "ARM_A_CASE_STUDY_UNDER_MINIMUM")
        self.assertEqual(r["empirical_result_status"], "DRY_RUN_UNDERPOWERED")
        self.assertIsNone(r["decision"])
        self.assertEqual(r["decisive_arm"], "B")
        self.assertFalse(r["copyability_claim_produced"])
        # The approval fixes the window's edges, not only its length.
        self.assertEqual(r["evaluation_window"], {"start_ms": T0 - 52 * DAY, "end_ms": T0 - 7 * DAY, "days": "45"})
        self.assertEqual(runner.characterisation_window(T0), (T0 - 90 * DAY, T0 - 60 * DAY))
        self.assertEqual(r["scope"]["coins_evaluated"], ["BTC"])
        self.assertEqual(r["price_series_span_by_coin"]["BTC"]["spans_window"], True)
        self.assertEqual(r["price_provenance"]["fetch_runs"][0]["run_id"], "candles-btc")
        self.assertEqual(r["stage_counts"]["discovered"], 5)
        self.assertEqual(r["primary"]["disclosures"]["of_n"], 3)
        self.assertEqual(r["primary"]["disclosures"]["liquidity_assumed"], 3)
        self.assertEqual(len(r["rows"]), 3 * len(runner.LATENCY_GRID_MS))
        self.assertEqual(r["survivorship"]["cohort"], 3)
        self.assertEqual(r["survivorship"]["stopped"], 1)  # COHORT[2]'s last fill is 8.4 days before the end
        self.assertEqual(r["what_broke"], [])
        for latency in runner.LATENCY_GRID_MS:
            self.assertEqual(r["secondary"]["mean_d_by_latency"][str(latency)]["n"], 3)
        self.assertEqual(float(r["secondary"]["mean_d_by_latency"]["30000"]["mean"]), round(r["primary"]["mean"], 4))
        self.assertTrue(any("Survivorship" in s for s in r["sample_limitations_disclosure"]))
        self.assertFalse(self.out.with_name(self.out.name + ".partial.json").exists())
        self.assertNotIn("_runtime_seconds_by_wallet", r)
        sidecar = json.loads(self.out.with_name(self.out.name + ".runtime.json").read_text(encoding="utf-8"))
        self.assertEqual(set(sidecar["runtime_seconds_by_wallet"]), set(COHORT))

    def test_the_statistics_in_the_file_follow_from_its_own_d_values(self) -> None:
        self.run_main()
        p = json.loads(self.out.read_text(encoding="utf-8"))["primary"]
        d = [float(v) for v in p["d_by_wallet"].values()]
        self.assertAlmostEqual(p["mean"], statistics.fmean(d), places=3)
        sd = statistics.stdev(d)
        self.assertAlmostEqual(p["sd"], sd, places=3)
        half = stats.student_t_quantile(0.975, len(d) - 1) * sd / math.sqrt(len(d))
        self.assertAlmostEqual(p["ci95"][1] - p["ci95"][0], 2 * half, places=2)
        self.assertEqual(p["t_critical"], round(stats.student_t_quantile(0.975, 2), 4))

    def test_the_log_carries_counts_and_a_digest_but_never_a_number_from_the_result(self) -> None:
        _, logged = self.run_main()
        self.assertEqual(len(logged), 4)  # one line per wallet, one summary
        for line in logged[:3]:
            self.assertRegex(line, r"^L2-ARM-A-001: [123]/3 (scored|refused) refused_so_far=\d elapsed_s=[\d.]+$")
        self.assertRegex(
            logged[3],
            r"^L2-ARM-A-001: wallets=3 scored=3 refused=0 in_primary=3 status=DRY_RUN_UNDERPOWERED file_sha256=[0-9a-f]{64}$",
        )

    def test_two_runs_on_the_same_inputs_are_byte_identical(self) -> None:
        _, first = self.run_main()
        _, second = self.run_main()
        self.assertEqual(first[-1], second[-1])

    def test_an_underpowered_cohort_is_refused_without_the_dry_run_flag(self) -> None:
        code, logged = self.run_main(self.argv(dry_run=False))
        self.assertEqual(code, 2)
        self.assertFalse(self.out.exists())
        self.assertIn("under the minimum", logged[0])

    def test_a_record_whose_list_does_not_hash_to_its_digest_is_refused(self) -> None:
        rec = self.record(COHORT)
        rec["cohort"] = rec["cohort"][:2]  # edited list, stale digest
        code, logged = self.run_main(self.argv(cohort=self.write_record(rec)))
        self.assertEqual(code, 2)
        self.assertFalse(self.out.exists())
        self.assertIn("does not hash", logged[0])

    def test_a_frozen_hard_stop_is_not_evaluated(self) -> None:
        code, logged = self.run_main(self.argv(cohort=self.write_record(self.record(COHORT, hard_stop=True))))
        self.assertEqual(code, 2)
        self.assertFalse(self.out.exists())
        self.assertIn("hard stop", logged[0])

    def test_a_freeze_from_another_plan_commit_is_refused(self) -> None:
        code, logged = self.run_main(self.argv(plan="deadbeef"))
        self.assertEqual(code, 2)
        self.assertIn("plan commit", logged[0])

    def test_a_scope_that_differs_from_the_freeze_is_refused(self) -> None:
        code, logged = self.run_main(self.argv(cohort=self.write_record(self.record(COHORT, funding_coins=5))))
        self.assertEqual(code, 2)
        self.assertFalse(self.out.exists())
        self.assertIn("not the one the cohort was frozen under", logged[0])

    def test_each_scope_input_excludes_what_it_should(self) -> None:
        w = COHORT[0]
        with LiveDataStore(self.db) as store:
            # ETH: fills but no funding row. SOL: funding but candles incomplete.
            # LINK: funding and complete candles but excluded by the freeze.
            rows = [_fill(w, 9_001, START + 10 * DAY, coin="ETH"), _fill(w, 9_002, START + 11 * DAY, coin="SOL"),
                    _fill(w, 9_003, START + 12 * DAY, coin="LINK")]
            store.write_fills(rows, source="test", ingested_at_ms=T0)
            store.write_funding([_funding(w, START + HOUR, coin="SOL"), _funding(w, START + HOUR, coin="LINK")],
                                ingested_at_ms=T0)
            # Priceable, so only the scope split can take them out.
            for coin in ("SOL", "LINK"):
                store.write_candles(_candles(START - DAY, T0, coin=coin), ingested_at_ms=T0)
        self.candles_json.write_text(json.dumps({"per_coin": [
            {"coin": "BTC", "complete": True}, {"coin": "SOL", "complete": False}, {"coin": "LINK", "complete": True},
        ]}), encoding="utf-8")
        rec = self.record(COHORT, funding_coins=3, candle_complete=2, excluded=["LINK"])
        code, logged = self.run_main(self.argv(cohort=self.write_record(rec)))
        self.assertEqual(code, 0, logged)
        r = json.loads(self.out.read_text(encoding="utf-8"))
        self.assertEqual(r["scope"]["out_of_scope_fills_by_wallet"], {w: 3})
        self.assertEqual(r["scope"]["coins_evaluated"], ["BTC"])
        self.assertEqual(r["scope"]["funding_coins"], ["BTC", "LINK", "SOL"])

    def test_an_unspanned_benchmark_is_missing_data_not_a_result(self) -> None:
        with LiveDataStore(self.db) as store:
            store.connection.execute("DELETE FROM candles WHERE close_time_ms > ?", (END - 20 * DAY,))
            store.connection.commit()
        code, logged = self.run_main()
        self.assertEqual(code, 2, logged)
        self.assertFalse(self.out.exists())
        self.assertIn("benchmark coin BTC has no price series spanning the window", logged[0])

    def test_a_coin_whose_series_does_not_span_the_window_leaves_scope_and_is_counted(self) -> None:
        self.add_second_coin(candles_until=END - 20 * DAY, pool_peer_trades_it=True)
        with LiveDataStore(self.db) as store:
            store.write_fills([_fill(COHORT[0], 9_601, START + 6 * DAY, coin="ETH"),
                               _fill(COHORT[0], 9_602, START + 6 * DAY + HOUR, coin="ETH", side="A"),
                               _fill(COHORT[0], 9_603, START - 3 * DAY, coin="ETH")],  # before the window: not counted
                              source="test", ingested_at_ms=T0)
        r = self.run_ok()
        self.assertFalse(r["price_series_span_by_coin"]["ETH"]["spans_window"])
        self.assertEqual(r["scope"]["coins_evaluated"], ["BTC"])
        self.assertEqual(r["diagnostics_rollup"]["coins_without_a_spanning_price_series"], ["ETH"])
        self.assertEqual(r["scope"]["out_of_scope_fills_by_wallet"], {COHORT[0]: 2})
        self.assertEqual(r["what_broke"], [])
        # The peer that also traded ETH stays a peer on its BTC fills.
        self.assertIn(POOL_ONLY[0], r["matched_peers_by_wallet"][COHORT[1]]["contributed"])

    def test_a_pool_peer_trading_a_coin_the_cohort_does_not_still_enters_the_baseline(self) -> None:
        # Round two's blocker: the market was built over the cohort's coins
        # only, so a peer with a fill on any other in-scope coin threw inside
        # the baseline, dropped out of M_i, and was still listed as averaged.
        self.add_second_coin(pool_peer_trades_it=True)
        r = self.run_ok()
        self.assertEqual(r["scope"]["coins_evaluated"], ["BTC", "ETH"])
        for peers in r["matched_peers_by_wallet"].values():
            self.assertIn(POOL_ONLY[0], peers["contributed"])
            self.assertEqual(peers["dropped"], {})

    def test_the_first_edge_of_the_span_rule_admits_what_the_freeze_post_check_admits(self) -> None:
        self.add_second_coin(pool_peer_trades_it=True)  # someone must trade ETH for it to be priced
        with LiveDataStore(self.db) as store:
            store.connection.execute("DELETE FROM candles WHERE coin = 'ETH' AND open_time_ms < ?", (START + FIFTEEN_MIN,))
            store.connection.commit()
        self.assertTrue(self.run_ok()["price_series_span_by_coin"]["ETH"]["spans_window"])
        with LiveDataStore(self.db) as store:
            store.connection.execute("DELETE FROM candles WHERE coin = 'ETH' AND open_time_ms < ?", (START + 2 * FIFTEEN_MIN,))
            store.connection.commit()
        self.assertFalse(self.run_ok()["price_series_span_by_coin"]["ETH"]["spans_window"])

    def test_a_gap_in_the_price_series_produces_stale_skips_under_the_freshness_bound(self) -> None:
        with LiveDataStore(self.db) as store:
            store.connection.execute("DELETE FROM candles WHERE close_time_ms BETWEEN ? AND ?",
                                     (START + 5 * DAY - 30 * 60_000, START + 5 * DAY + 3 * HOUR))
            store.connection.commit()
        r = self.run_ok()
        self.assertGreater(r["diagnostics_rollup"]["stale_price_skips"], 0)
        self.assertGreaterEqual(r["primary"]["disclosures"]["stale_price_skips_present"], 1)

    def test_the_disclosed_study_parameters_are_the_frozen_ones(self) -> None:
        r = self.run_ok()
        self.assertEqual(r["assumptions"], {
            "benchmark_coin": "BTC", "fees_bps": {"maker": "1.5", "taker": "4.5"}, "impact_bps_per_full_depth": "10",
            "latencies_ms": [1000, 5000, 30000, 120000, 300000, 900000], "liquidity_source": "ASSUMED",
            "liquidity_tiers": {"tier1": {"depth_notional_usd": "2000000", "half_spread_bps": "0.5"},
                                "tier2": {"depth_notional_usd": "300000", "half_spread_bps": "1.5"},
                                "tier3": {"depth_notional_usd": "50000", "half_spread_bps": "5"}},
            "matched_random_eligibility": "another pool wallet whose in-window fill count is within the tolerance "
                                          "of the target's and whose coverage certifies the same window",
            "matched_random_peer_tolerance": "0.5", "matched_random_sample_size": 20, "max_price_age_ms": 900000,
            "momentum": {"lookback_ms": 3600000, "step_ms": 600000}, "nominal_capital": "10000",
            "seed": 2605216799, "seed_derivation": "int(cohort_sha256[:8], 16)", "size_scale": "1",
        })
        self.assertEqual(r["assumptions"]["seed"], runner.seed_from(cohort_hash(sorted(COHORT))))
        # Disclosed values are the ones the simulator is handed, not constants beside it.
        config = core.study_config(r["assumptions"]["seed"])
        self.assertEqual(config.max_price_age_ms, r["price_source"]["max_age_ms"])
        self.assertEqual(str(config.random_tolerance), r["assumptions"]["matched_random_peer_tolerance"])
        self.assertEqual(config.random_sample_size, r["assumptions"]["matched_random_sample_size"])
        self.assertEqual(config.random_seed, r["assumptions"]["seed"])
        self.assertEqual(list(config.latencies_ms), r["assumptions"]["latencies_ms"])
        self.assertEqual(str(config.follower.capital), r["assumptions"]["nominal_capital"])
        self.assertEqual(str(config.follower.size_scale), r["assumptions"]["size_scale"])

    def test_the_record_cannot_lower_the_plans_minimum(self) -> None:
        rec = {**self.record(COHORT), "minimum_evaluable": 3}
        code, logged = self.run_main(self.argv(cohort=self.write_record(rec), dry_run=False))
        self.assertEqual(code, 2)
        self.assertFalse(self.out.exists())
        self.assertIn("minimum_evaluable=3", logged[0])

    def test_a_record_whose_characterisation_window_is_not_the_plans_is_refused(self) -> None:
        rec = self.record(COHORT)
        rec["characterisation_window"]["start_ms"] -= DAY
        code, logged = self.run_main(self.argv(cohort=self.write_record(rec)))
        self.assertEqual(code, 2)
        self.assertIn("characterisation window", logged[0])

    def test_a_sweep_written_after_t0_cannot_move_the_arm_a_pool(self) -> None:
        with LiveDataStore(self.db) as store:
            store.connection.execute("DELETE FROM ingest_runs WHERE wallet_address = ?", (POOL_ONLY[1],))
            store.connection.commit()
            _coverage(store, "short-4", POOL_ONLY[1], covered_until_ms=END - 3 * DAY)
        before = self.run_ok()
        self.assertEqual(before["pool"]["size"], 4)
        with LiveDataStore(self.db) as store:
            # The shape sweep.py writes: resumed at latest_fill + 1, certifying past T0.
            store.start_run("sweep-late", mode="sweep_wallet", started_at_ms=T0 + DAY, wallet_address=POOL_ONLY[1])
            store.finish_run(
                "sweep-late", finished_at_ms=T0 + DAY, status=RUN_STATUS_COMPLETED, records_seen=1, records_written=1,
                coverage={"window": {"start_time_ms": END - 3 * DAY, "end_time_ms": T0 + DAY},
                          "fills": {"attempted": True, "completed": True, "truncated_at_page_cap": False,
                                    "covered_until_ms": T0 + DAY},
                          "funding": {"attempted": True, "completed": True, "truncated_at_response_cap": True}},
            )
        after = self.run_ok()
        self.assertEqual(after["pool"], before["pool"])
        self.assertEqual(after["ledger_snapshot"], before["ledger_snapshot"])
        self.assertEqual(after["primary"]["d_by_wallet"], before["primary"]["d_by_wallet"])
        self.assertEqual(after["primary"]["disclosures"]["source_funding_truncated"], 0)

    def test_nothing_written_after_t0_reaches_the_arm_a_file(self) -> None:
        before = self.run_ok()
        with LiveDataStore(self.db) as store:
            store.write_funding([_funding(COHORT[0], T0 + HOUR, coin="DOGE")], ingested_at_ms=T0 + HOUR)
            store.write_fills([_fill(COHORT[0], 9_701, T0 + DAY, coin="ETH")], source="test", ingested_at_ms=T0 + DAY)
        after = self.run_ok()
        self.assertEqual(after["scope"]["funding_coins"], ["BTC"])
        self.assertEqual(after["scope"]["out_of_scope_fills_by_wallet"], {})
        self.assertEqual(after, before)

    def test_survivorship_is_measured_on_every_fill_in_or_out_of_scope(self) -> None:
        before = self.run_ok()
        self.assertTrue(before["survivorship"]["per_wallet"][COHORT[2]]["stopped"])
        self.assertEqual(before["survivorship"]["per_wallet"][COHORT[0]], {
            "characterisation_fills": 60, "expected_tail_fills": "28.0000", "faded": False,
            "fills_in_window": 40, "last_fill_ms": 1_998_880_400_000, "stopped": False, "tail_fills": 10,
        })
        with LiveDataStore(self.db) as store:  # LINK has no funding row: out of scope, still activity
            store.write_fills([_fill(COHORT[2], 9_801, END - DAY, coin="LINK")], source="test", ingested_at_ms=T0)
        after = self.run_ok()
        self.assertFalse(after["survivorship"]["per_wallet"][COHORT[2]]["stopped"])
        self.assertEqual(after["survivorship"]["stopped"], 0)
        self.assertEqual(after["scope"]["out_of_scope_fills_by_wallet"], {COHORT[2]: 1})

    def test_the_checkpoint_is_written_before_progress_is_reported(self) -> None:
        partial = self.out.with_name(self.out.name + ".partial.json")
        seen: dict = {}

        def spy(line: str) -> None:
            if " 2/3 " in line:
                seen.update(json.loads(partial.read_text(encoding="utf-8")))

        self.assertEqual(runner.main(self.argv(), log=spy), 0)
        self.assertEqual((seen["completed"], seen["of"], seen["arm"]), (2, 3, "A"))
        self.assertEqual((seen["empirical_result_status"], seen["decision"], seen["copyability_claim_produced"]),
                         ("PARTIAL_CHECKPOINT", None, False))
        self.assertEqual(len(seen["rows"]), 2 * len(runner.LATENCY_GRID_MS))
        self.assertFalse(partial.exists())

    def test_a_stop_mid_run_keeps_the_partial_under_an_aborted_name_and_writes_no_evidence(self) -> None:
        original = core.run_study
        calls: list = []

        def failing(**kwargs):
            calls.append(kwargs["wallets"])
            if len(calls) == 2:
                raise RuntimeError("synthetic stop on the second wallet")
            return original(**kwargs)

        core.run_study = failing
        try:
            code, logged = self.run_main()
        finally:
            core.run_study = original
        self.assertEqual(code, 2)
        self.assertFalse(self.out.exists())
        self.assertIn("stopped: RuntimeError: synthetic stop", logged[-1])
        aborted = json.loads(self.out.with_name(self.out.name + ".aborted.json").read_text(encoding="utf-8"))
        self.assertEqual((aborted["completed"], aborted["empirical_result_status"], aborted["decision"]),
                         (1, "PARTIAL_CHECKPOINT", None))
        self.assertFalse(self.out.with_name(self.out.name + ".partial.json").exists())

    def test_coverage_that_stops_before_the_window_end_refuses_every_wallet(self) -> None:
        with LiveDataStore(self.db) as store:
            store.connection.execute("DELETE FROM ingest_runs WHERE mode = 'backfill_wallet'")
            store.connection.commit()
            for index, wallet in enumerate(COHORT + POOL_ONLY):
                _coverage(store, f"short-{index}", wallet, covered_until_ms=END - DAY)
        code, logged = self.run_main()
        self.assertEqual(code, 3, logged)
        r = json.loads(self.out.read_text(encoding="utf-8"))
        self.assertEqual(r["counts"]["refused"], 3)
        self.assertEqual(r["pool"]["size"], 0)
        self.assertEqual(r["diagnostics_rollup"]["refusal_reasons"], {"UnknownIntervalError": 3})
        self.assertEqual(r["empirical_result_status"], "BROKE_SEE_WHAT_BROKE")
        self.assertIsNone(r["decision"])
        self.assertTrue(logged[-1].endswith(" broke=1"), logged[-1])


class SurvivorshipTests(unittest.TestCase):
    @staticmethod
    def _fills(wallet: str, times: list[int], coin: str = "BTC") -> list[SourceFill]:
        return [SourceFill(wallet, coin, t, "B", Decimal("1"), Decimal("1"), Decimal("0"), Decimal("0"), i)
                for i, t in enumerate(times)]

    def _measure(self, fills):
        return report.survivorship(fills, list(fills), window=(START, END), characterisation=(C_START, C_END))

    def test_shares_are_over_the_cohort_and_idle_counts_as_stopped(self) -> None:
        healthy, stopped, faded, idle = ("0x" + c * 40 for c in "abcd")
        rate = [C_START + i * DAY for i in range(30)]  # one fill a day
        result = self._measure({
            healthy: self._fills(healthy, rate + [START + i * DAY for i in range(45)]),
            stopped: self._fills(stopped, rate + [START + i * DAY for i in range(30)]),  # last fill 15 d before end
            faded: self._fills(faded, rate + [START + i * DAY for i in range(30)] + [END - DAY]),  # 1 in last 14 d
            idle: self._fills(idle, rate),
        })
        self.assertEqual(result["cohort"], 4)
        self.assertEqual(result["active_in_window"], 3)
        self.assertTrue(result["per_wallet"][idle]["stopped"])
        self.assertEqual(result["stopped"], 2)  # stopped + idle
        self.assertEqual(result["stopped_share_of_cohort"], "0.5000")
        self.assertEqual(result["stopped_share_of_active"], "0.3333")
        self.assertEqual(result["faded"], 3)  # the stopped wallet has also faded, by the rule; so has idle
        self.assertEqual(result["per_wallet"][idle]["faded"], True)
        self.assertEqual(result["faded_share_of_cohort"], "0.7500")
        self.assertFalse(result["per_wallet"][healthy]["stopped"])
        self.assertFalse(result["per_wallet"][healthy]["faded"])

    def test_the_seven_and_fourteen_day_tails_and_the_strict_boundary_are_necessary(self) -> None:
        ten, seven, sparse = ("0x" + c * 40 for c in "efg")
        rate = [C_START + i * DAY for i in range(30)]
        result = self._measure({
            ten: self._fills(ten, rate + [START, END - 10 * DAY]),          # stopped under 7, not under 14
            seven: self._fills(seven, rate + [START, END - 7 * DAY]),        # exactly 7: not stopped
            sparse: self._fills(sparse, rate + [START] + [END - i * DAY for i in (1, 2, 3, 4)]),  # 4 in last 14 d
        })
        self.assertTrue(result["per_wallet"][ten]["stopped"])
        self.assertFalse(result["per_wallet"][seven]["stopped"])
        # 4 fills in the last 14 days against a rate of 1/day: 4 >= 0.25 x 14, not faded;
        # under a 7-day tail it would read 4 >= 1.75 too, but 0 fills in the last 7
        # days is what a swapped constant would have to explain.
        self.assertFalse(result["per_wallet"][sparse]["faded"])
        self.assertEqual(result["per_wallet"][sparse]["tail_fills"], 4)
        self.assertEqual(result["per_wallet"][sparse]["expected_tail_fills"], "14.0000")

    def test_out_of_scope_fills_still_count_as_activity(self) -> None:
        w = "0x" + "h" * 40
        rate = [C_START + i * DAY for i in range(30)]
        spot = [START + i * DAY for i in range(45)]
        result = self._measure({w: self._fills(w, rate) + self._fills(w, spot, coin="@1")})
        self.assertFalse(result["per_wallet"][w]["stopped"])
        self.assertFalse(result["per_wallet"][w]["faded"])

    def test_a_wallet_without_characterisation_fills_is_not_judged_for_fade(self) -> None:
        w = "0x" + "i" * 40
        result = self._measure({w: self._fills(w, [START + i * DAY for i in range(45)])})
        self.assertIsNone(result["per_wallet"][w]["faded"])
        self.assertEqual(result["faded_judged"], 0)
        self.assertIsNone(result["faded_share_of_judged"])


def _study(wallet: str, *, refusal=None, outcomes=()):
    return SimpleNamespace(wallet=wallet, refusal=refusal, outcomes=list(outcomes), matched_peers=())


def _outcome(latency_ms: int, ret, peer=None, **flags):
    base = dict(latency_ms=latency_ms, return_on_deployed=None if ret is None else Decimal(ret),
                baseline_returns={} if peer is None else {"matched_random": Decimal(peer)}, versus={},
                funding_incomplete=False, source_funding_truncated=False, liquidity_assumed=True,
                stale_price_skips=0, catch_up_fills=0, skipped_fills=0, fills_after_cutoff=0, trade_count=1)
    base.update(flags)
    return SimpleNamespace(**base)


class PrimaryStatisticTests(unittest.TestCase):
    DAYS = Decimal(45)

    def test_it_averages_only_wallets_with_a_peer_figure_at_thirty_seconds(self) -> None:
        studies = [
            _study("a", outcomes=[_outcome(30_000, "0.02", "0.01"), _outcome(1_000, "0.9", "0.0")]),
            _study("b", outcomes=[_outcome(30_000, "0.03", "0.01")]),
            _study("c", outcomes=[_outcome(30_000, "0.05", "0.02")]),
            _study("d", outcomes=[_outcome(30_000, "0.05", "0.01")]),
            _study("refused", refusal="UnknownIntervalError: gap"),
            _study("nothing", outcomes=[_outcome(30_000, None)]),
            _study("nopeer", outcomes=[_outcome(30_000, "0.5")]),
        ]
        p = stats.primary_statistic(studies, window_days=self.DAYS, minimum=4)
        # d in points per 14 days: (R - M) * 1400 / 45
        expected = {"a": 0.01, "b": 0.02, "c": 0.03, "d": 0.04}
        self.assertEqual(p["n"], 4)
        for w, v in expected.items():
            self.assertAlmostEqual(float(p["d_by_wallet"][w]), v * 1400 / 45, places=4)
        self.assertEqual(set(p["excluded"]), {"refused", "nothing", "nopeer"})
        d = [v * 1400 / 45 for v in expected.values()]
        self.assertAlmostEqual(p["mean"], statistics.fmean(d), places=4)
        half = stats.student_t_quantile(0.975, 3) * statistics.stdev(d) / 2
        self.assertAlmostEqual(p["ci95"][0], round(statistics.fmean(d) - half, 4), places=4)
        self.assertFalse(p["case_study"])
        self.assertEqual(p["reading"], stats.reading_for(*p["ci95"]))

    def test_the_reading_is_taken_on_the_written_bounds(self) -> None:
        # Unrounded upper bound 0.49998 rounds to 0.5000: the written interval
        # contains the target, so the reading must be inconclusive, not negative.
        studies = [_study(w, outcomes=[_outcome(30_000, str(Decimal(v) * 45 / 1400), "0")])
                   for w, v in (("a", "0.2195"), ("b", "0.3"), ("c", "0.3805"))]
        p = stats.primary_statistic(studies, window_days=self.DAYS, minimum=3)
        self.assertEqual(p["ci95"][1], 0.5)
        self.assertEqual(p["reading"], "ARM_A_INCONCLUSIVE")

    def test_zero_variance_and_too_few_wallets_are_not_measurable(self) -> None:
        same = [_study(w, outcomes=[_outcome(30_000, "0.02", "0.01")]) for w in "abc"]
        self.assertEqual(stats.primary_statistic(same, window_days=self.DAYS, minimum=3)["reading"], "ARM_A_NOT_MEASURABLE")
        one = [_study("a", outcomes=[_outcome(30_000, "0.02", "0.01")])]
        p = stats.primary_statistic(one, window_days=self.DAYS, minimum=1)
        self.assertEqual(p["reading"], "ARM_A_NOT_MEASURABLE")
        self.assertEqual({k for k, v in p.items() if v is None}, {"mean", "sd", "standard_error", "ci95", "t_critical", "t_statistic"})

    def test_under_the_minimum_is_a_case_study_whatever_the_interval_says(self) -> None:
        studies = [_study(w, outcomes=[_outcome(30_000, v, "0")]) for w, v in (("a", "0.5"), ("b", "0.6"), ("c", "0.7"))]
        p = stats.primary_statistic(studies, window_days=self.DAYS)  # default minimum 200
        self.assertTrue(p["case_study"])
        self.assertEqual(p["reading"], "ARM_A_CASE_STUDY_UNDER_MINIMUM")
        self.assertIsNotNone(p["mean"])

    def test_disclosure_rollup_counts_the_wallets_in_the_primary(self) -> None:
        studies = [
            _study("a", outcomes=[_outcome(30_000, "0.1", "0", funding_incomplete=True, stale_price_skips=2)]),
            _study("b", outcomes=[_outcome(30_000, "0.1", "0", source_funding_truncated=True, catch_up_fills=1)]),
            _study("c", outcomes=[_outcome(30_000, "0.1", "0")]),
        ]
        d = stats.disclosure_rollup(studies, wallets=["a", "b"])
        self.assertEqual(d, {"of_n": 2, "funding_incomplete": 1, "source_funding_truncated": 1,
                             "liquidity_assumed": 2, "stale_price_skips_present": 1, "catch_up_fills_present": 1})


class StatisticsTests(unittest.TestCase):
    def test_t_quantiles_match_the_tables(self) -> None:
        self.assertAlmostEqual(stats.student_t_quantile(0.975, 10), 2.228, places=3)
        self.assertAlmostEqual(stats.student_t_quantile(0.975, 30), 2.042, places=3)
        self.assertAlmostEqual(stats.student_t_quantile(0.975, 1_000_000), 1.960, places=3)

    def test_the_reading_rule_is_the_frozen_one(self) -> None:
        self.assertEqual(stats.reading_for(-1.0, 0.49), "ARM_A_NEGATIVE")
        self.assertEqual(stats.reading_for(0.51, 2.0), "ARM_A_POSITIVE")
        self.assertEqual(stats.reading_for(0.1, 0.9), "ARM_A_INCONCLUSIVE")
        self.assertEqual(stats.reading_for(0.5, 0.5), "ARM_A_INCONCLUSIVE")


if __name__ == "__main__":
    unittest.main()
