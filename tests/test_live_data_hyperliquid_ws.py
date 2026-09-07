from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from src.live_data.config import LiveDataConfig
from src.live_data.hyperliquid_ws import (
    CHANNEL_BY_SUBSCRIPTION,
    HyperliquidWebSocketClient,
    Subscription,
    WebSocketError,
    build_subscribe_message,
    build_unsubscribe_message,
)

WALLET = "0x" + "ab" * 20
OTHER_WALLET = "0x" + "cd" * 20


class FakeConnection:
    """In-memory websocket stand-in that replays a queued script of frames."""

    def __init__(self, inbound: list[str] | None = None) -> None:
        self.sent: list[dict[str, Any]] = []
        self.inbound = list(inbound or [])
        self.closed = False

    def send(self, message: str) -> None:
        self.sent.append(json.loads(message))

    def recv(self) -> str:
        if not self.inbound:
            raise ConnectionResetError("peer closed the connection")
        return self.inbound.pop(0)

    def close(self) -> None:
        self.closed = True


class FakeFactory:
    def __init__(self, connections: list[FakeConnection]) -> None:
        self._connections = list(connections)
        self.urls: list[str] = []
        self.created: list[FakeConnection] = []

    def __call__(self, url: str) -> FakeConnection:
        self.urls.append(url)
        if not self._connections:
            raise ConnectionRefusedError("no more connections scripted")
        connection = self._connections.pop(0)
        self.created.append(connection)
        return connection


class Clock:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def build_client(
    connections: list[FakeConnection], **kwargs: Any
) -> tuple[HyperliquidWebSocketClient, FakeFactory, Clock]:
    factory = FakeFactory(connections)
    clock = Clock()
    client = HyperliquidWebSocketClient(
        LiveDataConfig(),
        connection_factory=factory,
        clock=clock,
        sleeper=clock.sleep,
        backoff_base_seconds=1.0,
        **kwargs,
    )
    return client, factory, clock


class SubscriptionShapeTests(unittest.TestCase):
    def test_every_supported_subscription_builds_the_documented_payload(self) -> None:
        cases = [
            (Subscription(type="allMids"), {"type": "allMids"}),
            (Subscription(type="trades", coin="BTC"), {"type": "trades", "coin": "BTC"}),
            (Subscription(type="l2Book", coin="ETH"), {"type": "l2Book", "coin": "ETH"}),
            (Subscription(type="userFills", user=WALLET), {"type": "userFills", "user": WALLET}),
            (Subscription(type="userEvents", user=WALLET), {"type": "userEvents", "user": WALLET}),
        ]
        for subscription, expected in cases:
            with self.subTest(subscription=expected):
                self.assertEqual(subscription.as_payload(), expected)
                self.assertEqual(
                    build_subscribe_message(subscription),
                    {"method": "subscribe", "subscription": expected},
                )
                self.assertEqual(
                    build_unsubscribe_message(subscription),
                    {"method": "unsubscribe", "subscription": expected},
                )

    def test_user_events_arrives_on_the_user_channel(self) -> None:
        self.assertEqual(Subscription(type="userEvents", user=WALLET).channel, "user")
        self.assertEqual(Subscription(type="userFills", user=WALLET).channel, "userFills")
        self.assertEqual(CHANNEL_BY_SUBSCRIPTION["userEvents"], "user")

    def test_addresses_and_coins_are_validated(self) -> None:
        self.assertEqual(Subscription(type="userFills", user="0x" + "AB" * 20).user, WALLET)
        with self.assertRaises(ValueError):
            Subscription(type="userFills", user="0xdeadbeef")
        with self.assertRaises(ValueError):
            Subscription(type="trades", coin="")

    def test_missing_or_extraneous_subscription_fields_are_refused(self) -> None:
        cases = [
            {"type": "unknownStream"},
            {"type": "trades"},
            {"type": "l2Book"},
            {"type": "userFills"},
            {"type": "userEvents"},
            {"type": "allMids", "coin": "BTC"},
            {"type": "trades", "coin": "BTC", "user": WALLET},
            {"type": "userFills", "user": WALLET, "coin": "BTC"},
        ]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(WebSocketError):
                    Subscription(**kwargs)


