from __future__ import annotations

import types
import unittest
import shutil
import subprocess
import sys
import tempfile
from contextlib import nullcontext
from pathlib import Path
from unittest import mock

from governance import _validate_r11a_runtime_binding_core_r7 as core
from governance import r11a_stage_common_r4 as common
from governance import validate_r11a_runtime_binding_r7 as subject
from governance.r11a_repository_provenance import RepositoryProvenanceError


COMMIT = "a" * 40
DIGEST = "b" * 64
ACTIVATION_DIGEST = "c" * 64
BINDING_DIGEST = "d" * 64
EVIDENCE_DIGEST = "e" * 64
ROOT = Path("/tmp/r11a-runtime-binding-review-test")
PROJECT_ROOT = Path(__file__).absolute().parents[1]


def _identity(gate_id: str, ordinal: int = 1) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        gate_id=gate_id,
        review_id=ordinal,
        evidence_sha256=f"{ordinal:064x}",
    )


def _closed(keys: frozenset[str]) -> dict[str, bool]:
    return {key: False for key in keys}


class RuntimeBindingCoreV2Tests(unittest.TestCase):
    def binding(self) -> dict[str, object]:
        return {
            "schema_version": "2.0",
            "binding_id": "HL-ARCHIVE-R11A-RUNTIME-BINDING-R7-001",
            "diagnostic_id": common.DIAGNOSTIC_ID,
            "implementation_id": core.IMPLEMENTATION_ID,
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
            "activation_review_evidence_sha256": DIGEST,
            "bound_files": {
                relative: DIGEST for relative in core.REQUIRED_BOUND_PATHS
            },
            "runtime_authority": dict(core.EXPECTED_RUNTIME_AUTHORITY),
            "science_state": dict(core.EXPECTED_SCIENCE_STATE),
            "downstream_authorizations": _closed(common.DOWNSTREAM_AUTHORITY_KEYS),
            "trading_authorizations": _closed(common.TRADING_AUTHORITY_KEYS),
            "r11_closed": False,
            "r12_ready": False,
        }

    def validate_core(self, binding: dict[str, object]) -> tuple[dict[str, object], list[object], mock.Mock]:
        lineage: list[object] = []
        gate = mock.Mock()

        def activation(
            root: Path,
            *,
            permitted_successor_paths: frozenset[str],
            _review_lineage: list[object],
        ) -> dict[str, object]:
            self.assertIs(_review_lineage, lineage)
            self.assertIn(
                common.REVIEW_EVIDENCE_PATHS[core.ACTIVATION_REVIEW_GATE],
                permitted_successor_paths,
            )
            self.assertIn(
                common.REVIEW_EVIDENCE_PATHS[core.RUNTIME_BINDING_REVIEW_GATE],
                permitted_successor_paths,
            )
            _review_lineage.extend(
                _identity(gate_id, ordinal)
                for ordinal, gate_id in enumerate(common.REVIEW_GATE_IDS[:9], start=1)
            )
            return {"single_use_window_start_utc": "2026-08-26T00:00:00Z"}

        def consume_gate(*args: object, **kwargs: object) -> object:
            gate(*args, **kwargs)
            mapping = args[1]
            field = args[2]
            core.require_sha256(mapping[field], field)
            observed = kwargs["lineage"]
            self.assertIs(observed, lineage)
            self.assertEqual(
                tuple(identity.gate_id for identity in observed),
                common.REVIEW_GATE_IDS[:9],
            )
            identity = _identity(core.ACTIVATION_REVIEW_GATE, 10)
            observed.append(identity)
            return identity

        with (
            mock.patch.object(core, "validate_activation", side_effect=activation),
            mock.patch.object(core, "require_absent"),
            mock.patch.object(core, "stage_load", return_value=binding),
            mock.patch.object(core, "stage_sha256", return_value=DIGEST),
            mock.patch.object(core, "require_gate_review", side_effect=consume_gate),
            mock.patch.object(core, "read_bytes", return_value=b"same workflow\n"),
            mock.patch.object(core, "pricing_projection"),
        ):
            observed = core.validate_binding(root=ROOT, _review_lineage=lineage)
        return observed, lineage, gate

    def test_schema_v2_consumes_exact_activation_review_and_full_lineage(self) -> None:
        binding = self.binding()
        observed, lineage, gate = self.validate_core(binding)
        self.assertIs(observed, binding)
        self.assertEqual(
            tuple(identity.gate_id for identity in lineage),
            common.REVIEW_GATE_IDS[:10],
        )
        arguments, keywords = gate.call_args
        self.assertEqual(arguments[:4], (ROOT, binding, "activation_review_evidence_sha256", core.ACTIVATION_REVIEW_GATE))
        self.assertEqual(
            keywords["target_files"],
            {common.ACTIVATION_RELATIVE: DIGEST},
        )
        self.assertEqual(
            keywords["predecessor_files"],
            {
                common.RELEASE_RELATIVE: DIGEST,
                common.RELEASE_DIGEST_RELATIVE: DIGEST,
            },
        )

    def test_old_self_claim_fields_and_own_commit_are_rejected(self) -> None:
        binding = self.binding()
        binding.pop("activation_review_evidence_sha256")
        binding.update(
            {
                "canonical_commit": COMMIT,
                "activation_review_completed": True,
                "activation_review_id": 9,
                "activation_review_event": "COMMENTED",
                "activation_review_verdict": "GREEN",
                "activation_reviewed_head": "9" * 40,
                "activation_reviewed_tree": "8" * 40,
            }
        )
        with self.assertRaisesRegex(core.RuntimeBindingError, "key set drift"):
            self.validate_core(binding)

    def test_activation_review_digest_cannot_be_omitted_or_mistyped(self) -> None:
        for mutation in (None, 7, True, "A" * 64):
            with self.subTest(mutation=mutation):
                binding = self.binding()
                if mutation is None:
                    binding.pop("activation_review_evidence_sha256")
                    expected = "key set drift"
                else:
                    binding["activation_review_evidence_sha256"] = mutation
                    expected = "lowercase SHA-256"
                with self.assertRaisesRegex(core.RuntimeBindingError, expected):
                    self.validate_core(binding)


