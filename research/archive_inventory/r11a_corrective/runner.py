from __future__ import annotations

import dataclasses
import hashlib
import os
from collections.abc import Mapping
from pathlib import Path

from .artifact_r3 import (
    ArtifactOutcome,
    ArtifactSession,
    ScientificCapExceeded,
)
from .canonical import canonical_json_bytes
from .identity import BlockObservation
from .index_r3 import CandidateDiscovery, FirstPassIndexes, discover_candidates
from .limits import DEFAULT_LIMITS, R11ALimits
from .materialize_r3 import CandidateMaterializer
from .network import AWSCredentials, download_exact_object
from .parser import ObjectPassResult, parse_object_pass
from .pricing import BudgetGuard, PricingSnapshot
from .runtime import ExecutionEvidenceState, RuntimeGuard, RuntimeTarget
from .selection import DEFAULT_SELECTION, Selection
from .storage import StorageBoundaryError, WorkspaceMeter
from .taxonomy_r3 import TaxonomyError, TaxonomyResult, classify_materialized_candidates


class RunnerError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True, slots=True)
class RunInputs:
    workspace: Path
    context: Mapping[str, object]
    selection: Selection = DEFAULT_SELECTION
    limits: R11ALimits = DEFAULT_LIMITS


@dataclasses.dataclass(frozen=True, slots=True)
class RunResult:
    artifact: ArtifactOutcome
    diagnostic_terminal: str
    research_conclusion: str


def _runtime_targets(selection: Selection) -> tuple[RuntimeTarget, ...]:
    selection.validate()
    return selection.targets


def _resource_row(
    *,
    meter: WorkspaceMeter,
    guard: RuntimeGuard,
    phase: str,
    state: ExecutionEvidenceState,
    additional: Mapping[str, object] | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "record_type": "RESOURCE_MEASUREMENT",
        "phase": phase,
        "elapsed_runtime_seconds_floor": guard.elapsed_seconds_floor(),
        "tracked_workspace_bytes": meter.known_bytes,
        "reserved_workspace_bytes": meter.reserved_bytes,
        "network_request_count": state.network_request_count,
    }
    if additional is not None:
        row.update(additional)
    return row


def _safe_stop_code(exc: BaseException) -> str:
    if isinstance(exc, ScientificCapExceeded):
        return "SCIENTIFIC_ARTIFACT_CAP_EXCEEDED"
    if isinstance(exc, StorageBoundaryError):
        return "WORKSPACE_OR_ATOMIC_OUTPUT_BOUNDARY_FAILURE"
    if isinstance(exc, TaxonomyError):
        return "TAXONOMY_OR_FOREIGN_KEY_INCOMPLETE"
    name = type(exc).__name__.upper()
    if len(name) > 80:
        name = hashlib.sha256(name.encode("utf-8")).hexdigest()
    return f"R11A_FAIL_CLOSED_{name}"


def _aggregate_parse_conservation(
    first: Mapping[int, ObjectPassResult], second: Mapping[int, ObjectPassResult]
) -> dict[str, object]:
    if set(first) != set(range(72)) or set(second) != set(range(72)):
        raise RunnerError("both parse passes must contain the exact 72 object ordinals")
    fields = tuple(dataclasses.asdict(next(iter(first.values())).conservation))
    first_totals = {field: 0 for field in fields}
    second_totals = {field: 0 for field in fields}
    for ordinal in range(72):
        if not first[ordinal].exact_match(second[ordinal]):
            raise RunnerError(f"first and second local pass differ at object {ordinal}")
        for field, value in dataclasses.asdict(first[ordinal].conservation).items():
            first_totals[field] += int(value)
        for field, value in dataclasses.asdict(second[ordinal].conservation).items():
            second_totals[field] += int(value)
    if first_totals != second_totals:
        raise RunnerError("aggregate layer conservation differs across local passes")
    raw_events = first_totals["raw_event_observation_count"]
    for valid, invalid in (
        ("valid_wallet_occurrence_count", "invalid_wallet_occurrence_count"),
        ("valid_coin_occurrence_count", "invalid_coin_occurrence_count"),
        ("valid_tid_occurrence_count", "invalid_tid_occurrence_count"),
    ):
        if first_totals[valid] + first_totals[invalid] != raw_events:
            raise RunnerError(f"aggregate valid/invalid partition failed: {valid}")
    return {
        "status": "EXACT_TWO_PASS_LAYER_CONSERVATION_PASS",
        "first_pass_totals": first_totals,
        "second_pass_totals": second_totals,
    }


