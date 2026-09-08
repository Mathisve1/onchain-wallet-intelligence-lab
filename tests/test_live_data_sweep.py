"""Arm B: one operator-started sweep, and the light mid sample beside it.

The sweep is the only collection path that touches hundreds of wallets in one
run, so what these tests pin is mostly about what it must *not* do: it must not
re-ask for history it already stores, must not abandon the cohort when one
wallet fails, and must not spend more venue weight than the requests it made.
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from src.live_data import cli
from src.live_data.models import Fill, PayloadError
from src.live_data.storage import RUN_STATUS_COMPLETED, LiveDataStore
from src.live_data.watch import IngestError
from tests.test_live_data_ingest import (
    OTHER_WALLET,
    WALLET,
    IngestTestCase,
    ScriptedTransport,
    clearinghouse_payload,
    fill_payload,
)

T0_MS = 1_699_000_000_000
PRIOR_FILL_MS = 1_699_500_000_000

ALL_MIDS = {"BTC": "64000.5", "ETH": "3000.25"}


def funding_row(time_ms: int, *, coin: str = "BTC") -> dict:
    """One ``userFunding`` row in the venue's own shape."""
    return {
        "time": time_ms,
        "delta": {
            "type": "funding",
            "coin": coin,
            "usdc": "-0.42",
            "szi": "0.01",
            "fundingRate": "0.0000125",
        },
    }


def funding_page(count: int, *, first_time_ms: int) -> list[dict]:
    """A full or partial funding page, one row per hour per coin."""
    return [
        funding_row(first_time_ms + index * 3_600_000, coin=f"COIN{index}")
        for index in range(count)
    ]


def request_sequence(transport: ScriptedTransport) -> list[tuple]:
    """The venue-visible request sequence: type, user, and the start time asked for."""
    return [
        (body["type"], body.get("user"), body.get("startTime"))
        for body in transport.bodies
    ]


class SweepTestCase(IngestTestCase):
    def store_prior_fill(self, wallet: str, time_ms: int) -> None:
        row = fill_payload(1, time_ms)
        self.store.write_fills(
            [(Fill.parse(row, wallet), row)], source="test", ingested_at_ms=1
        )


class RequestSequenceTests(SweepTestCase):
    def test_the_sweep_resumes_from_stored_history_wallet_by_wallet(self) -> None:
        self.store_prior_fill(WALLET, PRIOR_FILL_MS)
        orchestrator, transport = self.build(
            [
                ALL_MIDS,
                [],  # WALLET fills, none since its last stored fill
                [],  # WALLET funding
                [fill_payload(7, T0_MS + 1_000)],  # OTHER_WALLET fills from T0
                [],  # OTHER_WALLET funding
                clearinghouse_payload(),  # snapshot, first wallet only
            ]
        )
        report = orchestrator.sweep(
            [WALLET, OTHER_WALLET], ["BTC", "ETH"], t0_ms=T0_MS, snapshot_top=1
        )

        self.assertEqual(
            request_sequence(transport),
            [
                ("allMids", None, None),
                ("userFillsByTime", WALLET, PRIOR_FILL_MS + 1),
                ("userFunding", WALLET, T0_MS),
                ("userFillsByTime", OTHER_WALLET, T0_MS),
                ("userFunding", OTHER_WALLET, T0_MS),
                ("clearinghouseState", WALLET, None),
            ],
        )
        self.assertEqual(report["sweep"]["snapshots"], 1)
        self.assertEqual(report["sweep"]["wallets_failed"], 0)
        self.assertEqual(report["sweep"]["fills_written"], 1)
        self.assertEqual(report["per_wallet"][WALLET]["fills_from_ms"], PRIOR_FILL_MS + 1)
        self.assertEqual(report["per_wallet"][OTHER_WALLET]["fills_from_ms"], T0_MS)

    def test_the_fills_window_ends_at_the_sweep_start(self) -> None:
        orchestrator, transport = self.build(
            [ALL_MIDS, [], [], clearinghouse_payload()]
        )
        orchestrator.sweep([WALLET], ["BTC"], t0_ms=T0_MS, snapshot_top=1)
        fills_body = next(b for b in transport.bodies if b["type"] == "userFillsByTime")
        self.assertEqual(fills_body["endTime"], self.now_ms)

    def test_a_funding_resume_uses_the_stored_funding_time(self) -> None:
        orchestrator, _ = self.build([ALL_MIDS, [], [funding_row(T0_MS + 5_000)], []])
        orchestrator.sweep([WALLET], ["BTC"], t0_ms=T0_MS, snapshot_top=0)
        orchestrator, transport = self.build([ALL_MIDS, [], []])
        orchestrator.sweep([WALLET], ["BTC"], t0_ms=T0_MS, snapshot_top=0)
        self.assertEqual(
            request_sequence(transport)[2], ("userFunding", WALLET, T0_MS + 5_001)
        )


