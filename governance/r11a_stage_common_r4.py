from __future__ import annotations

import hashlib
import json
import re
import stat
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

try:  # Package import (tests and ``python -m``).
    from governance import r11a_post_approval_context as _post_approval
    from governance import r11a_github_review_evidence as _review_evidence
except ModuleNotFoundError:  # Direct ``python governance/<validator>.py`` execution.
    import r11a_post_approval_context as _post_approval
    import r11a_github_review_evidence as _review_evidence


ROOT = Path(__file__).absolute().parents[1]

ARCHIVE_RELATIVE = "research/archive_inventory"
CORRECTIVE_RELATIVE = f"{ARCHIVE_RELATIVE}/r11a_corrective"
G1_RELATIVE = f"{ARCHIVE_RELATIVE}/r11a_g1"
APPROVAL_RELATIVE = f"{ARCHIVE_RELATIVE}/r11a_approval"
ROLE_RELATIVE = f"{ARCHIVE_RELATIVE}/r11a_role_attestation"
PREFLIGHT_RELATIVE = f"{ARCHIVE_RELATIVE}/r11a_role_preflight"
INSTALL_RELATIVE = f"{ARCHIVE_RELATIVE}/r11a_workflow_installation"
RUNTIME_RELATIVE = f"{ARCHIVE_RELATIVE}/r11a_runtime"
REVIEW_EVIDENCE_RELATIVE = f"{ARCHIVE_RELATIVE}/r11a_review_evidence"

ROLE_ARN = (
    "arn:aws:iam::630956766927:role/"
    "onchain-wallet-intelligence-hl-archive-identity-r11a"
)
DIAGNOSTIC_ID = "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-002"
APPROVAL_ID = "APPROVE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001"
WORKFLOW_NAME = "Hyperliquid Archive R11A Identity Boundary Diagnostic"
WORKFLOW_FILE = "hyperliquid-archive-r11a-identity-boundary-diagnostic.yml"

