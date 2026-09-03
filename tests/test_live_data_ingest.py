from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from src.live_data.config import LiveDataConfig
from src.live_data.hyperliquid_rest import (
    MAX_FILLS_PER_RESPONSE,
    HttpRequest,
    HttpResponse,
    HyperliquidRestClient,
)
from src.live_data.hyperliquid_ws import HyperliquidWebSocketClient, Subscription
from src.live_data.ingest import IngestError, IngestOrchestrator
from src.live_data.models import PayloadError
from src.live_data.rate_limit import TokenBucket
from src.live_data.storage import RUN_STATUS_COMPLETED, RUN_STATUS_FAILED, LiveDataStore

WALLET = "0x" + "ab" * 20


def fill_payload(tid: int, time_ms: int, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "coin": "BTC",
        "px": "64000.5",
        "sz": "0.01",
        "side": "B",
        "time": time_ms,
        "startPosition": "0.0",
        "dir": "Open Long",
        "closedPnl": "0.0",
        "hash": "0x" + "cd" * 32,
        "oid": 1,
        "crossed": True,
        "fee": "0.32",
        "tid": tid,
        "feeToken": "USDC",
    }
    payload.update(overrides)
    return payload


class ScriptedTransport:
    def __init__(self, payloads: list[object]) -> None:
        self._payloads = list(payloads)
        self.bodies: list[dict[str, Any]] = []

    def __call__(self, request: HttpRequest) -> HttpResponse:
        self.bodies.append(json.loads(request.body))
        if not self._payloads:
            raise AssertionError("more requests issued than the test scripted")
        return HttpResponse(status_code=200, body=json.dumps(self._payloads.pop(0)))


class FakeConnection:
    def __init__(self, inbound: list[str]) -> None:
        self.sent: list[dict[str, Any]] = []
        self.inbound = list(inbound)
        self.closed = False

    def send(self, message: str) -> None:
        self.sent.append(json.loads(message))

    def recv(self) -> str:
        if not self.inbound:
            raise ConnectionResetError("closed")
        return self.inbound.pop(0)

    def close(self) -> None:
        self.closed = True


class IngestTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.store = LiveDataStore(Path(self._tempdir.name) / "live.sqlite3")
        self.addCleanup(self.store.close)
        self.run_ids = iter(f"run-{index}" for index in range(100))
        self.now_ms = 1_700_000_000_000

    def build(
        self,
        payloads: list[object],
        *,
        config: LiveDataConfig | None = None,
        ws_connection: FakeConnection | None = None,
    ) -> tuple[IngestOrchestrator, ScriptedTransport]:
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


