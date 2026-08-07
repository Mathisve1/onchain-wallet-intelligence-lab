from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

TERMINAL_STATES = {"FILLED", "CANCELED", "REJECTED", "EXPIRED", "RECONCILED_NO_ACTION"}
UNCERTAIN_STATES = {"POSSIBLY_SUBMITTED", "RECONCILING"}
ALLOWED_TRANSITIONS = {
    "INTENT_CREATED": {"POLICY_ALLOWED", "BLOCKED"},
    "POLICY_ALLOWED": {"PERMIT_ISSUED", "BLOCKED"},
    "PERMIT_ISSUED": {"PERMIT_CONSUMED", "EXPIRED", "BLOCKED"},
    "PERMIT_CONSUMED": {"SIGNED", "BLOCKED"},
    "SIGNED": {"SUBMITTED", "POSSIBLY_SUBMITTED"},
    "SUBMITTED": {"ACKNOWLEDGED", "POSSIBLY_SUBMITTED", "REJECTED", "EXPIRED"},
    "ACKNOWLEDGED": {"PARTIALLY_FILLED", "FILLED", "CANCELED", "REJECTED", "EXPIRED", "RECONCILING"},
    "PARTIALLY_FILLED": {"PARTIALLY_FILLED", "FILLED", "CANCELED", "RECONCILING"},
    "POSSIBLY_SUBMITTED": {"RECONCILING"},
    "RECONCILING": {"ACKNOWLEDGED", "PARTIALLY_FILLED", "FILLED", "CANCELED", "REJECTED", "EXPIRED", "RECONCILED_NO_ACTION"},
    "BLOCKED": set(),
    "FILLED": set(),
    "CANCELED": set(),
    "REJECTED": set(),
    "EXPIRED": set(),
    "RECONCILED_NO_ACTION": set(),
}


class ReconciliationError(ValueError):
    pass


def _decimal(value: Any, label: str, *, nonnegative: bool = True) -> Decimal:
    try:
        out = Decimal(str(value))
    except InvalidOperation as exc:
        raise ReconciliationError(f"{label}:invalid") from exc
    if not out.is_finite():
        raise ReconciliationError(f"{label}:nonfinite")
    if nonnegative and out < 0:
        raise ReconciliationError(f"{label}:negative")
    return out


@dataclass
class ActionRecord:
    action_id: str
    permit_id: str
    action: str
    instrument: str
    risk_increasing: bool
    expected_quantity: Decimal
    state: str = "INTENT_CREATED"
    filled_quantity: Decimal = Decimal("0")

    def transition(self, target: str) -> None:
        if target not in ALLOWED_TRANSITIONS:
            raise ReconciliationError("state:unknown")
        if target not in ALLOWED_TRANSITIONS.get(self.state, set()):
            raise ReconciliationError(f"state:invalid_transition:{self.state}->{target}")
        self.state = target

    def record_fill(self, quantity: Any) -> None:
        if self.state not in {"ACKNOWLEDGED", "PARTIALLY_FILLED", "RECONCILING"}:
            raise ReconciliationError(f"fill:invalid_state:{self.state}")
        quantity_d = _decimal(quantity, "fill:quantity")
        if quantity_d <= 0:
            raise ReconciliationError("fill:nonpositive")
        new_total = self.filled_quantity + quantity_d
        if new_total > self.expected_quantity:
            raise ReconciliationError("fill:exceeds_expected_quantity")
        self.filled_quantity = new_total
        self.state = "FILLED" if new_total == self.expected_quantity else "PARTIALLY_FILLED"

    @property
    def terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    @property
    def uncertain(self) -> bool:
        return self.state in UNCERTAIN_STATES


class ActionJournal:
    def __init__(self) -> None:
        self.records: dict[str, ActionRecord] = {}
        self.permit_to_action: dict[str, str] = {}

    def create(
        self,
        *,
        action_id: str,
        permit_id: str,
        action: str,
        instrument: str,
        risk_increasing: bool,
        expected_quantity: Any,
    ) -> ActionRecord:
        if not action_id or action_id in self.records:
            raise ReconciliationError("journal:duplicate_action_id")
        if not permit_id or permit_id in self.permit_to_action:
            raise ReconciliationError("journal:duplicate_permit_id")
        quantity = _decimal(expected_quantity, "journal:expected_quantity")
        if action == "CANCEL_BY_CLOID":
            if quantity != 0:
                raise ReconciliationError("journal:cancel_quantity_must_be_zero")
            if risk_increasing:
                raise ReconciliationError("journal:cancel_cannot_increase_risk")
        elif quantity <= 0:
            raise ReconciliationError("journal:order_quantity_nonpositive")
        record = ActionRecord(
            action_id=action_id,
            permit_id=permit_id,
            action=action,
            instrument=instrument,
            risk_increasing=risk_increasing,
            expected_quantity=quantity,
        )
        self.records[action_id] = record
        self.permit_to_action[permit_id] = action_id
        return record

    def get(self, action_id: str) -> ActionRecord:
        try:
            return self.records[action_id]
        except KeyError as exc:
            raise ReconciliationError("journal:unknown_action") from exc

    def unresolved_risk_increasing(self) -> list[ActionRecord]:
        return [r for r in self.records.values() if r.risk_increasing and not r.terminal]

    def can_issue_new_risk(self) -> bool:
        return not self.unresolved_risk_increasing()

    def mark_crash_after_sign_before_ack(self, action_id: str) -> None:
        record = self.get(action_id)
        if record.state not in {"SIGNED", "SUBMITTED"}:
            raise ReconciliationError("journal:crash_marker_wrong_state")
        record.state = "POSSIBLY_SUBMITTED"

    def begin_reconciliation(self, action_id: str) -> None:
        record = self.get(action_id)
        if record.state not in {"POSSIBLY_SUBMITTED", "ACKNOWLEDGED", "PARTIALLY_FILLED"}:
            raise ReconciliationError("journal:reconcile_wrong_state")
        record.state = "RECONCILING"
