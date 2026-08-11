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
INSTALLED_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic.yml"
APPROVAL_ROOT = BASE / "r11a_approval"
RUNTIME_ROOT = BASE / "r11a_runtime"
EVIDENCE_ROOT = BASE / "r11a_evidence"

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
    "governance/validate_r11a_corrective_implementation_r5.py",
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


class ValidationError(AssertionError):
    pass


def load(path: Path) -> dict:
    def pairs(rows: list[tuple[str, object]]) -> dict:
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-inert-stage", action="store_true")
    parser.add_argument("--canonical-bytes", action="store_true")
    arguments = parser.parse_args()
    require(
        arguments.current_inert_stage != arguments.canonical_bytes,
        "select exactly one validation mode",
    )

    contract = load(CONTRACT)
    status = load(STATUS)
    findings = load(FINDINGS)
    pricing = load(PRICING)
    require(
        contract["implementation_id"]
        == "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-CORRECTIVE-R3",
        "implementation ID drift",
    )
    require(
        contract["diagnostic_id"]
        == "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-001",
        "diagnostic ID drift",
    )
    require(
        contract["parent_main_commit"]
        == "57566456624eb758049aa7687bdb7b8a2844c91d",
        "containment parent drift",
    )
    require(
        findings["verdict"] == "RED" and len(findings["findings"]) == 21,
        "authoritative RED finding set drift",
    )
    require(
        all(value is False for value in contract["runtime_authority"].values()),
        "immutable implementation opens runtime authority",
    )
    require(
        all(value is False for value in contract["downstream_authorizations"].values()),
        "immutable implementation opens downstream authority",
    )
    require(
        all(value is False for value in contract["trading_authorizations"].values()),
        "immutable implementation opens trading authority",
    )
    require(
        contract["network_requests_executed_by_implementation"] == 0,
        "implementation performed network request",
    )
    require(
        contract["aws_iam_mutations_executed_by_implementation"] == 0,
        "implementation mutated IAM",
    )
    require(
        contract["diagnostic_rows_created_by_implementation"] == 0,
        "implementation created diagnostic result",
    )
    require(
        contract["wallet_feature_rows_created_by_implementation"] == 0,
        "implementation created wallet feature",
    )
    require(contract["empirical_result"] is None, "implementation contains empirical result")
    require(
        contract["r11_closed"] is False and contract["r12_ready"] is False,
        "implementation overclaims lifecycle closure",
    )

    for relative in EXECUTION_GRAPH:
        path = CORRECTIVE / relative
        require(path.is_file(), f"execution graph file is absent: {relative}")
        if path.suffix == ".py":
            validate_ast(path)
    require(
        "urllib.request" in (CORRECTIVE / "network.py").read_text(encoding="utf-8"),
        "direct HTTPS transport is absent",
    )

    if arguments.current_inert_stage:
        require(
            contract["status"]
            in {
                "CORRECTIVE_IMPLEMENTATION_IN_PROGRESS_NO_EXECUTION",
                "CORRECTIVE_IMPLEMENTATION_SEALED_AWAITING_CLEAN_CONTEXT_REVIEW_NO_EXECUTION",
                "CORRECTIVE_IMPLEMENTATION_SEALED_APPROVAL_ELIGIBLE_NO_EXECUTION",
            },
            "current inert status drift",
        )
        require(not INSTALLED_WORKFLOW.exists(), "workflow installed during inert stage")
        require(not APPROVAL_ROOT.exists(), "approval present during inert stage")
        require(not RUNTIME_ROOT.exists(), "runtime overlay present during inert stage")
        require(not EVIDENCE_ROOT.exists(), "execution evidence present during inert stage")
    else:
        require(
            contract["status"]
            == "CORRECTIVE_IMPLEMENTATION_SEALED_APPROVAL_ELIGIBLE_NO_EXECUTION",
            "canonical bytes are not approval-eligible sealed implementation",
        )
        require(contract["implementation_sealed"] is True, "implementation is not sealed")
        require(contract["owner_approval_eligible"] is True, "owner approval is not eligible")
        closed = contract["red_findings_closed"]
        require(
            set(closed) == {f"R11A-RED-{index:03d}" for index in range(1, 22)},
            "RED finding closure set incomplete",
        )
        require(all(value is True for value in closed.values()), "one or more RED findings remain open")
        require(
            pricing["status"] == "BOUND_CURRENT_OFFICIAL_SNAPSHOT",
            "official pricing/EUR snapshot is not bound",
        )
        hashes = contract["implementation_file_hashes"]
        required_paths = {
            f"research/archive_inventory/r11a_corrective/{relative}"
            for relative in EXECUTION_GRAPH
        } | set(SEALED_GOVERNANCE_FILES)
        require(
            isinstance(hashes, dict) and set(hashes) == required_paths,
            "sealed implementation hash set differs from exact execution graph",
        )
        for relative, digest in hashes.items():
            path = ROOT / relative
            require(path.is_file(), f"sealed path absent: {relative}")
            require(sha256(path) == digest, f"sealed path hash drift: {relative}")
        require(
            contract["workflow_candidate_path"]
            == "research/archive_inventory/r11a_corrective/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic-r6.yml",
            "workflow candidate path drift",
        )
        workflow_path = ROOT / contract["workflow_candidate_path"]
        require(
            contract["workflow_candidate_sha256"] == sha256(workflow_path),
            "workflow candidate SHA-256 drift",
        )
    print("R11A_CORRECTIVE_R5_IMMUTABLE_IMPLEMENTATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
