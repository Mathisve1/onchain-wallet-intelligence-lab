#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "research/archive_inventory/r11a_implementation/R11A_IMPLEMENTATION_CONTRACT.json"
WORKFLOW = ROOT / "research/archive_inventory/r11a_implementation/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic.yml"

SEALED_PATHS = (
    "research/archive_inventory/r11a_implementation/__init__.py",
    "research/archive_inventory/r11a_implementation/activity.py",
    "research/archive_inventory/r11a_implementation/collector.py",
    "research/archive_inventory/r11a_implementation/diagnostic.py",
    "research/archive_inventory/r11a_implementation/identity.py",
    "research/archive_inventory/r11a_implementation/limits.py",
    "research/archive_inventory/r11a_implementation/schema.py",
    "research/archive_inventory/r11a_implementation/storage.py",
    "research/archive_inventory/r11a_implementation/README.md",
    "research/archive_inventory/r11a_implementation/R11A_DEPENDENCIES.json",
    "research/archive_inventory/r11a_implementation/R11A_OIDC_TRUST_POLICY.json",
    "research/archive_inventory/r11a_implementation/R11A_PERMISSION_POLICY.json",
    "research/archive_inventory/r11a_implementation/R11A_RESOURCE_FEASIBILITY.json",
    "research/archive_inventory/r11a_implementation/R11A_RESOURCE_FEASIBILITY.md",
    "research/archive_inventory/r11a_implementation/R11A_ROLE_DECISION.json",
    "research/archive_inventory/r11a_implementation/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic.yml",
    "governance/validate_r11a_implementation.py",
)


class SealError(ValueError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def expected_hashes() -> dict[str, str]:
    values: dict[str, str] = {}
    for relative in SEALED_PATHS:
        path = ROOT / relative
        if not path.is_file():
            raise SealError(f"required R11A implementation file absent: {relative}")
        values[relative] = sha256(path)
    return values


def load_contract() -> dict:
    value = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SealError("R11A implementation contract root must be object")
    return value


def render_sealed() -> str:
    contract = load_contract()
    contract["implementation_sealed"] = True
    contract["implementation_file_hashes"] = expected_hashes()
    contract["workflow_candidate_git_blob_sha"] = git_blob_sha(WORKFLOW)
    return json.dumps(contract, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render_sealed()
    if args.write:
        CONTRACT.write_text(expected, encoding="utf-8")
        print("R11A_IMPLEMENTATION_SEAL_WRITTEN")
        return 0
    if args.check:
        observed = CONTRACT.read_text(encoding="utf-8")
        if observed != expected:
            print("R11A_IMPLEMENTATION_SEAL_OUT_OF_DATE")
            return 1
        print("R11A_IMPLEMENTATION_SEAL_VALID")
        return 0
    print(expected, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
