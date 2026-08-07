from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/hyperliquid-public-probe-r1.yml"


class ProbeR1ExactHeadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_manual_dispatch_requires_explicit_reviewed_commit(self) -> None:
        self.assertIn("on:\n  workflow_dispatch:\n    inputs:\n", self.text)
        self.assertIn("reviewed_commit:", self.text)
        self.assertIn(
            "EXACT_REVIEWED_COMMIT: ${{ inputs.reviewed_commit }}",
            self.text,
        )
        self.assertNotIn("github.event.pull_request.head.sha", self.text)
        self.assertNotIn("REVIEWED_COMMIT: ${{ github.sha }}", self.text)

    def test_checkout_is_cryptographically_bound_to_manual_input(self) -> None:
        self.assertIn("ref: ${{ env.EXACT_REVIEWED_COMMIT }}", self.text)
        self.assertIn("observed=\"$(git rev-parse HEAD)\"", self.text)
        self.assertIn(
            'test "${observed}" = "${EXACT_REVIEWED_COMMIT}"',
            self.text,
        )
        self.assertIn("^[0-9a-f]{40}$", self.text)
        self.assertIn(
            'git cat-file -e "${EXACT_REVIEWED_COMMIT}^{commit}"',
            self.text,
        )

    def test_attestation_separates_reviewed_and_checked_out_commit(self) -> None:
        self.assertIn(
            "REVIEWED_COMMIT: ${{ env.EXACT_REVIEWED_COMMIT }}",
            self.text,
        )
        self.assertIn(
            'checked_out_commit="$(git rev-parse HEAD)"',
            self.text,
        )
        self.assertIn(
            'export CHECKED_OUT_COMMIT="${checked_out_commit}"',
            self.text,
        )
        self.assertIn(
            "'reviewed_commit': os.environ['REVIEWED_COMMIT']",
            self.text,
        )
        self.assertIn(
            "'checked_out_commit': os.environ['CHECKED_OUT_COMMIT']",
            self.text,
        )


if __name__ == "__main__":
    unittest.main()
