from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping

from .limits import R11AV2LimitError, R11AV2Limits


class R11AV2RuntimeError(ValueError):
    """Raised when runtime or lifecycle evidence fails closed."""


STOP_CONDITIONS = (
    "PRE_OIDC_STATIC_GATE_FAILURE",
    "PRE_OIDC_FREE_SPACE_FAILURE",
    "OIDC_OR_STS_PRINCIPAL_FAILURE",
    "REQUEST_BUDGET_FAILURE",
    "TRANSPORT_METADATA_FAILURE",
    "TRANSPORT_BODY_FAILURE",
    "COMPRESSED_INTEGRITY_FAILURE",
    "DECOMPRESSION_OR_PARSE_FAILURE",
    "TWO_PASS_COMMITMENT_MISMATCH",
    "WORKSPACE_CAP_FAILURE",
    "RUNTIME_RESERVE_FAILURE",
    "RETENTION_OR_ARTIFACT_CAP_FAILURE",
    "TAXONOMY_CONSERVATION_OR_PROOF_FAILURE",
)

OBJECT_STATUSES = (
    "NOT_REQUESTED",
    "REQUEST_SENT",
    "RESPONSE_METADATA_ACCEPTED",
    "BODY_PARTIAL",
    "BODY_COMPLETE_VERIFIED",
    "FIRST_PASS_COMPLETE",
    "SECOND_PASS_COMPLETE",
    "COMPLETE_TWO_LOCAL_PASSES",
    "FAILED",
)


@dataclass(slots=True)
class RuntimeGuard:
    limits: R11AV2Limits
    monotonic_ns: Callable[[], int] = time.monotonic_ns
    start_ns: int = field(init=False)
    checkpoints: list[dict[str, object]] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self.limits.validate_shape()
        self.start_ns = self.monotonic_ns()

    def elapsed_ns(self) -> int:
        value = self.monotonic_ns() - self.start_ns
        if value < 0:
            raise R11AV2RuntimeError("monotonic clock moved backwards")
        return value

    def elapsed_milliseconds(self) -> int:
        return self.elapsed_ns() // 1_000_000

    def _check(self, label: str, deadline_seconds: int, phase: str) -> int:
        elapsed_ms = self.elapsed_milliseconds()
        if elapsed_ms > deadline_seconds * 1000:
            raise R11AV2RuntimeError(
                f"runtime reserve exceeded at {label}: {elapsed_ms}ms > {deadline_seconds*1000}ms"
            )
        self.checkpoints.append(
            {
                "checkpoint_ordinal_zero_based": len(self.checkpoints),
                "phase": phase,
                "label_sha256": hashlib.sha256(label.encode("utf-8", errors="strict")).hexdigest(),
                "elapsed_runtime_milliseconds": elapsed_ms,
                "deadline_milliseconds": deadline_seconds * 1000,
            }
        )
        return elapsed_ms

    def check_measurement(self, label: str) -> int:
        deadline = (
            self.limits.maximum_runtime_seconds
            - self.limits.post_measurement_packaging_reservation_seconds
            - self.limits.minimum_upload_window_seconds
        )
        return self._check(label, deadline, "MEASUREMENT")

    def check_packaging(self, label: str) -> int:
        deadline = self.limits.maximum_runtime_seconds - self.limits.minimum_upload_window_seconds
        return self._check(label, deadline, "PACKAGING")

    def check_pre_upload(self, label: str) -> int:
        return self._check(label, self.limits.maximum_runtime_seconds, "PRE_UPLOAD")


@dataclass(frozen=True, slots=True)
class RuntimeTarget:
    object_ordinal_zero_based: int
    object_key: str
    expected_etag: str
    expected_size_bytes: int
    expected_compressed_sha256: str
    path_hour_utc: str

    def __post_init__(self) -> None:
        if type(self.object_ordinal_zero_based) is not int or self.object_ordinal_zero_based < 0:
            raise R11AV2RuntimeError("object ordinal invalid")
        if type(self.object_key) is not str or not self.object_key:
            raise R11AV2RuntimeError("object key invalid")
        if type(self.expected_etag) is not str or not self.expected_etag:
            raise R11AV2RuntimeError("expected ETag invalid")
        if type(self.expected_size_bytes) is not int or self.expected_size_bytes < 1:
            raise R11AV2RuntimeError("expected object size invalid")
        if type(self.expected_compressed_sha256) is not str or len(self.expected_compressed_sha256) != 64:
            raise R11AV2RuntimeError("expected compressed SHA invalid")


