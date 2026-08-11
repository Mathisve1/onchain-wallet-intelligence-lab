#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r11a_implementation"
CONTRACT = BASE / "R11A_D1_CLOSURE_REPAIR_CONTRACT.json"
STATUS = BASE / "R11A_D1_CLOSURE_STATUS.json"
WORKFLOW = BASE / "workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic-r2.yml"

SEALED_PATHS = (
    "research/archive_inventory/r11a_implementation/collector.py",
    "research/archive_inventory/r11a_implementation/runtime.py",
    "research/archive_inventory/r11a_implementation/failure.py",
    "research/archive_inventory/r11a_implementation/network.py",
    "research/archive_inventory/r11a_implementation/runner.py",
    "research/archive_inventory/r11a_implementation/entrypoint.py",
    "research/archive_inventory/r11a_implementation/storage.py",
    "research/archive_inventory/r11a_implementation/schema.py",
    "research/archive_inventory/r11a_implementation/limits.py",
    "research/archive_inventory/r11a_implementation/identity.py",
    "research/archive_inventory/r11a_implementation/diagnostic.py",
    "research/archive_inventory/r11a_implementation/R11A_D1_CLOSURE_STATUS.json",
    "research/archive_inventory/r11a_implementation/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic-r2.yml",
    "governance/seal_r11a_d1_closure.py",
    "governance/validate_r11a_d1_closure.py",
    "tests/test_archive_inventory_r11a_runtime_failure.py",
    "tests/test_archive_inventory_r11a_network.py",
)


class SealError(ValueError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SealError(f"JSON root must be object: {path}")
    return value


def status_text() -> str:
    value = load(STATUS)
    value["status"] = "CLOSURE_REPAIRED_AWAITING_OWNER_APPROVAL_NO_EXECUTION"
    value["owner_approval_eligible"] = True
    value["execution_release_eligible"] = False
    value["workflow_installation_eligible"] = False
    value["known_blockers"] = []
    value["repair_pr"] = 142
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def expected_hashes() -> dict[str, str]:
    output: dict[str, str] = {}
    for relative in SEALED_PATHS:
        path = ROOT / relative
        if not path.is_file():
            raise SealError(f"required closure path absent: {relative}")
        output[relative] = sha256(path)
    return output


def sealed_contract_text() -> str:
    value = load(CONTRACT)
    value["status"] = "CLOSED_AWAITING_OWNER_APPROVAL_NO_EXECUTION"
    value["closure_sealed"] = True
    value["review_blockers"] = {
        "minimal_failure_artifact_for_precollector_and_runtime_failures": True,
        "runtime_and_workspace_guards_at_mutating_boundaries": True,
        "prematerialization_scientific_cap_gate": True,
        "complete_object_reducer_stop_and_resource_ledgers": True,
        "response_content_length_metadata_bound_before_body_acceptance": True,
    }
    value["repaired_workflow_candidate_git_blob_sha"] = git_blob_sha(WORKFLOW)
    value["closure_file_hashes"] = expected_hashes()
    value["owner_approval_eligible"] = True
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.write:
        STATUS.write_text(status_text(), encoding="utf-8")
        CONTRACT.write_text(sealed_contract_text(), encoding="utf-8")
        print("R11A_D1_CLOSURE_SEAL_WRITTEN")
        return 0
    expected_status = status_text()
    expected_contract = sealed_contract_text()
    if args.check:
        if STATUS.read_text(encoding="utf-8") != expected_status:
            print("R11A_D1_CLOSURE_STATUS_OUT_OF_DATE")
            return 1
        if CONTRACT.read_text(encoding="utf-8") != expected_contract:
            print("R11A_D1_CLOSURE_CONTRACT_OUT_OF_DATE")
            return 1
        print("R11A_D1_CLOSURE_SEAL_VALID")
        return 0
    print(expected_contract, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
