from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
PREREG = BASE / "r10c/R10C_BOUNDARY_RECORD_CORRELATION_PREREGISTRATION.json"
DIR = BASE / "r10c_approval"
TEXT = DIR / "APPROVE_HL_ARCHIVE_R10C_BOUNDARY_RECORD_CORRELATION_001.txt"
RECEIPT = DIR / "APPROVE_HL_ARCHIVE_R10C_BOUNDARY_RECORD_CORRELATION_001.json"


class R10CApprovalTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        value = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsInstance(value, dict)
        return value

    def test_exact_approval_text_is_hash_bound(self) -> None:
        self.assertEqual(hashlib.sha256(TEXT.read_bytes()).hexdigest(), "3bea842b40837f791f1c2799822382adbab4f256185a59287b2f635cbaa4bdbe")
        self.assertTrue(TEXT.read_bytes().endswith(b"\n"))
        a = self.load(RECEIPT)
        self.assertEqual(a["exact_approval_text_sha256"], "3bea842b40837f791f1c2799822382adbab4f256185a59287b2f635cbaa4bdbe")
        self.assertEqual(a["reviewed_commit"], "a812f7d5b67203c801f856c85b046af8e136c8f3")

    def test_scope_matches_preregistration(self) -> None:
        p = self.load(PREREG)
        a = self.load(RECEIPT)
        s = a["approved_future_scope"]
        t = p["exact_future_network_target"]
        self.assertEqual(s["maximum_get_object_requests"], 1)
        self.assertEqual(s["maximum_retries_per_request"], 0)
        self.assertEqual(s["object_key"], t["key"])
        self.assertEqual(s["object_expected_size_bytes"], t["expected_size_bytes"])
        self.assertEqual(s["object_expected_etag"], t["expected_etag"])
        self.assertEqual(s["object_expected_compressed_sha256"], t["expected_compressed_sha256"])

    def test_processing_is_exact_boundary_correlation_only(self) -> None:
        a = self.load(RECEIPT)
        p = a["approved_future_processing"]
        self.assertTrue(p["metadata_prefix_processing"])
        self.assertTrue(p["event_array_contents_inspection"])
        self.assertEqual(p["event_array_contents_inspection_scope"], "PAIR_SHAPE_AND_FILL_TIME_ONLY")
        self.assertEqual(p["fill_object_field_allowlist"], ["time"])
        self.assertTrue(p["fill_time_integer_milliseconds_processing"])
        self.assertTrue(p["aggregate_boundary_correlation_retention"])
        self.assertFalse(p["individual_metadata_value_retention"])
        self.assertFalse(p["individual_fill_time_retention"])
        self.assertFalse(p["leading_event_string_value_retention"])
        self.assertFalse(p["leading_event_string_wallet_semantics"])
        self.assertFalse(p["economic_fill_field_processing"])
        self.assertFalse(p["wallet_address_retention"])

    def test_approval_opens_implementation_not_execution(self) -> None:
        a = self.load(RECEIPT)
        self.assertEqual(a["status"], "OWNER_APPROVED_IMPLEMENTATION_NO_EXECUTION")
        self.assertFalse(a["execution_authorized_by_this_approval"])
        self.assertTrue(a["separate_execution_release_required"])
        self.assertTrue(a["separate_canonical_activation_required"])
        self.assertTrue(all(v is False for v in a["current_runtime_authority"].values()))
        self.assertTrue(all(v is False for v in a["downstream_authorizations"].values()))
        self.assertTrue(all(v is False for v in a["trading_authorizations"].values()))

    def test_dedicated_validator_passes(self) -> None:
        done = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r10c_approval.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("R10C_APPROVAL_VALID", done.stdout)


if __name__ == "__main__":
    unittest.main()