class BackfillTests(IngestTestCase):
    def test_a_single_short_page_ends_the_backfill(self) -> None:
        orchestrator, transport = self.build([[fill_payload(1, 1_699_000_000_000)]])
        result = orchestrator.backfill_wallet_fills(WALLET, start_time_ms=1_000)
        self.assertEqual((result.pages, result.records_seen, result.records_written), (1, 1, 1))
        self.assertEqual(
            transport.bodies[0],
            {"type": "userFillsByTime", "user": WALLET, "startTime": 1_000},
        )
        self.assertEqual(self.store.count("fills"), 1)

    def test_a_full_page_pages_forward_from_the_last_timestamp(self) -> None:
        first_page = [
            fill_payload(index, 1_699_000_000_000 + index) for index in range(MAX_FILLS_PER_RESPONSE)
        ]
        second_page = [fill_payload(9_999, 1_699_000_001_000)]
        orchestrator, transport = self.build([first_page, second_page])
        result = orchestrator.backfill_wallet_fills(WALLET, start_time_ms=1_000)
        self.assertEqual(result.pages, 2)
        self.assertEqual(transport.bodies[1]["startTime"], 1_699_000_000_000 + 499)
        self.assertEqual(result.forced_cursor_advances, 0)
        self.assertEqual(self.store.count("fills"), MAX_FILLS_PER_RESPONSE + 1)

    def test_overlapping_pages_do_not_duplicate_rows(self) -> None:
        page = [fill_payload(index, 1_699_000_000_000 + index) for index in range(MAX_FILLS_PER_RESPONSE)]
        # The second page repeats the boundary fill, as the venue does.
        orchestrator, _ = self.build([page, [page[-1]]])
        result = orchestrator.backfill_wallet_fills(WALLET, start_time_ms=1_000)
        self.assertEqual(result.records_seen, MAX_FILLS_PER_RESPONSE + 1)
        self.assertEqual(result.records_written, MAX_FILLS_PER_RESPONSE)
        self.assertEqual(self.store.count("fills"), MAX_FILLS_PER_RESPONSE)

    def test_a_full_page_inside_one_millisecond_forces_the_cursor_forward(self) -> None:
        stuck = [fill_payload(index, 1_699_000_000_000) for index in range(MAX_FILLS_PER_RESPONSE)]
        orchestrator, transport = self.build([stuck, []])
        result = orchestrator.backfill_wallet_fills(WALLET, start_time_ms=1_699_000_000_000)
        self.assertEqual(result.forced_cursor_advances, 1)
        self.assertEqual(transport.bodies[1]["startTime"], 1_699_000_000_001)
        run = self.store.recent_runs()[0]
        self.assertIn("forced cursor advances: 1", run["notes"])

    def test_pagination_stops_at_the_page_budget(self) -> None:
        page = [fill_payload(index, 1_699_000_000_000 + index) for index in range(MAX_FILLS_PER_RESPONSE)]
        second = [
            fill_payload(index + 1000, 1_699_000_001_000 + index)
            for index in range(MAX_FILLS_PER_RESPONSE)
        ]
        orchestrator, _ = self.build([page, second])
        result = orchestrator.backfill_wallet_fills(WALLET, start_time_ms=1_000, max_pages=2)
        self.assertEqual(result.pages, 2)

    def test_the_end_of_the_window_stops_pagination(self) -> None:
        page = [fill_payload(index, 1_699_000_000_000 + index) for index in range(MAX_FILLS_PER_RESPONSE)]
        orchestrator, transport = self.build([page])
        result = orchestrator.backfill_wallet_fills(
            WALLET, start_time_ms=1_000, end_time_ms=1_699_000_000_100
        )
        self.assertEqual(result.pages, 1)
        self.assertEqual(transport.bodies[0]["endTime"], 1_699_000_000_100)

    def test_the_run_is_recorded_as_completed_with_its_counts(self) -> None:
        orchestrator, _ = self.build([[fill_payload(1, 1_699_000_000_000)]])
        result = orchestrator.backfill_wallet_fills(WALLET, start_time_ms=1)
        run = self.store.recent_runs()[0]
        self.assertEqual(run["run_id"], result.run_id)
        self.assertEqual(run["mode"], "backfill_fills")
        self.assertEqual(run["status"], RUN_STATUS_COMPLETED)
        self.assertEqual(run["wallet_address"], WALLET)
        self.assertEqual((run["records_seen"], run["records_written"]), (1, 1))
        self.assertEqual(self.store.count("wallets"), 1)

    def test_a_malformed_page_fails_the_run_and_records_the_error(self) -> None:
        orchestrator, _ = self.build([[fill_payload(1, 1_699_000_000_000, px="oops")]])
        with self.assertRaises(PayloadError):
            orchestrator.backfill_wallet_fills(WALLET, start_time_ms=1)
        run = self.store.recent_runs()[0]
        self.assertEqual(run["status"], RUN_STATUS_FAILED)
        self.assertEqual(run["error_count"], 1)
        self.assertIn("PayloadError", run["notes"])
        self.assertEqual(self.store.count("fills"), 0)

    def test_a_non_array_response_is_rejected(self) -> None:
        orchestrator, _ = self.build([{"fills": []}])
        with self.assertRaises(PayloadError):
            orchestrator.backfill_wallet_fills(WALLET, start_time_ms=1)

    def test_invalid_backfill_arguments_are_refused(self) -> None:
        orchestrator, _ = self.build([])
        with self.assertRaises(ValueError):
            orchestrator.backfill_wallet_fills("0xnope", start_time_ms=1)
        with self.assertRaises(IngestError):
            orchestrator.backfill_wallet_fills(WALLET, start_time_ms=-1)
        with self.assertRaises(IngestError):
            orchestrator.backfill_wallet_fills(WALLET, start_time_ms=10, end_time_ms=5)
        with self.assertRaises(IngestError):
            orchestrator.backfill_wallet_fills(WALLET, start_time_ms=1, max_pages=0)
        with self.assertRaises(IngestError):
            orchestrator.backfill_days(WALLET, 0)

    def test_backfill_days_builds_a_trailing_window(self) -> None:
        orchestrator, transport = self.build([[]])
        orchestrator.backfill_days(WALLET, 2)
        body = transport.bodies[0]
        self.assertEqual(body["endTime"], self.now_ms)
        self.assertEqual(body["startTime"], self.now_ms - 2 * 86_400_000)


