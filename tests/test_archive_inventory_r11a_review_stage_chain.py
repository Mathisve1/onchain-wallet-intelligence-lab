from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, mock

from governance import r11a_post_approval_context as post_approval
from governance import r11a_stage_common_r4 as common
from governance import validate_r11a_activation_r4 as activation
from governance import validate_r11a_execution_release_r4 as execution_release
from governance import validate_r11a_role_attestation_r4 as role_attestation
from governance import validate_r11a_role_configuration_candidate_r4 as role_configuration
from governance import validate_r11a_role_preflight_evidence_r4 as preflight
from governance import validate_r11a_workflow_installation_r4 as installation


ROOT = Path(__file__).absolute().parents[1]


def _all_false(keys: frozenset[str]) -> dict[str, bool]:
    return {key: False for key in keys}


class ReviewStageChainTests(TestCase):
    def _configuration_candidate(self) -> dict[str, object]:
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
            "alignment_record_sha256": "a" * 64,
            "approval_receipt_sha256": common.APPROVAL_RECEIPT_SHA,
            "g2_review_id": common.G2_REVIEW_ID,
            "alignment_review_evidence_sha256": "e" * 64,
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
            "downstream_authorizations": _all_false(
                common.DOWNSTREAM_AUTHORITY_KEYS
            ),
            "trading_authorizations": _all_false(common.TRADING_AUTHORITY_KEYS),
        }

    def test_configuration_candidate_is_inert_and_consumes_alignment_capture(self) -> None:
        record = self._configuration_candidate()

        def digest(_root: Path, relative: str) -> str:
            fixed = {
                common.APPROVAL_JSON_RELATIVE: common.APPROVAL_RECEIPT_SHA,
                common.APPROVAL_TEXT_RELATIVE: "b" * 64,
                common.TRUST_POLICY_RELATIVE: common.APPROVED_TRUST_SHA,
                common.PERMISSION_POLICY_RELATIVE: common.APPROVED_PERMISSION_SHA,
            }
            return fixed.get(relative, "a" * 64)

        with (
            mock.patch.object(role_configuration, "validate_approval"),
            mock.patch.object(role_configuration, "load", return_value=record),
            mock.patch.object(role_configuration, "sha256", side_effect=digest),
            mock.patch.object(
                role_configuration,
                "alignment_review_target_files",
                return_value={
                    common.ALIGNMENT_RELATIVE: "a" * 64,
                    **{
                        relative: "a" * 64
                        for relative in post_approval.ALIGNED_CONSUMERS
                    },
                },
            ),
            mock.patch.object(
                role_configuration,
                "require_gate_review",
                return_value=SimpleNamespace(gate_id="R11A_ALIGNMENT_REVIEW"),
            ) as review,
        ):
            observed = role_configuration.validate(Path("/synthetic/root"))

        self.assertIs(observed, record)
        self.assertFalse(record["role_creation_authorized_by_candidate"])
        kwargs = review.call_args.kwargs
        self.assertEqual(kwargs["expected_pr_number"], 151)
        self.assertEqual(
            set(kwargs["target_files"]),
            {common.ALIGNMENT_RELATIVE, *post_approval.ALIGNED_CONSUMERS},
        )
        self.assertEqual(
            set(kwargs["predecessor_files"]),
            {common.APPROVAL_JSON_RELATIVE, common.APPROVAL_TEXT_RELATIVE},
        )

    def test_configuration_candidate_rejects_inline_review_self_claim(self) -> None:
        record = self._configuration_candidate()
        record["alignment_review_id"] = 5049607285
        with (
            mock.patch.object(role_configuration, "validate_approval"),
            mock.patch.object(role_configuration, "load", return_value=record),
        ):
            with self.assertRaisesRegex(
                common.StageValidationError,
                "role configuration candidate key set drift",
            ):
                role_configuration.validate(Path("/synthetic/root"))

    def test_every_r4_consumer_uses_one_digest_not_six_editable_review_fields(self) -> None:
        schemas = (
            (
                role_configuration.CANDIDATE_KEYS,
                "alignment_review_evidence_sha256",
            ),
            (
                role_attestation.ATTESTATION_KEYS,
                "identity_configuration_review_evidence_sha256",
            ),
            (preflight.CANDIDATE_KEYS, "role_attestation_review_evidence_sha256"),
            (
                preflight.RELEASE_KEYS,
                "sts_preflight_candidate_review_evidence_sha256",
            ),
            (
                preflight.EVIDENCE_KEYS,
                "sts_preflight_release_review_evidence_sha256",
            ),
            (installation.CONTRACT_KEYS, "sts_preflight_review_evidence_sha256"),
            (
                execution_release.CANDIDATE_KEYS,
                "workflow_installation_review_evidence_sha256",
            ),
            (
                execution_release.RELEASE_KEYS,
                "execution_release_candidate_review_evidence_sha256",
            ),
            (
                activation.ACTIVATION_KEYS,
                "execution_release_review_evidence_sha256",
            ),
        )
        prohibited_suffixes = (
            "_review_completed",
            "_review_id",
            "_review_event",
            "_review_verdict",
            "_reviewed_head",
            "_reviewed_tree",
        )
        for keys, evidence_field in schemas:
            with self.subTest(evidence_field=evidence_field):
                self.assertIn(evidence_field, keys)
                self.assertFalse(
                    any(
                        key != "g2_review_id" and key.endswith(prohibited_suffixes)
                        for key in keys
                    ),
                    sorted(keys),
                )
        self.assertNotIn("activation_base_commit", activation.ACTIVATION_KEYS)
        self.assertNotIn(
            "canonical_activation_merge_commit",
            activation.ACTIVATION_KEYS,
        )

    def test_review_gate_lineage_is_exact_and_cannot_skip_or_reuse(self) -> None:
        self.assertEqual(
            ("review_id", "review_node_id", "reviewed_head", "reviewed_tree"),
            common._review_evidence.HISTORICAL_SEED_NON_REUSE_FIELDS,
        )
        self.assertEqual(
            (
                "review_id",
                "review_node_id",
                "evidence_sha256",
                "reviewed_head",
                "reviewed_tree",
            ),
            common._review_evidence.SCHEMA_1_1_GATE_NON_REUSE_FIELDS,
        )
        self.assertEqual(
            (
                "PRR_kwDOTw6wFs8AAAABKyjipA",
                "PRR_kwDOTw6wFs8AAAABK6wxjQ",
                "PRR_kwDOTw6wFs8AAAABLAIfvA",
            ),
            tuple(
                seed.review_node_id
                for seed in common._review_evidence.SEED_REVIEWS
            ),
        )
        lineage: list[object] = []

        def identity(_root: Path, gate_id: str, **kwargs: object) -> object:
            gate_index = common.REVIEW_GATE_IDS.index(gate_id)
            if gate_index:
                self.assertEqual(
                    common._review_evidence.bundle_sha256(
                        kwargs["expected_predecessor_files"]
                    ),
                    lineage[-1].target_bundle_sha256,
                )
            return SimpleNamespace(
                gate_id=gate_id,
                evidence_sha256=(
                    f"{gate_index + 1:064x}"
                ),
                target_bundle_sha256=common._review_evidence.bundle_sha256(
                    kwargs["expected_target_files"]
                ),
            )

        with mock.patch.object(
            common._review_evidence,
            "validate_gate_evidence",
            side_effect=identity,
        ):
            for gate_index, gate_id in enumerate(common.REVIEW_GATE_IDS):
                common.require_gate_review(
                    Path("/synthetic/root"),
                    {"evidence_sha256": "a" * 64},
                    "evidence_sha256",
                    gate_id,
                    target_files={f"stage-{gate_index}.json": f"{gate_index + 20:064x}"},
                    predecessor_files=(
                        {"g2.json": "c" * 64}
                        if gate_index == 0
                        else {
                            f"stage-{gate_index - 1}.json": (
                                f"{gate_index + 19:064x}"
                            )
                        }
                    ),
                    lineage=lineage,
                )
        self.assertEqual(
            tuple(item.gate_id for item in lineage), common.REVIEW_GATE_IDS
        )

        skipped = [
            SimpleNamespace(
                gate_id=common.REVIEW_GATE_IDS[0],
                evidence_sha256="1" * 64,
            )
        ]
        with self.assertRaisesRegex(
            common.StageValidationError,
            "exact immediate review-gate lineage",
        ):
            common.require_gate_review(
                Path("/synthetic/root"),
                {"evidence_sha256": "a" * 64},
                "evidence_sha256",
                common.REVIEW_GATE_IDS[2],
                target_files={"target.json": "b" * 64},
                predecessor_files={"predecessor.json": "c" * 64},
                lineage=skipped,
            )

    def test_r4_consumers_fail_at_first_absent_configuration_stage(self) -> None:
        validators = (
            role_configuration.validate,
            role_attestation.validate,
            preflight.validate_candidate,
            preflight.validate_release,
            preflight.validate,
            installation.validate,
            execution_release.validate_candidate,
            execution_release.validate,
            activation.validate,
        )
        for validator in validators:
            with self.subTest(
                validator=validator.__module__ + "." + validator.__name__
            ):
                with self.assertRaisesRegex(
                    (common.StageValidationError, AssertionError),
                    "successor role creation/configuration candidate is absent",
                ):
                    validator(ROOT)


if __name__ == "__main__":
    import unittest

    unittest.main()
