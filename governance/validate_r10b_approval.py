from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
PREREG = BASE / "r10b/R10B_BATCH_METADATA_LEXICAL_PREREGISTRATION.json"
DIR = BASE / "r10b_approval"
TEXT = DIR / "APPROVE_HL_ARCHIVE_R10B_BATCH_METADATA_LEXICAL_DIAGNOSTIC_001.txt"
RECEIPT = DIR / "APPROVE_HL_ARCHIVE_R10B_BATCH_METADATA_LEXICAL_DIAGNOSTIC_001.json"
EXPECTED_SHA = "981b9277b652117c2a3648fa3870015d3efe590a595e84bcba22cf0b3f8f8061"
REVIEWED = "8ba7b0928ac45c66dd6df756491928fddbe2a060"
ROLE = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
KEY = "node_fills_by_block/hourly/20250727/9.lz4"
ETAG = '"5a9941a240118a57f77a4c3ee95b8430-3"'
OBJECT_SHA = "42fa96f9d693eb93d184c24a830483cea2e4aa526fc2ffb999619d24e41cc339"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    p = load(PREREG)
    a = load(RECEIPT)
    raw = TEXT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_SHA
    assert raw.endswith(b"\n")
    assert a["approval_id"] == "APPROVE_HL_ARCHIVE_R10B_BATCH_METADATA_LEXICAL_DIAGNOSTIC_001"
    assert a["diagnostic_id"] == p["diagnostic_id"] == "HL-ARCHIVE-R10B-BATCH-METADATA-LEXICAL-DIAGNOSTIC-001"
    assert a["status"] == "OWNER_APPROVED_IMPLEMENTATION_NO_EXECUTION"
    assert a["reviewed_commit"] == REVIEWED
    assert a["exact_approval_text_sha256"] == EXPECTED_SHA
    assert a["approval_source"] == "EXPLICIT_CHAT_CONFIRMATION_REFERENCING_PREVIOUSLY_PRESENTED_EXACT_APPROVAL_BLOCK"
    assert a["approval_source_user_text"] == "ga verder hiermee, ik heb je toestemming gegeven"

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
    assert scope["object_expected_size_bytes"] == target["expected_size_bytes"] == 18147822
    assert scope["object_expected_etag"] == target["expected_etag"] == ETAG
    assert scope["object_expected_compressed_sha256"] == target["expected_compressed_sha256_from_r10a"] == OBJECT_SHA

    transport = a["approved_future_transport"]
    assert transport["requester_pays"] is True and transport["get_object"] is True
    for key in ("head_object","range_get","list_objects_v2","list_object_versions","list_all_my_buckets","get_object_attributes","get_object_version","http_redirect_following"):
        assert transport[key] is False, key

    role = a["approved_role_reuse"]
    assert role["existing_dedicated_r10_role_reuse"] is True
    assert role["existing_dedicated_r10_role_mutation"] is False
    assert role["new_role_creation"] is False
    assert role["role_arn"] == ROLE
    assert role["future_session_policy_allowed_s3_actions_only"] == ["s3:GetObject"]
    assert role["future_session_policy_allowed_object_count"] == 1
    assert role["future_session_policy_exact_object_arn"] == f"arn:aws:s3:::hl-mainnet-node-data/{KEY}"
    assert role["future_role_duration_seconds"] == 900

    processing = a["approved_future_processing"]
    for key in ("decompression", "metadata_lexical_processing", "aggregate_lexical_retention"):
        assert processing[key] is True, key
    for key in ("timezone_parsing","timezone_inference","datetime_conversion","individual_metadata_value_retention","event_array_contents_inspection","event_pair_count_retention","block_number_value_retention","wallet_address_retention","wallet_aggregation","economic_fill_field_processing","individual_fill_time_processing","raw_object_retention","raw_block_event_fill_retention"):
        assert processing[key] is False, key

    assert all(v is False for v in a["current_runtime_authority"].values())
    assert a["execution_authorized_by_this_approval"] is False
    assert a["separate_execution_release_required"] is True
    assert a["separate_canonical_activation_required"] is True
    assert all(v is False for v in a["downstream_authorizations"].values())
    assert all(v is False for v in a["trading_authorizations"].values())
    assert not (BASE / "r10b_implementation").exists()
    assert not (ROOT / ".github/workflows/hyperliquid-archive-r10b-batch-metadata-lexical-diagnostic.yml").exists()
    print("R10B_APPROVAL_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
