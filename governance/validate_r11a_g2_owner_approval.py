#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

# Keep the caller-visible lexical path.  validate() deliberately rejects a
# repository root reached through a symlink instead of resolving it away.
ROOT = Path(__file__).absolute().parents[1]

APPROVAL_ID = "APPROVE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001"
PACKAGE_ID = "R11A-G1-OWNER-APPROVAL-PACKAGE-001"
DIAGNOSTIC_ID = "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-002"
REPOSITORY = "Mathisve1/onchain-wallet-intelligence-lab"

SOFTWARE_HEAD = "443500de54917417276c39a635ae444458d03b0b"
SOFTWARE_TREE = "516d72a43545c454ef163e02ee1146005e6cfb5c"
SOFTWARE_REVIEW = 5019067044
READINESS_HEAD = "4da7e67b600ef1ca10fb4f2e62b493d81d4dfcc3"
READINESS_TREE = "b4c7b1524e8856450028e53be7912a88d3a675e1"
READINESS_REVIEW = 5027672461

APPROVAL_DIR = "research/archive_inventory/r11a_approval"
APPROVAL_JSON = f"{APPROVAL_DIR}/{APPROVAL_ID}.json"
APPROVAL_TEXT = f"{APPROVAL_DIR}/{APPROVAL_ID}.txt"
PACKAGE = "research/archive_inventory/r11a_g1/R11A_G1_OWNER_APPROVAL_PACKAGE.json"
SOURCE_STATEMENT = "research/archive_inventory/r11a_g1/R11A_G1_OWNER_APPROVAL_STATEMENT.txt"
STATUS = "research/archive_inventory/r11a_g1/R11A_G1_STATUS.json"
ENVELOPE = "research/archive_inventory/r11a_g1/R11A_G1_EXECUTION_ENVELOPE.json"
PRICING = "research/archive_inventory/r11a_g1/R11A_G1_PRICING_EUR_BINDING.json"
RUNTIME_PRICING = "research/archive_inventory/r11a_g1/R11A_G1_RUNTIME_PRICING_SNAPSHOT_CANDIDATE.json"
PERMISSION = "research/archive_inventory/r11a_corrective/R11A_PERMISSION_POLICY.json"
TRUST = "research/archive_inventory/r11a_corrective/R11A_OIDC_TRUST_POLICY.json"
WORKFLOW = "research/archive_inventory/r11a_corrective/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic-r7.yml"
ALIGNMENT_DIR = "research/archive_inventory/r11a_alignment"
ALIGNMENT_PATH = f"{ALIGNMENT_DIR}/R11A_POST_APPROVAL_VALIDATOR_ALIGNMENT.json"

PACKAGE_SHA = "a31c09cb73b3c176c360a8218aa1eae2faf6e02772b2ca1ff35cfd0babedb24f"
HISTORICAL_G1_STATUS_SHA = "675a11be85dc1f7fc8db18c59dcf7027a32da5241ed44167902767de6121995f"
APPROVAL_STATEMENT_SHA = "16f9f2c31ff90952033251d917884b1ca55771511e82e4b813414dc1a3f807d3"
APPROVAL_RECEIPT_SHA = "531e61130b612fd12503e60ff56d1c3d51b05a64bb2785f1e10fa9c5471c7ae6"

EXPECTED_BOUND_FILES = {
    "research/archive_inventory/r11a_v2/R11A_CORRECTIVE_PREREGISTRATION_AMENDMENT.json": "bdd610c678189e8098381d8c4a0fd12296bf2e0cd8e9ec0fed375b073872552f",
    "research/archive_inventory/r11a_v2/R11A_V2_PREREGISTRATION_BINDINGS.json": "f60f7d6eac5f5a4633a5453c1c79bd84a54add69d1395d9048658450211bd0ba",
    "research/archive_inventory/r11/R11_72H_SELECTION.json": "7c134f4b62f547904126a5f810c177484dceeffa246d53c5c35944367d563eb2",
    "research/archive_inventory/r11_evidence/run-31436753081/r11-result.json": "9d3266eb53791d83df29b6ec3ae5f33c254b29a8182f2e6be7e3261c02686862",
    PERMISSION: "2769afe520efff6f0b619fff352d2cf13d412d96d6c4642fcfc61a8165787e6a",
    TRUST: "375e224b269a62873afb4516651a259483feed4f211e9184272cb2af91513668",
    "research/archive_inventory/r11a_corrective/R11A_ROLE_DECISION.json": "20f9895c83c1d61c79640ed551afd2458fa276502bf3eb9e7f8f3aa040d83d8f",
    "research/archive_inventory/r11a_corrective/R11A_DEPENDENCIES.json": "ce9387377db1f372c6425849549c25e2e47bf24e336510bca06892661e045d6a",
    "research/archive_inventory/r11a_corrective/R11A_RESOURCE_FEASIBILITY_R3.json": "fa71f17591caa0cf939c163733b6f2d87835a06b2f223421b6a6c07cb8d76efb",
    WORKFLOW: "c10b810304d6cdbc68f23cb3db113b57580d34f0f74e781aefa2140edd0b5e65",
    ENVELOPE: "89631f04394805bdf80be0a3784b1cc174eb0fe20e0627bc4eff63cc5f649b2e",
    PRICING: "3459dbfe25d2e7244823344312de5025b7064928c6f436fbe751c7299ea41574",
    RUNTIME_PRICING: "d5043062386b3d70f695f09c917f11719512918c56f318cace1e0530b709ac43",
    SOURCE_STATEMENT: APPROVAL_STATEMENT_SHA,
}

