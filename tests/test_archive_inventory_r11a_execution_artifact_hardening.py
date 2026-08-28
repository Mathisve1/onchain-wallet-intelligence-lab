from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from contextlib import ExitStack, nullcontext
from pathlib import Path
from unittest import mock

from governance import r11a_stage_common_r4 as stage
from governance import validate_r11a_execution_artifact_r7 as subject
from research.archive_inventory.r11a_corrective import (
    _artifact_contract_core_r7 as artifact_contract,
)
from research.archive_inventory.r11a_corrective.artifact import (
    ArtifactBoundaryError,
    validate_artifact,
)
from research.archive_inventory.r11a_corrective.artifact_schema import (
    ArtifactSchemaError,
    PHASES,
)
from research.archive_inventory.r11a_corrective.canonical import canonical_json_bytes
from research.archive_inventory.r11a_corrective.limits import DEFAULT_LIMITS
from tests import test_archive_inventory_r11a_corrective_r7 as r7_fixtures


DISPATCH_SHA = "a" * 40
WINDOW_START = "2026-01-01T00:00:00Z"
RELEASE_ID = "R11A-TEST-RELEASE"
ACTIVATION_ID = "R11A-TEST-ACTIVATION"
ROOT = Path("/synthetic-r11a-artifact-root")


def digest(relative: str) -> str:
    return hashlib.sha256(relative.encode("utf-8")).hexdigest()


def minimal_context(phase: str) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": "2.0",
        "diagnostic_id": stage.DIAGNOSTIC_ID,
        "implementation_id": subject.IMPLEMENTATION_ID,
        "execution_phase": phase,
        "event_name": "workflow_dispatch",
        "dispatch_ref": "refs/heads/main",
        "dispatch_sha": DISPATCH_SHA,
        "checked_out_commit": DISPATCH_SHA,
        "workflow_run_id": 17,
        "workflow_run_attempt": 1,
        "workflow_start_epoch_ns": 1,
        "repository": "Mathisve1/onchain-wallet-intelligence-lab",
        "workflow_name": stage.WORKFLOW_NAME,
        "principal_observed": False,
        "s3_requests_executed": 0,
        "object_bytes_downloaded": 0,
        "rerun_authorized": False,
    }
    if frozenset(value) != subject._CONTEXT_COMMON_FIELDS:
        raise AssertionError("test minimal context differs from approved core schema")
    return value


def full_context(phase: str = "ARTIFACT_PACKAGING") -> dict[str, object]:
    value = minimal_context(phase)
    value["principal_observed"] = True
    value.update(
        {
            "approval_id": stage.APPROVAL_ID,
            "approval_text_sha256": digest(stage.APPROVAL_TEXT_RELATIVE),
            "execution_release_id": RELEASE_ID,
            "execution_release_blob_sha256": digest(stage.RELEASE_RELATIVE),
            "activation_id": ACTIVATION_ID,
            "implementation_contract_sha256": digest(stage.IMPLEMENTATION_RELATIVE),
            "workflow_sha256": digest(stage.WORKFLOW_RELATIVE),
            "collector_sha256": digest(stage.RUNNER_RELATIVE),
            "validator_sha256": digest(stage.ARTIFACT_VALIDATOR_RELATIVE),
            "selection_sha256": digest(stage.SELECTION_RELATIVE),
            "pricing_snapshot_sha256": digest(stage.PRICING_TARGET_RELATIVE),
            "single_use_window_start_utc": WINDOW_START,
            "observed_account_id": "630956766927",
            "observed_assumed_role_session_arn": (
                "arn:aws:sts::630956766927:assumed-role/"
                "onchain-wallet-intelligence-hl-archive-identity-r11a/"
                "HLArchiveR11AIdentityBoundary"
            ),
            "observed_session_name": "HLArchiveR11AIdentityBoundary",
            "expected_role_arn": stage.ROLE_ARN,
            "pricing_projection_eur_micros": 383757,
            "raw_aws_credentials_retained": False,
            "raw_oidc_token_retained": False,
            "raw_sts_response_retained": False,
        }
    )
    if frozenset(value) != subject._FULL_BOUND_CONTEXT_SCHEMA:
        raise AssertionError("test bound context differs from approved core schema")
    return value


def result(terminal: str) -> dict[str, object]:
    return {"terminal_class": terminal}


