from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r3"
CONTRACT = BASE / "HOURLY_METADATA_INVENTORY_R3_CONTRACT.json"
DERIVATION = BASE / "R2_DERIVATION.json"
APPROVAL = BASE / "HUMAN_APPROVAL_TEMPLATE.md"


class ArchiveHourlyMetadataR3Tests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exact_parent_and_three_family_scope(self) -> None:
        c = self.load(CONTRACT)
        self.assertEqual(c["inventory_id"], "HL-ARCHIVE-HOURLY-METADATA-INVENTORY-R3-001")
        self.assertEqual(c["status"], "PREREGISTERED_STATIC_AWAITING_SEPARATE_HUMAN_SCOPE_BUDGET_APPROVAL")
        self.assertEqual(c["parent_r2_attestation_commit"], "1790d6e3e2453cd96504b0f6624ca37c3847324a")
        self.assertEqual(c["parent_r2_run_id"], 31280640653)
        self.assertEqual(c["target_bucket"], "hl-mainnet-node-data")
        self.assertEqual(c["signing_region"], "ap-northeast-1")
        self.assertEqual(c["operation"], "ListObjectsV2")
        self.assertEqual(c["request_payer"], "requester")
        self.assertEqual(
            [(x["dataset_family_id"], x["prefix"]) for x in c["dataset_families"]],
            [
                ("node_fills_by_block", "node_fills_by_block/hourly/"),
                ("node_fills", "node_fills/hourly/"),
                ("node_trades", "node_trades/hourly/"),
            ],
        )

    def test_envelope_is_smaller_than_parent_300_request_proposal(self) -> None:
        c = self.load(CONTRACT)
        e = c["listing_envelope"]
        self.assertEqual(e["maximum_keys_per_request"], 1000)
        self.assertEqual(e["maximum_pages_per_family"], 16)
        self.assertEqual(e["maximum_total_list_requests"], 48)
        self.assertEqual(e["maximum_total_entries"], 48000)
        self.assertEqual(e["maximum_total_response_bytes"], 33554432)
        self.assertEqual(e["maximum_runtime_seconds"], 300)
        self.assertEqual(e["maximum_retries_per_request"], 0)
        self.assertTrue(e["pagination_authorized_after_separate_approval"])
        self.assertTrue(e["continuation_token_follow_authorized_after_separate_approval"])
        self.assertFalse(e["continuation_token_values_may_be_retained"])
        self.assertTrue(e["repeated_continuation_token_fails_closed"])
        self.assertFalse(e["http_redirect_following_authorized"])
        self.assertFalse(e["start_after_authorized"])
        self.assertFalse(e["delimiter_authorized"])
        self.assertLess(e["maximum_total_list_requests"], 300)
        self.assertLess(e["maximum_total_entries"], 250000)
        self.assertLess(e["maximum_total_response_bytes"], 268435456)

    def test_complete_or_censored_gap_logic_is_fail_closed(self) -> None:
        c = self.load(CONTRACT)
        g = c["coverage_logic"]
        self.assertTrue(g["family_complete_only_if_final_page_is_truncated_false"])
        self.assertEqual(g["family_page_cap_status"], "CENSORED_BY_LIMIT")
        self.assertEqual(g["request_or_response_failure_status"], "INCOMPLETE_DUE_TO_FAILURE")
        self.assertEqual(g["invalid_key_grammar_status"], "UNRESOLVED_LAYOUT")
        self.assertTrue(g["duplicate_key_fails_closed"])
        self.assertTrue(g["gap_claim_requires_complete_family_enumeration"])
        self.assertEqual(g["internal_full_date_expected_hours"], 24)
        self.assertTrue(g["boundary_dates_are_not_automatically_gap_tested"])
        for pattern in g["hourly_key_regex_by_family"].values():
            self.assertIn("hourly", pattern)
            self.assertIn("2[0-3]", pattern)

    def test_cost_model_is_proposed_not_authorized(self) -> None:
        c = self.load(CONTRACT)
        cost = c["cost_gate"]
        self.assertEqual(cost["stress_request_cost_usd"], 0.0024)
        self.assertEqual(cost["stress_transfer_cost_usd"], 0.016777216)
        self.assertEqual(cost["stress_total_usd"], 0.019177216)
        self.assertEqual(cost["proposed_maximum_one_time_budget_eur"], 0.1)
        self.assertIsNone(cost["maximum_one_time_budget_eur"])
        self.assertEqual(cost["maximum_monthly_budget_eur"], 0)
        self.assertTrue(cost["human_scope_budget_approval_required"])
        self.assertFalse(cost["paid_request_authorized"])
        self.assertFalse(cost["requester_pays_authorized"])
        self.assertFalse(cost["list_objects_v2_authorized"])

    def test_no_execution_or_broader_data_capability_is_opened(self) -> None:
        c = self.load(CONTRACT)
        state = c["execution_state"]
        for key in (
            "implementation_authorized", "workflow_installation_authorized", "execution_release_present",
            "execution_ready", "network_execution_authorized",
        ):
            self.assertFalse(state[key], key)
        self.assertEqual(state["s3_requests_executed"], 0)
        self.assertEqual(state["metadata_entries_observed"], 0)
        self.assertIsNone(state["empirical_result"])
        self.assertTrue(all(value is False for value in c["forbidden_capabilities"].values()))
        self.assertTrue(all(value is False for value in c["trading_authorizations"].values()))

    def test_r2_derivation_is_evidence_bound_and_explicitly_non_empirical(self) -> None:
        d = self.load(DERIVATION)
        self.assertEqual(d["source_attestation_commit"], "1790d6e3e2453cd96504b0f6624ca37c3847324a")
        self.assertEqual(d["source_artifact_sha256"], "491e651ab5b434c2c7489a4ec194a10f42cce50e80d801a3bb816c3e6b5144c8")
        self.assertEqual(d["source_result"], "FIVE_PREFIX_METADATA_LISTABLE")
        self.assertTrue(all(row["key_count"] == 25 and row["is_truncated"] for row in d["observed_first_page"]))
        self.assertEqual(d["scope_reduction"]["parent_proposed_inventory_max_requests"], 300)
        self.assertEqual(d["scope_reduction"]["r3_max_requests"], 48)
        self.assertEqual(d["scope_reduction"]["maximum_request_reduction_fraction"], 0.84)
        self.assertIn("not prove", d["capacity_rationale_not_empirical_claim"]["interpretation"])

    def test_approval_template_is_exact_and_inert(self) -> None:
        text = APPROVAL.read_text(encoding="utf-8")
        self.assertIn("APPROVE_HL_ARCHIVE_HOURLY_METADATA_INVENTORY_R3_001", text)
        self.assertIn("reviewed_commit=<CANONICAL_R3_PREREGISTRATION_COMMIT>", text)
        self.assertIn("maximum_one_time_budget_eur=0.10", text)
        self.assertIn("maximum_list_requests=48", text)
        self.assertIn("maximum_pages_per_family=16", text)
        self.assertIn("maximum_keys_per_request=1000", text)
        self.assertIn("pagination_authorized=true", text)
        self.assertIn("continuation_token_values_retained=false", text)
        self.assertIn("prefix_1=node_fills_by_block/hourly/", text)
        self.assertIn("prefix_2=node_fills/hourly/", text)
        self.assertIn("prefix_3=node_trades/hourly/", text)
        self.assertIn("larger_300_request_inventory_authorized=false", text)
        self.assertIn("object_body_download_authorized=false", text)


if __name__ == "__main__":
    unittest.main()
