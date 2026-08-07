from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src/archive_inventory"


class ArchiveStaticBoundaryTests(unittest.TestCase):
    def test_no_network_sdk_or_subprocess_capability_in_preregistration_code(self) -> None:
        forbidden = {"boto3", "botocore", "requests", "urllib", "httpx", "aiohttp", "socket", "subprocess"}
        for path in SRC.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = {alias.name.split(".", 1)[0] for alias in node.names}
                    self.assertTrue(roots.isdisjoint(forbidden), f"forbidden import in {path}: {roots}")
                if isinstance(node, ast.ImportFrom) and node.module:
                    self.assertNotIn(node.module.split(".", 1)[0], forbidden)

    def test_contract_forbids_object_body_operations(self) -> None:
        contract = json.loads((ROOT / "research/archive_inventory/INVENTORY_CONTRACT.json").read_text(encoding="utf-8"))
        self.assertFalse(contract["execution"]["get_object_authorized"])
        self.assertFalse(contract["execution"]["head_object_authorized"])
        self.assertFalse(contract["execution"]["range_get_authorized"])
        self.assertFalse(contract["execution"]["object_body_download_authorized"])
        self.assertIn("GetObject", contract["forbidden_operations"])
        self.assertIn("HeadObject", contract["forbidden_operations"])


if __name__ == "__main__":
    unittest.main()
