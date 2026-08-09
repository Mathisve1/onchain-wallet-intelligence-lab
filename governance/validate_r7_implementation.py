from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R7 = ROOT / "research/archive_inventory/r7"
PREREG = R7 / "WALLET_INDEX_RECONSTRUCTION_R7_CONTRACT.json"
APPROVAL = R7 / "approvals/APPROVE_HL_ARCHIVE_WALLET_INDEX_RECONSTRUCTION_R7_001.json"
APPROVAL_TEXT = R7 / "approvals/APPROVE_HL_ARCHIVE_WALLET_INDEX_RECONSTRUCTION_R7_001.txt"
IMPLEMENTATION = R7 / "R7_IMPLEMENTATION_CONTRACT.json"
ROLE_REUSE = R7 / "R7_AWS_ROLE_REUSE_ANALYSIS.json"
COLLECTOR = R7 / "collector.py"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-wallet-index-r7.yml"
R4_LZ4 = ROOT / "research/archive_inventory/r4/lz4_frame.py"
R4_PERMISSION = ROOT / "research/archive_inventory/r4/R4_IAM_POLICY_TEMPLATE.json"
R4_TRUST = ROOT / "research/archive_inventory/r4/R4_OIDC_TRUST_POLICY_TEMPLATE.json"
RELEASE = R7 / "R7_EXECUTION_RELEASE.json"
ACTIVATION = R7 / "R7_EXECUTION_RELEASE_CANONICALIZATION.json"

PREREG_MERGE = "795281b2992466785ba48314d59feb61ac0b3aef"
APPROVAL_MERGE = "65a7b53796231b3aaea4c1dc1b41aa847b4ea3ba"
APPROVAL_SHA = "43f32634859eb39e4b1e464276f9721ed4ef8bcc30161f1f301f82e0312042a6"
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
    assert impl["pilot_id"] == prereg["pilot_id"] == "HL-ARCHIVE-WALLET-INDEX-RECONSTRUCTION-R7-001"
    assert impl["status"] == "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION"
    assert impl["preregistration_commit"] == PREREG_MERGE
    assert impl["approval_merge_commit"] == APPROVAL_MERGE
    assert impl["approval_text_sha256"] == APPROVAL_SHA
    assert impl["parent_r6a_evidence_commit"] == "6b7dcd85e6d0f82b63ab8c4dd50d56ef8dc72a57"
    assert impl["parent_r6a_run_id"] == 31328268134
    assert impl["working_semantic_label"] == "HYPERLIQUID_USER_ADDRESS"

    target = prereg["exact_future_network_target"]
    obj = impl["object"]
    assert obj["key"] == target["key"] == OBJECT_KEY
    assert obj["expected_size_bytes"] == target["expected_size_bytes"] == 12726384
    assert obj["expected_etag"] == target["expected_etag"] == '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"'
    assert obj["expected_compressed_sha256"] == target["expected_compressed_sha256"] == "f12d33da9733dbb71f02f9910fc187b9dd4b8f9dae1102b7dfe7690094542622"
    assert obj["expected_decompressed_byte_count"] == target["expected_decompressed_byte_count"] == 62169139
    assert obj["expected_nonempty_record_count"] == target["expected_nonempty_record_count"] == 162815
    assert obj["required_leading_string_regex"] == target["required_leading_string_pattern"] == "^0x[0-9a-f]{40}$"
    assert impl["target_bucket"] == "hl-mainnet-node-data"
    assert impl["signing_region"] == "ap-northeast-1"

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
        "wallet_index_entry_cap": 162815,
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
        "one_row_per_unique_wallet",
    ):
        assert impl[key] is True, key
    for key in (
        "head_object_authorized", "range_get_authorized", "list_objects_v2_authorized",
        "list_object_versions_authorized", "list_all_my_buckets_authorized", "http_redirect_following_authorized",
        "alternate_decompressor_fallback_authorized", "aws_role_mutation_required", "aws_role_mutation_authorized",
        "execution_release_present",
    ):
        assert impl[key] is False, key
    assert impl["required_top_level_record_type"] == "array"
    assert impl["required_array_arity"] == 2
    assert impl["required_ordered_element_types"] == ["string", "object"]
    assert impl["wallet_address_normalization"] == "LOWERCASE_EXACT_0X40HEX"
    assert impl["wallet_index_fields_only"] == ["wallet_address", "fill_count"]
    assert impl["wallet_index_sort_order"] == "LEXICOGRAPHIC_ASCENDING"
    assert impl["sum_fill_count_required"] == 162815
    assert all(value is True for value in impl["future_release_retention_authorizations"].values())
    assert all(value is False for value in impl["forbidden_retention_authorizations"].values())
    assert all(value is False for value in impl["current_runtime_authority"].values())
    assert all(value is False for value in impl["downstream_authorizations"].values())
    assert all(value is False for value in impl["trading_authorizations"].values())
    assert impl["expected_canonical_implementation_commit"] == "PENDING_CANONICAL_IMPLEMENTATION_MERGE"
    assert impl["s3_requests_executed"] == 0
    assert impl["wallet_addresses_retained"] == 0
    assert impl["empirical_result"] is None

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
    assert reuse["r7_session_scope"]["allowed_object_arns"] == [OBJECT_ARN]
    assert reuse["r7_session_scope"]["strict_subset_of_persistent_role"] is True
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
    assert "Range" not in collector
    assert "^0x[0-9a-f]{40}$" in collector
    assert '"wallet_address": address' in collector
    assert '"fill_count": self.counts[address]' in collector
    assert "sorted(self.counts)" in collector
    for forbidden_token in (
        '"coin":', '"px":', '"sz":', '"side":', '"closedPnl":',
    ):
        assert forbidden_token not in collector

    assert workflow.startswith("name: Hyperliquid Archive Hourly Body Schema Pilot R4\nrun-name: R7 bounded wallet-index reconstruction\n")
    assert "workflow_dispatch:" in workflow
    assert "pull_request:" not in workflow
    assert "push:" not in workflow
    assert "id-token: write" in workflow
    assert "persist-credentials: false" in workflow
    assert f"R7_ROLE_ARN: {ROLE_ARN}" in workflow
    assert "R7_EXECUTION_RELEASE.json" in workflow
    assert "R7_EXECUTION_RELEASE_CANONICALIZATION.json" in workflow
    assert workflow.index("Prove canonical R7 implementation and active release before AWS OIDC") < workflow.index("Assume unchanged dedicated AWS role with exact-one-object R7 session")
    assert workflow.index("Enforce R7 single-use release before AWS OIDC") < workflow.index("Assume unchanged dedicated AWS role with exact-one-object R7 session")
    assert '"Action":"s3:GetObject"' in workflow
    assert OBJECT_ARN in workflow
    for forbidden in ("s3:ListBucket", "s3:GetObjectVersion", "s3:GetObjectAttributes", "s3:ListAllMyBuckets"):
        assert forbidden not in workflow
    for filename in ("r7-context.json", "r7-result.json", "r7-wallet-index.ndjson", "r7.rc", "R7_FILES.sha256"):
        assert filename in workflow

    assert not RELEASE.exists()
    assert not ACTIVATION.exists()

    print("R7_IMPLEMENTATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
