"""Every declared table must actually be filled, and say what it covered.

A schema that declares ``positions_snapshot`` and ``funding`` but never writes
them is worse than not having them: an empty query then looks like a wallet
that did nothing, rather than a dataset nobody collected. These tests exist so
that gap cannot silently reopen.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.live_data.config import (
    DEFAULT_SNAPSHOT_INTERVAL_SECONDS,
    MAX_WS_TRACKED_USERS,
    LiveDataConfig,
)
from src.live_data.hyperliquid_rest import HyperliquidRestClient, request_weight
from src.live_data.hyperliquid_ws import HyperliquidWebSocketClient
from src.live_data.ingest import IngestOrchestrator
from src.live_data.rate_limit import TokenBucket
from src.live_data.storage import SCHEMA_VERSION, LiveDataStore, StorageError

from test_live_data_ingest import (  # reuse the fakes rather than fork them
    FakeConnection,
    ScriptedTransport,
    clearinghouse_payload,
    fill_payload,
)

WALLET = "0x" + "ab" * 20
OTHER_WALLET = "0x" + "cd" * 20

FUNDING_ROW = {
    "time": 1_699_000_000_000,
    "delta": {
        "type": "funding",
        "coin": "BTC",
        "usdc": "-0.42",
        "szi": "0.01",
        "fundingRate": "0.0000125",
    },
}


class CoverageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.store = LiveDataStore(Path(self._tempdir.name) / "live.sqlite3")
        self.addCleanup(self.store.close)
        self.now_ms = 1_700_000_000_000
        self.run_ids = iter(f"run-{index}" for index in range(100))

    def build(self, payloads, *, config=None, ws_connection=None):
        config = config or LiveDataConfig(tracked_wallets=(WALLET,))
        transport = ScriptedTransport(payloads)
        rest = HyperliquidRestClient(
            config,
            transport=transport,
            bucket=TokenBucket(1200, 20.0, clock=lambda: 0.0, sleeper=lambda _: None),
        )
        ws = None
        if ws_connection is not None:
            ws = HyperliquidWebSocketClient(
                config,
                connection_factory=lambda _: ws_connection,
                clock=lambda: 0.0,
                sleeper=lambda _: None,
            )
        orchestrator = IngestOrchestrator(
            config,
            self.store,
            rest,
            ws_client=ws,
            clock_ms=lambda: self.now_ms,
            run_id_factory=lambda: next(self.run_ids),
        )
        return orchestrator, transport

    def coverage_of(self, run_id: str) -> dict:
        row = self.store.connection.execute(
            "SELECT coverage FROM ingest_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        return json.loads(row["coverage"])


class BackfillFillsEveryTableTests(CoverageTestCase):
    def test_a_realistic_backfill_leaves_no_declared_table_empty(self) -> None:
        orchestrator, transport = self.build(
            [
                [fill_payload(1, 1_699_000_000_000)],  # userFillsByTime
                [FUNDING_ROW],  # userFunding
                clearinghouse_payload(),  # clearinghouseState
            ]
        )
        self.assertEqual(self.store.count("fills"), 0)
        self.assertEqual(self.store.count("funding"), 0)
        self.assertEqual(self.store.count("positions_snapshot"), 0)

        result = orchestrator.backfill_wallet(WALLET, days=30)

        self.assertGreater(self.store.count("fills"), 0)
        self.assertGreater(self.store.count("funding"), 0)
        self.assertGreater(self.store.count("positions_snapshot"), 0)
        self.assertGreater(self.store.count("wallets"), 0)
        self.assertEqual(
            (result.fills_written, result.funding_written, result.snapshot_taken), (1, 1, True)
        )
        self.assertEqual(
            [body["type"] for body in transport.bodies],
            ["userFillsByTime", "userFunding", "clearinghouseState"],
        )

    def test_a_full_funding_response_is_recorded_as_not_exhausted(self) -> None:
        # The venue caps one userFunding answer at 500 rows and this path does
        # not page. A full answer therefore proves nothing about the rest of
        # the window, and the run must say so instead of claiming completion.
        funding = [
            {**FUNDING_ROW, "time": FUNDING_ROW["time"] + index, "delta": {**FUNDING_ROW["delta"]}}
            for index in range(500)
        ]
        orchestrator, _ = self.build(
            [[fill_payload(1, 1_699_000_000_000)], funding, clearinghouse_payload()]
        )
        result = orchestrator.backfill_wallet(WALLET, days=30)
        self.assertEqual(result.funding_seen, 500)
        self.assertFalse(result.funding_exhausted)
        coverage = self.coverage_of(result.run_id)["funding"]
        self.assertTrue(coverage["attempted"])
        self.assertFalse(coverage["completed"])
        self.assertTrue(coverage["truncated_at_response_cap"])

    def test_backfill_is_idempotent_across_all_three_datasets(self) -> None:
        payloads = [[fill_payload(1, 1_699_000_000_000)], [FUNDING_ROW], clearinghouse_payload()]
        orchestrator, _ = self.build(payloads + list(payloads))
        orchestrator.backfill_wallet(WALLET, days=30)
        second = orchestrator.backfill_wallet(WALLET, days=30)
        self.assertEqual(self.store.count("fills"), 1)
        self.assertEqual(self.store.count("funding"), 1)
        self.assertEqual(self.store.count("positions_snapshot"), 1)
        self.assertEqual((second.fills_written, second.funding_written), (0, 0))


class WatchFillsPositionsTests(CoverageTestCase):
    def test_watch_snapshots_every_tracked_wallet_even_with_no_activity(self) -> None:
        connection = FakeConnection([])  # no frames at all
        config = LiveDataConfig(tracked_wallets=(WALLET, OTHER_WALLET))
        orchestrator, _ = self.build([], config=config, ws_connection=connection)

        result = orchestrator.watch(max_iterations=0)

        # A wallet that trades nothing must still have a position record;
        # otherwise "no rows" is ambiguous between quiet and unobserved.
        self.assertEqual(result.snapshots_taken, 2)
        self.assertEqual(self.store.count("positions_snapshot"), 2)

    def test_the_interval_bounds_repeat_snapshots(self) -> None:
        frames = [json.dumps({"channel": "allMids", "data": {"mids": {"BTC": "1"}}})] * 4
        connection = FakeConnection(frames)
        config = LiveDataConfig(
            tracked_wallets=(WALLET,), tracked_coins=("BTC",), snapshot_interval_seconds=60.0
        )
        orchestrator, _ = self.build([], config=config, ws_connection=connection)
        result = orchestrator.watch(max_iterations=4)
        # The clock never advances in this test, so only the baseline fires.
        self.assertEqual(result.snapshots_taken, 1)

    def test_a_snapshot_failure_is_recorded_without_killing_the_feed(self) -> None:
        # No scripted payload and a non-clearinghouse fallback miss would raise;
        # here the wallet snapshot fails on a malformed response instead.
        connection = FakeConnection([])
        orchestrator, _ = self.build(
            [{"marginSummary": "not-an-object"}], ws_connection=connection
        )
        result = orchestrator.watch(max_iterations=0)
        self.assertEqual(result.snapshots_taken, 0)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("snapshot", result.errors[0])


class CoverageProvenanceTests(CoverageTestCase):
    def test_a_composite_backfill_records_all_three_datasets_as_covered(self) -> None:
        orchestrator, _ = self.build(
            [[fill_payload(1, 1_699_000_000_000)], [FUNDING_ROW], clearinghouse_payload()]
        )
        result = orchestrator.backfill_wallet(WALLET, days=30)
        coverage = self.coverage_of(result.run_id)
        for dataset in ("fills", "funding", "positions"):
            with self.subTest(dataset=dataset):
                self.assertTrue(coverage[dataset]["attempted"])
                self.assertTrue(coverage[dataset]["completed"])
        self.assertEqual(coverage["window"]["days"], 30)

    def test_a_fills_only_backfill_says_it_did_not_attempt_the_others(self) -> None:
        # This is the distinction the schema previously could not express: a run
        # that never tried is not the same as a run that tried and found none.
        orchestrator, _ = self.build([[fill_payload(1, 1_699_000_000_000)]])
        result = orchestrator.backfill_wallet_fills(WALLET, start_time_ms=1)
        coverage = self.coverage_of(result.run_id)
        self.assertTrue(coverage["fills"]["attempted"])
        self.assertFalse(coverage["funding"]["attempted"])
        self.assertFalse(coverage["positions"]["attempted"])

    def test_an_empty_snapshot_is_distinguishable_from_no_snapshot(self) -> None:
        watched, _ = self.build(
            [], config=LiveDataConfig(tracked_wallets=(WALLET,)), ws_connection=FakeConnection([])
        )
        watched_run = watched.watch(max_iterations=0)
        attempted = self.coverage_of(watched_run.run_id)["positions"]

        coins_only, _ = self.build(
            [], config=LiveDataConfig(tracked_coins=("BTC",)), ws_connection=FakeConnection([])
        )
        coins_run = coins_only.watch(max_iterations=0)
        not_attempted = self.coverage_of(coins_run.run_id)["positions"]

        self.assertEqual((attempted["attempted"], attempted["snapshots"]), (True, 1))
        self.assertEqual((not_attempted["attempted"], not_attempted["snapshots"]), (False, 0))

    def test_a_failed_backfill_records_which_dataset_it_reached(self) -> None:
        # Fills succeed, funding payload is malformed: coverage must show fills
        # completed and funding attempted-but-not-completed.
        orchestrator, _ = self.build([[fill_payload(1, 1_699_000_000_000)], {"not": "a list"}])
        with self.assertRaises(Exception):
            orchestrator.backfill_wallet(WALLET, days=30)
        run = self.store.recent_runs()[0]
        coverage = json.loads(run["coverage"])
        self.assertTrue(coverage["fills"]["completed"])
        self.assertTrue(coverage["funding"]["attempted"])
        self.assertFalse(coverage["funding"]["completed"])
        self.assertFalse(coverage["positions"]["attempted"])


class SnapshotBudgetTests(unittest.TestCase):
    """The cadence has to fit the documented 1200 weight/minute IP budget."""

    def test_the_default_cadence_is_a_small_fraction_of_the_budget(self) -> None:
        config = LiveDataConfig()
        snapshots_per_minute = 60.0 / DEFAULT_SNAPSHOT_INTERVAL_SECONDS
        weight_per_minute = (
            MAX_WS_TRACKED_USERS * request_weight("clearinghouseState") * snapshots_per_minute
        )
        self.assertEqual(weight_per_minute, 20.0)  # 10 wallets x weight 2 x 1/min
        self.assertLess(weight_per_minute, config.weight_per_minute * 0.05)

    def test_even_an_aggressive_cadence_stays_inside_the_budget(self) -> None:
        config = LiveDataConfig(snapshot_interval_seconds=5.0)
        snapshots_per_minute = 60.0 / config.snapshot_interval_seconds
        weight_per_minute = (
            MAX_WS_TRACKED_USERS * request_weight("clearinghouseState") * snapshots_per_minute
        )
        self.assertEqual(weight_per_minute, 240.0)
        self.assertLess(weight_per_minute, config.weight_per_minute * 0.25)

    def test_the_wallet_cap_matches_the_documented_websocket_limit(self) -> None:
        self.assertEqual(MAX_WS_TRACKED_USERS, 10)
        with self.assertRaises(ValueError):
            LiveDataConfig(
                tracked_wallets=tuple(
                    "0x" + f"{index:040x}" for index in range(MAX_WS_TRACKED_USERS + 1)
                )
            )


class SchemaMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.path = Path(self._tempdir.name) / "legacy.sqlite3"

    def _write_version_one(self) -> None:
        connection = sqlite3.connect(self.path)
        connection.execute(
            "CREATE TABLE schema_version (version INTEGER NOT NULL PRIMARY KEY, "
            "applied_at_ms INTEGER NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE ingest_runs (run_id TEXT NOT NULL PRIMARY KEY, mode TEXT NOT NULL, "
            "wallet_address TEXT, started_at_ms INTEGER NOT NULL, finished_at_ms INTEGER, "
            "status TEXT NOT NULL, records_seen INTEGER NOT NULL DEFAULT 0, "
            "records_written INTEGER NOT NULL DEFAULT 0, error_count INTEGER NOT NULL DEFAULT 0, "
            "notes TEXT)"
        )
        connection.execute("INSERT INTO schema_version VALUES (1, 0)")
        connection.commit()
        connection.close()

    def test_a_version_one_database_is_migrated_in_place(self) -> None:
        self._write_version_one()
        with LiveDataStore(self.path) as store:
            columns = {
                row["name"]
                for row in store.connection.execute("PRAGMA table_info(ingest_runs)")
            }
            self.assertIn("coverage", columns)
            version = store.connection.execute(
                "SELECT MAX(version) AS v FROM schema_version"
            ).fetchone()["v"]
            self.assertEqual(version, SCHEMA_VERSION)

    def test_a_version_with_no_declared_migration_is_still_refused(self) -> None:
        connection = sqlite3.connect(self.path)
        connection.execute(
            "CREATE TABLE schema_version (version INTEGER NOT NULL PRIMARY KEY, "
            "applied_at_ms INTEGER NOT NULL)"
        )
        connection.execute("INSERT INTO schema_version VALUES (0, 0)")
        connection.commit()
        connection.close()
        with self.assertRaises(StorageError):
            LiveDataStore(self.path)


if __name__ == "__main__":
    unittest.main()
