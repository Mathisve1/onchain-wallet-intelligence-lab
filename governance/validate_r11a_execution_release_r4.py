#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).absolute().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))
import difflib as _r11a_bytecode_boundary  # noqa: E402,F401

try:
    from governance.r11a_stage_common_r4 import (
        APPROVAL_RECEIPT_SHA,
        APPROVAL_TEXT_RELATIVE,
        ARTIFACT_VALIDATOR_RELATIVE,
        DIAGNOSTIC_ID,
        IMPLEMENTATION_RELATIVE,
        INSTALLATION_RELATIVE,
        PREFLIGHT_CONSUMPTION_RELATIVE,
        PREFLIGHT_EVIDENCE_RELATIVE,
        PRICING_TARGET_RELATIVE,
        RELEASE_CANDIDATE_RELATIVE,
        RELEASE_DIGEST_RELATIVE,
        RELEASE_RELATIVE,
        REVIEW_EVIDENCE_PATHS,
        ROOT,
        RUNNER_RELATIVE,
        SELECTION_RELATIVE,
        WORKFLOW_RELATIVE,
        load,
        read_bytes,
        require,
        require_exact,
        require_gate_review,
        require_int,
        require_sha256,
        sha256,
        stage_authority,
        successor_permissions,
        trading_authority,
    )
    from governance.validate_r11a_workflow_installation_r4 import validate as validate_installation
except ModuleNotFoundError:
    from r11a_stage_common_r4 import (
        APPROVAL_RECEIPT_SHA,
        APPROVAL_TEXT_RELATIVE,
        ARTIFACT_VALIDATOR_RELATIVE,
        DIAGNOSTIC_ID,
        IMPLEMENTATION_RELATIVE,
        INSTALLATION_RELATIVE,
        PREFLIGHT_CONSUMPTION_RELATIVE,
        PREFLIGHT_EVIDENCE_RELATIVE,
        PRICING_TARGET_RELATIVE,
        RELEASE_CANDIDATE_RELATIVE,
        RELEASE_DIGEST_RELATIVE,
        RELEASE_RELATIVE,
        REVIEW_EVIDENCE_PATHS,
        ROOT,
        RUNNER_RELATIVE,
        SELECTION_RELATIVE,
        WORKFLOW_RELATIVE,
        load,
        read_bytes,
        require,
        require_exact,
        require_gate_review,
        require_int,
        require_sha256,
        sha256,
        stage_authority,
        successor_permissions,
        trading_authority,
    )
    from validate_r11a_workflow_installation_r4 import validate as validate_installation

RELEASE_CANDIDATE = ROOT / RELEASE_CANDIDATE_RELATIVE
RELEASE = ROOT / RELEASE_RELATIVE
RELEASE_DIGEST = ROOT / RELEASE_DIGEST_RELATIVE
APPROVAL_TEXT = ROOT / APPROVAL_TEXT_RELATIVE
ARTIFACT_VALIDATOR = ROOT / ARTIFACT_VALIDATOR_RELATIVE
WORKFLOW_INSTALLATION_REVIEW_GATE = "R11A_WORKFLOW_INSTALLATION_REVIEW"
EXECUTION_RELEASE_CANDIDATE_REVIEW_GATE = "R11A_EXECUTION_RELEASE_CANDIDATE_REVIEW"

