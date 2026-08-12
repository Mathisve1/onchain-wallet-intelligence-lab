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
FINDINGS = CORRECTIVE / "R11A_RED_REVIEW_FINDINGS.json"
PRICING = CORRECTIVE / "R11A_PRICING_EUR_SNAPSHOT.json"
DEPENDENCIES = CORRECTIVE / "R11A_DEPENDENCIES.json"
ROLE_DECISION = CORRECTIVE / "R11A_ROLE_DECISION.json"
RESOURCE_REPORT = CORRECTIVE / "R11A_RESOURCE_FEASIBILITY_R3.json"
V2_BINDINGS = BASE / "r11a_v2/R11A_V2_PREREGISTRATION_BINDINGS.json"
INSTALLED_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic.yml"
APPROVAL_ROOT = BASE / "r11a_approval"
RUNTIME_ROOT = BASE / "r11a_runtime"
EVIDENCE_ROOT = BASE / "r11a_evidence"

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
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-identity-r11a"
ZERO_SHA256 = "0" * 64

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


class ValidationError(AssertionError):
    pass


def load(path: Path) -> dict[str, object]:
    def pairs(rows: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in rows:
            if key in result:
                raise ValidationError(f"duplicate JSON key in {path}: {key}")
            result[key] = value
        return result

    def constant(token: str) -> object:
        raise ValidationError(f"non-finite constant in {path}: {token}")

    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=pairs,
        parse_constant=constant,
    )
    if not isinstance(value, dict):
        raise ValidationError(f"{path} root must be object")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    return hashlib.sha1(
        b"blob " + str(len(payload)).encode("ascii") + b"\0" + payload
    ).hexdigest()


def canonical_projection_sha256(contract: dict[str, object]) -> str:
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


