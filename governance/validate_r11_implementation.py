from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
PREREG = BASE / "r11/R11_72H_PERSISTENCE_SCALING_PREREGISTRATION.json"
SELECTION = BASE / "r11/R11_72H_SELECTION.json"
APPROVAL = BASE / "r11_approval/APPROVE_HL_ARCHIVE_R11_72H_PERSISTENCE_SCALING_001.json"
APPROVAL_TEXT = BASE / "r11_approval/APPROVE_HL_ARCHIVE_R11_72H_PERSISTENCE_SCALING_001.txt"
IMPL = BASE / "r11_implementation/R11_IMPLEMENTATION_CONTRACT.json"
TRUST = BASE / "r11_implementation/R11_OIDC_TRUST_POLICY.json"
PERMISSION = BASE / "r11_implementation/R11_PERMISSION_POLICY.json"
COLLECTOR = BASE / "r11_implementation/collector.py"
PREFLIGHT = BASE / "r11_implementation/workflows/hyperliquid-archive-r11-role-preflight.yml"
DATA = BASE / "r11_implementation/workflows/hyperliquid-archive-r11-72h-persistence.yml"
RUNBOOK = BASE / "r11_implementation/R11_ROLE_CREATION_RUNBOOK.md"
ATTEST = BASE / "r11_implementation/R11_OPERATOR_ATTESTATION_TEMPLATE.txt"
INSTALLED_PREFLIGHT = ROOT / ".github/workflows/hyperliquid-archive-r11-role-preflight.yml"
INSTALLED_DATA = ROOT / ".github/workflows/hyperliquid-archive-r11-72h-persistence.yml"