class SubscribeUnsubscribeTests(unittest.TestCase):
    def test_connect_sends_every_registered_subscription(self) -> None:
        connection = FakeConnection()
        client, factory, _ = build_client([connection])
        client.subscribe(Subscription(type="allMids"), lambda _: None)
        client.subscribe(Subscription(type="userFills", user=WALLET), lambda _: None)
        self.assertEqual(connection.sent, [])  # nothing sent before connecting
        client.connect()
        self.assertEqual(factory.urls, ["wss://api.hyperliquid.xyz/ws"])
        self.assertEqual(
            connection.sent,
            [
                {"method": "subscribe", "subscription": {"type": "allMids"}},
                {"method": "subscribe", "subscription": {"type": "userFills", "user": WALLET}},
            ],
        )

    def test_subscribing_while_connected_sends_immediately(self) -> None:
        connection = FakeConnection()
        client, _, _ = build_client([connection])
        client.connect()
        client.subscribe(Subscription(type="trades", coin="BTC"), lambda _: None)
        self.assertEqual(
            connection.sent,
            [{"method": "subscribe", "subscription": {"type": "trades", "coin": "BTC"}}],
        )

    def test_second_handler_on_the_same_subscription_does_not_resend(self) -> None:
        connection = FakeConnection()
        client, _, _ = build_client([connection])
        client.connect()
        subscription = Subscription(type="trades", coin="BTC")
        client.subscribe(subscription, lambda _: None)
        client.subscribe(subscription, lambda _: None)
        self.assertEqual(len(connection.sent), 1)

    def test_unsubscribe_sends_the_frame_and_forgets_the_subscription(self) -> None:
        connection = FakeConnection()
        client, _, _ = build_client([connection])
        subscription = Subscription(type="l2Book", coin="ETH")
        client.subscribe(subscription, lambda _: None)
        client.connect()
        client.unsubscribe(subscription)
        self.assertEqual(
            connection.sent[-1],
            {"method": "unsubscribe", "subscription": {"type": "l2Book", "coin": "ETH"}},
        )
        self.assertEqual(client.subscriptions, ())

    def test_unsubscribing_an_unknown_subscription_is_an_error(self) -> None:
        client, _, _ = build_client([FakeConnection()])
        with self.assertRaises(WebSocketError):
            client.unsubscribe(Subscription(type="allMids"))

    def test_sending_on_a_closed_connection_is_refused(self) -> None:
        client, _, _ = build_client([FakeConnection()])
        client.connect()
        client.close()
        self.assertFalse(client.is_connected)
        with self.assertRaises(WebSocketError):
            client._send({"method": "ping"})

    def test_heartbeat_is_a_noop_while_disconnected(self) -> None:
        client, _, _ = build_client([FakeConnection()])
        self.assertFalse(client.heartbeat_if_due())


class HeartbeatTests(unittest.TestCase):
    def test_ping_is_withheld_until_the_heartbeat_window_elapses(self) -> None:
        connection = FakeConnection()
        client, _, clock = build_client([connection])
        client.connect()
        clock.now = 49.0
        self.assertFalse(client.heartbeat_if_due())
        clock.now = 50.0
        self.assertTrue(client.heartbeat_if_due())
        self.assertEqual(connection.sent[-1], {"method": "ping"})
        self.assertEqual(client.pings_sent, 1)

    def test_any_outbound_frame_resets_the_heartbeat_timer(self) -> None:
        connection = FakeConnection()
        client, _, clock = build_client([connection])
        client.connect()
        clock.now = 40.0
        client.subscribe(Subscription(type="allMids"), lambda _: None)
        clock.now = 89.0
        self.assertFalse(client.heartbeat_if_due())
        clock.now = 90.0
        self.assertTrue(client.heartbeat_if_due())

    def test_pong_frames_are_counted(self) -> None:
        client, _, _ = build_client([FakeConnection()])
        client.connect()
        self.assertEqual(client.dispatch(json.dumps({"channel": "pong"})), "pong")
        self.assertEqual(client.pongs_received, 1)