CAP_KEYS = frozenset(
    {
        "maximum_runs",
        "bucket",
        "region",
        "selected_object_count",
        "maximum_get_object_requests",
        "maximum_requests_per_object",
        "maximum_retries_per_request",
        "maximum_total_compressed_bytes",
        "maximum_total_decompressed_processing_bytes",
        "maximum_ephemeral_workspace_bytes",
        "maximum_retained_artifact_bytes",
        "artifact_retention_days",
        "maximum_runtime_seconds",
        "maximum_one_time_budget_eur_micros",
        "maximum_monthly_budget_eur_micros",
        "http_redirect_following_authorized",
        "pagination_authorized",
        "list_authorized",
        "head_authorized",
        "range_get_authorized",
        "seventy_third_object_authorized",
        "broader_archive_access_authorized",
        "other_historical_window_authorized",
    }
)
CANDIDATE_KEYS = frozenset(
    {
        "schema_version",
        "execution_release_candidate_id",
        "status",
        "diagnostic_id",
        "installation_contract_sha256",
        "approval_receipt_sha256",
        "workflow_sha256",
        "runtime_pricing_snapshot_sha256",
        "selection_sha256",
        "runner_sha256",
        "validator_sha256",
        "workflow_installation_review_evidence_sha256",
        *CAP_KEYS,
        "single_workflow_dispatch_authorized",
        "owner_dispatch_required",
        "execution_release_present",
        "runtime_binding_present",
        "canonical_activation_present",
        "network_requests_executed_by_candidate",
        "aws_iam_mutations_executed_by_candidate",
        "downstream_authorizations",
        "trading_authorizations",
    }
)
RELEASE_KEYS = frozenset(
    {
        "schema_version",
        "execution_release_id",
        "execution_release_candidate_id",
        "status",
        "release_candidate_sha256",
        "implementation_contract_sha256",
        "approval_receipt_sha256",
        "approval_text_sha256",
        "pricing_snapshot_sha256",
        "workflow_sha256",
        "collector_sha256",
        "validator_sha256",
        "selection_sha256",
        "execution_release_candidate_review_evidence_sha256",
        *CAP_KEYS,
        "single_workflow_dispatch_authorized_by_release",
        "single_workflow_dispatch_eligible_after_activation",
        "rerun_authorized",
        "release_consumed",
        "canonical_activation_required",
        "canonical_activation_present",
        "network_requests_executed_by_release",
        "aws_iam_mutations_executed_by_release",
        "downstream_authorizations",
        "trading_authorizations",
    }
)
EXPECTED_CAPS = {
    "maximum_runs": 1,
    "bucket": "hl-mainnet-node-data",
    "region": "ap-northeast-1",
    "selected_object_count": 72,
    "maximum_get_object_requests": 72,
    "maximum_requests_per_object": 1,
    "maximum_retries_per_request": 0,
    "maximum_total_compressed_bytes": 2107738436,
    "maximum_total_decompressed_processing_bytes": 21079958490,
    "maximum_ephemeral_workspace_bytes": 5368709120,
    "maximum_retained_artifact_bytes": 134217728,
    "artifact_retention_days": 30,
    "maximum_runtime_seconds": 21600,
    "maximum_one_time_budget_eur_micros": 500000,
    "maximum_monthly_budget_eur_micros": 0,
    "http_redirect_following_authorized": False,
    "pagination_authorized": False,
    "list_authorized": False,
    "head_authorized": False,
    "range_get_authorized": False,
    "seventy_third_object_authorized": False,
    "broader_archive_access_authorized": False,
    "other_historical_window_authorized": False,
}


def _validate_caps(record: dict[str, object], label: str) -> None:
    for key, expected in EXPECTED_CAPS.items():
        if isinstance(expected, bool):
            require(type(record[key]) is bool, f"{label} {key} must be boolean")
        elif isinstance(expected, int):
            require_int(record[key], f"{label} {key}")
        else:
            require(isinstance(record[key], str), f"{label} {key} must be text")
        require(record[key] == expected, f"{label} {key} drift")


