from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R5 = ROOT / "research/archive_inventory/r5"
PREREG = R5 / "LEGACY_FORMAT_FINGERPRINT_R5_CONTRACT.json"
APPROVAL = R5 / "approvals/APPROVE_HL_ARCHIVE_LEGACY_FORMAT_FINGERPRINT_R5_001.json"
APPROVAL_TEXT = R5 / "approvals/APPROVE_HL_ARCHIVE_LEGACY_FORMAT_FINGERPRINT_R5_001.txt"
IMPLEMENTATION = R5 / "R5_IMPLEMENTATION_CONTRACT.json"
ROLE_REUSE = R5 / "R5_AWS_ROLE_REUSE_ANALYSIS.json"
COLLECTOR = R5 / "collector.py"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-legacy-format-fingerprint-r5.yml"
R4_LZ4 = ROOT / "research/archive_inventory/r4/lz4_frame.py"
R4_PERMISSION = ROOT / "research/archive_inventory/r4/R4_IAM_POLICY_TEMPLATE.json"
R4_TRUST = ROOT / "research/archive_inventory/r4/R4_OIDC_TRUST_POLICY_TEMPLATE.json"
RELEASE = R5 / "R5_EXECUTION_RELEASE.json"
ACTIVATION = R5 / "R5_EXECUTION_RELEASE_CANONICALIZATION.json"

