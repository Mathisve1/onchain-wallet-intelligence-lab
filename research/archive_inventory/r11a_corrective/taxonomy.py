from __future__ import annotations

import dataclasses

from . import _taxonomy_contract_core_r7 as _core
from . import taxonomy_precedence_r7 as _precedence
from .artifact_schema import AUTHORITATIVE_UNIT_UNIVERSES, TAXA

_precedence.install()

TaxonomyBoundaryError = _core.TaxonomyBoundaryError
TaxonomyCleanupError = _core.TaxonomyCleanupError
Taxon = _core.Taxon
UnitUniverse = _core.UnitUniverse
EvidenceEmitter = _core.EvidenceEmitter
UniverseConservation = _core.UniverseConservation
ProofReference = _core.ProofReference
TaxonomyResult = _core.TaxonomyResult
BlockProofIndex = _core.BlockProofIndex
ProtocolProofIndex = _core.ProtocolProofIndex
BlockScratch = _core.BlockScratch
EventScratch = _core.EventScratch


def classify_materialized_candidates(*args: object, **kwargs: object) -> TaxonomyResult:
    result = _core.classify_materialized_candidates(*args, **kwargs)
    if tuple(
        str(row["unit_universe"]) for row in result.universe_rows
    ) != AUTHORITATIVE_UNIT_UNIVERSES:
        raise TaxonomyBoundaryError("authoritative unit universe drift")
    protocol_row = result.universe_rows[
        AUTHORITATIVE_UNIT_UNIVERSES.index(
            "PROTOCOL_MATCHED_TRADE_GROUP_PER_RAW_BLOCK_OCCURRENCE"
        )
    ]
    protocol_primary_pairs = int(
        protocol_row["primary_taxon_group_counts"][
            "EXPECTED_COUNTERPARTY_PAIR"
        ]
    )
    supporting = {
        taxon: int(result.supporting_taxon_counts[taxon])
        for taxon in TAXA
    }
    if supporting["EXPECTED_COUNTERPARTY_PAIR"] < protocol_primary_pairs:
        raise TaxonomyBoundaryError(
            "supporting counterparty count is smaller than primary protocol groups"
        )
    supporting["EXPECTED_COUNTERPARTY_PAIR"] -= protocol_primary_pairs
    return dataclasses.replace(
        result,
        supporting_taxon_counts=supporting,
    )


__all__ = [
    "BlockProofIndex",
    "BlockScratch",
    "EventScratch",
    "EvidenceEmitter",
    "ProofReference",
    "ProtocolProofIndex",
    "Taxon",
    "TaxonomyBoundaryError",
    "TaxonomyResult",
    "UnitUniverse",
    "UniverseConservation",
    "classify_materialized_candidates",
]
