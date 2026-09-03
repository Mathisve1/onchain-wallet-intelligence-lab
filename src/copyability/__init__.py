"""Deterministic, network-free copyability simulator.

Answers one question per wallet per copy latency: what would a follower have
made, after every cost, over a period we fully observed, and how does that
compare with doing nothing, holding, chasing momentum or copying a random
wallet of similar activity.

Layering matches ``src.live_data``: standard library only, no transport, no
entry point. The only sibling dependency is ``src.live_data.storage`` inside
:mod:`.loader`, which reads a local SQLite file.
"""

from .baselines import BASELINE_NAMES, buy_and_hold, matched_random, momentum, no_trade
from .costs import COST_COMPONENTS, CostBreakdown, CostError, CostModel, FeeSchedule
from .coverage import CoverageLedger, KnownInterval, ObservedInterval, UnknownIntervalError
from .execution import (
    LATENCY_GRID_MS,
    EquityPoint,
    FollowerConfig,
    FollowerRun,
    simulate_follower,
    source_pnl,
)
from .inputs import (
    SIDE_BUY,
    SIDE_SELL,
    FundingEvent,
    FundingSchedule,
    InputError,
    LiquidityProfile,
    MarketData,
    PricePoint,
    PriceSeries,
    SourceFill,
)
from .metrics import Drawdown, Outcome, as_row, max_drawdown, outcome_for
from .pit import LookAheadError, PointInTimeView, assert_point_in_time
from .pnl import FollowerPnl, PnlComparison, PnlMixingError, SourcePnl
from .simulate import StudyConfig, WalletStudy, run_study

__all__ = [
    "BASELINE_NAMES", "COST_COMPONENTS", "LATENCY_GRID_MS", "SIDE_BUY", "SIDE_SELL",
    "CostBreakdown", "CostError", "CostModel", "CoverageLedger", "Drawdown", "EquityPoint",
    "FeeSchedule", "FollowerConfig", "FollowerPnl", "FollowerRun", "FundingEvent",
    "FundingSchedule", "InputError", "KnownInterval", "LiquidityProfile", "LookAheadError",
    "MarketData", "ObservedInterval", "Outcome", "PnlComparison", "PnlMixingError",
    "PointInTimeView", "PricePoint", "PriceSeries", "SourceFill", "SourcePnl", "StudyConfig",
    "UnknownIntervalError", "WalletStudy", "as_row", "assert_point_in_time", "buy_and_hold",
    "matched_random", "max_drawdown", "momentum", "no_trade", "outcome_for", "run_study",
    "simulate_follower", "source_pnl",
]