class ReviewedRuntimeBindingWrapperTests(unittest.TestCase):
    def _validate(
        self,
        *,
        evidence_side_effect: object | None = None,
        digest_overrides: dict[str, str] | None = None,
    ) -> tuple[dict[str, object], mock.Mock]:
        binding = {"binding_id": "HL-ARCHIVE-R11A-RUNTIME-BINDING-R7-001"}
        snapshot_root = ROOT / "authenticated-snapshot"
        snapshot = subject.AuthenticatedRepository(
            snapshot_root=snapshot_root,
            head=COMMIT,
            tree="f" * 40,
            index_version=2,
            entries=(),
            _source_root=ROOT,
        )
        digest_overrides = {} if digest_overrides is None else digest_overrides

        def validate_binding(*, root: Path, _review_lineage: list[object]) -> dict[str, object]:
            self.assertEqual(root, snapshot_root)
            _review_lineage.extend(
                _identity(gate_id, ordinal)
                for ordinal, gate_id in enumerate(common.REVIEW_GATE_IDS[:10], start=1)
            )
            return binding

        def digest(root: Path, relative: str) -> str:
            self.assertEqual(root, snapshot_root)
            defaults = {
                common.REVIEW_EVIDENCE_PATHS[core.RUNTIME_BINDING_REVIEW_GATE]: EVIDENCE_DIGEST,
                common.BINDING_RELATIVE: BINDING_DIGEST,
                common.ACTIVATION_RELATIVE: ACTIVATION_DIGEST,
            }
            return digest_overrides.get(relative, defaults[relative])

        evidence = mock.Mock()
        if evidence_side_effect is None:
            evidence.return_value = _identity(core.RUNTIME_BINDING_REVIEW_GATE, 11)
        else:
            evidence.side_effect = evidence_side_effect
        with (
            mock.patch.object(
                subject,
                "open_authenticated_repository",
                return_value=nullcontext(snapshot),
            ) as provenance,
            mock.patch.object(subject._core, "validate_binding", side_effect=validate_binding),
            mock.patch.object(subject, "stage_sha256", side_effect=digest),
            mock.patch.object(subject, "authenticated_repository_checkpoint"),
            mock.patch.object(common._review_evidence, "validate_gate_evidence", evidence),
        ):
            observed = subject.validate(COMMIT, 1, root=ROOT)
        provenance.assert_called_once_with(ROOT, expected_head=COMMIT)
        return observed, evidence

    def test_wrapper_requires_distinct_runtime_review_of_exact_binding(self) -> None:
        observed, evidence = self._validate()
        self.assertEqual(observed["binding_id"], "HL-ARCHIVE-R11A-RUNTIME-BINDING-R7-001")
        arguments, keywords = evidence.call_args
        self.assertEqual(arguments[:2], (ROOT / "authenticated-snapshot", core.RUNTIME_BINDING_REVIEW_GATE))
        self.assertEqual(keywords["expected_evidence_sha256"], EVIDENCE_DIGEST)
        self.assertEqual(
            keywords["expected_target_files"],
            {
                common.BINDING_RELATIVE: BINDING_DIGEST,
                common.REVIEW_EVIDENCE_PATHS[core.ACTIVATION_REVIEW_GATE]: (
                    f"{10:064x}"
                ),
            },
        )
        self.assertEqual(
            keywords["expected_predecessor_files"],
            {
                common.ACTIVATION_RELATIVE: ACTIVATION_DIGEST,
                common.REVIEW_EVIDENCE_PATHS[
                    common.REVIEW_GATE_IDS[8]
                ]: f"{9:064x}",
            },
        )
        self.assertEqual(
            tuple(identity.gate_id for identity in keywords["consumed"]),
            common.REVIEW_GATE_IDS[:10],
        )

    def test_missing_wrong_or_reused_runtime_review_fails_closed(self) -> None:
        for message in (
            "review evidence is absent",
            "selected review belongs to the wrong head",
            "review ID reused across governance gates",
        ):
            with self.subTest(message=message):
                with self.assertRaisesRegex(subject.RuntimeBindingError, message):
                    self._validate(evidence_side_effect=AssertionError(message))

    def test_binding_or_activation_drift_after_review_fails_closed(self) -> None:
        def exact_evidence(*args: object, **kwargs: object) -> object:
            if kwargs["expected_target_files"] != {
                common.BINDING_RELATIVE: BINDING_DIGEST,
                common.REVIEW_EVIDENCE_PATHS[core.ACTIVATION_REVIEW_GATE]: (
                    f"{10:064x}"
                ),
            }:
                raise AssertionError("reviewed target file set or digest drift")
            if kwargs["expected_predecessor_files"] != {
                common.ACTIVATION_RELATIVE: ACTIVATION_DIGEST,
                common.REVIEW_EVIDENCE_PATHS[
                    common.REVIEW_GATE_IDS[8]
                ]: f"{9:064x}",
            }:
                raise AssertionError("reviewed predecessor file set or digest drift")
            return _identity(core.RUNTIME_BINDING_REVIEW_GATE, 11)

        mutations = (
            (common.BINDING_RELATIVE, "0" * 64, "reviewed target"),
            (common.ACTIVATION_RELATIVE, "1" * 64, "reviewed predecessor"),
        )
        for relative, digest, expected in mutations:
            with self.subTest(relative=relative):
                with self.assertRaisesRegex(subject.RuntimeBindingError, expected):
                    self._validate(
                        evidence_side_effect=exact_evidence,
                        digest_overrides={relative: digest},
                    )

    def test_dispatch_attempt_and_physical_head_are_outer_fail_closed_gates(self) -> None:
        with mock.patch.object(subject, "open_authenticated_repository") as provenance:
            with self.assertRaisesRegex(subject.RuntimeBindingError, "attempt one"):
                subject.validate(COMMIT, 2, root=ROOT)
            provenance.assert_not_called()

        with (
            mock.patch.object(
                subject,
                "open_authenticated_repository",
                side_effect=RepositoryProvenanceError("HEAD identity drift"),
            ),
            mock.patch.object(subject._core, "validate_binding") as binding,
        ):
            with self.assertRaisesRegex(subject.RuntimeBindingError, "HEAD identity drift"):
                subject.validate(COMMIT, 1, root=ROOT)
            binding.assert_not_called()

    def test_runtime_consumer_never_reads_post_authentication_source_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "repository"
            shutil.copytree(
                PROJECT_ROOT,
                source,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
            )
            for command in (
                [sys.executable, "-B", "governance/regenerate_manifest.py", "--write"],
                ["git", "config", "user.name", "R11A Snapshot Test"],
                ["git", "config", "user.email", "r11a-snapshot@example.invalid"],
                ["git", "add", "--all"],
                ["git", "commit", "-q", "--allow-empty", "-m", "snapshot routing fixture"],
            ):
                subprocess.run(
                    command,
                    cwd=source,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=source,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            ).stdout.strip().decode("ascii")
            original = (source / "README.md").read_bytes()
            observed_roots: list[Path] = []

            def validate_binding(
                *,
                root: Path,
                _review_lineage: list[object],
            ) -> dict[str, object]:
                observed_roots.append(root)
                self.assertNotEqual(root, source)
                self.assertEqual((root / "README.md").read_bytes(), original)
                (source / "README.md").write_bytes(b"late runtime source mutation\n")
                self.assertEqual((root / "README.md").read_bytes(), original)
                _review_lineage.extend(
                    _identity(gate_id, ordinal)
                    for ordinal, gate_id in enumerate(
                        common.REVIEW_GATE_IDS[:10],
                        start=1,
                    )
                )
                return {"binding_id": "snapshot-only"}

            def consume_final(
                _root: Path,
                _record: object,
                _field: str,
                gate_id: str,
                *,
                lineage: list[object],
                **_kwargs: object,
            ) -> object:
                identity = _identity(gate_id, 11)
                lineage.append(identity)
                return identity

            with (
                mock.patch.object(subject._core, "validate_binding", side_effect=validate_binding),
                mock.patch.object(subject, "stage_sha256", return_value="e" * 64),
                mock.patch.object(subject, "require_gate_review", side_effect=consume_final),
                self.assertRaisesRegex(
                    subject.RuntimeBindingError,
                    "working-tree byte drift|worktree identity drift",
                ),
            ):
                subject.validate(head, 1, root=source)
            self.assertEqual(len(observed_roots), 1)


if __name__ == "__main__":
    unittest.main()
