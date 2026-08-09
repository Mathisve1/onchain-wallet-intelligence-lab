from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R6A = ROOT / "research/archive_inventory/r6a"
PREREG = R6A / "LEGACY_USER_KEY_LEXICAL_R6A_CONTRACT.json"
APPROVAL = R6A / "approvals/APPROVE_HL_ARCHIVE_LEGACY_USER_KEY_LEXICAL_R6A_001.json"
APPROVAL_TEXT = R6A / "approvals/APPROVE_HL_ARCHIVE_LEGACY_USER_KEY_LEXICAL_R6A_001.txt"
IMPLEMENTATION = R6A / "R6A_IMPLEMENTATION_CONTRACT.json"
ROLE_REUSE = R6A / "R6A_AWS_ROLE_REUSE_ANALYSIS.json"
COLLECTOR = R6A / "collector.py"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-legacy-user-key-lexical-r6a.yml"
R4_LZ4 = ROOT / "research/archive_inventory/r4/lz4_frame.py"
R4_PERMISSION = ROOT / "research/archive_inventory/r4/R4_IAM_POLICY_TEMPLATE.json"
R4_TRUST = ROOT / "research/archive_inventory/r4/R4_OIDC_TRUST_POLICY_TEMPLATE.json"
RELEASE = R6A / "R6A_EXECUTION_RELEASE.json"
ACTIVATION = R6A / "R6A_EXECUTION_RELEASE_CANONICALIZATION.json"

