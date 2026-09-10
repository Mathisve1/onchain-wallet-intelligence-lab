"""Arm B: the forward, decisive arm, ``T0`` to ``T0+56d`` on the polled mids.

The arm's specification lives here; the run itself is :mod:`.l2_arm_runner`,
shared with arm A so both arms are computed the same way. Arm B refuses to
compute anything until every cohort wallet carries a completed closing sweep
row and the coverage ledger certifies its whole window for at least one of
them - the approval forbids interim result inspection - and it applies
the decision rule the plan fixed before T0: B decides, A measures. Given arm
A's evidence file it also reports ``mean d_A - mean d_B``, the measured
survivorship inflation, as a number and never as a gate.

Run from the repository root, after day 56::

    python -m research.wallet_copyability.live_data_collector.arm_b_runner \\
        --db <DB> --cohort <freeze record> --candles-json <post-check> \\
        --plan-commit 1833f34 --arm-a-json <arm A evidence> --out <evidence file>
"""

from __future__ import annotations

import sys
from typing import Sequence

from .l2_arm_runner import MAX_PRICE_AGE_MS, ArmSpec
from .l2_arm_runner import main as _main

#: ``APPROVE_HL_LIVE_DATA_L2_TWO_ARM_STUDY_001``: ``forward_evaluation_window_days=56``;
#: prices from ``allMids`` polled by the operator, 15-minute freshness as in arm A.
ARM_B = ArmSpec(
    arm="B",
    run_id="L2-ARM-B-001",
    variant="B-56",
    approvals=("APPROVE_HL_LIVE_DATA_L2_TWO_ARM_STUDY_001",),
    window_start_days=0,
    window_end_days=56,
    price_source="mids",
    # Both edges at the freshness bound: the first mid within 15 minutes of
    # T0, the last within 15 minutes of the end (the exit mark takes the last
    # quote whatever its age and counts it stale beyond the bound).
    span_tolerance_ms=MAX_PRICE_AGE_MS,
    end_tolerance_ms=MAX_PRICE_AGE_MS,
    decides=True,
    price_note="priced on the polled allMids alone; the public tape while a session is connected "
               "is not used, so the series has one resolution and does not depend on the sample",
)


def evaluation_window(t0_ms: int) -> tuple[int, int]:
    return ARM_B.window(t0_ms)


def main(argv: Sequence[str] | None = None, *, log=print) -> int:
    return _main(ARM_B, argv, log=log)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
