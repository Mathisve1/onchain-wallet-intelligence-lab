#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from governance.regenerate_manifest import render_manifest
except ModuleNotFoundError:  # direct ``python governance/...`` execution
    from regenerate_manifest import render_manifest

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "research/archive_inventory"
CORRECTIVE = ARCHIVE / "r11a_corrective"
CONTRACT = CORRECTIVE / "R11A_CORRECTIVE_IMPLEMENTATION_CONTRACT_R7.json"
STATUS = CORRECTIVE / "R11A_CORRECTIVE_STATUS_R7.json"

IMPLEMENTATION_ID = "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-CORRECTIVE-R7"
DIAGNOSTIC_ID = "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-002"
ZERO_SHA256 = "0" * 64
SEALED_AMENDMENT = (
    "research/archive_inventory/r11a_v2/"
    "R11A_CORRECTIVE_PREREGISTRATION_AMENDMENT.json"
)
SEALED_AMENDMENT_ID = "R11A-CORRECTIVE-PREREGISTRATION-AMENDMENT-002"
SEALED_AMENDMENT_SHA256 = (
    "bdd610c678189e8098381d8c4a0fd12296bf2e0cd8e9ec0fed375b073872552f"
)
V2_BINDINGS = (
    "research/archive_inventory/r11a_v2/"
    "R11A_V2_PREREGISTRATION_BINDINGS.json"
)
CANDIDATE_WORKFLOW = (
    "research/archive_inventory/r11a_corrective/workflows/"
    "hyperliquid-archive-r11a-identity-boundary-diagnostic-r7.yml"
)
DEVELOPMENT_WORKFLOW = ".github/workflows/r11a-r7-dev.yml"
REPOSITORY_MANIFEST = "governance/REPOSITORY_MANIFEST.sha256"

R7_CODE_PATHS = (
    "research/__init__.py",
    "research/archive_inventory/r11a_corrective/__init__.py",
    "research/archive_inventory/r11a_corrective/_artifact_contract_core_r7.py",
    "research/archive_inventory/r11a_corrective/_artifact_core_r7.py",
    "research/archive_inventory/r11a_corrective/_artifact_schema_core_r7.py",
    "research/archive_inventory/r11a_corrective/_runner_core_r7.py",
    "research/archive_inventory/r11a_corrective/_taxonomy_contract_core_r7.py",
    "research/archive_inventory/r11a_corrective/_taxonomy_core_r7.py",
    "research/archive_inventory/r11a_corrective/activity.py",
    "research/archive_inventory/r11a_corrective/artifact.py",
    "research/archive_inventory/r11a_corrective/artifact_schema.py",
    "research/archive_inventory/r11a_corrective/canonical.py",
    "research/archive_inventory/r11a_corrective/context.py",
    "research/archive_inventory/r11a_corrective/entrypoint.py",
    "research/archive_inventory/r11a_corrective/identity.py",
    "research/archive_inventory/r11a_corrective/index.py",
    "research/archive_inventory/r11a_corrective/join_r7.py",
    "research/archive_inventory/r11a_corrective/limits.py",
    "research/archive_inventory/r11a_corrective/locator_order.py",
    "research/archive_inventory/r11a_corrective/lz4stream.py",
    "research/archive_inventory/r11a_corrective/materialize.py",
    "research/archive_inventory/r11a_corrective/meter_r7.py",
    "research/archive_inventory/r11a_corrective/network.py",
    "research/archive_inventory/r11a_corrective/parser.py",
    "research/archive_inventory/r11a_corrective/preflight_artifact_r7.py",
    "research/archive_inventory/r11a_corrective/pricing.py",
    "research/archive_inventory/r11a_corrective/proof_semantics_r7.py",
    "research/archive_inventory/r11a_corrective/runner.py",
    "research/archive_inventory/r11a_corrective/runtime.py",
    "research/archive_inventory/r11a_corrective/selection.py",
    "research/archive_inventory/r11a_corrective/storage_r7.py",
    "research/archive_inventory/r11a_corrective/taxonomy.py",
    "research/archive_inventory/r11a_corrective/taxonomy_precedence_r7.py",
    "research/archive_inventory/r11a_corrective/terminal_propagation.py",
    CANDIDATE_WORKFLOW,
)

