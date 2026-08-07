from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE_ROOT = ROOT / "research/wallet_copyability/probe_r1"
PYTHON_FILES = tuple(PROBE_ROOT / name for name in ("contract.py", "http_client.py", "probe.py", "validate_evidence.py"))
ALLOWED_IMPORT_ROOTS = {
    "__future__", "argparse", "datetime", "hashlib", "json", "re", "sys", "time",
    "urllib", "dataclasses", "pathlib", "typing", "contract", "http_client", "probe",
}
FORBIDDEN_IMPORT_ROOTS = {"os", "subprocess", "socket", "requests", "httpx", "boto3", "web3"}
FORBIDDEN_CALL_NAMES = {"eval", "exec", "compile", "__import__", "system", "popen", "check_call", "check_output"}


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
                name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else None
                if name is not None:
                    self.assertNotIn(name, FORBIDDEN_CALL_NAMES, f"{path}:{name}")

    def test_no_environment_access(self) -> None:
        for path in PYTHON_FILES:
            for node in ast.walk(self.parse(path)):
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                    self.assertFalse(node.value.id == "os" and node.attr in {"environ", "getenv"}, f"{path}:os.{node.attr}")

    def test_only_probe_module_constructs_http_requests(self) -> None:
        for path in PYTHON_FILES:
            request_calls = 0
            for node in ast.walk(self.parse(path)):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "Request":
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
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith("https://"):
                    self.assertIn(node.value.rstrip("/"), allowed, f"{path}:{node.value}")


if __name__ == "__main__":
    unittest.main()
