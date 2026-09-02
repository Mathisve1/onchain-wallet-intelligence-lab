from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import stat
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Iterable, Mapping


ROOT = Path(__file__).absolute().parents[1]

REPOSITORY_FULL_NAME = "Mathisve1/onchain-wallet-intelligence-lab"
REPOSITORY_ID = 1326362646
EVIDENCE_DIRECTORY = "research/archive_inventory/r11a_review_evidence"
CAPTURE_INTEGRITY_STATUS = "CAPTURE_INTEGRITY_VALID"
ORIGIN_AUTHENTICATION_STATUS = "NOT_PROVEN_BY_OFFLINE_VALIDATION"
CAPTURE_METHOD = "SEPARATE_READ_ONLY_GITHUB_API_CAPTURE"

_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_GIT_OID_RE = re.compile(r"[0-9a-f]{40}")
_UTC_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z")
_SAFE_COMPONENT_RE = re.compile(r"[A-Za-z0-9._-]+")
_GITHUB_LOGIN_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?")
_KNOWN_AUTHOR_ASSOCIATIONS = frozenset(
    {
        "COLLABORATOR",
        "CONTRIBUTOR",
        "FIRST_TIMER",
        "FIRST_TIME_CONTRIBUTOR",
        "MANNEQUIN",
        "MEMBER",
        "NONE",
        "OWNER",
    }
)
_AUTHORIZED_REVIEW_ASSOCIATIONS = frozenset({"COLLABORATOR", "MEMBER", "OWNER"})
_AUTHORIZED_REPOSITORY_PERMISSIONS = frozenset({"write", "maintain", "admin"})

OWNER_SELF_REVIEW_COMMENTED_GREEN = "OWNER_SELF_REVIEW_COMMENTED_GREEN"
DISTINCT_REPOSITORY_ASSOCIATED_COMMENTED_GREEN = (
    "DISTINCT_REPOSITORY_ASSOCIATED_COMMENTED_GREEN"
)
_REVIEWER_MODELS = frozenset(
    {
        OWNER_SELF_REVIEW_COMMENTED_GREEN,
        DISTINCT_REPOSITORY_ASSOCIATED_COMMENTED_GREEN,
    }
)
_GITHUB_APPROVAL_STATUS = "NOT_APPROVED"
_THIRD_PARTY_INDEPENDENCE_STATUS = "NOT_CLAIMED"
_AUTHORITY_STATUS = "NOT_GRANTED"
_HUMAN_REVIEW_RESPONSIBILITY_STATUS = "RETAINED_BY_REVIEWER"


