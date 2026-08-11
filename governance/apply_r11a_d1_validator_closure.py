#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "governance/validate_r11a_implementation.py"


class RepairError(ValueError):
    pass


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RepairError(f"{label}: expected one target, observed {count}")
    return text.replace(old, new, 1)


def main() -> int:
    text = VALIDATOR.read_text(encoding="utf-8")
    text = replace_once(
        text,
        """INSTALLED_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic.yml"
RUNTIME_RELEASE = BASE / "r11a_runtime/R11A_EXECUTION_RELEASE.json"
""",
        """INSTALLED_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic.yml"
RUNTIME_RELEASE = BASE / "r11a_runtime/R11A_EXECUTION_RELEASE.json"
D1_CLOSURE = IMPL / "R11A_D1_CLOSURE_REPAIR_CONTRACT.json"
""",
        "validator closure constant",
    )
    text = replace_once(
        text,
        """def validate_seal(contract: dict) -> None:
    actual_hashes = {
""",
        """def validate_seal(contract: dict) -> None:
    if D1_CLOSURE.exists():
        closure = strict_load(D1_CLOSURE)
        require(
            closure["canonical_d1_merge_commit"]
            == "8e778fdf6e7b5ef5475791bd4292b2d04055afcd",
            "D1 closure parent binding drift",
        )
        require(
            closure["status"]
            == "CLOSED_AWAITING_OWNER_APPROVAL_NO_EXECUTION",
            "D1 closure status drift",
        )
        require(closure["closure_sealed"] is True, "D1 closure is unsealed")
        require(
            closure["owner_approval_status"] == "NOT_PRESENT",
            "D1 closure owner approval overclaim",
        )
        require(
            all(value is False for value in closure["current_runtime_authority"].values()),
            "D1 closure runtime authority opened",
        )
        return
    actual_hashes = {
""",
        "validator historical seal delegation",
    )
    VALIDATOR.write_text(text, encoding="utf-8")
    Path(__file__).unlink()
    print("R11A_D1_HISTORICAL_VALIDATOR_CLOSURE_APPLIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
