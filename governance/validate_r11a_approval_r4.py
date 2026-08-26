#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

try:
    from governance.r11a_stage_common_r4 import (
        APPROVAL_ID,
        APPROVAL_JSON_RELATIVE,
        APPROVAL_TEXT_RELATIVE,
        DIAGNOSTIC_ID,
        ROOT,
        implementation,
        load,
        require,
        successor_permissions,
        validate_alignment_context,
    )
except ModuleNotFoundError:
    from r11a_stage_common_r4 import (
        APPROVAL_ID,
        APPROVAL_JSON_RELATIVE,
        APPROVAL_TEXT_RELATIVE,
        DIAGNOSTIC_ID,
        ROOT,
        implementation,
        load,
        require,
        successor_permissions,
        validate_alignment_context,
    )

APPROVAL_JSON = ROOT / APPROVAL_JSON_RELATIVE
APPROVAL_TEXT = ROOT / APPROVAL_TEXT_RELATIVE


def validate(
    root: Path = ROOT,
    *,
    permitted_successor_paths: frozenset[str] = frozenset(),
    runtime_pricing_projection_permitted: bool = False,
) -> dict[str, object]:
    permitted = successor_permissions(permitted_successor_paths)
    validate_alignment_context(
        root,
        permitted_successor_paths=permitted,
        runtime_pricing_projection_permitted=runtime_pricing_projection_permitted,
    )
    implementation(root)
    approval = load(root, APPROVAL_JSON_RELATIVE)

    # The shared immutable-context validator enforces the complete 136-leaf
    # record.  These projections make the authority consumed by R4 explicit.
    require(approval["approval_id"] == APPROVAL_ID, "approval ID drift")
    require(approval["diagnostic_id"] == DIAGNOSTIC_ID, "approval diagnostic ID drift")
    require(
        approval["status"]
        == "OWNER_APPROVED_HASH_BOUND_FUTURE_STAGES_NO_CURRENT_RUNTIME",
        "approval status drift",
    )
    require(approval["owner_approval_present"] is True, "owner approval is absent")
    require(
        approval["canonical_approval_record_present"] is True,
        "canonical approval record is absent",
    )
    require(
        approval["execution_authorized_by_this_approval"] is False,
        "approval self-authorizes execution",
    )
    identity = approval["approved_future_identity"]
    diagnostic = approval["approved_future_diagnostic"]
    gates = approval["required_separate_future_gates"]
    require(
        identity["creation_and_configuration_authorized_only_in_separate_reviewed_stage"]
        is True,
        "separate identity gate missing",
    )
    require(identity["maximum_session_duration_seconds"] == 21600, "role duration drift")
    require(identity["persistent_get_object_resource_count"] == 72, "role resource count drift")
    require(diagnostic["maximum_runs_after_all_later_gates"] == 1, "run count drift")
    require(diagnostic["selected_object_count"] == 72, "approval object count drift")
    require(diagnostic["maximum_s3_get_object_requests"] == 72, "approval request cap drift")
    require(diagnostic["maximum_requests_per_object"] == 1, "approval per-object cap drift")
    require(diagnostic["maximum_retries_per_request"] == 0, "approval retry cap drift")
    require(diagnostic["maximum_runtime_seconds"] == 21600, "approval runtime cap drift")
    require(
        diagnostic["maximum_one_time_budget_eur_micros"] == 500000,
        "approval one-time budget drift",
    )
    require(
        diagnostic["maximum_monthly_budget_eur_micros"] == 0,
        "approval recurring budget drift",
    )
    require(gates["identity_creation_and_configuration_review"] is True, "identity gate missing")
    require(gates["operator_role_attestation"] is True, "role attestation gate missing")
    require(gates["sts_only_preflight_review"] is True, "STS preflight gate missing")
    require(gates["workflow_installation_review"] is True, "workflow installation gate missing")
    require(gates["execution_release_candidate_review"] is True, "release candidate gate missing")
    require(gates["runtime_binding_review"] is True, "runtime binding gate missing")
    require(gates["single_use_activation_review"] is True, "activation gate missing")
    require(gates["explicit_owner_dispatch"] is True, "owner dispatch gate missing")
    return approval


def main() -> int:
    validate()
    print("OWNER_APPROVAL_VALID_POST_G2_NO_CURRENT_RUNTIME")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