def validate_candidate(
    root: Path = ROOT,
    *,
    permitted_successor_paths: frozenset[str] = frozenset(),
    _review_lineage: list[object] | None = None,
) -> dict[str, object]:
    lineage = [] if _review_lineage is None else _review_lineage
    permitted = successor_permissions(
        frozenset(permitted_successor_paths)
        | {
            RELEASE_CANDIDATE_RELATIVE,
            REVIEW_EVIDENCE_PATHS[WORKFLOW_INSTALLATION_REVIEW_GATE],
        }
    )
    validate_installation(
        root,
        permitted_successor_paths=permitted,
        runtime_pricing_projection_permitted=True,
        _review_lineage=lineage,
    )
    candidate = load(
        root,
        RELEASE_CANDIDATE_RELATIVE,
        missing_label="execution release candidate is absent",
    )
    require_exact(candidate, CANDIDATE_KEYS, "execution release candidate")
    require(candidate["schema_version"] == "1.0", "release candidate schema drift")
    require(
        candidate["execution_release_candidate_id"]
        == "CANDIDATE_RELEASE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001",
        "release candidate ID drift",
    )
    require(
        candidate["status"]
        == "CANDIDATE_AWAITING_EXACT_HEAD_COMMENTED_GREEN_EXECUTION_RELEASE_REVIEW_NO_EXECUTION",
        "release candidate status drift",
    )
    require(candidate["diagnostic_id"] == DIAGNOSTIC_ID, "release candidate diagnostic ID drift")
    bindings = {
        "installation_contract_sha256": INSTALLATION_RELATIVE,
        "workflow_sha256": WORKFLOW_RELATIVE,
        "runtime_pricing_snapshot_sha256": PRICING_TARGET_RELATIVE,
        "selection_sha256": SELECTION_RELATIVE,
        "runner_sha256": RUNNER_RELATIVE,
        "validator_sha256": ARTIFACT_VALIDATOR_RELATIVE,
    }
    for key, relative in bindings.items():
        require_sha256(candidate[key], key)
        require(candidate[key] == sha256(root, relative), f"release candidate {key} drift")
    require_sha256(candidate["approval_receipt_sha256"], "approval_receipt_sha256")
    require(candidate["approval_receipt_sha256"] == APPROVAL_RECEIPT_SHA, "release candidate approval binding drift")
    require_gate_review(
        root,
        candidate,
        "workflow_installation_review_evidence_sha256",
        WORKFLOW_INSTALLATION_REVIEW_GATE,
        target_files={
            INSTALLATION_RELATIVE: sha256(root, INSTALLATION_RELATIVE),
            WORKFLOW_RELATIVE: sha256(root, WORKFLOW_RELATIVE),
            PRICING_TARGET_RELATIVE: sha256(root, PRICING_TARGET_RELATIVE),
        },
        predecessor_files={
            PREFLIGHT_EVIDENCE_RELATIVE: sha256(root, PREFLIGHT_EVIDENCE_RELATIVE),
            PREFLIGHT_CONSUMPTION_RELATIVE: sha256(root, PREFLIGHT_CONSUMPTION_RELATIVE),
        },
        lineage=lineage,
    )
    _validate_caps(candidate, "release candidate")
    require(candidate["single_workflow_dispatch_authorized"] is False, "release candidate self-authorizes dispatch")
    require(candidate["owner_dispatch_required"] is True, "release candidate omits owner dispatch gate")
    require(candidate["execution_release_present"] is False, "release candidate snapshot rewritten after release")
    require(candidate["runtime_binding_present"] is False, "release candidate snapshot rewritten after binding")
    require(candidate["canonical_activation_present"] is False, "release candidate snapshot rewritten after activation")
    require_int(candidate["network_requests_executed_by_candidate"], "release-candidate network request count")
    require(candidate["network_requests_executed_by_candidate"] == 0, "release candidate performed network request")
    require_int(candidate["aws_iam_mutations_executed_by_candidate"], "release-candidate IAM mutation count")
    require(candidate["aws_iam_mutations_executed_by_candidate"] == 0, "release candidate mutated IAM")
    stage_authority(candidate["downstream_authorizations"], "release-candidate downstream authority")
    trading_authority(candidate["trading_authorizations"], "release-candidate trading authority")
    return candidate