WORKFLOW_RELATIVE = f".github/workflows/{WORKFLOW_FILE}"
CANDIDATE_RELATIVE = (
    f"{CORRECTIVE_RELATIVE}/workflows/"
    "hyperliquid-archive-r11a-identity-boundary-diagnostic-r7.yml"
)
IMPLEMENTATION_RELATIVE = (
    f"{CORRECTIVE_RELATIVE}/R11A_CORRECTIVE_IMPLEMENTATION_CONTRACT_R7.json"
)
PRICING_SOURCE_RELATIVE = (
    f"{G1_RELATIVE}/R11A_G1_RUNTIME_PRICING_SNAPSHOT_CANDIDATE.json"
)
G1_ENVELOPE_RELATIVE = f"{G1_RELATIVE}/R11A_G1_EXECUTION_ENVELOPE.json"
G1_PRICING_BINDING_RELATIVE = f"{G1_RELATIVE}/R11A_G1_PRICING_EUR_BINDING.json"
G1_APPROVAL_PACKAGE_RELATIVE = f"{G1_RELATIVE}/R11A_G1_OWNER_APPROVAL_PACKAGE.json"
G1_SOURCE_STATEMENT_RELATIVE = f"{G1_RELATIVE}/R11A_G1_OWNER_APPROVAL_STATEMENT.txt"
PRICING_TARGET_RELATIVE = f"{CORRECTIVE_RELATIVE}/R11A_PRICING_EUR_SNAPSHOT.json"
SELECTION_RELATIVE = f"{ARCHIVE_RELATIVE}/r11/R11_72H_SELECTION.json"
PRIOR_RESULT_RELATIVE = (
    f"{ARCHIVE_RELATIVE}/r11_evidence/run-31436753081/r11-result.json"
)
APPROVAL_JSON_RELATIVE = f"{APPROVAL_RELATIVE}/{APPROVAL_ID}.json"
APPROVAL_TEXT_RELATIVE = f"{APPROVAL_RELATIVE}/{APPROVAL_ID}.txt"
ROLE_ATTESTATION_RELATIVE = (
    f"{ROLE_RELATIVE}/R11A_SUCCESSOR_ROLE_OPERATOR_ATTESTATION.json"
)
ROLE_CONFIGURATION_CANDIDATE_RELATIVE = (
    f"{ROLE_RELATIVE}/R11A_SUCCESSOR_ROLE_CREATION_CONFIGURATION_CANDIDATE.json"
)
PREFLIGHT_CANDIDATE_RELATIVE = (
    f"{PREFLIGHT_RELATIVE}/R11A_STS_PREFLIGHT_CANDIDATE.json"
)
PREFLIGHT_RELEASE_RELATIVE = (
    f"{PREFLIGHT_RELATIVE}/R11A_STS_PREFLIGHT_RELEASE.json"
)
PREFLIGHT_EVIDENCE_RELATIVE = (
    f"{PREFLIGHT_RELATIVE}/R11A_SUCCESSOR_ROLE_STS_PREFLIGHT_ATTESTATION.json"
)
PREFLIGHT_CONSUMPTION_RELATIVE = (
    f"{PREFLIGHT_RELATIVE}/R11A_STS_PREFLIGHT_RELEASE_CONSUMPTION.json"
)
INSTALLATION_RELATIVE = (
    f"{INSTALL_RELATIVE}/R11A_WORKFLOW_INSTALLATION_CONTRACT.json"
)
RELEASE_CANDIDATE_RELATIVE = (
    f"{RUNTIME_RELATIVE}/R11A_EXECUTION_RELEASE_CANDIDATE.json"
)
RELEASE_RELATIVE = f"{RUNTIME_RELATIVE}/R11A_EXECUTION_RELEASE.json"
RELEASE_DIGEST_RELATIVE = f"{RUNTIME_RELATIVE}/R11A_EXECUTION_RELEASE.sha256"
ACTIVATION_RELATIVE = f"{RUNTIME_RELATIVE}/R11A_CANONICAL_ACTIVATION.json"
BINDING_RELATIVE = f"{RUNTIME_RELATIVE}/R11A_RUNTIME_BINDING_R7.json"
RELEASE_CONSUMPTION_RELATIVE = (
    f"{RUNTIME_RELATIVE}/R11A_EXECUTION_RELEASE_CONSUMPTION.json"
)
TRUST_POLICY_RELATIVE = f"{CORRECTIVE_RELATIVE}/R11A_OIDC_TRUST_POLICY.json"
PERMISSION_POLICY_RELATIVE = f"{CORRECTIVE_RELATIVE}/R11A_PERMISSION_POLICY.json"
ROLE_DECISION_RELATIVE = f"{CORRECTIVE_RELATIVE}/R11A_ROLE_DECISION.json"
DEPENDENCIES_RELATIVE = f"{CORRECTIVE_RELATIVE}/R11A_DEPENDENCIES.json"
RESOURCE_FEASIBILITY_RELATIVE = f"{CORRECTIVE_RELATIVE}/R11A_RESOURCE_FEASIBILITY_R3.json"
RUNNER_RELATIVE = f"{CORRECTIVE_RELATIVE}/runner.py"
ARTIFACT_VALIDATOR_RELATIVE = "governance/validate_r11a_execution_artifact_r7.py"

REVIEW_GATE_IDS = tuple(_review_evidence.GATE_REGISTRY)
REVIEW_EVIDENCE_PATHS = {
    gate_id: _review_evidence.evidence_path(gate_id)
    for gate_id in REVIEW_GATE_IDS
}

APPROVED_WORKFLOW_SHA = "c10b810304d6cdbc68f23cb3db113b57580d34f0f74e781aefa2140edd0b5e65"
APPROVED_PRICING_SOURCE_SHA = "d5043062386b3d70f695f09c917f11719512918c56f318cace1e0530b709ac43"
APPROVED_PERMISSION_SHA = "2769afe520efff6f0b619fff352d2cf13d412d96d6c4642fcfc61a8165787e6a"
APPROVED_TRUST_SHA = "375e224b269a62873afb4516651a259483feed4f211e9184272cb2af91513668"
ALIGNMENT_ID = _post_approval.ALIGNMENT_ID
ALIGNMENT_RELATIVE = _post_approval.ALIGNMENT_PATH
APPROVAL_RECEIPT_SHA = _post_approval.APPROVAL_RECEIPT_SHA
G2_REVIEW_ID = _post_approval.G2_REVIEW_ID

