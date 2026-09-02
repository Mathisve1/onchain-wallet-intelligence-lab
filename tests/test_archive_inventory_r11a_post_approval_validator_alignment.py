from __future__ import annotations

import ast
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import types
import unittest
from contextlib import ExitStack, nullcontext
from pathlib import Path
from unittest import mock

from governance import r11a_github_review_evidence as review_evidence
from governance import r11a_post_approval_context as context
from governance import r11a_stage_common_r4 as common
from governance import r11a_workflow_identity as workflow_identity
from governance import validate_r11a_activation_r4 as activation
from governance import validate_r11a_approval_r4 as approval_r4
from governance import validate_r11a_execution_artifact_r7 as execution_artifact
from governance import validate_r11a_execution_release_r4 as release
from governance import validate_r11a_g2_owner_approval as g2
from governance import validate_r11a_post_approval_validator_alignment as alignment
from governance import validate_r11a_role_attestation_r4 as role
from governance import validate_r11a_role_configuration_candidate_r4 as role_configuration
from governance import validate_r11a_role_preflight_evidence_r4 as preflight
from governance import validate_r11a_runtime_binding_r7 as runtime_binding
from governance import validate_r11a_workflow_installation_r4 as installation
from governance.r11a_repository_provenance import (
    AuthenticatedRepository,
    authenticated_repository_copy,
)


ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_COMMIT = "a" * 40
ZERO_SHA = "0" * 64
FIRST_MISSING = "successor role creation/configuration candidate is absent"


def canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def false_mapping(keys: frozenset[str]) -> dict[str, bool]:
    return {key: False for key in sorted(keys, key=lambda item: item.encode("utf-8"))}


