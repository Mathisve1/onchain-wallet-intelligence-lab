from __future__ import annotations

import inspect
import unittest

from research.archive_inventory.r11a_corrective.taxonomy import Taxon
from research.archive_inventory.r11a_corrective.taxonomy_precedence_r7 import (
    legacy_primary_taxon,
)


def metrics(
    *,
    count: int = 2,
    event_hash_count: int = 1,
    raw_block_count: int = 2,
    explicit_block_conflict_count: int = 0,
    unresolved_replay_member_count: int = 0,
    distinct_proof_count: int = 1,
    intra_block_repeat: bool = False,
    proof: object | None = object(),
) -> dict[str, object]:
    return {
        "count": count,
        "event_hash_count": event_hash_count,
        "raw_block_count": raw_block_count,
        "explicit_block_conflict_count": explicit_block_conflict_count,
        "unresolved_replay_member_count": unresolved_replay_member_count,
        "distinct_proof_count": distinct_proof_count,
        "intra_block_repeat": intra_block_repeat,
        "proof": proof,
    }


def classify(
    observed: dict[str, object] | None,
    *,
    tid_valid: bool = True,
    wallet_valid: bool = True,
    coin_valid: bool = True,
    protocol_identity_present: bool = True,
    wallet_fill_identity_present: bool = True,
    scope_group_complete: bool = False,
) -> Taxon:
    return legacy_primary_taxon(
        tid_valid=tid_valid,
        wallet_valid=wallet_valid,
        coin_valid=coin_valid,
        protocol_identity_present=protocol_identity_present,
        wallet_fill_identity_present=wallet_fill_identity_present,
        metrics=observed,
        scope_group_complete=scope_group_complete,
    )


class FrozenOccurrencePrecedenceTests(unittest.TestCase):
    def test_tid_schema_violation_has_first_precedence(self) -> None:
        self.assertIs(
            classify(
                metrics(
                    event_hash_count=2,
                    explicit_block_conflict_count=1,
                    intra_block_repeat=True,
                ),
                tid_valid=False,
            ),
            Taxon.TID_SCHEMA_VIOLATION,
        )

    def test_missing_identity_is_unclassifiable_before_other_taxa(self) -> None:
        self.assertIs(
            classify(
                metrics(event_hash_count=2, intra_block_repeat=True),
                wallet_valid=False,
            ),
            Taxon.UNCLASSIFIABLE,
        )
        self.assertIs(
            classify(
                metrics(event_hash_count=2),
                protocol_identity_present=False,
            ),
            Taxon.UNCLASSIFIABLE,
        )

    def test_explicit_block_conflict_precedes_user_fill_conflict(self) -> None:
        self.assertIs(
            classify(
                metrics(
                    event_hash_count=2,
                    explicit_block_conflict_count=1,
                )
            ),
            Taxon.UNCLASSIFIABLE,
        )

    def test_missing_cross_block_replay_proof_precedes_conflict_and_intra(self) -> None:
        self.assertIs(
            classify(
                metrics(
                    event_hash_count=2,
                    intra_block_repeat=True,
                    unresolved_replay_member_count=1,
                    distinct_proof_count=0,
                    proof=None,
                )
            ),
            Taxon.UNCLASSIFIABLE,
        )

    def test_conflicting_user_fill_precedes_intra_block_repeat(self) -> None:
        self.assertIs(
            classify(
                metrics(
                    event_hash_count=2,
                    intra_block_repeat=True,
                )
            ),
            Taxon.CONFLICTING_USER_FILL,
        )

    def test_intra_block_repeat_precedes_exact_replay(self) -> None:
        self.assertIs(
            classify(metrics(intra_block_repeat=True)),
            Taxon.INTRA_BLOCK_REPEAT,
        )

    def test_exact_user_fill_reobservation_requires_one_complete_replay_proof(self) -> None:
        self.assertIs(
            classify(metrics()),
            Taxon.EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY,
        )
        self.assertIs(
            classify(metrics(distinct_proof_count=2)),
            Taxon.UNCLASSIFIABLE,
        )

    def test_scope_false_positive_is_only_reached_after_earlier_predicates(self) -> None:
        self.assertIs(
            classify(
                metrics(
                    count=1,
                    raw_block_count=1,
                    unresolved_replay_member_count=1,
                    distinct_proof_count=0,
                    proof=None,
                ),
                scope_group_complete=True,
            ),
            Taxon.TID_SCOPE_FALSE_POSITIVE,
        )
        self.assertIs(
            classify(
                metrics(
                    count=1,
                    raw_block_count=1,
                    unresolved_replay_member_count=1,
                    distinct_proof_count=0,
                    proof=None,
                ),
                scope_group_complete=False,
            ),
            Taxon.UNCLASSIFIABLE,
        )

    def test_group_classifier_explicitly_blocks_unresolved_multi_block_scope(self) -> None:
        import research.archive_inventory.r11a_corrective.taxonomy_precedence_r7 as precedence

        source = inspect.getsource(precedence.classify_legacy)
        self.assertIn("unresolved_multi_block", source)
        self.assertIn("and not unresolved_multi_block", source)


if __name__ == "__main__":
    unittest.main()
