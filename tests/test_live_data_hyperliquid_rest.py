from __future__ import annotations

import json
import unittest

from src.live_data.config import LiveDataConfig
from src.live_data.hyperliquid_rest import (
    DEFAULT_REQUEST_WEIGHT,
    SIZE_WEIGHT_ROWS_PER_UNIT,
    HttpRequest,
    HttpResponse,
    HyperliquidRestClient,
    RestError,
    RestHttpError,
    build_info_body,
    is_retryable,
    request_weight,
    response_weight,
)
from src.live_data.models import PayloadError
from src.live_data.rate_limit import TokenBucket

WALLET = "0x" + "ab" * 20


class RecordingTransport:
    """Fake transport returning queued responses and recording every request."""

    def __init__(self, responses: list[HttpResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[HttpRequest] = []

    def __call__(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        if not self._responses:
            raise AssertionError("transport called more times than the test queued responses")
        return self._responses.pop(0)

    @property
    def bodies(self) -> list[dict[str, object]]:
        return [json.loads(request.body) for request in self.requests]


def ok(payload: object) -> HttpResponse:
    return HttpResponse(status_code=200, body=json.dumps(payload))


def build_client(
    responses: list[HttpResponse], *, max_retries: int = 3
) -> tuple[HyperliquidRestClient, RecordingTransport, list[float]]:
    transport = RecordingTransport(responses)
    slept: list[float] = []
    config = LiveDataConfig(max_retries=max_retries)
    client = HyperliquidRestClient(
        config,
        transport=transport,
        bucket=TokenBucket(1200, 20.0, clock=lambda: 0.0, sleeper=lambda _: None),
        sleeper=slept.append,
        backoff_base_seconds=0.5,
    )
    return client, transport, slept


class RequestBodyConstructionTests(unittest.TestCase):
    def test_each_supported_request_type_builds_the_documented_body(self) -> None:
        self.assertEqual(build_info_body("meta"), {"type": "meta"})
        self.assertEqual(build_info_body("allMids"), {"type": "allMids"})
        self.assertEqual(
            build_info_body("clearinghouseState", user=WALLET),
            {"type": "clearinghouseState", "user": WALLET},
        )
        self.assertEqual(
            build_info_body("userFills", user=WALLET), {"type": "userFills", "user": WALLET}
        )
        self.assertEqual(
            build_info_body("userFills", user=WALLET, aggregate_by_time=False),
            {"type": "userFills", "user": WALLET, "aggregateByTime": False},
        )
        self.assertEqual(
            build_info_body("userFillsByTime", user=WALLET, start_time=100, end_time=200),
            {"type": "userFillsByTime", "user": WALLET, "startTime": 100, "endTime": 200},
        )
        self.assertEqual(
            build_info_body("userFunding", user=WALLET), {"type": "userFunding", "user": WALLET}
        )
        self.assertEqual(
            build_info_body("openOrders", user=WALLET), {"type": "openOrders", "user": WALLET}
        )

    def test_candle_snapshot_nests_its_parameters_under_req(self) -> None:
        # The venue takes candle parameters under "req", unlike every other
        # request type here, which take them at the top level.
        self.assertEqual(
            build_info_body(
                "candleSnapshot", coin="BTC", interval="15m", start_time=100, end_time=200
            ),
            {
                "type": "candleSnapshot",
                "req": {"coin": "BTC", "interval": "15m", "startTime": 100, "endTime": 200},
            },
        )

    def test_address_is_canonicalized_inside_the_request_body(self) -> None:
        body = build_info_body("userFills", user="0x" + "AB" * 20)
        self.assertEqual(body["user"], WALLET)

    def test_optional_fields_are_omitted_rather_than_sent_as_null(self) -> None:
        body = build_info_body("userFillsByTime", user=WALLET, start_time=1, end_time=None)
        self.assertNotIn("endTime", body)
        self.assertNotIn("aggregateByTime", body)

    def test_unsupported_request_types_are_refused(self) -> None:
        for request_type in ("", "order", "cancel", "l2Book", "userRole", "META"):
            with self.subTest(request_type=request_type):
                with self.assertRaises(RestError):
                    build_info_body(request_type, user=WALLET)

    def test_missing_or_malformed_parameters_are_refused(self) -> None:
        with self.assertRaises(RestError):
            build_info_body("userFillsByTime", user=WALLET)  # no start_time
        with self.assertRaises(RestError):
            build_info_body("userFillsByTime", user=WALLET, start_time="100")
        with self.assertRaises(RestError):
            build_info_body("userFillsByTime", user=WALLET, start_time=-1)
        with self.assertRaises(RestError):
            build_info_body("userFillsByTime", user=WALLET, start_time=200, end_time=100)
        with self.assertRaises(RestError):
            build_info_body("userFills", user=WALLET, aggregate_by_time="yes")
        with self.assertRaises(RestError):
            build_info_body("allMids", dex=7)
        with self.assertRaises(ValueError):
            build_info_body("clearinghouseState", user="not-an-address")

    def test_unknown_parameters_are_refused_rather_than_forwarded(self) -> None:
        with self.assertRaises(RestError):
            build_info_body("meta", user=WALLET)
        with self.assertRaises(RestError):
            build_info_body("userFills", user=WALLET, startTime=1)
        with self.assertRaises(RestError):
            build_info_body("clearinghouseState", user=WALLET, start_time=1)


class RequestWeightTests(unittest.TestCase):
    def test_documented_weights(self) -> None:
        self.assertEqual(request_weight("allMids"), 2)
        self.assertEqual(request_weight("clearinghouseState"), 2)
        self.assertEqual(request_weight("userFillsByTime"), 20)
        self.assertEqual(request_weight("candleSnapshot"), 20)
        self.assertEqual(request_weight("somethingUndocumented"), DEFAULT_REQUEST_WEIGHT)

    def test_weight_is_spent_before_the_request_is_sent(self) -> None:
        transport = RecordingTransport([ok({"BTC": "1"})])
        bucket = TokenBucket(1200, 20.0, clock=lambda: 0.0, sleeper=lambda _: None)
        client = HyperliquidRestClient(LiveDataConfig(), transport=transport, bucket=bucket)
        client.request("allMids")
        self.assertEqual(bucket.available(), 1198)

    def test_response_weight_uses_the_documented_divisor_for_each_type(self) -> None:
        # The venue documents one extra unit per 20 items for the fill and
        # funding endpoints and one per 60 items for candleSnapshot.
        self.assertEqual(SIZE_WEIGHT_ROWS_PER_UNIT["userFills"], 20)
        self.assertEqual(SIZE_WEIGHT_ROWS_PER_UNIT["userFillsByTime"], 20)
        self.assertEqual(SIZE_WEIGHT_ROWS_PER_UNIT["userFunding"], 20)
        self.assertEqual(SIZE_WEIGHT_ROWS_PER_UNIT["candleSnapshot"], 60)
        self.assertEqual(response_weight("userFills", 2000), 20 + 100)
        self.assertEqual(response_weight("candleSnapshot", 5000), 20 + 83)
        self.assertEqual(response_weight("userFunding", 60), 20 + 3)
        self.assertEqual(response_weight("userFills", 0), 20)

    def test_a_type_with_no_documented_surcharge_pays_only_its_base_weight(self) -> None:
        self.assertNotIn("allMids", SIZE_WEIGHT_ROWS_PER_UNIT)
        self.assertEqual(response_weight("allMids", 5000), request_weight("allMids"))


class ResponseSizeWeightTests(unittest.TestCase):
    def test_a_2000_row_fill_response_consumes_base_plus_row_surcharge(self) -> None:
        client, transport, _ = build_client([ok([{}] * 2000)])
        client.request("userFills", user=WALLET)
        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(client.consumed_weight, 20 + 100)

    def test_a_5000_row_candle_response_uses_the_sixty_row_divisor(self) -> None:
        client, transport, _ = build_client([ok([{}] * 5000)])
        client.request(
            "candleSnapshot", coin="BTC", interval="15m", start_time=1, end_time=2
        )
        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(client.consumed_weight, 20 + 83)

    def test_a_dict_response_consumes_only_the_base_weight(self) -> None:
        client, transport, _ = build_client([ok({"BTC": "64000.0"})])
        client.request("allMids")
        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(client.consumed_weight, request_weight("allMids"))

    def test_the_surcharge_is_actually_drawn_from_the_bucket(self) -> None:
        transport = RecordingTransport([ok([{}] * 2000)])
        bucket = TokenBucket(1200, 20.0, clock=lambda: 0.0, sleeper=lambda _: None)
        client = HyperliquidRestClient(
            LiveDataConfig(),
            transport=transport,
            bucket=bucket,
            sleeper=lambda _: None,
        )
        client.request("userFills", user=WALLET)
        self.assertEqual(bucket.available(), 1200 - (20 + 100))
        self.assertEqual(client.consumed_weight, 20 + 100)


class RetryPolicyTests(unittest.TestCase):
    def test_only_429_and_5xx_are_retryable(self) -> None:
        for status in (429, 500, 502, 503, 599):
            self.assertTrue(is_retryable(status), status)
        for status in (200, 201, 301, 400, 401, 403, 404, 422, 600):
            self.assertFalse(is_retryable(status), status)

    def test_every_attempt_including_retries_spends_its_weight(self) -> None:
        # A retry is a real request against the venue's IP budget. Spending
        # weight once per logical request would under-report consumption by up
        # to max_retries + 1 times, precisely while we are being throttled.
        transport = RecordingTransport([HttpResponse(429, "rate limited")] * 4)
        bucket = TokenBucket(1200, 20.0, clock=lambda: 0.0, sleeper=lambda _: None)
        client = HyperliquidRestClient(
            LiveDataConfig(max_retries=3),
            transport=transport,
            bucket=bucket,
            sleeper=lambda _: None,
        )
        before = bucket.available()
        with self.assertRaises(RestHttpError):
            client.request("allMids")

        issued = len(transport.requests)
        spent = before - bucket.available()
        self.assertEqual(issued, 4)  # one attempt plus three retries
        self.assertEqual(client.attempted_requests, issued)
        self.assertEqual(spent, request_weight("allMids") * issued)

    def test_weight_accounting_holds_for_a_heavier_request_type(self) -> None:
        transport = RecordingTransport([HttpResponse(500, "boom")] * 3)
        bucket = TokenBucket(1200, 20.0, clock=lambda: 0.0, sleeper=lambda _: None)
        client = HyperliquidRestClient(
            LiveDataConfig(max_retries=2),
            transport=transport,
            bucket=bucket,
            sleeper=lambda _: None,
        )
        before = bucket.available()
        with self.assertRaises(RestHttpError):
            client.request("userFills", user=WALLET)
        issued = len(transport.requests)
        self.assertEqual(issued, 3)
        self.assertEqual(before - bucket.available(), request_weight("userFills") * issued)

    def test_429_is_retried_with_exponential_backoff(self) -> None:
        client, transport, slept = build_client(
            [
                HttpResponse(429, "rate limited"),
                HttpResponse(429, "rate limited"),
                ok({"BTC": "64000.0"}),
            ]
        )
        self.assertEqual(client.request("allMids"), {"BTC": "64000.0"})
        self.assertEqual(len(transport.requests), 3)
        self.assertEqual(slept, [5.0, 10.0])
        self.assertEqual(client.retried_requests, 2)

    def test_server_errors_are_retried(self) -> None:
        client, transport, _ = build_client([HttpResponse(503, "down"), ok({"BTC": "1"})])
        client.request("allMids")
        self.assertEqual(len(transport.requests), 2)

    def test_client_errors_are_not_retried(self) -> None:
        for status in (400, 404, 422):
            with self.subTest(status=status):
                client, transport, slept = build_client([HttpResponse(status, "nope")])
                with self.assertRaises(RestHttpError) as caught:
                    client.request("allMids")
                self.assertEqual(caught.exception.status_code, status)
                self.assertEqual(len(transport.requests), 1)
                self.assertEqual(slept, [])

    def test_retries_stop_at_the_configured_budget(self) -> None:
        client, transport, slept = build_client([HttpResponse(500, "boom")] * 3, max_retries=2)
        with self.assertRaises(RestHttpError):
            client.request("allMids")
        self.assertEqual(len(transport.requests), 3)
        self.assertEqual(slept, [5.0, 10.0])

    def test_non_json_success_body_is_rejected(self) -> None:
        client, _, _ = build_client([HttpResponse(200, "<html>maintenance</html>")])
        with self.assertRaises(RestError):
            client.request("allMids")


class TypedWrapperTests(unittest.TestCase):
    def test_requests_only_ever_target_the_info_endpoint(self) -> None:
        client, transport, _ = build_client([ok({"BTC": "1"}), ok([])])
        client.request("allMids")
        client.request("userFills", user=WALLET)
        for request in transport.requests:
            self.assertEqual(request.url, "https://api.hyperliquid.xyz/info")
            self.assertEqual(request.method, "POST")

    def test_typed_wrappers_parse_their_payloads(self) -> None:
        client, transport, _ = build_client(
            [
                ok({"universe": [{"name": "BTC", "szDecimals": 5, "maxLeverage": 40}]}),
                ok({"BTC": "64000.0"}),
                ok([]),
            ]
        )
        self.assertEqual(client.meta().universe[0].name, "BTC")
        self.assertEqual(str(client.all_mids()["BTC"]), "64000.0")
        self.assertEqual(client.user_fills(WALLET), ())
        self.assertEqual(transport.bodies[2], {"type": "userFills", "user": WALLET})

    def test_malformed_response_payload_is_rejected_by_the_typed_wrapper(self) -> None:
        client, _, _ = build_client([ok({"universe": "not-a-list"})])
        with self.assertRaises(PayloadError):
            client.meta()

    def test_user_fills_by_time_body_carries_the_time_window(self) -> None:
        client, transport, _ = build_client([ok([])])
        client.user_fills_by_time(WALLET, start_time=10, end_time=20)
        self.assertEqual(
            transport.bodies[0],
            {"type": "userFillsByTime", "user": WALLET, "startTime": 10, "endTime": 20},
        )


if __name__ == "__main__":
    unittest.main()
