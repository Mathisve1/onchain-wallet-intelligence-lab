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
    canonical_joined_rows,
    validate,
)

ROOT = Path(__file__).resolve().parents[1]


class R11AG1OwnerApprovalReadinessTests(unittest.TestCase):
    def copy_repository(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        destination = Path(temporary.name) / "repository"
        shutil.copytree(
            ROOT,
            destination,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
        )
        return temporary, destination

    def test_canonical_g1_readiness_passes_without_owner_or_runtime(self) -> None:
        validate(ROOT)

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
        with self.assertRaisesRegex(G1ReadinessError, "status runtime authority"):
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