class ReviewEvidenceError(AssertionError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewEvidenceError(message)


@dataclass(frozen=True)
class GateContract:
    gate_id: str
    evidence_relative: str
    target_stage_id: str
    predecessor_stage_id: str
    subject_paths: tuple[str, ...]


def _gate(
    gate_id: str,
    filename: str,
    target_stage_id: str,
    predecessor_stage_id: str,
    *subject_paths: str,
) -> GateContract:
    _require(bool(subject_paths), f"{gate_id} must declare a canonical reviewed subject")
    for relative in subject_paths:
        _require(
            type(relative) is str
            and bool(relative)
            and not relative.startswith("/")
            and not relative.endswith("/")
            and "\\" not in relative
            and "\x00" not in relative
            and all(
                part not in {"", ".", ".."}
                and _SAFE_COMPONENT_RE.fullmatch(part) is not None
                for part in relative.split("/")
            ),
            f"{gate_id} reviewed subject path is not canonical",
        )
    return GateContract(
        gate_id=gate_id,
        evidence_relative=f"{EVIDENCE_DIRECTORY}/{filename}",
        target_stage_id=target_stage_id,
        predecessor_stage_id=predecessor_stage_id,
        subject_paths=tuple(subject_paths),
    )


_GATES = (
    _gate(
        "R11A_ALIGNMENT_REVIEW",
        "R11A_ALIGNMENT_REVIEW_EVIDENCE.json",
        "R11A-POST-APPROVAL-VALIDATOR-ALIGNMENT-001",
        "APPROVE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001",
        "research/archive_inventory/r11a_alignment/R11A_POST_APPROVAL_VALIDATOR_ALIGNMENT.json",
    ),
    _gate(
        "R11A_IDENTITY_CONFIGURATION_REVIEW",
        "R11A_IDENTITY_CONFIGURATION_REVIEW_EVIDENCE.json",
        "R11A-SUCCESSOR-IDENTITY-CREATION-AND-CONFIGURATION-001",
        "R11A-POST-APPROVAL-VALIDATOR-ALIGNMENT-001",
        "research/archive_inventory/r11a_role_attestation/R11A_SUCCESSOR_ROLE_CREATION_CONFIGURATION_CANDIDATE.json",
    ),
    _gate(
        "R11A_ROLE_ATTESTATION_REVIEW",
        "R11A_ROLE_ATTESTATION_REVIEW_EVIDENCE.json",
        "ATTEST_HL_ARCHIVE_R11A_SUCCESSOR_ROLE_001",
        "R11A-SUCCESSOR-IDENTITY-CREATION-AND-CONFIGURATION-001",
        "research/archive_inventory/r11a_role_attestation/R11A_SUCCESSOR_ROLE_OPERATOR_ATTESTATION.json",
    ),
    _gate(
        "R11A_STS_PREFLIGHT_CANDIDATE_REVIEW",
        "R11A_STS_PREFLIGHT_CANDIDATE_REVIEW_EVIDENCE.json",
        "CANDIDATE_HL_ARCHIVE_R11A_STS_ONLY_PREFLIGHT_001",
        "ATTEST_HL_ARCHIVE_R11A_SUCCESSOR_ROLE_001",
        "research/archive_inventory/r11a_role_preflight/R11A_STS_PREFLIGHT_CANDIDATE.json",
    ),
    _gate(
        "R11A_STS_PREFLIGHT_RELEASE_REVIEW",
        "R11A_STS_PREFLIGHT_RELEASE_REVIEW_EVIDENCE.json",
        "RELEASE_HL_ARCHIVE_R11A_STS_ONLY_PREFLIGHT_001",
        "CANDIDATE_HL_ARCHIVE_R11A_STS_ONLY_PREFLIGHT_001",
        "research/archive_inventory/r11a_role_preflight/R11A_STS_PREFLIGHT_RELEASE.json",
    ),
    _gate(
        "R11A_STS_PREFLIGHT_REVIEW",
        "R11A_STS_PREFLIGHT_REVIEW_EVIDENCE.json",
        "HL-ARCHIVE-R11A-SUCCESSOR-ROLE-STS-PREFLIGHT-001",
        "RELEASE_HL_ARCHIVE_R11A_STS_ONLY_PREFLIGHT_001",
        "research/archive_inventory/r11a_role_preflight/R11A_SUCCESSOR_ROLE_STS_PREFLIGHT_ATTESTATION.json",
        "research/archive_inventory/r11a_role_preflight/R11A_STS_PREFLIGHT_RELEASE_CONSUMPTION.json",
    ),
    _gate(
        "R11A_WORKFLOW_INSTALLATION_REVIEW",
        "R11A_WORKFLOW_INSTALLATION_REVIEW_EVIDENCE.json",
        "HL-ARCHIVE-R11A-WORKFLOW-INSTALLATION-001",
        "HL-ARCHIVE-R11A-SUCCESSOR-ROLE-STS-PREFLIGHT-001",
        "research/archive_inventory/r11a_workflow_installation/R11A_WORKFLOW_INSTALLATION_CONTRACT.json",
        ".github/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic.yml",
        "research/archive_inventory/r11a_corrective/R11A_PRICING_EUR_SNAPSHOT.json",
    ),
    _gate(
        "R11A_EXECUTION_RELEASE_CANDIDATE_REVIEW",
        "R11A_EXECUTION_RELEASE_CANDIDATE_REVIEW_EVIDENCE.json",
        "CANDIDATE_RELEASE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001",
        "HL-ARCHIVE-R11A-WORKFLOW-INSTALLATION-001",
        "research/archive_inventory/r11a_runtime/R11A_EXECUTION_RELEASE_CANDIDATE.json",
    ),
    _gate(
        "R11A_EXECUTION_RELEASE_REVIEW",
        "R11A_EXECUTION_RELEASE_REVIEW_EVIDENCE.json",
        "RELEASE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001",
        "CANDIDATE_RELEASE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001",
        "research/archive_inventory/r11a_runtime/R11A_EXECUTION_RELEASE.json",
        "research/archive_inventory/r11a_runtime/R11A_EXECUTION_RELEASE.sha256",
    ),
    _gate(
        "R11A_ACTIVATION_REVIEW",
        "R11A_ACTIVATION_REVIEW_EVIDENCE.json",
        "ACTIVATE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001",
        "RELEASE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001",
        "research/archive_inventory/r11a_runtime/R11A_CANONICAL_ACTIVATION.json",
    ),
    _gate(
        "R11A_RUNTIME_BINDING_REVIEW",
        "R11A_RUNTIME_BINDING_REVIEW_EVIDENCE.json",
        "HL-ARCHIVE-R11A-RUNTIME-BINDING-R7-001",
        "ACTIVATE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001",
        "research/archive_inventory/r11a_runtime/R11A_RUNTIME_BINDING_R7.json",
    ),
)

GATE_REGISTRY: Mapping[str, GateContract] = MappingProxyType(
    {contract.gate_id: contract for contract in _GATES}
)


@dataclass(frozen=True)
class ReviewSeed:
    label: str
    review_id: int
    review_node_id: str
    reviewed_head: str
    reviewed_tree: str


SEED_REVIEWS = (
    ReviewSeed(
        "software",
        5019067044,
        "PRR_kwDOTw6wFs8AAAABKyjipA",
        "443500de54917417276c39a635ae444458d03b0b",
        "516d72a43545c454ef163e02ee1146005e6cfb5c",
    ),
    ReviewSeed(
        "g1",
        5027672461,
        "PRR_kwDOTw6wFs8AAAABK6wxjQ",
        "4da7e67b600ef1ca10fb4f2e62b493d81d4dfcc3",
        "b4c7b1524e8856450028e53be7912a88d3a675e1",
    ),
    ReviewSeed(
        "g2",
        5033303996,
        "PRR_kwDOTw6wFs8AAAABLAIfvA",
        "63526d6c39c9225e647a18693c70ec8e73535ff4",
        "eedeb4d6166c554b996ede740931c4bacb306f5d",
    ),
)

# Historical seed reviews predate the schema-1.1 evidence envelope. Their
# GitHub-native identities therefore bind exactly these four fields. No
# canonical seed evidence digest exists or is claimed here.
HISTORICAL_SEED_NON_REUSE_FIELDS = (
    "review_id",
    "review_node_id",
    "reviewed_head",
    "reviewed_tree",
)

# Canonical schema-1.1 governance-gate evidence identities additionally bind
# the digest of the complete evidence envelope.
SCHEMA_1_1_GATE_NON_REUSE_FIELDS = (
    "review_id",
    "review_node_id",
    "evidence_sha256",
    "reviewed_head",
    "reviewed_tree",
)

for _seed_field in HISTORICAL_SEED_NON_REUSE_FIELDS:
    _require(
        len({getattr(seed, _seed_field) for seed in SEED_REVIEWS})
        == len(SEED_REVIEWS),
        f"historical seed {_seed_field} values must be unique",
    )


@dataclass(frozen=True)
class ReviewerPolicy:
    expected_login: str | None = None
    expected_user_id: int | None = None
    expected_model: str | None = None
    forbid_pull_request_author: bool = False


@dataclass(frozen=True)
class ReviewEvidenceIdentity:
    gate_id: str
    evidence_relative: str
    evidence_sha256: str
    repository_full_name: str
    repository_id: int
    pull_request_number: int
    pull_request_node_id: str
    pull_request_author_login: str
    pull_request_author_id: int
    review_id: int
    review_node_id: str
    reviewer_login: str
    reviewer_id: int
    reviewer_model: str
    reviewer_author_association: str
    reviewer_repository_permission: str
    reviewer_repository_role_name: str
    submitted_at: str
    reviewed_commit_committed_at: str
    captured_at: str
    reviewed_head: str
    reviewed_tree: str
    target_stage_id: str
    target_bundle_sha256: str
    predecessor_stage_id: str
    predecessor_reviewed_head: str
    predecessor_reviewed_tree: str
    predecessor_bundle_sha256: str
    integrity_status: str = CAPTURE_INTEGRITY_STATUS
    origin_authentication: str = ORIGIN_AUTHENTICATION_STATUS


ReviewedBlobReader = Callable[[str, str], bytes]


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _nonfinite(value: str) -> Any:
    raise ReviewEvidenceError(f"non-finite JSON constant: {value}")


def _load_json(raw: bytes, label: str) -> Any:
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise ReviewEvidenceError(f"{label} is not UTF-8") from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_pairs,
            parse_constant=_nonfinite,
        )
    except ReviewEvidenceError:
        raise
    except (TypeError, ValueError) as exc:
        raise ReviewEvidenceError(f"{label} is not strict JSON") from exc


def canonical_json_bytes(value: Any) -> bytes:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ReviewEvidenceError("value is not canonical-JSON encodable") from exc
    return encoded + b"\n"


def _exact_keys(value: Any, expected: frozenset[str], label: str) -> dict[str, Any]:
    _require(type(value) is dict, f"{label} must be an object")
    observed = frozenset(value)
    _require(
        observed == expected,
        f"{label} keys drift: expected {sorted(expected)}, observed {sorted(observed)}",
    )
    return value


def _positive_int(value: Any, label: str) -> int:
    _require(type(value) is int and value > 0, f"{label} must be a positive integer")
    return value


def _text(value: Any, label: str) -> str:
    _require(type(value) is str and bool(value), f"{label} must be nonempty text")
    return value


def _sha256(value: Any, label: str) -> str:
    _require(type(value) is str and _SHA256_RE.fullmatch(value) is not None, f"{label} is not SHA-256")
    return value


def _git_oid(value: Any, label: str) -> str:
    _require(type(value) is str and _GIT_OID_RE.fullmatch(value) is not None, f"{label} is not a Git object ID")
    return value


def _utc(value: Any, label: str) -> datetime:
    _require(type(value) is str and _UTC_RE.fullmatch(value) is not None, f"{label} is not canonical UTC")
    try:
        result = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ReviewEvidenceError(f"{label} is not a valid UTC timestamp") from exc
    _require(result.tzinfo == timezone.utc, f"{label} is not UTC")
    return result


