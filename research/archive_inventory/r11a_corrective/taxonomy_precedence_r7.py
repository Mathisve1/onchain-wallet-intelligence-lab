from __future__ import annotations

import hashlib
import sqlite3
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

from . import _taxonomy_core_r7 as _base
from .canonical import strict_json_loads
from .identity import frame
from .join_r7 import DiskJoinLedger
from .materialize import MaterializedIndexes
from .storage_r7 import WorkspaceMeter

Taxon = _base.Taxon
UnitUniverse = _base.UnitUniverse
TaxonomyBoundaryError = _base.TaxonomyBoundaryError
UniverseConservation = _base.UniverseConservation
ProofReference = _base.ProofReference
EvidenceEmitter = _base.EvidenceEmitter
BlockProofIndex = _base.BlockProofIndex
ProtocolProofIndex = _base.ProtocolProofIndex
GroupScratch = _base.GroupScratch


def wallet_fill_metrics(
    connection: sqlite3.Connection,
    wallet_fill_key: bytes,
) -> dict[str, object]:
    summary = connection.execute(
        """
        SELECT COUNT(*),
               COUNT(DISTINCT event_hash),
               COUNT(DISTINCT raw_block_key),
               SUM(
                 CASE WHEN block_taxon IN (?,?) OR block_locator_resolved=0
                      THEN 1 ELSE 0 END
               ),
               SUM(
                 CASE WHEN block_taxon IS NULL OR block_taxon<>?
                           OR block_proof_id IS NULL OR block_locator_resolved=0
                      THEN 1 ELSE 0 END
               ),
               COUNT(
                 DISTINCT CASE WHEN block_proof_id IS NOT NULL
                               THEN block_proof_id END
               )
        FROM events
        WHERE wallet_fill_key=?
        """,
        (
            Taxon.CONFLICTING_BLOCK_REPLAY.value,
            Taxon.UNCLASSIFIABLE.value,
            Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS.value,
            sqlite3.Binary(wallet_fill_key),
        ),
    ).fetchone()
    if summary is None:
        raise TaxonomyBoundaryError("wallet-fill metrics query returned no row")
    intra = connection.execute(
        """
        SELECT 1
        FROM events
        WHERE wallet_fill_key=?
        GROUP BY raw_block_key,event_hash
        HAVING COUNT(DISTINCT event_ordinal)>1
        LIMIT 1
        """,
        (sqlite3.Binary(wallet_fill_key),),
    ).fetchone()
    proof_row = connection.execute(
        """
        SELECT block_proof_id,block_proof_projection
        FROM events
        WHERE wallet_fill_key=? AND block_proof_id IS NOT NULL
        GROUP BY block_proof_id,block_proof_projection
        ORDER BY block_proof_id
        LIMIT 1
        """,
        (sqlite3.Binary(wallet_fill_key),),
    ).fetchone()
    return {
        "count": int(summary[0]),
        "event_hash_count": int(summary[1]),
        "raw_block_count": int(summary[2]),
        "explicit_block_conflict_count": int(summary[3] or 0),
        "unresolved_replay_member_count": int(summary[4] or 0),
        "distinct_proof_count": int(summary[5]),
        "intra_block_repeat": intra is not None,
        "proof": (
            None
            if proof_row is None
            else ProofReference(
                "R11A_V2_EXACT_BLOCK_REPLAY_PROOF",
                str(proof_row[0]),
                bytes(proof_row[1]),
            )
        ),
    }


