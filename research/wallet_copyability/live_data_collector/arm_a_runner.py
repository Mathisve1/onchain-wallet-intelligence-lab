"""Arm A: the historical early read, ``T0-52d`` to ``T0-7d`` on 15-minute candles.

The arm's specification lives here; the run itself is :mod:`.l2_arm_runner`,
shared with arm B so both arms are computed the same way. Arm A decides
nothing: its file always carries ``decision: null``.

Run from the repository root::

    python -m research.wallet_copyability.live_data_collector.arm_a_runner \\
        --db <DB> --cohort <freeze record> --candles-json <post-check> \\
        --plan-commit 1833f34 --out <evidence file>
"""

from __future__ import annotations

import sys
from typing import Sequence

from src.copyability.execution import LATENCY_GRID_MS  # noqa: F401 - re-exported for tests

from .l2_arm_runner import (  # noqa: F401 - re-exported for callers and tests
    CANDLE_INTERVAL_MS,
    EXIT_BROKE,
    EXIT_REFUSED,
    MAX_PRICE_AGE_MS,
    MILLISECONDS_PER_DAY,
    ArmRunnerError,
    ArmSpec,
    characterisation_window,
    load_cohort,
    pool_wallets,
    seed_from,
)
from .l2_arm_runner import main as _main

#: ``APPROVE_HL_LIVE_DATA_L2_ARM_A_WINDOW_001``: ``arm_a_evaluation_window=T0-52..T0-7``,
#: 15-minute candles, 15-minute freshness, no mixed resolution.
ARM_A = ArmSpec(
    arm="A",
    run_id="L2-ARM-A-001",
    variant="A-45",
    approvals=("APPROVE_HL_LIVE_DATA_L2_TWO_ARM_STUDY_001", "APPROVE_HL_LIVE_DATA_L2_ARM_A_WINDOW_001"),
    window_start_days=-52,
    window_end_days=-7,
    price_source="candles",
    # The freeze's post-check admits a first open up to one interval after the
    # window start; closes are stamped one interval later, so the same rule on
    # closes is two intervals. Stricter here would evict coins the freeze passed.
    span_tolerance_ms=2 * CANDLE_INTERVAL_MS,
    decides=False,
)


def evaluation_window(t0_ms: int) -> tuple[int, int]:
    return ARM_A.window(t0_ms)


def main(argv: Sequence[str] | None = None, *, log=print) -> int:
    return _main(ARM_A, argv, log=log)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