GOVERNANCE_PATHS = (
    "governance/_validate_r11a_runtime_binding_core_r7.py",
    "governance/generate_r11a_corrective_policies.py",
    "governance/r11a_post_approval_context.py",
    "governance/r11a_stage_common_r4.py",
    "governance/regenerate_manifest.py",
    "governance/run_r11a_network_deny.py",
    "governance/seal_r11a_corrective_r7.py",
    "governance/seal_r11a_v2_preregistration.py",
    "governance/validate_r11a_activation_r4.py",
    "governance/validate_r11a_approval_r4.py",
    "governance/validate_r11a_execution_artifact_r7.py",
    "governance/validate_r11a_execution_release_r4.py",
    "governance/validate_r11a_g2_owner_approval.py",
    "governance/validate_r11a_post_approval_validator_alignment.py",
    "governance/validate_repository.py",
    "governance/validate_r11a_role_attestation_r4.py",
    "governance/validate_r11a_role_preflight_evidence_r4.py",
    "governance/validate_r11a_runtime_binding_r7.py",
    "governance/validate_r11a_v2_bindings.py",
    "governance/validate_r11a_v2_preregistration.py",
    "governance/validate_r11a_workflow_installation_r4.py",
)

SUPPORTING_PATHS = (
    ".gitattributes",
    DEVELOPMENT_WORKFLOW,
    "DECISION_LOG.md",
    "PROJECT_STATE.md",
    "README.md",
    "ROADMAP.md",
    "research/archive_inventory/r11/R11_72H_SELECTION.json",
    "research/archive_inventory/r11_evidence/run-31436753081/r11-result.json",
    "research/archive_inventory/r11a/R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_PREREGISTRATION.json",
    "research/archive_inventory/r11a_alignment/R11A_POST_APPROVAL_VALIDATOR_ALIGNMENT.json",
    "research/archive_inventory/r11a_approval/APPROVE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001.json",
    "research/archive_inventory/r11a_approval/APPROVE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001.txt",
    "research/archive_inventory/r11a_corrective/README.md",
    "research/archive_inventory/r11a_corrective/R11A_DEPENDENCIES.json",
    "research/archive_inventory/r11a_corrective/R11A_OIDC_TRUST_POLICY.json",
    "research/archive_inventory/r11a_corrective/R11A_PERMISSION_POLICY.json",
    "research/archive_inventory/r11a_corrective/R11A_PRICING_EUR_SNAPSHOT.json",
    "research/archive_inventory/r11a_corrective/R11A_RED_REVIEW_FINDINGS.json",
    "research/archive_inventory/r11a_corrective/R11A_RESOURCE_FEASIBILITY_R3.json",
    "research/archive_inventory/r11a_corrective/R11A_ROLE_DECISION.json",
    "research/archive_inventory/r11a_g1/R11A_G1_EXECUTION_ENVELOPE.json",
    "research/archive_inventory/r11a_g1/R11A_G1_OWNER_APPROVAL_PACKAGE.json",
    "research/archive_inventory/r11a_g1/R11A_G1_OWNER_APPROVAL_STATEMENT.txt",
    "research/archive_inventory/r11a_g1/R11A_G1_PRICING_EUR_BINDING.json",
    "research/archive_inventory/r11a_g1/R11A_G1_RUNTIME_PRICING_SNAPSHOT_CANDIDATE.json",
    "research/archive_inventory/r11a_g1/R11A_G1_STATUS.json",
    SEALED_AMENDMENT,
    "research/archive_inventory/r11a_v2/R11A_CORRECTIVE_PREREGISTRATION_AMENDMENT.md",
    V2_BINDINGS,
    "research/archive_inventory/r11a_v2/R11A_V2_STATUS.json",
    "research/archive_inventory/r11a_v2/README.md",
    "governance/R11A_V2_REVIEW_FINDINGS.md",
)

