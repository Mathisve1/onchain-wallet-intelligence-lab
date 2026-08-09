from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R5 = ROOT / "research/archive_inventory/r5"
ACTIVATION = R5 / "R5_EXECUTION_RELEASE_CANONICALIZATION.json"
ANCHOR = R5 / "R5_EXECUTION_RELEASE_ACTIVATION_ANCHOR.json"
CANDIDATE = R5 / "R5_EXECUTION_RELEASE.json"
IMPLEMENTATION = R5 / "R5_IMPLEMENTATION_CONTRACT.json"
APPROVAL = R5 / "approvals/APPROVE_HL_ARCHIVE_LEGACY_FORMAT_FINGERPRINT_R5_001.json"
APPROVAL_TEXT = R5 / "approvals/APPROVE_HL_ARCHIVE_LEGACY_FORMAT_FINGERPRINT_R5_001.txt"
ROLE_REUSE = R5 / "R5_AWS_ROLE_REUSE_ANALYSIS.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-legacy-format-fingerprint-r5.yml"
COLLECTOR = R5 / "collector.py"

PREREG_MERGE = "58f724d7f0208a43f7462abd80e1e69d995acff9"
APPROVAL_MERGE = "c22e28074ba2e95e1fe88912c364124e01eb0ff7"
APPROVAL_SHA = "667f94a66ea07296162ae0627a9cf7fc5b439b3f8312c8617ece923159f5ddc8"
IMPLEMENTATION_HEAD = "defc33f7316acee3640cbba360690f4fc969b13a"
IMPLEMENTATION_MERGE = "40bc4d138c71a4367c9415982f58bcd24c5a57eb"
RELEASE_CANDIDATE_MERGE = "0ed4aed8f2361e995122a0fc57c84135952f70d5"
RELEASE_CANDIDATE_SHA256 = "9661c8a90fae9cd920e4500a3dac2b6c41fbb0d8c1889f8d94006ddf16833510"
ANCHOR_COMMIT = "308054c3e69a79a4be2c395e3c47fe725b5abc6c"
WINDOW_START = "2026-08-09T14:54:18Z"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"
OBJECT_KEY = "node_fills/hourly/20250727/8.lz4"
OBJECT_ARN = f"arn:aws:s3:::hl-mainnet-node-data/{OBJECT_KEY}"
COLLECTOR_SHA256 = "028f5f6052f4aa7dcc3e00804afbb1f965317a985859d83c6c5c179a5592ed25"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    activation = load(ACTIVATION)
    anchor = load(ANCHOR)
    candidate = load(CANDIDATE)
    impl = load(IMPLEMENTATION)
    approval = load(APPROVAL)
    reuse = load(ROLE_REUSE)

    assert activation["release_id"] == candidate["release_id"] == "RELEASE_HL_ARCHIVE_LEGACY_FORMAT_FINGERPRINT_R5_001"
    assert activation["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R5_RUN"
    assert activation["pilot_id"] == candidate["pilot_id"] == impl["pilot_id"]
    assert activation["preregistration_commit"] == candidate["preregistration_commit"] == PREREG_MERGE
    assert activation["approval_merge_commit"] == candidate["approval_merge_commit"] == APPROVAL_MERGE
    assert activation["approval_id"] == approval["approval_id"]
    assert activation["approval_text_sha256"] == candidate["approval_text_sha256"] == APPROVAL_SHA
    assert sha256(APPROVAL_TEXT) == APPROVAL_SHA
    assert activation["implementation_reviewed_exact_head"] == candidate["implementation_reviewed_exact_head"] == IMPLEMENTATION_HEAD
    assert activation["implementation_commit"] == candidate["implementation_commit"] == IMPLEMENTATION_MERGE
    assert activation["release_candidate_merge_commit"] == RELEASE_CANDIDATE_MERGE
    assert sha256(CANDIDATE) == RELEASE_CANDIDATE_SHA256

    assert anchor["release_id"] == activation["release_id"]
    assert anchor["status"] == "R5_ACTIVATION_WINDOW_ANCHOR_ONLY_NO_AUTHORITY"
    assert anchor["release_candidate_merge_commit"] == RELEASE_CANDIDATE_MERGE
    assert anchor["implementation_commit"] == IMPLEMENTATION_MERGE
    for key in (
        "execution_authorized", "requester_pays_authorized", "get_object_authorized",
        "decompression_authorized", "format_classification_authorized",
        "single_workflow_dispatch_authorized", "rerun_authorized", "aws_role_mutation_authorized",
    ):
        assert anchor[key] is False, key
    assert anchor["s3_requests_executed"] == 0
    assert anchor["empirical_result"] is None
    assert activation["activation_anchor_commit"] == ANCHOR_COMMIT
    assert activation["single_use_window_start_utc"] == WINDOW_START
    start = datetime.fromisoformat(WINDOW_START.replace("Z", "+00:00")).astimezone(timezone.utc)
    assert start == datetime(2026, 8, 9, 14, 54, 18, tzinfo=timezone.utc)

    # Candidate remains immutable and inert; only the separate activation opens the one run.
    assert candidate["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
    assert candidate["requester_pays_authorized_by_candidate"] is False
    assert candidate["get_object_authorized_by_candidate"] is False
    assert candidate["decompression_authorized_by_candidate"] is False
    assert candidate["format_classification_authorized_by_candidate"] is False
    assert candidate["single_workflow_dispatch_authorized"] is False
    assert candidate["rerun_authorized"] is False
    assert candidate["single_use_window_start_utc"] is None
    assert candidate["execution_ready"] is False
    assert candidate["s3_requests_executed"] == 0
    assert candidate["empirical_result"] is None

    assert activation["github_event_required"] == "workflow_dispatch"
    assert activation["canonical_dispatch_ref_required"] == "refs/heads/main"
    assert activation["canonical_dispatch_sha_source"] == "github.sha"
    assert activation["dedicated_role_arn"] == reuse["reused_role_arn"] == ROLE_ARN
    assert activation["aws_role_mutation_required"] is False
    assert activation["aws_role_mutation_authorized"] is False
    assert activation["aws_role_mutation_performed"] is False
    assert activation["session_s3_policy"] == "ALLOW_GETOBJECT_EXACT_LEGACY_OBJECT_ONLY"
    assert activation["session_policy_strict_subset_of_persistent_role"] is True
    assert reuse["r5_session_scope"]["allowed_object_arns"] == [OBJECT_ARN]
    assert reuse["aws_iam_mutation_performed"] is False
    assert reuse["new_sts_preflight_required"] is False

    assert activation["target_bucket"] == "hl-mainnet-node-data"
    assert activation["signing_region"] == "ap-northeast-1"
    assert activation["object_key"] == OBJECT_KEY
    assert activation["object_size_bytes"] == 12726384
    assert activation["object_etag"] == '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"'
    assert activation["expected_compressed_sha256"] == "f12d33da9733dbb71f02f9910fc187b9dd4b8f9dae1102b7dfe7690094542622"
    assert activation["expected_decompressed_byte_count"] == 62169139
    for key, expected in {
        "maximum_one_time_budget_eur": 0.10,
        "maximum_monthly_budget_eur": 0,
        "maximum_get_object_requests": 1,
        "maximum_requests_per_object": 1,
        "maximum_total_compressed_bytes": 12726384,
        "maximum_total_decompressed_bytes": 134217728,
        "maximum_runtime_seconds": 120,
        "maximum_retries_per_request": 0,
        "maximum_record_bytes": 16777216,
        "maximum_records_parsed": 5000000,
        "maximum_schema_nesting_depth": 16,
        "maximum_unique_field_paths": 4096,
        "maximum_unique_structural_signatures": 256,
    }.items():
        assert activation[key] == expected, key

    for key in (
        "if_match_etag_required", "exact_content_length_required", "exact_response_etag_required",
        "require_request_charged_requester_on_success", "exact_compressed_sha256_required",
        "exact_decompressed_byte_count_required", "lz4_frame_stream_only", "strict_utf8_decode",
        "strict_json_duplicate_keys_rejected", "strict_json_nonfinite_constants_rejected",
        "requester_pays_authorized", "get_object_authorized", "decompression_authorized",
        "format_classification_authorized", "single_workflow_dispatch_authorized", "execution_ready",
    ):
        assert activation[key] is True, key
    assert activation["alternate_decompressor_fallback_authorized"] is False
    assert activation["rerun_authorized"] is False
    for key in (
        "head_object_authorized", "range_get_authorized", "list_objects_v2_authorized",
        "list_object_versions_authorized", "list_all_my_buckets_authorized", "http_redirect_following_authorized",
        "raw_compressed_object_retention_authorized", "raw_decompressed_payload_retention_authorized",
        "record_payload_retention_authorized", "wallet_address_retention_from_body_authorized",
        "payload_values_in_evidence_authorized", "string_values_in_evidence_authorized",
        "numeric_values_in_evidence_authorized", "string_element_semantic_wallet_or_user_label_authorized",
        "schema_equivalence_inference_authorized", "semantic_equivalence_inference_authorized",
        "wallet_reconstruction_authorized", "entity_clustering_authorized", "copyability_analysis_authorized",
        "pnl_or_alpha_analysis_authorized", "market_data_ingestion_authorized",
    ):
        assert activation[key] is False, key
    assert all(value is False for value in activation["trading_authorizations"].values())
    assert activation["s3_requests_executed"] == 0
    assert activation["compressed_bytes_downloaded"] == 0
    assert activation["decompressed_bytes_processed"] == 0
    assert activation["empirical_result"] is None

    # Executable bytes: only the workflow binding changes; collector remains canonical implementation bytes.
    assert sha256(COLLECTOR) == COLLECTOR_SHA256
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert f"EXPECTED_IMPLEMENTATION_COMMIT: {IMPLEMENTATION_MERGE}" in workflow
    assert "EXPECTED_IMPLEMENTATION_COMMIT: PENDING_CANONICAL_IMPLEMENTATION_MERGE" not in workflow
    assert workflow.startswith("name: Hyperliquid Archive Hourly Body Schema Pilot R4\nrun-name: R5 legacy format fingerprint\n")
    assert '"Action":"s3:GetObject"' in workflow
    assert OBJECT_ARN in workflow
    assert "node_fills_by_block/hourly/20250727/8.lz4" not in workflow
    assert workflow.index("Prove canonical R5 implementation and release before AWS OIDC") < workflow.index("Assume unchanged dedicated AWS role with exact-one-object R5 session permissions")
    assert workflow.index("Enforce R5 single-use release before AWS OIDC") < workflow.index("Assume unchanged dedicated AWS role with exact-one-object R5 session permissions")

    print("R5_ACTIVATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