@dataclass(slots=True)
class ObjectEvidenceState:
    targets: tuple[RuntimeTarget, ...]
    _rows: list[dict[str, object]] = field(init=False)

    def __post_init__(self) -> None:
        ordinals = [target.object_ordinal_zero_based for target in self.targets]
        if ordinals != list(range(len(self.targets))):
            raise R11AV2RuntimeError("target ordinals must be exact contiguous order")
        if len({target.object_key for target in self.targets}) != len(self.targets):
            raise R11AV2RuntimeError("target object keys must be unique")
        self._rows = [self._initial_row(target) for target in self.targets]

    @staticmethod
    def _initial_row(target: RuntimeTarget) -> dict[str, object]:
        return {
            "record_type": "OBJECT_EXECUTION_EVIDENCE",
            "object_ordinal_zero_based": target.object_ordinal_zero_based,
            "object_key": target.object_key,
            "path_hour_utc": target.path_hour_utc,
            "expected_etag": target.expected_etag,
            "expected_content_length_bytes": target.expected_size_bytes,
            "expected_compressed_sha256": target.expected_compressed_sha256,
            "processing_status": "NOT_REQUESTED",
            "get_object_request_count": 0,
            "http_status": None,
            "requester_charged_header": None,
            "observed_etag": None,
            "observed_content_length_bytes": None,
            "received_body_bytes": 0,
            "observed_compressed_sha256": None,
            "first_pass_summary_sha256": None,
            "first_pass_raw_block_count": None,
            "first_pass_raw_event_count": None,
            "second_pass_summary_sha256": None,
            "second_pass_raw_block_count": None,
            "second_pass_raw_event_count": None,
            "failure_code": None,
            "failure_message_sha256": None,
            "last_transition_ordinal": 0,
        }

    def _row(self, ordinal: int) -> dict[str, object]:
        if type(ordinal) is not int or not 0 <= ordinal < len(self._rows):
            raise R11AV2RuntimeError("object ordinal outside evidence state")
        return self._rows[ordinal]

    def _transition(self, ordinal: int, expected: Iterable[str], target: str) -> dict[str, object]:
        if target not in OBJECT_STATUSES:
            raise R11AV2RuntimeError("unknown object status")
        row = self._row(ordinal)
        if row["processing_status"] not in set(expected):
            raise R11AV2RuntimeError(
                f"invalid object transition {row['processing_status']} -> {target} for {ordinal}"
            )
        row["processing_status"] = target
        row["last_transition_ordinal"] = int(row["last_transition_ordinal"]) + 1
        return row

    def mark_request_sent(self, ordinal: int) -> None:
        row = self._transition(ordinal, ("NOT_REQUESTED",), "REQUEST_SENT")
        row["get_object_request_count"] = 1

    def mark_response_metadata(
        self,
        ordinal: int,
        *,
        http_status: int,
        requester_charged_header: str,
        observed_etag: str,
        observed_content_length_bytes: int,
    ) -> None:
        row = self._transition(ordinal, ("REQUEST_SENT",), "RESPONSE_METADATA_ACCEPTED")
        row["http_status"] = http_status
        row["requester_charged_header"] = requester_charged_header
        row["observed_etag"] = observed_etag
        row["observed_content_length_bytes"] = observed_content_length_bytes

    def mark_body_progress(self, ordinal: int, cumulative_bytes: int) -> None:
        row = self._row(ordinal)
        if row["processing_status"] not in {"RESPONSE_METADATA_ACCEPTED", "BODY_PARTIAL"}:
            raise R11AV2RuntimeError("body progress before metadata acceptance")
        if type(cumulative_bytes) is not int or cumulative_bytes <= int(row["received_body_bytes"]):
            raise R11AV2RuntimeError("body byte count must increase strictly")
        row["processing_status"] = "BODY_PARTIAL"
        row["received_body_bytes"] = cumulative_bytes
        row["last_transition_ordinal"] = int(row["last_transition_ordinal"]) + 1

    def mark_body_complete(self, ordinal: int, observed_sha256: str) -> None:
        row = self._transition(ordinal, ("BODY_PARTIAL",), "BODY_COMPLETE_VERIFIED")
        if row["received_body_bytes"] != row["expected_content_length_bytes"]:
            raise R11AV2RuntimeError("body complete with wrong byte count")
        if observed_sha256 != row["expected_compressed_sha256"]:
            raise R11AV2RuntimeError("body complete with wrong compressed SHA")
        row["observed_compressed_sha256"] = observed_sha256

    def mark_first_pass(
        self,
        ordinal: int,
        *,
        summary_sha256: str,
        raw_block_count: int,
        raw_event_count: int,
    ) -> None:
        row = self._transition(ordinal, ("BODY_COMPLETE_VERIFIED",), "FIRST_PASS_COMPLETE")
        row["first_pass_summary_sha256"] = summary_sha256
        row["first_pass_raw_block_count"] = raw_block_count
        row["first_pass_raw_event_count"] = raw_event_count

    def mark_second_pass(
        self,
        ordinal: int,
        *,
        summary_sha256: str,
        raw_block_count: int,
        raw_event_count: int,
    ) -> None:
        row = self._transition(ordinal, ("FIRST_PASS_COMPLETE",), "SECOND_PASS_COMPLETE")
        row["second_pass_summary_sha256"] = summary_sha256
        row["second_pass_raw_block_count"] = raw_block_count
        row["second_pass_raw_event_count"] = raw_event_count
        if row["first_pass_summary_sha256"] != summary_sha256:
            raise R11AV2RuntimeError("two-pass summary commitment mismatch")
        if row["first_pass_raw_block_count"] != raw_block_count:
            raise R11AV2RuntimeError("two-pass block count mismatch")
        if row["first_pass_raw_event_count"] != raw_event_count:
            raise R11AV2RuntimeError("two-pass event count mismatch")
        self._transition(ordinal, ("SECOND_PASS_COMPLETE",), "COMPLETE_TWO_LOCAL_PASSES")

    def mark_failure(self, ordinal: int, *, failure_code: str, message: str) -> None:
        row = self._row(ordinal)
        if row["processing_status"] == "COMPLETE_TWO_LOCAL_PASSES":
            raise R11AV2RuntimeError("cannot fail an already complete object")
        row["processing_status"] = "FAILED"
        row["failure_code"] = failure_code
        row["failure_message_sha256"] = hashlib.sha256(message.encode("utf-8", errors="strict")).hexdigest()
        row["last_transition_ordinal"] = int(row["last_transition_ordinal"]) + 1

    def rows(self) -> tuple[dict[str, object], ...]:
        return tuple(dict(row) for row in self._rows)

    def completed_count(self) -> int:
        return sum(row["processing_status"] == "COMPLETE_TWO_LOCAL_PASSES" for row in self._rows)

    def total_request_count(self) -> int:
        return sum(int(row["get_object_request_count"]) for row in self._rows)

    def validate_terminal_shape(self, *, expected_count: int) -> None:
        if len(self._rows) != expected_count:
            raise R11AV2RuntimeError("object ledger cardinality drift")
        if self.total_request_count() > expected_count:
            raise R11AV2RuntimeError("object request count exceeds one per object")
        failure_seen = False
        for row in self._rows:
            status = row["processing_status"]
            if failure_seen and status not in {"NOT_REQUESTED", "FAILED"}:
                raise R11AV2RuntimeError("processing continued after first failed object")
            if status == "FAILED":
                failure_seen = True