# Compatibility path constants. Validation derives paths from the supplied root.
BASE = ROOT / ARCHIVE_RELATIVE
CORRECTIVE = ROOT / CORRECTIVE_RELATIVE
APPROVAL_DIR = ROOT / APPROVAL_RELATIVE
ROLE_DIR = ROOT / ROLE_RELATIVE
PREFLIGHT_DIR = ROOT / PREFLIGHT_RELATIVE
INSTALL_DIR = ROOT / INSTALL_RELATIVE
RUNTIME_DIR = ROOT / RUNTIME_RELATIVE
EVIDENCE_DIR = BASE / "r11a_evidence"
WORKFLOW_PATH = ROOT / WORKFLOW_RELATIVE
CANDIDATE_PATH = ROOT / CANDIDATE_RELATIVE
SELECTION_PATH = ROOT / SELECTION_RELATIVE
IMPLEMENTATION_CONTRACT = ROOT / IMPLEMENTATION_RELATIVE
PRICING_SNAPSHOT = ROOT / PRICING_TARGET_RELATIVE

DOWNSTREAM_AUTHORITY_KEYS = frozenset(
    {
        "workflow_installed",
        "runtime_binding_present",
        "runtime_release",
        "runtime_activation",
        "workflow_dispatch",
        "requester_pays",
        "get_object",
        "object_body_download",
        "decompression",
        "diagnostic_execution",
        "diagnostic_artifact_retention",
        "r11_closed",
        "r12_ready",
        "rerun",
    }
)
TRADING_AUTHORITY_KEYS = frozenset(
    {
        "integration",
        "paper",
        "shadow",
        "live",
        "leverage",
        "capital_allocation",
        "withdrawals_or_transfers",
    }
)
KNOWN_SUCCESSOR_PATHS = frozenset(
    {
        ROLE_CONFIGURATION_CANDIDATE_RELATIVE,
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
        RELEASE_CONSUMPTION_RELATIVE,
        *REVIEW_EVIDENCE_PATHS.values(),
    }
)


class StageValidationError(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise StageValidationError(message)


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value: str) -> Any:
    raise StageValidationError(f"non-finite JSON constant: {value}")


def _root(root: Path) -> Path:
    candidate = Path(root)
    require(candidate.is_absolute(), "repository root must be an absolute path")
    require(".." not in candidate.parts, "repository root traversal rejected")
    current = Path(candidate.anchor)
    for part in candidate.parts[1:]:
        current /= part
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise StageValidationError("repository root is absent") from exc
        require(not stat.S_ISLNK(metadata.st_mode), "repository root ancestry must not contain symlink")
        require(stat.S_ISDIR(metadata.st_mode), "repository root ancestry must contain directories only")
    return candidate


def _relative_parts(relative: str) -> tuple[str, ...]:
    require(isinstance(relative, str) and bool(relative), "repository path must be nonempty text")
    pure = PurePosixPath(relative)
    require(not pure.is_absolute(), f"repository path must be relative: {relative}")
    require("\\" not in relative, f"repository path contains backslash: {relative}")
    require(
        all(part not in {"", ".", ".."} for part in pure.parts),
        f"repository path traversal rejected: {relative}",
    )
    require(str(pure) == relative, f"repository path is not canonical: {relative}")
    return pure.parts


