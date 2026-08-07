from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE_ROOT = ROOT / "research/wallet_copyability/probe_r1"
EVIDENCE_ROOT = PROBE_ROOT / "evidence"


class ProbeR1ImplementationBoundaryTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_only_pending_templates_exist(self) -> None:
        pending = self.load(PROBE_ROOT / "PENDING_EVIDENCE.json")
        attestation = self.load(PROBE_ROOT / "ATTESTATION_TEMPLATE.json")
        self.assertEqual(pending["status"], "PENDING_PUBLIC_PROBE_R1")
        self.assertEqual(pending["observations"], [])
        self.assertEqual(
            attestation["status"],
            "PENDING_EXACT_WORKFLOW_EVIDENCE",
        )
        self.assertFalse(
            (EVIDENCE_ROOT / "HL-PUBLIC-PROBE-001R1-ATTESTATION.json").exists()
        )
        self.assertEqual(list(EVIDENCE_ROOT.glob("run-*")), [])

    def test_project_state_remains_pre_data(self) -> None:
        text = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
        self.assertIn("`PRE_DATA`", text)
        self.assertIn("`PREREGISTERED_NO_MARKET_RELEASE`", text)
        self.assertNotIn("PUBLIC_TECHNICAL_PROBE_ATTESTED", text)

    def test_no_archive_inventory_directory_exists(self) -> None:
        self.assertFalse((ROOT / "research/archive_inventory").exists())

    def test_all_authorizations_remain_false(self) -> None:
        contract = self.load(PROBE_ROOT / "PROBE_CONTRACT.json")
        pending = self.load(PROBE_ROOT / "PENDING_EVIDENCE.json")
        attestation = self.load(PROBE_ROOT / "ATTESTATION_TEMPLATE.json")
        for record in (contract, pending, attestation):
            self.assertTrue(
                all(
                    value is False
                    for value in record["authorizations"].values()
                )
            )
            self.assertFalse(record["market_data_ingested"])
            self.assertIsNone(record["empirical_result"])


if __name__ == "__main__":
    unittest.main()
