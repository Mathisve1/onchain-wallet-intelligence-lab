import random
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
    def test_one_thousand_single_field_action_mutations_all_deny(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            store = DurableStore(tmp.name + "/x.db")
            store.register_signer("s1", ADDR, "TESTNET", 1000)
            store.set_execution_state("SIGNED_TEST_ONLY", False, 1100, "state:1")
            ps = PermitService(store, evaluator=evaluator, action_compiler=compiler, cloid_deriver=cloid)
            ps.issue(
                intent=intent(), envelope={"environment": "TESTNET", "account_address": ADDR}, risk_state={},
                now_ms=2000, quote_timestamp_ms=1900, current_policy_hash=H,
                permit_id="permit-0000000001", action_id="action-0000000001", action_sequence=1,
                signer_id="s1", signer_address=ADDR, account_address=ADDR,
            )
            original = store.action("action-0000000001")["action"]
            rng = random.Random(20260807)
            fields = ["coin", "side", "size", "limit", "reduce_only", "cloid", "action_type"]
            for n in range(1000):
                mutated = dict(original)
                field = rng.choice(fields)
                if field == "coin":
                    mutated[field] = rng.choice(["ETH", "SOL", "BAD"])
                elif field == "side":
                    mutated[field] = rng.choice(["SELL", "BAD"])
                elif field == "size":
                    mutated[field] = f"0.{rng.randint(11, 999):03d}"
                elif field == "limit":
                    mutated[field] = str(50001 + rng.randint(0, 9999))
                elif field == "reduce_only":
                    mutated[field] = True
                elif field == "cloid":
                    mutated[field] = "0x" + f"{n + 1:032x}"
                else:
                    mutated[field] = rng.choice(["withdraw", "updateLeverage", "usdSend"])
                with self.assertRaises(SignerError, msg=f"{n}:{field}"):
                    RestrictedSignerSimulator(store, "s1", ADDR).sign_permitted_action(
                        permit_id="permit-0000000001", compiled_action=mutated,
                        now_ms=2100 + n, current_policy_hash=H,
                    )
                self.assertEqual(store.permit("permit-0000000001")["state"], "ISSUED")
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
