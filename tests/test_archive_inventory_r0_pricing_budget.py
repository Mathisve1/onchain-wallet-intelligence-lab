from __future__ import annotations

import json
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "research/archive_inventory"


class ArchiveR0PricingBudgetTests(unittest.TestCase):
    def load(self, name: str) -> dict:
        return json.loads((ARCHIVE / name).read_text(encoding="utf-8"))

    def test_pricing_freeze_is_conservative_but_not_self_authorizing(self) -> None:
        pricing = self.load("PRICING_EVIDENCE_TEMPLATE.json")
        self.assertEqual(pricing["status"], "PENDING_PRE_EXECUTION_PRICING_REFRESH")
        self.assertEqual(pricing["pricing_freeze_status"], "FROZEN_CONSERVATIVE_R0_PRE_APPROVAL")
        self.assertIsNone(pricing["bucket_regions"]["hl-mainnet-node-data"])
        self.assertIsNone(pricing["bucket_regions"]["hyperliquid-archive"])
        self.assertFalse(pricing["official_claims"]["free_transfer_allowance_relied_on_for_budget"])
        self.assertEqual(Decimal(str(pricing["stress_price_ceilings"]["list_rate_usd_per_1000"])), Decimal("0.05"))
        self.assertEqual(Decimal(str(pricing["stress_price_ceilings"]["transfer_rate_usd_per_gb"])), Decimal("0.5"))
        self.assertEqual(Decimal(str(pricing["proposed_maximum_one_time_budget_eur"])), Decimal("1.0"))
        self.assertIsNone(pricing["maximum_one_time_budget_eur"])
        self.assertEqual(pricing["maximum_monthly_budget_eur"], 0)
        self.assertFalse(pricing["paid_request_authorized"])
        self.assertFalse(pricing["requester_pays_authorized"])
        self.assertFalse(pricing["list_objects_authorized"])

    def test_r0_preregistration_remains_frozen_after_separate_approval(self) -> None:
        contract = self.load("METADATA_CANARY_R0_CONTRACT.json")
        self.assertEqual(contract["canary_id"], "HL-ARCHIVE-METADATA-CANARY-R0-001")
        self.assertEqual(contract["status"], "PREREGISTERED_MICRO_CANARY_NOT_AUTHORIZED")
        self.assertEqual(contract["operation"], "ListObjectsV2")
        self.assertEqual(contract["request_payer"], "requester")
        self.assertEqual(contract["dataset_family_count"], 7)
        self.assertTrue(contract["exactly_one_request_per_family"])
        self.assertFalse(contract["pagination_allowed"])
        self.assertFalse(contract["continuation_token_follow_allowed"])
        self.assertEqual(contract["max_keys_per_request"], 25)
        self.assertEqual(contract["max_total_list_requests"], 7)
        self.assertEqual(contract["max_total_entries"], 175)
        self.assertEqual(contract["max_total_response_bytes"], 8388608)
        self.assertEqual(contract["max_runtime_seconds"], 180)
        self.assertEqual(contract["max_retries_per_request"], 0)
        self.assertFalse(contract["execution_authorized"])
        self.assertFalse(contract["list_objects_authorized"])
        self.assertFalse(contract["cost_gate"]["paid_request_authorized"])
        self.assertFalse(contract["cost_gate"]["requester_pays_authorized"])
        self.assertIsNone(contract["cost_gate"]["maximum_one_time_budget_eur"])
        self.assertEqual(contract["cost_gate"]["proposed_maximum_one_time_budget_eur"], 1.0)
        self.assertTrue(all(v is False for v in contract["authorizations"].values()))

    def test_stress_cost_math_is_exact(self) -> None:
        pricing = self.load("PRICING_EVIDENCE_TEMPLATE.json")
        calls = Decimal(str(pricing["r0_hard_usage_caps"]["max_total_list_requests"]))
        bytes_cap = Decimal(str(pricing["r0_hard_usage_caps"]["max_total_response_bytes"]))
        list_rate = Decimal(str(pricing["stress_price_ceilings"]["list_rate_usd_per_1000"]))
        transfer_rate = Decimal(str(pricing["stress_price_ceilings"]["transfer_rate_usd_per_gb"]))
        request_cost = calls / Decimal(1000) * list_rate
        transfer_cost = bytes_cap / Decimal(1_000_000_000) * transfer_rate
        total = request_cost + transfer_cost
        self.assertEqual(request_cost, Decimal("0.00035"))
        self.assertEqual(transfer_cost, Decimal("0.0041943040"))
        self.assertEqual(total, Decimal("0.0045443040"))
        self.assertEqual(Decimal(str(pricing["modeled_costs_usd"]["stress_total_cost_at_all_caps"])), Decimal("0.004544304"))

    def test_human_approval_and_installed_workflow_are_separate_from_frozen_pricing_template(self) -> None:
        approval = (ARCHIVE / "HUMAN_APPROVAL_TEMPLATE.md").read_text(encoding="utf-8")
        for token in (
            "APPROVE_HL_ARCHIVE_METADATA_CANARY_R0_001",
            "maximum_one_time_budget_eur=1.00",
            "maximum_list_requests=7",
            "maximum_keys_per_request=25",
            "maximum_retries_per_request=0",
            "pagination_authorized=false",
            "requester_pays_authorized=true",
            "list_objects_v2_authorized=true",
            "get_object_authorized=false",
            "object_body_download_authorized=false",
        ):
            self.assertIn(token, approval)
        self.assertTrue((ROOT / ".github/workflows/hyperliquid-archive-metadata-canary-r0.yml").exists())
        self.assertFalse((ROOT / ".github/workflows/hyperliquid-archive-metadata-canary.yml").exists())


if __name__ == "__main__":
    unittest.main()
