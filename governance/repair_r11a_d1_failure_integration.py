#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "research/archive_inventory/r11a_implementation/collector.py"
WORKFLOW = ROOT / "research/archive_inventory/r11a_implementation/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic.yml"
SEALER = ROOT / "governance/seal_r11a_implementation.py"
VALIDATOR = ROOT / "governance/validate_r11a_implementation.py"


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
        "from research.archive_inventory.r11a_implementation import diagnostic, identity, schema, storage\n",
        "from research.archive_inventory.r11a_implementation import diagnostic, failure, identity, runtime, schema, storage\n",
        "collector runtime imports",
    )

    text = replace_once(
        text,
        """def seal_artifact(
    *,
    staging: Path,
    report: diagnostic.DiagnosticReport,
    context: Mapping[str, object],
    object_rows: Sequence[Mapping[str, object]],
    reducer_rows: Sequence[Mapping[str, object]],
    meter: storage.WorkspaceMeter,
    elapsed_runtime_seconds: int,
    limits: R11ALimits = DEFAULT_LIMITS,
) -> tuple[dict[str, object], dict[str, bytes]]:
""",
        """def seal_artifact(
    *,
    staging: Path,
    report: diagnostic.DiagnosticReport,
    context: Mapping[str, object],
    object_rows: Sequence[Mapping[str, object]],
    reducer_rows: Sequence[Mapping[str, object]],
    stop_rows: Sequence[Mapping[str, object]],
    meter: storage.WorkspaceMeter,
    elapsed_runtime_seconds: int,
    limits: R11ALimits = DEFAULT_LIMITS,
) -> tuple[dict[str, object], dict[str, bytes]]:
""",
        "collector seal stop-ledger signature",
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
        '        "get_object_request_count": len(object_rows),\n',
        '        "get_object_request_count": sum(int(row["get_object_request_count"]) for row in object_rows),\n',
        "collector request count projection",
    )

    signature_old = """def run_from_compressed_files(
    *,
    targets: Sequence[Target],
    compressed_paths: Mapping[str, Path],
    workspace: Path,
    artifact_directory: Path,
    context: Mapping[str, object],
    limits: R11ALimits = DEFAULT_LIMITS,
) -> ExecutionOutcome:
"""
    signature_new = """def run_from_compressed_files(
    *,
    targets: Sequence[Target],
    compressed_paths: Mapping[str, Path],
    workspace: Path,
    artifact_directory: Path,
    context: Mapping[str, object],
    limits: R11ALimits = DEFAULT_LIMITS,
    evidence_state: runtime.ExecutionEvidenceState | None = None,
    runtime_guard: runtime.RuntimeGuard | None = None,
) -> ExecutionOutcome:
"""
    text = replace_once(text, signature_old, signature_new, "collector local runner signature")
    text = replace_once(
        text,
        """    started = time.monotonic()
    meter = storage.WorkspaceMeter(workspace, limits)
    meter.bootstrap()
""",
        """    started = time.monotonic()
    meter = storage.WorkspaceMeter(workspace, limits)
    meter.bootstrap()
    guard = runtime_guard or runtime.RuntimeGuard(limits)
    state = evidence_state or runtime.ExecutionEvidenceState(
        runtime.runtime_targets_from_objects(targets),
        limits,
    )
    if evidence_state is None:
        for target in targets:
            path = compressed_paths.get(target.object_key)
            if path is None or not path.is_file():
                raise R11ACollectorError(f"compressed object absent: {target.object_key}")
            state.mark_request_sent(target.object_ordinal_zero_based)
            state.mark_response_metadata(
                target.object_ordinal_zero_based,
                etag=target.expected_etag,
                content_length=target.expected_size_bytes,
            )
            state.mark_body_progress(target.object_ordinal_zero_based, target.expected_size_bytes)
            state.mark_body_complete(
                target.object_ordinal_zero_based,
                sha256=target.expected_compressed_sha256,
            )
""",
        "collector runtime guard and evidence state",
    )
    text = replace_once(
        text,
        """        for target in targets:
            path = compressed_paths.get(target.object_key)
""",
        """        for target in targets:
            guard.check(f"first parse object {target.object_ordinal_zero_based}")
            path = compressed_paths.get(target.object_key)
""",
        "collector first-pass runtime guard",
    )
    text = replace_once(
        text,
        """            runs.append(ObjectRun(target, path, first))
            compressed = b""
""",
        """            runs.append(ObjectRun(target, path, first))
            state.mark_first_parse(
                target.object_ordinal_zero_based,
                dataclasses.asdict(first),
            )
            guard.check(f"after first parse object {target.object_ordinal_zero_based}")
            compressed = b""
""",
        "collector first-pass state",
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
        """    for run in runs:
        compressed = run.compressed_path.read_bytes()
""",
        """    for run in runs:
        guard.check(f"second parse object {run.target.object_ordinal_zero_based}")
        compressed = run.compressed_path.read_bytes()
""",
        "collector second-pass runtime guard",
    )
    text = replace_once(
        text,
        """        completed_runs.append(dataclasses.replace(run, second_pass=second))
        run.compressed_path.unlink(missing_ok=True)
""",
        """        completed_runs.append(dataclasses.replace(run, second_pass=second))
        state.mark_second_parse(
            run.target.object_ordinal_zero_based,
            dataclasses.asdict(second),
        )
        guard.check(f"after second parse object {run.target.object_ordinal_zero_based}")
        run.compressed_path.unlink(missing_ok=True)
""",
        "collector second-pass state",
    )
    text = replace_once(
        text,
        """    object_rows = [item.ledger_row("COMPLETE_TWO_LOCAL_PASSES") for item in completed_runs]
""",
        """    object_rows = list(state.object_rows())
""",
        "collector object ledger source",
    )
    text = replace_once(
        text,
        """            reducer_rows=discovery.reducer_rows,
            meter=meter,
""",
        """            reducer_rows=discovery.reducer_rows,
            stop_rows=state.stop_rows(),
            meter=meter,
""",
        "collector complete stop rows",
    )

    execute_start = text.index("def execute_network(\n")
    main_start = text.index("\ndef main(", execute_start)
    old_execute = text[execute_start:main_start]
    new_execute = '''def _stop_for_exception(exc: Exception) -> tuple[str, str, dict[str, object]]:
    message = str(exc).lower()
    if isinstance(exc, runtime.R11ARuntimeError) or "runtime cap" in message:
        return (
            "RUNTIME_CAP_REACHED",
            "DURING_RUNTIME_OPERATION",
            {"failure_class": type(exc).__name__},
        )
    if isinstance(exc, storage.R11AStorageError) or "workspace cap" in message:
        return (
            "INDEX_OR_WORKSPACE_CAP_REACHED",
            "DURING_WORKSPACE_OPERATION",
            {"failure_class": type(exc).__name__},
        )
    if "requester pays" in message or "s3 http" in message or "transport" in message:
        return (
            "HTTP_OR_REQUESTER_PAYS_FAILURE",
            "AFTER_EACH_REQUEST_ATTEMPT",
            {"failure_class": type(exc).__name__},
        )
    if any(token in message for token in ("etag", "content length", "compressed sha", "metadata mismatch")):
        return (
            "ETAG_CONTENT_LENGTH_OR_COMPRESSED_SHA256_MISMATCH",
            "AFTER_RESPONSE_METADATA_OR_BODY",
            {"failure_class": type(exc).__name__},
        )
    if any(token in message for token in ("lz4", "decompress", "ndjson", "block wrapper", "event must", "fill.")):
        return (
            "DECOMPRESSION_OR_BLOCK_ENVELOPE_SCHEMA_FAILURE_PREVENTING_LOSSLESS_RAW_LOCATOR_OR_CONTINUED_PARSE",
            "DURING_EACH_LOCAL_PARSE",
            {"failure_class": type(exc).__name__},
        )
    return (
        "TAXONOMY_OR_CONSERVATION_INCOMPLETE",
        "FINAL_VALIDATION_ONLY",
        {"failure_class": type(exc).__name__},
    )


def execute_network(
    *,
    workspace: Path,
    artifact_directory: Path,
    transport: Callable[[str, str, dict[str, str], int, float], tuple[int, dict[str, str], bytes]] = transport_base.https_transport,
    request_time: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    env: dict[str, str] | None = None,
    limits: R11ALimits = DEFAULT_LIMITS,
) -> ExecutionOutcome:
    validate_static_inputs(require_release=True)
    targets = frozen_targets()
    guard = runtime.RuntimeGuard(limits)
    state = runtime.ExecutionEvidenceState(
        runtime.runtime_targets_from_objects(targets),
        limits,
    )
    meter = storage.WorkspaceMeter(workspace, limits)
    context = _network_context()
    try:
        meter.require_pre_oidc_free_space()
        guard.check("download phase start")
        compressed_root = workspace / "compressed"
        compressed_root.mkdir(parents=True, exist_ok=True)
        paths: dict[str, Path] = {}
        request_count = total_compressed = 0
        for target in targets:
            guard.check(f"request object {target.object_ordinal_zero_based}")
            if request_count >= limits.maximum_get_object_requests:
                raise R11ACollectorError("request cap reached")
            transport_target = {
                "path_hour_utc": target.path_hour_utc,
                "key": target.object_key,
                "size": target.expected_size_bytes,
                "etag": target.expected_etag,
            }
            host, path, headers = transport_base.build_signed_request(
                transport_target,
                request_time(),
                env,
            )
            if host != REGIONAL_ENDPOINT or headers.get("If-Match") != target.expected_etag:
                raise R11ACollectorError("signed target or If-Match drift")
            if headers.get("x-amz-request-payer") != "requester":
                raise R11ACollectorError("Requester Pays header absent")
            state.mark_request_sent(target.object_ordinal_zero_based)
            request_count += 1
            remaining = max(
                1.0,
                limits.maximum_runtime_seconds
                - limits.post_measurement_packaging_reservation_seconds
                - guard.elapsed_milliseconds() / 1000,
            )
            status, response_headers, compressed = transport(
                host,
                path,
                headers,
                target.expected_size_bytes,
                remaining,
            )
            try:
                observed_content_length = int(response_headers.get("content-length", ""))
            except (TypeError, ValueError) as exc:
                raise R11ACollectorError("response content length metadata invalid") from exc
            observed_etag = response_headers.get("etag")
            state.mark_response_metadata(
                target.object_ordinal_zero_based,
                etag=observed_etag,
                content_length=observed_content_length,
            )
            if status != 200 or response_headers.get("x-amz-request-charged", "").lower() != "requester":
                raise R11ACollectorError("S3 HTTP or Requester Pays failure")
            if observed_etag != target.expected_etag:
                raise R11ACollectorError("response ETag mismatch")
            if observed_content_length != target.expected_size_bytes:
                raise R11ACollectorError("response content length metadata mismatch")
            state.mark_body_progress(target.object_ordinal_zero_based, len(compressed))
            if len(compressed) != target.expected_size_bytes:
                raise R11ACollectorError("response content length mismatch")
            observed_sha = hashlib.sha256(compressed).hexdigest()
            state.mark_body_complete(
                target.object_ordinal_zero_based,
                sha256=observed_sha,
            )
            if observed_sha != target.expected_compressed_sha256:
                raise R11ACollectorError("response compressed SHA mismatch")
            total_compressed += len(compressed)
            if total_compressed > limits.maximum_total_compressed_bytes:
                raise R11ACollectorError("aggregate compressed cap exceeded")
            object_path = compressed_root / f"{target.object_ordinal_zero_based:03d}.lz4"
            schema.write_bytes_atomic(object_path, compressed)
            paths[target.object_key] = object_path
            compressed = b""
            meter.checkpoint(f"retain compressed object {target.object_ordinal_zero_based}")
            guard.check(f"after request object {target.object_ordinal_zero_based}")
        outcome = run_from_compressed_files(
            targets=targets,
            compressed_paths=paths,
            workspace=workspace,
            artifact_directory=artifact_directory,
            context=context,
            limits=limits,
            evidence_state=state,
            runtime_guard=guard,
        )
        shutil.rmtree(workspace, ignore_errors=True)
        return outcome
    except Exception as exc:
        condition, phase, inputs = _stop_for_exception(exc)
        state.trigger(condition, phase=phase, inputs=inputs)
        artifact_directory.unlink(missing_ok=True) if artifact_directory.is_file() else None
        shutil.rmtree(artifact_directory.with_name(artifact_directory.name + ".staging"), ignore_errors=True)
        failure.seal_minimal_failure_artifact(
            artifact_directory=artifact_directory,
            meter=meter,
            state=state,
            context=context,
            failure_class=type(exc).__name__,
            failure_message=str(exc),
            elapsed_runtime_milliseconds=guard.elapsed_milliseconds(),
            limits=limits,
        )
        shutil.rmtree(workspace, ignore_errors=True)
        result = _strict_dict(artifact_directory / "r11a-result.json")
        return ExecutionOutcome(
            return_code=21,
            terminal_class="R11A_DIAGNOSTIC_INCOMPLETE",
            root_cause_claim_status="NOT_PROVEN",
            artifact_directory=artifact_directory,
            result=result,
        )
'''
    text = text[:execute_start] + new_execute + text[main_start:]
    COLLECTOR.write_text(text, encoding="utf-8")


