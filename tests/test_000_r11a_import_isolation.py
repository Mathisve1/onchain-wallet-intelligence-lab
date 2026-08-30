from __future__ import annotations

import difflib
import hashlib
import os
import sitecustomize
import stat
import subprocess
import sys
import sysconfig
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).absolute().parents[1]
BOUNDARY_BUILDER = ROOT / "governance/r11a_native_boundary.sh"
BOUNDARY_SOURCE = ROOT / "governance/r11a_bytecode_boundary.c"
_NESTED = "R11A_IMPORT_ISOLATION_NESTED"
_NATIVE_KEYS = (
    "R11A_NATIVE_BOUNDARY_ROOT",
    "R11A_NATIVE_IMPORT_ROOT",
    "R11A_NATIVE_BOUNDARY_BINARY",
    "R11A_NATIVE_BOUNDARY_RECEIPT",
    "R11A_NATIVE_BOUNDARY_RECEIPT_SHA256",
    "R11A_NATIVE_ARTIFACT_SHA256",
    "R11A_NATIVE_ARTIFACT_DEV",
    "R11A_NATIVE_ARTIFACT_INO",
    "R11A_REPOSITORY_ROOT",
    "R11A_NATIVE_ENV_FILE",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_environment(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="ascii").splitlines():
        assert line.startswith("export ") and "=" in line
        key, value = line.removeprefix("export ").split("=", 1)
        result[key] = value
    return result


def _read_receipt(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="ascii").splitlines():
        key, value = line.split("=", 1)
        assert key not in result
        result[key] = value
    return result


class R11AImportIsolationTests(unittest.TestCase):
    maxDiff = None

    def subprocess_flags(self) -> tuple[tuple[str, ...], ...]:
        if sys.dont_write_bytecode:
            if sys.flags.optimize:
                return (("-B", "-O"),)
            return (("-B",),)
        if sys.flags.optimize:
            return (("-O",),)
        return ((), ("-O",), ("-B",), ("-B", "-O"))

    def child_environment(self, *, inherit_boundary: bool) -> dict[str, str]:
        environment = os.environ.copy()
        for key in (
            "PYTHONDONTWRITEBYTECODE",
            "PYTHONPYCACHEPREFIX",
            "R11A_PYCACHE_BOUNDARY_ACTIVE",
        ):
            environment.pop(key, None)
        if not inherit_boundary:
            for key in (*_NATIVE_KEYS, "PYTHONPATH", "PYTHONSAFEPATH", "PYTHONNOUSERSITE"):
                environment.pop(key, None)
        environment[_NESTED] = "1"
        return environment

    def run_python(
        self,
        arguments: tuple[str, ...],
        *,
        inherit_boundary: bool = False,
        expected_returncode: int = 0,
        expected_output: str | None = None,
        timeout: int = 1200,
    ) -> subprocess.CompletedProcess[bytes]:
        before = set(Path("/tmp").glob("r11a-pycache-*"))
        completed = subprocess.run(
            [sys.executable, *arguments],
            cwd=ROOT,
            env=self.child_environment(inherit_boundary=inherit_boundary),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
        combined = completed.stdout.decode("utf-8", errors="replace") + completed.stderr.decode(
            "utf-8", errors="replace"
        )
        self.assertEqual(completed.returncode, expected_returncode, combined[-16000:])
        if expected_output is not None:
            self.assertIn(expected_output, combined)
        self.assertEqual(
            [path for path in ROOT.rglob("__pycache__")],
            [],
            f"repository cache created by: {arguments}",
        )
        self.assertEqual(
            [path for path in ROOT.rglob("*.py[co]")],
            [],
            f"repository bytecode created by: {arguments}",
        )
        self.assertEqual(
            set(Path("/tmp").glob("r11a-pycache-*")) - before,
            set(),
            f"external cache root leaked by: {arguments}",
        )
        return completed

    def run_boundary_helper(
        self,
        repository: Path,
        operation: str,
        environment_file: Path,
        environment: dict[str, str],
        *,
        expected_returncode: int = 0,
        expected_output: str | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        completed = subprocess.run(
            [
                str(repository / "governance/r11a_native_boundary.sh"),
                operation,
                str(environment_file),
            ],
            cwd=repository,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=300,
        )
        combined = completed.stdout.decode("utf-8", errors="replace") + completed.stderr.decode(
            "utf-8", errors="replace"
        )
        if expected_returncode == 0:
            self.assertEqual(completed.returncode, 0, combined[-16000:])
        else:
            self.assertNotEqual(completed.returncode, 0, combined[-16000:])
        if expected_output is not None:
            self.assertIn(expected_output, combined)
        return completed

    def commit_fixture(self, repository: Path, message: str) -> None:
        committed = subprocess.run(
            [
                "git",
                "-c",
                "user.name=R11A Lifecycle Test",
                "-c",
                "user.email=r11a-lifecycle@example.invalid",
                "commit",
                "-am",
                message,
            ],
            cwd=repository,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(
            committed.returncode,
            0,
            committed.stdout.decode(errors="replace")
            + committed.stderr.decode(errors="replace"),
        )

    def test_native_boundary_is_source_built_authenticated_and_loaded(self) -> None:
        artifact = Path(os.environ["R11A_NATIVE_BOUNDARY_BINARY"])
        import_root = Path(os.environ["R11A_NATIVE_IMPORT_ROOT"])
        boundary_root = Path(os.environ["R11A_NATIVE_BOUNDARY_ROOT"])
        receipt_path = Path(os.environ["R11A_NATIVE_BOUNDARY_RECEIPT"])
        receipt = _read_receipt(receipt_path)

        self.assertEqual(Path(sitecustomize.__file__).resolve(), artifact)
        self.assertTrue(Path(sitecustomize.__spec__.origin or "").samefile(artifact))
        self.assertTrue(sys.flags.no_user_site)
        self.assertEqual(
            Path(difflib.__file__).resolve(),
            Path(sysconfig.get_path("stdlib")) / "difflib.py",
        )
        self.assertEqual(
            difflib.SequenceMatcher(None, "qabxcd", "abycdf").get_opcodes(),
            [
                ("delete", 0, 1, 0, 0),
                ("equal", 1, 3, 0, 2),
                ("replace", 3, 4, 2, 3),
                ("equal", 4, 6, 3, 5),
                ("insert", 6, 6, 5, 6),
            ],
        )
        delta = list(difflib.ndiff(["one\n", "two\n"], ["ore\n", "tree\n"]))
        self.assertEqual(list(difflib.restore(delta, 1)), ["one\n", "two\n"])
        self.assertEqual(list(difflib.restore(delta, 2)), ["ore\n", "tree\n"])
        self.assertEqual(difflib.get_close_matches("appel", ["ape", "apple", "peach"]), ["apple", "ape"])

        for path, mode, directory in (
            (boundary_root, 0o700, True),
            (import_root, 0o500, True),
            (artifact, 0o500, False),
            (receipt_path, 0o400, False),
        ):
            metadata = path.lstat()
            self.assertEqual(metadata.st_uid, os.geteuid())
            self.assertEqual(stat.S_IMODE(metadata.st_mode), mode)
            self.assertEqual(stat.S_ISDIR(metadata.st_mode), directory)
            if not directory:
                self.assertTrue(stat.S_ISREG(metadata.st_mode))
                self.assertEqual(metadata.st_nlink, 1)
        self.assertFalse(boundary_root.is_relative_to(ROOT))
        self.assertEqual(_sha256(artifact), receipt["artifact_sha256"])
        self.assertEqual(receipt["build_1_sha256"], receipt["build_2_sha256"])
        self.assertEqual(receipt["build_2_sha256"], receipt["artifact_sha256"])
        artifact_stat = artifact.stat()
        self.assertEqual(int(receipt["artifact_dev"]), artifact_stat.st_dev)
        self.assertEqual(int(receipt["artifact_ino"]), artifact_stat.st_ino)
        self.assertEqual(sorted(path.name for path in import_root.iterdir()), [artifact.name])
        self.assertEqual(
            sorted(path.name for path in boundary_root.iterdir()),
            ["import", "receipt.txt", "sitecustomize.reference.so"],
        )

        mapped = []
        for line in Path("/proc/self/maps").read_text(encoding="ascii").splitlines():
            fields = line.split(maxsplit=5)
            if len(fields) == 6 and fields[5] == str(artifact):
                major, minor = (int(part, 16) for part in fields[3].split(":"))
                mapped.append((major, minor, int(fields[4])))
        self.assertIn(
            (os.major(artifact_stat.st_dev), os.minor(artifact_stat.st_dev), artifact_stat.st_ino),
            mapped,
        )

        for key, wrong_value, expected_error in (
            (
                "R11A_NATIVE_ARTIFACT_INO",
                str(artifact_stat.st_ino + 1),
                "loaded artifact differs from receipted identity",
            ),
            (
                "R11A_NATIVE_BOUNDARY_BINARY",
                str(boundary_root / "sitecustomize.reference.so"),
                "loaded artifact is not the authenticated path",
            ),
        ):
            with self.subTest(loaded_artifact_binding=key):
                environment = self.child_environment(inherit_boundary=True)
                environment[key] = wrong_value
                completed = subprocess.run(
                    [sys.executable, "-c", "raise AssertionError('boundary did not fail closed')"],
                    cwd=ROOT,
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=30,
                )
                self.assertEqual(completed.returncode, 78, completed.stderr.decode(errors="replace"))
                self.assertIn(expected_error, completed.stderr.decode(errors="replace"))

        completed = subprocess.run(
            [str(BOUNDARY_BUILDER), "verify", os.environ["R11A_NATIVE_ENV_FILE"]],
            cwd=ROOT,
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=300,
        )
        self.assertEqual(
            completed.returncode,
            0,
            completed.stdout.decode(errors="replace") + completed.stderr.decode(errors="replace"),
        )

        if os.environ.get(_NESTED):
            return
        with tempfile.TemporaryDirectory(prefix="r11a-boundary-provenance-") as directory:
            temporary = Path(directory)
            fixture = temporary / "repository"
            clone = subprocess.run(
                ["git", "clone", "-q", "--no-hardlinks", str(ROOT), str(fixture)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(clone.returncode, 0, clone.stderr.decode(errors="replace"))
            fixture_builder = fixture / BOUNDARY_BUILDER.relative_to(ROOT)
            builder_text = fixture_builder.read_text(encoding="utf-8")
            build_hook = '    local output="$build_root/$ARTIFACT_NAME"\n\n'
            self.assertEqual(builder_text.count(build_hook), 1)
            fixture_builder.write_text(
                builder_text.replace(
                    build_hook,
                    build_hook
                    + "    if [[ ${R11A_NATIVE_TEST_VERIFY_BUILD_FAILURE-} = 1 "
                    + '&& "$build_root" = */verify ]]; then\n'
                    + "        printf '%s\\n' "
                    + "'R11A native boundary injected verify build failure' >&2\n"
                    + "        return 97\n"
                    + "    fi\n\n",
                    1,
                ),
                encoding="utf-8",
            )
            self.commit_fixture(fixture, "test: inject verify build failure hook")
            base_environment = self.child_environment(inherit_boundary=False)
            base_environment.pop(_NESTED, None)

            first_env_file = temporary / "first.env"
            self.run_boundary_helper(fixture, "prepare", first_env_file, base_environment)
            first_values = _read_environment(first_env_file)
            first_environment = {**base_environment, **first_values}
            self.run_boundary_helper(fixture, "verify", first_env_file, first_environment)
            first_artifact = Path(first_values["R11A_NATIVE_BOUNDARY_BINARY"])
            first_import_root = Path(first_values["R11A_NATIVE_IMPORT_ROOT"])
            first_bytes = first_artifact.read_bytes()
            self.run_boundary_helper(
                fixture,
                "verify",
                first_env_file,
                {
                    **first_environment,
                    "R11A_NATIVE_TEST_VERIFY_BUILD_FAILURE": "1",
                },
                expected_returncode=1,
                expected_output=(
                    "R11A native boundary injected verify build failure"
                ),
            )
            first_boundary_root = Path(first_values["R11A_NATIVE_BOUNDARY_ROOT"])
            for transient in ("verify", "verify-home", "verify-tmp"):
                self.assertFalse((first_boundary_root / transient).exists())

            second_env_file = temporary / "second.env"
            self.run_boundary_helper(fixture, "prepare", second_env_file, base_environment)
            second_values = _read_environment(second_env_file)
            second_environment = {**base_environment, **second_values}
            self.run_boundary_helper(fixture, "verify", second_env_file, second_environment)
            second_artifact = Path(second_values["R11A_NATIVE_BOUNDARY_BINARY"])
            self.assertEqual(first_bytes, second_artifact.read_bytes())
            self.run_boundary_helper(fixture, "cleanup", second_env_file, second_environment)

            source = fixture / BOUNDARY_SOURCE.relative_to(ROOT)
            source_bytes = source.read_bytes()
            source.write_bytes(source_bytes + b"\n/* unreviewed source */\n")
            self.run_boundary_helper(
                fixture,
                "verify",
                first_env_file,
                first_environment,
                expected_returncode=1,
                expected_output="worktree differs from index",
            )
            source.write_bytes(source_bytes)

            artifact_bytes = first_artifact.read_bytes()
            first_artifact.chmod(0o700)
            first_artifact.write_bytes(artifact_bytes[:-1] + bytes([artifact_bytes[-1] ^ 1]))
            first_artifact.chmod(0o500)
            diagnostic = self.run_boundary_helper(
                fixture,
                "verify",
                first_env_file,
                first_environment,
                expected_returncode=1,
                expected_output="R11A native boundary full-file mismatch: sealed reference versus promoted artifact",
            )
            diagnostic_output = diagnostic.stdout + diagnostic.stderr
            self.assertIn(b"expected_sha256=", diagnostic_output)
            self.assertIn(b"observed_sha256=", diagnostic_output)
            self.assertIn(b"--- expected:", diagnostic_output)
            self.assertIn(b"--- observed:", diagnostic_output)
            self.assertIn(b"ELF Header:", diagnostic_output)
            self.assertIn(b"Sections:", diagnostic_output)
            first_artifact.chmod(0o700)
            first_artifact.write_bytes(artifact_bytes)
            first_artifact.chmod(0o500)

            substitute = Path("/bin/true").read_bytes()
            for extra_name, is_directory in (
                ("sitecustomize.cpython-312-x86_64-linux-gnu.so", False),
                ("sitecustomize.py", False),
                ("sitecustomize", True),
                ("unrelated", False),
            ):
                with self.subTest(unreceipted_import_entry=extra_name):
                    extra = first_import_root / extra_name
                    first_import_root.chmod(0o700)
                    if is_directory:
                        extra.mkdir(mode=0o500)
                    else:
                        extra.write_bytes(substitute)
                        extra.chmod(0o500)
                    first_import_root.chmod(0o500)
                    self.run_boundary_helper(
                        fixture,
                        "verify",
                        first_env_file,
                        first_environment,
                        expected_returncode=1,
                        expected_output="import root inventory is not exact",
                    )
                    first_import_root.chmod(0o700)
                    if is_directory:
                        extra.rmdir()
                    else:
                        extra.unlink()
                    first_import_root.chmod(0o500)

            first_artifact.chmod(0o700)
            first_artifact.write_bytes(substitute)
            first_artifact.chmod(0o500)
            self.run_boundary_helper(
                fixture,
                "verify",
                first_env_file,
                first_environment,
                expected_returncode=1,
                expected_output="R11A native boundary full-file mismatch: sealed reference versus promoted artifact",
            )
            first_artifact.chmod(0o700)
            first_artifact.write_bytes(artifact_bytes)
            first_artifact.chmod(0o500)

            hardlink = first_artifact.with_name("unapproved-hardlink.so")
            first_artifact.parent.chmod(0o700)
            os.link(first_artifact, hardlink)
            first_artifact.parent.chmod(0o500)
            self.run_boundary_helper(
                fixture,
                "verify",
                first_env_file,
                first_environment,
                expected_returncode=1,
                expected_output="unsafe hard-link count",
            )
            first_artifact.parent.chmod(0o700)
            hardlink.unlink()
            first_artifact.parent.chmod(0o500)

            boundary_root = Path(first_values["R11A_NATIVE_BOUNDARY_ROOT"])
            boundary_root.chmod(0o755)
            self.run_boundary_helper(
                fixture,
                "verify",
                first_env_file,
                first_environment,
                expected_returncode=1,
                expected_output="directory has unsafe mode",
            )
            boundary_root.chmod(0o700)

            symlink_backup = first_artifact.with_name("artifact.backup")
            first_artifact.parent.chmod(0o700)
            first_artifact.rename(symlink_backup)
            first_artifact.symlink_to("/bin/true")
            first_artifact.parent.chmod(0o500)
            self.run_boundary_helper(
                fixture,
                "verify",
                first_env_file,
                first_environment,
                expected_returncode=1,
                expected_output="expected a regular non-symlink file",
            )
            first_artifact.parent.chmod(0o700)
            first_artifact.unlink()
            symlink_backup.rename(first_artifact)
            first_artifact.parent.chmod(0o500)

            override_environment = {**first_environment, "CFLAGS": "-O0"}
            self.run_boundary_helper(
                fixture,
                "verify",
                first_env_file,
                override_environment,
                expected_returncode=1,
                expected_output="unapproved build override is set: CFLAGS",
            )

            receipt = Path(first_values["R11A_NATIVE_BOUNDARY_RECEIPT"])
            receipt_bytes = receipt.read_bytes()
            env_bytes = first_env_file.read_bytes()
            receipt.chmod(0o600)
            receipt.write_bytes(receipt_bytes.replace(b"cc_sha256=", b"cc_sha256=0", 1))
            receipt.chmod(0o400)
            altered_receipt_sha = _sha256(receipt)
            first_env_file.write_bytes(
                env_bytes.replace(
                    first_values["R11A_NATIVE_BOUNDARY_RECEIPT_SHA256"].encode("ascii"),
                    altered_receipt_sha.encode("ascii"),
                )
            )
            first_env_file.chmod(0o600)
            altered_environment = {
                **first_environment,
                "R11A_NATIVE_BOUNDARY_RECEIPT_SHA256": altered_receipt_sha,
            }
            self.run_boundary_helper(
                fixture,
                "verify",
                first_env_file,
                altered_environment,
                expected_returncode=1,
                expected_output="receipt contract mismatch: cc_sha256",
            )
            receipt.chmod(0o600)
            receipt.write_bytes(receipt_bytes)
            receipt.chmod(0o400)
            first_env_file.write_bytes(env_bytes)
            first_env_file.chmod(0o600)

            receipt_values = _read_receipt(receipt)
            bad_build_receipt = receipt_bytes.replace(
                (
                    "build_1_sha256=" + receipt_values["build_1_sha256"]
                ).encode("ascii"),
                b"build_1_sha256=" + (b"0" * 64),
                1,
            )
            self.assertNotEqual(bad_build_receipt, receipt_bytes)
            receipt.chmod(0o600)
            receipt.write_bytes(bad_build_receipt)
            receipt.chmod(0o400)
            bad_build_receipt_sha = _sha256(receipt)
            first_env_file.write_bytes(
                env_bytes.replace(
                    first_values["R11A_NATIVE_BOUNDARY_RECEIPT_SHA256"].encode("ascii"),
                    bad_build_receipt_sha.encode("ascii"),
                )
            )
            first_env_file.chmod(0o600)
            bad_build_environment = {
                **first_environment,
                "R11A_NATIVE_BOUNDARY_RECEIPT_SHA256": bad_build_receipt_sha,
            }
            diagnostic = self.run_boundary_helper(
                fixture,
                "verify",
                first_env_file,
                bad_build_environment,
                expected_returncode=1,
                expected_output="R11A native boundary SHA-256 mismatch: fresh build 1 versus receipt",
            )
            diagnostic_output = diagnostic.stdout + diagnostic.stderr
            self.assertIn(b"expected_sha256=", diagnostic_output)
            self.assertIn(b"observed_sha256=", diagnostic_output)
            self.assertIn(b"--- observed:", diagnostic_output)
            self.assertIn(b"ELF Header:", diagnostic_output)
            for transient in ("verify", "verify-home", "verify-tmp"):
                self.assertFalse((boundary_root / transient).exists())
            receipt.chmod(0o600)
            receipt.write_bytes(receipt_bytes)
            receipt.chmod(0o400)
            first_env_file.write_bytes(env_bytes)
            first_env_file.chmod(0o600)

            first_artifact.parent.chmod(0o700)
            first_artifact.unlink()
            first_artifact.parent.chmod(0o500)
            self.run_boundary_helper(
                fixture,
                "verify",
                first_env_file,
                first_environment,
                expected_returncode=1,
                expected_output="expected a regular non-symlink file",
            )
            first_artifact.parent.chmod(0o700)
            first_artifact.write_bytes(artifact_bytes)
            first_artifact.chmod(0o500)
            first_artifact.parent.chmod(0o500)
            self.run_boundary_helper(fixture, "cleanup", first_env_file, first_environment)
            self.assertFalse(boundary_root.exists())
            self.assertFalse(first_env_file.exists())

            partial_runner = temporary / "partial-runner"
            partial_runner.mkdir(mode=0o700)
            partial_env_file = partial_runner / "boundary.env"
            source.write_bytes(
                source_bytes
                + b"\nthis_is_intentionally_invalid_c_for_partial_prepare_testing\n"
            )
            self.commit_fixture(fixture, "test: inject partial native prepare failure")
            self.run_boundary_helper(
                fixture,
                "prepare",
                partial_env_file,
                {**base_environment, "RUNNER_TEMP": str(partial_runner)},
                expected_returncode=1,
                expected_output=(
                    "this_is_intentionally_invalid_c_for_partial_prepare_testing"
                ),
            )
            self.assertFalse(partial_env_file.exists())
            self.assertEqual(list(partial_runner.iterdir()), [])

    def test_focused_literal_normal_optimized_and_bytecode_disabled(self) -> None:
        if os.environ.get(_NESTED):
            return
        modules = (
            "tests.test_archive_inventory_r11a_g2_owner_approval",
            "tests.test_archive_inventory_r11a_post_approval_validator_alignment",
        )
        for module in modules:
            for flags in self.subprocess_flags():
                with self.subTest(module=module, flags=flags):
                    self.run_python((*flags, "-m", "unittest", module, "-v"), inherit_boundary=True)

    def test_direct_validator_clis_and_child_imports_use_external_boundary(self) -> None:
        if os.environ.get(_NESTED):
            return
        for script in (
            "governance/validate_r11a_g2_owner_approval.py",
            "governance/validate_r11a_post_approval_validator_alignment.py",
            "governance/validate_r11a_v2_bindings.py",
            "governance/validate_r11a_v2_preregistration.py",
            "governance/validate_repository.py",
        ):
            for flags in self.subprocess_flags():
                with self.subTest(script=script, flags=flags):
                    self.run_python((*flags, script), inherit_boundary=True)
        for flags in self.subprocess_flags():
            self.run_python(
                (*flags, "governance/seal_r11a_corrective_r7.py", "--check"),
                inherit_boundary=True,
            )
            self.run_python(
                (*flags, "governance/regenerate_manifest.py", "--check"),
                inherit_boundary=True,
            )

        closed_gate_cases = (
            (
                "governance/validate_r11a_approval_r4.py",
                0,
                "OWNER_APPROVAL_VALID_POST_G2_NO_CURRENT_RUNTIME",
            ),
            (
                "governance/validate_r11a_activation_r4.py",
                1,
                "successor role creation/configuration candidate is absent",
            ),
            (
                "governance/validate_r11a_execution_release_r4.py",
                1,
                "successor role creation/configuration candidate is absent",
            ),
            (
                "governance/validate_r11a_role_attestation_r4.py",
                1,
                "successor role creation/configuration candidate is absent",
            ),
            (
                "governance/validate_r11a_role_configuration_candidate_r4.py",
                1,
                "successor role creation/configuration candidate is absent",
            ),
            (
                "governance/validate_r11a_role_preflight_evidence_r4.py",
                1,
                "successor role creation/configuration candidate is absent",
            ),
            (
                "governance/validate_r11a_workflow_installation_r4.py",
                1,
                "successor role creation/configuration candidate is absent",
            ),
            (
                "governance/validate_r11a_runtime_binding_r7.py",
                2,
                "--expected-commit",
            ),
            (
                "governance/validate_r11a_execution_artifact_r7.py",
                2,
                "artifact",
            ),
        )
        for script, returncode, output in closed_gate_cases:
            for flags in self.subprocess_flags():
                with self.subTest(closed_gate_script=script, flags=flags):
                    self.run_python(
                        (*flags, script),
                        inherit_boundary=True,
                        expected_returncode=returncode,
                        expected_output=output,
                    )

        for flags in self.subprocess_flags():
            with self.subTest(network_deny_flags=flags):
                self.run_python(
                    (*flags, "governance/run_r11a_network_deny.py", "tests.test_ci_exact_head"),
                    inherit_boundary=True,
                )

        child = (
            "import difflib, os, pathlib, sitecustomize, sys, sysconfig; "
            "assert pathlib.Path(sitecustomize.__file__).resolve() == pathlib.Path(os.environ['R11A_NATIVE_BOUNDARY_BINARY']); "
            "assert pathlib.Path(difflib.__file__).resolve() == pathlib.Path(sysconfig.get_path('stdlib'))/'difflib.py'; "
            "assert sys.pycache_prefix == os.environ['R11A_PYCACHE_BOUNDARY_ACTIVE']; "
            "assert not pathlib.Path(sys.pycache_prefix).is_relative_to(pathlib.Path.cwd()); "
            "import governance.r11a_repository_provenance as p; "
            "s=p.authenticate_repository(pathlib.Path.cwd()); assert s.head"
        )
        for flags in self.subprocess_flags():
            with self.subTest(child_flags=flags):
                self.run_python((*flags, "-c", child), inherit_boundary=True)

        failure_child = (
            "import os, pathlib, sys; "
            "root=pathlib.Path(sys.pycache_prefix); print(root, flush=True); "
            "assert root == pathlib.Path(os.environ['R11A_PYCACHE_BOUNDARY_ACTIVE']); "
            "raise SystemExit(19)"
        )
        failed = self.run_python(
            ("-c", failure_child),
            inherit_boundary=True,
            expected_returncode=19,
        )
        failed_root = Path(failed.stdout.decode("ascii").strip())
        self.assertFalse(failed_root.exists())

    def test_preexisting_cache_material_is_preserved_and_rejected_at_startup(self) -> None:
        if os.environ.get(_NESTED):
            return
        for case in ("regular-cache-name", "cache-directory-and-pyc"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                fixture = Path(directory) / "repository"
                clone = subprocess.run(
                    ["git", "clone", "-q", "--no-hardlinks", str(ROOT), str(fixture)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(clone.returncode, 0, clone.stderr.decode(errors="replace"))
                cache = fixture / "research/archive_inventory/r11a_alignment/__pycache__"
                if case == "regular-cache-name":
                    cache.write_bytes(b"preexisting material\n")
                    expected = {cache: b"preexisting material\n"}
                else:
                    cache.mkdir()
                    pyc = cache / "synthetic.cpython-312.pyc"
                    pyc.write_bytes(b"synthetic preexisting bytecode\n")
                    expected = {pyc: b"synthetic preexisting bytecode\n"}
                completed = subprocess.run(
                    [sys.executable, "governance/validate_r11a_g2_owner_approval.py"],
                    cwd=fixture,
                    env=self.child_environment(inherit_boundary=False),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=300,
                )
                self.assertNotEqual(completed.returncode, 0)
                for path, raw in expected.items():
                    self.assertEqual(path.read_bytes(), raw)

    def test_import_order_permutations_are_bytecode_order_invariant(self) -> None:
        if os.environ.get(_NESTED):
            return
        orders = (
            (
                "governance.validate_r11a_g2_owner_approval",
                "governance.r11a_post_approval_context",
                "governance.r11a_repository_provenance",
                "governance.validate_r11a_runtime_binding_r7",
            ),
            (
                "governance.r11a_repository_provenance",
                "governance.validate_r11a_g2_owner_approval",
                "governance.r11a_post_approval_context",
                "governance.validate_r11a_runtime_binding_r7",
            ),
            (
                "governance.validate_r11a_runtime_binding_r7",
                "governance.r11a_post_approval_context",
                "governance.validate_r11a_g2_owner_approval",
                "governance.r11a_repository_provenance",
            ),
            (
                "tests.test_archive_inventory_r11a_g1_owner_approval_readiness",
                "tests.test_archive_inventory_r11a_implementation",
                "governance.validate_r11a_g2_owner_approval",
                "governance.r11a_post_approval_context",
                "governance.r11a_repository_provenance",
            ),
            (
                "governance.validate_r11a_execution_artifact_r7",
                "governance.r11a_repository_provenance",
                "governance.r11a_post_approval_context",
                "governance.validate_r11a_g2_owner_approval",
            ),
        )
        for order in orders:
            source = (
                "import os, pathlib, subprocess, sys; "
                "assert sys.pycache_prefix == os.environ['R11A_PYCACHE_BOUNDARY_ACTIVE']; "
                + "; ".join(f"__import__({name!r})" for name in order)
                + "; import governance.validate_r11a_g2_owner_approval as g2"
                "; import governance.r11a_post_approval_context as alignment"
                "; import governance.validate_r11a_runtime_binding_r7 as runtime"
                "; root=pathlib.Path.cwd(); g2.validate(root); alignment.validate_alignment(root)"
                "; head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()"
                "; failed=False"
                ";\ntry: runtime.validate(head,1,root=root)\n"
                "except runtime.RuntimeBindingError as exc:\n"
                " failed='successor role creation/configuration candidate is absent' in str(exc)\n"
                "assert failed\n"
            )
            for flags in self.subprocess_flags():
                with self.subTest(order=order, flags=flags):
                    self.run_python((*flags, "-c", source), inherit_boundary=True)

    def test_discovery_entrypoints_activate_boundary_without_recursing(self) -> None:
        if os.environ.get(_NESTED):
            return
        for flags in self.subprocess_flags():
            self.run_python(
                (
                    *flags,
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "tests",
                    "-p",
                    "test_ci_exact_head.py",
                    "-v",
                ),
                inherit_boundary=True,
            )


if __name__ == "__main__":
    unittest.main()
