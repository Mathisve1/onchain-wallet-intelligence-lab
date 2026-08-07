from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE_ROOT = ROOT / "research/wallet_copyability/probe_r1"
EVIDENCE_ROOT = PROBE_ROOT / "evidence"
RUN_ROOT = EVIDENCE_ROOT / "run-31200124642"
FINAL_ATTESTATION = EVIDENCE_ROOT / "HL-PUBLIC-PROBE-001R1-ATTESTATION.json"


class ProbeR1ImplementationBoundaryTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_pending_templates_remain_immutable_non_results(self) -> None:
        pending = self.load(PROBE_ROOT / "PENDING_EVIDENCE.json")
        template = self.load(PROBE_ROOT / "ATTESTATION_TEMPLATE.json")
        self.assertEqual(pending["status"], "PENDING_PUBLIC_PROBE_R1")
        self.assertEqual(pending["observations"], [])
        self.assertEqual(template["status"], "PENDING_EXACT_WORKFLOW_EVIDENCE")
        self.assertIsNone(pending["reviewed_commit"])
        self.assertIsNone(template["reviewed_commit"])

    def test_canonical_final_evidence_exists_without_market_release(self) -> None:
        self.assertTrue(FINAL_ATTESTATION.is_file())
        self.assertTrue(RUN_ROOT.is_dir())
        attestation = self.load(FINAL_ATTESTATION)
        self.assertEqual(attestation["status"], "ATTESTED_PUBLIC_PROBE_PASS")
        self.assertEqual(
            attestation["reviewed_commit"],
            "c11046bf288687c6945fe9b8f17141204d24aae6",
        )
        self.assertEqual(attestation["workflow_run_id"], 31200124642)
        self.assertEqual(attestation["workflow_job_id"], 92937868268)
        self.assertEqual(attestation["artifact_id"], 9002459643)
        self.assertFalse(attestation["market_data_ingested"])
        self.assertIsNone(attestation["empirical_result"])

    def test_project_state_is_pre_archive_inventory_not_market_release(self) -> None:
        text = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
        self.assertIn("`PRE_ARCHIVE_INVENTORY`", text)
        self.assertIn(
            "`PUBLIC_TECHNICAL_PROBE_ATTESTED_ARCHIVE_ACCESS_RESTRICTED`",
            text,
        )
        self.assertIn("market_data_ingested = false", text)
        self.assertNotIn("market_data_ingested = true", text)

    def test_no_archive_inventory_directory_exists(self) -> None:
        self.assertFalse((ROOT / "research/archive_inventory").exists())

    def test_all_authorizations_remain_false(self) -> None:
        records = [
            self.load(PROBE_ROOT / "PROBE_CONTRACT.json"),
            self.load(PROBE_ROOT / "PENDING_EVIDENCE.json"),
            self.load(PROBE_ROOT / "ATTESTATION_TEMPLATE.json"),
            self.load(FINAL_ATTESTATION),
        ]
        for record in records:
            self.assertTrue(
                all(value is False for value in record["authorizations"].values())
            )
            self.assertFalse(record["market_data_ingested"])
            self.assertIsNone(record["empirical_result"])


if __name__ == "__main__":
    unittest.main()
