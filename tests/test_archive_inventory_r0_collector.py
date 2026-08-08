from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTOR_PATH = ROOT / "research/archive_inventory/r0/collector.py"
SPEC = importlib.util.spec_from_file_location("r0_collector", COLLECTOR_PATH)
assert SPEC is not None and SPEC.loader is not None
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        current = self.value
        self.value += 0.1
        return current


class ArchiveR0CollectorTests(unittest.TestCase):
    def test_build_command_is_exact_list_only_non_paginated_requester_pays(self) -> None:
        for _, bucket, prefix in collector.EXPECTED_DATASETS:
            command = collector.build_command(bucket, prefix)
            self.assertEqual(command[:3], ["aws", "s3api", "list-objects-v2"])
            self.assertEqual(command[command.index("--bucket") + 1], bucket)
            self.assertEqual(command[command.index("--prefix") + 1], prefix)
            self.assertEqual(command[command.index("--max-keys") + 1], "25")
            self.assertEqual(command[command.index("--request-payer") + 1], "requester")
            self.assertIn("--no-paginate", command)
            self.assertIn("--no-cli-pager", command)
            forbidden = {
                "get-object",
                "head-object",
                "get-object-attributes",
                "list-object-versions",
                "list-buckets",
                "put-object",
                "delete-object",
                "restore-object",
            }
            self.assertTrue(forbidden.isdisjoint(command))

    def test_unregistered_prefix_fails_before_runner(self) -> None:
        with self.assertRaises(collector.R0ContractError):
            collector.build_command("hl-mainnet-node-data", "not-approved/")

    def test_success_executes_exactly_seven_commands_and_never_follows_token(self) -> None:
        calls: list[list[str]] = []

        def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
            calls.append(command)
            bucket = command[command.index("--bucket") + 1]
            prefix = command[command.index("--prefix") + 1]
            payload = {
                "IsTruncated": True,
                "Contents": [
                    {
                        "Key": prefix + "sample-key",
                        "LastModified": "2026-08-08T00:00:00+00:00",
                        "ETag": "\"abc\"",
                        "Size": 123,
                        "StorageClass": "STANDARD",
                    }
                ],
                "Name": bucket,
                "Prefix": prefix,
                "MaxKeys": 25,
                "KeyCount": 1,
                "NextContinuationToken": "TOP-SECRET-TOKEN-MUST-NOT-BE-RETAINED",
                "RequestCharged": "requester",
            }
            return subprocess.CompletedProcess(command, 0, json.dumps(payload).encode(), b"")

        output = ROOT / ".tmp-r0-success.json"
        try:
            result = collector.execute_canary(
                output,
                runner=runner,
                monotonic=FakeClock(),
                now=lambda: "2026-08-08T10:00:00Z",
            )
            self.assertEqual(result["terminal_status"], "R0_METADATA_CANARY_PASS")
            self.assertEqual(result["request_attempt_count"], 7)
            self.assertEqual(result["successful_request_count"], 7)
            self.assertEqual(result["failed_request_count"], 0)
            self.assertEqual(result["total_entries"], 7)
            self.assertEqual(result["retries_used"], 0)
            self.assertFalse(result["pagination_followed"])
            self.assertEqual(len(calls), 7)
            self.assertEqual(
                [(c[c.index("--bucket") + 1], c[c.index("--prefix") + 1]) for c in calls],
                [(bucket, prefix) for _, bucket, prefix in collector.EXPECTED_DATASETS],
            )
            serialized = output.read_text(encoding="utf-8")
            self.assertNotIn("TOP-SECRET-TOKEN-MUST-NOT-BE-RETAINED", serialized)
            self.assertTrue(all(row["next_continuation_token_present"] for row in result["observations"]))
            self.assertTrue(all(row["request_charged"] == "requester" for row in result["observations"]))
        finally:
            output.unlink(missing_ok=True)

    def test_one_denied_family_is_retained_as_failure_without_retry(self) -> None:
        calls: list[list[str]] = []

        def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
            calls.append(command)
            bucket = command[command.index("--bucket") + 1]
            prefix = command[command.index("--prefix") + 1]
            if len(calls) == 3:
                return subprocess.CompletedProcess(
                    command,
                    255,
                    b"",
                    b"An error occurred (AccessDenied) when calling the ListObjectsV2 operation: Access Denied",
                )
            payload = {
                "IsTruncated": False,
                "Contents": [],
                "Name": bucket,
                "Prefix": prefix,
                "MaxKeys": 25,
                "KeyCount": 0,
                "RequestCharged": "requester",
            }
            return subprocess.CompletedProcess(command, 0, json.dumps(payload).encode(), b"")

        output = ROOT / ".tmp-r0-fail.json"
        try:
            result = collector.execute_canary(
                output,
                runner=runner,
                monotonic=FakeClock(),
                now=lambda: "2026-08-08T10:00:00Z",
            )
            self.assertEqual(result["terminal_status"], "R0_METADATA_CANARY_FAIL")
            self.assertEqual(result["request_attempt_count"], 7)
            self.assertEqual(result["successful_request_count"], 6)
            self.assertEqual(result["failed_request_count"], 1)
            self.assertEqual(len(calls), 7)
            self.assertEqual(result["observations"][2]["http_or_sdk_status_class"], "AWS_AccessDenied")
        finally:
            output.unlink(missing_ok=True)

    def test_environment_disables_aws_cli_retries(self) -> None:
        observed_env: list[dict[str, str]] = []

        def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
            env = kwargs["env"]
            assert isinstance(env, dict)
            observed_env.append(env)
            bucket = command[command.index("--bucket") + 1]
            prefix = command[command.index("--prefix") + 1]
            payload = {
                "IsTruncated": False,
                "Contents": [],
                "Name": bucket,
                "Prefix": prefix,
                "MaxKeys": 25,
                "KeyCount": 0,
            }
            return subprocess.CompletedProcess(command, 0, json.dumps(payload).encode(), b"")

        output = ROOT / ".tmp-r0-env.json"
        try:
            collector.execute_canary(output, runner=runner, monotonic=FakeClock(), now=lambda: "2026-08-08T10:00:00Z")
            self.assertEqual(len(observed_env), 7)
            self.assertTrue(all(env["AWS_MAX_ATTEMPTS"] == "1" for env in observed_env))
            self.assertTrue(all(env["AWS_RETRY_MODE"] == "standard" for env in observed_env))
            self.assertTrue(all(env["AWS_EC2_METADATA_DISABLED"] == "true" for env in observed_env))
        finally:
            output.unlink(missing_ok=True)

    def test_collector_ast_allows_only_subprocess_run_without_shell(self) -> None:
        tree = ast.parse(COLLECTOR_PATH.read_text(encoding="utf-8"), filename=str(COLLECTOR_PATH))
        subprocess_calls: list[ast.Call] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess":
                    subprocess_calls.append(node)
                    self.assertEqual(node.func.attr, "run")
                    for keyword in node.keywords:
                        if keyword.arg == "shell":
                            self.assertIsInstance(keyword.value, ast.Constant)
                            self.assertFalse(keyword.value.value)
        self.assertEqual(len(subprocess_calls), 0, "collector uses injected runner; direct subprocess calls must remain absent")

    def test_source_has_no_forbidden_aws_operation_literals(self) -> None:
        source = COLLECTOR_PATH.read_text(encoding="utf-8")
        for literal in (
            '"get-object"',
            '"head-object"',
            '"get-object-attributes"',
            '"list-object-versions"',
            '"list-buckets"',
            '"put-object"',
            '"delete-object"',
            '"restore-object"',
        ):
            self.assertNotIn(literal, source)


if __name__ == "__main__":
    unittest.main()
