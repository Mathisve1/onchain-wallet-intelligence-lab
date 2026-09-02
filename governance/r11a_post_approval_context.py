from __future__ import annotations

import stat
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from governance import r11a_github_review_evidence as _review_evidence
    from governance import validate_r11a_g2_owner_approval as _g2
    from governance import r11a_workflow_identity as _workflow_identity
except ModuleNotFoundError:  # Direct `python governance/<validator>.py` execution.
    import r11a_github_review_evidence as _review_evidence
    import validate_r11a_g2_owner_approval as _g2
    import r11a_workflow_identity as _workflow_identity

ROOT = _g2.ROOT
REPOSITORY = _g2.REPOSITORY

ALIGNMENT_ID = "R11A-POST-APPROVAL-VALIDATOR-ALIGNMENT-001"
ALIGNMENT_PATH = _g2.ALIGNMENT_PATH
OWNER_REVIEW_MODEL = "OWNER_SELF_REVIEW_COMMENTED_GREEN"
ALIGNMENT_STATUS = (
    "REVIEW_MODEL_CORRECTED_AWAITING_NEW_EXACT_HEAD_OWNER_COMMENTED_GREEN_"
    "REVIEW_AND_SEPARATE_EVIDENCE_CAPTURE_NO_AWS"
)

PREDECESSOR_HEAD = "63526d6c39c9225e647a18693c70ec8e73535ff4"
PREDECESSOR_TREE = "eedeb4d6166c554b996ede740931c4bacb306f5d"
G2_REVIEW_ID = 5033303996
RED_REVIEW_ID = 5049607285
RED_REVIEWED_HEAD = "44f9e912ca5b07bbe8f812d57a1706364d9c850b"
RED_REVIEWED_TREE = "739a3d3cf309d40258c8c725c72078ee571a5285"
LATER_RED_REVIEW_ID = 5054818123
LATER_RED_REVIEWED_HEAD = "6dc1bcccc66151b8aff7651965fa0d51ef9af0ed"
LATER_RED_REVIEWED_TREE = "2ac5c826407633d700894922ba86d32851e44177"
HISTORICAL_CONTENT_REVIEW_ID = 5087528366
HISTORICAL_CONTENT_REVIEWED_HEAD = "5616155ff7a70ca106be9a36288b4ca2d9eb0fd0"
HISTORICAL_CONTENT_REVIEWED_TREE = "3cf4cfcb0f8341087cd361993a719cc070333594"
HISTORICAL_CONTENT_REVIEW_SUBMITTED_AT = "2026-09-02T08:49:22Z"
HISTORICAL_CONTENT_REVIEW_AUTHOR_LOGIN = "Mathisve1"
HISTORICAL_CONTENT_REVIEW_AUTHOR_USER_ID = 163474992
REMEDIATED_FINDING_IDS = (
    "R11A-ALIGN-ISO-001",
    "R11A-ALIGN-ISO-002",
    "R11A-ALIGN-STATE-003",
    "R11A-ALIGN-REV-004",
    "R11A-ALIGN-ART-005",
    "R11A-ALIGN-GATE-006",
    "R11A-ALIGN-WF-007",
)

SOFTWARE_REVIEW_ID = _g2.SOFTWARE_REVIEW
SOFTWARE_REVIEWED_HEAD = _g2.SOFTWARE_HEAD
SOFTWARE_REVIEWED_TREE = _g2.SOFTWARE_TREE
G1_REVIEW_ID = _g2.READINESS_REVIEW
G1_REVIEWED_HEAD = _g2.READINESS_HEAD
G1_REVIEWED_TREE = _g2.READINESS_TREE

APPROVAL_JSON = _g2.APPROVAL_JSON
APPROVAL_TEXT = _g2.APPROVAL_TEXT
APPROVAL_RECEIPT_SHA = _g2.APPROVAL_RECEIPT_SHA
APPROVAL_STATEMENT_SHA = _g2.APPROVAL_STATEMENT_SHA
APPROVAL_SCALAR_LEAVES = 136

WORKFLOW = _g2.WORKFLOW
WORKFLOW_SHA = _g2.EXPECTED_BOUND_FILES[WORKFLOW]

