from __future__ import annotations

import difflib
import hashlib
import os
import shutil
import stat
import subprocess
import sys
import sysconfig
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).absolute().parents[1]
BOUNDARY_BINARY = ROOT / "difflib.abi3.so"
BOUNDARY_SOURCE = ROOT / "governance/r11a_bytecode_boundary.c"
_NESTED = "R11A_IMPORT_ISOLATION_NESTED"


class R11AImportIsolationTests(unittest.TestCase):
    maxDiff = None

    def child_environment(self, *, inherit_boundary: bool) -> dict[str, str]:
        environment = os.environ.copy()
        boundary = environment.get("R11A_PYCACHE_BOUNDARY_ACTIVE")
        for key in (
            "PYTHONDONTWRITEBYTECODE",
            "PYTHONPYCACHEPREFIX",
            "R11A_PYCACHE_BOUNDARY_ACTIVE",
        ):
            environment.pop(key, None)
        if not inherit_boundary and boundary:
            retained = [
                item
                for item in environment.get("PYTHONPATH", "").split(os.pathsep)
                if item and Path(item) != Path(boundary)
            ]
            if retained:
                environment["PYTHONPATH"] = os.pathsep.join(retained)
            else:
                environment.pop("PYTHONPATH", None)
        environment[_NESTED] = "1"
        return environment

    def run_python(
        self,
        arguments: tuple[str, ...],
        *,
        inherit_boundary: bool = False,
        expected_returncode: int | None = 0,
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
        if expected_returncode is not None:
            self.assertEqual(
                completed.returncode,
                expected_returncode,
                completed.stdout.decode("utf-8", errors="replace")[-4000:]
                + completed.stderr.decode("utf-8", errors="replace")[-12000:],
            )
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

    def test_native_boundary_is_first_and_reproducible(self) -> None:
        self.assertEqual(Path(difflib.__file__).absolute(), BOUNDARY_BINARY)
        self.assertEqual(difflib.SequenceMatcher(None, "abc", "abc").ratio(), 1.0)
        prefix = Path(sys.pycache_prefix or "")
        self.assertTrue(prefix.is_absolute())
        self.assertFalse(prefix.is_relative_to(ROOT))
        self.assertEqual(stat.S_IMODE(prefix.stat().st_mode), 0o700)
        self.assertEqual(os.environ.get("R11A_PYCACHE_BOUNDARY_ACTIVE"), str(prefix))
        self.assertEqual(os.environ.get("PYTHONPYCACHEPREFIX"), str(prefix))

        compiler = shutil.which("cc")
        self.assertIsNotNone(compiler)
        include = sysconfig.get_path("include")
        self.assertIsInstance(include, str)
        with tempfile.TemporaryDirectory() as directory:
            rebuilt = Path(directory) / "difflib.abi3.so"
            completed = subprocess.run(
                [
                    str(compiler),
                    "-std=c11",
                    "-O2",
                    "-fPIC",
                    "-fno-ident",
                    "-Werror",
                    "-DPy_LIMITED_API=0x03080000",
                    f"-I{include}",
                    "-shared",
                    "-Wl,--build-id=none",
                    "-o",
                    str(rebuilt),
                    str(BOUNDARY_SOURCE),
                ],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(
                completed.returncode,
                0,
                completed.stderr.decode("utf-8", errors="replace"),
            )
            self.assertEqual(rebuilt.read_bytes(), BOUNDARY_BINARY.read_bytes())
        self.assertEqual(
            hashlib.sha256(BOUNDARY_BINARY.read_bytes()).hexdigest(),
            "b13ccd113a79d099cfbb60a3f59bf092872b217b8df3e4061e7aad967590ee83",
        )

    def test_focused_literal_normal_optimized_and_bytecode_disabled(self) -> None:
        if os.environ.get(_NESTED) or sys.dont_write_bytecode:
            return
        modules = (
            "tests.test_archive_inventory_r11a_g2_owner_approval",
            "tests.test_archive_inventory_r11a_post_approval_validator_alignment",
        )
        for module in modules:
            for flags in ((), ("-O",), ("-B",), ("-B", "-O")):
                with self.subTest(module=module, flags=flags):
                    self.run_python((*flags, "-m", "unittest", module, "-v"))

    def test_direct_validator_clis_and_child_imports_use_external_boundary(self) -> None:
        if os.environ.get(_NESTED) or sys.dont_write_bytecode:
            return
        for script in (
            "governance/validate_r11a_g2_owner_approval.py",
            "governance/validate_r11a_post_approval_validator_alignment.py",
        ):
            for flags in ((), ("-O",)):
                with self.subTest(script=script, flags=flags):
                    self.run_python((*flags, script))

        for script in (
            "governance/validate_r11a_activation_r4.py",
            "governance/validate_r11a_approval_r4.py",
            "governance/validate_r11a_execution_release_r4.py",
            "governance/validate_r11a_role_attestation_r4.py",
            "governance/validate_r11a_role_configuration_candidate_r4.py",
            "governance/validate_r11a_role_preflight_evidence_r4.py",
            "governance/validate_r11a_workflow_installation_r4.py",
            "governance/validate_r11a_runtime_binding_r7.py",
            "governance/validate_r11a_execution_artifact_r7.py",
        ):
            for flags in ((), ("-O",)):
                with self.subTest(future_script=script, flags=flags):
                    self.run_python(
                        (*flags, script),
                        expected_returncode=None,
                    )
        for flags in ((), ("-O",)):
            with self.subTest(network_deny_flags=flags):
                self.run_python(
                    (
                        *flags,
                        "governance/run_r11a_network_deny.py",
                        "tests.test_ci_exact_head",
                    )
                )

        child = (
            "import os, pathlib, sys; "
            "assert sys.pycache_prefix == os.environ['R11A_PYCACHE_BOUNDARY_ACTIVE']; "
            "import governance.r11a_repository_provenance as p; "
            "r=pathlib.Path.cwd(); s=p.authenticate_repository(r); "
            "assert s.head and pathlib.Path(sys.pycache_prefix).is_dir(); "
            "assert not pathlib.Path(sys.pycache_prefix).is_relative_to(r); "
            "assert os.environ['R11A_PYCACHE_BOUNDARY_ACTIVE']==sys.pycache_prefix"
        )
        for flags in ((), ("-O",), ("-B",)):
            with self.subTest(child_flags=flags):
                self.run_python(
                    (*flags, "-c", child),
                    inherit_boundary=True,
                )

    def test_preexisting_cache_material_is_preserved_and_rejected_at_startup(self) -> None:
        if os.environ.get(_NESTED) or sys.dont_write_bytecode:
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
                self.assertEqual(
                    clone.returncode,
                    0,
                    clone.stderr.decode("utf-8", errors="replace"),
                )
                cache = (
                    fixture
                    / "research/archive_inventory/r11a_alignment/__pycache__"
                )
                if case == "regular-cache-name":
                    cache.write_bytes(b"preexisting material\n")
                    expected = {cache: b"preexisting material\n"}
                else:
                    cache.mkdir()
                    pyc = cache / "synthetic.cpython-312.pyc"
                    pyc.write_bytes(b"synthetic preexisting bytecode\n")
                    expected = {pyc: b"synthetic preexisting bytecode\n"}
                completed = subprocess.run(
                    [
                        sys.executable,
                        "governance/validate_r11a_g2_owner_approval.py",
                    ],
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
        if os.environ.get(_NESTED) or sys.dont_write_bytecode:
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
            for flags in ((), ("-O",), ("-B",)):
                with self.subTest(order=order, flags=flags):
                    self.run_python(
                        (*flags, "-c", source),
                        inherit_boundary=True,
                    )

    def test_full_discovery_literal_normal_and_bytecode_disabled_subprocesses(self) -> None:
        if os.environ.get(_NESTED) or sys.dont_write_bytecode:
            return
        self.run_python(("-m", "unittest", "discover", "-s", "tests", "-v"), timeout=1800)
        self.run_python(("-B", "-m", "unittest", "discover", "-s", "tests", "-v"), timeout=1800)


if __name__ == "__main__":
    unittest.main()
