from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Callable, Mapping, Sequence

from .limits import DEFAULT_LIMITS, R11ALimits


class R11ARuntimeError(ValueError):
    """Raised when runtime, stop-ledger, or object-state evidence drifts."""


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

PROCESSING_STAGE_ORDER = (
    "UNATTEMPTED",
    "REQUEST_SENT_NO_ACCEPTED_RESPONSE",
    "RESPONSE_METADATA_RECEIVED",
    "RESPONSE_METADATA_RECEIVED_INCOMPLETE_BODY",
    "RESPONSE_BODY_RECEIVED",
    "FIRST_LOCAL_PARSE_COMPLETE",
    "SECOND_LOCAL_PARSE_COMPLETE",
)


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
    last_label: str = field(default="INITIAL", init=False)

    def __post_init__(self) -> None:
        self.limits.validate()
        self.started_ns = self.monotonic_ns()

    def elapsed_milliseconds(self) -> int:
        elapsed = self.monotonic_ns() - self.started_ns
        if elapsed < 0:
            raise R11ARuntimeError("monotonic runtime moved backwards")
        return (elapsed + 999_999) // 1_000_000

    def check(self, label: str, *, reserve_packaging: bool = True) -> int:
        if type(label) is not str or not label:
            raise R11ARuntimeError("runtime label must be nonempty string")
        observed = self.elapsed_milliseconds()
        reservation = (
            self.limits.post_measurement_packaging_reservation_seconds * 1000
            if reserve_packaging
            else 0
        )
        if observed + reservation >= self.limits.maximum_runtime_seconds * 1000:
            raise R11ARuntimeError(f"runtime cap reached before {label}")
        self.last_label = label
        return observed


