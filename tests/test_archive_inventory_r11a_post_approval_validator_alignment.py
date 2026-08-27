from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from unittest import mock

from governance import r11a_post_approval_context as context
from governance import validate_r11a_activation_r4 as activation
from governance import validate_r11a_approval_r4 as approval_r4
from governance import validate_r11a_execution_release_r4 as release
from governance import validate_r11a_execution_artifact_r7 as execution_artifact
from governance import validate_r11a_g2_owner_approval as g2
from governance import validate_r11a_post_approval_validator_alignment as alignment
from governance import validate_r11a_role_attestation_r4 as role
from governance import validate_r11a_role_preflight_evidence_r4 as preflight
from governance import validate_r11a_runtime_binding_r7 as runtime_binding
from governance import validate_r11a_workflow_installation_r4 as installation
from governance import r11a_stage_common_r4 as common


ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_COMMIT = "a" * 40
ZERO_SHA = "0" * 64
VALIDATION_ERRORS = (
    common.StageValidationError,
    context.PostApprovalContextError,
    runtime_binding.RuntimeBindingError,
)
BYTECODE_SUFFIXES = frozenset({".pyc", ".pyo"})


class RepositoryIsolationError(RuntimeError):
    pass


def is_bytecode_residue_path(relative: str) -> bool:
    path = PurePosixPath(relative)
    return any(part.casefold() == "__pycache__" for part in path.parts) or (
        path.suffix.casefold() in BYTECODE_SUFFIXES
    )


def require_no_tracked_bytecode(paths: frozenset[str]) -> None:
    residue = sorted(
        (relative for relative in paths if is_bytecode_residue_path(relative)),
        key=lambda relative: relative.encode("utf-8"),
    )
    if residue:
        raise RepositoryIsolationError(
            "tracked Python bytecode/cache residue prohibited: " + ", ".join(residue)
        )


def require_safe_source_metadata(root: Path) -> None:
    stack: list[tuple[Path, PurePosixPath | None]] = [(root, None)]
    while stack:
        directory, prefix = stack.pop()
        try:
            entries = sorted(
                os.scandir(directory),
                key=lambda entry: entry.name.encode("utf-8"),
                reverse=True,
            )
        except OSError as exc:
            raise RepositoryIsolationError(
                f"cannot scan isolation source: {directory}"
            ) from exc
        for entry in entries:
            if entry.name == ".git":
                if prefix is None:
                    continue
                relative_git = (prefix / entry.name).as_posix()
                raise RepositoryIsolationError(
                    f"nested repository metadata prohibited: {relative_git}"
                )
            relative_path = (
                PurePosixPath(entry.name) if prefix is None else prefix / entry.name
            )
            relative = relative_path.as_posix()
            try:
                information = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise RepositoryIsolationError(
                    f"cannot lstat isolation source entry: {relative}"
                ) from exc
            cache_ancestors = tuple(
                part
                for part in relative_path.parts[:-1]
                if part.casefold() == "__pycache__"
            )
            if stat.S_ISLNK(information.st_mode):
                raise RepositoryIsolationError(
                    f"symlink prohibited in isolation source: {relative}"
                )
            if stat.S_ISDIR(information.st_mode):
                if cache_ancestors:
                    raise RepositoryIsolationError(
                        f"nested directory prohibited in process cache: {relative}"
                    )
                stack.append((Path(entry.path), relative_path))
                continue
            if not stat.S_ISREG(information.st_mode):
                raise RepositoryIsolationError(
                    f"special file prohibited in isolation source: {relative}"
                )
            if information.st_nlink != 1:
                raise RepositoryIsolationError(
                    f"hard-link prohibited in isolation source: {relative}"
                )
            if cache_ancestors and (
                PurePosixPath(relative).suffix.casefold() not in BYTECODE_SUFFIXES
            ):
                raise RepositoryIsolationError(
                    f"non-bytecode entry prohibited in process cache: {relative}"
                )
            if (
                PurePosixPath(relative).suffix.casefold() in BYTECODE_SUFFIXES
                and not cache_ancestors
            ):
                raise RepositoryIsolationError(
                    f"standalone bytecode prohibited in isolation source: {relative}"
                )


def tracked_repository_paths(root: Path) -> frozenset[str]:
    index_path = root / ".git/index"
    try:
        raw = index_path.read_bytes()
    except OSError as exc:
        raise RepositoryIsolationError("cannot read Git index") from exc
    if len(raw) < 32 or raw[:4] != b"DIRC":
        raise RepositoryIsolationError("malformed Git index header")
    version, entry_count = struct.unpack(">II", raw[4:12])
    if version not in {2, 3}:
        raise RepositoryIsolationError(f"unsupported Git index version: {version}")
    if hashlib.sha1(raw[:-20]).digest() != raw[-20:]:
        raise RepositoryIsolationError("Git index checksum mismatch")

    offset = 12
    content_end = len(raw) - 20
    paths: set[str] = set()
    for _ in range(entry_count):
        entry_start = offset
        fixed_end = offset + 62
        if fixed_end > content_end:
            raise RepositoryIsolationError("truncated Git index entry")
        fixed = struct.unpack(">10I20sH", raw[offset:fixed_end])
        mode = fixed[6]
        flags = fixed[-1]
        offset = fixed_end
        if flags & 0x3000:
            raise RepositoryIsolationError("unmerged Git index entry prohibited")
        if flags & 0x4000:
            if version != 3 or offset + 2 > content_end:
                raise RepositoryIsolationError("malformed extended Git index entry")
            offset += 2

        encoded_length = flags & 0x0FFF
        if encoded_length < 0x0FFF:
            name_end = offset + encoded_length
            if name_end >= content_end or raw[name_end] != 0:
                raise RepositoryIsolationError("malformed Git index path length")
        else:
            name_end = raw.find(b"\0", offset, content_end)
            if name_end < 0:
                raise RepositoryIsolationError("unterminated Git index path")
        try:
            relative = raw[offset:name_end].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RepositoryIsolationError("Git index path is not UTF-8") from exc
        if not relative or relative in paths:
            raise RepositoryIsolationError("empty or duplicate Git index path")
        file_type = stat.S_IFMT(mode)
        if file_type != stat.S_IFREG or mode not in {0o100644, 0o100755}:
            raise RepositoryIsolationError(
                f"tracked symlink, submodule, or unsupported mode prohibited: {relative}"
            )
        paths.add(relative)

        offset = name_end + 1
        padding = (8 - ((offset - entry_start) % 8)) % 8
        if offset + padding > content_end or any(raw[offset : offset + padding]):
            raise RepositoryIsolationError("malformed Git index entry padding")
        offset += padding

    while offset < content_end:
        if offset + 8 > content_end:
            raise RepositoryIsolationError("truncated Git index extension")
        signature = raw[offset : offset + 4]
        extension_length = struct.unpack(">I", raw[offset + 4 : offset + 8])[0]
        offset += 8
        if offset + extension_length > content_end:
            raise RepositoryIsolationError("truncated Git index extension data")
        if signature == b"link":
            raise RepositoryIsolationError("split Git index prohibited")
        offset += extension_length
    return frozenset(paths)


def manifest_bound_repository_paths(root: Path) -> frozenset[str]:
    manifest = root / "governance/REPOSITORY_MANIFEST.sha256"
    try:
        rows = manifest.read_bytes().splitlines()
    except OSError as exc:
        raise RepositoryIsolationError("cannot read repository manifest") from exc
    paths: set[str] = set()
    for row in rows:
        digest, separator, encoded_path = row.partition(b"  ")
        if (
            separator != b"  "
            or len(digest) != 64
            or any(character not in b"0123456789abcdef" for character in digest)
            or not encoded_path
        ):
            raise RepositoryIsolationError("malformed repository manifest row")
        try:
            relative = encoded_path.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RepositoryIsolationError(
                "repository manifest path is not UTF-8"
            ) from exc
        if relative in paths:
            raise RepositoryIsolationError(
                f"duplicate repository manifest path: {relative}"
            )
        paths.add(relative)
    return frozenset(paths)


def require_reconciled_repository_inventory(root: Path) -> None:
    tracked = tracked_repository_paths(root)
    require_no_tracked_bytecode(tracked)
    manifest_paths = manifest_bound_repository_paths(root)
    expected_manifest_paths = tracked - {
        "governance/REPOSITORY_MANIFEST.sha256"
    }
    if manifest_paths != expected_manifest_paths:
        raise RepositoryIsolationError("repository manifest path coverage drift")


def ignore_process_bytecode(_directory: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name == ".git"
        or name.casefold() == "__pycache__"
    }


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def false_mapping(keys: frozenset[str]) -> dict[str, bool]:
    return {key: False for key in sorted(keys, key=lambda item: item.encode("utf-8"))}


def green_review(prefix: str, review_id: int, oid_digit: str) -> dict[str, object]:
    return {
        f"{prefix}_completed": True,
        f"{prefix}_id": review_id,
        f"{prefix}_event": "COMMENTED",
        f"{prefix}_verdict": "GREEN",
        f"{prefix}ed_head": oid_digit * 40,
        f"{prefix}ed_tree": oid_digit * 40,
    }


