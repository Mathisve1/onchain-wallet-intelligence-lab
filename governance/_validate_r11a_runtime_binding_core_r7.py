#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from governance.r11a_stage_common_r4 import (
        ACTIVATION_RELATIVE,
        ALIGNMENT_ID,
        ALIGNMENT_RELATIVE,
        APPROVAL_ID,
        APPROVAL_JSON_RELATIVE,
        APPROVAL_TEXT_RELATIVE,
        ARTIFACT_VALIDATOR_RELATIVE,
        BINDING_RELATIVE,
        CANDIDATE_RELATIVE,
        DIAGNOSTIC_ID,
        DEPENDENCIES_RELATIVE,
        G1_APPROVAL_PACKAGE_RELATIVE,
        G1_ENVELOPE_RELATIVE,
        G1_PRICING_BINDING_RELATIVE,
        G1_SOURCE_STATEMENT_RELATIVE,
        IMPLEMENTATION_RELATIVE,
        INSTALLATION_RELATIVE,
        PERMISSION_POLICY_RELATIVE,
        PREFLIGHT_CANDIDATE_RELATIVE,
        PREFLIGHT_CONSUMPTION_RELATIVE,
        PREFLIGHT_EVIDENCE_RELATIVE,
        PREFLIGHT_RELEASE_RELATIVE,
        PRICING_SOURCE_RELATIVE,
        PRICING_TARGET_RELATIVE,
        PRIOR_RESULT_RELATIVE,
        RELEASE_CANDIDATE_RELATIVE,
        RELEASE_DIGEST_RELATIVE,
        RELEASE_RELATIVE,
        RELEASE_CONSUMPTION_RELATIVE,
        RESOURCE_FEASIBILITY_RELATIVE,
        REVIEW_EVIDENCE_PATHS,
        ROLE_ATTESTATION_RELATIVE,
        ROLE_CONFIGURATION_CANDIDATE_RELATIVE,
        ROLE_DECISION_RELATIVE,
        ROOT,
        RUNNER_RELATIVE,
        SELECTION_RELATIVE,
        TRUST_POLICY_RELATIVE,
        WORKFLOW_FILE,
        WORKFLOW_NAME,
        WORKFLOW_RELATIVE,
        load as stage_load,
        pricing_projection,
        read_bytes,
        require_commit as stage_require_commit,
        require_exact,
        require_gate_review,
        require_absent,
        require_sha256 as stage_require_sha256,
        sha256 as stage_sha256,
        stage_authority,
        successor_permissions,
        trading_authority,
    )
    from governance.validate_r11a_activation_r4 import validate as validate_activation
except ModuleNotFoundError:
    from r11a_stage_common_r4 import (
        ACTIVATION_RELATIVE,
        ALIGNMENT_ID,
        ALIGNMENT_RELATIVE,
        APPROVAL_ID,
        APPROVAL_JSON_RELATIVE,
        APPROVAL_TEXT_RELATIVE,
        ARTIFACT_VALIDATOR_RELATIVE,
        BINDING_RELATIVE,
        CANDIDATE_RELATIVE,
        DIAGNOSTIC_ID,
        DEPENDENCIES_RELATIVE,
        G1_APPROVAL_PACKAGE_RELATIVE,
        G1_ENVELOPE_RELATIVE,
        G1_PRICING_BINDING_RELATIVE,
        G1_SOURCE_STATEMENT_RELATIVE,
        IMPLEMENTATION_RELATIVE,
        INSTALLATION_RELATIVE,
        PERMISSION_POLICY_RELATIVE,
        PREFLIGHT_CANDIDATE_RELATIVE,
        PREFLIGHT_CONSUMPTION_RELATIVE,
        PREFLIGHT_EVIDENCE_RELATIVE,
        PREFLIGHT_RELEASE_RELATIVE,
        PRICING_SOURCE_RELATIVE,
        PRICING_TARGET_RELATIVE,
        PRIOR_RESULT_RELATIVE,
        RELEASE_CANDIDATE_RELATIVE,
        RELEASE_DIGEST_RELATIVE,
        RELEASE_RELATIVE,
        RELEASE_CONSUMPTION_RELATIVE,
        RESOURCE_FEASIBILITY_RELATIVE,
        REVIEW_EVIDENCE_PATHS,
        ROLE_ATTESTATION_RELATIVE,
        ROLE_CONFIGURATION_CANDIDATE_RELATIVE,
        ROLE_DECISION_RELATIVE,
        ROOT,
        RUNNER_RELATIVE,
        SELECTION_RELATIVE,
        TRUST_POLICY_RELATIVE,
        WORKFLOW_FILE,
        WORKFLOW_NAME,
        WORKFLOW_RELATIVE,
        load as stage_load,
        pricing_projection,
        read_bytes,
        require_commit as stage_require_commit,
        require_exact,
        require_gate_review,
        require_absent,
        require_sha256 as stage_require_sha256,
        sha256 as stage_sha256,
        stage_authority,
        successor_permissions,
        trading_authority,
    )
    from validate_r11a_activation_r4 import validate as validate_activation

