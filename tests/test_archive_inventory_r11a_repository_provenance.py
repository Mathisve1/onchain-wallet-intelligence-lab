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
    open_authenticated_repository,
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

    def index_extension_offset(self, raw: bytes) -> int:
        self.assertEqual(raw[:4], b"DIRC")
        self.assertEqual(int.from_bytes(raw[4:8], "big"), 2)
        position = 12
        for _ in range(int.from_bytes(raw[8:12], "big")):
            entry_start = position
            fixed_end = entry_start + 62
            nul = raw.index(b"\0", fixed_end, len(raw) - 20)
            consumed = nul + 1 - entry_start
            position = entry_start + ((consumed + 7) // 8) * 8
        return position

    def rebound_index(self, body: bytes | bytearray) -> bytes:
        raw = bytes(body)
        return raw[:-20] + hashlib.sha1(raw[:-20]).digest()

    def write_rebound_index(self, root: Path, body: bytes | bytearray) -> None:
        (root / ".git/index").write_bytes(self.rebound_index(body))

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
        self.assertEqual(snapshot.index_version, 2)

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

    def test_only_fully_implemented_index_v2_is_supported(self) -> None:
        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        self.git(root, "update-index", "--index-version=2")
        self.assertEqual(authenticate_repository(root).index_version, 2)

        for version in (3, 4, 5):
            with self.subTest(version=version):
                temporary, root = self.make_repository()
                self.addCleanup(temporary.cleanup)
                index = root / ".git/index"
                raw = bytearray(index.read_bytes())
                raw[4:8] = version.to_bytes(4, "big")
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
            (("update-index", "--skip-worktree", "README.md"), "unsupported Git index version|prohibited"),
            (("update-index", "--assume-unchanged", "README.md"), "assume-valid|prohibited"),
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
            "unsupported Git index version|unsupported Git index flags|invalid/zero Git index OID|differs from exact HEAD",
        )

        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        index = root / ".git/index"
        raw = index.read_bytes()
        body = raw[:-20] + b"zzzz" + (0).to_bytes(4, "big")
        index.write_bytes(body + hashlib.sha1(body).digest())
        self.assert_provenance_failure(root, "unsupported Git index extension")

        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        index = root / ".git/index"
        index.write_bytes(index.read_bytes()[:20])
        self.assert_provenance_failure(root, "malformed Git index|checksum")

    def test_tree_extension_exact_size_and_payload_mutations_fail_closed(self) -> None:
        mutations = ("size-minus-one", "size-plus-one", "root-byte")
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                temporary, root = self.make_repository()
                self.addCleanup(temporary.cleanup)
                index = root / ".git/index"
                raw = bytearray(index.read_bytes())
                offset = self.index_extension_offset(raw)
                self.assertEqual(raw[offset : offset + 4], b"TREE")
                size = int.from_bytes(raw[offset + 4 : offset + 8], "big")
                if mutation == "size-minus-one":
                    raw[offset + 4 : offset + 8] = (size - 1).to_bytes(4, "big")
                elif mutation == "size-plus-one":
                    raw[offset + 4 : offset + 8] = (size + 1).to_bytes(4, "big")
                else:
                    self.assertEqual(raw[offset + 8], 0)
                    raw[offset + 8] = 0xFF
                self.write_rebound_index(root, raw)
                self.assert_provenance_failure(
                    root,
                    "TREE|extension|UTF-8|truncated|checksum boundary",
                )

    def test_exact_4580_byte_tree_extension_review_reproductions_fail(self) -> None:
        root = b"\0" + b"0 150\n" + b"\x01" * 20
        children = []
        for ordinal in range(150):
            name = f"n{ordinal:03d}".encode("ascii")
            if ordinal == 0:
                name += b"x" * 203
            children.append(name + b"\0" + b"0 0\n" + b"\x02" * 20)
        payload = root + b"".join(children)
        self.assertEqual(len(payload), 4580)
        body = b"DIRC" + (2).to_bytes(4, "big") + (0).to_bytes(4, "big")
        body += b"TREE" + len(payload).to_bytes(4, "big") + payload
        canonical = body + hashlib.sha1(body).digest()
        self.assertIsNotNone(provenance._parse_git_index(canonical).cache_tree)

        for label, mutate in (
            (
                "4580-to-4579",
                lambda raw: raw[:16] + (4579).to_bytes(4, "big") + raw[20:-20],
            ),
            (
                "4580-to-4581",
                lambda raw: raw[:16] + (4581).to_bytes(4, "big") + raw[20:-20],
            ),
            (
                "root-nul-to-ff",
                lambda raw: raw[:20] + b"\xff" + raw[21:-20],
            ),
        ):
            with self.subTest(label=label):
                mutated_body = mutate(canonical)
                mutated = mutated_body + hashlib.sha1(mutated_body).digest()
                with self.assertRaises(RepositoryProvenanceError):
                    provenance._parse_git_index(mutated)

    def test_tree_extension_framing_and_semantics_are_exact(self) -> None:
        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        canonical = (root / ".git/index").read_bytes()
        offset = self.index_extension_offset(canonical)
        self.assertEqual(canonical[offset : offset + 4], b"TREE")
        size = int.from_bytes(canonical[offset + 4 : offset + 8], "big")
        payload = canonical[offset + 8 : offset + 8 + size]

        mutations: dict[str, bytes] = {
            "truncated-payload": payload[:-1],
            "excess-payload": payload + b"\0",
            "malformed-root": b"x" + payload[1:],
            "malformed-entry-count": payload.replace(b"\0", b"\0x", 1),
            "malformed-subtree-count": payload.replace(b" ", b" x", 1),
            "truncated-oid": payload[: payload.index(b"\n") + 10],
        }
        for label, mutated_payload in mutations.items():
            with self.subTest(label=label):
                body = (
                    canonical[:offset]
                    + b"TREE"
                    + len(mutated_payload).to_bytes(4, "big")
                    + mutated_payload
                )
                mutated = body + hashlib.sha1(body).digest()
                with self.assertRaises(RepositoryProvenanceError):
                    provenance._parse_git_index(mutated)

        extension = canonical[offset:-20]
        for label, signature in (
            ("unknown-mandatory", b"link"),
            ("unknown-optional", b"ABCD"),
        ):
            with self.subTest(label=label):
                body = canonical[:-20] + signature + (0).to_bytes(4, "big")
                with self.assertRaisesRegex(
                    RepositoryProvenanceError,
                    "unsupported Git index extension",
                ):
                    provenance._parse_git_index(body + hashlib.sha1(body).digest())

        body = canonical[:-20] + extension
        with self.assertRaisesRegex(RepositoryProvenanceError, "duplicate Git index extension"):
            provenance._parse_git_index(body + hashlib.sha1(body).digest())

        body = canonical[:-20] + b"ABCD" + (2**32 - 1).to_bytes(4, "big")
        with self.assertRaisesRegex(RepositoryProvenanceError, "crosses checksum"):
            provenance._parse_git_index(body + hashlib.sha1(body).digest())

    def test_index_extended_stage_and_entry_framing_fail_closed(self) -> None:
        for label, flag_mask, expected in (
            ("extended", 0x4000, "extended Git index flags"),
            ("conflict-stage", 0x1000, "unmerged Git index stage"),
            ("assume-valid", 0x8000, "assume-valid Git index state"),
        ):
            with self.subTest(label=label):
                temporary, root = self.make_repository()
                self.addCleanup(temporary.cleanup)
                raw = bytearray((root / ".git/index").read_bytes())
                flags = int.from_bytes(raw[72:74], "big") | flag_mask
                raw[72:74] = flags.to_bytes(2, "big")
                self.write_rebound_index(root, raw)
                self.assert_provenance_failure(root, expected)

        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        raw = bytearray((root / ".git/index").read_bytes())
        raw[73] ^= 1
        self.write_rebound_index(root, raw)
        self.assert_provenance_failure(root, "pathname length flag drift")

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
        self.assert_provenance_failure(
            root,
            "index differs from exact HEAD tree|Git TREE entry count",
        )

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

        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        (root / "pkg/__pycache__").mkdir()
        self.assert_provenance_failure(root, "untracked/empty repository directory")

        if hasattr(os, "mkfifo"):
            temporary, root = self.make_repository()
            self.addCleanup(temporary.cleanup)
            cache = root / "pkg/__pycache__"
            cache.mkdir()
            os.mkfifo(cache / "synthetic.pyc")
            self.assert_provenance_failure(root, "special file")

        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        cache = root / "pkg/__pycache__"
        cache.mkdir()
        (cache / "tracked.pyc").write_bytes(b"tracked synthetic cache")
        self.regenerate_manifest(root)
        self.git(root, "add", "--all")
        self.git(root, "commit", "-q", "-m", "tracked cache fixture")
        self.assert_provenance_failure(root, "tracked Python cache/bytecode prohibited")

    def test_real_process_cache_is_rejected_and_bytecode_disabled_import_is_clean(self) -> None:
        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        environment = os.environ.copy()
        boundary = environment.pop("R11A_PYCACHE_BOUNDARY_ACTIVE", None)
        environment.pop("PYTHONPYCACHEPREFIX", None)
        environment.pop("PYTHONDONTWRITEBYTECODE", None)
        if boundary:
            pythonpath = [
                item
                for item in environment.get("PYTHONPATH", "").split(os.pathsep)
                if item and Path(item) != Path(boundary)
            ]
            if pythonpath:
                environment["PYTHONPATH"] = os.pathsep.join(pythonpath)
            else:
                environment.pop("PYTHONPATH", None)
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
        cache = source.parent / "__pycache__/seal_r11a_v2_preregistration.cpython-312.pyc"
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

    def test_post_scan_untracked_and_tracked_mutations_are_rejected(self) -> None:
        for label in ("untracked-authority", "tracked-overwrite"):
            with self.subTest(label=label):
                temporary, root = self.make_repository()
                self.addCleanup(temporary.cleanup)
                mutated = False

                def checkpoint(
                    phase: str,
                    *,
                    source_root: Path,
                    snapshot_root: Path | None = None,
                ) -> None:
                    nonlocal mutated
                    del snapshot_root
                    if phase != "after_worktree_scan" or mutated:
                        return
                    mutated = True
                    if label == "untracked-authority":
                        target = (
                            source_root
                            / "research/archive_inventory/r11a_future/LATE_AUTHORITY.json"
                        )
                        target.parent.mkdir(parents=True)
                        target.write_text("{}\n", encoding="utf-8")
                    else:
                        (source_root / "README.md").write_text(
                            "late tracked overwrite\n",
                            encoding="utf-8",
                        )

                with (
                    mock.patch.object(provenance, "_provenance_checkpoint", checkpoint),
                    self.assertRaisesRegex(
                        RepositoryProvenanceError,
                        "untracked|working-tree byte drift|worktree identity drift",
                    ),
                ):
                    authenticate_repository(root)
                self.assertTrue(mutated)

    def test_snapshot_materialization_never_reads_mutated_source_bytes(self) -> None:
        for phase in (
            "during_snapshot_materialization",
            "after_snapshot_materialization",
            "before_semantic_validation",
        ):
            with self.subTest(phase=phase):
                temporary, root = self.make_repository()
                self.addCleanup(temporary.cleanup)
                mutated = False

                def checkpoint(
                    observed_phase: str,
                    *,
                    source_root: Path,
                    snapshot_root: Path | None = None,
                ) -> None:
                    nonlocal mutated
                    del snapshot_root
                    if observed_phase == phase and not mutated:
                        mutated = True
                        (source_root / "README.md").write_text(
                            "source mutation after capture\n",
                            encoding="utf-8",
                        )

                with (
                    mock.patch.object(provenance, "_provenance_checkpoint", checkpoint),
                    self.assertRaisesRegex(
                        RepositoryProvenanceError,
                        "working-tree byte drift|worktree identity drift",
                    ),
                ):
                    with open_authenticated_repository(root) as authenticated:
                        self.assertEqual(
                            (authenticated.snapshot_root / "README.md").read_bytes(),
                            b"authenticated snapshot\n",
                        )
                self.assertTrue(mutated)

    def test_materialization_rejects_replaced_ancestor_without_escape(self) -> None:
        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        snapshot = authenticate_repository(root)
        destination = Path(temporary.name) / "materialized"
        escaped = Path(temporary.name) / "escaped"
        escaped.mkdir()
        displaced = Path(temporary.name) / "displaced-pkg"
        replaced = False

        def checkpoint(
            phase: str,
            *,
            source_root: Path,
            snapshot_root: Path | None = None,
        ) -> None:
            nonlocal replaced
            del source_root
            if phase != "during_snapshot_materialization" or replaced:
                return
            self.assertIsNotNone(snapshot_root)
            package = snapshot_root / "pkg"  # type: ignore[operator]
            self.assertTrue(package.is_dir())
            package.rename(displaced)
            package.symlink_to(escaped, target_is_directory=True)
            replaced = True

        with (
            mock.patch.object(provenance, "_provenance_checkpoint", checkpoint),
            self.assertRaisesRegex(
                RepositoryProvenanceError,
                "snapshot directory traversal was replaced or escaped",
            ),
        ):
            materialize_snapshot(snapshot, destination)
        self.assertTrue(replaced)
        self.assertFalse((escaped / "module.py").exists())

    def test_cleanup_never_follows_snapshot_symlink_or_changes_external_mode(self) -> None:
        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        external = Path(temporary.name) / "external"
        external.mkdir(mode=0o711)
        external_file = external / "sentinel"
        external_file.write_bytes(b"external bytes\n")
        external_file.chmod(0o640)
        directory_mode = external.stat().st_mode
        file_mode = external_file.stat().st_mode

        with self.assertRaises(RepositoryProvenanceError):
            with open_authenticated_repository(root) as authenticated:
                authenticated.snapshot_root.chmod(0o700)
                package = authenticated.snapshot_root / "pkg"
                displaced = authenticated.snapshot_root / "pkg-original"
                package.rename(displaced)
                package.symlink_to(external, target_is_directory=True)

        self.assertEqual(external_file.read_bytes(), b"external bytes\n")
        self.assertEqual(external.stat().st_mode, directory_mode)
        self.assertEqual(external_file.stat().st_mode, file_mode)

    def test_watcher_rejects_transient_restore_and_hardlink_alias_writes(self) -> None:
        for mutation in ("direct-restore", "hardlink-alias"):
            with self.subTest(mutation=mutation):
                temporary, root = self.make_repository()
                self.addCleanup(temporary.cleanup)
                with self.assertRaisesRegex(
                    RepositoryProvenanceError,
                    "authenticated snapshot changed",
                ):
                    with open_authenticated_repository(root) as authenticated:
                        target = authenticated.snapshot_root / "README.md"
                        original = target.read_bytes()
                        original_mode = target.stat().st_mode
                        if mutation == "direct-restore":
                            target.chmod(0o600)
                            target.write_bytes(b"transient unreviewed bytes\n")
                            target.write_bytes(original)
                            target.chmod(original_mode)
                        else:
                            alias = Path(temporary.name) / "snapshot-hardlink-alias"
                            os.link(target, alias)
                            alias.chmod(0o600)
                            alias.write_bytes(b"transient unreviewed bytes\n")
                            alias.write_bytes(original)
                            alias.chmod(original_mode)
                            alias.unlink()

    def test_snapshot_lifetime_hooks_reject_transient_restore(self) -> None:
        for target_phase in (
            "after_snapshot_materialization",
            "before_semantic_validation",
            "before_final_success_revalidation",
        ):
            with self.subTest(target_phase=target_phase):
                temporary, root = self.make_repository()
                self.addCleanup(temporary.cleanup)
                mutated = False

                def checkpoint(
                    phase: str,
                    *,
                    source_root: Path,
                    snapshot_root: Path | None = None,
                ) -> None:
                    nonlocal mutated
                    del source_root
                    if phase != target_phase or mutated:
                        return
                    self.assertIsNotNone(snapshot_root)
                    target = snapshot_root / "README.md"  # type: ignore[operator]
                    original = target.read_bytes()
                    original_mode = target.stat().st_mode
                    target.chmod(0o600)
                    target.write_bytes(b"transient hook mutation\n")
                    target.write_bytes(original)
                    target.chmod(original_mode)
                    mutated = True

                with (
                    mock.patch.object(
                        provenance,
                        "_provenance_checkpoint",
                        checkpoint,
                    ),
                    self.assertRaisesRegex(
                        RepositoryProvenanceError,
                        "authenticated snapshot changed",
                    ),
                ):
                    with open_authenticated_repository(root) as authenticated:
                        self.assertEqual(
                            (authenticated.snapshot_root / "README.md").read_bytes(),
                            b"authenticated snapshot\n",
                        )
                self.assertTrue(mutated)

    def test_semantic_consumer_reads_snapshot_and_final_source_drift_fails(self) -> None:
        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        with self.assertRaisesRegex(
            RepositoryProvenanceError,
            "working-tree byte drift|worktree identity drift",
        ):
            with open_authenticated_repository(root) as authenticated:
                (root / "README.md").write_text("late source bytes\n", encoding="utf-8")
                self.assertEqual(
                    (authenticated.snapshot_root / "README.md").read_bytes(),
                    b"authenticated snapshot\n",
                )

    def test_final_revalidation_rejects_authority_and_git_metadata_drift(self) -> None:
        mutations = (
            "workflow-alias",
            "approval-alias",
            "tracked-symlink",
            "tracked-ancestor-replacement",
            "tracked-mode",
            "tracked-removal",
            "index",
            "head",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                temporary, root = self.make_repository()
                self.addCleanup(temporary.cleanup)
                with self.assertRaises(RepositoryProvenanceError):
                    with open_authenticated_repository(root) as authenticated:
                        self.assertTrue(authenticated.snapshot_root.is_dir())
                        if mutation == "workflow-alias":
                            target = root / ".github/workflows/alternate-r11a.yml"
                            target.parent.mkdir(parents=True)
                            target.write_text("name: alternate\n", encoding="utf-8")
                        elif mutation == "approval-alias":
                            target = root / "research/archive_inventory/r11a_approval/alternate.json"
                            target.parent.mkdir(parents=True)
                            target.write_text("{}\n", encoding="utf-8")
                        elif mutation == "tracked-symlink":
                            target = root / "README.md"
                            target.unlink()
                            target.symlink_to(root / "pkg/module.py")
                        elif mutation == "tracked-ancestor-replacement":
                            package = root / "pkg"
                            moved = root / "pkg-original"
                            package.rename(moved)
                            package.symlink_to(moved, target_is_directory=True)
                        elif mutation == "tracked-mode":
                            (root / "README.md").chmod(0o755)
                        elif mutation == "tracked-removal":
                            (root / "README.md").unlink()
                        elif mutation == "index":
                            index = root / ".git/index"
                            raw = bytearray(index.read_bytes())
                            raw[16] ^= 1
                            self.write_rebound_index(root, raw)
                        else:
                            (root / ".git/HEAD").write_text(
                                "ref: refs/heads/missing-r11a-ref\n",
                                encoding="ascii",
                            )

    def test_snapshot_is_read_only_and_rejects_semantic_tampering(self) -> None:
        temporary, root = self.make_repository()
        self.addCleanup(temporary.cleanup)
        with self.assertRaisesRegex(
            RepositoryProvenanceError,
            "authenticated snapshot changed|authenticated snapshot byte drift|writable",
        ):
            with open_authenticated_repository(root) as authenticated:
                target = authenticated.snapshot_root / "README.md"
                target.chmod(0o600)
                target.write_text("snapshot tamper\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
