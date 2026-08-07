from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Fill:
    wallet_address: str
    instrument: str
    side: str
    price: Decimal
    size: Decimal
    fee: Decimal
    event_time_ms: int
    first_seen_at_ms: int

    def validate(self) -> None:
        if not self.wallet_address.startswith("0x") or len(self.wallet_address) != 42:
            raise ValueError("invalid wallet address")
        if self.side not in {"BUY", "SELL"}:
            raise ValueError("invalid side")
        if self.price <= 0 or self.size <= 0 or self.fee < 0:
            raise ValueError("invalid fill economics")
        if self.first_seen_at_ms < self.event_time_ms:
            raise ValueError("first_seen_at cannot precede event time")
