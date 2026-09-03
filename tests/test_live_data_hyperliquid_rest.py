from __future__ import annotations

import json
import unittest

from src.live_data.config import LiveDataConfig
from src.live_data.hyperliquid_rest import (
    DEFAULT_REQUEST_WEIGHT,
    HttpRequest,
    HttpResponse,
    HyperliquidRestClient,
    RestError,
    RestHttpError,
    build_info_body,
    is_retryable,
    request_weight,
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
        self.assertEqual(request_weight("somethingUndocumented"), DEFAULT_REQUEST_WEIGHT)

    def test_weight_is_spent_before_the_request_is_sent(self) -> None:
        transport = RecordingTransport([ok({"BTC": "1"})])
        bucket = TokenBucket(1200, 20.0, clock=lambda: 0.0, sleeper=lambda _: None)
        client = HyperliquidRestClient(LiveDataConfig(), transport=transport, bucket=bucket)
        client.request("allMids")
        self.assertEqual(bucket.available(), 1198)


class RetryPolicyTests(unittest.TestCase):
    def test_only_429_and_5xx_are_retryable(self) -> None:
        for status in (429, 500, 502, 503, 599):
            self.assertTrue(is_retryable(status), status)
        for status in (200, 201, 301, 400, 401, 403, 404, 422, 600):
            self.assertFalse(is_retryable(status), status)

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
        self.assertEqual(slept, [0.5, 1.0])
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
        self.assertEqual(slept, [0.5, 1.0])

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
