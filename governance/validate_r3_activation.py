from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r3"
CANDIDATE = BASE / "R3_EXECUTION_RELEASE.json"
ACTIVATION = BASE / "R3_EXECUTION_RELEASE_CANONICALIZATION.json"
APPROVAL = BASE / "approvals/APPROVE_HL_ARCHIVE_HOURLY_METADATA_INVENTORY_R3_001.json"
APPROVAL_TEXT = BASE / "approvals/APPROVE_HL_ARCHIVE_HOURLY_METADATA_INVENTORY_R3_001.txt"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-hourly-metadata-inventory-r3.yml"

PREREG_COMMIT = "ab4d42be02fe49d7f90f933317ef856f0322fd85"
APPROVAL_MERGE_COMMIT = "e562f3fbd8f1dac1b4d7e93eed2f5ee6b77c5da6"
APPROVAL_SHA = "3c3931133fb8b0dd322d7a296b7b70fca65dd341401a6eda2b6372938ed6cd10"
IMPLEMENTATION_COMMIT = "3b1dd0df4c5194875e22c1b790e0b41961313aa8"
IMPLEMENTATION_HEAD = "02681dbf13415f953fd3c79f66ee5de4919a169c"
RELEASE_HEAD = "95dd5765728d2977cdf51b3ae13d6d76af93af2d"
RELEASE_MERGE = "6cd8ed06f311b6cda0a6e06c4d63f1cf05a9aad5"
ANCHOR_COMMIT = "4bc99701f6a24a045c84b205963685a2fe8c3122"
ANCHOR_UTC = "2026-08-09T06:38:46Z"
CANDIDATE_SHA256 = "c64719a8e9b8a82a361dcc7e4b03c12fba8027cd8d1e72bfc05487a2ef6ad55b"
PREFIXES = [
    "node_fills_by_block/hourly/",
    "node_fills/hourly/",
    "node_trades/hourly/",
]


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    candidate = load(CANDIDATE)
    activation = load(ACTIVATION)
    approval = load(APPROVAL)
    workflow = WORKFLOW.read_text(encoding="utf-8")

    # Immutable human approval and inert release candidate remain independent snapshots.
    assert hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest() == APPROVAL_SHA
    assert approval["reviewed_commit"] == PREREG_COMMIT
    assert approval["exact_approval_text_sha256"] == APPROVAL_SHA
    assert hashlib.sha256(CANDIDATE.read_bytes()).hexdigest() == CANDIDATE_SHA256
    assert candidate["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
    assert candidate["activation_required"] is True
    assert candidate["activation_record_present"] is False
    assert candidate["canonical_release_merge_commit"] is None
    assert candidate["single_use_window_start_utc"] is None
    assert candidate["requester_pays_authorized"] is False
    assert candidate["list_objects_v2_authorized"] is False
    assert candidate["single_workflow_dispatch_authorized"] is False
    assert candidate["execution_ready"] is False
    assert candidate["s3_requests_executed"] == 0
    assert candidate["metadata_entries_observed"] == 0
    assert candidate["empirical_result"] is None

    # Activation is a separate overlay bound to already-reviewed canonical evidence.
    assert activation["attestation_id"] == "ATTEST_HL_ARCHIVE_HOURLY_METADATA_INVENTORY_R3_RELEASE_001_CANONICAL"
    assert activation["release_id"] == "RELEASE_HL_ARCHIVE_HOURLY_METADATA_INVENTORY_R3_001"
    assert activation["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R3_RUN"
    assert activation["inventory_id"] == "HL-ARCHIVE-HOURLY-METADATA-INVENTORY-R3-001"
    assert activation["release_pr"] == 43
    assert activation["release_exact_head"] == RELEASE_HEAD
    assert activation["release_ci_run"] == 31299183537
    assert activation["release_ci_job"] == 93209089110
    assert activation["release_test_count"] == 244
    assert activation["release_ci_result"] == "SUCCESS"
    assert activation["repository_manifest_result"] == "BYTE_EXACT_PASS"
    assert activation["repository_governance_result"] == "PASS"
    assert activation["implementation_validator_result"] == "R3_IMPLEMENTATION_VALID"
    assert activation["release_validator_result"] == "R3_RELEASE_CANDIDATE_VALID"
    assert activation["release_merge_commit"] == RELEASE_MERGE
    assert activation["release_merge_verified_against_main"] is True
    assert activation["release_candidate_path"] == "research/archive_inventory/r3/R3_EXECUTION_RELEASE.json"
    assert activation["release_candidate_immutable"] is True
    assert activation["activation_anchor_commit"] == ANCHOR_COMMIT
    assert activation["single_use_window_start_utc"] == ANCHOR_UTC

    assert activation["preregistration_commit"] == PREREG_COMMIT
    assert activation["approval_merge_commit"] == APPROVAL_MERGE_COMMIT
    assert activation["approval_reviewed_commit"] == PREREG_COMMIT
    assert activation["approval_text_sha256"] == APPROVAL_SHA
    assert activation["implementation_pr"] == 42
    assert activation["implementation_commit"] == IMPLEMENTATION_COMMIT
    assert activation["implementation_exact_head_ci_commit"] == IMPLEMENTATION_HEAD
    assert activation["implementation_ci_run"] == 31297902934
    assert activation["implementation_ci_job"] == 93205871178
    assert activation["implementation_test_count"] == 236
    assert activation["implementation_ci_result"] == "SUCCESS"

    assert activation["github_event_required"] == "workflow_dispatch"
    assert activation["canonical_dispatch_ref_required"] == "refs/heads/main"
    assert activation["canonical_dispatch_sha_source"] == "github.sha"
    assert activation["manual_reviewed_commit_input_required"] is False
    assert activation["target_bucket"] == "hl-mainnet-node-data"
    assert activation["signing_region"] == "ap-northeast-1"
    assert activation["regional_virtual_hosted_endpoint"] == "hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com"
    assert activation["operation"] == "ListObjectsV2"
    assert activation["request_payer"] == "requester"
    assert activation["prefixes"] == PREFIXES

    for key, expected in {
        "maximum_one_time_budget_eur": 0.10,
        "maximum_monthly_budget_eur": 0,
        "maximum_list_requests": 48,
        "maximum_pages_per_family": 16,
        "maximum_keys_per_request": 1000,
        "maximum_total_entries": 48000,
        "maximum_total_response_bytes": 33554432,
        "maximum_runtime_seconds": 300,
        "maximum_retries_per_request": 0,
    }.items():
        assert activation[key] == expected, key

    assert activation["pagination_authorized"] is True
    assert activation["continuation_token_follow_authorized"] is True
    assert activation["continuation_token_values_retained"] is False
    assert activation["repeated_continuation_token_fails_closed"] is True
    assert activation["duplicate_key_fails_closed"] is True
    assert activation["http_redirect_following_authorized"] is False
    assert activation["start_after_authorized"] is False
    assert activation["delimiter_authorized"] is False
    assert activation["requester_pays_authorized"] is True
    assert activation["list_objects_v2_authorized"] is True
    assert activation["single_workflow_dispatch_authorized"] is True
    assert activation["rerun_authorized"] is False
    assert activation["execution_ready"] is True
    assert activation["session_s3_policy"] == "ALLOW_LISTBUCKET_EXACT_THREE_HOURLY_PREFIXES_MAX1000_ONLY"

    for key in (
        "get_object_authorized", "head_object_authorized", "get_object_attributes_authorized",
        "range_get_authorized", "list_object_versions_authorized", "list_all_my_buckets_authorized",
        "object_body_download_authorized", "decompression_authorized",
        "explorer_blocks_inventory_authorized", "replica_cmds_inventory_authorized",
        "market_data_ingestion_authorized", "larger_300_request_inventory_authorized",
    ):
        assert activation[key] is False, key
    assert all(value is False for value in activation["trading_authorizations"].values())
    assert activation["s3_requests_executed"] == 0
    assert activation["metadata_entries_observed"] == 0
    assert activation["empirical_result"] is None

    # The workflow is still manual-only and proves the active overlay before OIDC.
    assert "workflow_dispatch:" in workflow
    assert "pull_request:" not in workflow
    assert "push:" not in workflow
    assert f"EXPECTED_IMPLEMENTATION_COMMIT: {IMPLEMENTATION_COMMIT}" in workflow
    assert "EXECUTION_RELEASE_PATH: research/archive_inventory/r3/R3_EXECUTION_RELEASE_CANONICALIZATION.json" in workflow
    assert "RELEASE_CANDIDATE_PATH: research/archive_inventory/r3/R3_EXECUTION_RELEASE.json" in workflow
    assert "persist-credentials: false" in workflow
    assert "Run attempt must be 1; re-runs are forbidden" in workflow
    assert "a previous dispatch already consumed the R3 release" in workflow
    assert workflow.index("Prove canonical implementation and release before AWS OIDC") < workflow.index("Assume exact AWS role with R3-only session permissions")
    assert workflow.index("Enforce R3 single-use release before AWS OIDC") < workflow.index("Assume exact AWS role with R3-only session permissions")
    for forbidden in ("s3:GetObject", "s3:GetObjectAttributes", "s3:ListBucketVersions", "s3:ListAllMyBuckets"):
        assert forbidden not in workflow

    print("R3_ACTIVATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
