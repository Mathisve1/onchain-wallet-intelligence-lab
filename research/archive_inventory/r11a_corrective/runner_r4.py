from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Mapping, Sequence
from pathlib import Path

from .artifact_r3 import ArtifactOutcome, ArtifactSession, ScientificCapExceeded
from .index_r3 import CandidateDiscovery, FirstPassIndexes, discover_candidates
from .limits import DEFAULT_LIMITS, R11ALimits
from .materialize_r3 import CandidateMaterializer
from .network import AWSCredentials, download_exact_object
from .parser import ObjectPassResult, parse_object_pass
from .pricing import BudgetGuard, PricingSnapshot
from .runtime import ExecutionEvidenceState, RuntimeGuard
from .selection import DEFAULT_SELECTION, Selection
from .storage import StorageBoundaryError, WorkspaceMeter
from .taxonomy_r4 import TaxonomyError, TaxonomyResult, classify_materialized_candidates


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


def _aggregate_conservation(
    first: Mapping[int, ObjectPassResult],
    second: Mapping[int, ObjectPassResult],
) -> dict[str, object]:
    exact = set(range(72))
    if set(first) != exact or set(second) != exact:
        raise RunnerError("both passes must contain exact 72-object scope")
    first_totals: dict[str, int] = {}
    second_totals: dict[str, int] = {}
    for ordinal in range(72):
        if not first[ordinal].exact_match(second[ordinal]):
            raise RunnerError(f"independent local passes differ at object {ordinal}")
        for field, value in dataclasses.asdict(first[ordinal].conservation).items():
            first_totals[field] = first_totals.get(field, 0) + int(value)
        for field, value in dataclasses.asdict(second[ordinal].conservation).items():
            second_totals[field] = second_totals.get(field, 0) + int(value)
    if first_totals != second_totals:
        raise RunnerError("aggregate layer conservation differs across passes")
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


def _terminal(
    state: ExecutionEvidenceState,
    taxonomy: TaxonomyResult,
    aggregate: Mapping[str, object],
) -> tuple[str, str, int]:
    universe_names = {str(row["unit_universe"]) for row in taxonomy.conservation_rows}
    complete = (
        state.exact_scope_complete()
        and aggregate["status"] == "EXACT_TWO_PASS_LAYER_CONSERVATION_PASS"
        and len(taxonomy.conservation_rows) == 4
        and universe_names
        == {
            "BLOCK_NUMBER_REPEAT",
            "LEGACY_WEAK_KEY_REPEAT",
            "WALLET_FILL_REPEAT",
            "PROTOCOL_TRADE_GROUP",
        }
        and taxonomy.all_proof_references_resolve
        and taxonomy.all_unit_ids_unique
        and taxonomy.all_duplicate_rows_reference_one_unit
        and taxonomy.terminal_unclassifiable_group_count == 0
        and taxonomy.terminal_unclassifiable_occurrence_count == 0
    )
    if complete:
        return "R11A_ROOT_CAUSE_TAXONOMY_COMPLETE", "PROVEN_COMPLETE_TAXONOMY_ONLY", 0
    return "R11A_DIAGNOSTIC_INCOMPLETE", "ROOT_CAUSE_NOT_FULLY_PROVEN_NO_REPAIR_AUTHORIZED", 20


def prepare(inputs: RunInputs) -> tuple[RuntimeGuard, WorkspaceMeter, ExecutionEvidenceState, ArtifactSession]:
    inputs.limits.validate()
    inputs.selection.validate()
    guard = RuntimeGuard(inputs.limits)
    meter = WorkspaceMeter(inputs.workspace, inputs.limits, guard)
    meter.bootstrap()
    state = ExecutionEvidenceState(inputs.selection.targets, inputs.limits)
    session = ArtifactSession(inputs.workspace, meter, inputs.limits)
    return guard, meter, state, session


def _checked_processing_cleanup(
    meter: WorkspaceMeter,
    *,
    indexes: FirstPassIndexes | None,
    materializer: CandidateMaterializer | None,
) -> None:
    errors: list[BaseException] = []
    for value in (materializer, indexes):
        if value is None:
            continue
        try:
            value.abort()
        except BaseException as exc:
            errors.append(exc)
    protected = {"objects", ".r11a-artifact.staging", "r11a-artifact"}
    for path in sorted(meter.root.iterdir(), key=lambda item: item.name.encode("utf-8"), reverse=True):
        if path.name in protected:
            continue
        try:
            if path.is_dir():
                meter.checked_rmtree(path)
            elif path.is_file():
                meter.delete_file(path)
            else:
                raise RunnerError("unexpected workspace entry type during cleanup")
        except BaseException as exc:
            errors.append(exc)
    if errors:
        raise RunnerError("one or more checked processing cleanup operations failed") from errors[0]


