from __future__ import annotations

from .storage_r7 import WorkspaceMeter


class R7WorkspaceMeter(WorkspaceMeter):
    """Compatibility name for the canonical R7 workspace meter.

    Exact shared-directory category accounting now lives on ``WorkspaceMeter``
    itself because the production runner constructs that class directly.
    """

    pass
