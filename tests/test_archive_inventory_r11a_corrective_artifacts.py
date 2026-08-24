from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from research.archive_inventory.r11a_corrective.limits import DEFAULT_LIMITS
from research.archive_inventory.r11a_corrective.runtime import RuntimeGuard
from research.archive_inventory.r11a_corrective.storage import (
    AtomicArtifactDirectory,
    MultisetCommitment,
    ReservedBinaryWriter,
    SortEvidence,
    StorageBoundaryError,
    WorkspaceMeter,
)
class CorrectiveArtifactTests(unittest.TestCase):
    def test_atomic_commit_never_exposes_final_directory_when_validator_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "workspace"
            guard = RuntimeGuard(DEFAULT_LIMITS, monotonic_ns=lambda: 0)
            meter = WorkspaceMeter(root, DEFAULT_LIMITS, guard)
            meter.bootstrap()
            atomic = AtomicArtifactDirectory(root, meter, "final")
            with self.assertRaisesRegex(RuntimeError, "synthetic validator failure"):
                with atomic as staging:
                    writer = ReservedBinaryWriter(
                        staging / "payload.bin",
                        meter,
                        maximum_bytes=4,
                        label="synthetic payload",
                    )
                    writer.write(b"data")
                    writer.close()
                    atomic.commit(
                        lambda _: (_ for _ in ()).throw(
                            RuntimeError("synthetic validator failure")
                        )
                    )
            self.assertFalse((root / "final").exists())
            self.assertFalse((root / ".final.staging").exists())


class CorrectiveMultisetTests(unittest.TestCase):
    def test_multiplicity_sensitive_commitment_detects_record_loss_or_duplication(self) -> None:
        first = MultisetCommitment()
        second = MultisetCommitment()
        third = MultisetCommitment()
        for record in (b"a", b"b", b"b"):
            first.add(record)
        for record in (b"b", b"a", b"b"):
            second.add(record)
        for record in (b"a", b"b"):
            third.add(record)
        self.assertEqual(first.as_mapping(), second.as_mapping())
        self.assertNotEqual(first.as_mapping(), third.as_mapping())
        SortEvidence(
            input_records=3,
            output_records=3,
            input_logical_bytes=3,
            output_logical_bytes=3,
            source_commitment=first.as_mapping(),
            destination_commitment=second.as_mapping(),
            sorted_stream_sha256="0" * 64,
            output_bytes=3,
        ).validate()
        with self.assertRaises(StorageBoundaryError):
            SortEvidence(
                input_records=3,
                output_records=2,
                input_logical_bytes=3,
                output_logical_bytes=2,
                source_commitment=first.as_mapping(),
                destination_commitment=third.as_mapping(),
                sorted_stream_sha256="0" * 64,
                output_bytes=2,
            ).validate()


class CorrectiveWorkflowTests(unittest.TestCase):
    def test_candidate_separates_stages_and_validates_before_upload(self) -> None:
        root = Path(__file__).resolve().parents[1]
        candidate = root / "research/archive_inventory/r11a_corrective/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic-r6.yml"
        text = candidate.read_text(encoding="utf-8")
        self.assertIn("validate_r11a_corrective_implementation_r6.py --canonical-bytes", text)
        self.assertNotIn("validate_r11a_implementation.py", text)
        self.assertEqual(text.count("aws sts get-caller-identity --output json"), 1)
        self.assertNotIn("aws s3 ", text.lower())
        self.assertLess(
            text.index("Validate complete artifact before any upload"),
            text.index("Upload only the already validated R11A artifact"),
        )
        self.assertLess(text.index("free-space threshold"), text.index("configure-aws-credentials"))


if __name__ == "__main__":
    unittest.main()
