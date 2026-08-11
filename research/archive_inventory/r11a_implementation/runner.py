from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import collector as core
from . import failure, network, runtime, storage
from .limits import DEFAULT_LIMITS, R11ALimits


class R11ARunnerError(ValueError):
    """Raised when the repaired R11A network lane must fail closed."""


def _condition(exc: Exception) -> tuple[str, str]:
    text = str(exc).lower()
    if isinstance(exc, runtime.R11ARuntimeError) or "runtime cap" in text:
        return "RUNTIME_CAP_REACHED", "DURING_RUNTIME_OPERATION"
    if isinstance(exc, storage.R11AStorageError) or "workspace cap" in text:
        return "INDEX_OR_WORKSPACE_CAP_REACHED", "DURING_WORKSPACE_OPERATION"
    if isinstance(exc, network.R11ANetworkError):
        if any(token in text for token in ("etag", "content-length", "content length", "sha-256")):
            return (
                "ETAG_CONTENT_LENGTH_OR_COMPRESSED_SHA256_MISMATCH",
                "AFTER_RESPONSE_METADATA_OR_BODY",
            )
        return "HTTP_OR_REQUESTER_PAYS_FAILURE", "AFTER_EACH_REQUEST_ATTEMPT"
    if "request cap" in text:
        return "REQUEST_CAP_REACHED", "BEFORE_EACH_REQUEST"
    if any(token in text for token in ("lz4", "decompress", "ndjson", "block wrapper", "event must", "fill.")):
        return (
            "DECOMPRESSION_OR_BLOCK_ENVELOPE_SCHEMA_FAILURE_PREVENTING_LOSSLESS_RAW_LOCATOR_OR_CONTINUED_PARSE",
            "DURING_EACH_LOCAL_PARSE",
        )
    return "TAXONOMY_OR_CONSERVATION_INCOMPLETE", "FINAL_VALIDATION_ONLY"


def execute_network(
    *,
    workspace: Path,
    artifact_directory: Path,
    request_time: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    env: dict[str, str] | None = None,
    limits: R11ALimits = DEFAULT_LIMITS,
    downloader: Callable[..., network.DownloadResult] = network.https_get_to_file,
) -> core.ExecutionOutcome:
    targets = core.frozen_targets()
    guard = runtime.RuntimeGuard(limits)
    state = runtime.ExecutionEvidenceState(runtime.runtime_targets(targets), limits)
    meter = runtime.GuardedWorkspaceMeter(workspace, limits, runtime_guard=guard)
    context = {
        **core._network_context(),
        "runner_path": "research/archive_inventory/r11a_implementation/runner.py",
        "network_transport_path": "research/archive_inventory/r11a_implementation/network.py",
        "failure_artifact_path": "research/archive_inventory/r11a_implementation/failure.py",
    }
    try:
        core.validate_static_inputs(require_release=True)
        meter.require_pre_oidc_free_space()
        compressed_root = workspace / "compressed"
        compressed_root.mkdir(parents=True, exist_ok=True)
        paths: dict[str, Path] = {}
        total_compressed = 0
        for target in targets:
            guard.check(f"before request object {target.object_ordinal_zero_based}")
            if sum(int(row["get_object_request_count"]) for row in state.object_rows()) >= limits.maximum_get_object_requests:
                raise R11ARunnerError("request cap reached")
            transport_target = {
                "path_hour_utc": target.path_hour_utc,
                "key": target.object_key,
                "size": target.expected_size_bytes,
                "etag": target.expected_etag,
            }
            host, request_path, headers = core.transport_base.build_signed_request(
                transport_target,
                request_time(),
                env,
            )
            if host != core.REGIONAL_ENDPOINT:
                raise R11ARunnerError("signed regional endpoint drift")
            if headers.get("If-Match") != target.expected_etag:
                raise R11ARunnerError("signed If-Match drift")
            if headers.get("x-amz-request-payer") != "requester":
                raise R11ARunnerError("Requester Pays request header absent")
            state.mark_request_sent(target.object_ordinal_zero_based)
            destination = compressed_root / f"{target.object_ordinal_zero_based:03d}.lz4"

            def on_metadata(meta: network.ResponseMetadata, ordinal: int = target.object_ordinal_zero_based) -> None:
                state.mark_response_metadata(
                    ordinal,
                    etag=meta.etag,
                    content_length=meta.content_length,
                )

            def on_progress(byte_count: int, ordinal: int = target.object_ordinal_zero_based) -> None:
                state.mark_body_progress(ordinal, byte_count)

            result = downloader(
                host=host,
                request_path=request_path,
                request_headers=headers,
                destination=destination,
                expected_etag=target.expected_etag,
                expected_content_length=target.expected_size_bytes,
                maximum_body_bytes=target.expected_size_bytes,
                timeout_seconds=max(
                    1.0,
                    limits.maximum_runtime_seconds
                    - limits.post_measurement_packaging_reservation_seconds
                    - guard.elapsed_milliseconds() / 1000,
                ),
                on_metadata=on_metadata,
                on_progress=on_progress,
            )
            if not result.complete or result.body_sha256 is None:
                raise R11ARunnerError("download completed without body evidence")
            state.mark_body_complete(target.object_ordinal_zero_based, result.body_sha256)
            if result.body_sha256 != target.expected_compressed_sha256:
                raise R11ARunnerError("response compressed SHA-256 mismatch")
            total_compressed += result.body_bytes_received
            if total_compressed > limits.maximum_total_compressed_bytes:
                raise R11ARunnerError("aggregate compressed cap exceeded")
            paths[target.object_key] = destination
            meter.checkpoint(f"retain compressed object {target.object_ordinal_zero_based}")
        # The canonical local reducer remains separately sealed. The repaired
        # lane adds transport metadata binding and a truthful failure artifact;
        # the follow-up closure validator still blocks owner approval until the
        # local runtime/ledger review is complete.
        outcome = core.run_from_compressed_files(
            targets=targets,
            compressed_paths=paths,
            workspace=workspace,
            artifact_directory=artifact_directory,
            context=context,
            limits=limits,
        )
        shutil.rmtree(workspace, ignore_errors=True)
        return outcome
    except Exception as exc:
        condition, phase = _condition(exc)
        state.trigger(
            condition,
            phase=phase,
            inputs={"failure_class": type(exc).__name__},
        )
        shutil.rmtree(
            artifact_directory.with_name(artifact_directory.name + ".staging"),
            ignore_errors=True,
        )
        failure_meter = storage.WorkspaceMeter(workspace, limits)
        if not workspace.exists():
            failure_meter.bootstrap()
        else:
            try:
                failure_meter.checkpoint("failure artifact baseline")
            except storage.R11AStorageError:
                shutil.rmtree(workspace, ignore_errors=True)
                failure_meter.bootstrap()
        failure.seal_minimal_failure_artifact(
            artifact_directory=artifact_directory,
            meter=failure_meter,
            state=state,
            context=context,
            failure_class=type(exc).__name__,
            failure_message=str(exc),
            elapsed_runtime_milliseconds=guard.elapsed_milliseconds(),
            limits=limits,
        )
        result = core._strict_dict(artifact_directory / "r11a-result.json")
        shutil.rmtree(workspace, ignore_errors=True)
        return core.ExecutionOutcome(
            return_code=21,
            terminal_class="R11A_DIAGNOSTIC_INCOMPLETE",
            root_cause_claim_status="NOT_PROVEN",
            artifact_directory=artifact_directory,
            result=result,
        )
