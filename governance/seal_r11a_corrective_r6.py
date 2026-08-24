#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
CORRECTIVE = BASE / "r11a_corrective"
CONTRACT = CORRECTIVE / "R11A_CORRECTIVE_IMPLEMENTATION_CONTRACT.json"
STATUS = CORRECTIVE / "R11A_CORRECTIVE_STATUS.json"
DEPENDENCIES = CORRECTIVE / "R11A_DEPENDENCIES.json"
PRICING = CORRECTIVE / "R11A_PRICING_EUR_SNAPSHOT.json"
RESOURCE_REPORT = CORRECTIVE / "R11A_RESOURCE_FEASIBILITY_R3.json"
ROLE_DECISION = CORRECTIVE / "R11A_ROLE_DECISION.json"
FINDINGS = CORRECTIVE / "R11A_RED_REVIEW_FINDINGS.json"
V2_BINDINGS = BASE / "r11a_v2/R11A_V2_PREREGISTRATION_BINDINGS.json"
WORKFLOW = CORRECTIVE / "workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic-r6.yml"
ZERO_SHA256 = "0" * 64

IMPLEMENTATION_ID = "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-CORRECTIVE-R6"
DIAGNOSTIC_ID = "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-002"
CORRECTIVE_PREREGISTRATION_MERGE = "1d218755ead2cbf635ca0e1741f53e0184c0e239"
CORRECTIVE_PREREGISTRATION_TREE = "5cbe87e5221be4e9b98a2be4c52626128a71726a"
ORIGINAL_PREREGISTRATION_MERGE = "5103c846be8a53732d8559a281ac8b57ce4d7aac"
R11_EVIDENCE_CLOSURE_MERGE = "f7aa612d2a5638cce0fd197f57efea4b787f87f1"
REJECTED_IMPLEMENTATION_MERGE = "8e778fdf6e7b5ef5475791bd4292b2d04055afcd"
QUARANTINED_CLOSURE_MERGE = "4bb3eaf4cbcfea7771261ade73d618912496585a"
CONTAINMENT_MERGE = "57566456624eb758049aa7687bdb7b8a2844c91d"
WORKFLOW_RELATIVE = (
    "research/archive_inventory/r11a_corrective/workflows/"
    "hyperliquid-archive-r11a-identity-boundary-diagnostic-r6.yml"
)

EXECUTION_GRAPH = (
    "__init__.py",
    "activity.py",
    "artifact_r3.py",
    "canonical.py",
    "context.py",
    "entrypoint_r5.py",
    "identity.py",
    "index_r3.py",
    "join.py",
    "limits.py",
    "lz4stream.py",
    "materialize_r3.py",
    "network.py",
    "parser.py",
    "preflight_artifact.py",
    "pricing.py",
    "runner_r4.py",
    "runtime.py",
    "selection.py",
    "storage.py",
    "taxonomy_r4.py",
    "workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic-r6.yml",
)

SEALED_GOVERNANCE_FILES = (
    "governance/seal_r11a_corrective_r6.py",
    "governance/validate_r11a_corrective_implementation_r6.py",
    "governance/validate_r11a_execution_artifact_r4.py",
    "governance/generate_r11a_corrective_policies.py",
    "governance/r11a_stage_common_r4.py",
    "governance/validate_r11a_approval_r4.py",
    "governance/validate_r11a_role_attestation_r4.py",
    "governance/validate_r11a_role_preflight_evidence_r4.py",
    "governance/validate_r11a_workflow_installation_r4.py",
    "governance/validate_r11a_execution_release_r4.py",
    "governance/validate_r11a_activation_r4.py",
)

SUPPORTING_FILES = (
    "research/archive_inventory/r11a_v2/R11A_V2_PREREGISTRATION_BINDINGS.json",
    "research/archive_inventory/r11a_corrective/R11A_DEPENDENCIES.json",
    "research/archive_inventory/r11a_corrective/R11A_PRICING_EUR_SNAPSHOT.json",
    "research/archive_inventory/r11a_corrective/R11A_RESOURCE_FEASIBILITY_R3.json",
    "research/archive_inventory/r11a_corrective/R11A_ROLE_DECISION.json",
    "research/archive_inventory/r11a_corrective/R11A_RED_REVIEW_FINDINGS.json",
)

