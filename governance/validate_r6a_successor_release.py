from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R6A = ROOT / "research/archive_inventory/r6a"
APPROVAL = R6A / "approvals/APPROVE_HL_ARCHIVE_LEGACY_USER_KEY_LEXICAL_R6A_001.json"
APPROVAL_TEXT = R6A / "approvals/APPROVE_HL_ARCHIVE_LEGACY_USER_KEY_LEXICAL_R6A_001.txt"
IMPLEMENTATION = R6A / "R6A_IMPLEMENTATION_CONTRACT.json"
ROLE_REUSE = R6A / "R6A_AWS_ROLE_REUSE_ANALYSIS.json"
PREDECESSOR = R6A / "R6A_EXECUTION_RELEASE_001_CONSUMPTION.json"
SUCCESSOR = R6A / "R6A_EXECUTION_RELEASE_002_CANONICALIZATION.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-legacy-user-key-lexical-r6a-successor.yml"

PREREG = "870fdf3e10a761d6c4589d43def8e436f3a129b5"
APPROVAL_MERGE = "06c0086f80cdbc3d058bdeea64b618da276e95ec"
APPROVAL_SHA = "b24c67f527a320e533408fd821d10b5e2ea01d020c837e87ae5e5bbd386c94ed"
IMPLEMENTATION_COMMIT = "806a054129de1f7d2480373be739ba7eea13258d"
FAILED_RUN = 31327463448
FAILED_JOB = 93280039214
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"
OBJECT_KEY = "node_fills/hourly/20250727/8.lz4"
OBJECT_ARN = f"arn:aws:s3:::hl-mainnet-node-data/{OBJECT_KEY}"
APPROVED_AGGREGATES = [
    "nonempty_record_count",
    "pair_string_object_record_count",
    "leading_string_count",
    "leading_string_length_42_count",
    "leading_string_0x40hex_count",
    "leading_string_lowercase_0x40hex_count",
    "leading_string_non_0x40hex_count",
]


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    approval = load(APPROVAL)
    impl = load(IMPLEMENTATION)
    reuse = load(ROLE_REUSE)
    predecessor = load(PREDECESSOR)
    successor = load(SUCCESSOR)
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest() == APPROVAL_SHA
    assert approval["reviewed_commit"] == PREREG
    assert approval["exact_approval_text_sha256"] == APPROVAL_SHA
    assert approval["maximum_one_time_budget_eur"] == 0.10
    assert approval["maximum_monthly_budget_eur"] == 0
    assert approval["maximum_get_object_requests"] == 1
    assert approval["maximum_requests_per_object"] == 1
    assert approval["maximum_retries_per_request"] == 0
    assert all(value is False for value in approval["retention_authorizations"].values())
    assert all(value is False for value in approval["downstream_authorizations"].values())
    assert all(value is False for value in approval["trading_authorizations"].values())

    assert impl["approval_merge_commit"] == APPROVAL_MERGE
    assert impl["approval_text_sha256"] == APPROVAL_SHA
    assert impl["reused_dedicated_role_arn"] == ROLE_ARN
    assert impl["aws_role_mutation_required"] is False
    assert impl["aws_role_mutation_authorized"] is False
    assert impl["retained_aggregates_only"] == APPROVED_AGGREGATES
    assert all(value is False for value in impl["trading_authorizations"].values())
    assert reuse["reused_role_arn"] == ROLE_ARN
    assert reuse["r6a_session_scope"]["allowed_object_arns"] == [OBJECT_ARN]
    assert reuse["r6a_session_scope"]["strict_subset_of_persistent_role"] is True
    assert reuse["aws_iam_mutation_performed"] is False

    assert predecessor["release_id"] == "RELEASE_HL_ARCHIVE_LEGACY_USER_KEY_LEXICAL_R6A_001"
    assert predecessor["status"] == "CONSUMED_BY_PRE_OIDC_FAILED_DISPATCH_ZERO_S3"
    assert predecessor["workflow_run_id"] == FAILED_RUN
    assert predecessor["workflow_job_id"] == FAILED_JOB
    assert predecessor["dispatch_consumed_release"] is True
    assert predecessor["rerun_authorized"] is False
    assert predecessor["pre_oidc_gate_failed"] is True
    assert predecessor["aws_oidc_role_assumption_attempted"] is False
    assert predecessor["collector_executed"] is False
    assert predecessor["s3_requests_executed"] == 0
    assert predecessor["get_object_requests_executed"] == 0
    assert predecessor["compressed_bytes_downloaded"] == 0
    assert predecessor["decompressed_bytes_processed"] == 0
    assert predecessor["network_budget_consumed"] is False
    assert predecessor["approved_total_get_object_budget"] == 1
    assert predecessor["remaining_approved_get_object_budget"] == 1
    assert predecessor["successor_policy"]["successor_release_permitted"] is True
    assert predecessor["successor_policy"]["maximum_aggregate_get_object_requests_across_r6a_release_chain"] == 1
    assert predecessor["successor_policy"]["scope_expansion_authorized"] is False
    assert predecessor["empirical_result"] is None
    assert all(value is False for value in predecessor["trading_authorizations"].values())

    assert successor["release_id"] == "RELEASE_HL_ARCHIVE_LEGACY_USER_KEY_LEXICAL_R6A_002"
    assert successor["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R6A_SUCCESSOR_RUN"
    assert successor["predecessor_release_id"] == predecessor["release_id"]
    assert successor["predecessor_workflow_run_id"] == FAILED_RUN
    assert successor["predecessor_workflow_job_id"] == FAILED_JOB
    assert successor["predecessor_dispatch_consumed"] is True
    assert successor["predecessor_pre_oidc_gate_failed"] is True
    assert successor["predecessor_aws_oidc_role_assumption_attempted"] is False
    assert successor["predecessor_s3_requests_executed"] == 0
    assert successor["predecessor_network_budget_consumed"] is False
    assert successor["aggregate_get_object_requests_already_executed_across_r6a_chain"] == 0
    assert successor["maximum_aggregate_get_object_requests_across_r6a_chain"] == 1
    assert successor["remaining_get_object_request_budget"] == 1
    assert successor["preregistration_commit"] == PREREG
    assert successor["approval_merge_commit"] == APPROVAL_MERGE
    assert successor["approval_text_sha256"] == APPROVAL_SHA
    assert successor["canonical_implementation_commit"] == IMPLEMENTATION_COMMIT
    assert successor["dedicated_role_arn"] == ROLE_ARN
    assert successor["aws_role_mutation_required"] is False
    assert successor["aws_role_mutation_authorized"] is False
    assert successor["aws_role_mutation_performed"] is False
    assert successor["session_policy_strict_subset_of_persistent_role"] is True
    assert successor["target_bucket"] == "hl-mainnet-node-data"
    assert successor["signing_region"] == "ap-northeast-1"
    assert successor["object_key"] == OBJECT_KEY
    assert successor["object_size_bytes"] == 12726384
    assert successor["object_etag"] == '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"'
    assert successor["expected_compressed_sha256"] == "f12d33da9733dbb71f02f9910fc187b9dd4b8f9dae1102b7dfe7690094542622"
    assert successor["expected_decompressed_byte_count"] == 62169139
    assert successor["expected_nonempty_record_count"] == 162815
    assert successor["maximum_one_time_budget_eur"] == 0.10
    assert successor["maximum_monthly_budget_eur"] == 0
    assert successor["maximum_get_object_requests_this_successor"] == 1
    assert successor["maximum_requests_per_object"] == 1
    assert successor["maximum_total_compressed_bytes"] == 12726384
    assert successor["maximum_total_decompressed_bytes"] == 134217728
    assert successor["maximum_runtime_seconds"] == 120
    assert successor["maximum_retries_per_request"] == 0
    for key in ("requester_pays_authorized", "get_object_authorized", "object_body_download_authorized", "decompression_authorized", "lexical_classification_authorized", "single_workflow_dispatch_authorized"):
        assert successor[key] is True, key
    for key in ("head_object_authorized", "range_get_authorized", "list_objects_v2_authorized", "list_object_versions_authorized", "list_all_my_buckets_authorized", "http_redirect_following_authorized", "raw_compressed_object_retention_authorized", "raw_decompressed_payload_retention_authorized", "record_payload_retention_authorized", "payload_values_in_evidence_authorized", "string_values_in_evidence_authorized", "numeric_values_in_evidence_authorized", "leading_string_retention_authorized", "wallet_address_retention_authorized", "leading_string_hash_retention_authorized", "distinct_address_set_retention_authorized", "wallet_reconstruction_authorized", "entity_clustering_authorized", "copyability_analysis_authorized", "pnl_or_alpha_analysis_authorized", "market_data_ingestion_authorized", "rerun_authorized", "release_consumed", "scope_expansion_authorized", "new_human_budget_authority_created"):
        assert successor[key] is False, key
    assert successor["retained_aggregates_only"] == APPROVED_AGGREGATES
    assert successor["s3_requests_executed"] == 0
    assert successor["compressed_bytes_downloaded"] == 0
    assert successor["decompressed_bytes_processed"] == 0
    assert successor["empirical_result"] is None
    assert all(value is False for value in successor["trading_authorizations"].values())

    assert workflow.startswith("name: Hyperliquid Archive Hourly Body Schema Pilot R4\nrun-name: R6A successor legacy user-key lexical confirmation\n")
    assert "workflow_dispatch:" in workflow
    assert "pull_request:" not in workflow
    assert "push:" not in workflow
    assert "id-token: write" in workflow
    assert "actions: read" in workflow
    assert "contents: read" in workflow
    assert "persist-credentials: false" in workflow
    assert f"EXPECTED_IMPLEMENTATION_COMMIT: {IMPLEMENTATION_COMMIT}" in workflow
    assert "PENDING_CANONICAL_IMPLEMENTATION_MERGE" not in workflow
    assert "R6A_EXECUTION_RELEASE_002_CANONICALIZATION.json" in workflow
    assert "R6A_EXECUTION_RELEASE_001_CONSUMPTION.json" in workflow
    assert "hyperliquid-archive-legacy-user-key-lexical-r6a-successor.yml/runs" in workflow
    assert "hyperliquid-archive-legacy-user-key-lexical-r6a.yml/runs" not in workflow
    assert f"R6A_ROLE_ARN: {ROLE_ARN}" in workflow
    assert OBJECT_ARN in workflow
    assert '"Action":"s3:GetObject"' in workflow
    for forbidden in ("s3:ListBucket", "s3:GetObjectVersion", "s3:GetObjectAttributes", "s3:ListAllMyBuckets"):
        assert forbidden not in workflow
    assert workflow.index("Prove successor release before AWS OIDC") < workflow.index("Assume unchanged dedicated AWS role with exact-one-object successor session")
    assert workflow.index("Enforce successor single-use release before AWS OIDC") < workflow.index("Assume unchanged dedicated AWS role with exact-one-object successor session")

    print("R6A_SUCCESSOR_RELEASE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
