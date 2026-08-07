from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FeatureObservation:
    name: str
    first_seen_at_ms: int
    value: object


def eligible_features(observations: list[FeatureObservation], selection_timestamp_ms: int) -> list[FeatureObservation]:
    """Return only features available at or before the decision timestamp."""
    return [row for row in observations if row.first_seen_at_ms <= selection_timestamp_ms]