IMPLEMENTATION_ID = "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-CORRECTIVE-R7"
BINDING = ROOT / BINDING_RELATIVE
ACTIVATION_REVIEW_GATE = "R11A_ACTIVATION_REVIEW"
RUNTIME_BINDING_REVIEW_GATE = "R11A_RUNTIME_BINDING_REVIEW"

# Runtime behavior plus every governance consumer whose result is relied upon
# by the binding.  The wrapper adds private R7 cores before validation.
TRANSITIVE_CODE_PATHS = (
    "research/__init__.py",
    "research/archive_inventory/r11a_corrective/__init__.py",
    "governance/r11a_post_approval_context.py",
    "governance/r11a_stage_common_r4.py",
    "governance/_validate_r11a_runtime_binding_core_r7.py",
    "governance/seal_r11a_corrective_r7.py",
    "governance/seal_r11a_v2_preregistration.py",
    "governance/validate_r11a_activation_r4.py",
    "governance/validate_r11a_approval_r4.py",
    "governance/validate_r11a_execution_release_r4.py",
    "governance/validate_r11a_g2_owner_approval.py",
    ARTIFACT_VALIDATOR_RELATIVE,
    "governance/validate_r11a_post_approval_validator_alignment.py",
    "governance/validate_r11a_role_attestation_r4.py",
    "governance/validate_r11a_role_preflight_evidence_r4.py",
    "governance/validate_r11a_runtime_binding_r7.py",
    "governance/validate_r11a_v2_bindings.py",
    "governance/validate_r11a_v2_preregistration.py",
    "governance/validate_r11a_workflow_installation_r4.py",
    "research/archive_inventory/r11a_corrective/_artifact_contract_core_r7.py",
    "research/archive_inventory/r11a_corrective/_artifact_core_r7.py",
    "research/archive_inventory/r11a_corrective/_artifact_schema_core_r7.py",
    "research/archive_inventory/r11a_corrective/_runner_core_r7.py",
    "research/archive_inventory/r11a_corrective/_taxonomy_contract_core_r7.py",
    "research/archive_inventory/r11a_corrective/_taxonomy_core_r7.py",
    "research/archive_inventory/r11a_corrective/artifact.py",
    "research/archive_inventory/r11a_corrective/artifact_schema.py",
    "research/archive_inventory/r11a_corrective/canonical.py",
    "research/archive_inventory/r11a_corrective/context.py",
    "research/archive_inventory/r11a_corrective/entrypoint.py",
    "research/archive_inventory/r11a_corrective/identity.py",
    "research/archive_inventory/r11a_corrective/index.py",
    "research/archive_inventory/r11a_corrective/join_r7.py",
    "research/archive_inventory/r11a_corrective/limits.py",
    "research/archive_inventory/r11a_corrective/locator_order.py",
    "research/archive_inventory/r11a_corrective/lz4stream.py",
    "research/archive_inventory/r11a_corrective/materialize.py",
    "research/archive_inventory/r11a_corrective/meter_r7.py",
    "research/archive_inventory/r11a_corrective/network.py",
    "research/archive_inventory/r11a_corrective/parser.py",
    "research/archive_inventory/r11a_corrective/preflight_artifact_r7.py",
    "research/archive_inventory/r11a_corrective/pricing.py",
    "research/archive_inventory/r11a_corrective/proof_semantics_r7.py",
    RUNNER_RELATIVE,
    "research/archive_inventory/r11a_corrective/runtime.py",
    "research/archive_inventory/r11a_corrective/selection.py",
    "research/archive_inventory/r11a_corrective/storage_r7.py",
    "research/archive_inventory/r11a_corrective/taxonomy.py",
    "research/archive_inventory/r11a_corrective/taxonomy_precedence_r7.py",
    "research/archive_inventory/r11a_corrective/terminal_propagation.py",
    "research/archive_inventory/r11a/R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_PREREGISTRATION.json",
    "research/archive_inventory/r11a_v2/R11A_CORRECTIVE_PREREGISTRATION_AMENDMENT.json",
    "research/archive_inventory/r11a_v2/R11A_CORRECTIVE_PREREGISTRATION_AMENDMENT.md",
    "research/archive_inventory/r11a_v2/R11A_V2_PREREGISTRATION_BINDINGS.json",
    "research/archive_inventory/r11a_v2/R11A_V2_STATUS.json",
    "research/archive_inventory/r11a_v2/README.md",
    "governance/R11A_V2_REVIEW_FINDINGS.md",
    "tests/test_archive_inventory_r11a_v2_bindings.py",
    "tests/test_archive_inventory_r11a_v2_preregistration.py",
)

