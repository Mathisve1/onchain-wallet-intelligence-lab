#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

APPROVAL_ID = "APPROVE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001"
PACKAGE_ID = "R11A-G1-OWNER-APPROVAL-PACKAGE-001"
DIAGNOSTIC_ID = "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-002"
REPOSITORY = "Mathisve1/onchain-wallet-intelligence-lab"

SOFTWARE_HEAD = "443500de54917417276c39a635ae444458d03b0b"
SOFTWARE_TREE = "516d72a43545c454ef163e02ee1146005e6cfb5c"
SOFTWARE_REVIEW = 5019067044
READINESS_HEAD = "4da7e67b600ef1ca10fb4f2e62b493d81d4dfcc3"
READINESS_TREE = "b4c7b1524e8856450028e53be7912a88d3a675e1"
READINESS_REVIEW = 5027672461

APPROVAL_DIR = "research/archive_inventory/r11a_approval"
APPROVAL_JSON = f"{APPROVAL_DIR}/{APPROVAL_ID}.json"
APPROVAL_TEXT = f"{APPROVAL_DIR}/{APPROVAL_ID}.txt"
PACKAGE = "research/archive_inventory/r11a_g1/R11A_G1_OWNER_APPROVAL_PACKAGE.json"
SOURCE_STATEMENT = "research/archive_inventory/r11a_g1/R11A_G1_OWNER_APPROVAL_STATEMENT.txt"
STATUS = "research/archive_inventory/r11a_g1/R11A_G1_STATUS.json"
ENVELOPE = "research/archive_inventory/r11a_g1/R11A_G1_EXECUTION_ENVELOPE.json"
PRICING = "research/archive_inventory/r11a_g1/R11A_G1_PRICING_EUR_BINDING.json"
RUNTIME_PRICING = "research/archive_inventory/r11a_g1/R11A_G1_RUNTIME_PRICING_SNAPSHOT_CANDIDATE.json"
PERMISSION = "research/archive_inventory/r11a_corrective/R11A_PERMISSION_POLICY.json"
TRUST = "research/archive_inventory/r11a_corrective/R11A_OIDC_TRUST_POLICY.json"
WORKFLOW = "research/archive_inventory/r11a_corrective/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic-r7.yml"

PACKAGE_SHA = "a31c09cb73b3c176c360a8218aa1eae2faf6e02772b2ca1ff35cfd0babedb24f"
STATUS_SHA = "675a11be85dc1f7fc8db18c59dcf7027a32da5241ed44167902767de6121995f"
STATEMENT_SHA = "16f9f2c31ff90952033251d917884b1ca55771511e82e4b813414dc1a3f807d3"

EXPECTED_BOUND_FILES = {
    "research/archive_inventory/r11a_v2/R11A_CORRECTIVE_PREREGISTRATION_AMENDMENT.json": "bdd610c678189e8098381d8c4a0fd12296bf2e0cd8e9ec0fed375b073872552f",
    "research/archive_inventory/r11a_v2/R11A_V2_PREREGISTRATION_BINDINGS.json": "f60f7d6eac5f5a4633a5453c1c79bd84a54add69d1395d9048658450211bd0ba",
    "research/archive_inventory/r11/R11_72H_SELECTION.json": "7c134f4b62f547904126a5f810c177484dceeffa246d53c5c35944367d563eb2",
    "research/archive_inventory/r11_evidence/run-31436753081/r11-result.json": "9d3266eb53791d83df29b6ec3ae5f33c254b29a8182f2e6be7e3261c02686862",
    PERMISSION: "2769afe520efff6f0b619fff352d2cf13d412d96d6c4642fcfc61a8165787e6a",
    TRUST: "375e224b269a62873afb4516651a259483feed4f211e9184272cb2af91513668",
    "research/archive_inventory/r11a_corrective/R11A_ROLE_DECISION.json": "20f9895c83c1d61c79640ed551afd2458fa276502bf3eb9e7f8f3aa040d83d8f",
    "research/archive_inventory/r11a_corrective/R11A_DEPENDENCIES.json": "ce9387377db1f372c6425849549c25e2e47bf24e336510bca06892661e045d6a",
    "research/archive_inventory/r11a_corrective/R11A_RESOURCE_FEASIBILITY_R3.json": "fa71f17591caa0cf939c163733b6f2d87835a06b2f223421b6a6c07cb8d76efb",
    WORKFLOW: "c10b810304d6cdbc68f23cb3db113b57580d34f0f74e781aefa2140edd0b5e65",
    ENVELOPE: "89631f04394805bdf80be0a3784b1cc174eb0fe20e0627bc4eff63cc5f649b2e",
    PRICING: "3459dbfe25d2e7244823344312de5025b7064928c6f436fbe751c7299ea41574",
    RUNTIME_PRICING: "d5043062386b3d70f695f09c917f11719512918c56f318cace1e0530b709ac43",
    SOURCE_STATEMENT: STATEMENT_SHA,
}

