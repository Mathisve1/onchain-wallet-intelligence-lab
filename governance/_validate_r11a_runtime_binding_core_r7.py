#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "research/archive_inventory"
CORRECTIVE = ARCHIVE / "r11a_corrective"
RUNTIME = ARCHIVE / "r11a_runtime"

DIAGNOSTIC_ID = "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-002"
IMPLEMENTATION_ID = "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-CORRECTIVE-R7"
WORKFLOW_NAME = "Hyperliquid Archive R11A Identity Boundary Diagnostic"
WORKFLOW_FILE = "hyperliquid-archive-r11a-identity-boundary-diagnostic.yml"
CANDIDATE_RELATIVE = (
    "research/archive_inventory/r11a_corrective/workflows/"
    "hyperliquid-archive-r11a-identity-boundary-diagnostic-r7.yml"
)
INSTALLED_RELATIVE = f".github/workflows/{WORKFLOW_FILE}"
BINDING_RELATIVE = "research/archive_inventory/r11a_runtime/R11A_RUNTIME_BINDING_R7.json"
BINDING = ROOT / BINDING_RELATIVE

IMPLEMENTATION_RELATIVE = (
    "research/archive_inventory/r11a_corrective/"
    "R11A_CORRECTIVE_IMPLEMENTATION_CONTRACT_R7.json"
)
PRICING_RELATIVE = (
    "research/archive_inventory/r11a_corrective/R11A_PRICING_EUR_SNAPSHOT.json"
)
APPROVAL_JSON_RELATIVE = (
    "research/archive_inventory/r11a_approval/"
    "APPROVE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001.json"
)
APPROVAL_TEXT_RELATIVE = (
    "research/archive_inventory/r11a_approval/"
    "APPROVE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001.txt"
)
ROLE_ATTESTATION_RELATIVE = (
    "research/archive_inventory/r11a_role_attestation/"
    "R11A_SUCCESSOR_ROLE_OPERATOR_ATTESTATION.json"
)
PREFLIGHT_EVIDENCE_RELATIVE = (
    "research/archive_inventory/r11a_role_preflight/"
    "R11A_SUCCESSOR_ROLE_STS_PREFLIGHT_ATTESTATION.json"
)
PREFLIGHT_CONSUMPTION_RELATIVE = (
    "research/archive_inventory/r11a_role_preflight/"
    "R11A_STS_PREFLIGHT_RELEASE_CONSUMPTION.json"
)
INSTALLATION_RELATIVE = (
    "research/archive_inventory/r11a_workflow_installation/"
    "R11A_WORKFLOW_INSTALLATION_CONTRACT.json"
)
RELEASE_RELATIVE = "research/archive_inventory/r11a_runtime/R11A_EXECUTION_RELEASE.json"
RELEASE_DIGEST_RELATIVE = (
    "research/archive_inventory/r11a_runtime/R11A_EXECUTION_RELEASE.sha256"
)
ACTIVATION_RELATIVE = (
    "research/archive_inventory/r11a_runtime/R11A_CANONICAL_ACTIVATION.json"
)
SELECTION_RELATIVE = "research/archive_inventory/r11/R11_72H_SELECTION.json"
PRIOR_RESULT_RELATIVE = (
    "research/archive_inventory/r11_evidence/run-31436753081/r11-result.json"
)
TRUST_POLICY_RELATIVE = (
    "research/archive_inventory/r11a_corrective/R11A_OIDC_TRUST_POLICY.json"
)
PERMISSION_POLICY_RELATIVE = (
    "research/archive_inventory/r11a_corrective/R11A_PERMISSION_POLICY.json"
)

