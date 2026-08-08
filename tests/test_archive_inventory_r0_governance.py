from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "governance/validate_r0_implementation.py"
SPEC = importlib.util.spec_from_file_location("validate_r0_implementation", VALIDATOR)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class ArchiveR0GovernanceTests(unittest.TestCase):
    def test_r0_implementation_validator_passes(self) -> None:
        module.validate()


if __name__ == "__main__":
    unittest.main()