class FailureIsolationTests(SweepTestCase):
    def test_one_failing_wallet_does_not_abort_the_sweep(self) -> None:
        orchestrator, transport = self.build(
            [
                ALL_MIDS,
                {"unexpected": "shape"},  # WALLET fills: not a list
                [fill_payload(7, T0_MS + 1_000)],  # OTHER_WALLET fills
                [],  # OTHER_WALLET funding
                clearinghouse_payload(),
                clearinghouse_payload(),
            ]
        )
        report = orchestrator.sweep(
            [WALLET, OTHER_WALLET], ["BTC"], t0_ms=T0_MS, snapshot_top=2
        )

        self.assertEqual(report["sweep"]["wallets_failed"], 1)
        self.assertEqual(report["sweep"]["wallets"], 2)
        self.assertIn("PayloadError", report["per_wallet"][WALLET]["status"])
        self.assertEqual(report["per_wallet"][OTHER_WALLET]["status"], "ok")
        self.assertEqual(report["sweep"]["fills_seen"], 1)
        # The failed wallet's funding call is skipped, the other wallet's is not.
        self.assertEqual(
            [body["type"] for body in transport.bodies],
            [
                "allMids",
                "userFillsByTime",
                "userFillsByTime",
                "userFunding",
                "clearinghouseState",
                "clearinghouseState",
            ],
        )

        run = next(r for r in self.store.recent_runs(10) if r["mode"] == "sweep")
        self.assertEqual(run["status"], RUN_STATUS_COMPLETED)
        self.assertEqual(run["error_count"], 1)
        self.assertIn(WALLET, run["notes"])
        coverage = json.loads(run["coverage"])
        self.assertEqual(coverage["sweep"]["wallets_failed"], 1)
        self.assertIn(OTHER_WALLET, coverage["per_wallet"])

    def test_a_failing_mid_sample_fails_the_whole_sweep(self) -> None:
        orchestrator, _ = self.build([{"BTC": "not a number"}])
        with self.assertRaises(PayloadError):
            orchestrator.sweep([WALLET], ["BTC"], t0_ms=T0_MS)
        modes = {run["mode"]: run["status"] for run in self.store.recent_runs(10)}
        self.assertEqual(modes["sweep"], "failed")
        self.assertEqual(modes["mids"], "failed")


class SweepWalletRowTests(SweepTestCase):
    """The per-wallet rows a sweep writes, and what reads them downstream."""

    def sweep_two_wallets(self) -> None:
        """One good wallet and one whose fills response is malformed."""
        orchestrator, _ = self.build(
            [
                ALL_MIDS,
                [fill_payload(7, T0_MS + 1_000)],  # WALLET fills
                [],  # WALLET funding
                {"unexpected": "shape"},  # OTHER_WALLET fills: not a list
            ]
        )
        orchestrator.sweep([WALLET, OTHER_WALLET], ["BTC"], t0_ms=T0_MS, snapshot_top=0)

    def test_a_sweep_writes_one_row_per_wallet_beside_the_summary_row(self) -> None:
        self.sweep_two_wallets()
        runs = self.store.recent_runs(20)
        per_wallet = [r for r in runs if r["mode"] == "sweep_wallet"]
        self.assertEqual(len([r for r in runs if r["mode"] == "sweep"]), 1)
        self.assertEqual(
            sorted((r["wallet_address"], r["status"]) for r in per_wallet),
            sorted([(WALLET, "completed"), (OTHER_WALLET, "failed")]),
        )
        good = next(r for r in per_wallet if r["wallet_address"] == WALLET)
        coverage = json.loads(good["coverage"])
        self.assertEqual(coverage["window"], {"start_time_ms": T0_MS, "end_time_ms": self.now_ms})
        self.assertTrue(coverage["fills"]["attempted"])
        self.assertTrue(coverage["fills"]["completed"])
        self.assertEqual(coverage["fills"]["covered_until_ms"], self.now_ms)
        self.assertEqual((coverage["fills"]["seen"], coverage["fills"]["written"]), (1, 1))
        self.assertEqual(coverage["fills"]["pages"], 1)
        self.assertEqual(coverage["funding"]["start_time_ms"], T0_MS)
        self.assertFalse(coverage["funding"]["truncated_at_response_cap"])
        self.assertIn("weight", coverage["requests"])
        bad = next(r for r in per_wallet if r["wallet_address"] == OTHER_WALLET)
        self.assertIn("PayloadError", bad["notes"])

    def test_the_coverage_ledger_certifies_the_swept_window(self) -> None:
        from src.copyability.coverage import UnknownIntervalError
        from src.copyability.loader import load_coverage

        self.sweep_two_wallets()
        ledger = load_coverage(self.store)
        self.assertEqual(ledger.covered(WALLET), [(T0_MS, self.now_ms)])
        self.assertTrue(ledger.is_fully_known(WALLET, T0_MS, self.now_ms))
        self.assertEqual(ledger.covered(OTHER_WALLET), [])
        with self.assertRaises(UnknownIntervalError):
            ledger.certify(OTHER_WALLET, T0_MS, self.now_ms)

    def test_health_reads_the_sweep_rows_it_wrote(self) -> None:
        from research.wallet_copyability.live_data_collector import health

        self.sweep_two_wallets()
        rows = {
            row["wallet_address"]: row
            for row in health.wallet_health(self.store, [WALLET, OTHER_WALLET], t0_ms=T0_MS)
        }
        self.assertEqual(rows[WALLET]["last_sweep_ms"], self.now_ms)
        self.assertEqual(rows[WALLET]["sweep_failures"], 0)
        self.assertIsNone(rows[OTHER_WALLET]["last_sweep_ms"])
        self.assertEqual(rows[OTHER_WALLET]["sweep_failures"], 1)


