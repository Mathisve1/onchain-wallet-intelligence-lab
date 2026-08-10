from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
PREREG = BASE / "r10a/R10A_TIMESTAMP_PARTITION_PREREGISTRATION.json"
APPROVAL_DIR = BASE / "r10a_approval"
TEXT = APPROVAL_DIR / "APPROVE_HL_ARCHIVE_R10A_TIMESTAMP_PARTITION_DIAGNOSTIC_001.txt"
RECEIPT = APPROVAL_DIR / "APPROVE_HL_ARCHIVE_R10A_TIMESTAMP_PARTITION_DIAGNOSTIC_001.json"
IMPLEMENTATION = BASE / "r10a_implementation/R10A_IMPLEMENTATION_CONTRACT.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r10a-timestamp-partition-diagnostic.yml"
RELEASE = BASE / "r10a_runtime/R10A_EXECUTION_RELEASE.json"
EXPECTED_SHA = "c990a1636b745908d9f58c4b119998dfa91b4e8740764081bbb19cb8ad8904f1"
REVIEWED = "7db55db0be5efeeadb569abb5faaadf3bc78254a"
APPROVAL_MERGE = "b67e4a0ca91a411230f3c1b8cebac047d6c69261"
ROLE = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
KEY = "node_fills_by_block/hourly/20250727/9.lz4"
ETAG = '"5a9941a240118a57f77a4c3ee95b8430-3"'


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def validate_later_implementation_if_present() -> None:
    if not IMPLEMENTATION.exists():
        assert not WORKFLOW.exists()
        assert not RELEASE.exists()
        return
    i = load(IMPLEMENTATION)
    assert i["diagnostic_id"] == "HL-ARCHIVE-R10A-TIMESTAMP-PARTITION-DIAGNOSTIC-001"
    assert i["status"] == "IMPLEMENTED_AWAITING_SEPARATE_EXECUTION_RELEASE"
    assert i["r10a_preregistration_merge_commit"] == REVIEWED
    assert i["r10a_approval_merge_commit"] == APPROVAL_MERGE
    assert i["approval_text_sha256"] == EXPECTED_SHA
    assert i["role_arn"] == ROLE
    assert i["role_reused_without_mutation"] is True
    assert i["new_role_created"] is False
    assert i["execution_release_required"] is True
    assert i["execution_release_present"] is False
    assert i["single_workflow_dispatch_authorized"] is False
    assert i["aws_oidc_authorized_now"] is False
    assert i["get_object_authorized_now"] is False
    assert i["network_requests_executed"] == 0
    assert i["aws_iam_mutations_executed"] == 0
    assert i["empirical_result"] is None
    assert all(v is False for v in i["downstream_authorizations"].values())
    assert all(v is False for v in i["trading_authorizations"].values())
    assert WORKFLOW.is_file()
    assert not RELEASE.exists()


def main() -> int:
    p = load(PREREG)
    a = load(RECEIPT)
    raw = TEXT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_SHA
    assert raw.endswith(b"\n")
    assert a["approval_id"] == "APPROVE_HL_ARCHIVE_R10A_TIMESTAMP_PARTITION_DIAGNOSTIC_001"
    assert a["diagnostic_id"] == p["diagnostic_id"] == "HL-ARCHIVE-R10A-TIMESTAMP-PARTITION-DIAGNOSTIC-001"
    assert a["status"] == "OWNER_APPROVED_IMPLEMENTATION_NO_EXECUTION"
    assert a["reviewed_commit"] == REVIEWED
    assert a["exact_approval_text_sha256"] == EXPECTED_SHA
    scope = a["approved_future_scope"]
    target = p["exact_future_network_target"]
    assert scope["maximum_one_time_budget_eur"] == 0.10
    assert scope["maximum_monthly_budget_eur"] == 0
    assert scope["maximum_get_object_requests"] == 1
    assert scope["maximum_requests_per_object"] == 1
    assert scope["maximum_retries_per_request"] == 0
    assert scope["maximum_total_compressed_bytes"] == target["expected_size_bytes"] == 18147822
    assert scope["maximum_total_decompressed_bytes"] == 268435456
    assert scope["maximum_runtime_seconds"] == 120
    assert scope["target_bucket"] == target["bucket"] == "hl-mainnet-node-data"
    assert scope["signing_region"] == target["region"] == "ap-northeast-1"
    assert scope["object_key"] == target["key"] == KEY
    assert scope["object_expected_etag"] == target["expected_etag"] == ETAG
    transport = a["approved_future_transport"]
    assert transport["requester_pays"] is True and transport["get_object"] is True
    assert all(transport[k] is False for k in ("head_object","range_get","list_objects_v2","list_object_versions","list_all_my_buckets","get_object_attributes","get_object_version","http_redirect_following"))
    role = a["approved_role_reuse"]
    assert role["existing_dedicated_r10_role_reuse"] is True
    assert role["existing_dedicated_r10_role_mutation"] is False
    assert role["new_role_creation"] is False
    assert role["role_arn"] == ROLE
    assert role["future_session_policy_allowed_s3_actions_only"] == ["s3:GetObject"]
    assert role["future_session_policy_allowed_object_count"] == 1
    assert role["future_role_duration_seconds"] == 900
    processing = a["approved_future_processing"]
    assert processing["decompression"] is True
    assert processing["timestamp_processing"] is True
    assert processing["aggregate_alignment_retention"] is True
    assert all(processing[k] is False for k in ("individual_timestamp_retention","wallet_address_retention","wallet_aggregation","economic_fill_field_processing","timezone_inference_for_local_time","raw_object_retention","raw_block_event_fill_retention"))
    assert all(v is False for v in a["current_runtime_authority"].values())
    assert a["execution_authorized_by_this_approval"] is False
    assert a["separate_execution_release_required"] is True
    assert a["separate_canonical_activation_required"] is True
    assert all(v is False for v in a["downstream_authorizations"].values())
    assert all(v is False for v in a["trading_authorizations"].values())
    validate_later_implementation_if_present()
    print("R10A_APPROVAL_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
