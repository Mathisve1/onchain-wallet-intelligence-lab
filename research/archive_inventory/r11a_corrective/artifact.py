from __future__ import annotations

from . import _artifact_contract_core_r7 as _core
from .artifact_schema import SCIENCE_CONTAINERS

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
