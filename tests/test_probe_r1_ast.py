from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE_ROOT = ROOT / "research/wallet_copyability/probe_r1"
PYTHON_FILES = tuple(
    PROBE_ROOT / name
    for name in (
        "contract.py",
        "http_client.py",
        "probe.py",
        "validate_evidence.py",
        "validate_attestation.py",
        "validate_attestation_strict.py",
    )
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
    "validate_evidence",
    "validate_attestation",
}
FORBIDDEN_IMPORT_ROOTS = {
    "os",
    "subprocess",
    "socket",
    "requests",
    "httpx",
    "boto3",
    "web3",
}
FORBIDDEN_DIRECT_CALL_NAMES = {
    "eval",
    "exec",
    "compile",
    "__import__",
}
FORBIDDEN_PROCESS_ATTRIBUTE_CALLS = {
    "system",
    "popen",
    "check_call",
    "check_output",
}


class ProbeR1ASTTests(unittest.TestCase):
    def parse(self, path: Path) -> ast.AST:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_imports_are_allowlisted(self) -> None:
        for path in PYTHON_FILES:
            for node in ast.walk(self.parse(path)):
                modules: list[str] = []
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module is not None:
                    modules = [node.module]
                for module in modules:
                    root = module.split(".", 1)[0]
                    self.assertIn(root, ALLOWED_IMPORT_ROOTS, f"{path}:{module}")
                    self.assertNotIn(root, FORBIDDEN_IMPORT_ROOTS, f"{path}:{module}")

    def test_dynamic_execution_and_process_calls_are_absent(self) -> None:
        for path in PYTHON_FILES:
            for node in ast.walk(self.parse(path)):
                if not isinstance(node, ast.Call):
                    continue
                if isinstance(node.func, ast.Name):
                    self.assertNotIn(
                        node.func.id,
                        FORBIDDEN_DIRECT_CALL_NAMES,
                        f"{path}:{node.func.id}",
                    )
                elif isinstance(node.func, ast.Attribute):
                    self.assertNotIn(
                        node.func.attr,
                        FORBIDDEN_PROCESS_ATTRIBUTE_CALLS,
                        f"{path}:{node.func.attr}",
                    )

    def test_only_probe_module_constructs_http_requests(self) -> None:
        for path in PYTHON_FILES:
            request_calls = 0
            for node in ast.walk(self.parse(path)):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "Request"
                ):
                    request_calls += 1
            if path.name == "probe.py":
                self.assertEqual(request_calls, 2)
            else:
                self.assertEqual(request_calls, 0, str(path))

    def test_no_embedded_unregistered_network_origin(self) -> None:
        allowed = {
            "https://api.hyperliquid.xyz",
            "https://hl-mainnet-node-data.s3.amazonaws.com",
            "https://hyperliquid-archive.s3.amazonaws.com",
        }
        for path in PYTHON_FILES:
            for node in ast.walk(self.parse(path)):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and node.value.startswith("https://")
                ):
                    self.assertIn(
                        node.value.rstrip("/"),
                        allowed,
                        f"{path}:{node.value}",
                    )


if __name__ == "__main__":
    unittest.main()
