"""Source-wallet P&L and follower P&L as two types that cannot be mixed.

The founding requirement of this study is that a wallet's own results and a
follower's results after all follower costs are reported separately. Making
that a convention would mean every reader has to remember it. Making it a
type means the interpreter refuses: :class:`SourcePnl` and :class:`FollowerPnl`
do not add, compare or convert to one another, and there is no function in
this package that takes one and returns the other. The only thing that holds
both is :class:`PnlComparison`, and it holds them under their own names.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .costs import CostBreakdown
from .inputs import _decimal


class PnlMixingError(TypeError):
    """Raised when source and follower economics are combined."""


@dataclass(frozen=True, slots=True)
class SourcePnl:
    """What the copied wallet itself made, as the venue reported it.

    Built only from the wallet's own fills: their ``closed_pnl`` and ``fee``.
    It carries no follower cost because no follower cost applies to it.
    """

    wallet: str
    closed_pnl: Decimal
    fees_paid: Decimal
    fill_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "closed_pnl", _decimal(self.closed_pnl, "closed_pnl"))
        object.__setattr__(self, "fees_paid", _decimal(self.fees_paid, "fees_paid"))
        if self.fill_count < 0:
            raise ValueError("fill_count cannot be negative")

    @property
    def net(self) -> Decimal:
        return self.closed_pnl - self.fees_paid

    def __add__(self, other: object) -> SourcePnl:
        if isinstance(other, FollowerPnl):
            raise PnlMixingError("source and follower P&L cannot be added")
        if not isinstance(other, SourcePnl) or other.wallet != self.wallet:
            return NotImplemented
        return SourcePnl(
            self.wallet,
            self.closed_pnl + other.closed_pnl,
            self.fees_paid + other.fees_paid,
            self.fill_count + other.fill_count,
        )

    def __lt__(self, other: object) -> bool:
        if isinstance(other, FollowerPnl):
            raise PnlMixingError("source and follower P&L are not comparable")
        return NotImplemented


@dataclass(frozen=True, slots=True)
class FollowerPnl:
    """What a follower would have made copying the wallet, after every cost.

    ``gross`` is mark-to-market trading result before costs; ``costs`` is the
    full breakdown; ``net`` is the only number that may be called a result.
    """

    wallet: str
    latency_ms: int
    gross: Decimal
    costs: CostBreakdown
    trade_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "gross", _decimal(self.gross, "gross"))
        if not isinstance(self.costs, CostBreakdown):
            raise TypeError("follower costs must be a CostBreakdown")
        self.costs.assert_complete()
        if self.latency_ms < 0 or self.trade_count < 0:
            raise ValueError("latency and trade_count cannot be negative")

    @property
    def net(self) -> Decimal:
        return self.gross - self.costs.total

    def __add__(self, other: object) -> FollowerPnl:
        if isinstance(other, SourcePnl):
            raise PnlMixingError("follower and source P&L cannot be added")
        if (
            not isinstance(other, FollowerPnl)
            or other.wallet != self.wallet
            or other.latency_ms != self.latency_ms
        ):
            return NotImplemented
        return FollowerPnl(
            self.wallet,
            self.latency_ms,
            self.gross + other.gross,
            self.costs + other.costs,
            self.trade_count + other.trade_count,
        )

    def __lt__(self, other: object) -> bool:
        if isinstance(other, SourcePnl):
            raise PnlMixingError("follower and source P&L are not comparable")
        return NotImplemented


@dataclass(frozen=True, slots=True)
class PnlComparison:
    """Both economics side by side, each under its own name. Never summed."""

    source: SourcePnl
    follower: FollowerPnl

    def __post_init__(self) -> None:
        if not isinstance(self.source, SourcePnl) or not isinstance(self.follower, FollowerPnl):
            raise PnlMixingError("comparison needs one SourcePnl and one FollowerPnl")
        if self.source.wallet != self.follower.wallet:
            raise ValueError("comparison must be about the same wallet")

    @property
    def follower_captures(self) -> Decimal | None:
        """Follower net as a share of source net; None when source net is zero."""
        if self.source.net == 0:
            return None
        return self.follower.net / self.source.net
