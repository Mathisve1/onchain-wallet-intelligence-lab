from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R5 = ROOT / "research/archive_inventory/r5"
RELEASE = R5 / "R5_EXECUTION_RELEASE.json"
ACTIVATION = R5 / "R5_EXECUTION_RELEASE_CANONICALIZATION.json"
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
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"
OBJECT_KEY = "node_fills/hourly/20250727/8.lz4"
OBJECT_ARN = f"arn:aws:s3:::hl-mainnet-node-data/{OBJECT_KEY}"
EXPECTED_FILE_HASHES = {
    ".github/workflows/hyperliquid-archive-legacy-format-fingerprint-r5.yml": "4e788d5386590abc43aac116e6b26aaa348707538fd0309cf40a46eaca80219c",
    "research/archive_inventory/r5/R5_AWS_ROLE_REUSE_ANALYSIS.json": "c52bf0c3d06c04831936a9f159c8fdbc7fade4fabb8b3b2a9455147796a86754",
    "research/archive_inventory/r5/R5_IMPLEMENTATION_CONTRACT.json": "83b1bec4280ddcab0d7b6c9f4f7791551fe6b75e68e86a715b4985f06cccc8d6",
    "research/archive_inventory/r5/collector.py": "028f5f6052f4aa7dcc3e00804afbb1f965317a985859d83c6c5c179a5592ed25",
}


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    release = load(RELEASE)
    impl = load(IMPLEMENTATION)
    approval = load(APPROVAL)
    reuse = load(ROLE_REUSE)

    assert release["release_id"] == "RELEASE_HL_ARCHIVE_LEGACY_FORMAT_FINGERPRINT_R5_001"
    assert release["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
    assert release["pilot_id"] == impl["pilot_id"] == "HL-ARCHIVE-LEGACY-FORMAT-FINGERPRINT-R5-001"
    assert release["preregistration_commit"] == impl["preregistration_commit"] == PREREG_MERGE
    assert release["approval_merge_commit"] == impl["approval_merge_commit"] == APPROVAL_MERGE
    assert release["approval_id"] == approval["approval_id"]
    assert release["approval_text_sha256"] == impl["approval_text_sha256"] == approval["exact_approval_text_sha256"] == APPROVAL_SHA
    assert sha256(APPROVAL_TEXT) == APPROVAL_SHA
    assert release["implementation_pr"] == 58
    assert release["implementation_reviewed_exact_head"] == IMPLEMENTATION_HEAD
    assert release["implementation_commit"] == IMPLEMENTATION_MERGE
    assert release["implementation_file_sha256"] == EXPECTED_FILE_HASHES
    for relative, expected in EXPECTED_FILE_HASHES.items():
        if relative == ".github/workflows/hyperliquid-archive-legacy-format-fingerprint-r5.yml" and ACTIVATION.exists():
            continue
        assert sha256(ROOT / relative) == expected, relative

    assert release["dedicated_role_arn"] == reuse["reused_role_arn"] == ROLE_ARN
    role = release["role_reuse_evidence"]
    assert role["r4_role_operator_attestation_merge"] == "c45527941dea7d152e332327ebd0593dc2413bea"
    assert role["r4_sts_preflight_evidence_merge"] == "a91f0849e8cf14b6924da73ca2b72595deab5d8d"
    assert role["r4_body_evidence_merge"] == "fe06874aeeb958d375a27100378f89bd25b4741b"
    assert role["canonical_trust_policy_sha256"] == "2ebb60a7747a636a475a23016951265fe377fd9d68f2d9f3a63e33f3bc0189b4"
    assert role["canonical_permission_policy_sha256"] == "14d055105b80e0c41462d4934bbaa8d860b0aeda9f2f1b9529267fd0d4d3613d"
    assert role["aws_role_mutation_required"] is False
    assert role["aws_role_mutation_authorized"] is False
    assert role["aws_role_mutation_performed"] is False
    assert release["session_s3_policy"] == "ALLOW_GETOBJECT_EXACT_LEGACY_OBJECT_ONLY"
    assert release["session_policy_strict_subset_of_persistent_role"] is True
    assert reuse["r5_session_scope"]["allowed_object_arns"] == [OBJECT_ARN]

    assert release["target_bucket"] == "hl-mainnet-node-data"
    assert release["signing_region"] == "ap-northeast-1"
    assert release["object_key"] == OBJECT_KEY
    assert release["object_size_bytes"] == 12726384
    assert release["object_etag"] == '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"'
    assert release["expected_compressed_sha256"] == "f12d33da9733dbb71f02f9910fc187b9dd4b8f9dae1102b7dfe7690094542622"
    assert release["expected_decompressed_byte_count"] == 62169139

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
        assert release[key] == expected, key

    for key in (
        "if_match_etag_required", "exact_content_length_required", "exact_response_etag_required",
        "require_request_charged_requester_on_success", "exact_compressed_sha256_required",
        "exact_decompressed_byte_count_required", "lz4_frame_stream_only", "strict_utf8_decode",
        "strict_json_duplicate_keys_rejected", "strict_json_nonfinite_constants_rejected",
    ):
        assert release[key] is True, key
    assert release["alternate_decompressor_fallback_authorized"] is False

    for key in (
        "requester_pays_authorized_by_candidate", "get_object_authorized_by_candidate",
        "decompression_authorized_by_candidate", "format_classification_authorized_by_candidate",
        "single_workflow_dispatch_authorized", "rerun_authorized", "execution_ready",
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
        assert release[key] is False, key
    assert release["single_use_window_start_utc"] is None
    assert all(value is False for value in release["trading_authorizations"].values())
    assert release["s3_requests_executed"] == 0
    assert release["compressed_bytes_downloaded"] == 0
    assert release["decompressed_bytes_processed"] == 0
    assert release["empirical_result"] is None
    assert release["activation_required"] is True
    assert release["activation_path"] == "research/archive_inventory/r5/R5_EXECUTION_RELEASE_CANONICALIZATION.json"
    workflow = WORKFLOW.read_text(encoding="utf-8")
    if ACTIVATION.exists():
        activation = load(ACTIVATION)
        assert activation["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R5_RUN"
        assert activation["implementation_commit"] == "40bc4d138c71a4367c9415982f58bcd24c5a57eb"
        assert activation["release_candidate_merge_commit"] == "0ed4aed8f2361e995122a0fc57c84135952f70d5"
        assert activation["activation_anchor_commit"] == "308054c3e69a79a4be2c395e3c47fe725b5abc6c"
        assert activation["single_use_window_start_utc"] == "2026-08-09T14:54:18Z"
        assert activation["single_workflow_dispatch_authorized"] is True
        assert activation["rerun_authorized"] is False
        assert activation["s3_requests_executed"] == 0
        assert activation["empirical_result"] is None
        assert "EXPECTED_IMPLEMENTATION_COMMIT: 40bc4d138c71a4367c9415982f58bcd24c5a57eb" in workflow
        assert "EXPECTED_IMPLEMENTATION_COMMIT: PENDING_CANONICAL_IMPLEMENTATION_MERGE" not in workflow
    else:
        assert "EXPECTED_IMPLEMENTATION_COMMIT: PENDING_CANONICAL_IMPLEMENTATION_MERGE" in workflow
    assert "R5_EXECUTION_RELEASE_CANONICALIZATION.json" in workflow
    assert "R5_EXECUTION_RELEASE.json" in workflow

    print("R5_RELEASE_CANDIDATE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
