from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r3"
EVIDENCE = BASE / "evidence"
RUN = EVIDENCE / "run-31299905850"
ATTESTATION = EVIDENCE / "HL-ARCHIVE-HOURLY-METADATA-INVENTORY-R3-001-ATTESTATION.json"
SUMMARY = RUN / "R3_COMPACT_INVENTORY_SUMMARY.json"
VERIFY = RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json"
LEDGER = RUN / "R3_METADATA_FILES.sha256"
CONTEXT = RUN / "r3-metadata-context.json"
CONSUMPTION = BASE / "R3_EXECUTION_RELEASE_CONSUMPTION.json"


class ArchiveHourlyMetadataR3EvidenceTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        value = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsInstance(value, dict)
        return value

    def test_exact_run_job_artifact_and_hash_binding(self) -> None:
        a = self.load(ATTESTATION)
        v = self.load(VERIFY)
        self.assertEqual(a["run_id"], 31299905850)
        self.assertEqual(a["job_id"], 93210902329)
        self.assertEqual(a["artifact_id"], 9034170863)
        self.assertEqual(a["activation_merge_commit"], "d2cc879ceb789c33ea7c6fe6ace17d1636de80ef")
        self.assertEqual(a["artifact_sha256"], "1049509ef12f1ef2a312f6ded1d443b434e2ed860503a264f103a73c2a70cf88")
        self.assertEqual(v["provider_sha256"], a["artifact_sha256"])
        self.assertEqual(v["independently_downloaded_zip_sha256"], a["artifact_sha256"])
        self.assertTrue(v["provider_digest_matches_independent_download"])
        self.assertEqual(v["verification_result"], "ALL_CHECKS_PASS")

    def test_retained_context_matches_internal_artifact_ledger(self) -> None:
        v = self.load(VERIFY)
        self.assertEqual(hashlib.sha256(CONTEXT.read_bytes()).hexdigest(), v["internal_ledger"]["r3-metadata-context.json"])
        self.assertEqual(v["internal_ledger"]["r3-metadata-result.json"], "94c3e77a05de2363b95abdce718dfd61f1b440f3d9c3972a0d03ce28a9edc479")
        self.assertEqual(v["internal_ledger"]["r3-metadata.rc"], "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa")
        ledger = LEDGER.read_text(encoding="utf-8")
        self.assertIn(v["internal_ledger"]["r3-metadata-context.json"] + "  r3-metadata-context.json", ledger)
        self.assertIn(v["internal_ledger"]["r3-metadata-result.json"] + "  r3-metadata-result.json", ledger)
        self.assertIn(v["internal_ledger"]["r3-metadata.rc"] + "  r3-metadata.rc", ledger)

    def test_result_is_complete_bounded_metadata_inventory(self) -> None:
        s = self.load(SUMMARY)
        self.assertEqual(s["terminal_status"], "R3_HOURLY_METADATA_INVENTORY_PASS")
        self.assertEqual(s["technical_result"], "THREE_HOURLY_FAMILIES_COMPLETE")
        self.assertEqual(s["request_attempt_count"], 14)
        self.assertEqual(s["s3_http_request_count"], 14)
        self.assertEqual(s["successful_request_count"], 14)
        self.assertEqual(s["failed_request_count"], 0)
        self.assertEqual(s["continuation_request_count"], 11)
        self.assertEqual(s["total_entries"], 12119)
        self.assertEqual(s["total_response_bytes"], 3997072)
        self.assertLessEqual(s["runtime_seconds"], 300)
        self.assertEqual(s["retries_used"], 0)
        self.assertTrue(s["pagination_followed"])
        self.assertFalse(s["continuation_token_values_retained"])
        self.assertFalse(s["http_redirects_followed"])
        self.assertTrue(s["requester_pays_requested"])
        self.assertFalse(s["object_body_requested"])
        self.assertFalse(s["decompression_used"])
        self.assertFalse(s["market_data_ingested"])
        self.assertIsNone(s["empirical_result"])

    def test_family_ranges_and_gap_are_exact(self) -> None:
        s = self.load(SUMMARY)
        fam = {row["dataset_family_id"]: row for row in s["family_summaries"]}
        self.assertEqual(set(fam), {"node_fills_by_block", "node_fills", "node_trades"})
        self.assertEqual((fam["node_fills_by_block"]["page_count"], fam["node_fills_by_block"]["entry_count"]), (10, 9070))
        self.assertEqual(fam["node_fills_by_block"]["earliest_path_hour_utc"], "2025-07-27T08:00:00Z")
        self.assertEqual(fam["node_fills_by_block"]["latest_path_hour_utc"], "2026-08-09T05:00:00Z")
        self.assertEqual((fam["node_fills"]["page_count"], fam["node_fills"]["entry_count"]), (2, 1507))
        self.assertEqual(fam["node_fills"]["earliest_path_hour_utc"], "2025-05-25T14:00:00Z")
        self.assertEqual(fam["node_fills"]["latest_path_hour_utc"], "2025-07-27T08:00:00Z")
        self.assertEqual((fam["node_trades"]["page_count"], fam["node_trades"]["entry_count"]), (2, 1542))
        self.assertEqual(fam["node_trades"]["gap_status"], "PROVEN_KEY_GAP")
        self.assertEqual(fam["node_trades"]["missing_internal_hour_count"], 633)
        self.assertEqual(fam["node_trades"]["first_missing_internal_hour_utc"], "2025-05-25T15:00:00Z")
        self.assertEqual(fam["node_trades"]["last_missing_internal_hour_utc"], "2025-06-20T23:00:00Z")

    def test_transition_is_same_hour_metadata_boundary_without_body_claim(self) -> None:
        a = self.load(ATTESTATION)
        t = a["metadata_transition"]
        self.assertEqual(t["legacy_node_fills_latest_path_hour_utc"], "2025-07-27T08:00:00Z")
        self.assertEqual(t["modern_node_fills_by_block_earliest_path_hour_utc"], "2025-07-27T08:00:00Z")
        self.assertEqual(t["delta_hours"], 0)
        self.assertFalse(t["schema_or_body_continuity_inferred"])
        self.assertIn("object body readability", a["claims_not_proven"])
        self.assertIn("wallet reconstruction correctness", a["claims_not_proven"])
        self.assertIn("alpha or profitability", a["claims_not_proven"])

    def test_release_is_consumed_and_all_broader_gates_closed(self) -> None:
        c = self.load(CONSUMPTION)
        self.assertEqual(c["status"], "CONSUMED_BY_RUN_31299905850_SUCCESS")
        self.assertEqual(c["s3_requests_executed"], 14)
        self.assertEqual(c["metadata_entries_observed"], 12119)
        self.assertFalse(c["rerun_authorized"])
        self.assertFalse(c["execution_ready"])
        self.assertFalse(c["requester_pays_authorized"])
        self.assertFalse(c["list_objects_v2_authorized"])
        self.assertFalse(c["single_workflow_dispatch_authorized"])
        self.assertFalse(c["object_body_download_authorized"])
        self.assertFalse(c["decompression_authorized"])
        self.assertFalse(c["market_data_ingestion_authorized"])
        self.assertFalse(c["larger_300_request_inventory_authorized"])
        self.assertTrue(all(value is False for value in c["trading_authorizations"].values()))


if __name__ == "__main__":
    unittest.main()
