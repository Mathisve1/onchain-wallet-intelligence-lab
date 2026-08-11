from __future__ import annotations

import dataclasses
import json
import unittest
from decimal import Decimal

from research.archive_inventory.r11a_implementation import diagnostic, identity
from research.archive_inventory.r11a_implementation.limits import DEFAULT_LIMITS


W1 = "0x" + "1" * 40
W2 = "0x" + "2" * 40
W3 = "0x" + "3" * 40


def fill(
    *,
    coin: object = "BTC",
    side: str = "A",
    time: int = 1_753_660_800_100,
    px: str = "100",
    sz: str = "1",
    closed_pnl: str = "0",
    tid: object = 42,
    crossed: bool = False,
    liquidation: object = None,
) -> dict[str, object]:
    return {
        "coin": coin,
        "side": side,
        "time": time,
        "px": px,
        "sz": sz,
        "closedPnl": closed_pnl,
        "tid": tid,
        "crossed": crossed,
        "liquidation": liquidation,
    }


def block(
    *,
    object_ordinal: int,
    block_number: int,
    block_time: str,
    events: list[list[object]],
    record_ordinal: int = 0,
    path_hour: str | None = None,
    object_key: str | None = None,
    sha_character: str | None = None,
) -> identity.BlockObservation:
    if path_hour is None:
        path_hour = f"2025-07-28T{object_ordinal:02d}:00:00Z"
    if object_key is None:
        object_key = f"node_fills_by_block/hourly/20250728/{object_ordinal}.lz4"
    if sha_character is None:
        sha_character = format((object_ordinal % 15) + 1, "x")
    source = identity.SourceObject(
        object_ordinal,
        object_key,
        sha_character * 64,
        path_hour,
    )
    raw = json.dumps(
        {
            "local_time": block_time,
            "block_time": block_time,
            "block_number": block_number,
            "events": events,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    return identity.parse_block_record(
        raw,
        source=source,
        record_ordinal_zero_based=record_ordinal,
    )


def paired_block(
    *,
    object_ordinal: int,
    block_number: int,
    block_time: str,
    wallet: str = W1,
    counterparty: str = W2,
    coin: str = "BTC",
    tid: int = 42,
    px: str = "100",
) -> identity.BlockObservation:
    return block(
        object_ordinal=object_ordinal,
        block_number=block_number,
        block_time=block_time,
        events=[
            [wallet, fill(coin=coin, side="A", tid=tid, px=px)],
            [counterparty, fill(coin=coin, side="B", tid=tid, px=px, crossed=True)],
        ],
    )


class R11AIdentityTests(unittest.TestCase):
    def test_frozen_canonical_serialization_golden_vectors(self) -> None:
        identity.validate_golden_vectors()
        self.assertEqual(identity.canonical_typed_bytes(None).hex(), "4e")
        self.assertEqual(identity.canonical_typed_bytes(Decimal("1.2300")).hex(), "44363a313233652d32")

    def test_strict_json_rejects_duplicate_keys_nonfinite_and_binary_float(self) -> None:
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(identity.R11AIdentityError):
                identity.strict_json_loads(raw)
        with self.assertRaises(identity.R11AIdentityError):
            identity.canonical_typed_bytes(1.25)

    def test_tid_coin_wallet_validation_is_exact_and_noncoercing(self) -> None:
        self.assertEqual(identity.validate_tid(0).status, "VALID_UINT50")
        self.assertEqual(identity.validate_tid((1 << 50) - 1).status, "VALID_UINT50")
        for value in (1 << 50, "42", Decimal("42"), True, None, identity.MISSING):
            with self.subTest(value=value):
                self.assertEqual(identity.validate_tid(value).status, "TID_SCHEMA_VIOLATION")
        self.assertEqual(identity.validate_coin("BTC").canonical_value, "BTC")
        self.assertEqual(identity.validate_coin(" btc ").canonical_value, " btc ")
        self.assertEqual(identity.validate_wallet(W1).canonical_value, W1)
        self.assertEqual(identity.validate_wallet(W1.upper()).status, "WALLET_SCHEMA_VIOLATION")

    def test_four_identity_layers_remain_distinct(self) -> None:
        parsed = paired_block(
            object_ordinal=0,
            block_number=100,
            block_time="2025-07-28T00:00:00.100",
        )
        row = parsed.observations[0]
        self.assertEqual(
            row.locator.as_mapping(),
            {
                "source_object_key": "node_fills_by_block/hourly/20250728/0.lz4",
                "compressed_object_sha256": "1" * 64,
                "record_ordinal_zero_based": 0,
                "event_ordinal_zero_based": 0,
            },
        )
        self.assertEqual(row.protocol_trade_identity, ("2025-07-28T00:00:00.100", "BTC", 42))
        self.assertEqual(row.wallet_fill_identity, (W1, "2025-07-28T00:00:00.100", "BTC", 42))
        self.assertEqual(row.legacy_weak_key, (W1, ("int", "42")))
        self.assertNotEqual(row.locator, row.wallet_fill_identity)

    def test_raw_record_and_event_fingerprints_are_deterministic(self) -> None:
        left = paired_block(
            object_ordinal=0,
            block_number=100,
            block_time="2025-07-28T00:00:00.100",
        )
        right = paired_block(
            object_ordinal=0,
            block_number=100,
            block_time="2025-07-28T00:00:00.100",
        )
        self.assertEqual(left.raw_record_sha256, right.raw_record_sha256)
        self.assertEqual(left.ordered_event_fingerprint_sha256, right.ordered_event_fingerprint_sha256)
        self.assertEqual(left.observations[0].full_event_sha256, right.observations[0].full_event_sha256)


class R11ADiagnosticTests(unittest.TestCase):
    def test_complete_scope_false_positive_and_expected_pairs(self) -> None:
        rows = (
            paired_block(
                object_ordinal=0,
                block_number=100,
                block_time="2025-07-28T00:00:00.100",
                counterparty=W2,
            ),
            paired_block(
                object_ordinal=1,
                block_number=101,
                block_time="2025-07-28T01:00:00.100",
                counterparty=W3,
            ),
        )
        report = diagnostic.classify(rows)
        self.assertEqual(report.terminal_class, diagnostic.TerminalClass.ROOT_CAUSE_TAXONOMY_COMPLETE)
        self.assertEqual(report.root_cause_claim_status, "PROVEN_COMPLETE_TAXONOMY_ONLY")
        self.assertEqual(report.repeat_occurrence_count_sum_n_minus_one, 1)
        self.assertEqual(report.taxonomy_group_counts_by_class[diagnostic.Taxon.TID_SCOPE_FALSE_POSITIVE], 1)
        self.assertEqual(report.taxonomy_occurrence_counts_by_class[diagnostic.Taxon.TID_SCOPE_FALSE_POSITIVE], 1)
        self.assertEqual(report.taxonomy_group_counts_by_class[diagnostic.Taxon.EXPECTED_COUNTERPARTY_PAIR], 2)
        self.assertEqual(len(report.pair_proofs), 2)
        self.assertEqual(len(report.protocol_member_rows), 4)
        self.assertTrue(report.taxonomy_conservation_passed)
        self.assertEqual(report.unclassifiable_group_count, 0)

    def test_exact_block_replay_and_wallet_fill_reobservation(self) -> None:
        first = paired_block(
            object_ordinal=0,
            block_number=100,
            block_time="2025-07-28T00:00:00.100",
        )
        second = paired_block(
            object_ordinal=1,
            block_number=100,
            block_time="2025-07-28T00:00:00.100",
        )
        report = diagnostic.classify((first, second))
        self.assertEqual(report.taxonomy_group_counts_by_class[diagnostic.Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS], 1)
        self.assertEqual(report.taxonomy_occurrence_counts_by_class[diagnostic.Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS], 2)
        self.assertEqual(report.taxonomy_group_counts_by_class[diagnostic.Taxon.EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY], 2)
        self.assertEqual(len(report.replay_proofs), 1)
        self.assertTrue(all(row["deduplication_authorized"] is False for row in report.duplicate_rows))

    def test_conflicting_block_replay_is_classified_not_suppressed(self) -> None:
        first = paired_block(
            object_ordinal=0,
            block_number=100,
            block_time="2025-07-28T00:00:00.100",
        )
        second = paired_block(
            object_ordinal=1,
            block_number=100,
            block_time="2025-07-28T01:00:00.100",
        )
        report = diagnostic.classify((first, second))
        self.assertEqual(report.taxonomy_group_counts_by_class[diagnostic.Taxon.CONFLICTING_BLOCK_REPLAY], 1)
        self.assertEqual(report.block_rows[0]["primary_taxon"], diagnostic.Taxon.CONFLICTING_BLOCK_REPLAY)
        self.assertIsNone(report.block_rows[0]["exact_block_replay_proof_id"])

    def test_conflicting_user_fill_is_classified(self) -> None:
        first = paired_block(
            object_ordinal=0,
            block_number=100,
            block_time="2025-07-28T00:00:00.100",
            px="100",
        )
        second = paired_block(
            object_ordinal=1,
            block_number=101,
            block_time="2025-07-28T00:00:00.100",
            px="101",
        )
        report = diagnostic.classify((first, second))
        self.assertGreaterEqual(
            report.taxonomy_occurrence_counts_by_class[diagnostic.Taxon.CONFLICTING_USER_FILL],
            1,
        )
        self.assertGreater(report.repeat_relationship_counts["conflicting_payload"], 0)

    def test_intra_block_repeat_is_classified(self) -> None:
        exact = fill(side="A", tid=42)
        parsed = block(
            object_ordinal=0,
            block_number=100,
            block_time="2025-07-28T00:00:00.100",
            events=[[W1, exact], [W1, dict(exact)]],
        )
        report = diagnostic.classify((parsed,))
        self.assertEqual(report.taxonomy_occurrence_counts_by_class[diagnostic.Taxon.INTRA_BLOCK_REPEAT], 1)
        self.assertEqual(report.terminal_class, diagnostic.TerminalClass.DIAGNOSTIC_INCOMPLETE)

    def test_invalid_tid_repeat_is_counted_once_by_schema_universe(self) -> None:
        first = block(
            object_ordinal=0,
            block_number=100,
            block_time="2025-07-28T00:00:00.100",
            events=[[W1, fill(tid="42")]],
        )
        second = block(
            object_ordinal=1,
            block_number=101,
            block_time="2025-07-28T01:00:00.100",
            events=[[W1, fill(tid="42")]],
        )
        report = diagnostic.classify((first, second))
        self.assertEqual(report.repeat_occurrence_count_sum_n_minus_one, 1)
        self.assertEqual(report.invalid_tid_repeat_occurrence_count, 1)
        self.assertEqual(report.taxonomy_occurrence_counts_by_class[diagnostic.Taxon.TID_SCHEMA_VIOLATION], 2)
        self.assertEqual(len(report.schema_rows), 2)
        self.assertTrue(report.taxonomy_conservation_passed)

    def test_unclassifiable_identity_remains_fail_closed(self) -> None:
        first = block(
            object_ordinal=0,
            block_number=100,
            block_time="2025-07-28T00:00:00.100",
            events=[[W1, fill(tid=42)]],
        )
        second = block(
            object_ordinal=1,
            block_number=101,
            block_time="2025-07-28T00:00:00.100",
            events=[[W1, fill(tid=42)]],
        )
        report = diagnostic.classify((first, second))
        self.assertGreater(report.unclassifiable_group_count, 0)
        self.assertEqual(report.terminal_class, diagnostic.TerminalClass.DIAGNOSTIC_INCOMPLETE)
        self.assertEqual(report.root_cause_claim_status, "NOT_PROVEN")

    def test_retention_cap_returns_empty_science(self) -> None:
        limits = dataclasses.replace(
            DEFAULT_LIMITS,
            maximum_repeated_legacy_key_groups_retained=0,
        )
        rows = (
            paired_block(
                object_ordinal=0,
                block_number=100,
                block_time="2025-07-28T00:00:00.100",
            ),
            paired_block(
                object_ordinal=1,
                block_number=101,
                block_time="2025-07-28T01:00:00.100",
                counterparty=W3,
            ),
        )
        report = diagnostic.classify(rows, limits=limits)
        self.assertEqual(report.terminal_class, diagnostic.TerminalClass.ARTIFACT_CAP_EXCEEDED)
        self.assertEqual(report.duplicate_rows, ())
        self.assertEqual(report.block_rows, ())
        self.assertEqual(report.taxonomy_units, ())
        self.assertEqual(report.protocol_member_rows, ())

    def test_input_order_does_not_change_deterministic_evidence(self) -> None:
        rows = (
            paired_block(
                object_ordinal=0,
                block_number=100,
                block_time="2025-07-28T00:00:00.100",
            ),
            paired_block(
                object_ordinal=1,
                block_number=101,
                block_time="2025-07-28T01:00:00.100",
                counterparty=W3,
            ),
        )
        forward = diagnostic.classify(rows)
        reverse = diagnostic.classify(tuple(reversed(rows)))
        self.assertEqual(forward.summary(), reverse.summary())
        self.assertEqual(forward.duplicate_rows, reverse.duplicate_rows)
        self.assertEqual(forward.taxonomy_units, reverse.taxonomy_units)
        self.assertEqual(forward.pair_proofs, reverse.pair_proofs)


if __name__ == "__main__":
    unittest.main()
