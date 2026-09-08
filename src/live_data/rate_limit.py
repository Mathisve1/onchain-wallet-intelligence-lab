"""Client-side token bucket for the documented IP weight budget.

The venue publishes an aggregated budget of 1200 request weight per minute per
IP. Staying inside it locally is cheaper and more honest than discovering the
limit through rejected requests, so every REST call spends weight here first.
"""

from __future__ import annotations

import time
from typing import Callable

from .config import LiveDataConfig

Clock = Callable[[], float]
Sleeper = Callable[[float], None]


class RateLimitError(RuntimeError):
    """Raised when a request can never fit the budget, or the clock misbehaves."""


class TokenBucket:
    """Monotonic-clock token bucket with injectable clock and sleeper."""

    def __init__(
        self,
        capacity: float,
        refill_per_second: float,
        *,
        clock: Clock = time.monotonic,
        sleeper: Sleeper = time.sleep,
    ) -> None:
        if capacity <= 0:
            raise RateLimitError("capacity must be positive")
        if refill_per_second <= 0:
            raise RateLimitError("refill rate must be positive")
        self._capacity = float(capacity)
        self._refill_per_second = float(refill_per_second)
        self._clock = clock
        self._sleeper = sleeper
        self._tokens = float(capacity)
        self._updated_at = clock()

    @classmethod
    def from_config(
        cls,
        config: LiveDataConfig,
        *,
        clock: Clock = time.monotonic,
        sleeper: Sleeper = time.sleep,
    ) -> TokenBucket:
        return cls(
            capacity=config.weight_per_minute,
            refill_per_second=config.weight_per_minute / 60.0,
            clock=clock,
            sleeper=sleeper,
        )

    @property
    def capacity(self) -> float:
        return self._capacity

    def available(self) -> float:
        """Current token balance after accounting for elapsed time."""
        self._refill(self._clock())
        return self._tokens

    def _refill(self, now: float) -> None:
        if now < self._updated_at:
            raise RateLimitError("monotonic clock moved backwards")
        elapsed = now - self._updated_at
        self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_per_second)
        self._updated_at = now

    def acquire(self, weight: float) -> float:
        """Spend ``weight``, sleeping if needed. Returns the seconds waited."""
        if weight <= 0:
            raise RateLimitError("request weight must be positive")
        if weight > self._capacity:
            raise RateLimitError(
                f"request weight {weight} exceeds the whole budget {self._capacity}"
            )
        waited = 0.0
        while True:
            now = self._clock()
            self._refill(now)
            if self._tokens >= weight:
                self._tokens -= weight
                return waited
            shortfall = (weight - self._tokens) / self._refill_per_second
            self._sleeper(shortfall)
            waited += shortfall
            # A sleeper that does not advance the clock would spin forever;
            # fail loudly instead of burning the budget in a hot loop.
            if self._clock() <= now:
                raise RateLimitError("sleeper did not advance the clock")