REQUIRED_BOUND_PATHS = tuple(
    sorted(
        {
            ALIGNMENT_RELATIVE,
            CANDIDATE_RELATIVE,
            WORKFLOW_RELATIVE,
            IMPLEMENTATION_RELATIVE,
            G1_ENVELOPE_RELATIVE,
            G1_PRICING_BINDING_RELATIVE,
            G1_APPROVAL_PACKAGE_RELATIVE,
            G1_SOURCE_STATEMENT_RELATIVE,
            PRICING_SOURCE_RELATIVE,
            PRICING_TARGET_RELATIVE,
            APPROVAL_JSON_RELATIVE,
            APPROVAL_TEXT_RELATIVE,
            ROLE_CONFIGURATION_CANDIDATE_RELATIVE,
            ROLE_ATTESTATION_RELATIVE,
            PREFLIGHT_CANDIDATE_RELATIVE,
            PREFLIGHT_RELEASE_RELATIVE,
            PREFLIGHT_EVIDENCE_RELATIVE,
            PREFLIGHT_CONSUMPTION_RELATIVE,
            INSTALLATION_RELATIVE,
            RELEASE_CANDIDATE_RELATIVE,
            RELEASE_RELATIVE,
            RELEASE_DIGEST_RELATIVE,
            ACTIVATION_RELATIVE,
            SELECTION_RELATIVE,
            PRIOR_RESULT_RELATIVE,
            TRUST_POLICY_RELATIVE,
            PERMISSION_POLICY_RELATIVE,
            ROLE_DECISION_RELATIVE,
            DEPENDENCIES_RELATIVE,
            RESOURCE_FEASIBILITY_RELATIVE,
            *(
                relative
                for gate_id, relative in REVIEW_EVIDENCE_PATHS.items()
                if gate_id != RUNTIME_BINDING_REVIEW_GATE
            ),
            *TRANSITIVE_CODE_PATHS,
        },
        key=lambda value: value.encode("utf-8"),
    )
)

EXPECTED_RUNTIME_AUTHORITY = {
    "single_manual_main_dispatch": True,
    "workflow_run_attempt_one": True,
    "oidc_successor_role_assumption": True,
    "sts_get_caller_identity": True,
    "requester_pays_exact_72_getobject": True,
    "two_local_decompression_passes": True,
    "diagnostic_processing": True,
    "diagnostic_artifact_retention": True,
    "iam_mutation": False,
    "other_s3_capability": False,
    "rerun": False,
}
EXPECTED_SCIENCE_STATE = {
    "empirical_root_cause": "UNKNOWN_PENDING_DIAGNOSTIC",
    "historical_expansion": False,
    "deduplication": False,
    "replay_suppression": False,
    "r11b_repair": False,
    "wallet_ranking": False,
    "candidate_shortlisting": False,
    "pnl_or_alpha_interpretation": False,
    "copyability": False,
    "clustering": False,
    "strategy_inference": False,
    "r11_closed": False,
    "r12_ready": False,
}
BINDING_KEYS = frozenset(
    {
        "schema_version",
        "binding_id",
        "diagnostic_id",
        "implementation_id",
        "approval_id",
        "alignment_id",
        "status",
        "workflow_name",
        "workflow_file",
        "candidate_workflow_path",
        "installed_workflow_path",
        "runtime_pricing_source_path",
        "runtime_pricing_installed_path",
        "single_use_window_start_utc",
        "activation_review_evidence_sha256",
        "bound_files",
        "runtime_authority",
        "science_state",
        "downstream_authorizations",
        "trading_authorizations",
        "r11_closed",
        "r12_ready",
    }
)


