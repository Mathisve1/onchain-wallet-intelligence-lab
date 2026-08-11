from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Sequence

from .limits import DEFAULT_LIMITS, R11ALimits
from .storage import WorkspaceMeter

STOP_CONDITIONS = (
    "NONCANONICAL_MAIN_OR_NONFIRST_ATTEMPT",
    "RELEASE_NOT_EXACT_SINGLE_USE_OR_ALREADY_CONSUMED",
    "BUDGET_CAP_EXCEEDED",
    "INSUFFICIENT_EPHEMERAL_DISK_BEFORE_OIDC",
    "AWS_IDENTITY_MISMATCH",
    "REQUEST_CAP_REACHED",
    "HTTP_OR_REQUESTER_PAYS_FAILURE",
    "ETAG_CONTENT_LENGTH_OR_COMPRESSED_SHA256_MISMATCH",
    "DECOMPRESSION_OR_BLOCK_ENVELOPE_SCHEMA_FAILURE_PREVENTING_LOSSLESS_RAW_LOCATOR_OR_CONTINUED_PARSE",
    "INDEX_OR_WORKSPACE_CAP_REACHED",
    "RETENTION_OR_ARTIFACT_CAP_EXCEEDED",
    "RUNTIME_CAP_REACHED",
    "TAXONOMY_OR_CONSERVATION_INCOMPLETE",
)


class R11ARuntimeError(ValueError):
    """Raised when a frozen runtime or evidence-state boundary is violated."""


@dataclass(frozen=True, slots=True)
class RuntimeTarget:
    object_ordinal_zero_based: int
    path_hour_utc: str
    source_object_key: str
    expected_etag: str
    expected_content_length: int
    expected_compressed_object_sha256: str


@dataclass(slots=True)
class ObjectEvidence:
    target: RuntimeTarget
    processing_status: str = "UNATTEMPTED_AFTER_FAIL_CLOSED_STOP"
    last_completed_stage: str = "UNATTEMPTED"
    observed_etag: str | None = None
    observed_content_length: int | None = None
    compressed_response_body_bytes_received: int = 0
    observed_compressed_object_sha256: str | None = None
    get_object_request_count: int = 0
    retry_count: int = 0
    first_local_parse_decompressed_bytes_consumed: int = 0
    second_local_parse_decompressed_bytes_consumed: int = 0
    first_local_parse: Mapping[str, object] | None = None
    second_local_parse: Mapping[str, object] | None = None

    def as_mapping(self) -> dict[str, object]:
        return {
            "record_type": "OBJECT_TRANSPORT_AND_TWO_PASS_CONSERVATION",
            "object_ordinal_zero_based": self.target.object_ordinal_zero_based,
            "processing_status": self.processing_status,
            "last_completed_stage": self.last_completed_stage,
            "path_hour_utc": self.target.path_hour_utc,
            "source_object_key": self.target.source_object_key,
            "expected_etag": self.target.expected_etag,
            "observed_etag": self.observed_etag,
            "expected_content_length": self.target.expected_content_length,
            "observed_content_length": self.observed_content_length,
            "compressed_response_body_bytes_received": self.compressed_response_body_bytes_received,
            "expected_compressed_object_sha256": self.target.expected_compressed_object_sha256,
            "observed_compressed_object_sha256": self.observed_compressed_object_sha256,
            "get_object_request_count": self.get_object_request_count,
            "retry_count": self.retry_count,
            "first_local_parse_decompressed_bytes_consumed": self.first_local_parse_decompressed_bytes_consumed,
            "second_local_parse_decompressed_bytes_consumed": self.second_local_parse_decompressed_bytes_consumed,
            "first_local_parse": dict(self.first_local_parse) if self.first_local_parse is not None else None,
            "second_local_parse": dict(self.second_local_parse) if self.second_local_parse is not None else None,
        }