class FundingPagingTests(SweepTestCase):
    def test_a_full_funding_page_is_paged(self) -> None:
        first = funding_page(500, first_time_ms=T0_MS)
        last_time = first[-1]["time"]
        orchestrator, transport = self.build(
            [ALL_MIDS, [], first, funding_page(3, first_time_ms=last_time + 1)]
        )
        report = orchestrator.sweep([WALLET], ["BTC"], t0_ms=T0_MS, snapshot_top=0)

        funding_requests = [b for b in transport.bodies if b["type"] == "userFunding"]
        self.assertEqual(len(funding_requests), 2)
        self.assertEqual(funding_requests[0]["startTime"], T0_MS)
        self.assertEqual(funding_requests[1]["startTime"], last_time + 1)
        self.assertEqual(report["sweep"]["funding_pages"], 2)
        self.assertEqual(report["sweep"]["funding_seen"], 503)
        self.assertTrue(report["per_wallet"][WALLET]["funding_exhausted"])


class PollMidsTests(SweepTestCase):
    def test_only_the_requested_coins_are_written_and_absences_are_named(self) -> None:
        orchestrator, transport = self.build([ALL_MIDS])
        report = orchestrator.poll_mids(["BTC", "DOGE"])

        self.assertEqual([body["type"] for body in transport.bodies], ["allMids"])
        self.assertEqual(report["coins_requested"], 2)
        self.assertEqual(report["coins_written"], 1)
        self.assertEqual(report["missing"], ["DOGE"])
        rows = self.store.connection.execute(
            "SELECT coin, mid, observed_at_ms FROM mids"
        ).fetchall()
        self.assertEqual([(row["coin"], row["mid"]) for row in rows], [("BTC", "64000.5")])
        self.assertEqual(rows[0]["observed_at_ms"], self.now_ms)

        run = next(r for r in self.store.recent_runs(10) if r["mode"] == "mids")
        self.assertEqual(run["status"], RUN_STATUS_COMPLETED)
        self.assertEqual(json.loads(run["coverage"])["mids"]["missing"], ["DOGE"])

    def test_a_mid_sample_needs_at_least_one_coin(self) -> None:
        orchestrator, transport = self.build([])
        with self.assertRaises(IngestError):
            orchestrator.poll_mids([])
        self.assertEqual(transport.bodies, [])


class WeightAccountingTests(SweepTestCase):
    def test_the_consumed_weight_is_the_sum_of_the_requests_made(self) -> None:
        orchestrator, transport = self.build(
            [
                ALL_MIDS,  # dict: base 2, no row surcharge
                # 120 fill rows at the documented 20 rows per unit: 20 + 6
                [fill_payload(index, T0_MS + index) for index in range(120)],
                funding_page(60, first_time_ms=T0_MS),  # 60 rows: 20 + 3
                clearinghouse_payload(),  # dict: 2
            ]
        )
        orchestrator.sweep([WALLET], ["BTC"], t0_ms=T0_MS, snapshot_top=1)

        self.assertEqual(len(transport.bodies), 4)
        self.assertEqual(orchestrator.consumed_weight, 2 + 26 + 23 + 2)
        run = next(r for r in self.store.recent_runs(10) if r["mode"] == "sweep")
        self.assertEqual(json.loads(run["coverage"])["requests"]["weight"], 53)


