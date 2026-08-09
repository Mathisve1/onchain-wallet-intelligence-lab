from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r4"
PREREG = BASE / "HOURLY_BODY_SCHEMA_PILOT_R4_CONTRACT.json"
APPROVAL = BASE / "approvals/APPROVE_HL_ARCHIVE_HOURLY_BODY_SCHEMA_PILOT_R4_001.json"
APPROVAL_TEXT = BASE / "approvals/APPROVE_HL_ARCHIVE_HOURLY_BODY_SCHEMA_PILOT_R4_001.txt"
IMPLEMENTATION = BASE / "R4_IMPLEMENTATION_CONTRACT.json"
COLLECTOR = BASE / "collector.py"
LZ4 = BASE / "lz4_frame.py"
TRUST = BASE / "R4_OIDC_TRUST_POLICY_TEMPLATE.json"
PERMISSION = BASE / "R4_IAM_POLICY_TEMPLATE.json"
PARENT_IAM = ROOT / "research/archive_inventory/IAM_POLICY_TEMPLATE.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-hourly-body-schema-pilot-r4.yml"
RELEASE = BASE / "R4_EXECUTION_RELEASE.json"
ACTIVATION = BASE / "R4_EXECUTION_RELEASE_CANONICALIZATION.json"

PREREG_COMMIT = "25a1f621d15cb708a485893025f03b991628aae1"
APPROVAL_MERGE_COMMIT = "0191350683c6c943d3538c8c51db176cd1d58211"
APPROVAL_SHA = "e52399feb7a0d36959089f556dd9f55062eb91d52feaa4c5af680d3c4e557264"
PENDING = "PENDING_CANONICAL_IMPLEMENTATION_MERGE"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"
OBJECT_ARNS = [
    "arn:aws:s3:::hl-mainnet-node-data/node_fills/hourly/20250727/8.lz4",
    "arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250727/8.lz4",
]
OBJECT_KEYS = [
    "node_fills/hourly/20250727/8.lz4",
    "node_fills_by_block/hourly/20250727/8.lz4",
]
IMMUTABLE_SUBJECT = "repo:Mathisve1@163474992/onchain-wallet-intelligence-lab@1326362646:ref:refs/heads/main"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def imported_roots(source: str) -> set[str]:
    tree = ast.parse(source)
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def main() -> int:
    prereg = load(PREREG)
    approval = load(APPROVAL)
    impl = load(IMPLEMENTATION)
    trust = load(TRUST)
    permission = load(PERMISSION)
    parent_iam = load(PARENT_IAM)
    collector = COLLECTOR.read_text(encoding="utf-8")
    lz4 = LZ4.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest() == APPROVAL_SHA
    assert prereg["pilot_id"] == "HL-ARCHIVE-HOURLY-BODY-SCHEMA-PILOT-R4-001"
    assert approval["approval_id"] == "APPROVE_HL_ARCHIVE_HOURLY_BODY_SCHEMA_PILOT_R4_001"
    assert approval["reviewed_commit"] == PREREG_COMMIT
    assert approval["exact_approval_text_sha256"] == APPROVAL_SHA
    assert impl["preregistration_commit"] == PREREG_COMMIT
    assert impl["approval_merge_commit"] == APPROVAL_MERGE_COMMIT
    assert impl["approval_text_sha256"] == APPROVAL_SHA
    assert impl["status"] == "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION"

    assert [row["key"] for row in impl["selected_objects"]] == OBJECT_KEYS
    assert [row["expected_size_bytes"] for row in impl["selected_objects"]] == [12726384, 1517603]
    assert [row["expected_etag"] for row in impl["selected_objects"]] == [
        '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"',
        '"60d4c1277f76651b5f04666bbe8d7594"',
    ]
    assert impl["target_bucket"] == "hl-mainnet-node-data"
    assert impl["signing_region"] == "ap-northeast-1"
    assert impl["regional_virtual_hosted_endpoint"] == "hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com"
    assert impl["maximum_get_object_requests"] == 2
    assert impl["maximum_requests_per_object"] == 1
    assert impl["maximum_total_compressed_bytes"] == 14243987
    assert impl["maximum_total_decompressed_bytes"] == 536870912
    assert impl["maximum_decompressed_bytes_per_object"] == 268435456
    assert impl["maximum_runtime_seconds"] == 180
    assert impl["maximum_retries_per_request"] == 0
    assert impl["maximum_record_bytes"] == 16777216
    assert impl["maximum_records_parsed_per_object"] == 5000000
    assert impl["maximum_schema_nesting_depth"] == 16
    assert impl["maximum_unique_field_paths"] == 4096
    assert impl["request_counter_incremented_before_transport"] is True
    assert impl["require_if_match_etag"] is True
    assert impl["require_exact_content_length"] is True
    assert impl["require_response_etag_match"] is True
    assert impl["require_request_charged_requester_on_success"] is True
    assert impl["http_redirect_following_authorized"] is False
    assert impl["head_object_authorized"] is False
    assert impl["range_get_authorized"] is False
    assert impl["list_objects_v2_authorized"] is False
    assert impl["list_object_versions_authorized"] is False
    assert impl["list_all_my_buckets_authorized"] is False
    assert impl["raw_compressed_object_persisted"] is False
    assert impl["raw_decompressed_payload_retention_authorized"] is False
    assert impl["record_payload_retention_authorized"] is False
    assert impl["wallet_address_retention_from_body_authorized"] is False
    assert impl["payload_values_in_schema_evidence_authorized"] is False
    assert impl["semantic_equivalence_inference_authorized"] is False
    assert impl["wallet_reconstruction_authorized"] is False
    assert impl["entity_clustering_authorized"] is False
    assert impl["copyability_analysis_authorized"] is False
    assert impl["pnl_or_alpha_analysis_authorized"] is False
    assert impl["market_data_ingestion_authorized"] is False
    assert impl["maximum_one_time_budget_eur"] == 0.10
    assert impl["maximum_monthly_budget_eur"] == 0
    assert impl["current_metadata_role_usable_for_r4"] is False
    assert impl["dedicated_r4_role_required"] is True
    assert impl["expected_dedicated_r4_role_arn"] == ROLE_ARN
    assert impl["dedicated_r4_role_currently_verified"] is False
    assert impl["session_s3_policy"] == "ALLOW_GETOBJECT_EXACT_TWO_BOUNDARY_OBJECTS_ONLY"
    assert impl["execution_release_required"] is True
    assert impl["execution_release_present"] is False
    assert impl["expected_canonical_implementation_commit"] == PENDING
    for key in (
        "execution_authorized", "paid_request_authorized", "requester_pays_authorized",
        "get_object_authorized", "object_body_download_authorized", "decompression_authorized",
    ):
        assert impl[key] is False, key
    assert all(value is False for value in impl["trading_authorizations"].values())
    assert impl["s3_requests_executed"] == 0
    assert impl["compressed_bytes_downloaded"] == 0
    assert impl["decompressed_bytes_processed"] == 0
    assert impl["empirical_result"] is None

    parent_denied: set[str] = set()
    for statement in parent_iam["Statement"]:
        actions = statement["Action"] if isinstance(statement["Action"], list) else [statement["Action"]]
        if statement["Effect"] == "Deny":
            parent_denied.update(actions)
    assert "s3:GetObject" in parent_denied

    trust_statement = trust["Statement"][0]
    assert trust_statement["Effect"] == "Allow"
    assert trust_statement["Action"] == "sts:AssumeRoleWithWebIdentity"
    assert trust_statement["Principal"]["Federated"] == "arn:aws:iam::630956766927:oidc-provider/token.actions.githubusercontent.com"
    assert trust_statement["Condition"]["StringEquals"] == {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
        "token.actions.githubusercontent.com:sub": IMMUTABLE_SUBJECT,
        "token.actions.githubusercontent.com:repository_id": "1326362646",
        "token.actions.githubusercontent.com:repository_owner_id": "163474992",
        "token.actions.githubusercontent.com:ref": "refs/heads/main",
        "token.actions.githubusercontent.com:workflow": "Hyperliquid Archive Hourly Body Schema Pilot R4",
    }

    by_sid = {row["Sid"]: row for row in permission["Statement"]}
    allow = by_sid["AllowExactTwoBoundaryObjectsOnly"]
    assert allow["Effect"] == "Allow"
    assert allow["Action"] == "s3:GetObject"
    assert allow["Resource"] == OBJECT_ARNS
    outside = by_sid["DenyGetObjectOutsideExactTwo"]
    assert outside["Effect"] == "Deny"
    assert outside["Action"] == "s3:GetObject"
    assert outside["NotResource"] == OBJECT_ARNS
    serialized_permission = json.dumps(permission, sort_keys=True)
    assert "s3:ListBucket" in serialized_permission
    assert not any(
        row["Effect"] == "Allow" and row["Action"] != "s3:GetObject"
        for row in permission["Statement"]
    )

    banned = {"boto3", "botocore", "requests", "urllib3", "subprocess"}
    assert not imported_roots(collector).intersection(banned)
    assert not imported_roots(lz4).intersection(banned)
    assert "http.client.HTTPSConnection" in collector
    assert "response.read(expected_size + 1)" in collector
    assert "attempts += 1" in collector
    assert collector.index("attempts += 1") < collector.index("transport(host, path, headers")
    assert '"If-Match"' in collector
    assert "x-amz-request-payer" in collector
    assert "Range" not in collector
    assert "LZ4_FRAME_STREAM_ONLY" in json.dumps(impl)
    assert "alternate_decompressor_fallback_authorized" in json.dumps(impl)
    assert "import subprocess" not in collector + lz4
    assert "SCHEMA_UNRESOLVED" in collector
    assert "R4_BODY_SCHEMA_PILOT_COMPLETE" in collector

    assert "workflow_dispatch:" in workflow
    assert "pull_request:" not in workflow
    assert "push:" not in workflow
    assert "persist-credentials: false" in workflow
    assert "EVENT_NAME: ${{ github.event_name }}" in workflow
    assert "DISPATCH_REF: ${{ github.ref }}" in workflow
    assert "DISPATCH_SHA: ${{ github.sha }}" in workflow
    assert "refs/heads/main" in workflow
    assert f"R4_ROLE_ARN: {ROLE_ARN}" in workflow
    assert "EXPECTED_IMPLEMENTATION_COMMIT: PENDING_CANONICAL_IMPLEMENTATION_MERGE" in workflow or "EXPECTED_IMPLEMENTATION_COMMIT:" in workflow
    assert "R4_EXECUTION_RELEASE_CANONICALIZATION.json" in workflow
    assert '"Action":"s3:GetObject"' in workflow
    for arn in OBJECT_ARNS:
        assert arn in workflow
    for forbidden in (
        "s3:ListBucket", "s3:GetObjectVersion", "s3:GetObjectAttributes",
        "s3:ListBucketVersions", "s3:ListAllMyBuckets",
    ):
        assert forbidden not in workflow
    assert workflow.index("Prove canonical R4 implementation and release before AWS OIDC") < workflow.index("Assume dedicated R4 AWS role with exact-two-object session permissions")

    if RELEASE.exists():
        release = load(RELEASE)
        assert release["preregistration_commit"] == PREREG_COMMIT
        assert release["approval_merge_commit"] == APPROVAL_MERGE_COMMIT
        assert release["approval_text_sha256"] == APPROVAL_SHA
    if ACTIVATION.exists():
        activation = load(ACTIVATION)
        assert activation["preregistration_commit"] == PREREG_COMMIT
        assert activation["approval_merge_commit"] == APPROVAL_MERGE_COMMIT
        assert activation["approval_text_sha256"] == APPROVAL_SHA

    print("R4_IMPLEMENTATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