RUNTIME_EVIDENCE_PATHS = (
    "research/archive_inventory/r11a_runtime/R11A_RUNTIME_BINDING_R7.json",
    "research/archive_inventory/r11a_runtime/R11A_EXECUTION_RELEASE.json",
    "research/archive_inventory/r11a_runtime/R11A_CANONICAL_ACTIVATION.json",
    "research/archive_inventory/r11a_role_attestation/R11A_DEDICATED_ROLE_OPERATOR_ATTESTATION.json",
    "research/archive_inventory/r11a_role_preflight/R11A_STS_PREFLIGHT_EVIDENCE.json",
    "research/archive_inventory/r11a_workflow_installation/R11A_WORKFLOW_INSTALLATION.json",
)
INSTALLED_WORKFLOW = ".github/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic.yml"


class R11AG2ApprovalError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise R11AG2ApprovalError(message)


def _pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in rows:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(token: str) -> Any:
    raise R11AG2ApprovalError(f"non-finite JSON constant: {token}")


def load(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    require(path.is_file(), f"required file absent: {relative}")
    require(not path.is_symlink(), f"required file is symlink: {relative}")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise R11AG2ApprovalError(f"invalid strict JSON: {relative}") from exc
    require(isinstance(value, dict), f"JSON root is not object: {relative}")
    return value


def sha256(root: Path, relative: str) -> str:
    path = root / relative
    require(path.is_file(), f"hash target absent: {relative}")
    require(not path.is_symlink(), f"hash target is symlink: {relative}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_exact(observed: object, expected: object, label: str) -> None:
    require(type(observed) is type(expected), f"{label} type mismatch")
    if type(expected) is dict:
        observed_dict = observed
        expected_dict = expected
        require(set(observed_dict) == set(expected_dict), f"{label} key set mismatch")
        for key, expected_value in expected_dict.items():
            require_exact(observed_dict[key], expected_value, f"{label}.{key}")
        return
    if type(expected) is list:
        observed_list = observed
        expected_list = expected
        require(len(observed_list) == len(expected_list), f"{label} length mismatch")
        for index, expected_value in enumerate(expected_list):
            require_exact(observed_list[index], expected_value, f"{label}[{index}]")
        return
    require(observed == expected, f"{label} value mismatch")


def expected_record(root: Path) -> dict[str, Any]:
    package = load(root, PACKAGE)
    envelope = load(root, ENVELOPE)
    pricing = load(root, PRICING)
    identity = package["candidate_identity"]
    future = package["frozen_authority_if_explicitly_approved"]
    network = envelope["network_envelope"]
    resources = envelope["resource_envelope"]
    retention = envelope["artifact_retention"]
    calculation = pricing["calculation"]

    return {
        "schema_version": "1.0",
        "approval_id": APPROVAL_ID,
        "package_id": PACKAGE_ID,
        "diagnostic_id": DIAGNOSTIC_ID,
        "repository": REPOSITORY,
        "owner_identity": "Mathis Van Eeckhout",
        "status": "OWNER_APPROVED_HASH_BOUND_FUTURE_STAGES_NO_CURRENT_RUNTIME",
        "record_review_status": "AWAITING_INDEPENDENT_EXACT_HEAD_REVIEW",
        "approval_source": "EXPLICIT_CHAT_APPROVAL_EXACT_BLOCK",
        "approval_received_date_utc": "2026-08-26",
        "canonical_text": {
            "path": APPROVAL_TEXT,
            "sha256": STATEMENT_SHA,
            "source_statement_path": SOURCE_STATEMENT,
            "source_statement_sha256": STATEMENT_SHA,
            "normalization": "REPOSITORY_PROPOSED_STATEMENT_BYTES_WITH_SINGLE_TERMINAL_LF",
        },
        "approved_software_anchor": {
            "reviewed_head": SOFTWARE_HEAD,
            "reviewed_tree": SOFTWARE_TREE,
            "authoritative_review_id": SOFTWARE_REVIEW,
            "review_event": "COMMENTED",
            "review_verdict": "GREEN",
        },
        "readiness_lineage": {
            "base_sha": SOFTWARE_HEAD,
            "reviewed_head": READINESS_HEAD,
            "reviewed_tree": READINESS_TREE,
            "authoritative_review_id": READINESS_REVIEW,
            "review_event": "COMMENTED",
            "review_verdict": "GREEN",
            "g1_j_001_closed": True,
        },
        "approval_package": {
            "path": PACKAGE,
            "sha256": PACKAGE_SHA,
            "status_at_owner_decision": "AWAITING_EXPLICIT_OWNER_APPROVAL",
        },
        "approved_bound_files": dict(EXPECTED_BOUND_FILES),
        "approved_future_identity": {
            "role_arn": identity["role_arn"],
            "creation_and_configuration_authorized_only_in_separate_reviewed_stage": future[
                "dedicated_successor_role_creation_and_configuration_in_separate_next_stage"
            ],
            "maximum_session_duration_seconds": identity["maximum_session_duration_seconds"],
            "persistent_get_object_resource_count": identity[
                "persistent_get_object_resource_count"
            ],
            "permission_policy_sha256": EXPECTED_BOUND_FILES[PERMISSION],
            "oidc_trust_policy_sha256": EXPECTED_BOUND_FILES[TRUST],
            "additional_policy_or_role_authorized": False,
            "consumed_r11_role_reuse_or_mutation_authorized": False,
            "reusable_credentials_or_secrets_authorized": False,
        },
        "approved_future_diagnostic": {
            "maximum_runs_after_all_later_gates": future[
                "maximum_diagnostic_runs_after_all_later_gates"
            ],
            "bucket": envelope["scope"]["bucket"],
            "region": envelope["scope"]["region"],
            "selected_object_count": future["selected_object_count"],
            "seventy_third_object_authorized": envelope["scope"][
                "seventy_third_object_authorized"
            ],
            "broader_archive_access_authorized": False,
            "other_historical_window_authorized": envelope["scope"][
                "other_historical_window_authorized"
            ],
            "maximum_s3_get_object_requests": network["maximum_s3_get_object_requests"],
            "maximum_requests_per_object": network["maximum_requests_per_object"],
            "maximum_retries_per_request": network["maximum_retries_per_request"],
            "http_redirect_following_authorized": network[
                "http_redirect_following_authorized"
            ],
            "pagination_authorized": network["pagination_authorized"],
            "list_authorized": network["list_objects_v2_authorized"],
            "head_authorized": network["head_object_authorized"],
            "range_get_authorized": network["range_get_authorized"],
            "maximum_downloaded_bytes": resources["maximum_downloaded_bytes"],
            "maximum_ephemeral_workspace_bytes": resources[
                "maximum_ephemeral_workspace_bytes"
            ],
            "maximum_retained_artifact_bytes": resources[
                "maximum_retained_artifact_bytes"
            ],
            "artifact_retention_days": retention["github_artifact_retention_days"],
            "maximum_runtime_seconds": resources["maximum_runtime_seconds"],
            "maximum_one_time_budget_eur_micros": calculation[
                "owner_approval_max_eur_micros"
            ],
            "maximum_monthly_budget_eur_micros": calculation[
                "monthly_recurring_budget_eur_micros"
            ],
        },
        "required_separate_future_gates": {
            "post_approval_validator_alignment_and_exact_head_review": True,
            "identity_creation_and_configuration_review": True,
            "operator_role_attestation": True,
            "sts_only_preflight_review": True,
            "workflow_installation_review": True,
            "execution_release_candidate_review": True,
            "runtime_binding_review": True,
            "single_use_activation_review": True,
            "explicit_owner_dispatch": True,
        },
        "current_authority": {
            "successor_role_created": False,
            "aws_iam_mutation": False,
            "aws_oidc": False,
            "sts": False,
            "workflow_installed": False,
            "runtime_binding_present": False,
            "runtime_release": False,
            "runtime_activation": False,
            "workflow_dispatch": False,
            "requester_pays": False,
            "get_object": False,
            "object_body_download": False,
            "decompression": False,
            "diagnostic_execution": False,
            "diagnostic_artifact_retention": False,
            "pr_148_merge_or_github_approval": False,
            "rerun": False,
        },
        "science_state": {
            "empirical_root_cause": "UNKNOWN_PENDING_DIAGNOSTIC",
            "historical_expansion": False,
            "deduplication": False,
            "replay_suppression": False,
            "r11b_repair": False,
            "wallet_ranking": False,
            "candidate_shortlisting": False,
            "pnl_or_alpha_interpretation": False,
            "copyability": False,
            "clustering": False,
            "strategy_inference": False,
            "r11_closed": False,
            "r12_ready": False,
        },
        "trading_authorizations": {
            "integration": False,
            "paper": False,
            "shadow": False,
            "live": False,
            "leverage": False,
            "capital_allocation": False,
            "withdrawals_or_transfers": False,
        },
        "approval_alone": {
            "creates_or_modifies_iam": False,
            "installs_workflow": False,
            "creates_release": False,
            "activates_runtime": False,
            "dispatches_workflow": False,
            "executes_r11a": False,
            "authorizes_rerun": False,
        },
        "drift_policy": {
            "void_on_sha_or_hash_drift": True,
            "void_on_object_set_request_byte_runtime_or_cost_drift": True,
            "void_on_iam_workflow_or_governance_drift": True,
            "new_explicit_owner_statement_required_after_drift": True,
        },
        "owner_approval_present": True,
        "canonical_approval_record_present": True,
        "execution_authorized_by_this_approval": False,
        "next_gate": "INDEPENDENT_EXACT_HEAD_REVIEW_OF_APPROVAL_RECORD_NO_AWS",
    }


def validate(root: Path = ROOT) -> dict[str, Any]:
    require(root.is_dir(), "repository root is absent")
    expected_dir_files = {
        Path(APPROVAL_JSON).name,
        Path(APPROVAL_TEXT).name,
    }
    approval_dir = root / APPROVAL_DIR
    require(approval_dir.is_dir(), "canonical approval directory is absent")
    require(not approval_dir.is_symlink(), "canonical approval directory is symlink")
    observed_dir_entries = {path.name for path in approval_dir.iterdir()}
    require(
        observed_dir_entries == expected_dir_files,
        "canonical approval directory file set drift",
    )

    require(sha256(root, PACKAGE) == PACKAGE_SHA, "approval package raw hash drift")
    require(sha256(root, STATUS) == STATUS_SHA, "reviewed G1 status raw hash drift")
    require(sha256(root, SOURCE_STATEMENT) == STATEMENT_SHA, "source statement raw hash drift")
    require(sha256(root, APPROVAL_TEXT) == STATEMENT_SHA, "approval text raw hash drift")
    source_bytes = (root / SOURCE_STATEMENT).read_bytes()
    approval_bytes = (root / APPROVAL_TEXT).read_bytes()
    require(source_bytes == approval_bytes, "approval text differs from frozen statement")
    require(approval_bytes.endswith(b"\n"), "approval text lacks terminal LF")
    require(not approval_bytes.endswith(b"\n\n"), "approval text has extra terminal LF")

    package = load(root, PACKAGE)
    require(package.get("package_id") == PACKAGE_ID, "approval package ID drift")
    require(package.get("proposed_approval_id") == APPROVAL_ID, "proposed approval ID drift")
    require(
        package.get("approval_status") == "AWAITING_EXPLICIT_OWNER_APPROVAL",
        "historical package status was rewritten",
    )
    require(package.get("owner_approval_present") is False, "historical package claims approval")
    require_exact(package.get("bound_files"), EXPECTED_BOUND_FILES, "package bound_files")
    for relative, expected_hash in EXPECTED_BOUND_FILES.items():
        require(re.fullmatch(r"[0-9a-f]{64}", expected_hash) is not None, "invalid bound hash")
        relative_path = Path(relative)
        require(
            not relative_path.is_absolute() and ".." not in relative_path.parts,
            f"unsafe bound path: {relative}",
        )
        require(sha256(root, relative) == expected_hash, f"bound file hash drift: {relative}")

    anchor = package.get("software_anchor", {})
    require(anchor.get("reviewed_head") == SOFTWARE_HEAD, "software head drift")
    require(anchor.get("authoritative_review_id") == SOFTWARE_REVIEW, "software review drift")
    require(anchor.get("review_event") == "COMMENTED", "software review event drift")
    require(anchor.get("review_verdict") == "GREEN", "software verdict drift")
    require(anchor.get("superseding_red_review_present") is False, "superseding RED asserted")

    envelope = load(root, ENVELOPE)
    require(envelope.get("diagnostic_id") == DIAGNOSTIC_ID, "diagnostic ID drift")
    require(envelope.get("status") == "FROZEN_INERT_NO_EXECUTION", "envelope activated")
    require(envelope.get("authority_state", {}).get("owner_approval_present") is False, "historical envelope rewritten")
    require(
        all(value is False for value in envelope.get("prohibited_scientific_scope", {}).values()),
        "envelope opens prohibited science scope",
    )
    pricing = load(root, PRICING)
    require(
        pricing.get("status") == "PASS_CURRENT_OFFICIAL_PRICING_BOUND_NO_EXECUTION",
        "pricing binding status drift",
    )
    require(pricing.get("pricing_binding_pending") is False, "pricing binding pending")
    require(pricing.get("owner_approval_present") is False, "historical pricing rewritten")
    require(pricing.get("runtime_authority_opened") is False, "pricing opens runtime")

    record = load(root, APPROVAL_JSON)
    require_exact(record, expected_record(root), "canonical approval record")
    require(
        all(value is False for value in record["current_authority"].values()),
        "current authority opened",
    )
    require(
        all(
            value is False
            for key, value in record["science_state"].items()
            if key != "empirical_root_cause"
        ),
        "science authority opened",
    )
    require(
        all(value is False for value in record["trading_authorizations"].values()),
        "trading authority opened",
    )
    require(
        all(value is False for value in record["approval_alone"].values()),
        "approval self-executes a later stage",
    )

    installed_workflow = root / INSTALLED_WORKFLOW
    require(
        not installed_workflow.exists() and not installed_workflow.is_symlink(),
        "R11A runtime workflow is installed",
    )
    for relative in RUNTIME_EVIDENCE_PATHS:
        evidence = root / relative
        require(
            not evidence.exists() and not evidence.is_symlink(),
            f"runtime evidence unexpectedly present: {relative}",
        )

    return record


def main() -> int:
    validate()
    print("R11A_G2_OWNER_APPROVAL_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