@dataclass(slots=True)
class ExecutionEvidenceState:
    targets: Sequence[RuntimeTarget]
    limits: R11ALimits = DEFAULT_LIMITS
    rows: list[ObjectEvidence] = field(init=False)
    stop_condition: str | None = None
    stop_phase: str | None = None
    stop_inputs: Mapping[str, object] | None = None
    stop_step_ordinal: int | None = None
    evaluation_step: int = 0

    def __post_init__(self) -> None:
        self.limits.validate()
        if len(self.targets) != self.limits.maximum_get_object_requests:
            raise R11ARuntimeError("execution state requires exact target cardinality")
        ordinals = [row.object_ordinal_zero_based for row in self.targets]
        if ordinals != list(range(len(self.targets))):
            raise R11ARuntimeError("runtime targets are not canonical ordinal order")
        self.rows = [ObjectEvidence(row) for row in self.targets]

    def row(self, ordinal: int) -> ObjectEvidence:
        if type(ordinal) is not int or not 0 <= ordinal < len(self.rows):
            raise R11ARuntimeError("object ordinal outside runtime state")
        return self.rows[ordinal]

    def mark_request_sent(self, ordinal: int) -> None:
        row = self.row(ordinal)
        if row.processing_status != "UNATTEMPTED_AFTER_FAIL_CLOSED_STOP":
            raise R11ARuntimeError("object request attempted more than once")
        row.processing_status = "TRANSPORT_ATTEMPT_FAILED"
        row.last_completed_stage = "REQUEST_SENT_NO_ACCEPTED_RESPONSE"
        row.get_object_request_count = 1

    def mark_response_metadata(
        self,
        ordinal: int,
        *,
        etag: str | None,
        content_length: int | None,
    ) -> None:
        row = self.row(ordinal)
        if row.last_completed_stage != "REQUEST_SENT_NO_ACCEPTED_RESPONSE":
            raise R11ARuntimeError("response metadata reached out of order")
        row.processing_status = "RESPONSE_METADATA_IDENTITY_MISMATCH"
        row.last_completed_stage = "RESPONSE_METADATA_RECEIVED"
        row.observed_etag = etag
        row.observed_content_length = content_length

    def mark_body_progress(self, ordinal: int, byte_count: int) -> None:
        row = self.row(ordinal)
        if type(byte_count) is not int or byte_count < row.compressed_response_body_bytes_received:
            raise R11ARuntimeError("compressed body byte counter regressed")
        row.compressed_response_body_bytes_received = byte_count
        if row.last_completed_stage == "RESPONSE_METADATA_RECEIVED":
            row.processing_status = "BODY_READ_FAILED_AFTER_RESPONSE_METADATA"
            row.last_completed_stage = "RESPONSE_METADATA_RECEIVED_INCOMPLETE_BODY"

    def mark_body_complete(self, ordinal: int, *, sha256: str) -> None:
        row = self.row(ordinal)
        if row.observed_content_length is None:
            raise R11ARuntimeError("body completed before response metadata")
        if row.compressed_response_body_bytes_received != row.observed_content_length:
            raise R11ARuntimeError("complete body byte count differs from response metadata")
        row.processing_status = "COMPRESSED_BODY_SHA256_MISMATCH"
        row.last_completed_stage = "RESPONSE_BODY_RECEIVED"
        row.observed_compressed_object_sha256 = sha256

    def mark_first_parse(self, ordinal: int, summary: Mapping[str, object]) -> None:
        row = self.row(ordinal)
        if row.last_completed_stage != "RESPONSE_BODY_RECEIVED":
            raise R11ARuntimeError("first parse completed before body")
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

    def trigger(
        self,
        condition: str,
        *,
        phase: str,
        inputs: Mapping[str, object],
    ) -> None:
        if condition not in STOP_CONDITIONS:
            raise R11ARuntimeError(f"unknown stop condition {condition}")
        if self.stop_condition is not None:
            return
        self.stop_condition = condition
        self.stop_phase = phase
        self.stop_inputs = dict(inputs)
        self.stop_step_ordinal = self.evaluation_step
        self.evaluation_step += 1

    def object_rows(self) -> tuple[dict[str, object], ...]:
        return tuple(row.as_mapping() for row in self.rows)

    def stop_rows(self) -> tuple[dict[str, object], ...]:
        output: list[dict[str, object]] = []
        for ordinal, condition in enumerate(STOP_CONDITIONS):
            if self.stop_condition is None:
                status = "PASS"
                predicate = False
                inputs: object = {}
                trigger_step: object = None
            elif condition == self.stop_condition:
                status = "TRIGGERED"
                predicate = True
                inputs = dict(self.stop_inputs or {})
                trigger_step = self.stop_step_ordinal
            elif ordinal < STOP_CONDITIONS.index(self.stop_condition):
                status = "PASS"
                predicate = False
                inputs = {}
                trigger_step = None
            else:
                status = "NOT_REACHED_AFTER_EARLIER_STOP"
                predicate = None
                inputs = None
                trigger_step = None
            output.append(
                {
                    "stop_condition": condition,
                    "evaluation_phase": (
                        self.stop_phase
                        if condition == self.stop_condition
                        else "FROZEN_PHASE_ORDER"
                    ),
                    "evaluation_status": status,
                    "predicate_inputs": inputs,
                    "predicate_result": predicate,
                    "first_evaluation_step_ordinal": (
                        ordinal if status != "NOT_REACHED_AFTER_EARLIER_STOP" else None
                    ),
                    "trigger_step_ordinal": trigger_step,
                }
            )
        return tuple(output)


def runtime_targets_from_objects(targets: Sequence[object]) -> tuple[RuntimeTarget, ...]:
    output: list[RuntimeTarget] = []
    for row in targets:
        output.append(
            RuntimeTarget(
                object_ordinal_zero_based=int(getattr(row, "object_ordinal_zero_based")),
                path_hour_utc=str(getattr(row, "path_hour_utc")),
                source_object_key=str(getattr(row, "object_key")),
                expected_etag=str(getattr(row, "expected_etag")),
                expected_content_length=int(getattr(row, "expected_size_bytes")),
                expected_compressed_object_sha256=str(
                    getattr(row, "expected_compressed_sha256")
                ),
            )
        )
    return tuple(output)
