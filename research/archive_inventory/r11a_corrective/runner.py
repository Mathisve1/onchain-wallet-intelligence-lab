from __future__ import annotations

from collections.abc import Mapping

from . import _runner_core_r7 as _core
from .artifact_schema import AUTHORITATIVE_UNIT_UNIVERSES, TAXA
from .runtime import ExecutionEvidenceState, RuntimeGuard
from .storage_r7 import WorkspaceMeter
from .taxonomy import TaxonomyResult

RunnerBoundaryError = _core.RunnerBoundaryError
RunInputs = _core.RunInputs
RunResult = _core.RunResult


def _taxonomy_complete(
    *,
    state: ExecutionEvidenceState,
    taxonomy: TaxonomyResult,
    aggregate: Mapping[str, object],
    meter: WorkspaceMeter,
    guard: RuntimeGuard,
) -> bool:
    universe_rows = taxonomy.universe_rows
    if tuple(str(row["unit_universe"]) for row in universe_rows) != (
        AUTHORITATIVE_UNIT_UNIVERSES
    ):
        return False
    group_total = 0
    occurrence_total = 0
    for row in universe_rows:
        group_counts = row["primary_taxon_group_counts"]
        occurrence_counts = row["primary_taxon_occurrence_counts"]
        if not isinstance(group_counts, Mapping) or set(group_counts) != set(TAXA):
            return False
        if not isinstance(occurrence_counts, Mapping) or set(occurrence_counts) != set(TAXA):
            return False
        group_count = int(row["group_count"])
        occurrence_count = int(row["occurrence_count"])
        if group_count < 0 or occurrence_count < 0:
            return False
        if sum(int(value) for value in group_counts.values()) != group_count:
            return False
        if (
            sum(int(value) for value in occurrence_counts.values())
            != occurrence_count
        ):
            return False
        if int(group_counts["UNCLASSIFIABLE"]) != int(
            row["unclassifiable_group_count"]
        ):
            return False
        if int(occurrence_counts["UNCLASSIFIABLE"]) != int(
            row["unclassifiable_occurrence_count"]
        ):
            return False
        group_total += group_count
        occurrence_total += occurrence_count

    totals = aggregate.get("totals")
    partitions = aggregate.get("raw_event_partition_totals")
    if not isinstance(totals, Mapping) or not isinstance(partitions, Mapping):
        return False
    raw_blocks = int(totals["raw_block_observation_count"])
    raw_events = int(totals["raw_event_observation_count"])
    if any(int(partitions[name]) != raw_events for name in ("wallet", "coin", "tid")):
        return False
    if taxonomy.repeated_block_group_count < 0:
        return False
    if not (
        taxonomy.repeated_block_group_count
        <= taxonomy.repeated_block_observation_count
        <= raw_blocks
    ):
        return False
    if not (
        0
        <= taxonomy.legacy_repeat_group_count
        <= taxonomy.legacy_repeat_observation_count
    ):
        return False
    if taxonomy.legacy_repeat_occurrence_count != (
        taxonomy.legacy_repeat_observation_count
        - taxonomy.legacy_repeat_group_count
    ):
        return False
    if taxonomy.legacy_repeat_occurrence_count != (
        taxonomy.valid_tid_legacy_repeat_occurrence_count
        + taxonomy.invalid_tid_legacy_repeat_occurrence_count
    ):
        return False

    join = taxonomy.join_validation
    if join.unit_count != group_total:
        return False
    if join.retained_row_reference_count != occurrence_total:
        return False
    if not all(
        (
            join.all_unit_ids_unique,
            join.all_proof_ids_unique,
            join.all_nonnull_proof_references_resolve_exactly_once,
            join.all_retained_rows_reference_exactly_one_unit,
            join.all_referenced_projections_are_byte_equal,
            join.all_retained_row_counts_match_unit_occurrence_counts,
        )
    ):
        return False
    if set(taxonomy.supporting_taxon_counts) != set(TAXA):
        return False
    if any(int(value) < 0 for value in taxonomy.supporting_taxon_counts.values()):
        return False

    guard.check_packaging_phase("evaluate complete R11A R7 taxonomy terminal")
    actual_workspace = meter.verify_actual_usage()
    return bool(
        state.exact_scope_complete()
        and aggregate.get("status")
        == "EXACT_TWO_PASS_LAYER_CONSERVATION_PASS"
        and aggregate.get("per_object_pass_equality") is True
        and taxonomy.exact_three_utc_days
        and taxonomy.unclassifiable_group_count == 0
        and taxonomy.unclassifiable_occurrence_count == 0
        and actual_workspace + meter.reserved_bytes
        <= meter.limits.maximum_ephemeral_workspace_bytes
    )


_core._taxonomy_complete = _taxonomy_complete

prepare = _core.prepare
run_network = _core.run_network
run_with_compressed_paths = _core.run_with_compressed_paths

__all__ = [
    "RunInputs",
    "RunResult",
    "RunnerBoundaryError",
    "prepare",
    "run_network",
    "run_with_compressed_paths",
]