CANONICAL_FUTURE_AUTHORITY_PATHS = (
    "research/archive_inventory/r11a_role_attestation/R11A_SUCCESSOR_ROLE_OPERATOR_ATTESTATION.json",
    "research/archive_inventory/r11a_role_preflight/R11A_STS_PREFLIGHT_CANDIDATE.json",
    "research/archive_inventory/r11a_role_preflight/R11A_STS_PREFLIGHT_RELEASE.json",
    "research/archive_inventory/r11a_role_preflight/R11A_SUCCESSOR_ROLE_STS_PREFLIGHT_ATTESTATION.json",
    "research/archive_inventory/r11a_role_preflight/R11A_STS_PREFLIGHT_RELEASE_CONSUMPTION.json",
    "research/archive_inventory/r11a_workflow_installation/R11A_WORKFLOW_INSTALLATION_CONTRACT.json",
    "research/archive_inventory/r11a_runtime/R11A_RUNTIME_BINDING_R7.json",
    "research/archive_inventory/r11a_runtime/R11A_EXECUTION_RELEASE.json",
    "research/archive_inventory/r11a_runtime/R11A_EXECUTION_RELEASE.sha256",
    "research/archive_inventory/r11a_runtime/R11A_CANONICAL_ACTIVATION.json",
    "research/archive_inventory/r11a_runtime/R11A_EXECUTION_RELEASE_CANDIDATE.json",
    "research/archive_inventory/r11a_runtime/R11A_EXECUTION_RELEASE_CONSUMPTION.json",
)

PROHIBITED_AUTHORITY_NAMESPACES = (
    "research/archive_inventory/r11a_role_attestation",
    "research/archive_inventory/r11a_role_preflight",
    "research/archive_inventory/r11a_workflow_installation",
    "research/archive_inventory/r11a_runtime",
    "research/archive_inventory/r11a_evidence",
    "research/archive_inventory/r11a_v2_approval",
    "research/archive_inventory/r11a_v2_runtime",
    "research/archive_inventory/r11a_v2_evidence",
)

ALLOWED_R11A_NAMESPACES = frozenset(
    {
        "r11a",
        "r11a_alignment",
        "r11a_approval",
        "r11a_corrective",
        "r11a_g1",
        "r11a_implementation",
        "r11a_v2",
    }
)

ALLOWED_R11A_DIRECTORIES = frozenset(
    {
        "research/archive_inventory/r11a",
        ALIGNMENT_DIR,
        "research/archive_inventory/r11a_approval",
        "research/archive_inventory/r11a_corrective",
        "research/archive_inventory/r11a_corrective/workflows",
        "research/archive_inventory/r11a_g1",
        "research/archive_inventory/r11a_implementation",
        "research/archive_inventory/r11a_implementation/workflows",
        "research/archive_inventory/r11a_v2",
    }
)

PROHIBITED_INSTALLED_WORKFLOWS = (
    ".github/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic.yml",
    ".github/workflows/hyperliquid-archive-r11a-v2-identity-boundary-diagnostic.yml",
)
INSTALLED_WORKFLOW = PROHIBITED_INSTALLED_WORKFLOWS[0]
KNOWN_FUTURE_STAGE_PATHS = frozenset(
    {*CANONICAL_FUTURE_AUTHORITY_PATHS, *PROHIBITED_INSTALLED_WORKFLOWS}
)

R4_WORKFLOW_CANDIDATE = (
    "research/archive_inventory/r11a_corrective/workflows/"
    "hyperliquid-archive-r11a-identity-boundary-diagnostic-r6.yml"
)
HISTORICAL_IMPLEMENTATION_WORKFLOW_CANDIDATE = (
    "research/archive_inventory/r11a_implementation/workflows/"
    "hyperliquid-archive-r11a-identity-boundary-diagnostic.yml"
)

R11A_DEVELOPMENT_WORKFLOW = ".github/workflows/r11a-r7-dev.yml"
R11A_DEVELOPMENT_WORKFLOW_SHA = (
    "23754917699c0f685f0164b64cc78807ab7872e7fe179982d0f0145da35f74fe"
)
INSTALLED_WORKFLOW_INVENTORY_SHA256 = (
    "89ed9152230a97865f4ac3531156a5cc5dffb09e9d942586d043215b5332dcb6"
)

CANONICAL_R11A_JSON_PATHS = frozenset(
    {
        "research/archive_inventory/r11a/R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_PREREGISTRATION.json",
        "research/archive_inventory/r11a/R11A_IDENTITY_DECISION_DOSSIER.json",
        "research/archive_inventory/r11a/R11_ROOT_CAUSE_STATUS.json",
        ALIGNMENT_PATH,
        APPROVAL_JSON,
        "research/archive_inventory/r11a_corrective/R11A_CORRECTIVE_IMPLEMENTATION_CONTRACT.json",
        "research/archive_inventory/r11a_corrective/R11A_CORRECTIVE_IMPLEMENTATION_CONTRACT_R7.json",
        "research/archive_inventory/r11a_corrective/R11A_CORRECTIVE_STATUS.json",
        "research/archive_inventory/r11a_corrective/R11A_CORRECTIVE_STATUS_R7.json",
        "research/archive_inventory/r11a_corrective/R11A_DEPENDENCIES.json",
        PERMISSION,
        TRUST,
        "research/archive_inventory/r11a_corrective/R11A_PRICING_EUR_SNAPSHOT.json",
        "research/archive_inventory/r11a_corrective/R11A_RED_REVIEW_FINDINGS.json",
        "research/archive_inventory/r11a_corrective/R11A_RESOURCE_FEASIBILITY_R3.json",
        "research/archive_inventory/r11a_corrective/R11A_ROLE_DECISION.json",
        ENVELOPE,
        PACKAGE,
        PRICING,
        RUNTIME_PRICING,
        STATUS,
        "research/archive_inventory/r11a_implementation/R11A_DEPENDENCIES.json",
        "research/archive_inventory/r11a_implementation/R11A_IMPLEMENTATION_CONTRACT.json",
        "research/archive_inventory/r11a_implementation/R11A_OIDC_TRUST_POLICY.json",
        "research/archive_inventory/r11a_implementation/R11A_PERMISSION_POLICY.json",
        "research/archive_inventory/r11a_implementation/R11A_RESOURCE_FEASIBILITY.json",
        "research/archive_inventory/r11a_implementation/R11A_ROLE_DECISION.json",
        "research/archive_inventory/r11a_v2/R11A_CORRECTIVE_PREREGISTRATION_AMENDMENT.json",
        "research/archive_inventory/r11a_v2/R11A_V2_PREREGISTRATION_BINDINGS.json",
        "research/archive_inventory/r11a_v2/R11A_V2_STATUS.json",
    }
)

