from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from src.live_data.models import ClearinghouseState, Fill, parse_funding
from src.live_data.storage import (
    RUN_STATUS_COMPLETED,
    SCHEMA_VERSION,
    LiveDataStore,
    StorageError,
)

WALLET = "0x" + "ab" * 20
OTHER_WALLET = "0x" + "cd" * 20


def fill_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "coin": "BTC",
        "px": "64000.5",
        "sz": "0.01",
        "side": "B",
        "time": 1_700_000_000_000,
        "startPosition": "0.0",
        "dir": "Open Long",
        "closedPnl": "0.0",
        "hash": "0x" + "cd" * 32,
        "oid": 987654321,
        "crossed": True,
        "fee": "0.32",
        "tid": 123456789012345,
        "feeToken": "USDC",
    }
    payload.update(overrides)
    return payload


def clearinghouse_payload() -> dict[str, object]:
    summary = {
        "accountValue": "10000.0",
        "totalNtlPos": "2500.0",
        "totalRawUsd": "7500.0",
        "totalMarginUsed": "250.0",
    }
    return {
        "marginSummary": dict(summary),
        "crossMarginSummary": dict(summary),
        "withdrawable": "9750.0",
        "time": 1_700_000_000_000,
        "assetPositions": [],
    }


class StoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.db_path = Path(self._tempdir.name) / "live.sqlite3"
        self.store = LiveDataStore(self.db_path)
        self.addCleanup(self.store.close)