RUNTIME_PRICING_SOURCE = _g2.RUNTIME_PRICING
RUNTIME_PRICING_SOURCE_SHA = _g2.EXPECTED_BOUND_FILES[RUNTIME_PRICING_SOURCE]
RUNTIME_PRICING_TARGET = (
    "research/archive_inventory/r11a_corrective/R11A_PRICING_EUR_SNAPSHOT.json"
)
RUNTIME_PRICING_TARGET_SHA = (
    "5e5a6469b921a15cbac1e2f03184e2dfcf6ffee51dc2e86833e9556a5c23c226"
)

NEXT_GATE = (
    "NEW_EXACT_HEAD_MACHINE_READABLE_OWNER_COMMENTED_GREEN_REVIEW_ON_UPDATED_"
    "ALIGNMENT_PR_151_THEN_SEPARATE_EVIDENCE_CAPTURE_NO_AWS"
)

ALIGNED_CONSUMERS = (
    "governance/r11a_bytecode_boundary.c",
    "governance/r11a_native_boundary.sh",
    "governance/r11a_repository_provenance.py",
    "governance/seal_r11a_v2_preregistration.py",
    "governance/r11a_github_review_evidence.py",
    "governance/r11a_post_approval_context.py",
    "governance/r11a_stage_common_r4.py",
    "governance/r11a_workflow_identity.py",
    "governance/validate_r11a_approval_r4.py",
    "governance/validate_r11a_g2_owner_approval.py",
    "governance/validate_r11a_post_approval_validator_alignment.py",
    "governance/validate_r11a_role_configuration_candidate_r4.py",
    "governance/validate_r11a_role_attestation_r4.py",
    "governance/validate_r11a_role_preflight_evidence_r4.py",
    "governance/validate_r11a_workflow_installation_r4.py",
    "governance/validate_r11a_execution_release_r4.py",
    "governance/validate_r11a_activation_r4.py",
    "governance/validate_r11a_runtime_binding_r7.py",
    "governance/_validate_r11a_runtime_binding_core_r7.py",
    "governance/validate_r11a_execution_artifact_r7.py",
    "governance/validate_r11a_v2_bindings.py",
)

FUTURE_STAGE_PATHS = _g2.KNOWN_FUTURE_STAGE_PATHS
CANONICAL_FUTURE_AUTHORITY_PATHS = _g2.CANONICAL_FUTURE_AUTHORITY_PATHS
PROHIBITED_AUTHORITY_NAMESPACES = _g2.PROHIBITED_AUTHORITY_NAMESPACES
PROHIBITED_INSTALLED_WORKFLOWS = _g2.PROHIBITED_INSTALLED_WORKFLOWS