class DispatchTests(unittest.TestCase):
    def test_messages_route_to_the_handler_of_their_channel(self) -> None:
        received: list[dict[str, Any]] = []
        client, _, _ = build_client([FakeConnection()])
        client.subscribe(Subscription(type="userFills", user=WALLET), received.append)
        client.subscribe(Subscription(type="userEvents", user=WALLET), received.append)
        client.connect()
        client.dispatch(
            json.dumps({"channel": "userFills", "data": {"user": WALLET, "fills": []}})
        )
        client.dispatch(json.dumps({"channel": "user", "data": {"fills": []}}))
        self.assertEqual([message["channel"] for message in received], ["userFills", "user"])

    def test_subscription_acknowledgements_are_counted_not_routed(self) -> None:
        client, _, _ = build_client([FakeConnection()])
        client.connect()
        client.dispatch(json.dumps({"channel": "subscriptionResponse", "data": {}}))
        self.assertEqual(client.acknowledged_subscriptions, 1)
        self.assertEqual(client.unrouted_messages, 0)

    def test_unknown_channels_are_counted_rather_than_crashing_the_feed(self) -> None:
        client, _, _ = build_client([FakeConnection()])
        client.connect()
        client.dispatch(json.dumps({"channel": "candle", "data": {}}))
        self.assertEqual(client.unrouted_messages, 1)

    def test_malformed_frames_are_rejected(self) -> None:
        client, _, _ = build_client([FakeConnection()])
        client.connect()
        for raw in ("not json", "[]", '"text"', "{}", '{"channel": 7}', '{"channel": ""}'):
            with self.subTest(raw=raw):
                with self.assertRaises(WebSocketError):
                    client.dispatch(raw)

    def test_venue_error_frames_are_raised(self) -> None:
        client, _, _ = build_client([FakeConnection()])
        client.connect()
        with self.assertRaises(WebSocketError):
            client.dispatch(json.dumps({"channel": "error", "data": "bad subscription"}))

    def test_a_failing_handler_is_recorded_without_dropping_the_feed(self) -> None:
        def explode(_: dict[str, Any]) -> None:
            raise ValueError("handler bug")

        client, _, _ = build_client([FakeConnection()])
        client.subscribe(Subscription(type="allMids"), explode)
        client.connect()
        client.dispatch(json.dumps({"channel": "allMids", "data": {"mids": {}}}))
        self.assertEqual(len(client.handler_errors), 1)
        self.assertIn("handler bug", client.handler_errors[0])