def checked_path(
    root: Path,
    relative: str,
    *,
    must_exist: bool = True,
    expected_kind: str = "file",
    missing_label: str | None = None,
) -> Path:
    """Inspect every component without resolving away symlinks."""

    base = _root(root)
    parts = _relative_parts(relative)
    current = base
    for index, part in enumerate(parts):
        current = current / part
        final = index == len(parts) - 1
        try:
            metadata = current.lstat()
        except FileNotFoundError as exc:
            if not must_exist:
                return current
            raise StageValidationError(missing_label or f"required path is absent: {relative}") from exc
        except OSError as exc:
            raise StageValidationError(f"cannot inspect repository path: {relative}") from exc
        require(not stat.S_ISLNK(metadata.st_mode), f"symlink rejected: {relative}")
        if not final:
            require(
                stat.S_ISDIR(metadata.st_mode),
                f"non-directory intermediate component rejected: {relative}",
            )
            continue
        if expected_kind == "file":
            require(stat.S_ISREG(metadata.st_mode), f"non-regular file rejected: {relative}")
            require(metadata.st_nlink == 1, f"hard-linked file rejected: {relative}")
        elif expected_kind == "directory":
            require(stat.S_ISDIR(metadata.st_mode), f"non-directory rejected: {relative}")
        elif expected_kind == "any":
            require(
                stat.S_ISREG(metadata.st_mode) or stat.S_ISDIR(metadata.st_mode),
                f"special file rejected: {relative}",
            )
        else:  # pragma: no cover - caller programming error.
            raise ValueError(f"unsupported expected kind: {expected_kind}")
    return current


def require_absent(root: Path, relative: str, label: str) -> None:
    path = checked_path(root, relative, must_exist=False, expected_kind="any")
    try:
        path.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise StageValidationError(f"cannot inspect {label}") from exc
    raise StageValidationError(f"{label} must be absent")


def read_bytes(root: Path, relative: str, *, missing_label: str | None = None) -> bytes:
    path = checked_path(root, relative, missing_label=missing_label)
    try:
        return path.read_bytes()
    except OSError as exc:
        raise StageValidationError(f"cannot read repository file: {relative}") from exc


def read_text(
    root: Path,
    relative: str,
    *,
    encoding: str = "utf-8",
    missing_label: str | None = None,
) -> str:
    raw = read_bytes(root, relative, missing_label=missing_label)
    try:
        return raw.decode(encoding)
    except UnicodeError as exc:
        raise StageValidationError(f"invalid {encoding} text: {relative}") from exc


def load(
    root: Path,
    relative: str,
    *,
    missing_label: str | None = None,
) -> dict[str, Any]:
    """Load strict JSON through the component-safe root-relative boundary."""

    raw = read_bytes(Path(root), relative, missing_label=missing_label)
    label = relative
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise StageValidationError(f"invalid strict JSON: {label}") from exc
    require(isinstance(value, dict), f"JSON root must be object: {label}")
    return value


def sha256(root: Path, relative: str) -> str:
    return hashlib.sha256(read_bytes(Path(root), relative)).hexdigest()


def file_sha256_map(root: Path, relatives: Iterable[str]) -> dict[str, str]:
    """Bind a stage bundle to exact current raw bytes without path aliases."""

    paths = tuple(relatives)
    require(len(paths) == len(frozenset(paths)), "stage bundle contains duplicate path")
    return {relative: sha256(root, relative) for relative in paths}


def alignment_review_target_files(root: Path) -> dict[str, str]:
    """The alignment review covers its record and every active aligned consumer."""

    return file_sha256_map(
        root,
        (ALIGNMENT_RELATIVE, *_post_approval.ALIGNED_CONSUMERS),
    )


def require_exact(mapping: object, keys: Iterable[str], label: str) -> dict[str, Any]:
    require(isinstance(mapping, dict), f"{label} must be object")
    require(set(mapping) == frozenset(keys), f"{label} key set drift")
    return mapping


def require_text(value: object, label: str, *, nonempty: bool = True) -> str:
    require(isinstance(value, str), f"{label} must be text")
    require(not nonempty or bool(value), f"{label} must be nonempty text")
    return value


def require_int(value: object, label: str) -> int:
    require(isinstance(value, int) and not isinstance(value, bool), f"{label} must be integer")
    return value


