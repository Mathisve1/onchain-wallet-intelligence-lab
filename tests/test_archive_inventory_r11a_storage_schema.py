from __future__ import annotations

import dataclasses
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from research.archive_inventory.r11a_implementation import limits, schema, storage


class R11AStorageTests(unittest.TestCase):
    def test_partition_routing_uses_hash_only_for_routing_and_full_key_for_equality(self) -> None:
        key = b"complete-equality-key"
        ordinal = storage.PartitionSet.partition_ordinal(key)
        self.assertEqual(ordinal, hashlib.sha256(key).digest()[0])
        encoded = storage.PartitionSet.encode_record(key, b"payload")
        self.assertEqual(storage.PartitionSet.decode_record(encoded), (key, b"payload"))
        with self.assertRaises(storage.R11AStorageError):
            storage.PartitionSet.partition_ordinal(b"")

    def test_external_sort_is_deterministic_and_preserves_complete_record_multiset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.frames"
            records = [b"z", b"a", b"a", b"m", b"longer-record"]
            with storage.FramedWriter(source) as writer:
                for record in records:
                    writer.write(record)
            destination = root / "sorted.frames"
            result = storage.external_sort_framed(
                source,
                destination,
                temporary_root=root / "sort",
                memory_limit_bytes=10,
            )
            self.assertEqual(result.record_count, len(records))
            self.assertEqual(list(storage.iter_framed(destination)), sorted(records))
            self.assertEqual(result.logical_input_bytes, sum(map(len, records)))
            self.assertEqual(
                result.sorted_record_stream_sha256,
                hashlib.sha256(b"".join(sorted(records))).hexdigest(),
            )

    def test_group_sorted_records_keeps_multiplicity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "groups.frames"
            records = [
                storage.PartitionSet.encode_record(b"a", b"1"),
                storage.PartitionSet.encode_record(b"a", b"2"),
                storage.PartitionSet.encode_record(b"b", b"3"),
            ]
            with storage.FramedWriter(path) as writer:
                for record in records:
                    writer.write(record)
            self.assertEqual(
                list(storage.group_sorted_records(path)),
                [(b"a", (b"1", b"2")), (b"b", (b"3",))],
            )

    def test_truncated_frame_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.frames"
            path.write_bytes(b"\x00\x00\x00\x05abc")
            with self.assertRaises(storage.R11AStorageError):
                list(storage.iter_framed(path))

    def test_workspace_cap_is_checked_after_mutating_boundary(self) -> None:
        tiny = dataclasses.replace(
            limits.DEFAULT_LIMITS,
            maximum_ephemeral_workspace_bytes=1,
            minimum_free_workspace_bytes_before_oidc=2,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "workspace"
            meter = storage.WorkspaceMeter(root, tiny)
            meter.bootstrap()
            (root / "data").write_bytes(b"x" * 4096)
            with self.assertRaises(storage.R11AStorageError):
                meter.checkpoint("synthetic cap overflow")

    def test_atomic_output_never_exposes_partial_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            final = Path(directory) / "artifact"
            atomic = storage.AtomicOutputDirectory(final)
            with self.assertRaises(RuntimeError):
                with atomic as staging:
                    (staging / "partial").write_text("partial", encoding="utf-8")
                    raise RuntimeError("stop")
            self.assertFalse(final.exists())
            self.assertFalse(final.with_name("artifact.staging").exists())

    def test_atomic_output_commit_is_all_or_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            final = Path(directory) / "artifact"
            atomic = storage.AtomicOutputDirectory(final)
            with atomic as staging:
                (staging / "complete").write_text("complete", encoding="utf-8")
                atomic.commit()
            self.assertEqual((final / "complete").read_text(), "complete")


class R11ASchemaTests(unittest.TestCase):
    def test_deterministic_json_rejects_binary_float_and_orders_mapping(self) -> None:
        first = schema.deterministic_json_document({"b": 2, "a": 1})
        second = schema.deterministic_json_document({"a": 1, "b": 2})
        self.assertEqual(first, second)
        self.assertEqual(first, b'{"a":1,"b":2}\n')
        with self.assertRaises(schema.R11ASchemaError):
            schema.deterministic_json_document({"x": 1.5})

    def test_deterministic_ndjson_has_final_newline_and_empty_sequence_is_zero_bytes(self) -> None:
        self.assertEqual(schema.deterministic_ndjson([]), b"")
        rendered = schema.deterministic_ndjson([{"x": 1}, {"x": 2}])
        self.assertEqual(rendered, b'{"x":1}\n{"x":2}\n')

    def test_hash_manifest_covers_every_preboundary_file_once(self) -> None:
        files = {"a.json": b"a", "b.ndjson": b"b\n", "empty": b""}
        manifest = schema.render_hash_manifest(files)
        schema.verify_hash_manifest(manifest, files)
        rows = manifest.decode().splitlines()
        self.assertEqual(len(rows), 3)
        self.assertEqual([row.split("  ", 1)[1] for row in rows], sorted(files))
        with self.assertRaises(schema.R11ASchemaError):
            schema.verify_hash_manifest(manifest + manifest.splitlines(keepends=True)[0], files)

    def test_package_boundary_is_exactly_1024_bytes_and_self_consistent(self) -> None:
        boundary = schema.render_package_boundary(
            scientific_output_bytes=100,
            other_metadata_bytes_excluding_this_record=200,
            reserved_metadata_limit_bytes=4_194_304,
            artifact_limit_bytes=134_217_728,
            preupload_elapsed_runtime_milliseconds=1_000,
            hard_runtime_limit_milliseconds=21_600_000,
            minimum_upload_window_milliseconds=60_000,
            preupload_peak_workspace_bytes=1_000,
            filesystem_allocation_unit_bytes=4_096,
            boundary_overwrite_allocation_reservation_bytes=8_192,
            workspace_limit_bytes=5_368_709_120,
        )
        self.assertEqual(len(boundary), 1024)
        self.assertTrue(boundary.endswith(b"\n"))
        schema.verify_package_boundary(boundary)
        mutated = bytearray(boundary)
        mutated[0] = ord("X")
        with self.assertRaises(schema.R11ASchemaError):
            schema.verify_package_boundary(bytes(mutated))

    def test_artifact_registry_has_unique_safe_paths_and_empty_wallet_output(self) -> None:
        paths = [path for _, path in schema.ALL_CONTAINERS]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertTrue(all("/" not in path and ".." not in path for path in paths))
        self.assertIn(("empty_forbidden_wallet_feature_output", "r11a-wallet-features.ndjson"), schema.METADATA_CONTAINERS)


if __name__ == "__main__":
    unittest.main()