@dataclass(slots=True)
class StopLedger:
    _rows: list[dict[str, object]] = field(init=False)
    _triggered: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self._rows = [
            {
                "record_type": "STOP_CONDITION_EVIDENCE",
                "stop_condition_ordinal_zero_based": index,
                "stop_condition": name,
                "triggered": False,
                "phase": None,
                "evidence_sha256": None,
            }
            for index, name in enumerate(STOP_CONDITIONS)
        ]

    def trigger(self, name: str, *, phase: str, evidence: Mapping[str, object]) -> None:
        if name not in STOP_CONDITIONS:
            raise R11AV2RuntimeError(f"unknown stop condition: {name}")
        if self._triggered:
            raise R11AV2RuntimeError("a second stop condition cannot be triggered")
        row = self._rows[STOP_CONDITIONS.index(name)]
        row["triggered"] = True
        row["phase"] = phase
        canonical = repr(sorted(evidence.items(), key=lambda item: item[0])).encode("utf-8", errors="strict")
        row["evidence_sha256"] = hashlib.sha256(canonical).hexdigest()
        self._triggered = True

    def rows(self) -> tuple[dict[str, object], ...]:
        return tuple(dict(row) for row in self._rows)

    def triggered_name(self) -> str | None:
        for row in self._rows:
            if row["triggered"]:
                return str(row["stop_condition"])
        return None


