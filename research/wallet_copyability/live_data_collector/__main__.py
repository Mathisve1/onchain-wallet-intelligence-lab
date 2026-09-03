"""Executable entry point for the read-only live data pipeline.

Run from the repository root::

    python -m research.wallet_copyability.live_data_collector status
    python -m research.wallet_copyability.live_data_collector backfill --wallet 0x... --days 30

This is the composition root: it is the one place that builds concrete network
transports and hands them to the deterministic core. Argument parsing itself
lives in ``src.live_data.cli`` and stays free of I/O.
"""

from __future__ import annotations

import sys
from typing import Sequence

from src.live_data.cli import Dependencies, main as run_cli

from .transports import build_default_connection_factory, build_urllib_transport


def build_dependencies() -> Dependencies:
    """Assemble the concrete transports the core needs to reach the venue."""
    return Dependencies(
        transport=build_urllib_transport(),
        connection_factory=build_default_connection_factory(),
    )


def main(argv: Sequence[str] | None = None) -> int:
    return run_cli(argv, dependencies=build_dependencies())


if __name__ == "__main__":
    raise SystemExit(main())
