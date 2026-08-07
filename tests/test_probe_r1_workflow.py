from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/hyperliquid-public-probe-r1.yml"


class ProbeR1WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_repository_permission_is_read_only(self) -> None:
        self.assertIn("permissions:\n  contents: read", self.text)
        for forbidden in ("contents: write", "pull-requests: write", "actions: write", "id-token: write"):
            self.assertNotIn(forbidden, self.text)

    def test_checkout_does_not_persist_credentials(self) -> None:
        self.assertIn("persist-credentials: false", self.text)
        self.assertNotIn("persist-credentials: true", self.text)

    def test_actions_are_exactly_pinned(self) -> None:
        uses = [line.strip().split("uses:", 1)[1].strip() for line in self.text.splitlines() if "uses:" in line]
        self.assertEqual(
            uses,
            [
                "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
                "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
                "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
            ],
        )

    def test_static_gates_precede_network(self) -> None:
        self.assertLess(
            self.text.index("Prove static safety and repository gates before network access"),
            self.text.index("Execute bounded public read-only probe"),
        )
        self.assertIn("python -m unittest discover -s tests -v", self.text)
        self.assertIn("python governance/validate_repository.py", self.text)

    def test_artifact_and_terminal_enforcement_are_present(self) -> None:
        for token in (
            "retention-days: 90",
            "overwrite: false",
            "ARTIFACT_FILES.sha256",
            "--require-non-fail",
            "workflow_run_id",
            "reviewed_commit",
        ):
            self.assertIn(token, self.text)

    def test_no_secret_or_execution_reference(self) -> None:
        lowered = self.text.lower()
        for token in ("secrets.", "api.hyperliquid.xyz/exchange", "private_key", "market_open", "order_submission"):
            self.assertNotIn(token, lowered)


if __name__ == "__main__":
    unittest.main()
