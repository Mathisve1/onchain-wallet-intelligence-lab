from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from governance import validate_r11a_g1_owner_approval_readiness as readiness
from governance.validate_r11a_g1_owner_approval_readiness import (
    G1ReadinessError,
    STATUS_FIELD_CLASSIFICATION,
    STATUS_INFORMATIONAL_FIELDS,
    canonical_joined_rows,
    validate,
)

ROOT = Path(__file__).resolve().parents[1]
STATUS_RELATIVE = Path("research/archive_inventory/r11a_g1/R11A_G1_STATUS.json")

AUTHORITATIVE_STATUS_LEAVES = (
    ("schema_version",),
    ("status_id",),
    ("status",),
    ("decision",),
    ("repository",),
    ("software_anchor", "review_id"),
    ("software_anchor", "review_event"),
    ("software_anchor", "review_verdict"),
    ("software_anchor", "reviewed_head"),
    ("software_anchor", "reviewed_tree"),
    ("software_anchor", "base_sha"),
    ("software_anchor", "sha_drift"),
    ("software_anchor", "superseding_red_review_present"),
    ("software_anchor", "verified_against_live_github_on_date_utc"),
    ("historical_r7_seal", "semantics"),
    ("historical_r7_seal", "reviewed_head_contract_sha256"),
    ("historical_r7_seal", "reviewed_head_status_sha256"),
    ("historical_r7_seal", "historical_semantics_rewritten"),
    (
        "historical_r7_seal",
        "successor_manifest_projection_may_be_mechanically_resealed",
    ),
    ("current_bindings", "execution_envelope_path"),
    ("current_bindings", "execution_envelope_sha256"),
    ("current_bindings", "pricing_eur_binding_path"),
    ("current_bindings", "pricing_eur_binding_sha256"),
    ("current_bindings", "runtime_pricing_candidate_path"),
    ("current_bindings", "runtime_pricing_candidate_sha256"),
    ("current_bindings", "owner_approval_package_path"),
    ("current_bindings", "owner_approval_package_sha256"),
    ("current_bindings", "proposed_owner_statement_path"),
    ("current_bindings", "proposed_owner_statement_sha256"),
    ("pricing", "current_official_binding"),
    ("pricing", "pricing_binding_pending"),
    ("pricing", "raw_max_eur_ceil_6dp"),
    ("pricing", "projected_with_contingency_eur_ceil_6dp"),
    ("pricing", "owner_approval_max_eur"),
    ("pricing", "monthly_recurring_budget_eur"),
    ("iam_workflow_readiness", "status"),
    (
        "iam_workflow_readiness",
        "permission_policy_exact_72_getobject_resources",
    ),
    (
        "iam_workflow_readiness",
        "oidc_repository_owner_ref_and_workflow_restricted",
    ),
    ("iam_workflow_readiness", "workflow_exact_hash_bound"),
    ("iam_workflow_readiness", "workflow_candidate_outside_dot_github"),
    ("iam_workflow_readiness", "secrets_or_reusable_credentials"),
    ("iam_workflow_readiness", "external_infrastructure_created"),
    ("owner_approval", "approval_id"),
    ("owner_approval", "approval_status"),
    ("owner_approval", "owner_approval_ready"),
    ("owner_approval", "owner_approval_present"),
    ("owner_approval", "canonical_approval_record_present"),
    ("runtime_authority", "successor_role_created"),
    ("runtime_authority", "aws_iam_mutation"),
    ("runtime_authority", "aws_oidc"),
    ("runtime_authority", "sts"),
    ("runtime_authority", "workflow_installed"),
    ("runtime_authority", "runtime_binding_present"),
    ("runtime_authority", "runtime_release"),
    ("runtime_authority", "runtime_activation"),
    ("runtime_authority", "requester_pays"),
    ("runtime_authority", "get_object"),
    ("runtime_authority", "object_body_download"),
    ("runtime_authority", "decompression"),
    ("runtime_authority", "diagnostic_execution"),
    ("runtime_authority", "diagnostic_artifact_retention"),
    ("science_state", "empirical_root_cause"),
    ("science_state", "deduplication"),
    ("science_state", "replay_suppression"),
    ("science_state", "r11b_repair"),
    ("science_state", "wallet_ranking"),
    ("science_state", "copyability"),
    ("science_state", "r11_closed"),
    ("science_state", "r12_ready"),
    ("trading_authorizations", "integration"),
    ("trading_authorizations", "paper"),
    ("trading_authorizations", "shadow"),
    ("trading_authorizations", "live"),
    ("trading_authorizations", "leverage"),
    ("trading_authorizations", "capital_allocation"),
)

