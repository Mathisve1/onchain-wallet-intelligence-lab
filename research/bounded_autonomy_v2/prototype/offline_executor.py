from __future__ import annotations

from durable_store import DurableStore
from fake_venue import FakeHyperliquidVenue, FakeVenueTimeout, VenueEvent
from restricted_signer import RestrictedSignerSimulator


class OfflineExecutionError(ValueError):
    pass


class OfflineExecutor:
    def __init__(self, store: DurableStore, signer: RestrictedSignerSimulator, venue: FakeHyperliquidVenue):
        self.store = store
        self.signer = signer
        self.venue = venue

    def execute(self, *, permit_id: str, now_ms: int, current_policy_hash: str, behavior: str = "FILL") -> str:
        p = self.store.permit(permit_id)
        action_id = p["action_id"]
        action = self.store.action(action_id)["action"]
        self.signer.sign_permitted_action(
            permit_id=permit_id,
            compiled_action=action,
            now_ms=now_ms,
            current_policy_hash=current_policy_hash,
        )
        self.store.transition_action(
            action_id, "SIGNED", "SUBMITTED", now_ms + 1, f"submit:{action_id}:{now_ms + 1}"
        )
        try:
            events = self.venue.submit(action, behavior)
        except FakeVenueTimeout:
            self.store.transition_action(
                action_id,
                "SUBMITTED",
                "POSSIBLY_SUBMITTED",
                now_ms + 2,
                f"uncertain:{action_id}:{now_ms + 2}",
                {"reason": "FAKE_TIMEOUT_AFTER_ACCEPT"},
            )
            return "POSSIBLY_SUBMITTED"
        for idx, event in enumerate(events, start=1):
            self._apply_event(action_id, event, now_ms + 1 + idx)
        return self.store.action(action_id)["state"]

    def _apply_event(self, action_id: str, event: VenueEvent, ts: int) -> None:
        row = self.store.action(action_id)
        state = row["state"]
        if event.kind == "ACKNOWLEDGED":
            if state == "SUBMITTED":
                self.store.transition_action(
                    action_id, "SUBMITTED", "ACKNOWLEDGED", ts, f"ack:{action_id}:{ts}", event.payload
                )
            elif state in {"ACKNOWLEDGED", "PARTIALLY_FILLED", "FILLED"}:
                self.store.append_audit(
                    event_id=f"duplicate-ack:{action_id}:{ts}",
                    timestamp_ms=ts,
                    event_type="DUPLICATE_ACK_IGNORED",
                    action_id=action_id,
                    permit_id=row["permit_id"],
                    payload=event.payload,
                )
            else:
                raise OfflineExecutionError(f"ack_invalid_state:{state}")
        elif event.kind == "FILL":
            self.store.record_fill(action_id, event.payload["quantity"], ts, f"fill:{action_id}:{ts}")
        elif event.kind in {"REJECTED", "CANCELED", "EXPIRED"}:
            current = self.store.action(action_id)["state"]
            if current in {"SUBMITTED", "ACKNOWLEDGED", "PARTIALLY_FILLED", "RECONCILING"}:
                self.store.transition_action(
                    action_id, current, event.kind, ts, f"{event.kind.lower()}:{action_id}:{ts}", event.payload
                )
            else:
                raise OfflineExecutionError(f"terminal_invalid_state:{current}")
        else:
            raise OfflineExecutionError(f"unknown_event:{event.kind}")

    def reconcile_uncertain(self, *, action_id: str, now_ms: int) -> str:
        row = self.store.action(action_id)
        if row["state"] != "POSSIBLY_SUBMITTED":
            raise OfflineExecutionError("not_uncertain")
        action = row["action"]
        cloid = action.get("cloid")
        self.store.transition_action(
            action_id,
            "POSSIBLY_SUBMITTED",
            "RECONCILING",
            now_ms,
            f"reconcile-start:{action_id}:{now_ms}",
        )
        if not cloid:
            self.store.transition_action(
                action_id,
                "RECONCILING",
                "RECONCILED_NO_ACTION",
                now_ms + 1,
                f"reconcile-none:{action_id}:{now_ms + 1}",
            )
            return "RECONCILED_NO_ACTION"
        remote = self.venue.query_by_cloid(cloid)
        if remote is None:
            self.store.transition_action(
                action_id,
                "RECONCILING",
                "RECONCILED_NO_ACTION",
                now_ms + 1,
                f"reconcile-none:{action_id}:{now_ms + 1}",
            )
            return "RECONCILED_NO_ACTION"
        status = remote["status"]
        if status == "FILLED":
            self.store.record_fill(
                action_id, str(remote["filled"]), now_ms + 1, f"reconcile-fill:{action_id}:{now_ms + 1}"
            )
            return self.store.action(action_id)["state"]
        if status == "PARTIALLY_FILLED":
            filled = str(remote["filled"])
            if filled != "0":
                self.store.record_fill(
                    action_id, filled, now_ms + 1, f"reconcile-partial:{action_id}:{now_ms + 1}"
                )
            return self.store.action(action_id)["state"]
        if status == "OPEN":
            self.store.transition_action(
                action_id,
                "RECONCILING",
                "ACKNOWLEDGED",
                now_ms + 1,
                f"reconcile-open:{action_id}:{now_ms + 1}",
                remote,
            )
            return "ACKNOWLEDGED"
        if status in {"REJECTED", "CANCELED"}:
            self.store.transition_action(
                action_id,
                "RECONCILING",
                status,
                now_ms + 1,
                f"reconcile-terminal:{action_id}:{now_ms + 1}",
                remote,
            )
            return status
        raise OfflineExecutionError("unknown_remote_status")
