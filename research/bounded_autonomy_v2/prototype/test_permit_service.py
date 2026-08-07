import tempfile
from dataclasses import dataclass
import unittest

from durable_store import DurableStore, sha256_hex_bytes
from permit_service import PermitService
from restricted_signer import RestrictedSignerSimulator, SignerError

H = "a" * 64
ADDR = "0x" + "1" * 40


@dataclass(frozen=True)
class D:
    allowed: bool
    code: str


def evaluator(intent, envelope, risk_state, **kwargs):
    if intent.get("force_block"):
        return D(False, "BLOCK_FORCED")
    return D(True, "ALLOW")


def cloid(strategy, permit, seq, env):
    return "0x" + sha256_hex_bytes(f"{strategy}|{permit}|{seq}|{env}".encode())[:32]


def compiler(intent, *, new_order_cloid=None, owned_orders=None):
    if intent["action"] == "CANCEL_BY_CLOID":
        order = owned_orders[intent["target_strategy_order_id"]]
        return {"action_type": "cancelByCloid", "coin": intent["instrument"], "target_cloid": order["cloid"]}
    return {
        "action_type": "order",
        "coin": intent["instrument"],
        "side": intent["side"],
        "size": intent["requested_quantity"],
        "limit": intent["limit_price"],
        "reduce_only": intent["reduce_only"],
        "cloid": new_order_cloid,
    }


def env():
    return {"environment": "TESTNET", "account_address": ADDR}


def intent(action="PLACE_IOC_LIMIT"):
    x = {
        "schema_version": "0.3-design",
        "strategy_id": "COPY-001",
        "strategy_version_hash": H,
        "policy_version_hash": H,
        "data_snapshot_hash": H,
        "risk_snapshot_hash": H,
        "instrument": "BTC",
        "action": action,
        "decision_mode": "DETERMINISTIC_ONLY",
        "expires_at_ms": 10000,
    }
    if action == "PLACE_IOC_LIMIT":
        x.update(side="BUY", reduce_only=False, requested_quantity="0.01", limit_price="50000", max_slippage_bps=25)
    elif action == "REDUCE_ONLY_IOC":
        x.update(reason_code="RISK_REDUCTION", side="SELL", reduce_only=True, requested_quantity="0.01", limit_price="50000", max_slippage_bps=25)
    else:
        x.update(reason_code="RISK_REDUCTION", target_strategy_order_id="order-12345678")
    return x


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = DurableStore(self.tmp.name + "/x.db")
        self.store.register_signer("s1", ADDR, "TESTNET", 1000)
        self.store.set_execution_state("SIGNED_TEST_ONLY", False, 1200, "state:active")
        self.ps = PermitService(self.store, evaluator=evaluator, action_compiler=compiler, cloid_deriver=cloid)

    def tearDown(self):
        self.tmp.cleanup()

    def issue(self, i=None, pid="permit-0000000001", aid="action-0000000001"):
        return self.ps.issue(
            intent=i or intent(), envelope=env(), risk_state={}, now_ms=2000, quote_timestamp_ms=1900,
            current_policy_hash=H, permit_id=pid, action_id=aid, action_sequence=1,
            signer_id="s1", signer_address=ADDR, account_address=ADDR,
        )

    def test_issue_and_sign(self):
        out = self.issue()
        self.assertTrue(out.issued)
        action = self.store.action("action-0000000001")["action"]
        sig = RestrictedSignerSimulator(self.store, "s1", ADDR).sign_permitted_action(
            permit_id=out.permit["permit_id"], compiled_action=action, now_ms=2100, current_policy_hash=H
        )
        self.assertEqual(sig.marker, "SIMULATED_NON_SIGNATURE_V1")
        self.assertEqual(self.store.action("action-0000000001")["state"], "SIGNED")

    def test_mutation_denied(self):
        out = self.issue()
        action = self.store.action("action-0000000001")["action"]
        action["size"] = "0.02"
        with self.assertRaises(SignerError):
            RestrictedSignerSimulator(self.store, "s1", ADDR).sign_permitted_action(
                permit_id=out.permit["permit_id"], compiled_action=action, now_ms=2100, current_policy_hash=H
            )

    def test_policy_rotation_denied(self):
        out = self.issue()
        action = self.store.action("action-0000000001")["action"]
        with self.assertRaises(SignerError):
            RestrictedSignerSimulator(self.store, "s1", ADDR).sign_permitted_action(
                permit_id=out.permit["permit_id"], compiled_action=action, now_ms=2100, current_policy_hash="b" * 64
            )

    def test_blocked_not_issued(self):
        i = intent()
        i["force_block"] = True
        out = self.issue(i=i)
        self.assertFalse(out.issued)
        self.assertTrue(self.store.verify_audit_chain())

    def test_cancel_owned_order(self):
        self.store.register_owned_order("order-12345678", "BTC", "0x" + "c" * 32, False, 1500)
        out = self.issue(i=intent("CANCEL_BY_CLOID"))
        self.assertTrue(out.issued)
        self.assertEqual(out.permit["target_cloid"], "0x" + "c" * 32)
        self.assertNotIn("quantity", out.permit)

    def test_durable_unreconciled_blocks_second_entry(self):
        self.issue()
        out = self.issue(pid="permit-0000000002", aid="action-0000000002")
        self.assertFalse(out.issued)
        self.assertEqual(out.code, "BLOCK_DURABLE_UNRECONCILED")


if __name__ == "__main__":
    unittest.main()
