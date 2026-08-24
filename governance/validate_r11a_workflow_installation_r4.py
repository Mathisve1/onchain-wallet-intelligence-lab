#!/usr/bin/env python3
from __future__ import annotations

from r11a_stage_common_r4 import (
    CANDIDATE_PATH,
    INSTALL_DIR,
    WORKFLOW_NAME,
    WORKFLOW_PATH,
    implementation,
    load,
    require,
    require_all_false,
    sha256,
)
from validate_r11a_approval_r4 import main as validate_approval
from validate_r11a_role_preflight_evidence_r4 import main as validate_preflight

CONTRACT = INSTALL_DIR / "R11A_WORKFLOW_INSTALLATION_CONTRACT.json"


def main() -> int:
    impl = implementation()
    validate_approval()
    validate_preflight()
    contract = load(CONTRACT)
    require(
        contract["installation_id"] == "HL-ARCHIVE-R11A-WORKFLOW-INSTALLATION-001",
        "installation ID drift",
    )
    require(
        contract["status"] == "INSTALLED_AWAITING_SEPARATE_EXECUTION_RELEASE",
        "installation status drift",
    )
    require(contract["workflow_name"] == WORKFLOW_NAME, "workflow name drift")
    require(
        contract["workflow_path"]
        == ".github/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic.yml",
        "installed workflow path drift",
    )
    require(CANDIDATE_PATH.is_file(), "frozen workflow candidate is absent")
    require(WORKFLOW_PATH.is_file(), "installed workflow is absent")
    require(
        CANDIDATE_PATH.read_bytes() == WORKFLOW_PATH.read_bytes(),
        "installed workflow differs from frozen candidate",
    )
    require(
        contract["workflow_sha256"] == sha256(WORKFLOW_PATH),
        "installed workflow SHA-256 drift",
    )
    require(
        contract["workflow_sha256"] == impl["workflow_candidate_sha256"],
        "installed workflow is not implementation-bound",
    )
    require(
        contract["single_workflow_dispatch_authorized"] is False,
        "installation self-authorizes dispatch",
    )
    require(
        contract["execution_release_present"] is False,
        "historical installation snapshot rewritten after release",
    )
    require(
        contract["canonical_activation_present"] is False,
        "historical installation snapshot rewritten after activation",
    )
    require(contract["aws_oidc_authorized_now"] is False, "installation opens OIDC")
    require(contract["get_object_authorized_now"] is False, "installation opens GetObject")
    require(
        contract["network_requests_executed_by_installation"] == 0,
        "installation performed network request",
    )
    require(
        contract["aws_iam_mutations_executed_by_installation"] == 0,
        "installation mutated IAM",
    )
    require_all_false(
        contract["downstream_authorizations"], "installation downstream authority"
    )
    require_all_false(contract["trading_authorizations"], "installation trading authority")
    print("R11A_WORKFLOW_INSTALLATION_R4_VALID_INERT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
