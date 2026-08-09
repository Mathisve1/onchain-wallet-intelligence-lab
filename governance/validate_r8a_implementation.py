from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R8 = ROOT / "research/archive_inventory/r8"
PREREG = R8 / "MODERN_WALLET_INDEX_BRIDGE_R8A_CONTRACT.json"
APPROVAL = R8 / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_INDEX_BRIDGE_R8A_001.json"
APPROVAL_TEXT = R8 / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_INDEX_BRIDGE_R8A_001.txt"
IMPLEMENTATION = R8 / "R8A_IMPLEMENTATION_CONTRACT.json"
ROLE_REUSE = R8 / "R8A_AWS_ROLE_REUSE_ANALYSIS.json"
COLLECTOR = R8 / "collector.py"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-modern-wallet-index-r8a.yml"
R4_LZ4 = ROOT / "research/archive_inventory/r4/lz4_frame.py"
R4_PERMISSION = ROOT / "research/archive_inventory/r4/R4_IAM_POLICY_TEMPLATE.json"
R4_TRUST = ROOT / "research/archive_inventory/r4/R4_OIDC_TRUST_POLICY_TEMPLATE.json"
RELEASE = R8 / "R8A_EXECUTION_RELEASE.json"
ACTIVATION = R8 / "R8A_EXECUTION_RELEASE_CANONICALIZATION.json"

