#!/usr/bin/env python3
"""R2 compatibility wrapper around the frozen R1 read-only probe engine.

The network, parsing, hashing and no-raw-retention implementation remains the
exact reviewed R1 engine. R2 changes only the frozen contract identity and the
classification of explicitly documented drift/inconclusive probes. The R1
engine is imported by file path and its contract gate is replaced with this
strict R2 gate before its normal CLI is executed.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
R1_ENGINE = ROOT / "research/wallet_copyability/scripts/probe_public_api.py"
EXPECTED_ORIGINS = {
    "https://api.hyperliquid.xyz",
    "https://hl-mainnet-node-data.s3.amazonaws.com",
    "https://hyperliquid-archive.s3.amazonaws.com",
}
EXPECTED_DEGRADED = {
    "P003_MASTER_USER_ROLE",
    "P004_MASTER_SUBACCOUNTS",
    "P005_SUBACCOUNT_USER_ROLE",
    "P014_VAULT_FILLS_BY_TIME_RECENT_24H",
    "P016_NODE_FILL_ARCHIVE_LISTING",
    "P017_MARKET_DATA_ARCHIVE_LISTING",
    "P018_ASSET_CTX_ARCHIVE_LISTING",
}


def load_r1_engine():
    spec = importlib.util.spec_from_file_location("hyperliquid_probe_r1_engine", R1_ENGINE)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load frozen R1 engine")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_contract_r2(contract: dict[str, Any], source_register: dict[str, Any]) -> None:
    if contract.get("schema_version") != "1.1":
        raise RuntimeError("R2 contract schema drift")
    if contract.get("contract_id") != "HYPERLIQUID_PUBLIC_TECHNICAL_PROBE_CONTRACT_R2":
        raise RuntimeError("R2 contract identity drift")
    if contract.get("study_id") != "WALLET-COPYABILITY-STUDY-001":
        raise RuntimeError("study identity drift")
    if contract.get("probe_id") != "HL-PUBLIC-PROBE-001R2":
        raise RuntimeError("R2 probe identity drift")
    if contract.get("status") != "FROZEN_PRE_EXECUTION_READ_ONLY":
        raise RuntimeError("R2 contract is not frozen")
    if set(contract.get("terminal_statuses", [])) != {
        "PUBLIC_PROBE_PASS",
        "PUBLIC_PROBE_PARTIAL",
        "PUBLIC_PROBE_FAIL",
    }:
        raise RuntimeError("terminal status set drift")
    if set(contract.get("allowed_origins", [])) != EXPECTED_ORIGINS:
        raise RuntimeError("network-origin allowlist drift")

    execution = contract.get("execution_boundary", {})
    if execution.get("read_only") is not True:
        raise RuntimeError("R2 is not read-only")
    for key, value in execution.items():
        if key != "read_only" and value is not False:
            raise RuntimeError(f"execution capability opened: {key}")
    if any(value is not False for value in contract.get("authorizations", {}).values()):
        raise RuntimeError("research authorization opened")
    if contract.get("retention_policy", {}).get("raw_response_bytes_retained") is not False:
        raise RuntimeError("raw response retention opened")
    if contract.get("retention_policy", {}).get("response_values_retained") is not False:
        raise RuntimeError("response-value retention opened")

    probes = contract.get("probes")
    if not isinstance(probes, list) or len(probes) != 18:
        raise RuntimeError("R2 must contain exactly 18 probes")
    probe_ids = [probe.get("probe_id") for probe in probes]
    if probe_ids != sorted(probe_ids) or len(set(probe_ids)) != 18:
        raise RuntimeError("R2 probe identities are not unique and ordered")
    observed_degraded = {
        probe["probe_id"]
        for probe in probes
        if probe.get("failure_impact") == "DEGRADE"
    }
    if observed_degraded != EXPECTED_DEGRADED:
        raise RuntimeError("R2 degraded-probe set drift")
    for probe in probes:
        if probe.get("method") not in {"GET", "POST"}:
            raise RuntimeError(f"unsupported method: {probe.get('probe_id')}")
        if probe.get("failure_impact") not in {"FAIL", "DEGRADE"}:
            raise RuntimeError(f"invalid failure impact: {probe.get('probe_id')}")
        if probe.get("failure_impact") == "DEGRADE" and probe.get("required") is not False:
            raise RuntimeError(f"degraded probe marked required: {probe.get('probe_id')}")
        url = probe.get("url")
        if url is not None and module.origin_of(url) not in EXPECTED_ORIGINS:
            raise RuntimeError(f"probe origin outside allowlist: {probe.get('probe_id')}")

    if source_register.get("study_id") != "WALLET-COPYABILITY-STUDY-001":
        raise RuntimeError("source-register study drift")
    if any(value is not False for value in source_register.get("authorizations", {}).values()):
        raise RuntimeError("source-register authorization opened")


module = load_r1_engine()
module.validate_contract = validate_contract_r2


if __name__ == "__main__":
    raise SystemExit(module.main())
