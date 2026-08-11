from __future__ import annotations

import json
import unittest

from research.archive_inventory.r11a_implementation import diagnostic, identity

A = "0x" + "1" * 40
B = "0x" + "2" * 40
C = "0x" + "3" * 40


def source(ordinal: int, hour: int) -> identity.SourceObject:
    return identity.SourceObject(
        ordinal,
        f"node_fills_by_block/hourly/20250728/{hour}.lz4",
        f"{ordinal + 1:064x}",
        f"2025-07-28T{hour:02d}:00:00Z",
    )


def fill(tid: object, *, coin: object = "BTC", side: str = "A", px: str = "100", time_ms: int = 1753660800000) -> dict[str, object]:
    return {
        "coin": coin,
        "tid": tid,
        "time": time_ms,
        "side": side,
        "px": px,
        "sz": "1",
        "closedPnl": "0",
        "crossed": side == "A",
        "liquidation": None,
    }


def parsed_block(
    *,
    src: identity.SourceObject,
    record: int,
    block_number: int,
    block_time: str,
    events: list[list[object]],
) -> identity.BlockObservation:
    raw = json.dumps(
        {
            "local_time": block_time,
            "block_time": block_time,
            "block_number": block_number,
            "events": events,
        },
        separators=(",", ":"),
    ).encode()
    return identity.parse_block_record(
        raw,
        source=src,
        record_ordinal_zero_based=record,
    )


def pair_events(
    tid: int,
    *,
    coin: str = "BTC",
    wallet_a: str = A,
    wallet_b: str = B,
    px_a: str = "100",
    px_b: str = "100",
    time_ms: int = 1753660800000,
) -> list[list[object]]:
    return [
        [wallet_a, fill(tid, coin=coin, side="A", px=px_a, time_ms=time_ms)],
        [wallet_b, fill(tid, coin=coin, side="B", px=px_b, time_ms=time_ms)],
    ]


