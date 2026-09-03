from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.live_data.config import LiveDataConfig
from src.live_data.hyperliquid_rest import HttpRequest, HttpResponse, HyperliquidRestClient
from src.live_data.hyperliquid_ws import HyperliquidWebSocketClient
from src.live_data.ingest import IngestOrchestrator
from src.live_data.models import PayloadError
from src.live_data.rate_limit import TokenBucket
from src.live_data.storage import SCHEMA_VERSION, LiveDataStore, StorageError
from src.live_data.trades import DISCOVERY_LABEL, Trade, make_trades_handler, parse_trades

BUYER = "0x" + "a" * 40
SELLER = "0x" + "b" * 40
THIRD = "0x" + "c" * 40


def trade_payload(tid: int, *, buyer: str = BUYER, seller: str = SELLER, coin: str = "BTC") -> dict:
    return {
        "coin": coin,
        "side": "B",
        "px": "64000.5",
        "sz": "0.01",
        "hash": "0x" + "1" * 64,
        "time": 1_699_000_000_000 + tid,
        "tid": tid,
        "users": [buyer, seller],
    }


class TradeParsingTests(unittest.TestCase):
    def test_a_trade_names_both_counterparties_in_order(self) -> None:
        trade = Trade.parse(trade_payload(7, buyer=BUYER.upper()))
        self.assertEqual(trade.trade_id, 7)
        self.assertEqual(trade.price, Decimal("64000.5"))
        self.assertEqual(trade.wallets, (BUYER, SELLER))  # normalized to lowercase

    def test_a_trade_with_the_wrong_number_of_users_is_rejected(self) -> None:
        payload = trade_payload(1)
        payload["users"] = [BUYER]
        with self.assertRaises(PayloadError):
            Trade.parse(payload)

    def test_an_unknown_side_is_rejected(self) -> None:
        payload = trade_payload(1)
        payload["side"] = "X"
        with self.assertRaises(PayloadError):
            Trade.parse(payload)

    def test_parse_trades_requires_a_list(self) -> None:
        with self.assertRaises(PayloadError):
            parse_trades({"not": "a list"})


class DiscoveryHandlerTests(unittest.TestCase):
    def test_each_wallet_is_discovered_once_however_often_it_trades(self) -> None:
        observed: list[str] = []
        tallies: list[tuple[int, int, int]] = []
        handler = make_trades_handler(
            write_trades=lambda rows: len(rows),
            observe_wallet=observed.append,
            on_trades=lambda *args: tallies.append(args),
        )
        handler({"channel": "trades", "data": [trade_payload(1), trade_payload(2)]})
        handler({"channel": "trades", "data": [trade_payload(3, buyer=THIRD)]})
        # Every appearance is observed (last-seen bookkeeping)...
        self.assertEqual(observed.count(BUYER), 2)
        self.assertEqual(observed.count(SELLER), 3)
        # ...but discovery counts an address exactly once across frames.
        self.assertEqual(tallies, [(2, 2, 2), (1, 1, 1)])


class TradeStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.db_path = Path(self._tempdir.name) / "live.sqlite3"
        self.store = LiveDataStore(self.db_path)
        self.addCleanup(self.store.close)

    def rows(self, *tids: int, **kwargs: Any) -> list[tuple[Trade, dict]]:
        return [(Trade.parse(trade_payload(tid, **kwargs)), trade_payload(tid, **kwargs)) for tid in tids]

    def test_trades_are_idempotent_on_coin_and_trade_id(self) -> None:
        first = self.store.write_trades(self.rows(1, 2), ingested_at_ms=1)
        second = self.store.write_trades(self.rows(2, 3), ingested_at_ms=2)
        self.assertEqual((first.seen, first.written), (2, 2))
        self.assertEqual((second.seen, second.written), (2, 1))
        self.assertEqual(self.store.count("trades"), 3)

    def test_the_same_trade_id_on_another_coin_is_a_different_trade(self) -> None:
        self.store.write_trades(self.rows(1), ingested_at_ms=1)
        self.store.write_trades(self.rows(1, coin="ETH"), ingested_at_ms=1)
        self.assertEqual(self.store.count("trades"), 2)

    def test_most_active_wallets_counts_both_sides_of_the_tape(self) -> None:
        self.store.write_trades(self.rows(1, 2), ingested_at_ms=1)
        self.store.write_trades(self.rows(3, buyer=THIRD), ingested_at_ms=1)
        ranked = self.store.most_active_wallets(10)
        self.assertEqual(
            [(row["address"], row["trade_count"]) for row in ranked],
            [(SELLER, 3), (BUYER, 2), (THIRD, 1)],
        )
        self.assertEqual(ranked[0]["first_trade_ms"], 1_699_000_000_001)
        self.assertEqual(ranked[0]["last_trade_ms"], 1_699_000_000_003)

    def test_most_active_wallets_rejects_a_nonpositive_limit(self) -> None:
        with self.assertRaises(StorageError):
            self.store.most_active_wallets(0)

    def test_a_version_two_database_gains_the_trades_table_in_place(self) -> None:
        self.store.close()
        connection = sqlite3.connect(self.db_path)
        connection.execute("DROP TABLE trades")
        connection.execute("DELETE FROM schema_version")
        connection.execute("INSERT INTO schema_version (version, applied_at_ms) VALUES (2, 0)")
        connection.commit()
        connection.close()
        with LiveDataStore(self.db_path) as upgraded:
            self.assertEqual(upgraded.count("trades"), 0)
            version = upgraded.connection.execute(
                "SELECT MAX(version) AS v FROM schema_version"
            ).fetchone()["v"]
            self.assertEqual(version, SCHEMA_VERSION)


