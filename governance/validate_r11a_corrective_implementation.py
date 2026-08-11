#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
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

REQUIRED_MODULES = (
    "__init__.py",
    "activity.py",
    "artifact_r3.py",
    "canonical.py",
    "context.py",
    "entrypoint.py",
    "identity.py",
    "index_r3.py",
    "limits.py",
    "lz4stream.py",
    "materialize_r3.py",
    "network.py",
    "parser.py",
    "pricing.py",
    "runner.py",
    "runtime.py",
    "selection.py",
    "storage.py",
    "taxonomy_r3.py",
)


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path} root must be object")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_ast(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "hash":
            raise AssertionError(f"Python hash() is forbidden in {path}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "quantize":
                raise AssertionError(f"Decimal.quantize is forbidden in {path}")
    forbidden = (
        "drop_duplicates",
        "ignore_errors=True",
        "first_seen_wins",
        "last_seen_wins",
        "blind_dedup",
    )
    for token in forbidden:
        require(token not in text, f"forbidden corrective implementation token {token} in {path}")
    network_tokens = ("urllib.request", "socket", "boto3", "requests", "httpx")
    if path.name not in {"network.py"}:
        for token in network_tokens:
            require(token not in text, f"network capability outside network.py: {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--approval-eligible", action="store_true")
    arguments = parser.parse_args()

    contract = load(CONTRACT)
    status = load(STATUS)
    findings = load(FINDINGS)
    pricing = load(PRICING)

    require(contract["implementation_id"] == "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-CORRECTIVE-R3", "implementation ID drift")
    require(contract["diagnostic_id"] == "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-001", "diagnostic ID drift")
    require(contract["parent_main_commit"] == "57566456624eb758049aa7687bdb7b8a2844c91d", "containment parent drift")
    require(contract["parent_preregistration_merge_commit"] == "5103c846be8a53732d8559a281ac8b57ce4d7aac", "preregistration lineage drift")
    require(contract["red_finding_count"] == 21, "red finding count drift")
    require(findings["verdict"] == "RED", "authoritative review verdict drift")
    require(len(findings["findings"]) == 21, "authoritative finding set incomplete")
    require(
        {row["finding_id"] for row in findings["findings"]}
        == {f"R11A-RED-{index:03d}" for index in range(1, 22)},
        "authoritative finding identifiers drift",
    )
    require(status["status"] in {
        "CORRECTIVE_IMPLEMENTATION_IN_PROGRESS_NO_EXECUTION",
        "CORRECTIVE_IMPLEMENTATION_SEALED_APPROVAL_ELIGIBLE_NO_EXECUTION",
    }, "corrective status drift")

    for mapping_name in (
        "runtime_authority",
        "downstream_authorizations",
        "trading_authorizations",
    ):
        require(all(value is False for value in contract[mapping_name].values()), f"{mapping_name} opened")
    require(all(value is False for value in status["current_runtime_authority"].values()), "status runtime authority opened")
    require(all(value is False for value in status["downstream_authorizations"].values()), "status downstream authority opened")
    require(all(value is False for value in status["trading_authorizations"].values()), "status trading authority opened")
    for key in (
        "owner_approval_present",
        "workflow_installed_under_dot_github",
        "successor_role_created",
        "role_attestation_present",
        "sts_preflight_evidence_present",
        "execution_release_present",
        "canonical_activation_present",
        "single_workflow_dispatch_authorized",
        "rerun_authorized",
        "r11_closed",
        "r12_ready",
    ):
        require(contract[key] is False, f"forbidden current-stage flag opened: {key}")
    require(contract["network_requests_executed_by_implementation"] == 0, "implementation performed network request")
    require(contract["aws_iam_mutations_executed_by_implementation"] == 0, "implementation mutated IAM")
    require(contract["diagnostic_rows_created_by_implementation"] == 0, "implementation created diagnostic rows")
    require(contract["wallet_feature_rows_created_by_implementation"] == 0, "implementation created wallet features")
    require(contract["empirical_result"] is None, "implementation contract contains empirical result")

    require(not INSTALLED_WORKFLOW.exists(), "R11A workflow is installed before approval")
    require(not APPROVAL_ROOT.exists(), "R11A owner approval exists in corrective implementation stage")
    require(not RUNTIME_ROOT.exists(), "R11A runtime release exists in corrective implementation stage")
    require(not EVIDENCE_ROOT.exists(), "R11A execution evidence exists in corrective implementation stage")

    for name in REQUIRED_MODULES:
        path = CORRECTIVE / name
        require(path.is_file(), f"missing corrective module: {name}")
        check_ast(path)

    # Only the direct HTTPS transport may import urllib.request.
    network_source = (CORRECTIVE / "network.py").read_text(encoding="utf-8")
    require("urllib.request" in network_source, "network.py lacks the reviewed direct HTTPS transport")
    require("retry" not in network_source.lower() or "without retry" in network_source.lower(), "network transport contains retry logic")

    if contract["implementation_sealed"]:
        hashes = contract["implementation_file_hashes"]
        require(isinstance(hashes, dict) and hashes, "sealed implementation lacks file hashes")
        for relative, digest in hashes.items():
            path = ROOT / relative
            require(path.is_file(), f"sealed file absent: {relative}")
            require(sha256(path) == digest, f"sealed file hash mismatch: {relative}")

    if arguments.approval_eligible or contract["owner_approval_eligible"]:
        require(contract["status"] == "CORRECTIVE_IMPLEMENTATION_SEALED_APPROVAL_ELIGIBLE_NO_EXECUTION", "approval eligibility status drift")
        require(contract["implementation_sealed"] is True, "approval eligibility requires sealed implementation")
        require(contract["owner_approval_eligible"] is True, "owner approval eligibility flag is false")
        closed = contract["red_findings_closed"]
        require(set(closed) == {f"R11A-RED-{index:03d}" for index in range(1, 22)}, "closed finding set incomplete")
        require(all(value is True for value in closed.values()), "one or more RED findings remain open")
        require(pricing["status"] == "BOUND_CURRENT_OFFICIAL_SNAPSHOT", "current official pricing/EUR snapshot is not bound")
        workflow_path = ROOT / contract["workflow_candidate_path"]
        require(workflow_path.is_file(), "sealed workflow candidate is absent")
        require(sha256(workflow_path) == contract["workflow_candidate_sha256"], "workflow candidate hash mismatch")
    else:
        require(contract["owner_approval_eligible"] is False, "draft implementation cannot be approval eligible")
        require(pricing["status"] == contract["pricing_snapshot_status"], "pricing status and contract differ")

    print("R11A_CORRECTIVE_IMPLEMENTATION_VALID_INERT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
