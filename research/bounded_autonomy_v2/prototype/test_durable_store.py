import sqlite3
import tempfile
from concurrent.futures import ThreadPoolExecutor
import unittest

from durable_store import DurableStore, StoreError

H = "a" * 64
A = "0x" + "1" * 40


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = self.tmp.name + "/db.sqlite"
        self.s = DurableStore(self.db)
        self.s.register_signer("s1", A, "TESTNET", 1000)

    def tearDown(self):
        self.tmp.cleanup()

    def base(self, pid, aid):
        return {
            "schema_version": "0.3-design",
            "permit_id": pid,
            "intent_sha256": H,
            "compiled_action_sha256": H,
            "strategy_id": "COPY-001",
            "strategy_version_hash": H,
            "policy_version_hash": H,
            "data_snapshot_hash": H,
            "risk_snapshot_hash": H,
            "venue": "HYPERLIQUID",
            "network": "TESTNET",
            "account_address": A,
            "signer_id": "s1",
            "signer_address": A,
            "action": "PLACE_IOC_LIMIT",
            "instrument": "BTC",
            "decision_mode": "DETERMINISTIC_ONLY",
            "issued_at_ms": 2000,
            "expires_at_ms": 10000,
            "cloid": "0x" + "b" * 32,
        }

    def issue(self, pid="permit-0000000001", aid="action-0000000001", now=2000):
        return self.s.create_permit_bundle(
            permit_base=self.base(pid, aid),
            action_id=aid,
            action={"action_type": "order", "coin": "BTC"},
            risk_increasing=True,
            expected_quantity="0.01",
            now_ms=now,
            audit_event_id=f"issue:{pid}",
        )

    def test_audit_chain(self):
        self.issue()
        self.assertTrue(self.s.verify_audit_chain())

    def test_audit_append_only(self):
        self.issue()
        con = sqlite3.connect(self.db)
        with self.assertRaises(sqlite3.DatabaseError):
            con.execute("UPDATE audit_events SET event_type='X'")
        con.close()

    def test_monotonic_nonces(self):
        p1 = self.issue("permit-0000000001", "action-0000000001", 2000)
        p2 = self.issue("permit-0000000002", "action-0000000002", 2000)
        self.assertGreater(p2["nonce"], p1["nonce"])

    def test_concurrent_nonces_unique(self):
        def work(i):
            return self.issue(f"permit-{i:010d}", f"action-{i:010d}", 3000)["nonce"]
        with ThreadPoolExecutor(max_workers=8) as ex:
            vals = list(ex.map(work, range(1, 21)))
        self.assertEqual(len(vals), len(set(vals)))
        self.assertEqual(max(vals) - min(vals), 19)

    def test_consume_once(self):
        self.issue()
        self.s.set_execution_state("SIGNED_TEST_ONLY", False, 3000, "state:1")
        self.s.consume_permit(
            permit_id="permit-0000000001", signer_id="s1", action_sha256=H,
            current_policy_hash=H, now_ms=4000, audit_event_id="consume:1"
        )
        with self.assertRaises(StoreError):
            self.s.consume_permit(
                permit_id="permit-0000000001", signer_id="s1", action_sha256=H,
                current_policy_hash=H, now_ms=4001, audit_event_id="consume:2"
            )

    def test_kill_switch_blocks_consume(self):
        self.issue()
        self.s.set_execution_state("SIGNED_TEST_ONLY", True, 3000, "state:1")
        with self.assertRaises(StoreError):
            self.s.consume_permit(
                permit_id="permit-0000000001", signer_id="s1", action_sha256=H,
                current_policy_hash=H, now_ms=4000, audit_event_id="consume:1"
            )

    def test_revoked_signer_blocks(self):
        self.issue()
        self.s.set_execution_state("SIGNED_TEST_ONLY", False, 3000, "state:1")
        self.s.revoke_signer("s1", 3500)
        with self.assertRaises(StoreError):
            self.s.consume_permit(
                permit_id="permit-0000000001", signer_id="s1", action_sha256=H,
                current_policy_hash=H, now_ms=4000, audit_event_id="consume:1"
            )

    def test_restart_persists_nonce_and_audit(self):
        p = self.issue()
        s2 = DurableStore(self.db)
        p2 = s2.create_permit_bundle(
            permit_base=self.base("permit-0000000002", "action-0000000002"),
            action_id="action-0000000002",
            action={"action_type": "order", "coin": "BTC"},
            risk_increasing=True,
            expected_quantity="0.01",
            now_ms=2000,
            audit_event_id="issue:2",
        )
        self.assertGreater(p2["nonce"], p["nonce"])
        self.assertTrue(s2.verify_audit_chain())

    def test_fill_partial_then_full(self):
        self.issue()
        self.s.transition_action("action-0000000001", "PERMIT_ISSUED", "ACKNOWLEDGED", 3000, "ack:1")
        self.assertEqual(self.s.record_fill("action-0000000001", "0.004", 3100, "fill:1"), "PARTIALLY_FILLED")
        self.assertEqual(self.s.record_fill("action-0000000001", "0.006", 3200, "fill:2"), "FILLED")
        self.assertEqual(self.s.unresolved_risk_increasing_count(), 0)

    def test_unresolved_blocks_until_terminal(self):
        self.issue()
        self.assertEqual(self.s.unresolved_risk_increasing_count(), 1)
        self.s.transition_action("action-0000000001", "PERMIT_ISSUED", "BLOCKED", 3000, "block:1")
        self.assertEqual(self.s.unresolved_risk_increasing_count(), 0)


if __name__ == "__main__":
    unittest.main()