def patch_workflow() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    text = replace_once(
        text,
        """      - name: Assume exact successor R11A role with three-date session intersection
""",
        """      - name: Seal pre-OIDC failure evidence when the static gate fails
        if: failure()
        shell: bash
        run: |
          set -euo pipefail
          python - <<'PY'
          import os
          from pathlib import Path
          from research.archive_inventory.r11a_implementation import collector, failure, runtime, storage

          targets = collector.frozen_targets()
          state = runtime.ExecutionEvidenceState(runtime.runtime_targets_from_objects(targets))
          state.trigger(
              'RELEASE_NOT_EXACT_SINGLE_USE_OR_ALREADY_CONSUMED',
              phase='PRE_OIDC_STATIC',
              inputs={'static_gate_failed': True},
          )
          workspace = Path(os.environ['RUNNER_TEMP']) / 'r11a-workspace'
          meter = storage.WorkspaceMeter(workspace)
          meter.bootstrap()
          failure.seal_minimal_failure_artifact(
              artifact_directory=Path(os.environ['RUNNER_TEMP']) / 'r11a-artifact',
              meter=meter,
              state=state,
              context=collector._network_context(),
              failure_class='PRE_OIDC_STATIC_GATE_FAILURE',
              failure_message='pre-OIDC static gate failed; inspect workflow logs',
              elapsed_runtime_milliseconds=0,
          )
          PY

      - name: Assume exact successor R11A role with three-date session intersection
""",
        "workflow pre-OIDC failure evidence",
    )
    WORKFLOW.write_text(text, encoding="utf-8")


