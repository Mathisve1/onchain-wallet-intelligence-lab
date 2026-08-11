#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "governance/validate_r11a_v2_preregistration.py"


def main() -> int:
    text = VALIDATOR.read_text(encoding="utf-8")
    old = 'require(len(required_values) == len(set(required_values)) == 10, "pre-approval hash binding list drift")'
    new = 'require(len(required_values) == len(set(required_values)) == 11, "pre-approval hash binding list drift")'
    if text.count(old) != 1:
        raise SystemExit("R11A_V2_PREREG_SEAL_FIX_TARGET_DRIFT")
    VALIDATOR.write_text(text.replace(old, new, 1), encoding="utf-8")
    Path(__file__).unlink()
    print("R11A_V2_PREREG_SEAL_FIX_APPLIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
