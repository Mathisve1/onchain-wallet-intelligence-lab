from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from research.archive_inventory.r11a_corrective_core import canonical, model, output, storage, taxonomy


def source(index: int, day: int = 28, hour: int | None = None) -> model.SourceObject:
    hour = index if hour is None else hour
    return model.SourceObject(
        index,
        f"node_fills_by_block/hourly/202507{day:02d}/{hour}.lz4",
        f"{index + 1:064x}",
        f"2025-07-{day:02d}T{hour:02d}:00:00Z",
    )


def event(wallet: str, *, tid: object = 7, coin: object = "BTC", side: str = "A", time: int = 1, px: str = "100", sz: str = "1", pnl: str = "0", crossed: bool = False, extra: dict[str, object] | None = None) -> list[object]:
    fill: dict[str, object] = {
        "coin": coin,
        "side": side,
        "time": time,
        "px": px,
        "sz": sz,
        "closedPnl": pnl,
        "tid": tid,
        "crossed": crossed,
        "liquidation": None,
    }
    if extra:
        fill.update(extra)
    return [wallet, fill]


def block(src: model.SourceObject, record: int, number: int, block_time: str, events: list[list[object]]) -> model.BlockObservation:
    raw = canonical.canonical_json_bytes({
        "local_time": src.path_hour_utc.replace("Z", ".000"),
        "block_time": block_time,
        "block_number": number,
        "events": events,
    })
    return model.parse_block_record(raw, src, record)


COMPLETE_SCOPE = taxonomy.ScopeEvidence(
    selected_object_count=72,
    complete_object_count=72,
    complete_utc_day_count=3,
    expected_utc_day_count=3,
    all_object_two_pass_commitments_match=True,
    all_512_reducer_rows_complete=True,
    all_resource_caps_respected=True,
    scientific_output_logical_status="COMPLETE",
)


class CanonicalTests(unittest.TestCase):
    def test_decimal_integral_exponent_never_uses_context_quantize(self) -> None:
        huge = Decimal("1e+10000")
        token = canonical.decimal_fixed_token(huge)
        self.assertEqual(len(token), 10001)
        self.assertTrue(token.startswith("1"))
        self.assertEqual(canonical.decimal_fixed_token(Decimal("-0e+999")), "0")

    def test_mapping_key_order_is_utf8_canonical(self) -> None:
        left = {"z": 1, "ä": 2, "a": {"y": 1, "x": 2}}
        right = {"a": {"x": 2, "y": 1}, "ä": 2, "z": 1}
        self.assertEqual(canonical.canonical_json_bytes(left), canonical.canonical_json_bytes(right))
        self.assertEqual(canonical.typed_bytes(left), canonical.typed_bytes(right))

    def test_strict_json_rejects_duplicate_nonfinite_and_binary_float(self) -> None:
        with self.assertRaises(canonical.CanonicalError):
            canonical.strict_json_loads(b'{"a":1,"a":2}')
        with self.assertRaises(canonical.CanonicalError):
            canonical.strict_json_loads(b'{"a":NaN}')
        with self.assertRaises(canonical.CanonicalError):
            canonical.canonical_json_bytes(1.5)


class IdentityTests(unittest.TestCase):
    def test_payload_snapshot_is_deeply_immutable_bytes(self) -> None:
        wallet = "0x" + "1" * 40
        src = source(0)
        raw_event = event(wallet, extra={"nested": {"b": 2, "a": 1}})
        row = block(src, 0, 1, "2025-07-28T00:00:01.000", [raw_event]).observations[0]
        before = row.full_event_canonical_bytes
        raw_event[1]["nested"] = {"changed": True}  # type: ignore[index]
        self.assertEqual(row.full_event_canonical_bytes, before)
        self.assertIsInstance(row.full_fill_canonical_bytes, bytes)

    def test_four_identity_layers_remain_separate(self) -> None:
        wallet = "0x" + "2" * 40
        row = block(source(0), 0, 5, "2025-07-28T00:00:01.000", [event(wallet)]).observations[0]
        self.assertEqual(len(row.locator.as_mapping()), 4)
        self.assertEqual(row.protocol_trade_identity, ("2025-07-28T00:00:01.000", "BTC", 7))
        self.assertEqual(row.wallet_fill_identity, (wallet, "2025-07-28T00:00:01.000", "BTC", 7))
        self.assertEqual(row.legacy_weak_key, (wallet, ("int", "7")))


