from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r2"
CONTRACT = BASE / "NODEDATA_METADATA_CANARY_R2_CONTRACT.json"
APPROVAL = BASE / "HUMAN_APPROVAL_TEMPLATE.md"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-nodedata-canary-r2.yml"


class ArchiveNodeDataCanaryR2Tests(unittest.TestCase):
    def load(self) -> dict:
        return json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_exact_parent_region_target_and_prefixes_are_frozen(self) -> None:
        c = self.load()
        self.assertEqual(c["canary_id"], "HL-ARCHIVE-NODEDATA-METADATA-CANARY-R2-001")
        self.assertEqual(c["status"], "PREREGISTERED_CORRECT_REGION_METADATA_CANARY_NOT_AUTHORIZED")
        self.assertEqual(c["parent_region_probe_attestation_commit"], "9378f625648592bd4a5890f47a98b36028cbd433")
        self.assertEqual(c["parent_region_probe_run_id"], 31273770895)
        self.assertEqual(c["target_bucket"], "hl-mainnet-node-data")
        self.assertEqual(c["observed_bucket_region"], "ap-northeast-1")
        self.assertEqual(c["signing_region"], "ap-northeast-1")
        self.assertEqual(c["operation"], "ListObjectsV2")
        self.assertEqual(c["request_payer"], "requester")
        self.assertEqual(
            [(row["dataset_family_id"], row["prefix"]) for row in c["dataset_families"]],
            [
                ("node_fills_by_block", "node_fills_by_block/"),
                ("node_fills", "node_fills/"),
                ("node_trades", "node_trades/"),
                ("explorer_blocks", "explorer_blocks/"),
                ("replica_cmds", "replica_cmds/"),
            ],
        )

    def test_request_and_cost_envelope_is_small_and_not_authorized(self) -> None:
        c = self.load()
        self.assertEqual(c["dataset_family_count"], 5)
        self.assertTrue(c["exactly_one_request_per_family"])
        self.assertEqual(c["maximum_keys_per_request"], 25)
        self.assertEqual(c["maximum_total_list_requests"], 5)
        self.assertEqual(c["maximum_total_entries"], 125)
        self.assertEqual(c["maximum_total_response_bytes"], 8388608)
        self.assertEqual(c["maximum_runtime_seconds"], 120)
        self.assertEqual(c["maximum_retries_per_request"], 0)
        self.assertFalse(c["pagination_authorized"])
        self.assertFalse(c["continuation_token_follow_authorized"])
        self.assertFalse(c["http_redirect_following_authorized"])
        cost = c["cost_gate"]
        self.assertEqual(cost["proposed_maximum_one_time_budget_eur"], 0.1)
        self.assertIsNone(cost["maximum_one_time_budget_eur"])
        self.assertEqual(cost["maximum_monthly_budget_eur"], 0)
        self.assertFalse(cost["paid_request_authorized"])
        self.assertFalse(cost["requester_pays_authorized"])

    def test_no_object_market_or_trading_capability_is_opened(self) -> None:
        c = self.load()
        for key in (
            "implementation_authorized", "workflow_installation_authorized", "execution_authorized",
            "fresh_paid_attempt_authorized", "list_objects_v2_authorized", "requester_pays_authorized",
            "get_object_authorized", "head_object_authorized", "get_object_attributes_authorized",
            "range_get_authorized", "object_body_download_authorized", "decompression_authorized",
            "market_data_ingestion_authorized", "larger_300_request_inventory_authorized",
        ):
            self.assertFalse(c[key], key)
        self.assertEqual(c["s3_requests_executed"], 0)
        self.assertEqual(c["metadata_entries_observed"], 0)
        self.assertIsNone(c["empirical_result"])
        self.assertTrue(all(value is False for value in c["trading_authorizations"].values()))

    def test_approval_template_is_exact_but_inert(self) -> None:
        text = APPROVAL.read_text(encoding="utf-8")
        self.assertIn("APPROVE_HL_ARCHIVE_NODEDATA_CANARY_R2_001", text)
        self.assertIn("reviewed_commit=<CANONICAL_R2_PREREGISTRATION_COMMIT>", text)
        self.assertIn("maximum_one_time_budget_eur=0.10", text)
        self.assertIn("maximum_list_requests=5", text)
        self.assertIn("maximum_keys_per_request=25", text)
        self.assertIn("signing_region=ap-northeast-1", text)
        self.assertIn("requester_pays_authorized=true", text)
        self.assertIn("list_objects_v2_authorized=true", text)
        self.assertIn("object_body_download_authorized=false", text)
        self.assertIn("larger_300_request_inventory_authorized=false", text)

    def test_preregistration_has_no_executable_or_workflow(self) -> None:
        self.assertFalse((BASE / "collector.py").exists())
        self.assertFalse((BASE / "implementation.py").exists())
        self.assertFalse((BASE / "evidence").exists())
        self.assertFalse((BASE / "outputs").exists())
        self.assertFalse(WORKFLOW.exists())


if __name__ == "__main__":
    unittest.main()
