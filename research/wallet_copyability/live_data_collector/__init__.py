"""Outer collector layer for the read-only Hyperliquid live data pipeline.

This package owns the concrete network transports and the executable entry
point. It depends on ``src.live_data`` for the deterministic core; the core
never depends on this package, so ``src/`` stays free of network machinery and
can be validated as such.

Observation only: the transports here can issue exactly the read-only requests
the core constructs. Nothing in this package can place an order.
"""

from .transports import build_default_connection_factory, build_urllib_transport

__all__ = ["build_default_connection_factory", "build_urllib_transport"]
