#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "research/archive_inventory/r11a_v2/R11A_V2_PREREGISTRATION_BINDINGS.json"
FILES = (
    "research/archive_inventory/r11a_v2/R11A_CORRECTIVE_PREREGISTRATION_AMENDMENT.json",
    "research/archive_inventory/r11a_v2/R11A_CORRECTIVE_PREREGISTRATION_AMENDMENT.md",
    "research/archive_inventory/r11a_v2/R11A_V2_STATUS.json",
    "research/archive_inventory/r11a_v2/README.md",
    "governance/R11A_V2_REVIEW_FINDINGS.md",
    "governance/validate_r11a_v2_preregistration.py",
    "governance/validate_r11a_v2_bindings.py",
    "tests/test_archive_inventory_r11a_v2_preregistration.py",
    "tests/test_archive_inventory_r11a_v2_bindings.py",
)
EXTERNAL_BINDINGS = {
    "canonical_parent_commit": "57566456624eb758049aa7687bdb7b8a2844c91d",
    "original_preregistration_merge_commit": "5103c846be8a53732d8559a281ac8b57ce4d7aac",
    "original_inert_implementation_merge_commit": "8e778fdf6e7b5ef5475791bd4292b2d04055afcd",
    "failed_closure_attempt_merge_commit": "4bb3eaf4cbcfea7771261ade73d618912496585a",
    "containment_merge_commit": "57566456624eb758049aa7687bdb7b8a2844c91d",
    "selection_sha256": "7c134f4b62f547904126a5f810c177484dceeffa246d53c5c35944367d563eb2",
    "prior_result_sha256": "9d3266eb53791d83df29b6ec3ae5f33c254b29a8182f2e6be7e3261c02686862",
    "original_r11_artifact_sha256": "45ee57df7a63561bef1772d8612d5fe32b06b9c407d9c1464ce0a02b65a15cc5",
}


class SealError(ValueError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected() -> dict[str, object]:
    missing = [path for path in FILES if not (ROOT / path).is_file()]
    if missing:
        raise SealError(f"missing sealed files: {missing}")
    return {
        "schema_version": "1.0",
        "binding_id": "R11A-V2-PREREGISTRATION-BINDINGS-001",
        "status": "SEALED_PREREGISTRATION_NO_EXECUTION",
        "diagnostic_id": "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-002",
        "file_sha256": {path: sha256(ROOT / path) for path in FILES},
        "external_bindings": EXTERNAL_BINDINGS,
        "owner_approval_eligible": False,
        "network_execution_authorized": False,
        "r11_closed": False,
        "r12_ready": False,
        "empirical_result": None,
    }


def render() -> str:
    return json.dumps(expected(), indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = render()
    if args.write:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(rendered, encoding="utf-8")
        print("R11A_V2_PREREGISTRATION_BINDINGS_WRITTEN")
        return 0
    if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != rendered:
        raise SealError("R11A V2 preregistration binding seal is stale")
    print("R11A_V2_PREREGISTRATION_BINDINGS_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
