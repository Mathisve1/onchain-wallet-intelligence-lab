from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.archive_inventory.r10_implementation import collector

R10 = ROOT / "research/archive_inventory/r10"
APPROVAL = ROOT / "research/archive_inventory/r10_approval"
IMPL = ROOT / "research/archive_inventory/r10_implementation"
CONTRACT = IMPL / "R10_IMPLEMENTATION_CONTRACT.json"
TRUST = IMPL / "R10_OIDC_TRUST_POLICY.json"
PERMISSION = IMPL / "R10_PERMISSION_POLICY.json"
RUNBOOK = IMPL / "R10_ROLE_CREATION_RUNBOOK.md"
ATTESTATION_TEMPLATE = IMPL / "R10_OPERATOR_ATTESTATION_TEMPLATE.txt"
PREFLIGHT_CANDIDATE = IMPL / "workflows/hyperliquid-archive-post-boundary-multihour-role-preflight-r10.yml"
DATA_CANDIDATE = IMPL / "workflows/hyperliquid-archive-post-boundary-multihour-feature-r10.yml"
PREFLIGHT_INSTALLED = ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-role-preflight-r10.yml"
DATA_INSTALLED = ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-feature-r10.yml"
APPROVAL_JSON = APPROVAL / "APPROVE_HL_ARCHIVE_POST_BOUNDARY_MULTI_HOUR_FEATURE_R10_001.json"
APPROVAL_TXT = APPROVAL / "APPROVE_HL_ARCHIVE_POST_BOUNDARY_MULTI_HOUR_FEATURE_R10_001.txt"

PREREG_MERGE = "37e4486a7f68982feafcb361bd40dffd546def05"
APPROVAL_MERGE = "92761986d8dc6bf818eebf7dc0411d24649a27df"
APPROVAL_SHA = "ec631e7e6d40cb63383afd012a989419f97cd603ff144e4c5dfb90c18ff90882"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
WORKFLOW_NAME = "Hyperliquid Archive Post-Boundary Multi-Hour Feature Pilot R10"
SUBJECT = "repo:Mathisve1@163474992/onchain-wallet-intelligence-lab@1326362646:ref:refs/heads/main"
OBJECT_ARNS = [f"arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250727/{hour}.lz4" for hour in range(9, 15)]


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_workflow_candidate(path: Path) -> str:
    assert path.is_file(), path
    text = path.read_text(encoding="utf-8")
    assert text.startswith(f"name: {WORKFLOW_NAME}\n")
    assert "workflow_dispatch:" in text
    assert "id-token: write" in text
    assert "actions/checkout@11d5960a326750d5838078e36cf38b85af677262" in text
    assert "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065" in text
    assert "aws-actions/configure-aws-credentials@e6de054238d6b7531b4efff3b6587d9aade6a06c" in text
    assert "persist-credentials: false" in text
    assert "role-duration-seconds: 900" in text
    assert text.index("test -f") < text.index("aws-actions/configure-aws-credentials")
    return text


