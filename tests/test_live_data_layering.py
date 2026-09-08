"""Layering guards for the live data pipeline.

The deterministic core lives under ``src/`` and the network-touching collector
lives under ``research/``. The dependency arrow runs research -> src and must
never run the other way: an outer I/O layer may depend on a pure core, but a
pure core that reaches back into the experiment tree stops being pure.

These tests exist to fail if someone later reintroduces a transport under
``src/`` or an import of ``research`` from it.
"""

from __future__ import annotations

import ast
import io
import contextlib
import unittest
from pathlib import Path

from src.live_data.cli import Dependencies, main

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CORE = REPOSITORY_ROOT / "src"
COLLECTOR = REPOSITORY_ROOT / "research" / "wallet_copyability" / "live_data_collector"

#: The rule governance already applies to src/archive_inventory.
FORBIDDEN_IMPORT_ROOTS = frozenset(
    {"boto3", "botocore", "requests", "urllib", "httpx", "aiohttp", "socket", "subprocess"}
)

WALLET = "0x" + "ab" * 20


def imported_roots(path: Path) -> set[str]:
    """Every module root imported anywhere in a file, nested imports included."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".", 1)[0])
    return roots


class ArrowDirectionTests(unittest.TestCase):
    def test_no_module_under_src_imports_research(self) -> None:
        for path in sorted(CORE.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            with self.subTest(module=str(path.relative_to(REPOSITORY_ROOT))):
                self.assertNotIn("research", imported_roots(path))

    def test_the_collector_depends_on_the_core(self) -> None:
        # The arrow has to actually exist, otherwise this guard proves nothing.
        roots: set[str] = set()
        for path in sorted(COLLECTOR.glob("*.py")):
            roots |= imported_roots(path)
        self.assertIn("src", roots)


class CoreIsNetworkFreeTests(unittest.TestCase):
    def test_the_core_has_no_network_import_at_any_depth(self) -> None:
        # ast.walk semantics, matching governance/validate_repository.py: a
        # deferred import inside a function still counts as a network import.
        for path in sorted((CORE / "live_data").glob("*.py")):
            offending = imported_roots(path) & FORBIDDEN_IMPORT_ROOTS
            with self.subTest(module=path.name):
                self.assertEqual(offending, set(), f"{path.name} imports {sorted(offending)}")

    def test_the_core_defines_no_transport_of_its_own(self) -> None:
        source = "\n".join(
            path.read_text(encoding="utf-8") for path in sorted((CORE / "live_data").glob("*.py"))
        )
        for token in ("urlopen", "urllib", "websockets"):
            with self.subTest(token=token):
                self.assertNotIn(token, source)

    def test_the_cli_is_not_an_executable_entry_point(self) -> None:
        source = (CORE / "live_data" / "cli.py").read_text(encoding="utf-8")
        self.assertNotIn('if __name__ == "__main__"', source)


class CompositionRootTests(unittest.TestCase):
    def test_the_entry_point_supplies_both_transports(self) -> None:
        from research.wallet_copyability.live_data_collector.__main__ import build_dependencies

        dependencies = build_dependencies()
        self.assertTrue(callable(dependencies.transport))
        self.assertTrue(callable(dependencies.connection_factory))

    def test_network_commands_refuse_to_run_without_injected_transports(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            backfill = main(["backfill", "--wallet", WALLET, "--days", "1"])
            watch = main(["watch", "--wallets", WALLET])
        self.assertEqual((backfill, watch), (2, 2))
        self.assertIn("transport", stderr.getvalue())

    def test_local_only_commands_need_no_transports(self) -> None:
        # init-db and status must stay usable without any network dependency.
        parsed = Dependencies()
        self.assertIsNone(parsed.transport)
        self.assertIsNone(parsed.connection_factory)


if __name__ == "__main__":
    unittest.main()
