from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE_ROOT = ROOT / "research/wallet_copyability/probe_r1"
PYTHON_FILES = (
    PROBE_ROOT / "contract.py",
    PROBE_ROOT / "http_client.py",
    PROBE_ROOT / "probe.py",
    PROBE_ROOT / "validate_evidence.py",
)
ALLOWED_IMPORT_ROOTS = {
    "__future__",
    "argparse",
    "datetime",
    "hashlib",
    "json",
    "re",
    "sys",
    "time",
    "urllib",
    "dataclasses",
    "pathlib",
    "typing",
    "contract",
    "http_client",
    "probe",
}
ALLOWED_NETWORK_ORIGINS = {
    "https://api.hyperliquid.xyz",
    "https://hl-mainnet-node-data.s3.amazonaws.com",
    "https://hyperliquid-archive.s3.amazonaws.com",
}
FORBIDDEN_CALL_NAMES = {
    "eval",
    "exec",
    "compile",
    "__import__",
    "system",
    "popen",
    "run",
    "check_call",
    "check_output",
}


class ProbeR1ASTTests(unittest.TestCase):
    def parse(self, path: Path) -> ast.AST:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_imports_are_allowlisted(self) -> None:
        for path in PYTHON_FILES:
            tree = self.parse(path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertIn(alias.name.split(".", 1)[0], ALLOWED_IMPORT_ROOTS, f"{path}:{alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    self.assertIsNotNone(node.module, str(path))
                    self.assertIn(node.module.split(".", 1)[0], ALLOWED_IMPORT_ROOTS, f"{path}:{node.module}")

    def test_dynamic_execution_and_process_calls_are_absent(self) -> None:
        for path in PYTHON_FILES:
            tree = self.parse(path)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = None
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                if name is not None:
                    self.assertNotIn(name, FORBIDDEN_CALL_NAMES, f"{path}:{name}")

    def test_no_environment_or_secret_access(self) -> None:
        for path in PYTHON_FILES:
            tree = self.parse(path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                    self.assertFalse(node.value.id == "os" and node.attr in {"environ", "getenv"}, f"{path}:os.{node.attr}")
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    lowered = node.value.lower()
                    for token in ("authorization", "private key", "api_key", "secret_key", "/exchange"):
                        self.assertNotIn(token, lowered, f"{path}:{node.value}")

    def test_embedded_network_origins_are_closed(self) -> None:
        observed: set[str] = set()
        for path in PYTHON_FILES:
            tree = self.parse(path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith("https://"):
                    observed.add(node.value.rstrip("/"))
        self.assertTrue(observed.issubset(ALLOWED_NETWORK_ORIGINS), observed - ALLOWED_NETWORK_ORIGINS)

    def test_only_probe_module_constructs_requests(self) -> None:
        for path in PYTHON_FILES:
            tree = self.parse(path)
            request_calls = 0
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "Request":
                    request_calls += 1
            if path.name == "probe.py":
                self.assertGreaterEqual(request_calls, 2)
            else:
                self.assertEqual(request_calls, 0, str(path))


if __name__ == "__main__":
    unittest.main()