@dataclass(slots=True)
class ResourceLedger:
    limits: R11AV2Limits
    get_object_requests: int = 0
    retries: int = 0
    total_compressed_bytes: int = 0
    total_decompressed_bytes_across_two_local_passes: int = 0
    peak_ephemeral_workspace_bytes: int = 0
    retained_scientific_output_bytes: int = 0
    retained_artifact_bytes: int = 0
    repeated_legacy_groups: int = 0
    repeated_legacy_observations: int = 0
    repeated_block_groups: int = 0
    maximum_single_group_spool_bytes_observed: int = 0

    def __post_init__(self) -> None:
        self.limits.validate_shape()

    def observe(self, **values: int) -> None:
        for key, value in values.items():
            if not hasattr(self, key):
                raise R11AV2RuntimeError(f"unknown resource field: {key}")
            if type(value) is not int or value < 0:
                raise R11AV2RuntimeError(f"resource observation must be nonnegative integer: {key}")
            setattr(self, key, value)
        self.validate()

    def validate(self) -> None:
        try:
            self.limits.require_not_exceeded(
                {
                    "get_object_requests": self.get_object_requests,
                    "retries": self.retries,
                    "total_compressed_bytes": self.total_compressed_bytes,
                    "total_decompressed_bytes_across_two_local_passes": self.total_decompressed_bytes_across_two_local_passes,
                    "peak_ephemeral_workspace_bytes": self.peak_ephemeral_workspace_bytes,
                    "retained_scientific_output_bytes": self.retained_scientific_output_bytes,
                    "retained_artifact_bytes": self.retained_artifact_bytes,
                    "repeated_legacy_groups": self.repeated_legacy_groups,
                    "repeated_legacy_observations": self.repeated_legacy_observations,
                    "repeated_block_groups": self.repeated_block_groups,
                    "single_group_spool_bytes": self.maximum_single_group_spool_bytes_observed,
                }
            )
        except R11AV2LimitError as exc:
            raise R11AV2RuntimeError(str(exc)) from exc

    def as_mapping(self, *, elapsed_runtime_milliseconds: int) -> dict[str, object]:
        self.validate()
        return {
            "record_type": "RESOURCE_LEDGER",
            "get_object_requests": self.get_object_requests,
            "retries": self.retries,
            "total_compressed_bytes": self.total_compressed_bytes,
            "total_decompressed_bytes_across_two_local_passes": self.total_decompressed_bytes_across_two_local_passes,
            "peak_ephemeral_workspace_bytes": self.peak_ephemeral_workspace_bytes,
            "retained_scientific_output_bytes": self.retained_scientific_output_bytes,
            "retained_artifact_bytes": self.retained_artifact_bytes,
            "repeated_legacy_groups": self.repeated_legacy_groups,
            "repeated_legacy_observations": self.repeated_legacy_observations,
            "repeated_block_groups": self.repeated_block_groups,
            "maximum_single_group_spool_bytes_observed": self.maximum_single_group_spool_bytes_observed,
            "elapsed_runtime_milliseconds": elapsed_runtime_milliseconds,
            "limits": self.limits.as_mapping(),
        }
