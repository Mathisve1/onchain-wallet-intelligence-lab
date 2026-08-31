from __future__ import annotations

import os
import re
import stat
import subprocess
import tempfile
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

    def _run_boundary_functions(
        self,
        command: str,
        *arguments: str,
    ) -> subprocess.CompletedProcess[str]:
        marker = '\nmain "$@"\n'
        self.assertEqual(self.boundary_text.count(marker), 1)
        definitions = self.boundary_text.split(marker, 1)[0]
        return subprocess.run(
            ["/usr/bin/bash", "-s", "--", *arguments],
            cwd="/",
            env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
            input=definitions + "\n" + command + "\n",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=30,
        )

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
        safe_start = self.boundary_text.index("safe_absolute_path() {")
        safe_end = self.boundary_text.index("\n}\n\nphysical_path() {", safe_start) + 2
        self.assertEqual(
            self.boundary_text[safe_start:safe_end],
            "safe_absolute_path() {\n"
            "    local value=$1\n"
            "    [[ \"$value\" =~ ^/[A-Za-z0-9._/-]+$ ]] || die \"path is outside the supported absolute-path grammar: $value\"\n"
            "    [[ \"$value\" != *//* ]] || die \"path is not canonical: $value\"\n"
            "    [[ \"$value\" != *:* ]] || die \"path contains a PYTHONPATH separator: $value\"\n"
            "}",
        )
        physical_start = self.boundary_text.index("physical_path() {")
        physical_end = self.boundary_text.index(
            "\n}\n\nassert_literal_github_filesystem_root_observation() {",
            physical_start,
        ) + 2
        self.assertEqual(
            self.boundary_text[physical_start:physical_end],
            "physical_path() {\n"
            "    local value\n"
            "    value=$(readlink -f -- \"$1\")\n"
            "    safe_absolute_path \"$value\"\n"
            "    printf '%s\\n' \"$value\"\n"
            "}",
        )
        literal_start = self.boundary_text.index(
            "assert_literal_github_filesystem_root() {"
        )
        literal_end = self.boundary_text.index(
            "\n}\n\nassert_github_opt_ancestor_observation() {",
            literal_start,
        )
        literal_body = self.boundary_text[literal_start:literal_end]
        for required in (
            '[[ $# = 0 ]]',
            '[[ -d / && ! -L / ]]',
            'resolved=$(/usr/bin/readlink -f -- /)',
            "ownership_mode=$(/usr/bin/stat -c '%u:%g:%a' -- /)",
            "identity=$(/usr/bin/stat -c '%d:%i' -- /)",
            'if [[ -w / ]]; then',
            'assert_literal_github_filesystem_root_observation',
        ):
            self.assertIn(required, literal_body)
        self.assertNotIn("safe_absolute_path", literal_body)
        self.assertNotIn("physical_path", literal_body)
        self.assertIsNone(
            re.search(r"physical_path[ \t]+/[ \t]*\)", self.boundary_text)
        )
        self.assertEqual(
            self.boundary_text.count(
                "\n    root_identity=$(assert_literal_github_filesystem_root)\n"
            ),
            2,
        )
        self.assertEqual(
            self.boundary_text.count(
                "observed_root_identity=$(assert_literal_github_filesystem_root)"
            ),
            1,
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
            "observed_opt_identity=$(stat -c '%d:%i' -- /opt)",
            self.boundary_text,
        )
        self.assertIn(
            '"GitHub filesystem root" "$root_identity" "$observed_root_identity"',
            self.boundary_text,
        )
        self.assertIn(
            '"GitHub /opt ancestor" "$opt_identity" "$observed_opt_identity"',
            self.boundary_text,
        )
        self.assertEqual(
            self.boundary_text.count('if [[ -d /opt && ! -L /opt ]]; then'),
            2,
        )
        self.assertEqual(
            self.boundary_text.count(
                '"$opt_contract" "$opt_writable" bootstrap'
            ),
            1,
        )
        self.assertEqual(
            self.boundary_text.count(
                '"$opt_contract" "$opt_writable" sealed'
            ),
            1,
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

        generic_cases = (
            ("safe root", 'safe_absolute_path "$1"', "/"),
            ("physical root", 'physical_path "$1"', "/"),
            ("double slash", 'safe_absolute_path "$1"', "//"),
            ("dot root", 'physical_path "$1"', "/./"),
            ("parent root", 'physical_path "$1"', "/../"),
            ("opt parent", 'physical_path "$1"', "/opt/.."),
            ("opt double slash", 'safe_absolute_path "$1"', "/opt//"),
            (
                "opt normalized traversal",
                'safe_absolute_path "$1"; resolved=$(physical_path "$1"); '
                '[[ "$resolved" = "$1" ]] || die "path is not canonical: $1"',
                "/opt/../opt",
            ),
            ("relative", 'safe_absolute_path "$1"', "relative/path"),
            ("empty", 'safe_absolute_path "$1"', ""),
            ("colon", 'safe_absolute_path "$1"', "/opt:other"),
            ("newline", 'safe_absolute_path "$1"', "/opt\nbad"),
            ("control", 'safe_absolute_path "$1"', "/opt\tbad"),
            ("confusable slash", 'safe_absolute_path "$1"', "／opt"),
        )
        for label, command, value in generic_cases:
            with self.subTest(generic_rejection=label):
                completed = self._run_boundary_functions(command, value)
                self.assertNotEqual(completed.returncode, 0, completed.stderr)
        for command in ('safe_absolute_path "$1"', 'physical_path "$1"'):
            with self.subTest(generic_root_reproduction=command):
                completed = self._run_boundary_functions(command, "/")
                self.assertIn(
                    "path is outside the supported absolute-path grammar: /",
                    completed.stderr,
                )
        physical_opt = self._run_boundary_functions('physical_path "$1"', "/opt")
        self.assertEqual(physical_opt.returncode, 0, physical_opt.stderr)
        self.assertEqual(physical_opt.stdout, "/opt\n")

        literal_root = self._run_boundary_functions(
            "assert_literal_github_filesystem_root",
        )
        if os.geteuid() == 0:
            self.assertNotEqual(literal_root.returncode, 0)
            self.assertIn(
                "GitHub filesystem root is writable by the runner identity",
                literal_root.stderr,
            )
        else:
            self.assertEqual(literal_root.returncode, 0, literal_root.stderr)
            self.assertRegex(literal_root.stdout, r"^[0-9]+:[0-9]+\n$")
        literal_argument = self._run_boundary_functions(
            'assert_literal_github_filesystem_root "$1"',
            "/",
        )
        self.assertNotEqual(literal_argument.returncode, 0)
        self.assertIn("does not accept path arguments", literal_argument.stderr)

        observation_command = (
            'assert_literal_github_filesystem_root_observation '
            '"$1" "$2" "$3" "$4"'
        )
        valid_observation = self._run_boundary_functions(
            observation_command,
            "/",
            "0:0:755",
            "false",
            "28:786433",
        )
        self.assertEqual(valid_observation.returncode, 0, valid_observation.stderr)
        self.assertEqual(valid_observation.stdout, "28:786433\n")
        invalid_observations = (
            ("resolved", "/opt", "0:0:755", "false", "28:786433"),
            ("owner", "/", "1:0:755", "false", "28:786433"),
            ("group", "/", "0:1:755", "false", "28:786433"),
            ("mode", "/", "0:0:775", "false", "28:786433"),
            ("special bits", "/", "0:0:4755", "false", "28:786433"),
            ("writable", "/", "0:0:755", "true", "28:786433"),
            ("writable unknown", "/", "0:0:755", "unknown", "28:786433"),
            ("identity", "/", "0:0:755", "false", "invalid"),
        )
        for label, *observation in invalid_observations:
            with self.subTest(root_observation_rejection=label):
                completed = self._run_boundary_functions(
                    observation_command,
                    *observation,
                )
                self.assertNotEqual(completed.returncode, 0, completed.stderr)

        opt_observation_command = (
            'assert_github_opt_ancestor_observation '
            '"$1" "$2" "$3" "$4" "$5" "$6" "$7"'
        )
        valid_opt_observations = (
            ("bootstrap 0777", "true", "/opt", "28:1", "28:2", "0:0:777", "true", "bootstrap"),
            ("bootstrap 0755", "true", "/opt", "28:1", "28:2", "0:0:755", "false", "bootstrap"),
            ("sealed 0755", "true", "/opt", "28:1", "28:2", "0:0:755", "false", "sealed"),
        )
        for label, *observation in valid_opt_observations:
            with self.subTest(opt_observation_acceptance=label):
                completed = self._run_boundary_functions(
                    opt_observation_command,
                    *observation,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
        invalid_opt_observations = (
            ("symlink", "false", "/opt", "28:1", "28:2", "0:0:777", "true", "bootstrap"),
            ("noncanonical", "true", "/tmp", "28:1", "28:2", "0:0:777", "true", "bootstrap"),
            ("cross device", "true", "/opt", "28:1", "29:2", "0:0:777", "true", "bootstrap"),
            ("wrong owner", "true", "/opt", "28:1", "28:2", "1:0:777", "true", "bootstrap"),
            ("wrong group", "true", "/opt", "28:1", "28:2", "0:1:777", "true", "bootstrap"),
            ("unexpected mode", "true", "/opt", "28:1", "28:2", "0:0:775", "true", "bootstrap"),
            ("sealed wrong owner", "true", "/opt", "28:1", "28:2", "1:0:755", "false", "sealed"),
            ("sealed wrong mode", "true", "/opt", "28:1", "28:2", "0:0:777", "false", "sealed"),
            ("sealed writable", "true", "/opt", "28:1", "28:2", "0:0:755", "true", "sealed"),
            ("identity", "true", "/opt", "28:1", "invalid", "0:0:777", "true", "bootstrap"),
        )
        for label, *observation in invalid_opt_observations:
            with self.subTest(opt_observation_rejection=label):
                completed = self._run_boundary_functions(
                    opt_observation_command,
                    *observation,
                )
                self.assertNotEqual(completed.returncode, 0, completed.stderr)

        stable_identity = (
            'assert_filesystem_identity_stable "$1" "$2" "$3"'
        )
        stable = self._run_boundary_functions(
            stable_identity,
            "GitHub filesystem root",
            "28:1",
            "28:1",
        )
        self.assertEqual(stable.returncode, 0, stable.stderr)
        for label in ("GitHub filesystem root", "GitHub /opt ancestor"):
            with self.subTest(identity_drift=label):
                drift = self._run_boundary_functions(
                    stable_identity,
                    label,
                    "28:1",
                    "28:2",
                )
                self.assertNotEqual(drift.returncode, 0, drift.stderr)
                self.assertIn(f"{label} identity changed during sealing", drift.stderr)

        with tempfile.TemporaryDirectory(prefix="r11a-opt-seal-") as directory:
            fixture = Path(directory) / "opt"
            fixture.mkdir(mode=0o777)
            os.chmod(fixture, 0o777)
            before = fixture.stat()
            for expected_initial_mode in (0o777, 0o755):
                with self.subTest(opt_seal_initial_mode=oct(expected_initial_mode)):
                    os.chmod(fixture, expected_initial_mode)
                    completed = subprocess.run(
                        ["/usr/bin/chmod", "0755", "--", str(fixture)],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    observed = fixture.stat()
                    self.assertEqual(
                        (observed.st_dev, observed.st_ino),
                        (before.st_dev, before.st_ino),
                    )
                    self.assertEqual(stat.S_IMODE(observed.st_mode), 0o755)

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