PREREG_MERGE = "870fdf3e10a761d6c4589d43def8e436f3a129b5"
APPROVAL_MERGE = "06c0086f80cdbc3d058bdeea64b618da276e95ec"
APPROVAL_SHA = "b24c67f527a320e533408fd821d10b5e2ea01d020c837e87ae5e5bbd386c94ed"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"
OBJECT_KEY = "node_fills/hourly/20250727/8.lz4"
OBJECT_ARN = f"arn:aws:s3:::hl-mainnet-node-data/{OBJECT_KEY}"
TRUST_HASH = "2ebb60a7747a636a475a23016951265fe377fd9d68f2d9f3a63e33f3bc0189b4"
PERMISSION_HASH = "14d055105b80e0c41462d4934bbaa8d860b0aeda9f2f1b9529267fd0d4d3613d"
RETAINED_AGGREGATES = [
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
    assert impl["pilot_id"] == prereg["pilot_id"] == "HL-ARCHIVE-LEGACY-USER-KEY-LEXICAL-R6A-001"
    assert impl["status"] == "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION"
    assert impl["preregistration_commit"] == PREREG_MERGE
    assert impl["approval_merge_commit"] == APPROVAL_MERGE
    assert impl["approval_text_sha256"] == APPROVAL_SHA
    assert impl["parent_r6_commit"] == "17a907923f63476c983b8c2dc131d34c491af913"
    assert impl["parent_r5_evidence_commit"] == "4400963aa972ed878650116202cc72880e667849"

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
        "expected_nonempty_record_count": 162815,
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
        "payload_values_in_evidence_authorized", "string_values_in_evidence_authorized",
        "numeric_values_in_evidence_authorized", "leading_string_retention_authorized",
        "wallet_address_retention_authorized", "leading_string_hash_retention_authorized",
        "distinct_address_set_retention_authorized", "wallet_reconstruction_authorized",
        "entity_clustering_authorized", "copyability_analysis_authorized", "pnl_or_alpha_analysis_authorized",
        "market_data_ingestion_authorized", "aws_role_mutation_required", "aws_role_mutation_authorized",
        "execution_release_present", "execution_authorized", "paid_request_authorized",
        "requester_pays_authorized", "get_object_authorized", "object_body_download_authorized",
        "decompression_authorized", "lexical_classification_authorized",
    ):
        assert impl[key] is False, key
    assert impl["required_top_level_record_type"] == "array"
    assert impl["required_array_arity"] == 2
    assert impl["required_ordered_element_types"] == ["string", "object"]
    assert impl["retained_aggregates_only"] == RETAINED_AGGREGATES
    assert impl["allowed_research_conclusions"] == prereg["allowed_research_conclusions"]
    assert impl["expected_canonical_implementation_commit"] == "PENDING_CANONICAL_IMPLEMENTATION_MERGE"
    assert impl["s3_requests_executed"] == 0
    assert impl["compressed_bytes_downloaded"] == 0
    assert impl["decompressed_bytes_processed"] == 0
    assert impl["empirical_result"] is None
    assert all(value is False for value in impl["trading_authorizations"].values())

    assert impl["reused_dedicated_role_arn"] == ROLE_ARN
    assert impl["session_s3_policy"] == "ALLOW_GETOBJECT_EXACT_R5_BOUND_LEGACY_OBJECT_ONLY"
    assert impl["canonical_r4_lz4_decoder_path"] == "research/archive_inventory/r4/lz4_frame.py"
    assert R4_LZ4.is_file()
    assert reuse["status"] == "STATIC_REVALIDATION_ONLY_NO_AWS_MUTATION_NO_NETWORK"
    assert reuse["reused_role_arn"] == ROLE_ARN
    assert reuse["canonical_trust_policy_sha256"] == TRUST_HASH
    assert reuse["canonical_permission_policy_sha256"] == PERMISSION_HASH
    assert hashlib.sha256(R4_TRUST.read_bytes()).hexdigest() == TRUST_HASH
    assert hashlib.sha256(R4_PERMISSION.read_bytes()).hexdigest() == PERMISSION_HASH
    assert reuse["r6a_session_scope"]["allowed_object_arns"] == [OBJECT_ARN]
    assert reuse["r6a_session_scope"]["strict_subset_of_persistent_role"] is True
    assert reuse["r6a_session_scope"]["same_exact_object_as_successful_r5_session"] is True
    assert reuse["aws_iam_mutation_performed"] is False
    assert reuse["new_sts_preflight_required"] is False
    persistent_allowed = reuse["persistent_role_permission_scope"]["allowed_object_arns"]
    assert OBJECT_ARN in persistent_allowed and len(persistent_allowed) == 2
    assert reuse["independent_prior_network_proofs"]["r5_run"] == 31321019885
    assert reuse["independent_prior_network_proofs"]["r5_same_exact_legacy_get_succeeded"] is True

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
    for aggregate in RETAINED_AGGREGATES:
        assert aggregate in collector
    for flag in (
        "leading_string_values_retained", "wallet_addresses_retained", "leading_string_hashes_retained",
        "distinct_address_set_retained", "payload_values_retained", "record_payload_retained",
        "wallet_reconstruction_performed", "entity_clustering_performed", "copyability_analysis_performed",
        "pnl_or_alpha_analysis_performed", "market_data_ingested",
    ):
        assert flag in collector
    assert "ADDRESS_RE" in collector and "LOWERCASE_ADDRESS_RE" in collector
    assert "ALL_LEADING_STRINGS_MATCH_HYPERLIQUID_ADDRESS_SHAPE" in collector
    assert "SOME_LEADING_STRINGS_DO_NOT_MATCH_HYPERLIQUID_ADDRESS_SHAPE" in collector

    assert workflow.startswith("name: Hyperliquid Archive Hourly Body Schema Pilot R4\nrun-name: R6A legacy user-key lexical confirmation\n")
    assert "workflow_dispatch:" in workflow
    assert "pull_request:" not in workflow
    assert "push:" not in workflow
    assert "id-token: write" in workflow
    assert "persist-credentials: false" in workflow
    assert f"R6A_ROLE_ARN: {ROLE_ARN}" in workflow
    if ACTIVATION.exists():
        activation = load(ACTIVATION)
        expected = activation["implementation_commit"]
        assert f"EXPECTED_IMPLEMENTATION_COMMIT: {expected}" in workflow
        assert "EXPECTED_IMPLEMENTATION_COMMIT: PENDING_CANONICAL_IMPLEMENTATION_MERGE" not in workflow
    else:
        assert "EXPECTED_IMPLEMENTATION_COMMIT: PENDING_CANONICAL_IMPLEMENTATION_MERGE" in workflow
    assert "R6A_EXECUTION_RELEASE_CANONICALIZATION.json" in workflow
    assert "hyperliquid-archive-legacy-user-key-lexical-r6a.yml/runs" in workflow
    assert workflow.index("Prove canonical R6A implementation and release before AWS OIDC") < workflow.index("Assume unchanged dedicated AWS role with exact-one-object R6A session permissions")
    assert workflow.index("Enforce R6A single-use release before AWS OIDC") < workflow.index("Assume unchanged dedicated AWS role with exact-one-object R6A session permissions")
    assert workflow.count(OBJECT_ARN) >= 1
    assert "node_fills_by_block/hourly/20250727/8.lz4" not in workflow
    assert '"Action":"s3:GetObject"' in workflow
    for forbidden in ("s3:ListBucket", "s3:GetObjectVersion", "s3:GetObjectAttributes", "s3:ListAllMyBuckets"):
        assert forbidden not in workflow
    for filename in ("r6a-lexical-context.json", "r6a-lexical-result.json", "r6a-lexical.rc", "R6A_LEXICAL_FILES.sha256"):
        assert filename in workflow

    if RELEASE.exists():
        release = load(RELEASE)
        assert release["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
        assert release["execution_ready"] is False
        assert release["single_workflow_dispatch_authorized"] is False
        assert release["s3_requests_executed"] == 0
        assert release["empirical_result"] is None
    if ACTIVATION.exists():
        activation = load(ACTIVATION)
        assert activation["single_workflow_dispatch_authorized"] is True
        assert activation["rerun_authorized"] is False
        assert activation["s3_requests_executed"] == 0
        assert activation["empirical_result"] is None

    print("R6A_IMPLEMENTATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
