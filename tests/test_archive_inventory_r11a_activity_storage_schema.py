from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from research.archive_inventory.r11a_implementation import activity, schema, storage


WALLET = "0x" + "a" * 40


class R11AActivityTests(unittest.TestCase):
    def test_absent_and_existing_reads_never_mutate_state(self) -> None:
        tracker = activity.ActivityTracker()
        self.assertEqual(tracker.wallet_count(), 0)
        self.assertIsNone(tracker.snapshot(WALLET))
        self.assertFalse(tracker.contains(WALLET))
        self.assertEqual(tracker.wallet_count(), 0)

        tracker.record(
            WALLET,
            path_hour_utc="2025-07-28T00:00:00Z",
            block_time_exact="2025-07-28T00:00:00.100",
            fill_time_ms=1_753_660_800_100,
        )
        first = tracker.snapshot(WALLET)
        second = tracker.snapshot(WALLET)
        self.assertEqual(first, second)
        self.assertEqual(tracker.wallet_count(), 1)
        self.assertEqual(first.path_days, ("2025-07-28",))
        self.assertEqual(first.path_hours, ("2025-07-28T00:00:00Z",))

    def test_only_explicit_record_adds_activity(self) -> None:
        tracker = activity.ActivityTracker()
        tracker.record_many(
            (
                (WALLET, "2025-07-28T00:00:00Z", "b0", 1),
                (WALLET, "2025-07-29T00:00:00Z", "b1", 2),
            )
        )
        snapshot = tracker.snapshot(WALLET)
        self.assertEqual(snapshot.path_days, ("2025-07-28", "2025-07-29"))
        self.assertEqual(snapshot.fill_times_ms, (1, 2))
        mapping = tracker.immutable_mapping()
        with self.assertRaises(TypeError):
            mapping[WALLET] = snapshot

    def test_invalid_activity_writes_fail(self) -> None:
        tracker = activity.ActivityTracker()
        for wallet, hour, block_time, fill_time in (
            ("0xABC", "2025-07-28T00:00:00Z", "b", 1),
            (WALLET, "2025-07-28 00:00:00", "b", 1),
            (WALLET, "2025-07-28T00:00:00Z", "", 1),
            (WALLET, "2025-07-28T00:00:00Z", "b", -1),
        ):
            with self.subTest(wallet=wallet, hour=hour), self.assertRaises(activity.ActivityError):
                tracker.record(
                    wallet,
                    path_hour_utc=hour,
                    block_time_exact=block_time,
                    fill_time_ms=fill_time,
                )
        self.assertEqual(tracker.wallet_count(), 0)

    def test_historical_read_mutation_hooks_are_absent(self) -> None:
        self.assertNotIn("__getitem__", activity.ActivityTracker.__dict__)
        self.assertNotIn("__missing__", activity.ActivityTracker.__dict__)


class R11AStorageTests(unittest.TestCase):
    def test_fixed_partition_external_sort_conserves_exact_record_multiset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = [
                (b"key-b", b"payload-2"),
                (b"key-a", b"payload-3"),
                (b"key-a", b"payload-1"),
                (b"key-c", b"payload-4"),
            ]
            storage.validate_storage_fixture(records, root)

    def test_external_sort_is_deterministic_across_input_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outputs = []
            for run, records in enumerate(
                (
                    [b"c", b"a", b"b", b"a"],
                    [b"a", b"b", b"a", b"c"],
                )
            ):
                source = root / f"input-{run}.frames"
                with storage.FramedWriter(source) as writer:
                    for record in records:
                        writer.write(record)
                destination = root / f"output-{run}.frames"
                result = storage.external_sort_framed(
                    source,
                    destination,
                    temporary_root=root / f"runs-{run}",
                    memory_limit_bytes=6,
                )
                outputs.append((tuple(storage.iter_framed(destination)), result.sorted_record_stream_sha256))
            self.assertEqual(outputs[0], outputs[1])
            self.assertEqual(outputs[0][0], (b"a", b"a", b"b", b"c"))

    def test_atomic_output_cleans_partial_staging_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            final = Path(directory) / "artifact"
            atomic = storage.AtomicOutputDirectory(final)
            with self.assertRaises(RuntimeError):
                with atomic as staging:
                    (staging / "partial.txt").write_text("partial", encoding="utf-8")
                    raise RuntimeError("synthetic failure")
            self.assertFalse(final.exists())
            self.assertFalse(final.with_name("artifact.staging").exists())

    def test_atomic_output_commit_is_one_way(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            final = Path(directory) / "artifact"
            atomic = storage.AtomicOutputDirectory(final)
            with atomic as staging:
                (staging / "result.txt").write_text("complete", encoding="utf-8")
                atomic.commit()
            self.assertEqual((final / "result.txt").read_text(), "complete")


class R11ASchemaTests(unittest.TestCase):
    def test_deterministic_json_has_exact_newline_and_rejects_binary_float(self) -> None:
        data = schema.deterministic_json_document({"b": 2, "a": 1})
        self.assertEqual(data, b'{"b":2,"a":1}\n')
        with self.assertRaises(schema.R11ASchemaError):
            schema.deterministic_json_document({"x": 1.5})

    def test_ndjson_empty_sequence_is_exact_zero_bytes(self) -> None:
        self.assertEqual(schema.deterministic_ndjson(()), b"")
        self.assertEqual(hashlib.sha256(schema.deterministic_ndjson(())).hexdigest(), schema.EMPTY_SHA256)

    def test_hash_manifest_is_complete_sorted_and_tamper_evident(self) -> None:
        files = {
            "r11a-context.json": b"{}\n",
            "r11a-wallet-features.ndjson": b"",
            "r11a.rc": b"0\n",
        }
        manifest = schema.render_hash_manifest(files)
        schema.verify_hash_manifest(manifest, files)
        tampered = dict(files)
        tampered["r11a.rc"] = b"21\n"
        with self.assertRaises(schema.R11ASchemaError):
            schema.verify_hash_manifest(manifest, tampered)

    def test_package_boundary_is_exactly_1024_bytes(self) -> None:
        boundary = schema.render_package_boundary(
            scientific_output_bytes=10,
            other_metadata_bytes_excluding_this_record=20,
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
        schema.verify_package_boundary(boundary)
        with self.assertRaises(schema.R11ASchemaError):
            schema.verify_package_boundary(boundary[:-1])


if __name__ == "__main__":
    unittest.main()