ALLOWED_R11A_AUTHORITY_NAMED_PATHS = frozenset(
    {
        *CANONICAL_R11A_JSON_PATHS,
        APPROVAL_TEXT,
        SOURCE_STATEMENT,
        "research/archive_inventory/r11a/R11A_GOVERNANCE_AND_EVIDENCE_CLOSURE_CHECKLIST.md",
        "research/archive_inventory/r11a_implementation/R11A_ROLE_DECISION.md",
        R4_WORKFLOW_CANDIDATE,
        WORKFLOW,
        HISTORICAL_IMPLEMENTATION_WORKFLOW_CANDIDATE,
    }
)

R11A_AUTHORITY_NAME_TOKENS = frozenset(
    {
        "approval",
        "authority",
        "runtime",
        "role",
        "attestation",
        "preflight",
        "workflow",
        "installation",
        "release",
        "activation",
        "evidence",
        "diagnostic",
        "artifact",
        "dispatch",
        "sts",
    }
)

OPEN_AUTHORITY_TRUE_KEYS = frozenset(
    {
        "owner_approval_present",
        "canonical_approval_record_present",
        "execution_authorized_by_this_approval",
        "successor_role_created",
        "role_created",
        "role_created_and_configured",
        "aws_iam_mutation",
        "aws_oidc",
        "sts",
        "workflow_installed",
        "runtime_binding_present",
        "runtime_release",
        "execution_release_present",
        "runtime_activation",
        "canonical_activation_present",
        "workflow_dispatch",
        "requester_pays",
        "get_object",
        "object_body_download",
        "decompression",
        "diagnostic_execution",
        "diagnostic_artifact_retention",
        "rerun",
        "r11_closed",
        "r12_ready",
        "integration",
        "paper",
        "shadow",
        "live",
        "leverage",
        "capital_allocation",
        "withdrawals_or_transfers",
    }
)

APPROVAL_REFERENCE_JSON_ALLOWLIST = frozenset({APPROVAL_JSON, STATUS})
APPROVAL_TEXT_COPY_ALLOWLIST = frozenset({APPROVAL_TEXT, SOURCE_STATEMENT})
ALLOWED_R11A_DATA_PATHS = frozenset(
    {
        *CANONICAL_R11A_JSON_PATHS,
        *APPROVAL_TEXT_COPY_ALLOWLIST,
        R4_WORKFLOW_CANDIDATE,
        WORKFLOW,
        HISTORICAL_IMPLEMENTATION_WORKFLOW_CANDIDATE,
    }
)
APPROVAL_ID_DATA_REFERENCE_ALLOWLIST = frozenset(
    {
        APPROVAL_JSON,
        APPROVAL_TEXT,
        SOURCE_STATEMENT,
        PACKAGE,
        STATUS,
        R4_WORKFLOW_CANDIDATE,
        WORKFLOW,
        "governance/REPOSITORY_MANIFEST.sha256",
        ALIGNMENT_PATH,
        (
            "research/archive_inventory/r11a_corrective/"
            "R11A_CORRECTIVE_IMPLEMENTATION_CONTRACT_R7.json"
        ),
    }
)


class R11AG2ApprovalError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise R11AG2ApprovalError(message)


def _pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in rows:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(token: str) -> Any:
    raise R11AG2ApprovalError(f"non-finite JSON constant: {token}")


def _relative_parts(relative: str) -> tuple[str, ...]:
    require(type(relative) is str and relative != "", "unsafe repository-relative path")
    require("\\" not in relative and "\x00" not in relative, f"unsafe repository-relative path: {relative!r}")
    pure = PurePosixPath(relative)
    require(not pure.is_absolute(), f"unsafe repository-relative path: {relative}")
    require(pure.as_posix() == relative, f"non-canonical repository-relative path: {relative}")
    require(
        bool(pure.parts) and all(part not in {"", ".", ".."} for part in pure.parts),
        f"unsafe repository-relative path: {relative}",
    )
    return pure.parts


def _checked_root(root: Path) -> Path:
    lexical = Path(root)
    require(lexical.is_absolute(), "repository root must be an absolute lexical path")
    require(lexical.anchor == os.sep, "repository root anchor is ambiguous")
    require(".." not in lexical.parts, "repository root contains traversal")
    current = Path(lexical.anchor)
    for part in lexical.parts[1:]:
        current /= part
        try:
            information = current.lstat()
        except OSError as exc:
            raise R11AG2ApprovalError(f"repository root path component is absent: {current}") from exc
        require(
            not stat.S_ISLNK(information.st_mode),
            f"repository root path component is symlink: {current}",
        )
        require(
            stat.S_ISDIR(information.st_mode),
            f"repository root path component is not directory: {current}",
        )
    return lexical


def _inspect_path(
    root: Path,
    relative: str,
    *,
    allow_missing: bool = False,
) -> tuple[Path, os.stat_result | None]:
    lexical_root = _checked_root(root)
    parts = _relative_parts(relative)
    current = lexical_root
    for index, part in enumerate(parts):
        current /= part
        try:
            information = current.lstat()
        except FileNotFoundError as exc:
            if allow_missing:
                return lexical_root / PurePosixPath(relative), None
            raise R11AG2ApprovalError(f"required path absent: {relative}") from exc
        except OSError as exc:
            raise R11AG2ApprovalError(f"cannot inspect security-critical path: {relative}") from exc
        component = "/".join(parts[: index + 1])
        require(
            not stat.S_ISLNK(information.st_mode),
            f"symlink path component: {component}",
        )
        if index < len(parts) - 1:
            require(
                stat.S_ISDIR(information.st_mode),
                f"non-directory path component: {component}",
            )
    return current, information


def _required_file(root: Path, relative: str) -> Path:
    path, information = _inspect_path(root, relative)
    require(
        information is not None and stat.S_ISREG(information.st_mode),
        f"required file is not regular: {relative}",
    )
    require(information.st_nlink == 1, f"security-critical file has hard-link alias: {relative}")
    return path


def _required_directory(root: Path, relative: str) -> Path:
    path, information = _inspect_path(root, relative)
    require(
        information is not None and stat.S_ISDIR(information.st_mode),
        f"required directory is not directory: {relative}",
    )
    return path


def _require_absent(root: Path, relative: str, label: str) -> None:
    _, information = _inspect_path(root, relative, allow_missing=True)
    require(information is None, f"{label}: {relative}")


def _read_bytes(root: Path, relative: str) -> bytes:
    path = _required_file(root, relative)
    try:
        return path.read_bytes()
    except OSError as exc:
        raise R11AG2ApprovalError(f"cannot read security-critical file: {relative}") from exc


