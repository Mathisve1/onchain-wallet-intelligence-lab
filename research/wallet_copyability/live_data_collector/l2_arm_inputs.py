"""What both arm runners take as given: the study's constants, the freeze
record's checks, and the pieces of the study configuration the plan or L1
fixed. Nothing here reads a database beyond the freeze record itself.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from src.copyability.classify import ClassifierThresholds
from src.copyability.cohort import cohort_hash
from src.copyability.costs import CostModel, FeeSchedule
from src.copyability.coverage import CoverageLedger
from src.copyability.execution import LATENCY_GRID_MS, FollowerConfig
from src.copyability.inputs import LiquidityProfile
from src.copyability.simulate import StudyConfig

from .l2_arm_statistics import MINIMUM_EVALUATED

MILLISECONDS_PER_DAY = 86_400_000
#: Both arms: 15-minute freshness, no mixed-resolution series.
MAX_PRICE_AGE_MS = 900_000
CANDLE_INTERVAL = "15m"
CANDLE_INTERVAL_MS = 900_000
#: The characterisation window the freeze used; the record must agree.
CHARACTERISATION_START_DAYS_BEFORE_T0 = 90
CHARACTERISATION_END_DAYS_BEFORE_T0 = 60

#: Study parameters carried over from ``L1_INSTRUMENT_VALIDATION_001`` so the
#: instruments agree on every cost, plus the ones this runner fixes and
#: discloses because neither the plan nor L1 did.
NOMINAL_CAPITAL = Decimal("10000")
SIZE_SCALE = Decimal(1)
FEES = FeeSchedule(taker_bps=Decimal("4.5"), maker_bps=Decimal("1.5"))
IMPACT_BPS_PER_FULL_DEPTH = Decimal("10")
BENCHMARK_COIN = "BTC"
MOMENTUM_LOOKBACK_MS = 3_600_000
MOMENTUM_STEP_MS = 600_000
MATCHED_RANDOM_SAMPLE_SIZE = 20
MATCHED_RANDOM_TOLERANCE = Decimal("0.5")
TIER1_COINS = frozenset({"BTC", "ETH"})
TIER2_COINS = frozenset({
    "AAVE", "ADA", "APT", "ARB", "ATOM", "AVAX", "BNB", "DOGE", "ENA", "HYPE", "LINK",
    "LTC", "NEAR", "PAXG", "SOL", "SUI", "TAO", "TRX", "UNI", "WLD", "XLM", "XRP", "kPEPE",
})
LIQUIDITY_TIERS = {
    "tier1": (Decimal("0.5"), Decimal("2000000")),
    "tier2": (Decimal("1.5"), Decimal("300000")),
    "tier3": (Decimal("5"), Decimal("50000")),
}

STATUS_EARLY_READ = "ARM_A_EARLY_READ_ONLY"
STATUS_DECIDED = "ARM_B_DECIDED"
STATUS_CASE_STUDY = "CASE_STUDY_UNDER_MINIMUM"
STATUS_NOT_MEASURABLE = "NOT_MEASURABLE"
STATUS_DRY_RUN = "DRY_RUN_UNDERPOWERED"
#: Something broke (rule 5 of the reading): the file says what, and decides nothing.
STATUS_BROKE = "BROKE_SEE_WHAT_BROKE"
#: What may certify an L2 window: the REST walks whose coverage names the
#: window they observed. A websocket session is not part of this study's
#: collection and claims its interval from the run's start rather than from
#: the subscription it was given, so it certifies nothing here.
L2_LEDGER_MODES = ("backfill_wallet", "sweep_wallet")
#: Arm A reads the rows that had finished by T0, the freeze instant, and
#: refuses unless they are the rows the freeze recorded. Arm B reads the rows
#: finishing within this grace after its window end, so a rerun months later
#: consults the same rows.
ARM_B_CLOSE_GRACE_MS = 3 * MILLISECONDS_PER_DAY
EXIT_REFUSED = 2
EXIT_BROKE = 3


class ArmRunnerError(ValueError):
    """An input the runner refuses to evaluate on."""


@dataclass(frozen=True, slots=True)
class ArmSpec:
    """What distinguishes one arm from the other; everything else is shared."""

    arm: str
    run_id: str
    variant: str
    approvals: tuple[str, ...]
    #: Window edges in days relative to T0: arm A is (-52, -7), arm B (0, +56).
    window_start_days: int
    window_end_days: int
    price_source: str
    #: How far after the window start the first usable quote may sit, and how
    #: far before the window end the last may sit: zero for candles fetched
    #: after the window closed, the freshness bound for polled mids.
    span_tolerance_ms: int
    end_tolerance_ms: int
    decides: bool
    #: What the file says when the series is not the plan's wording.
    price_note: str | None = None

    def window(self, t0_ms: int) -> tuple[int, int]:
        return (t0_ms + self.window_start_days * MILLISECONDS_PER_DAY,
                t0_ms + self.window_end_days * MILLISECONDS_PER_DAY)

    @property
    def price_kind(self) -> dict:
        kind = {"kind": self.price_source, "interval": CANDLE_INTERVAL if self.price_source == "candles" else None,
                "max_age_ms": MAX_PRICE_AGE_MS}
        if self.price_note is not None:
            kind["deviation_from_plan_wording"] = self.price_note
        return kind


# -- inputs ------------------------------------------------------------------------


def characterisation_window(t0_ms: int) -> tuple[int, int]:
    return (t0_ms - CHARACTERISATION_START_DAYS_BEFORE_T0 * MILLISECONDS_PER_DAY,
            t0_ms - CHARACTERISATION_END_DAYS_BEFORE_T0 * MILLISECONDS_PER_DAY)


def load_cohort(path: Path, *, plan_commit: str, allow_underpowered: bool = False) -> dict:
    """The freeze record, trusted only after every check a reader would make."""
    record = json.loads(path.read_text(encoding="utf-8"))
    for key in ("t0_ms", "cohort", "cohort_sha256", "plan_commit", "hard_stop", "ledger_snapshot"):
        if key not in record:
            raise ArmRunnerError(f"freeze record lacks {key!r}: {path} (a record without the ledger snapshot "
                                 "predates the runner; re-freeze)")
    if record["plan_commit"] != plan_commit:
        raise ArmRunnerError(
            f"freeze record was made under plan commit {record['plan_commit']!r}, this run names {plan_commit!r}"
        )
    if cohort_hash(record["cohort"]) != record["cohort_sha256"]:
        raise ArmRunnerError("the cohort list does not hash to the recorded cohort_sha256; the record was altered")
    recorded_minimum = int(record.get("minimum_evaluable", MINIMUM_EVALUATED))
    if recorded_minimum < MINIMUM_EVALUATED and not allow_underpowered:
        # The plan's minimum is not the record's to lower: a freeze made with
        # --minimum N below it is refused, not evaluated at N.
        raise ArmRunnerError(
            f"the freeze was made with minimum_evaluable={recorded_minimum}, under the plan's {MINIMUM_EVALUATED} "
            "(pass --allow-underpowered-dry-run for a synthetic dry run)"
        )
    minimum = max(recorded_minimum, MINIMUM_EVALUATED)
    if not record["hard_stop"] and len(record["cohort"]) < minimum and not allow_underpowered:
        raise ArmRunnerError(
            f"{len(record['cohort'])} wallets is under the minimum of {minimum}; an underpowered study "
            "is not run to have something (pass --allow-underpowered-dry-run for a synthetic dry run)"
        )
    recorded = record.get("characterisation_window")
    if recorded is not None:
        if (int(recorded["start_ms"]), int(recorded["end_ms"])) != characterisation_window(int(record["t0_ms"])):
            raise ArmRunnerError("the freeze's characterisation window is not [T0-90d, T0-60d]")
    return record


def liquidity_for(coin: str) -> LiquidityProfile:
    """The L1 tiered assumption, labelled ASSUMED: no order book is read."""
    tier = "tier1" if coin in TIER1_COINS else "tier2" if coin in TIER2_COINS else "tier3"
    half_spread_bps, depth = LIQUIDITY_TIERS[tier]
    return LiquidityProfile(coin, half_spread_bps, depth, IMPACT_BPS_PER_FULL_DEPTH)


def study_config(seed: int) -> StudyConfig:
    return StudyConfig(
        follower=FollowerConfig(capital=NOMINAL_CAPITAL, size_scale=SIZE_SCALE),
        cost_model=CostModel(FEES), benchmark_coin=BENCHMARK_COIN,
        momentum_lookback_ms=MOMENTUM_LOOKBACK_MS, momentum_step_ms=MOMENTUM_STEP_MS,
        random_seed=seed, random_sample_size=MATCHED_RANDOM_SAMPLE_SIZE, latencies_ms=LATENCY_GRID_MS,
        thresholds=ClassifierThresholds(), max_price_age_ms=MAX_PRICE_AGE_MS,
        random_tolerance=MATCHED_RANDOM_TOLERANCE,
    )


def seed_from(cohort_sha256: str) -> int:
    """A seed the cohort itself fixes, so a rerun on the same freeze repeats."""
    return int(cohort_sha256[:8], 16)


def pool_wallets(ledger: CoverageLedger, window: tuple[int, int]) -> list[str]:
    """Every wallet the ledger certifies over the whole window: the peer pool."""
    start_ms, end_ms = window
    return sorted(w for w in ledger.wallets() if ledger.is_fully_known(w, start_ms, end_ms))


def assumptions(seed: int) -> dict:
    return {
        "fees_bps": {"taker": str(FEES.taker_bps), "maker": str(FEES.maker_bps)},
        "liquidity_tiers": {k: {"half_spread_bps": str(v[0]), "depth_notional_usd": str(v[1])} for k, v in LIQUIDITY_TIERS.items()},
        "impact_bps_per_full_depth": str(IMPACT_BPS_PER_FULL_DEPTH),
        "liquidity_source": "ASSUMED",
        "benchmark_coin": BENCHMARK_COIN,
        "momentum": {"lookback_ms": MOMENTUM_LOOKBACK_MS, "step_ms": MOMENTUM_STEP_MS},
        "size_scale": str(SIZE_SCALE),
        "nominal_capital": str(NOMINAL_CAPITAL),
        "matched_random_sample_size": MATCHED_RANDOM_SAMPLE_SIZE,
        "matched_random_peer_tolerance": str(MATCHED_RANDOM_TOLERANCE),
        "matched_random_eligibility": "another pool wallet whose in-window fill count is within the tolerance "
                                      "of the target's and whose coverage certifies the same window",
        "seed": seed,
        "seed_derivation": "int(cohort_sha256[:8], 16)",
        "latencies_ms": list(LATENCY_GRID_MS),
        "max_price_age_ms": MAX_PRICE_AGE_MS,
    }