def _terminal_from_taxonomy(
    *,
    state: ExecutionEvidenceState,
    taxonomy: TaxonomyResult,
    aggregate_conservation: Mapping[str, object],
) -> tuple[str, str, int]:
    proof_and_join_complete = (
        taxonomy.all_proof_references_resolve
        and taxonomy.all_unit_ids_unique
        and taxonomy.all_duplicate_rows_reference_one_unit
    )
    no_unclassifiable = (
        taxonomy.terminal_unclassifiable_group_count == 0
        and taxonomy.terminal_unclassifiable_occurrence_count == 0
    )
    universes = taxonomy.conservation_rows
    universe_names = {str(row["unit_universe"]) for row in universes}
    expected_universes = {
        "BLOCK_NUMBER_REPEAT",
        "LEGACY_WEAK_KEY_REPEAT",
        "WALLET_FILL_REPEAT",
        "PROTOCOL_TRADE_GROUP",
    }
    every_universe_conserves = len(universes) == 4 and universe_names == expected_universes
    if (
        state.exact_scope_complete()
        and aggregate_conservation["status"] == "EXACT_TWO_PASS_LAYER_CONSERVATION_PASS"
        and proof_and_join_complete
        and no_unclassifiable
        and every_universe_conserves
    ):
        return (
            "R11A_ROOT_CAUSE_TAXONOMY_COMPLETE",
            "PROVEN_COMPLETE_TAXONOMY_ONLY",
            0,
        )
    return (
        "R11A_DIAGNOSTIC_INCOMPLETE",
        "ROOT_CAUSE_NOT_FULLY_PROVEN_NO_REPAIR_AUTHORIZED",
        20,
    )


def _prepare(
    inputs: RunInputs,
) -> tuple[RuntimeGuard, WorkspaceMeter, ExecutionEvidenceState, ArtifactSession]:
    inputs.limits.validate()
    inputs.selection.validate()
    guard = RuntimeGuard(inputs.limits)
    meter = WorkspaceMeter(inputs.workspace, inputs.limits, guard)
    meter.bootstrap()
    state = ExecutionEvidenceState(_runtime_targets(inputs.selection), inputs.limits)
    session = ArtifactSession(inputs.workspace, meter, inputs.limits)
    return guard, meter, state, session