class PostApprovalContextError(_g2.R11AG2ApprovalError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PostApprovalContextError(message)


def _normalize_permitted_successor_paths(
    paths: frozenset[str],
) -> frozenset[str]:
    try:
        return _g2._normalize_permitted_successor_paths(paths)
    except _g2.R11AG2ApprovalError as exc:
        raise PostApprovalContextError(str(exc)) from exc


def _scalar_leaf_count(value: object) -> int:
    if type(value) is dict:
        return sum(_scalar_leaf_count(child) for child in value.values())
    if type(value) is list:
        return sum(_scalar_leaf_count(child) for child in value)
    return 1


def load_strict_json(root: Path, relative: str) -> dict[str, Any]:
    try:
        return _g2.load(root, relative)
    except _g2.R11AG2ApprovalError as exc:
        raise PostApprovalContextError(str(exc)) from exc


def sha256(root: Path, relative: str) -> str:
    try:
        return _g2.sha256(root, relative)
    except _g2.R11AG2ApprovalError as exc:
        raise PostApprovalContextError(str(exc)) from exc


def require_exact(observed: object, expected: object, label: str) -> None:
    try:
        _g2.require_exact(observed, expected, label)
    except _g2.R11AG2ApprovalError as exc:
        raise PostApprovalContextError(str(exc)) from exc


def require_absent(root: Path, relative: str, label: str) -> None:
    try:
        _g2._require_absent(root, relative, label)
    except _g2.R11AG2ApprovalError as exc:
        raise PostApprovalContextError(str(exc)) from exc


def required_file(root: Path, relative: str) -> Path:
    try:
        return _g2._required_file(root, relative)
    except _g2.R11AG2ApprovalError as exc:
        raise PostApprovalContextError(str(exc)) from exc


def relative_path(root: Path, relative: str) -> Path:
    """Return a checked lexical repository path without resolving symlinks."""
    try:
        path, _ = _g2._inspect_path(root, relative, allow_missing=True)
    except _g2.R11AG2ApprovalError as exc:
        raise PostApprovalContextError(str(exc)) from exc
    return path


def _allowed_successor_directories(
    permitted_successor_paths: frozenset[str],
) -> frozenset[str]:
    result: set[str] = set()
    for relative in permitted_successor_paths:
        pure = PurePosixPath(relative)
        for parent in pure.parents:
            value = parent.as_posix()
            if value in {".", "research", "research/archive_inventory", ".github", ".github/workflows"}:
                continue
            if value.startswith("research/archive_inventory/"):
                result.add(value)
    return frozenset(result)


def _validate_successor_surface(
    root: Path,
    permitted_successor_paths: frozenset[str],
) -> None:
    require_absent(root, ".gitmodules", "submodule metadata unexpectedly present")
    allowed_directories = _allowed_successor_directories(permitted_successor_paths)

    for relative in sorted(
        FUTURE_STAGE_PATHS - permitted_successor_paths,
        key=lambda value: value.encode("utf-8"),
    ):
        require_absent(
            root,
            relative,
            "future authority artifact unexpectedly present",
        )

    for namespace in PROHIBITED_AUTHORITY_NAMESPACES:
        permitted_below = frozenset(
            relative
            for relative in permitted_successor_paths
            if relative.startswith(namespace + "/")
        )
        if not permitted_below:
            require_absent(
                root,
                namespace,
                "future authority namespace unexpectedly present",
            )

    try:
        entries = tuple(_g2._repository_entries(root))
    except _g2.R11AG2ApprovalError as exc:
        raise PostApprovalContextError(str(exc)) from exc
    for relative, information in entries:
        in_future_namespace = any(
            relative == namespace or relative.startswith(namespace + "/")
            for namespace in PROHIBITED_AUTHORITY_NAMESPACES
        )
        if not in_future_namespace:
            continue
        if stat.S_ISDIR(information.st_mode):
            _require(
                relative in allowed_directories,
                f"unpermitted future authority directory present: {relative}",
            )
            continue
        _require(
            relative in permitted_successor_paths,
            f"unpermitted future authority artifact present: {relative}",
        )
        _require(
            stat.S_ISREG(information.st_mode),
            f"permitted future authority path is not regular file: {relative}",
        )

    for relative in sorted(
        permitted_successor_paths,
        key=lambda value: value.encode("utf-8"),
    ):
        path, information = _g2._inspect_path(root, relative, allow_missing=True)
        if information is not None:
            _require(
                stat.S_ISREG(information.st_mode),
                f"permitted successor path is not regular file: {relative}",
            )
            _require(
                information.st_nlink == 1,
                f"permitted successor path has hard-link alias: {relative}",
            )
            _require(path == root / PurePosixPath(relative), "successor path ambiguity")

    try:
        _, installed_information = _g2._inspect_path(
            root,
            _g2.INSTALLED_WORKFLOW,
            allow_missing=True,
        )
        _workflow_identity.validate_workflow_identity_inventory(
            root,
            canonical_installed=(installed_information is not None),
        )
    except (_g2.R11AG2ApprovalError, _workflow_identity.R11AWorkflowIdentityError) as exc:
        raise PostApprovalContextError(str(exc)) from exc


def validate_approval_context(
    root: Path = ROOT,
    *,
    permitted_successor_paths: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    root = Path(root)
    permitted = _normalize_permitted_successor_paths(permitted_successor_paths)
    try:
        record = _g2.validate_immutable_approval_context(
            root,
            permitted_successor_paths=permitted,
        )
    except _g2.R11AG2ApprovalError as exc:
        raise PostApprovalContextError(str(exc)) from exc
    _require(
        _scalar_leaf_count(record) == APPROVAL_SCALAR_LEAVES,
        "canonical approval record scalar leaf count drift",
    )
    def present(relative: str) -> bool:
        try:
            _, information = _g2._inspect_path(root, relative, allow_missing=True)
        except _g2.R11AG2ApprovalError as exc:
            raise PostApprovalContextError(str(exc)) from exc
        if information is None:
            return False
        _require(stat.S_ISREG(information.st_mode), f"live stage path is not regular: {relative}")
        _require(information.st_nlink == 1, f"live stage path has hard-link alias: {relative}")
        return True

    live_stage_state = {
        "r11a_successor_role_created": present(
            "research/archive_inventory/r11a_role_attestation/"
            "R11A_SUCCESSOR_ROLE_OPERATOR_ATTESTATION.json"
        ),
        "r11a_successor_role_attestation_present": present(
            "research/archive_inventory/r11a_role_attestation/"
            "R11A_SUCCESSOR_ROLE_OPERATOR_ATTESTATION.json"
        ),
        "r11a_sts_preflight": present(
            "research/archive_inventory/r11a_role_preflight/"
            "R11A_SUCCESSOR_ROLE_STS_PREFLIGHT_ATTESTATION.json"
        ),
        "r11a_workflow_installed": present(
            ".github/workflows/"
            "hyperliquid-archive-r11a-identity-boundary-diagnostic.yml"
        ),
        "r11a_release_present": present(
            "research/archive_inventory/r11a_runtime/R11A_EXECUTION_RELEASE.json"
        ),
        "r11a_runtime_release": present(
            "research/archive_inventory/r11a_runtime/R11A_EXECUTION_RELEASE.json"
        ),
        "r11a_runtime_activation": present(
            "research/archive_inventory/r11a_runtime/R11A_CANONICAL_ACTIVATION.json"
        ),
        "r11a_runtime_binding": present(
            "research/archive_inventory/r11a_runtime/R11A_RUNTIME_BINDING_R7.json"
        ),
        "r11a_runtime_binding_review": present(
            _review_evidence.evidence_path("R11A_RUNTIME_BINDING_REVIEW")
        ),
    }
    try:
        _workflow_identity.validate_post_g2_project_state(
            root,
            approval_id=_g2.APPROVAL_ID,
            approval_text_sha256=APPROVAL_STATEMENT_SHA,
            approval_record=record,
            live_stage_state=live_stage_state,
        )
    except _workflow_identity.R11AProjectStateError as exc:
        raise PostApprovalContextError(str(exc)) from exc
    _validate_successor_surface(root, permitted)
    return record


def expected_alignment_record(root: Path = ROOT) -> dict[str, Any]:
    approval = _g2.expected_record(root)
    return {
        "schema_version": "1.0",
        "alignment_id": ALIGNMENT_ID,
        "repository": REPOSITORY,
        "status": ALIGNMENT_STATUS,
        "predecessor": {
            "head": PREDECESSOR_HEAD,
            "tree": PREDECESSOR_TREE,
        },
        "g2_review": {
            "review_id": G2_REVIEW_ID,
            "review_event": "COMMENTED",
            "review_verdict": "GREEN",
        },
        "prior_exact_head_review": {
            "review_id": RED_REVIEW_ID,
            "review_event": "COMMENTED",
            "review_verdict": "RED",
            "reviewed_head": RED_REVIEWED_HEAD,
            "reviewed_tree": RED_REVIEWED_TREE,
        },
        "later_exact_head_red_review": {
            "review_id": LATER_RED_REVIEW_ID,
            "review_event": "COMMENTED",
            "review_verdict": "RED",
            "reviewed_head": LATER_RED_REVIEWED_HEAD,
            "reviewed_tree": LATER_RED_REVIEWED_TREE,
        },
        "review_governance_model": {
            "classification": OWNER_REVIEW_MODEL,
            "same_github_identity_as_pull_author_permitted": True,
            "distinct_qualified_reviewer_supported": True,
            "review_event_required": "COMMENTED",
            "authorized_author_associations": ["OWNER", "MEMBER", "COLLABORATOR"],
            "authorized_repository_permissions": ["write", "maintain", "admin"],
            "immutable_review_and_permission_payloads_required": True,
            "exact_head_and_tree_required": True,
            "exact_green_and_gate_markers_required": True,
            "exact_canonical_marker_only_body_required": True,
            "chronology_required": True,
            "later_red_supersession_forbidden": True,
            "target_and_predecessor_bundles_required": True,
            "cross_gate_review_id_reuse_forbidden": True,
            "cross_gate_review_node_id_reuse_forbidden": True,
            "cross_gate_evidence_digest_reuse_forbidden": True,
            "cross_gate_reviewed_head_reuse_forbidden": True,
            "cross_gate_reviewed_tree_reuse_forbidden": True,
            "human_substantive_responsibility_retained": True,
            "github_approved": False,
            "third_party_independence_claimed": False,
            "merge_authority": False,
            "aws_iam_oidc_sts_s3_authority": False,
            "workflow_release_activation_runtime_diagnostic_authority": False,
        },
        "historical_content_review": {
            "review_id": HISTORICAL_CONTENT_REVIEW_ID,
            "review_event": "COMMENTED",
            "content_verdict": "GREEN",
            "reviewed_head": HISTORICAL_CONTENT_REVIEWED_HEAD,
            "reviewed_tree": HISTORICAL_CONTENT_REVIEWED_TREE,
            "submitted_at": HISTORICAL_CONTENT_REVIEW_SUBMITTED_AT,
            "author_login": HISTORICAL_CONTENT_REVIEW_AUTHOR_LOGIN,
            "author_user_id": HISTORICAL_CONTENT_REVIEW_AUTHOR_USER_ID,
            "content_green": True,
            "machine_readable_gate_evidence": False,
            "review_modified": False,
            "review_dismissed": False,
            "review_deleted": False,
            "evidence_capture_present": False,
            "failure_reasons": [
                "FIRST_NONEMPTY_LINE_NOT_EXACT_GREEN",
                "REQUIRED_GATE_TARGET_AND_PREDECESSOR_MARKERS_ABSENT",
                "OWNER_REVIEW_CONTAINS_INDEPENDENCE_CLAIM",
            ],
        },
        "seven_finding_remediation": {
            "finding_ids": list(REMEDIATED_FINDING_IDS),
            "remediation_status": (
                "IMPLEMENTED_AWAITING_NEW_EXACT_HEAD_OWNER_COMMENTED_GREEN_"
                "REVIEW_AND_SEPARATE_EVIDENCE_CAPTURE"
            ),
            "machine_readable_owner_review_pending": True,
            "separate_evidence_capture_pending": True,
            "review_gate_closed": False,
            "repository_only": True,
            "aws_or_runtime_action_performed": False,
        },
        "approved_bound_bytes_unchanged": True,
        "alignment_implementation_status": (
            "SEVEN_FINDING_REMEDIATION_IMPLEMENTED_INERT_REVIEW_MODEL_CORRECTED_"
            "PENDING_NEW_OWNER_REVIEW_AND_SEPARATE_EVIDENCE_NO_AWS"
        ),
        "no_aws_action_performed": True,
        "canonical_approval": {
            "receipt_path": APPROVAL_JSON,
            "receipt_sha256": APPROVAL_RECEIPT_SHA,
            "statement_path": APPROVAL_TEXT,
            "statement_sha256": APPROVAL_STATEMENT_SHA,
            "scalar_leaf_count": APPROVAL_SCALAR_LEAVES,
        },
        "approved_bound_files": dict(_g2.EXPECTED_BOUND_FILES),
        "aligned_consumers": list(ALIGNED_CONSUMERS),
        "r7_workflow": {
            "path": WORKFLOW,
            "sha256": WORKFLOW_SHA,
        },
        "future_runtime_pricing_projection": {
            "status": "REQUIRED_LATER_NOT_PRESENT",
            "source_path": RUNTIME_PRICING_SOURCE,
            "source_sha256": RUNTIME_PRICING_SOURCE_SHA,
            "target_historical_snapshot_path": RUNTIME_PRICING_TARGET,
            "target_historical_snapshot_current_sha256": RUNTIME_PRICING_TARGET_SHA,
            "projection_present": False,
        },
        "current_authority": dict(approval["current_authority"]),
        "future_authority_absence": {
            "canonical_artifact_paths": list(CANONICAL_FUTURE_AUTHORITY_PATHS),
            "prohibited_namespace_paths": list(PROHIBITED_AUTHORITY_NAMESPACES),
            "installed_workflow_paths": list(PROHIBITED_INSTALLED_WORKFLOWS),
            "all_absent": True,
        },
        "aws_activity": {
            "iam": False,
            "oidc": False,
            "sts": False,
            "s3": False,
        },
        "machine_readable_owner_review_pending": True,
        "separate_review_evidence_capture_pending": True,
        "alignment_review_gate_closed": False,
        "next_gate": NEXT_GATE,
    }


def validate_alignment(
    root: Path = ROOT,
    *,
    permitted_successor_paths: frozenset[str] = frozenset(),
    runtime_pricing_projection_permitted: bool = False,
) -> dict[str, Any]:
    root = Path(root)
    _require(
        type(runtime_pricing_projection_permitted) is bool,
        "runtime-pricing projection permission must be exact boolean",
    )
    permitted = _normalize_permitted_successor_paths(permitted_successor_paths)
    validate_approval_context(root, permitted_successor_paths=permitted)
    observed = load_strict_json(root, ALIGNMENT_PATH)
    require_exact(observed, expected_alignment_record(root), "post-approval alignment")
    _require(
        sha256(root, WORKFLOW) == WORKFLOW_SHA,
        "approved R7 workflow raw hash drift",
    )
    _require(
        sha256(root, RUNTIME_PRICING_SOURCE) == RUNTIME_PRICING_SOURCE_SHA,
        "future runtime-pricing source hash drift",
    )
    for relative in ALIGNED_CONSUMERS:
        required_file(root, relative)
    if runtime_pricing_projection_permitted:
        _require(
            required_file(root, RUNTIME_PRICING_TARGET).read_bytes()
            == required_file(root, RUNTIME_PRICING_SOURCE).read_bytes(),
            "runtime-pricing projection is not exact approved source bytes",
        )
        _require(
            sha256(root, RUNTIME_PRICING_TARGET) == RUNTIME_PRICING_SOURCE_SHA,
            "runtime-pricing projection hash drift",
        )
    else:
        _require(
            sha256(root, RUNTIME_PRICING_TARGET) == RUNTIME_PRICING_TARGET_SHA,
            "historical corrective pricing snapshot hash drift",
        )
    return observed


__all__ = [
    "ALIGNMENT_ID",
    "ALIGNMENT_PATH",
    "ALIGNMENT_STATUS",
    "ALIGNED_CONSUMERS",
    "APPROVAL_JSON",
    "APPROVAL_RECEIPT_SHA",
    "APPROVAL_SCALAR_LEAVES",
    "APPROVAL_STATEMENT_SHA",
    "APPROVAL_TEXT",
    "CANONICAL_FUTURE_AUTHORITY_PATHS",
    "FUTURE_STAGE_PATHS",
    "G2_REVIEW_ID",
    "HISTORICAL_CONTENT_REVIEW_AUTHOR_LOGIN",
    "HISTORICAL_CONTENT_REVIEW_AUTHOR_USER_ID",
    "HISTORICAL_CONTENT_REVIEW_ID",
    "HISTORICAL_CONTENT_REVIEW_SUBMITTED_AT",
    "HISTORICAL_CONTENT_REVIEWED_HEAD",
    "HISTORICAL_CONTENT_REVIEWED_TREE",
    "LATER_RED_REVIEW_ID",
    "LATER_RED_REVIEWED_HEAD",
    "LATER_RED_REVIEWED_TREE",
    "NEXT_GATE",
    "OWNER_REVIEW_MODEL",
    "PREDECESSOR_HEAD",
    "PREDECESSOR_TREE",
    "PROHIBITED_AUTHORITY_NAMESPACES",
    "PROHIBITED_INSTALLED_WORKFLOWS",
    "PostApprovalContextError",
    "REPOSITORY",
    "ROOT",
    "RUNTIME_PRICING_SOURCE",
    "RUNTIME_PRICING_SOURCE_SHA",
    "RUNTIME_PRICING_TARGET",
    "RUNTIME_PRICING_TARGET_SHA",
    "WORKFLOW",
    "WORKFLOW_SHA",
    "expected_alignment_record",
    "load_strict_json",
    "relative_path",
    "require_absent",
    "require_exact",
    "required_file",
    "sha256",
    "validate_alignment",
    "validate_approval_context",
]