@dataclass(slots=True)
class RuntimeGuard:
    limits: R11ALimits = DEFAULT_LIMITS
    monotonic_ns: Callable[[], int] = time.monotonic_ns
    started_ns: int = field(init=False)

    def __post_init__(self) -> None:
        self.limits.validate()
        self.started_ns = self.monotonic_ns()

    def elapsed_milliseconds(self) -> int:
        delta = self.monotonic_ns() - self.started_ns
        if delta < 0:
            raise R11ARuntimeError("monotonic clock regressed")
        return (delta + 999_999) // 1_000_000

    def check(self, label: str, *, reserve_packaging: bool = True) -> int:
        if type(label) is not str or not label:
            raise R11ARuntimeError("runtime checkpoint label must be nonempty")
        elapsed = self.elapsed_milliseconds()
        reserve = (
            self.limits.post_measurement_packaging_reservation_seconds * 1000
            if reserve_packaging
            else 0
        )
        if elapsed + reserve >= self.limits.maximum_runtime_seconds * 1000:
            raise R11ARuntimeError(f"runtime cap reached before {label}")
        return elapsed


class GuardedWorkspaceMeter(WorkspaceMeter):
    """Workspace meter that also enforces the frozen runtime at every checkpoint."""

    def __init__(
        self,
        root: Path,
        limits: R11ALimits = DEFAULT_LIMITS,
        *,
        runtime_guard: RuntimeGuard,
    ) -> None:
        super().__init__(root, limits)
        self.runtime_guard = runtime_guard

    def bootstrap(self) -> None:
        self.runtime_guard.check("workspace bootstrap")
        super().bootstrap()
        self.runtime_guard.check("after workspace bootstrap")

    def require_pre_oidc_free_space(self) -> int:
        self.runtime_guard.check("pre-OIDC free-space check")
        value = super().require_pre_oidc_free_space()
        self.runtime_guard.check("after pre-OIDC free-space check")
        return value

    def checkpoint(self, label: str) -> int:
        self.runtime_guard.check(f"before {label}")
        value = super().checkpoint(label)
        self.runtime_guard.check(f"after {label}")
        return value


