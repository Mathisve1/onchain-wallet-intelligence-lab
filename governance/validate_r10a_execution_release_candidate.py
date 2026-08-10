from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
CANDIDATE = BASE / "r10a_runtime/R10A_EXECUTION_RELEASE_CANDIDATE.json"
IMPLEMENTATION = BASE / "r10a_implementation/R10A_IMPLEMENTATION_CONTRACT.json"
APPROVAL = BASE / "r10a_approval/APPROVE_HL_ARCHIVE_R10A_TIMESTAMP_PARTITION_DIAGNOSTIC_001.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r10a-timestamp-partition-diagnostic.yml"
RELEASE = BASE / "r10a_runtime/R10A_EXECUTION_RELEASE.json"
ROLE = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
WORKFLOW_BLOB_SHA = "1aeec8b4fe09a3ddffb85171ca62da94e56cc2ba"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def main() -> int:
    c = load(CANDIDATE)
    i = load(IMPLEMENTATION)
    a = load(APPROVAL)
    assert c["release_candidate_id"] == "CANDIDATE_RELEASE_HL_ARCHIVE_R10A_TIMESTAMP_PARTITION_001"
    assert c["diagnostic_id"] == i["diagnostic_id"] == a["diagnostic_id"] == "HL-ARCHIVE-R10A-TIMESTAMP-PARTITION-DIAGNOSTIC-001"
    assert c["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
    assert c["r10a_preregistration_merge_commit"] == "7db55db0be5efeeadb569abb5faaadf3bc78254a"
    assert c["r10a_approval_merge_commit"] == "b67e4a0ca91a411230f3c1b8cebac047d6c69261"
    assert c["r10a_implementation_merge_commit"] == "91eca6f1c93ef58d889b9d8b78fcee81731dd2cc"
    assert c["approval_text_sha256"] == "c990a1636b745908d9f58c4b119998dfa91b4e8740764081bbb19cb8ad8904f1"
    assert c["workflow_path"] == ".github/workflows/hyperliquid-archive-r10a-timestamp-partition-diagnostic.yml"
    assert c["workflow_name"] == "Hyperliquid Archive Post-Boundary Multi-Hour Feature Pilot R10"
    assert c["workflow_run_name"] == "R10A timestamp partition diagnostic"
    assert c["workflow_git_blob_sha"] == WORKFLOW_BLOB_SHA
    assert git_blob_sha(WORKFLOW.read_bytes()) == WORKFLOW_BLOB_SHA
    assert c["role_arn"] == ROLE and c["role_reuse_without_mutation"] is True
    target = c["exact_network_target"]
    assert target == {
        "bucket":"hl-mainnet-node-data","region":"ap-northeast-1",
        "key":"node_fills_by_block/hourly/20250727/9.lz4","path_hour_utc":"2025-07-27T09:00:00Z",
        "expected_size_bytes":18147822,"expected_etag":'"5a9941a240118a57f77a4c3ee95b8430-3"',
    }
    e = c["execution_envelope"]
    assert e["maximum_one_time_budget_eur"] == 0.10 and e["maximum_monthly_budget_eur"] == 0
    assert e["maximum_get_object_requests"] == 1 and e["maximum_requests_per_object"] == 1 and e["maximum_retries_per_request"] == 0
    assert e["maximum_total_compressed_bytes"] == 18147822 and e["maximum_total_decompressed_bytes"] == 268435456
    assert e["maximum_runtime_seconds"] == 120
    assert e["requester_pays_required"] is True and e["if_match_etag_required"] is True
    assert e["exact_content_length_required"] is True and e["exact_response_etag_required"] is True
    assert all(e[k] is False for k in ("http_redirect_following_authorized","head_object_authorized","range_get_authorized","list_objects_v2_authorized","list_object_versions_authorized","list_all_my_buckets_authorized","get_object_attributes_authorized","get_object_version_authorized"))
    p = c["future_processing_authority_if_separately_activated"]
    assert p["decompression"] is True and p["timestamp_processing"] is True and p["aggregate_alignment_retention"] is True
    assert all(p[k] is False for k in ("individual_timestamp_retention","wallet_address_retention","wallet_aggregation","economic_fill_field_processing","timezone_inference_for_local_time","raw_object_retention","raw_block_event_fill_retention"))
    assert c["canonical_activation_required"] is True and c["canonical_activation_present"] is False
    assert c["single_use_window_start_utc"] is None
    for key in ("single_workflow_dispatch_authorized","aws_oidc_authorized","requester_pays_authorized","get_object_authorized","object_body_download_authorized","decompression_authorized","timestamp_processing_authorized","aggregate_alignment_retention_authorized","release_consumed","rerun_authorized"):
        assert c[key] is False, key
    assert c["network_requests_executed"] == 0 and c["aws_iam_mutations_executed"] == 0 and c["empirical_result"] is None
    assert all(v is False for v in c["downstream_authorizations"].values())
    assert all(v is False for v in c["trading_authorizations"].values())
    assert i["status"] == "IMPLEMENTED_AWAITING_SEPARATE_EXECUTION_RELEASE"
    assert i["execution_release_present"] is False and i["single_workflow_dispatch_authorized"] is False
    assert a["execution_authorized_by_this_approval"] is False
    assert not RELEASE.exists()
    print("R10A_EXECUTION_RELEASE_CANDIDATE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