def run_with_compressed_paths(
    *,
    inputs: RunInputs,
    compressed_paths: Mapping[str, Path],
    state: ExecutionEvidenceState | None = None,
    guard: RuntimeGuard | None = None,
    meter: WorkspaceMeter | None = None,
    session: ArtifactSession | None = None,
) -> RunResult:
    if any(target.object_key not in compressed_paths for target in inputs.selection.targets):
        raise RunnerError("compressed path mapping is not the exact selection")
    if state is None or guard is None or meter is None or session is None:
        guard, meter, state, session = _prepare(inputs)
        # Local fixtures represent already integrity-verified bodies. They are never
        # used by the network workflow, which supplies the live evidence state.
        for target in inputs.selection.targets:
            state.request_sent(target.object_ordinal_zero_based)
            state.response_metadata(
                target.object_ordinal_zero_based,
                http_status=200,
                etag=target.expected_etag,
                content_length=target.expected_size_bytes,
                requester_charged="requester",
            )
            state.body_progress(target.object_ordinal_zero_based, target.expected_size_bytes)
            state.body_complete(
                target.object_ordinal_zero_based, target.expected_compressed_sha256
            )

    first_results: dict[int, ObjectPassResult] = {}
    second_results: dict[int, ObjectPassResult] = {}
    reducer_rows: tuple[dict[str, object], ...] = ()
    resource_rows: list[dict[str, object]] = [
        _resource_row(meter=meter, guard=guard, phase="RUN_START", state=state)
    ]
    indexes: FirstPassIndexes | None = None
    materializer: CandidateMaterializer | None = None
    try:
        indexes = FirstPassIndexes(meter, inputs.limits)
        for target in inputs.selection.targets:
            result = parse_object_pass(
                compressed_path=compressed_paths[target.object_key],
                target=target,
                limits=inputs.limits,
                runtime_guard=guard,
                on_block=lambda block, ordinal=target.object_ordinal_zero_based: indexes.add_block(
                    block, ordinal
                ),
            )
            first_results[target.object_ordinal_zero_based] = result
            state.pass_complete(
                target.object_ordinal_zero_based,
                pass_number=1,
                decompressed_bytes=result.transport.decompressed_bytes,
                record_count=result.transport.record_count,
                event_count=result.transport.event_count,
                stream_sha256=result.transport.decompressed_stream_sha256,
            )
        block_commitments, weak_commitments = indexes.close()
        discovery: CandidateDiscovery = discover_candidates(
            indexes, block_commitments, weak_commitments
        )
        reducer_rows = discovery.reducer_rows
        resource_rows.append(
            _resource_row(
                meter=meter,
                guard=guard,
                phase="PRIMARY_REDUCERS_COMPLETE",
                state=state,
                additional={
                    "repeated_block_group_count": discovery.repeated_block_group_count,
                    "repeated_block_observation_count": discovery.repeated_block_observation_count,
                    "repeated_legacy_weak_group_count": discovery.repeated_weak_group_count,
                    "repeated_legacy_weak_observation_count": discovery.repeated_weak_observation_count,
                },
            )
        )
        if discovery.cap_fallback_required:
            state.stop(
                "FIRST_PASS_RETENTION_CAP_EXCEEDED",
                phase="AFTER_PRIMARY_REDUCERS_BEFORE_SECOND_PASS",
                evidence={
                    "repeated_block_group_count": discovery.repeated_block_group_count,
                    "repeated_legacy_weak_group_count": discovery.repeated_weak_group_count,
                },
            )
            artifact = session.finalize_empty(
                state=state,
                context=inputs.context,
                reducer_rows=reducer_rows,
                resource_rows=resource_rows,
                terminal_class="R11A_ARTIFACT_CAP_EXCEEDED",
                research_conclusion="ROOT_CAUSE_NOT_PROVEN_EMPTY_CAP_FALLBACK",
            )
            return RunResult(
                artifact,
                "R11A_ARTIFACT_CAP_EXCEEDED",
                "ROOT_CAUSE_NOT_PROVEN_EMPTY_CAP_FALLBACK",
            )

        materializer = CandidateMaterializer(meter, inputs.limits, discovery)
        for target in inputs.selection.targets:
            result = parse_object_pass(
                compressed_path=compressed_paths[target.object_key],
                target=target,
                limits=inputs.limits,
                runtime_guard=guard,
                on_block=materializer.add_block,
            )
            second_results[target.object_ordinal_zero_based] = result
            if not result.exact_match(first_results[target.object_ordinal_zero_based]):
                raise RunnerError("object differs across independent local passes")
            state.pass_complete(
                target.object_ordinal_zero_based,
                pass_number=2,
                decompressed_bytes=result.transport.decompressed_bytes,
                record_count=result.transport.record_count,
                event_count=result.transport.event_count,
                stream_sha256=result.transport.decompressed_stream_sha256,
            )
        materialized = materializer.close()
        if materialized.cap_fallback_required:
            state.stop(
                "SECOND_PASS_MATERIALIZATION_CAP_EXCEEDED",
                phase="AFTER_SECOND_PASS_BEFORE_TAXONOMY",
                evidence={
                    "retained_block_observation_count": materialized.retained_block_observation_count,
                    "retained_event_observation_count": materialized.retained_event_observation_count,
                },
            )
            artifact = session.finalize_empty(
                state=state,
                context=inputs.context,
                reducer_rows=reducer_rows,
                resource_rows=resource_rows,
                terminal_class="R11A_ARTIFACT_CAP_EXCEEDED",
                research_conclusion="ROOT_CAUSE_NOT_PROVEN_EMPTY_CAP_FALLBACK",
            )
            return RunResult(
                artifact,
                "R11A_ARTIFACT_CAP_EXCEEDED",
                "ROOT_CAUSE_NOT_PROVEN_EMPTY_CAP_FALLBACK",
            )

        aggregate_conservation = _aggregate_parse_conservation(first_results, second_results)
        taxonomy = classify_materialized_candidates(materialized, meter, session.emitter)
        terminal, conclusion, return_code = _terminal_from_taxonomy(
            state=state,
            taxonomy=taxonomy,
            aggregate_conservation=aggregate_conservation,
        )
        if terminal != "R11A_ROOT_CAUSE_TAXONOMY_COMPLETE":
            state.stop(
                "FULLY_MATERIALIZED_TAXONOMY_INCOMPLETE",
                phase="FINAL_SCIENTIFIC_VALIDATION",
                evidence={
                    "unclassifiable_group_count": taxonomy.terminal_unclassifiable_group_count,
                    "unclassifiable_occurrence_count": taxonomy.terminal_unclassifiable_occurrence_count,
                    "all_proof_references_resolve": taxonomy.all_proof_references_resolve,
                },
            )
        resource_rows.append(
            _resource_row(
                meter=meter,
                guard=guard,
                phase="SCIENCE_COMPLETE_BEFORE_PACKAGING",
                state=state,
                additional={"aggregate_parse_conservation": aggregate_conservation},
            )
        )
        artifact = session.finalize_full(
            state=state,
            context=inputs.context,
            reducer_rows=reducer_rows,
            resource_rows=resource_rows,
            terminal_class=terminal,
            research_conclusion=conclusion,
            return_code=return_code,
            taxonomy_result=taxonomy,
        )
        return RunResult(artifact, terminal, conclusion)
    except Exception as exc:
        stop_code = _safe_stop_code(exc)
        state.stop(
            stop_code,
            phase="FAIL_CLOSED_EXCEPTION_BOUNDARY",
            evidence={"exception_type_sha256": hashlib.sha256(type(exc).__name__.encode()).hexdigest()},
        )
        resource_rows.append(
            _resource_row(
                meter=meter,
                guard=guard,
                phase="FAIL_CLOSED_BEFORE_MINIMAL_ARTIFACT",
                state=state,
                additional={"stop_code": stop_code},
            )
        )
        try:
            artifact = session.finalize_empty(
                state=state,
                context=inputs.context,
                reducer_rows=reducer_rows,
                resource_rows=resource_rows,
                terminal_class="R11A_DIAGNOSTIC_INCOMPLETE",
                research_conclusion="ROOT_CAUSE_NOT_PROVEN_FAIL_CLOSED_EMPTY_ARTIFACT",
            )
        except Exception:
            session.abort()
            raise
        return RunResult(
            artifact,
            "R11A_DIAGNOSTIC_INCOMPLETE",
            "ROOT_CAUSE_NOT_PROVEN_FAIL_CLOSED_EMPTY_ARTIFACT",
        )


