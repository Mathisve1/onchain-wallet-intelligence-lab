from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Mapping, Sequence
from pathlib import Path

from .artifact import ArtifactOutcome, ArtifactSession, ScientificCapExceeded
from .artifact_schema import AUTHORITATIVE_UNIT_UNIVERSES
from .index import CandidateDiscovery, FirstPassIndexes, discover_candidates
from .limits import DEFAULT_LIMITS, R11ALimits
from .materialize import CandidateMaterializer
from .network import AWSCredentials, download_exact_object
from .parser import ObjectPassResult, parse_object_pass
from .pricing import BudgetGuard, PricingSnapshot
from .runtime import ExecutionEvidenceState, RuntimeGuard
from .selection import DEFAULT_SELECTION, Selection
from .storage_r7 import StorageBoundaryError, WorkspaceMeter
from .taxonomy import TaxonomyBoundaryError, TaxonomyResult, classify_materialized_candidates


class RunnerBoundaryError(RuntimeError):
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
    state: ExecutionEvidenceState,
    phase: str,
    additional: Mapping[str, object] | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "record_type": "R11A_V2_RESOURCE_MEASUREMENT",
        "phase": phase,
        "elapsed_runtime_seconds_floor": guard.elapsed_seconds_floor(),
        "tracked_workspace_bytes": meter.known_bytes,
        "reserved_workspace_bytes": meter.reserved_bytes,
        "peak_tracked_workspace_bytes": meter.peak_known_bytes,
        "peak_bounded_workspace_bytes": meter.peak_bounded_bytes,
        "network_request_count": state.network_request_count,
    }
    if additional is not None:
        row.update(additional)
    return row


def _safe_stop_code(exc: BaseException) -> str:
    if isinstance(exc, ScientificCapExceeded):
        return "SCIENTIFIC_RETENTION_CAP_EXCEEDED"
    if isinstance(exc, StorageBoundaryError):
        return "WORKSPACE_OR_ATOMIC_STORAGE_BOUNDARY_FAILURE"
    if isinstance(exc, TaxonomyBoundaryError):
        return "TAXONOMY_OR_PROOF_BOUNDARY_FAILURE"
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
        raise RunnerBoundaryError("both passes must contain exact 72-object scope")
    totals: dict[str, int] = {}
    per_object_equal = True
    for ordinal in range(72):
        if not first[ordinal].exact_match(second[ordinal]):
            per_object_equal = False
            break
        for field, value in dataclasses.asdict(first[ordinal].conservation).items():
            totals[field] = totals.get(field, 0) + int(value)
    if not per_object_equal:
        raise RunnerBoundaryError("independent local passes differ")
    raw_events = totals["raw_event_observation_count"]
    partitions = {
        "wallet": totals["valid_wallet_occurrence_count"]
        + totals["invalid_wallet_occurrence_count"],
        "coin": totals["valid_coin_occurrence_count"]
        + totals["invalid_coin_occurrence_count"],
        "tid": totals["valid_tid_occurrence_count"]
        + totals["invalid_tid_occurrence_count"],
    }
    if any(value != raw_events for value in partitions.values()):
        raise RunnerBoundaryError("raw event schema partitions do not conserve")
    return {
        "status": "EXACT_TWO_PASS_LAYER_CONSERVATION_PASS",
        "per_object_pass_equality": True,
        "totals": totals,
        "raw_event_partition_totals": partitions,
    }


