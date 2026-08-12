from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Final

from .canonical import FrozenObject, NumberToken, strict_json_loads

ROOT: Final[Path] = Path(__file__).resolve().parents[3]
PREREGISTRATION_PATH: Final[Path] = (
    ROOT
    / "research/archive_inventory/r11a_v2/R11A_CORRECTIVE_PREREGISTRATION_AMENDMENT.json"
)
SELECTION_PATH: Final[Path] = ROOT / "research/archive_inventory/r11/R11_72H_SELECTION.json"


class R11ALimitError(ValueError):
    pass


def _as_object(value: object, label: str) -> FrozenObject:
    if not isinstance(value, FrozenObject):
        raise R11ALimitError(f"{label} must be an object")
    return value


def _as_int(value: object, label: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, NumberToken) and value.is_integer_token:
        return int(value.token, 10)
    raise R11ALimitError(f"{label} must be an exact JSON integer")


@dataclasses.dataclass(frozen=True, slots=True)
class R11ALimits:
    maximum_one_time_budget_eur_micros: int
    maximum_monthly_budget_eur_micros: int
    maximum_get_object_requests: int
    maximum_requests_per_object: int
    maximum_retries_per_request: int
    maximum_total_compressed_bytes: int
    maximum_individual_compressed_bytes: int
    maximum_total_decompressed_bytes_across_two_passes: int
    maximum_individual_decompressed_bytes_per_pass: int
    maximum_ephemeral_workspace_bytes: int
    minimum_free_workspace_bytes_before_oidc: int
    maximum_retained_artifact_bytes: int
    reserved_non_scientific_package_metadata_bytes: int
    maximum_retained_scientific_output_bytes: int
    maximum_runtime_seconds: int
    maximum_repeated_legacy_key_groups_retained: int
    maximum_repeated_observations_retained: int
    maximum_repeated_block_groups_retained: int
    partition_count: int = 256
    package_boundary_bytes: int = 1024
    post_measurement_packaging_reservation_seconds: int = 300
    minimum_upload_window_seconds: int = 60
    maximum_json_number_token_bytes: int = 4096
    maximum_equality_group_spool_bytes: int = 67_108_864
    maximum_sort_chunk_bytes: int = 67_108_864

    @property
    def scientific_deadline_seconds(self) -> int:
        return (
            self.maximum_runtime_seconds
            - self.post_measurement_packaging_reservation_seconds
            - self.minimum_upload_window_seconds
        )

    def validate(self) -> None:
        exact_values = {
            "maximum_one_time_budget_eur_micros": 500_000,
            "maximum_monthly_budget_eur_micros": 0,
            "maximum_get_object_requests": 72,
            "maximum_requests_per_object": 1,
            "maximum_retries_per_request": 0,
            "maximum_total_compressed_bytes": 2_107_738_436,
            "maximum_individual_compressed_bytes": 76_616_104,
            "maximum_total_decompressed_bytes_across_two_passes": 21_079_958_490,
            "maximum_individual_decompressed_bytes_per_pass": 536_870_912,
            "maximum_ephemeral_workspace_bytes": 5_368_709_120,
            "minimum_free_workspace_bytes_before_oidc": 6_442_450_944,
            "maximum_retained_artifact_bytes": 134_217_728,
            "reserved_non_scientific_package_metadata_bytes": 4_194_304,
            "maximum_retained_scientific_output_bytes": 130_023_424,
            "maximum_runtime_seconds": 21_600,
            "maximum_repeated_legacy_key_groups_retained": 100_000,
            "maximum_repeated_observations_retained": 250_000,
            "maximum_repeated_block_groups_retained": 100_000,
            "partition_count": 256,
            "package_boundary_bytes": 1_024,
            "post_measurement_packaging_reservation_seconds": 300,
            "minimum_upload_window_seconds": 60,
            "maximum_json_number_token_bytes": 4_096,
            "maximum_equality_group_spool_bytes": 67_108_864,
            "maximum_sort_chunk_bytes": 67_108_864,
        }
        for key, expected in exact_values.items():
            observed = getattr(self, key)
            if observed != expected:
                raise R11ALimitError(f"frozen V2 limit drift: {key}={observed}, expected {expected}")
        if (
            self.reserved_non_scientific_package_metadata_bytes
            + self.maximum_retained_scientific_output_bytes
            != self.maximum_retained_artifact_bytes
        ):
            raise R11ALimitError("scientific plus metadata reservations must equal the artifact cap")
        if self.minimum_free_workspace_bytes_before_oidc < self.maximum_ephemeral_workspace_bytes:
            raise R11ALimitError("pre-OIDC free-space threshold must cover the workspace cap")
        if self.scientific_deadline_seconds <= 0:
            raise R11ALimitError("runtime must retain packaging and upload windows")
        positive = (
            self.maximum_individual_decompressed_bytes_per_pass,
            self.reserved_non_scientific_package_metadata_bytes,
            self.maximum_retained_scientific_output_bytes,
            self.maximum_repeated_legacy_key_groups_retained,
            self.maximum_repeated_observations_retained,
            self.maximum_repeated_block_groups_retained,
            self.maximum_equality_group_spool_bytes,
            self.maximum_sort_chunk_bytes,
        )
        if any(value <= 0 for value in positive):
            raise R11ALimitError("all nonzero capacity bounds must be positive")

    def as_contract_mapping(self) -> dict[str, int]:
        self.validate()
        return {field.name: int(getattr(self, field.name)) for field in dataclasses.fields(self)}