def _strict_json_value(raw: bytes, relative: str) -> Any:
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise R11AG2ApprovalError(f"invalid strict JSON: {relative}") from exc


def _strict_json(raw: bytes, relative: str) -> dict[str, Any]:
    value = _strict_json_value(raw, relative)
    require(isinstance(value, dict), f"JSON root is not object: {relative}")
    return value


def load(root: Path, relative: str) -> dict[str, Any]:
    return _strict_json(_read_bytes(root, relative), relative)


def sha256(root: Path, relative: str) -> str:
    return hashlib.sha256(_read_bytes(root, relative)).hexdigest()


def _repository_entries(root: Path) -> Iterator[tuple[str, os.stat_result]]:
    lexical_root = _checked_root(root)
    stack: list[tuple[Path, PurePosixPath | None]] = [(lexical_root, None)]
    while stack:
        directory, prefix = stack.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name.encode("utf-8"), reverse=True)
        except OSError as exc:
            raise R11AG2ApprovalError(f"cannot scan repository directory: {directory}") from exc
        for entry in entries:
            if entry.name == ".git":
                if prefix is None:
                    continue
                raise R11AG2ApprovalError(
                    f"nested repository metadata is prohibited: {(prefix / entry.name).as_posix()}"
                )
            relative_path = PurePosixPath(entry.name) if prefix is None else prefix / entry.name
            relative = relative_path.as_posix()
            try:
                relative.encode("ascii")
            except UnicodeEncodeError as exc:
                parts = relative_path.parts
                archive_parts = parts[2:] if parts[:2] == ("research", "archive_inventory") else ()
                has_r11a_namespace = any(_has_r11a_marker(part) for part in archive_parts)
                has_r11a_confusable = any(
                    not part.isascii()
                    and (
                        _normalized_name(part).startswith("r11")
                        or "11a" in _normalized_name(part)
                    )
                    for part in archive_parts
                )
                security_sensitive = (
                    relative.startswith(".github/workflows/")
                    or has_r11a_namespace
                    or has_r11a_confusable
                )
                if security_sensitive:
                    raise R11AG2ApprovalError(
                        f"non-ASCII security-sensitive repository path is prohibited: {relative}"
                    ) from exc
            try:
                information = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise R11AG2ApprovalError(f"cannot lstat repository entry: {relative}") from exc
            yield relative, information
            if stat.S_ISDIR(information.st_mode):
                stack.append((Path(entry.path), relative_path))


def _contains_exact_approval_id(value: object) -> bool:
    if type(value) is dict:
        return any(
            (key == "approval_id" and child == APPROVAL_ID)
            or _contains_exact_approval_id(child)
            for key, child in value.items()
        )
    if type(value) is list:
        return any(_contains_exact_approval_id(child) for child in value)
    return False


def _contains_positive_approval_claim(value: object) -> bool:
    if type(value) is dict:
        for key, child in value.items():
            if key in {"owner_approval_present", "canonical_approval_record_present"} and child is True:
                return True
            if _contains_positive_approval_claim(child):
                return True
    elif type(value) is list:
        return any(_contains_positive_approval_claim(child) for child in value)
    return False


def _contains_scalar(value: object, expected: object) -> bool:
    if type(value) is dict:
        return any(_contains_scalar(child, expected) for child in value.values())
    if type(value) is list:
        return any(_contains_scalar(child, expected) for child in value)
    return type(value) is type(expected) and value == expected


def _contains_open_authority(value: object) -> bool:
    if type(value) is dict:
        for key, child in value.items():
            if key in OPEN_AUTHORITY_TRUE_KEYS and child is True:
                return True
            if _contains_open_authority(child):
                return True
    elif type(value) is list:
        return any(_contains_open_authority(child) for child in value)
    return False