class SweepArgumentTests(SweepTestCase):
    def test_an_empty_cohort_or_coin_list_is_refused_before_any_request(self) -> None:
        for wallets, coins in (([], ["BTC"]), ([WALLET], [])):
            with self.subTest(wallets=wallets, coins=coins):
                orchestrator, transport = self.build([])
                with self.assertRaises(IngestError):
                    orchestrator.sweep(wallets, coins, t0_ms=T0_MS)
                self.assertEqual(transport.bodies, [])

    def test_a_repeated_wallet_is_refused(self) -> None:
        orchestrator, transport = self.build([])
        with self.assertRaises(IngestError):
            orchestrator.sweep([WALLET, WALLET], ["BTC"], t0_ms=T0_MS)
        self.assertEqual(transport.bodies, [])


class CommandTests(unittest.TestCase):
    """The two commands, dispatched through ``main`` with an injected transport."""

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.root = Path(self._tempdir.name)
        self.db_path = self.root / "live.sqlite3"

    def run_cli(self, argv: list[str], payloads: list[object]) -> tuple[int, str, str]:
        transport = ScriptedTransport(payloads)
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli.main(
                ["--db", str(self.db_path), *argv],
                dependencies=cli.Dependencies(transport=transport),
            )
        return code, stdout.getvalue(), stderr.getvalue()

    def write_cohort(self, wallets: list[str]) -> Path:
        path = self.root / "L2_COHORT_T0.json"
        path.write_text(
            json.dumps({"t0_ms": T0_MS, "cohort": wallets}), encoding="utf-8"
        )
        return path

    def test_mids_parses_a_coin_list_and_reports_what_it_wrote(self) -> None:
        args = cli.build_parser().parse_args(["mids", "--coins", "BTC,ETH"])
        self.assertEqual(args.coins, ("BTC", "ETH"))

        code, out, _ = self.run_cli(["mids", "--coins", "BTC,DOGE"], [ALL_MIDS])
        report = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(report["mids"]["coins_written"], 1)
        self.assertEqual(report["mids"]["missing"], ["DOGE"])
        self.assertEqual(report["request_weight"], 2)

    def test_sweep_dispatches_over_the_cohort_file(self) -> None:
        cohort = self.write_cohort([WALLET])
        code, out, _ = self.run_cli(
            ["sweep", "--cohort", str(cohort), "--coins", "BTC", "--snapshot-top", "1"],
            [ALL_MIDS, [], [], clearinghouse_payload()],
        )
        report = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(report["sweep"]["t0_ms"], T0_MS)
        self.assertEqual(report["sweep"]["wallets"], 1)
        self.assertEqual(report["sweep"]["snapshots"], 1)
        self.assertEqual(report["failed_wallets"], [])

    def test_sweep_defaults_its_coins_to_what_the_cohort_has_traded(self) -> None:
        cohort = self.write_cohort([WALLET])
        with LiveDataStore(self.db_path) as store:
            row = fill_payload(1, PRIOR_FILL_MS, coin="ETH")
            store.write_fills(
                [(Fill.parse(row, WALLET), row)], source="test", ingested_at_ms=1
            )
        code, out, _ = self.run_cli(
            ["sweep", "--cohort", str(cohort), "--snapshot-top", "0"],
            [ALL_MIDS, [], []],
        )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["mids"]["coins_requested"], 1)
        self.assertEqual(json.loads(out)["mids"]["missing"], [])

    def test_a_missing_cohort_file_exits_nonzero_without_a_request(self) -> None:
        code, _, err = self.run_cli(
            ["sweep", "--cohort", str(self.root / "absent.json")], [ALL_MIDS]
        )
        self.assertEqual(code, 2)
        self.assertIn("cannot read cohort", err)

    def test_a_malformed_cohort_file_exits_nonzero(self) -> None:
        cases = {
            "no_t0.json": {"cohort": [WALLET]},
            "empty.json": {"t0_ms": T0_MS, "cohort": []},
            "repeated.json": {"t0_ms": T0_MS, "cohort": [WALLET, WALLET]},
        }
        for name, payload in cases.items():
            with self.subTest(case=name):
                path = self.root / name
                path.write_text(json.dumps(payload), encoding="utf-8")
                code, _, err = self.run_cli(["sweep", "--cohort", str(path)], [ALL_MIDS])
                self.assertEqual(code, 2)
                self.assertIn("cannot read cohort", err)

    def test_both_commands_refuse_to_run_without_a_transport(self) -> None:
        cohort = self.write_cohort([WALLET])
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            mids = cli.main(["--db", str(self.db_path), "mids", "--coins", "BTC"])
            sweep = cli.main(["--db", str(self.db_path), "sweep", "--cohort", str(cohort)])
        self.assertEqual((mids, sweep), (2, 2))
        self.assertEqual(stderr.getvalue().count("transport"), 2)


if __name__ == "__main__":
    unittest.main()