def _safe_relative(relative: Any, label: str) -> str:
    _require(type(relative) is str and bool(relative), f"{label} must be nonempty text")
    _require(unicodedata.normalize("NFC", relative) == relative, f"{label} is not NFC")
    _require("\x00" not in relative and "\\" not in relative, f"{label} contains an ambiguous separator")
    _require(not relative.startswith("/") and not relative.endswith("/"), f"{label} must be relative")
    parts = relative.split("/")
    _require(all(part not in {"", ".", ".."} for part in parts), f"{label} contains unsafe components")
    _require(
        all(_SAFE_COMPONENT_RE.fullmatch(part) is not None for part in parts),
        f"{label} contains a noncanonical component",
    )
    return relative


def _root(root: Path) -> Path:
    candidate = Path(root)
    _require(candidate.is_absolute(), "repository root must be absolute")
    _require(".." not in candidate.parts, "repository root traversal rejected")
    current = Path(candidate.anchor)
    for part in candidate.parts[1:]:
        current /= part
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise ReviewEvidenceError("repository root is absent") from exc
        _require(not stat.S_ISLNK(metadata.st_mode), "repository root ancestry contains a symlink")
        _require(stat.S_ISDIR(metadata.st_mode), "repository root ancestry is not entirely directories")
    return candidate


def _checked_file(root: Path, relative: str) -> Path:
    base = _root(root)
    _safe_relative(relative, "evidence path")
    current = base
    parts = relative.split("/")
    for index, part in enumerate(parts):
        current /= part
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise ReviewEvidenceError(f"required review evidence is absent: {relative}") from exc
        _require(not stat.S_ISLNK(metadata.st_mode), f"symlink rejected in review evidence path: {relative}")
        if index != len(parts) - 1:
            _require(stat.S_ISDIR(metadata.st_mode), f"non-directory review evidence ancestor: {relative}")
        else:
            _require(stat.S_ISREG(metadata.st_mode), f"review evidence is not a regular file: {relative}")
            _require(metadata.st_nlink == 1, f"hard-linked review evidence rejected: {relative}")
    return current


def evidence_path(gate_id: str) -> str:
    try:
        return GATE_REGISTRY[gate_id].evidence_relative
    except KeyError as exc:
        raise ReviewEvidenceError(f"unknown review gate: {gate_id}") from exc


def require_no_review_evidence(root: Path = ROOT) -> None:
    base = _root(root)
    directory = base / EVIDENCE_DIRECTORY
    try:
        metadata = directory.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise ReviewEvidenceError("cannot inspect review-evidence namespace") from exc
    _require(not stat.S_ISLNK(metadata.st_mode), "review-evidence namespace symlink rejected")
    _require(stat.S_ISDIR(metadata.st_mode), "review-evidence namespace is not a directory")
    try:
        entries = tuple(directory.iterdir())
    except OSError as exc:
        raise ReviewEvidenceError("cannot enumerate review-evidence namespace") from exc
    _require(not entries, "future GitHub review evidence must be absent from the live tree")


def _validated_file_map(files: Mapping[str, str], label: str) -> dict[str, str]:
    _require(isinstance(files, Mapping), f"{label} must be a mapping")
    result: dict[str, str] = {}
    folded_paths: dict[str, str] = {}
    for relative, digest in files.items():
        path = _safe_relative(relative, f"{label} path")
        _require(path not in result, f"duplicate {label} path: {path}")
        folded = path.casefold()
        _require(
            folded not in folded_paths,
            f"case-fold-colliding {label} paths: {folded_paths.get(folded)} and {path}",
        )
        folded_paths[folded] = path
        result[path] = _sha256(digest, f"{label}[{path}]")
    _require(bool(result), f"{label} must not be empty")
    return result


