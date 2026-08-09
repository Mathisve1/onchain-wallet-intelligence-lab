from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R10 = ROOT / "research/archive_inventory/r10"
CONTRACT = R10 / "POST_BOUNDARY_MULTI_HOUR_FEATURE_R10_CONTRACT.json"
TEMPLATE = R10 / "HUMAN_APPROVAL_TEMPLATE_R10.md"
STATUS = R10 / "APPROVAL_STATUS.md"
APPROVAL_TXT = R10 / "approvals/APPROVE_HL_ARCHIVE_POST_BOUNDARY_MULTI_HOUR_FEATURE_R10_001.txt"
APPROVAL_JSON = R10 / "approvals/APPROVE_HL_ARCHIVE_POST_BOUNDARY_MULTI_HOUR_FEATURE_R10_001.json"

APPROVAL_ID = "APPROVE_HL_ARCHIVE_POST_BOUNDARY_MULTI_HOUR_FEATURE_R10_001"
PILOT_ID = "HL-ARCHIVE-POST-BOUNDARY-MULTI-HOUR-FEATURE-R10-001"
PREREG_MERGE = "37e4486a7f68982feafcb361bd40dffd546def05"
APPROVAL_SHA = "ec631e7e6d40cb63383afd012a989419f97cd603ff144e4c5dfb90c18ff90882"
ROLE_NAME = "onchain-wallet-intelligence-hl-archive-multihour-r10"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
EXPECTED = [
    ("node_fills_by_block/hourly/20250727/9.lz4", 18147822, '"5a9941a240118a57f77a4c3ee95b8430-3"'),
    ("node_fills_by_block/hourly/20250727/10.lz4", 21349239, '"cb25fba5dc3be80fd8c46dde03144655-3"'),
    ("node_fills_by_block/hourly/20250727/11.lz4", 17582600, '"758da733bb2d3913d0fdd8088b6fb63d-3"'),
    ("node_fills_by_block/hourly/20250727/12.lz4", 21672141, '"d6ee46b1bdfad4026e21d4285ed0cbc5-3"'),
    ("node_fills_by_block/hourly/20250727/13.lz4", 20840630, '"c3c9db0101ff278b5ced13ab278a2b85-3"'),
    ("node_fills_by_block/hourly/20250727/14.lz4", 21407266, '"3c6ab944be1ed8bd12932eb390267a21-3"'),
]


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    contract = load(CONTRACT)
    approval = load(APPROVAL_JSON)
    approval_text = APPROVAL_TXT.read_text(encoding="utf-8")
    template = TEMPLATE.read_text(encoding="utf-8")
    status = STATUS.read_text(encoding="utf-8")

    assert contract["pilot_id"] == PILOT_ID
    assert contract["status"] == "PREREGISTERED_NO_EXECUTION"
    assert contract["human_approval_required_before_implementation"] is True
    assert contract["network_requests_executed_by_r10_preregistration"] == 0
    assert contract["aws_iam_mutations_executed_by_r10_preregistration"] == 0

    assert approval["approval_id"] == APPROVAL_ID
    assert approval["pilot_id"] == PILOT_ID
    assert approval["reviewed_commit"] == PREREG_MERGE
    assert approval["status"] == "OWNER_APPROVED_IMPLEMENTATION_AND_DEDICATED_ROLE_CREATION_NO_EXECUTION"
    assert approval["exact_approval_text_sha256"] == APPROVAL_SHA
    assert hashlib.sha256(approval_text.encode("utf-8")).hexdigest() == APPROVAL_SHA

    match = re.search(r"```text\n(.*?)```", template, flags=re.DOTALL)
    assert match is not None
    expected_text = match.group(1).replace("<CANONICAL_R10_PREREGISTRATION_MERGE_COMMIT>", PREREG_MERGE)
    assert approval_text == expected_text

    scope = approval["approved_future_scope"]
    assert scope == {
        "maximum_one_time_budget_eur": 0.10,
        "maximum_monthly_budget_eur": 0,
        "maximum_get_object_requests": 6,
        "maximum_requests_per_object": 1,
        "maximum_total_compressed_bytes": 120999698,
        "maximum_individual_compressed_bytes": 21672141,
        "maximum_total_decompressed_bytes": 1073741824,
        "maximum_individual_decompressed_bytes": 268435456,
        "maximum_runtime_seconds": 300,
        "maximum_retries_per_request": 0,
        "target_bucket": "hl-mainnet-node-data",
        "signing_region": "ap-northeast-1",
        "window_start_utc": "2025-07-27T09:00:00Z",
        "window_end_exclusive_utc": "2025-07-27T15:00:00Z",
        "selected_hour_count": 6,
        "request_order": "PATH_HOUR_ASCENDING",
        "stop_after_first_failed_or_mismatched_object": True,
    }

    objects = approval["approved_future_objects"]
    assert len(objects) == 6
    assert sum(row["size_bytes"] for row in objects) == 120999698
    for row, (key, size, etag) in zip(objects, EXPECTED, strict=True):
        assert row == {"key": key, "size_bytes": size, "etag": etag}

    role = approval["dedicated_role_authorization"]
    assert role["existing_r4_role_reuse_authorized"] is False
    assert role["existing_r4_role_mutation_authorized"] is False
    assert role["new_dedicated_r10_role_creation_authorized"] is True
    assert role["role_name"] == ROLE_NAME
    assert role["role_arn"] == ROLE_ARN
    assert role["allowed_s3_actions_only"] == ["s3:GetObject"]
    assert role["allowed_object_count"] == 6
    assert role["explicit_deny_getobject_outside_allowlist_required"] is True
    assert role["explicit_deny_other_s3_reads_required"] is True
    assert role["explicit_deny_s3_mutation_required"] is True
    assert role["operator_attestation_required"] is True
    assert role["separate_sts_only_preflight_required"] is True
    assert role["s3_access_authorized_during_sts_preflight"] is False

    processing = approval["approved_future_processing"]
    assert processing["decompression"] is True
    assert processing["selected_fill_field_processing"] is True
    assert processing["selected_fill_fields"] == ["coin","side","time","px","sz","closedPnl","tid","crossed","liquidation"]
    assert processing["exact_decimal_arithmetic_required"] is True
    assert processing["floating_point_aggregation_authorized"] is False
    assert processing["cross_object_wallet_aggregation"] is True
    assert processing["active_hour_count_retention"] is True
    assert processing["blind_duplicate_deduplication_authorized"] is False

    assert approval["execution_authorized_by_this_approval"] is False
    assert approval["separate_execution_release_required"] is True
    assert approval["separate_canonical_activation_required"] is True
    assert all(value is False for value in approval["current_runtime_authority"].values())
    assert all(value is False for value in approval["downstream_authorizations"].values())
    assert all(value is False for value in approval["trading_authorizations"].values())

    assert "OWNER_APPROVED_IMPLEMENTATION_AND_DEDICATED_ROLE_CREATION_NO_EXECUTION" in status
    assert APPROVAL_SHA in status
    assert "current STS/OIDC authority: `NONE`" in status
    assert "current Requester Pays / GetObject authority: `NONE`" in status

    print("R10_APPROVAL_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