class R11ADiagnosticTaxonomyTests(unittest.TestCase):
    def assert_taxon_present(self, report: diagnostic.DiagnosticReport, taxon: diagnostic.Taxon) -> None:
        self.assertGreater(
            report.taxonomy_occurrence_counts_by_class[taxon.value],
            0,
            report.summary(),
        )

    def test_tid_scope_false_positive_and_expected_pairs_are_complete(self) -> None:
        blocks = (
            parsed_block(
                src=source(0, 0),
                record=0,
                block_number=1,
                block_time="2025-07-28T00:00:00Z",
                events=pair_events(7, coin="BTC", time_ms=1753660800000),
            ),
            parsed_block(
                src=source(1, 1),
                record=0,
                block_number=2,
                block_time="2025-07-28T01:00:00Z",
                events=pair_events(7, coin="ETH", time_ms=1753664400000),
            ),
        )
        report = diagnostic.classify(blocks)
        self.assertEqual(report.terminal_class, diagnostic.TerminalClass.ROOT_CAUSE_TAXONOMY_COMPLETE)
        self.assert_taxon_present(report, diagnostic.Taxon.TID_SCOPE_FALSE_POSITIVE)
        self.assert_taxon_present(report, diagnostic.Taxon.EXPECTED_COUNTERPARTY_PAIR)
        self.assertEqual(report.affected_weak_key_group_count, 2)
        self.assertEqual(report.repeat_occurrence_count_sum_n_minus_one, 2)
        self.assertTrue(report.taxonomy_conservation_passed)
        self.assertEqual(report.unclassifiable_group_count, 0)
        self.assertEqual(len(report.pair_proofs), 2)

    def test_exact_block_replay_proves_user_fill_reobservation(self) -> None:
        events = pair_events(9)
        blocks = (
            parsed_block(
                src=source(0, 0),
                record=0,
                block_number=42,
                block_time="2025-07-28T00:00:00Z",
                events=events,
            ),
            parsed_block(
                src=source(1, 1),
                record=0,
                block_number=42,
                block_time="2025-07-28T00:00:00Z",
                events=events,
            ),
        )
        report = diagnostic.classify(blocks)
        self.assertEqual(report.terminal_class, diagnostic.TerminalClass.ROOT_CAUSE_TAXONOMY_COMPLETE)
        self.assert_taxon_present(report, diagnostic.Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS)
        self.assert_taxon_present(
            report,
            diagnostic.Taxon.EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY,
        )
        self.assertEqual(len(report.replay_proofs), 1)
        replay_id = report.replay_proofs[0]["exact_block_replay_proof_id"]
        repeat_rows = [row for row in report.duplicate_rows if row["primary_taxon"] == diagnostic.Taxon.EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY.value]
        self.assertEqual(len(repeat_rows), 2)
        self.assertTrue(all(row["exact_block_replay_proof"]["exact_block_replay_proof_id"] == replay_id for row in repeat_rows))
        self.assertTrue(all(row["deduplication_authorized"] is False for row in repeat_rows))

    def test_conflicting_block_replay_is_not_suppressed(self) -> None:
        blocks = (
            parsed_block(
                src=source(0, 0),
                record=0,
                block_number=77,
                block_time="2025-07-28T00:00:00Z",
                events=pair_events(12, time_ms=1753660800000),
            ),
            parsed_block(
                src=source(1, 1),
                record=0,
                block_number=77,
                block_time="2025-07-28T01:00:00Z",
                events=pair_events(12, time_ms=1753664400000),
            ),
        )
        report = diagnostic.classify(blocks)
        self.assert_taxon_present(report, diagnostic.Taxon.CONFLICTING_BLOCK_REPLAY)
        row = next(row for row in report.block_rows if row["block_number"] == 77)
        self.assertIn("exact_raw_block_time", row["conflicting_invariant_fields"])
        self.assertIsNone(row["exact_block_replay_proof_id"])

    def test_conflicting_user_fill_is_fail_closed_taxon(self) -> None:
        blocks = (
            parsed_block(
                src=source(0, 0),
                record=0,
                block_number=1,
                block_time="2025-07-28T00:00:00Z",
                events=pair_events(21, wallet_b=B, px_a="100"),
            ),
            parsed_block(
                src=source(1, 1),
                record=0,
                block_number=2,
                block_time="2025-07-28T00:00:00Z",
                events=pair_events(21, wallet_b=C, px_a="101"),
            ),
        )
        report = diagnostic.classify(blocks)
        self.assert_taxon_present(report, diagnostic.Taxon.CONFLICTING_USER_FILL)
        rows = [row for row in report.duplicate_rows if row["primary_taxon"] == diagnostic.Taxon.CONFLICTING_USER_FILL.value]
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["first_versus_occurrence_field_diffmask"]["px_differs"])
        self.assertFalse(rows[0]["deduplication_authorized"])

    def test_intra_block_repeat_is_classified_without_deduplication(self) -> None:
        repeated = fill(30, side="A")
        block = parsed_block(
            src=source(0, 0),
            record=0,
            block_number=1,
            block_time="2025-07-28T00:00:00Z",
            events=[[A, repeated], [A, dict(repeated)]],
        )
        report = diagnostic.classify((block,))
        self.assert_taxon_present(report, diagnostic.Taxon.INTRA_BLOCK_REPEAT)
        row = next(row for row in report.duplicate_rows if row["primary_taxon"] == diagnostic.Taxon.INTRA_BLOCK_REPEAT.value)
        self.assertTrue(row["boundary_relationship_to_group_first"]["same_raw_block_locator"])
        self.assertFalse(row["deduplication_authorized"])
        self.assertEqual(report.terminal_class, diagnostic.TerminalClass.DIAGNOSTIC_INCOMPLETE)

    def test_tid_schema_violation_is_retained_without_coercion(self) -> None:
        blocks = (
            parsed_block(
                src=source(0, 0),
                record=0,
                block_number=1,
                block_time="2025-07-28T00:00:00Z",
                events=[[A, fill("7")]],
            ),
            parsed_block(
                src=source(1, 1),
                record=0,
                block_number=2,
                block_time="2025-07-28T01:00:00Z",
                events=[[A, fill("7", time_ms=1753664400000)]],
            ),
        )
        report = diagnostic.classify(blocks)
        self.assert_taxon_present(report, diagnostic.Taxon.TID_SCHEMA_VIOLATION)
        self.assertEqual(report.invalid_tid_repeat_occurrence_count, 1)
        self.assertEqual(len([row for row in report.schema_rows if row["taxonomy_unit_type"] == "RAW_TID_SCHEMA_VIOLATION_OBSERVATION"]), 2)
        self.assertTrue(all(row["validated_integer_tid"] is None for row in report.duplicate_rows))

    def test_unclassifiable_exact_reobservation_without_block_replay_stays_open(self) -> None:
        blocks = (
            parsed_block(
                src=source(0, 0),
                record=0,
                block_number=1,
                block_time="2025-07-28T00:00:00Z",
                events=pair_events(44, wallet_b=B),
            ),
            parsed_block(
                src=source(1, 1),
                record=0,
                block_number=2,
                block_time="2025-07-28T00:00:00Z",
                events=pair_events(44, wallet_b=C),
            ),
        )
        report = diagnostic.classify(blocks)
        self.assert_taxon_present(report, diagnostic.Taxon.UNCLASSIFIABLE)
        self.assertGreater(report.unclassifiable_group_count, 0)
        self.assertEqual(report.terminal_class, diagnostic.TerminalClass.DIAGNOSTIC_INCOMPLETE)
        self.assertEqual(report.root_cause_claim_status, "NOT_PROVEN")

    def test_output_is_deterministic_under_input_order_reversal(self) -> None:
        blocks = [
            parsed_block(
                src=source(0, 0),
                record=0,
                block_number=1,
                block_time="2025-07-28T00:00:00Z",
                events=pair_events(55, coin="BTC"),
            ),
            parsed_block(
                src=source(1, 1),
                record=0,
                block_number=2,
                block_time="2025-07-28T01:00:00Z",
                events=pair_events(55, coin="ETH", time_ms=1753664400000),
            ),
        ]
        first = diagnostic.classify(blocks)
        second = diagnostic.classify(reversed(blocks))
        self.assertEqual(first.summary(), second.summary())
        self.assertEqual(first.duplicate_rows, second.duplicate_rows)
        self.assertEqual(first.block_rows, second.block_rows)
        self.assertEqual(first.taxonomy_units, second.taxonomy_units)
        self.assertEqual(first.pair_proofs, second.pair_proofs)

    def test_duplicate_raw_block_locator_is_hard_failure(self) -> None:
        block = parsed_block(
            src=source(0, 0),
            record=0,
            block_number=1,
            block_time="2025-07-28T00:00:00Z",
            events=pair_events(1),
        )
        with self.assertRaises(diagnostic.R11ADiagnosticError):
            diagnostic.classify((block, block))


if __name__ == "__main__":
    unittest.main()
