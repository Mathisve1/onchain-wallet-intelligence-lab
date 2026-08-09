from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r5"
CANDIDATE = BASE / "R5_EXECUTION_RELEASE_CANDIDATE.json"
APPROVAL = BASE / "approvals/APPROVE_HL_ARCHIVE_LEGACY_FORMAT_FINGERPRINT_R5_001.json"
APPROVAL_TEXT = BASE / "approvals/APPROVE_HL_ARCHIVE_LEGACY_FORMAT_FINGERPRINT_R5_001.txt"
IMPL = BASE / "R5_IMPLEMENTATION_CONTRACT.json"
ROLE_REUSE = BASE / "R5_AWS_ROLE_REUSE_ANALYSIS.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-legacy-format-fingerprint-r5.yml"
COLLECTOR = BASE / "collector.py"
RUNTIME_RELEASE = BASE / "R5_EXECUTION_RELEASE.json"
ACTIVATION = BASE / "R5_EXECUTION_RELEASE_CANONICALIZATION.json"

APPROVAL_SHA = "667f94a66ea07296162ae0627a9cf7fc5b439b3f8312c8617ece923159f5ddc8"
IMPLEMENTATION_HEAD = "9128783516942ee40050986fb33c467279eba700"
EXPECTED_FILES = {
    ".github/workflows/hyperliquid-archive-legacy-format-fingerprint-r5.yml": "4e788d7b7516477d940d2aa10c23f1ba8769471369395a3e012f02f48ceb8b37",
    "research/archive_inventory/r5/R5_AWS_ROLE_REUSE_ANALYSIS.json": "c52b4552eedec2406b9f9456efb24d76e81e1d49bbd4aa7690e1801761da4d25",
    "research/archive_inventory/r5/R5_IMPLEMENTATION_CONTRACT.json": "83b70e109f354045123679b0a40ff7cbff1394c6e9039429d7513559d2ad80bb",
    "research/archive_inventory/r5/collector.py": "028190a07daff9527db1c2175134095882425af3864d587d3ca0686698d14f71",
}


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    candidate = load(CANDIDATE)
    approval = load(APPROVAL)
    impl = load(IMPL)
    role_reuse = load(ROLE_REUSE)

    assert hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest() == APPROVAL_SHA
    assert candidate["release_id"] == "RELEASE_HL_ARCHIVE_LEGACY_FORMAT_FINGERPRINT_R5_001"
    assert candidate["status"] == "RELEASE_CANDIDATE_INERT_AWAITING_CANONICAL_ACTIVATION"
    assert candidate["pilot_id"] == "HL-ARCHIVE-LEGACY-FORMAT-FINGERPRINT-R5-001"
    assert candidate["preregistration_commit"] == "58f724d7f0208a43f7462abd80e1e69d995acff9"
    assert candidate["approval_merge_commit"] == "c22e28074ba2e95e1fe88912c364124e01eb0ff7"
    assert candidate["approval_text_sha256"] == APPROVAL_SHA
    assert candidate["implementation_pr"] == 58
    assert candidate["implementation_reviewed_exact_head"] == IMPLEMENTATION_HEAD
    assert candidate["implementation_file_sha256"] == EXPECTED_FILES

    for path_text, expected in EXPECTED_FILES.items():
        path = ROOT / path_text
        assert path.is_file(), path
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, path

    assert approval["reviewed_commit"] == candidate["preregistration_commit"]
    assert approval["exact_approval_text_sha256"] == APPROVAL_SHA
    assert approval["approval_scope"] == "IMPLEMENTATION_AND_LATER_SEPARATE_RELEASE_PATH_ONLY"
    assert approval["execution_authorized_by_this_record"] is False
    assert approval["request_authorized_by_this_record"] is False

    assert impl["status"] == "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION"
    assert impl["approval_merge_commit"] == candidate["approval_merge_commit"]
    assert impl["approval_text_sha256"] == APPROVAL_SHA
    assert impl["execution_release_present"] is False
    assert impl["execution_authorized"] is False
    assert impl["s3_requests_executed"] == 0
    assert role_reuse["aws_iam_mutation_performed"] is False
    assert role_reuse["current_r5_network_authority"] is False

    assert candidate["dedicated_role_arn"] == "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"
    assert candidate["aws_role_mutation_required"] is False
    assert candidate["aws_role_mutation_authorized"] is False
    assert candidate["aws_role_mutation_performed"] is False
    assert candidate["session_s3_policy"] == "ALLOW_GETOBJECT_EXACT_LEGACY_OBJECT_ONLY"
    assert candidate["session_policy_strict_subset_of_persistent_role"] is True

    assert candidate["target_bucket"] == "hl-mainnet-node-data"
    assert candidate["signing_region"] == "ap-northeast-1"
    assert candidate["object_key"] == "node_fills/hourly/20250727/8.lz4"
    assert candidate["object_size_bytes"] == 12726384
    assert candidate["object_etag"] == '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"'
    assert candidate["expected_compressed_sha256"] == "f12d33da9733dbb71f02f9910fc187b9dd4b8f9dae1102b7dfe7690094542622"
    assert candidate["expected_decompressed_byte_count"] == 62169139
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
        assert candidate[key] == expected, key

    for key in (
        "requester_pays_authorized_by_candidate", "get_object_authorized_by_candidate",
        "decompression_authorized_by_candidate", "format_classification_authorized_by_candidate",
        "single_workflow_dispatch_authorized", "rerun_authorized", "execution_ready",
        "head_object_authorized", "range_get_authorized", "list_objects_v2_authorized",
        "list_object_versions_authorized", "list_all_my_buckets_authorized",
        "http_redirect_following_authorized", "raw_compressed_object_retention_authorized",
        "raw_decompressed_payload_retention_authorized", "record_payload_retention_authorized",
        "wallet_address_retention_from_body_authorized", "payload_values_in_evidence_authorized",
        "string_values_in_evidence_authorized", "numeric_values_in_evidence_authorized",
        "string_element_semantic_wallet_or_user_label_authorized", "schema_equivalence_inference_authorized",
        "semantic_equivalence_inference_authorized", "wallet_reconstruction_authorized",
        "entity_clustering_authorized", "copyability_analysis_authorized", "pnl_or_alpha_analysis_authorized",
        "market_data_ingestion_authorized",
    ):
        assert candidate[key] is False, key
    assert candidate["single_use_window_start_utc"] is None
    assert all(value is False for value in candidate["trading_authorizations"].values())
    assert candidate["s3_requests_executed"] == 0
    assert candidate["compressed_bytes_downloaded"] == 0
    assert candidate["decompressed_bytes_processed"] == 0
    assert candidate["empirical_result"] is None
    assert candidate["activation_required"] is True
    assert candidate["activation_path"] == "research/archive_inventory/r5/R5_EXECUTION_RELEASE_CANONICALIZATION.json"

    # Candidate cannot be mistaken for runtime authority.
    assert not RUNTIME_RELEASE.exists(), RUNTIME_RELEASE
    assert not ACTIVATION.exists(), ACTIVATION
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "EXPECTED_IMPLEMENTATION_COMMIT: PENDING_CANONICAL_IMPLEMENTATION_MERGE" in workflow

    print("R5_RELEASE_CANDIDATE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
