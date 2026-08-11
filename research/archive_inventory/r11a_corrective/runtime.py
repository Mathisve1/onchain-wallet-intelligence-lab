from __future__ import annotations

import dataclasses
import hashlib
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Final

from .canonical import canonical_json_bytes
from .limits import R11ALimits


class RuntimeBoundaryError(RuntimeError):
    pass


@dataclasses.dataclass(slots=True)
class RuntimeGuard:
    limits: R11ALimits
    monotonic_ns: Callable[[], int] = time.monotonic_ns
    _started_ns: int = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        self.limits.validate()
        self._started_ns = self.monotonic_ns()

    def elapsed_ns(self) -> int:
        current = self.monotonic_ns()
        if current < self._started_ns:
            raise RuntimeBoundaryError("monotonic clock moved backwards")
        return current - self._started_ns

    def elapsed_seconds_floor(self) -> int:
        return self.elapsed_ns() // 1_000_000_000

    def check_scientific_phase(self, phase: str) -> None:
        if self.elapsed_ns() >= self.limits.scientific_deadline_seconds * 1_000_000_000:
            raise RuntimeBoundaryError(f"scientific runtime reserve reached at {phase}")

    def check_packaging_phase(self, phase: str) -> None:
        packaging_deadline = (
            self.limits.maximum_runtime_seconds - self.limits.minimum_upload_window_seconds
        )
        if self.elapsed_ns() >= packaging_deadline * 1_000_000_000:
            raise RuntimeBoundaryError(f"packaging runtime reserve reached at {phase}")

    def check_hard_deadline(self, phase: str) -> None:
        if self.elapsed_ns() >= self.limits.maximum_runtime_seconds * 1_000_000_000:
            raise RuntimeBoundaryError(f"hard runtime reached at {phase}")


@dataclasses.dataclass(frozen=True, slots=True)
class RuntimeTarget:
    object_ordinal_zero_based: int
    object_key: str
    expected_size_bytes: int
    expected_etag: str
    expected_compressed_sha256: str
    source_path_hour_utc: str

    def __post_init__(self) -> None:
        if self.object_ordinal_zero_based < 0:
            raise RuntimeBoundaryError("object ordinal must be nonnegative")
        if not self.object_key:
            raise RuntimeBoundaryError("object key is required")
        if self.expected_size_bytes <= 0:
            raise RuntimeBoundaryError("expected object size must be positive")
        if len(self.expected_compressed_sha256) != 64:
            raise RuntimeBoundaryError("expected compressed SHA-256 is malformed")


@dataclasses.dataclass(slots=True)
class _MutableObjectState:
    target: RuntimeTarget
    request_count: int = 0
    request_status: str = "NOT_REQUESTED"
    response_http_status: int | None = None
    response_etag: str | None = None
    response_content_length: int | None = None
    response_requester_charged: str | None = None
    received_body_bytes: int = 0
    observed_compressed_sha256: str | None = None
    first_pass_status: str = "NOT_STARTED"
    first_pass_decompressed_bytes: int | None = None
    first_pass_record_count: int | None = None
    first_pass_event_count: int | None = None
    first_pass_stream_sha256: str | None = None
    second_pass_status: str = "NOT_STARTED"
    second_pass_decompressed_bytes: int | None = None
    second_pass_record_count: int | None = None
    second_pass_event_count: int | None = None
    second_pass_stream_sha256: str | None = None
    terminal_status: str = "PENDING"
    terminal_error_code: str | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class StopEntry:
    sequence_zero_based: int
    stop_code: str
    phase: str
    object_ordinal_zero_based: int | None
    evidence_sha256: str

    def as_mapping(self) -> dict[str, object]:
        return dataclasses.asdict(self)


