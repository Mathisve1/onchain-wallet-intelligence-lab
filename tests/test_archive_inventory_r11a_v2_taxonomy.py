from __future__ import annotations

import json
import unittest

from research.archive_inventory.r11a_v2_implementation import identity, taxonomy


def source(ordinal: int, hour: str) -> identity.SourceObject:
    return identity.SourceObject(
        object_ordinal_zero_based=ordinal,
        object_key=f"node_fills_by_block/hourly/20250728/{ordinal}.lz4",
        compressed_sha256=f"{ordinal + 1:064x}",
        path_hour_utc=hour,
    )


def fill(*, coin: object = "BTC", tid: object = 7, side: str = "A", px: str = "100", time: int = 1) -> dict:
    return {
        "coin": coin,
        "tid": tid,
        "time": time,
        "side": side,
        "px": px,
        "sz": "1",
        "closedPnl": "0",
        "crossed": False,
        "liquidation": None,
    }


def block(src: identity.SourceObject, *, record: int, block_number: int, block_time: str, events: list[list[object]]) -> identity.BlockObservation:
    raw = json.dumps({
        "local_time": block_time,
        "block_time": block_time,
        "block_number": block_number,
        "events": events,
    }, separators=(",", ":")).encode()
    return identity.parse_block_record(raw, source=src, record_ordinal_zero_based=record)


W1 = "0x" + "1" * 40
W2 = "0x" + "2" * 40
W3 = "0x" + "3" * 40


