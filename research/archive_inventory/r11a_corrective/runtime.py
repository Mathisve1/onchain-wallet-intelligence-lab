from __future__ import annotations

import dataclasses
import hashlib
import time
from collections.abc import Callable, Mapping, Sequence

from .artifact_schema import (
    DIAGNOSTIC_ID,
    PARSE_CONSERVATION_FIELDS,
    PHASES,
    validate_object_row_shape,
    validate_parse_conservation,
)
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
        deadline = (
            self.limits.maximum_runtime_seconds
            - self.limits.minimum_upload_window_seconds
        )
        if self.elapsed_ns() >= deadline * 1_000_000_000:
            raise RuntimeBoundaryError(f"packaging runtime reserve reached at {phase}")

    def check_hard_deadline(self, phase: str) -> None:
        if self.elapsed_ns() >= self.limits.maximum_runtime_seconds * 1_000_000_000:
            raise RuntimeBoundaryError(f"hard runtime reached at {phase}")

    def package_flags(self) -> dict[str, bool]:
        elapsed = self.elapsed_seconds_floor()
        return {
            "preupload_runtime_within_hard_limit_after_upload_window": elapsed
            < self.limits.maximum_runtime_seconds
            - self.limits.minimum_upload_window_seconds,
            "scientific_runtime_completed_before_packaging_reservation": elapsed
            < self.limits.maximum_runtime_seconds,
        }


@dataclasses.dataclass(frozen=True, slots=True)
class RuntimeTarget:
    object_ordinal_zero_based: int
    object_key: str
    expected_size_bytes: int
    expected_etag: str
    expected_compressed_sha256: str
    source_path_hour_utc: str

    def __post_init__(self) -> None:
        if not 0 <= self.object_ordinal_zero_based < 72:
            raise RuntimeBoundaryError("object ordinal outside exact 72-object scope")
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
    response: dict[str, object] | None = None
    body_status: str = "NOT_STARTED"
    body_bytes_received: int = 0
    observed_compressed_sha256: str | None = None
    first_pass: dict[str, object] | None = None
    second_pass: dict[str, object] | None = None
    terminal_status: str = "PENDING"
    terminal_error_code: str | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class StopEntry:
    sequence_zero_based: int
    diagnostic_id: str
    stop_code: str
    phase: str
    object_ordinal_zero_based: int | None
    evidence_sha256: str

    def as_mapping(self) -> dict[str, object]:
        return dataclasses.asdict(self)