def legacy_primary_taxon(
    *,
    tid_valid: bool,
    wallet_valid: bool,
    coin_valid: bool,
    protocol_identity_present: bool,
    wallet_fill_identity_present: bool,
    metrics: Mapping[str, object] | None,
    scope_group_complete: bool,
) -> Taxon:
    if not tid_valid:
        return Taxon.TID_SCHEMA_VIOLATION
    if (
        not wallet_valid
        or not coin_valid
        or not protocol_identity_present
        or not wallet_fill_identity_present
        or metrics is None
    ):
        return Taxon.UNCLASSIFIABLE

    raw_block_count = int(metrics["raw_block_count"])
    if int(metrics["explicit_block_conflict_count"]) > 0:
        return Taxon.UNCLASSIFIABLE
    if raw_block_count > 1 and (
        int(metrics["unresolved_replay_member_count"]) > 0
        or int(metrics["distinct_proof_count"]) != 1
    ):
        return Taxon.UNCLASSIFIABLE
    if int(metrics["event_hash_count"]) > 1:
        return Taxon.CONFLICTING_USER_FILL
    if bool(metrics["intra_block_repeat"]):
        return Taxon.INTRA_BLOCK_REPEAT
    if (
        int(metrics["count"]) > 1
        and int(metrics["event_hash_count"]) == 1
        and raw_block_count > 1
        and int(metrics["unresolved_replay_member_count"]) == 0
        and int(metrics["distinct_proof_count"]) == 1
        and metrics["proof"] is not None
    ):
        return Taxon.EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY
    if scope_group_complete:
        return Taxon.TID_SCOPE_FALSE_POSITIVE
    return Taxon.UNCLASSIFIABLE


def _schema_unit(
    *,
    universe: UnitUniverse,
    taxon: Taxon,
    source: _base.FrozenObject,
    emitter: EvidenceEmitter,
    joins: DiskJoinLedger,
    conservation: UniverseConservation,
) -> None:
    _base._schema_unit(
        universe=universe,
        taxon=taxon,
        source=source,
        emitter=emitter,
        joins=joins,
        conservation=conservation,
    )