TEST_FILES = (
    "tests/test_archive_inventory_r11a_corrective_artifacts.py",
    "tests/test_archive_inventory_r11a_corrective_r3.py",
    "tests/test_archive_inventory_r11a_v2_bindings.py",
    "tests/test_archive_inventory_r11a_v2_preregistration.py",
)


class SealError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    return hashlib.sha1(
        b"blob " + str(len(payload)).encode("ascii") + b"\0" + payload
    ).hexdigest()


def strict_load(path: Path) -> dict[str, object]:
    def pairs(rows: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in rows:
            if key in result:
                raise SealError(f"duplicate JSON key in {path}: {key}")
            result[key] = value
        return result

    def constant(token: str) -> object:
        raise SealError(f"non-finite JSON constant in {path}: {token}")

    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=pairs,
        parse_constant=constant,
    )
    if not isinstance(value, dict):
        raise SealError(f"{path} root must be object")
    return value


def render_json(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def contract_projection_sha256(contract: dict[str, object]) -> str:
    projection = dict(contract)
    projection["contract_projection_sha256"] = ZERO_SHA256
    payload = (
        json.dumps(
            projection,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def replace_required(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old in text:
        path.write_text(text.replace(old, new), encoding="utf-8")
        return
    if new not in text:
        raise SealError(f"expected text absent in {path}: {old}")


def patch_runtime_bindings() -> None:
    replace_required(
        WORKFLOW,
        "governance/validate_r11a_corrective_implementation_r5.py --canonical-bytes",
        "governance/validate_r11a_corrective_implementation_r6.py --canonical-bytes",
    )
    for relative in TEST_FILES:
        path = ROOT / relative
        if not path.is_file():
            continue
        value = path.read_text(encoding="utf-8")
        old_name = "validate_r11a_corrective_implementation_r5.py"
        new_name = "validate_r11a_corrective_implementation_r6.py"
        if old_name in value:
            path.write_text(value.replace(old_name, new_name), encoding="utf-8")
    old_validator = ROOT / "governance/validate_r11a_corrective_implementation_r5.py"
    if old_validator.exists():
        old_validator.unlink()



def patch_review_mode() -> None:
    validator = ROOT / "governance/validate_r11a_corrective_implementation_r6.py"
    text = validator.read_text(encoding="utf-8")
    old = '''        require(all(value is True for value in closed.values()), "one or more RED findings remain implementation-open")
        validate_hash_set(contract)

        if mode == "review":'''
    new = '''        if mode == "review" and pricing.get("status") != "BOUND_CURRENT_OFFICIAL_SNAPSHOT":
            remaining = {key for key, value in closed.items() if value is not True}
            require(
                remaining == {"R11A-RED-009"},
                "review-stage implementation may leave only the official pricing binding pending",
            )
        else:
            require(all(value is True for value in closed.values()), "one or more RED findings remain implementation-open")
        validate_hash_set(contract)

        if mode == "review":'''
    if old in text:
        validator.write_text(text.replace(old, new, 1), encoding="utf-8")
    elif new not in text:
        raise SealError("review-stage pricing exception patch drift")


def collect_standard_library_modules() -> list[str]:
    modules: set[str] = set()
    for relative in EXECUTION_GRAPH:
        path = CORRECTIVE / relative
        if path.suffix != ".py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules.add(node.module.split(".", 1)[0])
    modules.discard("__future__")
    modules.discard("research")
    return sorted(modules)


def write_dependencies() -> None:
    value = {
        "schema_version": "1.0",
        "dependency_declaration_id": "R11A-CORRECTIVE-R6-STDLIB-DEPENDENCIES-001",
        "status": "FROZEN_CORRECTIVE_IMPLEMENTATION_NO_INSTALLATION",
        "python_runtime": {
            "implementation": "CPython",
            "exact_version": "3.12.13",
            "third_party_python_packages_required": [],
        },
        "standard_library_modules": collect_standard_library_modules(),
        "repository_local_runtime_dependencies": [],
        "system_executables_required_by_collector": [],
        "network_dependency_installation_authorized": False,
        "pip_install_authorized": False,
        "apt_install_authorized": False,
        "unlocked_dependency_authorized": False,
        "dependency_resolution_performed_by_this_stage": False,
    }
    DEPENDENCIES.write_text(render_json(value), encoding="utf-8")


def write_docs() -> None:
    progress = CORRECTIVE / "R11A_CORRECTIVE_PROGRESS.md"
    progress.write_text(
        "# R11A corrective implementation progress\n\n"
        "The corrective R6 implementation is cryptographically sealed and remains strictly inert. "
        "It claims offline closure of twenty RED findings and leaves only the current official AWS-pricing/ECB-EUR binding pending before owner-approval eligibility. "
        "A new exact-head Research CI run and a separate clean-context review are mandatory before any approval-stage promotion.\n\n"
        "No owner approval, IAM role creation, workflow installation, OIDC, STS, S3 request, decompression, diagnostic evidence, deduplication, R11B repair, wallet feature, ranking, PnL/alpha, copyability or trading/capital authority is opened.\n",
        encoding="utf-8",
    )
    corrective_readme = CORRECTIVE / "README.md"
    corrective_readme.write_text(
        "# R11A corrective R6 implementation\n\n"
        "This directory contains the sealed, still-inert corrective implementation of `HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-002`. "
        "It supersedes the rejected PR #141 implementation design without rewriting historical evidence. The execution graph, lifecycle validators, successor-role templates, resource report and workflow candidate are hash-bound in `R11A_CORRECTIVE_IMPLEMENTATION_CONTRACT.json`.\n\n"
        "The current stage is `CORRECTIVE_IMPLEMENTATION_SEALED_AWAITING_CLEAN_CONTEXT_REVIEW_NO_EXECUTION`. Owner approval remains ineligible while the official pricing/EUR binding and independent review are incomplete. The workflow candidate remains outside `.github/workflows`.\n\n"
        "No network execution, duplicate suppression, wallet-feature publication or downstream trading research is authorized by this directory.\n",
        encoding="utf-8",
    )

    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    old = '''R11 is canonically `CONSUMED_UNRESOLVED`; its exact artifact is retained and its
single-use release has zero remaining request budget. R11A is
`PREREGISTERED_NO_EXECUTION` over exactly the same 72 objects. It may diagnose
identity scope, archive-block overlap and repeat provenance only. No owner
approval, installed workflow, release, AWS/S3 authority, empirical root-cause
claim, deduplication, repair, wallet ranking or R12 promotion exists.'''
    new = '''R11 is canonically `CONSUMED_UNRESOLVED`; its exact artifact is retained and its
single-use release has zero remaining request budget. The corrective R11A V2
preregistration is sealed over exactly the same 72 objects, and its R6
implementation is sealed but still awaiting independent clean-context review.
The workflow candidate remains outside `.github/workflows`; owner approval,
role creation, release, AWS/S3 authority, empirical root-cause claims,
deduplication, repair, wallet ranking and R12 promotion remain absent.'''
    if old not in text:
        raise SealError("top-level README archive gate drift")
    readme.write_text(text.replace(old, new, 1), encoding="utf-8")

    roadmap = ROOT / "ROADMAP.md"
    text = roadmap.read_text(encoding="utf-8")
    old = '''- [ ] Merge the separately reviewed inert R11A implementation and workflow candidate outside `.github/workflows`.
- [ ] Obtain one exact hash-bound owner approval for role reuse and the frozen diagnostic envelope.'''
    new = '''- [ ] Complete exact-head CI and independent review of the sealed corrective R11A V2 R6 implementation and workflow candidate outside `.github/workflows`.
- [ ] Bind current official pricing/EUR evidence and obtain one exact hash-bound owner approval for the dedicated successor role and frozen diagnostic envelope.'''
    if old not in text:
        raise SealError("roadmap R11A gate drift")
    roadmap.write_text(text.replace(old, new, 1), encoding="utf-8")

    project = ROOT / "PROJECT_STATE.md"
    text = project.read_text(encoding="utf-8")
    old = '''2. Review and merge a fully inert R11A implementation and frozen workflow candidate. No `.github/workflows` installation, OIDC, S3 request or release may appear at this stage.
3. After exact-head CI and clean-context review of the inert implementation, request one new hash-bound owner approval for the diagnostic scope, unchanged role reuse, 72-request / zero-retry envelope, byte/runtime/disk/artifact caps and EUR 0.50 one-time / EUR 0 monthly ceiling.'''
    new = '''2. Validate and independently review the cryptographically sealed corrective R11A V2 R6 implementation. Its workflow candidate must remain outside `.github/workflows`; no OIDC, S3 request or release may appear at this stage.
3. After exact-head CI, clean-context review and official pricing/EUR binding, request one new hash-bound owner approval for the dedicated successor role, exact 72-request / zero-retry envelope, byte/runtime/disk/artifact caps and EUR 0.50 one-time / EUR 0 monthly ceiling.'''
    if old not in text:
        raise SealError("project-state R11A gate drift")
    project.write_text(text.replace(old, new, 1), encoding="utf-8")


def build_contract() -> dict[str, object]:
    findings = strict_load(FINDINGS)
    finding_rows = findings.get("findings")
    if not isinstance(finding_rows, list) or len(finding_rows) != 21:
        raise SealError("authoritative RED finding set drift")
    closed = {str(row["finding_id"]): True for row in finding_rows if isinstance(row, dict)}
    pricing = strict_load(PRICING)
    pricing_bound = pricing.get("status") == "BOUND_CURRENT_OFFICIAL_SNAPSHOT"
    if not pricing_bound:
        closed["R11A-RED-009"] = False

    implementation_paths = {
        f"research/archive_inventory/r11a_corrective/{relative}"
        for relative in EXECUTION_GRAPH
    } | set(SEALED_GOVERNANCE_FILES)
    implementation_hashes = {
        relative: sha256(ROOT / relative)
        for relative in sorted(implementation_paths)
    }
    support_hashes = {
        relative: sha256(ROOT / relative)
        for relative in sorted(SUPPORTING_FILES)
    }
    test_hashes = {
        relative: sha256(ROOT / relative)
        for relative in sorted(TEST_FILES)
    }
    role = strict_load(ROLE_DECISION)
    resource = strict_load(RESOURCE_REPORT)
    workflow_sha = sha256(WORKFLOW)
    contract: dict[str, object] = {
        "schema_version": "2.0",
        "implementation_id": IMPLEMENTATION_ID,
        "diagnostic_id": DIAGNOSTIC_ID,
        "status": "CORRECTIVE_IMPLEMENTATION_SEALED_AWAITING_CLEAN_CONTEXT_REVIEW_NO_EXECUTION",
        "corrective_preregistration_merge_commit": CORRECTIVE_PREREGISTRATION_MERGE,
        "corrective_preregistration_tree": CORRECTIVE_PREREGISTRATION_TREE,
        "corrective_preregistration_bindings_sha256": sha256(V2_BINDINGS),
        "original_preregistration_merge_commit": ORIGINAL_PREREGISTRATION_MERGE,
        "parent_r11_evidence_closure_merge_commit": R11_EVIDENCE_CLOSURE_MERGE,
        "rejected_pr141_merge_commit": REJECTED_IMPLEMENTATION_MERGE,
        "quarantined_pr142_merge_commit": QUARANTINED_CLOSURE_MERGE,
        "containment_pr143_merge_commit": CONTAINMENT_MERGE,
        "red_review_id": "R11A-D1-INDEPENDENT-CLEAN-CONTEXT-RED-001",
        "red_finding_count": 21,
        "red_findings_closed": closed,
        "closed_red_finding_count": sum(value is True for value in closed.values()),
        "implementation_sealed": True,
        "implementation_file_hashes": implementation_hashes,
        "supporting_file_hashes": support_hashes,
        "test_file_hashes": test_hashes,
        "workflow_candidate_path": WORKFLOW_RELATIVE,
        "workflow_candidate_sha256": workflow_sha,
        "workflow_candidate_git_blob_sha": git_blob_sha(WORKFLOW),
        "dependency_declaration_sha256": sha256(DEPENDENCIES),
        "pricing_snapshot_status": pricing.get("status"),
        "pricing_snapshot_sha256": sha256(PRICING),
        "resource_feasibility_report_sha256": sha256(RESOURCE_REPORT),
        "successor_role_decision_sha256": sha256(ROLE_DECISION),
        "successor_role_arn": role["successor_role"]["role_arn"],
        "maximum_ephemeral_workspace_bytes": resource["maximum_ephemeral_workspace_bytes"],
        "maximum_retained_artifact_bytes": resource["maximum_retained_artifact_bytes"],
        "maximum_runtime_seconds": resource["maximum_runtime_seconds"],
        "independent_clean_context_review_required": True,
        "independent_clean_context_review_completed": False,
        "independent_clean_context_review_verdict": None,
        "exact_head_ci_required_before_merge": True,
        "owner_approval_eligible": False,
        "owner_approval_present": False,
        "workflow_installed_under_dot_github": False,
        "successor_role_created": False,
        "role_attestation_present": False,
        "sts_preflight_evidence_present": False,
        "execution_release_present": False,
        "canonical_activation_present": False,
        "single_workflow_dispatch_authorized": False,
        "rerun_authorized": False,
        "network_requests_executed_by_implementation": 0,
        "aws_iam_mutations_executed_by_implementation": 0,
        "diagnostic_rows_created_by_implementation": 0,
        "wallet_feature_rows_created_by_implementation": 0,
        "r11_closed": False,
        "r12_ready": False,
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
        "contract_projection_sha256": ZERO_SHA256,
        "empirical_result": None,
    }
    contract["contract_projection_sha256"] = contract_projection_sha256(contract)
    return contract


def write_status(contract: dict[str, object]) -> None:
    status = {
        "schema_version": "2.0",
        "status_id": "R11A-CORRECTIVE-R6-STATUS-001",
        "implementation_id": IMPLEMENTATION_ID,
        "diagnostic_id": DIAGNOSTIC_ID,
        "status": contract["status"],
        "implementation_sealed": True,
        "owner_approval_eligible": False,
        "exact_head_ci_required_before_merge": True,
        "independent_clean_context_review_required_before_owner_approval": True,
        "independent_clean_context_review_completed": False,
        "independent_clean_context_review_verdict": None,
        "red_finding_count": 21,
        "closed_red_finding_count": contract["closed_red_finding_count"],
        "pricing_binding_pending": contract["pricing_snapshot_status"] != "BOUND_CURRENT_OFFICIAL_SNAPSHOT",
        "workflow_installed_under_dot_github": False,
        "owner_approval_present": False,
        "successor_role_created": False,
        "runtime_release_present": False,
        "canonical_activation_present": False,
        "network_requests_executed": 0,
        "aws_iam_mutations_executed": 0,
        "diagnostic_rows_created": 0,
        "wallet_feature_rows_created": 0,
        "r11_closed": False,
        "r12_ready": False,
        "current_runtime_authority": contract["runtime_authority"],
        "downstream_authorizations": contract["downstream_authorizations"],
        "trading_authorizations": contract["trading_authorizations"],
        "empirical_result": None,
    }
    STATUS.write_text(render_json(status), encoding="utf-8")


def write_all() -> None:
    patch_runtime_bindings()
    patch_review_mode()
    write_dependencies()
    write_docs()
    contract = build_contract()
    CONTRACT.write_text(render_json(contract), encoding="utf-8")
    write_status(contract)


def check_all() -> None:
    contract = strict_load(CONTRACT)
    if contract.get("implementation_id") != IMPLEMENTATION_ID:
        raise SealError("implementation seal identity drift")
    if contract.get("diagnostic_id") != DIAGNOSTIC_ID:
        raise SealError("diagnostic seal identity drift")
    if contract.get("contract_projection_sha256") != contract_projection_sha256(contract):
        raise SealError("contract projection SHA-256 drift")
    expected = build_contract()
    if contract != expected:
        raise SealError("R11A corrective R6 implementation seal is stale")


def main() -> int:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--write", action="store_true")
    modes.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    if arguments.write:
        write_all()
        print("R11A_CORRECTIVE_R6_IMPLEMENTATION_SEAL_WRITTEN")
        return 0
    check_all()
    print("R11A_CORRECTIVE_R6_IMPLEMENTATION_SEAL_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
