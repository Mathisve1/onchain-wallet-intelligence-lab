from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "research/archive_inventory/INVENTORY_CONTRACT.json"
DATASET_PATH = ROOT / "research/archive_inventory/DATASET_REGISTER.json"

AUTHORIZATION_FIELDS = {
    "integration_authorized",
    "paper_authorized",
    "shadow_authorized",
    "live_authorized",
    "leverage_authorized",
    "capital_allocation_authorized",
}


class ContractError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ContractError(f"JSON root must be object: {path}")
    return value


def load_dataset_register(path: Path = DATASET_PATH) -> dict[str, Any]:
    register = _load(path)
    rows = register.get("datasets")
    if not isinstance(rows, list) or len(rows) != 7:
        raise ContractError("dataset register must contain exactly seven families")
    seen: set[tuple[str, str]] = set()
    names: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ContractError("dataset row must be object")
        family = row.get("family")
        bucket = row.get("bucket")
        prefix = row.get("prefix")
        if not all(isinstance(v, str) and v for v in (family, bucket, prefix)):
            raise ContractError("dataset identity fields must be nonempty strings")
        if not prefix.endswith("/") or prefix.startswith("/"):
            raise ContractError(f"invalid dataset prefix: {prefix}")
        pair = (bucket, prefix)
        if pair in seen or family in names:
            raise ContractError("duplicate dataset family or bucket/prefix")
        seen.add(pair)
        names.add(family)
    return register


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = _load(path)
    if contract.get("inventory_id") != "HL-ARCHIVE-INVENTORY-001":
        raise ContractError("inventory identity drift")
    if contract.get("status") != "PREREGISTERED_METADATA_ONLY_NO_EXECUTION":
        raise ContractError("inventory status drift")
    execution = contract.get("execution")
    if not isinstance(execution, dict) or any(execution.values()):
        raise ContractError("execution gate opened")
    if contract.get("allowed_future_operation_after_separate_approval") != "ListObjectsV2":
        raise ContractError("future operation allowlist drift")
    required_forbidden = {
        "GetObject", "HeadObject", "GetObjectAttributes", "SelectObjectContent",
        "RestoreObject", "PutObject", "DeleteObject", "DeleteObjects", "CopyObject",
    }
    if set(contract.get("forbidden_operations", [])) != required_forbidden:
        raise ContractError("forbidden operation set drift")
    expected_canary = {
        "authorized": False,
        "max_total_list_requests": 300,
        "max_pages_per_family": 40,
        "max_total_entries": 250000,
        "max_total_response_bytes": 268435456,
        "max_runtime_seconds": 900,
        "max_retries_per_request": 1,
    }
    if contract.get("proposed_canary") != expected_canary:
        raise ContractError("canary guard drift")
    cost = contract.get("cost_gate")
    if (
        not isinstance(cost, dict)
        or cost.get("human_approval_required") is not True
        or cost.get("paid_request_authorized") is not False
        or cost.get("maximum_one_time_budget_eur") is not None
        or cost.get("maximum_monthly_budget_eur") != 0
    ):
        raise ContractError("cost gate opened or drifted")
    if contract.get("market_data_ingested") is not False or contract.get("empirical_result") is not None:
        raise ContractError("market result created")
    auth = contract.get("authorizations")
    if set(auth or {}) != AUTHORIZATION_FIELDS or any(auth.values()):
        raise ContractError("trading/execution authorization opened")
    load_dataset_register()
    return contract
