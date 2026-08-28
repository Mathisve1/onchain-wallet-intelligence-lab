from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ci.yml"


class ExactCIHeadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_pull_request_uses_source_head_and_other_runs_use_github_sha(self) -> None:
        self.assertIn(
            "github.event.pull_request.head.sha || github.sha",
            self.text,
        )
        self.assertIn("ref: ${{ env.EXACT_CI_COMMIT }}", self.text)
        self.assertIn("fetch-depth: 1", self.text)
        self.assertIn("persist-credentials: false", self.text)

    def test_checked_out_commit_is_verified(self) -> None:
        self.assertIn('observed="$(git rev-parse HEAD)"', self.text)
        self.assertIn(
            'test "${observed}" = "${EXACT_CI_COMMIT}"',
            self.text,
        )

    def test_ci_is_read_only_and_actions_are_pinned(self) -> None:
        self.assertIn("permissions:\n  contents: read", self.text)
        self.assertNotIn("contents: write", self.text)
        for action in (
            "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
            "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
        ):
            self.assertIn(action, self.text)

    def test_ci_proves_normal_optimized_and_bytecode_disabled_environments(self) -> None:
        self.assertNotIn("PYTHONDONTWRITEBYTECODE: '1'", self.text)
        self.assertGreaterEqual(
            self.text.count("env -u PYTHONDONTWRITEBYTECODE -u PYTHONPYCACHEPREFIX"),
            7,
        )
        self.assertIn(
            "python -m unittest tests.test_archive_inventory_r11a_g2_owner_approval -v",
            self.text,
        )
        self.assertIn(
            "python -O -m unittest tests.test_archive_inventory_r11a_g2_owner_approval -v",
            self.text,
        )
        self.assertIn(
            "python -m unittest tests.test_archive_inventory_r11a_post_approval_validator_alignment -v",
            self.text,
        )
        self.assertIn(
            "python -O -m unittest tests.test_archive_inventory_r11a_post_approval_validator_alignment -v",
            self.text,
        )
        self.assertIn("python -m unittest discover -s tests -v", self.text)
        self.assertIn("python -B -m unittest discover -s tests -v", self.text)

    def test_ci_rebuilds_boundary_and_keeps_fail_closed_governance(self) -> None:
        self.assertIn("governance/r11a_bytecode_boundary.c", self.text)
        self.assertIn("cmp --silent difflib.abi3.so", self.text)
        self.assertIn("python governance/validate_repository.py", self.text)
        self.assertNotIn("continue-on-error", self.text)
        self.assertNotIn("id-token:", self.text)
        self.assertNotIn("secrets.", self.text)


if __name__ == "__main__":
    unittest.main()
