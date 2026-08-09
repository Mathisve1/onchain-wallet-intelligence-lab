from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r4"
ACTIVATION = BASE / "R4_EXECUTION_RELEASE_CANONICALIZATION.json"
ANCHOR = BASE / "R4_BODY_RELEASE_ACTIVATION_ANCHOR.json"
CANDIDATE = BASE / "R4_EXECUTION_RELEASE.json"
APPROVAL = BASE / "approvals/APPROVE_HL_ARCHIVE_HOURLY_BODY_SCHEMA_PILOT_R4_001.json"
APPROVAL_TEXT = BASE / "approvals/APPROVE_HL_ARCHIVE_HOURLY_BODY_SCHEMA_PILOT_R4_001.txt"
PREFLIGHT_ATTESTATION = BASE / "role_attestation/HL-ARCHIVE-R4-DEDICATED-ROLE-STS-PREFLIGHT-001-ATTESTATION.json"
PREFLIGHT_CONSUMPTION = BASE / "role_attestation/R4_ROLE_STS_PREFLIGHT_RELEASE_CONSUMPTION.json"
PREFLIGHT_VERIFICATION = BASE / "role_attestation/evidence/run-31312067367/INDEPENDENT_ARTIFACT_VERIFICATION.json"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def main() -> int:
    a = load(ACTIVATION)
    anchor = load(ANCHOR)
    candidate = load(CANDIDATE)
    approval = load(APPROVAL)
    preflight_attestation = load(PREFLIGHT_ATTESTATION)
    preflight_consumption = load(PREFLIGHT_CONSUMPTION)
    preflight_verification = load(PREFLIGHT_VERIFICATION)

    assert a["release_id"] == "RELEASE_HL_ARCHIVE_HOURLY_BODY_SCHEMA_PILOT_R4_001"
    assert a["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R4_RUN"
    assert a["pilot_id"] == "HL-ARCHIVE-HOURLY-BODY-SCHEMA-PILOT-R4-001"
    assert a["release_candidate_merge_commit"] == "01521d1cad209263a217dbcca98ecd74ec16857c"
    assert a["release_candidate_immutable"] is True
    assert a["activation_anchor_commit"] == "c259a39f630e2ff59f8291483033e6213b470c3c"
    assert a["single_use_window_start_utc"] == "2026-08-09T12:12:39Z"
    assert a["preregistration_commit"] == "25a1f621d15cb708a485893025f03b991628aae1"
    assert a["approval_merge_commit"] == "0191350683c6c943d3538c8c51db176cd1d58211"
    assert a["approval_text_sha256"] == hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest()
    assert a["approval_text_sha256"] == approval["exact_approval_text_sha256"]
    assert a["implementation_commit"] == "180c89ead78f9a6f4560a1ec12575658e62586ee"

    assert anchor["base_main_commit"] == "a91f0849e8cf14b6924da73ca2b72595deab5d8d"
    assert anchor["preflight_run_id"] == 31312067367
    assert anchor["execution_authorized_by_this_file"] is False
    assert anchor["single_workflow_dispatch_authorized_by_this_file"] is False
    assert anchor["s3_requests_executed"] == 0

    assert candidate["status"] == "RELEASE_CANDIDATE_AWAITING_DEDICATED_R4_ROLE_ATTESTATION"
    assert candidate["implementation_commit"] == a["implementation_commit"]
    assert candidate["single_workflow_dispatch_authorized"] is False
    assert candidate["requester_pays_authorized"] is False
    assert candidate["get_object_authorized"] is False
    assert candidate["decompression_authorized"] is False
    assert candidate["execution_ready"] is False
    assert candidate["s3_requests_executed"] == 0
    assert candidate["empirical_result"] is None

    assert a["role_attestation_merge_commit"] == "c45527941dea7d152e332327ebd0593dc2413bea"
    assert a["operator_attestation_text_sha256"] == "5af72489211b1ad79e35f0491502e34d518df7c14ae6f2f8d56fbd2c3a5a83c2"
    assert a["preflight_evidence_merge_commit"] == "a91f0849e8cf14b6924da73ca2b72595deab5d8d"
    assert a["preflight_run_id"] == 31312067367
    assert a["preflight_job_id"] == 93241269551
    assert a["preflight_artifact_id"] == 9037655204
    assert a["preflight_artifact_sha256"] == "6d30969525156ad3354c4a9abdb5d661cfc1b7b2d1a6cfd07eb02f4300f20376"
    assert a["preflight_terminal_status"] == "R4_ROLE_STS_PREFLIGHT_PASS"
    assert a["preflight_technical_result"] == "DEDICATED_R4_ROLE_ASSUMEABLE_FROM_CANONICAL_MAIN"
    assert a["preflight_release_consumed"] is True
    assert a["preflight_rerun_authorized"] is False
    assert a["preflight_s3_requests_executed"] == 0
    assert preflight_attestation["operator_attestation_independently_verified_by_preflight"] is True
    assert preflight_consumption["status"] == "CONSUMED_SUCCESS"
    assert preflight_consumption["rerun_authorized"] is False
    assert preflight_verification["verification_result"] == "ALL_CHECKS_PASS"
    assert preflight_verification["provider_sha256"] == a["preflight_artifact_sha256"]

    assert a["github_event_required"] == "workflow_dispatch"
    assert a["canonical_dispatch_ref_required"] == "refs/heads/main"
    assert a["canonical_dispatch_sha_source"] == "github.sha"
    assert a["dedicated_r4_role_arn"] == "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"
    assert a["dedicated_r4_role_operator_attested"] is True
    assert a["dedicated_r4_role_independently_verified"] is True
    assert a["target_bucket"] == "hl-mainnet-node-data"
    assert a["signing_region"] == "ap-northeast-1"
    assert a["regional_virtual_hosted_endpoint"] == "hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com"
    assert a["operation"] == "GetObject"
    assert a["request_payer"] == "requester"

    assert a["object_keys"] == [
        "node_fills/hourly/20250727/8.lz4",
        "node_fills_by_block/hourly/20250727/8.lz4",
    ]
    assert a["object_sizes_bytes"] == [12726384, 1517603]
    assert a["object_etags"] == [
        '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"',
        '"60d4c1277f76651b5f04666bbe8d7594"',
    ]
    assert sum(a["object_sizes_bytes"]) == 14243987
    assert a["maximum_one_time_budget_eur"] == 0.10
    assert a["maximum_monthly_budget_eur"] == 0
    assert a["maximum_get_object_requests"] == 2
    assert a["maximum_requests_per_object"] == 1
    assert a["maximum_total_compressed_bytes"] == 14243987
    assert a["maximum_total_decompressed_bytes"] == 536870912
    assert a["maximum_decompressed_bytes_per_object"] == 268435456
    assert a["maximum_runtime_seconds"] == 180
    assert a["maximum_retries_per_request"] == 0
    assert a["maximum_record_bytes"] == 16777216
    assert a["maximum_records_parsed_per_object"] == 5000000
    assert a["maximum_schema_nesting_depth"] == 16
    assert a["maximum_unique_field_paths"] == 4096

    for key in (
        "if_match_etag_required",
        "exact_content_length_required",
        "requester_pays_authorized",
        "get_object_authorized",
        "object_body_download_authorized",
        "decompression_authorized",
        "lz4_frame_stream_only",
        "schema_parser_utf8_ndjson_object_stream_only",
        "single_workflow_dispatch_authorized",
        "execution_ready",
    ):
        assert a[key] is True, key
    assert a["rerun_authorized"] is False

    for key in (
        "head_object_authorized",
        "range_get_authorized",
        "list_objects_v2_authorized",
        "list_object_versions_authorized",
        "list_all_my_buckets_authorized",
        "http_redirect_following_authorized",
        "alternate_decompressor_fallback_authorized",
        "raw_compressed_object_retention_authorized",
        "raw_decompressed_payload_retention_authorized",
        "record_payload_retention_authorized",
        "wallet_address_retention_from_body_authorized",
        "payload_values_in_schema_evidence_authorized",
        "semantic_equivalence_inference_authorized",
        "wallet_reconstruction_authorized",
        "entity_clustering_authorized",
        "copyability_analysis_authorized",
        "pnl_or_alpha_analysis_authorized",
        "market_data_ingestion_authorized",
    ):
        assert a[key] is False, key
    assert all(value is False for value in a["trading_authorizations"].values())
    assert a["s3_requests_executed"] == 0
    assert a["compressed_bytes_downloaded"] == 0
    assert a["decompressed_bytes_processed"] == 0
    assert a["empirical_result"] is None

    print("R4_BODY_ACTIVATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
