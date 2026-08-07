from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class BoundedAutonomyGovernanceTests(unittest.TestCase):
    def load(self, path: str) -> dict:
        return json.loads((ROOT / path).read_text())

    def test_policy_keeps_execution_closed(self) -> None:
        policy = self.load("governance/BOUND_AUTONOMY_POLICY.json")
        self.assertEqual(policy["policy_id"], "BOUND-AUTONOMY-POLICY-001")
        self.assertEqual(policy["research_track"], "DEX-COPY-AUTONOMY-001")
        self.assertEqual(policy["current_maximum_stage"], "RESEARCH")
        authorizations = policy["current_authorizations"]
        self.assertTrue(authorizations["governance_research_authorized"])
        for key, value in authorizations.items():
            if key != "governance_research_authorized":
                self.assertFalse(value, key)
        self.assertEqual(
            policy["execution_controls"]["unknown_state_behavior"], "BLOCK"
        )
        self.assertFalse(policy["execution_controls"]["llm_direct_key_access"])
        self.assertFalse(
            policy["execution_controls"]["llm_direct_action_endpoint_access"]
        )
        self.assertEqual(
            policy["live_risk_parameters"]["state"], "UNSET_LIVE_BLOCKER"
        )

    def test_human_retains_exclusive_governance(self) -> None:
        policy = self.load("governance/BOUND_AUTONOMY_POLICY.json")
        powers = set(policy["human_governance"]["exclusive_powers"])
        required = {
            "PROMOTE_STAGE",
            "ADD_OR_REMOVE_CAPITAL",
            "PROMOTE_MODEL_VERSION",
            "PROMOTE_POLICY_VERSION",
            "CHANGE_RISK_LIMITS",
            "AUTHORIZE_LEVERAGE",
            "AUTHORIZE_SIGNING",
            "REVOKE_AGENT_AUTHORITY",
        }
        self.assertTrue(required.issubset(powers))
        forbidden = set(policy["ai_boundary"]["always_forbidden"])
        self.assertIn("TRANSFER_FUNDS", forbidden)
        self.assertIn("WITHDRAW_FUNDS", forbidden)
        self.assertIn("CHANGE_POLICY_OR_RISK_LIMIT", forbidden)
        self.assertIn("OVERRIDE_BLOCK", forbidden)

    def test_authorization_matrix_is_fail_closed(self) -> None:
        matrix = self.load(
            "research/bounded_autonomy/AUTHORIZATION_MATRIX.json"
        )
        self.assertEqual(matrix["current_maximum_stage"], "RESEARCH")
        self.assertFalse(matrix["automatic_promotion"])
        self.assertFalse(matrix["positive_result_can_change_authorization"])
        self.assertEqual(matrix["missing_state_behavior"], "DENY")
        states = matrix["states"]
        self.assertTrue(states["governance_and_architecture_research"]["authorized"])
        self.assertTrue(states["public_read_only_probe"]["authorized"])
        for key, record in states.items():
            if key not in {
                "governance_and_architecture_research",
                "public_read_only_probe",
            }:
                self.assertFalse(record["authorized"], key)

    def test_trade_intent_contract_is_closed(self) -> None:
        contract = self.load(
            "research/bounded_autonomy/TRADE_INTENT_CONTRACT.json"
        )
        self.assertFalse(contract["additional_fields_allowed"])
        self.assertEqual(contract["allowed_values"]["order_type"], ["IOC_LIMIT"])
        self.assertEqual(contract["allowed_values"]["venue"], ["HYPERLIQUID"])
        forbidden = set(contract["always_forbidden_action_types"])
        self.assertTrue(
            {
                "TRANSFER",
                "WITHDRAW",
                "APPROVE_AGENT",
                "UPDATE_LEVERAGE",
                "ARBITRARY_EXCHANGE_ACTION",
            }.issubset(forbidden)
        )
        self.assertTrue(contract["permit_rules"]["single_use"])
        self.assertTrue(contract["permit_rules"]["mutation_invalidates_permit"])

    def test_official_source_register_is_capability_only(self) -> None:
        register = self.load(
            "research/bounded_autonomy/OFFICIAL_SOURCE_REGISTER.json"
        )
        self.assertEqual(register["research_track"], "DEX-COPY-AUTONOMY-001")
        self.assertFalse(
            register["rules"]["vendor_claim_is_independent_audit"]
        )
        self.assertFalse(
            register["rules"]["vendor_claim_is_profitability_evidence"]
        )
        sources = register["sources"]
        self.assertGreaterEqual(len(sources), 10)
        self.assertEqual(len({item["source_id"] for item in sources}), len(sources))
        for item in sources:
            self.assertTrue(item["url"].startswith("https://"))
            self.assertIn("OFFICIAL", item["source_class"])

    def test_parent_study_contract_remains_read_only(self) -> None:
        parent = self.load(
            "research/wallet_copyability/DATA_CONTRACT.json"
        )
        self.assertEqual(parent["study_id"], "WALLET-COPYABILITY-STUDY-001")
        self.assertTrue(parent["execution_boundary"]["read_only"])
        self.assertFalse(parent["market_data_ingested"])
        self.assertIsNone(parent["empirical_result"])
        self.assertTrue(
            all(value is False for value in parent["authorizations"].values())
        )


if __name__ == "__main__":
    unittest.main()