TEST_PATHS = (
    "tests/test_archive_inventory_r11a_corrective_artifacts.py",
    "tests/test_archive_inventory_r11a_corrective_r3.py",
    "tests/test_archive_inventory_r11a_corrective_r7.py",
    "tests/test_archive_inventory_r11a_corrective_r7_precedence.py",
    "tests/test_archive_inventory_r11a_g2_owner_approval.py",
    "tests/test_archive_inventory_r11a_post_approval_validator_alignment.py",
    "tests/test_archive_inventory_r11a_v2_bindings.py",
    "tests/test_archive_inventory_r11a_v2_preregistration.py",
)

EXECUTED_SECURITY_PATHS = frozenset(
    R7_CODE_PATHS
    + GOVERNANCE_PATHS
    + (
        DEVELOPMENT_WORKFLOW,
        SEALED_AMENDMENT,
        V2_BINDINGS,
        "research/archive_inventory/r11/R11_72H_SELECTION.json",
        "research/archive_inventory/r11a_corrective/R11A_OIDC_TRUST_POLICY.json",
        "research/archive_inventory/r11a_corrective/R11A_PERMISSION_POLICY.json",
    )
)


class SealError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SealError(message)


def sha256(relative: str) -> str:
    path = ROOT / relative
    require(path.is_file(), f"sealed input is absent: {relative}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict_load(relative: str) -> dict[str, Any]:
    path = ROOT / relative

    def pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in rows:
            require(key not in result, f"duplicate JSON key in {relative}: {key}")
            result[key] = value
        return result

    def constant(token: str) -> Any:
        raise SealError(f"non-finite JSON constant in {relative}: {token}")

    try:
        value = json.loads(
            path.read_bytes().decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SealError(f"invalid strict JSON: {relative}") from exc
    require(isinstance(value, dict), f"JSON root is not an object: {relative}")
    return value


def render_json(value: object) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def projection_sha256(contract: dict[str, Any]) -> str:
    projection = dict(contract)
    projection["contract_projection_sha256"] = ZERO_SHA256
    return hashlib.sha256(render_json(projection)).hexdigest()


def hashes(paths: tuple[str, ...]) -> dict[str, str]:
    return {relative: sha256(relative) for relative in sorted(paths)}


def manifest_projection() -> str:
    """Bind the full repository manifest without a cryptographic self-cycle.

    The manifest contains the R7 contract and status, while the contract binds
    this projection.  Their two manifest rows are therefore normalized to zero;
    every other exact path and digest remains in the projection.  ``check_all``
    separately requires the raw manifest to equal a fresh full rendering.
    """

    normalized: list[str] = []
    self_rows = {
        CONTRACT.relative_to(ROOT).as_posix(),
        STATUS.relative_to(ROOT).as_posix(),
    }
    for row in render_manifest(ROOT).splitlines():
        digest, relative = row.split("  ", 1)
        if relative in self_rows:
            digest = ZERO_SHA256
        normalized.append(f"{digest}  {relative}")
    raw = ("\n".join(normalized) + "\n").encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_seal_coverage(contract: dict[str, Any]) -> None:
    bound: set[str] = set()
    for key in (
        "implementation_file_hashes",
        "supporting_file_hashes",
        "test_file_hashes",
    ):
        value = contract.get(key)
        require(isinstance(value, dict), f"seal {key} is not an object")
        bound.update(str(relative) for relative in value)
    missing = sorted(EXECUTED_SECURITY_PATHS - bound)
    require(not missing, f"executed security-critical paths are unsealed: {missing}")
    require(
        contract.get("repository_manifest_path") == REPOSITORY_MANIFEST,
        "repository manifest path is not sealed",
    )
    require(
        contract.get("repository_manifest_projection_sha256")
        == manifest_projection(),
        "repository manifest projection is stale",
    )


def build_contract() -> dict[str, Any]:
    findings = strict_load(
        "research/archive_inventory/r11a_corrective/R11A_RED_REVIEW_FINDINGS.json"
    )
    rows = findings.get("findings")
    require(isinstance(rows, list) and len(rows) == 21, "RED finding set drift")
    finding_ids = [row.get("finding_id") for row in rows if isinstance(row, dict)]
    require(len(finding_ids) == 21 and len(set(finding_ids)) == 21, "RED finding IDs drift")

    pricing = strict_load(
        "research/archive_inventory/r11a_corrective/R11A_PRICING_EUR_SNAPSHOT.json"
    )
    pricing_pending = pricing.get("status") != "BOUND_CURRENT_OFFICIAL_SNAPSHOT"
    remediation = {str(finding_id): finding_id != "R11A-RED-009" for finding_id in finding_ids}

    amendment = strict_load(SEALED_AMENDMENT)
    require(amendment.get("amendment_id") == SEALED_AMENDMENT_ID, "Amendment 002 ID drift")
    require(sha256(SEALED_AMENDMENT) == SEALED_AMENDMENT_SHA256, "Amendment 002 SHA drift")
    terminal_rows = amendment.get("terminal_decision_table")
    require(isinstance(terminal_rows, list) and len(terminal_rows) == 4, "terminal table drift")
    bindings = strict_load(V2_BINDINGS)
    require(
        bindings.get("binding_id") == "R11A-V2-PREREGISTRATION-BINDINGS-001",
        "V2 binding ID drift",
    )
    require(bindings.get("status") == "SEALED_PREREGISTRATION_NO_EXECUTION", "V2 binding status drift")
    file_sha256 = bindings.get("file_sha256")
    require(isinstance(file_sha256, dict), "V2 file bindings are absent")
    require(
        file_sha256.get(SEALED_AMENDMENT) == SEALED_AMENDMENT_SHA256,
        "V2 bindings do not bind canonical Amendment 002",
    )

    contract: dict[str, Any] = {
        "schema_version": "3.0",
        "contract_id": "R11A-CORRECTIVE-R7-LOCAL-SEAL-001",
        "implementation_id": IMPLEMENTATION_ID,
        "diagnostic_id": DIAGNOSTIC_ID,
        "status": "CORRECTIVE_R7_IMPLEMENTATION_SEALED_AWAITING_CLEAN_CONTEXT_REVIEW_NO_EXECUTION",
        "implementation_sealed": True,
        "implementation_review_green": False,
        "independent_clean_context_review_completed": False,
        "independent_clean_context_review_verdict": None,
        "pricing_binding_pending": pricing_pending,
        "owner_approval_eligible": False,
        "owner_approval_present": False,
        "authority_reconciliation": {
            "canonical_amendment_002_path": SEALED_AMENDMENT,
            "canonical_amendment_002_internal_id": SEALED_AMENDMENT_ID,
            "canonical_amendment_002_sha256": SEALED_AMENDMENT_SHA256,
            "canonical_amendment_002_present": True,
            "canonical_amendment_002_bound_by": V2_BINDINGS,
            "canonical_amendment_002_binding_id": bindings["binding_id"],
            "canonical_amendment_002_binding_valid": True,
            "preregistration_was_modified_by_r7_seal": False,
            "terminal_vocabulary_mapping": {
                "COMPLETE": "FULLY_MATERIALIZED_SEMANTICS",
                "EMPTY": "EARLY_STOP_EMPTY_SEMANTICS",
                "NOT_PROVEN": "UNRESOLVED_SEMANTICS",
            },
        },
        "approval_blockers": [
            "INDEPENDENT_CLEAN_CONTEXT_REVIEW_NOT_COMPLETED",
            "CURRENT_OFFICIAL_PRICING_AND_EUR_BINDING_PENDING",
        ],
        "red_finding_count": 21,
        "locally_tested_remediation_claims": remediation,
        "locally_tested_remediation_count": sum(remediation.values()),
        "independently_closed_red_finding_count": 0,
        "implementation_file_hashes": hashes(R7_CODE_PATHS + GOVERNANCE_PATHS),
        "supporting_file_hashes": hashes(SUPPORTING_PATHS),
        "test_file_hashes": hashes(TEST_PATHS),
        "workflow_candidate_path": CANDIDATE_WORKFLOW,
        "workflow_candidate_sha256": sha256(CANDIDATE_WORKFLOW),
        "repository_manifest_path": REPOSITORY_MANIFEST,
        "repository_manifest_binding_mode": "ALL_ROWS_EXCEPT_SELF_OUTPUT_ROWS_EXACT_SHA256",
        "repository_manifest_projection_sha256": manifest_projection(),
        "pricing_snapshot_status": pricing.get("status"),
        "pricing_snapshot_sha256": sha256(
            "research/archive_inventory/r11a_corrective/R11A_PRICING_EUR_SNAPSHOT.json"
        ),
        "workflow_installed_under_dot_github": False,
        "successor_role_created": False,
        "sts_preflight_evidence_present": False,
        "execution_release_present": False,
        "canonical_activation_present": False,
        "single_workflow_dispatch_authorized": False,
        "rerun_authorized": False,
        "network_requests_executed_by_implementation": 0,
        "aws_iam_mutations_executed_by_implementation": 0,
        "diagnostic_rows_created_by_implementation": 0,
        "wallet_feature_rows_created_by_implementation": 0,
        "runtime_authority": {
            "aws_iam_mutation": False,
            "aws_oidc": False,
            "sts": False,
            "requester_pays": False,
            "get_object": False,
            "object_body_download": False,
            "decompression": False,
            "diagnostic_processing": False,
            "diagnostic_artifact_retention": False,
        },
        "downstream_authorizations": {
            "deduplication": False,
            "block_replay_suppression": False,
            "wallet_feature_publication": False,
            "r11b_repair": False,
            "historical_expansion": False,
            "wallet_ranking": False,
            "candidate_shortlisting": False,
            "pnl_or_alpha_analysis": False,
            "copyability_analysis": False,
            "entity_clustering": False,
            "strategy_inference": False,
        },
        "trading_authorizations": {
            "integration": False,
            "paper": False,
            "shadow": False,
            "live": False,
            "leverage": False,
            "capital_allocation": False,
        },
        "r11_closed": False,
        "r12_ready": False,
        "empirical_result": None,
        "contract_projection_sha256": ZERO_SHA256,
    }
    validate_seal_coverage(contract)
    contract["contract_projection_sha256"] = projection_sha256(contract)
    return contract


def build_status(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "3.0",
        "status_id": "R11A-CORRECTIVE-R7-STATUS-001",
        "implementation_id": IMPLEMENTATION_ID,
        "diagnostic_id": DIAGNOSTIC_ID,
        "status": contract["status"],
        "implementation_sealed": True,
        "implementation_review_green": False,
        "pricing_binding_pending": contract["pricing_binding_pending"],
        "owner_approval_eligible": False,
        "owner_approval_present": False,
        "canonical_amendment_002_path": SEALED_AMENDMENT,
        "canonical_amendment_002_internal_id": SEALED_AMENDMENT_ID,
        "canonical_amendment_002_sha256": SEALED_AMENDMENT_SHA256,
        "canonical_amendment_002_present": True,
        "canonical_amendment_002_binding_valid": True,
        "locally_tested_remediation_count": contract[
            "locally_tested_remediation_count"
        ],
        "independently_closed_red_finding_count": 0,
        "runtime_authority": contract["runtime_authority"],
        "downstream_authorizations": contract["downstream_authorizations"],
        "trading_authorizations": contract["trading_authorizations"],
        "network_requests_executed": 0,
        "aws_iam_mutations_executed": 0,
        "r11_closed": False,
        "r12_ready": False,
        "empirical_result": None,
    }


def write_all() -> None:
    contract = build_contract()
    CONTRACT.write_bytes(render_json(contract))
    STATUS.write_bytes(render_json(build_status(contract)))


def check_all() -> None:
    expected_contract = build_contract()
    expected_status = build_status(expected_contract)
    require(CONTRACT.is_file(), "R7 contract is absent")
    require(STATUS.is_file(), "R7 status is absent")
    require(CONTRACT.read_bytes() == render_json(expected_contract), "R7 contract is stale")
    require(STATUS.read_bytes() == render_json(expected_status), "R7 status is stale")
    manifest = ROOT / REPOSITORY_MANIFEST
    require(manifest.is_file(), "repository manifest is absent")
    require(
        manifest.read_text(encoding="utf-8") == render_manifest(ROOT),
        "repository manifest is incomplete or stale",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--write", action="store_true")
    modes.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    if arguments.write:
        write_all()
        print("R11A_CORRECTIVE_R7_IMPLEMENTATION_SEAL_WRITTEN")
        return 0
    check_all()
    print("R11A_CORRECTIVE_R7_IMPLEMENTATION_SEAL_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
