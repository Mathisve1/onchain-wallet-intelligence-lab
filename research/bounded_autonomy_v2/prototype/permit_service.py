from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from durable_store import DurableStore, StoreError, canonical_json, sha256_hex_bytes


class PermitServiceError(ValueError):
    pass


@dataclass(frozen=True)
class PermitOutcome:
    issued: bool
    code: str
    permit: dict[str, Any] | None = None


class PermitService:
    def __init__(
        self,
        store: DurableStore,
        *,
        evaluator: Callable[..., Any],
        action_compiler: Callable[..., dict[str, Any]],
        cloid_deriver: Callable[[str, str, int, str], str],
    ):
        self.store = store
        self.evaluator = evaluator
        self.action_compiler = action_compiler
        self.cloid_deriver = cloid_deriver

    def issue(
        self,
        *,
        intent: dict[str, Any],
        envelope: dict[str, Any],
        risk_state: dict[str, Any],
        now_ms: int,
        quote_timestamp_ms: int,
        current_policy_hash: str,
        permit_id: str,
        action_id: str,
        action_sequence: int,
        signer_id: str,
        signer_address: str,
        account_address: str,
    ) -> PermitOutcome:
        decision = self.evaluator(
            intent,
            envelope,
            risk_state,
            now_ms=now_ms,
            quote_timestamp_ms=quote_timestamp_ms,
            current_policy_hash=current_policy_hash,
        )
        if not getattr(decision, "allowed", False):
            code = getattr(decision, "code", "BLOCK_UNKNOWN")
            self.store.append_audit(
                event_id=f"permit-block:{action_id}:{now_ms}",
                timestamp_ms=now_ms,
                event_type="PERMIT_BLOCKED",
                action_id=action_id,
                permit_id=None,
                payload={"decision_code": code},
            )
            return PermitOutcome(False, code)

        if envelope.get("account_address") != account_address:
            return self._block(action_id, now_ms, "BLOCK_ACCOUNT_MISMATCH")
        signer = self.store.signer(signer_id)
        if signer["public_address"] != signer_address or signer["enabled"] != 1:
            return self._block(action_id, now_ms, "BLOCK_SIGNER_IDENTITY")
        environment = envelope.get("environment")
        if signer["environment"] != environment:
            return self._block(action_id, now_ms, "BLOCK_SIGNER_ENVIRONMENT")

        action_type = intent.get("action")
        risk_increasing = action_type == "PLACE_IOC_LIMIT"
        if risk_increasing and self.store.unresolved_risk_increasing_count() != 0:
            return self._block(action_id, now_ms, "BLOCK_DURABLE_UNRECONCILED")

        if action_type == "CANCEL_BY_CLOID":
            action = self.action_compiler(intent, owned_orders=self.store.owned_orders())
            cloid = None
            target_cloid = action["target_cloid"]
            expected_quantity = "0"
        elif action_type in {"PLACE_IOC_LIMIT", "REDUCE_ONLY_IOC"}:
            cloid = self.cloid_deriver(intent["strategy_id"], permit_id, action_sequence, environment)
            action = self.action_compiler(intent, new_order_cloid=cloid)
            target_cloid = None
            expected_quantity = intent["requested_quantity"]
        else:
            return self._block(action_id, now_ms, "BLOCK_ACTION")

        action_hash = sha256_hex_bytes(canonical_json(action).encode("utf-8"))
        intent_hash = sha256_hex_bytes(canonical_json(intent).encode("utf-8"))
        network = "TESTNET" if environment == "TESTNET" else "MAINNET"
        permit_base: dict[str, Any] = {
            "schema_version": "0.3-design",
            "permit_id": permit_id,
            "intent_sha256": intent_hash,
            "compiled_action_sha256": action_hash,
            "strategy_id": intent["strategy_id"],
            "strategy_version_hash": intent["strategy_version_hash"],
            "policy_version_hash": intent["policy_version_hash"],
            "data_snapshot_hash": intent["data_snapshot_hash"],
            "risk_snapshot_hash": intent["risk_snapshot_hash"],
            "venue": "HYPERLIQUID",
            "network": network,
            "account_address": account_address,
            "signer_id": signer_id,
            "signer_address": signer_address,
            "action": action_type,
            "instrument": intent["instrument"],
            "decision_mode": intent["decision_mode"],
            "issued_at_ms": now_ms,
            "expires_at_ms": intent["expires_at_ms"],
            "single_use": True,
            "reconciliation_precondition": "NO_OPEN_UNRECONCILED_RISK_INCREASING_ACTION",
        }
        if intent.get("model_version_hash") is not None:
            permit_base["model_version_hash"] = intent["model_version_hash"]
        if intent.get("reason_code") is not None:
            permit_base["reason_code"] = intent["reason_code"]
        if action_type == "CANCEL_BY_CLOID":
            permit_base["target_cloid"] = target_cloid
        else:
            permit_base.update(
                side=intent["side"],
                reduce_only=bool(intent["reduce_only"]),
                quantity=intent["requested_quantity"],
                limit_price=intent["limit_price"],
                max_slippage_bps=intent["max_slippage_bps"],
                cloid=cloid,
                venue_expires_after_ms=intent["expires_at_ms"],
            )

        try:
            permit = self.store.create_permit_bundle(
                permit_base=permit_base,
                action_id=action_id,
                action=action,
                risk_increasing=risk_increasing,
                expected_quantity=expected_quantity,
                now_ms=now_ms,
                audit_event_id=f"permit-issue:{action_id}:{now_ms}",
            )
        except StoreError as exc:
            raise PermitServiceError(str(exc)) from exc
        return PermitOutcome(True, "PERMIT_ISSUED", permit)

    def _block(self, action_id: str, now_ms: int, code: str) -> PermitOutcome:
        self.store.append_audit(
            event_id=f"permit-block:{action_id}:{now_ms}",
            timestamp_ms=now_ms,
            event_type="PERMIT_BLOCKED",
            action_id=action_id,
            permit_id=None,
            payload={"decision_code": code},
        )
        return PermitOutcome(False, code)
