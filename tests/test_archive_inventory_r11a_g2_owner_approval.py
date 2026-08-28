from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from governance import validate_r11a_g2_owner_approval as approval
from governance.r11a_repository_provenance import authenticated_repository_copy
from governance.validate_r11a_g2_owner_approval import R11AG2ApprovalError, validate

ROOT = Path(__file__).resolve().parents[1]


def scalar_leaf_paths(value: object, prefix: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    if isinstance(value, dict):
        result: list[tuple[str, ...]] = []
        for key, child in value.items():
            result.extend(scalar_leaf_paths(child, prefix + (key,)))
        return result
    return [prefix]


def object_paths(value: object, prefix: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    if not isinstance(value, dict):
        return []
    result = [prefix]
    for key, child in value.items():
        result.extend(object_paths(child, prefix + (key,)))
    return result


def get_path(value: dict, path: tuple[str, ...]) -> object:
    current: object = value
    for key in path:
        if not isinstance(current, dict):
            raise TypeError(path)
        current = current[key]
    return current


def set_path(value: dict, path: tuple[str, ...], replacement: object) -> None:
    current = value
    for key in path[:-1]:
        child = current[key]
        if not isinstance(child, dict):
            raise TypeError(path)
        current = child
    current[path[-1]] = replacement


def delete_path(value: dict, path: tuple[str, ...]) -> None:
    current = value
    for key in path[:-1]:
        child = current[key]
        if not isinstance(child, dict):
            raise TypeError(path)
        current = child
    del current[path[-1]]


def contradictory(value: object) -> object:
    if type(value) is bool:
        return not value
    if type(value) is int:
        return value + 1
    if type(value) is str:
        if len(value) == 64 and all(character in "0123456789abcdef" for character in value):
            return ("0" if value[0] != "0" else "1") + value[1:]
        if len(value) == 40 and all(character in "0123456789abcdef" for character in value):
            return ("0" if value[0] != "0" else "1") + value[1:]
        return value + "_MUTATED"
    raise TypeError(type(value))


class R11AG2OwnerApprovalTests(unittest.TestCase):
    def copy_repository(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        return authenticated_repository_copy(
            ROOT,
        )

    def record_copy(self) -> tuple[tempfile.TemporaryDirectory[str], Path, Path, bytes, dict]:
        temporary, repository = self.copy_repository()
        path = repository / approval.APPROVAL_JSON
        raw = path.read_bytes()
        value = json.loads(raw)
        return temporary, repository, path, raw, value

    def write_record(self, path: Path, value: dict) -> bytes:
        raw = (json.dumps(value, indent=2) + "\n").encode("utf-8")
        path.write_bytes(raw)
        return raw

    @contextmanager
    def rebound_receipt_hash(self, raw: bytes):
        digest = hashlib.sha256(raw).hexdigest()
        with mock.patch.object(approval, "APPROVAL_RECEIPT_SHA", digest):
            yield

    def assert_semantic_record_failure(
        self,
        repository: Path,
        raw: bytes,
        message: str = "canonical approval record",
    ) -> None:
        with self.rebound_receipt_hash(raw):
            with self.assertRaisesRegex(R11AG2ApprovalError, message):
                validate(repository)

    def remove_any(self, path: Path) -> None:
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)

    def future_namespace_for(self, relative: str) -> str | None:
        for namespace in approval.PROHIBITED_AUTHORITY_NAMESPACES:
            if relative == namespace or relative.startswith(namespace + "/"):
                return namespace
        return None

    def test_canonical_record_passes_and_text_is_exact(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        record = validate(repository)
        canonical = (repository / approval.APPROVAL_TEXT).read_bytes()
        source = (repository / approval.SOURCE_STATEMENT).read_bytes()
        receipt = (repository / approval.APPROVAL_JSON).read_bytes()
        status = (repository / approval.STATUS).read_bytes()
        self.assertEqual(canonical, source)
        self.assertEqual(
            hashlib.sha256(canonical).hexdigest(), approval.APPROVAL_STATEMENT_SHA
        )
        self.assertEqual(
            hashlib.sha256(receipt).hexdigest(), approval.APPROVAL_RECEIPT_SHA
        )
        self.assertEqual(
            hashlib.sha256(status).hexdigest(), approval.HISTORICAL_G1_STATUS_SHA
        )
        self.assertEqual(len(scalar_leaf_paths(json.loads(receipt))), 136)
        self.assertTrue(canonical.endswith(b"\n"))
        self.assertFalse(record["execution_authorized_by_this_approval"])
        self.assertTrue(record["owner_approval_present"])

    def test_ci_import_bytecode_is_isolated_without_weakening_descendant_rejection(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        corrective_cache = (
            repository
            / "research/archive_inventory/r11a_corrective/__pycache__"
        )
        import_command = (
            "from research.archive_inventory.r11a_corrective.limits "
            "import DEFAULT_LIMITS"
        )
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
            [sys.executable, "-c", import_command],
            cwd=repository,
            env=environment,
            check=True,
        )
        self.assertTrue(corrective_cache.is_dir())
        self.assertTrue(any(corrective_cache.glob("*.pyc")))
        self.assertNotIn(
            corrective_cache.relative_to(repository).as_posix(),
            approval.ALLOWED_R11A_DIRECTORIES,
        )
        with self.assertRaisesRegex(
            R11AG2ApprovalError,
            "Python bytecode cache path prohibited",
        ):
            validate(repository)

        for generated_cache in sorted(
            repository.rglob("__pycache__"),
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            if generated_cache.exists():
                shutil.rmtree(generated_cache)
        self.assertFalse(corrective_cache.exists())

        corrective_cache.mkdir()
        (corrective_cache / "synthetic.pyc").write_bytes(b"synthetic-pyc")
        (corrective_cache / "synthetic.pyo").write_bytes(b"synthetic-pyo")
        with self.assertRaisesRegex(
            R11AG2ApprovalError,
            "Python bytecode cache path prohibited",
        ):
            validate(repository)
        shutil.rmtree(corrective_cache)

        for suffix in (".pyc", ".pyo"):
            with self.subTest(standalone_bytecode=suffix):
                standalone = corrective_cache.parent / f"synthetic{suffix}"
                standalone.write_bytes(b"synthetic-bytecode")
                try:
                    with self.assertRaisesRegex(
                        R11AG2ApprovalError,
                        "Python bytecode file path prohibited",
                    ):
                        validate(repository)
                finally:
                    standalone.unlink()

        cache_target = repository / "synthetic-cache-target"
        cache_target.mkdir()
        corrective_cache.symlink_to(cache_target, target_is_directory=True)
        with self.assertRaisesRegex(
            R11AG2ApprovalError,
            "Python bytecode cache path prohibited|symlink",
        ):
            validate(repository)
        corrective_cache.unlink()
        cache_target.rmdir()

        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        subprocess.run(
            [sys.executable, "-B", "-c", import_command],
            cwd=repository,
            env=environment,
            check=True,
        )
        self.assertFalse(corrective_cache.exists())
        validate(repository)

        unknown_descendant = corrective_cache.parent / "unknown-descendant"
        unknown_descendant.mkdir()
        with self.assertRaisesRegex(
            R11AG2ApprovalError,
            "unrecognized R11A authority namespace",
        ):
            validate(repository)
        shutil.rmtree(unknown_descendant)

        unknown_descendant.symlink_to(repository / "README.md")
        with self.assertRaisesRegex(
            R11AG2ApprovalError,
            "symlink|unrecognized R11A authority namespace",
        ):
            validate(repository)

    def test_every_scalar_leaf_type_valid_mutation_fails_closed(self) -> None:
        temporary, repository, path, raw, canonical = self.record_copy()
        self.addCleanup(temporary.cleanup)
        leaves = scalar_leaf_paths(canonical)
        self.assertEqual(len(leaves), 136)
        for leaf in leaves:
            with self.subTest(path=".".join(leaf)):
                mutated = copy.deepcopy(canonical)
                set_path(mutated, leaf, contradictory(get_path(canonical, leaf)))
                mutated_raw = self.write_record(path, mutated)
                self.assert_semantic_record_failure(repository, mutated_raw)
                path.write_bytes(raw)

    def test_every_scalar_leaf_missing_and_null_fails_closed(self) -> None:
        temporary, repository, path, raw, canonical = self.record_copy()
        self.addCleanup(temporary.cleanup)
        for leaf in scalar_leaf_paths(canonical):
            with self.subTest(kind="missing", path=".".join(leaf)):
                mutated = copy.deepcopy(canonical)
                delete_path(mutated, leaf)
                mutated_raw = self.write_record(path, mutated)
                self.assert_semantic_record_failure(repository, mutated_raw)
                path.write_bytes(raw)
            with self.subTest(kind="null", path=".".join(leaf)):
                mutated = copy.deepcopy(canonical)
                set_path(mutated, leaf, None)
                mutated_raw = self.write_record(path, mutated)
                self.assert_semantic_record_failure(repository, mutated_raw)
                path.write_bytes(raw)

    def test_wrong_types_and_unexpected_keys_fail_closed(self) -> None:
        temporary, repository, path, raw, canonical = self.record_copy()
        self.addCleanup(temporary.cleanup)
        representatives = {
            "schema_version": 1,
            "owner_approval_present": 1,
            "approved_bound_files": [],
            "approved_future_diagnostic": "not-an-object",
        }
        for key, replacement in representatives.items():
            with self.subTest(key=key):
                mutated = copy.deepcopy(canonical)
                mutated[key] = replacement
                mutated_raw = self.write_record(path, mutated)
                self.assert_semantic_record_failure(repository, mutated_raw)
                path.write_bytes(raw)

        for object_path in object_paths(canonical):
            with self.subTest(unexpected_at=".".join(object_path) or "root"):
                mutated = copy.deepcopy(canonical)
                target = get_path(mutated, object_path) if object_path else mutated
                if not isinstance(target, dict):
                    raise TypeError(object_path)
                target["unexpected_authority_bearing_key"] = False
                mutated_raw = self.write_record(path, mutated)
                self.assert_semantic_record_failure(repository, mutated_raw)
                path.write_bytes(raw)

    def test_duplicate_json_keys_fail_closed(self) -> None:
        temporary, repository, path, raw, _ = self.record_copy()
        self.addCleanup(temporary.cleanup)
        duplicate = raw.replace(
            b'{\n  "schema_version": "1.0",',
            b'{\n  "schema_version": "1.0",\n  "schema_version": "1.0",',
            1,
        )
        self.assertNotEqual(duplicate, raw)
        path.write_bytes(duplicate)
        self.assert_semantic_record_failure(repository, duplicate, "duplicate JSON key")

    def test_every_package_bound_raw_file_mutation_fails_closed(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        for relative in approval.EXPECTED_BOUND_FILES:
            with self.subTest(path=relative):
                path = repository / relative
                raw = path.read_bytes()
                path.write_bytes(raw + b"\n")
                with self.assertRaisesRegex(R11AG2ApprovalError, "hash drift"):
                    validate(repository)
                path.write_bytes(raw)

    def test_every_package_bound_file_missing_fails_closed(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        for relative in approval.EXPECTED_BOUND_FILES:
            with self.subTest(path=relative):
                path = repository / relative
                backup = path.with_name(path.name + ".g2-backup")
                path.rename(backup)
                try:
                    with self.assertRaisesRegex(R11AG2ApprovalError, "required path absent"):
                        validate(repository)
                finally:
                    backup.rename(path)

    def test_text_tamper_missing_file_and_symlink_fail_closed(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        path = repository / approval.APPROVAL_TEXT
        raw = path.read_bytes()
        path.write_bytes(raw + b"changed\n")
        with self.assertRaisesRegex(
            R11AG2ApprovalError, "canonical approval statement hash drift"
        ):
            validate(repository)
        path.write_bytes(raw)
        path.unlink()
        with self.assertRaisesRegex(R11AG2ApprovalError, "file set drift"):
            validate(repository)
        path.symlink_to(repository / approval.SOURCE_STATEMENT)
        with self.assertRaisesRegex(R11AG2ApprovalError, "symlink"):
            validate(repository)

    def test_path_hash_pair_mutations_fail_closed(self) -> None:
        temporary, repository, path, raw, canonical = self.record_copy()
        self.addCleanup(temporary.cleanup)
        bound = canonical["approved_bound_files"]
        original_path = next(iter(bound))
        original_hash = bound[original_path]

        mutated = copy.deepcopy(canonical)
        del mutated["approved_bound_files"][original_path]
        mutated["approved_bound_files"][original_path + ".moved"] = original_hash
        mutated_raw = self.write_record(path, mutated)
        self.assert_semantic_record_failure(repository, mutated_raw)

        mutated = copy.deepcopy(canonical)
        mutated["approved_bound_files"][original_path] = "0" * 64
        mutated_raw = self.write_record(path, mutated)
        self.assert_semantic_record_failure(repository, mutated_raw)
        path.write_bytes(raw)

    def test_extra_canonical_approval_entries_are_rejected(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        extra = repository / approval.APPROVAL_DIR / "EXTRA_AUTHORITY.json"
        extra.write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(R11AG2ApprovalError, "file set drift"):
            validate(repository)
        extra.unlink()

        unexpected_directory = repository / approval.APPROVAL_DIR / "extra_authority"
        unexpected_directory.mkdir()
        with self.assertRaisesRegex(R11AG2ApprovalError, "file set drift"):
            validate(repository)

    def test_sha_labels_map_to_exact_raw_artifacts_and_errors(self) -> None:
        self.assertEqual(
            hashlib.sha256((ROOT / approval.STATUS).read_bytes()).hexdigest(),
            approval.HISTORICAL_G1_STATUS_SHA,
        )
        self.assertEqual(
            hashlib.sha256((ROOT / approval.APPROVAL_TEXT).read_bytes()).hexdigest(),
            approval.APPROVAL_STATEMENT_SHA,
        )
        self.assertEqual(
            hashlib.sha256((ROOT / approval.SOURCE_STATEMENT).read_bytes()).hexdigest(),
            approval.APPROVAL_STATEMENT_SHA,
        )
        self.assertEqual(
            hashlib.sha256((ROOT / approval.APPROVAL_JSON).read_bytes()).hexdigest(),
            approval.APPROVAL_RECEIPT_SHA,
        )

        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        cases = (
            (approval.STATUS, "historical G1 status hash drift"),
            (approval.SOURCE_STATEMENT, "source approval statement hash drift"),
            (approval.APPROVAL_TEXT, "canonical approval statement hash drift"),
            (approval.APPROVAL_JSON, "approval receipt raw hash drift"),
        )
        for relative, message in cases:
            with self.subTest(path=relative):
                path = repository / relative
                raw = path.read_bytes()
                path.write_bytes(raw + b" ")
                with self.assertRaisesRegex(R11AG2ApprovalError, message):
                    validate(repository)
                path.write_bytes(raw)

    def test_non_finite_receipt_number_reaches_strict_json_check(self) -> None:
        temporary, repository, path, raw, _ = self.record_copy()
        self.addCleanup(temporary.cleanup)
        mutated = raw.replace(
            b'"schema_version": "1.0"',
            b'"schema_version": NaN',
            1,
        )
        self.assertNotEqual(mutated, raw)
        path.write_bytes(mutated)
        self.assert_semantic_record_failure(repository, mutated, "non-finite JSON constant")

    def test_repository_wide_approval_alias_matrix_fails_closed(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        statement = (repository / approval.APPROVAL_TEXT).read_bytes()
        receipt = (repository / approval.APPROVAL_JSON).read_bytes()
        conflicting_text = statement.replace(
            b"This approval alone does not",
            b"This altered approval does",
            1,
        )
        self.assertNotEqual(conflicting_text, statement)
        conflicting_receipt = json.loads(receipt)
        conflicting_receipt["current_authority"]["runtime_activation"] = True
        conflicting_receipt_raw = (
            json.dumps(conflicting_receipt, indent=2) + "\n"
        ).encode("utf-8")

        cases = (
            (
                "exact_text",
                "research/archive_inventory/r11a_runtime/approval-copy.txt",
                "file",
                statement,
            ),
            (
                "conflicting_text",
                "research/archive_inventory/r11a_role_attestation/owner.txt",
                "file",
                conflicting_text,
            ),
            (
                "exact_json",
                "research/archive_inventory/r11a_role_preflight/receipt-copy.json",
                "file",
                receipt,
            ),
            (
                "conflicting_json",
                "research/archive_inventory/r11a_workflow_installation/conflict.json",
                "file",
                conflicting_receipt_raw,
            ),
            (
                "same_approval_id",
                "research/archive_inventory/r11a_evidence/another-name.json",
                "file",
                (json.dumps({"approval_id": approval.APPROVAL_ID}) + "\n").encode(),
            ),
            (
                "canonical_id_filename",
                f"research/archive_inventory/r11a_runtime/{approval.APPROVAL_ID}.backup",
                "file",
                b"conflicting bytes\n",
            ),
            (
                "alias_symlink",
                "research/archive_inventory/r11a_role_attestation/owner-link.txt",
                "symlink",
                b"",
            ),
            (
                "dangling_alias_symlink",
                f"research/archive_inventory/r11a_role_preflight/{approval.APPROVAL_ID}.json.link",
                "dangling",
                b"",
            ),
            (
                "nested_alias_directory",
                f"research/archive_inventory/r11a_evidence/nested/{approval.APPROVAL_ID}",
                "directory",
                b"",
            ),
        )
        observed_namespaces: set[str] = set()
        for label, relative, kind, payload in cases:
            with self.subTest(case=label, path=relative):
                namespace = self.future_namespace_for(relative)
                self.assertIsNotNone(namespace)
                observed_namespaces.add(namespace or "")
                path = repository / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                if kind == "file":
                    path.write_bytes(payload)
                elif kind == "directory":
                    path.mkdir()
                elif kind == "symlink":
                    path.symlink_to(repository / approval.APPROVAL_TEXT)
                elif kind == "dangling":
                    path.symlink_to(repository / "missing-approval-alias")
                else:
                    self.fail(kind)
                try:
                    with self.assertRaisesRegex(
                        R11AG2ApprovalError,
                        "approval.*alias|approval/authority symlink|approval/authority data file",
                    ):
                        validate(repository)
                finally:
                    self.remove_any(repository / (namespace or relative))

        required_alias_namespaces = {
            "research/archive_inventory/r11a_runtime",
            "research/archive_inventory/r11a_role_attestation",
            "research/archive_inventory/r11a_role_preflight",
            "research/archive_inventory/r11a_workflow_installation",
            "research/archive_inventory/r11a_evidence",
        }
        self.assertEqual(observed_namespaces, required_alias_namespaces)

    def test_aliases_outside_future_namespaces_and_hardlinks_fail_closed(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        statement = (repository / approval.APPROVAL_TEXT).read_bytes()
        alias_root = repository / "research/archive_inventory/r11a_g1"
        cases = (
            ("G2_ALIAS_full-statement.bin", statement),
            (
                "G2_ALIAS_unicode-id.json",
                (
                    '{"approval_id":"\\u0041PPROVE_HL_ARCHIVE_R11A_'
                    'IDENTITY_BOUNDARY_DIAGNOSTIC_001"}\n'
                ).encode("ascii"),
            ),
            (
                "G2_ALIAS_positive-approval.json",
                (
                    json.dumps(
                        {
                            "package_id": approval.PACKAGE_ID,
                            "owner_approval_present": True,
                        }
                    )
                    + "\n"
                ).encode(),
            ),
            (
                "G2_ALIAS_positive-approval-without-id.json",
                b'{"owner_approval_present":true}\n',
            ),
            (
                "G2_ALIAS_invalid-approval-alias.json",
                b'{"approval_id":"broken", "approval_id":"broken"}\n',
            ),
        )
        for filename, raw in cases:
            with self.subTest(filename=filename):
                path = alias_root / filename
                path.write_bytes(raw)
                try:
                    with self.assertRaisesRegex(
                        R11AG2ApprovalError,
                        "approval.*alias|approval/authority data file",
                    ):
                        validate(repository)
                finally:
                    path.unlink()

        hardlink = alias_root / "G2_ALIAS_hard-linked-statement.txt"
        os.link(repository / approval.APPROVAL_TEXT, hardlink)
        try:
            with self.assertRaisesRegex(R11AG2ApprovalError, "hard-link alias"):
                validate(repository)
        finally:
            hardlink.unlink()

        generic_symlink = repository / "generic-owner-record-link"
        generic_symlink.symlink_to(repository / approval.APPROVAL_TEXT)
        try:
            with self.assertRaisesRegex(R11AG2ApprovalError, "repository symlink prohibited"):
                validate(repository)
        finally:
            generic_symlink.unlink()

        generic_dangling = repository / "generic-dangling-record-link"
        generic_dangling.symlink_to(repository / "missing-owner-record")
        try:
            with self.assertRaisesRegex(R11AG2ApprovalError, "repository symlink prohibited"):
                validate(repository)
        finally:
            generic_dangling.unlink()

    def test_approval_alias_extension_root_and_filename_evasions_fail_closed(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        statement = (repository / approval.APPROVAL_TEXT).read_bytes()
        approval_id_raw = approval.APPROVAL_ID.encode("ascii")
        signed_prefix = statement.split(approval_id_raw, 1)[0]
        conflicting_signed_text = (
            signed_prefix
            + approval_id_raw
            + b" under a conflicting package and repository.\n"
        )
        same_id_object = (json.dumps({"approval_id": approval.APPROVAL_ID}) + "\n").encode()
        same_id_array = (
            json.dumps(
                [
                    {
                        "approval_id": approval.APPROVAL_ID,
                        "owner_approval_present": True,
                    }
                ]
            )
            + "\n"
        ).encode()

        alias_root = repository / "research/archive_inventory/r11a_g1"
        misc_root = repository / "g2_alias_misc"
        misc_root.mkdir()
        cases = (
            (alias_root / "G2_ALIAS_receipt.JSON", same_id_object),
            (alias_root / "G2_ALIAS_receipt.json ", same_id_object),
            (alias_root / "G2_ALIAS_receipt_no_suffix", same_id_object),
            (misc_root / "receipt.JSON", same_id_object),
            (misc_root / "receipt-array.data", same_id_array),
            (alias_root / "G2_ALIAS_signed.TXT", conflicting_signed_text),
            (alias_root / "G2_ALIAS_signed.text", conflicting_signed_text),
            (misc_root / "signed-owner.TXT", conflicting_signed_text),
            (misc_root / f"{approval.APPROVAL_ID}-copy.bin", b"conflict\n"),
            (misc_root / f"{approval.APPROVAL_ID}_backup", b"conflict\n"),
            (misc_root / f"{approval.APPROVAL_ID} (1).dat", b"conflict\n"),
            (
                misc_root / "paraphrased-owner.txt",
                (
                    b"Approval ID "
                    + approval_id_raw
                    + b" is approved by Mathis Van Eeckhout.\n"
                ),
            ),
        )
        for path, raw in cases:
            with self.subTest(path=path.relative_to(repository).as_posix()):
                path.write_bytes(raw)
                try:
                    with self.assertRaisesRegex(
                        R11AG2ApprovalError,
                        "approval.*alias|signed approval text|R11A approval/authority JSON alias|approval/authority data file",
                    ):
                        validate(repository)
                finally:
                    path.unlink()

    def test_nested_casefold_and_unicode_r11a_namespaces_fail_closed(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        cases = (
            (
                "research/archive_inventory/r11a_g1/runtime",
                "research/archive_inventory/r11a_g1/runtime",
            ),
            (
                "research/archive_inventory/r11a_corrective/release",
                "research/archive_inventory/r11a_corrective/release",
            ),
            (
                "research/archive_inventory/r11a_v2/evidence",
                "research/archive_inventory/r11a_v2/evidence",
            ),
            (
                "research/archive_inventory/r11a_implementation/preflight",
                "research/archive_inventory/r11a_implementation/preflight",
            ),
            (
                "research/archive_inventory/alias/r11a_runtime",
                "research/archive_inventory/alias",
            ),
            (
                "research/archive_inventory/foo/r11a_role_preflight",
                "research/archive_inventory/foo",
            ),
            (
                "research/archive_inventory/r11a_g1/nested/r11a_evidence",
                "research/archive_inventory/r11a_g1/nested",
            ),
            (
                "research/archive_inventory/other/R11A-ACTIVATION",
                "research/archive_inventory/other",
            ),
            (
                "research/archive_inventory/R11A_G1",
                "research/archive_inventory/R11A_G1",
            ),
            (
                "research/archive_inventory/r11a_\uff471",
                "research/archive_inventory/r11a_\uff471",
            ),
            (
                "research/archive_inventory/r11\u0430_runtime",
                "research/archive_inventory/r11\u0430_runtime",
            ),
            (
                "research/archive_inventory/r11\u03b1_runtime",
                "research/archive_inventory/r11\u03b1_runtime",
            ),
            (
                "research/archive_inventory/misc/r11a-approval",
                "research/archive_inventory/misc",
            ),
            (
                "research/archive_inventory/misc/approval_r11a",
                "research/archive_inventory/misc",
            ),
        )
        for relative, cleanup_relative in cases:
            with self.subTest(path=relative):
                directory = repository / relative
                directory.mkdir(parents=True)
                try:
                    with self.assertRaisesRegex(
                        R11AG2ApprovalError,
                        "unrecognized R11A authority namespace|approval alias directory|non-ASCII.*repository path",
                    ):
                        validate(repository)
                finally:
                    self.remove_any(repository / cleanup_relative)

    def test_alternate_r11a_authority_records_and_name_variants_fail_closed(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        records = (
            (
                "research/archive_inventory/r11a_g1/R11A_STAGE_AUTHORITY.record",
                {"successor_role_created": True},
            ),
            (
                "research/archive_inventory/r11a_corrective/R11A_ROLE_CREATED_CONFIGURED_EVIDENCE.data",
                {"role_created_and_configured": True},
            ),
            (
                "research/archive_inventory/r11a_v2/R11A_STS_OTHER_EVIDENCE.JSON",
                {"sts": True},
            ),
            (
                "research/archive_inventory/r11a_implementation/R11A_RUNTIME_OTHER",
                {"runtime_activation": True},
            ),
        )
        for relative, value in records:
            with self.subTest(path=relative):
                path = repository / relative
                path.write_text(json.dumps(value) + "\n", encoding="utf-8")
                try:
                    with self.assertRaisesRegex(
                        R11AG2ApprovalError,
                        "approval/authority file alias|approval/authority JSON alias|approval/authority data file|opens current authority",
                    ):
                        validate(repository)
                finally:
                    path.unlink()

        misc = repository / "g2_authority_misc"
        misc.mkdir()
        variants = (
            "R11A_EXECUTION_RELEASE_v2.json",
            "R11A_SUCCESSOR_ROLE_OPERATOR_ATTESTATION_COPY.json",
            "R11A_STS_PREFLIGHT_EVIDENCE.json",
            "R11A_WORKFLOW_INSTALLATION.json",
        )
        for basename in variants:
            with self.subTest(basename=basename):
                path = misc / basename
                path.write_text("{}\n", encoding="utf-8")
                try:
                    with self.assertRaisesRegex(
                        R11AG2ApprovalError, "approval/authority file alias"
                    ):
                        validate(repository)
                finally:
                    path.unlink()

    def test_reference_only_documentation_and_source_are_not_aliases(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        reference_root = repository / "research/archive_inventory/r11a_g1"
        created = []
        for suffix in ("md", "py", "rst", "sh"):
            path = reference_root / f"G2_REFERENCE_ONLY.{suffix}"
            path.write_text(
                f"Reference only: {approval.APPROVAL_ID} under {approval.PACKAGE_ID}.\n",
                encoding="utf-8",
            )
            created.append(path)
        try:
            validate(repository)
        finally:
            for path in created:
                path.unlink()

        unrelated = repository / "fixtures/broken.json"
        unrelated.parent.mkdir()
        unrelated.write_text("{not valid JSON\n", encoding="utf-8")
        unicode_document = repository / "docs/caf\u00e9.md"
        unicode_document.parent.mkdir()
        unicode_document.write_text("Unrelated documentation.\n", encoding="utf-8")
        try:
            validate(repository)
        finally:
            unrelated.unlink()
            unicode_document.unlink()

        authority_yaml = reference_root / "G2_AUTHORITY_DATA.yml"
        authority_yaml.write_text(
            "owner_approval_present: true\ncanonical_approval_record_present: true\n",
            encoding="utf-8",
        )
        try:
            with self.assertRaisesRegex(
                R11AG2ApprovalError, "approval/authority data file"
            ):
                validate(repository)
        finally:
            authority_yaml.unlink()

    def test_cache_and_nested_metadata_directories_cannot_hide_aliases(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        receipt = (repository / approval.APPROVAL_JSON).read_bytes()
        directory_cases = (
            "research/archive_inventory/r11a_g1/__pycache__",
            "research/archive_inventory/r11a_g1/.pytest_cache",
            "research/archive_inventory/r11a_g1/.mypy_cache",
            "research/archive_inventory/r11a_g1/.ruff_cache",
            "research/archive_inventory/r11a_g1/.venv",
            "research/archive_inventory/r11a_g1/venv",
            "research/archive_inventory/r11a_g1/.git",
            ".mypy_cache",
        )
        for relative in directory_cases:
            with self.subTest(directory=relative):
                directory = repository / relative
                directory.mkdir(parents=True)
                alias = directory / f"{approval.APPROVAL_ID}.json"
                alias.write_bytes(receipt)
                try:
                    with self.assertRaisesRegex(
                        R11AG2ApprovalError,
                        "approval.*alias|approval/authority data file|nested repository metadata|Python bytecode cache path prohibited",
                    ):
                        validate(repository)
                finally:
                    self.remove_any(directory)

    def test_complete_r4_r7_authority_inventory_is_exact(self) -> None:
        expected_paths = {
            "research/archive_inventory/r11a_role_attestation/R11A_SUCCESSOR_ROLE_CREATION_CONFIGURATION_CANDIDATE.json",
            "research/archive_inventory/r11a_role_attestation/R11A_SUCCESSOR_ROLE_OPERATOR_ATTESTATION.json",
            "research/archive_inventory/r11a_role_preflight/R11A_STS_PREFLIGHT_CANDIDATE.json",
            "research/archive_inventory/r11a_role_preflight/R11A_STS_PREFLIGHT_RELEASE.json",
            "research/archive_inventory/r11a_role_preflight/R11A_SUCCESSOR_ROLE_STS_PREFLIGHT_ATTESTATION.json",
            "research/archive_inventory/r11a_role_preflight/R11A_STS_PREFLIGHT_RELEASE_CONSUMPTION.json",
            "research/archive_inventory/r11a_workflow_installation/R11A_WORKFLOW_INSTALLATION_CONTRACT.json",
            "research/archive_inventory/r11a_runtime/R11A_RUNTIME_BINDING_R7.json",
            "research/archive_inventory/r11a_runtime/R11A_EXECUTION_RELEASE.json",
            "research/archive_inventory/r11a_runtime/R11A_EXECUTION_RELEASE.sha256",
            "research/archive_inventory/r11a_runtime/R11A_CANONICAL_ACTIVATION.json",
            "research/archive_inventory/r11a_runtime/R11A_EXECUTION_RELEASE_CANDIDATE.json",
            "research/archive_inventory/r11a_runtime/R11A_EXECUTION_RELEASE_CONSUMPTION.json",
            "research/archive_inventory/r11a_review_evidence/R11A_ALIGNMENT_REVIEW_EVIDENCE.json",
            "research/archive_inventory/r11a_review_evidence/R11A_IDENTITY_CONFIGURATION_REVIEW_EVIDENCE.json",
            "research/archive_inventory/r11a_review_evidence/R11A_ROLE_ATTESTATION_REVIEW_EVIDENCE.json",
            "research/archive_inventory/r11a_review_evidence/R11A_STS_PREFLIGHT_CANDIDATE_REVIEW_EVIDENCE.json",
            "research/archive_inventory/r11a_review_evidence/R11A_STS_PREFLIGHT_RELEASE_REVIEW_EVIDENCE.json",
            "research/archive_inventory/r11a_review_evidence/R11A_STS_PREFLIGHT_REVIEW_EVIDENCE.json",
            "research/archive_inventory/r11a_review_evidence/R11A_WORKFLOW_INSTALLATION_REVIEW_EVIDENCE.json",
            "research/archive_inventory/r11a_review_evidence/R11A_EXECUTION_RELEASE_CANDIDATE_REVIEW_EVIDENCE.json",
            "research/archive_inventory/r11a_review_evidence/R11A_EXECUTION_RELEASE_REVIEW_EVIDENCE.json",
            "research/archive_inventory/r11a_review_evidence/R11A_ACTIVATION_REVIEW_EVIDENCE.json",
            "research/archive_inventory/r11a_review_evidence/R11A_RUNTIME_BINDING_REVIEW_EVIDENCE.json",
        }
        expected_namespaces = {
            "research/archive_inventory/r11a_role_attestation",
            "research/archive_inventory/r11a_role_preflight",
            "research/archive_inventory/r11a_workflow_installation",
            "research/archive_inventory/r11a_runtime",
            "research/archive_inventory/r11a_review_evidence",
            "research/archive_inventory/r11a_evidence",
            "research/archive_inventory/r11a_v2_approval",
            "research/archive_inventory/r11a_v2_runtime",
            "research/archive_inventory/r11a_v2_evidence",
        }
        expected_workflows = {
            ".github/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic.yml",
            ".github/workflows/hyperliquid-archive-r11a-v2-identity-boundary-diagnostic.yml",
        }
        self.assertEqual(set(approval.CANONICAL_FUTURE_AUTHORITY_PATHS), expected_paths)
        self.assertEqual(set(approval.PROHIBITED_AUTHORITY_NAMESPACES), expected_namespaces)
        self.assertEqual(set(approval.PROHIBITED_INSTALLED_WORKFLOWS), expected_workflows)

        expected_directories = {
            "research/archive_inventory/r11a",
            "research/archive_inventory/r11a_alignment",
            "research/archive_inventory/r11a_approval",
            "research/archive_inventory/r11a_corrective",
            "research/archive_inventory/r11a_corrective/workflows",
            "research/archive_inventory/r11a_g1",
            "research/archive_inventory/r11a_implementation",
            "research/archive_inventory/r11a_implementation/workflows",
            "research/archive_inventory/r11a_v2",
        }
        self.assertEqual(approval.ALLOWED_R11A_DIRECTORIES, expected_directories)
        observed_json = {
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "research/archive_inventory").rglob("*.json")
            if approval._is_r11a_archive_path(path.relative_to(ROOT).as_posix())
        }
        self.assertEqual(len(observed_json), 30)
        self.assertEqual(approval.CANONICAL_R11A_JSON_PATHS, observed_json)

        workflow_rows = []
        for path in sorted(
            (ROOT / ".github/workflows").iterdir(),
            key=lambda value: value.name.encode("utf-8"),
        ):
            if path.is_file() and path.suffix.casefold() in {".yml", ".yaml"}:
                relative = path.relative_to(ROOT).as_posix()
                workflow_rows.append(
                    f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {relative}\n"
                )
        self.assertEqual(len(workflow_rows), 24)
        self.assertEqual(
            hashlib.sha256("".join(workflow_rows).encode("ascii")).hexdigest(),
            approval.INSTALLED_WORKFLOW_INVENTORY_SHA256,
        )

    def test_every_real_authority_path_rejects_every_filesystem_kind(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        paths = (
            *approval.CANONICAL_FUTURE_AUTHORITY_PATHS,
            *approval.PROHIBITED_INSTALLED_WORKFLOWS,
        )
        for relative in paths:
            for kind in ("file", "directory", "symlink", "dangling"):
                with self.subTest(path=relative, kind=kind):
                    path = repository / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    if kind == "file":
                        path.write_text("{}\n", encoding="utf-8")
                    elif kind == "directory":
                        path.mkdir()
                    elif kind == "symlink":
                        path.symlink_to(repository / "README.md")
                    else:
                        path.symlink_to(repository / "missing-authority-target")
                    namespace = self.future_namespace_for(relative)
                    try:
                        with self.assertRaisesRegex(
                            R11AG2ApprovalError,
                            "future authority|runtime workflow|symlink path component|approval/authority symlink|approval/authority file alias|approval/authority data file",
                        ):
                            validate(repository)
                    finally:
                        self.remove_any(repository / (namespace or relative))

    def test_real_authority_basenames_are_rejected_at_alternate_paths(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        alias_root = repository / "research/archive_inventory/r11a_g1"
        basenames = {
            Path(relative).name
            for relative in (
                *approval.CANONICAL_FUTURE_AUTHORITY_PATHS,
                *approval.PROHIBITED_INSTALLED_WORKFLOWS,
            )
        }
        for basename in sorted(basenames):
            with self.subTest(basename=basename):
                path = alias_root / f"G2_ALIAS_{basename}"
                path.write_text("{}\n", encoding="utf-8")
                try:
                    with self.assertRaisesRegex(
                        R11AG2ApprovalError,
                        "approval/authority file alias|authority artifact alias|approval/authority data file",
                    ):
                        validate(repository)
                finally:
                    path.unlink()

    def test_every_future_authority_namespace_rejects_every_filesystem_kind(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        for relative in approval.PROHIBITED_AUTHORITY_NAMESPACES:
            for kind in ("file", "directory", "symlink", "dangling"):
                with self.subTest(path=relative, kind=kind):
                    path = repository / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    if kind == "file":
                        path.write_text("{}\n", encoding="utf-8")
                    elif kind == "directory":
                        path.mkdir()
                    elif kind == "symlink":
                        path.symlink_to(repository / "README.md")
                    else:
                        path.symlink_to(repository / "missing-authority-namespace")
                    try:
                        with self.assertRaisesRegex(
                            R11AG2ApprovalError,
                            "future authority|non-directory path component|approval/authority symlink|approval/authority file alias|approval/authority data file|approval alias directory",
                        ):
                            validate(repository)
                    finally:
                        self.remove_any(path)

    def test_unknown_r11a_authority_namespace_fails_closed(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        relative = "research/archive_inventory/r11a_future_authority"
        for kind in ("file", "directory", "symlink", "dangling"):
            with self.subTest(kind=kind):
                path = repository / relative
                if kind == "file":
                    path.write_text("{}\n", encoding="utf-8")
                elif kind == "directory":
                    path.mkdir()
                elif kind == "symlink":
                    path.symlink_to(repository / "README.md")
                else:
                    path.symlink_to(repository / "missing-unknown-authority")
                try:
                    with self.assertRaisesRegex(
                        R11AG2ApprovalError,
                        "unrecognized R11A authority|approval/authority symlink|approval/authority file alias|approval/authority data file",
                    ):
                        validate(repository)
                finally:
                    self.remove_any(path)

        nested = repository / "research/archive_inventory/r11a_evidence/deep/run/evidence.json"
        nested.parent.mkdir(parents=True)
        nested.write_text("{}\n", encoding="utf-8")
        try:
            with self.assertRaisesRegex(
                R11AG2ApprovalError,
                "future authority namespace|approval/authority JSON alias|approval/authority data file",
            ):
                validate(repository)
        finally:
            self.remove_any(repository / "research/archive_inventory/r11a_evidence")

    def test_alternate_installed_runtime_workflow_aliases_fail_closed(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        cases = (
            (
                "candidate-copy.yml",
                (repository / approval.WORKFLOW).read_bytes(),
            ),
            (
                "candidate-r4-copy.yaml",
                (repository / approval.R4_WORKFLOW_CANDIDATE).read_bytes(),
            ),
            (
                "R11A-runtime.yml",
                "on:\n  workflow_dispatch:\npermissions:\n  id-token: write\n"
                "jobs:\n  run:\n    steps:\n      - run: echo "
                "onchain-wallet-intelligence-hl-archive-identity-r11a\n"
                .encode(),
            ),
            (
                "r11a-diagnostic.yaml",
                b"name: inert placeholder\non: []\n",
            ),
            (
                "innocent.yml",
                b"name: R11A identity-boundary diagnostic\non: []\n",
            ),
        )
        for filename, raw in cases:
            with self.subTest(filename=filename, sha256=hashlib.sha256(raw).hexdigest()):
                installed = repository / ".github/workflows" / filename
                installed.write_bytes(raw)
                try:
                    with self.assertRaisesRegex(
                        R11AG2ApprovalError,
                        "approval.*alias|runtime workflow alias|workflow path/raw-byte inventory drift",
                    ):
                        validate(repository)
                finally:
                    installed.unlink()

        development = repository / approval.R11A_DEVELOPMENT_WORKFLOW
        raw = development.read_bytes()
        development.write_bytes(raw + b"\n")
        try:
            with self.assertRaisesRegex(
                R11AG2ApprovalError, "R11A development workflow hash drift"
            ):
                validate(repository)
        finally:
            development.write_bytes(raw)

        obfuscated = repository / ".github/workflows/run.yml"
        obfuscated.write_text(
            "name: future identity\n"
            "on: workflow_dispatch\n"
            "permissions:\n  id-token: write\n"
            "jobs:\n  run:\n    runs-on: ubuntu-latest\n    steps:\n"
            "      - run: echo ${{ format('{0}{1}', 'r11', 'a') }}\n",
            encoding="utf-8",
        )
        try:
            with self.assertRaisesRegex(
                R11AG2ApprovalError, "workflow path/raw-byte inventory drift"
            ):
                validate(repository)
        finally:
            obfuscated.unlink()

    def test_every_security_critical_ancestor_symlink_fails_closed(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        critical_paths = {
            approval.APPROVAL_DIR,
            approval.APPROVAL_JSON,
            approval.APPROVAL_TEXT,
            approval.SOURCE_STATEMENT,
            approval.PACKAGE,
            approval.STATUS,
            approval.ENVELOPE,
            approval.PRICING,
            approval.RUNTIME_PRICING,
            approval.R4_WORKFLOW_CANDIDATE,
            approval.HISTORICAL_IMPLEMENTATION_WORKFLOW_CANDIDATE,
            *approval.EXPECTED_BOUND_FILES,
            *approval.PROHIBITED_INSTALLED_WORKFLOWS,
        }
        ancestors: set[str] = set()
        for relative in critical_paths:
            parts = Path(relative).parts
            maximum = len(parts) if relative == approval.APPROVAL_DIR else len(parts) - 1
            for length in range(1, maximum + 1):
                ancestor = Path(*parts[:length]).as_posix()
                if (repository / ancestor).is_dir():
                    ancestors.add(ancestor)

        required_minimum = {
            "research",
            "research/archive_inventory",
            "research/archive_inventory/r11a_g1",
            "research/archive_inventory/r11a_approval",
            "research/archive_inventory/r11a_corrective",
            "research/archive_inventory/r11a_corrective/workflows",
            ".github",
            ".github/workflows",
        }
        self.assertTrue(required_minimum.issubset(ancestors))

        for relative in sorted(ancestors):
            for dangling in (False, True):
                with self.subTest(ancestor=relative, dangling=dangling):
                    path = repository / relative
                    backup = path.with_name(path.name + "__g2_real")
                    path.rename(backup)
                    target = path.name + "__missing" if dangling else backup.name
                    path.symlink_to(target, target_is_directory=True)
                    try:
                        with self.assertRaisesRegex(
                            R11AG2ApprovalError, "symlink path component"
                        ):
                            validate(repository)
                    finally:
                        path.unlink()
                        backup.rename(path)

    def test_repository_root_symlinks_and_symlinked_parent_fail_closed(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        direct = repository.with_name("repository-link")
        direct.symlink_to(repository, target_is_directory=True)
        with self.assertRaisesRegex(R11AG2ApprovalError, "root path component is symlink"):
            validate(direct)

        dangling = repository.with_name("dangling-repository-link")
        dangling.symlink_to(repository.with_name("missing-repository"), target_is_directory=True)
        with self.assertRaisesRegex(R11AG2ApprovalError, "root path component is symlink"):
            validate(dangling)

        parent_link = repository.parent / "parent-link"
        parent_link.symlink_to(repository.parent, target_is_directory=True)
        with self.assertRaisesRegex(R11AG2ApprovalError, "root path component is symlink"):
            validate(parent_link / repository.name)

        with self.assertRaisesRegex(R11AG2ApprovalError, "root must be an absolute"):
            validate(Path("relative-repository"))
        with self.assertRaisesRegex(R11AG2ApprovalError, "root contains traversal"):
            validate(repository / ".." / repository.name)
        ambiguous = Path("//" + repository.as_posix().lstrip("/"))
        with self.assertRaisesRegex(R11AG2ApprovalError, "root anchor is ambiguous"):
            validate(ambiguous)

    def test_path_traversal_noncanonical_and_non_directory_components_fail_closed(self) -> None:
        unsafe = (
            "",
            ".",
            "../outside",
            "a/../../outside",
            "/tmp/outside",
            "a//b",
            "a/./b",
            "a/",
            "a\\b",
            "a\x00b",
        )
        for relative in unsafe:
            with self.subTest(relative=repr(relative)):
                with self.assertRaisesRegex(
                    R11AG2ApprovalError, "unsafe|non-canonical"
                ):
                    approval._inspect_path(ROOT, relative, allow_missing=True)

        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        archive = repository / "research/archive_inventory"
        backup = archive.with_name("archive_inventory__g2_real")
        archive.rename(backup)
        archive.write_text("not a directory\n", encoding="utf-8")
        try:
            with self.assertRaisesRegex(R11AG2ApprovalError, "non-directory path component"):
                validate(repository)
        finally:
            archive.unlink()
            backup.rename(archive)

        fifo = repository / "research/archive_inventory/r11a_g1/R11A_RUNTIME_AUTHORITY.py"
        os.mkfifo(fifo)
        try:
            with self.assertRaisesRegex(
                R11AG2ApprovalError, "unsupported repository entry type"
            ):
                validate(repository)
        finally:
            fifo.unlink()


if __name__ == "__main__":
    unittest.main()
