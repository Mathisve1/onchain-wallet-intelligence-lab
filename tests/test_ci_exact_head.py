from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ci.yml"
BOUNDARY_HELPER = ROOT / "governance/r11a_native_boundary.sh"


class ExactCIHeadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.boundary_text = BOUNDARY_HELPER.read_text(encoding="utf-8")

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

    def test_ci_source_builds_and_reverifies_boundary_before_every_python(self) -> None:
        self.assertIn("governance/r11a_bytecode_boundary.c", self.boundary_text)
        self.assertNotIn("difflib.abi3.so", self.text)
        self.assertIn(
            'governance/r11a_native_boundary.sh prepare "${R11A_NATIVE_ENV_FILE}"',
            self.text,
        )
        self.assertEqual(
            self.text.count(
                'governance/r11a_native_boundary.sh verify "${R11A_NATIVE_ENV_FILE}"'
            ),
            8,
        )
        self.assertIn(
            'governance/r11a_native_boundary.sh cleanup "${R11A_NATIVE_ENV_FILE}"',
            self.text,
        )
        self.assertIn("if: always()", self.text)
        self.assertIn("python governance/validate_repository.py", self.text)
        self.assertNotIn("continue-on-error", self.text)
        self.assertNotIn("|| true", self.text)
        self.assertNotIn("id-token:", self.text)
        self.assertNotIn("secrets.", self.text)
        self.assertNotIn("aws-actions", self.text)
        self.assertIn("timeout-minutes: 60", self.text)

    def test_boundary_contract_is_repeatable_source_bound_and_diagnostic(self) -> None:
        for required in (
            "B_FRESH_AUTHENTICATED_HEAD_SOURCE",
            'git cat-file blob "$SOURCE_OID"',
            'compare_full_files "repeat build"',
            'compare_full_files "fresh rebuild versus promoted artifact"',
            "python_headers_inventory_sha256",
            "cc_specs_sha256",
            "compile_argv_sha256",
            "artifact_sha256",
            "print_binary_diagnostics",
            "require_binary_sha256",
            "import root inventory is not exact",
            "R11A_NATIVE_ARTIFACT_DEV",
            "R11A_NATIVE_ARTIFACT_INO",
            "readelf -S",
            "objdump -x",
            "cmp -l",
            "PYTHONSAFEPATH",
            "PYTHONNOUSERSITE",
        ):
            self.assertIn(required, self.boundary_text)
        self.assertNotIn("|| true", self.boundary_text)
        self.assertIn("printf -- '--- %s: %s ---", self.boundary_text)
        self.assertIn("set +e", self.boundary_text)

    def test_required_ci_steps_remain_in_fail_closed_order(self) -> None:
        names = (
            "Verify exact CI commit identity",
            "Prepare and verify source-built native boundary",
            "Run focused normal and optimized import-isolation tests",
            "Run complete bytecode-enabled verification",
            "Run complete bytecode-disabled control",
            "Validate repository governance",
            "Clean source-built native boundary",
        )
        offsets = [self.text.index(name) for name in names]
        self.assertEqual(offsets, sorted(offsets))


if __name__ == "__main__":
    unittest.main()
