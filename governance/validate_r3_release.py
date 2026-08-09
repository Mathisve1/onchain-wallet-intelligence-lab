from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r3"
RELEASE = BASE / "R3_EXECUTION_RELEASE.json"
ACTIVATION = BASE / "R3_EXECUTION_RELEASE_CANONICALIZATION.json"
IMPLEMENTATION = BASE / "R3_IMPLEMENTATION_CONTRACT.json"
APPROVAL = BASE / "approvals/APPROVE_HL_ARCHIVE_HOURLY_METADATA_INVENTORY_R3_001.json"
APPROVAL_TEXT = BASE / "approvals/APPROVE_HL_ARCHIVE_HOURLY_METADATA_INVENTORY_R3_001.txt"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-hourly-metadata-inventory-r3.yml"

PREREG_COMMIT = "ab4d42be02fe49d7f90f933317ef856f0322fd85"
APPROVAL_MERGE_COMMIT = "e562f3fbd8f1dac1b4d7e93eed2f5ee6b77c5da6"
APPROVAL_SHA = "3c3931133fb8b0dd322d7a296b7b70fca65dd341401a6eda2b6372938ed6cd10"
IMPLEMENTATION_COMMIT = "3b1dd0df4c5194875e22c1b790e0b41961313aa8"
IMPLEMENTATION_HEAD = "02681dbf13415f953fd3c79f66ee5de4919a169c"
PREFIXES = ["node_fills_by_block/hourly/", "node_fills/hourly/", "node_trades/hourly/"]


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    release = load(RELEASE)
    impl = load(IMPLEMENTATION)
    approval = load(APPROVAL)
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest() == APPROVAL_SHA
    assert approval["reviewed_commit"] == PREREG_COMMIT
    assert approval["exact_approval_text_sha256"] == APPROVAL_SHA
    assert impl["preregistration_commit"] == PREREG_COMMIT
    assert impl["approval_merge_commit"] == APPROVAL_MERGE_COMMIT
    assert impl["approval_text_sha256"] == APPROVAL_SHA

    assert release["release_id"] == "RELEASE_HL_ARCHIVE_HOURLY_METADATA_INVENTORY_R3_001"
    assert release["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
    assert release["inventory_id"] == "HL-ARCHIVE-HOURLY-METADATA-INVENTORY-R3-001"
    assert release["preregistration_commit"] == PREREG_COMMIT
    assert release["approval_merge_commit"] == APPROVAL_MERGE_COMMIT
    assert release["approval_reviewed_commit"] == PREREG_COMMIT
    assert release["approval_text_sha256"] == APPROVAL_SHA
    assert release["implementation_pr"] == 42
    assert release["implementation_commit"] == IMPLEMENTATION_COMMIT
    assert release["implementation_exact_head_ci_commit"] == IMPLEMENTATION_HEAD
    assert release["implementation_ci_run"] == 31297902934
    assert release["implementation_ci_job"] == 93205871178
    assert release["implementation_test_count"] == 236
    assert release["implementation_ci_result"] == "SUCCESS"
    assert release["implementation_repository_manifest_result"] == "BYTE_EXACT_PASS"
    assert release["implementation_repository_governance_result"] == "PASS"
    assert release["implementation_validator_result"] == "R3_IMPLEMENTATION_VALID"

    assert release["activation_required"] is True
    assert release["activation_record_path"] == "research/archive_inventory/r3/R3_EXECUTION_RELEASE_CANONICALIZATION.json"
    assert release["activation_record_present"] is False
    assert release["canonical_release_merge_commit"] is None
    assert release["single_use_window_start_utc"] is None
    assert not ACTIVATION.exists()

    assert release["github_event_required"] == "workflow_dispatch"
    assert release["canonical_dispatch_ref_required"] == "refs/heads/main"
    assert release["canonical_dispatch_sha_source"] == "github.sha"
    assert release["manual_reviewed_commit_input_required"] is False
    assert release["target_bucket"] == "hl-mainnet-node-data"
    assert release["signing_region"] == "ap-northeast-1"
    assert release["regional_virtual_hosted_endpoint"] == "hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com"
    assert release["prefixes"] == PREFIXES
    assert release["maximum_one_time_budget_eur"] == 0.10
    assert release["maximum_monthly_budget_eur"] == 0
    assert release["maximum_list_requests"] == 48
    assert release["maximum_pages_per_family"] == 16
    assert release["maximum_keys_per_request"] == 1000
    assert release["maximum_total_entries"] == 48000
    assert release["maximum_total_response_bytes"] == 33554432
    assert release["maximum_runtime_seconds"] == 300
    assert release["maximum_retries_per_request"] == 0
    assert release["pagination_authorized_after_activation"] is True
    assert release["continuation_token_follow_authorized_after_activation"] is True
    assert release["continuation_token_values_retained"] is False
    assert release["repeated_continuation_token_fails_closed"] is True
    assert release["duplicate_key_fails_closed"] is True
    assert release["http_redirect_following_authorized"] is False
    assert release["start_after_authorized"] is False
    assert release["delimiter_authorized"] is False

    assert release["requester_pays_scope_authorized_after_activation"] is True
    assert release["list_objects_v2_scope_authorized_after_activation"] is True
    assert release["single_workflow_dispatch_authorized_after_activation"] is True
    assert release["rerun_authorized"] is False
    assert release["requester_pays_authorized"] is False
    assert release["list_objects_v2_authorized"] is False
    assert release["single_workflow_dispatch_authorized"] is False
    assert release["execution_ready"] is False
    for key in (
        "get_object_authorized", "head_object_authorized", "get_object_attributes_authorized",
        "range_get_authorized", "list_object_versions_authorized", "list_all_my_buckets_authorized",
        "object_body_download_authorized", "decompression_authorized",
        "explorer_blocks_inventory_authorized", "replica_cmds_inventory_authorized",
        "market_data_ingestion_authorized", "larger_300_request_inventory_authorized",
    ):
        assert release[key] is False, key
    assert all(value is False for value in release["trading_authorizations"].values())
    assert release["s3_requests_executed"] == 0
    assert release["metadata_entries_observed"] == 0
    assert release["empirical_result"] is None

    # Release candidate merge must remain unable to reach AWS: workflow is still implementation-pending.
    assert "EXPECTED_IMPLEMENTATION_COMMIT: PENDING_CANONICAL_IMPLEMENTATION_MERGE" in workflow
    assert "R3_EXECUTION_RELEASE.json" in workflow
    assert workflow.index("Prove canonical implementation and release before AWS OIDC") < workflow.index("Assume exact AWS role with R3-only session permissions")

    print("R3_RELEASE_CANDIDATE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