def _taxonomy_complete(
    *,
    state: ExecutionEvidenceState,
    taxonomy: TaxonomyResult,
    aggregate: Mapping[str, object],
    meter: WorkspaceMeter,
    guard: RuntimeGuard,
) -> bool:
    universe_names = tuple(str(row["unit_universe"]) for row in taxonomy.universe_rows)
    unit_conservation = all(
        sum(int(value) for value in row["primary_taxon_group_counts"].values())
        == int(row["group_count"])
        and sum(int(value) for value in row["primary_taxon_occurrence_counts"].values())
        == int(row["occurrence_count"])
        for row in taxonomy.universe_rows
    )
    join = taxonomy.join_validation
    totals = aggregate["totals"]
    block_conservation = int(totals["raw_block_observation_count"]) >= taxonomy.repeated_block_observation_count
    legacy_conservation = taxonomy.legacy_repeat_occurrence_count == (
        taxonomy.valid_tid_legacy_repeat_occurrence_count
        + taxonomy.invalid_tid_legacy_repeat_occurrence_count
    )
    guard.check_packaging_phase("evaluate complete taxonomy terminal")
    workspace_within_cap = (
        meter.known_bytes + meter.reserved_bytes
        <= meter.limits.maximum_ephemeral_workspace_bytes
    )
    return bool(
        state.exact_scope_complete()
        and aggregate["status"] == "EXACT_TWO_PASS_LAYER_CONSERVATION_PASS"
        and taxonomy.exact_three_utc_days
        and universe_names == AUTHORITATIVE_UNIT_UNIVERSES
        and unit_conservation
        and block_conservation
        and legacy_conservation
        and join.all_unit_ids_unique
        and join.all_proof_ids_unique
        and join.all_nonnull_proof_references_resolve_exactly_once
        and join.all_retained_rows_reference_exactly_one_unit
        and join.all_referenced_projections_are_byte_equal
        and taxonomy.unclassifiable_group_count == 0
        and taxonomy.unclassifiable_occurrence_count == 0
        and workspace_within_cap
    )


def prepare(
    inputs: RunInputs,
) -> tuple[RuntimeGuard, WorkspaceMeter, ExecutionEvidenceState, ArtifactSession]:
    inputs.limits.validate()
    inputs.selection.validate()
    start_epoch_ns = inputs.context.get("workflow_start_epoch_ns")
    if type(start_epoch_ns) is not int:
        raise RunnerBoundaryError("workflow start epoch is absent from runtime context")
    guard = RuntimeGuard.from_start_epoch_ns(inputs.limits, start_epoch_ns)
    meter = WorkspaceMeter(inputs.workspace, inputs.limits, guard)
    meter.bootstrap()
    state = ExecutionEvidenceState(inputs.selection.targets, inputs.limits)
    session = ArtifactSession(inputs.workspace, meter, inputs.limits, guard)
    return guard, meter, state, session


def _checked_cleanup(
    meter: WorkspaceMeter,
    *,
    preserve_artifact_paths: bool = True,
) -> None:
    protected = {".r11a-v2-artifact.staging", "r11a-v2-artifact"} if preserve_artifact_paths else set()
    errors: list[BaseException] = []
    for path in sorted(meter.root.iterdir(), key=lambda value: value.name.encode("utf-8"), reverse=True):
        if path.name in protected:
            continue
        try:
            if path.is_dir():
                meter.checked_rmtree(path)
            elif path.is_file():
                meter.delete_file(path)
            else:
                raise RunnerBoundaryError("unexpected workspace entry type")
        except BaseException as exc:
            errors.append(exc)
    if errors:
        raise RunnerBoundaryError("checked processing cleanup failed") from errors[0]


