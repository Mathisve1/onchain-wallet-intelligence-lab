from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/hyperliquid-public-probe-r1.yml"


class ProbeR1ExactHeadTests(unittest.TestCase):
    def test_pull_request_checks_out_source_head_not_merge_ref(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("github.event.pull_request.head.sha", text)
        self.assertIn("EXACT_REVIEWED_COMMIT", text)
        self.assertIn("ref: ${{ env.EXACT_REVIEWED_COMMIT }}", text)
        self.assertIn('git rev-parse HEAD', text)
        self.assertIn('test "${observed}" = "${EXACT_REVIEWED_COMMIT}"', text)

    def test_attested_reviewed_commit_uses_exact_head_variable(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("REVIEWED_COMMIT: ${{ env.EXACT_REVIEWED_COMMIT }}", text)
        self.assertNotIn("REVIEWED_COMMIT: ${{ github.sha }}", text)


if __name__ == "__main__":
    unittest.main()