def bundle_sha256(files: Mapping[str, str]) -> str:
    validated = _validated_file_map(files, "bundle files")
    digest = hashlib.sha256(b"R11A_REVIEWED_FILE_BUNDLE_V1\0")
    for relative in sorted(validated, key=lambda item: item.encode("utf-8")):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(validated[relative].encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _decode_payload(wrapper: Any, label: str) -> tuple[str, Any]:
    value = _exact_keys(
        wrapper,
        frozenset({"endpoint", "http_status", "content_type", "encoding", "sha256", "body_base64"}),
        label,
    )
    endpoint = _text(value["endpoint"], f"{label} endpoint")
    _require(endpoint.startswith("/repos/") and ".." not in endpoint, f"{label} endpoint is not canonical")
    _require(type(value["http_status"]) is int and value["http_status"] == 200, f"{label} HTTP status is not 200")
    _require(value["content_type"] == "application/json", f"{label} content type drift")
    _require(value["encoding"] == "base64", f"{label} encoding drift")
    expected = _sha256(value["sha256"], f"{label} SHA-256")
    encoded = _text(value["body_base64"], f"{label} base64 body")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ReviewEvidenceError(f"{label} base64 body is invalid") from exc
    _require(base64.b64encode(raw).decode("ascii") == encoded, f"{label} base64 is not canonical")
    _require(hashlib.sha256(raw).hexdigest() == expected, f"{label} payload SHA-256 mismatch")
    return endpoint, _load_json(raw, f"{label} payload")


def _required_object(value: Any, label: str) -> dict[str, Any]:
    _require(type(value) is dict, f"{label} must be an object")
    return value


def _member(value: dict[str, Any], key: str, label: str) -> Any:
    _require(key in value, f"{label} omits {key}")
    return value[key]


def _api_user(value: Any, label: str) -> tuple[str, int]:
    user = _required_object(value, label)
    return (
        _text(_member(user, "login", label), f"{label} login"),
        _positive_int(_member(user, "id", label), f"{label} ID"),
    )


def _github_login(value: Any, label: str) -> str:
    login = _text(value, label)
    _require(
        _GITHUB_LOGIN_RE.fullmatch(login) is not None,
        f"{label} is not a canonical GitHub login",
    )
    return login


def _marker(body: str, label: str) -> str:
    prefix = f"{label}: `"
    matches = [
        line[len(prefix) : -1]
        for line in body.splitlines()
        if line.startswith(prefix) and line.endswith("`")
    ]
    _require(len(matches) == 1, f"review body must contain exactly one {label} marker")
    return matches[0]


def _validate_review_body(
    body: Any,
    *,
    contract: GateContract,
    pr_number: int,
    head: str,
    tree: str,
    target_bundle: str,
    predecessor_head: str,
    predecessor_tree: str,
    predecessor_bundle: str,
    reviewer_model: str,
    reviewer_login: str,
    reviewer_id: int,
    reviewer_author_association: str,
    reviewer_repository_permission: str,
) -> None:
    text = _text(body, "selected review body")
    nonempty = [line.strip() for line in text.splitlines() if line.strip()]
    _require(bool(nonempty) and nonempty[0] == "GREEN", "selected review body does not start with GREEN")
    _require("RED" not in nonempty, "selected review body also contains a RED verdict")
    expected = {
        "repository": REPOSITORY_FULL_NAME,
        "pull request": f"#{pr_number}",
        "event": "COMMENTED",
        "verdict": "GREEN",
        "gate": contract.gate_id,
        "reviewed head": head,
        "reviewed tree": tree,
        "target stage": contract.target_stage_id,
        "target bundle": target_bundle,
        "immediate predecessor stage": contract.predecessor_stage_id,
        "immediate predecessor head": predecessor_head,
        "immediate predecessor tree": predecessor_tree,
        "immediate predecessor bundle": predecessor_bundle,
        "reviewer model": reviewer_model,
        "reviewer login": reviewer_login,
        "reviewer user ID": str(reviewer_id),
        "reviewer author association": reviewer_author_association,
        "reviewer repository permission": reviewer_repository_permission,
        "github approval": _GITHUB_APPROVAL_STATUS,
        "third-party independence": _THIRD_PARTY_INDEPENDENCE_STATUS,
        "merge authority": _AUTHORITY_STATUS,
        "AWS/IAM/OIDC/STS/S3 authority": _AUTHORITY_STATUS,
        "workflow/release/activation/runtime/diagnostic authority": (
            _AUTHORITY_STATUS
        ),
        "human substantive responsibility": _HUMAN_REVIEW_RESPONSIBILITY_STATUS,
    }
    for label, expected_value in expected.items():
        _require(_marker(text, label) == expected_value, f"review body {label} binding drift")
    if reviewer_model == OWNER_SELF_REVIEW_COMMENTED_GREEN:
        folded = text.casefold()
        for prohibited_claim in (
            "independent reviewer",
            "third-party reviewer",
            "independent third-party",
            "third-party independent",
        ):
            _require(
                prohibited_claim not in folded,
                "owner self-review cannot claim third-party independence",
            )
    canonical_body = "\n".join(
        (
            "GREEN",
            "",
            *(f"{label}: `{value}`" for label, value in expected.items()),
        )
    )
    _require(
        text == canonical_body,
        "selected review body is not the exact canonical machine-readable form",
    )


def _first_verdict(body: Any) -> str | None:
    if type(body) is not str:
        return None
    for line in body.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped if stripped in {"GREEN", "RED"} else None
    return None


def _corroborate_local_blobs(
    target_head: str,
    predecessor_head: str,
    target: Mapping[str, str],
    predecessor: Mapping[str, str],
    reader: ReviewedBlobReader,
) -> None:
    target_folded = {relative.casefold(): relative for relative in target}
    predecessor_folded = {relative.casefold(): relative for relative in predecessor}
    overlap = frozenset(target_folded) & frozenset(predecessor_folded)
    _require(not overlap, f"target and immediate-predecessor bundles overlap: {sorted(overlap)}")
    for label, head, files in (
        ("target", target_head, target),
        ("immediate predecessor", predecessor_head, predecessor),
    ):
        for relative, expected in files.items():
            try:
                raw = reader(head, relative)
            except ReviewEvidenceError:
                raise
            except Exception as exc:
                raise ReviewEvidenceError(f"cannot read {label} reviewed blob: {relative}") from exc
            _require(type(raw) is bytes, f"reviewed blob reader did not return bytes: {relative}")
            _require(
                hashlib.sha256(raw).hexdigest() == expected,
                f"{label} local reviewed blob SHA-256 mismatch: {relative}",
            )


def _git_blob_oid(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw).hexdigest()


def _git_tree_oid(entries: list[tuple[str, str, str]]) -> str:
    body = bytearray()
    for name, mode, oid in sorted(
        entries,
        key=lambda item: item[0].encode("utf-8")
        + (b"/" if item[1] == "040000" else b""),
    ):
        encoded_mode = mode.lstrip("0") if mode == "040000" else mode
        body.extend(encoded_mode.encode("ascii"))
        body.extend(b" ")
        body.extend(name.encode("utf-8"))
        body.extend(b"\0")
        body.extend(bytes.fromhex(oid))
    header = f"tree {len(body)}\0".encode("ascii")
    return hashlib.sha1(header + body).hexdigest()


def _tree_entry_map(
    value: Any,
    *,
    label: str,
    repository_name: str,
    expected_tree: str,
) -> dict[str, tuple[str, str, int | None]]:
    tree_payload = _required_object(value, label)
    observed_tree = _git_oid(_member(tree_payload, "sha", label), f"{label} SHA")
    _require(observed_tree == expected_tree, f"{label} root SHA drift")
    _require(_member(tree_payload, "truncated", label) is False, f"{label} is truncated")
    _require(
        _member(tree_payload, "url", label)
        == f"https://api.github.com/repos/{repository_name}/git/trees/{expected_tree}",
        f"{label} URL drift",
    )
    entries = _member(tree_payload, "tree", label)
    _require(type(entries) is list, f"{label} entries must be an array")
    result: dict[str, tuple[str, str, int | None]] = {}
    folded_paths: dict[str, str] = {}
    for entry_value in entries:
        entry = _required_object(entry_value, f"{label} entry")
        relative = _safe_relative(_member(entry, "path", f"{label} entry"), f"{label} entry path")
        _require(relative not in result, f"duplicate path in {label}: {relative}")
        folded = relative.casefold()
        _require(
            folded not in folded_paths,
            f"case-fold-colliding paths in {label}: {folded_paths.get(folded)} and {relative}",
        )
        folded_paths[folded] = relative
        entry_type = _text(_member(entry, "type", f"{label} entry"), f"{label} entry type")
        mode = _text(_member(entry, "mode", f"{label} entry"), f"{label} entry mode")
        oid = _git_oid(_member(entry, "sha", f"{label} entry"), f"{label} entry object ID")
        size_value = entry.get("size")
        if entry_type == "blob":
            _require(mode in {"100644", "100755"}, f"unsupported blob mode in {label}: {relative}")
            _require(type(size_value) is int and size_value >= 0, f"blob size is invalid in {label}: {relative}")
            expected_url = f"https://api.github.com/repos/{repository_name}/git/blobs/{oid}"
            size: int | None = size_value
        elif entry_type == "tree":
            _require(mode == "040000", f"unsupported tree mode in {label}: {relative}")
            _require(size_value is None, f"tree entry unexpectedly has a size in {label}: {relative}")
            expected_url = f"https://api.github.com/repos/{repository_name}/git/trees/{oid}"
            size = None
        else:
            raise ReviewEvidenceError(f"symlink, submodule, or unsupported entry in {label}: {relative}")
        _require(
            _member(entry, "url", f"{label} entry") == expected_url,
            f"{label} entry URL drift: {relative}",
        )
        result[relative] = (oid, mode, size)

    directories = {relative for relative, (_, mode, _) in result.items() if mode == "040000"}
    for relative in result:
        parent, separator, _ = relative.rpartition("/")
        if separator:
            _require(parent in directories, f"orphaned recursive-tree entry in {label}: {relative}")
    for directory in sorted({"", *directories}, key=lambda item: item.count("/"), reverse=True):
        children: list[tuple[str, str, str]] = []
        for relative, (oid, mode, _) in result.items():
            parent, separator, name = relative.rpartition("/")
            if not separator:
                parent = ""
                name = relative
            if parent == directory:
                children.append((name, mode, oid))
        _require(bool(children), f"empty directory entry in {label}: {directory or '<root>'}")
        expected_oid = expected_tree if not directory else result[directory][0]
        _require(
            _git_tree_oid(children) == expected_oid,
            f"{label} Git tree object ID mismatch: {directory or '<root>'}",
        )
    return result


def _decode_git_blob_content(value: Any, label: str) -> bytes:
    _require(type(value) is str, f"{label} content must be base64 text")
    _require(" " not in value and "\t" not in value, f"{label} content contains noncanonical whitespace")
    compact = value.replace("\r", "").replace("\n", "")
    try:
        raw = base64.b64decode(compact, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ReviewEvidenceError(f"{label} content is not valid base64") from exc
    _require(base64.b64encode(raw).decode("ascii") == compact, f"{label} content base64 is not canonical")
    return raw


def _validate_captured_blobs(
    wrappers: Any,
    *,
    label: str,
    repository_name: str,
    expected_files: Mapping[str, str],
    tree_entries: Mapping[str, tuple[str, str, int | None]],
) -> None:
    _require(type(wrappers) is dict, f"{label} must be an object")
    _require(frozenset(wrappers) == frozenset(expected_files), f"{label} path inventory drift")
    for relative, expected_sha256 in expected_files.items():
        _require(relative in tree_entries, f"{label} path is absent from captured recursive tree: {relative}")
        expected_oid, mode, tree_size = tree_entries[relative]
        _require(mode in {"100644", "100755"}, f"{label} path is not a regular Git blob: {relative}")
        endpoint, payload_value = _decode_payload(wrappers[relative], f"{label}[{relative}]")
        _require(
            endpoint == f"/repos/{repository_name}/git/blobs/{expected_oid}",
            f"{label} endpoint drift: {relative}",
        )
        payload = _required_object(payload_value, f"{label} payload: {relative}")
        observed_oid = _git_oid(
            _member(payload, "sha", f"{label} payload"),
            f"{label} object ID: {relative}",
        )
        _require(observed_oid == expected_oid, f"{label} tree/blob object binding drift: {relative}")
        _require(
            _member(payload, "url", f"{label} payload")
            == f"https://api.github.com/repos/{repository_name}/git/blobs/{expected_oid}",
            f"{label} blob URL drift: {relative}",
        )
        _require(_member(payload, "encoding", f"{label} payload") == "base64", f"{label} blob encoding drift: {relative}")
        raw = _decode_git_blob_content(
            _member(payload, "content", f"{label} payload"),
            f"{label}[{relative}]",
        )
        size = _member(payload, "size", f"{label} payload")
        _require(type(size) is int and size == len(raw), f"{label} blob size drift: {relative}")
        _require(tree_size == size, f"{label} recursive-tree size drift: {relative}")
        _require(_git_blob_oid(raw) == expected_oid, f"{label} Git blob OID mismatch: {relative}")
        _require(
            hashlib.sha256(raw).hexdigest() == expected_sha256,
            f"{label} blob SHA-256 mismatch: {relative}",
        )


def _lineage_predecessor(
    gate_id: str,
    consumed: tuple[ReviewEvidenceIdentity, ...],
) -> tuple[str, str]:
    gate_ids = tuple(GATE_REGISTRY)
    gate_index = gate_ids.index(gate_id)
    _require(
        all(isinstance(identity, ReviewEvidenceIdentity) for identity in consumed),
        "consumed review identity has wrong type",
    )
    _require(
        tuple(identity.gate_id for identity in consumed) == gate_ids[:gate_index],
        f"{gate_id} does not consume the exact review-gate prefix",
    )
    if gate_index == 0:
        g2 = SEED_REVIEWS[-1]
        return g2.reviewed_head, g2.reviewed_tree
    predecessor = consumed[-1]
    return predecessor.reviewed_head, predecessor.reviewed_tree


def _validate_reuse(identity: ReviewEvidenceIdentity, consumed: Iterable[ReviewEvidenceIdentity]) -> None:
    lineage = (*tuple(consumed), identity)
    observed_gate_ids: set[str] = set()
    for candidate in lineage:
        _require(
            isinstance(candidate, ReviewEvidenceIdentity),
            "consumed review identity has wrong type",
        )
        _require(
            candidate.gate_id not in observed_gate_ids,
            "review gate reused in governance lineage",
        )
        observed_gate_ids.add(candidate.gate_id)
        for seed in SEED_REVIEWS:
            seed_messages = {
                "review_id": "seed review ID",
                "review_node_id": "seed review node ID",
                "reviewed_head": "seed reviewed head",
                "reviewed_tree": "seed reviewed tree",
            }
            for field in HISTORICAL_SEED_NON_REUSE_FIELDS:
                _require(
                    getattr(candidate, field) != getattr(seed, field),
                    (
                        f"{candidate.gate_id} reuses {seed.label} "
                        f"{seed_messages[field]}"
                    ),
                )

    reuse_messages = {
        "review_id": "review ID reused across governance gates",
        "review_node_id": "review node ID reused across governance gates",
        "evidence_sha256": "review evidence bytes reused across governance gates",
        "reviewed_head": "reviewed head reused across governance gates",
        "reviewed_tree": "reviewed tree reused across governance gates",
    }
    for index, candidate in enumerate(lineage):
        for ancestor in lineage[:index]:
            for field in SCHEMA_1_1_GATE_NON_REUSE_FIELDS:
                _require(
                    getattr(candidate, field) != getattr(ancestor, field),
                    reuse_messages[field],
                )


def validate_gate_evidence(
    root: Path,
    gate_id: str,
    *,
    expected_evidence_sha256: str,
    expected_pr_number: int | None = None,
    expected_target_files: Mapping[str, str],
    expected_predecessor_files: Mapping[str, str],
    expected_reviewer: ReviewerPolicy | None = None,
    consumed: Iterable[ReviewEvidenceIdentity] = (),
    reviewed_blob_reader: ReviewedBlobReader | None = None,
) -> ReviewEvidenceIdentity:
    """Validate an immutable, externally captured review-evidence envelope.

    This function is deliberately offline.  It proves canonical envelope and
    payload integrity, exact Git-byte bindings, chronology, gate lineage, and
    review non-reuse.  GitHub REST payloads are not signed; therefore it does
    *not* prove that the captured bytes originated at GitHub.  A separate
    read-only capture/review process establishes that provenance before the
    next stage hash-binds this evidence file.
    """

    try:
        contract = GATE_REGISTRY[gate_id]
    except KeyError as exc:
        raise ReviewEvidenceError(f"unknown review gate: {gate_id}") from exc

    lineage = tuple(consumed)
    expected_predecessor_head, expected_predecessor_tree = _lineage_predecessor(
        gate_id,
        lineage,
    )

    expected_evidence = _sha256(expected_evidence_sha256, "expected review-evidence SHA-256")
    target_files = _validated_file_map(expected_target_files, "expected target files")
    predecessor_files = _validated_file_map(
        expected_predecessor_files,
        "expected immediate-predecessor files",
    )
    _require(contract.evidence_relative not in target_files, "review evidence cannot review itself")
    _require(contract.evidence_relative not in predecessor_files, "review evidence cannot be its own predecessor")

    evidence_file = _checked_file(root, contract.evidence_relative)
    try:
        raw = evidence_file.read_bytes()
    except OSError as exc:
        raise ReviewEvidenceError("cannot read review evidence") from exc
    evidence_digest = hashlib.sha256(raw).hexdigest()
    _require(evidence_digest == expected_evidence, "review-evidence SHA-256 binding drift")
    envelope = _load_json(raw, "review evidence")
    _require(raw == canonical_json_bytes(envelope), "review evidence is not canonical JSON")
    value = _exact_keys(
        envelope,
        frozenset(
            {
                "schema_version",
                "evidence_type",
                "gate_id",
                "selected_review_id",
                "selected_review_node_id",
                "reviewer_model",
                "capture",
                "source_payloads",
                "reviewed_stage",
                "immediate_predecessor",
            }
        ),
        "review evidence",
    )
    _require(value["schema_version"] == "1.1", "review-evidence schema version drift")
    _require(
        value["evidence_type"] == "EXTERNALLY_CAPTURED_GITHUB_PULL_REQUEST_REVIEW",
        "review-evidence type drift",
    )
    _require(value["gate_id"] == gate_id, "review-evidence gate drift")
    selected_review_id = _positive_int(value["selected_review_id"], "selected review ID")
    selected_review_node_id = _text(
        value["selected_review_node_id"],
        "selected review node ID",
    )
    declared_reviewer_model = _text(value["reviewer_model"], "reviewer model")
    _require(
        declared_reviewer_model in _REVIEWER_MODELS,
        "reviewer model is unknown",
    )

    capture = _exact_keys(
        value["capture"],
        frozenset(
            {
                "capture_method",
                "captured_at",
                "integrity_scope",
                "origin_authentication",
                "offline_network_access",
            }
        ),
        "capture metadata",
    )
    _require(capture["capture_method"] == CAPTURE_METHOD, "review capture method drift")
    captured_at = _text(capture["captured_at"], "capture timestamp")
    captured_time = _utc(captured_at, "capture timestamp")
    _require(capture["integrity_scope"] == CAPTURE_INTEGRITY_STATUS, "capture integrity scope drift")
    _require(
        capture["origin_authentication"] == ORIGIN_AUTHENTICATION_STATUS,
        "capture falsely claims GitHub origin authentication",
    )
    _require(capture["offline_network_access"] is False, "offline evidence validator may not use network")

    target = _exact_keys(
        value["reviewed_stage"],
        frozenset({"stage_id", "bundle_sha256", "files"}),
        "reviewed-stage binding",
    )
    predecessor = _exact_keys(
        value["immediate_predecessor"],
        frozenset({"stage_id", "reviewed_head", "reviewed_tree", "bundle_sha256", "files"}),
        "immediate-predecessor binding",
    )
    _require(target["stage_id"] == contract.target_stage_id, "reviewed target stage drift")
    _require(predecessor["stage_id"] == contract.predecessor_stage_id, "reviewed predecessor stage drift")
    predecessor_head = _git_oid(
        predecessor["reviewed_head"],
        "immediate-predecessor reviewed head",
    )
    predecessor_tree = _git_oid(
        predecessor["reviewed_tree"],
        "immediate-predecessor reviewed tree",
    )
    _require(
        predecessor_head == expected_predecessor_head,
        "immediate-predecessor reviewed head does not match exact review lineage",
    )
    _require(
        predecessor_tree == expected_predecessor_tree,
        "immediate-predecessor reviewed tree does not match exact review lineage",
    )
    observed_target = _validated_file_map(target["files"], "reviewed-stage files")
    observed_predecessor = _validated_file_map(predecessor["files"], "immediate-predecessor files")
    _require(observed_target == target_files, "reviewed target file set or digest drift")
    _require(observed_predecessor == predecessor_files, "reviewed predecessor file set or digest drift")
    target_bundle = _sha256(target["bundle_sha256"], "reviewed-stage bundle SHA-256")
    predecessor_bundle = _sha256(
        predecessor["bundle_sha256"],
        "immediate-predecessor bundle SHA-256",
    )
    _require(target_bundle == bundle_sha256(target_files), "reviewed-stage bundle digest drift")
    _require(
        predecessor_bundle == bundle_sha256(predecessor_files),
        "immediate-predecessor bundle digest drift",
    )
    if lineage:
        _require(
            predecessor_bundle == lineage[-1].target_bundle_sha256,
            "immediate-predecessor bundle does not equal the prior reviewed target",
        )

    sources = _exact_keys(
        value["source_payloads"],
        frozenset(
            {
                "repository",
                "pull_request",
                "reviewed_commit",
                "reviewed_tree",
                "predecessor_tree",
                "review_pages",
                "reviewer_permission",
                "target_blobs",
                "predecessor_blobs",
            }
        ),
        "source payloads",
    )
    repository_endpoint, repository_payload = _decode_payload(sources["repository"], "repository payload")
    pull_endpoint, pull_payload = _decode_payload(sources["pull_request"], "pull-request payload")
    commit_endpoint, commit_payload = _decode_payload(sources["reviewed_commit"], "reviewed-commit payload")

    repository = _required_object(repository_payload, "repository payload")
    repository_name = _text(_member(repository, "full_name", "repository payload"), "repository full name")
    repository_id = _positive_int(_member(repository, "id", "repository payload"), "repository ID")
    _require(repository_name == REPOSITORY_FULL_NAME, "review evidence belongs to the wrong repository")
    _require(repository_id == REPOSITORY_ID, "review evidence repository ID drift")
    _require(repository_endpoint == f"/repos/{repository_name}", "repository endpoint drift")

    pull = _required_object(pull_payload, "pull-request payload")
    pr_number = _positive_int(_member(pull, "number", "pull-request payload"), "pull-request number")
    if expected_pr_number is not None:
        _require(type(expected_pr_number) is int and expected_pr_number > 0, "expected PR number must be positive")
        _require(pr_number == expected_pr_number, "review evidence belongs to the wrong pull request")
    pull_node_id = _text(_member(pull, "node_id", "pull-request payload"), "pull-request node ID")
    pull_author_login, pull_author_id = _api_user(
        _member(pull, "user", "pull-request payload"),
        "pull-request author",
    )
    _github_login(pull_author_login, "pull-request author login")
    pull_url = f"https://api.github.com/repos/{repository_name}/pulls/{pr_number}"
    _require(_member(pull, "url", "pull-request payload") == pull_url, "pull-request URL drift")
    pull_created_at = _utc(
        _member(pull, "created_at", "pull-request payload"),
        "pull-request creation timestamp",
    )
    pull_head = _required_object(_member(pull, "head", "pull-request payload"), "pull-request head")
    head = _git_oid(_member(pull_head, "sha", "pull-request head"), "pull-request head SHA")
    head_repository = _required_object(_member(pull_head, "repo", "pull-request head"), "head repository")
    _require(_member(head_repository, "full_name", "head repository") == repository_name, "forked review head repository rejected")
    _require(_member(head_repository, "id", "head repository") == repository_id, "head repository ID drift")
    pull_base = _required_object(_member(pull, "base", "pull-request payload"), "pull-request base")
    base_sha = _git_oid(_member(pull_base, "sha", "pull-request base"), "pull-request base SHA")
    _require(base_sha == predecessor_head, "pull-request base skips the immediate reviewed predecessor")
    base_repository = _required_object(_member(pull_base, "repo", "pull-request base"), "base repository")
    _require(_member(base_repository, "full_name", "base repository") == repository_name, "base repository name drift")
    _require(_member(base_repository, "id", "base repository") == repository_id, "base repository ID drift")
    _require(pull_endpoint == f"/repos/{repository_name}/pulls/{pr_number}", "pull-request endpoint drift")

    commit = _required_object(commit_payload, "reviewed-commit payload")
    commit_sha = _git_oid(_member(commit, "sha", "reviewed-commit payload"), "reviewed commit SHA")
    _require(commit_sha == head, "reviewed commit does not equal pull-request head")
    commit_detail = _required_object(_member(commit, "commit", "reviewed-commit payload"), "reviewed commit detail")
    tree_object = _required_object(_member(commit_detail, "tree", "reviewed commit detail"), "reviewed commit tree")
    tree = _git_oid(_member(tree_object, "sha", "reviewed commit tree"), "reviewed tree SHA")
    committer = _required_object(_member(commit_detail, "committer", "reviewed commit detail"), "reviewed commit committer")
    committed_at = _text(_member(committer, "date", "reviewed commit committer"), "reviewed commit timestamp")
    committed_time = _utc(committed_at, "reviewed commit timestamp")
    _require(commit_endpoint == f"/repos/{repository_name}/commits/{head}", "reviewed-commit endpoint drift")
    _require(head != predecessor_head, "reviewed head does not advance the immediate predecessor")
    _require(tree != predecessor_tree, "reviewed tree does not advance the immediate predecessor")

    reviewed_tree_endpoint, reviewed_tree_payload = _decode_payload(
        sources["reviewed_tree"],
        "reviewed recursive-tree payload",
    )
    _require(
        reviewed_tree_endpoint
        == f"/repos/{repository_name}/git/trees/{tree}?recursive=1",
        "reviewed recursive-tree endpoint drift",
    )
    reviewed_tree_entries = _tree_entry_map(
        reviewed_tree_payload,
        label="reviewed recursive tree",
        repository_name=repository_name,
        expected_tree=tree,
    )
    predecessor_tree_endpoint, predecessor_tree_payload = _decode_payload(
        sources["predecessor_tree"],
        "predecessor recursive-tree payload",
    )
    _require(
        predecessor_tree_endpoint
        == f"/repos/{repository_name}/git/trees/{predecessor_tree}?recursive=1",
        "predecessor recursive-tree endpoint drift",
    )
    predecessor_tree_entries = _tree_entry_map(
        predecessor_tree_payload,
        label="predecessor recursive tree",
        repository_name=repository_name,
        expected_tree=predecessor_tree,
    )
    for relative in contract.subject_paths:
        _require(
            relative in target_files,
            f"reviewed target bundle omits canonical stage subject: {relative}",
        )
        _require(
            reviewed_tree_entries.get(relative) != predecessor_tree_entries.get(relative),
            f"canonical stage subject predates its mandatory review transition: {relative}",
        )

    gate_ids = tuple(GATE_REGISTRY)
    gate_index = gate_ids.index(gate_id)
    prior_subject_paths = {
        relative
        for prior_gate in gate_ids[:gate_index]
        for relative in GATE_REGISTRY[prior_gate].subject_paths
    }
    older_evidence_paths = {
        GATE_REGISTRY[prior_gate].evidence_relative
        for prior_gate in gate_ids[: max(0, gate_index - 1)]
    }
    immutable_prior_paths = prior_subject_paths | older_evidence_paths
    for relative in sorted(immutable_prior_paths, key=lambda item: item.encode("utf-8")):
        _require(
            relative in predecessor_tree_entries,
            f"immediate-predecessor tree drops an earlier stage/review subject: {relative}",
        )
        _require(
            reviewed_tree_entries.get(relative) == predecessor_tree_entries[relative],
            f"reviewed transition mutates an earlier stage/review subject: {relative}",
        )
    if gate_index:
        immediate_evidence = GATE_REGISTRY[gate_ids[gate_index - 1]].evidence_relative
        _require(
            immediate_evidence in target_files,
            "reviewed target bundle omits immediate-predecessor review evidence",
        )
        _require(
            reviewed_tree_entries.get(immediate_evidence)
            != predecessor_tree_entries.get(immediate_evidence),
            "immediate-predecessor review evidence predates its consuming stage",
        )
    for relative in predecessor_files:
        _require(
            relative in reviewed_tree_entries,
            f"reviewed tree drops immediate-predecessor path: {relative}",
        )
        _require(
            reviewed_tree_entries[relative] == predecessor_tree_entries.get(relative),
            f"reviewed tree mutates immediate-predecessor Git entry: {relative}",
        )
    _validate_captured_blobs(
        sources["target_blobs"],
        label="target captured blobs",
        repository_name=repository_name,
        expected_files=target_files,
        tree_entries=reviewed_tree_entries,
    )
    _validate_captured_blobs(
        sources["predecessor_blobs"],
        label="immediate-predecessor captured blobs",
        repository_name=repository_name,
        expected_files=predecessor_files,
        tree_entries=predecessor_tree_entries,
    )

    review_pages = sources["review_pages"]
    _require(type(review_pages) is list and bool(review_pages), "review page capture must be a nonempty list")
    all_reviews: list[dict[str, Any]] = []
    seen_review_ids: set[int] = set()
    seen_review_nodes: set[str] = set()
    for page_number, wrapper in enumerate(review_pages, start=1):
        endpoint, page_payload = _decode_payload(wrapper, f"review page {page_number}")
        _require(
            endpoint
            == f"/repos/{repository_name}/pulls/{pr_number}/reviews?per_page=100&page={page_number}",
            f"review page {page_number} endpoint drift",
        )
        _require(type(page_payload) is list and len(page_payload) <= 100, f"review page {page_number} is not an API array")
        if page_number != len(review_pages):
            _require(len(page_payload) == 100, "review pagination has a premature partial page")
        else:
            _require(len(page_payload) < 100, "review pagination omits the terminal page")
        for item in page_payload:
            review = _required_object(item, "review payload")
            review_id = _positive_int(_member(review, "id", "review payload"), "review ID")
            _require(review_id not in seen_review_ids, "duplicate review ID in captured review pages")
            seen_review_ids.add(review_id)
            review_node = _text(_member(review, "node_id", "review payload"), "review node ID")
            _require(review_node not in seen_review_nodes, "duplicate review node ID in captured review pages")
            seen_review_nodes.add(review_node)
            _text(_member(review, "state", "review payload"), "review state")
            association = _text(
                _member(review, "author_association", "review payload"),
                "review author association",
            )
            _require(
                association in _KNOWN_AUTHOR_ASSOCIATIONS,
                "review author association is unknown",
            )
            body = _member(review, "body", "review payload")
            _require(body is None or type(body) is str, "review body must be text or null")
            captured_review_time = _utc(
                _member(review, "submitted_at", "review payload"),
                "review submission timestamp",
            )
            _require(captured_review_time <= captured_time, "captured review postdates evidence capture")
            _git_oid(_member(review, "commit_id", "review payload"), "review commit ID")
            _api_user(_member(review, "user", "review payload"), "review author")
            _require(
                _member(review, "pull_request_url", "review payload") == pull_url,
                "captured review belongs to the wrong PR",
            )
            all_reviews.append(review)

    selected = [review for review in all_reviews if review["id"] == selected_review_id]
    _require(len(selected) == 1, "selected review ID is absent or duplicated")
    review = selected[0]
    review_node_id = _text(_member(review, "node_id", "selected review"), "selected review node ID")
    _require(
        review_node_id == selected_review_node_id,
        "selected review node ID binding drift",
    )
    _require(_member(review, "state", "selected review") == "COMMENTED", "selected review event is not COMMENTED")
    _require(_member(review, "pull_request_url", "selected review") == pull_url, "selected review belongs to the wrong PR")
    _require(_member(review, "commit_id", "selected review") == head, "selected review belongs to the wrong head")
    reviewer_login, reviewer_id = _api_user(_member(review, "user", "selected review"), "reviewer")
    _github_login(reviewer_login, "reviewer login")
    exact_same_login = reviewer_login == pull_author_login
    casefold_same_login = (
        reviewer_login.casefold() == pull_author_login.casefold()
    )
    same_user_id = reviewer_id == pull_author_id
    case_ambiguous_login = casefold_same_login and not exact_same_login
    _require(
        not case_ambiguous_login,
        "reviewer login case ambiguity",
    )
    _require(
        same_user_id == exact_same_login,
        "reviewer and pull-request-author identity partially match",
    )
    reviewer_model = (
        OWNER_SELF_REVIEW_COMMENTED_GREEN
        if same_user_id and exact_same_login
        else DISTINCT_REPOSITORY_ASSOCIATED_COMMENTED_GREEN
    )
    _require(
        declared_reviewer_model == reviewer_model,
        "declared reviewer model does not match immutable GitHub identities",
    )
    reviewer_author_association = _text(
        _member(review, "author_association", "selected review"),
        "selected reviewer author association",
    )
    _require(
        reviewer_author_association in _AUTHORIZED_REVIEW_ASSOCIATIONS,
        "selected reviewer is not repository-associated",
    )
    permission_endpoint, permission_payload = _decode_payload(
        sources["reviewer_permission"],
        "reviewer repository-permission payload",
    )
    _require(
        permission_endpoint
        == (
            f"/repos/{repository_name}/collaborators/{reviewer_login}/permission"
        ),
        "reviewer repository-permission endpoint drift",
    )
    permission = _required_object(
        permission_payload,
        "reviewer repository-permission payload",
    )
    reviewer_repository_permission = _text(
        _member(
            permission,
            "permission",
            "reviewer repository-permission payload",
        ),
        "reviewer repository permission",
    )
    _require(
        reviewer_repository_permission in _AUTHORIZED_REPOSITORY_PERMISSIONS,
        "selected reviewer lacks write-or-higher repository permission",
    )
    reviewer_repository_role_name = _text(
        _member(
            permission,
            "role_name",
            "reviewer repository-permission payload",
        ),
        "reviewer repository role name",
    )
    permission_login, permission_user_id = _api_user(
        _member(permission, "user", "reviewer repository-permission payload"),
        "repository-permission user",
    )
    _require(
        permission_login == reviewer_login and permission_user_id == reviewer_id,
        "reviewer repository-permission identity drift",
    )
    submitted_at = _text(_member(review, "submitted_at", "selected review"), "review submission timestamp")
    submitted_time = _utc(submitted_at, "review submission timestamp")
    _require(pull_created_at <= submitted_time, "selected review predates pull-request creation")
    _require(committed_time <= submitted_time, "review predates the reviewed commit bytes")
    _require(submitted_time <= captured_time, "review capture predates review submission")
    _validate_review_body(
        _member(review, "body", "selected review"),
        contract=contract,
        pr_number=pr_number,
        head=head,
        tree=tree,
        target_bundle=target_bundle,
        predecessor_head=predecessor_head,
        predecessor_tree=predecessor_tree,
        predecessor_bundle=predecessor_bundle,
        reviewer_model=reviewer_model,
        reviewer_login=reviewer_login,
        reviewer_id=reviewer_id,
        reviewer_author_association=reviewer_author_association,
        reviewer_repository_permission=reviewer_repository_permission,
    )

    for other in all_reviews:
        if other is review or other.get("commit_id") != head:
            continue
        if _first_verdict(other.get("body")) != "RED":
            continue
        other_time = _utc(_member(other, "submitted_at", "later RED review"), "later RED review timestamp")
        _require(other_time < submitted_time, "selected GREEN review is superseded by a later RED review")

    if expected_reviewer is not None:
        _require(isinstance(expected_reviewer, ReviewerPolicy), "reviewer policy has wrong type")
        if expected_reviewer.expected_login is not None:
            _require(reviewer_login == expected_reviewer.expected_login, "unexpected reviewer login")
        if expected_reviewer.expected_user_id is not None:
            _require(reviewer_id == expected_reviewer.expected_user_id, "unexpected reviewer ID")
        if expected_reviewer.expected_model is not None:
            _require(
                type(expected_reviewer.expected_model) is str
                and expected_reviewer.expected_model in _REVIEWER_MODELS,
                "configured reviewer model is unknown",
            )
            _require(
                reviewer_model == expected_reviewer.expected_model,
                "unexpected reviewer model",
            )
        if expected_reviewer.forbid_pull_request_author:
            _require(
                reviewer_model
                == DISTINCT_REPOSITORY_ASSOCIATED_COMMENTED_GREEN,
                "pull-request author cannot satisfy the configured distinct-reviewer policy",
            )

    if reviewed_blob_reader is not None:
        _corroborate_local_blobs(
            head,
            predecessor_head,
            target_files,
            predecessor_files,
            reviewed_blob_reader,
        )

    identity = ReviewEvidenceIdentity(
        gate_id=gate_id,
        evidence_relative=contract.evidence_relative,
        evidence_sha256=evidence_digest,
        repository_full_name=repository_name,
        repository_id=repository_id,
        pull_request_number=pr_number,
        pull_request_node_id=pull_node_id,
        pull_request_author_login=pull_author_login,
        pull_request_author_id=pull_author_id,
        review_id=selected_review_id,
        review_node_id=review_node_id,
        reviewer_login=reviewer_login,
        reviewer_id=reviewer_id,
        reviewer_model=reviewer_model,
        reviewer_author_association=reviewer_author_association,
        reviewer_repository_permission=reviewer_repository_permission,
        reviewer_repository_role_name=reviewer_repository_role_name,
        submitted_at=submitted_at,
        reviewed_commit_committed_at=committed_at,
        captured_at=captured_at,
        reviewed_head=head,
        reviewed_tree=tree,
        target_stage_id=contract.target_stage_id,
        target_bundle_sha256=target_bundle,
        predecessor_stage_id=contract.predecessor_stage_id,
        predecessor_reviewed_head=predecessor_head,
        predecessor_reviewed_tree=predecessor_tree,
        predecessor_bundle_sha256=predecessor_bundle,
    )
    _validate_reuse(identity, lineage)
    return identity


__all__ = [
    "CAPTURE_INTEGRITY_STATUS",
    "CAPTURE_METHOD",
    "EVIDENCE_DIRECTORY",
    "GATE_REGISTRY",
    "HISTORICAL_SEED_NON_REUSE_FIELDS",
    "ORIGIN_AUTHENTICATION_STATUS",
    "OWNER_SELF_REVIEW_COMMENTED_GREEN",
    "DISTINCT_REPOSITORY_ASSOCIATED_COMMENTED_GREEN",
    "REPOSITORY_FULL_NAME",
    "REPOSITORY_ID",
    "ROOT",
    "ReviewEvidenceError",
    "ReviewEvidenceIdentity",
    "ReviewerPolicy",
    "SEED_REVIEWS",
    "SCHEMA_1_1_GATE_NON_REUSE_FIELDS",
    "bundle_sha256",
    "canonical_json_bytes",
    "evidence_path",
    "require_no_review_evidence",
    "validate_gate_evidence",
]
