from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
CORRECTIVE = BASE / "r11a_corrective"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-identity-r11a"
WORKFLOW_NAME = "Hyperliquid Archive R11A Identity Boundary Diagnostic"
WORKFLOW_PATH = ROOT / ".github/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic.yml"
CANDIDATE_PATH = CORRECTIVE / "workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic.yml"
SELECTION_PATH = BASE / "r11/R11_72H_SELECTION.json"
IMPLEMENTATION_CONTRACT = CORRECTIVE / "R11A_CORRECTIVE_IMPLEMENTATION_CONTRACT.json"
PRICING_SNAPSHOT = CORRECTIVE / "R11A_PRICING_EUR_SNAPSHOT.json"
APPROVAL_DIR = BASE / "r11a_approval"
ROLE_DIR = BASE / "r11a_role_attestation"
PREFLIGHT_DIR = BASE / "r11a_role_preflight"
INSTALL_DIR = BASE / "r11a_workflow_installation"
RUNTIME_DIR = BASE / "r11a_runtime"
EVIDENCE_DIR = BASE / "r11a_evidence"


class StageValidationError(AssertionError):
    pass


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StageValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value: str) -> Any:
    raise StageValidationError(f"non-finite JSON constant: {value}")


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise StageValidationError(f"invalid strict JSON: {path}") from exc
    if not isinstance(value, dict):
        raise StageValidationError(f"JSON root must be object: {path}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise StageValidationError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_sha256(value: object, label: str) -> str:
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None, f"{label} is not SHA-256")
    return value


def require_commit(value: object, label: str) -> str:
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None, f"{label} is not full Git commit")
    return value


def require_all_false(mapping: object, label: str) -> None:
    require(isinstance(mapping, dict), f"{label} must be object")
    require(all(value is False for value in mapping.values()), f"{label} contains opened authority")


def implementation() -> dict[str, Any]:
    value = load(IMPLEMENTATION_CONTRACT)
    require(value["status"] == "CORRECTIVE_IMPLEMENTATION_SEALED_APPROVAL_ELIGIBLE_NO_EXECUTION", "implementation is not approval-eligible sealed R3")
    require(value["implementation_sealed"] is True, "implementation is not sealed")
    require(value["owner_approval_eligible"] is True, "owner approval is not eligible")
    require_all_false(value["runtime_authority"], "implementation runtime authority")
    require_all_false(value["downstream_authorizations"], "implementation downstream authority")
    require_all_false(value["trading_authorizations"], "implementation trading authority")
    return value


def pricing() -> dict[str, Any]:
    value = load(PRICING_SNAPSHOT)
    require(value["status"] == "BOUND_CURRENT_OFFICIAL_SNAPSHOT", "pricing snapshot is not current and bound")
    return value


def exact_selection() -> dict[str, Any]:
    value = load(SELECTION_PATH)
    targets = value.get("exact_targets")
    require(isinstance(targets, list) and len(targets) == 72, "selection must contain exact 72 targets")
    return value
