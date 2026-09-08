from __future__ import annotations

import unittest

from src.live_data.config import LiveDataConfig
from src.live_data.rate_limit import RateLimitError, TokenBucket


class FakeClock:
    """Monotonic clock the test advances explicitly, including via sleep."""

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


class FrozenClock(FakeClock):
    """A sleeper that does not actually advance time."""

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)


class TokenBucketTests(unittest.TestCase):
    def test_bucket_starts_full_and_spends_without_waiting(self) -> None:
        clock = FakeClock()
        bucket = TokenBucket(1200, 20.0, clock=clock, sleeper=clock.sleep)
        self.assertEqual(bucket.available(), 1200)
        self.assertEqual(bucket.acquire(20), 0.0)
        self.assertEqual(bucket.available(), 1180)
        self.assertEqual(clock.slept, [])

    def test_exhausted_budget_throttles_for_the_refill_time(self) -> None:
        clock = FakeClock()
        # 60 weight capacity refilling at 1/second.
        bucket = TokenBucket(60, 1.0, clock=clock, sleeper=clock.sleep)
        bucket.acquire(60)
        waited = bucket.acquire(20)
        self.assertEqual(waited, 20.0)
        self.assertEqual(clock.slept, [20.0])
        self.assertEqual(clock.now, 20.0)

    def test_partial_refill_only_waits_for_the_shortfall(self) -> None:
        clock = FakeClock()
        bucket = TokenBucket(60, 1.0, clock=clock, sleeper=clock.sleep)
        bucket.acquire(60)
        clock.now += 15.0  # 15 tokens have accrued
        self.assertEqual(bucket.acquire(20), 5.0)

    def test_budget_refills_no_further_than_capacity(self) -> None:
        clock = FakeClock()
        bucket = TokenBucket(60, 1.0, clock=clock, sleeper=clock.sleep)
        bucket.acquire(60)
        clock.now += 10_000.0
        self.assertEqual(bucket.available(), 60)

    def test_request_larger_than_the_whole_budget_is_refused(self) -> None:
        bucket = TokenBucket(60, 1.0, clock=FakeClock(), sleeper=lambda _: None)
        with self.assertRaises(RateLimitError):
            bucket.acquire(61)

    def test_nonpositive_weight_is_refused(self) -> None:
        bucket = TokenBucket(60, 1.0, clock=FakeClock(), sleeper=lambda _: None)
        for weight in (0, -1):
            with self.subTest(weight=weight):
                with self.assertRaises(RateLimitError):
                    bucket.acquire(weight)

    def test_invalid_bucket_parameters_are_refused(self) -> None:
        for capacity, rate in ((0, 1.0), (-1, 1.0), (60, 0), (60, -1)):
            with self.subTest(capacity=capacity, rate=rate):
                with self.assertRaises(RateLimitError):
                    TokenBucket(capacity, rate, clock=FakeClock(), sleeper=lambda _: None)

    def test_a_sleeper_that_does_not_advance_the_clock_fails_loudly(self) -> None:
        clock = FrozenClock()
        bucket = TokenBucket(60, 1.0, clock=clock, sleeper=clock.sleep)
        bucket.acquire(60)
        with self.assertRaises(RateLimitError):
            bucket.acquire(20)

    def test_backwards_clock_is_rejected(self) -> None:
        clock = FakeClock()
        clock.now = 100.0
        bucket = TokenBucket(60, 1.0, clock=clock, sleeper=clock.sleep)
        clock.now = 50.0
        with self.assertRaises(RateLimitError):
            bucket.acquire(1)

    def test_from_config_uses_the_documented_per_minute_budget(self) -> None:
        clock = FakeClock()
        bucket = TokenBucket.from_config(LiveDataConfig(), clock=clock, sleeper=clock.sleep)
        self.assertEqual(bucket.capacity, 1200)
        bucket.acquire(1200)
        # 1200 weight per minute refills at 20 per second.
        self.assertEqual(bucket.acquire(20), 1.0)


if __name__ == "__main__":
    unittest.main()