class RuntimeBindingError(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeBindingError(message)


def require_typed_exact(observed: object, expected: object, label: str) -> None:
    """Require recursive value equality without Python's bool/int coercion."""

    require(type(observed) is type(expected), f"{label} type drift")
    if type(expected) is dict:
        require(set(observed) == set(expected), f"{label} key set drift")
        for key, expected_value in expected.items():
            require_typed_exact(observed[key], expected_value, f"{label}.{key}")
        return
    if type(expected) is list:
        require(len(observed) == len(expected), f"{label} length drift")
        for index, expected_value in enumerate(expected):
            require_typed_exact(
                observed[index],
                expected_value,
                f"{label}[{index}]",
            )
        return
    require(observed == expected, f"{label} value drift")


def load(path: Path) -> dict[str, Any]:
    try:
        relative = path.relative_to(ROOT).as_posix()
    except ValueError:
        # Compatibility helper only; validation itself always uses root-relative
        # checked paths and rejects external paths.
        raise RuntimeBindingError("runtime JSON path escapes repository")
    try:
        return stage_load(ROOT, relative)
    except AssertionError as exc:
        raise RuntimeBindingError(str(exc)) from exc


def sha256(path: Path) -> str:
    try:
        relative = path.relative_to(ROOT).as_posix()
        return stage_sha256(ROOT, relative)
    except (ValueError, AssertionError) as exc:
        raise RuntimeBindingError("runtime hash path is invalid") from exc


def require_sha256(value: object, label: str) -> str:
    try:
        return stage_require_sha256(value, label)
    except AssertionError as exc:
        raise RuntimeBindingError(str(exc)) from exc


def require_commit(value: object, label: str) -> str:
    try:
        return stage_require_commit(value, label)
    except AssertionError as exc:
        raise RuntimeBindingError(str(exc)) from exc


def _utc_timestamp(value: object, label: str) -> str:
    require(isinstance(value, str) and value.endswith("Z"), f"{label} must be UTC text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeBindingError(f"{label} malformed") from exc
    require(parsed.tzinfo is not None and parsed.astimezone(timezone.utc) == parsed, f"{label} is not UTC")
    return value


def validate_binding(
    *,
    root: Path = ROOT,
    _review_lineage: list[object] | None = None,
) -> dict[str, Any]:
    """Validate the immutable binding subject and consume its activation review.

    Dispatch identity and the separate review of these binding bytes are outer
    concerns.  Keeping them out of this record avoids the impossible cycle in
    which a binding would need to contain either its own future Git commit or
    the digest of evidence that can exist only after the binding was reviewed.
    """

    lineage = [] if _review_lineage is None else _review_lineage
    try:
        permitted = successor_permissions(
            {
                ROLE_ATTESTATION_RELATIVE,
                PREFLIGHT_CANDIDATE_RELATIVE,
                PREFLIGHT_RELEASE_RELATIVE,
                PREFLIGHT_EVIDENCE_RELATIVE,
                PREFLIGHT_CONSUMPTION_RELATIVE,
                INSTALLATION_RELATIVE,
                WORKFLOW_RELATIVE,
                RELEASE_CANDIDATE_RELATIVE,
                RELEASE_RELATIVE,
                RELEASE_DIGEST_RELATIVE,
                ACTIVATION_RELATIVE,
                BINDING_RELATIVE,
                REVIEW_EVIDENCE_PATHS[ACTIVATION_REVIEW_GATE],
                REVIEW_EVIDENCE_PATHS[RUNTIME_BINDING_REVIEW_GATE],
            }
        )
        activation = validate_activation(
            root,
            permitted_successor_paths=permitted,
            _review_lineage=lineage,
        )
        require_absent(root, RELEASE_CONSUMPTION_RELATIVE, "execution release consumption")
    except AssertionError as exc:
        raise RuntimeBindingError(str(exc)) from exc
    try:
        binding = stage_load(root, BINDING_RELATIVE, missing_label="R7 runtime binding is absent")
    except AssertionError as exc:
        raise RuntimeBindingError(str(exc)) from exc
    try:
        require_exact(binding, BINDING_KEYS, "runtime binding")
    except AssertionError as exc:
        raise RuntimeBindingError(str(exc)) from exc
    require(binding["schema_version"] == "2.0", "runtime binding schema version drift")
    require(binding["binding_id"] == "HL-ARCHIVE-R11A-RUNTIME-BINDING-R7-001", "runtime binding ID drift")
    require(binding["diagnostic_id"] == DIAGNOSTIC_ID, "diagnostic ID drift")
    require(binding["implementation_id"] == IMPLEMENTATION_ID, "implementation ID drift")
    require(binding["approval_id"] == APPROVAL_ID, "approval ID drift")
    require(binding["alignment_id"] == ALIGNMENT_ID, "alignment ID drift")
    require(binding["status"] == "ACTIVE_FOR_EXACTLY_ONE_CANONICAL_R11A_R7_RUN", "runtime binding status drift")
    require(binding["workflow_name"] == WORKFLOW_NAME, "workflow name drift")
    require(binding["workflow_file"] == WORKFLOW_FILE, "workflow file drift")
    require(binding["candidate_workflow_path"] == CANDIDATE_RELATIVE, "candidate workflow path drift")
    require(binding["installed_workflow_path"] == WORKFLOW_RELATIVE, "installed workflow path drift")
    require(binding["runtime_pricing_source_path"] == PRICING_SOURCE_RELATIVE, "runtime pricing source path drift")
    require(binding["runtime_pricing_installed_path"] == PRICING_TARGET_RELATIVE, "runtime pricing target path drift")
    try:
        require_gate_review(
            root,
            binding,
            "activation_review_evidence_sha256",
            ACTIVATION_REVIEW_GATE,
            target_files={
                ACTIVATION_RELATIVE: stage_sha256(root, ACTIVATION_RELATIVE),
            },
            predecessor_files={
                RELEASE_RELATIVE: stage_sha256(root, RELEASE_RELATIVE),
                RELEASE_DIGEST_RELATIVE: stage_sha256(root, RELEASE_DIGEST_RELATIVE),
            },
            lineage=lineage,
        )
    except AssertionError as exc:
        raise RuntimeBindingError(str(exc)) from exc
    start = _utc_timestamp(binding["single_use_window_start_utc"], "single-use window")

    bound_files = binding["bound_files"]
    require(isinstance(bound_files, dict), "bound_files must be object")
    observed_paths = tuple(sorted(bound_files, key=lambda value: value.encode("utf-8")))
    require(observed_paths == REQUIRED_BOUND_PATHS, "runtime binding transitive file set drift")
    for relative in REQUIRED_BOUND_PATHS:
        expected = require_sha256(bound_files[relative], f"bound_files[{relative}]")
        try:
            observed = stage_sha256(root, relative)
        except AssertionError as exc:
            raise RuntimeBindingError(str(exc)) from exc
        require(observed == expected, f"bound runtime input hash drift: {relative}")

    try:
        require(read_bytes(root, CANDIDATE_RELATIVE) == read_bytes(root, WORKFLOW_RELATIVE), "installed workflow differs from R7 candidate")
        pricing_projection(root)
    except AssertionError as exc:
        raise RuntimeBindingError(str(exc)) from exc
    require(activation["single_use_window_start_utc"] == start, "runtime binding and activation windows differ")

    require_typed_exact(
        binding["runtime_authority"],
        EXPECTED_RUNTIME_AUTHORITY,
        "runtime authority",
    )
    require_typed_exact(
        binding["science_state"],
        EXPECTED_SCIENCE_STATE,
        "runtime science state",
    )
    try:
        stage_authority(binding["downstream_authorizations"], "runtime downstream authority")
        trading_authority(binding["trading_authorizations"], "runtime trading authority")
    except AssertionError as exc:
        raise RuntimeBindingError(str(exc)) from exc
    require(binding["r11_closed"] is False, "runtime binding prematurely closes R11")
    require(binding["r12_ready"] is False, "runtime binding prematurely opens R12")
    return binding
