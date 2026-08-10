from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
IMPL = BASE / "r10a_implementation/R10A_IMPLEMENTATION_CONTRACT.json"
APPROVAL = BASE / "r10a_approval/APPROVE_HL_ARCHIVE_R10A_TIMESTAMP_PARTITION_DIAGNOSTIC_001.json"
APPROVAL_TEXT = BASE / "r10a_approval/APPROVE_HL_ARCHIVE_R10A_TIMESTAMP_PARTITION_DIAGNOSTIC_001.txt"
PREREG = BASE / "r10a/R10A_TIMESTAMP_PARTITION_PREREGISTRATION.json"
COLLECTOR = BASE / "r10a_implementation/collector.py"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r10a-timestamp-partition-diagnostic.yml"
RELEASE = BASE / "r10a_runtime/R10A_EXECUTION_RELEASE.json"
APPROVAL_SHA = "c990a1636b745908d9f58c4b119998dfa91b4e8740764081bbb19cb8ad8904f1"
ROLE = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
OBJECT_ARN = "arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250727/9.lz4"


def load(path: Path) -> dict:
    value=json.loads(path.read_text(encoding="utf-8")); assert isinstance(value,dict); return value


def main() -> int:
    i=load(IMPL); a=load(APPROVAL); p=load(PREREG)
    assert hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest()==APPROVAL_SHA
    assert i["diagnostic_id"]==p["diagnostic_id"]==a["diagnostic_id"]=="HL-ARCHIVE-R10A-TIMESTAMP-PARTITION-DIAGNOSTIC-001"
    assert i["status"]=="IMPLEMENTED_AWAITING_SEPARATE_EXECUTION_RELEASE"
    assert i["r10a_preregistration_merge_commit"]=="7db55db0be5efeeadb569abb5faaadf3bc78254a"
    assert i["r10a_approval_merge_commit"]=="b67e4a0ca91a411230f3c1b8cebac047d6c69261"
    assert i["approval_text_sha256"]==APPROVAL_SHA
    assert i["role_arn"]==ROLE and i["role_reused_without_mutation"] is True and i["new_role_created"] is False
    t=i["exact_network_target"]
    assert t=={"bucket":"hl-mainnet-node-data","region":"ap-northeast-1","key":"node_fills_by_block/hourly/20250727/9.lz4","path_hour_utc":"2025-07-27T09:00:00Z","expected_size_bytes":18147822,"expected_etag":'"5a9941a240118a57f77a4c3ee95b8430-3"'}
    e=i["execution_envelope"]
    assert e["maximum_get_object_requests"]==1 and e["maximum_requests_per_object"]==1 and e["maximum_retries_per_request"]==0
    assert e["maximum_total_compressed_bytes"]==18147822 and e["maximum_total_decompressed_bytes"]==268435456 and e["maximum_runtime_seconds"]==120
    assert e["requester_pays_required"] is True and e["if_match_etag_required"] is True
    assert all(e[k] is False for k in ("http_redirect_following_authorized","head_object_authorized","range_get_authorized","list_objects_v2_authorized","list_object_versions_authorized","list_all_my_buckets_authorized","get_object_attributes_authorized","get_object_version_authorized"))
    b=i["processing_boundary"]
    assert b["decompression"] is True and b["timestamp_processing"] is True and b["aggregate_alignment_retention"] is True
    assert all(b[k] is False for k in ("individual_timestamp_retention","wallet_address_retention","wallet_aggregation","economic_fill_field_processing","timezone_inference_for_local_time","raw_object_retention","raw_block_event_fill_retention"))
    assert i["execution_release_required"] is True and i["execution_release_present"] is False
    assert i["single_workflow_dispatch_authorized"] is False and i["aws_oidc_authorized_now"] is False and i["get_object_authorized_now"] is False
    assert i["network_requests_executed"]==0 and i["aws_iam_mutations_executed"]==0 and i["empirical_result"] is None
    assert all(v is False for v in i["downstream_authorizations"].values()) and all(v is False for v in i["trading_authorizations"].values())
    assert COLLECTOR.is_file() and WORKFLOW.is_file() and not RELEASE.exists()
    text=WORKFLOW.read_text(encoding="utf-8")
    assert text.startswith("name: Hyperliquid Archive Post-Boundary Multi-Hour Feature Pilot R10\n")
    assert "run-name: R10A timestamp partition diagnostic" in text
    assert "workflow_dispatch:" in text and "id-token: write" in text
    assert "role-duration-seconds: 900" in text and "retry-max-attempts: 1" in text
    assert OBJECT_ARN in text
    assert '"Action":"s3:GetObject"' in text and text.count(OBJECT_ARN)==1
    assert "R10A_EXECUTION_RELEASE.json" in text
    assert text.index('test -f "${RELEASE_PATH}"') < text.index("aws-actions/configure-aws-credentials")
    assert "python -m research.archive_inventory.r10a_implementation.collector" in text
    assert "python research/archive_inventory/r10a_implementation/collector.py" not in text
    assert "aws s3" not in text and "aws s3api" not in text
    source=COLLECTOR.read_text(encoding="utf-8")
    for forbidden in ("closedPnl", "feeToken", "startPosition", "sum_abs_px", "wallet_feature"):
        assert forbidden not in source
    assert "pair[0]" in source and "wallet_address_retained\": False" in source
    print("R10A_IMPLEMENTATION_VALID")
    return 0


if __name__=="__main__": raise SystemExit(main())
