from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINDING = ROOT / "research/archive_inventory/r11a_v2/R11A_V2_PREREGISTRATION_BINDINGS.json"


class R11AV2BindingTests(unittest.TestCase):
    def test_binding_validator_passes_normal_and_optimized(self) -> None:
        for args in (
            [sys.executable, "governance/validate_r11a_v2_bindings.py"],
            [sys.executable, "-O", "governance/validate_r11a_v2_bindings.py"],
        ):
            completed = subprocess.run(
                args,
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertIn("R11A_V2_PREREGISTRATION_BINDINGS_VALID", completed.stdout)

    def test_binding_is_inert_and_contains_exact_file_set(self) -> None:
        value = json.loads(BINDING.read_text(encoding="utf-8"))
        self.assertEqual(value["status"], "SEALED_PREREGISTRATION_NO_EXECUTION")
        self.assertFalse(value["owner_approval_eligible"])
        self.assertFalse(value["network_execution_authorized"])
        self.assertFalse(value["r11_closed"])
        self.assertFalse(value["r12_ready"])
        self.assertIsNone(value["empirical_result"])
        self.assertEqual(len(value["file_sha256"]), 9)
        self.assertEqual(
            value["external_bindings"]["canonical_parent_commit"],
            "57566456624eb758049aa7687bdb7b8a2844c91d",
        )

    def test_sealer_check_mode_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, "governance/seal_r11a_v2_preregistration.py", "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R11A_V2_PREREGISTRATION_BINDINGS_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
