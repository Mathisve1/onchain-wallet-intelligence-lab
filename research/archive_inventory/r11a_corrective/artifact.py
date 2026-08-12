from __future__ import annotations

from . import _artifact_contract_core_r7 as _core
from .artifact_schema import SCIENCE_CONTAINERS
from .canonical import FrozenObject, NumberToken, strict_json_loads as _strict_json_loads


def _normalize_artifact_integers(value: object) -> object:
    """Normalize strict-decoded integer tokens for artifact arithmetic only.

    Artifact bytes are first parsed by the strict lossless decoder. Once that
    boundary has rejected duplicate keys, invalid UTF-8, non-finite constants,
    and noncanonical number tokens, validators may safely perform exact integer
    arithmetic over Python ints. Non-integer number tokens remain untouched.
    """

    if isinstance(value, NumberToken):
        return int(value.token, 10) if value.is_integer_token else value
    if isinstance(value, FrozenObject):
        return FrozenObject(
            tuple(
                (key, _normalize_artifact_integers(child))
                for key, child in value.items_tuple
            )
        )
    if isinstance(value, tuple):
        return tuple(_normalize_artifact_integers(child) for child in value)
    return value


def _artifact_json_loads(raw: bytes) -> object:
    return _normalize_artifact_integers(_strict_json_loads(raw))


# The contract core performs arithmetic over strict-decoded artifact metadata.
# Bind its parser to the exact-integer normalization above without weakening the
# source JSON boundary or changing scientific payload serialization.
_core.strict_json_loads = _artifact_json_loads

ArtifactBoundaryError = _core.ArtifactBoundaryError
ArtifactOutcome = _core.ArtifactOutcome
FileEvidence = _core.FileEvidence
ScientificCapExceeded = _core.ScientificCapExceeded
SharedMetadataWriter = _core.SharedMetadataWriter
StreamingScientificEmitter = _core.StreamingScientificEmitter
complete_reducer_rows = _core.complete_reducer_rows
validate_artifact = _core.validate_artifact
_reducer_summary = _core._reducer_summary


class ArtifactSession(_core.ArtifactSession):
    """R7 session with recoverable, meter-correct full-to-empty fallback."""

    def _discard_science_and_create_empty(self) -> tuple[FileEvidence, ...]:
        self.emitter.abort()
        for name in SCIENCE_CONTAINERS:
            path = self.staging / name
            if path.exists():
                self.meter.delete_file(path)
            if path.exists():
                raise ArtifactBoundaryError(
                    "closed scientific output could not be discarded"
                )
        replacement = StreamingScientificEmitter(
            self.staging,
            self.meter,
            self.limits,
        )
        self.emitter = replacement
        return replacement.close()


__all__ = [
    "ArtifactBoundaryError",
    "ArtifactOutcome",
    "ArtifactSession",
    "FileEvidence",
    "ScientificCapExceeded",
    "SharedMetadataWriter",
    "StreamingScientificEmitter",
    "complete_reducer_rows",
    "validate_artifact",
]