class UserScopedRoutingTests(unittest.TestCase):
    """Frames must reach exactly the wallet they belong to.

    Routing on the channel alone would deliver every wallet's frames to every
    wallet's handler, so per-wallet provenance would depend on each handler
    remembering to filter. The wallet is part of the routing key instead.
    """

    def test_route_key_carries_the_wallet_only_for_user_scoped_channels(self) -> None:
        self.assertEqual(
            Subscription(type="userFills", user=WALLET).route_key, ("userFills", WALLET)
        )
        self.assertEqual(Subscription(type="userEvents", user=WALLET).route_key, ("user", WALLET))
        self.assertEqual(Subscription(type="allMids").route_key, ("allMids", None))
        self.assertEqual(Subscription(type="trades", coin="BTC").route_key, ("trades", None))

    def test_a_frame_reaches_only_the_wallet_it_names(self) -> None:
        first: list[dict[str, Any]] = []
        second: list[dict[str, Any]] = []
        client, _, _ = build_client([FakeConnection()])
        client.subscribe(Subscription(type="userFills", user=WALLET), first.append)
        client.subscribe(Subscription(type="userFills", user=OTHER_WALLET), second.append)
        client.connect()
        client.dispatch(
            json.dumps({"channel": "userFills", "data": {"user": WALLET, "fills": []}})
        )
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])

    def test_a_frame_for_an_untracked_wallet_is_unrouted_not_misdelivered(self) -> None:
        received: list[dict[str, Any]] = []
        client, _, _ = build_client([FakeConnection()])
        client.subscribe(Subscription(type="userFills", user=WALLET), received.append)
        client.connect()
        client.dispatch(
            json.dumps({"channel": "userFills", "data": {"user": OTHER_WALLET, "fills": []}})
        )
        self.assertEqual(received, [])
        self.assertEqual(client.unrouted_messages, 1)

    def test_unsubscribing_one_wallet_leaves_the_other_subscribed_and_routed(self) -> None:
        first: list[dict[str, Any]] = []
        second: list[dict[str, Any]] = []
        connection = FakeConnection()
        client, _, _ = build_client([connection])
        subscription_a = Subscription(type="userFills", user=WALLET)
        subscription_b = Subscription(type="userFills", user=OTHER_WALLET)
        client.subscribe(subscription_a, first.append)
        client.subscribe(subscription_b, second.append)
        client.connect()
        client.unsubscribe(subscription_a)
        self.assertEqual(
            connection.sent[-1],
            {"method": "unsubscribe", "subscription": {"type": "userFills", "user": WALLET}},
        )
        self.assertEqual(client.subscriptions, (subscription_b,))
        client.dispatch(
            json.dumps({"channel": "userFills", "data": {"user": WALLET, "fills": []}})
        )
        client.dispatch(
            json.dumps({"channel": "userFills", "data": {"user": OTHER_WALLET, "fills": []}})
        )
        self.assertEqual(first, [])
        self.assertEqual(len(second), 1)
        self.assertEqual(client.unrouted_messages, 1)

    def test_reconnect_resubscribes_every_wallet_and_routing_survives(self) -> None:
        first_connection = FakeConnection()  # drops on the first recv
        second_connection = FakeConnection(
            [json.dumps({"channel": "userFills", "data": {"user": OTHER_WALLET, "fills": []}})]
        )
        client, factory, _ = build_client([first_connection, second_connection])
        first: list[dict[str, Any]] = []
        second: list[dict[str, Any]] = []
        client.subscribe(Subscription(type="userFills", user=WALLET), first.append)
        client.subscribe(Subscription(type="userFills", user=OTHER_WALLET), second.append)
        client.connect()

        self.assertFalse(client.poll_once())  # socket drops, triggers reconnect
        self.assertEqual(len(factory.created), 2)
        # Both wallets must be restored; dropping one would silently stop
        # observing that wallet for the rest of the run.
        self.assertEqual(
            second_connection.sent,
            [
                {"method": "subscribe", "subscription": {"type": "userFills", "user": WALLET}},
                {
                    "method": "subscribe",
                    "subscription": {"type": "userFills", "user": OTHER_WALLET},
                },
            ],
        )
        self.assertTrue(client.poll_once())
        self.assertEqual(first, [])
        self.assertEqual(len(second), 1)

    def test_user_events_route_when_exactly_one_subscription_is_open(self) -> None:
        received: list[dict[str, Any]] = []
        client, _, _ = build_client([FakeConnection()])
        client.subscribe(Subscription(type="userEvents", user=WALLET), received.append)
        client.connect()
        client.dispatch(json.dumps({"channel": "user", "data": {"fills": []}}))
        self.assertEqual(len(received), 1)
        self.assertEqual(client.ambiguous_messages, 0)

    def test_user_events_fail_closed_when_two_wallets_are_watched(self) -> None:
        # WsUserEvent carries no wallet, so with two subscriptions open the
        # frame is unattributable. Dropping it is correct; handing it to both
        # would fabricate an observation for a wallet that produced none.
        first: list[dict[str, Any]] = []
        second: list[dict[str, Any]] = []
        client, _, _ = build_client([FakeConnection()])
        client.subscribe(Subscription(type="userEvents", user=WALLET), first.append)
        client.subscribe(Subscription(type="userEvents", user=OTHER_WALLET), second.append)
        client.connect()
        client.dispatch(json.dumps({"channel": "user", "data": {"fills": []}}))
        self.assertEqual((first, second), ([], []))
        self.assertEqual(client.ambiguous_messages, 1)

    def test_a_user_fills_frame_that_names_no_wallet_is_dropped(self) -> None:
        received: list[dict[str, Any]] = []
        client, _, _ = build_client([FakeConnection()])
        client.subscribe(Subscription(type="userFills", user=WALLET), received.append)
        client.connect()
        for raw in (
            json.dumps({"channel": "userFills", "data": {"fills": []}}),
            json.dumps({"channel": "userFills", "data": None}),
            json.dumps({"channel": "userFills", "data": {"user": 7, "fills": []}}),
        ):
            with self.subTest(raw=raw):
                client.dispatch(raw)
        self.assertEqual(received, [])
        self.assertEqual(client.ambiguous_messages, 3)

    def test_public_channels_still_route_without_a_wallet(self) -> None:
        received: list[dict[str, Any]] = []
        client, _, _ = build_client([FakeConnection()])
        client.subscribe(Subscription(type="allMids"), received.append)
        client.subscribe(Subscription(type="userFills", user=WALLET), received.append)
        client.connect()
        client.dispatch(json.dumps({"channel": "allMids", "data": {"mids": {"BTC": "1"}}}))
        self.assertEqual(len(received), 1)
        self.assertEqual(client.ambiguous_messages, 0)


