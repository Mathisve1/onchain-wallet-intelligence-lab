from __future__ import annotations

import hashlib
import importlib.util
import json
import marshal
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

from governance import r11a_repository_provenance as provenance
from governance.r11a_repository_provenance import (
    RepositoryProvenanceError,
    authenticated_repository_copy,
    authenticate_repository,
    materialize_snapshot,
)


class R11ARepositoryProvenanceTests(unittest.TestCase):
    def git(
        self,
        root: Path,
        *arguments: str,
        input_data: bytes | None = None,
    ) -> bytes:
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("GIT_")
        }
        environment.update(
            {
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_SYSTEM": os.devnull,
                "LC_ALL": "C",
            }
        )
        completed = subprocess.run(
            ["git", *arguments],
            cwd=root,
            env=environment,
            input=input_data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            completed.stderr.decode("utf-8", errors="replace"),
        )
        return completed.stdout

    def regenerate_manifest(self, root: Path) -> None:
        manifest = root / provenance.MANIFEST_PATH
        manifest.parent.mkdir(parents=True, exist_ok=True)
        rows: list[bytes] = []
        for path in sorted(
            (
                path
                for path in root.rglob("*")
                if path.is_file()
                and ".git" not in path.relative_to(root).parts
                and path != manifest
            ),
            key=lambda path: path.relative_to(root).as_posix().encode("utf-8"),
        ):
            relative = path.relative_to(root).as_posix()
            rows.append(
                hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii")
                + b"  "
                + relative.encode("utf-8")
                + b"\n"
            )
        manifest.write_bytes(b"".join(rows))

    def make_repository(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name) / "repository"
        root.mkdir()
        self.git(root, "init", "-q")
        self.git(root, "config", "user.name", "R11A Offline Test")
        self.git(root, "config", "user.email", "r11a-offline@example.invalid")
        (root / "README.md").write_text("authenticated snapshot\n", encoding="utf-8")
        package = root / "pkg"
        package.mkdir()
        (package / "__init__.py").write_text("\n", encoding="utf-8")
        (package / "module.py").write_text("VALUE = 7\n", encoding="utf-8")
        self.regenerate_manifest(root)
        self.git(root, "add", "--all")
        self.git(root, "commit", "-q", "-m", "fixture")
        return temporary, root

    def assert_provenance_failure(self, root: Path, pattern: str = ".*") -> None:
        with self.assertRaisesRegex(RepositoryProvenanceError, pattern):
            authenticate_repository(root)

    def hardening_environment(
        self,
        root: Path,
        snapshot: provenance.AuthenticatedRepositorySnapshot,
    ) -> dict[str, str]:
        return {
            "GITHUB_ACTIONS": "true",
            "GITHUB_REPOSITORY": "Mathisve1/onchain-wallet-intelligence-lab",
            "CURRENT_REPOSITORY": "Mathisve1/onchain-wallet-intelligence-lab",
            "GITHUB_WORKFLOW": (
                "Hyperliquid Archive R11A Identity Boundary Diagnostic"
            ),
            "GITHUB_WORKFLOW_REF": (
                "Mathisve1/onchain-wallet-intelligence-lab/.github/workflows/"
                "hyperliquid-archive-r11a-identity-boundary-diagnostic.yml"
                "@refs/heads/main"
            ),
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_SHA": snapshot.head,
            "DISPATCH_SHA": snapshot.head,
            "GITHUB_RUN_ATTEMPT": "1",
            "CURRENT_RUN_ATTEMPT": "1",
            "GITHUB_RUN_ID": "123456789",
            "CURRENT_RUN_ID": "123456789",
            "GITHUB_WORKSPACE": str(root),
        }

    def test_canonical_repository_authenticates_and_materializes_exact_blobs(self) -> None:
        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        snapshot = authenticate_repository(root)
        self.assertRegex(snapshot.head, r"^[0-9a-f]{40}$")
        self.assertRegex(snapshot.tree, r"^[0-9a-f]{40}$")
        self.assertIn(snapshot.index_version, {2, 3, 4})

        destination = Path(temporary.name) / "materialized"
        materialize_snapshot(snapshot, destination)
        self.assertFalse((destination / ".git").exists())
        for entry in snapshot.entries:
            self.assertEqual((destination / entry.path).read_bytes(), entry.raw)
        self.assertEqual(
            sorted(
                path.relative_to(destination).as_posix()
                for path in destination.rglob("*")
                if path.is_file()
            ),
            sorted(entry.path for entry in snapshot.entries),
        )

        copied_temporary, copied = authenticated_repository_copy(
            root,
            expected_head=snapshot.head,
            expected_tree=snapshot.tree,
        )
        self.addCleanup(copied_temporary.cleanup)
        self.assertEqual((copied / "README.md").read_bytes(), b"authenticated snapshot\n")
        self.assertFalse((copied / ".git").exists())

    def test_supported_index_versions_use_canonical_git_parser(self) -> None:
        for version in (2, 4):
            with self.subTest(version=version):
                temporary, root = self.make_repository()
                self.addCleanup(temporary.cleanup)
                self.git(root, "update-index", f"--index-version={version}")
                snapshot = authenticate_repository(root)
                self.assertEqual(snapshot.index_version, version)

        # Version 3 uses the same entry encoding as v2 when no extended bits
        # are set.  Git normally writes the minimal v2 form, so construct the
        # canonical v3 header and checksum directly and let Git parse it.
        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        index = root / ".git/index"
        raw = bytearray(index.read_bytes())
        raw[4:8] = (3).to_bytes(4, "big")
        raw[-20:] = hashlib.sha1(raw[:-20]).digest()
        index.write_bytes(raw)
        self.assertEqual(authenticate_repository(root).index_version, 3)

        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        index = root / ".git/index"
        raw = bytearray(index.read_bytes())
        raw[4:8] = (5).to_bytes(4, "big")
        raw[-20:] = hashlib.sha1(raw[:-20]).digest()
        index.write_bytes(raw)
        self.assert_provenance_failure(root, "unsupported Git index version")

    def test_git_root_and_metadata_indirection_fail_closed(self) -> None:
        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        root_link = Path(temporary.name) / "root-link"
        root_link.symlink_to(root, target_is_directory=True)
        self.assert_provenance_failure(root_link, "root path component is symlink")

        git_directory = root / ".git"
        external = Path(temporary.name) / "external-git"
        git_directory.rename(external)
        git_directory.symlink_to(external, target_is_directory=True)
        self.assert_provenance_failure(root, "physical .git directory is symlink")
        git_directory.unlink()
        external.rename(git_directory)

        external = Path(temporary.name) / "gitfile-target"
        git_directory.rename(external)
        git_directory.write_text(f"gitdir: {external}\n", encoding="utf-8")
        self.assert_provenance_failure(root, "gitfile indirection")

    def test_index_flags_unknown_mandatory_extension_and_malformed_bytes_fail(self) -> None:
        for arguments, pattern in (
            (("update-index", "--skip-worktree", "README.md"), "prohibited index state"),
            (("update-index", "--assume-unchanged", "README.md"), "prohibited index state"),
        ):
            with self.subTest(arguments=arguments):
                temporary, root = self.make_repository()
                self.addCleanup(temporary.cleanup)
                self.git(root, *arguments)
                self.assert_provenance_failure(root, pattern)

        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        candidate = root / "intent.txt"
        candidate.write_text("intent\n", encoding="utf-8")
        self.git(root, "add", "--intent-to-add", "intent.txt")
        self.assert_provenance_failure(
            root,
            "unsupported Git index flags|invalid/zero Git index OID|differs from exact HEAD",
        )

        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        index = root / ".git/index"
        raw = index.read_bytes()
        body = raw[:-20] + b"zzzz" + (0).to_bytes(4, "big")
        index.write_bytes(body + hashlib.sha1(body).digest())
        self.assert_provenance_failure(root, "Git plumbing failed")

        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        index = root / ".git/index"
        index.write_bytes(index.read_bytes()[:20])
        self.assert_provenance_failure(root, "malformed Git index|checksum")

    def test_index_oid_worktree_and_tracked_presence_are_exact(self) -> None:
        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        alternate_oid = self.git(
            root,
            "hash-object",
            "-w",
            "--stdin",
            input_data=b"alternate\n",
        ).strip().decode("ascii")
        self.git(root, "update-index", "--cacheinfo", f"100644,{alternate_oid},README.md")
        self.assert_provenance_failure(root, "index differs from exact HEAD tree")

        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        (root / "README.md").write_text("working tree drift\n", encoding="utf-8")
        self.assert_provenance_failure(root, "working-tree byte drift")

        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        (root / "README.md").unlink()
        self.assert_provenance_failure(root, "tracked worktree path absent")

    def test_commit_and_blob_object_content_is_rehashed(self) -> None:
        for object_expression, object_type in (
            ("HEAD", b"commit"),
            ("HEAD:README.md", b"blob"),
        ):
            with self.subTest(object_expression=object_expression):
                temporary, root = self.make_repository()
                self.addCleanup(temporary.cleanup)
                oid = self.git(
                    root,
                    "rev-parse",
                    "--verify",
                    object_expression,
                ).strip().decode("ascii")
                canonical = self.git(root, "cat-file", object_type.decode("ascii"), oid)
                forged = canonical + b"forged-object-byte\n"
                loose_object = root / ".git/objects" / oid[:2] / oid[2:]
                loose_object.chmod(0o600)
                loose_object.write_bytes(
                    zlib.compress(
                        object_type
                        + b" "
                        + str(len(forged)).encode("ascii")
                        + b"\0"
                        + forged
                    )
                )
                self.assert_provenance_failure(
                    root,
                    "Git object hash mismatch|Git plumbing failed",
                )

    def test_manifest_digest_coverage_order_and_self_exclusion_are_exact(self) -> None:
        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        manifest = root / provenance.MANIFEST_PATH
        rows = manifest.read_bytes().splitlines(keepends=True)
        manifest.write_bytes(b"".join(reversed(rows)))
        self.git(root, "add", provenance.MANIFEST_PATH)
        self.git(root, "commit", "-q", "-m", "unordered manifest")
        self.assert_provenance_failure(root, "UTF-8 byte ordered")

        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        manifest = root / provenance.MANIFEST_PATH
        raw = manifest.read_bytes()
        manifest.write_bytes(b"0" * 64 + raw[64:])
        self.git(root, "add", provenance.MANIFEST_PATH)
        self.git(root, "commit", "-q", "-m", "wrong manifest digest")
        self.assert_provenance_failure(root, "manifest digest drift")

        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        manifest = root / provenance.MANIFEST_PATH
        manifest.write_bytes(
            manifest.read_bytes()
            + b"0" * 64
            + b"  "
            + provenance.MANIFEST_PATH.encode("ascii")
            + b"\n"
        )
        self.git(root, "add", provenance.MANIFEST_PATH)
        self.git(root, "commit", "-q", "-m", "self listed manifest")
        self.assert_provenance_failure(root, "UTF-8 byte ordered|path coverage drift")

    def test_unsafe_paths_and_normalization_collisions_fail_before_materialization(self) -> None:
        unsafe = (
            b"",
            b"../escape",
            b"/absolute",
            b"double//slash",
            b"back\\slash",
            b"dot/./path",
            b"trailing/",
            "space ",
            "e\u0301.txt",
        )
        for value in unsafe:
            with self.subTest(value=repr(value)):
                with self.assertRaises(RepositoryProvenanceError):
                    provenance._validate_relative_path(value)

        collisions: dict[str, str] = {}
        provenance._validate_relative_path("Alpha.txt", collision_map=collisions)
        with self.assertRaisesRegex(RepositoryProvenanceError, "collision"):
            provenance._validate_relative_path("alpha.txt", collision_map=collisions)

    def test_untracked_authority_cache_variants_symlinks_and_hardlinks_fail(self) -> None:
        cases = (
            ("regular-cache-name", "pkg/__pycache__"),
            ("random-pyc", "pkg/__pycache__/synthetic.pyc"),
            ("pyo", "pkg/__pycache__/synthetic.pyo"),
            ("case", "pkg/__PYCACHE__/synthetic.pyc"),
            ("unicode", "pkg/＿＿pycache＿＿/synthetic.pyc"),
            ("space", "pkg/__pycache__ /synthetic.pyc"),
            ("nested", "pkg/__pycache__/nested/synthetic.pyc"),
            ("authority", "research/archive_inventory/r11a_future/AUTHORITY.json"),
        )
        for label, relative in cases:
            with self.subTest(label=label):
                temporary, root = self.make_repository()
                self.addCleanup(temporary.cleanup)
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                if label == "regular-cache-name":
                    path.write_bytes(b"synthetic")
                else:
                    path.write_bytes(b"synthetic")
                self.assert_provenance_failure(root, "untracked|non-canonical|whitespace ambiguity")

        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        cache = root / "pkg/__pycache__"
        cache.symlink_to(root / "pkg", target_is_directory=True)
        self.assert_provenance_failure(root, "symlink")

        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        cache = root / "pkg/__pycache__"
        cache.mkdir()
        os.link(root / "README.md", cache / "synthetic.pyc")
        self.assert_provenance_failure(root, "hard-link")

    def test_real_process_cache_is_rejected_and_bytecode_disabled_import_is_clean(self) -> None:
        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        environment = os.environ.copy()
        environment.pop("PYTHONPYCACHEPREFIX", None)
        environment.pop("PYTHONDONTWRITEBYTECODE", None)
        subprocess.run(
            [sys.executable, "-c", "import pkg.module"],
            cwd=root,
            env=environment,
            check=True,
        )
        cache_directory = root / "pkg/__pycache__"
        self.assertTrue(any(cache_directory.glob("*.pyc")))
        self.assert_provenance_failure(root, "untracked repository file")

        shutil.rmtree(cache_directory)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        subprocess.run(
            [sys.executable, "-B", "-c", "import pkg.module"],
            cwd=root,
            env=environment,
            check=True,
        )
        self.assertFalse(cache_directory.exists())
        snapshot = authenticate_repository(root)
        self.assertRegex(snapshot.head, r"^[0-9a-f]{40}$")

    def test_exact_manufactured_v2_bytecode_is_never_omitted(self) -> None:
        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        governance = root / "governance"
        governance.mkdir(exist_ok=True)
        source = governance / "seal_r11a_v2_preregistration.py"
        source.write_text("VALUE = 11\n", encoding="utf-8")
        self.regenerate_manifest(root)
        self.git(root, "add", "--all")
        self.git(root, "commit", "-q", "-m", "fixture")

        source_raw = source.read_bytes()
        code = compile(
            source_raw,
            str(source),
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        source_information = source.stat()
        exact_synthetic_pyc = (
            importlib.util.MAGIC_NUMBER
            + struct.pack("<I", 0)
            + struct.pack(
                "<II",
                int(source_information.st_mtime) & 0xFFFFFFFF,
                len(source_raw) & 0xFFFFFFFF,
            )
            + marshal.dumps(code)
        )
        cache = Path(importlib.util.cache_from_source(str(source)))
        cache.parent.mkdir()
        cache.write_bytes(exact_synthetic_pyc)
        self.assert_provenance_failure(root, "untracked repository file")
        (cache.parent / "synthetic.pyo").write_bytes(b"synthetic")
        self.assert_provenance_failure(root, "untracked repository file")

    def test_historical_v2_binding_is_immutable_and_live_validator_is_cache_free(self) -> None:
        from governance import seal_r11a_v2_preregistration as seal

        binding_relative = (
            "research/archive_inventory/r11a_v2/"
            "R11A_V2_PREREGISTRATION_BINDINGS.json"
        )
        validator_relative = "governance/validate_r11a_v2_bindings.py"
        historical_validator_sha = (
            "ac68cc6f07a1a0b960ed271b26f642906de1dad96d9ade009b7ba3e4243e3c93"
        )
        repository_root = Path(__file__).resolve().parents[1]
        binding = json.loads(
            (repository_root / binding_relative).read_text(encoding="utf-8")
        )
        self.assertEqual(
            hashlib.sha256((repository_root / binding_relative).read_bytes()).hexdigest(),
            "f60f7d6eac5f5a4633a5453c1c79bd84a54add69d1395d9048658450211bd0ba",
        )
        self.assertEqual(
            binding["file_sha256"][validator_relative],
            historical_validator_sha,
        )
        self.assertEqual(
            seal.HISTORICAL_FILE_SHA256,
            {validator_relative: historical_validator_sha},
        )
        self.assertNotEqual(
            hashlib.sha256((repository_root / validator_relative).read_bytes()).hexdigest(),
            historical_validator_sha,
        )

        with tempfile.TemporaryDirectory() as directory:
            isolated = Path(directory) / "repository"
            paths = {
                *seal.FILES,
                "governance/seal_r11a_v2_preregistration.py",
                binding_relative,
            }
            for relative in paths:
                target = isolated / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(repository_root / relative, target)
            environment = os.environ.copy()
            environment.pop("PYTHONDONTWRITEBYTECODE", None)
            environment.pop("PYTHONPYCACHEPREFIX", None)
            for optimization in ((), ("-O",)):
                completed = subprocess.run(
                    [
                        sys.executable,
                        *optimization,
                        validator_relative,
                    ],
                    cwd=isolated,
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(
                    completed.returncode,
                    0,
                    completed.stderr.decode("utf-8", errors="replace"),
                )
                self.assertFalse(any(isolated.rglob("__pycache__")))
                self.assertFalse(any(isolated.rglob("*.pyc")))
                self.assertFalse(any(isolated.rglob("*.pyo")))

    def test_authenticated_actions_hardening_prevents_uncontrolled_bytecode(self) -> None:
        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        Path(temporary.name).chmod(0o755)
        snapshot = authenticate_repository(root)
        environment = self.hardening_environment(root, snapshot)
        with (
            mock.patch.object(provenance.os, "geteuid", return_value=1000),
            mock.patch.object(provenance.os, "access", return_value=False),
        ):
            hardened = provenance.harden_authenticated_worktree_for_bytecode_free_dispatch(
                snapshot,
                environment=environment,
            )
        self.assertEqual((hardened.head, hardened.tree), (snapshot.head, snapshot.tree))
        for directory in (root, root / "pkg", root / "governance"):
            self.assertEqual(directory.stat().st_mode & 0o222, 0)

        child_environment = os.environ.copy()
        child_environment.pop("PYTHONDONTWRITEBYTECODE", None)
        child_environment.pop("PYTHONPYCACHEPREFIX", None)

        # The production boundary rejects euid 0.  On ordinary CI runners,
        # prove an uncontrolled import cannot create bytecode; this container
        # runs tests as root, so its DAC override would invalidate that probe.
        if not hasattr(os, "geteuid") or os.geteuid() != 0:
            completed = subprocess.run(
                [sys.executable, "-c", "import pkg.module"],
                cwd=root,
                env=child_environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(
                completed.returncode,
                0,
                completed.stderr.decode("utf-8", errors="replace"),
            )
        self.assertFalse((root / "pkg/__pycache__").exists())
        self.assertEqual(authenticate_repository(root).head, snapshot.head)

    def test_hardening_rejects_new_cache_and_wrong_actions_context_before_chmod(self) -> None:
        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        snapshot = authenticate_repository(root)
        environment = self.hardening_environment(root, snapshot)
        cache = root / "pkg/__pycache__"
        cache.mkdir()
        (cache / "synthetic.pyc").write_bytes(b"synthetic")
        with (
            mock.patch.object(provenance.os, "geteuid", return_value=1000),
            self.assertRaisesRegex(RepositoryProvenanceError, "untracked"),
        ):
            provenance.harden_authenticated_worktree_for_bytecode_free_dispatch(
                snapshot,
                environment=environment,
            )
        self.assertNotEqual(root.stat().st_mode & 0o222, 0)

        shutil.rmtree(cache)
        for key, value in (
            ("GITHUB_REPOSITORY", "wrong/repository"),
            ("GITHUB_EVENT_NAME", "pull_request"),
            ("GITHUB_REF", "refs/heads/not-main"),
            ("GITHUB_SHA", "f" * 40),
            ("GITHUB_RUN_ATTEMPT", "2"),
            ("GITHUB_RUN_ID", "not-a-number"),
        ):
            with self.subTest(context_key=key):
                mutated = dict(environment)
                mutated[key] = value
                with (
                    mock.patch.object(provenance.os, "geteuid", return_value=1000),
                    self.assertRaisesRegex(RepositoryProvenanceError, "context drift|run ID"),
                ):
                    provenance.harden_authenticated_worktree_for_bytecode_free_dispatch(
                        snapshot,
                        environment=mutated,
                    )

    def test_materialization_rejects_unsafe_destination(self) -> None:
        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        snapshot = authenticate_repository(root)
        inside = root / "snapshot"
        with self.assertRaisesRegex(RepositoryProvenanceError, "inside source"):
            materialize_snapshot(snapshot, inside)

        existing = Path(temporary.name) / "existing"
        existing.mkdir()
        with self.assertRaisesRegex(RepositoryProvenanceError, "already exists"):
            materialize_snapshot(snapshot, existing)


if __name__ == "__main__":
    unittest.main()