def patch_sealer_and_validator() -> None:
    sealer = SEALER.read_text(encoding="utf-8")
    for path in (
        "research/archive_inventory/r11a_implementation/runtime.py",
        "research/archive_inventory/r11a_implementation/failure.py",
        "tests/test_archive_inventory_r11a_runtime.py",
        "tests/test_archive_inventory_r11a_failure_artifact.py",
    ):
        literal = f'    "{path}",\n'
        if literal not in sealer:
            anchor = '    "research/archive_inventory/r11a_implementation/storage.py",\n'
            if path.startswith("tests/"):
                anchor = '    "tests/test_archive_inventory_r11a_implementation.py",\n'
            if anchor not in sealer:
                raise RepairError(f"seal anchor absent for {path}")
            sealer = sealer.replace(anchor, anchor + literal, 1)
    SEALER.write_text(sealer, encoding="utf-8")

    validator = VALIDATOR.read_text(encoding="utf-8")
    validator = replace_once(
        validator,
        '''        "storage.py",
    ):
''',
        '''        "storage.py",
        "runtime.py",
        "failure.py",
    ):
''',
        "validator module compilation list",
    )
    for path in (
        "research/archive_inventory/r11a_implementation/runtime.py",
        "research/archive_inventory/r11a_implementation/failure.py",
        "tests/test_archive_inventory_r11a_runtime.py",
        "tests/test_archive_inventory_r11a_failure_artifact.py",
    ):
        literal = f'    "{path}",\n'
        if literal not in validator:
            anchor = '    "research/archive_inventory/r11a_implementation/storage.py",\n'
            if path.startswith("tests/"):
                anchor = '    "tests/test_archive_inventory_r11a_implementation.py",\n'
            if anchor not in validator:
                raise RepairError(f"validator seal anchor absent for {path}")
            validator = validator.replace(anchor, anchor + literal, 1)
    VALIDATOR.write_text(validator, encoding="utf-8")


def main() -> int:
    patch_collector()
    patch_workflow()
    patch_sealer_and_validator()
    Path(__file__).unlink()
    print("R11A_D1_FAILURE_INTEGRATION_APPLIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