def _empty_failure(
    *,
    session: ArtifactSession,
    state: ExecutionEvidenceState,
    context: Mapping[str, object],
    reducer_rows: Sequence[Mapping[str, object]],
    resources: Sequence[Mapping[str, object]],
    terminal_class: str,
    conclusion: str,
) -> RunResult:
    artifact = session.finalize_empty(
        state=state,
        context=context,
        reducer_rows=reducer_rows,
        resource_rows=resources,
        terminal_class=terminal_class,
        research_conclusion=conclusion,
    )
    return RunResult(artifact, terminal_class, conclusion)


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
    expected = {target.object_key for target in inputs.selection.targets}
    if set(compressed_paths) != expected:
        raise RunnerBoundaryError("compressed paths do not equal exact selection")
    first: dict[int, ObjectPassResult] = {}
    second: dict[int, ObjectPassResult] = {}
    reducer_rows: tuple[dict[str, object], ...] = ()
    resources = [dict(value) for value in initial_resource_rows]
    indexes: FirstPassIndexes | None = None
    discovery: CandidateDiscovery | None = None
    materializer: CandidateMaterializer | None = None
    try:
        state.mark_phase("FIRST_LOCAL_PASS")
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
            first[target.object_ordinal_zero_based] = result
            state.pass_complete(
                target.object_ordinal_zero_based,
                pass_number=1,
                decompressed_bytes=result.transport.decompressed_bytes,
                record_count=result.transport.record_count,
                event_count=result.transport.event_count,
                stream_sha256=result.transport.decompressed_stream_sha256,
                conservation=result.conservation.as_mapping(),
            )
        block_stats, weak_stats = indexes.close()
        state.mark_phase("PRIMARY_REDUCERS")
        discovery = discover_candidates(indexes, block_stats, weak_stats)
        reducer_rows = discovery.reducer_rows
        resources.append(
            _resource_row(
                meter=meter,
                guard=guard,
                state=state,
                phase="PRIMARY_REDUCERS_COMPLETE",
                additional={
                    "repeated_block_group_count": discovery.repeated_block_group_count,
                    "repeated_block_observation_count": discovery.repeated_block_observation_count,
                    "repeated_legacy_group_count": discovery.repeated_weak_group_count,
                    "repeated_legacy_observation_count": discovery.repeated_weak_observation_count,
                },
            )
        )
        if discovery.cap_fallback_required:
            state.stop("DISCOVERY_RETENTION_CAP_EXCEEDED")
            discovery.candidates.close_delete()
            discovery = None
            _checked_cleanup(meter)
            return _empty_failure(
                session=session,
                state=state,
                context=inputs.context,
                reducer_rows=reducer_rows,
                resources=resources,
                terminal_class="R11A_V2_ARTIFACT_CAP_EXCEEDED",
                conclusion="ROOT_CAUSE_NOT_PROVEN_EMPTY_CAP_FALLBACK",
            )
        state.mark_phase("SECOND_LOCAL_PASS")
        materializer = CandidateMaterializer(meter, inputs.limits, discovery)
        for target in inputs.selection.targets:
            result = parse_object_pass(
                compressed_path=compressed_paths[target.object_key],
                target=target,
                limits=inputs.limits,
                runtime_guard=guard,
                on_block=lambda block, ordinal=target.object_ordinal_zero_based: materializer.add_block(
                    block, ordinal
                ),
            )
            second[target.object_ordinal_zero_based] = result
            if not result.exact_match(first[target.object_ordinal_zero_based]):
                raise RunnerBoundaryError("independent local passes differ")
            state.pass_complete(
                target.object_ordinal_zero_based,
                pass_number=2,
                decompressed_bytes=result.transport.decompressed_bytes,
                record_count=result.transport.record_count,
                event_count=result.transport.event_count,
                stream_sha256=result.transport.decompressed_stream_sha256,
                conservation=result.conservation.as_mapping(),
            )
            meter.delete_file(compressed_paths[target.object_key])
        materialized = materializer.close()
        discovery.candidates.close_delete()
        discovery = None
        if materialized.cap_fallback_required:
            state.stop("MATERIALIZATION_RETENTION_CAP_EXCEEDED")
            _checked_cleanup(meter)
            return _empty_failure(
                session=session,
                state=state,
                context=inputs.context,
                reducer_rows=reducer_rows,
                resources=resources,
                terminal_class="R11A_V2_ARTIFACT_CAP_EXCEEDED",
                conclusion="ROOT_CAUSE_NOT_PROVEN_EMPTY_CAP_FALLBACK",
            )
        aggregate = _aggregate_conservation(first, second)
        state.mark_phase("TAXONOMY")
        taxonomy = classify_materialized_candidates(
            materialized,
            meter,
            session.emitter,
            exact_three_utc_days=inputs.selection.complete_utc_day_count == 3,
        )
        complete = _taxonomy_complete(
            state=state,
            taxonomy=taxonomy,
            aggregate=aggregate,
            meter=meter,
            guard=guard,
        )
        terminal = (
            "R11A_V2_ROOT_CAUSE_TAXONOMY_COMPLETE"
            if complete
            else "R11A_V2_DIAGNOSTIC_INCOMPLETE"
        )
        conclusion = (
            "PROVEN_COMPLETE_TAXONOMY_ONLY"
            if complete
            else "ROOT_CAUSE_NOT_FULLY_PROVEN_NO_REPAIR_AUTHORIZED"
        )
        if not complete:
            state.stop(
                "FULL_SCOPE_TAXONOMY_INCOMPLETE",
                evidence={
                    "unclassifiable_group_count": taxonomy.unclassifiable_group_count,
                    "unclassifiable_occurrence_count": taxonomy.unclassifiable_occurrence_count,
                },
            )
        resources.append(
            _resource_row(
                meter=meter,
                guard=guard,
                state=state,
                phase="SCIENCE_COMPLETE_BEFORE_PACKAGING",
                additional={"aggregate_conservation": aggregate},
            )
        )
        state.mark_phase("ARTIFACT_PACKAGING")
        artifact = session.finalize_full(
            state=state,
            context=inputs.context,
            reducer_rows=reducer_rows,
            resource_rows=resources,
            terminal_class=terminal,
            research_conclusion=conclusion,
            taxonomy_result=taxonomy,
        )
        return RunResult(artifact, terminal, conclusion)
    except ScientificCapExceeded as exc:
        state.stop(
            _safe_stop_code(exc),
            evidence={"exception_type_sha256": hashlib.sha256(type(exc).__name__.encode()).hexdigest()},
        )
        _checked_cleanup(meter)
        return _empty_failure(
            session=session,
            state=state,
            context=inputs.context,
            reducer_rows=reducer_rows,
            resources=resources,
            terminal_class="R11A_V2_ARTIFACT_CAP_EXCEEDED",
            conclusion="ROOT_CAUSE_NOT_PROVEN_EMPTY_CAP_FALLBACK",
        )
    except Exception as exc:
        state.stop(
            _safe_stop_code(exc),
            evidence={"exception_type_sha256": hashlib.sha256(type(exc).__name__.encode()).hexdigest()},
        )
        if discovery is not None:
            discovery.candidates.close_delete()
        cleanup_error: BaseException | None = None
        try:
            _checked_cleanup(meter)
        except BaseException as observed:
            cleanup_error = observed
            state.stop(
                "CHECKED_CLEANUP_FAILURE",
                evidence={"exception_type_sha256": hashlib.sha256(type(observed).__name__.encode()).hexdigest()},
            )
        resources.append(
            _resource_row(
                meter=meter,
                guard=guard,
                state=state,
                phase="FAIL_CLOSED_BEFORE_MINIMAL_ARTIFACT",
                additional={"cleanup_completed": cleanup_error is None},
            )
        )
        return _empty_failure(
            session=session,
            state=state,
            context=inputs.context,
            reducer_rows=reducer_rows,
            resources=resources,
            terminal_class="R11A_V2_FAIL_CLOSED_EARLY_STOP",
            conclusion="ROOT_CAUSE_NOT_PROVEN_FAIL_CLOSED_EMPTY_ARTIFACT",
        )