PREREG_MERGE = "58f724d7f0208a43f7462abd80e1e69d995acff9"
APPROVAL_MERGE = "c22e28074ba2e95e1fe88912c364124e01eb0ff7"
APPROVAL_SHA = "667f94a66ea07296162ae0627a9cf7fc5b439b3f8312c8617ece923159f5ddc8"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"
OBJECT_KEY = "node_fills/hourly/20250727/8.lz4"
OBJECT_ARN = f"arn:aws:s3:::hl-mainnet-node-data/{OBJECT_KEY}"
TRUST_HASH = "2ebb60a7747a636a475a23016951265fe377fd9d68f2d9f3a63e33f3bc0189b4"
PERMISSION_HASH = "14d055105b80e0c41462d4934bbaa8d860b0aeda9f2f1b9529267fd0d4d3613d"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def imported_roots(source: str) -> set[str]:
    tree = ast.parse(source)
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def main() -> int:
    prereg = load(PREREG)
    approval = load(APPROVAL)
    impl = load(IMPLEMENTATION)
    reuse = load(ROLE_REUSE)
    permission = load(R4_PERMISSION)
    trust = load(R4_TRUST)
    collector = COLLECTOR.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest() == APPROVAL_SHA
    assert approval["reviewed_commit"] == PREREG_MERGE
    assert approval["exact_approval_text_sha256"] == APPROVAL_SHA
    assert impl["pilot_id"] == prereg["pilot_id"] == "HL-ARCHIVE-LEGACY-FORMAT-FINGERPRINT-R5-001"
    assert impl["status"] == "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION"
    assert impl["preregistration_commit"] == PREREG_MERGE
    assert impl["approval_merge_commit"] == APPROVAL_MERGE
    assert impl["approval_text_sha256"] == APPROVAL_SHA

    obj = impl["object"]
    target = prereg["exact_future_network_target"]
    assert obj["key"] == target["key"] == OBJECT_KEY
    assert obj["expected_size_bytes"] == target["expected_size_bytes"] == 12726384
    assert obj["expected_etag"] == target["expected_etag"] == '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"'
    assert obj["expected_compressed_sha256"] == target["expected_compressed_sha256"] == "f12d33da9733dbb71f02f9910fc187b9dd4b8f9dae1102b7dfe7690094542622"
    assert obj["expected_decompressed_byte_count"] == target["expected_decompressed_byte_count"] == 62169139
    assert impl["target_bucket"] == "hl-mainnet-node-data"
    assert impl["signing_region"] == "ap-northeast-1"
    assert impl["regional_virtual_hosted_endpoint"] == "hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com"

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
        assert impl[key] == expected, key

    for key in (
        "request_counter_incremented_before_transport", "requester_pays_required", "if_match_etag_required",
        "exact_content_length_required", "exact_response_etag_required", "exact_compressed_sha256_required",
        "exact_decompressed_byte_count_required", "require_request_charged_requester_on_success",
        "lz4_frame_stream_only", "reuse_canonical_r4_lz4_decoder", "strict_utf8_decode",
        "strict_json_duplicate_keys_rejected", "strict_json_nonfinite_constants_rejected",
        "session_policy_strict_subset_of_persistent_role", "execution_release_required",
    ):
        assert impl[key] is True, key
    for key in (
        "head_object_authorized", "range_get_authorized", "list_objects_v2_authorized",
        "list_object_versions_authorized", "list_all_my_buckets_authorized", "http_redirect_following_authorized",
        "alternate_decompressor_fallback_authorized", "raw_compressed_object_retention_authorized",
        "raw_decompressed_payload_retention_authorized", "record_payload_retention_authorized",
        "wallet_address_retention_from_body_authorized", "payload_values_in_evidence_authorized",
        "string_values_in_evidence_authorized", "numeric_values_in_evidence_authorized",
        "string_element_semantic_wallet_or_user_label_authorized", "schema_equivalence_inference_authorized",
        "semantic_equivalence_inference_authorized", "wallet_reconstruction_authorized",
        "entity_clustering_authorized", "copyability_analysis_authorized", "pnl_or_alpha_analysis_authorized",
        "market_data_ingestion_authorized", "aws_role_mutation_required", "aws_role_mutation_authorized",
        "execution_release_present", "execution_authorized", "paid_request_authorized",
        "requester_pays_authorized", "get_object_authorized", "object_body_download_authorized",
        "decompression_authorized", "format_classification_authorized",
    ):
        assert impl[key] is False, key
    assert impl["expected_canonical_implementation_commit"] == "PENDING_CANONICAL_IMPLEMENTATION_MERGE"
    assert impl["s3_requests_executed"] == 0
    assert impl["compressed_bytes_downloaded"] == 0
    assert impl["decompressed_bytes_processed"] == 0
    assert impl["empirical_result"] is None
    assert all(value is False for value in impl["trading_authorizations"].values())

    assert impl["reused_dedicated_role_arn"] == ROLE_ARN
    assert impl["session_s3_policy"] == "ALLOW_GETOBJECT_EXACT_LEGACY_OBJECT_ONLY"
    assert impl["canonical_r4_lz4_decoder_path"] == "research/archive_inventory/r4/lz4_frame.py"
    assert R4_LZ4.is_file()
    assert reuse["status"] == "STATIC_REVALIDATION_ONLY_NO_AWS_MUTATION_NO_NETWORK"
    assert reuse["reused_role_arn"] == ROLE_ARN
    assert reuse["canonical_trust_policy_sha256"] == TRUST_HASH
    assert reuse["canonical_permission_policy_sha256"] == PERMISSION_HASH
    assert hashlib.sha256(R4_TRUST.read_bytes()).hexdigest() == TRUST_HASH
    assert hashlib.sha256(R4_PERMISSION.read_bytes()).hexdigest() == PERMISSION_HASH
    assert reuse["r5_session_scope"]["allowed_object_arns"] == [OBJECT_ARN]
    assert reuse["r5_session_scope"]["strict_subset_of_persistent_role"] is True
    assert reuse["aws_iam_mutation_performed"] is False
    assert reuse["new_sts_preflight_required"] is False
    persistent_allowed = reuse["persistent_role_permission_scope"]["allowed_object_arns"]
    assert OBJECT_ARN in persistent_allowed and len(persistent_allowed) == 2

    # Persistent role trust remains exactly workflow-name-bound; R5 reuses that claim without mutation.
    trust_statement = trust["Statement"][0]
    assert trust_statement["Condition"]["StringEquals"]["token.actions.githubusercontent.com:workflow"] == "Hyperliquid Archive Hourly Body Schema Pilot R4"
    by_sid = {row["Sid"]: row for row in permission["Statement"]}
    assert by_sid["AllowExactTwoBoundaryObjectsOnly"]["Resource"] == persistent_allowed

    banned = {"boto3", "botocore", "requests", "urllib3", "subprocess"}
    assert not imported_roots(collector).intersection(banned)
    assert "http.client.HTTPSConnection" in collector
    assert '"If-Match"' in collector
    assert "x-amz-request-payer" in collector
    assert "attempts += 1" in collector
    assert collector.index("attempts += 1") < collector.index("transport(host, path, headers")
    assert "Range" not in collector
    assert "payload_values_retained" in collector
    assert "string_values_retained" in collector
    assert "numeric_values_retained" in collector
    assert "wallet_addresses_retained_from_body" in collector
    assert "structural_signature_hash_counts" in collector
    assert "LEGACY_FORMAT_RESOLVED_AS_NDJSON_PAIR_STRING_OBJECT" in collector

    assert workflow.startswith("name: Hyperliquid Archive Hourly Body Schema Pilot R4\nrun-name: R5 legacy format fingerprint\n")
    assert "workflow_dispatch:" in workflow
    assert "pull_request:" not in workflow
    assert "push:" not in workflow
    assert "id-token: write" in workflow
    assert "persist-credentials: false" in workflow
    assert f"R5_ROLE_ARN: {ROLE_ARN}" in workflow
    assert "EXPECTED_IMPLEMENTATION_COMMIT: PENDING_CANONICAL_IMPLEMENTATION_MERGE" in workflow
    assert "R5_EXECUTION_RELEASE_CANONICALIZATION.json" in workflow
    assert "hyperliquid-archive-legacy-format-fingerprint-r5.yml/runs" in workflow
    assert workflow.index("Prove canonical R5 implementation and release before AWS OIDC") < workflow.index("Assume unchanged dedicated AWS role with exact-one-object R5 session permissions")
    assert workflow.index("Enforce R5 single-use release before AWS OIDC") < workflow.index("Assume unchanged dedicated AWS role with exact-one-object R5 session permissions")
    assert workflow.count(OBJECT_ARN) >= 1
    assert "node_fills_by_block/hourly/20250727/8.lz4" not in workflow
    assert '"Action":"s3:GetObject"' in workflow
    for forbidden in ("s3:ListBucket", "s3:GetObjectVersion", "s3:GetObjectAttributes", "s3:ListAllMyBuckets"):
        assert forbidden not in workflow
    assert "r5-format-context.json" in workflow
    assert "r5-format-result.json" in workflow
    assert "r5-format.rc" in workflow
    assert "R5_FORMAT_FILES.sha256" in workflow

    # Implementation PR must remain non-release. Later validators may become release-aware explicitly.
    assert not RELEASE.exists()
    assert not ACTIVATION.exists()

    print("R5_IMPLEMENTATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