class R11AV2TaxonomyTests(unittest.TestCase):
    def test_scope_false_positive_is_group_wide_and_pair_proven(self) -> None:
        first = block(source(0, "2025-07-28T00:00:00Z"), record=0, block_number=10, block_time="2025-07-28T00:00:01.000", events=[[W1, fill(tid=7, side="A", time=1)], [W2, fill(tid=7, side="B", time=1)]])
        second = block(source(1, "2025-07-28T01:00:00Z"), record=0, block_number=11, block_time="2025-07-28T01:00:01.000", events=[[W1, fill(tid=7, side="A", time=2)], [W3, fill(tid=7, side="B", time=2)]])
        key = taxonomy.weak_key_bytes(first.observations[0])
        assert key is not None
        report = taxonomy.classify([first, second], repeated_weak_keys={key}, repeated_block_numbers=set(), selected_object_keys={first.source.object_key, second.source.object_key})
        legacy = [row for row in report.taxonomy_units if row["unit_universe"] == taxonomy.UNIT_LEGACY]
        self.assertEqual(len(legacy), 1)
        self.assertEqual(legacy[0]["primary_taxon"], taxonomy.Taxon.TID_SCOPE_FALSE_POSITIVE.value)
        protocol = [row for row in report.taxonomy_units if row["unit_universe"] == taxonomy.UNIT_PROTOCOL]
        self.assertEqual(len(protocol), 2)
        self.assertTrue(all(row["primary_taxon"] == taxonomy.Taxon.EXPECTED_COUNTERPARTY_PAIR.value for row in protocol))
        self.assertEqual(len(report.pair_proofs), 2)
        self.assertTrue(report.all_proof_references_resolve)
        self.assertTrue(report.complete_taxonomy)

    def test_exact_block_replay_proves_wallet_fill_reobservation(self) -> None:
        events = [[W1, fill(tid=9, side="A", time=3)], [W2, fill(tid=9, side="B", time=3)]]
        first = block(source(0, "2025-07-28T00:00:00Z"), record=0, block_number=99, block_time="2025-07-28T00:00:03.000", events=events)
        second = block(source(1, "2025-07-28T01:00:00Z"), record=0, block_number=99, block_time="2025-07-28T00:00:03.000", events=events)
        keys = {taxonomy.weak_key_bytes(first.observations[0]), taxonomy.weak_key_bytes(first.observations[1])}
        self.assertNotIn(None, keys)
        report = taxonomy.classify([first, second], repeated_weak_keys={key for key in keys if key is not None}, repeated_block_numbers={99}, selected_object_keys={first.source.object_key, second.source.object_key})
        legacy = [row for row in report.taxonomy_units if row["unit_universe"] == taxonomy.UNIT_LEGACY]
        self.assertEqual(len(legacy), 2)
        self.assertTrue(all(row["primary_taxon"] == taxonomy.Taxon.EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY.value for row in legacy))
        blocks = [row for row in report.taxonomy_units if row["unit_universe"] == taxonomy.UNIT_BLOCK]
        self.assertEqual(blocks[0]["primary_taxon"], taxonomy.Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS.value)
        self.assertEqual(len(report.replay_proofs), 1)
        self.assertTrue(report.complete_taxonomy)

    def test_conflicting_user_fill_uses_complete_subgroup(self) -> None:
        first = block(source(0, "2025-07-28T00:00:00Z"), record=0, block_number=1, block_time="2025-07-28T00:00:01.000", events=[[W1, fill(tid=5, side="A", px="100", time=1)], [W2, fill(tid=5, side="B", px="100", time=1)]])
        second = block(source(1, "2025-07-28T01:00:00Z"), record=0, block_number=2, block_time="2025-07-28T00:00:01.000", events=[[W1, fill(tid=5, side="A", px="101", time=1)], [W2, fill(tid=5, side="B", px="101", time=1)]])
        key = taxonomy.weak_key_bytes(first.observations[0])
        assert key is not None
        report = taxonomy.classify([first, second], repeated_weak_keys={key}, repeated_block_numbers=set(), selected_object_keys={first.source.object_key, second.source.object_key})
        legacy = [row for row in report.taxonomy_units if row["unit_universe"] == taxonomy.UNIT_LEGACY]
        self.assertEqual(legacy[0]["primary_taxon"], taxonomy.Taxon.CONFLICTING_USER_FILL.value)

    def test_intra_block_repeat_detects_nonfirst_subgroup_member(self) -> None:
        repeated = fill(tid=12, side="A", time=4)
        only = block(source(0, "2025-07-28T00:00:00Z"), record=0, block_number=4, block_time="2025-07-28T00:00:04.000", events=[[W1, repeated], [W2, fill(tid=12, side="B", time=4)], [W1, repeated]])
        key = taxonomy.weak_key_bytes(only.observations[0])
        assert key is not None
        report = taxonomy.classify([only], repeated_weak_keys={key}, repeated_block_numbers=set(), selected_object_keys={only.source.object_key})
        legacy = [row for row in report.taxonomy_units if row["unit_universe"] == taxonomy.UNIT_LEGACY]
        self.assertEqual(len(legacy), 1)
        self.assertEqual(legacy[0]["primary_taxon"], taxonomy.Taxon.INTRA_BLOCK_REPEAT.value)
        self.assertFalse(report.complete_taxonomy)

    def test_tid_schema_violation_is_retained_without_coercion(self) -> None:
        first = block(source(0, "2025-07-28T00:00:00Z"), record=0, block_number=1, block_time="2025-07-28T00:00:01.000", events=[[W1, fill(tid="x", side="A", time=1)]])
        second = block(source(1, "2025-07-28T01:00:00Z"), record=0, block_number=2, block_time="2025-07-28T01:00:01.000", events=[[W1, fill(tid="x", side="A", time=2)]])
        key = taxonomy.weak_key_bytes(first.observations[0])
        assert key is not None
        report = taxonomy.classify([first, second], repeated_weak_keys={key}, repeated_block_numbers=set(), selected_object_keys={first.source.object_key, second.source.object_key})
        legacy = [row for row in report.taxonomy_units if row["unit_universe"] == taxonomy.UNIT_LEGACY]
        self.assertEqual(legacy[0]["primary_taxon"], taxonomy.Taxon.TID_SCHEMA_VIOLATION.value)
        schema_units = [row for row in report.taxonomy_units if row["unit_universe"] == taxonomy.UNIT_TID_SCHEMA]
        self.assertEqual(len(schema_units), 2)
        self.assertEqual(len(report.schema_rows), 2)

    def test_input_order_does_not_change_scientific_commitments(self) -> None:
        first = block(source(0, "2025-07-28T00:00:00Z"), record=0, block_number=10, block_time="2025-07-28T00:00:01.000", events=[[W1, fill(tid=7, side="A", time=1)], [W2, fill(tid=7, side="B", time=1)]])
        second = block(source(1, "2025-07-28T01:00:00Z"), record=0, block_number=11, block_time="2025-07-28T01:00:01.000", events=[[W1, fill(tid=7, side="A", time=2)], [W3, fill(tid=7, side="B", time=2)]])
        key = taxonomy.weak_key_bytes(first.observations[0])
        assert key is not None
        kwargs = {"repeated_weak_keys": {key}, "repeated_block_numbers": set(), "selected_object_keys": {first.source.object_key, second.source.object_key}}
        left = taxonomy.classify([first, second], **kwargs)
        right = taxonomy.classify([second, first], **kwargs)
        self.assertEqual(left.taxonomy_units, right.taxonomy_units)
        self.assertEqual(left.duplicate_rows, right.duplicate_rows)
        self.assertEqual(left.conservation, right.conservation)


if __name__ == "__main__":
    unittest.main()