TRANSITIVE_CODE_PATHS = (
    "governance/_validate_r11a_runtime_binding_core_r7.py",
    "governance/seal_r11a_corrective_r7.py",
    "governance/seal_r11a_v2_preregistration.py",
    "governance/validate_r11a_runtime_binding_r7.py",
    "governance/validate_r11a_execution_artifact_r7.py",
    "governance/validate_r11a_v2_bindings.py",
    "governance/validate_r11a_v2_preregistration.py",
    "research/archive_inventory/r11a_corrective/_artifact_contract_core_r7.py",
    "research/archive_inventory/r11a_corrective/_artifact_core_r7.py",
    "research/archive_inventory/r11a_corrective/_artifact_schema_core_r7.py",
    "research/archive_inventory/r11a_corrective/_runner_core_r7.py",
    "research/archive_inventory/r11a_corrective/_taxonomy_contract_core_r7.py",
    "research/archive_inventory/r11a_corrective/_taxonomy_core_r7.py",
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
    "research/archive_inventory/r11a/R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_PREREGISTRATION.json",
    "research/archive_inventory/r11a_v2/R11A_CORRECTIVE_PREREGISTRATION_AMENDMENT.json",
    "research/archive_inventory/r11a_v2/R11A_CORRECTIVE_PREREGISTRATION_AMENDMENT.md",
    "research/archive_inventory/r11a_v2/R11A_V2_PREREGISTRATION_BINDINGS.json",
    "research/archive_inventory/r11a_v2/R11A_V2_STATUS.json",
    "research/archive_inventory/r11a_v2/README.md",
    "governance/R11A_V2_REVIEW_FINDINGS.md",
    "tests/test_archive_inventory_r11a_v2_bindings.py",
    "tests/test_archive_inventory_r11a_v2_preregistration.py",
)

REQUIRED_BOUND_PATHS = tuple(
    sorted(
        {
            CANDIDATE_RELATIVE,
            INSTALLED_RELATIVE,
            IMPLEMENTATION_RELATIVE,
            PRICING_RELATIVE,
            APPROVAL_JSON_RELATIVE,
            APPROVAL_TEXT_RELATIVE,
            ROLE_ATTESTATION_RELATIVE,
            PREFLIGHT_EVIDENCE_RELATIVE,
            PREFLIGHT_CONSUMPTION_RELATIVE,
            INSTALLATION_RELATIVE,
            RELEASE_RELATIVE,
            RELEASE_DIGEST_RELATIVE,
            ACTIVATION_RELATIVE,
            SELECTION_RELATIVE,
            PRIOR_RESULT_RELATIVE,
            TRUST_POLICY_RELATIVE,
            PERMISSION_POLICY_RELATIVE,
            *TRANSITIVE_CODE_PATHS,
        },
        key=lambda value: value.encode("utf-8"),
    )
)

EXPECTED_RUNTIME_AUTHORITY = {
    "single_manual_main_dispatch": True,
    "workflow_run_attempt_one": True,
    "oidc_successor_role_assumption": True,
    "sts_get_caller_identity": True,
    "requester_pays_exact_72_getobject": True,
    "two_local_decompression_passes": True,
    "diagnostic_processing": True,
    "diagnostic_artifact_retention": True,
    "iam_mutation": False,
    "other_s3_capability": False,
    "rerun": False,
}


