#!/usr/bin/env python3
from __future__ import annotations

from r11a_stage_common import (
    CORRECTIVE,
    ROOT,
    RUNTIME_DIR,
    SELECTION_PATH,
    WORKFLOW_PATH,
    implementation,
    load,
    require,
    require_all_false,
    require_sha256,
    sha256,
)
from validate_r11a_workflow_installation import main as validate_installation

RELEASE = RUNTIME_DIR / "R11A_EXECUTION_RELEASE.json"
RELEASE_DIGEST = RUNTIME_DIR / "R11A_EXECUTION_RELEASE.sha256"
APPROVAL_TEXT = ROOT / "research/archive_inventory/r11a_approval/APPROVE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001.txt"
ARTIFACT_VALIDATOR = ROOT / "governance/validate_r11a_execution_artifact.py"


def main() -> int:
    impl = implementation()
    validate_installation()
    release = load(RELEASE)
    require(RELEASE_DIGEST.is_file(), "detached release digest is absent")
    detached = RELEASE_DIGEST.read_text(encoding="ascii").strip()
    require_sha256(detached, "detached release digest")
    require(detached == sha256(RELEASE), "detached release digest mismatch")
    require(release["execution_release_id"] == "RELEASE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001", "release ID drift")
    require(release["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R11A_RUN", "release status drift")
    require(release["implementation_contract_sha256"] == sha256(CORRECTIVE / "R11A_CORRECTIVE_IMPLEMENTATION_CONTRACT.json"), "implementation contract binding drift")
    require(release["approval_text_sha256"] == sha256(APPROVAL_TEXT), "approval text binding drift")
    require(release["pricing_snapshot_sha256"] == sha256(CORRECTIVE / "R11A_PRICING_EUR_SNAPSHOT.json"), "pricing snapshot binding drift")
    require(release["workflow_sha256"] == sha256(WORKFLOW_PATH), "workflow binding drift")
    require(release["collector_sha256"] == impl["implementation_file_hashes"]["research/archive_inventory/r11a_corrective/runner_r3.py"], "collector binding drift")
    require(release["validator_sha256"] == sha256(ARTIFACT_VALIDATOR), "artifact validator binding drift")
    require(release["selection_sha256"] == sha256(SELECTION_PATH), "selection binding drift")
    require(release["selected_object_count"] == 72, "release object count drift")
    require(release["maximum_get_object_requests"] == 72, "release request count drift")
    require(release["maximum_requests_per_object"] == 1, "release per-object request cap drift")
    require(release["maximum_retries_per_request"] == 0, "release retries drift")
    require(release["maximum_total_compressed_bytes"] == 2107738436, "release compressed cap drift")
    require(release["maximum_total_decompressed_processing_bytes"] == 21079958490, "release decompressed cap drift")
    require(release["maximum_ephemeral_workspace_bytes"] == 5368709120, "release workspace cap drift")
    require(release["maximum_retained_artifact_bytes"] == 134217728, "release artifact cap drift")
    require(release["maximum_runtime_seconds"] == 21600, "release runtime cap drift")
    require(release["maximum_one_time_budget_eur_micros"] == 500000, "release one-time budget drift")
    require(release["maximum_monthly_budget_eur_micros"] == 0, "release monthly budget drift")
    require(release["single_workflow_dispatch_authorized"] is True, "release does not authorize one dispatch")
    require(release["rerun_authorized"] is False, "release authorizes rerun")
    require(release["release_consumed"] is False, "pre-run release snapshot marked consumed")
    require(release["canonical_activation_required"] is True, "canonical activation requirement missing")
    require(release["canonical_activation_present"] is False, "historical release snapshot rewritten after activation")
    require_all_false(release["downstream_authorizations"], "release downstream authority")
    require_all_false(release["trading_authorizations"], "release trading authority")
    print("R11A_EXECUTION_RELEASE_R3_VALID_SINGLE_USE_AWAITING_ACTIVATION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