class PostApprovalValidatorAlignmentTests(unittest.TestCase):
    """Combined-chain tests; primitive evidence/provenance attacks live separately.

    This module deliberately no longer manufactures editable six-field GitHub
    review self-claims. Synthetic stage records carry only an evidence digest;
    a gate double composes the independently tested evidence verifier with all
    production consumers and enforces the exact fixed-gate lineage while the
    complete on-disk stage ladder is exercised.
    """

    def copy_repository(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        return authenticated_repository_copy(ROOT)

    def write_json(self, root: Path, relative: str, value: object) -> bytes:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = canonical_json(value)
        path.write_bytes(raw)
        return raw

    def copy_static_input(self, root: Path, relative: str) -> None:
        source = ROOT / relative
        if not source.is_file():
            return
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())

    def prepare_synthetic_root(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name).resolve()
        required = {
            common.ALIGNMENT_RELATIVE,
            common.APPROVAL_JSON_RELATIVE,
            common.APPROVAL_TEXT_RELATIVE,
            common.TRUST_POLICY_RELATIVE,
            common.PERMISSION_POLICY_RELATIVE,
            common.CANDIDATE_RELATIVE,
            common.PRICING_SOURCE_RELATIVE,
            common.SELECTION_RELATIVE,
            common.IMPLEMENTATION_RELATIVE,
            common.RUNNER_RELATIVE,
            common.ARTIFACT_VALIDATOR_RELATIVE,
            *context.ALIGNED_CONSUMERS,
            *runtime_binding.REQUIRED_BOUND_PATHS,
        }
        for relative in sorted(required, key=lambda item: item.encode("utf-8")):
            self.copy_static_input(root, relative)
        self.add_synthetic_review_evidence(root)
        return temporary, root

    def add_synthetic_review_evidence(self, root: Path) -> None:
        for gate_id, relative in common.REVIEW_EVIDENCE_PATHS.items():
            self.write_json(root, relative, {"synthetic_gate_id": gate_id})

    def reconcile_project_state_from_physical_stages(
        self,
        root: Path,
    ) -> dict[str, bool]:
        """Project the exact canonical stage files into the machine-state block."""

        paths = {
            "r11a_successor_role_created": common.ROLE_ATTESTATION_RELATIVE,
            "r11a_successor_role_attestation_present": common.ROLE_ATTESTATION_RELATIVE,
            "r11a_sts_preflight": common.PREFLIGHT_EVIDENCE_RELATIVE,
            "r11a_workflow_installed": common.WORKFLOW_RELATIVE,
            "r11a_release_present": common.RELEASE_RELATIVE,
            "r11a_runtime_release": common.RELEASE_RELATIVE,
            "r11a_runtime_activation": common.ACTIVATION_RELATIVE,
            "r11a_runtime_binding": common.BINDING_RELATIVE,
            "r11a_runtime_binding_review": common.REVIEW_EVIDENCE_PATHS[
                "R11A_RUNTIME_BINDING_REVIEW"
            ],
        }
        projection: dict[str, bool] = {}
        for key, relative in paths.items():
            path = root / relative
            try:
                information = path.lstat()
            except FileNotFoundError:
                projection[key] = False
                continue
            self.assertTrue(stat.S_ISREG(information.st_mode), relative)
            self.assertEqual(information.st_nlink, 1, relative)
            projection[key] = True
        state_path = root / workflow_identity.PROJECT_STATE_RELATIVE
        lines = state_path.read_text(encoding="utf-8").splitlines()
        for key, present in projection.items():
            candidates = {f"{key} = false", f"{key} = true"}
            indexes = [index for index, line in enumerate(lines) if line in candidates]
            self.assertEqual(len(indexes), 1, key)
            lines[indexes[0]] = f"{key} = {'true' if present else 'false'}"
        state_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return projection

    @staticmethod
    def evidence_digest(root: Path, gate_id: str) -> str:
        return common.sha256(root, common.REVIEW_EVIDENCE_PATHS[gate_id])

    def configuration_record(self, root: Path) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "configuration_candidate_id": (
                "R11A-SUCCESSOR-IDENTITY-CREATION-AND-CONFIGURATION-001"
            ),
            "status": (
                "CANDIDATE_AWAITING_EXACT_HEAD_COMMENTED_GREEN_"
                "IDENTITY_CONFIGURATION_REVIEW_NO_AWS"
            ),
            "alignment_id": common.ALIGNMENT_ID,
            "alignment_record_sha256": common.sha256(root, common.ALIGNMENT_RELATIVE),
            "approval_receipt_sha256": common.APPROVAL_RECEIPT_SHA,
            "g2_review_id": common.G2_REVIEW_ID,
            "alignment_review_evidence_sha256": self.evidence_digest(
                root, "R11A_ALIGNMENT_REVIEW"
            ),
            "account_id": "630956766927",
            "role_arn": common.ROLE_ARN,
            "role_max_session_duration_seconds": 21600,
            "persistent_permission_resource_count": 72,
            "persistent_permission_resources_match_exact_selection": True,
            "trust_policy_sha256": common.APPROVED_TRUST_SHA,
            "permission_policy_sha256": common.APPROVED_PERMISSION_SHA,
            "additional_managed_policies_authorized": False,
            "additional_inline_policies_authorized": False,
            "additional_role_authorized": False,
            "reusable_credentials_authorized": False,
            "access_keys_authorized": False,
            "secrets_authorized": False,
            "existing_r11_role_mutation_authorized": False,
            "existing_r11_role_reuse_authorized": False,
            "role_creation_authorized_by_candidate": False,
            "role_creation_eligible_after_separate_review": True,
            "network_requests_executed_by_candidate": 0,
            "aws_iam_mutations_executed_by_candidate": 0,
            "downstream_authorizations": false_mapping(common.DOWNSTREAM_AUTHORITY_KEYS),
            "trading_authorizations": false_mapping(common.TRADING_AUTHORITY_KEYS),
        }

    def role_record(self, root: Path) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "attestation_id": "ATTEST_HL_ARCHIVE_R11A_SUCCESSOR_ROLE_001",
            "status": "ROLE_CREATED_POLICIES_APPLIED_AWAITING_STS_PREFLIGHT",
            "alignment_id": common.ALIGNMENT_ID,
            "alignment_record_sha256": common.sha256(root, common.ALIGNMENT_RELATIVE),
            "approval_receipt_sha256": common.APPROVAL_RECEIPT_SHA,
            "g2_review_id": common.G2_REVIEW_ID,
            "role_configuration_candidate_sha256": common.sha256(
                root, common.ROLE_CONFIGURATION_CANDIDATE_RELATIVE
            ),
            "identity_configuration_review_evidence_sha256": self.evidence_digest(
                root, "R11A_IDENTITY_CONFIGURATION_REVIEW"
            ),
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
            "status": "CANDIDATE_AWAITING_EXACT_HEAD_COMMENTED_GREEN_STS_ONLY_PREFLIGHT_RELEASE_REVIEW_NO_AWS",
            "role_attestation_review_evidence_sha256": self.evidence_digest(
                root, "R11A_ROLE_ATTESTATION_REVIEW"
            ),
            "role_attestation_sha256": common.sha256(root, common.ROLE_ATTESTATION_RELATIVE),
            "alignment_record_sha256": common.sha256(root, common.ALIGNMENT_RELATIVE),
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
        return {
            "schema_version": "1.0",
            "preflight_release_id": "RELEASE_HL_ARCHIVE_R11A_STS_ONLY_PREFLIGHT_001",
            "preflight_candidate_id": "CANDIDATE_HL_ARCHIVE_R11A_STS_ONLY_PREFLIGHT_001",
            "status": "RELEASED_FOR_EXACTLY_ONE_STS_GET_CALLER_IDENTITY_NO_S3",
            "preflight_candidate_sha256": common.sha256(
                root, common.PREFLIGHT_CANDIDATE_RELATIVE
            ),
            "sts_preflight_candidate_review_evidence_sha256": self.evidence_digest(
                root, "R11A_STS_PREFLIGHT_CANDIDATE_REVIEW"
            ),
            "role_attestation_sha256": common.sha256(root, common.ROLE_ATTESTATION_RELATIVE),
            "alignment_record_sha256": common.sha256(root, common.ALIGNMENT_RELATIVE),
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

    def preflight_records(self, root: Path) -> tuple[dict[str, object], dict[str, object]]:
        evidence = {
            "schema_version": "1.0",
            "preflight_id": "HL-ARCHIVE-R11A-SUCCESSOR-ROLE-STS-PREFLIGHT-001",
            "status": "R11A_STS_PREFLIGHT_PASS",
            "technical_result": "DEDICATED_R11A_ROLE_ASSUMEABLE_FROM_CANONICAL_MAIN",
            "preflight_release_id": "RELEASE_HL_ARCHIVE_R11A_STS_ONLY_PREFLIGHT_001",
            "preflight_release_sha256": common.sha256(root, common.PREFLIGHT_RELEASE_RELATIVE),
            "sts_preflight_release_review_evidence_sha256": self.evidence_digest(
                root, "R11A_STS_PREFLIGHT_RELEASE_REVIEW"
            ),
            "role_attestation_sha256": common.sha256(root, common.ROLE_ATTESTATION_RELATIVE),
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
        evidence_raw = self.write_json(root, common.PREFLIGHT_EVIDENCE_RELATIVE, evidence)
        consumption = {
            "schema_version": "1.0",
            "consumption_id": "CONSUME_HL_ARCHIVE_R11A_STS_PREFLIGHT_RELEASE_001",
            "status": "CONSUMED_SUCCESS",
            "preflight_id": evidence["preflight_id"],
            "preflight_release_id": evidence["preflight_release_id"],
            "preflight_release_sha256": evidence["preflight_release_sha256"],
            "preflight_evidence_sha256": hashlib.sha256(evidence_raw).hexdigest(),
            "preflight_release_consumed": True,
            "rerun_authorized": False,
            "s3_requests_executed": 0,
            "object_bytes_downloaded": 0,
            "downstream_authorizations": false_mapping(common.DOWNSTREAM_AUTHORITY_KEYS),
            "trading_authorizations": false_mapping(common.TRADING_AUTHORITY_KEYS),
        }
        self.write_json(root, common.PREFLIGHT_CONSUMPTION_RELATIVE, consumption)
        return evidence, consumption

    def installation_record(self, root: Path) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "installation_id": "HL-ARCHIVE-R11A-WORKFLOW-INSTALLATION-001",
            "status": "INSTALLED_AWAITING_SEPARATE_EXECUTION_RELEASE",
            "preflight_candidate_sha256": common.sha256(root, common.PREFLIGHT_CANDIDATE_RELATIVE),
            "preflight_release_sha256": common.sha256(root, common.PREFLIGHT_RELEASE_RELATIVE),
            "preflight_evidence_sha256": common.sha256(root, common.PREFLIGHT_EVIDENCE_RELATIVE),
            "preflight_consumption_sha256": common.sha256(root, common.PREFLIGHT_CONSUMPTION_RELATIVE),
            "sts_preflight_review_evidence_sha256": self.evidence_digest(
                root, "R11A_STS_PREFLIGHT_REVIEW"
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

    def release_candidate_record(self, root: Path) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "execution_release_candidate_id": (
                "CANDIDATE_RELEASE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001"
            ),
            "status": "CANDIDATE_AWAITING_EXACT_HEAD_COMMENTED_GREEN_EXECUTION_RELEASE_REVIEW_NO_EXECUTION",
            "diagnostic_id": common.DIAGNOSTIC_ID,
            "installation_contract_sha256": common.sha256(root, common.INSTALLATION_RELATIVE),
            "approval_receipt_sha256": common.APPROVAL_RECEIPT_SHA,
            "workflow_sha256": common.sha256(root, common.WORKFLOW_RELATIVE),
            "runtime_pricing_snapshot_sha256": common.sha256(root, common.PRICING_TARGET_RELATIVE),
            "selection_sha256": common.sha256(root, common.SELECTION_RELATIVE),
            "runner_sha256": common.sha256(root, common.RUNNER_RELATIVE),
            "validator_sha256": common.sha256(root, common.ARTIFACT_VALIDATOR_RELATIVE),
            "workflow_installation_review_evidence_sha256": self.evidence_digest(
                root, "R11A_WORKFLOW_INSTALLATION_REVIEW"
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

    def release_record(self, root: Path) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "execution_release_id": "RELEASE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001",
            "execution_release_candidate_id": (
                "CANDIDATE_RELEASE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001"
            ),
            "status": "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R11A_RUN",
            "release_candidate_sha256": common.sha256(root, common.RELEASE_CANDIDATE_RELATIVE),
            "implementation_contract_sha256": common.sha256(root, common.IMPLEMENTATION_RELATIVE),
            "approval_receipt_sha256": common.APPROVAL_RECEIPT_SHA,
            "approval_text_sha256": common.sha256(root, common.APPROVAL_TEXT_RELATIVE),
            "pricing_snapshot_sha256": common.sha256(root, common.PRICING_TARGET_RELATIVE),
            "workflow_sha256": common.sha256(root, common.WORKFLOW_RELATIVE),
            "collector_sha256": common.sha256(root, common.RUNNER_RELATIVE),
            "validator_sha256": common.sha256(root, common.ARTIFACT_VALIDATOR_RELATIVE),
            "selection_sha256": common.sha256(root, common.SELECTION_RELATIVE),
            "execution_release_candidate_review_evidence_sha256": self.evidence_digest(
                root, "R11A_EXECUTION_RELEASE_CANDIDATE_REVIEW"
            ),
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

    def activation_record(self, root: Path) -> dict[str, object]:
        return {
            "schema_version": "2.0",
            "activation_id": "ACTIVATE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001",
            "status": "ACTIVATED_FOR_EXACTLY_ONE_CANONICAL_R11A_RUN",
            "execution_release_id": "RELEASE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001",
            "execution_release_candidate_sha256": common.sha256(root, common.RELEASE_CANDIDATE_RELATIVE),
            "execution_release_blob_sha256": common.sha256(root, common.RELEASE_RELATIVE),
            "dispatch_ref_required": "refs/heads/main",
            "workflow_name": common.WORKFLOW_NAME,
            "workflow_path": common.WORKFLOW_RELATIVE,
            "workflow_sha256": common.sha256(root, common.WORKFLOW_RELATIVE),
            "execution_release_review_evidence_sha256": self.evidence_digest(
                root, "R11A_EXECUTION_RELEASE_REVIEW"
            ),
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

    def binding_record(self, root: Path) -> dict[str, object]:
        return {
            "schema_version": "2.0",
            "binding_id": "HL-ARCHIVE-R11A-RUNTIME-BINDING-R7-001",
            "diagnostic_id": common.DIAGNOSTIC_ID,
            "implementation_id": runtime_binding.IMPLEMENTATION_ID,
            "approval_id": common.APPROVAL_ID,
            "alignment_id": common.ALIGNMENT_ID,
            "status": "ACTIVE_FOR_EXACTLY_ONE_CANONICAL_R11A_R7_RUN",
            "workflow_name": common.WORKFLOW_NAME,
            "workflow_file": common.WORKFLOW_FILE,
            "candidate_workflow_path": common.CANDIDATE_RELATIVE,
            "installed_workflow_path": common.WORKFLOW_RELATIVE,
            "runtime_pricing_source_path": common.PRICING_SOURCE_RELATIVE,
            "runtime_pricing_installed_path": common.PRICING_TARGET_RELATIVE,
            "single_use_window_start_utc": "2026-08-26T00:00:00Z",
            "activation_review_evidence_sha256": self.evidence_digest(
                root, "R11A_ACTIVATION_REVIEW"
            ),
            "bound_files": {
                relative: common.sha256(root, relative)
                for relative in runtime_binding.REQUIRED_BOUND_PATHS
            },
            "runtime_authority": dict(runtime_binding._core.EXPECTED_RUNTIME_AUTHORITY),
            "science_state": dict(runtime_binding._core.EXPECTED_SCIENCE_STATE),
            "downstream_authorizations": false_mapping(common.DOWNSTREAM_AUTHORITY_KEYS),
            "trading_authorizations": false_mapping(common.TRADING_AUTHORITY_KEYS),
            "r11_closed": False,
            "r12_ready": False,
        }

    def add_configuration(self, root: Path) -> None:
        self.write_json(root, common.ROLE_CONFIGURATION_CANDIDATE_RELATIVE, self.configuration_record(root))

    def add_role(self, root: Path) -> None:
        self.write_json(root, common.ROLE_ATTESTATION_RELATIVE, self.role_record(root))

    def add_preflight_candidate(self, root: Path) -> None:
        self.write_json(root, common.PREFLIGHT_CANDIDATE_RELATIVE, self.preflight_candidate_record(root))

    def add_preflight_release(self, root: Path) -> None:
        self.write_json(root, common.PREFLIGHT_RELEASE_RELATIVE, self.preflight_release_record(root))

    def add_preflight(self, root: Path) -> None:
        self.preflight_records(root)

    def add_installation(self, root: Path) -> None:
        source = root / common.PRICING_SOURCE_RELATIVE
        target = root / common.PRICING_TARGET_RELATIVE
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        candidate = root / common.CANDIDATE_RELATIVE
        installed = root / common.WORKFLOW_RELATIVE
        installed.parent.mkdir(parents=True, exist_ok=True)
        installed.write_bytes(candidate.read_bytes())
        self.write_json(root, common.INSTALLATION_RELATIVE, self.installation_record(root))

    def add_release_candidate(self, root: Path) -> None:
        self.write_json(root, common.RELEASE_CANDIDATE_RELATIVE, self.release_candidate_record(root))

    def add_release(self, root: Path) -> None:
        raw = self.write_json(root, common.RELEASE_RELATIVE, self.release_record(root))
        digest = hashlib.sha256(raw).hexdigest()
        path = root / common.RELEASE_DIGEST_RELATIVE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"{digest}\n".encode("ascii"))

    def add_activation(self, root: Path) -> None:
        self.write_json(root, common.ACTIVATION_RELATIVE, self.activation_record(root))

    def add_binding(self, root: Path) -> None:
        self.write_json(root, common.BINDING_RELATIVE, self.binding_record(root))

    def add_complete_ladder(self, root: Path) -> None:
        self.add_configuration(root)
        self.add_role(root)
        self.add_preflight_candidate(root)
        self.add_preflight_release(root)
        self.add_preflight(root)
        self.add_installation(root)
        self.add_release_candidate(root)
        self.add_release(root)
        self.add_activation(root)
        self.add_binding(root)

    def gate_patches(self, root: Path, *, mock_approval: bool = True) -> ExitStack:
        stack = ExitStack()
        gate_modules = (
            role_configuration,
            role,
            preflight,
            installation,
            release,
            activation,
            runtime_binding._core,
            runtime_binding,
        )

        def consume_gate(
            repository: Path,
            record: dict[str, object],
            evidence_field: str,
            gate_id: str,
            *,
            lineage: list[object],
            **_kwargs: object,
        ) -> object:
            expected_index = len(lineage)
            if expected_index >= len(common.REVIEW_GATE_IDS):
                raise common.StageValidationError("review gate identity reused")
            if common.REVIEW_GATE_IDS[expected_index] != gate_id:
                raise common.StageValidationError("exact immediate review-gate lineage")
            observed_digest = common.require_sha256(record[evidence_field], evidence_field)
            expected_digest = self.evidence_digest(repository, gate_id)
            if observed_digest != expected_digest:
                raise common.StageValidationError("review evidence digest drift")
            target_files = _kwargs.get("target_files")
            predecessor_files = _kwargs.get("predecessor_files")
            if not isinstance(target_files, dict) or not isinstance(
                predecessor_files, dict
            ):
                raise common.StageValidationError("review byte bundle is absent")
            target_bundle = review_evidence.bundle_sha256(target_files)
            predecessor_bundle = review_evidence.bundle_sha256(predecessor_files)
            if lineage and predecessor_bundle != getattr(
                lineage[-1], "target_bundle_sha256", None
            ):
                raise common.StageValidationError(
                    "immediate-predecessor bundle does not equal prior target"
                )
            identity = types.SimpleNamespace(
                gate_id=gate_id,
                review_id=7000000000 + expected_index,
                reviewed_head=f"{expected_index + 1:040x}",
                reviewed_tree=f"{expected_index + 101:040x}",
                target_bundle_sha256=target_bundle,
            )
            lineage.append(identity)
            return identity

        if mock_approval:
            stack.enter_context(mock.patch.object(role_configuration, "validate_approval"))
        for module in gate_modules:
            stack.enter_context(mock.patch.object(module, "require_gate_review", side_effect=consume_gate))
        stack.enter_context(
            mock.patch.object(
                runtime_binding,
                "open_authenticated_repository",
                return_value=nullcontext(
                    AuthenticatedRepository(
                        snapshot_root=root,
                        head=SYNTHETIC_COMMIT,
                        tree="f" * 40,
                        index_version=2,
                        entries=(),
                        _source_root=root,
                    )
                ),
            )
        )
        stack.enter_context(
            mock.patch.object(
                runtime_binding,
                "authenticated_repository_checkpoint",
            )
        )
        return stack

    def validate_runtime(
        self,
        root: Path,
        *,
        mock_approval: bool = True,
    ) -> dict[str, object]:
        with self.gate_patches(root, mock_approval=mock_approval):
            return runtime_binding.validate(SYNTHETIC_COMMIT, 1, root=root)

    def test_live_alignment_and_approval_pass_then_every_future_gate_is_absent(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)

        record = g2.validate(repository)
        self.assertTrue(record["owner_approval_present"])
        self.assertTrue(record["canonical_approval_record_present"])
        self.assertFalse(record["execution_authorized_by_this_approval"])
        self.assertTrue(all(value is False for value in record["current_authority"].values()))
        self.assertEqual(record["science_state"]["empirical_root_cause"], "UNKNOWN_PENDING_DIAGNOSTIC")
        self.assertTrue(all(value is False for key, value in record["science_state"].items() if key != "empirical_root_cause"))
        self.assertTrue(all(value is False for value in record["trading_authorizations"].values()))
        self.assertEqual(alignment.validate_alignment(repository)["alignment_id"], context.ALIGNMENT_ID)
        approval_r4.validate(repository)

        absent = (
            common.ROLE_CONFIGURATION_CANDIDATE_RELATIVE,
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
            *common.REVIEW_EVIDENCE_PATHS.values(),
        )
        for relative in absent:
            with self.subTest(absent=relative):
                self.assertFalse((repository / relative).exists())

        validators = (
            role_configuration.validate,
            role.validate,
            preflight.validate_candidate,
            preflight.validate_release,
            preflight.validate,
            installation.validate,
            release.validate_candidate,
            release.validate,
            activation.validate,
        )
        for validator in validators:
            with self.subTest(validator=validator.__module__ + "." + validator.__name__):
                with self.assertRaisesRegex(common.StageValidationError, FIRST_MISSING):
                    validator(repository)
        with self.assertRaisesRegex(runtime_binding.RuntimeBindingError, FIRST_MISSING):
            runtime_binding._core.validate_binding(root=repository)

    def test_cache_free_validation_is_import_order_invariant(self) -> None:
        orders = (
            (
                "tests.test_archive_inventory_r11a_g2_owner_approval",
                "tests.test_archive_inventory_r11a_g1_owner_approval_readiness",
                "tests.test_archive_inventory_r11a_implementation",
                "tests.test_archive_inventory_r11a_post_approval_validator_alignment",
                "tests.test_archive_inventory_r11a_corrective_r7",
            ),
            (
                "tests.test_archive_inventory_r11a_post_approval_validator_alignment",
                "tests.test_archive_inventory_r11a_implementation",
                "tests.test_archive_inventory_r11a_g1_owner_approval_readiness",
                "tests.test_archive_inventory_r11a_g2_owner_approval",
                "tests.test_archive_inventory_r11a_corrective_r7",
            ),
            (
                "tests.test_archive_inventory_r11a_corrective_r7",
                "tests.test_archive_inventory_r11a_post_approval_validator_alignment",
                "tests.test_archive_inventory_r11a_g2_owner_approval",
                "tests.test_archive_inventory_r11a_implementation",
                "tests.test_archive_inventory_r11a_g1_owner_approval_readiness",
            ),
        )
        script = (
            "import importlib,sys\n"
            "from pathlib import Path\n"
            "for name in sys.argv[1:]: importlib.import_module(name)\n"
            "from governance import validate_r11a_g2_owner_approval as g2\n"
            "from governance import validate_r11a_post_approval_validator_alignment as a\n"
            "root=Path.cwd(); record=g2.validate(root); a.validate_alignment(root)\n"
            "if record['execution_authorized_by_this_approval'] is not False: raise SystemExit(9)\n"
        )
        environment = os.environ.copy()
        environment.pop("PYTHONPYCACHEPREFIX", None)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        for order in orders:
            with self.subTest(order=order[0]):
                temporary, repository = self.copy_repository()
                self.addCleanup(temporary.cleanup)
                completed = subprocess.run(
                    [sys.executable, "-B", "-c", script, *order],
                    cwd=repository,
                    env=environment,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                residue = [
                    path for path in repository.rglob("*")
                    if path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"}
                ]
                self.assertEqual(residue, [])

    def test_offline_successor_ladder_requires_every_predecessor_in_order(self) -> None:
        temporary, root = self.prepare_synthetic_root()
        self.addCleanup(temporary.cleanup)
        with self.gate_patches(root):
            steps = (
                (role_configuration.validate, self.add_configuration, FIRST_MISSING),
                (role.validate, self.add_role, "successor role attestation is absent"),
                (preflight.validate_candidate, self.add_preflight_candidate, "STS preflight candidate is absent"),
                (preflight.validate_release, self.add_preflight_release, "STS preflight release is absent"),
                (preflight.validate, self.add_preflight, "STS preflight evidence is absent"),
                (installation.validate, self.add_installation, "workflow installation contract is absent"),
                (release.validate_candidate, self.add_release_candidate, "execution release candidate is absent"),
                (release.validate, self.add_release, "execution release is absent"),
                (activation.validate, self.add_activation, "canonical activation is absent"),
            )
            for validator, add, message in steps:
                with self.subTest(stage=validator.__module__):
                    with self.assertRaisesRegex((common.StageValidationError, runtime_binding.RuntimeBindingError), message):
                        validator(root)
                    add(root)
                    validator(root)
            with self.assertRaisesRegex(runtime_binding.RuntimeBindingError, "R7 runtime binding is absent"):
                runtime_binding._core.validate_binding(root=root)
            self.add_binding(root)
            observed = runtime_binding.validate(SYNTHETIC_COMMIT, 1, root=root)
            self.assertEqual(observed["schema_version"], "2.0")
            self.assertEqual(observed["binding_id"], "HL-ARCHIVE-R11A-RUNTIME-BINDING-R7-001")

    def test_complete_offline_ladder_consumes_all_distinct_review_gates(self) -> None:
        temporary, root = self.prepare_synthetic_root()
        self.addCleanup(temporary.cleanup)
        self.add_complete_ladder(root)
        observed = self.validate_runtime(root)
        self.assertEqual(observed["activation_review_evidence_sha256"], self.evidence_digest(root, "R11A_ACTIVATION_REVIEW"))
        self.assertFalse(observed["runtime_authority"]["rerun"])
        self.assertFalse(observed["r11_closed"])
        self.assertFalse(observed["r12_ready"])

    def test_future_ladder_reconciles_project_state_without_fixed_current_blocker(
        self,
    ) -> None:
        """Run the ladder through the real approval/state consumer.

        GitHub review authenticity remains replaced by the focused gate double,
        while immutable G2 bytes, physical stage discovery, workflow inventory
        and PROJECT_STATE reconciliation are all validated without mocks.
        """

        temporary, root = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        self.add_synthetic_review_evidence(root)
        self.add_complete_ladder(root)
        projection = self.reconcile_project_state_from_physical_stages(root)
        self.assertTrue(all(projection.values()))

        observed = self.validate_runtime(root, mock_approval=False)
        self.assertEqual(observed["schema_version"], "2.0")
        parsed = workflow_identity.parse_project_state(root)
        for key in projection:
            with self.subTest(project_state=key):
                self.assertEqual(parsed[key], "true")
        self.assertEqual(
            parsed["r11a_execution_authorized_by_this_approval"],
            "false",
        )
        self.assertEqual(parsed["r11a_diagnostic_execution"], "false")
        self.assertEqual(parsed["r11a_execution_evidence"], "false")

    def test_removing_any_predecessor_invalidates_every_dependent_successor(self) -> None:
        stages = (
            (common.ROLE_CONFIGURATION_CANDIDATE_RELATIVE, FIRST_MISSING),
            (common.ROLE_ATTESTATION_RELATIVE, "successor role attestation is absent"),
            (common.PREFLIGHT_CANDIDATE_RELATIVE, "STS preflight candidate is absent"),
            (common.PREFLIGHT_RELEASE_RELATIVE, "STS preflight release is absent"),
            (common.PREFLIGHT_EVIDENCE_RELATIVE, "STS preflight evidence is absent"),
            (common.PREFLIGHT_CONSUMPTION_RELATIVE, "STS preflight release consumption is absent"),
            (common.INSTALLATION_RELATIVE, "workflow installation contract is absent"),
            (common.RELEASE_CANDIDATE_RELATIVE, "execution release candidate is absent"),
            (common.RELEASE_RELATIVE, "execution release is absent"),
            (common.RELEASE_DIGEST_RELATIVE, "detached execution release digest is absent"),
            (common.ACTIVATION_RELATIVE, "canonical activation is absent"),
            (common.BINDING_RELATIVE, "R7 runtime binding is absent"),
        )
        for relative, message in stages:
            with self.subTest(predecessor=relative):
                temporary, root = self.prepare_synthetic_root()
                try:
                    self.add_complete_ladder(root)
                    (root / relative).unlink()
                    with self.assertRaisesRegex((common.StageValidationError, runtime_binding.RuntimeBindingError), message):
                        self.validate_runtime(root)
                finally:
                    temporary.cleanup()

    def test_review_evidence_digest_and_runtime_review_cannot_be_omitted(self) -> None:
        temporary, root = self.prepare_synthetic_root()
        self.addCleanup(temporary.cleanup)
        self.add_complete_ladder(root)

        binding_path = root / common.BINDING_RELATIVE
        binding_value = json.loads(binding_path.read_bytes())
        binding_value["activation_review_evidence_sha256"] = ZERO_SHA
        binding_path.write_bytes(canonical_json(binding_value))
        with self.assertRaisesRegex(runtime_binding.RuntimeBindingError, "review evidence digest drift"):
            self.validate_runtime(root)

        self.add_binding(root)
        runtime_review = root / common.REVIEW_EVIDENCE_PATHS["R11A_RUNTIME_BINDING_REVIEW"]
        runtime_review.unlink()
        with self.assertRaisesRegex(runtime_binding.RuntimeBindingError, "required path is absent"):
            self.validate_runtime(root)

    def test_execution_artifact_post_precollector_route_requires_closed_context(self) -> None:
        minimal = {
            "schema_version": "2.0",
            "diagnostic_id": common.DIAGNOSTIC_ID,
            "implementation_id": runtime_binding.IMPLEMENTATION_ID,
            "execution_phase": "ARTIFACT_PACKAGING",
            "event_name": "workflow_dispatch",
            "dispatch_ref": "refs/heads/main",
            "dispatch_sha": SYNTHETIC_COMMIT,
            "checked_out_commit": SYNTHETIC_COMMIT,
            "workflow_run_id": 1,
            "workflow_run_attempt": 1,
            "workflow_start_epoch_ns": 1,
            "repository": g2.REPOSITORY,
            "workflow_name": common.WORKFLOW_NAME,
            "principal_observed": False,
            "s3_requests_executed": 0,
            "object_bytes_downloaded": 0,
            "rerun_authorized": False,
        }
        self.assertEqual(frozenset(minimal), execution_artifact._CONTEXT_COMMON_FIELDS)
        with self.assertRaisesRegex(
            execution_artifact.EvidenceValidationError,
            "post-precollector artifact requires exact complete bound context",
        ):
            execution_artifact._validate_artifact_route(
                minimal,
                {"terminal_class": "R11A_DIAGNOSTIC_SUCCESS"},
            )
        required = {
            "approval_id",
            "approval_text_sha256",
            "execution_release_id",
            "execution_release_blob_sha256",
            "activation_id",
            "implementation_contract_sha256",
            "workflow_sha256",
            "single_use_window_start_utc",
        }
        self.assertTrue(required <= execution_artifact._FULL_BOUND_CONTEXT_SCHEMA)

    def test_approved_owner_bytes_are_immutable(self) -> None:
        expected = {
            common.APPROVAL_TEXT_RELATIVE: "16f9f2c31ff90952033251d917884b1ca55771511e82e4b813414dc1a3f807d3",
            common.APPROVAL_JSON_RELATIVE: "531e61130b612fd12503e60ff56d1c3d51b05a64bb2785f1e10fa9c5471c7ae6",
            common.CANDIDATE_RELATIVE: "c10b810304d6cdbc68f23cb3db113b57580d34f0f74e781aefa2140edd0b5e65",
            common.TRUST_POLICY_RELATIVE: common.APPROVED_TRUST_SHA,
            common.PERMISSION_POLICY_RELATIVE: common.APPROVED_PERMISSION_SHA,
        }
        for relative, digest in expected.items():
            with self.subTest(path=relative):
                self.assertEqual(common.sha256(ROOT, relative), digest)

    def test_alignment_record_and_project_state_are_exact_post_g2_truth(self) -> None:
        record = alignment.validate_alignment(ROOT)
        self.assertEqual(record["alignment_id"], context.ALIGNMENT_ID)
        self.assertEqual(record["g2_review"]["review_id"], context.G2_REVIEW_ID)
        self.assertEqual(
            record["prior_exact_head_review"]["review_id"],
            context.RED_REVIEW_ID,
        )
        self.assertEqual(
            record["seven_finding_remediation"]["finding_ids"],
            list(context.REMEDIATED_FINDING_IDS),
        )
        self.assertEqual(
            record["review_governance_model"]["classification"],
            context.OWNER_REVIEW_MODEL,
        )
        self.assertTrue(
            record["review_governance_model"][
                "same_github_identity_as_pull_author_permitted"
            ]
        )
        for exact_identity_key in (
            "owner_exact_login_string_required",
            "owner_exact_user_id_required",
            "casefold_collision_with_different_exact_login_rejected",
            "permission_payload_reviewer_login_exact_match_required",
            "permission_payload_reviewer_user_id_exact_match_required",
        ):
            with self.subTest(exact_identity_key=exact_identity_key):
                self.assertTrue(
                    record["review_governance_model"][exact_identity_key]
                )
        self.assertFalse(
            record["review_governance_model"]["third_party_independence_claimed"]
        )
        self.assertTrue(
            record["review_governance_model"][
                "exact_canonical_marker_only_body_required"
            ]
        )
        model = record["review_governance_model"]
        self.assertEqual(
            ["review_id", "review_node_id", "reviewed_head", "reviewed_tree"],
            model["historical_seed_non_reuse_fields"],
        )
        self.assertEqual(
            [
                "review_id",
                "review_node_id",
                "evidence_sha256",
                "reviewed_head",
                "reviewed_tree",
            ],
            model["schema_1_1_governance_gate_non_reuse_fields"],
        )
        self.assertEqual(
            [
                ("software", 5019067044, "PRR_kwDOTw6wFs8AAAABKyjipA"),
                ("g1", 5027672461, "PRR_kwDOTw6wFs8AAAABK6wxjQ"),
                ("g2", 5033303996, "PRR_kwDOTw6wFs8AAAABLAIfvA"),
            ],
            [
                (seed["label"], seed["review_id"], seed["review_node_id"])
                for seed in model["historical_seed_reviews"]
            ],
        )
        self.assertFalse(
            model["historical_seed_evidence_sha256_non_reuse_claimed"]
        )
        self.assertFalse(model["seed_evidence_digests_fabricated"])
        self.assertTrue(
            record["review_governance_model"][
                "human_substantive_responsibility_retained"
            ]
        )
        self.assertEqual(
            record["historical_content_review"]["review_id"],
            context.HISTORICAL_CONTENT_REVIEW_ID,
        )
        self.assertTrue(record["historical_content_review"]["content_green"])
        self.assertFalse(
            record["historical_content_review"]["machine_readable_gate_evidence"]
        )
        self.assertFalse(record["historical_content_review"]["review_modified"])
        red_review = record["owner_review_model_red_review"]
        self.assertEqual(context.OWNER_MODEL_RED_REVIEW_ID, red_review["review_id"])
        self.assertEqual(
            context.OWNER_MODEL_RED_REVIEW_NODE_ID,
            red_review["review_node_id"],
        )
        self.assertEqual("RED", red_review["review_verdict"])
        self.assertFalse(red_review["review_modified"])
        remediation = record["owner_review_model_red_finding_remediation"]
        self.assertEqual(
            list(context.OWNER_MODEL_RED_FINDING_IDS),
            remediation["finding_ids"],
        )
        self.assertEqual(
            "IMPLEMENTED_AWAITING_EXACT_HEAD_REREVIEW",
            remediation["remediation_status"],
        )
        self.assertFalse(remediation["independent_closure"])
        self.assertFalse(remediation["review_closure"])
        self.assertEqual(context.NEXT_GATE, record["next_gate"])
        self.assertFalse(record["alignment_review_gate_closed"])
        state = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
        self.assertIn("r11a_owner_approval_record_review_complete = true", state)
        self.assertIn("r11a_execution_authorized_by_this_approval = false", state)
        self.assertIn("r11a_runtime_binding_review = false", state)

    def test_active_consumers_have_no_legacy_review_self_claim_helpers(self) -> None:
        active = tuple(context.ALIGNED_CONSUMERS) + (
            "governance/r11a_post_approval_context.py",
            "governance/r11a_stage_common_r4.py",
        )
        forbidden = (
            "require_green_review",
            "require_distinct_review",
            "require_fresh_review",
            "R11A_DEDICATED_ROLE_OPERATOR_ATTESTATION.json",
            "R11A_STS_PREFLIGHT_EVIDENCE.json",
            "R11A_WORKFLOW_INSTALLATION.json",
            "first matching contract",
        )
        for relative in active:
            raw = (ROOT / relative).read_bytes()
            for token in forbidden:
                with self.subTest(path=relative, token=token):
                    self.assertNotIn(token.encode("utf-8"), raw)
        self.assertEqual(tuple(common.REVIEW_GATE_IDS)[-1], "R11A_RUNTIME_BINDING_REVIEW")
        self.assertEqual(len(common.REVIEW_GATE_IDS), len(set(common.REVIEW_GATE_IDS)))

    def test_aligned_production_graph_is_offline_and_optimization_invariant(self) -> None:
        forbidden_import_roots = {"aiohttp", "boto3", "botocore", "httpx", "requests", "socket", "urllib"}
        for relative in ("governance/r11a_post_approval_context.py", *context.ALIGNED_CONSUMERS):
            with self.subTest(path=relative):
                if not relative.endswith(".py"):
                    raw = (ROOT / relative).read_bytes().lower()
                    self.assertFalse(
                        any(token.encode("ascii") in raw for token in forbidden_import_roots)
                    )
                    continue
                tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"), filename=relative)
                self.assertFalse(any(isinstance(node, ast.Assert) for node in ast.walk(tree)))
                self.assertFalse(any(isinstance(node, ast.Name) and node.id == "__debug__" for node in ast.walk(tree)))
                imports: set[str] = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imports.update(alias.name.split(".", 1)[0] for alias in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imports.add(node.module.split(".", 1)[0])
                self.assertFalse(imports & forbidden_import_roots)

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
