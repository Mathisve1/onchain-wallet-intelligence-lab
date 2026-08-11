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
    "entrypoint_r3.py",
    "identity.py",
    "index_r3.py",
    "limits.py",
    "lz4stream.py",
    "materialize_r3.py",
    "network.py",
    "parser.py",
    "pricing.py",
    "runner_r3.py",
    "runtime.py",
    "selection.py",
    "storage.py",
    "taxonomy_r3.py",
    "workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic-r4.yml",
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
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=constant)
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
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "hash":
            raise ValidationError(f"Python hash() is forbidden in {path}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "quantize":
            raise ValidationError(f"Decimal.quantize is forbidden in {path}")
    for token in ("drop_duplicates", "ignore_errors=True", "first_seen_wins", "last_seen_wins"):
        require(token not in text, f"forbidden implementation token {token}: {path}")
    if path.name != "network.py":
        for token in ("urllib.request", "boto3", "requests", "httpx", "socket"):
            require(token not in text, f"network capability outside network.py: {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-inert-stage", action="store_true")
    parser.add_argument("--canonical-bytes", action="store_true")
    arguments = parser.parse_args()
    require(arguments.current_inert_stage != arguments.canonical_bytes, "select exactly one validation mode")

    contract = load(CONTRACT)
    status = load(STATUS)
    findings = load(FINDINGS)
    pricing = load(PRICING)
    require(contract["implementation_id"] == "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-CORRECTIVE-R3", "implementation ID drift")
    require(contract["diagnostic_id"] == "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-001", "diagnostic ID drift")
    require(contract["parent_main_commit"] == "57566456624eb758049aa7687bdb7b8a2844c91d", "containment parent drift")
    require(findings["verdict"] == "RED" and len(findings["findings"]) == 21, "authoritative RED finding set drift")
    require(all(value is False for value in contract["runtime_authority"].values()), "immutable implementation opens runtime authority")
    require(all(value is False for value in contract["downstream_authorizations"].values()), "immutable implementation opens downstream authority")
    require(all(value is False for value in contract["trading_authorizations"].values()), "immutable implementation opens trading authority")
    require(contract["network_requests_executed_by_implementation"] == 0, "implementation performed network request")
    require(contract["aws_iam_mutations_executed_by_implementation"] == 0, "implementation mutated IAM")
    require(contract["diagnostic_rows_created_by_implementation"] == 0, "implementation created diagnostic result")
    require(contract["wallet_feature_rows_created_by_implementation"] == 0, "implementation created wallet feature")
    require(contract["empirical_result"] is None, "implementation contract contains empirical result")
    require(contract["r11_closed"] is False and contract["r12_ready"] is False, "implementation overclaims lifecycle closure")

    for relative in EXECUTION_GRAPH:
        path = CORRECTIVE / relative
        require(path.is_file(), f"sealed execution graph file is absent: {relative}")
        if path.suffix == ".py":
            validate_ast(path)
    require("urllib.request" in (CORRECTIVE / "network.py").read_text(encoding="utf-8"), "direct HTTPS transport is absent")

    if arguments.current_inert_stage:
        require(contract["status"] in {
            "CORRECTIVE_IMPLEMENTATION_IN_PROGRESS_NO_EXECUTION",
            "CORRECTIVE_IMPLEMENTATION_SEALED_APPROVAL_ELIGIBLE_NO_EXECUTION",
        }, "current inert status drift")
        require(not INSTALLED_WORKFLOW.exists(), "workflow installed during inert implementation stage")
        require(not APPROVAL_ROOT.exists(), "approval present during inert implementation stage")
        require(not RUNTIME_ROOT.exists(), "runtime overlay present during inert implementation stage")
        require(not EVIDENCE_ROOT.exists(), "execution evidence present during inert implementation stage")
    else:
        require(contract["status"] == "CORRECTIVE_IMPLEMENTATION_SEALED_APPROVAL_ELIGIBLE_NO_EXECUTION", "canonical implementation bytes are not sealed and approval eligible")
        require(contract["implementation_sealed"] is True, "canonical implementation is not sealed")
        require(contract["owner_approval_eligible"] is True, "canonical implementation is not owner-approval eligible")
        closed = contract["red_findings_closed"]
        require(set(closed) == {f"R11A-RED-{index:03d}" for index in range(1,22)}, "RED finding closure set incomplete")
        require(all(value is True for value in closed.values()), "one or more RED findings remain open")
        require(pricing["status"] == "BOUND_CURRENT_OFFICIAL_SNAPSHOT", "official pricing/EUR snapshot is not bound")
        hashes = contract["implementation_file_hashes"]
        require(isinstance(hashes, dict) and set(hashes) >= {f"research/archive_inventory/r11a_corrective/{relative}" for relative in EXECUTION_GRAPH}, "sealed execution graph hashes incomplete")
        for relative, digest in hashes.items():
            path = ROOT / relative
            require(path.is_file(), f"sealed path absent: {relative}")
            require(sha256(path) == digest, f"sealed path hash drift: {relative}")
        # Later approval, installation and runtime overlays are deliberately outside
        # this immutable byte validator and must pass their own stage validators.
    print("R11A_CORRECTIVE_R3_IMMUTABLE_IMPLEMENTATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
