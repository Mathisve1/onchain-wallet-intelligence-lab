#!/usr/bin/env python3
from __future__ import annotations

import re

from r11a_stage_common import (
    PREFLIGHT_DIR,
    ROLE_ARN,
    implementation,
    load,
    require,
    require_all_false,
    require_commit,
    require_sha256,
)
from validate_r11a_role_attestation import main as validate_role

EVIDENCE = PREFLIGHT_DIR / "R11A_SUCCESSOR_ROLE_STS_PREFLIGHT_ATTESTATION.json"
CONSUMPTION = PREFLIGHT_DIR / "R11A_STS_PREFLIGHT_RELEASE_CONSUMPTION.json"


def main() -> int:
    implementation()
    validate_role()
    evidence = load(EVIDENCE)
    consumption = load(CONSUMPTION)
    require(evidence["preflight_id"] == "HL-ARCHIVE-R11A-SUCCESSOR-ROLE-STS-PREFLIGHT-001", "preflight ID drift")
    require(evidence["status"] == "R11A_STS_PREFLIGHT_PASS", "preflight did not pass")
    require(evidence["technical_result"] == "DEDICATED_R11A_ROLE_ASSUMEABLE_FROM_CANONICAL_MAIN", "preflight technical result drift")
    require(evidence["expected_role_arn"] == ROLE_ARN, "expected role ARN drift")
    require(evidence["observed_account_id"] == "630956766927", "observed AWS account drift")
    require(
        re.fullmatch(
            r"arn:aws:sts::630956766927:assumed-role/onchain-wallet-intelligence-hl-archive-identity-r11a/HLArchiveR11ASTSPreflight",
            evidence["observed_assumed_role_session_arn"],
        )
        is not None,
        "observed STS principal drift",
    )
    require_commit(evidence["dispatch_sha"], "dispatch_sha")
    require(evidence["dispatch_ref"] == "refs/heads/main", "preflight was not canonical main")
    require(evidence["workflow_run_attempt"] == 1, "preflight rerun detected")
    require(evidence["explicit_sts_caller_identity_calls"] == 1, "preflight STS call count drift")
    require(evidence["s3_requests_authorized"] is False, "preflight authorized S3")
    require(evidence["s3_http_request_count"] == 0, "preflight performed S3 request")
    require(evidence["object_bytes_downloaded"] == 0, "preflight downloaded object bytes")
    require_sha256(evidence["artifact_sha256"], "artifact_sha256")
    require(consumption["status"] == "CONSUMED_SUCCESS", "preflight release was not consumed successfully")
    require(consumption["preflight_release_consumed"] is True, "preflight release consumption flag false")
    require(consumption["rerun_authorized"] is False, "preflight rerun reopened")
    require(consumption["s3_requests_executed"] == 0, "preflight consumption reports S3")
    require_all_false(evidence["downstream_authorizations"], "preflight downstream authority")
    require_all_false(evidence["trading_authorizations"], "preflight trading authority")
    print("R11A_STS_PREFLIGHT_EVIDENCE_VALID_ZERO_S3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
