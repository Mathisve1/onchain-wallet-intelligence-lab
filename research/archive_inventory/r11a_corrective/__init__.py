"""Inert corrective R11A identity-boundary diagnostic implementation.

Nothing in this package self-authorizes network execution. Runtime entrypoints require
separately validated approval, role, preflight, release and activation overlays.
"""

from .canonical import NumberToken, canonical_json_bytes, deep_freeze, strict_json_loads

__all__ = [
    "NumberToken",
    "canonical_json_bytes",
    "deep_freeze",
    "strict_json_loads",
]
