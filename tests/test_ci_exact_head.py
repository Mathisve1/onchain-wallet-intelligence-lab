from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ci.yml"
BOUNDARY_HELPER = ROOT / "governance/r11a_native_boundary.sh"

_EXPRESSION = re.compile(r"\$\{\{.*?\}\}")
_CONTEXT_ROOT = re.compile(
    r"\b(github|runner|env|steps|job|needs|matrix|strategy|vars|secrets|inputs)\."
)
_STEP = re.compile(
    r"^      - name: (?P<name>[^\n]+)\n"
    r"(?P<body>.*?)(?=^      - name: |\Z)",
    re.MULTILINE | re.DOTALL,
)

_CONTEXT_AVAILABILITY = {
    "workflow_env": {"github", "secrets", "inputs", "vars"},
    "job_env": {"github", "needs", "strategy", "matrix", "vars", "secrets", "inputs"},
    "step_env": {
        "github", "needs", "strategy", "matrix", "job", "runner",
        "env", "vars", "secrets", "steps", "inputs",
    },
    "step_with": {
        "github", "needs", "strategy", "matrix", "job", "runner",
        "env", "vars", "secrets", "steps", "inputs",
    },
}


def _unsupported_contexts(expression: str, placement: str) -> set[str]:
    referenced = set(_CONTEXT_ROOT.findall(expression))
    return referenced - _CONTEXT_AVAILABILITY[placement]


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
        native_operations = re.findall(
            r'governance/r11a_native_boundary\.sh setup-python '
            r'(prepare|verify|cleanup) "\$\{R11A_NATIVE_ENV_FILE\}"',
            self.text,
        )
        self.assertEqual(
            native_operations,
            ["prepare"] + ["verify"] * 8 + ["cleanup"],
        )
        native_calls = re.findall(
            r"governance/r11a_native_boundary\.sh [^\n]+",
            self.text,
        )
        self.assertEqual(len(native_calls), len(native_operations))
        for operation in ("prepare", "verify", "cleanup"):
            self.assertNotIn(
                f'governance/r11a_native_boundary.sh {operation} '
                '"${R11A_NATIVE_ENV_FILE}"',
                self.text,
            )
        self.assertIn(
            'if [[ -e "${R11A_NATIVE_ENV_FILE}" || '
            '-L "${R11A_NATIVE_ENV_FILE}" ]]; then',
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

    def test_setup_python_trust_bootstrap_is_prepare_only_and_fail_closed(self) -> None:
        self.assertIn(
            'if [[ "$operation" = prepare ]]; then\n'
            '            freeze_github_setup_python_tree "$root" "$runner_tool_cache"\n'
            "        fi",
            self.boundary_text,
        )
        self.assertEqual(
            self.boundary_text.count(
                'freeze_github_setup_python_tree "$root" "$runner_tool_cache"'
            ),
            1,
        )
        self.assertIn(
            'assert_github_frozen_setup_python_tree "$root" "$runner_tool_cache"',
            self.boundary_text,
        )
        self.assertIn(
            '/usr/bin/env -i PATH=/usr/bin:/bin \\\n'
            '            /usr/bin/sudo -n /usr/bin/chown 0:0 -- "$path"',
            self.boundary_text,
        )
        self.assertIn(
            '/usr/bin/sudo -n /usr/bin/find -P "$root" -xdev',
            self.boundary_text,
        )
        self.assertIn(
            'setup-python installation contains a nested mount',
            self.boundary_text,
        )
        self.assertIn(
            'die "setup-python mount-table inspection failed"',
            self.boundary_text,
        )
        self.assertIn(
            'die "setup-python mount-table inspection returned no mounts"',
            self.boundary_text,
        )
        self.assertIn(
            'find -P "$root" -xdev ! -type l -perm /022',
            self.boundary_text,
        )
        self.assertIn(
            '[[ "$target" = "$root"/* ]]',
            self.boundary_text,
        )
        self.assertIn(
            'setup-python installation contains a non-root-owned path',
            self.boundary_text,
        )
        self.assertIn(
            'setup-python installation contains a group/world-writable path',
            self.boundary_text,
        )
        self.assertIn(
            'setup-python $label is writable by the effective user',
            self.boundary_text,
        )
        self.assertIn(
            "[[ $(stat -c '%u:%g:%a' -- /) = 0:0:755 ]]",
            self.boundary_text,
        )
        self.assertIn(
            '0:0:777|0:0:755)',
            self.boundary_text,
        )
        self.assertIn(
            '/usr/bin/sudo -n /usr/bin/chmod 0755 -- /opt',
            self.boundary_text,
        )
        self.assertNotIn(
            '/usr/bin/chown 0:0 -- /opt',
            self.boundary_text,
        )
        self.assertIn(
            "opt_identity=$(stat -c '%d:%i' -- /opt)",
            self.boundary_text,
        )
        self.assertIn(
            "observed_identity=$(stat -c '%d:%i' -- /opt)",
            self.boundary_text,
        )
        self.assertIn(
            '[[ "$observed_identity" = "$opt_identity" ]]',
            self.boundary_text,
        )
        self.assertIn(
            '[[ ! -w /opt ]]',
            self.boundary_text,
        )
        self.assertEqual(
            self.boundary_text.count('    seal_github_opt_ancestor\n'),
            1,
        )
        self.assertGreaterEqual(
            self.boundary_text.count('assert_github_opt_ancestor_sealed'),
            3,
        )
        freeze_start = self.boundary_text.index(
            'freeze_github_setup_python_tree() {'
        )
        freeze_end = self.boundary_text.index(
            '\n}\n\ncheck_required_commands()',
            freeze_start,
        )
        freeze_body = self.boundary_text[freeze_start:freeze_end]
        self.assertLess(
            freeze_body.index(
                'assert_setup_python_system_helper /usr/bin/chmod 755'
            ),
            freeze_body.index('seal_github_opt_ancestor'),
        )
        self.assertLess(
            freeze_body.index('seal_github_opt_ancestor'),
            freeze_body.index('for path in "${chain[@]}"; do'),
        )
        self.assertLess(
            freeze_body.index('seal_github_opt_ancestor'),
            freeze_body.index('assert_setup_python_tree_shape "$root"'),
        )
        self.assertNotIn("sudo -E", self.boundary_text)

    def test_workflow_context_availability_and_runner_temp_scope(self) -> None:
        exact_commit = "${{ github.event_name == 'pull_request' && github.event.pull_request.head.sha || github.sha }}"
        checkout_ref = "${{ env.EXACT_CI_COMMIT }}"
        runner_expression = "${{ runner.temp }}"
        version_expression = "${{ steps.pinned_python.outputs['python-version'] }}"
        path_expression = "${{ steps.pinned_python.outputs['python-path'] }}"
        bindings = (
            "R11A_NATIVE_ENV_FILE: "
            f"{runner_expression}/r11a-native-boundary.env",
            f"R11A_SETUP_PYTHON_VERSION: {version_expression}",
            f"R11A_SETUP_PYTHON_PATH: {path_expression}",
        )
        self.assertEqual(_unsupported_contexts(exact_commit, "workflow_env"), set())
        self.assertEqual(_unsupported_contexts(checkout_ref, "step_with"), set())
        self.assertEqual(_unsupported_contexts(runner_expression, "job_env"), {"runner"})
        self.assertEqual(_unsupported_contexts(runner_expression, "step_env"), set())
        self.assertIn("steps", _CONTEXT_AVAILABILITY["step_env"])
        self.assertEqual(_unsupported_contexts(version_expression, "job_env"), {"steps"})
        self.assertEqual(_unsupported_contexts(version_expression, "step_env"), set())
        self.assertEqual(_unsupported_contexts(path_expression, "step_env"), set())
        for binding in bindings:
            self.assertNotIn("    env:\n      " + binding, self.text)

        steps = dict(_STEP.findall(self.text))
        self.assertIn("        id: pinned_python\n", steps["Set up pinned Python"])

        consumers = {
            name: body
            for name, body in _STEP.findall(self.text)
            if '${R11A_NATIVE_ENV_FILE}' in body
        }
        self.assertEqual(
            set(consumers),
            {
                "Prepare and verify source-built native boundary",
                "Run focused normal and optimized import-isolation tests",
                "Run complete bytecode-enabled verification",
                "Run complete bytecode-disabled control",
                "Validate repository governance",
                "Clean source-built native boundary",
            },
        )
        placement = (
            "        env:\n"
            + "".join(f"          {binding}\n" for binding in bindings)
        )
        for name, body in consumers.items():
            with self.subTest(step=name):
                self.assertIn(placement, body)
        self.assertEqual(
            _EXPRESSION.findall(self.text),
            [exact_commit, checkout_ref]
            + [runner_expression, version_expression, path_expression]
            * len(consumers),
        )

    def test_setup_python_adapter_scrubs_loader_environment(self) -> None:
        reject_start = self.boundary_text.index("reject_build_overrides() {")
        reject_end = self.boundary_text.index(
            "assert_loader_environment_absent() {",
            reject_start,
        )
        reject_body = self.boundary_text[reject_start:reject_end]
        self.assertIn(
            "GCC_EXEC_PREFIX LD_AUDIT LD_PRELOAD LD_LIBRARY_PATH LD_RUN_PATH",
            reject_body,
        )

        adapter_start = self.boundary_text.index("setup_python_adapter() {")
        adapter_end = self.boundary_text.index("validate_elf() {", adapter_start)
        adapter = self.boundary_text[adapter_start:adapter_end]
        unset_block = (
            "    unset \\\n"
            "        LD_AUDIT LD_LIBRARY_PATH LD_PRELOAD LD_RUN_PATH PKG_CONFIG_PATH \\\n"
            "        Python_ROOT_DIR Python2_ROOT_DIR Python3_ROOT_DIR pythonLocation \\\n"
            "        R11A_SETUP_PYTHON_VERSION R11A_SETUP_PYTHON_PATH \\\n"
            "        R11A_NATIVE_TRUSTED_PYTHON_CONFIG\n"
        )
        unset_offset = adapter.index(unset_block)
        for capture in (
            "local saved_loader_path=${LD_LIBRARY_PATH-}",
            "local saved_ld_audit=${LD_AUDIT-}",
            "local saved_ld_preload=${LD_PRELOAD-}",
            "local saved_ld_run_path=${LD_RUN_PATH-}",
            "local saved_internal_python_config=${R11A_NATIVE_TRUSTED_PYTHON_CONFIG-}",
        ):
            self.assertLess(adapter.index(capture), unset_offset)
        self.assertLess(
            unset_offset,
            adapter.index("    assert_loader_environment_absent\n", unset_offset),
        )
        self.assertLess(unset_offset, adapter.index("    check_required_commands\n"))
        path_reset = "    PATH=/usr/bin:/bin\n    export PATH\n"
        self.assertLess(unset_offset, adapter.index(path_reset))
        self.assertLess(adapter.index(path_reset), adapter.index("    check_required_commands\n"))

        scrubbed_start = adapter.index("    if ! scrubbed_probe=$(\n")
        scrubbed_end = adapter.index(
            "    assert_loader_environment_absent\n",
            scrubbed_start,
        )
        scrubbed_probe = adapter[scrubbed_start:scrubbed_end]
        self.assertIn(
            '[[ "$python_real" = "$root/bin/python3.12" ]]',
            adapter,
        )
        self.assertEqual(adapter.count("        env -i \\\n"), 1)
        self.assertIn('            PATH="$root/bin:/usr/bin:/bin" \\\n', scrubbed_probe)
        self.assertIn('            "$python_real" -I -S -c \\\n', scrubbed_probe)
        self.assertIn(
            'any(name in os.environ for name in '
            '("LD_AUDIT", "LD_LIBRARY_PATH", "LD_PRELOAD", "LD_RUN_PATH"))',
            scrubbed_probe,
        )
        self.assertIn("    [[ ${probe_lines[6]} = absent ]]", scrubbed_probe)
        self.assertIsNone(
            re.search(
                r"(?m)^\s+(?:LD_AUDIT|LD_LIBRARY_PATH|LD_PRELOAD|LD_RUN_PATH)=",
                adapter,
            )
        )

        trusted_config = (
            '    readonly R11A_NATIVE_TRUSTED_PYTHON_CONFIG='
            '"$root/bin/python3-config"\n'
        )
        self.assertGreater(adapter.index(trusted_config), adapter.index(path_reset))
        self.assertNotIn("    exec env \\\n", adapter)
        self.assertGreater(
            adapter.index('    run_boundary_operation "$operation" "$env_file"\n'),
            scrubbed_start,
        )
        self.assertIn(
            '        setup_python_adapter "$2" "$3"\n'
            "        return\n",
            self.boundary_text,
        )

        compile_start = self.boundary_text.index("compile_once() {")
        compile_end = self.boundary_text.index("build_pair() {", compile_start)
        compile_once = self.boundary_text[compile_start:compile_end]
        self.assertIn("    env -i \\\n", compile_once)
        for loader_name in ("LD_AUDIT", "LD_LIBRARY_PATH", "LD_PRELOAD", "LD_RUN_PATH"):
            self.assertNotIn(loader_name, compile_once)

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
            "Set up pinned Python",
            "Prepare and verify source-built native boundary",
            "Run focused normal and optimized import-isolation tests",
            "Run complete bytecode-enabled verification",
            "Run complete bytecode-disabled control",
            "Validate repository governance",
            "Clean source-built native boundary",
        )
        offsets = [self.text.index(name) for name in names]
        self.assertEqual(offsets, sorted(offsets))
        step_names = [name for name, _ in _STEP.findall(self.text)]
        setup_index = step_names.index("Set up pinned Python")
        self.assertEqual(
            step_names[setup_index + 1],
            "Prepare and verify source-built native boundary",
        )


if __name__ == "__main__":
    unittest.main()
