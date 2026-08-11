from __future__ import annotations

import base64
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from governance import validate_r11_execution_evidence as validator

ROOT = Path(__file__).resolve().parents[1]


class R11ExecutionEvidenceTests(unittest.TestCase):
    def fixture_root(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        source = ROOT / "research/archive_inventory"
        target = root / "research/archive_inventory"
        for relative in ("r11_evidence", "r11_runtime", "r11"):
            shutil.copytree(source / relative, target / relative)
        return temporary, root

    def test_dedicated_validator_passes(self) -> None:
        done = subprocess.run(
            [sys.executable, "governance/validate_r11_execution_evidence.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("R11_EXECUTION_EVIDENCE_VALID_UNRESOLVED", done.stdout)

    def test_artifact_byte_mutation_fails_closed(self) -> None:
        temporary, root = self.fixture_root()
        self.addCleanup(temporary.cleanup)
        path = root / validator.RUN / "artifact/r11-72h-persistence-31436753081.zip.b64"
        data = bytearray(base64.b64decode(b"".join(path.read_bytes().split())))
        data[len(data) // 2] ^= 1
        path.write_bytes(base64.encodebytes(bytes(data)))
        with self.assertRaises(validator.R11EvidenceError):
            validator.validate(root)

    def test_missing_raw_entry_fails_closed(self) -> None:
        temporary, root = self.fixture_root()
        self.addCleanup(temporary.cleanup)
        (root / validator.RUN / "r11.rc").unlink()
        with self.assertRaises((validator.R11EvidenceError, FileNotFoundError)):
            validator.validate(root)

    def test_extra_zip_entry_fails_closed(self) -> None:
        temporary, root = self.fixture_root()
        self.addCleanup(temporary.cleanup)
        path = root / validator.RUN / "artifact/r11-72h-persistence-31436753081.zip.b64"
        original = base64.b64decode(b"".join(path.read_bytes().split()))
        source = zipfile.ZipFile(io.BytesIO(original), "r")
        rendered = io.BytesIO()
        with zipfile.ZipFile(rendered, "w", compression=zipfile.ZIP_DEFLATED) as target:
            for info in source.infolist():
                target.writestr(info.filename, source.read(info.filename))
            target.writestr("unexpected.txt", b"not preregistered")
        source.close()
        path.write_bytes(base64.encodebytes(rendered.getvalue()))
        with self.assertRaises(validator.R11EvidenceError):
            validator.validate(root)

    def test_internal_ledger_mismatch_fails_closed(self) -> None:
        temporary, root = self.fixture_root()
        self.addCleanup(temporary.cleanup)
        path = root / validator.RUN / "R11_FILES.sha256"
        rows = path.read_text().splitlines()
        rows[0] = "0" * 64 + rows[0][64:]
        path.write_text("\n".join(rows) + "\n")
        with self.assertRaises(validator.R11EvidenceError):
            validator.validate(root)

    def test_nonempty_feature_output_fails_closed(self) -> None:
        temporary, root = self.fixture_root()
        self.addCleanup(temporary.cleanup)
        (root / validator.RUN / "r11-wallet-features.ndjson").write_bytes(b"{}\n")
        with self.assertRaises(validator.R11EvidenceError):
            validator.validate(root)

    def test_dispatch_attempt_drift_fails_closed(self) -> None:
        temporary, root = self.fixture_root()
        self.addCleanup(temporary.cleanup)
        path = root / validator.RUN / "r11-context.json"
        value = json.loads(path.read_text())
        value["workflow_run_attempt"] = 2
        value["dispatch_sha"] = "0" * 40
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(validator.R11EvidenceError):
            validator.validate(root)

    def test_consumption_run_identity_mutation_fails_closed(self) -> None:
        temporary, root = self.fixture_root()
        self.addCleanup(temporary.cleanup)
        path = root / validator.CONSUMPTION
        value = json.loads(path.read_text())
        value["workflow_run_id"] += 1
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(validator.R11EvidenceError):
            validator.validate(root)

    def test_attestation_claim_proven_value_mutation_fails_closed(self) -> None:
        temporary, root = self.fixture_root()
        self.addCleanup(temporary.cleanup)
        path = root / validator.EVIDENCE / "HL-ARCHIVE-R11-72H-PERSISTENCE-SCALING-001-ATTESTATION.json"
        value = json.loads(path.read_text())
        value["claims_proven"]["all_72_getobject_requests_succeeded"] = False
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(validator.R11EvidenceError):
            validator.validate(root)

    def test_attestation_exact_summary_success_count_mutation_fails_closed(self) -> None:
        temporary, root = self.fixture_root()
        self.addCleanup(temporary.cleanup)
        path = root / validator.EVIDENCE / "HL-ARCHIVE-R11-72H-PERSISTENCE-SCALING-001-ATTESTATION.json"
        value = json.loads(path.read_text())
        value["exact_execution_summary"]["successful_get_object_requests"] = 71
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(validator.R11EvidenceError):
            validator.validate(root)

    def test_consumption_duplicate_locations_mutation_fails_closed(self) -> None:
        temporary, root = self.fixture_root()
        self.addCleanup(temporary.cleanup)
        path = root / validator.CONSUMPTION
        value = json.loads(path.read_text())
        value["duplicate_wallet_tid_locations_known"] = True
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(validator.R11EvidenceError):
            validator.validate(root)

    def test_consumption_success_count_mutation_fails_closed(self) -> None:
        temporary, root = self.fixture_root()
        self.addCleanup(temporary.cleanup)
        path = root / validator.CONSUMPTION
        value = json.loads(path.read_text())
        value["successful_get_object_requests"] = 71
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(validator.R11EvidenceError):
            validator.validate(root)

    def test_exact_nested_schema_drift_fails_closed(self) -> None:
        mutations = (
            (
                validator.EVIDENCE / "HL-ARCHIVE-R11-72H-PERSISTENCE-SCALING-001-ATTESTATION.json",
                lambda value: value["claims_proven"].pop("zero_retries"),
            ),
            (
                validator.EVIDENCE / "HL-ARCHIVE-R11-72H-PERSISTENCE-SCALING-001-ATTESTATION.json",
                lambda value: value["exact_execution_summary"].__setitem__("unreviewed_extra", 0),
            ),
            (
                validator.CONSUMPTION,
                lambda value: value.pop("artifact_name"),
            ),
        )
        for relative, mutate in mutations:
            with self.subTest(relative=relative, mutation=mutate):
                temporary, root = self.fixture_root()
                try:
                    path = root / relative
                    value = json.loads(path.read_text())
                    mutate(value)
                    path.write_text(json.dumps(value), encoding="utf-8")
                    with self.assertRaises(validator.R11EvidenceError):
                        validator.validate(root)
                finally:
                    temporary.cleanup()

    def test_exact_claim_type_drift_fails_closed(self) -> None:
        temporary, root = self.fixture_root()
        self.addCleanup(temporary.cleanup)
        path = root / validator.EVIDENCE / "HL-ARCHIVE-R11-72H-PERSISTENCE-SCALING-001-ATTESTATION.json"
        value = json.loads(path.read_text())
        value["claims_proven"]["zero_retries"] = 1
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(validator.R11EvidenceError):
            validator.validate(root)

    def test_rerun_or_budget_reopening_fails_closed(self) -> None:
        temporary, root = self.fixture_root()
        self.addCleanup(temporary.cleanup)
        path = root / validator.CONSUMPTION
        value = json.loads(path.read_text())
        value["rerun_authorized"] = True
        value["remaining_get_object_budget_from_consumed_release"] = 72
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(validator.R11EvidenceError):
            validator.validate(root)

    def test_duplicate_root_cause_overclaim_fails_closed(self) -> None:
        temporary, root = self.fixture_root()
        self.addCleanup(temporary.cleanup)
        path = root / validator.EVIDENCE / "HL-ARCHIVE-R11-72H-PERSISTENCE-SCALING-001-ATTESTATION.json"
        value = json.loads(path.read_text())
        value["claims_not_proven"]["tid_is_globally_unique_per_wallet"] = True
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(validator.R11EvidenceError):
            validator.validate(root)

    def test_diagnostic_conservation_mutation_fails_closed(self) -> None:
        temporary, root = self.fixture_root()
        self.addCleanup(temporary.cleanup)
        path = root / validator.EVIDENCE / "R11_AGGREGATE_DIAGNOSTICS.json"
        value = json.loads(path.read_text())
        value["event_pair_count"] -= 1
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(validator.R11EvidenceError):
            validator.validate(root)

    def test_r12_ready_overclaim_fails_closed(self) -> None:
        temporary, root = self.fixture_root()
        self.addCleanup(temporary.cleanup)
        path = root / validator.EVIDENCE / "R11_RESEARCH_CONCLUSION.md"
        path.write_text(path.read_text() + "\nR12_READY\n", encoding="utf-8")
        with self.assertRaises(validator.R11EvidenceError):
            validator.validate(root)


if __name__ == "__main__":
    unittest.main()
