from __future__ import annotations

import stat
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from governance import validate_r11a_g2_owner_approval as _g2
except ModuleNotFoundError:  # Direct `python governance/<validator>.py` execution.
    import validate_r11a_g2_owner_approval as _g2

ROOT = _g2.ROOT
REPOSITORY = _g2.REPOSITORY

ALIGNMENT_ID = "R11A-POST-APPROVAL-VALIDATOR-ALIGNMENT-001"
ALIGNMENT_PATH = _g2.ALIGNMENT_PATH
ALIGNMENT_STATUS = "ALIGNED_INERT_AWAITING_INDEPENDENT_EXACT_HEAD_REVIEW_NO_AWS"

PREDECESSOR_HEAD = "63526d6c39c9225e647a18693c70ec8e73535ff4"
PREDECESSOR_TREE = "eedeb4d6166c554b996ede740931c4bacb306f5d"
G2_REVIEW_ID = 5033303996

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

NEXT_GATE = "INDEPENDENT_EXACT_HEAD_REVIEW_OF_POST_APPROVAL_VALIDATOR_ALIGNMENT_NO_AWS"

ALIGNED_CONSUMERS = (
    "governance/r11a_stage_common_r4.py",
    "governance/validate_r11a_approval_r4.py",
    "governance/validate_r11a_role_attestation_r4.py",
    "governance/validate_r11a_role_preflight_evidence_r4.py",
    "governance/validate_r11a_workflow_installation_r4.py",
    "governance/validate_r11a_execution_release_r4.py",
    "governance/validate_r11a_activation_r4.py",
    "governance/validate_r11a_runtime_binding_r7.py",
    "governance/_validate_r11a_runtime_binding_core_r7.py",
    "governance/validate_r11a_execution_artifact_r7.py",
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
        "approved_bound_bytes_unchanged": True,
        "alignment_implementation_status": (
            "IMPLEMENTED_INERT_PENDING_INDEPENDENT_EXACT_HEAD_REVIEW_NO_AWS"
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
        "independent_exact_head_review_pending": True,
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
    "NEXT_GATE",
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