def reviewed_binding() -> dict[str, object]:
    return {
        "approval_id": stage.APPROVAL_ID,
        "implementation_id": subject.IMPLEMENTATION_ID,
        "workflow_name": stage.WORKFLOW_NAME,
        "single_use_window_start_utc": WINDOW_START,
        "bound_files": {
            relative: digest(relative)
            for relative in subject.RUNTIME_REQUIRED_BOUND_PATHS
        },
    }


class ArtifactHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        return_code, cls.complete_artifact = r7_fixtures.execute_public_synthetic_route(
            cls.root / "complete-workspace",
            incomplete=False,
        )
        if return_code != 0:
            raise AssertionError("synthetic RC0 fixture did not complete")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def stage_patches(self) -> ExitStack:
        stack = ExitStack()

        def load(_root: Path, relative: str) -> dict[str, object]:
            if relative == stage.RELEASE_RELATIVE:
                return {"execution_release_id": RELEASE_ID}
            if relative == stage.ACTIVATION_RELATIVE:
                return {"activation_id": ACTIVATION_ID}
            if relative == stage.PRICING_TARGET_RELATIVE:
                return {"projected_eur_micros_at_frozen_maximum": 383757}
            raise AssertionError(f"unexpected stage load: {relative}")

        stack.enter_context(mock.patch.object(subject._stage, "load", side_effect=load))
        stack.enter_context(
            mock.patch.object(
                subject._stage,
                "sha256",
                side_effect=lambda _root, relative: digest(relative),
            )
        )
        return stack

    def authenticated_repository(self) -> subject.AuthenticatedRepository:
        return subject.AuthenticatedRepository(
            snapshot_root=ROOT / "authenticated-snapshot",
            head=DISPATCH_SHA,
            tree="f" * 40,
            index_version=2,
            entries=(),
            _source_root=ROOT,
        )

    def assert_combined_bound_validation_rejects(
        self,
        context: dict[str, object],
    ) -> None:
        try:
            artifact_contract._validate_context_shape(context)
        except (ArtifactBoundaryError, ArtifactSchemaError):
            return
        with self.stage_patches(), self.assertRaises(subject.EvidenceValidationError):
            subject._validate_bound_context(context, reviewed_binding(), root=ROOT)

    def write_stub_artifact(
        self,
        context: dict[str, object],
        terminal: str,
    ) -> Path:
        artifact = self.root / "stub-artifact"
        if artifact.exists():
            shutil.rmtree(artifact)
        artifact.mkdir()
        (artifact / subject.CONTEXT_FILE).write_bytes(canonical_json_bytes(context))
        (artifact / subject.RESULT_FILE).write_bytes(
            canonical_json_bytes(
                {
                    "terminal_class": terminal,
                }
            )
        )
        return artifact

    def test_old_all_bound_fields_removed_exploit_is_closed_outside_frozen_core(
        self,
    ) -> None:
        artifact = self.root / "all-bound-fields-removed"
        shutil.copytree(self.complete_artifact, artifact)
        context_path = artifact / subject.CONTEXT_FILE
        context = json.loads(context_path.read_bytes())
        for key in subject._CONTEXT_BOUND_FIELDS:
            context.pop(key)
        context_path.write_bytes(canonical_json_bytes(context))
        r7_fixtures.refresh_artifact_bindings(artifact)

        # The frozen core deliberately supports the minimal schema.  The
        # aligned consumer must reject its use at ARTIFACT_PACKAGING.
        validate_artifact(artifact, DEFAULT_LIMITS)
        with (
            mock.patch.object(subject, "validate_reviewed_runtime_binding") as gate,
            mock.patch.object(subject, "validate_science") as science,
            self.assertRaisesRegex(
                subject.EvidenceValidationError,
                "post-precollector artifact requires exact complete bound context",
            ),
        ):
            subject.validate_aligned_execution_artifact(
                artifact,
                root=ROOT,
                expected_run_id=17,
            )
        gate.assert_not_called()
        science.assert_not_called()

    def test_phase_and_terminal_select_schema_without_field_presence_fallback(
        self,
    ) -> None:
        early_terminal = result(subject._FAIL_CLOSED_EARLY_TERMINAL)
        for phase in PHASES[:4]:
            with self.subTest(valid_minimal_precollector_phase=phase):
                observed = subject._validate_artifact_route(
                    minimal_context(phase),
                    early_terminal,
                )
                self.assertEqual(observed, (phase, False))
            with self.subTest(bound_context_cannot_select_early_route=phase):
                with self.assertRaisesRegex(
                    subject.EvidenceValidationError,
                    "must use exact minimal context",
                ):
                    subject._validate_artifact_route(
                        full_context(phase),
                        early_terminal,
                    )

        for phase in PHASES[4:]:
            with self.subTest(minimal_context_cannot_select_runtime_route=phase):
                with self.assertRaisesRegex(
                    subject.EvidenceValidationError,
                    "requires exact complete bound context",
                ):
                    subject._validate_artifact_route(
                        minimal_context(phase),
                        early_terminal,
                    )
            with self.subTest(valid_bound_runtime_phase=phase):
                self.assertEqual(
                    subject._validate_artifact_route(
                        full_context(phase),
                        early_terminal,
                    ),
                    (phase, True),
                )

        for phase in PHASES[:4]:
            for terminal in (
                "R11A_V2_ROOT_CAUSE_TAXONOMY_COMPLETE",
                "R11A_V2_DIAGNOSTIC_INCOMPLETE",
                "R11A_V2_ARTIFACT_CAP_EXCEEDED",
            ):
                with self.subTest(illegal_precollector_terminal=terminal, phase=phase):
                    with self.assertRaisesRegex(
                        subject.EvidenceValidationError,
                        "not an exact fail-closed early terminal",
                    ):
                        subject._validate_artifact_route(
                            minimal_context(phase),
                            result(terminal),
                        )

        for terminal in subject._FULL_SCIENCE_TERMINALS:
            self.assertEqual(
                subject._validate_artifact_route(
                    full_context("ARTIFACT_PACKAGING"),
                    result(terminal),
                ),
                ("ARTIFACT_PACKAGING", True),
            )
            with self.assertRaisesRegex(
                subject.EvidenceValidationError,
                "lacks packaging-phase bound context",
            ):
                subject._validate_artifact_route(
                    full_context("S3_DOWNLOAD"),
                    result(terminal),
                )

    def test_each_bound_field_is_required_individually(self) -> None:
        for key in sorted(subject._CONTEXT_BOUND_FIELDS):
            with self.subTest(removed_bound_field=key):
                mutated = full_context()
                mutated.pop(key)
                with self.assertRaisesRegex(
                    subject.EvidenceValidationError,
                    "neither exact minimal nor exact bound schema",
                ):
                    subject._validate_artifact_route(
                        mutated,
                        result("R11A_V2_ROOT_CAUSE_TAXONOMY_COMPLETE"),
                    )

    def test_each_bound_field_rejects_null_wrong_type_and_wrong_value(self) -> None:
        for key in sorted(subject._CONTEXT_BOUND_FIELDS):
            if key.endswith("_sha256"):
                wrong_value: object = "f" * 64
            elif key == "pricing_projection_eur_micros":
                wrong_value = 0
            elif key.startswith("raw_"):
                wrong_value = True
            else:
                wrong_value = "WRONG"
            for label, replacement in (
                ("null", None),
                ("wrong_type", []),
                ("wrong_value", wrong_value),
            ):
                with self.subTest(field=key, mutation=label):
                    mutated = full_context()
                    mutated[key] = replacement
                    self.assert_combined_bound_validation_rejects(mutated)

    def test_reviewed_binding_must_bind_every_artifact_sha(self) -> None:
        context = full_context()
        with self.stage_patches():
            subject._validate_bound_context(context, reviewed_binding(), root=ROOT)

        for key, relative in (
            ("approval_text_sha256", stage.APPROVAL_TEXT_RELATIVE),
            ("execution_release_blob_sha256", stage.RELEASE_RELATIVE),
            ("implementation_contract_sha256", stage.IMPLEMENTATION_RELATIVE),
            ("workflow_sha256", stage.WORKFLOW_RELATIVE),
            ("collector_sha256", stage.RUNNER_RELATIVE),
            ("validator_sha256", stage.ARTIFACT_VALIDATOR_RELATIVE),
            ("selection_sha256", stage.SELECTION_RELATIVE),
            ("pricing_snapshot_sha256", stage.PRICING_TARGET_RELATIVE),
        ):
            for mutation in ("missing", "drift"):
                with self.subTest(context_field=key, binding_mutation=mutation):
                    binding = copy.deepcopy(reviewed_binding())
                    bound_files = binding["bound_files"]
                    self.assertIsInstance(bound_files, dict)
                    if mutation == "missing":
                        bound_files.pop(relative)  # type: ignore[union-attr]
                    else:
                        bound_files[relative] = "f" * 64  # type: ignore[index]
                    expected_error = (
                        "exact complete stage chain"
                        if mutation == "missing"
                        else f"reviewed runtime: {key}"
                    )
                    with self.stage_patches(), self.assertRaisesRegex(
                        subject.EvidenceValidationError,
                        expected_error,
                    ):
                        subject._validate_bound_context(context, binding, root=ROOT)

    def test_every_phase_calls_reviewed_runtime_gate_before_science(
        self,
    ) -> None:
        for phase in PHASES:
            context = (
                minimal_context(phase)
                if phase in subject._PRECOLLECTOR_FAILURE_PHASES
                else full_context(phase)
            )
            artifact = self.write_stub_artifact(
                context,
                subject._FAIL_CLOSED_EARLY_TERMINAL,
            )
            authenticated = self.authenticated_repository()
            with (
                mock.patch.object(subject, "validate_artifact"),
                mock.patch.object(
                    subject,
                    "open_authenticated_repository",
                    return_value=nullcontext(authenticated),
                ),
                mock.patch.object(
                    subject,
                    "validate_reviewed_runtime_binding",
                    return_value=reviewed_binding(),
                ) as gate,
                mock.patch.object(subject, "authenticated_repository_checkpoint"),
                mock.patch.object(subject, "_validate_bound_context") as bound,
                mock.patch.object(subject, "validate_science") as science,
            ):
                subject.validate_aligned_execution_artifact(
                    artifact,
                    root=ROOT,
                    expected_run_id=17,
                )
            gate.assert_called_once_with(
                DISPATCH_SHA,
                1,
                root=authenticated.snapshot_root,
                authenticated=authenticated,
            )
            if phase in subject._PRECOLLECTOR_FAILURE_PHASES:
                bound.assert_not_called()
            else:
                bound.assert_called_once()
            science.assert_called_once_with(artifact)

    def test_missing_reviewed_runtime_gate_stops_before_science(self) -> None:
        artifact = self.write_stub_artifact(
            minimal_context("OIDC_ROLE_ASSUMPTION"),
            subject._FAIL_CLOSED_EARLY_TERMINAL,
        )
        authenticated = self.authenticated_repository()
        with (
            mock.patch.object(subject, "validate_artifact"),
            mock.patch.object(
                subject,
                "open_authenticated_repository",
                return_value=nullcontext(authenticated),
            ),
            mock.patch.object(
                subject,
                "validate_reviewed_runtime_binding",
                side_effect=subject.EvidenceValidationError(
                    "runtime-binding review evidence is absent"
                ),
            ) as gate,
            mock.patch.object(subject, "authenticated_repository_checkpoint"),
            mock.patch.object(subject, "validate_science") as science,
            self.assertRaisesRegex(
                subject.EvidenceValidationError,
                "runtime-binding review evidence is absent",
            ),
        ):
            subject.validate_aligned_execution_artifact(
                artifact,
                root=ROOT,
                expected_run_id=17,
            )
        gate.assert_called_once_with(
            DISPATCH_SHA,
            1,
            root=authenticated.snapshot_root,
            authenticated=authenticated,
        )
        science.assert_not_called()

    def test_workflow_run_id_must_match_trusted_runtime_identity(self) -> None:
        artifact = self.write_stub_artifact(
            minimal_context("PRE_OIDC_STATIC_GATE"),
            subject._FAIL_CLOSED_EARLY_TERMINAL,
        )
        with (
            mock.patch.object(subject, "validate_artifact"),
            mock.patch.object(subject, "validate_reviewed_runtime_binding") as gate,
            mock.patch.object(subject, "validate_science") as science,
            self.assertRaisesRegex(
                subject.EvidenceValidationError,
                "workflow run ID differs from trusted current run",
            ),
        ):
            subject.validate_aligned_execution_artifact(
                artifact,
                root=ROOT,
                expected_run_id=18,
            )
        gate.assert_not_called()
        science.assert_not_called()


if __name__ == "__main__":
    unittest.main()