def main() -> int:
    impl = load(CONTRACT)
    approval = load(APPROVAL_JSON)
    prereg = load(R10 / "POST_BOUNDARY_MULTI_HOUR_FEATURE_R10_CONTRACT.json")
    trust = load(TRUST)
    permission = load(PERMISSION)

    assert prereg["status"] == "PREREGISTERED_NO_EXECUTION"
    assert prereg["network_requests_executed_by_r10_preregistration"] == 0
    assert approval["reviewed_commit"] == PREREG_MERGE
    assert approval["exact_approval_text_sha256"] == APPROVAL_SHA
    assert sha(APPROVAL_TXT) == APPROVAL_SHA
    assert approval["execution_authorized_by_this_approval"] is False
    role_approval = approval["dedicated_role_authorization"]
    assert role_approval["new_dedicated_r10_role_creation_authorized"] is True
    assert role_approval["existing_r4_role_reuse_authorized"] is False
    assert role_approval["existing_r4_role_mutation_authorized"] is False

    assert impl["status"] == "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION"
    assert impl["r10_preregistration_merge_commit"] == PREREG_MERGE
    assert impl["r10_approval_merge_commit"] == APPROVAL_MERGE
    assert impl["approval_text_sha256"] == APPROVAL_SHA
    assert impl["expected_canonical_implementation_commit"] == "PENDING_CANONICAL_IMPLEMENTATION_MERGE"
    assert impl["dedicated_role_arn"] == ROLE_ARN
    assert impl["workflow_oidc_name"] == WORKFLOW_NAME
    assert impl["role_creation_authorized_by_owner"] is True
    for key in ("role_creation_performed", "role_attestation_present", "sts_preflight_release_present", "sts_preflight_completed", "execution_release_present", "canonical_activation_present"):
        assert impl[key] is False, key
    assert impl["s3_requests_executed"] == 0
    assert impl["aws_iam_mutations_executed"] == 0
    assert impl["aws_sts_requests_executed"] == 0
    assert impl["wallet_feature_rows_created"] == 0
    assert impl["empirical_result"] is None
    assert all(v is False for v in impl["current_runtime_authority"].values())
    assert all(v is False for v in impl["downstream_authorizations"].values())
    assert all(v is False for v in impl["trading_authorizations"].values())
    assert all(v is False for v in impl["forbidden_retention_authorizations"].values())
    assert all(v is False for v in impl["semantic_boundaries"].values())

    assert len(impl["exact_network_targets"]) == 6
    assert len(approval["approved_future_objects"]) == 6
    assert len(prereg["exact_future_network_targets"]) == 6
    assert sum(row["expected_size_bytes"] for row in impl["exact_network_targets"]) == 120999698
    assert max(row["expected_size_bytes"] for row in impl["exact_network_targets"]) == 21672141
    env = impl["execution_envelope"]
    assert env["maximum_get_object_requests"] == 6
    assert env["maximum_requests_per_object"] == 1
    assert env["maximum_retries_per_request"] == 0
    assert env["maximum_total_compressed_bytes"] == 120999698
    assert env["stop_after_first_failed_or_mismatched_object"] is True
    parse = impl["parse_and_aggregation"]
    assert parse["duplicate_wallet_tid_count_required_for_clean_success"] == 0
    assert parse["blind_duplicate_deduplication_authorized"] is False
    assert parse["fill_time_must_fall_within_source_path_hour_utc"] is True
    assert parse["exact_decimal_arithmetic_required"] is True
    assert parse["floating_point_aggregation_authorized"] is False
    assert impl["wallet_feature_output"]["fields_only"] == collector.OUTPUT_FIELDS

    statements = trust["Statement"]
    assert len(statements) == 1
    statement = statements[0]
    assert statement["Effect"] == "Allow"
    assert statement["Action"] == "sts:AssumeRoleWithWebIdentity"
    assert statement["Principal"]["Federated"] == "arn:aws:iam::630956766927:oidc-provider/token.actions.githubusercontent.com"
    assert statement["Condition"]["StringEquals"] == {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
        "token.actions.githubusercontent.com:sub": SUBJECT,
        "token.actions.githubusercontent.com:repository_id": "1326362646",
        "token.actions.githubusercontent.com:repository_owner_id": "163474992",
        "token.actions.githubusercontent.com:ref": "refs/heads/main",
        "token.actions.githubusercontent.com:workflow": WORKFLOW_NAME,
    }

    by_sid = {row["Sid"]: row for row in permission["Statement"]}
    assert by_sid["AllowExactSixR10ObjectsOnly"] == {
        "Sid": "AllowExactSixR10ObjectsOnly", "Effect": "Allow", "Action": "s3:GetObject", "Resource": OBJECT_ARNS
    }
    assert by_sid["DenyGetObjectOutsideExactSixR10Objects"]["Effect"] == "Deny"
    assert by_sid["DenyGetObjectOutsideExactSixR10Objects"]["Action"] == "s3:GetObject"
    assert by_sid["DenyGetObjectOutsideExactSixR10Objects"]["NotResource"] == OBJECT_ARNS
    assert set(by_sid["DenyOtherS3ReadCapabilities"]["Action"]) == {
        "s3:GetObjectVersion", "s3:GetObjectAttributes", "s3:SelectObjectContent",
        "s3:ListBucket", "s3:ListBucketVersions", "s3:ListAllMyBuckets",
    }
    assert by_sid["DenyOtherS3ReadCapabilities"]["Effect"] == "Deny"
    assert by_sid["DenyS3MutationAndRestore"]["Effect"] == "Deny"

    runbook = RUNBOOK.read_text(encoding="utf-8")
    attestation = ATTESTATION_TEMPLATE.read_text(encoding="utf-8")
    assert "If and only if AWS reports that the role does not exist" in runbook
    assert "--max-session-duration 3600" in runbook
    assert "IAM role `MaxSessionDuration`: `3600` seconds" in runbook
    assert "intended GitHub Actions assumed-role session duration: `900` seconds" in runbook
    assert "Do **not** run `aws s3`, `aws s3api`" in runbook
    assert "separate STS-only preflight release" in runbook
    assert "ATTEST_R10_DEDICATED_ROLE_CREATED_EXACTLY" in attestation
    assert "role_max_session_duration_seconds=3600" in attestation
    assert "future_workflow_role_duration_seconds=900" in attestation
    assert "existing_r4_role_modified=false" in attestation
    assert "s3_requests_executed_during_role_creation=0" in attestation

    preflight_text = validate_workflow_candidate(PREFLIGHT_CANDIDATE)
    data_text = validate_workflow_candidate(DATA_CANDIDATE)
    assert '"Effect":"Deny","Action":"s3:*","Resource":"*"' in preflight_text
    assert "aws sts get-caller-identity --output json" in preflight_text
    assert "aws s3" not in preflight_text
    for arn in OBJECT_ARNS:
        assert arn in data_text
    assert "R10_EXECUTION_RELEASE_CANONICALIZATION.json" in data_text
    assert "R10_DEDICATED_ROLE_OPERATOR_ATTESTATION.json" in data_text
    assert "R10_STS_PREFLIGHT_ATTESTATION.json" in data_text

    assert not PREFLIGHT_INSTALLED.exists()
    assert not DATA_INSTALLED.exists()
    assert not (ROOT / "research/archive_inventory/r10_role_attestation").exists()
    assert not (ROOT / "research/archive_inventory/r10_runtime").exists()
    collector.validate_static_inputs()

    print("R10_IMPLEMENTATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
