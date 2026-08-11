#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "research/archive_inventory/r11a_corrective_core/R11A_CORRECTIVE_CORE_CONTRACT.json"
SEALED_PATHS = (
    "research/archive_inventory/r11a_corrective_core/__init__.py",
    "research/archive_inventory/r11a_corrective_core/canonical.py",
    "research/archive_inventory/r11a_corrective_core/model.py",
    "research/archive_inventory/r11a_corrective_core/taxonomy_types.py",
    "research/archive_inventory/r11a_corrective_core/taxonomy_logic.py",
    "research/archive_inventory/r11a_corrective_core/taxonomy.py",
    "research/archive_inventory/r11a_corrective_core/storage.py",
    "research/archive_inventory/r11a_corrective_core/output.py",
    "research/archive_inventory/r11a_corrective_core/RED_REVIEW_ACCEPTANCE.md",
    "governance/seal_r11a_corrective_core.py",
    "governance/validate_r11a_corrective_core.py",
    "tests/test_r11a_corrective_core.py",
)


def render() -> str:
    value = json.loads(CONTRACT.read_text(encoding="utf-8"))
    value["file_sha256"] = {
        relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        for relative in SEALED_PATHS
    }
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render()
    if args.write:
        CONTRACT.write_text(expected, encoding="utf-8")
    if args.check or not args.write:
        if CONTRACT.read_text(encoding="utf-8") != expected:
            raise SystemExit("R11A_CORRECTIVE_CORE_SEAL_STALE")
    print("R11A_CORRECTIVE_CORE_SEAL_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