class ScriptedTransport:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    def __call__(self, request: HttpRequest) -> HttpResponse:
        body = json.loads(request.body)
        self.requests.append(body)
        if body.get("type") == "clearinghouseState":
            return HttpResponse(
                status_code=200,
                body=json.dumps(
                    {
                        "marginSummary": {
                            "accountValue": "100",
                            "totalNtlPos": "0",
                            "totalRawUsd": "100",
                            "totalMarginUsed": "0",
                        },
                        "crossMarginSummary": {
                            "accountValue": "100",
                            "totalNtlPos": "0",
                            "totalRawUsd": "100",
                            "totalMarginUsed": "0",
                        },
                        "crossMaintenanceMarginUsed": "0",
                        "withdrawable": "100",
                        "assetPositions": [],
                        "time": 1_699_000_000_000,
                    }
                ),
            )
        raise AssertionError(f"unexpected request {body}")


class FakeConnection:
    def __init__(self, inbound: list[str]) -> None:
        self.inbound = list(inbound)

    def send(self, message: str) -> None:
        pass

    def recv(self) -> str:
        if not self.inbound:
            raise ConnectionResetError("closed")
        return self.inbound.pop(0)

    def close(self) -> None:
        pass


class WatchDiscoveryTests(unittest.TestCase):
    def test_a_coins_only_watch_discovers_wallets_and_records_them(self) -> None:
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        store = LiveDataStore(Path(tempdir.name) / "live.sqlite3")
        self.addCleanup(store.close)
        config = LiveDataConfig(tracked_coins=("BTC",))
        transport = ScriptedTransport()
        rest = HyperliquidRestClient(
            config,
            transport=transport,
            bucket=TokenBucket(1200, 20.0, clock=lambda: 0.0, sleeper=lambda _: None),
        )
        frames = [
            json.dumps({"channel": "trades", "data": [trade_payload(1), trade_payload(2)]}),
            json.dumps({"channel": "trades", "data": [trade_payload(3, buyer=THIRD)]}),
            json.dumps({"channel": "trades", "data": [trade_payload(3, buyer=THIRD)]}),  # dup
        ]
        ws = HyperliquidWebSocketClient(
            config,
            connection_factory=lambda _: FakeConnection(frames),
            clock=lambda: 0.0,
            sleeper=lambda _: None,
        )
        orchestrator = IngestOrchestrator(
            config, store, rest, ws_client=ws, clock_ms=lambda: 1_700_000_000_000,
            run_id_factory=lambda: "run-discovery",
        )
        result = orchestrator.watch(max_iterations=3)

        self.assertEqual((result.trades_seen, result.trades_written), (4, 3))
        self.assertEqual(result.wallets_discovered, 3)
        self.assertEqual(store.count("trades"), 3)
        self.assertEqual(store.count("wallets"), 3)
        labels = {
            row["label"] for row in store.connection.execute("SELECT label FROM wallets")
        }
        self.assertEqual(labels, {DISCOVERY_LABEL})
        # No tracked wallets, so no clearinghouse polling and no REST weight.
        self.assertEqual(transport.requests, [])
        self.assertEqual(orchestrator.consumed_weight, 0)

        run = store.recent_runs(1)[0]
        coverage = json.loads(run["coverage"])
        self.assertEqual(coverage["trades"]["coins"], ["BTC"])
        self.assertEqual(coverage["trades"]["wallets_discovered"], 3)
        self.assertEqual(coverage["requests"], {"attempted": 0, "retried": 0, "weight": 0})
        self.assertEqual(store.most_active_wallets(1)[0]["address"], SELLER)


if __name__ == "__main__":
    unittest.main()
