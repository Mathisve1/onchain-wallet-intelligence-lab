from __future__ import annotations

import dataclasses
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Final

from .canonical import FrozenObject, NumberToken, strict_json_loads

ROOT: Final[Path] = Path(__file__).resolve().parents[3]
PREREGISTRATION_PATH: Final[Path] = (
    ROOT
    / "research/archive_inventory/r11a/R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_PREREGISTRATION.json"
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
        parsed = int(value.token, 10)
        return parsed
    raise R11ALimitError(f"{label} must be an exact JSON integer")


def _as_decimal(value: object, label: str) -> Decimal:
    if isinstance(value, NumberToken):
        try:
            parsed = Decimal(value.token)
        except InvalidOperation as exc:
            raise R11ALimitError(f"{label} is not an exact decimal") from exc
        if not parsed.is_finite():
            raise R11ALimitError(f"{label} must be finite")
        return parsed
    if isinstance(value, int) and not isinstance(value, bool):
        return Decimal(value)
    raise R11ALimitError(f"{label} must be a JSON number")


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
    maximum_equality_group_spool_bytes: int = 268_435_456
    maximum_sort_chunk_bytes: int = 67_108_864

    @property
    def scientific_deadline_seconds(self) -> int:
        return (
            self.maximum_runtime_seconds
            - self.post_measurement_packaging_reservation_seconds
            - self.minimum_upload_window_seconds
        )

    def validate(self) -> None:
        if self.maximum_one_time_budget_eur_micros != 500_000:
            raise R11ALimitError("one-time budget must remain exactly EUR 0.50")
        if self.maximum_monthly_budget_eur_micros != 0:
            raise R11ALimitError("monthly budget must remain zero")
        if self.maximum_get_object_requests != 72:
            raise R11ALimitError("exact request count must remain 72")
        if self.maximum_requests_per_object != 1:
            raise R11ALimitError("each object may be requested once")
        if self.maximum_retries_per_request != 0:
            raise R11ALimitError("network retries are forbidden")
        if self.maximum_total_compressed_bytes != 2_107_738_436:
            raise R11ALimitError("total compressed byte cap drift")
        if self.maximum_individual_compressed_bytes != 76_616_104:
            raise R11ALimitError("individual compressed byte cap drift")
        if self.maximum_total_decompressed_bytes_across_two_passes != 21_079_958_490:
            raise R11ALimitError("two-pass decompressed processing cap drift")
        if self.maximum_ephemeral_workspace_bytes != 5_368_709_120:
            raise R11ALimitError("workspace cap must remain 5 GiB")
        if self.minimum_free_workspace_bytes_before_oidc != 6_442_450_944:
            raise R11ALimitError("pre-OIDC free-space threshold drift")
        if self.maximum_retained_artifact_bytes != 134_217_728:
            raise R11ALimitError("artifact cap must remain 128 MiB")
        if (
            self.reserved_non_scientific_package_metadata_bytes
            + self.maximum_retained_scientific_output_bytes
            > self.maximum_retained_artifact_bytes
        ):
            raise R11ALimitError("artifact reservations exceed the total artifact cap")
        if self.maximum_runtime_seconds != 21_600:
            raise R11ALimitError("runtime cap must remain six hours")
        if self.scientific_deadline_seconds <= 0:
            raise R11ALimitError("runtime must retain packaging and upload windows")
        if self.partition_count != 256:
            raise R11ALimitError("partition count must remain 256")
        if self.package_boundary_bytes != 1024:
            raise R11ALimitError("package boundary must remain 1024 bytes")
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
        return {field.name: int(getattr(self, field.name)) for field in dataclasses.fields(self)}


def _eur_micros(value: object, label: str) -> int:
    decimal_value = _as_decimal(value, label)
    micros = decimal_value * Decimal(1_000_000)
    if micros != micros.to_integral_value():
        raise R11ALimitError(f"{label} cannot be represented exactly in EUR micros")
    return int(micros)


def load_limits(path: Path = PREREGISTRATION_PATH) -> R11ALimits:
    prereg = _as_object(strict_json_loads(path.read_bytes()), "preregistration")
    proposed = _as_object(prereg["proposed_request_envelope"], "proposed_request_envelope")
    retention = _as_object(prereg["retention_and_privacy"], "retention_and_privacy")
    limits = R11ALimits(
        maximum_one_time_budget_eur_micros=_eur_micros(
            proposed["maximum_one_time_budget_eur"], "maximum_one_time_budget_eur"
        ),
        maximum_monthly_budget_eur_micros=_eur_micros(
            proposed["maximum_monthly_budget_eur"], "maximum_monthly_budget_eur"
        ),
        maximum_get_object_requests=_as_int(
            proposed["maximum_get_object_requests"], "maximum_get_object_requests"
        ),
        maximum_requests_per_object=_as_int(
            proposed["maximum_requests_per_object"], "maximum_requests_per_object"
        ),
        maximum_retries_per_request=_as_int(
            proposed["maximum_retries_per_request"], "maximum_retries_per_request"
        ),
        maximum_total_compressed_bytes=_as_int(
            proposed["maximum_total_compressed_bytes"], "maximum_total_compressed_bytes"
        ),
        maximum_individual_compressed_bytes=_as_int(
            proposed["maximum_individual_compressed_bytes"],
            "maximum_individual_compressed_bytes",
        ),
        maximum_total_decompressed_bytes_across_two_passes=_as_int(
            proposed["maximum_total_decompressed_bytes_processed_across_two_local_passes"],
            "maximum_total_decompressed_bytes_processed_across_two_local_passes",
        ),
        maximum_individual_decompressed_bytes_per_pass=_as_int(
            proposed["maximum_individual_decompressed_bytes_per_pass"],
            "maximum_individual_decompressed_bytes_per_pass",
        ),
        maximum_ephemeral_workspace_bytes=_as_int(
            proposed["maximum_ephemeral_workspace_bytes"],
            "maximum_ephemeral_workspace_bytes",
        ),
        minimum_free_workspace_bytes_before_oidc=_as_int(
            proposed["minimum_free_workspace_bytes_before_oidc"],
            "minimum_free_workspace_bytes_before_oidc",
        ),
        maximum_retained_artifact_bytes=_as_int(
            proposed["maximum_retained_artifact_bytes"], "maximum_retained_artifact_bytes"
        ),
        reserved_non_scientific_package_metadata_bytes=_as_int(
            proposed["reserved_non_scientific_package_metadata_bytes"],
            "reserved_non_scientific_package_metadata_bytes",
        ),
        maximum_retained_scientific_output_bytes=_as_int(
            proposed["maximum_retained_scientific_output_bytes"],
            "maximum_retained_scientific_output_bytes",
        ),
        maximum_runtime_seconds=_as_int(
            proposed["maximum_runtime_seconds"], "maximum_runtime_seconds"
        ),
        maximum_repeated_legacy_key_groups_retained=_as_int(
            retention["maximum_repeated_legacy_key_groups_retained"],
            "maximum_repeated_legacy_key_groups_retained",
        ),
        maximum_repeated_observations_retained=_as_int(
            retention["maximum_repeated_observations_retained"],
            "maximum_repeated_observations_retained",
        ),
        maximum_repeated_block_groups_retained=_as_int(
            retention["maximum_repeated_block_groups_retained"],
            "maximum_repeated_block_groups_retained",
        ),
    )
    limits.validate()
    return limits


DEFAULT_LIMITS: Final[R11ALimits] = load_limits()
