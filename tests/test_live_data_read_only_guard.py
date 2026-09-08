"""Falsification tests for the read-only constraint.

These tests exist to fail if someone later adds a write path, a key, a
signature or an opened authorization. They read the source directly, so a
violation cannot hide behind an untested branch.

The guard covers both layers of the pipeline. The deterministic core under
``src/live_data`` is the easy half; the collector under ``research/`` is the
half that actually holds a socket, so leaving it unscanned would guard
everything except the code that can reach the venue. Checks that only make
sense for one layer are scoped and say so.

Forbidden tokens are assembled from fragments so that this file does not
itself contain the strings it forbids.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
import unittest
from pathlib import Path

from src.live_data.config import TradingAuthorizations

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = REPOSITORY_ROOT / "src" / "live_data"
COLLECTOR_ROOT = REPOSITORY_ROOT / "research" / "wallet_copyability" / "live_data_collector"

WRITE_ENDPOINT_PATH = "/" + "exchange"

FORBIDDEN_TOKENS = (
    WRITE_ENDPOINT_PATH,
    "private" + "_key",
    "private" + "Key",
    "secret" + "_key",
    "mnemonic",
    "seed" + "_phrase",
    "eth" + "_account",
    "sign" + "_typed_data",
    "sign" + "TypedData",
    "signature",
    "wallet." + "sign",
)


def core_sources() -> list[Path]:
    """The deterministic core: pure, injected, no I/O of its own."""
    return sorted(CORE_ROOT.glob("*.py"))


def collector_sources() -> list[Path]:
    """The outer layer that owns the concrete transports."""
    return sorted(COLLECTOR_ROOT.glob("*.py"))


def guarded_sources() -> list[Path]:
    """Every file the read-only constraint applies to, in both layers."""
    return core_sources() + collector_sources()


def label(path: Path) -> str:
    """Repository-relative name: both layers contain an ``__init__.py``."""
    return path.relative_to(REPOSITORY_ROOT).as_posix()


class PackageSurfaceTests(unittest.TestCase):
    def test_the_core_has_the_expected_modules(self) -> None:
        self.assertEqual(
            {path.name for path in core_sources()},
            {
                "__init__.py",
                "candles.py",
                "cli.py",
                "config.py",
                "hyperliquid_rest.py",
                "hyperliquid_ws.py",
                "ingest.py",
                "models.py",
                "rate_limit.py",
                "results.py",
                "schema.py",
                "storage.py",
                "sweep.py",
                "trades.py",
                "watch.py",
            },
        )

    def test_the_collector_has_the_expected_modules(self) -> None:
        # Pinning the file set means a new module in the layer that holds the
        # socket cannot appear without this guard being updated to cover it.
        self.assertEqual(
            {path.name for path in collector_sources()},
            {"__init__.py", "__main__.py", "transports.py", "candle_probe.py", "arm_a_candles.py", "health.py", "cohort_pipeline.py", "cohort_pipeline_freeze.py"},
        )

    def test_both_layers_are_actually_being_scanned(self) -> None:
        # A glob that silently matches nothing would make every scan below
        # vacuously pass, which is the failure mode this guard must not have.
        self.assertTrue(core_sources(), "core sources not found")
        self.assertTrue(collector_sources(), "collector sources not found")
        self.assertEqual(len(guarded_sources()), len(core_sources()) + len(collector_sources()))

    def test_every_module_stays_under_five_hundred_lines(self) -> None:
        for path in guarded_sources():
            with self.subTest(module=label(path)):
                line_count = len(path.read_text(encoding="utf-8").splitlines())
                self.assertLess(line_count, 500, f"{label(path)} has {line_count} lines")


class ForbiddenTokenTests(unittest.TestCase):
    def test_no_module_mentions_a_write_endpoint_key_or_signature(self) -> None:
        for path in guarded_sources():
            source = path.read_text(encoding="utf-8")
            for token in FORBIDDEN_TOKENS:
                with self.subTest(module=label(path), token=token):
                    self.assertFalse(
                        token in source, f"{label(path)} mentions forbidden token {token!r}"
                    )

    def test_no_module_mentions_a_write_token_even_in_a_comment(self) -> None:
        # Commented-out write code is still a write path waiting to be enabled.
        for path in guarded_sources():
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                stripped = line.strip()
                if not stripped.startswith("#"):
                    continue
                with self.subTest(module=label(path), line=line_number):
                    self.assertNotIn(WRITE_ENDPOINT_PATH, stripped)

    def test_the_only_rest_path_in_either_layer_is_info(self) -> None:
        path_pattern = re.compile(r'"(/[a-zA-Z][a-zA-Z0-9_/-]*)"')
        for path in guarded_sources():
            for match in path_pattern.finditer(path.read_text(encoding="utf-8")):
                with self.subTest(module=label(path), literal=match.group(1)):
                    self.assertEqual(match.group(1), "/info")

    def test_the_only_venue_hosts_are_the_documented_read_endpoints(self) -> None:
        url_pattern = re.compile(r'"(https://[^"]+|wss://[^"]+)"')
        allowed = {"https://api.hyperliquid.xyz", "wss://api.hyperliquid.xyz/ws"}
        for path in guarded_sources():
            found = {
                match.group(1)
                for match in url_pattern.finditer(path.read_text(encoding="utf-8"))
            }
            with self.subTest(module=label(path)):
                self.assertTrue(
                    found <= allowed, f"unexpected endpoints: {sorted(found - allowed)}"
                )

    def test_the_collector_hardcodes_no_endpoint_of_its_own(self) -> None:
        # Collector-scoped: the transports must send only where the guarded
        # core tells them to, so they may not carry a URL at all. This is what
        # makes "the transport adds no reach of its own" an enforced property
        # rather than a claim in a docstring.
        for path in collector_sources():
            source = path.read_text(encoding="utf-8")
            for token in ("https://", "wss://", "http://", "ws://"):
                with self.subTest(module=label(path), token=token):
                    self.assertNotIn(token, source)


class NetworkImportBoundaryTests(unittest.TestCase):
    """Mirror the forbidden-import rule governance applies to src/archive_inventory.

    Core-scoped on purpose: the collector exists precisely to hold the network
    imports, so applying this rule to it would be nonsense. What keeps the
    collector honest is the token, path and endpoint scanning above, plus the
    pinned module set.
    """

    FORBIDDEN_IMPORT_ROOTS = frozenset(
        {"boto3", "botocore", "requests", "urllib", "httpx", "aiohttp", "socket", "subprocess"}
    )

    def _module_level_imports(self, tree: ast.Module) -> set[str]:
        roots: set[str] = set()
        for node in tree.body:  # only top-level statements, not deferred imports
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                roots.add(node.module.split(".", 1)[0])
        return roots

    def test_the_core_has_no_module_level_network_or_process_imports(self) -> None:
        for path in core_sources():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            offending = self._module_level_imports(tree) & self.FORBIDDEN_IMPORT_ROOTS
            with self.subTest(module=label(path)):
                self.assertEqual(offending, set(), f"{label(path)} imports {sorted(offending)}")

    def test_importing_the_package_does_not_load_ssl_or_socket(self) -> None:
        script = (
            "import sys\n"
            "sys.path.insert(0, %r)\n"
            "import src.live_data\n"
            "loaded = {m for m in ('ssl', 'socket', 'http.client', 'urllib.request') "
            "if m in sys.modules}\n"
            "print(','.join(sorted(loaded)))\n"
        ) % str(REPOSITORY_ROOT)
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, check=True
        )
        self.assertEqual(result.stdout.strip(), "", "importing live_data loaded network modules")


class AuthorizationDriftTests(unittest.TestCase):
    def test_no_module_in_either_layer_sets_an_authorization_to_true(self) -> None:
        assignment = re.compile(r"_authorized\s*=\s*True")
        for path in guarded_sources():
            with self.subTest(module=label(path)):
                self.assertIsNone(assignment.search(path.read_text(encoding="utf-8")))

    def test_defaults_match_the_risk_policy_table(self) -> None:
        policy = (REPOSITORY_ROOT / "RISK_POLICY.md").read_text(encoding="utf-8")
        rows = re.findall(r"^\|\s*([^|]+?)\s*\|\s*`(true|false)`\s*\|$", policy, re.MULTILINE)
        self.assertTrue(rows, "RISK_POLICY.md authorization table could not be parsed")

        field_by_policy_name = {
            "integration": "integration_authorized",
            "paper": "paper_authorized",
            "shadow": "shadow_authorized",
            "live": "live_authorized",
            "leverage": "leverage_authorized",
            "capital allocation": "capital_allocation_authorized",
        }
        defaults = TradingAuthorizations().as_dict()
        covered = set()
        for name, state in rows:
            field = field_by_policy_name.get(name)
            if field is None:
                continue
            with self.subTest(authorization=name):
                self.assertEqual(state, "false", f"{name} is open in RISK_POLICY.md")
                self.assertIs(defaults[field], False)
                covered.add(field)
        self.assertEqual(covered, set(defaults), "an authorization is missing from RISK_POLICY.md")


if __name__ == "__main__":
    unittest.main()
