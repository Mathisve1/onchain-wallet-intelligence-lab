#!/usr/bin/env python3
from __future__ import annotations

from r11a_stage_common import (
    APPROVAL_DIR,
    implementation,
    load,
    pricing,
    require,
    require_all_false,
    require_commit,
    require_sha256,
    sha256,
)

APPROVAL_JSON = APPROVAL_DIR / "APPROVE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001.json"
APPROVAL_TEXT = APPROVAL_DIR / "APPROVE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001.txt"


def main() -> int:
    impl = implementation()
    price = pricing()
    approval = load(APPROVAL_JSON)
    require(APPROVAL_TEXT.is_file(), "exact owner approval text is absent")
    require(approval["approval_id"] == "APPROVE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001", "approval ID drift")
    require(approval["status"] == "APPROVED_IMPLEMENTATION_ROLE_AND_PREFLIGHT_NO_DATA_EXECUTION", "approval status drift")
    require_commit(approval["reviewed_commit"], "reviewed_commit")
    require(approval["reviewed_commit"] == impl["canonical_merge_commit"], "approval does not review canonical corrective merge")
    require_sha256(approval["approval_text_sha256"], "approval_text_sha256")
    require(sha256(APPROVAL_TEXT) == approval["approval_text_sha256"], "approval text hash mismatch")
    require(approval["implementation_contract_sha256"] == sha256(APPROVAL_JSON.parents[1] / "r11a_corrective/R11A_CORRECTIVE_IMPLEMENTATION_CONTRACT.json"), "implementation contract hash mismatch")
    require(approval["pricing_snapshot_sha256"] == sha256(APPROVAL_JSON.parents[1] / "r11a_corrective/R11A_PRICING_EUR_SNAPSHOT.json"), "pricing snapshot hash mismatch")
    require(approval["selected_object_count"] == 72, "approval object count drift")
    require(approval["maximum_get_object_requests"] == 72, "approval request cap drift")
    require(approval["maximum_requests_per_object"] == 1, "approval per-object request cap drift")
    require(approval["maximum_retries_per_request"] == 0, "approval retries drift")
    require(approval["maximum_total_compressed_bytes"] == 2107738436, "approval compressed cap drift")
    require(approval["maximum_total_decompressed_processing_bytes"] == 21079958490, "approval decompressed cap drift")
    require(approval["maximum_ephemeral_workspace_bytes"] == 5368709120, "approval workspace cap drift")
    require(approval["maximum_retained_artifact_bytes"] == 134217728, "approval artifact cap drift")
    require(approval["maximum_runtime_seconds"] == 21600, "approval runtime cap drift")
    require(approval["maximum_one_time_budget_eur_micros"] == 500000, "approval one-time budget drift")
    require(approval["maximum_monthly_budget_eur_micros"] == 0, "approval monthly budget drift")
    require(approval["role_creation_authorized"] is True, "successor role creation is not approved")
    require(approval["sts_only_preflight_authorized"] is True, "STS-only preflight is not approved")
    require(approval["data_execution_authorized_by_this_approval"] is False, "approval self-authorizes data execution")
    require(approval["separate_workflow_installation_required"] is True, "workflow installation gate missing")
    require(approval["separate_execution_release_required"] is True, "execution release gate missing")
    require(approval["separate_canonical_activation_required"] is True, "canonical activation gate missing")
    require_all_false(approval["downstream_authorizations"], "approval downstream authority")
    require_all_false(approval["trading_authorizations"], "approval trading authority")
    require(price["snapshot_sha256"] == approval["pricing_snapshot_self_sha256"], "pricing self hash binding drift")
    print("R11A_OWNER_APPROVAL_VALID_NO_DATA_EXECUTION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