class PostApprovalValidatorAlignmentTests(unittest.TestCase):
    def copy_repository(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        require_reconciled_repository_inventory(ROOT)
        require_safe_source_metadata(ROOT)
        temporary = tempfile.TemporaryDirectory()
        destination = Path(temporary.name) / "repository"
        shutil.copytree(
            ROOT,
            destination,
            symlinks=True,
            ignore=ignore_process_bytecode,
        )
        return temporary, destination

    def write_json(self, root: Path, relative: str, value: object) -> bytes:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = canonical_json(value)
        path.write_bytes(raw)
        return raw

    def role_record(self, root: Path = ROOT) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "attestation_id": "ATTEST_HL_ARCHIVE_R11A_SUCCESSOR_ROLE_001",
            "status": "ROLE_CREATED_POLICIES_APPLIED_AWAITING_STS_PREFLIGHT",
            "alignment_id": common.ALIGNMENT_ID,
            "alignment_record_sha256": common.sha256(
                root, common.ALIGNMENT_RELATIVE
            ),
            "approval_receipt_sha256": common.APPROVAL_RECEIPT_SHA,
            "g2_review_id": common.G2_REVIEW_ID,
            "alignment_review_completed": True,
            "alignment_review_id": 1,
            "alignment_review_event": "COMMENTED",
            "alignment_review_verdict": "GREEN",
            "alignment_reviewed_head": "c" * 40,
            "alignment_reviewed_tree": "d" * 40,
            "identity_creation_and_configuration_review_completed": True,
            "identity_creation_and_configuration_review_id": 2,
            "identity_creation_and_configuration_review_event": "COMMENTED",
            "identity_creation_and_configuration_review_verdict": "GREEN",
            "identity_creation_and_configuration_reviewed_head": "e" * 40,
            "identity_creation_and_configuration_reviewed_tree": "f" * 40,
            "account_id": "630956766927",
            "role_arn": common.ROLE_ARN,
            "role_max_session_duration_seconds": 21600,
            "persistent_permission_resource_count": 72,
            "persistent_permission_resources_match_exact_selection": True,
            "additional_managed_policies_attached": False,
            "additional_inline_policies_attached": False,
            "additional_role_created": False,
            "reusable_credentials_present": False,
            "access_keys_present": False,
            "secrets_present": False,
            "existing_r11_role_mutated": False,
            "existing_r11_role_reused": False,
            "trust_policy_sha256": common.APPROVED_TRUST_SHA,
            "permission_policy_sha256": common.APPROVED_PERMISSION_SHA,
            "s3_requests_performed_during_operator_step": 0,
            "object_bytes_downloaded_during_operator_step": 0,
            "sts_only_preflight_required": True,
            "sts_only_preflight_completed": False,
            "downstream_authorizations": false_mapping(common.DOWNSTREAM_AUTHORITY_KEYS),
            "trading_authorizations": false_mapping(common.TRADING_AUTHORITY_KEYS),
        }

    def preflight_candidate_record(self, root: Path) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "preflight_candidate_id": "CANDIDATE_HL_ARCHIVE_R11A_STS_ONLY_PREFLIGHT_001",
            "status": "CANDIDATE_AWAITING_INDEPENDENT_STS_ONLY_PREFLIGHT_RELEASE_REVIEW_NO_AWS",
            **green_review("role_attestation_review", 3, "3"),
            "role_attestation_sha256": common.sha256(
                root, common.ROLE_ATTESTATION_RELATIVE
            ),
            "alignment_record_sha256": common.sha256(
                root, common.ALIGNMENT_RELATIVE
            ),
            "approval_receipt_sha256": common.APPROVAL_RECEIPT_SHA,
            "permission_policy_sha256": common.APPROVED_PERMISSION_SHA,
            "oidc_trust_policy_sha256": common.APPROVED_TRUST_SHA,
            "account_id": "630956766927",
            "role_arn": common.ROLE_ARN,
            "dispatch_ref_required": "refs/heads/main",
            "workflow_run_attempt_required": 1,
            "maximum_sts_get_caller_identity_calls": 1,
            "authorized_aws_actions_after_release": ["sts:GetCallerIdentity"],
            "sts_call_authorized_by_candidate": False,
            "single_use_sts_preflight_eligible_after_release": True,
            "s3_requests_authorized": False,
            "requester_pays_authorized": False,
            "object_body_access_authorized": False,
            "decompression_authorized": False,
            "workflow_installation_authorized": False,
            "diagnostic_execution_authorized": False,
            "network_requests_executed_by_candidate": 0,
            "aws_iam_mutations_executed_by_candidate": 0,
            "downstream_authorizations": false_mapping(common.DOWNSTREAM_AUTHORITY_KEYS),
            "trading_authorizations": false_mapping(common.TRADING_AUTHORITY_KEYS),
        }

    def preflight_release_record(self, root: Path) -> dict[str, object]:
        candidate = json.loads(
            (root / common.PREFLIGHT_CANDIDATE_RELATIVE).read_bytes()
        )
        return {
            "schema_version": "1.0",
            "preflight_release_id": "RELEASE_HL_ARCHIVE_R11A_STS_ONLY_PREFLIGHT_001",
            "preflight_candidate_id": candidate["preflight_candidate_id"],
            "status": "RELEASED_FOR_EXACTLY_ONE_STS_GET_CALLER_IDENTITY_NO_S3",
            "preflight_candidate_sha256": common.sha256(
                root, common.PREFLIGHT_CANDIDATE_RELATIVE
            ),
            **green_review("candidate_review", 4, "4"),
            "role_attestation_sha256": common.sha256(
                root, common.ROLE_ATTESTATION_RELATIVE
            ),
            "alignment_record_sha256": common.sha256(
                root, common.ALIGNMENT_RELATIVE
            ),
            "approval_receipt_sha256": common.APPROVAL_RECEIPT_SHA,
            "permission_policy_sha256": common.APPROVED_PERMISSION_SHA,
            "oidc_trust_policy_sha256": common.APPROVED_TRUST_SHA,
            "account_id": "630956766927",
            "role_arn": common.ROLE_ARN,
            "authorized_aws_actions": ["sts:GetCallerIdentity"],
            "maximum_sts_get_caller_identity_calls": 1,
            "single_sts_get_caller_identity_authorized": True,
            "s3_requests_authorized": False,
            "requester_pays_authorized": False,
            "object_body_access_authorized": False,
            "decompression_authorized": False,
            "workflow_installation_authorized": False,
            "release_or_activation_authorized": False,
            "diagnostic_execution_authorized": False,
            "single_use": True,
            "release_consumed": False,
            "rerun_authorized": False,
            "network_requests_executed_by_release": 0,
            "aws_iam_mutations_executed_by_release": 0,
            "downstream_authorizations": false_mapping(common.DOWNSTREAM_AUTHORITY_KEYS),
            "trading_authorizations": false_mapping(common.TRADING_AUTHORITY_KEYS),
        }

    def preflight_records(
        self, root: Path
    ) -> tuple[dict[str, object], dict[str, object]]:
        preflight_release = json.loads(
            (root / common.PREFLIGHT_RELEASE_RELATIVE).read_bytes()
        )
        evidence = {
            "schema_version": "1.0",
            "preflight_id": "HL-ARCHIVE-R11A-SUCCESSOR-ROLE-STS-PREFLIGHT-001",
            "status": "R11A_STS_PREFLIGHT_PASS",
            "technical_result": "DEDICATED_R11A_ROLE_ASSUMEABLE_FROM_CANONICAL_MAIN",
            "preflight_release_id": preflight_release["preflight_release_id"],
            "preflight_release_sha256": common.sha256(
                root, common.PREFLIGHT_RELEASE_RELATIVE
            ),
            "role_attestation_sha256": ZERO_SHA,
            "alignment_record_sha256": common.sha256(root, common.ALIGNMENT_RELATIVE),
            "approval_receipt_sha256": common.APPROVAL_RECEIPT_SHA,
            "permission_policy_sha256": common.APPROVED_PERMISSION_SHA,
            "oidc_trust_policy_sha256": common.APPROVED_TRUST_SHA,
            "expected_role_arn": common.ROLE_ARN,
            "observed_account_id": "630956766927",
            "observed_assumed_role_session_arn": (
                "arn:aws:sts::630956766927:assumed-role/"
                "onchain-wallet-intelligence-hl-archive-identity-r11a/"
                "HLArchiveR11ASTSPreflight"
            ),
            "dispatch_sha": SYNTHETIC_COMMIT,
            "dispatch_ref": "refs/heads/main",
            "workflow_run_attempt": 1,
            "explicit_sts_caller_identity_calls": 1,
            "authorized_aws_actions": ["sts:GetCallerIdentity"],
            "s3_requests_authorized": False,
            "requester_pays_authorized": False,
            "object_body_access_authorized": False,
            "decompression_authorized": False,
            "workflow_installation_authorized": False,
            "release_authorized": False,
            "activation_authorized": False,
            "diagnostic_execution_authorized": False,
            "s3_http_request_count": 0,
            "object_bytes_downloaded": 0,
            "downstream_authorizations": false_mapping(common.DOWNSTREAM_AUTHORITY_KEYS),
            "trading_authorizations": false_mapping(common.TRADING_AUTHORITY_KEYS),
        }
        consumption = {
            "schema_version": "1.0",
            "consumption_id": "CONSUME_HL_ARCHIVE_R11A_STS_PREFLIGHT_RELEASE_001",
            "status": "CONSUMED_SUCCESS",
            "preflight_id": evidence["preflight_id"],
            "preflight_release_id": preflight_release["preflight_release_id"],
            "preflight_release_sha256": common.sha256(
                root, common.PREFLIGHT_RELEASE_RELATIVE
            ),
            "preflight_evidence_sha256": "",
            "preflight_release_consumed": True,
            "rerun_authorized": False,
            "s3_requests_executed": 0,
            "object_bytes_downloaded": 0,
            "downstream_authorizations": false_mapping(common.DOWNSTREAM_AUTHORITY_KEYS),
            "trading_authorizations": false_mapping(common.TRADING_AUTHORITY_KEYS),
        }
        return evidence, consumption

    def add_role(self, root: Path) -> dict[str, object]:
        value = self.role_record(root)
        self.write_json(root, common.ROLE_ATTESTATION_RELATIVE, value)
        return value

    def add_preflight_candidate(self, root: Path) -> dict[str, object]:
        value = self.preflight_candidate_record(root)
        self.write_json(root, common.PREFLIGHT_CANDIDATE_RELATIVE, value)
        return value

    def add_preflight_release(self, root: Path) -> dict[str, object]:
        value = self.preflight_release_record(root)
        self.write_json(root, common.PREFLIGHT_RELEASE_RELATIVE, value)
        return value

    def add_preflight(self, root: Path) -> tuple[dict[str, object], dict[str, object]]:
        evidence, consumption = self.preflight_records(root)
        evidence["role_attestation_sha256"] = common.sha256(
            root, common.ROLE_ATTESTATION_RELATIVE
        )
        evidence["alignment_record_sha256"] = common.sha256(
            root, common.ALIGNMENT_RELATIVE
        )
        raw = self.write_json(root, common.PREFLIGHT_EVIDENCE_RELATIVE, evidence)
        consumption["preflight_evidence_sha256"] = hashlib.sha256(raw).hexdigest()
        self.write_json(root, common.PREFLIGHT_CONSUMPTION_RELATIVE, consumption)
        return evidence, consumption

    def installation_record(self, root: Path) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "installation_id": "HL-ARCHIVE-R11A-WORKFLOW-INSTALLATION-001",
            "status": "INSTALLED_AWAITING_SEPARATE_EXECUTION_RELEASE",
            **green_review("sts_preflight_review", 5, "5"),
            "preflight_candidate_sha256": common.sha256(
                root, common.PREFLIGHT_CANDIDATE_RELATIVE
            ),
            "preflight_release_sha256": common.sha256(
                root, common.PREFLIGHT_RELEASE_RELATIVE
            ),
            "preflight_evidence_sha256": common.sha256(
                root, common.PREFLIGHT_EVIDENCE_RELATIVE
            ),
            "preflight_consumption_sha256": common.sha256(
                root, common.PREFLIGHT_CONSUMPTION_RELATIVE
            ),
            "workflow_name": common.WORKFLOW_NAME,
            "candidate_workflow_path": common.CANDIDATE_RELATIVE,
            "workflow_path": common.WORKFLOW_RELATIVE,
            "workflow_sha256": common.APPROVED_WORKFLOW_SHA,
            "runtime_pricing_source_path": common.PRICING_SOURCE_RELATIVE,
            "runtime_pricing_source_sha256": common.APPROVED_PRICING_SOURCE_SHA,
            "runtime_pricing_installed_path": common.PRICING_TARGET_RELATIVE,
            "runtime_pricing_installed_sha256": common.APPROVED_PRICING_SOURCE_SHA,
            "single_workflow_dispatch_authorized": False,
            "execution_release_present": False,
            "canonical_activation_present": False,
            "aws_oidc_authorized_now": False,
            "get_object_authorized_now": False,
            "network_requests_executed_by_installation": 0,
            "aws_iam_mutations_executed_by_installation": 0,
            "downstream_authorizations": false_mapping(common.DOWNSTREAM_AUTHORITY_KEYS),
            "trading_authorizations": false_mapping(common.TRADING_AUTHORITY_KEYS),
        }

    def add_installation(self, root: Path) -> dict[str, object]:
        source = root / common.PRICING_SOURCE_RELATIVE
        target = root / common.PRICING_TARGET_RELATIVE
        target.write_bytes(source.read_bytes())
        candidate = root / common.CANDIDATE_RELATIVE
        installed = root / common.WORKFLOW_RELATIVE
        installed.parent.mkdir(parents=True, exist_ok=True)
        installed.write_bytes(candidate.read_bytes())
        value = self.installation_record(root)
        self.write_json(root, common.INSTALLATION_RELATIVE, value)
        return value

    def release_candidate_record(self, root: Path) -> dict[str, object]:
        value: dict[str, object] = {
            "schema_version": "1.0",
            "execution_release_candidate_id": (
                "CANDIDATE_RELEASE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001"
            ),
            "status": "CANDIDATE_AWAITING_INDEPENDENT_EXECUTION_RELEASE_REVIEW_NO_EXECUTION",
            **green_review("workflow_installation_review", 6, "6"),
            "diagnostic_id": common.DIAGNOSTIC_ID,
            "installation_contract_sha256": common.sha256(
                root, common.INSTALLATION_RELATIVE
            ),
            "approval_receipt_sha256": common.APPROVAL_RECEIPT_SHA,
            "workflow_sha256": common.sha256(root, common.WORKFLOW_RELATIVE),
            "runtime_pricing_snapshot_sha256": common.sha256(
                root, common.PRICING_TARGET_RELATIVE
            ),
            "selection_sha256": common.sha256(root, common.SELECTION_RELATIVE),
            "runner_sha256": common.sha256(root, common.RUNNER_RELATIVE),
            "validator_sha256": common.sha256(
                root, common.ARTIFACT_VALIDATOR_RELATIVE
            ),
            **release.EXPECTED_CAPS,
            "single_workflow_dispatch_authorized": False,
            "owner_dispatch_required": True,
            "execution_release_present": False,
            "runtime_binding_present": False,
            "canonical_activation_present": False,
            "network_requests_executed_by_candidate": 0,
            "aws_iam_mutations_executed_by_candidate": 0,
            "downstream_authorizations": false_mapping(common.DOWNSTREAM_AUTHORITY_KEYS),
            "trading_authorizations": false_mapping(common.TRADING_AUTHORITY_KEYS),
        }
        return value

    def add_release_candidate(self, root: Path) -> dict[str, object]:
        value = self.release_candidate_record(root)
        self.write_json(root, common.RELEASE_CANDIDATE_RELATIVE, value)
        return value

    def release_record(self, root: Path) -> dict[str, object]:
        candidate = json.loads((root / common.RELEASE_CANDIDATE_RELATIVE).read_bytes())
        value: dict[str, object] = {
            "schema_version": "1.0",
            "execution_release_id": (
                "RELEASE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001"
            ),
            "execution_release_candidate_id": candidate[
                "execution_release_candidate_id"
            ],
            "status": "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R11A_RUN",
            **green_review("release_candidate_review", 7, "7"),
            "release_candidate_sha256": common.sha256(
                root, common.RELEASE_CANDIDATE_RELATIVE
            ),
            "implementation_contract_sha256": common.sha256(
                root, common.IMPLEMENTATION_RELATIVE
            ),
            "approval_receipt_sha256": common.APPROVAL_RECEIPT_SHA,
            "approval_text_sha256": common.sha256(
                root, common.APPROVAL_TEXT_RELATIVE
            ),
            "pricing_snapshot_sha256": common.sha256(
                root, common.PRICING_TARGET_RELATIVE
            ),
            "workflow_sha256": common.sha256(root, common.WORKFLOW_RELATIVE),
            "collector_sha256": common.sha256(root, common.RUNNER_RELATIVE),
            "validator_sha256": common.sha256(
                root, common.ARTIFACT_VALIDATOR_RELATIVE
            ),
            "selection_sha256": common.sha256(root, common.SELECTION_RELATIVE),
            **release.EXPECTED_CAPS,
            "single_workflow_dispatch_authorized_by_release": False,
            "single_workflow_dispatch_eligible_after_activation": True,
            "rerun_authorized": False,
            "release_consumed": False,
            "canonical_activation_required": True,
            "canonical_activation_present": False,
            "network_requests_executed_by_release": 0,
            "aws_iam_mutations_executed_by_release": 0,
            "downstream_authorizations": false_mapping(common.DOWNSTREAM_AUTHORITY_KEYS),
            "trading_authorizations": false_mapping(common.TRADING_AUTHORITY_KEYS),
        }
        return value

    def add_release(self, root: Path) -> dict[str, object]:
        value = self.release_record(root)
        raw = self.write_json(root, common.RELEASE_RELATIVE, value)
        digest = hashlib.sha256(raw).hexdigest()
        (root / common.RELEASE_DIGEST_RELATIVE).write_text(
            digest + "\n", encoding="ascii"
        )
        return value

    def activation_record(self, root: Path) -> dict[str, object]:
        release_value = json.loads((root / common.RELEASE_RELATIVE).read_bytes())
        return {
            "schema_version": "1.0",
            "activation_id": "ACTIVATE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001",
            "status": "ACTIVATED_FOR_EXACTLY_ONE_CANONICAL_R11A_RUN",
            **green_review("execution_release_review", 8, "8"),
            "execution_release_id": release_value["execution_release_id"],
            "execution_release_candidate_sha256": common.sha256(
                root, common.RELEASE_CANDIDATE_RELATIVE
            ),
            "execution_release_blob_sha256": common.sha256(
                root, common.RELEASE_RELATIVE
            ),
            "activation_base_commit": "b" * 40,
            "canonical_activation_merge_commit": SYNTHETIC_COMMIT,
            "dispatch_ref_required": "refs/heads/main",
            "workflow_name": common.WORKFLOW_NAME,
            "workflow_path": common.WORKFLOW_RELATIVE,
            "workflow_sha256": common.sha256(root, common.WORKFLOW_RELATIVE),
            "automatic_dispatch_authorized": False,
            "reusable_activation_authorized": False,
            "maximum_runs": 1,
            "single_workflow_dispatch_authorized": True,
            "workflow_run_attempt_required": 1,
            "rerun_authorized": False,
            "release_consumed": False,
            "runtime_binding_present": False,
            "single_use_window_start_utc": "2026-08-26T00:00:00Z",
            "explicit_owner_dispatch_required": True,
            "network_requests_executed_by_activation": 0,
            "object_bytes_downloaded_by_activation": 0,
            "aws_iam_mutations_executed_by_activation": 0,
            "downstream_authorizations": false_mapping(common.DOWNSTREAM_AUTHORITY_KEYS),
            "trading_authorizations": false_mapping(common.TRADING_AUTHORITY_KEYS),
        }

    def add_activation(self, root: Path) -> dict[str, object]:
        value = self.activation_record(root)
        self.write_json(root, common.ACTIVATION_RELATIVE, value)
        return value

    def runtime_binding_record(self, root: Path) -> dict[str, object]:
        bound_files = {
            relative: common.sha256(root, relative)
            for relative in runtime_binding.REQUIRED_BOUND_PATHS
        }
        return {
            "schema_version": "1.0",
            "binding_id": "HL-ARCHIVE-R11A-RUNTIME-BINDING-R7-001",
            "diagnostic_id": common.DIAGNOSTIC_ID,
            "implementation_id": runtime_binding.IMPLEMENTATION_ID,
            "approval_id": common.APPROVAL_ID,
            "alignment_id": common.ALIGNMENT_ID,
            "status": "ACTIVE_FOR_EXACTLY_ONE_CANONICAL_R11A_R7_RUN",
            **green_review("activation_review", 9, "9"),
            "canonical_commit": SYNTHETIC_COMMIT,
            "workflow_name": common.WORKFLOW_NAME,
            "workflow_file": common.WORKFLOW_FILE,
            "candidate_workflow_path": common.CANDIDATE_RELATIVE,
            "installed_workflow_path": common.WORKFLOW_RELATIVE,
            "runtime_pricing_source_path": common.PRICING_SOURCE_RELATIVE,
            "runtime_pricing_installed_path": common.PRICING_TARGET_RELATIVE,
            "single_use_window_start_utc": "2026-08-26T00:00:00Z",
            "bound_files": bound_files,
            "runtime_authority": dict(runtime_binding._core.EXPECTED_RUNTIME_AUTHORITY),
            "downstream_authorizations": false_mapping(common.DOWNSTREAM_AUTHORITY_KEYS),
            "science_state": dict(runtime_binding._core.EXPECTED_SCIENCE_STATE),
            "trading_authorizations": false_mapping(common.TRADING_AUTHORITY_KEYS),
            "r11_closed": False,
            "r12_ready": False,
        }

    def add_runtime_binding(self, root: Path) -> dict[str, object]:
        value = self.runtime_binding_record(root)
        self.write_json(root, common.BINDING_RELATIVE, value)
        return value

    def add_complete_offline_ladder(self, root: Path) -> dict[str, dict[str, object]]:
        values: dict[str, dict[str, object]] = {}
        values["role"] = self.add_role(root)
        values["preflight_candidate"] = self.add_preflight_candidate(root)
        values["preflight_release"] = self.add_preflight_release(root)
        evidence, consumption = self.add_preflight(root)
        values["preflight"] = evidence
        values["consumption"] = consumption
        values["installation"] = self.add_installation(root)
        values["release_candidate"] = self.add_release_candidate(root)
        values["release"] = self.add_release(root)
        values["activation"] = self.add_activation(root)
        values["runtime_binding"] = self.add_runtime_binding(root)
        return values

    def validate_role_in_complete_fixture(self, root: Path) -> dict[str, object]:
        return role.validate(
            root,
            permitted_successor_paths=common.KNOWN_SUCCESSOR_PATHS,
            runtime_pricing_projection_permitted=True,
        )

    def validate_preflight_in_complete_fixture(self, root: Path) -> dict[str, object]:
        return preflight.validate(
            root,
            permitted_successor_paths=common.KNOWN_SUCCESSOR_PATHS,
            runtime_pricing_projection_permitted=True,
        )

    def validate_preflight_candidate_in_complete_fixture(
        self, root: Path
    ) -> dict[str, object]:
        return preflight.validate_candidate(
            root,
            permitted_successor_paths=common.KNOWN_SUCCESSOR_PATHS,
            runtime_pricing_projection_permitted=True,
        )

    def validate_preflight_release_in_complete_fixture(
        self, root: Path
    ) -> dict[str, object]:
        return preflight.validate_release(
            root,
            permitted_successor_paths=common.KNOWN_SUCCESSOR_PATHS,
            runtime_pricing_projection_permitted=True,
        )

    def validate_candidate_in_complete_fixture(self, root: Path) -> dict[str, object]:
        return release.validate_candidate(
            root,
            permitted_successor_paths=common.KNOWN_SUCCESSOR_PATHS,
        )

    def validate_installation_in_complete_fixture(
        self, root: Path
    ) -> dict[str, object]:
        return installation.validate(
            root,
            permitted_successor_paths=common.KNOWN_SUCCESSOR_PATHS,
        )

    def validate_release_in_complete_fixture(self, root: Path) -> dict[str, object]:
        return release.validate(
            root,
            permitted_successor_paths=common.KNOWN_SUCCESSOR_PATHS,
        )

    def validate_activation_in_complete_fixture(
        self, root: Path
    ) -> dict[str, object]:
        return activation.validate(
            root,
            permitted_successor_paths=common.KNOWN_SUCCESSOR_PATHS,
        )

    def validate_runtime_in_complete_fixture(self, root: Path) -> dict[str, object]:
        return runtime_binding.validate(SYNTHETIC_COMMIT, 1, root=root)

    def artifact_context(
        self,
        phase: str,
        *,
        bound_root: Path | None = None,
    ) -> dict[str, object]:
        value: dict[str, object] = {
            "schema_version": "2.0",
            "diagnostic_id": common.DIAGNOSTIC_ID,
            "implementation_id": runtime_binding.IMPLEMENTATION_ID,
            "execution_phase": phase,
            "event_name": "workflow_dispatch",
            "dispatch_ref": "refs/heads/main",
            "dispatch_sha": SYNTHETIC_COMMIT,
            "checked_out_commit": SYNTHETIC_COMMIT,
            "workflow_run_id": 1,
            "workflow_run_attempt": 1,
            "workflow_start_epoch_ns": 1,
            "repository": g2.REPOSITORY,
            "workflow_name": common.WORKFLOW_NAME,
            "principal_observed": bound_root is not None,
            "s3_requests_executed": 0,
            "object_bytes_downloaded": 0,
            "rerun_authorized": False,
        }
        if bound_root is None:
            return value
        release_value = json.loads(
            (bound_root / common.RELEASE_RELATIVE).read_bytes()
        )
        activation_value = json.loads(
            (bound_root / common.ACTIVATION_RELATIVE).read_bytes()
        )
        value.update(
            {
                "approval_id": common.APPROVAL_ID,
                "approval_text_sha256": common.sha256(
                    bound_root, common.APPROVAL_TEXT_RELATIVE
                ),
                "execution_release_id": release_value["execution_release_id"],
                "execution_release_blob_sha256": common.sha256(
                    bound_root, common.RELEASE_RELATIVE
                ),
                "activation_id": activation_value["activation_id"],
                "implementation_contract_sha256": common.sha256(
                    bound_root, common.IMPLEMENTATION_RELATIVE
                ),
                "workflow_sha256": common.sha256(
                    bound_root, common.WORKFLOW_RELATIVE
                ),
                "collector_sha256": common.sha256(
                    bound_root, common.RUNNER_RELATIVE
                ),
                "validator_sha256": common.sha256(
                    bound_root, common.ARTIFACT_VALIDATOR_RELATIVE
                ),
                "selection_sha256": common.sha256(
                    bound_root, common.SELECTION_RELATIVE
                ),
                "pricing_snapshot_sha256": common.sha256(
                    bound_root, common.PRICING_TARGET_RELATIVE
                ),
                "single_use_window_start_utc": activation_value[
                    "single_use_window_start_utc"
                ],
                "observed_account_id": "630956766927",
                "observed_assumed_role_session_arn": (
                    "arn:aws:sts::630956766927:assumed-role/"
                    "onchain-wallet-intelligence-hl-archive-identity-r11a/"
                    "HLArchiveR11AIdentityBoundary"
                ),
                "observed_session_name": "HLArchiveR11AIdentityBoundary",
                "expected_role_arn": common.ROLE_ARN,
                "pricing_projection_eur_micros": 383757,
                "raw_aws_credentials_retained": False,
                "raw_oidc_token_retained": False,
                "raw_sts_response_retained": False,
            }
        )
        return value

    def test_live_alignment_and_approval_pass_then_each_future_gate_is_absent(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)

        record = g2.validate(repository)
        self.assertTrue(record["owner_approval_present"])
        self.assertTrue(record["canonical_approval_record_present"])
        self.assertFalse(record["execution_authorized_by_this_approval"])
        self.assertTrue(
            all(value is False for value in record["current_authority"].values())
        )
        self.assertEqual(
            record["science_state"]["empirical_root_cause"],
            "UNKNOWN_PENDING_DIAGNOSTIC",
        )
        self.assertTrue(
            all(
                value is False
                for key, value in record["science_state"].items()
                if key != "empirical_root_cause"
            )
        )
        self.assertTrue(
            all(value is False for value in record["trading_authorizations"].values())
        )
        aligned = alignment.validate_alignment(repository)
        self.assertEqual(aligned["alignment_id"], context.ALIGNMENT_ID)
        approval_r4.validate(repository)

        for relative in (
            common.ROLE_ATTESTATION_RELATIVE,
            common.PREFLIGHT_CANDIDATE_RELATIVE,
            common.PREFLIGHT_RELEASE_RELATIVE,
            common.PREFLIGHT_EVIDENCE_RELATIVE,
            common.PREFLIGHT_CONSUMPTION_RELATIVE,
            common.INSTALLATION_RELATIVE,
            common.WORKFLOW_RELATIVE,
            common.RELEASE_CANDIDATE_RELATIVE,
            common.RELEASE_RELATIVE,
            common.ACTIVATION_RELATIVE,
            common.BINDING_RELATIVE,
        ):
            with self.subTest(absent=relative):
                self.assertFalse((repository / relative).exists())

        with self.assertRaisesRegex(
            common.StageValidationError, "successor role attestation is absent"
        ):
            role.validate(repository)
        with self.assertRaisesRegex(
            common.StageValidationError, "successor role attestation is absent"
        ):
            preflight.validate(repository)
        with self.assertRaisesRegex(
            common.StageValidationError, "successor role attestation is absent"
        ):
            installation.validate(repository)
        with self.assertRaisesRegex(
            common.StageValidationError, "successor role attestation is absent"
        ):
            release.validate_candidate(repository)
        with self.assertRaisesRegex(
            common.StageValidationError, "successor role attestation is absent"
        ):
            release.validate(repository)
        with self.assertRaisesRegex(
            common.StageValidationError, "successor role attestation is absent"
        ):
            activation.validate(repository)
        with self.assertRaisesRegex(
            runtime_binding.RuntimeBindingError, "successor role attestation is absent"
        ):
            runtime_binding.validate(SYNTHETIC_COMMIT, 1, root=repository)

    def test_cache_free_validation_is_import_order_invariant(self) -> None:
        modules = (
            "tests.test_archive_inventory_r11a_g2_owner_approval",
            "tests.test_archive_inventory_r11a_g1_owner_approval_readiness",
            "tests.test_archive_inventory_r11a_implementation",
            "tests.test_archive_inventory_r11a_corrective_r7",
            "tests.test_archive_inventory_r11a_corrective_r7_precedence",
            "tests.test_archive_inventory_r11a_post_approval_validator_alignment",
        )
        import_and_validate = (
            "import importlib, sys\n"
            "from pathlib import Path\n"
            "for module in sys.argv[1:]:\n"
            "    importlib.import_module(module)\n"
            "from governance import validate_r11a_g2_owner_approval as g2\n"
            "from governance import "
            "validate_r11a_post_approval_validator_alignment as alignment\n"
            "root = Path.cwd()\n"
            "record = g2.validate(root)\n"
            "if record['owner_approval_present'] is not True:\n"
            "    raise SystemExit('owner approval missing after imports')\n"
            "if record['canonical_approval_record_present'] is not True:\n"
            "    raise SystemExit('canonical approval missing after imports')\n"
            "if record['execution_authorized_by_this_approval'] is not False:\n"
            "    raise SystemExit('approval opened execution after imports')\n"
            "alignment.validate_alignment(root)\n"
        )
        environment = os.environ.copy()
        environment.pop("PYTHONPYCACHEPREFIX", None)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"

        orders = tuple(
            (f"first:{modules[index]}", modules[index:] + modules[:index])
            for index in range(len(modules))
        )
        for label, order in orders:
            with self.subTest(order=label):
                temporary, repository = self.copy_repository()
                self.addCleanup(temporary.cleanup)
                completed = subprocess.run(
                    [sys.executable, "-B", "-c", import_and_validate, *order],
                    cwd=repository,
                    env=environment,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(
                    completed.returncode,
                    0,
                    completed.stdout + completed.stderr,
                )
                residue = sorted(
                    path.relative_to(repository).as_posix()
                    for path in repository.rglob("*")
                    if path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"}
                )
                self.assertEqual(residue, [])

    def test_isolation_source_provenance_and_metadata_fail_closed(self) -> None:
        index_temporary = tempfile.TemporaryDirectory()
        self.addCleanup(index_temporary.cleanup)
        index_root = Path(index_temporary.name)
        (index_root / ".git").mkdir()

        def write_index(relative: str, mode: int = 0o100644) -> None:
            encoded = relative.encode("utf-8")
            fixed = struct.pack(
                ">10I20sH",
                0,
                0,
                0,
                0,
                0,
                0,
                mode,
                0,
                0,
                0,
                b"\0" * 20,
                len(encoded),
            )
            entry = fixed + encoded + b"\0"
            entry += b"\0" * ((8 - (len(entry) % 8)) % 8)
            body = b"DIRC" + struct.pack(">II", 2, 1) + entry
            (index_root / ".git/index").write_bytes(
                body + hashlib.sha1(body).digest()
            )

        for relative in (
            "research/archive_inventory/r11a_corrective/__pycache__/tracked.pyc",
            "research/archive_inventory/r11a_corrective/tracked.pyc",
            "research/archive_inventory/r11a_corrective/tracked.pyo",
        ):
            with self.subTest(tracked=relative):
                write_index(relative)
                parsed = tracked_repository_paths(index_root)
                self.assertEqual(parsed, frozenset({relative}))
                with self.assertRaisesRegex(
                    RepositoryIsolationError, "tracked Python bytecode/cache residue"
                ):
                    require_no_tracked_bytecode(parsed)

        for mode in (0o120000, 0o160000):
            with self.subTest(tracked_mode=oct(mode)):
                write_index("tracked-non-regular", mode)
                with self.assertRaisesRegex(
                    RepositoryIsolationError, "symlink, submodule, or unsupported mode"
                ):
                    tracked_repository_paths(index_root)

        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        synthetic_cache = (
            repository
            / "research/archive_inventory/r11a_corrective/__pycache__"
        )
        synthetic_cache.mkdir()
        unknown_cache_entry = synthetic_cache / "UNKNOWN_AUTHORITY.json"
        unknown_cache_entry.write_text(
            '{"owner_approval_present":true}\n', encoding="utf-8"
        )
        try:
            with self.assertRaisesRegex(
                RepositoryIsolationError, "non-bytecode entry"
            ):
                require_safe_source_metadata(repository)
        finally:
            shutil.rmtree(synthetic_cache)

        for suffix in (".pyc", ".pyo"):
            standalone = repository / f"synthetic{suffix}"
            standalone.write_bytes(b"synthetic-bytecode")
            try:
                with self.assertRaisesRegex(
                    RepositoryIsolationError, "standalone bytecode"
                ):
                    require_safe_source_metadata(repository)
            finally:
                standalone.unlink()

        approval_path = repository / g2.APPROVAL_JSON
        external_alias = Path(temporary.name) / "approval-hard-link.json"
        os.link(approval_path, external_alias)
        try:
            with self.assertRaisesRegex(RepositoryIsolationError, "hard-link"):
                require_safe_source_metadata(repository)
        finally:
            external_alias.unlink()

        symlink = repository / "synthetic-cache-link"
        symlink.symlink_to(repository / "README.md")
        try:
            with self.assertRaisesRegex(RepositoryIsolationError, "symlink"):
                require_safe_source_metadata(repository)
        finally:
            symlink.unlink()

        special = repository / "synthetic-special"
        os.mkfifo(special)
        try:
            with self.assertRaisesRegex(RepositoryIsolationError, "special file"):
                require_safe_source_metadata(repository)
        finally:
            special.unlink()

    def test_offline_successor_ladder_requires_every_predecessor_in_order(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)

        with self.assertRaisesRegex(
            common.StageValidationError, "successor role attestation is absent"
        ):
            role.validate(repository)
        self.add_role(repository)
        role.validate(repository)

        with self.assertRaisesRegex(
            common.StageValidationError, "STS preflight candidate is absent"
        ):
            preflight.validate_candidate(repository)
        self.add_preflight_candidate(repository)
        preflight.validate_candidate(repository)

        with self.assertRaisesRegex(
            common.StageValidationError, "STS preflight release is absent"
        ):
            preflight.validate_release(repository)
        self.add_preflight_release(repository)
        preflight.validate_release(repository)

        with self.assertRaisesRegex(
            common.StageValidationError, "STS preflight evidence is absent"
        ):
            preflight.validate(repository)
        self.add_preflight(repository)
        preflight.validate(repository)

        with self.assertRaisesRegex(
            common.StageValidationError, "workflow installation contract is absent"
        ):
            installation.validate(repository)
        self.add_installation(repository)
        installation.validate(repository)

        with self.assertRaisesRegex(
            common.StageValidationError, "execution release candidate is absent"
        ):
            release.validate_candidate(repository)
        self.add_release_candidate(repository)
        release.validate_candidate(repository)

        with self.assertRaisesRegex(
            common.StageValidationError, "execution release is absent"
        ):
            release.validate(repository)
        self.add_release(repository)
        release.validate(repository)

        with self.assertRaisesRegex(
            common.StageValidationError, "canonical activation is absent"
        ):
            activation.validate(repository)
        self.add_activation(repository)
        activation.validate(repository)

        with self.assertRaisesRegex(
            runtime_binding.RuntimeBindingError, "R7 runtime binding is absent"
        ):
            runtime_binding.validate(SYNTHETIC_COMMIT, 1, root=repository)

    def test_complete_offline_synthetic_ladder_reaches_runtime_binding(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        self.add_complete_offline_ladder(repository)
        observed = runtime_binding.validate(SYNTHETIC_COMMIT, 1, root=repository)
        self.assertEqual(observed["canonical_commit"], SYNTHETIC_COMMIT)
        self.assertEqual(observed["runtime_authority"]["requester_pays_exact_72_getobject"], True)
        self.assertFalse(observed["r11_closed"])
        self.assertFalse(observed["r12_ready"])

    def test_execution_artifact_routes_every_post_static_context_through_runtime(
        self,
    ) -> None:
        artifact_temporary = tempfile.TemporaryDirectory()
        self.addCleanup(artifact_temporary.cleanup)
        artifact = Path(artifact_temporary.name) / "artifact"
        artifact.mkdir()
        context_path = artifact / execution_artifact.CONTEXT_FILE

        context_path.write_bytes(canonical_json(self.artifact_context("PRE_OIDC_STATIC_GATE")))
        with (
            mock.patch.object(execution_artifact, "validate_artifact") as ordinary,
            mock.patch.object(execution_artifact, "validate_science") as science,
            mock.patch.object(
                execution_artifact,
                "validate_runtime_binding",
                side_effect=AssertionError("runtime binding must not run"),
            ) as runtime,
        ):
            execution_artifact.validate_aligned_execution_artifact(artifact, root=ROOT)
            ordinary.assert_called_once()
            science.assert_called_once_with(artifact)
            runtime.assert_not_called()

        for phase in (
            "OIDC_ROLE_ASSUMPTION",
            "STS_PRINCIPAL_VALIDATION",
            "POST_STS_PRECOLLECTOR",
        ):
            with self.subTest(minimal_runtime_required_phase=phase):
                context_path.write_bytes(canonical_json(self.artifact_context(phase)))
                with (
                    mock.patch.object(execution_artifact, "validate_artifact"),
                    mock.patch.object(execution_artifact, "validate_science") as science,
                    mock.patch.object(
                        execution_artifact,
                        "validate_runtime_binding",
                        side_effect=runtime_binding.RuntimeBindingError(
                            "aligned runtime gate invoked"
                        ),
                    ) as runtime,
                ):
                    with self.assertRaisesRegex(
                        runtime_binding.RuntimeBindingError,
                        "aligned runtime gate invoked",
                    ):
                        execution_artifact.validate_aligned_execution_artifact(
                            artifact, root=ROOT
                        )
                    runtime.assert_called_once_with(SYNTHETIC_COMMIT, 1, root=ROOT)
                    science.assert_not_called()

    def test_bound_execution_artifact_requires_and_matches_complete_runtime_chain(
        self,
    ) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        self.add_complete_offline_ladder(repository)
        artifact = Path(temporary.name) / "artifact"
        artifact.mkdir()
        context_path = artifact / execution_artifact.CONTEXT_FILE
        exact_context = self.artifact_context(
            "ARTIFACT_PACKAGING", bound_root=repository
        )
        context_path.write_bytes(canonical_json(exact_context))

        with (
            mock.patch.object(execution_artifact, "validate_artifact"),
            mock.patch.object(execution_artifact, "validate_science") as science,
        ):
            with self.assertRaisesRegex(
                VALIDATION_ERRORS, "successor role attestation is absent"
            ):
                execution_artifact.validate_aligned_execution_artifact(
                    artifact, root=ROOT
                )
            science.assert_not_called()

        with (
            mock.patch.object(execution_artifact, "validate_artifact") as ordinary,
            mock.patch.object(execution_artifact, "validate_science") as science,
        ):
            execution_artifact.validate_aligned_execution_artifact(
                artifact, root=repository
            )
            ordinary.assert_called_once()
            science.assert_called_once_with(artifact)

        for key, replacement in (
            ("selection_sha256", ZERO_SHA),
            ("pricing_projection_eur_micros", 0),
        ):
            with self.subTest(bound_context_field=key):
                mutated = copy.deepcopy(exact_context)
                mutated[key] = replacement
                context_path.write_bytes(canonical_json(mutated))
                with (
                    mock.patch.object(execution_artifact, "validate_artifact"),
                    mock.patch.object(execution_artifact, "validate_science") as science,
                ):
                    with self.assertRaisesRegex(
                        execution_artifact.EvidenceValidationError,
                        f"artifact bound context drift: {key}",
                    ):
                        execution_artifact.validate_aligned_execution_artifact(
                            artifact, root=repository
                        )
                    science.assert_not_called()

    def test_successor_skip_and_rebound_predecessor_tamper_fail_closed(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        self.add_complete_offline_ladder(repository)

        role_path = repository / common.ROLE_ATTESTATION_RELATIVE
        role_raw = role_path.read_bytes()
        role_path.unlink()
        with self.assertRaisesRegex(
            common.StageValidationError, "successor role attestation is absent"
        ):
            installation.validate(
                repository,
                permitted_successor_paths=common.KNOWN_SUCCESSOR_PATHS,
            )
        role_path.write_bytes(role_raw)

        tampered = json.loads(role_raw)
        tampered["role_arn"] += "-tampered"
        role_path.write_bytes(canonical_json(tampered))
        binding_path = repository / common.BINDING_RELATIVE
        binding_value = json.loads(binding_path.read_bytes())
        binding_value["bound_files"][common.ROLE_ATTESTATION_RELATIVE] = common.sha256(
            repository, common.ROLE_ATTESTATION_RELATIVE
        )
        binding_path.write_bytes(canonical_json(binding_value))
        with self.assertRaisesRegex(
            runtime_binding.RuntimeBindingError, "successor role ARN drift"
        ):
            runtime_binding.validate(SYNTHETIC_COMMIT, 1, root=repository)

    def test_each_immediate_predecessor_is_required_even_when_successor_exists(
        self,
    ) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        self.add_complete_offline_ladder(repository)
        probes = (
            (
                common.ROLE_ATTESTATION_RELATIVE,
                self.validate_preflight_candidate_in_complete_fixture,
                "successor role attestation is absent",
            ),
            (
                common.PREFLIGHT_CANDIDATE_RELATIVE,
                self.validate_preflight_release_in_complete_fixture,
                "STS preflight candidate is absent",
            ),
            (
                common.PREFLIGHT_RELEASE_RELATIVE,
                self.validate_preflight_in_complete_fixture,
                "STS preflight release is absent",
            ),
            (
                common.PREFLIGHT_EVIDENCE_RELATIVE,
                self.validate_preflight_in_complete_fixture,
                "STS preflight evidence is absent",
            ),
            (
                common.PREFLIGHT_CONSUMPTION_RELATIVE,
                self.validate_installation_in_complete_fixture,
                "STS preflight release consumption is absent",
            ),
            (
                common.INSTALLATION_RELATIVE,
                self.validate_candidate_in_complete_fixture,
                "workflow installation contract is absent",
            ),
            (
                common.RELEASE_CANDIDATE_RELATIVE,
                self.validate_release_in_complete_fixture,
                "execution release candidate is absent",
            ),
            (
                common.RELEASE_RELATIVE,
                self.validate_activation_in_complete_fixture,
                "execution release is absent",
            ),
            (
                common.ACTIVATION_RELATIVE,
                self.validate_runtime_in_complete_fixture,
                "canonical activation is absent",
            ),
        )
        for relative, validator, label in probes:
            with self.subTest(missing=relative):
                path = repository / relative
                original = path.read_bytes()
                path.unlink()
                with self.assertRaisesRegex(AssertionError, label):
                    validator(repository)
                path.write_bytes(original)

    def test_dispatch_release_consumption_and_rerun_gates_fail_closed(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        self.add_complete_offline_ladder(repository)

        release_path = repository / common.RELEASE_RELATIVE
        release_raw = release_path.read_bytes()
        release_value = json.loads(release_raw)
        release_probes = (
            (
                "single_workflow_dispatch_authorized_by_release",
                True,
                "release self-authorizes workflow dispatch",
            ),
            (
                "single_workflow_dispatch_eligible_after_activation",
                False,
                "activation-contingent single-dispatch eligibility",
            ),
            ("rerun_authorized", True, "release authorizes rerun"),
            ("release_consumed", True, "release snapshot marked consumed"),
        )
        for key, replacement, label in release_probes:
            with self.subTest(release_field=key):
                mutated = copy.deepcopy(release_value)
                mutated[key] = replacement
                mutated_raw = canonical_json(mutated)
                release_path.write_bytes(mutated_raw)
                (repository / common.RELEASE_DIGEST_RELATIVE).write_text(
                    hashlib.sha256(mutated_raw).hexdigest() + "\n", encoding="ascii"
                )
                with self.assertRaisesRegex(common.StageValidationError, label):
                    self.validate_release_in_complete_fixture(repository)
        release_path.write_bytes(release_raw)
        (repository / common.RELEASE_DIGEST_RELATIVE).write_text(
            hashlib.sha256(release_raw).hexdigest() + "\n", encoding="ascii"
        )

        activation_path = repository / common.ACTIVATION_RELATIVE
        activation_raw = activation_path.read_bytes()
        activation_value = json.loads(activation_raw)
        activation_probes = (
            (
                "single_workflow_dispatch_authorized",
                False,
                "does not authorize exactly one dispatch",
            ),
            ("explicit_owner_dispatch_required", False, "owner dispatch gate"),
            ("rerun_authorized", True, "activation opens rerun"),
            ("release_consumed", True, "activation marked release consumed"),
        )
        for key, replacement, label in activation_probes:
            with self.subTest(activation_field=key):
                mutated = copy.deepcopy(activation_value)
                mutated[key] = replacement
                activation_path.write_bytes(canonical_json(mutated))
                with self.assertRaisesRegex(common.StageValidationError, label):
                    self.validate_activation_in_complete_fixture(repository)
        activation_path.write_bytes(activation_raw)

        self.write_json(repository, common.RELEASE_CONSUMPTION_RELATIVE, {})
        with self.assertRaisesRegex(
            (runtime_binding.RuntimeBindingError, context.PostApprovalContextError),
            "unrecognized R11A approval/authority data file|"
            "future authority artifact unexpectedly present|execution release consumption",
        ):
            runtime_binding.validate(SYNTHETIC_COMMIT, 1, root=repository)
        (repository / common.RELEASE_CONSUMPTION_RELATIVE).unlink()
        with self.assertRaisesRegex(
            runtime_binding.RuntimeBindingError, "workflow run attempt one"
        ):
            runtime_binding.validate(SYNTHETIC_COMMIT, 2, root=repository)

    def test_immutable_approval_alignment_and_bound_bytes_mutations_fail(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        probes = [
            (common.APPROVAL_JSON_RELATIVE, "approval receipt"),
            (common.APPROVAL_TEXT_RELATIVE, "approval statement"),
        ]
        probes.extend(
            (
                relative,
                "approval statement"
                if relative == common.G1_SOURCE_STATEMENT_RELATIVE
                else "bound file",
            )
            for relative in g2.EXPECTED_BOUND_FILES
        )
        for relative, label in probes:
            with self.subTest(path=relative):
                path = repository / relative
                original = path.read_bytes()
                path.write_bytes(original + b" ")
                with self.assertRaisesRegex(context.PostApprovalContextError, label):
                    approval_r4.validate(repository)
                path.write_bytes(original)

        alignment_path = repository / context.ALIGNMENT_PATH
        original = alignment_path.read_bytes()
        value = json.loads(original)
        value["g2_review"]["review_verdict"] = "RED"
        alignment_path.write_bytes(canonical_json(value))
        with self.assertRaisesRegex(
            context.PostApprovalContextError, "post-approval alignment"
        ):
            context.validate_alignment(repository)

    def test_installed_workflow_byte_trigger_and_secret_tampering_fail(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        self.add_role(repository)
        self.add_preflight_candidate(repository)
        self.add_preflight_release(repository)
        self.add_preflight(repository)
        self.add_installation(repository)
        path = repository / common.WORKFLOW_RELATIVE
        original = path.read_bytes()
        probes = (
            (b"\n# byte drift\n", "differs from approved R7 candidate"),
            (b"\nworkflow_call:\n", "differs from approved R7 candidate"),
            (b"\n${{ secrets.UNAUTHORIZED }}\n", "differs from approved R7 candidate"),
        )
        for suffix, label in probes:
            with self.subTest(payload=suffix):
                path.write_bytes(original + suffix)
                with self.assertRaisesRegex(common.StageValidationError, label):
                    installation.validate(repository)
                path.write_bytes(original)

    def test_every_stage_rejects_unknown_keys_wrong_types_and_strict_json_drift(
        self,
    ) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        self.add_complete_offline_ladder(repository)
        stages = (
            (common.ROLE_ATTESTATION_RELATIVE, self.validate_role_in_complete_fixture, "role_max_session_duration_seconds", True, "integer"),
            (common.PREFLIGHT_CANDIDATE_RELATIVE, self.validate_preflight_candidate_in_complete_fixture, "workflow_run_attempt_required", True, "integer"),
            (common.PREFLIGHT_RELEASE_RELATIVE, self.validate_preflight_release_in_complete_fixture, "maximum_sts_get_caller_identity_calls", True, "integer"),
            (common.PREFLIGHT_EVIDENCE_RELATIVE, self.validate_preflight_in_complete_fixture, "workflow_run_attempt", True, "integer"),
            (common.PREFLIGHT_CONSUMPTION_RELATIVE, self.validate_preflight_in_complete_fixture, "s3_requests_executed", False, "integer"),
            (common.INSTALLATION_RELATIVE, self.validate_installation_in_complete_fixture, "network_requests_executed_by_installation", False, "integer"),
            (common.RELEASE_CANDIDATE_RELATIVE, self.validate_candidate_in_complete_fixture, "maximum_runs", True, "integer"),
            (common.RELEASE_RELATIVE, self.validate_release_in_complete_fixture, "maximum_runs", True, "integer"),
            (common.ACTIVATION_RELATIVE, self.validate_activation_in_complete_fixture, "maximum_runs", True, "integer"),
            (common.BINDING_RELATIVE, self.validate_runtime_in_complete_fixture, "r11_closed", 0, "closes R11"),
        )
        release_digest_path = repository / common.RELEASE_DIGEST_RELATIVE
        for relative, validator, typed_key, wrong_type, type_label in stages:
            path = repository / relative
            original = path.read_bytes()
            observed = json.loads(original)
            with self.subTest(path=relative, mutation="unknown key"):
                unknown = copy.deepcopy(observed)
                unknown["unknown_authority"] = False
                path.write_bytes(canonical_json(unknown))
                with self.assertRaisesRegex(AssertionError, "key set drift"):
                    validator(repository)
            with self.subTest(path=relative, mutation="wrong type"):
                wrong = copy.deepcopy(observed)
                wrong[typed_key] = wrong_type
                wrong_raw = canonical_json(wrong)
                path.write_bytes(wrong_raw)
                if relative == common.RELEASE_RELATIVE:
                    release_digest_path.write_text(
                        hashlib.sha256(wrong_raw).hexdigest() + "\n",
                        encoding="ascii",
                    )
                with self.assertRaisesRegex(AssertionError, type_label):
                    validator(repository)
            path.write_bytes(original)
            if relative == common.RELEASE_RELATIVE:
                release_digest_path.write_text(
                    hashlib.sha256(original).hexdigest() + "\n", encoding="ascii"
                )

        role_path = repository / common.ROLE_ATTESTATION_RELATIVE
        role_raw = role_path.read_bytes()
        role_path.write_bytes(role_raw[:-2] + b',"schema_version":"1.0"}\n')
        with self.assertRaisesRegex(common.StageValidationError, "duplicate JSON key"):
            common.load(repository, common.ROLE_ATTESTATION_RELATIVE)
        with self.assertRaisesRegex(
            context.PostApprovalContextError,
            "invalid approval/authority JSON alias candidate",
        ):
            self.validate_role_in_complete_fixture(repository)

        role_path.write_bytes(
            role_raw.replace(
                b'"schema_version":"1.0"', b'"schema_version":NaN'
            )
        )
        with self.assertRaisesRegex(common.StageValidationError, "non-finite JSON"):
            common.load(repository, common.ROLE_ATTESTATION_RELATIVE)
        with self.assertRaisesRegex(
            context.PostApprovalContextError,
            "invalid approval/authority JSON alias candidate",
        ):
            self.validate_role_in_complete_fixture(repository)

    def test_each_successor_review_gate_is_green_present_and_not_reused(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        self.add_complete_offline_ladder(repository)
        stages = (
            (common.PREFLIGHT_CANDIDATE_RELATIVE, self.validate_preflight_candidate_in_complete_fixture, "role_attestation_review", "role attestation review", 2, "e" * 40, "f" * 40),
            (common.PREFLIGHT_RELEASE_RELATIVE, self.validate_preflight_release_in_complete_fixture, "candidate_review", "preflight candidate review", 3, "3" * 40, "3" * 40),
            (common.INSTALLATION_RELATIVE, self.validate_installation_in_complete_fixture, "sts_preflight_review", "STS preflight review", 4, "4" * 40, "4" * 40),
            (common.RELEASE_CANDIDATE_RELATIVE, self.validate_candidate_in_complete_fixture, "workflow_installation_review", "workflow installation review", 5, "5" * 40, "5" * 40),
            (common.RELEASE_RELATIVE, self.validate_release_in_complete_fixture, "release_candidate_review", "execution release candidate review", 6, "6" * 40, "6" * 40),
            (common.ACTIVATION_RELATIVE, self.validate_activation_in_complete_fixture, "execution_release_review", "execution release review", 7, "7" * 40, "7" * 40),
            (common.BINDING_RELATIVE, self.validate_runtime_in_complete_fixture, "activation_review", "single-use activation review", 8, "8" * 40, "8" * 40),
        )
        digest_path = repository / common.RELEASE_DIGEST_RELATIVE
        for (
            relative,
            validator,
            prefix,
            label,
            predecessor_review_id,
            predecessor_head,
            predecessor_tree,
        ) in stages:
            path = repository / relative
            original = path.read_bytes()
            observed = json.loads(original)
            mutations = (
                (f"{prefix}_completed", False, "is not complete"),
                (f"{prefix}_verdict", "RED", "verdict is not GREEN"),
                (f"{prefix}_id", predecessor_review_id, "reuses|not separate"),
                (f"{prefix}ed_head", predecessor_head, "reuses predecessor reviewed head"),
                (f"{prefix}ed_tree", predecessor_tree, "reuses predecessor reviewed tree"),
            )
            for key, replacement, failure in mutations:
                with self.subTest(path=relative, review_mutation=key):
                    mutated = copy.deepcopy(observed)
                    mutated[key] = replacement
                    raw = canonical_json(mutated)
                    path.write_bytes(raw)
                    if relative == common.RELEASE_RELATIVE:
                        digest_path.write_text(
                            hashlib.sha256(raw).hexdigest() + "\n", encoding="ascii"
                        )
                    with self.assertRaisesRegex(
                        VALIDATION_ERRORS,
                        f"{label}.*(?:{failure})",
                    ):
                        validator(repository)
            with self.subTest(path=relative, review_mutation="missing review ID"):
                missing = copy.deepcopy(observed)
                missing.pop(f"{prefix}_id")
                raw = canonical_json(missing)
                path.write_bytes(raw)
                if relative == common.RELEASE_RELATIVE:
                    digest_path.write_text(
                        hashlib.sha256(raw).hexdigest() + "\n", encoding="ascii"
                    )
                with self.assertRaisesRegex(VALIDATION_ERRORS, "key set drift"):
                    validator(repository)
            path.write_bytes(original)
            if relative == common.RELEASE_RELATIVE:
                digest_path.write_text(
                    hashlib.sha256(original).hexdigest() + "\n", encoding="ascii"
                )

    def test_activation_and_runtime_reviews_reject_every_consumed_lineage_identity(
        self,
    ) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        self.add_complete_offline_ladder(repository)

        role_value = json.loads(
            (repository / common.ROLE_ATTESTATION_RELATIVE).read_bytes()
        )
        preflight_candidate_value = json.loads(
            (repository / common.PREFLIGHT_CANDIDATE_RELATIVE).read_bytes()
        )
        preflight_release_value = json.loads(
            (repository / common.PREFLIGHT_RELEASE_RELATIVE).read_bytes()
        )
        installation_value = json.loads(
            (repository / common.INSTALLATION_RELATIVE).read_bytes()
        )
        release_candidate_value = json.loads(
            (repository / common.RELEASE_CANDIDATE_RELATIVE).read_bytes()
        )
        release_value = json.loads(
            (repository / common.RELEASE_RELATIVE).read_bytes()
        )
        activation_value = json.loads(
            (repository / common.ACTIVATION_RELATIVE).read_bytes()
        )

        def review_identity(
            value: dict[str, object], prefix: str
        ) -> tuple[int, str, str]:
            review_id = value[f"{prefix}_id"]
            reviewed_head = value[f"{prefix}ed_head"]
            reviewed_tree = value[f"{prefix}ed_tree"]
            self.assertIs(type(review_id), int)
            self.assertIs(type(reviewed_head), str)
            self.assertIs(type(reviewed_tree), str)
            return review_id, reviewed_head, reviewed_tree

        baseline = [
            (
                "software GREEN",
                common.SOFTWARE_REVIEW_ID,
                common.SOFTWARE_REVIEWED_HEAD,
                common.SOFTWARE_REVIEWED_TREE,
            ),
            (
                "G1 GREEN",
                common.G1_REVIEW_ID,
                common.G1_REVIEWED_HEAD,
                common.G1_REVIEWED_TREE,
            ),
            (
                "G2 GREEN",
                common.G2_REVIEW_ID,
                common.ALIGNMENT_PREDECESSOR_HEAD,
                common.ALIGNMENT_PREDECESSOR_TREE,
            ),
        ]
        stage_lineage = [
            (
                "alignment review",
                *review_identity(role_value, "alignment_review"),
            ),
            (
                "identity creation/configuration review",
                *review_identity(
                    role_value, "identity_creation_and_configuration_review"
                ),
            ),
            (
                "role-attestation review",
                *review_identity(
                    preflight_candidate_value, "role_attestation_review"
                ),
            ),
            (
                "preflight-candidate review",
                *review_identity(preflight_release_value, "candidate_review"),
            ),
            (
                "STS-preflight review",
                *review_identity(installation_value, "sts_preflight_review"),
            ),
            (
                "workflow-installation review",
                *review_identity(
                    release_candidate_value, "workflow_installation_review"
                ),
            ),
            (
                "release-candidate review",
                *review_identity(release_value, "release_candidate_review"),
            ),
            (
                "execution-release review",
                *review_identity(activation_value, "execution_release_review"),
            ),
        ]
        targets = (
            (
                common.ACTIVATION_RELATIVE,
                "execution_release_review",
                "execution release review",
                self.validate_activation_in_complete_fixture,
                baseline + stage_lineage[:-1],
            ),
            (
                common.BINDING_RELATIVE,
                "activation_review",
                "single-use activation review",
                self.validate_runtime_in_complete_fixture,
                baseline + stage_lineage,
            ),
        )
        for relative, prefix, label, validator, consumed in targets:
            path = repository / relative
            original = path.read_bytes()
            observed = json.loads(original)
            for source, review_id, reviewed_head, reviewed_tree in consumed:
                for key, replacement in (
                    (f"{prefix}_id", review_id),
                    (f"{prefix}ed_head", reviewed_head),
                    (f"{prefix}ed_tree", reviewed_tree),
                ):
                    with self.subTest(
                        target=relative,
                        reused_source=source,
                        reused_component=key,
                    ):
                        mutated = copy.deepcopy(observed)
                        mutated[key] = replacement
                        path.write_bytes(canonical_json(mutated))
                        with self.assertRaisesRegex(
                            VALIDATION_ERRORS,
                            f"{label} reuses (?:consumed|predecessor)",
                        ):
                            validator(repository)
            path.write_bytes(original)

    def test_every_review_stage_rejects_seed_and_non_immediate_ancestor_reuse(
        self,
    ) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        self.add_complete_offline_ladder(repository)

        role_path = repository / common.ROLE_ATTESTATION_RELATIVE
        role_value = json.loads(role_path.read_bytes())
        seeds = (
            (
                "software GREEN",
                common.SOFTWARE_REVIEW_ID,
                common.SOFTWARE_REVIEWED_HEAD,
                common.SOFTWARE_REVIEWED_TREE,
            ),
            (
                "G1 GREEN",
                common.G1_REVIEW_ID,
                common.G1_REVIEWED_HEAD,
                common.G1_REVIEWED_TREE,
            ),
            (
                "G2 GREEN",
                common.G2_REVIEW_ID,
                common.ALIGNMENT_PREDECESSOR_HEAD,
                common.ALIGNMENT_PREDECESSOR_TREE,
            ),
        )
        original = role_path.read_bytes()
        for source, review_id, reviewed_head, reviewed_tree in seeds:
            for key, replacement in (
                ("alignment_review_id", review_id),
                ("alignment_reviewed_head", reviewed_head),
                ("alignment_reviewed_tree", reviewed_tree),
            ):
                with self.subTest(
                    target="alignment review",
                    reused_source=source,
                    reused_component=key,
                ):
                    mutated = copy.deepcopy(role_value)
                    mutated[key] = replacement
                    role_path.write_bytes(canonical_json(mutated))
                    with self.assertRaisesRegex(
                        common.StageValidationError,
                        "alignment review.*(?:reuses|does not review)",
                    ):
                        self.validate_role_in_complete_fixture(repository)
        role_path.write_bytes(original)

        alignment_identity = (
            role_value["alignment_review_id"],
            role_value["alignment_reviewed_head"],
            role_value["alignment_reviewed_tree"],
        )
        non_immediate_targets = (
            (
                common.ROLE_ATTESTATION_RELATIVE,
                "identity_creation_and_configuration_review",
                "identity creation/configuration review",
                self.validate_role_in_complete_fixture,
                seeds[2][1:],
            ),
            (
                common.PREFLIGHT_CANDIDATE_RELATIVE,
                "role_attestation_review",
                "role attestation review",
                self.validate_preflight_candidate_in_complete_fixture,
                alignment_identity,
            ),
            (
                common.PREFLIGHT_RELEASE_RELATIVE,
                "candidate_review",
                "STS preflight candidate review",
                self.validate_preflight_release_in_complete_fixture,
                alignment_identity,
            ),
            (
                common.INSTALLATION_RELATIVE,
                "sts_preflight_review",
                "STS preflight review",
                self.validate_installation_in_complete_fixture,
                alignment_identity,
            ),
            (
                common.RELEASE_CANDIDATE_RELATIVE,
                "workflow_installation_review",
                "workflow installation review",
                self.validate_candidate_in_complete_fixture,
                alignment_identity,
            ),
            (
                common.RELEASE_RELATIVE,
                "release_candidate_review",
                "execution release candidate review",
                self.validate_release_in_complete_fixture,
                alignment_identity,
            ),
            (
                common.ACTIVATION_RELATIVE,
                "execution_release_review",
                "execution release review",
                self.validate_activation_in_complete_fixture,
                alignment_identity,
            ),
            (
                common.BINDING_RELATIVE,
                "activation_review",
                "single-use activation review",
                self.validate_runtime_in_complete_fixture,
                alignment_identity,
            ),
        )
        release_digest_path = repository / common.RELEASE_DIGEST_RELATIVE
        for relative, prefix, label, validator, reused in non_immediate_targets:
            path = repository / relative
            original = path.read_bytes()
            observed = json.loads(original)
            review_id, reviewed_head, reviewed_tree = reused
            for key, replacement in (
                (f"{prefix}_id", review_id),
                (f"{prefix}ed_head", reviewed_head),
                (f"{prefix}ed_tree", reviewed_tree),
            ):
                with self.subTest(target=relative, reused_component=key):
                    mutated = copy.deepcopy(observed)
                    mutated[key] = replacement
                    raw = canonical_json(mutated)
                    path.write_bytes(raw)
                    if relative == common.RELEASE_RELATIVE:
                        release_digest_path.write_text(
                            hashlib.sha256(raw).hexdigest() + "\n",
                            encoding="ascii",
                        )
                    with self.assertRaisesRegex(
                        VALIDATION_ERRORS,
                        f"{label} reuses consumed",
                    ):
                        validator(repository)
            path.write_bytes(original)
            if relative == common.RELEASE_RELATIVE:
                release_digest_path.write_text(
                    hashlib.sha256(original).hexdigest() + "\n",
                    encoding="ascii",
                )

    def test_stage_paths_reject_symlinked_ancestors_root_hardlinks_and_special_files(
        self,
    ) -> None:
        for relative in (
            "research/archive_inventory/r11a_role_attestation",
            "research/archive_inventory/r11a_role_preflight",
            "research/archive_inventory/r11a_workflow_installation",
            "research/archive_inventory/r11a_runtime",
            ".github/workflows",
        ):
            with self.subTest(symlinked_ancestor=relative):
                temporary, repository = self.copy_repository()
                self.addCleanup(temporary.cleanup)
                self.add_complete_offline_ladder(repository)
                ancestor = repository / relative
                physical = Path(temporary.name) / (
                    "physical-" + relative.replace("/", "-").replace(".", "dot")
                )
                shutil.move(ancestor, physical)
                os.symlink(physical, ancestor)
                with self.assertRaisesRegex(VALIDATION_ERRORS, "symlink"):
                    runtime_binding.validate(SYNTHETIC_COMMIT, 1, root=repository)

        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        root_alias = Path(temporary.name) / "repository-symlink"
        os.symlink(repository, root_alias)
        with self.assertRaisesRegex(context.PostApprovalContextError, "symlink"):
            context.validate_alignment(root_alias)
        with self.assertRaisesRegex(
            context.PostApprovalContextError, "unsafe repository-relative path"
        ):
            context.validate_alignment(
                repository, permitted_successor_paths=frozenset({"../escape"})
            )

        self.add_complete_offline_ladder(repository)
        role_path = repository / common.ROLE_ATTESTATION_RELATIVE
        hardlink = Path(temporary.name) / "role-hardlink.json"
        os.link(role_path, hardlink)
        with self.assertRaisesRegex(VALIDATION_ERRORS, "hard-link"):
            self.validate_role_in_complete_fixture(repository)
        hardlink.unlink()
        role_raw = role_path.read_bytes()
        role_path.unlink()
        os.mkfifo(role_path)
        try:
            with self.assertRaisesRegex(
                VALIDATION_ERRORS,
                "regular|special|unsupported repository entry type",
            ):
                self.validate_role_in_complete_fixture(repository)
        finally:
            role_path.unlink()
            role_path.write_bytes(role_raw)

    def test_stage_cap_policy_identity_science_and_trading_mutations_fail(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        self.add_complete_offline_ladder(repository)

        probes: list[tuple[str, tuple[str, ...], object, object, str]] = [
            (common.ROLE_ATTESTATION_RELATIVE, ("role_arn",), "bad", self.validate_role_in_complete_fixture, "role ARN"),
            (common.ROLE_ATTESTATION_RELATIVE, ("account_id",), "000000000000", self.validate_role_in_complete_fixture, "account"),
            (common.ROLE_ATTESTATION_RELATIVE, ("role_max_session_duration_seconds",), 7200, self.validate_role_in_complete_fixture, "session duration"),
            (common.ROLE_ATTESTATION_RELATIVE, ("persistent_permission_resource_count",), 73, self.validate_role_in_complete_fixture, "resource count"),
            (common.ROLE_ATTESTATION_RELATIVE, ("g2_review_id",), 5030488859, self.validate_role_in_complete_fixture, "G2 review lineage"),
            (common.ROLE_ATTESTATION_RELATIVE, ("alignment_review_completed",), False, self.validate_role_in_complete_fixture, "alignment review is not complete"),
            (common.ROLE_ATTESTATION_RELATIVE, ("alignment_review_id",), common.G2_REVIEW_ID, self.validate_role_in_complete_fixture, "alignment review reuses G2 review"),
            (common.ROLE_ATTESTATION_RELATIVE, ("alignment_review_event",), "APPROVED", self.validate_role_in_complete_fixture, "alignment review event"),
            (common.ROLE_ATTESTATION_RELATIVE, ("alignment_review_verdict",), "RED", self.validate_role_in_complete_fixture, "alignment review verdict"),
            (common.ROLE_ATTESTATION_RELATIVE, ("alignment_reviewed_head",), context.PREDECESSOR_HEAD, self.validate_role_in_complete_fixture, "does not review an alignment successor|reuses consumed reviewed head"),
            (common.ROLE_ATTESTATION_RELATIVE, ("alignment_reviewed_tree",), context.PREDECESSOR_TREE, self.validate_role_in_complete_fixture, "reuses predecessor tree|reuses consumed reviewed tree"),
            (common.ROLE_ATTESTATION_RELATIVE, ("identity_creation_and_configuration_review_completed",), False, self.validate_role_in_complete_fixture, "identity creation/configuration review is not complete"),
            (common.ROLE_ATTESTATION_RELATIVE, ("identity_creation_and_configuration_review_id",), 0, self.validate_role_in_complete_fixture, "identity creation/configuration review ID"),
            (common.ROLE_ATTESTATION_RELATIVE, ("identity_creation_and_configuration_review_id",), 1, self.validate_role_in_complete_fixture, "not separate from alignment review"),
            (common.ROLE_ATTESTATION_RELATIVE, ("identity_creation_and_configuration_review_event",), "APPROVED", self.validate_role_in_complete_fixture, "identity creation/configuration review event"),
            (common.ROLE_ATTESTATION_RELATIVE, ("identity_creation_and_configuration_review_verdict",), "RED", self.validate_role_in_complete_fixture, "identity creation/configuration review verdict"),
            (common.ROLE_ATTESTATION_RELATIVE, ("identity_creation_and_configuration_reviewed_head",), "c" * 40, self.validate_role_in_complete_fixture, "reuses alignment-reviewed head"),
            (common.ROLE_ATTESTATION_RELATIVE, ("identity_creation_and_configuration_reviewed_tree",), "d" * 40, self.validate_role_in_complete_fixture, "reuses alignment-reviewed tree"),
            (common.ROLE_ATTESTATION_RELATIVE, ("permission_policy_sha256",), ZERO_SHA, self.validate_role_in_complete_fixture, "permission policy"),
            (common.ROLE_ATTESTATION_RELATIVE, ("trust_policy_sha256",), ZERO_SHA, self.validate_role_in_complete_fixture, "trust policy"),
            (common.ROLE_ATTESTATION_RELATIVE, ("additional_managed_policies_attached",), True, self.validate_role_in_complete_fixture, "managed policy"),
            (common.ROLE_ATTESTATION_RELATIVE, ("additional_inline_policies_attached",), True, self.validate_role_in_complete_fixture, "inline policy"),
            (common.ROLE_ATTESTATION_RELATIVE, ("reusable_credentials_present",), True, self.validate_role_in_complete_fixture, "reusable credentials"),
            (common.ROLE_ATTESTATION_RELATIVE, ("access_keys_present",), True, self.validate_role_in_complete_fixture, "access keys"),
            (common.ROLE_ATTESTATION_RELATIVE, ("secrets_present",), True, self.validate_role_in_complete_fixture, "secrets"),
            (common.PREFLIGHT_CANDIDATE_RELATIVE, ("account_id",), "000000000000", self.validate_preflight_candidate_in_complete_fixture, "account"),
            (common.PREFLIGHT_CANDIDATE_RELATIVE, ("role_arn",), "bad", self.validate_preflight_candidate_in_complete_fixture, "role ARN"),
            (common.PREFLIGHT_CANDIDATE_RELATIVE, ("permission_policy_sha256",), ZERO_SHA, self.validate_preflight_candidate_in_complete_fixture, "permission-policy"),
            (common.PREFLIGHT_CANDIDATE_RELATIVE, ("oidc_trust_policy_sha256",), ZERO_SHA, self.validate_preflight_candidate_in_complete_fixture, "trust-policy"),
            (common.PREFLIGHT_CANDIDATE_RELATIVE, ("authorized_aws_actions_after_release",), ["sts:GetCallerIdentity", "s3:GetObject"], self.validate_preflight_candidate_in_complete_fixture, "AWS action scope"),
            (common.PREFLIGHT_CANDIDATE_RELATIVE, ("sts_call_authorized_by_candidate",), True, self.validate_preflight_candidate_in_complete_fixture, "self-authorizes STS"),
            (common.PREFLIGHT_CANDIDATE_RELATIVE, ("single_use_sts_preflight_eligible_after_release",), False, self.validate_preflight_candidate_in_complete_fixture, "release gate"),
            (common.PREFLIGHT_CANDIDATE_RELATIVE, ("s3_requests_authorized",), True, self.validate_preflight_candidate_in_complete_fixture, "authorizes S3"),
            (common.PREFLIGHT_RELEASE_RELATIVE, ("candidate_review_completed",), False, self.validate_preflight_release_in_complete_fixture, "candidate review is not complete"),
            (common.PREFLIGHT_RELEASE_RELATIVE, ("candidate_review_id",), 0, self.validate_preflight_release_in_complete_fixture, "candidate review ID"),
            (common.PREFLIGHT_RELEASE_RELATIVE, ("candidate_review_event",), "APPROVED", self.validate_preflight_release_in_complete_fixture, "candidate review event"),
            (common.PREFLIGHT_RELEASE_RELATIVE, ("candidate_review_verdict",), "RED", self.validate_preflight_release_in_complete_fixture, "candidate review verdict"),
            (common.PREFLIGHT_RELEASE_RELATIVE, ("authorized_aws_actions",), ["sts:GetCallerIdentity", "s3:GetObject"], self.validate_preflight_release_in_complete_fixture, "AWS action scope"),
            (common.PREFLIGHT_RELEASE_RELATIVE, ("single_sts_get_caller_identity_authorized",), False, self.validate_preflight_release_in_complete_fixture, "exact STS-only probe"),
            (common.PREFLIGHT_RELEASE_RELATIVE, ("s3_requests_authorized",), True, self.validate_preflight_release_in_complete_fixture, "authorizes S3"),
            (common.PREFLIGHT_RELEASE_RELATIVE, ("release_consumed",), True, self.validate_preflight_release_in_complete_fixture, "already consumed"),
            (common.PREFLIGHT_RELEASE_RELATIVE, ("rerun_authorized",), True, self.validate_preflight_release_in_complete_fixture, "authorizes rerun"),
            (common.PREFLIGHT_EVIDENCE_RELATIVE, ("observed_account_id",), "000000000000", self.validate_preflight_in_complete_fixture, "account"),
            (common.PREFLIGHT_EVIDENCE_RELATIVE, ("expected_role_arn",), "bad", self.validate_preflight_in_complete_fixture, "role ARN"),
            (common.PREFLIGHT_EVIDENCE_RELATIVE, ("permission_policy_sha256",), ZERO_SHA, self.validate_preflight_in_complete_fixture, "permission-policy"),
            (common.PREFLIGHT_EVIDENCE_RELATIVE, ("oidc_trust_policy_sha256",), ZERO_SHA, self.validate_preflight_in_complete_fixture, "trust-policy"),
            (common.PREFLIGHT_EVIDENCE_RELATIVE, ("authorized_aws_actions",), ["sts:GetCallerIdentity", "s3:GetObject"], self.validate_preflight_in_complete_fixture, "AWS action authority"),
            (common.PREFLIGHT_EVIDENCE_RELATIVE, ("requester_pays_authorized",), True, self.validate_preflight_in_complete_fixture, "Requester Pays"),
            (common.PREFLIGHT_EVIDENCE_RELATIVE, ("object_body_access_authorized",), True, self.validate_preflight_in_complete_fixture, "object body"),
            (common.PREFLIGHT_EVIDENCE_RELATIVE, ("decompression_authorized",), True, self.validate_preflight_in_complete_fixture, "decompression"),
            (common.RELEASE_CANDIDATE_RELATIVE, ("single_workflow_dispatch_authorized",), True, self.validate_candidate_in_complete_fixture, "self-authorizes dispatch"),
            (common.RELEASE_CANDIDATE_RELATIVE, ("owner_dispatch_required",), False, self.validate_candidate_in_complete_fixture, "owner dispatch gate"),
            (common.RELEASE_CANDIDATE_RELATIVE, ("downstream_authorizations", "r11_closed"), True, self.validate_candidate_in_complete_fixture, "downstream authority"),
            (common.RELEASE_CANDIDATE_RELATIVE, ("trading_authorizations", "live"), True, self.validate_candidate_in_complete_fixture, "trading authority"),
        ]
        for key, expected in release.EXPECTED_CAPS.items():
            if type(expected) is bool:
                replacement: object = not expected
            elif type(expected) is int:
                replacement = expected + 1
            else:
                replacement = f"{expected}-drift"
            probes.append(
                (
                    common.RELEASE_CANDIDATE_RELATIVE,
                    (key,),
                    replacement,
                    self.validate_candidate_in_complete_fixture,
                    key,
                )
            )
        for relative, keys, replacement, validator, label in probes:
            with self.subTest(path=relative, field=".".join(keys)):
                path = repository / relative
                original = path.read_bytes()
                value = json.loads(original)
                target = value
                for key in keys[:-1]:
                    target = target[key]
                target[keys[-1]] = replacement
                path.write_bytes(canonical_json(value))
                with self.assertRaisesRegex(common.StageValidationError, label):
                    validator(repository)
                path.write_bytes(original)

    def test_runtime_authority_science_trading_and_bound_set_mutations_fail(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        self.add_complete_offline_ladder(repository)
        path = repository / common.BINDING_RELATIVE
        original = path.read_bytes()
        probes: list[tuple[tuple[str, ...], object, str]] = []
        probes.extend(
            (("runtime_authority", key), not expected, "runtime authority")
            for key, expected in runtime_binding._core.EXPECTED_RUNTIME_AUTHORITY.items()
        )
        probes.extend(
            (("runtime_authority", key), int(expected), "runtime authority")
            for key, expected in runtime_binding._core.EXPECTED_RUNTIME_AUTHORITY.items()
        )
        probes.extend(
            (
                ("science_state", key),
                not expected if type(expected) is bool else "PROVEN",
                "science state",
            )
            for key, expected in runtime_binding._core.EXPECTED_SCIENCE_STATE.items()
        )
        probes.extend(
            (
                ("science_state", key),
                int(expected) if type(expected) is bool else False,
                "science state",
            )
            for key, expected in runtime_binding._core.EXPECTED_SCIENCE_STATE.items()
        )
        probes.extend(
            (("downstream_authorizations", key), True, "downstream authority")
            for key in common.DOWNSTREAM_AUTHORITY_KEYS
        )
        probes.extend(
            (("trading_authorizations", key), True, "trading authority")
            for key in common.TRADING_AUTHORITY_KEYS
        )
        probes.extend(
            (
                (("r11_closed",), True, "closes R11"),
                (("r12_ready",), True, "opens R12"),
                (("r11_closed",), 0, "closes R11"),
                (("r12_ready",), 0, "opens R12"),
            )
        )
        for keys, replacement, label in probes:
            with self.subTest(field=".".join(keys)):
                value = json.loads(original)
                target = value
                for key in keys[:-1]:
                    target = target[key]
                target[keys[-1]] = replacement
                path.write_bytes(canonical_json(value))
                with self.assertRaisesRegex(runtime_binding.RuntimeBindingError, label):
                    runtime_binding.validate(SYNTHETIC_COMMIT, 1, root=repository)
                path.write_bytes(original)

        for relative in (
            "research/__init__.py",
            "research/archive_inventory/r11a_corrective/__init__.py",
        ):
            with self.subTest(bound_package_initializer=relative):
                initializer = repository / relative
                initializer_raw = initializer.read_bytes()
                initializer.write_bytes(initializer_raw + b"# initializer drift\n")
                with self.assertRaisesRegex(
                    runtime_binding.RuntimeBindingError,
                    f"bound runtime input hash drift: {relative}",
                ):
                    runtime_binding.validate(SYNTHETIC_COMMIT, 1, root=repository)
                initializer.write_bytes(initializer_raw)

        value = json.loads(original)
        value["bound_files"].pop(common.APPROVAL_JSON_RELATIVE)
        path.write_bytes(canonical_json(value))
        with self.assertRaisesRegex(
            runtime_binding.RuntimeBindingError, "transitive file set drift"
        ):
            runtime_binding.validate(SYNTHETIC_COMMIT, 1, root=repository)

    def test_alignment_record_is_exact_and_fails_closed_on_schema_and_lineage(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        path = repository / context.ALIGNMENT_PATH
        original = path.read_bytes()
        value = json.loads(original)
        mutations = (
            ("predecessor head", ("predecessor", "head"), "b" * 40),
            ("G2 review", ("g2_review", "review_id"), context.G2_REVIEW_ID + 1),
            ("wrong type", ("independent_exact_head_review_pending",), 1),
        )
        for label, keys, replacement in mutations:
            with self.subTest(label=label):
                mutated = copy.deepcopy(value)
                target = mutated
                for key in keys[:-1]:
                    target = target[key]
                target[keys[-1]] = replacement
                path.write_bytes(canonical_json(mutated))
                with self.assertRaises(context.PostApprovalContextError):
                    context.validate_alignment(repository)
                path.write_bytes(original)

        unknown = copy.deepcopy(value)
        unknown["unknown_authority"] = False
        path.write_bytes(canonical_json(unknown))
        with self.assertRaisesRegex(
            context.PostApprovalContextError, "post-approval alignment"
        ):
            context.validate_alignment(repository)
        path.write_bytes(original)

        # Strict JSON parsing rejects duplicate keys independently of semantics.
        path.write_bytes(original[:-2] + b',"schema_version":"1.0"}\n')
        with self.assertRaisesRegex(context.PostApprovalContextError, "duplicate JSON key"):
            context.validate_alignment(repository)

    def test_alignment_rejects_symlinked_security_ancestor(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        alignment_dir = repository / "research/archive_inventory/r11a_alignment"
        real = Path(temporary.name) / "real-alignment"
        shutil.copytree(alignment_dir, real)
        shutil.rmtree(alignment_dir)
        os.symlink(real, alignment_dir)
        with self.assertRaisesRegex(context.PostApprovalContextError, "symlink"):
            context.validate_alignment(repository)

    def test_live_historical_pricing_stays_pending_and_projection_is_exact_bytes(self) -> None:
        historical = ROOT / common.PRICING_TARGET_RELATIVE
        source = ROOT / common.PRICING_SOURCE_RELATIVE
        self.assertEqual(
            hashlib.sha256(source.read_bytes()).hexdigest(),
            common.APPROVED_PRICING_SOURCE_SHA,
        )
        self.assertEqual(
            hashlib.sha256(historical.read_bytes()).hexdigest(),
            context.RUNTIME_PRICING_TARGET_SHA,
        )
        self.assertNotEqual(historical.read_bytes(), source.read_bytes())
        self.assertEqual(
            json.loads(historical.read_bytes())["status"],
            "AWAITING_CURRENT_OFFICIAL_BINDING_BEFORE_OWNER_APPROVAL",
        )

        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        target = repository / common.PRICING_TARGET_RELATIVE
        approved = (repository / common.PRICING_SOURCE_RELATIVE).read_bytes()
        target.write_bytes(approved + b" ")
        with self.assertRaisesRegex(
            common.StageValidationError,
            "runtime pricing projection differs from approved candidate",
        ):
            common.pricing_projection(repository)
        target.write_bytes(approved)
        projected = common.pricing_projection(repository)
        self.assertEqual(projected["projected_eur_micros_at_frozen_maximum"], 383757)

    def test_active_consumers_have_no_legacy_authority_constants(self) -> None:
        active = tuple(context.ALIGNED_CONSUMERS) + (
            "governance/r11a_post_approval_context.py",
        )
        forbidden = {
            "R6 workflow": "hyperliquid-archive-r11a-identity-boundary-diagnostic-r6.yml",
            "R6 contract": "R11A_CORRECTIVE_IMPLEMENTATION_CONTRACT.json",
            "R6 workflow hash": "3b9ec32b6d6228a29057208cea56445b3f93e5e12bafe891fc4da665c093f0b5",
            "historical pending pricing hash": "5e5a6469b921a15cbac1e2f03184e2dfcf6ffee51dc2e86833e9556a5c23c226",
            "legacy receipt status": "APPROVED_IMPLEMENTATION_ROLE_AND_PREFLIGHT_NO_DATA_EXECUTION",
            "legacy receipt reviewed commit": '["reviewed_commit"]',
            "legacy receipt pricing self digest": '["pricing_snapshot_self_sha256"]',
            "obsolete role filename": "R11A_DEDICATED_ROLE_OPERATOR_ATTESTATION.json",
            "obsolete preflight filename": "R11A_STS_PREFLIGHT_EVIDENCE.json",
            "obsolete installation filename": "R11A_WORKFLOW_INSTALLATION.json",
            "obsolete G2 initial head": "50f04f4c984bad767d6af4297c440e4c9a9e0209",
            "obsolete G2 remediation head": "909d6fee02f55d3c57d7cedfc461c8f59d97743e",
            "superseded RED review": "5030488859",
            "old session duration": "7200",
            "old EUR ceiling": "EUR 0.30",
        }
        for relative in active:
            text = (ROOT / relative).read_text(encoding="utf-8")
            for label, token in forbidden.items():
                with self.subTest(path=relative, legacy=label):
                    if (
                        relative == "governance/r11a_post_approval_context.py"
                        and label == "historical pending pricing hash"
                    ):
                        self.assertIn("RUNTIME_PRICING_TARGET_SHA", text)
                        continue
                    self.assertNotIn(token, text)

        self.assertEqual(context.APPROVAL_RECEIPT_SHA, g2.APPROVAL_RECEIPT_SHA)
        self.assertEqual(context.APPROVAL_STATEMENT_SHA, g2.APPROVAL_STATEMENT_SHA)
        self.assertEqual(context.WORKFLOW_SHA, common.APPROVED_WORKFLOW_SHA)
        self.assertEqual(context.RUNTIME_PRICING_SOURCE_SHA, common.APPROVED_PRICING_SOURCE_SHA)
        self.assertEqual(context.PREDECESSOR_HEAD, "63526d6c39c9225e647a18693c70ec8e73535ff4")
        self.assertEqual(context.PREDECESSOR_TREE, "eedeb4d6166c554b996ede740931c4bacb306f5d")
        self.assertEqual(context.G2_REVIEW_ID, 5033303996)
        self.assertEqual(g2.SOFTWARE_HEAD, "443500de54917417276c39a635ae444458d03b0b")
        self.assertEqual(g2.SOFTWARE_TREE, "516d72a43545c454ef163e02ee1146005e6cfb5c")
        self.assertEqual(g2.SOFTWARE_REVIEW, 5019067044)
        self.assertEqual(g2.READINESS_HEAD, "4da7e67b600ef1ca10fb4f2e62b493d81d4dfcc3")
        self.assertEqual(g2.READINESS_TREE, "b4c7b1524e8856450028e53be7912a88d3a675e1")
        self.assertEqual(g2.READINESS_REVIEW, 5027672461)

    def test_aligned_production_graph_is_offline_and_optimization_invariant(self) -> None:
        forbidden_import_roots = {
            "aiohttp",
            "boto3",
            "botocore",
            "httpx",
            "requests",
            "socket",
            "subprocess",
            "urllib",
        }
        for relative in (
            "governance/r11a_post_approval_context.py",
            *context.ALIGNED_CONSUMERS,
        ):
            with self.subTest(path=relative):
                source = (ROOT / relative).read_text(encoding="utf-8")
                tree = ast.parse(source, filename=relative)
                self.assertFalse(
                    any(isinstance(node, ast.Assert) for node in ast.walk(tree)),
                    f"optimization-sensitive assert in {relative}",
                )
                self.assertFalse(
                    any(
                        isinstance(node, ast.Name) and node.id == "__debug__"
                        for node in ast.walk(tree)
                    ),
                    f"optimization-sensitive __debug__ in {relative}",
                )
                imports: set[str] = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imports.update(alias.name.split(".", 1)[0] for alias in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imports.add(node.module.split(".", 1)[0])
                self.assertFalse(
                    imports & forbidden_import_roots,
                    f"network/process capability imported by {relative}",
                )

    def test_execution_artifact_validator_direct_cli_imports_without_network(self) -> None:
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            [sys.executable, "-B", "governance/validate_r11a_execution_artifact_r7.py"],
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 2, completed.stderr)
        self.assertIn("usage:", completed.stderr)
        self.assertNotIn("ModuleNotFoundError", completed.stderr)


if __name__ == "__main__":
    unittest.main()
