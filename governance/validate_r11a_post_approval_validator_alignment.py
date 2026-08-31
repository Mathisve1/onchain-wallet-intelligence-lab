#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).absolute().parents[1]))

import difflib as _r11a_bytecode_boundary  # noqa: E402,F401

from governance.r11a_post_approval_context import (
    PostApprovalContextError,
    ROOT,
    validate_alignment,
)


def main() -> int:
    validate_alignment(ROOT)
    print("R11A_POST_APPROVAL_VALIDATOR_ALIGNMENT_VALID_INERT_NO_AWS")
    return 0


__all__ = ["PostApprovalContextError", "ROOT", "main", "validate_alignment"]


if __name__ == "__main__":
    raise SystemExit(main())
