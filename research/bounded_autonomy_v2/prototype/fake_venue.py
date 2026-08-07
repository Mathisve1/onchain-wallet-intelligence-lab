from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


class FakeVenueError(ValueError):
    pass


class FakeVenueTimeout(TimeoutError):
    pass


@dataclass(frozen=True)
class VenueEvent:
    kind: str
    payload: dict[str, Any]


class FakeHyperliquidVenue:
    """Offline deterministic venue model. No sockets, HTTP, SDK, or signatures."""

    def __init__(self):
        self.orders: dict[str, dict[str, Any]] = {}

    def submit(self, action: dict[str, Any], behavior: str = "FILL") -> list[VenueEvent]:
        kind = action.get("action_type")
        if kind == "order":
            cloid = action["cloid"]
            if cloid in self.orders:
                raise FakeVenueError("duplicate_cloid")
            order = {
                "cloid": cloid,
                "coin": action["coin"],
                "size": Decimal(str(action["size"])),
                "filled": Decimal("0"),
                "status": "OPEN",
                "action": dict(action),
            }
            self.orders[cloid] = order
            if behavior == "TIMEOUT_AFTER_ACCEPT":
                raise FakeVenueTimeout("accepted_but_ack_lost")
            if behavior == "REJECT":
                order["status"] = "REJECTED"
                return [VenueEvent("REJECTED", {"cloid": cloid})]
            events = [VenueEvent("ACKNOWLEDGED", {"cloid": cloid})]
            if behavior == "ACK_ONLY":
                return events
            if behavior == "DUPLICATE_ACK":
                return events + [VenueEvent("ACKNOWLEDGED", {"cloid": cloid, "duplicate": True})]
            if behavior == "PARTIAL_THEN_FILL":
                first = order["size"] / 2
                second = order["size"] - first
                order["filled"] = order["size"]
                order["status"] = "FILLED"
                return events + [
                    VenueEvent("FILL", {"quantity": format(first, "f")}),
                    VenueEvent("FILL", {"quantity": format(second, "f")}),
                ]
            if behavior == "PARTIAL_ONLY":
                first = order["size"] / 2
                order["filled"] = first
                order["status"] = "PARTIALLY_FILLED"
                return events + [VenueEvent("FILL", {"quantity": format(first, "f")})]
            if behavior == "FILL":
                order["filled"] = order["size"]
                order["status"] = "FILLED"
                return events + [VenueEvent("FILL", {"quantity": format(order["size"], "f")})]
            raise FakeVenueError("unknown_behavior")

        if kind == "cancelByCloid":
            cloid = action["target_cloid"]
            order = self.orders.get(cloid)
            if order is None:
                return [VenueEvent("REJECTED", {"reason": "unknown_target", "cloid": cloid})]
            if order["status"] in {"FILLED", "CANCELED", "REJECTED"}:
                return [VenueEvent("REJECTED", {"reason": "already_terminal", "cloid": cloid})]
            order["status"] = "CANCELED"
            return [
                VenueEvent("ACKNOWLEDGED", {"cloid": cloid}),
                VenueEvent("CANCELED", {"cloid": cloid}),
            ]
        raise FakeVenueError("unsupported_action")

    def query_by_cloid(self, cloid: str) -> dict[str, Any] | None:
        order = self.orders.get(cloid)
        if order is None:
            return None
        return {
            "cloid": cloid,
            "coin": order["coin"],
            "size": format(order["size"], "f"),
            "filled": format(order["filled"], "f"),
            "status": order["status"],
        }