def run_network(
    *,
    inputs: RunInputs,
    credentials: AWSCredentials,
    pricing_snapshot: PricingSnapshot,
) -> RunResult:
    guard, meter, state, session = prepare(inputs)
    objects = meter.root / "objects"
    objects.mkdir(exist_ok=False)
    budget = BudgetGuard(
        inputs.limits,
        pricing_snapshot,
        inputs.selection.aggregate_expected_compressed_bytes,
    )
    paths: dict[str, Path] = {}
    resources: list[dict[str, object]] = []
    try:
        for target in inputs.selection.targets:
            path = objects / f"object-{target.object_ordinal_zero_based:03d}.lz4"
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
                state=state,
                phase="ALL_72_OBJECTS_DOWNLOADED",
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
        state.stop(
            _safe_stop_code(exc),
            evidence={"exception_type_sha256": hashlib.sha256(type(exc).__name__.encode()).hexdigest()},
        )
        try:
            _checked_cleanup(meter)
        except BaseException as cleanup_exc:
            state.stop(
                "CHECKED_NETWORK_CLEANUP_FAILURE",
                evidence={"exception_type_sha256": hashlib.sha256(type(cleanup_exc).__name__.encode()).hexdigest()},
            )
        resources.append(
            _resource_row(
                meter=meter,
                guard=guard,
                state=state,
                phase="NETWORK_FAILURE_BEFORE_MINIMAL_ARTIFACT",
            )
        )
        return _empty_failure(
            session=session,
            state=state,
            context=inputs.context,
            reducer_rows=(),
            resources=resources,
            terminal_class="R11A_V2_FAIL_CLOSED_EARLY_STOP",
            conclusion="ROOT_CAUSE_NOT_PROVEN_NETWORK_FAIL_CLOSED_EMPTY_ARTIFACT",
        )
