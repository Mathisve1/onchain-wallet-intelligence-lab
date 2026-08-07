#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from regenerate_manifest import render_manifest

ROOT = Path(__file__).resolve().parents[1]
SHA_ROW = re.compile(r"^([0-9a-f]{64})  (.+)$")
PROBE_ROOT = ROOT / "research/wallet_copyability/probe_r1"
EVIDENCE_ROOT = PROBE_ROOT / "evidence"
REQUIRED_PROBE_PATHS = {
    ".github/workflows/hyperliquid-public-probe-r1.yml",
    "research/wallet_copyability/probe_r1/ATTESTATION_TEMPLATE.json",
    "research/wallet_copyability/probe_r1/PENDING_EVIDENCE.json",
    "research/wallet_copyability/probe_r1/PROBE_CONTRACT.json",
    "research/wallet_copyability/probe_r1/contract.py",
    "research/wallet_copyability/probe_r1/http_client.py",
    "research/wallet_copyability/probe_r1/probe.py",
    "research/wallet_copyability/probe_r1/validate_attestation.py",
    "research/wallet_copyability/probe_r1/validate_attestation_strict.py",
    "research/wallet_copyability/probe_r1/validate_evidence.py",
}
FORBIDDEN_PREMERGE_PATHS = {
    "research/wallet_copyability/probe_r1/evidence/HL-PUBLIC-PROBE-001R1-ATTESTATION.json",
    "research/archive_inventory",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"REPOSITORY_VALIDATION_FAIL: {message}")


def load_json(relative: str) -> dict:
    value = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON root not object: {relative}")
    return value


def validate_manifest() -> int:
    manifest = ROOT / "governance/REPOSITORY_MANIFEST.sha256"
    observed_manifest = manifest.read_text(encoding="utf-8")
    expected_manifest = render_manifest(ROOT)
    if observed_manifest != expected_manifest:
        print("EXPECTED_MANIFEST_BEGIN")
        print(expected_manifest, end="")
        print("EXPECTED_MANIFEST_END")
        require(False, "repository manifest is incomplete or stale")

    seen: set[str] = set()
    for line in observed_manifest.splitlines():
        if not line or line.startswith("#"):
            continue
        match = SHA_ROW.fullmatch(line)
        require(match is not None, f"invalid manifest row: {line}")
        expected, rel = match.groups()
        require(rel not in seen, f"duplicate manifest path: {rel}")
        seen.add(rel)
        path = ROOT / rel
        require(path.is_file(), f"missing manifest target: {rel}")
        observed = hashlib.sha256(path.read_bytes()).hexdigest()
        require(observed == expected, f"manifest mismatch: {rel}")
    return len(seen)


def validate_parent_contract() -> None:
    contract = load_json(
        "research/wallet_copyability/DATA_CONTRACT.json"
    )
    require(
        contract["market_data_ingested"] is False,
        "market-data gate opened",
    )
    require(
        contract["empirical_result"] is None,
        "empirical result created",
    )
    require(
        contract["execution_boundary"]["read_only"] is True,
        "read-only gate disabled",
    )
    require(
        all(
            value is False
            for value in contract["authorizations"].values()
        ),
        "authorization opened",
    )


def validate_probe_boundary() -> None:
    for relative in REQUIRED_PROBE_PATHS:
        require((ROOT / relative).is_file(), f"missing probe path: {relative}")
    for relative in FORBIDDEN_PREMERGE_PATHS:
        require(
            not (ROOT / relative).exists(),
            f"premature successor/evidence path exists: {relative}",
        )
    require(
        not any(EVIDENCE_ROOT.glob("run-*")),
        "premature workflow run directory exists",
    )

    contract = load_json(
        "research/wallet_copyability/probe_r1/PROBE_CONTRACT.json"
    )
    require(
        contract["status"] == "FROZEN_READ_ONLY_PUBLIC_PROBE",
        "probe contract status drift",
    )
    require(
        contract["market_data_ingested"] is False
        and contract["empirical_result"] is None,
        "probe contract creates market result",
    )
    require(
        all(
            value is False
            for value in contract["authorizations"].values()
        ),
        "probe contract opens authorization",
    )

    pending = load_json(
        "research/wallet_copyability/probe_r1/PENDING_EVIDENCE.json"
    )
    require(
        pending["status"] == "PENDING_PUBLIC_PROBE_R1"
        and pending["observations"] == [],
        "pending evidence drift",
    )
    for key in (
        "output_sha256",
        "reviewed_commit",
        "workflow_run_id",
        "workflow_job_id",
        "artifact_id",
        "artifact_digest",
    ):
        require(pending[key] is None, f"pending evidence invents {key}")

    attestation = load_json(
        "research/wallet_copyability/probe_r1/ATTESTATION_TEMPLATE.json"
    )
    require(
        attestation["status"] == "PENDING_EXACT_WORKFLOW_EVIDENCE",
        "attestation template is not pending",
    )
    require(
        attestation["next_gate"]
        == "DO_NOT_OPEN_ARCHIVE_INVENTORY_UNTIL_EXACT_EVIDENCE_AND_REVIEW_PASS",
        "attestation template opens next gate",
    )

    project_state = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
    require("`PRE_DATA`" in project_state, "project state left PRE_DATA")
    require(
        "`PREREGISTERED_NO_MARKET_RELEASE`" in project_state,
        "project state prematurely promoted experiment",
    )


def main() -> int:
    manifest_files = validate_manifest()
    validate_parent_contract()
    validate_probe_boundary()
    print(f"REPOSITORY_MANIFEST_FILES:{manifest_files}")
    print("REPOSITORY_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
