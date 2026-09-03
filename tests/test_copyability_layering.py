"""The copyability package keeps the same layer discipline as the live-data core.

Standard library only, no transport, no entry point, and its single sibling
dependency is the local live-data store inside the loader.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = REPOSITORY_ROOT / "src" / "copyability"

FORBIDDEN_ROOTS = {
    "aiohttp", "boto3", "botocore", "httpx", "requests", "socket", "subprocess",
    "urllib", "websocket", "websockets", "http", "ssl", "asyncio",
}
ALLOWED_SIBLING_IMPORTS = {"loader.py": {"src.live_data.storage", "src.live_data.ingest"}}
FORBIDDEN_TOKENS = ("/exchange", "api.hyperliquid", "private_key", "signature", "secret")


def sources() -> list[Path]:
    return sorted(PACKAGE.glob("*.py"))


class LayeringTests(unittest.TestCase):
    def test_the_package_has_the_expected_modules(self) -> None:
        self.assertEqual(
            {p.name for p in sources()},
            {
                "__init__.py", "baselines.py", "classify.py", "costs.py", "coverage.py",
                "execution.py", "inputs.py", "loader.py", "metrics.py", "pit.py", "pnl.py",
                "simulate.py",
            },
        )

    def test_no_module_reaches_the_network_or_a_process(self) -> None:
        for path in sources():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                roots: set[str] = set()
                if isinstance(node, ast.Import):
                    roots = {alias.name.split(".", 1)[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    roots = {node.module.split(".", 1)[0]}
                self.assertEqual(roots & FORBIDDEN_ROOTS, set(), f"{path.name} imports {roots & FORBIDDEN_ROOTS}")

    def test_only_the_loader_touches_the_live_data_package(self) -> None:
        for path in sources():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            siblings = {
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module and node.level == 0
                and node.module.startswith("src.")
            }
            self.assertEqual(siblings, ALLOWED_SIBLING_IMPORTS.get(path.name, set()), path.name)

    def test_no_module_has_an_entry_point_or_a_venue_write_token(self) -> None:
        for path in sources():
            text = path.read_text(encoding="utf-8")
            self.assertNotIn('__name__ == "__main__"', text, path.name)
            for token in FORBIDDEN_TOKENS:
                self.assertNotIn(token, text, f"{path.name} mentions {token!r}")

    def test_every_module_stays_under_five_hundred_lines(self) -> None:
        for path in sources():
            count = len(path.read_text(encoding="utf-8").splitlines())
            self.assertLess(count, 500, f"{path.name} has {count} lines")

    def test_importing_the_package_has_no_side_effects(self) -> None:
        import importlib
        import sys

        for name in [n for n in sys.modules if n.startswith("src.copyability")]:
            del sys.modules[name]
        module = importlib.import_module("src.copyability")
        self.assertTrue(module.__all__)


if __name__ == "__main__":
    unittest.main()