def _normalized_name(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _name_tokens(value: str) -> frozenset[str]:
    return frozenset(
        token
        for token in re.split(r"[^a-z0-9]+", _normalized_name(value))
        if token
    )


def _has_r11a_marker(value: str) -> bool:
    normalized = _normalized_name(value)
    return normalized.startswith("r11a") or "r11a" in _name_tokens(value)


def _is_r11a_archive_path(relative: str) -> bool:
    parts = PurePosixPath(relative).parts
    if len(parts) < 3 or parts[:2] != ("research", "archive_inventory"):
        return False
    return any(_has_r11a_marker(part) for part in parts[2:])


def _is_json_record_name(value: str) -> bool:
    return _normalized_name(value).rstrip().endswith(".json")


def _has_r11a_authority_name(value: str) -> bool:
    tokens = _name_tokens(value)
    return "r11a" in tokens and bool(tokens & R11A_AUTHORITY_NAME_TOKENS)


def _is_authority_data_name(value: str) -> bool:
    suffix = PurePosixPath(_normalized_name(value).rstrip()).suffix
    return suffix not in {
        ".c",
        ".go",
        ".h",
        ".java",
        ".js",
        ".jsx",
        ".md",
        ".py",
        ".pyc",
        ".pyi",
        ".pyo",
        ".rb",
        ".rs",
        ".rst",
        ".sh",
        ".ts",
        ".tsx",
    }


def _validate_approval_uniqueness(
    root: Path,
    *,
    statement_bytes: bytes,
    receipt_bytes: bytes,
    permitted_successor_paths: frozenset[str] = frozenset(),
) -> None:
    lexical_root = _checked_root(root)
    canonical_id = _normalized_name(APPROVAL_ID)
    canonical_receipt_information = _required_file(root, APPROVAL_JSON).lstat()
    canonical_receipt_inode = (
        canonical_receipt_information.st_dev,
        canonical_receipt_information.st_ino,
    )
    canonical_text_path = _required_file(root, APPROVAL_TEXT)
    canonical_text_information = canonical_text_path.lstat()
    canonical_text_inode = (
        canonical_text_information.st_dev,
        canonical_text_information.st_ino,
    )
    source_path = _required_file(root, SOURCE_STATEMENT)
    source_information = source_path.lstat()
    source_inode = source_information.st_dev, source_information.st_ino

    for relative, information in _repository_entries(lexical_root):
        path = lexical_root / PurePosixPath(relative)
        permitted_successor = relative in permitted_successor_paths
        normalized_basename = _normalized_name(PurePosixPath(relative).name)
        canonical_record_path = relative in {APPROVAL_JSON, APPROVAL_TEXT}

        if normalized_basename.startswith(canonical_id):
            suffix = normalized_basename[len(canonical_id) :]
            approval_like_name = not suffix or not suffix[0].isalnum()
        else:
            approval_like_name = False
        if approval_like_name:
            require(canonical_record_path, f"approval alias path present: {relative}")
        if stat.S_ISDIR(information.st_mode):
            directory_tokens = _name_tokens(PurePosixPath(relative).name)
            if "r11a" in directory_tokens and "approval" in directory_tokens:
                require(relative == APPROVAL_DIR, f"approval alias directory present: {relative}")
            continue
        if stat.S_ISLNK(information.st_mode):
            require(
                canonical_id not in _normalized_name(relative),
                f"approval alias symlink present: {relative}",
            )
            if relative.startswith("research/archive_inventory/"):
                raise R11AG2ApprovalError(f"approval/authority symlink prohibited: {relative}")
            continue
        require(
            stat.S_ISREG(information.st_mode),
            f"unsupported repository entry type: {relative}",
        )

        basename = PurePosixPath(relative).name
        if _is_r11a_archive_path(relative) and _is_authority_data_name(basename):
            require(
                relative in ALLOWED_R11A_DATA_PATHS or permitted_successor,
                f"unrecognized R11A approval/authority data file: {relative}",
            )
        if _is_authority_data_name(basename) and _has_r11a_authority_name(basename):
            require(
                relative in ALLOWED_R11A_AUTHORITY_NAMED_PATHS
                or permitted_successor,
                f"future R11A approval/authority file alias present: {relative}",
            )

        inode = information.st_dev, information.st_ino
        if inode == canonical_receipt_inode:
            require(relative == APPROVAL_JSON, f"approval receipt hard-link alias present: {relative}")
        if inode in {canonical_text_inode, source_inode}:
            require(relative in APPROVAL_TEXT_COPY_ALLOWLIST, f"approval text hard-link alias present: {relative}")

        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise R11AG2ApprovalError(f"cannot inspect approval alias candidate: {relative}") from exc

        approval_id_bytes = APPROVAL_ID.encode("ascii")
        if approval_id_bytes in raw and _is_authority_data_name(basename):
            require(
                relative in APPROVAL_ID_DATA_REFERENCE_ALLOWLIST
                or permitted_successor,
                f"unpermitted approval ID data/record alias present: {relative}",
            )

        if receipt_bytes in raw:
            require(relative == APPROVAL_JSON, f"duplicate approval receipt alias present: {relative}")
        if statement_bytes in raw:
            require(
                relative in APPROVAL_TEXT_COPY_ALLOWLIST and raw == statement_bytes,
                f"duplicate approval text alias present: {relative}",
            )

        declaration_line = statement_bytes.split(b"\n", 1)[0]
        if relative not in APPROVAL_TEXT_COPY_ALLOWLIST:
            require(
                declaration_line not in raw,
                f"conflicting approval text alias present: {relative}",
            )
            signed_prefix = declaration_line.split(approval_id_bytes, 1)[0]
            signed_owner_claim = signed_prefix in raw and approval_id_bytes in raw
            require(
                not signed_owner_claim,
                f"conflicting signed approval text alias present: {relative}",
            )

        json_named = _is_json_record_name(PurePosixPath(relative).name)
        try:
            value = _strict_json_value(raw, relative)
        except R11AG2ApprovalError as exc:
            if relative == ALIGNMENT_PATH:
                raise
            invalid_alias_candidate = json_named and (
                _is_r11a_archive_path(relative)
                or _has_r11a_authority_name(basename)
                or canonical_id in normalized_basename
                or b"approval_id" in raw.lower()
                or APPROVAL_ID.encode("ascii") in raw
            )
            if invalid_alias_candidate:
                raise R11AG2ApprovalError(
                    f"invalid approval/authority JSON alias candidate: {relative}"
                ) from exc
            continue

        r11a_record = (
            _is_r11a_archive_path(relative)
            and type(value) in {dict, list}
        )
        if r11a_record:
            require(
                relative in CANONICAL_R11A_JSON_PATHS or permitted_successor,
                f"unrecognized R11A approval/authority JSON alias record: {relative}",
            )

        if (
            relative not in APPROVAL_REFERENCE_JSON_ALLOWLIST
            and not permitted_successor
        ):
            same_approval = _contains_exact_approval_id(value)
            require(not same_approval, f"conflicting approval_id alias present: {relative}")
            if _contains_positive_approval_claim(value):
                linked_to_this_approval = _contains_scalar(
                    value, APPROVAL_ID
                ) or _contains_scalar(value, PACKAGE_ID)
                linked_to_this_approval = linked_to_this_approval or relative.startswith(
                    "research/archive_inventory/r11a"
                )
                require(
                    not linked_to_this_approval,
                    f"positive owner-approval alias present: {relative}",
                )
            if r11a_record:
                require(
                    not _contains_open_authority(value),
                    f"alternate R11A authority record opens current authority: {relative}",
                )


def _normalize_permitted_successor_paths(
    paths: frozenset[str],
) -> frozenset[str]:
    require(type(paths) is frozenset, "permitted successor paths must be frozenset")
    for relative in paths:
        _relative_parts(relative)
    require(
        paths <= KNOWN_FUTURE_STAGE_PATHS,
        "permitted successor paths contain unknown future-stage path",
    )
    return paths


def _validate_alignment_namespace(root: Path) -> None:
    _, information = _inspect_path(root, ALIGNMENT_DIR, allow_missing=True)
    if information is None:
        return
    require(
        stat.S_ISDIR(information.st_mode),
        f"alignment namespace is not directory: {ALIGNMENT_DIR}",
    )
    alignment_dir = _required_directory(root, ALIGNMENT_DIR)
    try:
        entries = {entry.name for entry in os.scandir(alignment_dir)}
    except OSError as exc:
        raise R11AG2ApprovalError("cannot inventory alignment namespace") from exc
    require(
        entries == {PurePosixPath(ALIGNMENT_PATH).name},
        "alignment namespace file set drift",
    )
    _required_file(root, ALIGNMENT_PATH)


def _validate_no_future_authority(root: Path) -> None:
    _require_absent(root, ".gitmodules", "submodule metadata unexpectedly present")
    for relative in CANONICAL_FUTURE_AUTHORITY_PATHS:
        _require_absent(root, relative, "future authority artifact unexpectedly present")
    for relative in PROHIBITED_AUTHORITY_NAMESPACES:
        _require_absent(root, relative, "future authority namespace unexpectedly present")
    for relative in PROHIBITED_INSTALLED_WORKFLOWS:
        _require_absent(root, relative, "R11A runtime workflow is installed")

    archive = _required_directory(root, "research/archive_inventory")
    try:
        entries = list(os.scandir(archive))
    except OSError as exc:
        raise R11AG2ApprovalError("cannot inventory R11A authority namespaces") from exc
    for entry in entries:
        if _has_r11a_marker(entry.name):
            require(
                entry.name in ALLOWED_R11A_NAMESPACES,
                f"unrecognized R11A authority namespace present: research/archive_inventory/{entry.name}",
            )

    for relative, information in _repository_entries(root):
        if _is_r11a_archive_path(relative):
            normalized_parts = tuple(
                _normalized_name(part) for part in PurePosixPath(relative).parts
            )
            normalized_basename = _normalized_name(PurePosixPath(relative).name)
            require(
                "__pycache__" not in normalized_parts,
                f"Python bytecode cache path prohibited: {relative}",
            )
            require(
                PurePosixPath(normalized_basename.rstrip()).suffix
                not in {".pyc", ".pyo"},
                f"Python bytecode file path prohibited: {relative}",
            )
        if stat.S_ISDIR(information.st_mode) and _is_r11a_archive_path(relative):
            require(
                relative in ALLOWED_R11A_DIRECTORIES,
                f"unrecognized R11A authority namespace present: {relative}",
            )

    authority_basenames = {
        _normalized_name(PurePosixPath(relative).name)
        for relative in (
            *CANONICAL_FUTURE_AUTHORITY_PATHS,
            *PROHIBITED_INSTALLED_WORKFLOWS,
        )
    }
    exact_authority_paths = frozenset(
        {
            *CANONICAL_FUTURE_AUTHORITY_PATHS,
            *PROHIBITED_INSTALLED_WORKFLOWS,
            HISTORICAL_IMPLEMENTATION_WORKFLOW_CANDIDATE,
        }
    )
    for relative, _ in _repository_entries(root):
        if _normalized_name(PurePosixPath(relative).name) in authority_basenames:
            require(
                relative in exact_authority_paths,
                f"future authority artifact alias present: {relative}",
            )

    development_workflow = _read_bytes(root, R11A_DEVELOPMENT_WORKFLOW)
    require(
        hashlib.sha256(development_workflow).hexdigest() == R11A_DEVELOPMENT_WORKFLOW_SHA,
        "R11A development workflow hash drift",
    )
    workflow_directory = _required_directory(root, ".github/workflows")
    try:
        workflow_entries = list(os.scandir(workflow_directory))
    except OSError as exc:
        raise R11AG2ApprovalError("cannot inventory installed workflows") from exc
    prohibited_names = {PurePosixPath(value).name for value in PROHIBITED_INSTALLED_WORKFLOWS}
    inventory_rows: list[bytes] = []
    for entry in sorted(workflow_entries, key=lambda item: item.name.encode("utf-8")):
        if entry.name in prohibited_names:
            raise R11AG2ApprovalError(f"R11A runtime workflow is installed: .github/workflows/{entry.name}")
        try:
            information = entry.stat(follow_symlinks=False)
        except OSError as exc:
            raise R11AG2ApprovalError(f"cannot inspect workflow entry: {entry.name}") from exc
        if stat.S_ISLNK(information.st_mode):
            raise R11AG2ApprovalError(f"workflow symlink prohibited: .github/workflows/{entry.name}")
        require(
            stat.S_ISREG(information.st_mode)
            and Path(entry.name).suffix.casefold() in {".yml", ".yaml"},
            f"unexpected installed-workflow directory entry: .github/workflows/{entry.name}",
        )
        raw = Path(entry.path).read_bytes()
        relative = f".github/workflows/{entry.name}"
        inventory_rows.append(
            hashlib.sha256(raw).hexdigest().encode("ascii")
            + b"  "
            + relative.encode("ascii")
            + b"\n"
        )
        if relative == R11A_DEVELOPMENT_WORKFLOW:
            require(raw == development_workflow, "R11A development workflow changed during inventory")
    require(
        hashlib.sha256(b"".join(inventory_rows)).hexdigest()
        == INSTALLED_WORKFLOW_INVENTORY_SHA256,
        "installed workflow path/raw-byte inventory drift",
    )


def _validate_no_repository_symlinks(root: Path) -> None:
    for relative, information in _repository_entries(root):
        require(
            not stat.S_ISLNK(information.st_mode),
            f"repository symlink prohibited: {relative}",
        )


def require_exact(observed: object, expected: object, label: str) -> None:
    require(type(observed) is type(expected), f"{label} type mismatch")
    if type(expected) is dict:
        observed_dict = observed
        expected_dict = expected
        require(set(observed_dict) == set(expected_dict), f"{label} key set mismatch")
        for key, expected_value in expected_dict.items():
            require_exact(observed_dict[key], expected_value, f"{label}.{key}")
        return
    if type(expected) is list:
        observed_list = observed
        expected_list = expected
        require(len(observed_list) == len(expected_list), f"{label} length mismatch")
        for index, expected_value in enumerate(expected_list):
            require_exact(observed_list[index], expected_value, f"{label}[{index}]")
        return
    require(observed == expected, f"{label} value mismatch")


def expected_record(root: Path) -> dict[str, Any]:
    package = load(root, PACKAGE)
    envelope = load(root, ENVELOPE)
    pricing = load(root, PRICING)
    identity = package["candidate_identity"]
    future = package["frozen_authority_if_explicitly_approved"]
    network = envelope["network_envelope"]
    resources = envelope["resource_envelope"]
    retention = envelope["artifact_retention"]
    calculation = pricing["calculation"]

    return {
        "schema_version": "1.0",
        "approval_id": APPROVAL_ID,
        "package_id": PACKAGE_ID,
        "diagnostic_id": DIAGNOSTIC_ID,
        "repository": REPOSITORY,
        "owner_identity": "Mathis Van Eeckhout",
        "status": "OWNER_APPROVED_HASH_BOUND_FUTURE_STAGES_NO_CURRENT_RUNTIME",
        "record_review_status": "AWAITING_INDEPENDENT_EXACT_HEAD_REVIEW",
        "approval_source": "EXPLICIT_CHAT_APPROVAL_EXACT_BLOCK",
        "approval_received_date_utc": "2026-08-26",
        "canonical_text": {
            "path": APPROVAL_TEXT,
            "sha256": APPROVAL_STATEMENT_SHA,
            "source_statement_path": SOURCE_STATEMENT,
            "source_statement_sha256": APPROVAL_STATEMENT_SHA,
            "normalization": "REPOSITORY_PROPOSED_STATEMENT_BYTES_WITH_SINGLE_TERMINAL_LF",
        },
        "approved_software_anchor": {
            "reviewed_head": SOFTWARE_HEAD,
            "reviewed_tree": SOFTWARE_TREE,
            "authoritative_review_id": SOFTWARE_REVIEW,
            "review_event": "COMMENTED",
            "review_verdict": "GREEN",
        },
        "readiness_lineage": {
            "base_sha": SOFTWARE_HEAD,
            "reviewed_head": READINESS_HEAD,
            "reviewed_tree": READINESS_TREE,
            "authoritative_review_id": READINESS_REVIEW,
            "review_event": "COMMENTED",
            "review_verdict": "GREEN",
            "g1_j_001_closed": True,
        },
        "approval_package": {
            "path": PACKAGE,
            "sha256": PACKAGE_SHA,
            "status_at_owner_decision": "AWAITING_EXPLICIT_OWNER_APPROVAL",
        },
        "approved_bound_files": dict(EXPECTED_BOUND_FILES),
        "approved_future_identity": {
            "role_arn": identity["role_arn"],
            "creation_and_configuration_authorized_only_in_separate_reviewed_stage": future[
                "dedicated_successor_role_creation_and_configuration_in_separate_next_stage"
            ],
            "maximum_session_duration_seconds": identity["maximum_session_duration_seconds"],
            "persistent_get_object_resource_count": identity[
                "persistent_get_object_resource_count"
            ],
            "permission_policy_sha256": EXPECTED_BOUND_FILES[PERMISSION],
            "oidc_trust_policy_sha256": EXPECTED_BOUND_FILES[TRUST],
            "additional_policy_or_role_authorized": False,
            "consumed_r11_role_reuse_or_mutation_authorized": False,
            "reusable_credentials_or_secrets_authorized": False,
        },
        "approved_future_diagnostic": {
            "maximum_runs_after_all_later_gates": future[
                "maximum_diagnostic_runs_after_all_later_gates"
            ],
            "bucket": envelope["scope"]["bucket"],
            "region": envelope["scope"]["region"],
            "selected_object_count": future["selected_object_count"],
            "seventy_third_object_authorized": envelope["scope"][
                "seventy_third_object_authorized"
            ],
            "broader_archive_access_authorized": False,
            "other_historical_window_authorized": envelope["scope"][
                "other_historical_window_authorized"
            ],
            "maximum_s3_get_object_requests": network["maximum_s3_get_object_requests"],
            "maximum_requests_per_object": network["maximum_requests_per_object"],
            "maximum_retries_per_request": network["maximum_retries_per_request"],
            "http_redirect_following_authorized": network[
                "http_redirect_following_authorized"
            ],
            "pagination_authorized": network["pagination_authorized"],
            "list_authorized": network["list_objects_v2_authorized"],
            "head_authorized": network["head_object_authorized"],
            "range_get_authorized": network["range_get_authorized"],
            "maximum_downloaded_bytes": resources["maximum_downloaded_bytes"],
            "maximum_ephemeral_workspace_bytes": resources[
                "maximum_ephemeral_workspace_bytes"
            ],
            "maximum_retained_artifact_bytes": resources[
                "maximum_retained_artifact_bytes"
            ],
            "artifact_retention_days": retention["github_artifact_retention_days"],
            "maximum_runtime_seconds": resources["maximum_runtime_seconds"],
            "maximum_one_time_budget_eur_micros": calculation[
                "owner_approval_max_eur_micros"
            ],
            "maximum_monthly_budget_eur_micros": calculation[
                "monthly_recurring_budget_eur_micros"
            ],
        },
        "required_separate_future_gates": {
            "post_approval_validator_alignment_and_exact_head_review": True,
            "identity_creation_and_configuration_review": True,
            "operator_role_attestation": True,
            "sts_only_preflight_review": True,
            "workflow_installation_review": True,
            "execution_release_candidate_review": True,
            "runtime_binding_review": True,
            "single_use_activation_review": True,
            "explicit_owner_dispatch": True,
        },
        "current_authority": {
            "successor_role_created": False,
            "aws_iam_mutation": False,
            "aws_oidc": False,
            "sts": False,
            "workflow_installed": False,
            "runtime_binding_present": False,
            "runtime_release": False,
            "runtime_activation": False,
            "workflow_dispatch": False,
            "requester_pays": False,
            "get_object": False,
            "object_body_download": False,
            "decompression": False,
            "diagnostic_execution": False,
            "diagnostic_artifact_retention": False,
            "pr_148_merge_or_github_approval": False,
            "rerun": False,
        },
        "science_state": {
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
        },
        "trading_authorizations": {
            "integration": False,
            "paper": False,
            "shadow": False,
            "live": False,
            "leverage": False,
            "capital_allocation": False,
            "withdrawals_or_transfers": False,
        },
        "approval_alone": {
            "creates_or_modifies_iam": False,
            "installs_workflow": False,
            "creates_release": False,
            "activates_runtime": False,
            "dispatches_workflow": False,
            "executes_r11a": False,
            "authorizes_rerun": False,
        },
        "drift_policy": {
            "void_on_sha_or_hash_drift": True,
            "void_on_object_set_request_byte_runtime_or_cost_drift": True,
            "void_on_iam_workflow_or_governance_drift": True,
            "new_explicit_owner_statement_required_after_drift": True,
        },
        "owner_approval_present": True,
        "canonical_approval_record_present": True,
        "execution_authorized_by_this_approval": False,
        "next_gate": "INDEPENDENT_EXACT_HEAD_REVIEW_OF_APPROVAL_RECORD_NO_AWS",
    }


def _validate_immutable_approval_context(
    root: Path = ROOT,
    *,
    permitted_successor_paths: frozenset[str] = frozenset(),
    validate_repository_symlinks: bool,
) -> dict[str, Any]:
    root = _checked_root(root)
    permitted_successor_paths = _normalize_permitted_successor_paths(
        permitted_successor_paths
    )
    expected_dir_files = {
        Path(APPROVAL_JSON).name,
        Path(APPROVAL_TEXT).name,
    }
    approval_dir = _required_directory(root, APPROVAL_DIR)
    try:
        observed_dir_entries = {entry.name for entry in os.scandir(approval_dir)}
    except OSError as exc:
        raise R11AG2ApprovalError("cannot inventory canonical approval directory") from exc
    require(
        observed_dir_entries == expected_dir_files,
        "canonical approval directory file set drift",
    )

    require(sha256(root, PACKAGE) == PACKAGE_SHA, "approval package raw hash drift")
    require(
        sha256(root, STATUS) == HISTORICAL_G1_STATUS_SHA,
        "historical G1 status hash drift",
    )
    require(
        sha256(root, SOURCE_STATEMENT) == APPROVAL_STATEMENT_SHA,
        "source approval statement hash drift",
    )
    require(
        sha256(root, APPROVAL_TEXT) == APPROVAL_STATEMENT_SHA,
        "canonical approval statement hash drift",
    )
    require(
        sha256(root, APPROVAL_JSON) == APPROVAL_RECEIPT_SHA,
        "approval receipt raw hash drift",
    )
    source_bytes = _read_bytes(root, SOURCE_STATEMENT)
    approval_bytes = _read_bytes(root, APPROVAL_TEXT)
    receipt_bytes = _read_bytes(root, APPROVAL_JSON)
    require(source_bytes == approval_bytes, "approval text differs from frozen statement")
    require(approval_bytes.endswith(b"\n"), "approval text lacks terminal LF")
    require(not approval_bytes.endswith(b"\n\n"), "approval text has extra terminal LF")

    package = load(root, PACKAGE)
    require(package.get("package_id") == PACKAGE_ID, "approval package ID drift")
    require(package.get("proposed_approval_id") == APPROVAL_ID, "proposed approval ID drift")
    require(
        package.get("approval_status") == "AWAITING_EXPLICIT_OWNER_APPROVAL",
        "historical package status was rewritten",
    )
    require(package.get("owner_approval_present") is False, "historical package claims approval")
    require_exact(package.get("bound_files"), EXPECTED_BOUND_FILES, "package bound_files")
    for relative, expected_hash in EXPECTED_BOUND_FILES.items():
        require(re.fullmatch(r"[0-9a-f]{64}", expected_hash) is not None, "invalid bound hash")
        relative_path = Path(relative)
        require(
            not relative_path.is_absolute() and ".." not in relative_path.parts,
            f"unsafe bound path: {relative}",
        )
        require(sha256(root, relative) == expected_hash, f"bound file hash drift: {relative}")

    anchor = package.get("software_anchor", {})
    require(anchor.get("reviewed_head") == SOFTWARE_HEAD, "software head drift")
    require(anchor.get("authoritative_review_id") == SOFTWARE_REVIEW, "software review drift")
    require(anchor.get("review_event") == "COMMENTED", "software review event drift")
    require(anchor.get("review_verdict") == "GREEN", "software verdict drift")
    require(anchor.get("superseding_red_review_present") is False, "superseding RED asserted")

    envelope = load(root, ENVELOPE)
    require(envelope.get("diagnostic_id") == DIAGNOSTIC_ID, "diagnostic ID drift")
    require(envelope.get("status") == "FROZEN_INERT_NO_EXECUTION", "envelope activated")
    require(envelope.get("authority_state", {}).get("owner_approval_present") is False, "historical envelope rewritten")
    require(
        all(value is False for value in envelope.get("prohibited_scientific_scope", {}).values()),
        "envelope opens prohibited science scope",
    )
    pricing = load(root, PRICING)
    require(
        pricing.get("status") == "PASS_CURRENT_OFFICIAL_PRICING_BOUND_NO_EXECUTION",
        "pricing binding status drift",
    )
    require(pricing.get("pricing_binding_pending") is False, "pricing binding pending")
    require(pricing.get("owner_approval_present") is False, "historical pricing rewritten")
    require(pricing.get("runtime_authority_opened") is False, "pricing opens runtime")

    record = load(root, APPROVAL_JSON)
    require_exact(record, expected_record(root), "canonical approval record")
    require(
        all(value is False for value in record["current_authority"].values()),
        "current authority opened",
    )
    require(
        all(
            value is False
            for key, value in record["science_state"].items()
            if key != "empirical_root_cause"
        ),
        "science authority opened",
    )
    require(
        all(value is False for value in record["trading_authorizations"].values()),
        "trading authority opened",
    )
    require(
        all(value is False for value in record["approval_alone"].values()),
        "approval self-executes a later stage",
    )

    # These historical candidates are source-of-truth inputs for detecting an
    # installed workflow alias even though they grant no current authority.
    _read_bytes(root, R4_WORKFLOW_CANDIDATE)
    _read_bytes(root, HISTORICAL_IMPLEMENTATION_WORKFLOW_CANDIDATE)
    _validate_approval_uniqueness(
        root,
        statement_bytes=approval_bytes,
        receipt_bytes=receipt_bytes,
        permitted_successor_paths=permitted_successor_paths,
    )
    _validate_alignment_namespace(root)
    if validate_repository_symlinks:
        _validate_no_repository_symlinks(root)

    return record


def validate_immutable_approval_context(
    root: Path = ROOT,
    *,
    permitted_successor_paths: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    return _validate_immutable_approval_context(
        root,
        permitted_successor_paths=permitted_successor_paths,
        validate_repository_symlinks=True,
    )


def validate(root: Path = ROOT) -> dict[str, Any]:
    checked_root = _checked_root(root)
    record = _validate_immutable_approval_context(
        checked_root,
        validate_repository_symlinks=False,
    )
    _validate_no_future_authority(checked_root)
    _validate_no_repository_symlinks(checked_root)
    return record


def main() -> int:
    validate()
    print("R11A_G2_OWNER_APPROVAL_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
