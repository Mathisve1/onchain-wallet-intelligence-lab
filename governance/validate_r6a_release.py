from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r6a"
PREREG = BASE / "LEGACY_USER_KEY_LEXICAL_R6A_CONTRACT.json"
APPROVAL = BASE / "approvals/APPROVE_HL_ARCHIVE_LEGACY_USER_KEY_LEXICAL_R6A_001.json"
APPROVAL_TEXT = BASE / "approvals/APPROVE_HL_ARCHIVE_LEGACY_USER_KEY_LEXICAL_R6A_001.txt"
IMPLEMENTATION = BASE / "R6A_IMPLEMENTATION_CONTRACT.json"
ROLE_REUSE = BASE / "R6A_AWS_ROLE_REUSE_ANALYSIS.json"
COLLECTOR = BASE / "collector.py"
RELEASE = BASE / "R6A_EXECUTION_RELEASE.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-legacy-user-key-lexical-r6a.yml"
IMPLEMENTATION_VALIDATOR = ROOT / "governance/validate_r6a_implementation.py"

PREREG_MERGE = "870fdf3e10a761d6c4589d43def8e436f3a129b5"
APPROVAL_MERGE = "06c0086f80cdbc3d058bdeea64b618da276e95ec"
APPROVAL_SHA = "b24c67f527a320e533408fd821d10b5e2ea01d020c837e87ae5e5bbd386c94ed"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"
IMPLEMENTATION_HASHES = {
    "implementation_contract_sha256": "76fe0a35a4b1d89a6025a8d9889b38e5111db0f3ee44be8149d01812c6409f75",
    "role_reuse_analysis_sha256": "1c1534423692f49465c2b8db5398a4d51d0a041b6af68e55027c2effc2048af9",
    "collector_sha256": "ef125c18ed73a6b592e02a1a37e36c76f8001d5408cf627342c94e87ee561746",
    "implementation_validator_sha256": "1847096f7a264b208e047538e96622937758256057429c0d3e7765c7729c190a",
    "workflow_candidate_sha256": "92307b7840163b01c51b0b6f2c8cac33f982cb8c9bf22ab219eb46ae7260dd5c",
}
RETAINED = [
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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    prereg = load(PREREG)
    approval = load(APPROVAL)
    impl = load(IMPLEMENTATION)
    reuse = load(ROLE_REUSE)
    release = load(RELEASE)

    assert sha256(APPROVAL_TEXT) == APPROVAL_SHA
    assert prereg["pilot_id"] == release["pilot_id"] == "HL-ARCHIVE-LEGACY-USER-KEY-LEXICAL-R6A-001"
    assert release["release_id"] == "RELEASE_HL_ARCHIVE_LEGACY_USER_KEY_LEXICAL_R6A_001"
    assert release["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
    assert release["preregistration_commit"] == PREREG_MERGE
    assert release["approval_merge_commit"] == APPROVAL_MERGE
    assert release["approval_id"] == approval["approval_id"] == "APPROVE_HL_ARCHIVE_LEGACY_USER_KEY_LEXICAL_R6A_001"
    assert release["approval_text_sha256"] == APPROVAL_SHA
    assert approval["reviewed_commit"] == PREREG_MERGE
    assert approval["exact_approval_text_sha256"] == APPROVAL_SHA

    binding = release["implementation_binding"]
    assert binding["canonical_pull_request_number"] == 66
    assert binding["binding_method"] == "CANONICAL_PR_PLUS_BYTE_EXACT_IMPLEMENTATION_FILE_HASHES"
    assert {key: binding[key] for key in IMPLEMENTATION_HASHES} == IMPLEMENTATION_HASHES
    assert sha256(IMPLEMENTATION) == binding["implementation_contract_sha256"]
    assert sha256(ROLE_REUSE) == binding["role_reuse_analysis_sha256"]
    assert sha256(COLLECTOR) == binding["collector_sha256"]
    assert sha256(IMPLEMENTATION_VALIDATOR) == binding["implementation_validator_sha256"]
    assert sha256(WORKFLOW) == binding["workflow_candidate_sha256"]
    assert impl["status"] == "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION"
    assert impl["approval_merge_commit"] == APPROVAL_MERGE
    assert impl["execution_release_present"] is False
    assert impl["execution_authorized"] is False
    assert impl["s3_requests_executed"] == 0
    assert impl["empirical_result"] is None

    scope = release["approved_scope"]
    for key, expected in {
        "maximum_one_time_budget_eur": 0.10,
        "maximum_monthly_budget_eur": 0,
        "maximum_get_object_requests": 1,
        "maximum_requests_per_object": 1,
        "maximum_total_compressed_bytes": 12726384,
        "maximum_total_decompressed_bytes": 134217728,
        "maximum_runtime_seconds": 120,
        "maximum_retries_per_request": 0,
        "target_bucket": "hl-mainnet-node-data",
        "signing_region": "ap-northeast-1",
        "regional_virtual_hosted_endpoint": "hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com",
        "object_key": "node_fills/hourly/20250727/8.lz4",
        "object_size_bytes": 12726384,
        "object_etag": '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"',
        "expected_compressed_sha256": "f12d33da9733dbb71f02f9910fc187b9dd4b8f9dae1102b7dfe7690094542622",
        "expected_decompressed_byte_count": 62169139,
        "expected_nonempty_record_count": 162815,
        "required_top_level_record_type": "array",
        "required_array_arity": 2,
    }.items():
        assert scope[key] == expected, key
    assert scope["required_ordered_element_types"] == ["string", "object"]
    assert scope["retained_aggregates_only"] == RETAINED

    planned = release["planned_runtime_permissions_after_separate_activation"]
    assert planned == {
        "requester_pays": True,
        "get_object": True,
        "decompression": True,
        "lexical_classification": True,
        "head_object": False,
        "range_get": False,
        "list_objects_v2": False,
        "list_object_versions": False,
        "list_all_my_buckets": False,
        "http_redirect_following": False,
    }
    assert release["dedicated_role_arn"] == ROLE_ARN
    assert reuse["reused_role_arn"] == ROLE_ARN
    assert release["aws_role_mutation_required"] is False
    assert release["aws_role_mutation_authorized"] is False
    assert release["aws_role_mutation_performed"] is False
    assert release["session_s3_policy"] == "ALLOW_GETOBJECT_EXACT_R5_BOUND_LEGACY_OBJECT_ONLY"
    assert release["session_policy_strict_subset_of_persistent_role"] is True

    for key in (
        "single_workflow_dispatch_authorized",
        "execution_ready",
        "requester_pays_authorized",
        "get_object_authorized",
        "object_body_download_authorized",
        "decompression_authorized",
        "lexical_classification_authorized",
        "rerun_authorized",
        "raw_compressed_object_retention_authorized",
        "raw_decompressed_payload_retention_authorized",
        "record_payload_retention_authorized",
        "payload_values_in_evidence_authorized",
        "string_values_in_evidence_authorized",
        "numeric_values_in_evidence_authorized",
        "leading_string_retention_authorized",
        "wallet_address_retention_authorized",
        "leading_string_hash_retention_authorized",
        "distinct_address_set_retention_authorized",
        "wallet_reconstruction_authorized",
        "entity_clustering_authorized",
        "copyability_analysis_authorized",
        "pnl_or_alpha_analysis_authorized",
        "market_data_ingestion_authorized",
    ):
        assert release[key] is False, key
    assert all(value is False for value in release["trading_authorizations"].values())
    assert release["s3_requests_executed"] == 0
    assert release["compressed_bytes_downloaded"] == 0
    assert release["decompressed_bytes_processed"] == 0
    assert release["empirical_result"] is None

    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "EXPECTED_IMPLEMENTATION_COMMIT: PENDING_CANONICAL_IMPLEMENTATION_MERGE" in workflow
    assert "R6A_EXECUTION_RELEASE_CANONICALIZATION.json" in workflow
    assert workflow.index("Prove canonical R6A implementation and release before AWS OIDC") < workflow.index(
        "Assume unchanged dedicated AWS role with exact-one-object R6A session permissions"
    )

    print("R6A_RELEASE_CANDIDATE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