class TaxonomyTests(unittest.TestCase):
    def test_tid_scope_false_positive_requires_clean_complete_group(self) -> None:
        wallet = "0x" + "3" * 40
        blocks = [
            block(source(0), 0, 10, "2025-07-28T00:00:01.000", [event(wallet, coin="BTC", tid=7)]),
            block(source(1), 0, 11, "2025-07-28T01:00:01.000", [event(wallet, coin="ETH", tid=7)]),
        ]
        report = taxonomy.classify(blocks, COMPLETE_SCOPE)
        repeat_units = [u for u in report.taxonomy_units if u["taxonomy_unit_type"] == "LEGACY_REPEAT_OCCURRENCE"]
        self.assertEqual([u["primary_taxon"] for u in repeat_units], [taxonomy.Taxon.TID_SCOPE_FALSE_POSITIVE.value])

        invalid = [
            block(source(0), 0, 10, "2025-07-28T00:00:01.000", [event(wallet, coin="BTC", tid=7)]),
            block(source(1), 0, 11, "2025-07-28T01:00:01.000", [event(wallet, coin="", tid=7)]),
        ]
        report = taxonomy.classify(invalid, COMPLETE_SCOPE)
        repeat_units = [u for u in report.taxonomy_units if u["taxonomy_unit_type"] == "LEGACY_REPEAT_OCCURRENCE"]
        self.assertEqual(repeat_units[0]["primary_taxon"], taxonomy.Taxon.UNCLASSIFIABLE.value)

    def test_intra_block_repeat_is_group_wide_not_group_first_only(self) -> None:
        wallet = "0x" + "4" * 40
        first = block(source(0), 0, 1, "2025-07-28T00:00:01.000", [event(wallet, coin="BTC", tid=9)])
        later = block(
            source(1), 0, 2, "2025-07-28T01:00:01.000",
            [event(wallet, coin="ETH", tid=9), event(wallet, coin="ETH", tid=9)],
        )
        report = taxonomy.classify([first, later], COMPLETE_SCOPE)
        repeat_units = [u for u in report.taxonomy_units if u["taxonomy_unit_type"] == "LEGACY_REPEAT_OCCURRENCE"]
        self.assertEqual(len(repeat_units), 2)
        self.assertTrue(all(u["primary_taxon"] == taxonomy.Taxon.INTRA_BLOCK_REPEAT.value for u in repeat_units))

    def test_replay_reobservation_uses_full_wallet_group_all_locators(self) -> None:
        wallet = "0x" + "5" * 40
        first = block(source(0), 0, 1, "2025-07-28T00:00:01.000", [event(wallet, coin="BTC", tid=10)])
        replay_events = [event(wallet, coin="ETH", tid=10)]
        replay_a = block(source(1), 0, 77, "2025-07-28T01:00:01.000", replay_events)
        replay_b = block(source(2), 0, 77, "2025-07-28T01:00:01.000", replay_events)
        report = taxonomy.classify([first, replay_a, replay_b], COMPLETE_SCOPE)
        repeat_units = [u for u in report.taxonomy_units if u["taxonomy_unit_type"] == "LEGACY_REPEAT_OCCURRENCE"]
        self.assertEqual(len(repeat_units), 2)
        self.assertTrue(all(u["primary_taxon"] == taxonomy.Taxon.EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY.value for u in repeat_units))
        self.assertTrue(all(u["exact_block_replay_proof_id"] for u in repeat_units))

    def test_conflicting_user_fill_precedes_intra_or_replay(self) -> None:
        wallet = "0x" + "6" * 40
        rows = block(
            source(0), 0, 9, "2025-07-28T00:00:01.000",
            [event(wallet, tid=11, px="100"), event(wallet, tid=11, px="101")],
        )
        report = taxonomy.classify([rows], COMPLETE_SCOPE)
        repeat_units = [u for u in report.taxonomy_units if u["taxonomy_unit_type"] == "LEGACY_REPEAT_OCCURRENCE"]
        self.assertEqual(repeat_units[0]["primary_taxon"], taxonomy.Taxon.CONFLICTING_USER_FILL.value)

    def test_complete_terminal_requires_exact_scope_conservation_fks_and_zero_unclassifiable(self) -> None:
        report = taxonomy.classify([], COMPLETE_SCOPE)
        self.assertNotEqual(report.terminal_class, taxonomy.TerminalClass.COMPLETE)
        incomplete_scope = taxonomy.ScopeEvidence(72, 71, 3, 3, True, True, True, "COMPLETE")
        report = taxonomy.classify([], incomplete_scope)
        self.assertEqual(report.terminal_class, taxonomy.TerminalClass.INCOMPLETE)

    def test_per_universe_unclassifiable_counts_are_authoritative(self) -> None:
        wallet = "0x" + "7" * 40
        rows = [
            block(source(0), 0, 1, "2025-07-28T00:00:01.000", [event(wallet, tid=12)]),
            block(source(1), 0, 2, "2025-07-28T01:00:01.000", [event(wallet, tid=12)]),
        ]
        report = taxonomy.classify(rows, COMPLETE_SCOPE)
        protocol = report.unclassifiable_by_unit_universe["PROTOCOL_MATCHED_TRADE_GROUP_PER_RAW_BLOCK_OCCURRENCE"]
        self.assertGreater(protocol["group_count"], 0)
        self.assertEqual(report.terminal_class, taxonomy.TerminalClass.INCOMPLETE)

    def test_foreign_key_claim_is_computed_not_hard_coded(self) -> None:
        wallet = "0x" + "8" * 40
        rows = [
            block(source(0), 0, 1, "2025-07-28T00:00:01.000", [event(wallet, tid=13)]),
            block(source(1), 0, 2, "2025-07-28T01:00:01.000", [event(wallet, tid=13, coin="ETH")]),
        ]
        report = taxonomy.classify(rows, COMPLETE_SCOPE)
        self.assertTrue(report.all_proof_references_resolve)
        tampered = [dict(row) for row in report.duplicate_rows]
        tampered[-1]["taxonomy_unit_id"] = "f" * 64
        self.assertFalse(taxonomy._validate_foreign_keys(
            units=report.taxonomy_units,
            duplicate_rows=tampered,
            block_rows=report.block_rows,
            replay_proofs=report.replay_proofs,
            pair_proofs=report.pair_proofs,
            schema_rows=report.schema_rows,
            protocol_member_rows=report.protocol_member_rows,
        ))