class ExecutionEvidenceState:
    """Phase-truthful exact lifecycle evidence for all selected objects."""

    def __init__(self, targets: Sequence[RuntimeTarget], limits: R11ALimits) -> None:
        limits.validate()
        if len(targets) != 72:
            raise RuntimeBoundaryError(
                "runtime target count must equal exact 72-object scope"
            )
        ordered = sorted(targets, key=lambda value: value.object_ordinal_zero_based)
        if [value.object_ordinal_zero_based for value in ordered] != list(range(72)):
            raise RuntimeBoundaryError(
                "object ordinals must be contiguous from zero"
            )
        if len({value.object_key for value in ordered}) != 72:
            raise RuntimeBoundaryError("object keys must be unique")
        self._limits = limits
        self._objects = [_MutableObjectState(value) for value in ordered]
        self._stops: list[StopEntry] = []
        self._network_request_count = 0
        self._current_phase = "PRE_OIDC_STATIC_GATE"

    @property
    def network_request_count(self) -> int:
        return self._network_request_count

    @property
    def current_phase(self) -> str:
        return self._current_phase

    def mark_phase(self, phase: str) -> None:
        if phase not in PHASES:
            raise RuntimeBoundaryError(f"unknown execution phase: {phase}")
        current = PHASES.index(self._current_phase)
        requested = PHASES.index(phase)
        if requested < current:
            raise RuntimeBoundaryError("execution phase moved backwards")
        self._current_phase = phase

    def _state(self, ordinal: int) -> _MutableObjectState:
        if not 0 <= ordinal < 72:
            raise RuntimeBoundaryError("object ordinal outside exact scope")
        return self._objects[ordinal]

    def request_sent(self, ordinal: int) -> None:
        self.mark_phase("S3_DOWNLOAD")
        state = self._state(ordinal)
        if state.request_count != 0:
            raise RuntimeBoundaryError("object request attempted more than once")
        if ordinal != self._network_request_count:
            raise RuntimeBoundaryError(
                "request order differs from path-hour ascending selection"
            )
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
            raise RuntimeBoundaryError("response metadata outside request lifecycle")
        state.response = {
            "http_status": http_status,
            "etag": etag,
            "content_length": content_length,
            "requester_charged": requester_charged,
        }
        state.request_status = "RESPONSE_METADATA_RECEIVED"

    def body_progress(self, ordinal: int, received_total: int) -> None:
        state = self._state(ordinal)
        if (
            state.request_status != "RESPONSE_METADATA_RECEIVED"
            or state.response is None
        ):
            raise RuntimeBoundaryError("body arrived before response metadata")
        if received_total < state.body_bytes_received:
            raise RuntimeBoundaryError("received body byte count decreased")
        if received_total > state.target.expected_size_bytes:
            raise RuntimeBoundaryError("received body exceeds verified size")
        state.body_bytes_received = received_total
        state.body_status = "STREAMING"

    def body_complete(self, ordinal: int, observed_sha256: str) -> None:
        state = self._state(ordinal)
        if state.body_status != "STREAMING":
            raise RuntimeBoundaryError("body completion outside streaming state")
        if state.body_bytes_received != state.target.expected_size_bytes:
            raise RuntimeBoundaryError("body completion with short bytes")
        if observed_sha256 != state.target.expected_compressed_sha256:
            raise RuntimeBoundaryError("compressed SHA-256 mismatch")
        state.observed_compressed_sha256 = observed_sha256
        state.body_status = "COMPLETE"
        state.request_status = "COMPLETE"

    def pass_complete(
        self,
        ordinal: int,
        *,
        pass_number: int,
        decompressed_bytes: int,
        record_count: int,
        event_count: int,
        stream_sha256: str,
        conservation: Mapping[str, object],
    ) -> None:
        state = self._state(ordinal)
        if state.body_status != "COMPLETE":
            raise RuntimeBoundaryError("local parse before integrity-bound body")
        if min(decompressed_bytes, record_count, event_count) < 0:
            raise RuntimeBoundaryError("negative local parse evidence")
        if len(stream_sha256) != 64:
            raise RuntimeBoundaryError("decompressed stream SHA-256 malformed")
        try:
            validate_parse_conservation(
                conservation,
                record_count=record_count,
                event_count=event_count,
                label=f"object_{ordinal}_pass_{pass_number}",
            )
        except ValueError as exc:
            raise RuntimeBoundaryError(
                "local pass conservation does not match shared artifact schema"
            ) from exc
        value = {
            "status": "COMPLETE",
            "decompressed_bytes": decompressed_bytes,
            "record_count": record_count,
            "event_count": event_count,
            "decompressed_stream_sha256": stream_sha256,
            "conservation": dict(conservation),
        }
        if pass_number == 1:
            self.mark_phase("FIRST_LOCAL_PASS")
            if state.first_pass is not None:
                raise RuntimeBoundaryError("first pass recorded twice")
            state.first_pass = value
        elif pass_number == 2:
            self.mark_phase("SECOND_LOCAL_PASS")
            if state.first_pass is None or state.second_pass is not None:
                raise RuntimeBoundaryError("second pass lifecycle invalid")
            if value != state.first_pass:
                raise RuntimeBoundaryError("independent local passes differ")
            state.second_pass = value
            state.terminal_status = "COMPLETE_TWO_LOCAL_PASSES"
        else:
            raise RuntimeBoundaryError("pass number must be one or two")

    def stop(
        self,
        stop_code: str,
        *,
        phase: str | None = None,
        object_ordinal_zero_based: int | None = None,
        evidence: Mapping[str, object] | None = None,
    ) -> None:
        observed_phase = self._current_phase if phase is None else phase
        if observed_phase not in PHASES:
            raise RuntimeBoundaryError("stop evidence uses unknown phase")
        payload = {} if evidence is None else dict(evidence)
        self._stops.append(
            StopEntry(
                sequence_zero_based=len(self._stops),
                diagnostic_id=DIAGNOSTIC_ID,
                stop_code=stop_code,
                phase=observed_phase,
                object_ordinal_zero_based=object_ordinal_zero_based,
                evidence_sha256=hashlib.sha256(
                    canonical_json_bytes(payload, final_newline=False)
                ).hexdigest(),
            )
        )
        if object_ordinal_zero_based is not None:
            state = self._state(object_ordinal_zero_based)
            state.terminal_status = "STOPPED"
            state.terminal_error_code = stop_code

    def object_rows(self) -> tuple[dict[str, object], ...]:
        rows: list[dict[str, object]] = []
        for state in self._objects:
            row = {
                "record_type": "R11A_V2_OBJECT_EXECUTION_EVIDENCE",
                "diagnostic_id": DIAGNOSTIC_ID,
                "object_ordinal_zero_based": (
                    state.target.object_ordinal_zero_based
                ),
                "object_key": state.target.object_key,
                "source_path_hour_utc": state.target.source_path_hour_utc,
                "expected_identity": {
                    "size_bytes": state.target.expected_size_bytes,
                    "etag": state.target.expected_etag,
                    "compressed_sha256": (
                        state.target.expected_compressed_sha256
                    ),
                },
                "request": {
                    "count": state.request_count,
                    "status": state.request_status,
                },
                "response": state.response,
                "body": {
                    "status": state.body_status,
                    "bytes_received": state.body_bytes_received,
                    "observed_compressed_sha256": (
                        state.observed_compressed_sha256
                    ),
                },
                "first_pass": state.first_pass,
                "second_pass": state.second_pass,
                "terminal_status": state.terminal_status,
                "terminal_error_code": state.terminal_error_code,
            }
            validate_object_row_shape(row)
            rows.append(row)
        return tuple(rows)

    def stop_rows(self) -> tuple[dict[str, object], ...]:
        return tuple(value.as_mapping() for value in self._stops)

    def exact_scope_complete(self) -> bool:
        return (
            self._network_request_count == 72
            and all(
                value.request_count == 1
                and value.request_status == "COMPLETE"
                and value.body_status == "COMPLETE"
                and value.observed_compressed_sha256
                == value.target.expected_compressed_sha256
                and value.first_pass is not None
                and value.second_pass is not None
                and value.first_pass == value.second_pass
                and value.terminal_status == "COMPLETE_TWO_LOCAL_PASSES"
                and value.terminal_error_code is None
                for value in self._objects
            )
        )

    def aggregate_counts(self) -> dict[str, int]:
        def total(pass_name: str, field: str) -> int:
            result = 0
            for state in self._objects:
                value = getattr(state, pass_name)
                if value is not None:
                    result += int(value[field])
            return result

        def conservation_total(pass_name: str, field: str) -> int:
            result = 0
            for state in self._objects:
                value = getattr(state, pass_name)
                if value is not None:
                    observed = value["conservation"]
                    if not isinstance(observed, Mapping):
                        raise RuntimeBoundaryError(
                            "stored pass conservation is not a mapping"
                        )
                    result += int(observed[field])
            return result

        result = {
            "selected_object_count": 72,
            "get_object_request_count": self._network_request_count,
            "first_pass_completed_object_count": sum(
                value.first_pass is not None for value in self._objects
            ),
            "second_pass_completed_object_count": sum(
                value.second_pass is not None for value in self._objects
            ),
            "first_pass_decompressed_bytes": total(
                "first_pass", "decompressed_bytes"
            ),
            "second_pass_decompressed_bytes": total(
                "second_pass", "decompressed_bytes"
            ),
            "first_pass_record_count": total("first_pass", "record_count"),
            "second_pass_record_count": total("second_pass", "record_count"),
            "first_pass_event_count": total("first_pass", "event_count"),
            "second_pass_event_count": total("second_pass", "event_count"),
        }
        for pass_name in ("first_pass", "second_pass"):
            for field in PARSE_CONSERVATION_FIELDS:
                result[f"{pass_name}_{field}"] = conservation_total(
                    pass_name, field
                )
        return result