def classify_legacy(
    materialized: MaterializedIndexes,
    meter: WorkspaceMeter,
    emitter: EvidenceEmitter,
    joins: DiskJoinLedger,
    conservations: Mapping[UnitUniverse, UniverseConservation],
    scratch: GroupScratch,
    block_proofs: BlockProofIndex,
    protocol_proofs: ProtocolProofIndex,
) -> tuple[list[dict[str, object]], int, int, int, int, Counter[str]]:
    reducer_rows: list[dict[str, object]] = []
    group_count = 0
    observation_count = 0
    valid_tid_repeat_occurrences = 0
    invalid_tid_repeat_occurrences = 0
    supporting: Counter[str] = Counter()

    for partition, sorted_path, reducer_row in _base._sort_partitions(
        reducer_id="EXACT_LEGACY_WEAK_KEY",
        directory=materialized.weak_directory,
        stats=materialized.weak_stats,
        meter=meter,
    ):
        reducer_rows.append(reducer_row)
        spool = meter.root / f"taxonomy-legacy-groups-{partition:03d}"
        for group in _base.iter_equality_group_spools(
            sorted_path,
            spool,
            meter,
            maximum_group_spool_bytes=(
                meter.limits.maximum_equality_group_spool_bytes
            ),
        ):
            count = scratch.load_events(group.path, meter, block_proofs)
            if count <= 1:
                raise TaxonomyBoundaryError(
                    "materialized legacy repeat group is singleton"
                )
            group_count += 1
            observation_count += count
            connection = scratch.database.connection
            group_summary = connection.execute(
                """
                SELECT COUNT(DISTINCT protocol_key),
                       SUM(
                         protocol_key IS NULL OR wallet_fill_key IS NULL
                         OR tid_valid=0 OR coin_valid=0 OR wallet_valid=0
                       ),
                       SUM(
                         CASE WHEN block_taxon IN (?,?)
                                   OR block_locator_resolved=0
                              THEN 1 ELSE 0 END
                       )
                FROM events
                """,
                (
                    Taxon.CONFLICTING_BLOCK_REPLAY.value,
                    Taxon.UNCLASSIFIABLE.value,
                ),
            ).fetchone()
            if group_summary is None:
                raise TaxonomyBoundaryError(
                    "legacy group summary query returned no row"
                )
            conflicting_wallet_group = (
                connection.execute(
                    """
                    SELECT 1
                    FROM events
                    WHERE wallet_fill_key IS NOT NULL
                    GROUP BY wallet_fill_key
                    HAVING COUNT(DISTINCT event_hash)>1
                    LIMIT 1
                    """
                ).fetchone()
                is not None
            )
            unresolved_multi_block = (
                connection.execute(
                    """
                    SELECT 1
                    FROM events
                    WHERE wallet_fill_key IS NOT NULL
                    GROUP BY wallet_fill_key
                    HAVING COUNT(DISTINCT raw_block_key)>1
                       AND (
                         SUM(
                           CASE WHEN block_taxon IS NULL OR block_taxon<>?
                                     OR block_proof_id IS NULL
                                     OR block_locator_resolved=0
                                THEN 1 ELSE 0 END
                         )>0
                         OR COUNT(DISTINCT block_proof_id)<>1
                       )
                    LIMIT 1
                    """,
                    (Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS.value,),
                ).fetchone()
                is not None
            )
            scope_group_complete = (
                int(group_summary[0]) >= 2
                and int(group_summary[1] or 0) == 0
                and int(group_summary[2] or 0) == 0
                and not conflicting_wallet_group
                and not unresolved_multi_block
            )
            first_sequence_row = connection.execute(
                """
                SELECT sequence
                FROM events
                ORDER BY object_key_bytes,compressed_sha256,
                         record_ordinal,event_ordinal
                LIMIT 1
                """
            ).fetchone()
            if first_sequence_row is None:
                raise TaxonomyBoundaryError("legacy group lacks first sequence")
            first_sequence = int(first_sequence_row[0])

            for row in scratch.iter_ordered():
                source = _base._object(
                    strict_json_loads(bytes(row["row_json"])),
                    "legacy row",
                )
                tid_valid = bool(row["tid_valid"])
                coin_valid = bool(row["coin_valid"])
                wallet_valid = bool(row["wallet_valid"])
                if not tid_valid:
                    _schema_unit(
                        universe=(
                            UnitUniverse.REPEAT_INTERSECTING_TID_SCHEMA_VIOLATION
                        ),
                        taxon=Taxon.TID_SCHEMA_VIOLATION,
                        source=source,
                        emitter=emitter,
                        joins=joins,
                        conservation=conservations[
                            UnitUniverse.REPEAT_INTERSECTING_TID_SCHEMA_VIOLATION
                        ],
                    )
                if not coin_valid:
                    _schema_unit(
                        universe=(
                            UnitUniverse.REPEAT_INTERSECTING_COIN_SCHEMA_VIOLATION
                        ),
                        taxon=Taxon.UNCLASSIFIABLE,
                        source=source,
                        emitter=emitter,
                        joins=joins,
                        conservation=conservations[
                            UnitUniverse.REPEAT_INTERSECTING_COIN_SCHEMA_VIOLATION
                        ],
                    )
                if not wallet_valid:
                    _schema_unit(
                        universe=(
                            UnitUniverse.REPEAT_INTERSECTING_WALLET_SCHEMA_VIOLATION
                        ),
                        taxon=Taxon.UNCLASSIFIABLE,
                        source=source,
                        emitter=emitter,
                        joins=joins,
                        conservation=conservations[
                            UnitUniverse.REPEAT_INTERSECTING_WALLET_SCHEMA_VIOLATION
                        ],
                    )
                if int(row["sequence"]) == first_sequence:
                    continue
                if tid_valid:
                    valid_tid_repeat_occurrences += 1
                else:
                    invalid_tid_repeat_occurrences += 1

                proof_references: list[ProofReference] = []
                supporting_taxa: list[Taxon] = []
                protocol_key = (
                    None
                    if row["protocol_key"] is None
                    else bytes(row["protocol_key"])
                )
                raw_block_key = bytes(row["raw_block_key"])
                if protocol_key is not None:
                    protocol_taxon, protocol_proof = protocol_proofs.lookup(
                        frame(raw_block_key, protocol_key)
                    )
                    if (
                        protocol_taxon
                        == Taxon.EXPECTED_COUNTERPARTY_PAIR.value
                    ):
                        supporting_taxa.append(
                            Taxon.EXPECTED_COUNTERPARTY_PAIR
                        )
                        supporting[
                            Taxon.EXPECTED_COUNTERPARTY_PAIR.value
                        ] += 1
                        if protocol_proof is not None:
                            proof_references.append(protocol_proof)
                wallet_fill_key = (
                    None
                    if row["wallet_fill_key"] is None
                    else bytes(row["wallet_fill_key"])
                )
                metrics = (
                    None
                    if wallet_fill_key is None
                    else wallet_fill_metrics(connection, wallet_fill_key)
                )
                taxon = legacy_primary_taxon(
                    tid_valid=tid_valid,
                    wallet_valid=wallet_valid,
                    coin_valid=coin_valid,
                    protocol_identity_present=protocol_key is not None,
                    wallet_fill_identity_present=(
                        wallet_fill_key is not None
                    ),
                    metrics=metrics,
                    scope_group_complete=scope_group_complete,
                )
                if (
                    taxon
                    is Taxon.EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY
                ):
                    if metrics is None or metrics["proof"] is None:
                        raise TaxonomyBoundaryError(
                            "replay taxon lacks exact block proof"
                        )
                    proof_references.append(
                        metrics["proof"]  # type: ignore[arg-type]
                    )
                key_projection = {
                    "legacy_weak_key_sha256": hashlib.sha256(
                        group.equality_key
                    ).hexdigest(),
                    "raw_locator": source["raw_locator"],
                    "complete_group_observation_count": count,
                    "complete_wallet_fill_group_key_sha256": (
                        None
                        if wallet_fill_key is None
                        else hashlib.sha256(wallet_fill_key).hexdigest()
                    ),
                }
                unique_references = tuple(
                    {
                        reference.proof_id: reference
                        for reference in proof_references
                    }.values()
                )
                unit_id, unit_projection = _base._emit_unit(
                    emitter=emitter,
                    joins=joins,
                    conservation=conservations[
                        UnitUniverse.LEGACY_REPEAT_OCCURRENCE
                    ],
                    universe=UnitUniverse.LEGACY_REPEAT_OCCURRENCE,
                    key_projection=key_projection,
                    taxon=taxon,
                    occurrence_count=1,
                    proof_references=unique_references,
                    supporting_taxa=tuple(supporting_taxa),
                )
                _base._emit_referenced_row(
                    emitter=emitter,
                    joins=joins,
                    container="r11a-v2-duplicate-observations.ndjson",
                    unit_id=unit_id,
                    unit_projection=unit_projection,
                    row={
                        "record_type": (
                            "R11A_V2_LEGACY_REPEAT_OCCURRENCE"
                        ),
                        "primary_taxon": taxon.value,
                        "supporting_taxa": [
                            value.value for value in supporting_taxa
                        ],
                        "raw_locator": source["raw_locator"],
                        "raw_wallet_value": source["raw_wallet_value"],
                        "raw_fill_value": source["raw_fill_value"],
                        "raw_record_fingerprint_sha256": source[
                            "raw_record_fingerprint_sha256"
                        ],
                        "block_number": source["block_number"],
                        "exact_raw_local_time": source[
                            "exact_raw_local_time"
                        ],
                        "exact_raw_block_time": source[
                            "exact_raw_block_time"
                        ],
                        "canonical_wallet": source["canonical_wallet"],
                        "exact_raw_coin_string": source[
                            "exact_raw_coin_string"
                        ],
                        "validated_tid": source["validated_tid"],
                        "exact_raw_side_string": source[
                            "exact_raw_side_string"
                        ],
                        "full_event_sha256": source[
                            "full_event_sha256"
                        ],
                        "fill_payload_sha256": source[
                            "fill_payload_sha256"
                        ],
                        "schema_errors": source["schema_errors"],
                        "selected_fill_payload": source[
                            "selected_fill_payload"
                        ],
                    },
                )
        meter.delete_file(sorted_path)
        meter.delete_file(
            materialized.weak_directory
            / f"part-{partition:03d}.frames"
        )
    if materialized.weak_directory.exists():
        materialized.weak_directory.rmdir()
    return (
        reducer_rows,
        group_count,
        observation_count,
        valid_tid_repeat_occurrences,
        invalid_tid_repeat_occurrences,
        supporting,
    )


def install() -> None:
    _base._wallet_fill_metrics = wallet_fill_metrics
    _base._classify_legacy = classify_legacy