class RuntimeBindingError(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeBindingError(message)


def _pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value: str) -> Any:
    raise RuntimeBindingError(f"non-finite JSON constant: {value}")


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeBindingError(f"invalid strict JSON: {path}") from exc
    require(isinstance(value, dict), f"JSON root must be object: {path}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def require_sha256(value: object, label: str) -> str:
    require(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
        f"{label} is not lowercase SHA-256",
    )
    return value


def require_commit(value: object, label: str) -> str:
    require(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None,
        f"{label} is not a full Git commit",
    )
    return value


def require_all_false(value: object, label: str) -> None:
    require(isinstance(value, dict) and bool(value), f"{label} must be nonempty object")
    require(all(observed is False for observed in value.values()), f"{label} opens authority")


def _require_exact_top_level(binding: dict[str, Any]) -> None:
    expected = {
        "schema_version",
        "binding_id",
        "diagnostic_id",
        "implementation_id",
        "status",
        "canonical_commit",
        "workflow_name",
        "workflow_file",
        "candidate_workflow_path",
        "installed_workflow_path",
        "single_use_window_start_utc",
        "bound_files",
        "runtime_authority",
        "downstream_authorizations",
        "trading_authorizations",
        "r11_closed",
        "r12_ready",
    }
    require(set(binding) == expected, "runtime binding top-level schema drift")


def validate(expected_commit: str, run_attempt: int) -> None:
    require_commit(expected_commit, "expected commit")
    require(run_attempt == 1, "runtime binding requires workflow run attempt one")
    require(BINDING.is_file(), "R7 runtime binding is absent")
    binding = load(BINDING)
    _require_exact_top_level(binding)
    require(binding["schema_version"] == "1.0", "runtime binding schema version drift")
    require(
        binding["binding_id"] == "HL-ARCHIVE-R11A-RUNTIME-BINDING-R7-001",
        "runtime binding ID drift",
    )
    require(binding["diagnostic_id"] == DIAGNOSTIC_ID, "diagnostic ID drift")
    require(binding["implementation_id"] == IMPLEMENTATION_ID, "implementation ID drift")
    require(
        binding["status"] == "ACTIVE_FOR_EXACTLY_ONE_CANONICAL_R11A_R7_RUN",
        "runtime binding is not active for exact one run",
    )
    canonical_commit = require_commit(binding["canonical_commit"], "canonical_commit")
    require(canonical_commit == expected_commit, "runtime binding does not bind dispatch commit")
    require(binding["workflow_name"] == WORKFLOW_NAME, "workflow name drift")
    require(binding["workflow_file"] == WORKFLOW_FILE, "workflow file drift")
    require(
        binding["candidate_workflow_path"] == CANDIDATE_RELATIVE,
        "candidate workflow path drift",
    )
    require(
        binding["installed_workflow_path"] == INSTALLED_RELATIVE,
        "installed workflow path drift",
    )
    start = binding["single_use_window_start_utc"]
    require(isinstance(start, str), "single-use window must be text")
    try:
        parsed = datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError as exc:
        raise RuntimeBindingError("single-use window timestamp malformed") from exc
    require(parsed.isoformat().endswith("+00:00"), "single-use window is not UTC")

    bound_files = binding["bound_files"]
    require(isinstance(bound_files, dict), "bound_files must be object")
    observed_paths = tuple(sorted(bound_files, key=lambda value: value.encode("utf-8")))
    require(observed_paths == REQUIRED_BOUND_PATHS, "runtime binding transitive file set drift")
    for relative in REQUIRED_BOUND_PATHS:
        path = ROOT / relative
        require(path.is_file(), f"bound runtime input is absent: {relative}")
        expected = require_sha256(bound_files[relative], f"bound_files[{relative}]")
        require(sha256(path) == expected, f"bound runtime input hash drift: {relative}")

    candidate = ROOT / CANDIDATE_RELATIVE
    installed = ROOT / INSTALLED_RELATIVE
    require(candidate.read_bytes() == installed.read_bytes(), "installed workflow differs from R7 candidate")

    implementation = load(ROOT / IMPLEMENTATION_RELATIVE)
    require(implementation["diagnostic_id"] == DIAGNOSTIC_ID, "implementation diagnostic ID drift")
    require(implementation["implementation_id"] == IMPLEMENTATION_ID, "implementation ID is not R7")
    require(implementation["implementation_sealed"] is True, "R7 implementation is not sealed")
    require(implementation["owner_approval_eligible"] is True, "R7 implementation not approval eligible")
    require(
        implementation["status"] == "CORRECTIVE_R7_IMPLEMENTATION_SEALED_APPROVAL_ELIGIBLE_NO_EXECUTION",
        "R7 implementation status drift",
    )

    pricing = load(ROOT / PRICING_RELATIVE)
    require(
        pricing["status"] == "BOUND_CURRENT_OFFICIAL_SNAPSHOT",
        "pricing snapshot is not current and bound",
    )

    approval = load(ROOT / APPROVAL_JSON_RELATIVE)
    require(
        approval["approval_id"]
        == "APPROVE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001",
        "approval ID drift",
    )
    require(approval["reviewed_commit"] == canonical_commit, "approval does not bind canonical R7 commit")
    require(
        approval["implementation_contract_sha256"] == sha256(ROOT / IMPLEMENTATION_RELATIVE),
        "approval implementation binding drift",
    )
    require(
        approval["approval_text_sha256"] == sha256(ROOT / APPROVAL_TEXT_RELATIVE),
        "approval text binding drift",
    )

    role = load(ROOT / ROLE_ATTESTATION_RELATIVE)
    require(
        role["attestation_id"] == "ATTEST_HL_ARCHIVE_R11A_SUCCESSOR_ROLE_001",
        "role attestation ID drift",
    )
    require(role["existing_r11_role_mutated"] is False, "consumed R11 role mutated")
    require(role["existing_r11_role_reused"] is False, "consumed R11 role reused")
    require(role["trust_policy_sha256"] == sha256(ROOT / TRUST_POLICY_RELATIVE), "trust policy drift")
    require(
        role["permission_policy_sha256"] == sha256(ROOT / PERMISSION_POLICY_RELATIVE),
        "permission policy drift",
    )

    preflight = load(ROOT / PREFLIGHT_EVIDENCE_RELATIVE)
    consumption = load(ROOT / PREFLIGHT_CONSUMPTION_RELATIVE)
    require(preflight["status"] == "R11A_STS_PREFLIGHT_PASS", "STS preflight did not pass")
    require(preflight["s3_http_request_count"] == 0, "STS preflight performed S3 request")
    require(consumption["status"] == "CONSUMED_SUCCESS", "STS preflight release not consumed")
    require(consumption["rerun_authorized"] is False, "STS preflight rerun reopened")

    installation = load(ROOT / INSTALLATION_RELATIVE)
    require(
        installation["status"] == "INSTALLED_AWAITING_SEPARATE_EXECUTION_RELEASE",
        "workflow installation status drift",
    )
    require(installation["workflow_sha256"] == sha256(installed), "installation workflow hash drift")

    release = load(ROOT / RELEASE_RELATIVE)
    detached = (ROOT / RELEASE_DIGEST_RELATIVE).read_text(encoding="ascii").strip()
    require_sha256(detached, "detached release digest")
    require(detached == sha256(ROOT / RELEASE_RELATIVE), "detached release digest mismatch")
    require(
        release["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R11A_RUN",
        "execution release status drift",
    )
    require(release["rerun_authorized"] is False, "execution release opens rerun")
    require(release["release_consumed"] is False, "pre-run release marked consumed")
    require(release["workflow_sha256"] == sha256(installed), "release workflow hash drift")
    require(
        release["validator_sha256"]
        == sha256(ROOT / "governance/validate_r11a_execution_artifact_r7.py"),
        "release artifact validator hash drift",
    )
    require(release["selection_sha256"] == sha256(ROOT / SELECTION_RELATIVE), "release selection drift")

    activation = load(ROOT / ACTIVATION_RELATIVE)
    require(
        activation["status"] == "ACTIVATED_FOR_EXACTLY_ONE_CANONICAL_R11A_RUN",
        "activation status drift",
    )
    require(
        activation["execution_release_blob_sha256"] == sha256(ROOT / RELEASE_RELATIVE),
        "activation release binding drift",
    )
    require(
        activation["single_use_window_start_utc"] == start,
        "runtime binding and activation single-use windows differ",
    )
    require(activation["workflow_run_attempt_required"] == 1, "activation attempt drift")
    require(activation["rerun_authorized"] is False, "activation opens rerun")

    require(binding["runtime_authority"] == EXPECTED_RUNTIME_AUTHORITY, "runtime authority drift")
    require_all_false(binding["downstream_authorizations"], "runtime downstream authority")
    require_all_false(binding["trading_authorizations"], "runtime trading authority")
    require(binding["r11_closed"] is False, "runtime binding prematurely closes R11")
    require(binding["r12_ready"] is False, "runtime binding prematurely opens R12")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate exact post-approval R11A R7 runtime binding")
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--run-attempt", required=True, type=int)
    arguments = parser.parse_args(argv)
    validate(arguments.expected_commit, arguments.run_attempt)
    print("R11A_R7_RUNTIME_BINDING_VALID_SINGLE_USE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