class ExecutionEvidenceState:
    """Exact lifecycle evidence for all 72 selected objects and ordered stops."""

    def __init__(self, targets: Sequence[RuntimeTarget], limits: R11ALimits) -> None:
        limits.validate()
        if len(targets) != limits.maximum_get_object_requests:
            raise RuntimeBoundaryError("runtime target count must equal the exact 72-object selection")
        ordered = sorted(targets, key=lambda row: row.object_ordinal_zero_based)
        if [row.object_ordinal_zero_based for row in ordered] != list(range(len(ordered))):
            raise RuntimeBoundaryError("object ordinals must be contiguous from zero")
        if len({row.object_key for row in ordered}) != len(ordered):
            raise RuntimeBoundaryError("object keys must be unique")
        self._limits = limits
        self._objects = [_MutableObjectState(row) for row in ordered]
        self._stops: list[StopEntry] = []
        self._network_request_count = 0

    @property
    def network_request_count(self) -> int:
        return self._network_request_count

    def _state(self, ordinal: int) -> _MutableObjectState:
        if ordinal < 0 or ordinal >= len(self._objects):
            raise RuntimeBoundaryError("object ordinal outside exact selection")
        return self._objects[ordinal]

    def request_sent(self, ordinal: int) -> None:
        state = self._state(ordinal)
        if state.request_status != "NOT_REQUESTED":
            raise RuntimeBoundaryError("object request attempted more than once")
        if self._network_request_count >= self._limits.maximum_get_object_requests:
            raise RuntimeBoundaryError("global request cap exceeded")
        state.request_count = 1
        state.request_status = "REQUEST_SENT"
        self._network_request_count += 1

    def response_metadata(
        self,
        ordinal: int,
        *,
        http_status: int,
        etag: str | None,
        content_length: int | None,
        requester_charged: str | None,
    ) -> None:
        state = self._state(ordinal)
        if state.request_status != "REQUEST_SENT":
            raise RuntimeBoundaryError("response metadata arrived outside request lifecycle")
        state.response_http_status = http_status
        state.response_etag = etag
        state.response_content_length = content_length
        state.response_requester_charged = requester_charged
        state.request_status = "METADATA_RECEIVED"

    def body_progress(self, ordinal: int, received_total: int) -> None:
        state = self._state(ordinal)
        if state.request_status not in {"METADATA_RECEIVED", "BODY_STREAMING"}:
            raise RuntimeBoundaryError("body bytes arrived before verified response metadata")
        if received_total < state.received_body_bytes:
            raise RuntimeBoundaryError("received body byte count decreased")
        if received_total > state.target.expected_size_bytes:
            raise RuntimeBoundaryError("received body exceeds expected Content-Length")
        state.received_body_bytes = received_total
        state.request_status = "BODY_STREAMING"

    def body_complete(self, ordinal: int, observed_sha256: str) -> None:
        state = self._state(ordinal)
        if state.request_status != "BODY_STREAMING":
            raise RuntimeBoundaryError("body completion outside streaming state")
        if state.received_body_bytes != state.target.expected_size_bytes:
            raise RuntimeBoundaryError("body completion with short byte count")
        if observed_sha256 != state.target.expected_compressed_sha256:
            raise RuntimeBoundaryError("compressed SHA-256 mismatch")
        state.observed_compressed_sha256 = observed_sha256
        state.request_status = "BODY_COMPLETE"

    def pass_complete(
        self,
        ordinal: int,
        *,
        pass_number: int,
        decompressed_bytes: int,
        record_count: int,
        event_count: int,
        stream_sha256: str,
    ) -> None:
        state = self._state(ordinal)
        if state.request_status != "BODY_COMPLETE":
            raise RuntimeBoundaryError("local parse started before complete integrity-bound body")
        if min(decompressed_bytes, record_count, event_count) < 0:
            raise RuntimeBoundaryError("negative local parse evidence")
        if len(stream_sha256) != 64:
            raise RuntimeBoundaryError("decompressed stream SHA-256 is malformed")
        if pass_number == 1:
            if state.first_pass_status != "NOT_STARTED":
                raise RuntimeBoundaryError("first pass recorded more than once")
            state.first_pass_status = "COMPLETE"
            state.first_pass_decompressed_bytes = decompressed_bytes
            state.first_pass_record_count = record_count
            state.first_pass_event_count = event_count
            state.first_pass_stream_sha256 = stream_sha256
        elif pass_number == 2:
            if state.first_pass_status != "COMPLETE" or state.second_pass_status != "NOT_STARTED":
                raise RuntimeBoundaryError("second pass lifecycle is invalid")
            if (
                decompressed_bytes != state.first_pass_decompressed_bytes
                or record_count != state.first_pass_record_count
                or event_count != state.first_pass_event_count
                or stream_sha256 != state.first_pass_stream_sha256
            ):
                raise RuntimeBoundaryError("independent local passes do not match exactly")
            state.second_pass_status = "COMPLETE"
            state.second_pass_decompressed_bytes = decompressed_bytes
            state.second_pass_record_count = record_count
            state.second_pass_event_count = event_count
            state.second_pass_stream_sha256 = stream_sha256
            state.terminal_status = "COMPLETE_TWO_LOCAL_PASSES"
        else:
            raise RuntimeBoundaryError("pass number must be one or two")

    def stop(
        self,
        stop_code: str,
        *,
        phase: str,
        object_ordinal_zero_based: int | None = None,
        evidence: Mapping[str, object] | None = None,
    ) -> None:
        payload = {} if evidence is None else dict(evidence)
        digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
        self._stops.append(
            StopEntry(
                sequence_zero_based=len(self._stops),
                stop_code=stop_code,
                phase=phase,
                object_ordinal_zero_based=object_ordinal_zero_based,
                evidence_sha256=digest,
            )
        )
        if object_ordinal_zero_based is not None:
            state = self._state(object_ordinal_zero_based)
            state.terminal_status = "STOPPED"
            state.terminal_error_code = stop_code

    def object_rows(self) -> tuple[dict[str, object], ...]:
        rows: list[dict[str, object]] = []
        for state in self._objects:
            rows.append(
                {
                    "record_type": "OBJECT_EXECUTION_EVIDENCE",
                    "object_ordinal_zero_based": state.target.object_ordinal_zero_based,
                    "object_key": state.target.object_key,
                    "source_path_hour_utc": state.target.source_path_hour_utc,
                    "expected_size_bytes": state.target.expected_size_bytes,
                    "expected_etag": state.target.expected_etag,
                    "expected_compressed_sha256": state.target.expected_compressed_sha256,
                    "request_count": state.request_count,
                    "request_status": state.request_status,
                    "response_http_status": state.response_http_status,
                    "response_etag": state.response_etag,
                    "response_content_length": state.response_content_length,
                    "response_requester_charged": state.response_requester_charged,
                    "received_body_bytes": state.received_body_bytes,
                    "observed_compressed_sha256": state.observed_compressed_sha256,
                    "first_pass_status": state.first_pass_status,
                    "first_pass_decompressed_bytes": state.first_pass_decompressed_bytes,
                    "first_pass_record_count": state.first_pass_record_count,
                    "first_pass_event_count": state.first_pass_event_count,
                    "first_pass_stream_sha256": state.first_pass_stream_sha256,
                    "second_pass_status": state.second_pass_status,
                    "second_pass_decompressed_bytes": state.second_pass_decompressed_bytes,
                    "second_pass_record_count": state.second_pass_record_count,
                    "second_pass_event_count": state.second_pass_event_count,
                    "second_pass_stream_sha256": state.second_pass_stream_sha256,
                    "terminal_status": state.terminal_status,
                    "terminal_error_code": state.terminal_error_code,
                }
            )
        return tuple(rows)

    def stop_rows(self) -> tuple[dict[str, object], ...]:
        return tuple(entry.as_mapping() for entry in self._stops)

    def exact_scope_complete(self) -> bool:
        return (
            len(self._objects) == 72
            and self._network_request_count == 72
            and all(state.terminal_status == "COMPLETE_TWO_LOCAL_PASSES" for state in self._objects)
        )

    def aggregate_counts(self) -> dict[str, int]:
        first_decompressed = sum(state.first_pass_decompressed_bytes or 0 for state in self._objects)
        second_decompressed = sum(state.second_pass_decompressed_bytes or 0 for state in self._objects)
        return {
            "selected_object_count": len(self._objects),
            "get_object_request_count": self._network_request_count,
            "first_pass_completed_object_count": sum(
                state.first_pass_status == "COMPLETE" for state in self._objects
            ),
            "second_pass_completed_object_count": sum(
                state.second_pass_status == "COMPLETE" for state in self._objects
            ),
            "first_pass_decompressed_bytes": first_decompressed,
            "second_pass_decompressed_bytes": second_decompressed,
            "total_decompressed_processing_bytes": first_decompressed + second_decompressed,
            "first_pass_record_count": sum(state.first_pass_record_count or 0 for state in self._objects),
            "second_pass_record_count": sum(state.second_pass_record_count or 0 for state in self._objects),
            "first_pass_event_count": sum(state.first_pass_event_count or 0 for state in self._objects),
            "second_pass_event_count": sum(state.second_pass_event_count or 0 for state in self._objects),
        }