class ReconnectTests(unittest.TestCase):
    def test_a_dropped_socket_reconnects_and_resubscribes(self) -> None:
        first = FakeConnection([json.dumps({"channel": "allMids", "data": {"mids": {}}})])
        second = FakeConnection([json.dumps({"channel": "allMids", "data": {"mids": {}}})])
        client, factory, clock = build_client([first, second])
        received: list[dict[str, Any]] = []
        client.subscribe(Subscription(type="allMids"), received.append)
        client.connect()

        self.assertTrue(client.poll_once())  # first frame
        self.assertFalse(client.poll_once())  # socket drops, triggers reconnect
        self.assertTrue(client.poll_once())  # frame from the new socket

        self.assertTrue(first.closed)
        self.assertEqual(len(factory.created), 2)
        self.assertEqual(
            second.sent, [{"method": "subscribe", "subscription": {"type": "allMids"}}]
        )
        self.assertEqual(client.reconnects, 1)
        self.assertEqual(len(received), 2)

    def test_reconnect_backoff_grows_exponentially_and_is_capped(self) -> None:
        client, _, clock = build_client(
            [FakeConnection()], max_backoff_seconds=4.0, max_reconnects=10
        )
        # No connections are scripted after the first, so every attempt fails.
        client.connect()
        with self.assertRaises(WebSocketError):
            client.poll_once()
        self.assertEqual(clock.slept, [1.0, 2.0, 4.0, 4.0, 4.0, 4.0, 4.0, 4.0, 4.0, 4.0])

    def test_reconnect_budget_is_enforced(self) -> None:
        client, _, _ = build_client([FakeConnection()], max_reconnects=2)
        client.connect()
        with self.assertRaises(WebSocketError):
            client.poll_once()
        self.assertEqual(client.reconnects, 2)


