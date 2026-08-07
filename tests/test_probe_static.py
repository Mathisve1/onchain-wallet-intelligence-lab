from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/wallet_copyability/scripts/probe_public_api.py"


class ProbeStaticTests(unittest.TestCase):
    def test_probe_has_no_order_or_secret_capability(self) -> None:
        text = SCRIPT.read_text()
        self.assertIn('INFO_ENDPOINT = "https://api.hyperliquid.xyz/info"', text)
        for forbidden in (
            "api.hyperliquid.xyz/exchange",
            "private_key",
            "secret_key",
            "Authorization",
            "sign_l1_action",
            "market_open",
        ):
            self.assertNotIn(forbidden, text)

    def test_import_allowlist(self) -> None:
        tree = ast.parse(SCRIPT.read_text())
        allowed = {"argparse", "datetime", "hashlib", "json", "time", "urllib", "pathlib", "typing", "__future__"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertIn(alias.name.split(".")[0], allowed)
            elif isinstance(node, ast.ImportFrom):
                self.assertIn((node.module or "").split(".")[0], allowed)


if __name__ == "__main__":
    unittest.main()
