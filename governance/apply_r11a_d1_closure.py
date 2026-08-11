#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "research/archive_inventory/r11a_implementation/collector.py"
RUNNER = ROOT / "research/archive_inventory/r11a_implementation/runner.py"


class RepairError(ValueError):
    pass


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RepairError(f"{label}: expected one target, observed {count}")
    return text.replace(old, new, 1)


def patch_collector() -> None:
    text = COLLECTOR.read_text(encoding="utf-8")
    text = replace_once(
        text,
        """from research.archive_inventory.r11a_implementation import diagnostic, identity, schema, storage
""",
        """from research.archive_inventory.r11a_implementation import diagnostic, identity, runtime, schema, storage
""",
        "collector runtime import",
    )
    helper = '''\n\ndef _expanded_reducer_rows(\n    rows: Sequence[Mapping[str, object]],\n    *,\n    scientific_retained: bool,\n    cap_fallback: bool,\n) -> tuple[dict[str, object], ...]:\n    output: list[dict[str, object]] = []\n    for row in rows:\n        reducer_id = str(row["reducer_id"])\n        discovered_groups = int(row["discovered_repeat_group_count"])\n        discovered_observations = int(row["discovered_repeat_observation_count"])\n        output.append({\n            "record_type": "REDUCER_PARTITION_CONSERVATION",\n            "reducer_id": reducer_id,\n            "partition_ordinal_zero_based": int(row["partition_ordinal_zero_based"]),\n            "processing_status": "COMPLETE",\n            "partition_function": "FIRST_BYTE_OF_SHA256_OF_THE_COMPLETE_EQUALITY_KEY_BYTES",\n            "record_encoding": (\n                "UNSIGNED_UINT64_BIG_ENDIAN_BLOCK_NUMBER_PLUS_UNSIGNED_UINT64_BIG_ENDIAN_GLOBAL_BLOCK_ORDINAL"\n                if reducer_id == "BLOCK_NUMBER"\n                else "FRAME_OF_COMPLETE_EQUALITY_KEY_BYTES_PLUS_UNSIGNED_UINT64_BIG_ENDIAN_GLOBAL_EVENT_ORDINAL"\n            ),\n            "record_count": int(row["record_count"]),\n            "logical_input_bytes": int(row["logical_input_bytes"]),\n            "unsorted_record_stream_sha256": row["unsorted_record_stream_sha256"],\n            "sorted_record_stream_sha256": row["sorted_record_stream_sha256"],\n            "singleton_block_observation_count": (\n                int(row["record_count"]) - discovered_observations\n                if reducer_id == "BLOCK_NUMBER" else None\n            ),\n            "singleton_block_detail_commitment_sha256": None,\n            "discovered_repeat_group_count": discovered_groups,\n            "discovered_repeat_observation_count": discovered_observations,\n            "retained_repeat_group_count": discovered_groups if scientific_retained else 0,\n            "retained_repeat_observation_count": discovered_observations if scientific_retained else 0,\n            "omitted_due_to_cap_group_count": discovered_groups if cap_fallback else 0,\n            "omitted_due_to_cap_observation_count": discovered_observations if cap_fallback else 0,\n            "omitted_group_commitment_sha256": None,\n            "not_retained_due_to_incomplete_group_count": 0,\n            "not_retained_due_to_incomplete_observation_count": 0,\n            "incomplete_stop_group_commitment_sha256": None,\n        })\n    if len(output) != 512:\n        raise R11ACollectorError("expanded reducer ledger must contain 512 rows")\n    return tuple(output)\n'''
    text = replace_once(
        text,
        "\ndef seal_artifact(\n",
        helper + "\ndef seal_artifact(\n",
        "collector reducer expansion helper",
    )
    text = replace_once(
        text,
        """    reducer_rows: Sequence[Mapping[str, object]],
    meter: storage.WorkspaceMeter,
""",
        """    reducer_rows: Sequence[Mapping[str, object]],
    stop_rows: Sequence[Mapping[str, object]],
    meter: storage.WorkspaceMeter,
""",
        "collector seal stop rows signature",
    )
    text = replace_once(
        text,
        '        "get_object_request_count": len(object_rows),\n',
        '        "get_object_request_count": sum(int(row["get_object_request_count"]) for row in object_rows),\n',
        "collector request projection",
    )
    text = replace_once(
        text,
        """    files["r11a-preflight-stop-evidence.json"] = schema.deterministic_json_document({
        "stop_conditions": [],
        "network_execution_was_release_gated": True,
        "rerun_authorized": False,
    })
""",
        """    files["r11a-preflight-stop-evidence.json"] = schema.deterministic_json_document(list(stop_rows))
""",
        "collector exact stop ledger",
    )
    text = replace_once(
        text,
        """    limits: R11ALimits = DEFAULT_LIMITS,
) -> ExecutionOutcome:
    started = time.monotonic()
    meter = storage.WorkspaceMeter(workspace, limits)
    meter.bootstrap()
""",
        """    limits: R11ALimits = DEFAULT_LIMITS,
    evidence_state: runtime.ExecutionEvidenceState | None = None,
    runtime_guard: runtime.RuntimeGuard | None = None,
) -> ExecutionOutcome:
    started = time.monotonic()
    guard = runtime_guard or runtime.RuntimeGuard(limits)
    meter = runtime.GuardedWorkspaceMeter(workspace, limits, runtime_guard=guard)
    meter.bootstrap()
    state = evidence_state or runtime.ExecutionEvidenceState(runtime.runtime_targets(targets), limits)
    if evidence_state is None:
        for target in targets:
            state.mark_request_sent(target.object_ordinal_zero_based)
            state.mark_response_metadata(
                target.object_ordinal_zero_based,
                etag=target.expected_etag,
                content_length=target.expected_size_bytes,
            )
            state.mark_body_progress(target.object_ordinal_zero_based, target.expected_size_bytes)
            state.mark_body_complete(
                target.object_ordinal_zero_based,
                target.expected_compressed_sha256,
            )
""",
        "collector guarded local runner signature",
    )
    text = replace_once(
        text,
        """        for target in targets:
            path = compressed_paths.get(target.object_key)
""",
        """        for target in targets:
            guard.check(f"before first parse object {target.object_ordinal_zero_based}")
            path = compressed_paths.get(target.object_key)
""",
        "collector first pass runtime guard",
    )
    text = replace_once(
        text,
        """            runs.append(ObjectRun(target, path, first))
            compressed = b""
""",
        """            runs.append(ObjectRun(target, path, first))
            state.mark_first_parse(target.object_ordinal_zero_based, dataclasses.asdict(first))
            guard.check(f"after first parse object {target.object_ordinal_zero_based}")
            compressed = b""
""",
        "collector first parse evidence",
    )
    text = replace_once(
        text,
        """    discovery = discover(
""",
        """    guard.check("before reducer discovery")
    discovery = discover(
""",
        "collector reducer runtime guard",
    )
    text = replace_once(
        text,
        """    materialized: list[identity.BlockObservation] = []
    completed_runs: list[ObjectRun] = []
    interesting = discovery.interesting_blocks
""",
        """    materialized: list[identity.BlockObservation] = []
    completed_runs: list[ObjectRun] = []
    maximum_materialized_blocks = min(
        limits.maximum_repeated_observations_retained,
        limits.maximum_retained_scientific_output_bytes // 2048,
    )
    preclassified_cap = (
        discovery.legacy_repeat_group_count > limits.maximum_repeated_legacy_key_groups_retained
        or discovery.legacy_repeat_observation_count > limits.maximum_repeated_observations_retained
        or discovery.repeated_block_group_count > limits.maximum_repeated_block_groups_retained
        or len(discovery.interesting_blocks) > maximum_materialized_blocks
    )
    interesting = set() if preclassified_cap else discovery.interesting_blocks
""",
        "collector prematerialization cap gate",
    )
    text = replace_once(
        text,
        """    for run in runs:
        compressed = run.compressed_path.read_bytes()
""",
        """    for run in runs:
        guard.check(f"before second parse object {run.target.object_ordinal_zero_based}")
        compressed = run.compressed_path.read_bytes()
""",
        "collector second pass runtime guard",
    )
    text = replace_once(
        text,
        """        materialized.extend(blocks)
        completed_runs.append(dataclasses.replace(run, second_pass=second))
""",
        """        if not preclassified_cap:
            materialized.extend(blocks)
        completed_runs.append(dataclasses.replace(run, second_pass=second))
        state.mark_second_parse(run.target.object_ordinal_zero_based, dataclasses.asdict(second))
        guard.check(f"after second parse object {run.target.object_ordinal_zero_based}")
""",
        "collector second parse evidence",
    )
    text = replace_once(
        text,
        """    report = diagnostic.classify(materialized, limits=limits)
    report = dataclasses.replace(
        report,
        raw_block_observation_count=sum(item.first_pass.raw_record_count for item in completed_runs),
        raw_event_observation_count=sum(item.first_pass.raw_event_observation_count for item in completed_runs),
    )
    object_rows = [item.ledger_row("COMPLETE_TWO_LOCAL_PASSES") for item in completed_runs]
""",
        """    raw_block_count = sum(item.first_pass.raw_record_count for item in completed_runs)
    raw_event_count = sum(item.first_pass.raw_event_observation_count for item in completed_runs)
    if preclassified_cap:
        base_report = diagnostic.classify((), limits=limits)
        report = dataclasses.replace(
            base_report,
            terminal_class=diagnostic.TerminalClass.ARTIFACT_CAP_EXCEEDED,
            root_cause_claim_status="NOT_PROVEN",
            raw_block_observation_count=raw_block_count,
            raw_event_observation_count=raw_event_count,
            retention_caps_exceeded=True,
        )
        state.trigger(
            "RETENTION_OR_ARTIFACT_CAP_EXCEEDED",
            phase="BEFORE_SCIENTIFIC_MATERIALIZATION",
            inputs={"interesting_block_count": len(discovery.interesting_blocks)},
        )
    else:
        report = diagnostic.classify(materialized, limits=limits)
        report = dataclasses.replace(
            report,
            raw_block_observation_count=raw_block_count,
            raw_event_observation_count=raw_event_count,
        )
        if report.terminal_class is diagnostic.TerminalClass.DIAGNOSTIC_INCOMPLETE:
            state.trigger(
                "TAXONOMY_OR_CONSERVATION_INCOMPLETE",
                phase="FINAL_VALIDATION_ONLY",
                inputs={"unclassifiable_group_count": report.unclassifiable_group_count},
            )
    object_rows = list(state.object_rows())
""",
        "collector cap-safe classification",
    )
    text = replace_once(
        text,
        """            reducer_rows=discovery.reducer_rows,
            meter=meter,
""",
        """            reducer_rows=_expanded_reducer_rows(
                discovery.reducer_rows,
                scientific_retained=report.terminal_class is not diagnostic.TerminalClass.ARTIFACT_CAP_EXCEEDED,
                cap_fallback=report.terminal_class is diagnostic.TerminalClass.ARTIFACT_CAP_EXCEEDED,
            ),
            stop_rows=state.stop_rows(),
            meter=meter,
""",
        "collector exact complete ledgers",
    )
    COLLECTOR.write_text(text, encoding="utf-8")


def patch_runner() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    text = replace_once(
        text,
        """            workspace=workspace,
            artifact_directory=artifact_directory,
            context=context,
            limits=limits,
        )
""",
        """            workspace=workspace / "processing",
            artifact_directory=artifact_directory,
            context=context,
            limits=limits,
            evidence_state=state,
            runtime_guard=guard,
        )
""",
        "runner guarded local call",
    )
    RUNNER.write_text(text, encoding="utf-8")


def main() -> int:
    patch_collector()
    patch_runner()
    Path(__file__).unlink()
    print("R11A_D1_LOCAL_CLOSURE_APPLIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