def validate_ast(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    forbidden_modules = {"urllib", "urllib.request", "socket", "boto3", "requests", "httpx"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "hash":
            raise ValidationError(f"Python hash() is forbidden in {path}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "quantize":
            raise ValidationError(f"Decimal.quantize is forbidden in {path}")
        if path.name != "network.py" and isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in forbidden_modules or any(
                    alias.name.startswith(value + ".") for value in forbidden_modules
                ):
                    raise ValidationError(f"network import outside network.py: {path}:{alias.name}")
        if path.name != "network.py" and isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in forbidden_modules or any(
                module.startswith(value + ".") for value in forbidden_modules
            ):
                raise ValidationError(f"network import outside network.py: {path}:{module}")
    for token in (
        "drop_duplicates",
        "ignore_errors=True",
        "first_seen_wins",
        "last_seen_wins",
    ):
        require(token not in text, f"forbidden implementation token {token}: {path}")


def validate_closed_authority(contract: dict[str, object]) -> None:
    for key in ("runtime_authority", "downstream_authorizations", "trading_authorizations"):
        value = contract.get(key)
        require(isinstance(value, dict), f"{key} must be an object")
        require(all(item is False for item in value.values()), f"{key} opens authority")
    for key in (
        "network_requests_executed_by_implementation",
        "aws_iam_mutations_executed_by_implementation",
        "diagnostic_rows_created_by_implementation",
        "wallet_feature_rows_created_by_implementation",
    ):
        require(contract.get(key) == 0, f"implementation activity overclaim: {key}")
    require(contract.get("empirical_result") is None, "implementation contains empirical result")
    require(contract.get("r11_closed") is False, "implementation overclaims R11 closure")
    require(contract.get("r12_ready") is False, "implementation overclaims R12 readiness")


def validate_lineage(contract: dict[str, object]) -> None:
    expected = {
        "implementation_id": IMPLEMENTATION_ID,
        "diagnostic_id": DIAGNOSTIC_ID,
        "corrective_preregistration_merge_commit": CORRECTIVE_PREREGISTRATION_MERGE,
        "corrective_preregistration_tree": CORRECTIVE_PREREGISTRATION_TREE,
        "original_preregistration_merge_commit": ORIGINAL_PREREGISTRATION_MERGE,
        "parent_r11_evidence_closure_merge_commit": R11_EVIDENCE_CLOSURE_MERGE,
        "rejected_pr141_merge_commit": REJECTED_IMPLEMENTATION_MERGE,
        "quarantined_pr142_merge_commit": QUARANTINED_CLOSURE_MERGE,
        "containment_pr143_merge_commit": CONTAINMENT_MERGE,
        "red_review_id": "R11A-D1-INDEPENDENT-CLEAN-CONTEXT-RED-001",
        "red_finding_count": 21,
    }
    for key, value in expected.items():
        require(contract.get(key) == value, f"lineage drift: {key}")
    bindings = load(V2_BINDINGS)
    require(bindings.get("diagnostic_id") == DIAGNOSTIC_ID, "V2 binding diagnostic drift")
    require(bindings.get("status") == "SEALED_PREREGISTRATION_NO_EXECUTION", "V2 binding status drift")
    require(
        contract.get("corrective_preregistration_bindings_sha256") == sha256(V2_BINDINGS),
        "corrective preregistration binding SHA drift",
    )


def validate_execution_graph() -> None:
    for relative in EXECUTION_GRAPH:
        path = CORRECTIVE / relative
        require(path.is_file(), f"execution graph file is absent: {relative}")
        if path.suffix == ".py":
            validate_ast(path)
    require(
        "urllib.request" in (CORRECTIVE / "network.py").read_text(encoding="utf-8"),
        "direct HTTPS transport is absent",
    )
    require(not INSTALLED_WORKFLOW.exists(), "R11A workflow is installed during inert stage")


def validate_dependencies_role_and_resource() -> None:
    dependencies = load(DEPENDENCIES)
    require(dependencies.get("status") == "FROZEN_CORRECTIVE_IMPLEMENTATION_NO_INSTALLATION", "dependency status drift")
    runtime = dependencies.get("python_runtime")
    require(isinstance(runtime, dict), "python runtime declaration absent")
    require(runtime.get("implementation") == "CPython", "Python implementation drift")
    require(runtime.get("exact_version") == "3.12.13", "Python version drift")
    require(runtime.get("third_party_python_packages_required") == [], "third-party dependency reopened")
    require(dependencies.get("network_dependency_installation_authorized") is False, "network dependency installation opened")
    require(dependencies.get("pip_install_authorized") is False, "pip installation opened")
    require(dependencies.get("apt_install_authorized") is False, "apt installation opened")

    role = load(ROLE_DECISION)
    successor = role.get("successor_role")
    require(isinstance(successor, dict), "successor role decision absent")
    require(successor.get("role_arn") == ROLE_ARN, "successor role ARN drift")
    require(successor.get("persistent_get_object_resource_count") == 72, "successor role target count drift")
    require(successor.get("persistent_permission_resources_are_exact_selection_objects") is True, "successor role exact-object boundary weakened")
    require(role.get("existing_r11_role_reused") is False, "consumed R11 role reuse reopened")
    require(role.get("existing_r11_role_mutated") is False, "consumed R11 role mutation reopened")
    require(role.get("new_role_created_by_this_decision") is False, "role decision executed IAM mutation")

    report = load(RESOURCE_REPORT)
    require(report.get("maximum_ephemeral_workspace_bytes") == 5_368_709_120, "workspace cap drift")
    require(report.get("minimum_free_workspace_bytes_before_oidc") == 6_442_450_944, "pre-OIDC free-space drift")
    require(report.get("maximum_retained_artifact_bytes") == 134_217_728, "artifact cap drift")
    require(report.get("maximum_runtime_seconds") == 21_600, "runtime cap drift")
    require(report.get("successful_completion_within_caps_claimed") is False, "resource report overclaims success")
    require(report.get("bounded_empty_artifact_on_preregistered_cap_failure_required") is True, "bounded failure requirement weakened")


def validate_hash_set(contract: dict[str, object]) -> None:
    required_implementation_paths = {
        f"research/archive_inventory/r11a_corrective/{relative}"
        for relative in EXECUTION_GRAPH
    } | set(SEALED_GOVERNANCE_FILES)
    observed = contract.get("implementation_file_hashes")
    require(isinstance(observed, dict), "implementation file hashes absent")
    require(set(observed) == required_implementation_paths, "sealed implementation hash set differs from exact execution graph")
    for relative, digest in observed.items():
        path = ROOT / relative
        require(path.is_file(), f"sealed implementation path absent: {relative}")
        require(digest == sha256(path), f"sealed implementation path hash drift: {relative}")

    support = contract.get("supporting_file_hashes")
    require(isinstance(support, dict), "supporting file hashes absent")
    require(set(support) == set(SUPPORTING_FILES), "supporting hash set drift")
    for relative, digest in support.items():
        path = ROOT / relative
        require(path.is_file(), f"supporting path absent: {relative}")
        require(digest == sha256(path), f"supporting path hash drift: {relative}")

    tests = contract.get("test_file_hashes")
    require(isinstance(tests, dict), "test file hashes absent")
    require(set(tests) == set(TEST_FILES), "test hash set drift")
    for relative, digest in tests.items():
        path = ROOT / relative
        require(path.is_file(), f"test path absent: {relative}")
        require(digest == sha256(path), f"test path hash drift: {relative}")

    workflow = ROOT / WORKFLOW_RELATIVE
    require(contract.get("workflow_candidate_path") == WORKFLOW_RELATIVE, "workflow candidate path drift")
    require(contract.get("workflow_candidate_sha256") == sha256(workflow), "workflow candidate SHA-256 drift")
    require(contract.get("workflow_candidate_git_blob_sha") == git_blob_sha(workflow), "workflow candidate Git blob drift")
    require(contract.get("contract_projection_sha256") == canonical_projection_sha256(contract), "contract projection SHA-256 drift")


def validate_status(contract: dict[str, object], *, mode: str) -> None:
    status = load(STATUS)
    require(status.get("implementation_id") == IMPLEMENTATION_ID, "status implementation ID drift")
    require(status.get("diagnostic_id") == DIAGNOSTIC_ID, "status diagnostic ID drift")
    require(status.get("status") == contract.get("status"), "status/contract lifecycle drift")
    require(status.get("implementation_sealed") == contract.get("implementation_sealed"), "status seal drift")
    require(status.get("owner_approval_eligible") == contract.get("owner_approval_eligible"), "status approval eligibility drift")
    require(status.get("closed_red_finding_count") == sum(value is True for value in contract.get("red_findings_closed", {}).values()), "status finding count drift")
    for key in (
        "workflow_installed_under_dot_github",
        "owner_approval_present",
        "successor_role_created",
        "runtime_release_present",
        "canonical_activation_present",
    ):
        require(status.get(key) is False, f"status opens inert-stage lifecycle: {key}")
    require(status.get("network_requests_executed") == 0, "status records network execution")
    require(status.get("aws_iam_mutations_executed") == 0, "status records IAM mutation")
    require(status.get("diagnostic_rows_created") == 0, "status records diagnostic result")
    require(status.get("wallet_feature_rows_created") == 0, "status records wallet feature")
    require(status.get("independent_clean_context_review_completed") is (mode == "approval"), "status review completion drift")


def main() -> int:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--current-inert-stage", action="store_true")
    modes.add_argument("--sealed-review-stage", action="store_true")
    modes.add_argument("--canonical-bytes", action="store_true")
    arguments = parser.parse_args()
    mode = "current" if arguments.current_inert_stage else "review" if arguments.sealed_review_stage else "approval"

    contract = load(CONTRACT)
    findings = load(FINDINGS)
    pricing = load(PRICING)
    validate_lineage(contract)
    require(findings.get("verdict") == "RED", "authoritative review verdict drift")
    require(isinstance(findings.get("findings"), list) and len(findings["findings"]) == 21, "authoritative RED finding set drift")
    validate_closed_authority(contract)
    validate_execution_graph()
    validate_dependencies_role_and_resource()

    require(not APPROVAL_ROOT.exists(), "approval present during inert implementation stage")
    require(not RUNTIME_ROOT.exists(), "runtime overlay present during inert implementation stage")
    require(not EVIDENCE_ROOT.exists(), "execution evidence present during inert implementation stage")

    if mode == "current":
        require(
            contract.get("status")
            in {
                "CORRECTIVE_IMPLEMENTATION_IN_PROGRESS_NO_EXECUTION",
                "CORRECTIVE_IMPLEMENTATION_SEALED_AWAITING_CLEAN_CONTEXT_REVIEW_NO_EXECUTION",
                "CORRECTIVE_IMPLEMENTATION_SEALED_APPROVAL_ELIGIBLE_NO_EXECUTION",
            },
            "current inert status drift",
        )
        if contract.get("implementation_sealed") is True:
            validate_hash_set(contract)
    else:
        expected_status = (
            "CORRECTIVE_IMPLEMENTATION_SEALED_AWAITING_CLEAN_CONTEXT_REVIEW_NO_EXECUTION"
            if mode == "review"
            else "CORRECTIVE_IMPLEMENTATION_SEALED_APPROVAL_ELIGIBLE_NO_EXECUTION"
        )
        require(contract.get("status") == expected_status, "sealed lifecycle status drift")
        require(contract.get("implementation_sealed") is True, "implementation is not sealed")
        closed = contract.get("red_findings_closed")
        require(isinstance(closed, dict), "RED finding closure map absent")
        require(set(closed) == {f"R11A-RED-{index:03d}" for index in range(1, 22)}, "RED finding closure set incomplete")
        if mode == "review" and pricing.get("status") != "BOUND_CURRENT_OFFICIAL_SNAPSHOT":
            remaining = {key for key, value in closed.items() if value is not True}
            require(
                remaining == {"R11A-RED-009"},
                "review-stage implementation may leave only the official pricing binding pending",
            )
        else:
            require(all(value is True for value in closed.values()), "one or more RED findings remain implementation-open")
        validate_hash_set(contract)

        if mode == "review":
            require(contract.get("owner_approval_eligible") is False, "review-stage implementation self-opens owner approval")
            require(contract.get("independent_clean_context_review_completed") is False, "review stage claims completed independent review")
            require(contract.get("independent_clean_context_review_verdict") is None, "review stage invents independent verdict")
        else:
            require(contract.get("owner_approval_eligible") is True, "canonical bytes are not owner-approval eligible")
            require(contract.get("independent_clean_context_review_completed") is True, "approval stage lacks independent review")
            require(contract.get("independent_clean_context_review_verdict") == "GREEN", "approval stage review verdict is not GREEN")
            require(pricing.get("status") == "BOUND_CURRENT_OFFICIAL_SNAPSHOT", "official pricing/EUR snapshot is not bound")
            require(contract.get("pricing_snapshot_status") == "BOUND_CURRENT_OFFICIAL_SNAPSHOT", "contract pricing status drift")
            require(contract.get("pricing_snapshot_sha256") == sha256(PRICING), "pricing snapshot SHA drift")

    validate_status(contract, mode=mode)
    print("R11A_CORRECTIVE_R6_IMMUTABLE_IMPLEMENTATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
