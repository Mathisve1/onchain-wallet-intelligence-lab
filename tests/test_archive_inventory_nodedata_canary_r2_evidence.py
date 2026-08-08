from __future__ import annotations

import base64
import gzip
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "research/archive_inventory/r2/evidence"
RUN = EVIDENCE / "run-31280640653"
ATTESTATION = EVIDENCE / "HL-ARCHIVE-NODEDATA-METADATA-CANARY-R2-001-ATTESTATION.json"

EXPECTED_FAMILIES = [
    "node_fills_by_block",
    "node_fills",
    "node_trades",
    "explorer_blocks",
    "replica_cmds",
]


class ArchiveNodeDataCanaryR2EvidenceTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def decoded_result_bytes(self) -> bytes:
        meta = self.load(RUN / "EVIDENCE_ENCODING.json")
        encoded = (RUN / meta["encoded_file"]).read_bytes()
        self.assertEqual(len(encoded), meta["encoded_size_bytes"])
        self.assertEqual(hashlib.sha256(encoded).hexdigest(), meta["encoded_sha256"])
        compressed = base64.b64decode(encoded, validate=True)
        self.assertEqual(len(compressed), meta["gzip_size_bytes"])
        self.assertEqual(hashlib.sha256(compressed).hexdigest(), meta["gzip_sha256"])
        raw = gzip.decompress(compressed)
        self.assertEqual(len(raw), meta["raw_size_bytes"])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), meta["raw_sha256"])
        return raw

    def decoded_result(self) -> dict:
        return json.loads(self.decoded_result_bytes())

    def test_exact_run_job_artifact_release_and_dispatch_are_bound(self) -> None:
        att = self.load(ATTESTATION)
        self.assertEqual(att["canonical_dispatch_commit"], "5cf612b2125877a097b9697c074ac82d66cb1635")
        self.assertEqual(att["successor_release_id"], "RELEASE_HL_ARCHIVE_NODEDATA_CANARY_R2_002")
        self.assertEqual(att["successor_release_commit"], "6128e6a9974742113f74c6e17fba7159dc60bde5")
        self.assertEqual(att["workflow_run_id"], 31280640653)
        self.assertEqual(att["workflow_job_id"], 93161240213)
        self.assertEqual(att["workflow_run_attempt"], 1)
        self.assertEqual(att["artifact_id"], 9028305474)
        self.assertEqual(att["artifact_sha256"], "491e651ab5b434c2c7489a4ec194a10f42cce50e80d801a3bb816c3e6b5144c8")
        self.assertTrue(att["release_consumed"])
        self.assertFalse(att["rerun_authorized"])

    def test_context_is_exact_manual_main_successor_identity(self) -> None:
        context = self.load(RUN / "r2-metadata-context.json")
        self.assertEqual(context["event_name"], "workflow_dispatch")
        self.assertEqual(context["dispatch_ref"], "refs/heads/main")
        self.assertEqual(context["dispatch_sha"], "5cf612b2125877a097b9697c074ac82d66cb1635")
        self.assertEqual(context["checked_out_commit"], context["dispatch_sha"])
        self.assertEqual(context["reviewed_commit"], context["dispatch_sha"])
        self.assertEqual(context["workflow_run_id"], 31280640653)
        self.assertEqual(context["workflow_run_attempt"], 1)
        self.assertEqual(context["execution_release_id"], "RELEASE_HL_ARCHIVE_NODEDATA_CANARY_R2_002")
        self.assertEqual(context["signing_region"], "ap-northeast-1")
        self.assertTrue(context["requester_pays_authorized_for_r2"])
        self.assertTrue(context["list_objects_v2_authorized_for_r2"])
        self.assertFalse(context["object_body_authorized"])
        self.assertFalse(context["market_data_ingestion_authorized"])

    def test_internal_ledger_matches_exact_retained_raw_bytes(self) -> None:
        expected = {}
        for line in (RUN / "R2_METADATA_FILES.sha256").read_text(encoding="utf-8").splitlines():
            digest, filename = line.split("  ", 1)
            expected[filename] = digest
        self.assertEqual(
            expected,
            {
                "r2-metadata-context.json": "ca346a1a1fab3e72323e081435f6755713934602968a6994c303fbb0fbf77d77",
                "r2-metadata-result.json": "ac85b1269f6c9e64dca1047246e682a8c0e47f3e4c4739a0fe72d8de9a662367",
                "r2-metadata.rc": "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa",
            },
        )
        self.assertEqual(
            hashlib.sha256((RUN / "r2-metadata-context.json").read_bytes()).hexdigest(),
            expected["r2-metadata-context.json"],
        )
        self.assertEqual(hashlib.sha256(self.decoded_result_bytes()).hexdigest(), expected["r2-metadata-result.json"])
        self.assertEqual(hashlib.sha256((RUN / "r2-metadata.rc").read_bytes()).hexdigest(), expected["r2-metadata.rc"])

    def test_result_is_exact_five_of_five_bounded_success(self) -> None:
        result = self.decoded_result()
        self.assertEqual(result["terminal_status"], "R2_NODEDATA_METADATA_CANARY_PASS")
        self.assertEqual(result["technical_result"], "FIVE_PREFIX_METADATA_LISTABLE")
        self.assertEqual(result["request_attempt_count"], 5)
        self.assertEqual(result["s3_http_request_count"], 5)
        self.assertEqual(result["successful_request_count"], 5)
        self.assertEqual(result["failed_request_count"], 0)
        self.assertEqual(result["total_entries"], 125)
        self.assertEqual(result["total_response_bytes"], 38693)
        self.assertEqual(result["runtime_seconds"], 2.340922)
        self.assertEqual(result["retries_used"], 0)
        self.assertFalse(result["pagination_followed"])
        self.assertFalse(result["http_redirects_followed"])
        self.assertTrue(result["requester_pays_requested"])
        self.assertFalse(result["continuation_token_values_retained"])
        self.assertFalse(result["object_body_requested"])
        self.assertFalse(result["decompression_used"])
        self.assertFalse(result["market_data_ingested"])
        self.assertIsNone(result["empirical_result"])

    def test_all_five_first_pages_are_successful_and_truncated(self) -> None:
        rows = self.decoded_result()["observations"]
        self.assertEqual([row["dataset_family_id"] for row in rows], EXPECTED_FAMILIES)
        self.assertEqual(len(rows), 5)
        for index, row in enumerate(rows, 1):
            self.assertEqual(row["request_index"], index)
            self.assertEqual(row["bucket"], "hl-mainnet-node-data")
            self.assertEqual(row["signing_region"], "ap-northeast-1")
            self.assertEqual(row["http_or_sdk_status_class"], "SUCCESS")
            self.assertEqual(row["key_count"], 25)
            self.assertEqual(len(row["entries"]), 25)
            self.assertTrue(row["is_truncated"])
            self.assertTrue(row["next_continuation_token_present"])
            self.assertEqual(row["request_charged"], "requester")
        self.assertEqual(sum(row["response_bytes"] for row in rows), 38693)

    def test_attestation_does_not_overclaim_complete_inventory_or_data_access(self) -> None:
        att = self.load(ATTESTATION)
        self.assertTrue(att["all_first_pages_truncated"])
        self.assertTrue(att["all_next_continuation_tokens_present"])
        self.assertFalse(att["continuation_token_values_retained"])
        self.assertEqual(att["interpretation"]["coverage_conclusion"], "FIRST_PAGE_ONLY_NOT_COMPLETE_INVENTORY")
        self.assertFalse(att["pagination_authorized"])
        self.assertFalse(att["larger_300_request_inventory_authorized"])
        self.assertFalse(att["get_object_authorized"])
        self.assertFalse(att["object_body_download_authorized"])
        self.assertFalse(att["market_data_ingestion_authorized"])
        self.assertTrue(all(value is False for value in att["trading_authorizations"].values()))
        self.assertEqual(
            att["next_gate"],
            "PREREGISTER_A_SEPARATE_BOUNDED_PAGINATED_METADATA_INVENTORY_BEFORE_ANY_CONTINUATION_OR_LARGER_REQUEST_ENVELOPE",
        )

    def test_independent_artifact_verification_is_all_pass(self) -> None:
        verification = self.load(RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
        artifact = verification["artifact"]
        self.assertEqual(artifact["provider_digest"], "sha256:" + artifact["downloaded_zip_sha256"])
        self.assertEqual(artifact["downloaded_zip_sha256"], "491e651ab5b434c2c7489a4ec194a10f42cce50e80d801a3bb816c3e6b5144c8")
        self.assertEqual(artifact["size_in_bytes"], 39364)
        self.assertTrue(all(verification["validation"].values()))
        self.assertEqual(verification["collector_return_code"], 0)
        self.assertEqual(verification["final_workflow_conclusion"], "success")


if __name__ == "__main__":
    unittest.main()