class StorageTests(unittest.TestCase):
    def _workspace(self, root: Path, sequence: list[int] | None = None) -> storage.Workspace:
        if sequence is None:
            guard = storage.RuntimeGuard(100, 10, 5)
        else:
            iterator = iter(sequence)
            guard = storage.RuntimeGuard(100, 10, 5, monotonic_ns=lambda: next(iterator))
        return storage.Workspace(root, 32 * 1024 * 1024, guard)

    def test_external_sort_conserves_strong_order_independent_multiset(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = self._workspace(Path(td) / "work")
            source_path = workspace.root / "source.frames"
            with storage.ReservedWriter(source_path, workspace) as writer:
                for record in (b"c", b"a", b"b", b"a"):
                    storage.write_frame(writer, record)
            result = storage.ExternalSorter(workspace, 16).sort(source_path, workspace.root / "sorted.frames")
            self.assertEqual(list(storage.read_frames(result.destination)), [b"a", b"a", b"b", b"c"])
            self.assertEqual(result.source_commitment, result.destination_commitment)
            self.assertNotEqual(result.destination_commitment.add(b"extra"), result.source_commitment)

    def test_group_spools_large_group_to_disk_without_losing_multiplicity(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = self._workspace(Path(td) / "work")
            path = workspace.root / "sorted.frames"
            with storage.ReservedWriter(path, workspace) as writer:
                for record in (b"a1", b"a2", b"a3", b"b1"):
                    storage.write_frame(writer, record)
            seen = []
            for group in storage.group_sorted_records(path, workspace=workspace, key_of=lambda row: row[:1], maximum_in_memory_group_bytes=2):
                seen.append((group.equality_key, group.multiplicity, list(group.records())))
            self.assertEqual(seen[0], (b"a", 3, [b"a1", b"a2", b"a3"]))

    def test_atomic_post_rename_failure_removes_final_directory(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "work"
            workspace = self._workspace(root)
            final = root / "artifact"
            original = workspace.checkpoint

            def failing(phase: str, *, packaging: bool = False) -> int:
                if phase == "after atomic artifact rename":
                    raise storage.StorageError("forced post-rename failure")
                return original(phase, packaging=packaging)

            workspace.checkpoint = failing  # type: ignore[method-assign]
            with self.assertRaises(storage.StorageError):
                with storage.AtomicOutputDirectory(workspace, final) as atomic:
                    (atomic.staging / "x").write_bytes(b"x")
                    atomic.commit()
            self.assertFalse(final.exists())


class FailureArtifactTests(unittest.TestCase):
    def test_failure_package_has_exact_empty_science_and_true_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "work"
            workspace = storage.Workspace(root, 32 * 1024 * 1024, storage.RuntimeGuard(100, 10, 5))
            final = root / "artifact"
            output.build_failure_package(
                workspace=workspace,
                final_directory=final,
                context={"status": "FAIL"},
                object_rows=[],
                reducer_rows=[],
                stop_rows=[{"stop": "TEST"}],
                resource_rows=[],
                result={"terminal": "INCOMPLETE"},
                return_code=21,
                artifact_limit_bytes=8 * 1024 * 1024,
            )
            output.validate_empty_science_package(final)
            self.assertEqual((final / "r11a-wallet-features.ndjson").read_bytes(), b"")


class GovernanceTests(unittest.TestCase):
    def test_dedicated_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, "governance/validate_r11a_corrective_core.py"],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R11A_CORRECTIVE_CORE_VALID_INERT_NO_EXECUTION", completed.stdout)


if __name__ == "__main__":
    unittest.main()