PREREG_MERGE = "dc63f2846652e50755369aa95d0f01ec2e174b02"
APPROVAL_MERGE = "86333a6759a492e5452bc565802fefce55a9fd6f"
APPROVAL_SHA = "1c3ec861d5df30dbdeef4dece7422bc05fab50d59aa58aa36cf3b7f8fea0d3ca"
ROLE_NAME = "onchain-wallet-intelligence-hl-archive-scaling-r11"
ROLE_ARN = f"arn:aws:iam::630956766927:role/{ROLE_NAME}"
WORKFLOW_NAME = "Hyperliquid Archive 72H Persistence Scaling R11"
PREFIX_ARNS = [
    "arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250728/*",
    "arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250729/*",
    "arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250730/*",
]


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    p = load(PREREG)
    s = load(SELECTION)
    a = load(APPROVAL)
    i = load(IMPL)
    trust = load(TRUST)
    permission = load(PERMISSION)

    assert hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest() == APPROVAL_SHA
    assert p["pilot_id"] == a["pilot_id"] == i["pilot_id"] == "HL-ARCHIVE-R11-72H-PERSISTENCE-SCALING-001"
    assert p["status"] == "PREREGISTERED_NO_EXECUTION"
    assert a["reviewed_commit"] == PREREG_MERGE
    assert a["exact_approval_text_sha256"] == APPROVAL_SHA
    assert a["execution_authorized_by_this_approval"] is False
    assert i["status"] == "IMPLEMENTED_AWAITING_OPERATOR_ROLE_CREATION_AND_ATTESTATION"
    assert i["r11_preregistration_merge_commit"] == PREREG_MERGE
    assert i["r11_approval_merge_commit"] == APPROVAL_MERGE
    assert i["approval_text_sha256"] == APPROVAL_SHA
    assert i["parent_r10d_evidence_merge_commit"] == "0b13a80235ecd43bcd220985383f79f8ccbfb6ca"
    assert i["selected_hour_count"] == s["selected_hour_count"] == 72
    assert i["selection_sha256"] == p["selection_sha256"] == "7c134f4b62f547904126a5f810c177484dceeffa246d53c5c35944367d563eb2"

    env = i["execution_envelope"]
    assert env["maximum_one_time_budget_eur"] == 0.50
    assert env["maximum_monthly_budget_eur"] == 0
    assert env["maximum_get_object_requests"] == 72
    assert env["maximum_requests_per_object"] == 1
    assert env["maximum_retries_per_request"] == 0
    assert env["maximum_total_compressed_bytes"] == 2107738436
    assert env["maximum_individual_compressed_bytes"] == 76616104
    assert env["maximum_total_decompressed_bytes"] == 17179869184
    assert env["maximum_individual_decompressed_bytes"] == 536870912
    assert env["maximum_runtime_seconds"] == 5400
    assert env["request_order"] == "PATH_HOUR_ASCENDING"
    assert env["stop_after_first_failed_or_mismatched_object"] is True
    for key in ("head_object_authorized","range_get_authorized","list_objects_v2_authorized","list_object_versions_authorized","list_all_my_buckets_authorized","get_object_attributes_authorized","get_object_version_authorized","http_redirect_following_authorized"):
        assert env[key] is False, key

    rule = i["record_anchored_alignment_rule"]
    assert rule["rule_id"] == "RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1"
    assert rule["numeric_tolerance_authorized"] is False
    assert rule["local_time_raw_prefix_must_match_source_path_hour_for_every_record"] is True
    assert rule["block_time_raw_prefix_allowed_buckets"] == ["MATCHES_PATH_DATE_HOUR_PREFIX","MATCHES_PREVIOUS_DATE_HOUR_PREFIX"]
    assert rule["path_block_record_allowed_fill_partitions"] == ["INSIDE_PATH_HOUR"]
    assert rule["previous_block_record_allowed_fill_partitions"] == ["BEFORE_PATH_HOUR"]
    assert rule["previous_block_record_before_fill_must_be_within_immediately_previous_epoch_hour"] is True
    assert rule["after_path_hour_fill_count_required_for_success"] == 0

    role = i["dedicated_role"]
    assert role["role_name"] == ROLE_NAME and role["role_arn"] == ROLE_ARN
    assert role["role_max_session_duration_seconds"] == 7200
    assert role["future_workflow_role_duration_seconds"] == 7200
    assert role["persistent_permission_resource_count"] == 72
    assert role["persistent_permission_resources_are_exact_selection_objects"] is True
    assert role["existing_r10_role_reused"] is False and role["existing_r10_role_mutated"] is False
    assert role["role_created_by_implementation_pr"] is False
    assert role["operator_creation_required_after_canonical_merge"] is True
    assert role["operator_attestation_required"] is True
    assert role["separate_s3_denied_sts_preflight_required"] is True

    statement = trust["Statement"][0]
    equals = statement["Condition"]["StringEquals"]
    assert statement["Action"] == "sts:AssumeRoleWithWebIdentity"
    assert equals["token.actions.githubusercontent.com:aud"] == "sts.amazonaws.com"
    assert equals["token.actions.githubusercontent.com:ref"] == "refs/heads/main"
    assert equals["token.actions.githubusercontent.com:workflow"] == WORKFLOW_NAME
    assert equals["token.actions.githubusercontent.com:repository_id"] == "1326362646"
    assert equals["token.actions.githubusercontent.com:repository_owner_id"] == "163474992"

    exact_targets = s["exact_targets"]
    expected_resources = [f"arn:aws:s3:::hl-mainnet-node-data/{row['key']}" for row in exact_targets]
    allow = permission["Statement"][0]
    assert allow["Sid"] == "AllowExactSeventyTwoR11ObjectsOnly"
    assert allow["Effect"] == "Allow" and allow["Action"] == "s3:GetObject"
    assert allow["Resource"] == expected_resources
    assert len(expected_resources) == len(set(expected_resources)) == 72
    compact = json.dumps(permission, separators=(",", ":"), ensure_ascii=True)
    assert len(compact) <= 10240
    denied = {action for stmt in permission["Statement"][1:] for action in stmt["Action"]}
    for action in ("s3:GetObjectVersion","s3:GetObjectAttributes","s3:ListBucket","s3:PutObject","s3:DeleteObject","s3:RestoreObject"):
        assert action in denied

    collector = COLLECTOR.read_text(encoding="utf-8")
    assert "active_day_count" in collector
    assert "RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1" in collector
    assert "MAX_REQUESTS = 72" in collector
    assert "wallet_ranking_performed" in collector and "copyability_analysis_performed" in collector
    assert "datetime.fromisoformat" not in collector

    preflight = PREFLIGHT.read_text(encoding="utf-8")
    data = DATA.read_text(encoding="utf-8")
    for text in (preflight, data):
        assert text.startswith(f"name: {WORKFLOW_NAME}\n")
        assert "workflow_dispatch:" in text
        assert "schedule:" not in text and "push:" not in text
        assert "persist-credentials: false" in text
        assert f"role-to-assume: {ROLE_ARN}" in text
        assert "role-duration-seconds: 7200" in text
    assert '"Action":"s3:*"' in preflight and '"Effect":"Deny"' in preflight
    assert "aws sts get-caller-identity" in preflight
    assert "aws s3 " not in preflight.lower() and "aws s3api " not in preflight.lower()
    for arn in PREFIX_ARNS:
        assert arn in data
    assert "research.archive_inventory.r11_implementation.collector" in data
    assert "r11-wallet-features.ndjson" in data

    if INSTALLED_PREFLIGHT.exists():
        assert INSTALLED_PREFLIGHT.read_bytes() == PREFLIGHT.read_bytes()
    assert not INSTALLED_DATA.exists(), "R11 data workflow must remain uninstalled before STS preflight evidence"
    assert "aws s3 " not in RUNBOOK.read_text(encoding="utf-8").lower().replace("`aws s3`", "")
    attest = ATTEST.read_text(encoding="utf-8")
    assert "persistent_permission_resource_count=72" in attest
    assert "additional_managed_policies_attached=false" in attest
    assert "additional_inline_policies_attached=false" in attest
    assert "s3_requests_performed_during_operator_step=0" in attest

    assert all(v is False for v in i["current_runtime_authority"].values())
    assert all(v is False for v in i["downstream_authorizations"].values())
    assert all(v is False for v in i["trading_authorizations"].values())
    assert i["network_requests_executed_by_implementation"] == 0
    assert i["aws_iam_mutations_executed_by_implementation"] == 0
    assert i["wallet_feature_rows_created_by_implementation"] == 0
    assert i["execution_release_present"] is False and i["canonical_activation_present"] is False
    assert i["empirical_result"] is None

    print("R11_IMPLEMENTATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
