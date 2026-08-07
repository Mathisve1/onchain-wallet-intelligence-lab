from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from durable_store import DurableStore, StoreError, canonical_json, sha256_hex_bytes


class SignerError(ValueError):
    pass


@dataclass(frozen=True)
class SimulatedSignature:
    permit_id: str
    signer_id: str
    signer_address: str
    nonce: int
    action_sha256: str
    marker: str
    digest: str


class RestrictedSignerSimulator:
    """Deliberately non-cryptographic. Cannot create a venue-valid signature."""

    MARKER = "SIMULATED_NON_SIGNATURE_V1"

    def __init__(self, store: DurableStore, signer_id: str, signer_address: str):
        self.store = store
        self.signer_id = signer_id
        self.signer_address = signer_address

    def sign_permitted_action(
        self,
        *,
        permit_id: str,
        compiled_action: dict[str, Any],
        now_ms: int,
        current_policy_hash: str,
    ) -> SimulatedSignature:
        signer = self.store.signer(self.signer_id)
        if signer["public_address"] != self.signer_address or signer["enabled"] != 1:
            raise SignerError("signer:identity_or_status")
        action_json = canonical_json(compiled_action)
        action_hash = sha256_hex_bytes(action_json.encode("utf-8"))
        try:
            permit = self.store.consume_permit(
                permit_id=permit_id,
                signer_id=self.signer_id,
                action_sha256=action_hash,
                current_policy_hash=current_policy_hash,
                now_ms=now_ms,
                audit_event_id=f"permit-consume:{permit_id}:{now_ms}",
            )
        except StoreError as exc:
            raise SignerError(str(exc)) from exc

        material = canonical_json({
            "marker": self.MARKER,
            "permit_id": permit_id,
            "signer_id": self.signer_id,
            "signer_address": self.signer_address,
            "nonce": permit["nonce"],
            "action_sha256": action_hash,
        })
        digest = sha256_hex_bytes(material.encode("utf-8"))
        action_id = self.store.permit(permit_id)["action_id"]
        self.store.transition_action(
            action_id,
            "PERMIT_CONSUMED",
            "SIGNED",
            now_ms,
            f"sim-sign:{action_id}:{now_ms}",
            {"marker": self.MARKER, "simulated_signature_digest": digest},
        )
        return SimulatedSignature(
            permit_id=permit_id,
            signer_id=self.signer_id,
            signer_address=self.signer_address,
            nonce=int(permit["nonce"]),
            action_sha256=action_hash,
            marker=self.MARKER,
            digest=digest,
        )
