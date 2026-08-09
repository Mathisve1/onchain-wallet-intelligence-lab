from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r4"
PREREG = BASE / "HOURLY_BODY_SCHEMA_PILOT_R4_CONTRACT.json"
APPROVAL = BASE / "approvals/APPROVE_HL_ARCHIVE_HOURLY_BODY_SCHEMA_PILOT_R4_001.json"
IMPLEMENTATION = BASE / "R4_IMPLEMENTATION_CONTRACT.json"
PRICING = BASE / "R4_PRICING_EVIDENCE.json"
RELEASE = BASE / "R4_EXECUTION_RELEASE.json"
ACTIVATION = BASE / "R4_EXECUTION_RELEASE_CANONICALIZATION.json"

PREREG_COMMIT = "25a1f621d15cb708a485893025f03b991628aae1"
APPROVAL_MERGE = "0191350683c6c943d3538c8c51db176cd1d58211"
APPROVAL_SHA = "e52399feb7a0d36959089f556dd9f55062eb91d52feaa4c5af680d3c4e557264"
IMPLEMENTATION_COMMIT = "180c89ead78f9a6f4560a1ec12575658e62586ee"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"
OBJECT_KEYS = [
    "node_fills/hourly/20250727/8.lz4",
    "node_fills_by_block/hourly/20250727/8.lz4",
]


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    prereg = load(PREREG)
    approval = load(APPROVAL)
    impl = load(IMPLEMENTATION)
    pricing = load(PRICING)
    release = load(RELEASE)

    assert prereg["pilot_id"] == "HL-ARCHIVE-HOURLY-BODY-SCHEMA-PILOT-R4-001"
    assert approval["reviewed_commit"] == PREREG_COMMIT
    assert approval["exact_approval_text_sha256"] == APPROVAL_SHA
    assert impl["approval_merge_commit"] == APPROVAL_MERGE
    assert impl["approval_text_sha256"] == APPROVAL_SHA

    assert release["release_id"] == "RELEASE_HL_ARCHIVE_HOURLY_BODY_SCHEMA_PILOT_R4_001"
    assert release["pilot_id"] == prereg["pilot_id"]
    assert release["status"] == "RELEASE_CANDIDATE_AWAITING_DEDICATED_R4_ROLE_ATTESTATION"
    assert release["preregistration_commit"] == PREREG_COMMIT
    assert release["approval_merge_commit"] == APPROVAL_MERGE
    assert release["approval_text_sha256"] == APPROVAL_SHA
    assert release["implementation_commit"] == IMPLEMENTATION_COMMIT
    assert release["pricing_evidence_path"] == "research/archive_inventory/r4/R4_PRICING_EVIDENCE.json"
    assert release["pricing_status"] == pricing["pricing_status"]
    assert pricing["pricing_status"] == "FRESH_AWS_PRICING_REVIEWED_ACCOUNT_SPECIFIC_FINAL_CHARGE_NOT_ASSERTED"
    assert pricing["checked_at_utc"].startswith("2026-08-09T")
    assert pricing["r3_storage_class_evidence"]["object_1_storage_class"] == "STANDARD"
    assert pricing["r3_storage_class_evidence"]["object_2_storage_class"] == "STANDARD"
    assert pricing["r3_storage_class_evidence"]["storage_class_retrieval_surcharge_inferred"] is False
    assert pricing["release_budget_decision"] == "RETAIN_USER_APPROVED_EUR_0_10_ONE_TIME_CEILING_WITH_EXACT_REQUEST_AND_BYTE_CAPS"
    assert pricing["execution_authorized_by_this_file"] is False
    assert pricing["requests_executed"] == 0
    assert pricing["empirical_result"] is None

    assert release["maximum_one_time_budget_eur"] == 0.10
    assert release["maximum_monthly_budget_eur"] == 0
    assert release["target_bucket"] == "hl-mainnet-node-data"
    assert release["signing_region"] == "ap-northeast-1"
    assert release["object_keys"] == OBJECT_KEYS
    assert release["object_sizes_bytes"] == [12726384, 1517603]
    assert release["object_etags"] == [
        '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"',
        '"60d4c1277f76651b5f04666bbe8d7594"',
    ]
    assert release["maximum_get_object_requests"] == 2
    assert release["maximum_requests_per_object"] == 1
    assert release["maximum_total_compressed_bytes"] == 14243987
    assert release["maximum_total_decompressed_bytes"] == 536870912
    assert release["maximum_decompressed_bytes_per_object"] == 268435456
    assert release["maximum_runtime_seconds"] == 180
    assert release["maximum_retries_per_request"] == 0
    assert release["maximum_record_bytes"] == 16777216
    assert release["maximum_records_parsed_per_object"] == 5000000
    assert release["maximum_schema_nesting_depth"] == 16
    assert release["maximum_unique_field_paths"] == 4096
    assert release["if_match_etag_required"] is True
    assert release["exact_content_length_required"] is True
    assert release["requester_pays_scope_approved"] is True
    assert release["get_object_scope_approved"] is True
    assert release["decompression_scope_approved"] is True
    assert release["lz4_frame_stream_only"] is True
    assert release["schema_parser_utf8_ndjson_object_stream_only"] is True

    assert release["dedicated_r4_role_name"] == "onchain-wallet-intelligence-hl-archive-body-schema-r4"
    assert release["dedicated_r4_role_arn"] == ROLE_ARN
    assert release["dedicated_r4_trust_policy_template"] == "research/archive_inventory/r4/R4_OIDC_TRUST_POLICY_TEMPLATE.json"
    assert release["dedicated_r4_permission_policy_template"] == "research/archive_inventory/r4/R4_IAM_POLICY_TEMPLATE.json"
    assert release["dedicated_r4_role_operator_attested"] is False
    assert release["dedicated_r4_role_independently_verified"] is False
    assert release["github_event_required"] == "workflow_dispatch"
    assert release["canonical_dispatch_ref_required"] == "refs/heads/main"
    assert release["canonical_dispatch_sha_source"] == "github.sha"
    assert release["single_use_window_start_utc"] is None
    assert release["single_workflow_dispatch_authorized"] is False
    assert release["rerun_authorized"] is False

    for key in (
        "requester_pays_authorized", "get_object_authorized", "object_body_download_authorized",
        "decompression_authorized", "head_object_authorized", "range_get_authorized",
        "list_objects_v2_authorized", "list_object_versions_authorized", "list_all_my_buckets_authorized",
        "http_redirect_following_authorized", "alternate_decompressor_fallback_authorized",
        "raw_compressed_object_retention_authorized", "raw_decompressed_payload_retention_authorized",
        "record_payload_retention_authorized", "wallet_address_retention_from_body_authorized",
        "payload_values_in_schema_evidence_authorized", "semantic_equivalence_inference_authorized",
        "wallet_reconstruction_authorized", "entity_clustering_authorized", "copyability_analysis_authorized",
        "pnl_or_alpha_analysis_authorized", "market_data_ingestion_authorized", "execution_ready",
    ):
        assert release[key] is False, key
    assert all(value is False for value in release["trading_authorizations"].values())
    assert release["s3_requests_executed"] == 0
    assert release["compressed_bytes_downloaded"] == 0
    assert release["decompressed_bytes_processed"] == 0
    assert release["empirical_result"] is None

    assert not ACTIVATION.exists(), "release candidate must not self-create canonical activation"
    workflow = (ROOT / ".github/workflows/hyperliquid-archive-hourly-body-schema-pilot-r4.yml").read_text(encoding="utf-8")
    assert "EXPECTED_IMPLEMENTATION_COMMIT: PENDING_CANONICAL_IMPLEMENTATION_MERGE" in workflow
    assert "R4 release gate 45" in workflow

    print("R4_RELEASE_CANDIDATE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