def require_bool(value: object, label: str) -> bool:
    require(type(value) is bool, f"{label} must be boolean")
    return value


def require_sha256(value: object, label: str) -> str:
    require(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
        f"{label} is not lowercase SHA-256",
    )
    return value


def require_commit(value: object, label: str) -> str:
    require(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None,
        f"{label} is not a full Git commit",
    )
    return value


def require_gate_review(
    root: Path,
    mapping: dict[str, Any],
    field: str,
    gate_id: str,
    *,
    target_files: dict[str, str],
    predecessor_files: dict[str, str],
    lineage: list[Any],
    expected_pr_number: int | None = None,
) -> Any:
    """Validate and consume one fixed, hash-bound external-review capture.

    Stage records carry only the digest of the fixed evidence object.  Review
    metadata is parsed from the independently captured object and reconciled
    with its raw GitHub payloads by ``r11a_github_review_evidence``; editable
    stage JSON never supplies review event, verdict, head, tree, or identity.
    ``lineage`` makes review identities single-use across the entire call
    graph rather than merely distinct from the immediately preceding gate.
    """

    require(gate_id in REVIEW_EVIDENCE_PATHS, f"unknown review gate: {gate_id}")
    gate_index = REVIEW_GATE_IDS.index(gate_id)
    observed_lineage = tuple(getattr(identity, "gate_id", None) for identity in lineage)
    require(
        observed_lineage == REVIEW_GATE_IDS[:gate_index],
        f"{gate_id} does not consume the exact immediate review-gate lineage",
    )
    reviewed_target_files = dict(target_files)
    reviewed_predecessor_files = dict(predecessor_files)
    if gate_index:
        predecessor_evidence = REVIEW_EVIDENCE_PATHS[REVIEW_GATE_IDS[gate_index - 1]]
        require(
            predecessor_evidence not in reviewed_target_files,
            "review target duplicates its immediate-predecessor evidence binding",
        )
        predecessor_identity = lineage[-1]
        predecessor_digest = require_sha256(
            getattr(predecessor_identity, "evidence_sha256", None),
            "immediate-predecessor review-evidence SHA-256",
        )
        reviewed_target_files[predecessor_evidence] = predecessor_digest
    if gate_index >= 2:
        inherited_evidence = REVIEW_EVIDENCE_PATHS[REVIEW_GATE_IDS[gate_index - 2]]
        require(
            inherited_evidence not in reviewed_predecessor_files,
            "review predecessor duplicates its inherited review-evidence binding",
        )
        inherited_identity = lineage[-2]
        inherited_digest = require_sha256(
            getattr(inherited_identity, "evidence_sha256", None),
            "inherited predecessor review-evidence SHA-256",
        )
        reviewed_predecessor_files[inherited_evidence] = inherited_digest
    expected_sha = require_sha256(mapping[field], field)
    identity = _review_evidence.validate_gate_evidence(
        Path(root),
        gate_id,
        expected_evidence_sha256=expected_sha,
        expected_pr_number=expected_pr_number,
        expected_target_files=reviewed_target_files,
        expected_predecessor_files=reviewed_predecessor_files,
        consumed=tuple(lineage),
    )
    lineage.append(identity)
    return identity


def require_all_false(
    mapping: object,
    label: str,
    *,
    keys: Iterable[str] | None = None,
) -> dict[str, Any]:
    require(isinstance(mapping, dict), f"{label} must be object")
    if keys is not None:
        require_exact(mapping, keys, label)
    require(bool(mapping), f"{label} must be nonempty object")
    require(
        all(type(value) is bool and value is False for value in mapping.values()),
        f"{label} contains opened authority",
    )
    return mapping


def stage_authority(mapping: object, label: str) -> dict[str, Any]:
    return require_all_false(mapping, label, keys=DOWNSTREAM_AUTHORITY_KEYS)


def trading_authority(mapping: object, label: str) -> dict[str, Any]:
    return require_all_false(mapping, label, keys=TRADING_AUTHORITY_KEYS)


