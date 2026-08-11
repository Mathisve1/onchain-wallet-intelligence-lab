#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r11a_corrective_core"
CONTRACT = BASE / "R11A_CORRECTIVE_CORE_CONTRACT.json"
OLD_IMPLEMENTATION = ROOT / "research/archive_inventory/r11a_implementation/R11A_IMPLEMENTATION_CONTRACT.json"
INSTALLED_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic.yml"
APPROVAL_ROOT = ROOT / "research/archive_inventory/r11a_approval"
RUNTIME_RELEASE = ROOT / "research/archive_inventory/r11a_runtime/R11A_EXECUTION_RELEASE.json"


class ValidationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def strict_load(path: Path) -> dict[str, object]:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise ValidationError(f"duplicate JSON key in {path}: {key}")
            result[key] = value
        return result

    def reject(token: str) -> object:
        raise ValidationError(f"non-finite constant in {path}: {token}")

    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=reject)
    require(isinstance(value, dict), f"top-level object required: {path}")
    return value


def main() -> int:
    contract = strict_load(CONTRACT)
    require(contract["implementation_id"] == "HL-ARCHIVE-R11A-CORRECTIVE-CORE-002", "implementation ID drift")
    require(contract["status"] == "CORRECTIVE_CORE_IMPLEMENTED_AWAITING_RUNTIME_AND_WORKFLOW_STAGE_NO_EXECUTION", "status drift")
    require(contract["canonical_parent_main_commit"] == "57566456624eb758049aa7687bdb7b8a2844c91d", "parent commit drift")
    require(contract["canonical_parent_tree"] == "e2221890e43a2a56d9854010957785e20594d25d", "parent tree drift")
    require(contract["independent_review_verdict"] == "RED", "review verdict overclaim")
    require(contract["historical_pr141_remains_immutable"] is True, "PR141 historical snapshot rewritten")
    require(contract["failed_pr142_quarantined_by_pr143"] is True, "PR142 containment missing")
    require(contract["owner_approval_eligible"] is False, "owner approval opened")
    require(contract["execution_release_eligible"] is False, "execution release opened")
    require(contract["workflow_installation_eligible"] is False, "workflow installation opened")
    require(all(value is False for value in contract["current_runtime_authority"].values()), "runtime authority opened")
    require(contract["network_requests_executed"] == 0, "network execution overclaim")
    require(contract["aws_iam_mutations_executed"] == 0, "IAM mutation overclaim")
    require(contract["diagnostic_rows_created"] == 0, "diagnostic result overclaim")
    require(contract["wallet_feature_rows_created"] == 0, "wallet feature overclaim")
    require(contract["r11_closed"] is False and contract["r12_ready"] is False, "lifecycle overclaim")
    require(contract["empirical_result"] is None, "empirical result created")
    expected_fixes = {
        "decimal_normalizer_without_quantize",
        "canonical_utf8_mapping_key_sort",
        "deep_immutable_payload_snapshots",
        "group_wide_repeat_classification",
        "per_unit_universe_unclassifiable_counts",
        "computed_proof_foreign_key_resolution",
        "exact_scope_and_conservation_terminal_predicate",
        "order_independent_external_sort_multiset_commitment",
        "bounded_group_spooling",
        "prewrite_workspace_reservation",
        "checked_cleanup",
        "post_rename_failure_removes_final_artifact",
        "streaming_ndjson_writer",
        "minimal_failure_artifact_with_zero_science",
        "package_boundary_boolean_recomputation",
    }
    fixes = contract["implemented_review_fixes"]
    require(set(fixes) == expected_fixes, "implemented fix set drift")
    require(all(value is True for value in fixes.values()), "implemented fix marked false")
    hashes = contract["file_sha256"]
    require(isinstance(hashes, dict) and hashes, "file hash map missing")
    for relative, expected in hashes.items():
        path = ROOT / relative
        require(path.is_file(), f"sealed file missing: {relative}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        require(actual == expected, f"sealed file drift: {relative}")
    old = strict_load(OLD_IMPLEMENTATION)
    require(old["status"] == "IMPLEMENTED_AWAITING_OWNER_APPROVAL_NO_EXECUTION", "historical PR141 snapshot unexpectedly changed")
    require(old["owner_approval_status"] == "NOT_PRESENT", "historical approval overclaim")
    require(not INSTALLED_WORKFLOW.exists(), "R11A workflow installed during corrective core stage")
    require(not APPROVAL_ROOT.exists(), "R11A owner approval exists during corrective core stage")
    require(not RUNTIME_RELEASE.exists(), "R11A runtime release exists during corrective core stage")
    print("R11A_CORRECTIVE_CORE_VALID_INERT_NO_EXECUTION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