AUTHORITATIVE_STATUS_OBJECTS = (
    (),
    ("software_anchor",),
    ("historical_r7_seal",),
    ("current_bindings",),
    ("pricing",),
    ("iam_workflow_readiness",),
    ("owner_approval",),
    ("runtime_authority",),
    ("science_state",),
    ("trading_authorizations",),
)

BINDING_PAIRS = (
    ("execution_envelope_path", "execution_envelope_sha256"),
    ("pricing_eur_binding_path", "pricing_eur_binding_sha256"),
    ("runtime_pricing_candidate_path", "runtime_pricing_candidate_sha256"),
    ("owner_approval_package_path", "owner_approval_package_sha256"),
    ("proposed_owner_statement_path", "proposed_owner_statement_sha256"),
)

STRING_MUTATIONS = {
    ("schema_version",): "2.0",
    ("status_id",): "R11A-G1-POST-GREEN-READINESS-STATUS-002",
    ("status",): "OWNER_APPROVAL_GRANTED_RUNTIME_AUTHORIZED",
    ("decision",): "OWNER_APPROVAL_NOT_READY",
    ("repository",): "example/other-repository",
    ("software_anchor", "review_event"): "APPROVED",
    ("software_anchor", "review_verdict"): "RED",
    (
        "software_anchor",
        "verified_against_live_github_on_date_utc",
    ): "2026-08-24",
    (
        "historical_r7_seal",
        "semantics",
    ): "POST_REVIEW_REWRITTEN_SEAL",
    ("pricing", "current_official_binding"): "FAIL",
    ("pricing", "raw_max_eur_ceil_6dp"): "0.191880",
    (
        "pricing",
        "projected_with_contingency_eur_ceil_6dp",
    ): "0.383758",
    ("pricing", "owner_approval_max_eur"): "0.600000",
    ("pricing", "monthly_recurring_budget_eur"): "0.010000",
    ("iam_workflow_readiness", "status"): "FAIL_AUTHORITY_OPEN",
    (
        "owner_approval",
        "approval_id",
    ): "APPROVE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_002",
    ("owner_approval", "approval_status"): "APPROVED",
    ("science_state", "empirical_root_cause"): "PROVEN_EXACT_REPLAY",
}


def status_leaf_paths(value: dict[str, object]) -> set[tuple[str, ...]]:
    leaves: set[tuple[str, ...]] = set()

    def walk(item: object, prefix: tuple[str, ...]) -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                walk(nested, prefix + (key,))
            return
        leaves.add(prefix)

    walk(value, ())
    return leaves


def nested(value: dict[str, object], path: tuple[str, ...]) -> object:
    current: object = value
    for key in path:
        if not isinstance(current, dict):
            raise TypeError(f"non-object before {'.'.join(path)}")
        current = current[key]
    return current


def set_nested(value: dict[str, object], path: tuple[str, ...], replacement: object) -> None:
    parent = nested(value, path[:-1])
    if not isinstance(parent, dict):
        raise TypeError(f"non-object parent for {'.'.join(path)}")
    parent[path[-1]] = replacement


def delete_nested(value: dict[str, object], path: tuple[str, ...]) -> None:
    parent = nested(value, path[:-1])
    if not isinstance(parent, dict):
        raise TypeError(f"non-object parent for {'.'.join(path)}")
    del parent[path[-1]]