class RunLoopTests(unittest.TestCase):
    def test_run_is_bounded_and_heartbeats_while_pumping(self) -> None:
        frames = [json.dumps({"channel": "allMids", "data": {"mids": {}}})] * 3
        connection = FakeConnection(frames)
        client, _, clock = build_client([connection])
        client.subscribe(Subscription(type="allMids"), lambda _: None)
        client.connect()
        clock.now = 100.0  # well past the heartbeat window
        self.assertEqual(client.run(max_iterations=3), 3)
        self.assertEqual(client.pings_sent, 1)

    def test_run_honours_the_stop_predicate(self) -> None:
        connection = FakeConnection([json.dumps({"channel": "pong"})] * 5)
        client, _, _ = build_client([connection])
        client.connect()
        self.assertEqual(client.run(max_iterations=5, stop=lambda: True), 0)

    def test_negative_iteration_budget_is_refused(self) -> None:
        client, _, _ = build_client([FakeConnection()])
        with self.assertRaises(WebSocketError):
            client.run(max_iterations=-1)



class ChannelRoutedFanOutTests(unittest.TestCase):
    """One frame on a channel-routed feed must reach a handler exactly once."""

    def _client(self, coins):
        config = LiveDataConfig(database_path=Path("x.sqlite3"), tracked_coins=tuple(coins))
        return HyperliquidWebSocketClient(config, connection_factory=lambda url: None)

    def test_a_shared_handler_runs_once_however_many_coins_are_subscribed(self) -> None:
        """Regression: ``trades/BTC``, ``trades/ETH`` and ``trades/SOL`` all key
        to ``("trades", None)``, and ``watch.py`` registers one shared handler
        under each. Collecting handlers per matching subscription therefore ran
        it three times for one frame, tripling ``trades_seen``, the
        ``ingest_runs`` coverage counts and the discovery evidence, and running
        the write path three times on the hot tape path.
        """
        client = self._client(("BTC", "ETH", "SOL"))
        seen = []

        def handler(message):
            seen.append(message["channel"])

        for coin in ("BTC", "ETH", "SOL"):
            client.subscribe(Subscription(type="trades", coin=coin), handler)

        client.dispatch(json.dumps({"channel": "trades", "data": [{"coin": "BTC"}]}))
        self.assertEqual(len(seen), 1)

    def test_two_distinct_handlers_on_one_route_both_still_run(self) -> None:
        client = self._client(("BTC", "ETH"))
        seen = []
        client.subscribe(Subscription(type="trades", coin="BTC"), lambda m: seen.append("a"))
        client.subscribe(Subscription(type="trades", coin="ETH"), lambda m: seen.append("b"))
        client.dispatch(json.dumps({"channel": "trades", "data": []}))
        self.assertEqual(sorted(seen), ["a", "b"])

    def test_the_same_handler_registered_twice_on_one_subscription_runs_once(self) -> None:
        client = self._client(("BTC",))
        seen = []

        def handler(message):
            seen.append(1)

        subscription = Subscription(type="trades", coin="BTC")
        client.subscribe(subscription, handler)
        client.subscribe(subscription, handler)
        client.dispatch(json.dumps({"channel": "trades", "data": []}))
        self.assertEqual(len(seen), 1)


class MalformedWalletFrameTests(unittest.TestCase):
    def test_an_unusable_wallet_is_dropped_instead_of_ending_the_session(self) -> None:
        """Regression: ``normalize_wallet_address`` raises ``ConfigError``, a
        ``ValueError``, which ``dispatch``'s ``except WebSocketError`` did not
        catch -- so one malformed ``userFills`` frame escaped ``poll_once`` and
        aborted the whole watch session instead of being counted and dropped.
        """
        config = LiveDataConfig(database_path=Path("x.sqlite3"), tracked_coins=("BTC",))
        client = HyperliquidWebSocketClient(config, connection_factory=lambda url: None)
        client.subscribe(
            Subscription(type="userFills", user="0x" + "ab" * 20), lambda m: None
        )
        channel = client.dispatch(
            json.dumps({"channel": "userFills", "data": {"user": "nonsense", "fills": []}})
        )
        self.assertEqual(channel, "userFills")
        self.assertEqual(client.ambiguous_messages, 1)

if __name__ == "__main__":
    unittest.main()