class SchemaTests(StoreTestCase):
    def test_initialization_creates_every_table_at_the_current_version(self) -> None:
        names = {
            row["name"]
            for row in self.store.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        self.assertLessEqual(
            {
                "schema_version",
                "wallets",
                "fills",
                "positions_snapshot",
                "mids",
                "funding",
                "ingest_runs",
            },
            names,
        )
        version = self.store.connection.execute(
            "SELECT MAX(version) AS v FROM schema_version"
        ).fetchone()["v"]
        self.assertEqual(version, SCHEMA_VERSION)

    def test_reopening_an_initialized_database_is_a_noop(self) -> None:
        self.store.close()
        with LiveDataStore(self.db_path) as reopened:
            self.assertEqual(reopened.count("fills"), 0)

    def test_a_newer_schema_version_is_refused(self) -> None:
        self.store.connection.execute(
            "INSERT INTO schema_version (version, applied_at_ms) VALUES (?, 1)",
            (SCHEMA_VERSION + 1,),
        )
        self.store.connection.commit()
        self.store.close()
        with self.assertRaises(StorageError):
            LiveDataStore(self.db_path)

    def test_an_older_schema_version_without_a_migration_is_refused(self) -> None:
        stale = Path(self._tempdir.name) / "stale.sqlite3"
        connection = sqlite3.connect(stale)
        connection.execute(
            "CREATE TABLE schema_version (version INTEGER NOT NULL PRIMARY KEY, "
            "applied_at_ms INTEGER NOT NULL)"
        )
        connection.execute("INSERT INTO schema_version VALUES (0, 0)")
        connection.commit()
        connection.close()
        with self.assertRaises(StorageError):
            LiveDataStore(stale)

    def test_a_schema_version_table_without_a_version_is_refused(self) -> None:
        broken = Path(self._tempdir.name) / "broken.sqlite3"
        connection = sqlite3.connect(broken)
        connection.execute(
            "CREATE TABLE schema_version (version INTEGER NOT NULL PRIMARY KEY, "
            "applied_at_ms INTEGER NOT NULL)"
        )
        connection.commit()
        connection.close()
        with self.assertRaises(StorageError):
            LiveDataStore(broken)

    def test_opening_an_uninitialized_database_without_create_is_refused(self) -> None:
        missing = Path(self._tempdir.name) / "absent.sqlite3"
        with self.assertRaises(StorageError):
            LiveDataStore(missing, create=False)


class FillIdempotencyTests(StoreTestCase):
    def test_the_same_fill_written_twice_yields_one_row(self) -> None:
        payload = fill_payload()
        rows = [(Fill.parse(payload, WALLET), payload)]
        first = self.store.write_fills(rows, source="test", ingested_at_ms=1)
        second = self.store.write_fills(rows, source="test", ingested_at_ms=2)
        self.assertEqual((first.seen, first.written), (1, 1))
        self.assertEqual((second.seen, second.written, second.duplicates), (1, 0, 1))
        self.assertEqual(self.store.count("fills"), 1)

    def test_a_repeated_batch_with_one_new_fill_writes_only_the_new_row(self) -> None:
        first_payload = fill_payload()
        second_payload = fill_payload(tid=999, time=1_700_000_001_000)
        self.store.write_fills(
            [(Fill.parse(first_payload, WALLET), first_payload)], source="test", ingested_at_ms=1
        )
        result = self.store.write_fills(
            [
                (Fill.parse(first_payload, WALLET), first_payload),
                (Fill.parse(second_payload, WALLET), second_payload),
            ],
            source="test",
            ingested_at_ms=2,
        )
        self.assertEqual((result.seen, result.written), (2, 1))
        self.assertEqual(self.store.count("fills"), 2)

    def test_each_natural_key_component_distinguishes_a_row(self) -> None:
        base = fill_payload()
        variants = [
            (base, WALLET),
            (base, OTHER_WALLET),
            (fill_payload(coin="ETH"), WALLET),
            (fill_payload(tid=1), WALLET),
            (fill_payload(time=1_700_000_009_000), WALLET),
        ]
        for payload, wallet in variants:
            self.store.write_fills(
                [(Fill.parse(payload, wallet), payload)], source="test", ingested_at_ms=1
            )
        self.assertEqual(self.store.count("fills"), len(variants))

    def test_the_raw_payload_is_stored_next_to_the_parsed_row(self) -> None:
        payload = fill_payload()
        self.store.write_fills(
            [(Fill.parse(payload, WALLET), payload)], source="rest:userFills", ingested_at_ms=7
        )
        row = self.store.connection.execute("SELECT * FROM fills").fetchone()
        self.assertEqual(json.loads(row["raw_payload"]), payload)
        self.assertEqual(row["source"], "rest:userFills")
        self.assertEqual(row["ingested_at_ms"], 7)

    def test_decimals_round_trip_exactly_as_text(self) -> None:
        payload = fill_payload(px="0.000000000000000001", sz="123456789.123456789")
        self.store.write_fills(
            [(Fill.parse(payload, WALLET), payload)], source="test", ingested_at_ms=1
        )
        row = self.store.connection.execute("SELECT price, size FROM fills").fetchone()
        self.assertEqual(Decimal(row["price"]), Decimal("0.000000000000000001"))
        self.assertEqual(Decimal(row["size"]), Decimal("123456789.123456789"))

    def test_non_fill_input_is_refused(self) -> None:
        with self.assertRaises(StorageError):
            self.store.write_fills([({"coin": "BTC"}, {})], source="test", ingested_at_ms=1)

    def test_invalid_write_metadata_is_refused(self) -> None:
        payload = fill_payload()
        rows = [(Fill.parse(payload, WALLET), payload)]
        with self.assertRaises(StorageError):
            self.store.write_fills(rows, source="", ingested_at_ms=1)
        with self.assertRaises(StorageError):
            self.store.write_fills(rows, source="test", ingested_at_ms=0)

    def test_latest_fill_time_tracks_the_newest_row(self) -> None:
        self.assertIsNone(self.store.latest_fill_time_ms(WALLET))
        payload = fill_payload()
        self.store.write_fills(
            [(Fill.parse(payload, WALLET), payload)], source="test", ingested_at_ms=1
        )
        self.assertEqual(self.store.latest_fill_time_ms(WALLET), 1_700_000_000_000)


class OtherTableIdempotencyTests(StoreTestCase):
    def test_wallet_upsert_keeps_the_first_sighting_and_advances_the_last(self) -> None:
        self.store.upsert_wallet(WALLET, observed_at_ms=100, label="candidate")
        self.store.upsert_wallet(WALLET, observed_at_ms=300)
        self.store.upsert_wallet(WALLET, observed_at_ms=200)
        row = self.store.connection.execute("SELECT * FROM wallets").fetchone()
        self.assertEqual(self.store.count("wallets"), 1)
        self.assertEqual(row["first_seen_at_ms"], 100)
        self.assertEqual(row["last_seen_at_ms"], 300)
        self.assertEqual(row["label"], "candidate")

    def test_position_snapshots_are_idempotent_on_wallet_and_time(self) -> None:
        payload = clearinghouse_payload()
        state = ClearinghouseState.parse(payload, WALLET)
        self.assertEqual(self.store.write_position_snapshot(state, payload, ingested_at_ms=1).written, 1)
        self.assertEqual(self.store.write_position_snapshot(state, payload, ingested_at_ms=2).written, 0)
        self.assertEqual(self.store.count("positions_snapshot"), 1)

    def test_mids_are_idempotent_on_coin_and_observation_time(self) -> None:
        mids = {"BTC": Decimal("64000.5"), "ETH": Decimal("3200")}
        first = self.store.write_mids(mids, mids, observed_at_ms=10, ingested_at_ms=10)
        second = self.store.write_mids(mids, mids, observed_at_ms=10, ingested_at_ms=11)
        third = self.store.write_mids(mids, mids, observed_at_ms=11, ingested_at_ms=11)
        self.assertEqual((first.written, second.written, third.written), (2, 0, 2))
        self.assertEqual(self.store.count("mids"), 4)

    def test_funding_rows_are_idempotent(self) -> None:
        rows = [
            {
                "time": 1_700_000_000_000,
                "delta": {
                    "type": "funding",
                    "coin": "BTC",
                    "usdc": "-0.42",
                    "szi": "0.01",
                    "fundingRate": "0.0000125",
                },
            }
        ]
        deltas = parse_funding(rows, WALLET)
        pairs = list(zip(deltas, rows, strict=True))
        self.assertEqual(self.store.write_funding(pairs, ingested_at_ms=1).written, 1)
        self.assertEqual(self.store.write_funding(pairs, ingested_at_ms=2).written, 0)
        self.assertEqual(self.store.count("funding"), 1)


class IngestRunProvenanceTests(StoreTestCase):
    def test_a_run_records_its_start_and_completion(self) -> None:
        self.store.start_run("run-1", mode="backfill_fills", started_at_ms=100, wallet_address=WALLET)
        self.store.finish_run(
            "run-1",
            finished_at_ms=200,
            status=RUN_STATUS_COMPLETED,
            records_seen=10,
            records_written=7,
            notes="ok",
        )
        run = self.store.recent_runs()[0]
        self.assertEqual(run["run_id"], "run-1")
        self.assertEqual(run["wallet_address"], WALLET)
        self.assertEqual((run["records_seen"], run["records_written"]), (10, 7))
        self.assertEqual(run["status"], RUN_STATUS_COMPLETED)
        self.assertEqual(run["finished_at_ms"], 200)

    def test_duplicate_run_ids_are_refused(self) -> None:
        self.store.start_run("run-1", mode="watch", started_at_ms=1)
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.start_run("run-1", mode="watch", started_at_ms=2)

    def test_finishing_an_unknown_run_is_refused(self) -> None:
        with self.assertRaises(StorageError):
            self.store.finish_run(
                "ghost",
                finished_at_ms=1,
                status=RUN_STATUS_COMPLETED,
                records_seen=0,
                records_written=0,
            )

    def test_unknown_run_status_is_refused(self) -> None:
        self.store.start_run("run-1", mode="watch", started_at_ms=1)
        with self.assertRaises(StorageError):
            self.store.finish_run(
                "run-1",
                finished_at_ms=2,
                status="probably-fine",
                records_seen=0,
                records_written=0,
            )

    def test_malformed_run_metadata_is_refused(self) -> None:
        with self.assertRaises(StorageError):
            self.store.start_run("", mode="watch", started_at_ms=1)
        with self.assertRaises(StorageError):
            self.store.start_run("run-2", mode="", started_at_ms=1)
        with self.assertRaises(StorageError):
            self.store.start_run("run-3", mode="watch", started_at_ms=0)

    def test_recent_runs_are_newest_first_and_bounded(self) -> None:
        for index in range(3):
            self.store.start_run(f"run-{index}", mode="watch", started_at_ms=index + 1)
        runs = self.store.recent_runs(limit=2)
        self.assertEqual([run["run_id"] for run in runs], ["run-2", "run-1"])
        with self.assertRaises(StorageError):
            self.store.recent_runs(limit=0)

    def test_counting_an_unknown_table_is_refused(self) -> None:
        with self.assertRaises(StorageError):
            self.store.count("sqlite_master")


if __name__ == "__main__":
    unittest.main()
