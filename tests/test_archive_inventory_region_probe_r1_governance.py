from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ArchiveRegionProbeR1GovernanceTests(unittest.TestCase):
    def test_region_probe_r1_implementation_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, "governance/validate_region_probe_r1_implementation.py"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("REGION_PROBE_R1_IMPLEMENTATION_VALIDATION_PASS", completed.stdout)


if __name__ == "__main__":
    unittest.main()
