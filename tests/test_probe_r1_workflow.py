from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/hyperliquid-public-probe-r1.yml"


class ProbeR1WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_probe_is_manual_only(self) -> None:
        self.assertIn("on:\n  workflow_dispatch:", self.text)
        self.assertIn("reviewed_commit:", self.text)
        for forbidden_trigger in (
            "pull_request:",
            "push:",
            "schedule:",
            "repository_dispatch:",
        ):
            self.assertNotIn(forbidden_trigger, self.text)

    def test_exact_reviewed_sha_is_checked_out_and_verified(self) -> None:
        for token in (
            "EXACT_REVIEWED_COMMIT: ${{ inputs.reviewed_commit }}",
            "DISPATCH_REF: ${{ github.ref }}",
            "DISPATCH_SHA: ${{ github.sha }}",
            "ref: ${{ env.EXACT_REVIEWED_COMMIT }}",
            'test "${DISPATCH_REF}" = "refs/heads/main"',
            'test "${EXACT_REVIEWED_COMMIT}" = "${DISPATCH_SHA}"',
            'observed="$(git rev-parse HEAD)"',
            'test "${observed}" = "${EXACT_REVIEWED_COMMIT}"',
            "REVIEWED_COMMIT: ${{ env.EXACT_REVIEWED_COMMIT }}",
            "CHECKED_OUT_COMMIT: ${{ env.EXACT_REVIEWED_COMMIT }}",
            "'dispatch_ref': os.environ['DISPATCH_REF']",
            "'dispatch_sha': os.environ['DISPATCH_SHA']",
        ):
            self.assertIn(token, self.text)
        self.assertNotIn("REVIEWED_COMMIT: ${{ github.sha }}", self.text)

    def test_permission_and_checkout_are_read_only(self) -> None:
        self.assertIn("permissions:\n  contents: read", self.text)
        self.assertIn("persist-credentials: false", self.text)
        for forbidden in (
            "contents: write",
            "pull-requests: write",
            "actions: write",
            "id-token: write",
            "persist-credentials: true",
        ):
            self.assertNotIn(forbidden, self.text)

    def test_actions_are_exactly_pinned(self) -> None:
        uses = [
            line.strip().split("uses:", 1)[1].strip()
            for line in self.text.splitlines()
            if "uses:" in line
        ]
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
            self.text.index(
                "Prove static safety and repository gates before network access"
            ),
            self.text.index("Execute bounded public read-only probe"),
        )
        self.assertIn(
            "python -m unittest discover -s tests -v",
            self.text,
        )
        self.assertIn(
            "python governance/validate_repository.py",
            self.text,
        )
        self.assertIn("validate_attestation_strict.py", self.text)

    def test_artifact_and_terminal_enforcement_are_present(self) -> None:
        for token in (
            "retention-days: 90",
            "overwrite: false",
            "ARTIFACT_FILES.sha256",
            "--require-non-fail",
            "workflow_run_id",
            "reviewed_commit",
            "total_declared_request_weight",
        ):
            self.assertIn(token, self.text)

    def test_no_secret_or_execution_reference(self) -> None:
        lowered = self.text.lower()
        for token in (
            "secrets.",
            "api.hyperliquid.xyz/exchange",
            "market_open",
            "order_submission",
        ):
            self.assertNotIn(token, lowered)


if __name__ == "__main__":
    unittest.main()
