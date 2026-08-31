from __future__ import annotations

import copy
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from governance import r11a_workflow_identity as identity


ROOT = Path(__file__).resolve().parents[1]
STAGE_KEYS = (
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


def canonical_approval_record() -> dict[str, object]:
    return {
        "owner_approval_present": True,
        "canonical_approval_record_present": True,
        "execution_authorized_by_this_approval": False,
        "current_authority": {
            "iam_role_creation": False,
            "workflow_installation": False,
            "runtime_activation": False,
        },
    }


def live_stage_state(**overrides: bool) -> dict[str, bool]:
    state = {key: False for key in STAGE_KEYS}
    for key, value in overrides.items():
        if key not in state:  # pragma: no cover - fixed test inputs
            raise ValueError(key)
        state[key] = value
    return state


class R11AWorkflowIdentityTests(unittest.TestCase):
    def fixture(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        repository = Path(temporary.name) / "repository"
        candidate_source = ROOT / identity.CANDIDATE_WORKFLOW_RELATIVE
        candidate_target = repository / identity.CANDIDATE_WORKFLOW_RELATIVE
        candidate_target.parent.mkdir(parents=True)
        shutil.copy2(candidate_source, candidate_target)
        workflow_target = repository / ".github/workflows"
        shutil.copytree(ROOT / ".github/workflows", workflow_target)
        shutil.copy2(ROOT / identity.PROJECT_STATE_RELATIVE, repository / identity.PROJECT_STATE_RELATIVE)
        return temporary, repository

    def validate_state(
        self,
        repository: Path,
        record: dict[str, object] | None = None,
        *,
        stage_state: dict[str, bool] | None = None,
    ) -> dict[str, str]:
        return identity.validate_post_g2_project_state(
            repository,
            approval_id="APPROVE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001",
            approval_text_sha256=(
                "16f9f2c31ff90952033251d917884b1ca55771511e82e4b813414dc1a3f807d3"
            ),
            approval_record=canonical_approval_record() if record is None else record,
            live_stage_state=(
                live_stage_state() if stage_state is None else stage_state
            ),
        )

    def replace_state(self, repository: Path, old: str, new: str) -> None:
        path = repository / identity.PROJECT_STATE_RELATIVE
        text = path.read_text(encoding="utf-8")
        self.assertEqual(text.count(old), 1)
        path.write_text(text.replace(old, new), encoding="utf-8")

    def write_stage_state(
        self,
        repository: Path,
        stage_state: dict[str, bool],
    ) -> None:
        path = repository / identity.PROJECT_STATE_RELATIVE
        text = path.read_text(encoding="utf-8")
        self.assertEqual(tuple(stage_state), STAGE_KEYS)
        for key, value in stage_state.items():
            old = f"{key} = false\n"
            self.assertEqual(text.count(old), 1)
            if value:
                text = text.replace(old, f"{key} = true\n")
        path.write_text(text, encoding="utf-8")

    def test_exact_preinstall_and_installed_inventory_states(self) -> None:
        temporary, repository = self.fixture()
        self.addCleanup(temporary.cleanup)
        observed = identity.validate_workflow_identity_inventory(
            repository,
            canonical_installed=False,
        )
        self.assertEqual(observed["preinstall_workflow_count"], 24)
        self.assertEqual(
            observed["preinstall_workflow_inventory_sha256"],
            identity.PREINSTALL_WORKFLOW_INVENTORY_SHA256,
        )
        self.assertEqual(observed["canonical_installed_count"], 0)

        candidate = repository / identity.CANDIDATE_WORKFLOW_RELATIVE
        installed = repository / identity.CANONICAL_INSTALLED_WORKFLOW_RELATIVE
        shutil.copy2(candidate, installed)
        installed_observed = identity.validate_workflow_identity_inventory(
            repository,
            canonical_installed=True,
        )
        self.assertEqual(installed_observed["preinstall_workflow_count"], 24)
        self.assertEqual(installed_observed["canonical_installed_count"], 1)
        with self.assertRaisesRegex(
            identity.R11AWorkflowIdentityError,
            "installed before its installation stage",
        ):
            identity.validate_workflow_identity_inventory(
                repository,
                canonical_installed=False,
            )

        installed.unlink()
        with self.assertRaisesRegex(
            identity.R11AWorkflowIdentityError,
            "presence does not match stage",
        ):
            identity.validate_workflow_identity_inventory(
                repository,
                canonical_installed=True,
            )

    def test_alternate_identity_and_byte_variants_fail_closed(self) -> None:
        candidate = (ROOT / identity.CANDIDATE_WORKFLOW_RELATIVE).read_bytes()
        cases = (
            (
                "same_name",
                "alternate.yml",
                b"name: Hyperliquid Archive R11A Identity Boundary Diagnostic\non: []\n",
            ),
            (
                "case_variant",
                "alternate.yml",
                b"name: HYPERLIQUID ARCHIVE R11A IDENTITY BOUNDARY DIAGNOSTIC\non: []\n",
            ),
            (
                "whitespace_variant",
                "alternate.yml",
                b"name: Hyperliquid  Archive R11A Identity Boundary Diagnostic   \non: []\n",
            ),
            (
                "punctuation_variant",
                "alternate.yml",
                b"name: Hyperliquid-Archive-R11A-Identity-Boundary-Diagnostic\non: []\n",
            ),
            (
                "unicode_variant",
                "alternate.yml",
                "name: Hyperliquid Archive \uff3211\uff21 Identity Boundary Diagnostic\non: []\n".encode(),
            ),
            ("copied_candidate", "candidate-copy.yml", candidate),
            (
                "equivalent_trigger",
                "alternate.yml",
                b"name: unrelated\non:\n  workflow_dispatch:\npermissions:\n  id-token: write\n",
            ),
            (
                "same_identity_with_secret",
                "alternate.yml",
                b"name: Hyperliquid Archive R11A Identity Boundary Diagnostic\n"
                b"on:\n  workflow_dispatch:\njobs:\n  run:\n    steps:\n"
                b"      - run: echo ${{ secrets.R11A_KEY }}\n",
            ),
        )
        for label, filename, raw in cases:
            with self.subTest(label=label):
                temporary, repository = self.fixture()
                try:
                    (repository / ".github/workflows" / filename).write_bytes(raw)
                    with self.assertRaises(identity.R11AWorkflowIdentityError):
                        identity.validate_workflow_identity_inventory(
                            repository,
                            canonical_installed=False,
                        )
                finally:
                    temporary.cleanup()

    def test_workflow_path_and_filesystem_aliases_fail_closed(self) -> None:
        cases = (
            ("case_filename", "R11A-ALIAS.YML", "file"),
            ("unicode_filename", "r11a-\uff41lias.yml", "file"),
            ("trailing_space", "r11a-alias.yml ", "file"),
            ("alternate_extension", "r11a-alias.txt", "file"),
            ("directory", "nested.yml", "directory"),
            ("symlink", "alias.yml", "symlink"),
            ("hardlink", "alias.yml", "hardlink"),
            ("fifo", "alias.yml", "fifo"),
        )
        for label, filename, kind in cases:
            with self.subTest(label=label):
                temporary, repository = self.fixture()
                try:
                    workflows = repository / ".github/workflows"
                    target = workflows / filename
                    if kind == "file":
                        target.write_text("name: unrelated\non: []\n", encoding="utf-8")
                    elif kind == "directory":
                        target.mkdir()
                    elif kind == "symlink":
                        target.symlink_to(workflows / "ci.yml")
                    elif kind == "hardlink":
                        os.link(workflows / "ci.yml", target)
                    elif kind == "fifo":
                        os.mkfifo(target)
                    else:  # pragma: no cover - fixed test table
                        self.fail(kind)
                    with self.assertRaises(identity.R11AWorkflowIdentityError):
                        identity.validate_workflow_identity_inventory(
                            repository,
                            canonical_installed=False,
                        )
                finally:
                    temporary.cleanup()

    def test_canonical_installed_workflow_is_byte_exact(self) -> None:
        temporary, repository = self.fixture()
        self.addCleanup(temporary.cleanup)
        candidate = repository / identity.CANDIDATE_WORKFLOW_RELATIVE
        installed = repository / identity.CANONICAL_INSTALLED_WORKFLOW_RELATIVE
        shutil.copy2(candidate, installed)
        raw = installed.read_bytes()
        mutations = (
            raw.replace(
                b"name: Hyperliquid Archive R11A Identity Boundary Diagnostic",
                b"name: hyperliquid archive r11a identity boundary diagnostic",
                1,
            ),
            raw + b"\n# widened\npermissions:\n  contents: write\n",
            raw + b"\n# secret\n# ${{ secrets.R11A_KEY }}\n",
        )
        for mutation in mutations:
            with self.subTest(mutation_size=len(mutation)):
                installed.write_bytes(mutation)
                with self.assertRaisesRegex(
                    identity.R11AWorkflowIdentityError,
                    "differs from owner-approved candidate",
                ):
                    identity.validate_workflow_identity_inventory(
                        repository,
                        canonical_installed=True,
                    )
        installed.write_bytes(raw)
        identity.validate_workflow_identity_inventory(
            repository,
            canonical_installed=True,
        )

    def test_live_post_g2_project_state_is_consistent(self) -> None:
        temporary, repository = self.fixture()
        self.addCleanup(temporary.cleanup)
        state = self.validate_state(repository)
        self.assertEqual(state["r11a_owner_approval_present"], "true")
        self.assertEqual(
            state["r11a_owner_approval_record_review_complete"],
            "true",
        )

    def test_live_stage_state_accepts_only_monotonic_prefixes(self) -> None:
        prefixes: list[tuple[str, dict[str, bool]]] = []
        state = live_stage_state()
        prefixes.append(("g2_only", state.copy()))
        for label, keys in (
            (
                "role_attestation",
                (
                    "r11a_successor_role_created",
                    "r11a_successor_role_attestation_present",
                ),
            ),
            ("sts_preflight", ("r11a_sts_preflight",)),
            ("workflow_installation", ("r11a_workflow_installed",)),
            (
                "execution_release",
                ("r11a_release_present", "r11a_runtime_release"),
            ),
            ("activation", ("r11a_runtime_activation",)),
            ("runtime_binding", ("r11a_runtime_binding",)),
            ("runtime_binding_review", ("r11a_runtime_binding_review",)),
        ):
            for key in keys:
                state[key] = True
            prefixes.append((label, state.copy()))

        for label, projection in prefixes:
            with self.subTest(label=label):
                temporary, repository = self.fixture()
                try:
                    self.write_stage_state(repository, projection)
                    observed = self.validate_state(
                        repository,
                        stage_state=projection,
                    )
                    self.assertEqual(
                        {key: observed[key] for key in STAGE_KEYS},
                        {
                            key: "true" if value else "false"
                            for key, value in projection.items()
                        },
                    )
                finally:
                    temporary.cleanup()

    def test_live_stage_state_rejects_skips_and_pair_contradictions(self) -> None:
        cases = (
            (
                "created_without_attestation",
                live_stage_state(r11a_successor_role_created=True),
                "role creation and role-attestation state contradict",
            ),
            (
                "attestation_without_created",
                live_stage_state(r11a_successor_role_attestation_present=True),
                "role creation and role-attestation state contradict",
            ),
            (
                "sts_without_role",
                live_stage_state(r11a_sts_preflight=True),
                "skips an immediate predecessor",
            ),
            (
                "workflow_without_sts",
                live_stage_state(r11a_workflow_installed=True),
                "skips an immediate predecessor",
            ),
            (
                "release_presence_without_release",
                live_stage_state(r11a_release_present=True),
                "release-present and runtime-release state contradict",
            ),
            (
                "release_without_presence",
                live_stage_state(r11a_runtime_release=True),
                "release-present and runtime-release state contradict",
            ),
            (
                "release_without_workflow",
                live_stage_state(
                    r11a_release_present=True,
                    r11a_runtime_release=True,
                ),
                "skips an immediate predecessor",
            ),
            (
                "activation_without_release",
                live_stage_state(r11a_runtime_activation=True),
                "skips an immediate predecessor",
            ),
            (
                "binding_without_activation",
                live_stage_state(r11a_runtime_binding=True),
                "skips an immediate predecessor",
            ),
            (
                "binding_review_without_binding",
                live_stage_state(r11a_runtime_binding_review=True),
                "skips an immediate predecessor",
            ),
        )
        for label, projection, message in cases:
            with self.subTest(label=label):
                temporary, repository = self.fixture()
                try:
                    self.write_stage_state(repository, projection)
                    with self.assertRaisesRegex(identity.R11AProjectStateError, message):
                        self.validate_state(repository, stage_state=projection)
                finally:
                    temporary.cleanup()

    def test_live_stage_projection_shape_and_types_are_exact(self) -> None:
        canonical = live_stage_state()
        cases: tuple[tuple[str, dict[str, object]], ...] = (
            ("missing", {key: False for key in STAGE_KEYS[:-1]}),
            ("extra", {**canonical, "r11a_future_alias": False}),
            ("reordered", dict(reversed(tuple(canonical.items())))),
            ("integer", {**canonical, "r11a_sts_preflight": 0}),
            ("string", {**canonical, "r11a_sts_preflight": "false"}),
        )
        for label, projection in cases:
            with self.subTest(label=label):
                temporary, repository = self.fixture()
                try:
                    with self.assertRaises(identity.R11AProjectStateError):
                        self.validate_state(  # type: ignore[arg-type]
                            repository,
                            stage_state=projection,
                        )
                finally:
                    temporary.cleanup()

    def test_workflow_stage_requires_matching_physical_path_state(self) -> None:
        temporary, repository = self.fixture()
        self.addCleanup(temporary.cleanup)
        preinstall = live_stage_state()
        self.validate_state(repository, stage_state=preinstall)
        identity.validate_workflow_identity_inventory(
            repository,
            canonical_installed=False,
        )
        with self.assertRaisesRegex(
            identity.R11AWorkflowIdentityError,
            "presence does not match stage",
        ):
            identity.validate_workflow_identity_inventory(
                repository,
                canonical_installed=True,
            )

        installed_state = live_stage_state(
            r11a_successor_role_created=True,
            r11a_successor_role_attestation_present=True,
            r11a_sts_preflight=True,
            r11a_workflow_installed=True,
        )
        self.write_stage_state(repository, installed_state)
        self.validate_state(repository, stage_state=installed_state)
        candidate = repository / identity.CANDIDATE_WORKFLOW_RELATIVE
        installed = repository / identity.CANONICAL_INSTALLED_WORKFLOW_RELATIVE
        shutil.copy2(candidate, installed)
        identity.validate_workflow_identity_inventory(
            repository,
            canonical_installed=True,
        )
        with self.assertRaisesRegex(
            identity.R11AWorkflowIdentityError,
            "installed before its installation stage",
        ):
            identity.validate_workflow_identity_inventory(
                repository,
                canonical_installed=False,
            )

    def test_project_state_missing_duplicate_malformed_and_wrong_values_fail(self) -> None:
        cases = (
            (
                "review_false",
                "r11a_owner_approval_record_review_complete = true\n",
                "r11a_owner_approval_record_review_complete = false\n",
            ),
            (
                "owner_absent",
                "r11a_owner_approval_present = true\n",
                "r11a_owner_approval_present = false\n",
            ),
            (
                "wrong_id",
                "r11a_owner_approval_id = APPROVE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001\n",
                "r11a_owner_approval_id = WRONG\n",
            ),
            (
                "wrong_hash",
                "r11a_owner_approval_text_sha256 = 16f9f2c31ff90952033251d917884b1ca55771511e82e4b813414dc1a3f807d3\n",
                "r11a_owner_approval_text_sha256 = " + "0" * 64 + "\n",
            ),
            (
                "missing",
                "r11a_owner_approval_record_review_complete = true\n",
                "",
            ),
            (
                "malformed",
                "r11a_owner_approval_record_review_complete = true\n",
                "r11a_owner_approval_record_review_complete=true\n",
            ),
            (
                "duplicate",
                "r11a_owner_approval_record_review_complete = true\n",
                "r11a_owner_approval_record_review_complete = true\n"
                "r11a_owner_approval_record_review_complete = true\n",
            ),
        )
        for label, old, new in cases:
            with self.subTest(label=label):
                temporary, repository = self.fixture()
                try:
                    self.replace_state(repository, old, new)
                    with self.assertRaises(identity.R11AProjectStateError):
                        self.validate_state(repository)
                finally:
                    temporary.cleanup()

    def test_approval_record_state_contradictions_fail(self) -> None:
        cases = (
            ("owner_approval_present", False),
            ("canonical_approval_record_present", False),
            ("execution_authorized_by_this_approval", True),
        )
        for key, replacement in cases:
            with self.subTest(key=key):
                temporary, repository = self.fixture()
                try:
                    record = canonical_approval_record()
                    record[key] = replacement
                    with self.assertRaises(identity.R11AProjectStateError):
                        self.validate_state(repository, record)
                finally:
                    temporary.cleanup()

        temporary, repository = self.fixture()
        self.addCleanup(temporary.cleanup)
        record = copy.deepcopy(canonical_approval_record())
        authority = record["current_authority"]
        self.assertIsInstance(authority, dict)
        authority["workflow_installation"] = True
        with self.assertRaisesRegex(
            identity.R11AProjectStateError,
            "current authority is not fully closed",
        ):
            self.validate_state(repository, record)


if __name__ == "__main__":
    unittest.main()