R8_MERGE = "526f92cf3666c8bb616ecb61b6f9881387c1d7ed"
APPROVAL_MERGE = "6c011cb604dec1f169d42b02de4ae67f3f8f8395"
APPROVAL_SHA = "cb39246e2e5f345b14f87c15ac2c4d6aa993bcc9fbd28076f5f57eff94420e64"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"
OBJECT_KEY = "node_fills_by_block/hourly/20250727/8.lz4"
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
    assert approval["reviewed_commit"] == R8_MERGE
    assert approval["exact_approval_text_sha256"] == APPROVAL_SHA
    assert impl["pilot_id"] == prereg["pilot_id"] == "HL-ARCHIVE-MODERN-WALLET-INDEX-BRIDGE-R8A-001"
    assert impl["status"] == "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION"
    assert impl["r8_static_design_commit"] == R8_MERGE
    assert impl["approval_merge_commit"] == APPROVAL_MERGE
    assert impl["approval_id"] == approval["approval_id"]
    assert impl["approval_text_sha256"] == APPROVAL_SHA
    assert impl["parent_r4_evidence_commit"] == "fe06874aeeb958d375a27100378f89bd25b4741b"
    assert impl["parent_r4_run_id"] == 31313913525

    target = prereg["exact_future_network_target"]
    obj = impl["object"]
    assert obj["key"] == target["key"] == OBJECT_KEY
    assert obj["expected_size_bytes"] == target["expected_size_bytes"] == 1517603
    assert obj["expected_etag"] == target["expected_etag"] == '"60d4c1277f76651b5f04666bbe8d7594"'
    assert obj["expected_compressed_sha256"] == target["expected_compressed_sha256"] == "928e1cd6bd7d69ad7243c263bacee48e53e4762ae9e99ef75f45007f6c0e6105"
    assert obj["expected_decompressed_byte_count"] == target["expected_decompressed_byte_count"] == 7380378
    assert obj["expected_top_level_block_record_count"] == target["expected_top_level_block_record_count"] == 4345
    assert obj["required_leading_string_regex"] == "^0x[0-9a-f]{40}$"
    assert impl["target_bucket"] == "hl-mainnet-node-data"
    assert impl["signing_region"] == "ap-northeast-1"

    for key, expected in {
        "maximum_one_time_budget_eur": 0.10,
        "maximum_monthly_budget_eur": 0,
        "maximum_get_object_requests": 1,
        "maximum_requests_per_object": 1,
        "maximum_total_compressed_bytes": 1517603,
        "maximum_total_decompressed_bytes": 16777216,
        "maximum_runtime_seconds": 120,
        "maximum_retries_per_request": 0,
        "maximum_record_bytes": 16777216,
        "maximum_block_records_parsed": 1000000,
        "maximum_event_pairs_parsed": 5000000,
        "wallet_index_entry_cap": 1000000,
        "wallet_index_output_byte_cap": 16777216,
    }.items():
        assert impl[key] == expected, key

    for key in (
        "request_counter_incremented_before_transport", "requester_pays_required", "if_match_etag_required",
        "exact_content_length_required", "exact_response_etag_required", "exact_compressed_sha256_required",
        "exact_decompressed_byte_count_required", "require_request_charged_requester_on_success",
        "lz4_frame_stream_only", "reuse_canonical_r4_lz4_decoder", "strict_utf8_decode",
        "strict_json_duplicate_keys_rejected", "strict_json_nonfinite_constants_rejected",
        "session_policy_strict_subset_of_persistent_role", "execution_release_required",
        "one_row_per_unique_wallet", "wallet_address_unique", "fill_count_positive_integer",
        "valid_event_pair_conservation_required",
    ):
        assert impl[key] is True, key
    for key in (
        "head_object_authorized", "range_get_authorized", "list_objects_v2_authorized",
        "list_object_versions_authorized", "list_all_my_buckets_authorized", "http_redirect_following_authorized",
        "alternate_decompressor_fallback_authorized", "aws_role_mutation_required", "aws_role_mutation_authorized",
        "execution_release_present",
    ):
        assert impl[key] is False, key

    assert impl["required_top_level_record_type"] == "object"
    assert impl["required_block_fields"] == {"local_time":"string","block_time":"string","block_number":"integer","events":"array"}
    assert impl["required_event_pair_type"] == "array"
    assert impl["required_event_pair_arity"] == 2
    assert impl["required_event_pair_ordered_element_types"] == ["string", "object"]
    assert impl["wallet_address_normalization"] == "LOWERCASE_EXACT_0X40HEX"
    assert impl["wallet_index_fields_only"] == ["wallet_address", "fill_count"]
    assert impl["wallet_index_sort_order"] == "LEXICOGRAPHIC_ASCENDING"
    assert impl["minimum_valid_event_pair_count"] == 1
    assert all(value is True for value in impl["future_release_retention_authorizations"].values())
    assert all(value is False for value in impl["forbidden_retention_authorizations"].values())
    assert all(value is False for value in impl["current_runtime_authority"].values())
    assert all(value is False for value in impl["downstream_authorizations"].values())
    assert all(value is False for value in impl["trading_authorizations"].values())
    assert impl["expected_canonical_implementation_commit"] == "PENDING_CANONICAL_IMPLEMENTATION_MERGE"
    assert impl["s3_requests_executed"] == 0
    assert impl["compressed_bytes_downloaded"] == 0
    assert impl["decompressed_bytes_processed"] == 0
    assert impl["wallet_addresses_retained"] == 0
    assert impl["empirical_result"] is None

    assert impl["reused_dedicated_role_arn"] == ROLE_ARN
    assert impl["session_s3_policy"] == "ALLOW_GETOBJECT_EXACT_R8A_MODERN_BOUNDARY_OBJECT_ONLY"
    assert impl["canonical_r4_lz4_decoder_path"] == "research/archive_inventory/r4/lz4_frame.py"
    assert R4_LZ4.is_file()
    assert reuse["status"] == "STATIC_REVALIDATION_ONLY_NO_AWS_MUTATION_NO_NETWORK"
    assert reuse["reused_role_arn"] == ROLE_ARN
    assert reuse["canonical_trust_policy_sha256"] == TRUST_HASH
    assert reuse["canonical_permission_policy_sha256"] == PERMISSION_HASH
    assert hashlib.sha256(R4_TRUST.read_bytes()).hexdigest() == TRUST_HASH
    assert hashlib.sha256(R4_PERMISSION.read_bytes()).hexdigest() == PERMISSION_HASH
    assert reuse["r8a_session_scope"]["allowed_object_arns"] == [OBJECT_ARN]
    assert reuse["r8a_session_scope"]["strict_subset_of_persistent_role"] is True
    assert reuse["aws_iam_mutation_performed"] is False
    assert reuse["new_sts_preflight_required"] is False

    trust_statement = trust["Statement"][0]
    assert trust_statement["Condition"]["StringEquals"]["token.actions.githubusercontent.com:workflow"] == "Hyperliquid Archive Hourly Body Schema Pilot R4"
    by_sid = {row["Sid"]: row for row in permission["Statement"]}
    assert OBJECT_ARN in by_sid["AllowExactTwoBoundaryObjectsOnly"]["Resource"]

    banned = {"boto3", "botocore", "requests", "urllib3", "subprocess"}
    assert not imported_roots(collector).intersection(banned)
    assert "http.client.HTTPSConnection" in collector
    assert '"If-Match"' in collector
    assert "x-amz-request-payer" in collector
    assert "attempts += 1" in collector
    assert collector.index("attempts += 1") < collector.index("transport(host, path, headers")
    assert '"wallet_address": address' in collector
    assert '"fill_count": self.counts[address]' in collector
    assert "sorted(self.counts)" in collector
    assert "Range" not in collector
    for forbidden_token in ('"coin":', '"px":', '"sz":', '"side":', '"closedPnl":'):
        assert forbidden_token not in collector

    assert workflow.startswith("name: Hyperliquid Archive Hourly Body Schema Pilot R4\nrun-name: R8A modern wallet-index bridge\n")
    assert "workflow_dispatch:" in workflow
    assert "pull_request:" not in workflow
    assert "push:" not in workflow
    assert "id-token: write" in workflow
    assert "persist-credentials: false" in workflow
    assert f"R8A_ROLE_ARN: {ROLE_ARN}" in workflow
    assert "R8A_EXECUTION_RELEASE.json" in workflow
    assert "R8A_EXECUTION_RELEASE_CANONICALIZATION.json" in workflow
    assert workflow.index("Prove canonical R8A implementation and active release before AWS OIDC") < workflow.index("Assume unchanged dedicated AWS role with exact-one-object R8A session")
    assert workflow.index("Enforce R8A single-use release before AWS OIDC") < workflow.index("Assume unchanged dedicated AWS role with exact-one-object R8A session")
    assert '"Action":"s3:GetObject"' in workflow
    assert OBJECT_ARN in workflow
    for forbidden in ("s3:ListBucket", "s3:GetObjectVersion", "s3:GetObjectAttributes", "s3:ListAllMyBuckets"):
        assert forbidden not in workflow
    for filename in ("r8a-context.json", "r8a-result.json", "r8a-wallet-index.ndjson", "r8a.rc", "R8A_FILES.sha256"):
        assert filename in workflow

    assert not RELEASE.exists()
    assert not ACTIVATION.exists()
    print("R8A_IMPLEMENTATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
