#!/usr/bin/env python3
from __future__ import annotations

from r11a_stage_common_r4 import (
    CORRECTIVE,
    ROLE_ARN,
    ROLE_DIR,
    implementation,
    load,
    require,
    require_all_false,
    require_sha256,
    sha256,
)

ATTESTATION = ROLE_DIR / "R11A_SUCCESSOR_ROLE_OPERATOR_ATTESTATION.json"
TRUST = CORRECTIVE / "R11A_OIDC_TRUST_POLICY.json"
PERMISSION = CORRECTIVE / "R11A_PERMISSION_POLICY.json"


def main() -> int:
    implementation()
    attestation = load(ATTESTATION)
    require(
        attestation["attestation_id"] == "ATTEST_HL_ARCHIVE_R11A_SUCCESSOR_ROLE_001",
        "role attestation ID drift",
    )
    require(
        attestation["status"] == "ROLE_CREATED_POLICIES_APPLIED_AWAITING_STS_PREFLIGHT",
        "role attestation status drift",
    )
    require(attestation["role_arn"] == ROLE_ARN, "successor role ARN drift")
    require(
        attestation["role_max_session_duration_seconds"] == 21600,
        "role max session duration drift",
    )
    require(
        attestation["persistent_permission_resource_count"] == 72,
        "persistent permission resource count drift",
    )
    require(
        attestation["persistent_permission_resources_match_exact_selection"] is True,
        "persistent policy differs from exact selection",
    )
    require(
        attestation["additional_managed_policies_attached"] is False,
        "managed policy attached",
    )
    require(
        attestation["additional_inline_policies_attached"] is False,
        "additional inline policy attached",
    )
    require(attestation["existing_r11_role_mutated"] is False, "consumed R11 role mutated")
    require(attestation["existing_r11_role_reused"] is False, "consumed R11 role reused")
    require_sha256(attestation["trust_policy_sha256"], "trust_policy_sha256")
    require_sha256(attestation["permission_policy_sha256"], "permission_policy_sha256")
    require(
        attestation["trust_policy_sha256"] == sha256(TRUST),
        "installed trust policy hash drift",
    )
    require(
        attestation["permission_policy_sha256"] == sha256(PERMISSION),
        "installed permission policy hash drift",
    )
    require(
        attestation["s3_requests_performed_during_operator_step"] == 0,
        "operator role step performed S3 request",
    )
    require(
        attestation["object_bytes_downloaded_during_operator_step"] == 0,
        "operator role step downloaded object bytes",
    )
    require(
        attestation["sts_only_preflight_required"] is True,
        "STS preflight requirement missing",
    )
    require(
        attestation["sts_only_preflight_completed"] is False,
        "historical role snapshot rewritten after preflight",
    )
    require_all_false(
        attestation["downstream_authorizations"], "role-attestation downstream authority"
    )
    require_all_false(
        attestation["trading_authorizations"], "role-attestation trading authority"
    )
    print("R11A_SUCCESSOR_ROLE_ATTESTATION_R4_VALID_AWAITING_STS_PREFLIGHT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