def write_status(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def contradictory_value(
    path: tuple[str, ...],
    observed: object,
    canonical: dict[str, object],
) -> object:
    if type(observed) is bool:
        return not observed
    if type(observed) is int:
        return observed + 1
    if type(observed) is str:
        if path in STRING_MUTATIONS:
            return STRING_MUTATIONS[path]
        if path[0] == "current_bindings" and path[-1].endswith("_path"):
            paths = [canonical["current_bindings"][pair[0]] for pair in BINDING_PAIRS]
            return paths[(paths.index(observed) + 1) % len(paths)]
        if path[0] == "current_bindings" and path[-1].endswith("_sha256"):
            hashes = [canonical["current_bindings"][pair[1]] for pair in BINDING_PAIRS]
            return hashes[(hashes.index(observed) + 1) % len(hashes)]
        if path[-1].endswith("sha256"):
            return "0" * 64
        if path[-1] in {"reviewed_head", "reviewed_tree", "base_sha"}:
            return "0" * 40
        return observed + "_MUTATED"
    raise TypeError(f"unhandled status leaf type at {'.'.join(path)}")


class R11AG1OwnerApprovalReadinessTests(unittest.TestCase):
    def copy_repository(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        destination = Path(temporary.name) / "repository"
        shutil.copytree(
            ROOT,
            destination,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
        )
        # G1 is the immutable pre-approval readiness snapshot. Successor owner
        # records must be absent whenever its historical semantics are tested.
        shutil.rmtree(
            destination / "research/archive_inventory/r11a_approval",
            ignore_errors=True,
        )
        return temporary, destination

    def copied_status(self) -> tuple[Path, Path, bytes]:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        path = repository / STATUS_RELATIVE
        original = path.read_bytes()
        self.addCleanup(path.write_bytes, original)
        return repository, path, original

    def test_canonical_g1_readiness_passes_without_owner_or_runtime(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        validate(repository)

    def test_live_post_approval_tree_is_rejected_by_consumed_g1_gate(self) -> None:
        with self.assertRaisesRegex(G1ReadinessError, "canonical owner approval record"):
            validate(ROOT)

    def test_status_leaf_registry_is_complete(self) -> None:
        status = json.loads((ROOT / STATUS_RELATIVE).read_text(encoding="utf-8"))
        self.assertEqual(len(AUTHORITATIVE_STATUS_LEAVES), 75)
        self.assertEqual(
            set(STATUS_FIELD_CLASSIFICATION),
            set(AUTHORITATIVE_STATUS_LEAVES),
        )
        self.assertEqual(
            set(STATUS_FIELD_CLASSIFICATION.values()),
            {"A", "B", "C"},
        )
        self.assertEqual(STATUS_INFORMATIONAL_FIELDS, frozenset())
        self.assertEqual(
            status_leaf_paths(status),
            set(AUTHORITATIVE_STATUS_LEAVES),
        )

    def test_every_authoritative_status_leaf_rejects_contradiction(self) -> None:
        repository, path, original = self.copied_status()
        canonical = json.loads(original)
        for leaf in AUTHORITATIVE_STATUS_LEAVES:
            with self.subTest(leaf=".".join(leaf)):
                mutated = json.loads(original)
                set_nested(
                    mutated,
                    leaf,
                    contradictory_value(leaf, nested(mutated, leaf), canonical),
                )
                write_status(path, mutated)
                with self.assertRaises(G1ReadinessError):
                    validate(repository)

    def test_every_authoritative_status_leaf_rejects_missing_key(self) -> None:
        repository, path, original = self.copied_status()
        for leaf in AUTHORITATIVE_STATUS_LEAVES:
            with self.subTest(leaf=".".join(leaf)):
                mutated = json.loads(original)
                delete_nested(mutated, leaf)
                write_status(path, mutated)
                with self.assertRaises(G1ReadinessError):
                    validate(repository)

    def test_every_authoritative_status_leaf_rejects_null(self) -> None:
        repository, path, original = self.copied_status()
        for leaf in AUTHORITATIVE_STATUS_LEAVES:
            with self.subTest(leaf=".".join(leaf)):
                mutated = json.loads(original)
                set_nested(mutated, leaf, None)
                write_status(path, mutated)
                with self.assertRaises(G1ReadinessError):
                    validate(repository)

    def test_every_authoritative_status_leaf_rejects_wrong_type(self) -> None:
        repository, path, original = self.copied_status()
        for leaf in AUTHORITATIVE_STATUS_LEAVES:
            with self.subTest(leaf=".".join(leaf)):
                mutated = json.loads(original)
                observed = nested(mutated, leaf)
                if type(observed) is bool:
                    replacement: object = int(observed)
                elif type(observed) is int:
                    replacement = float(observed)
                elif type(observed) is str:
                    replacement = {"unexpected": observed}
                else:
                    self.fail(f"unhandled status leaf type at {'.'.join(leaf)}")
                set_nested(mutated, leaf, replacement)
                write_status(path, mutated)
                with self.assertRaises(G1ReadinessError):
                    validate(repository)

    def test_authoritative_status_objects_reject_unexpected_keys(self) -> None:
        repository, path, original = self.copied_status()
        for object_path in AUTHORITATIVE_STATUS_OBJECTS:
            with self.subTest(object_path=".".join(object_path) or "root"):
                mutated = json.loads(original)
                target = nested(mutated, object_path)
                self.assertIsInstance(target, dict)
                target["unexpected_authority"] = False
                write_status(path, mutated)
                with self.assertRaises(G1ReadinessError):
                    validate(repository)

    def test_authoritative_status_objects_reject_missing_or_wrong_type(self) -> None:
        repository, path, original = self.copied_status()
        for object_path in AUTHORITATIVE_STATUS_OBJECTS[1:]:
            with self.subTest(object_path=".".join(object_path), mutation="missing"):
                mutated = json.loads(original)
                delete_nested(mutated, object_path)
                write_status(path, mutated)
                with self.assertRaises(G1ReadinessError):
                    validate(repository)
            with self.subTest(object_path=".".join(object_path), mutation="list"):
                mutated = json.loads(original)
                set_nested(mutated, object_path, [])
                write_status(path, mutated)
                with self.assertRaises(G1ReadinessError):
                    validate(repository)

    def test_renamed_authoritative_status_key_is_rejected(self) -> None:
        repository, path, original = self.copied_status()
        mutated = json.loads(original)
        anchor = mutated["software_anchor"]
        anchor["review_outcome"] = anchor.pop("review_verdict")
        write_status(path, mutated)
        with self.assertRaises(G1ReadinessError):
            validate(repository)

    def test_duplicate_json_keys_are_rejected_at_every_authoritative_depth(
        self,
    ) -> None:
        repository, path, original = self.copied_status()
        duplicate_targets = (
            ("schema_version",),
            ("software_anchor", "review_id"),
            ("historical_r7_seal", "semantics"),
            ("current_bindings", "execution_envelope_path"),
            ("pricing", "current_official_binding"),
            (
                "iam_workflow_readiness",
                "permission_policy_exact_72_getobject_resources",
            ),
            ("owner_approval", "approval_id"),
            ("runtime_authority", "successor_role_created"),
            ("science_state", "empirical_root_cause"),
            ("trading_authorizations", "integration"),
        )
        canonical = json.loads(original)
        text = original.decode("utf-8")
        for leaf in duplicate_targets:
            with self.subTest(leaf=".".join(leaf)):
                indent = "  " * len(leaf)
                key = leaf[-1]
                needle = f'{indent}"{key}": {json.dumps(nested(canonical, leaf))}'
                self.assertEqual(text.count(needle), 1)
                duplicate = f'{needle},\n{indent}"{key}": null'
                path.write_text(text.replace(needle, duplicate, 1), encoding="utf-8")
                with self.assertRaisesRegex(G1ReadinessError, "duplicate JSON key"):
                    validate(repository)

    def test_every_binding_rejects_path_and_hash_substitution_independently(
        self,
    ) -> None:
        repository, path, original = self.copied_status()
        canonical = json.loads(original)
        bindings = canonical["current_bindings"]
        for index, (path_key, sha_key) in enumerate(BINDING_PAIRS):
            alternate_path_key, alternate_sha_key = BINDING_PAIRS[
                (index + 1) % len(BINDING_PAIRS)
            ]
            with self.subTest(binding=path_key, mutation="path-only"):
                mutated = json.loads(original)
                mutated["current_bindings"][path_key] = bindings[alternate_path_key]
                self.assertEqual(
                    mutated["current_bindings"][sha_key],
                    bindings[sha_key],
                )
                write_status(path, mutated)
                with self.assertRaises(G1ReadinessError):
                    validate(repository)
            with self.subTest(binding=sha_key, mutation="sha-only"):
                mutated = json.loads(original)
                mutated["current_bindings"][sha_key] = bindings[alternate_sha_key]
                self.assertEqual(
                    mutated["current_bindings"][path_key],
                    bindings[path_key],
                )
                write_status(path, mutated)
                with self.assertRaises(G1ReadinessError):
                    validate(repository)

    def test_status_root_array_and_null_are_rejected(self) -> None:
        repository, path, _ = self.copied_status()
        for invalid in ([], None):
            with self.subTest(invalid=invalid):
                write_status(path, invalid)
                with self.assertRaisesRegex(G1ReadinessError, "JSON root is not object"):
                    validate(repository)

    def test_seventy_third_object_is_rejected_by_join(self) -> None:
        selection = json.loads(
            (ROOT / "research/archive_inventory/r11/R11_72H_SELECTION.json").read_text(
                encoding="utf-8"
            )
        )
        prior = json.loads(
            (
                ROOT
                / "research/archive_inventory/r11_evidence/run-31436753081/r11-result.json"
            ).read_text(encoding="utf-8")
        )
        selection["exact_targets"].append(dict(selection["exact_targets"][-1]))
        with self.assertRaisesRegex(G1ReadinessError, "selection is not exact 72"):
            canonical_joined_rows(selection, prior)

    def test_terminal_classes_cannot_be_conflated_at_shared_rc21(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        path = (
            repository
            / "research/archive_inventory/r11a_g1/R11A_G1_EXECUTION_ENVELOPE.json"
        )
        value = json.loads(path.read_text(encoding="utf-8"))
        value["terminal_classes"][3]["terminal_class"] = (
            "R11A_V2_ARTIFACT_CAP_EXCEEDED_OR_FAIL_CLOSED_EARLY_STOP"
        )
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        mutated_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        with mock.patch.object(readiness, "ENVELOPE_SHA", mutated_sha):
            with self.assertRaisesRegex(
                G1ReadinessError,
                "exact terminal class mapping drift",
            ):
                readiness.validate(repository)

    def test_pricing_rate_tamper_is_rejected(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        path = (
            repository
            / "research/archive_inventory/r11a_g1/R11A_G1_PRICING_EUR_BINDING.json"
        )
        value = json.loads(path.read_text(encoding="utf-8"))
        value["pricing_sources"][1]["quoted_rate_usd"] = "0.113"
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(G1ReadinessError, "bound file hash drift"):
            validate(repository)

    def test_proposed_statement_tamper_is_rejected(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        path = (
            repository
            / "research/archive_inventory/r11a_g1/R11A_G1_OWNER_APPROVAL_STATEMENT.txt"
        )
        path.write_text(path.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")
        with self.assertRaisesRegex(G1ReadinessError, "bound file hash drift"):
            validate(repository)

    def test_canonical_approval_record_presence_is_rejected(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        path = (
            repository
            / "research/archive_inventory/r11a_approval"
            / "APPROVE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001.json"
        )
        path.parent.mkdir(parents=True)
        path.write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(G1ReadinessError, "canonical owner approval record"):
            validate(repository)

    def test_installed_runtime_workflow_is_rejected(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        path = (
            repository
            / ".github/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic.yml"
        )
        path.write_text("name: unauthorized installation\n", encoding="utf-8")
        with self.assertRaisesRegex(G1ReadinessError, "runtime workflow is installed"):
            validate(repository)

    def test_runtime_authority_flag_is_rejected(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        path = repository / "research/archive_inventory/r11a_g1/R11A_G1_STATUS.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["runtime_authority"]["aws_oidc"] = True
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(
            G1ReadinessError,
            "G1 status projection.runtime_authority.aws_oidc value mismatch",
        ):
            validate(repository)

    def test_approval_package_cannot_self_release_execution(self) -> None:
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        path = (
            repository
            / "research/archive_inventory/r11a_g1/R11A_G1_OWNER_APPROVAL_PACKAGE.json"
        )
        value = json.loads(path.read_text(encoding="utf-8"))
        value["frozen_authority_if_explicitly_approved"][
            "data_execution_authorized_by_approval_alone"
        ] = True
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(G1ReadinessError, "bound file hash drift"):
            validate(repository)


if __name__ == "__main__":
    unittest.main()