def load_limits(path: Path = PREREGISTRATION_PATH) -> R11ALimits:
    prereg = _as_object(strict_json_loads(path.read_bytes()), "corrective preregistration")
    if prereg["diagnostic_id"] != "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-002":
        raise R11ALimitError("corrective diagnostic identity drift")
    if prereg["status"] != "PREREGISTERED_NO_EXECUTION":
        raise R11ALimitError("corrective preregistration status drift")
    envelope = _as_object(prereg["request_and_resource_envelope"], "request_and_resource_envelope")
    limits = R11ALimits(
        maximum_one_time_budget_eur_micros=_as_int(
            envelope["maximum_one_time_budget_eur_micros"],
            "maximum_one_time_budget_eur_micros",
        ),
        maximum_monthly_budget_eur_micros=_as_int(
            envelope["maximum_monthly_budget_eur_micros"],
            "maximum_monthly_budget_eur_micros",
        ),
        maximum_get_object_requests=_as_int(
            envelope["maximum_get_object_requests"], "maximum_get_object_requests"
        ),
        maximum_requests_per_object=_as_int(
            envelope["maximum_requests_per_object"], "maximum_requests_per_object"
        ),
        maximum_retries_per_request=_as_int(
            envelope["maximum_retries_per_request"], "maximum_retries_per_request"
        ),
        maximum_total_compressed_bytes=_as_int(
            envelope["maximum_total_compressed_bytes"], "maximum_total_compressed_bytes"
        ),
        maximum_individual_compressed_bytes=_as_int(
            envelope["maximum_individual_compressed_bytes"],
            "maximum_individual_compressed_bytes",
        ),
        maximum_total_decompressed_bytes_across_two_passes=_as_int(
            envelope["maximum_total_decompressed_bytes_across_two_local_passes"],
            "maximum_total_decompressed_bytes_across_two_local_passes",
        ),
        maximum_individual_decompressed_bytes_per_pass=_as_int(
            envelope["maximum_individual_decompressed_bytes_per_pass"],
            "maximum_individual_decompressed_bytes_per_pass",
        ),
        maximum_ephemeral_workspace_bytes=_as_int(
            envelope["maximum_ephemeral_workspace_bytes"],
            "maximum_ephemeral_workspace_bytes",
        ),
        minimum_free_workspace_bytes_before_oidc=_as_int(
            envelope["minimum_free_workspace_bytes_before_oidc"],
            "minimum_free_workspace_bytes_before_oidc",
        ),
        maximum_retained_artifact_bytes=_as_int(
            envelope["maximum_retained_artifact_bytes"], "maximum_retained_artifact_bytes"
        ),
        reserved_non_scientific_package_metadata_bytes=_as_int(
            envelope["reserved_non_scientific_package_metadata_bytes"],
            "reserved_non_scientific_package_metadata_bytes",
        ),
        maximum_retained_scientific_output_bytes=_as_int(
            envelope["maximum_retained_scientific_output_bytes"],
            "maximum_retained_scientific_output_bytes",
        ),
        maximum_runtime_seconds=_as_int(
            envelope["maximum_runtime_seconds"], "maximum_runtime_seconds"
        ),
        maximum_repeated_legacy_key_groups_retained=_as_int(
            envelope["maximum_retained_repeated_legacy_groups"],
            "maximum_retained_repeated_legacy_groups",
        ),
        maximum_repeated_observations_retained=_as_int(
            envelope["maximum_retained_repeated_legacy_observations"],
            "maximum_retained_repeated_legacy_observations",
        ),
        maximum_repeated_block_groups_retained=_as_int(
            envelope["maximum_retained_repeated_block_groups"],
            "maximum_retained_repeated_block_groups",
        ),
        partition_count=_as_int(envelope["partition_count"], "partition_count"),
        post_measurement_packaging_reservation_seconds=_as_int(
            envelope["post_measurement_packaging_reservation_seconds"],
            "post_measurement_packaging_reservation_seconds",
        ),
        minimum_upload_window_seconds=_as_int(
            envelope["minimum_upload_window_seconds"], "minimum_upload_window_seconds"
        ),
        maximum_equality_group_spool_bytes=_as_int(
            envelope["maximum_single_group_spool_bytes"],
            "maximum_single_group_spool_bytes",
        ),
        maximum_sort_chunk_bytes=_as_int(
            envelope["external_sort_memory_bytes"], "external_sort_memory_bytes"
        ),
    )
    limits.validate()
    return limits


DEFAULT_LIMITS: Final[R11ALimits] = load_limits()
