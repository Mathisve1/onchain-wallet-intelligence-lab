from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from governance import validate_r11a_g2_owner_approval as approval
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
        temporary = tempfile.TemporaryDirectory()
        destination = Path(temporary.name) / "repository"
        shutil.copytree(
            ROOT,
            destination,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", "*.pyo"),
        )
        return temporary, destination

    def record_copy(self) -> tuple[tempfile.TemporaryDirectory[str], Path, Path, bytes, dict]:
        temporary, repository = self.copy_repository()
        path = repository / approval.APPROVAL_JSON
        raw = path.read_bytes()
        value = json.loads(raw)
        return temporary, repository, path, raw, value

    def write_record(self, path: Path, value: dict) -> None:
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def test_canonical_record_passes_and_text_is_exact(self) -> None:
        record = validate(ROOT)
        canonical = (ROOT / approval.APPROVAL_TEXT).read_bytes()
        source = (ROOT / approval.SOURCE_STATEMENT).read_bytes()
        self.assertEqual(canonical, source)
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), approval.STATEMENT_SHA)
        self.assertTrue(canonical.endswith(b"\n"))
        self.assertFalse(record["execution_authorized_by_this_approval"])
        self.assertTrue(record["owner_approval_present"])

    def test_every_scalar_leaf_type_valid_mutation_fails_closed(self) -> None:
        temporary, repository, path, raw, canonical = self.record_copy()
        self.addCleanup(temporary.cleanup)
        leaves = scalar_leaf_paths(canonical)
        self.assertEqual(len(leaves), 136)
        for leaf in leaves:
            with self.subTest(path=".".join(leaf)):
                mutated = copy.deepcopy(canonical)
                set_path(mutated, leaf, contradictory(get_path(canonical, leaf)))
                self.write_record(path, mutated)
                with self.assertRaises(R11AG2ApprovalError):
                    validate(repository)
                path.write_bytes(raw)

    def test_every_scalar_leaf_missing_and_null_fails_closed(self) -> None:
        temporary, repository, path, raw, canonical = self.record_copy()
        self.addCleanup(temporary.cleanup)
        for leaf in scalar_leaf_paths(canonical):
            with self.subTest(kind="missing", path=".".join(leaf)):
                mutated = copy.deepcopy(canonical)
                delete_path(mutated, leaf)
                self.write_record(path, mutated)
                with self.assertRaises(R11AG2ApprovalError):
                    validate(repository)
                path.write_bytes(raw)
            with self.subTest(kind="null", path=".".join(leaf)):
                mutated = copy.deepcopy(canonical)
                set_path(mutated, leaf, None)
                self.write_record(path, mutated)
                with self.assertRaises(R11AG2ApprovalError):
                    validate(repository)
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
                self.write_record(path, mutated)
                with self.assertRaises(R11AG2ApprovalError):
                    validate(repository)
                path.write_bytes(raw)

        for object_path in object_paths(canonical):
            with self.subTest(unexpected_at=".".join(object_path) or "root"):
                mutated = copy.deepcopy(canonical)
                target = get_path(mutated, object_path) if object_path else mutated
                if not isinstance(target, dict):
                    raise TypeError(object_path)
                target["unexpected_authority_bearing_key"] = False
                self.write_record(path, mutated)
                with self.assertRaises(R11AG2ApprovalError):
                    validate(repository)
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
        with self.assertRaisesRegex(R11AG2ApprovalError, "duplicate JSON key"):
            validate(repository)

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

    def test_text_tamper_missing_file_and_symlink_fail_closed(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        path = repository / approval.APPROVAL_TEXT
        raw = path.read_bytes()
        path.write_bytes(raw + b"changed\n")
        with self.assertRaisesRegex(R11AG2ApprovalError, "approval text raw hash drift"):
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
        self.write_record(path, mutated)
        with self.assertRaises(R11AG2ApprovalError):
            validate(repository)

        mutated = copy.deepcopy(canonical)
        mutated["approved_bound_files"][original_path] = "0" * 64
        self.write_record(path, mutated)
        with self.assertRaises(R11AG2ApprovalError):
            validate(repository)
        path.write_bytes(raw)

    def test_runtime_evidence_workflow_and_extra_record_are_rejected(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        for relative in approval.RUNTIME_EVIDENCE_PATHS:
            with self.subTest(path=relative):
                path = repository / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}\n", encoding="utf-8")
                with self.assertRaisesRegex(R11AG2ApprovalError, "runtime evidence"):
                    validate(repository)
                path.unlink()

        workflow = repository / approval.INSTALLED_WORKFLOW
        workflow.write_text("name: unauthorized\n", encoding="utf-8")
        with self.assertRaisesRegex(R11AG2ApprovalError, "runtime workflow"):
            validate(repository)
        workflow.unlink()

        extra = repository / approval.APPROVAL_DIR / "EXTRA_AUTHORITY.json"
        extra.write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(R11AG2ApprovalError, "file set drift"):
            validate(repository)
        extra.unlink()

        unexpected_directory = repository / approval.APPROVAL_DIR / "extra_authority"
        unexpected_directory.mkdir()
        with self.assertRaisesRegex(R11AG2ApprovalError, "file set drift"):
            validate(repository)


if __name__ == "__main__":
    unittest.main()
