from __future__ import annotations

import base64
import gzip
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "research/archive_inventory/r0/evidence"
RUN = EVIDENCE / "run-31260043109"


class ArchiveR0EvidenceTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def decoded_result(self) -> dict:
        meta = self.load(RUN / "EVIDENCE_ENCODING.json")
        encoded = (RUN / meta["encoded_file"]).read_bytes()
        self.assertEqual(hashlib.sha256(encoded).hexdigest(), meta["encoded_sha256"])
        compressed = base64.b64decode(encoded, validate=True)
        self.assertEqual(hashlib.sha256(compressed).hexdigest(), meta["gzip_sha256"])
        raw = gzip.decompress(compressed)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), meta["raw_sha256"])
        return json.loads(raw)

    def test_exact_run_artifact_and_consumption_are_bound(self) -> None:
        att = self.load(EVIDENCE / "HL-ARCHIVE-METADATA-CANARY-R0-001-ATTESTATION.json")
        self.assertEqual(att["canonical_release_commit"], "bc8a47a1cdeb1163657ea243d6694286d6612bed")
        self.assertEqual(att["workflow_run_id"], 31260043109)
        self.assertEqual(att["workflow_job_id"], 93109335453)
        self.assertEqual(att["artifact_id"], 9022511541)
        self.assertEqual(att["artifact_sha256"], "40b26e33833b54a872a75be066a87b7e57a0e2f3930adada76ca3829a1142c8e")
        self.assertTrue(att["release_consumed"])
        self.assertFalse(att["rerun_authorized"])
        self.assertFalse(att["fresh_paid_attempt_authorized"])

    def test_result_is_exact_bounded_partial_failure(self) -> None:
        result = self.decoded_result()
        self.assertEqual(result["terminal_status"], "R0_METADATA_CANARY_FAIL")
        self.assertEqual(result["request_attempt_count"], 7)
        self.assertEqual(result["s3_http_request_count"], 7)
        self.assertEqual(result["successful_request_count"], 2)
        self.assertEqual(result["failed_request_count"], 5)
        self.assertEqual(result["total_entries"], 50)
        self.assertEqual(result["total_response_bytes"], 14229)
        self.assertEqual(result["retries_used"], 0)
        self.assertFalse(result["pagination_followed"])
        self.assertFalse(result["http_redirects_followed"])
        self.assertFalse(result["object_body_requested"])
        self.assertFalse(result["market_data_ingested"])
        self.assertIsNone(result["empirical_result"])

    def test_successes_and_failures_are_bucket_separated(self) -> None:
        rows = self.decoded_result()["observations"]
        successes = [row for row in rows if row["http_or_sdk_status_class"] == "SUCCESS"]
        failures = [row for row in rows if row["http_or_sdk_status_class"] != "SUCCESS"]
        self.assertEqual({row["dataset_family_id"] for row in successes}, {"market_data", "asset_ctxs"})
        self.assertTrue(all(row["bucket"] == "hyperliquid-archive" for row in successes))
        self.assertTrue(all(row["request_charged"] == "requester" for row in successes))
        self.assertEqual(len(failures), 5)
        self.assertTrue(all(row["bucket"] == "hl-mainnet-node-data" for row in failures))
        self.assertTrue(all(row["http_or_sdk_status_class"] == "S3_AuthorizationHeaderMalformed" for row in failures))

    def test_exact_region_is_not_invented(self) -> None:
        att = self.load(EVIDENCE / "HL-ARCHIVE-METADATA-CANARY-R0-001-ATTESTATION.json")
        assessment = att["root_cause_assessment"]
        self.assertEqual(assessment["classification"], "STRONGLY_CONSISTENT_WITH_SIGNING_REGION_MISMATCH")
        self.assertIsNone(assessment["exact_bucket_region"])
        self.assertEqual(att["next_gate"], "PREREGISTER_EXACT_BUCKET_REGION_DISCOVERY_BEFORE_ANY_FRESH_PAID_ATTEMPT")

    def test_independent_artifact_verification_is_all_pass(self) -> None:
        verification = self.load(RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
        self.assertEqual(verification["artifact"]["provider_digest"], "sha256:" + verification["artifact"]["downloaded_zip_sha256"])
        self.assertTrue(all(verification["validation"].values()))


if __name__ == "__main__":
    unittest.main()
