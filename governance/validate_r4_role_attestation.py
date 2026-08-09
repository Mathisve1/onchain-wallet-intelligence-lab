from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r4"
TEXT = BASE / "role_attestation/R4_DEDICATED_ROLE_OPERATOR_ATTESTATION.txt"
ATTESTATION = BASE / "role_attestation/R4_DEDICATED_ROLE_OPERATOR_ATTESTATION.json"
TRUST = BASE / "R4_OIDC_TRUST_POLICY_TEMPLATE.json"
PERMISSION = BASE / "R4_IAM_POLICY_TEMPLATE.json"
RELEASE = BASE / "R4_EXECUTION_RELEASE.json"
ACTIVATION = BASE / "R4_EXECUTION_RELEASE_CANONICALIZATION.json"

EXPECTED_TEXT_SHA = "5af72489211b1ad79e35f0491502e34d518df7c14ae6f2f8d56fbd2c3a5a83c2"
EXPECTED_TRUST_SHA = "2ebb60a7747a636a475a23016951265fe377fd9d68f2d9f3a63e33f3bc0189b4"
EXPECTED_PERMISSION_SHA = "14d055105b80e0c41462d4934bbaa8d860b0aeda9f2f1b9529267fd0d4d3613d"
EXPECTED_ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    a = load(ATTESTATION)
    release = load(RELEASE)

    assert sha256(TEXT) == EXPECTED_TEXT_SHA
    assert sha256(TRUST) == EXPECTED_TRUST_SHA
    assert sha256(PERMISSION) == EXPECTED_PERMISSION_SHA
    assert a["attestation_id"] == "R4_DEDICATED_ROLE_OPERATOR_ATTESTATION"
    assert a["recorded_against_main_commit"] == "01521d1cad209263a217dbcca98ecd74ec16857c"
    assert a["release_candidate_merge_commit"] == "01521d1cad209263a217dbcca98ecd74ec16857c"
    assert a["implementation_commit"] == "180c89ead78f9a6f4560a1ec12575658e62586ee"
    assert a["exact_attestation_text_sha256"] == EXPECTED_TEXT_SHA
    assert a["role_arn"] == EXPECTED_ROLE_ARN
    assert a["trust_policy_sha256"] == EXPECTED_TRUST_SHA
    assert a["permission_policy_sha256"] == EXPECTED_PERMISSION_SHA
    assert a["role_created_and_policies_applied"] is True
    assert a["existing_metadata_role_modified"] is False
    assert a["operator_attested"] is True
    assert a["independently_verified"] is False
    assert a["sts_only_preflight_required"] is True
    assert a["sts_only_preflight_completed"] is False
    assert a["preflight_s3_requests_authorized"] is False
    assert a["preflight_object_body_download_authorized"] is False
    assert a["preflight_decompression_authorized"] is False
    assert a["r4_execution_activation_authorized_by_this_attestation"] is False
    assert a["r4_execution_ready"] is False
    assert a["s3_requests_executed_by_this_attestation"] == 0
    assert a["compressed_bytes_downloaded_by_this_attestation"] == 0
    assert a["empirical_result"] is None

    assert release["dedicated_r4_role_operator_attested"] is False, "immutable release candidate must stay inert"
    assert release["dedicated_r4_role_independently_verified"] is False
    assert release["single_workflow_dispatch_authorized"] is False
    assert release["get_object_authorized"] is False
    assert release["execution_ready"] is False

    if ACTIVATION.exists():
        activation = load(ACTIVATION)
        assert activation["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R4_RUN"
        assert activation["release_candidate_immutable"] is True
        assert activation["role_attestation_merge_commit"] == "c45527941dea7d152e332327ebd0593dc2413bea"
        assert activation["operator_attestation_text_sha256"] == EXPECTED_TEXT_SHA
        assert activation["dedicated_r4_role_arn"] == EXPECTED_ROLE_ARN
        assert activation["dedicated_r4_role_operator_attested"] is True
        assert activation["dedicated_r4_role_independently_verified"] is True
        assert activation["preflight_evidence_merge_commit"] == "a91f0849e8cf14b6924da73ca2b72595deab5d8d"
        assert activation["preflight_run_id"] == 31312067367
        assert activation["preflight_s3_requests_executed"] == 0
        assert activation["rerun_authorized"] is False

    print("R4_ROLE_OPERATOR_ATTESTATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
