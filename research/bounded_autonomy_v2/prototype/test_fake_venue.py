import tempfile
import unittest
from dataclasses import dataclass

from durable_store import DurableStore, sha256_hex_bytes
from permit_service import PermitService
from restricted_signer import RestrictedSignerSimulator
from fake_venue import FakeHyperliquidVenue
from offline_executor import OfflineExecutor

H = "a" * 64
ADDR = "0x" + "1" * 40


@dataclass(frozen=True)
class D:
    allowed: bool
    code: str


def evaluator(intent, envelope, risk_state, **kwargs):
    return D(True, "ALLOW")


def cloid(strategy, permit, seq, env):
    return "0x" + sha256_hex_bytes(f"{strategy}|{permit}|{seq}|{env}".encode())[:32]


def compiler(intent, *, new_order_cloid=None, owned_orders=None):
    if intent["action"] == "CANCEL_BY_CLOID":
        order = owned_orders[intent["target_strategy_order_id"]]
        return {"action_type": "cancelByCloid", "coin": intent["instrument"], "target_cloid": order["cloid"]}
    return {
        "action_type": "order", "coin": intent["instrument"], "side": intent["side"],
        "size": intent["requested_quantity"], "limit": intent["limit_price"],
        "reduce_only": intent["reduce_only"], "cloid": new_order_cloid,
    }


def envelope():
    return {"environment": "TESTNET", "account_address": ADDR}


def entry():
    return {
        "schema_version": "0.3-design", "strategy_id": "COPY-001", "strategy_version_hash": H,
        "policy_version_hash": H, "data_snapshot_hash": H, "risk_snapshot_hash": H,
        "instrument": "BTC", "action": "PLACE_IOC_LIMIT", "decision_mode": "DETERMINISTIC_ONLY",
        "expires_at_ms": 20000, "side": "BUY", "reduce_only": False,
        "requested_quantity": "0.02", "limit_price": "50000", "max_slippage_bps": 25,
    }


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = DurableStore(self.tmp.name + "/x.db")
        self.store.register_signer("s1", ADDR, "TESTNET", 1000)
        self.store.set_execution_state("SIGNED_TEST_ONLY", False, 1100, "state:1")
        self.ps = PermitService(self.store, evaluator=evaluator, action_compiler=compiler, cloid_deriver=cloid)
        self.venue = FakeHyperliquidVenue()
        self.exec = OfflineExecutor(self.store, RestrictedSignerSimulator(self.store, "s1", ADDR), self.venue)

    def tearDown(self):
        self.tmp.cleanup()

    def issue(self, pid="permit-0000000001", aid="action-0000000001"):
        return self.ps.issue(
            intent=entry(), envelope=envelope(), risk_state={}, now_ms=2000, quote_timestamp_ms=1900,
            current_policy_hash=H, permit_id=pid, action_id=aid, action_sequence=1,
            signer_id="s1", signer_address=ADDR, account_address=ADDR,
        )

    def test_full_fill(self):
        p = self.issue().permit
        self.assertEqual(self.exec.execute(permit_id=p["permit_id"], now_ms=2100, current_policy_hash=H, behavior="FILL"), "FILLED")
        self.assertEqual(self.store.unresolved_risk_increasing_count(), 0)

    def test_partial_then_fill(self):
        p = self.issue().permit
        self.assertEqual(self.exec.execute(permit_id=p["permit_id"], now_ms=2100, current_policy_hash=H, behavior="PARTIAL_THEN_FILL"), "FILLED")
        self.assertEqual(self.store.action("action-0000000001")["filled_quantity"], "0.02")

    def test_partial_only_remains_unresolved(self):
        p = self.issue().permit
        self.assertEqual(self.exec.execute(permit_id=p["permit_id"], now_ms=2100, current_policy_hash=H, behavior="PARTIAL_ONLY"), "PARTIALLY_FILLED")
        self.assertEqual(self.store.unresolved_risk_increasing_count(), 1)

    def test_duplicate_ack_idempotent(self):
        p = self.issue().permit
        self.assertEqual(self.exec.execute(permit_id=p["permit_id"], now_ms=2100, current_policy_hash=H, behavior="DUPLICATE_ACK"), "ACKNOWLEDGED")
        self.assertTrue(self.store.verify_audit_chain())

    def test_timeout_after_accept_reconciles_open(self):
        p = self.issue().permit
        self.assertEqual(self.exec.execute(permit_id=p["permit_id"], now_ms=2100, current_policy_hash=H, behavior="TIMEOUT_AFTER_ACCEPT"), "POSSIBLY_SUBMITTED")
        self.assertEqual(self.exec.reconcile_uncertain(action_id="action-0000000001", now_ms=2200), "ACKNOWLEDGED")
        self.assertEqual(self.store.unresolved_risk_increasing_count(), 1)

    def test_reject_terminal(self):
        p = self.issue().permit
        self.assertEqual(self.exec.execute(permit_id=p["permit_id"], now_ms=2100, current_policy_hash=H, behavior="REJECT"), "REJECTED")
        self.assertEqual(self.store.unresolved_risk_increasing_count(), 0)

    def test_restart_after_uncertain(self):
        p = self.issue().permit
        self.exec.execute(permit_id=p["permit_id"], now_ms=2100, current_policy_hash=H, behavior="TIMEOUT_AFTER_ACCEPT")
        store2 = DurableStore(self.store.path)
        exec2 = OfflineExecutor(store2, RestrictedSignerSimulator(store2, "s1", ADDR), self.venue)
        self.assertEqual(exec2.reconcile_uncertain(action_id="action-0000000001", now_ms=2300), "ACKNOWLEDGED")
        self.assertTrue(store2.verify_audit_chain())


if __name__ == "__main__":
    unittest.main()
