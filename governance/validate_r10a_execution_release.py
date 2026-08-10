from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"research/archive_inventory"
RELEASE=BASE/"r10a_runtime/R10A_EXECUTION_RELEASE.json"
CANDIDATE=BASE/"r10a_runtime/R10A_EXECUTION_RELEASE_CANDIDATE.json"
IMPL=BASE/"r10a_implementation/R10A_IMPLEMENTATION_CONTRACT.json"
APPROVAL=BASE/"r10a_approval/APPROVE_HL_ARCHIVE_R10A_TIMESTAMP_PARTITION_DIAGNOSTIC_001.json"
WORKFLOW=ROOT/".github/workflows/hyperliquid-archive-r10a-timestamp-partition-diagnostic.yml"
WORKFLOW_BLOB_SHA="1aeec8b4fe09a3ddffb85171ca62da94e56cc2ba"
ROLE="arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
START="2026-08-10T11:40:00Z"


def load(path:Path)->dict:
    value=json.loads(path.read_text(encoding="utf-8")); assert isinstance(value,dict); return value


def git_blob_sha(data:bytes)->str:
    return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()


def main()->int:
    r=load(RELEASE); c=load(CANDIDATE); i=load(IMPL); a=load(APPROVAL)
    assert r["execution_release_id"]=="RELEASE_HL_ARCHIVE_R10A_TIMESTAMP_PARTITION_001"
    assert r["release_candidate_id"]==c["release_candidate_id"]=="CANDIDATE_RELEASE_HL_ARCHIVE_R10A_TIMESTAMP_PARTITION_001"
    assert r["diagnostic_id"]==c["diagnostic_id"]==i["diagnostic_id"]==a["diagnostic_id"]=="HL-ARCHIVE-R10A-TIMESTAMP-PARTITION-DIAGNOSTIC-001"
    assert r["status"]=="RELEASED_FOR_EXACTLY_ONE_CANONICAL_R10A_RUN"
    assert r["r10a_preregistration_merge_commit"]=="7db55db0be5efeeadb569abb5faaadf3bc78254a"
    assert r["r10a_approval_merge_commit"]=="b67e4a0ca91a411230f3c1b8cebac047d6c69261"
    assert r["r10a_implementation_merge_commit"]=="91eca6f1c93ef58d889b9d8b78fcee81731dd2cc"
    assert r["release_candidate_merge_commit"]=="e67b42ca6b605d3762604c46830df27d9d9574ec"
    assert r["approval_text_sha256"]=="c990a1636b745908d9f58c4b119998dfa91b4e8740764081bbb19cb8ad8904f1"
    assert r["workflow_path"]==".github/workflows/hyperliquid-archive-r10a-timestamp-partition-diagnostic.yml"
    assert r["workflow_name"]=="Hyperliquid Archive Post-Boundary Multi-Hour Feature Pilot R10"
    assert r["workflow_run_name"]=="R10A timestamp partition diagnostic"
    assert r["workflow_git_blob_sha"]==WORKFLOW_BLOB_SHA==git_blob_sha(WORKFLOW.read_bytes())
    assert r["role_arn"]==ROLE and r["role_reuse_without_mutation"] is True
    assert r["single_use_window_start_utc"]==START
    start=datetime.fromisoformat(START.replace("Z","+00:00")).astimezone(timezone.utc)
    assert start.isoformat()=="2026-08-10T11:40:00+00:00"
    assert r["single_workflow_dispatch_authorized"] is True
    assert r["rerun_authorized"] is False and r["release_consumed"] is False
    assert r["maximum_one_time_budget_eur"]==0.10 and r["maximum_monthly_budget_eur"]==0
    assert r["maximum_get_object_requests"]==1 and r["maximum_requests_per_object"]==1 and r["maximum_retries_per_request"]==0
    assert r["maximum_total_compressed_bytes"]==18147822 and r["maximum_total_decompressed_bytes"]==268435456 and r["maximum_runtime_seconds"]==120
    assert r["target_bucket"]=="hl-mainnet-node-data" and r["signing_region"]=="ap-northeast-1"
    assert r["object_key"]=="node_fills_by_block/hourly/20250727/9.lz4"
    assert r["path_hour_utc"]=="2025-07-27T09:00:00Z"
    assert r["object_expected_size_bytes"]==18147822 and r["object_expected_etag"]=='"5a9941a240118a57f77a4c3ee95b8430-3"'
    for key in ("requester_pays_authorized","get_object_authorized","object_body_download_authorized","decompression_authorized","timestamp_processing_authorized","aggregate_alignment_retention_authorized"):
        assert r[key] is True,key
    for key in ("head_object_authorized","range_get_authorized","list_objects_v2_authorized","list_object_versions_authorized","list_all_my_buckets_authorized","get_object_attributes_authorized","get_object_version_authorized","http_redirect_following_authorized","individual_timestamp_retention_authorized","wallet_address_retention_authorized","wallet_aggregation_authorized","economic_fill_field_processing_authorized","timezone_inference_for_local_time_authorized","raw_object_retention_authorized","raw_block_event_fill_retention_authorized"):
        assert r[key] is False,key
    assert r["network_requests_executed_by_release_creation"]==0 and r["aws_iam_mutations_executed_by_release_creation"]==0 and r["empirical_result"] is None
    assert all(v is False for v in r["downstream_authorizations"].values())
    assert all(v is False for v in r["trading_authorizations"].values())

    # Immutable prior snapshots remain non-self-authorizing.
    assert c["status"]=="RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
    assert c["canonical_activation_present"] is False
    assert c["single_workflow_dispatch_authorized"] is False
    assert c["aws_oidc_authorized"] is False and c["get_object_authorized"] is False
    assert i["status"]=="IMPLEMENTED_AWAITING_SEPARATE_EXECUTION_RELEASE"
    assert i["execution_release_present"] is False and i["single_workflow_dispatch_authorized"] is False
    assert a["execution_authorized_by_this_approval"] is False
    assert a["separate_execution_release_required"] is True and a["separate_canonical_activation_required"] is True
    print("R10A_EXECUTION_RELEASE_VALID")
    return 0


if __name__=="__main__": raise SystemExit(main())