def run_network(
    *,
    inputs: RunInputs,
    credentials: AWSCredentials,
    pricing_snapshot: PricingSnapshot,
) -> RunResult:
    guard, meter, state, session = _prepare(inputs)
    objects_directory = meter.root / "objects"
    objects_directory.mkdir(exist_ok=False)
    budget = BudgetGuard(
        inputs.limits,
        pricing_snapshot,
        inputs.selection.aggregate_expected_compressed_bytes,
    )
    compressed_paths: dict[str, Path] = {}
    reducer_rows: tuple[dict[str, object], ...] = ()
    resource_rows: list[dict[str, object]] = []
    try:
        for target in inputs.selection.targets:
            path = objects_directory / f"object-{target.object_ordinal_zero_based:03d}.lz4"
            compressed_paths[target.object_key] = download_exact_object(
                target=target,
                destination=path,
                credentials=credentials,
                state=state,
                meter=meter,
                runtime_guard=guard,
                budget_guard=budget,
            )
        resource_rows.append(
            _resource_row(
                meter=meter,
                guard=guard,
                phase="ALL_72_OBJECTS_DOWNLOADED",
                state=state,
                additional={
                    "authorized_request_count": budget.authorized_request_count,
                    "authorized_response_bytes": budget.authorized_response_bytes,
                },
            )
        )
        return run_with_compressed_paths(
            inputs=inputs,
            compressed_paths=compressed_paths,
            state=state,
            guard=guard,
            meter=meter,
            session=session,
        )
    except Exception as exc:
        stop_code = _safe_stop_code(exc)
        state.stop(
            stop_code,
            phase="NETWORK_OR_PRECOLLECTOR_FAILURE",
            evidence={"exception_type_sha256": hashlib.sha256(type(exc).__name__.encode()).hexdigest()},
        )
        resource_rows.append(
            _resource_row(
                meter=meter,
                guard=guard,
                phase="NETWORK_FAILURE_BEFORE_MINIMAL_ARTIFACT",
                state=state,
                additional={"stop_code": stop_code},
            )
        )
        artifact = session.finalize_empty(
            state=state,
            context=inputs.context,
            reducer_rows=reducer_rows,
            resource_rows=resource_rows,
            terminal_class="R11A_DIAGNOSTIC_INCOMPLETE",
            research_conclusion="ROOT_CAUSE_NOT_PROVEN_NETWORK_FAIL_CLOSED_EMPTY_ARTIFACT",
        )
        return RunResult(
            artifact,
            "R11A_DIAGNOSTIC_INCOMPLETE",
            "ROOT_CAUSE_NOT_PROVEN_NETWORK_FAIL_CLOSED_EMPTY_ARTIFACT",
        )
