from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping


class R11ALimitError(ValueError):
    """Raised when a frozen R11A resource limit is invalid or exceeded."""


@dataclass(frozen=True, slots=True)
class R11ALimits:
    maximum_one_time_budget_eur_micros: int = 500_000
    maximum_monthly_budget_eur_micros: int = 0
    maximum_get_object_requests: int = 72
    maximum_requests_per_object: int = 1
    maximum_retries_per_request: int = 0
    maximum_total_compressed_bytes: int = 2_107_738_436
    maximum_individual_compressed_bytes: int = 76_616_104
    maximum_total_decompressed_bytes_across_two_passes: int = 21_079_958_490
    maximum_individual_decompressed_bytes_per_pass: int = 536_870_912
    maximum_ephemeral_workspace_bytes: int = 5_368_709_120
    minimum_free_workspace_bytes_before_oidc: int = 6_442_450_944
    maximum_retained_artifact_bytes: int = 134_217_728
    reserved_non_scientific_package_metadata_bytes: int = 4_194_304
    maximum_retained_scientific_output_bytes: int = 134_217_728
    maximum_runtime_seconds: int = 21_600
    post_measurement_packaging_reservation_seconds: int = 300
    minimum_upload_window_seconds: int = 60
    maximum_repeated_legacy_key_groups_retained: int = 100_000
    maximum_repeated_observations_retained: int = 250_000
    maximum_repeated_block_groups_retained: int = 100_000
    partition_count: int = 256
    external_sort_memory_bytes: int = 67_108_864
    package_boundary_bytes: int = 1024

    def validate(self) -> None:
        for key, value in asdict(self).items():
            if type(value) is not int or value < 0:
                raise R11ALimitError(f"{key} must be a nonnegative integer")
        if self.maximum_get_object_requests != 72:
            raise R11ALimitError("R11A exact request count must remain 72")
        if self.maximum_requests_per_object != 1:
            raise R11ALimitError("R11A permits exactly one request per object")
        if self.maximum_retries_per_request != 0:
            raise R11ALimitError("R11A retries must remain zero")
        if self.partition_count != 256:
            raise R11ALimitError("R11A partition count must remain 256")
        if self.maximum_retained_scientific_output_bytes != self.maximum_retained_artifact_bytes:
            raise R11ALimitError("scientific cap may not be stricter than artifact cap")
        if self.reserved_non_scientific_package_metadata_bytes >= self.maximum_retained_artifact_bytes:
            raise R11ALimitError("metadata reservation must remain below artifact cap")
        if self.minimum_free_workspace_bytes_before_oidc < self.maximum_ephemeral_workspace_bytes:
            raise R11ALimitError("pre-OIDC free-space threshold must cover workspace cap")
        if self.post_measurement_packaging_reservation_seconds + self.minimum_upload_window_seconds >= self.maximum_runtime_seconds:
            raise R11ALimitError("runtime must leave packaging and upload windows")

    def as_contract_mapping(self) -> dict[str, int]:
        self.validate()
        return asdict(self)

    def require_not_exceeded(self, observed: Mapping[str, int]) -> None:
        self.validate()
        comparators = {
            "get_object_requests": (self.maximum_get_object_requests, False),
            "retries": (self.maximum_retries_per_request, False),
            "total_compressed_bytes": (self.maximum_total_compressed_bytes, False),
            "individual_compressed_bytes": (self.maximum_individual_compressed_bytes, False),
            "total_decompressed_bytes_across_two_passes": (self.maximum_total_decompressed_bytes_across_two_passes, False),
            "individual_decompressed_bytes_per_pass": (self.maximum_individual_decompressed_bytes_per_pass, False),
            "peak_ephemeral_workspace_bytes": (self.maximum_ephemeral_workspace_bytes, False),
            "retained_artifact_bytes": (self.maximum_retained_artifact_bytes, False),
            "elapsed_runtime_seconds": (self.maximum_runtime_seconds, True),
            "one_time_budget_eur_micros": (self.maximum_one_time_budget_eur_micros, False),
            "monthly_budget_eur_micros": (self.maximum_monthly_budget_eur_micros, False),
        }
        unknown = set(observed) - set(comparators)
        if unknown:
            raise R11ALimitError(f"unknown observed cap keys: {sorted(unknown)}")
        for key, value in observed.items():
            if type(value) is not int or value < 0:
                raise R11ALimitError(f"observed {key} must be nonnegative integer")
            limit, inclusive = comparators[key]
            if value >= limit if inclusive else value > limit:
                relation = ">=" if inclusive else ">"
                raise R11ALimitError(f"{key} cap exceeded: {value} {relation} {limit}")


DEFAULT_LIMITS = R11ALimits()
DEFAULT_LIMITS.validate()
R11A_LIMITS_ARE_INSTANCE_SCOPED = True
