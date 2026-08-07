from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "governance"))

from validate_probe_evidence import (  # noqa: E402
    load_json,
    validate_contract,
    validate_static_probe_script,
)


class ProbeStaticTests(unittest.TestCase):
    def test_probe_contract_and_capability_allowlist(self) -> None:
        contract = load_json(ROOT / "research/wallet_copyability/PROBE_CONTRACT.json")
        validate_contract(contract)
        validate_static_probe_script(contract)


if __name__ == "__main__":
    unittest.main()
