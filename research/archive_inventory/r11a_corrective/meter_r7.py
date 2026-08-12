from __future__ import annotations

from .storage_r7 import Reservation, StorageBoundaryError, WorkspaceMeter


class R7WorkspaceMeter(WorkspaceMeter):
    """Adds exact category-byte accounting for multi-file reserved containers.

    Category reservations account only the bytes owned by that category, avoiding
    double counting when multiple categories share one artifact staging directory.
    Final `verify_actual_usage()` still compares the sum to the actual workspace.
    """

    def checkpoint_value(
        self,
        reservation: Reservation,
        actual_bytes: int,
        *,
        packaging: bool,
        phase: str,
    ) -> int:
        self._check_runtime(packaging, f"{phase} before checkpoint")
        state = self._reservations.get(reservation.reservation_id)
        if state is None or state.token != reservation:
            raise StorageBoundaryError("unknown category reservation")
        if type(actual_bytes) is not int or not 0 <= actual_bytes <= reservation.maximum_bytes:
            raise StorageBoundaryError("category bytes exceed reservation")
        self._known_bytes += actual_bytes - state.accounted_bytes
        state.accounted_bytes = actual_bytes
        if self._known_bytes < 0:
            raise StorageBoundaryError("workspace accounting became negative")
        if self._known_bytes + self.reserved_bytes > self.limits.maximum_ephemeral_workspace_bytes:
            raise StorageBoundaryError("workspace cap exceeded after category mutation")
        self._check_runtime(packaging, f"{phase} after checkpoint")
        return actual_bytes

    def finalize_value(
        self,
        reservation: Reservation,
        actual_bytes: int,
        *,
        packaging: bool,
        phase: str,
    ) -> int:
        observed = self.checkpoint_value(
            reservation,
            actual_bytes,
            packaging=packaging,
            phase=phase,
        )
        state = self._reservations.pop(reservation.reservation_id, None)
        if state is None or state.token != reservation or state.accounted_bytes != observed:
            raise StorageBoundaryError("category reservation finalization drift")
        return observed

    def release_value(
        self,
        reservation: Reservation,
        *,
        packaging: bool,
        phase: str,
    ) -> None:
        self._check_runtime(packaging, f"{phase} before release")
        state = self._reservations.pop(reservation.reservation_id, None)
        if state is None or state.token != reservation:
            raise StorageBoundaryError("unknown category reservation release")
        self._known_bytes -= state.accounted_bytes
        if self._known_bytes < 0:
            raise StorageBoundaryError("workspace accounting became negative after category release")
        self._check_runtime(packaging, f"{phase} after release")