@dataclass(slots=True)
class ExecutionEvidenceState:
    targets: Sequence[RuntimeTarget]
    limits: R11ALimits = DEFAULT_LIMITS
    rows: list[ObjectEvidence] = field(init=False)
    stop_condition: str | None = None
    stop_phase: str | None = None
    stop_inputs: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        self.limits.validate()
        if len(self.targets) != self.limits.maximum_get_object_requests:
            raise R11ARuntimeError("runtime target count differs from request cap")
        if [item.object_ordinal_zero_based for item in self.targets] != list(range(len(self.targets))):
            raise R11ARuntimeError("runtime targets are not canonical ordinal order")
        self.rows = [ObjectEvidence(item) for item in self.targets]

    def row(self, ordinal: int) -> ObjectEvidence:
        if type(ordinal) is not int or not 0 <= ordinal < len(self.rows):
            raise R11ARuntimeError("object ordinal outside frozen state")
        return self.rows[ordinal]

    def mark_request_sent(self, ordinal: int) -> None:
        row = self.row(ordinal)
        if row.get_object_request_count != 0:
            raise R11ARuntimeError("second request for one object is forbidden")
        row.get_object_request_count = 1
        row.processing_status = "TRANSPORT_ATTEMPT_FAILED"
        row.last_completed_stage = "REQUEST_SENT_NO_ACCEPTED_RESPONSE"

    def mark_response_metadata(self, ordinal: int, *, etag: str | None, content_length: int | None) -> None:
        row = self.row(ordinal)
        if row.last_completed_stage != "REQUEST_SENT_NO_ACCEPTED_RESPONSE":
            raise R11ARuntimeError("response metadata observed out of order")
        row.observed_etag = etag
        row.observed_content_length = content_length
        row.processing_status = "RESPONSE_METADATA_IDENTITY_MISMATCH"
        row.last_completed_stage = "RESPONSE_METADATA_RECEIVED"

    def mark_body_progress(self, ordinal: int, byte_count: int) -> None:
        row = self.row(ordinal)
        if type(byte_count) is not int or byte_count < row.compressed_response_body_bytes_received:
            raise R11ARuntimeError("compressed body byte count regressed")
        row.compressed_response_body_bytes_received = byte_count
        if row.last_completed_stage == "RESPONSE_METADATA_RECEIVED":
            row.processing_status = "BODY_READ_FAILED_AFTER_RESPONSE_METADATA"
            row.last_completed_stage = "RESPONSE_METADATA_RECEIVED_INCOMPLETE_BODY"

    def mark_body_complete(self, ordinal: int, sha256: str) -> None:
        row = self.row(ordinal)
        if row.observed_content_length is None:
            raise R11ARuntimeError("body completed without response metadata")
        if row.compressed_response_body_bytes_received != row.observed_content_length:
            raise R11ARuntimeError("body byte count differs from observed Content-Length")
        row.observed_compressed_object_sha256 = sha256
        row.processing_status = "COMPRESSED_BODY_SHA256_MISMATCH"
        row.last_completed_stage = "RESPONSE_BODY_RECEIVED"

    def mark_first_parse(self, ordinal: int, summary: Mapping[str, object]) -> None:
        row = self.row(ordinal)
        if row.last_completed_stage != "RESPONSE_BODY_RECEIVED":
            raise R11ARuntimeError("first parse completed before accepted body")
        count = summary.get("decompressed_byte_count")
        if type(count) is not int or count < 0:
            raise R11ARuntimeError("first parse byte count invalid")
        row.first_local_parse = dict(summary)
        row.first_local_parse_decompressed_bytes_consumed = count
        row.processing_status = "FIRST_LOCAL_PARSE_COMPLETE_SECOND_NOT_STARTED"
        row.last_completed_stage = "FIRST_LOCAL_PARSE_COMPLETE"

    def mark_second_parse(self, ordinal: int, summary: Mapping[str, object]) -> None:
        row = self.row(ordinal)
        if row.last_completed_stage != "FIRST_LOCAL_PARSE_COMPLETE":
            raise R11ARuntimeError("second parse completed before first")
        count = summary.get("decompressed_byte_count")
        if type(count) is not int or count < 0:
            raise R11ARuntimeError("second parse byte count invalid")
        row.second_local_parse = dict(summary)
        row.second_local_parse_decompressed_bytes_consumed = count
        row.processing_status = "COMPLETE_TWO_LOCAL_PASSES"
        row.last_completed_stage = "SECOND_LOCAL_PARSE_COMPLETE"

    def trigger(self, condition: str, *, phase: str, inputs: Mapping[str, object]) -> None:
        if condition not in STOP_CONDITIONS:
            raise R11ARuntimeError(f"unknown stop condition: {condition}")
        if self.stop_condition is None:
            self.stop_condition = condition
            self.stop_phase = phase
            self.stop_inputs = dict(inputs)

    def object_rows(self) -> tuple[dict[str, object], ...]:
        return tuple(row.as_mapping() for row in self.rows)

    def stop_rows(self) -> tuple[dict[str, object], ...]:
        output: list[dict[str, object]] = []
        trigger_index = STOP_CONDITIONS.index(self.stop_condition) if self.stop_condition else None
        for index, condition in enumerate(STOP_CONDITIONS):
            if trigger_index is None:
                status = "PASS"
                inputs: object = {}
                result: object = False
            elif index < trigger_index:
                status = "PASS"
                inputs = {}
                result = False
            elif index == trigger_index:
                status = "TRIGGERED"
                inputs = dict(self.stop_inputs or {})
                result = True
            else:
                status = "NOT_REACHED_AFTER_EARLIER_STOP"
                inputs = None
                result = None
            output.append(
                {
                    "stop_condition": condition,
                    "evaluation_phase": self.stop_phase if index == trigger_index else "FROZEN_PHASE_ORDER",
                    "evaluation_status": status,
                    "predicate_inputs": inputs,
                    "predicate_result": result,
                    "first_evaluation_step_ordinal": index if status != "NOT_REACHED_AFTER_EARLIER_STOP" else None,
                    "trigger_step_ordinal": index if status == "TRIGGERED" else None,
                }
            )
        return tuple(output)


def runtime_targets(targets: Sequence[object]) -> tuple[RuntimeTarget, ...]:
    return tuple(
        RuntimeTarget(
            object_ordinal_zero_based=int(getattr(item, "object_ordinal_zero_based")),
            path_hour_utc=str(getattr(item, "path_hour_utc")),
            source_object_key=str(getattr(item, "object_key")),
            expected_etag=str(getattr(item, "expected_etag")),
            expected_content_length=int(getattr(item, "expected_size_bytes")),
            expected_compressed_object_sha256=str(getattr(item, "expected_compressed_sha256")),
        )
        for item in targets
    )
