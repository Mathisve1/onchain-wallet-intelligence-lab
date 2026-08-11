from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Mapping


class R11AV2LimitError(ValueError):
    """Raised when a V2 resource envelope is invalid or exceeded."""


@dataclass(frozen=True, slots=True)
class R11AV2Limits:
    maximum_one_time_budget_eur_micros: int = 500_000
    maximum_monthly_budget_eur_micros: int = 0
    maximum_get_object_requests: int = 72
    maximum_requests_per_object: int = 1
    maximum_retries_per_request: int = 0
    maximum_total_compressed_bytes: int = 2_107_738_436
    maximum_individual_compressed_bytes: int = 76_616_104
    maximum_total_decompressed_bytes_across_two_local_passes: int = 21_079_958_490
    maximum_individual_decompressed_bytes_per_pass: int = 536_870_912
    maximum_ephemeral_workspace_bytes: int = 5_368_709_120
    minimum_free_workspace_bytes_before_oidc: int = 6_442_450_944
    maximum_retained_artifact_bytes: int = 134_217_728
    reserved_non_scientific_package_metadata_bytes: int = 4_194_304
    maximum_retained_scientific_output_bytes: int = 130_023_424
    maximum_runtime_seconds: int = 21_600
    post_measurement_packaging_reservation_seconds: int = 300
    minimum_upload_window_seconds: int = 60
    partition_count: int = 256
    external_sort_memory_bytes: int = 67_108_864
    maximum_retained_repeated_legacy_groups: int = 100_000
    maximum_retained_repeated_legacy_observations: int = 250_000
    maximum_retained_repeated_block_groups: int = 100_000
    maximum_single_group_spool_bytes: int = 67_108_864
    package_boundary_bytes: int = 1_024

    def validate_shape(self) -> None:
        values = asdict(self)
        for key, value in values.items():
            if type(value) is not int or value < 0:
                raise R11AV2LimitError(f"{key} must be a nonnegative integer")
        if self.maximum_get_object_requests < 1:
            raise R11AV2LimitError("request count must be positive")
        if self.maximum_requests_per_object != 1:
            raise R11AV2LimitError("exactly one request per object is required")
        if self.maximum_retries_per_request != 0:
            raise R11AV2LimitError("retries are forbidden")
        if self.partition_count < 2 or self.partition_count > 256:
            raise R11AV2LimitError("partition count must be in 2..256")
        if self.maximum_retained_scientific_output_bytes + self.reserved_non_scientific_package_metadata_bytes != self.maximum_retained_artifact_bytes:
            raise R11AV2LimitError("scientific plus metadata caps must equal artifact cap")
        if self.minimum_free_workspace_bytes_before_oidc < self.maximum_ephemeral_workspace_bytes:
            raise R11AV2LimitError("pre-OIDC free-space threshold must cover workspace cap")
        if self.post_measurement_packaging_reservation_seconds + self.minimum_upload_window_seconds >= self.maximum_runtime_seconds:
            raise R11AV2LimitError("runtime must preserve packaging and upload windows")
        if self.external_sort_memory_bytes < 1:
            raise R11AV2LimitError("sort memory must be positive")
        if self.maximum_single_group_spool_bytes < 1:
            raise R11AV2LimitError("group spool cap must be positive")
        if self.package_boundary_bytes != 1_024:
            raise R11AV2LimitError("package boundary must remain 1024 bytes")

    def validate_frozen(self) -> None:
        self.validate_shape()
        if self != FROZEN_LIMITS:
            raise R11AV2LimitError("production limits differ from frozen V2 envelope")

    def for_test(self, **changes: int) -> "R11AV2Limits":
        candidate = replace(self, **changes)
        candidate.validate_shape()
        return candidate

    def as_mapping(self) -> dict[str, int]:
        self.validate_shape()
        return asdict(self)

    def require_not_exceeded(self, observed: Mapping[str, int]) -> None:
        self.validate_shape()
        comparators = {
            "one_time_budget_eur_micros": self.maximum_one_time_budget_eur_micros,
            "monthly_budget_eur_micros": self.maximum_monthly_budget_eur_micros,
            "get_object_requests": self.maximum_get_object_requests,
            "requests_for_one_object": self.maximum_requests_per_object,
            "retries": self.maximum_retries_per_request,
            "total_compressed_bytes": self.maximum_total_compressed_bytes,
            "individual_compressed_bytes": self.maximum_individual_compressed_bytes,
            "total_decompressed_bytes_across_two_local_passes": self.maximum_total_decompressed_bytes_across_two_local_passes,
            "individual_decompressed_bytes_per_pass": self.maximum_individual_decompressed_bytes_per_pass,
            "peak_ephemeral_workspace_bytes": self.maximum_ephemeral_workspace_bytes,
            "retained_artifact_bytes": self.maximum_retained_artifact_bytes,
            "retained_scientific_output_bytes": self.maximum_retained_scientific_output_bytes,
            "elapsed_runtime_seconds": self.maximum_runtime_seconds - 1,
            "repeated_legacy_groups": self.maximum_retained_repeated_legacy_groups,
            "repeated_legacy_observations": self.maximum_retained_repeated_legacy_observations,
            "repeated_block_groups": self.maximum_retained_repeated_block_groups,
            "single_group_spool_bytes": self.maximum_single_group_spool_bytes,
        }
        unknown = set(observed) - set(comparators)
        if unknown:
            raise R11AV2LimitError(f"unknown observed cap keys: {sorted(unknown)}")
        for key, value in observed.items():
            if type(value) is not int or value < 0:
                raise R11AV2LimitError(f"observed {key} must be a nonnegative integer")
            if value > comparators[key]:
                raise R11AV2LimitError(f"{key} cap exceeded: {value} > {comparators[key]}")


FROZEN_LIMITS = R11AV2Limits()
FROZEN_LIMITS.validate_shape()
