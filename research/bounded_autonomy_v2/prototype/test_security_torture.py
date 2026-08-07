import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import unittest

from durable_store import DurableStore, StoreError, canonical_json, sha256_hex_bytes
from permit_service import PermitService
from restricted_signer import RestrictedSignerSimulator, SignerError

H = "a" * 64
ADDR = "0x" + "1" * 40


@dataclass(frozen=True)
class D:
    allowed: bool
    code: str


def evaluator(*args, **kwargs):
    return D(True, "ALLOW")


def cloid(strategy, permit, seq, env):
    return "0x" + sha256_hex_bytes(f"{strategy}|{permit}|{seq}|{env}".encode())[:32]


def compiler(intent, *, new_order_cloid=None, owned_orders=None):
    return {
        "action_type": "order", "coin": intent["instrument"], "side": intent["side"],
        "size": intent["requested_quantity"], "limit": intent["limit_price"],
        "reduce_only": intent["reduce_only"], "cloid": new_order_cloid,
    }


def intent():
    return {
        "schema_version": "0.3-design", "strategy_id": "COPY-001", "strategy_version_hash": H,
        "policy_version_hash": H, "data_snapshot_hash": H, "risk_snapshot_hash": H,
        "instrument": "BTC", "action": "PLACE_IOC_LIMIT", "decision_mode": "DETERMINISTIC_ONLY",
        "expires_at_ms": 10000, "side": "BUY", "reduce_only": False,
        "requested_quantity": "0.01", "limit_price": "50000", "max_slippage_bps": 25,
    }


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.s = DurableStore(self.tmp.name + "/x.db")
        self.s.register_signer("s1", ADDR, "TESTNET", 1000)
        self.s.set_execution_state("SIGNED_TEST_ONLY", False, 1100, "state:1")
        ps = PermitService(self.s, evaluator=evaluator, action_compiler=compiler, cloid_deriver=cloid)
        self.out = ps.issue(
            intent=intent(), envelope={"environment": "TESTNET", "account_address": ADDR}, risk_state={},
            now_ms=2000, quote_timestamp_ms=1900, current_policy_hash=H,
            permit_id="permit-0000000001", action_id="action-0000000001", action_sequence=1,
            signer_id="s1", signer_address=ADDR, account_address=ADDR,
        )
        self.action = self.s.action("action-0000000001")["action"]

    def tearDown(self):
        self.tmp.cleanup()

    def test_concurrent_sign_at_most_one(self):
        def work(n):
            try:
                RestrictedSignerSimulator(self.s, "s1", ADDR).sign_permitted_action(
                    permit_id="permit-0000000001", compiled_action=self.action,
                    now_ms=2100 + n, current_policy_hash=H,
                )
                return "OK"
            except (SignerError, StoreError):
                return "DENY"
        with ThreadPoolExecutor(max_workers=16) as ex:
            results = list(ex.map(work, range(32)))
        self.assertEqual(results.count("OK"), 1)
        self.assertEqual(results.count("DENY"), 31)

    def test_mutations_all_deny_without_consuming(self):
        mutations = [
            ("coin", "ETH"), ("side", "SELL"), ("size", "0.011"), ("limit", "50001"),
            ("reduce_only", True), ("cloid", "0x" + "f" * 32), ("action_type", "withdraw"),
        ]
        for field, value in mutations:
            mutated = dict(self.action)
            mutated[field] = value
            with self.assertRaises(SignerError, msg=field):
                RestrictedSignerSimulator(self.s, "s1", ADDR).sign_permitted_action(
                    permit_id="permit-0000000001", compiled_action=mutated,
                    now_ms=2100, current_policy_hash=H,
                )
            self.assertEqual(self.s.permit("permit-0000000001")["state"], "ISSUED")

    def test_consumed_before_signature_crash_cannot_reuse(self):
        action_hash = sha256_hex_bytes(canonical_json(self.action).encode())
        self.s.consume_permit(
            permit_id="permit-0000000001", signer_id="s1", action_sha256=action_hash,
            current_policy_hash=H, now_ms=2100, audit_event_id="manual-consume",
        )
        s2 = DurableStore(self.s.path)
        with self.assertRaises(SignerError):
            RestrictedSignerSimulator(s2, "s1", ADDR).sign_permitted_action(
                permit_id="permit-0000000001", compiled_action=self.action,
                now_ms=2200, current_policy_hash=H,
            )


if __name__ == "__main__":
    unittest.main()