class SnapshotAndFundingTests(IngestTestCase):
    def test_clearinghouse_snapshot_is_persisted_with_its_raw_payload(self) -> None:
        summary = {
            "accountValue": "10000.0",
            "totalNtlPos": "2500.0",
            "totalRawUsd": "7500.0",
            "totalMarginUsed": "250.0",
        }
        payload = {
            "marginSummary": dict(summary),
            "crossMarginSummary": dict(summary),
            "withdrawable": "9750.0",
            "time": 1_699_000_000_000,
            "assetPositions": [],
        }
        orchestrator, _ = self.build([payload])
        state = orchestrator.snapshot_wallet_state(WALLET)
        self.assertEqual(state.snapshot_time_ms, 1_699_000_000_000)
        row = self.store.connection.execute("SELECT * FROM positions_snapshot").fetchone()
        self.assertEqual(json.loads(row["raw_payload"]), payload)

    def test_funding_rows_are_persisted(self) -> None:
        rows = [
            {
                "time": 1_699_000_000_000,
                "delta": {
                    "type": "funding",
                    "coin": "BTC",
                    "usdc": "-0.42",
                    "szi": "0.01",
                    "fundingRate": "0.0000125",
                },
            }
        ]
        orchestrator, _ = self.build([rows])
        self.assertEqual(orchestrator.backfill_wallet_funding(WALLET), 1)
        self.assertEqual(self.store.count("funding"), 1)


class WatchTests(IngestTestCase):
    def test_watch_subscribes_to_every_tracked_wallet_and_persists_fills(self) -> None:
        frames = [
            json.dumps(
                {
                    "channel": "userFills",
                    "data": {
                        "user": WALLET,
                        "isSnapshot": True,
                        "fills": [fill_payload(1, 1_699_000_000_000)],
                    },
                }
            ),
            json.dumps({"channel": "allMids", "data": {"mids": {"BTC": "64000.5", "SOL": "150"}}}),
        ]
        connection = FakeConnection(frames)
        config = LiveDataConfig(tracked_wallets=(WALLET,), tracked_coins=("BTC",))
        orchestrator, _ = self.build([], config=config, ws_connection=connection)
        result = orchestrator.watch(max_iterations=2)

        self.assertEqual(
            connection.sent,
            [
                {"method": "subscribe", "subscription": {"type": "userFills", "user": WALLET}},
                {"method": "subscribe", "subscription": {"type": "allMids"}},
            ],
        )
        self.assertEqual((result.fills_seen, result.fills_written), (1, 1))
        self.assertEqual(result.mids_written, 1)  # only the tracked coin is stored
        self.assertEqual(self.store.count("fills"), 1)
        self.assertTrue(connection.closed)

    def test_a_repeated_snapshot_frame_does_not_duplicate_fills(self) -> None:
        frame = json.dumps(
            {
                "channel": "userFills",
                "data": {"user": WALLET, "fills": [fill_payload(1, 1_699_000_000_000)]},
            }
        )
        connection = FakeConnection([frame, frame])
        orchestrator, _ = self.build([], ws_connection=connection)
        result = orchestrator.watch(max_iterations=2)
        self.assertEqual((result.fills_seen, result.fills_written), (2, 1))
        self.assertEqual(self.store.count("fills"), 1)

    def test_a_malformed_frame_is_recorded_as_a_handler_error(self) -> None:
        frame = json.dumps({"channel": "userFills", "data": {"user": WALLET, "fills": "nope"}})
        connection = FakeConnection([frame])
        orchestrator, _ = self.build([], ws_connection=connection)
        result = orchestrator.watch(max_iterations=1)
        self.assertEqual(len(result.errors), 1)
        run = self.store.recent_runs()[0]
        self.assertEqual(run["status"], RUN_STATUS_COMPLETED)
        self.assertEqual(run["error_count"], 1)

    def test_watch_records_run_provenance(self) -> None:
        connection = FakeConnection([json.dumps({"channel": "pong"})])
        orchestrator, _ = self.build([], ws_connection=connection)
        result = orchestrator.watch(max_iterations=1)
        run = self.store.recent_runs()[0]
        self.assertEqual(run["run_id"], result.run_id)
        self.assertEqual(run["mode"], "watch")
        self.assertIn("reconnects: 0", run["notes"])

    def test_watch_without_a_websocket_client_is_refused(self) -> None:
        orchestrator, _ = self.build([])
        with self.assertRaises(IngestError):
            orchestrator.watch(max_iterations=1)

    def test_watch_with_nothing_configured_is_refused(self) -> None:
        orchestrator, _ = self.build(
            [], config=LiveDataConfig(), ws_connection=FakeConnection([])
        )
        with self.assertRaises(IngestError):
            orchestrator.build_watch_subscriptions()

    def test_subscriptions_cover_wallets_and_mids(self) -> None:
        config = LiveDataConfig(tracked_wallets=(WALLET,), tracked_coins=("BTC", "ETH"))
        orchestrator, _ = self.build([], config=config, ws_connection=FakeConnection([]))
        self.assertEqual(
            orchestrator.build_watch_subscriptions(),
            (Subscription(type="userFills", user=WALLET), Subscription(type="allMids")),
        )


if __name__ == "__main__":
    unittest.main()