def run_with_compressed_paths(
    *,
    inputs: RunInputs,
    compressed_paths: Mapping[str, Path],
    state: ExecutionEvidenceState,
    guard: RuntimeGuard,
    meter: WorkspaceMeter,
    session: ArtifactSession,
    initial_resource_rows: Sequence[Mapping[str, object]] = (),
) -> RunResult:
    expected_keys = {target.object_key for target in inputs.selection.targets}
    if set(compressed_paths) != expected_keys:
        raise RunnerError("compressed path mapping is not exact 72-object selection")
    first: dict[int, ObjectPassResult] = {}
    second: dict[int, ObjectPassResult] = {}
    reducer_rows: tuple[dict[str, object], ...] = ()
    resources: list[dict[str, object]] = [dict(row) for row in initial_resource_rows]
    resources.append(_resource_row(meter=meter, guard=guard, phase="COLLECTOR_START", state=state))
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
                on_block=lambda block, ordinal=target.object_ordinal_zero_based: indexes.add_block(block, ordinal),
            )
            first[target.object_ordinal_zero_based] = result
            state.pass_complete(
                target.object_ordinal_zero_based,
                pass_number=1,
                decompressed_bytes=result.transport.decompressed_bytes,
                record_count=result.transport.record_count,
                event_count=result.transport.event_count,
                stream_sha256=result.transport.decompressed_stream_sha256,
            )
        block_commitments, weak_commitments = indexes.close()
        discovery: CandidateDiscovery = discover_candidates(indexes, block_commitments, weak_commitments)
        reducer_rows = discovery.reducer_rows
        resources.append(
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
                resource_rows=resources,
                terminal_class="R11A_ARTIFACT_CAP_EXCEEDED",
                research_conclusion="ROOT_CAUSE_NOT_PROVEN_EMPTY_CAP_FALLBACK",
            )
            return RunResult(artifact, artifact.terminal_class, artifact.research_conclusion)

        materializer = CandidateMaterializer(meter, inputs.limits, discovery)
        for target in inputs.selection.targets:
            result = parse_object_pass(
                compressed_path=compressed_paths[target.object_key],
                target=target,
                limits=inputs.limits,
                runtime_guard=guard,
                on_block=materializer.add_block,
            )
            second[target.object_ordinal_zero_based] = result
            if not result.exact_match(first[target.object_ordinal_zero_based]):
                raise RunnerError("independent local passes differ")
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
                resource_rows=resources,
                terminal_class="R11A_ARTIFACT_CAP_EXCEEDED",
                research_conclusion="ROOT_CAUSE_NOT_PROVEN_EMPTY_CAP_FALLBACK",
            )
            return RunResult(artifact, artifact.terminal_class, artifact.research_conclusion)

        aggregate = _aggregate_conservation(first, second)
        taxonomy = classify_materialized_candidates(materialized, meter, session.emitter)
        taxonomy = dataclasses.replace(
            taxonomy,
            secondary_sort_rows=taxonomy.secondary_sort_rows + taxonomy.join_partition_rows,
        )
        terminal, conclusion, return_code = _terminal(state, taxonomy, aggregate)
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
        resources.append(
            _resource_row(
                meter=meter,
                guard=guard,
                phase="SCIENCE_COMPLETE_BEFORE_PACKAGING",
                state=state,
                additional={"aggregate_parse_conservation": aggregate},
            )
        )
        artifact = session.finalize_full(
            state=state,
            context=inputs.context,
            reducer_rows=reducer_rows,
            resource_rows=resources,
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
        cleanup_error: BaseException | None = None
        try:
            _checked_processing_cleanup(meter, indexes=indexes, materializer=materializer)
        except BaseException as cleanup_exc:
            cleanup_error = cleanup_exc
            state.stop(
                "CHECKED_PROCESSING_CLEANUP_FAILURE",
                phase="FAIL_CLOSED_CLEANUP",
                evidence={"cleanup_exception_type_sha256": hashlib.sha256(type(cleanup_exc).__name__.encode()).hexdigest()},
            )
        resources.append(
            _resource_row(
                meter=meter,
                guard=guard,
                phase="FAIL_CLOSED_BEFORE_MINIMAL_ARTIFACT",
                state=state,
                additional={
                    "stop_code": stop_code,
                    "cleanup_completed": cleanup_error is None,
                },
            )
        )
        try:
            artifact = session.finalize_empty(
                state=state,
                context=inputs.context,
                reducer_rows=reducer_rows,
                resource_rows=resources,
                terminal_class="R11A_DIAGNOSTIC_INCOMPLETE",
                research_conclusion="ROOT_CAUSE_NOT_PROVEN_FAIL_CLOSED_EMPTY_ARTIFACT",
            )
        except Exception:
            session.abort()
            raise
        return RunResult(artifact, artifact.terminal_class, artifact.research_conclusion)


def run_network(
    *,
    inputs: RunInputs,
    credentials: AWSCredentials,
    pricing_snapshot: PricingSnapshot,
) -> RunResult:
    guard, meter, state, session = prepare(inputs)
    objects_directory = meter.root / "objects"
    objects_directory.mkdir(exist_ok=False)
    budget = BudgetGuard(inputs.limits, pricing_snapshot, inputs.selection.aggregate_expected_compressed_bytes)
    paths: dict[str, Path] = {}
    resources: list[dict[str, object]] = []
    try:
        for target in inputs.selection.targets:
            path = objects_directory / f"object-{target.object_ordinal_zero_based:03d}.lz4"
            paths[target.object_key] = download_exact_object(
                target=target,
                destination=path,
                credentials=credentials,
                state=state,
                meter=meter,
                runtime_guard=guard,
                budget_guard=budget,
            )
        resources.append(
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
            compressed_paths=paths,
            state=state,
            guard=guard,
            meter=meter,
            session=session,
            initial_resource_rows=resources,
        )
    except Exception as exc:
        stop_code = _safe_stop_code(exc)
        state.stop(
            stop_code,
            phase="NETWORK_OR_PRECOLLECTOR_FAILURE",
            evidence={"exception_type_sha256": hashlib.sha256(type(exc).__name__.encode()).hexdigest()},
        )
        resources.append(
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
            reducer_rows=(),
            resource_rows=resources,
            terminal_class="R11A_DIAGNOSTIC_INCOMPLETE",
            research_conclusion="ROOT_CAUSE_NOT_PROVEN_NETWORK_FAIL_CLOSED_EMPTY_ARTIFACT",
        )
        return RunResult(artifact, artifact.terminal_class, artifact.research_conclusion)
