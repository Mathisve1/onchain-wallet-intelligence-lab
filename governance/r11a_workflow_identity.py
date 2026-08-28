#!/usr/bin/env python3
"""Fail-closed R11A workflow identity and live project-state checks.

The owner-approved OIDC policy binds the workflow display name.  Repository
validation therefore treats the complete pre-installation workflow directory
as an authenticated baseline and permits exactly one later addition: the
canonical installed workflow with byte-for-byte owner-approved contents.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


CANDIDATE_WORKFLOW_RELATIVE = (
    "research/archive_inventory/r11a_corrective/workflows/"
    "hyperliquid-archive-r11a-identity-boundary-diagnostic-r7.yml"
)
CANONICAL_INSTALLED_WORKFLOW_RELATIVE = (
    ".github/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic.yml"
)
TRUSTED_WORKFLOW_NAME = "Hyperliquid Archive R11A Identity Boundary Diagnostic"
APPROVED_WORKFLOW_SHA256 = (
    "c10b810304d6cdbc68f23cb3db113b57580d34f0f74e781aefa2140edd0b5e65"
)
PREINSTALL_WORKFLOW_COUNT = 24
PREINSTALL_WORKFLOW_INVENTORY_SHA256 = (
    "6b0cd7878bf656e1d6e6c24b39c983ccd2dd6e2324ba5680f8a4b96c98f074e6"
)
PROJECT_STATE_RELATIVE = "PROJECT_STATE.md"

_WORKFLOW_DIRECTORY_RELATIVE = ".github/workflows"
_SAFE_WORKFLOW_FILENAME = re.compile(r"[a-z0-9][a-z0-9._-]*\.(?:yml|yaml)\Z")
_MACHINE_STATE_ROW = re.compile(r"([a-z][a-z0-9_]*) = ([^\x00\r\n]+)\Z")
_TRUSTED_IDENTITY_TOKENS = (
    "hyperliquid",
    "archive",
    "r11a",
    "identity",
    "boundary",
    "diagnostic",
)


class R11AWorkflowIdentityError(RuntimeError):
    pass


class R11AProjectStateError(RuntimeError):
    pass


def _workflow_require(condition: bool, message: str) -> None:
    if not condition:
        raise R11AWorkflowIdentityError(message)


def _state_require(condition: bool, message: str) -> None:
    if not condition:
        raise R11AProjectStateError(message)


def _checked_root(root: Path, error_type: type[RuntimeError]) -> Path:
    lexical = Path(root)
    if not lexical.is_absolute() or lexical.anchor != os.sep or ".." in lexical.parts:
        raise error_type("repository root must be an absolute canonical lexical path")
    current = Path(lexical.anchor)
    for part in lexical.parts[1:]:
        current /= part
        try:
            information = current.lstat()
        except OSError as exc:
            raise error_type(f"repository root path component is absent: {current}") from exc
        if stat.S_ISLNK(information.st_mode):
            raise error_type(f"repository root path component is symlink: {current}")
        if not stat.S_ISDIR(information.st_mode):
            raise error_type(f"repository root path component is not directory: {current}")
    return lexical


def _relative_parts(relative: str, error_type: type[RuntimeError]) -> tuple[str, ...]:
    if type(relative) is not str or not relative or "\\" in relative or "\x00" in relative:
        raise error_type(f"unsafe repository-relative path: {relative!r}")
    pure = PurePosixPath(relative)
    if (
        pure.is_absolute()
        or pure.as_posix() != relative
        or not pure.parts
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise error_type(f"unsafe repository-relative path: {relative!r}")
    return pure.parts


def _inspect_path(
    root: Path,
    relative: str,
    error_type: type[RuntimeError],
) -> tuple[Path, os.stat_result]:
    lexical = _checked_root(root, error_type)
    current = lexical
    parts = _relative_parts(relative, error_type)
    for index, part in enumerate(parts):
        current /= part
        try:
            information = current.lstat()
        except OSError as exc:
            raise error_type(f"required path is absent: {relative}") from exc
        component = "/".join(parts[: index + 1])
        if stat.S_ISLNK(information.st_mode):
            raise error_type(f"symlink path component: {component}")
        if index < len(parts) - 1 and not stat.S_ISDIR(information.st_mode):
            raise error_type(f"non-directory path component: {component}")
    return current, information


def _required_file(
    root: Path,
    relative: str,
    error_type: type[RuntimeError],
) -> Path:
    path, information = _inspect_path(root, relative, error_type)
    if not stat.S_ISREG(information.st_mode):
        raise error_type(f"required file is not regular: {relative}")
    if information.st_nlink != 1:
        raise error_type(f"security-critical file has hard-link alias: {relative}")
    return path


def _required_directory(
    root: Path,
    relative: str,
    error_type: type[RuntimeError],
) -> Path:
    path, information = _inspect_path(root, relative, error_type)
    if not stat.S_ISDIR(information.st_mode):
        raise error_type(f"required directory is not directory: {relative}")
    return path


def _read_file(root: Path, relative: str, error_type: type[RuntimeError]) -> bytes:
    path = _required_file(root, relative, error_type)
    try:
        return path.read_bytes()
    except OSError as exc:
        raise error_type(f"cannot read security-critical file: {relative}") from exc


def _contains_trusted_identity(text: str) -> bool:
    tokens = tuple(re.findall(r"[a-z0-9]+", text.casefold()))
    width = len(_TRUSTED_IDENTITY_TOKENS)
    return any(
        tokens[index : index + width] == _TRUSTED_IDENTITY_TOKENS
        for index in range(len(tokens) - width + 1)
    )


def validate_workflow_identity_inventory(
    root: Path,
    *,
    canonical_installed: bool,
) -> dict[str, Any]:
    """Validate the exact pre/post-installation workflow identity surface."""

    _workflow_require(
        type(canonical_installed) is bool,
        "canonical workflow installation mode must be exact boolean",
    )
    lexical = _checked_root(Path(root), R11AWorkflowIdentityError)
    candidate = _read_file(
        lexical,
        CANDIDATE_WORKFLOW_RELATIVE,
        R11AWorkflowIdentityError,
    )
    _workflow_require(
        hashlib.sha256(candidate).hexdigest() == APPROVED_WORKFLOW_SHA256,
        "approved R11A workflow candidate hash drift",
    )
    expected_name_line = f"name: {TRUSTED_WORKFLOW_NAME}\n".encode("ascii")
    _workflow_require(
        candidate.startswith(expected_name_line),
        "approved R11A workflow candidate name drift",
    )

    directory = _required_directory(
        lexical,
        _WORKFLOW_DIRECTORY_RELATIVE,
        R11AWorkflowIdentityError,
    )
    try:
        entries = list(os.scandir(directory))
    except OSError as exc:
        raise R11AWorkflowIdentityError("cannot inventory installed workflows") from exc
    try:
        entries.sort(key=lambda entry: entry.name.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise R11AWorkflowIdentityError("workflow filename is not canonical UTF-8") from exc

    baseline_rows: list[bytes] = []
    canonical_count = 0
    for entry in entries:
        try:
            entry.name.encode("ascii")
        except UnicodeEncodeError as exc:
            raise R11AWorkflowIdentityError(
                f"non-ASCII workflow filename prohibited: {entry.name}"
            ) from exc
        _workflow_require(
            _SAFE_WORKFLOW_FILENAME.fullmatch(entry.name) is not None,
            f"non-canonical workflow filename prohibited: {entry.name}",
        )
        relative = f"{_WORKFLOW_DIRECTORY_RELATIVE}/{entry.name}"
        try:
            information = entry.stat(follow_symlinks=False)
        except OSError as exc:
            raise R11AWorkflowIdentityError(
                f"cannot inspect workflow entry: {relative}"
            ) from exc
        _workflow_require(
            not stat.S_ISLNK(information.st_mode),
            f"workflow symlink prohibited: {relative}",
        )
        _workflow_require(
            stat.S_ISREG(information.st_mode),
            f"workflow entry is not a regular file: {relative}",
        )
        _workflow_require(
            information.st_nlink == 1,
            f"workflow file has hard-link alias: {relative}",
        )
        raw = _read_file(lexical, relative, R11AWorkflowIdentityError)
        try:
            text = raw.decode("ascii")
        except UnicodeDecodeError as exc:
            raise R11AWorkflowIdentityError(
                f"non-ASCII workflow content prohibited: {relative}"
            ) from exc

        if relative == CANONICAL_INSTALLED_WORKFLOW_RELATIVE:
            canonical_count += 1
            _workflow_require(
                canonical_installed,
                "R11A runtime workflow is installed before its installation stage",
            )
            _workflow_require(
                raw == candidate,
                "installed R11A workflow differs from owner-approved candidate",
            )
            continue

        _workflow_require(
            not _contains_trusted_identity(text),
            f"alternate OIDC-trusted workflow identity present: {relative}",
        )
        baseline_rows.append(
            hashlib.sha256(raw).hexdigest().encode("ascii")
            + b"  "
            + relative.encode("ascii")
            + b"\n"
        )

    _workflow_require(
        canonical_count == int(canonical_installed),
        "canonical installed R11A workflow presence does not match stage",
    )
    _workflow_require(
        len(baseline_rows) == PREINSTALL_WORKFLOW_COUNT,
        "pre-installation workflow path/raw-byte inventory drift: count",
    )
    observed_inventory = hashlib.sha256(b"".join(baseline_rows)).hexdigest()
    _workflow_require(
        observed_inventory == PREINSTALL_WORKFLOW_INVENTORY_SHA256,
        "pre-installation workflow path/raw-byte inventory drift",
    )
    return {
        "canonical_installed": canonical_installed,
        "canonical_installed_count": canonical_count,
        "preinstall_workflow_count": len(baseline_rows),
        "preinstall_workflow_inventory_sha256": observed_inventory,
        "trusted_workflow_name": TRUSTED_WORKFLOW_NAME,
        "approved_workflow_sha256": APPROVED_WORKFLOW_SHA256,
    }


def parse_project_state(root: Path) -> dict[str, str]:
    """Parse the unique strict machine-readable block in PROJECT_STATE.md."""

    raw = _read_file(
        Path(root),
        PROJECT_STATE_RELATIVE,
        R11AProjectStateError,
    )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise R11AProjectStateError("PROJECT_STATE.md is not UTF-8") from exc
    _state_require(text.endswith("\n"), "PROJECT_STATE.md lacks terminal LF")
    lines = text.splitlines()
    openings = [index for index, line in enumerate(lines) if line == "```text"]
    _state_require(
        len(openings) == 1,
        "PROJECT_STATE.md must contain exactly one machine-state block",
    )
    opening = openings[0]
    closings = [
        index for index in range(opening + 1, len(lines)) if lines[index] == "```"
    ]
    _state_require(
        len(closings) == 1,
        "PROJECT_STATE.md machine-state block has ambiguous closure",
    )

    result: dict[str, str] = {}
    for row in lines[opening + 1 : closings[0]]:
        match = _MACHINE_STATE_ROW.fullmatch(row)
        _state_require(match is not None, f"malformed project-state row: {row!r}")
        key, value = match.groups()
        _state_require(key not in result, f"duplicate project-state key: {key}")
        _state_require(value == value.strip(), f"project-state value has edge whitespace: {key}")
        result[key] = value
    _state_require(bool(result), "PROJECT_STATE.md machine-state block is empty")
    return result


def validate_post_g2_project_state(
    root: Path,
    *,
    approval_id: str,
    approval_text_sha256: str,
    approval_record: Mapping[str, Any],
    live_stage_state: Mapping[str, bool],
) -> dict[str, str]:
    """Cross-check live post-G2 state against the immutable approval record."""

    _state_require(type(approval_id) is str and bool(approval_id), "approval ID is invalid")
    _state_require(
        re.fullmatch(r"[0-9a-f]{64}", approval_text_sha256) is not None,
        "approval text SHA-256 is invalid",
    )
    _state_require(isinstance(approval_record, Mapping), "approval record is not a mapping")
    stage_keys = (
        "r11a_successor_role_created",
        "r11a_successor_role_attestation_present",
        "r11a_sts_preflight",
        "r11a_workflow_installed",
        "r11a_release_present",
        "r11a_runtime_release",
        "r11a_runtime_activation",
        "r11a_runtime_binding",
        "r11a_runtime_binding_review",
    )
    _state_require(
        tuple(live_stage_state) == stage_keys,
        "live project-state projection has unexpected fields or order",
    )
    _state_require(
        all(type(value) is bool for value in live_stage_state.values()),
        "live project-state projection must contain exact booleans",
    )
    _state_require(
        live_stage_state["r11a_successor_role_created"]
        == live_stage_state["r11a_successor_role_attestation_present"],
        "role creation and role-attestation state contradict",
    )
    _state_require(
        live_stage_state["r11a_release_present"]
        == live_stage_state["r11a_runtime_release"],
        "release-present and runtime-release state contradict",
    )
    monotonic = (
        live_stage_state["r11a_successor_role_attestation_present"],
        live_stage_state["r11a_sts_preflight"],
        live_stage_state["r11a_workflow_installed"],
        live_stage_state["r11a_runtime_release"],
        live_stage_state["r11a_runtime_activation"],
        live_stage_state["r11a_runtime_binding"],
        live_stage_state["r11a_runtime_binding_review"],
    )
    _state_require(
        not any(not earlier and later for earlier, later in zip(monotonic, monotonic[1:])),
        "live future-stage project state skips an immediate predecessor",
    )
    state = parse_project_state(Path(root))
    expected = {
        "r11a_owner_approval_ready": "true",
        "r11a_owner_approval_id": approval_id,
        "r11a_owner_approval_text_sha256": approval_text_sha256,
        "r11a_owner_approval_present": "true",
        "r11a_owner_approval_record_review_complete": "true",
        "r11a_canonical_approval_record_present": "true",
        "r11a_execution_authorized_by_this_approval": "false",
        "r11a_diagnostic_execution": "false",
        "r11a_execution_evidence": "false",
        "r11a_empirical_root_cause": "UNKNOWN_PENDING_DIAGNOSTIC",
        "r11a_deduplication": "false",
        "r11a_replay_suppression": "false",
        "r11a_r11b_repair": "false",
        "r11a_wallet_features": "false",
        "r11a_wallet_ranking": "false",
        "r11a_candidate_shortlisting": "false",
        "r11a_pnl_alpha": "false",
        "r11a_copyability": "false",
        "r11a_entity_clustering": "false",
        "r11a_strategy_inference": "false",
        "r11a_integration": "false",
        "r11a_paper_trading": "false",
        "r11a_shadow_trading": "false",
        "r11a_live_trading": "false",
        "r11a_leverage": "false",
        "r11a_capital_allocation": "false",
        "r11_closed": "false",
        "r12_ready": "false",
    }
    expected.update(
        {key: "true" if live_stage_state[key] else "false" for key in stage_keys}
    )
    for key, value in expected.items():
        _state_require(key in state, f"required post-G2 project-state key absent: {key}")
        _state_require(state[key] == value, f"post-G2 project-state contradiction: {key}")

    _state_require(
        approval_record.get("owner_approval_present") is True,
        "canonical approval record does not contain owner approval",
    )
    _state_require(
        approval_record.get("canonical_approval_record_present") is True,
        "canonical approval record presence is false",
    )
    _state_require(
        approval_record.get("execution_authorized_by_this_approval") is False,
        "canonical owner approval opens execution authority",
    )
    current_authority = approval_record.get("current_authority")
    _state_require(
        isinstance(current_authority, Mapping) and bool(current_authority),
        "canonical approval current-authority map is absent",
    )
    _state_require(
        all(type(value) is bool and value is False for value in current_authority.values()),
        "canonical approval current authority is not fully closed",
    )
    return state


__all__ = [
    "APPROVED_WORKFLOW_SHA256",
    "CANONICAL_INSTALLED_WORKFLOW_RELATIVE",
    "CANDIDATE_WORKFLOW_RELATIVE",
    "PREINSTALL_WORKFLOW_COUNT",
    "PREINSTALL_WORKFLOW_INVENTORY_SHA256",
    "PROJECT_STATE_RELATIVE",
    "R11AProjectStateError",
    "R11AWorkflowIdentityError",
    "TRUSTED_WORKFLOW_NAME",
    "parse_project_state",
    "validate_post_g2_project_state",
    "validate_workflow_identity_inventory",
]