def validate(
    root: Path = ROOT,
    *,
    permitted_successor_paths: frozenset[str] = frozenset(),
    _review_lineage: list[object] | None = None,
) -> dict[str, object]:
    lineage = [] if _review_lineage is None else _review_lineage
    permitted = successor_permissions(
        frozenset(permitted_successor_paths)
        | {
            RELEASE_CANDIDATE_RELATIVE,
            RELEASE_RELATIVE,
            RELEASE_DIGEST_RELATIVE,
            REVIEW_EVIDENCE_PATHS[EXECUTION_RELEASE_CANDIDATE_REVIEW_GATE],
        }
    )
    candidate = validate_candidate(
        root,
        permitted_successor_paths=permitted,
        _review_lineage=lineage,
    )
    release = load(root, RELEASE_RELATIVE, missing_label="execution release is absent")
    require_exact(release, RELEASE_KEYS, "execution release")
    detached_raw = read_bytes(
        root,
        RELEASE_DIGEST_RELATIVE,
        missing_label="detached execution release digest is absent",
    )
    release_digest = sha256(root, RELEASE_RELATIVE)
    require(detached_raw == f"{release_digest}\n".encode("ascii"), "detached release digest format or value drift")
    require(release["schema_version"] == "1.0", "execution release schema drift")
    require(
        release["execution_release_id"]
        == "RELEASE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001",
        "release ID drift",
    )
    require(
        release["execution_release_candidate_id"]
        == candidate["execution_release_candidate_id"],
        "release candidate ID binding drift",
    )
    require(release["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R11A_RUN", "release status drift")
    require_sha256(release["release_candidate_sha256"], "release_candidate_sha256")
    require(release["release_candidate_sha256"] == sha256(root, RELEASE_CANDIDATE_RELATIVE), "release candidate blob binding drift")
    bindings = {
        "implementation_contract_sha256": IMPLEMENTATION_RELATIVE,
        "approval_text_sha256": APPROVAL_TEXT_RELATIVE,
        "pricing_snapshot_sha256": PRICING_TARGET_RELATIVE,
        "workflow_sha256": WORKFLOW_RELATIVE,
        "collector_sha256": RUNNER_RELATIVE,
        "validator_sha256": ARTIFACT_VALIDATOR_RELATIVE,
        "selection_sha256": SELECTION_RELATIVE,
    }
    for key, relative in bindings.items():
        require_sha256(release[key], key)
        require(release[key] == sha256(root, relative), f"release {key} drift")
    require_sha256(release["approval_receipt_sha256"], "approval_receipt_sha256")
    require(release["approval_receipt_sha256"] == APPROVAL_RECEIPT_SHA, "release approval receipt binding drift")
    require_gate_review(
        root,
        release,
        "execution_release_candidate_review_evidence_sha256",
        EXECUTION_RELEASE_CANDIDATE_REVIEW_GATE,
        target_files={
            RELEASE_CANDIDATE_RELATIVE: sha256(root, RELEASE_CANDIDATE_RELATIVE)
        },
        predecessor_files={
            INSTALLATION_RELATIVE: sha256(root, INSTALLATION_RELATIVE),
            WORKFLOW_RELATIVE: sha256(root, WORKFLOW_RELATIVE),
            PRICING_TARGET_RELATIVE: sha256(root, PRICING_TARGET_RELATIVE),
        },
        lineage=lineage,
    )
    _validate_caps(release, "release")
    require(
        release["single_workflow_dispatch_authorized_by_release"] is False,
        "release self-authorizes workflow dispatch",
    )
    require(
        release["single_workflow_dispatch_eligible_after_activation"] is True,
        "release omits activation-contingent single-dispatch eligibility",
    )
    require(release["rerun_authorized"] is False, "release authorizes rerun")
    require(release["release_consumed"] is False, "immutable pre-run release snapshot marked consumed")
    require(release["canonical_activation_required"] is True, "canonical activation requirement missing")
    require(release["canonical_activation_present"] is False, "historical release snapshot rewritten after activation")
    require_int(release["network_requests_executed_by_release"], "release network request count")
    require(release["network_requests_executed_by_release"] == 0, "release performed network request")
    require_int(release["aws_iam_mutations_executed_by_release"], "release IAM mutation count")
    require(release["aws_iam_mutations_executed_by_release"] == 0, "release mutated IAM")
    stage_authority(release["downstream_authorizations"], "release downstream authority")
    trading_authority(release["trading_authorizations"], "release trading authority")
    return release


def main() -> int:
    validate()
    print("R11A_EXECUTION_RELEASE_R4_VALID_SINGLE_USE_AWAITING_ACTIVATION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