def successor_permissions(paths: Iterable[str]) -> frozenset[str]:
    observed = frozenset(paths)
    require(observed <= KNOWN_SUCCESSOR_PATHS, "unknown successor authority path requested")
    return observed


def validate_alignment_context(
    root: Path = ROOT,
    *,
    permitted_successor_paths: frozenset[str] = frozenset(),
    runtime_pricing_projection_permitted: bool = False,
) -> dict[str, Any]:
    permitted = successor_permissions(permitted_successor_paths)
    try:
        return _post_approval.validate_alignment(
            root,
            permitted_successor_paths=permitted,
            runtime_pricing_projection_permitted=runtime_pricing_projection_permitted,
        )
    except TypeError as exc:
        raise StageValidationError("post-approval alignment context API mismatch") from exc


def implementation(root: Path = ROOT) -> dict[str, Any]:
    """Validate the immutable historical R7 implementation snapshot as history."""

    value = load(root, IMPLEMENTATION_RELATIVE)
    require(
        value.get("implementation_id")
        == "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-CORRECTIVE-R7",
        "historical R7 implementation ID drift",
    )
    require(value.get("diagnostic_id") == DIAGNOSTIC_ID, "historical R7 diagnostic ID drift")
    require(
        value.get("status")
        == "CORRECTIVE_R7_IMPLEMENTATION_SEALED_AWAITING_CLEAN_CONTEXT_REVIEW_NO_EXECUTION",
        "historical R7 implementation status drift",
    )
    require(value.get("implementation_sealed") is True, "historical R7 implementation is not sealed")
    require(value.get("implementation_review_green") is False, "historical R7 review snapshot rewritten")
    require(value.get("owner_approval_eligible") is False, "historical R7 approval eligibility rewritten")
    require(value.get("pricing_binding_pending") is True, "historical R7 pricing state rewritten")
    require(value.get("owner_approval_present") is False, "historical R7 approval state rewritten")
    require(value.get("workflow_installed_under_dot_github") is False, "historical R7 workflow state rewritten")
    require(value.get("execution_release_present") is False, "historical R7 release state rewritten")
    require(value.get("canonical_activation_present") is False, "historical R7 activation state rewritten")
    require(value.get("workflow_candidate_sha256") == APPROVED_WORKFLOW_SHA, "historical R7 workflow hash drift")
    return value


def pricing_projection(root: Path = ROOT) -> dict[str, Any]:
    source_raw = read_bytes(root, PRICING_SOURCE_RELATIVE)
    require(
        hashlib.sha256(source_raw).hexdigest() == APPROVED_PRICING_SOURCE_SHA,
        "approved runtime pricing source hash drift",
    )
    target_raw = read_bytes(
        root,
        PRICING_TARGET_RELATIVE,
        missing_label="runtime pricing projection is absent",
    )
    require(target_raw == source_raw, "runtime pricing projection differs from approved candidate")
    value = load(root, PRICING_TARGET_RELATIVE)
    require(value.get("status") == "BOUND_CURRENT_OFFICIAL_SNAPSHOT", "runtime pricing projection is not bound")
    require(value.get("installed_at_runtime_snapshot_path") is False, "pricing source snapshot semantics rewritten")
    require(value.get("owner_approval_present") is False, "pricing source historical approval state rewritten")
    require(value.get("runtime_release") is False, "pricing source historical release state rewritten")
    require(value.get("runtime_activation") is False, "pricing source historical activation state rewritten")
    require(value.get("projected_eur_micros_at_frozen_maximum") == 383757, "pricing projection drift")
    require(value.get("owner_approval_maximum_eur_micros") == 500000, "pricing owner budget drift")
    require(value.get("monthly_recurring_budget_eur_micros") == 0, "pricing recurring budget drift")
    return value


def exact_selection(root: Path = ROOT) -> dict[str, Any]:
    value = load(root, SELECTION_RELATIVE)
    targets = value.get("exact_targets")
    require(isinstance(targets, list) and len(targets) == 72, "selection is not exact 72 targets")
    return value
