from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "research/archive_inventory/r10_implementation/collector.py"


class ArchiveR10CliTests(unittest.TestCase):
    def test_direct_script_help_starts_without_import_error(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(COLLECTOR), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("--result-output", completed.stdout)
        self.assertIn("--wallet-feature-output", completed.stdout)
        self.assertNotIn("ModuleNotFoundError", completed.stderr)


if __name__ == "__main__":
    unittest.main()
