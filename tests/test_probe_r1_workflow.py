from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/hyperliquid-public-probe-r1.yml"


class ProbeR1WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_repository_permission_is_read_only(self) -> None:
        self.assertIn("permissions:\n  contents: read", self.text)
        self.assertNotIn("contents: write", self.text)
        self.assertNotIn("pull-requests: write", self.text)
        self.assertNotIn("actions: write", self.text)
        self.assertNotIn("id-token: write", self.text)

    def test_checkout_does_not_persist_credentials(self) -> None:
        self.assertIn("persist-credentials: false", self.text)
        self.assertNotIn("persist-credentials: true", self.text)

    def test_all_actions_are_pinned_to_full_commit_shas(self) -> None:
        uses = [line.strip().split("uses:", 1)[1].strip() for line in self.text.splitlines() if "uses:" in line]
        self.assertEqual(
            uses,
            [
                "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
                "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
                "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
            ],
        )
        for use in uses:
            self.assertRegex(use, r"^[^@\s]+@[0-9a-f]{40}$")

    def test_workflow_runs_static_gates_before_network_probe(self) -> None:
        static_position = self.text.index("Prove static safety and repository gates before network access")
        probe_position = self.text.index("Execute bounded public read-only probe")
        self.assertLess(static_position, probe_position)
        self.assertIn("python -m unittest discover -s tests -v", self.text)
        self.assertIn("python governance/validate_repository.py", self.text)

    def test_artifact_capture_and_terminal_enforcement_are_present(self) -> None:
        self.assertIn("retention-days: 90", self.text)
        self.assertIn("overwrite: false", self.text)
        self.assertIn("ARTIFACT_FILES.sha256", self.text)
        self.assertIn("--require-non-fail", self.text)
        self.assertIn("workflow_run_id", self.text)
        self.assertIn("reviewed_commit", self.text)

    def test_no_secret_or_execution_capability_is_referenced(self) -> None:
        forbidden = (
            "secrets.",
            "api.hyperliquid.xyz/exchange",
            "private_key",
            "withdraw",
            "market_open",
            "order_submission",
        )
        lowered = self.text.lower()
        for token in forbidden:
            self.assertNotIn(token.lower(), lowered)


if __name__ == "__main__":
    unittest.main()
