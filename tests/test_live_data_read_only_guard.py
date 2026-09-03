"""Falsification tests for the read-only constraint.

These tests exist to fail if someone later adds a write path, a key, a
signature or an opened authorization to the package. They read the package
source directly, so a violation cannot hide behind an untested branch.

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

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "src" / "live_data"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

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


def package_sources() -> list[Path]:
    return sorted(PACKAGE_ROOT.glob("*.py"))


class PackageSurfaceTests(unittest.TestCase):
    def test_the_package_has_the_expected_modules(self) -> None:
        self.assertEqual(
            {path.name for path in package_sources()},
            {
                "__init__.py",
                "cli.py",
                "config.py",
                "hyperliquid_rest.py",
                "hyperliquid_ws.py",
                "ingest.py",
                "models.py",
                "rate_limit.py",
                "storage.py",
            },
        )

    def test_every_module_stays_under_five_hundred_lines(self) -> None:
        for path in package_sources():
            with self.subTest(module=path.name):
                line_count = len(path.read_text(encoding="utf-8").splitlines())
                self.assertLess(line_count, 500, f"{path.name} has {line_count} lines")


class ForbiddenTokenTests(unittest.TestCase):
    def test_no_module_mentions_a_write_endpoint_key_or_signature(self) -> None:
        for path in package_sources():
            source = path.read_text(encoding="utf-8")
            for token in FORBIDDEN_TOKENS:
                with self.subTest(module=path.name, token=token):
                    self.assertFalse(
                        token in source, f"{path.name} mentions forbidden token {token!r}"
                    )

    def test_no_module_mentions_a_write_token_even_in_a_comment(self) -> None:
        # Commented-out write code is still a write path waiting to be enabled.
        for path in package_sources():
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                stripped = line.strip()
                if not stripped.startswith("#"):
                    continue
                with self.subTest(module=path.name, line=line_number):
                    self.assertNotIn(WRITE_ENDPOINT_PATH, stripped)

    def test_the_only_rest_path_in_the_package_is_info(self) -> None:
        path_pattern = re.compile(r'"(/[a-zA-Z][a-zA-Z0-9_/-]*)"')
        for path in package_sources():
            for match in path_pattern.finditer(path.read_text(encoding="utf-8")):
                with self.subTest(module=path.name, literal=match.group(1)):
                    self.assertEqual(match.group(1), "/info")

    def test_the_only_venue_hosts_are_the_documented_read_endpoints(self) -> None:
        url_pattern = re.compile(r'"(https://[^"]+|wss://[^"]+)"')
        allowed = {"https://api.hyperliquid.xyz", "wss://api.hyperliquid.xyz/ws"}
        found = set()
        for path in package_sources():
            found.update(match.group(1) for match in url_pattern.finditer(path.read_text(encoding="utf-8")))
        self.assertTrue(found <= allowed, f"unexpected endpoints: {sorted(found - allowed)}")


class NetworkImportBoundaryTests(unittest.TestCase):
    """Mirror the forbidden-import rule governance applies to src/archive_inventory.

    Importing this package must load no network or process machinery. The
    stdlib HTTP client is imported inside the transport factory instead, so a
    caller that injects its own transport never pulls in ssl or socket.
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

    def test_no_module_level_network_or_process_imports(self) -> None:
        for path in package_sources():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            offending = self._module_level_imports(tree) & self.FORBIDDEN_IMPORT_ROOTS
            with self.subTest(module=path.name):
                self.assertEqual(offending, set(), f"{path.name} imports {sorted(offending)}")

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
    def test_no_module_sets_an_authorization_to_true(self) -> None:
        assignment = re.compile(r"_authorized\s*=\s*True")
        for path in package_sources():
            with self.subTest(module=path.name):
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
