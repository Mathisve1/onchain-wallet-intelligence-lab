from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE_ROOT = ROOT / "research/wallet_copyability/probe_r1"
EVIDENCE_ROOT = PROBE_ROOT / "evidence"
RUN_ROOT = EVIDENCE_ROOT / "run-31179660372"
sys.path.insert(0, str(PROBE_ROOT))

import contract
import validate_attestation
import validate_attestation_strict
import validate_evidence


class ProbeR1FinalEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract_path = PROBE_ROOT / "PROBE_CONTRACT.json"
        self.output_path = RUN_ROOT / "hl-public-probe-r1.json"
        self.context_path = RUN_ROOT / "probe-run-context.json"
        self.attestation_path = (
            EVIDENCE_ROOT / "HL-PUBLIC-PROBE-001R1-ATTESTATION.json"
        )
        self.verification_path = (
            RUN_ROOT / "INDEPENDENT_ARTIFACT_VERIFICATION.json"
        )
        self.lineage_path = EVIDENCE_ROOT / "RUN_LINEAGE.json"
        self.contract = contract.load_contract(self.contract_path)

    def load(self, path: Path) -> dict:
        return validate_evidence.load_json(path)

    def test_exact_probe_output_remains_valid(self) -> None:
        evidence = self.load(self.output_path)
        validate_evidence.validate_result(
            evidence,
            self.contract,
            self.contract_path,
        )
        self.assertEqual(evidence["terminal_status"], "PUBLIC_PROBE_PASS")
        self.assertEqual(
            evidence["archive_access_status"],
            "ROUTES_CONFIRMED_ACCESS_RESTRICTED",
        )
        self.assertEqual(
            (evidence["pass_count"], evidence["fail_count"]),
            (16, 0),
        )
        self.assertFalse(evidence["market_data_ingested"])
        self.assertIsNone(evidence["empirical_result"])

    def test_strict_final_attestation_binds_exact_output(self) -> None:
        record = self.load(self.attestation_path)
        evidence_bytes = self.output_path.read_bytes()
        evidence = self.load(self.output_path)
        validate_attestation_strict.validate_field_set(record)
        validate_attestation.validate_final(
            record,
            evidence,
            evidence_bytes,
            self.contract,
            self.contract_path,
        )
        self.assertEqual(
            record["reviewed_commit"],
            "facd8b26778eb483a4917fc4418069c35b981e8b",
        )
        self.assertEqual(record["workflow_run_id"], 31179660372)
        self.assertEqual(record["workflow_job_id"], 92869634761)
        self.assertEqual(record["artifact_id"], 8994227729)
        self.assertEqual(
            record["review_status"],
            "CLEAN_CONTEXT_REVIEW_PASS",
        )
        self.assertFalse(record["independent_external_review"])

    def test_artifact_file_ledger_matches_retained_files(self) -> None:
        mapping = {
            "hl-public-probe-r1.json": self.output_path,
            "probe-run-context.json": self.context_path,
            "probe-validation.log": RUN_ROOT / "probe-validation.log",
            "probe-validation.rc": RUN_ROOT / "probe-validation.rc",
        }
        observed_names: set[str] = set()
        for line in (
            RUN_ROOT / "ARTIFACT_FILES.sha256"
        ).read_text().splitlines():
            if not line:
                continue
            expected, original = line.split("  ", 1)
            name = Path(original).name
            self.assertIn(name, mapping)
            self.assertNotIn(name, observed_names)
            observed_names.add(name)
            actual = hashlib.sha256(mapping[name].read_bytes()).hexdigest()
            self.assertEqual(actual, expected, name)
        self.assertEqual(observed_names, set(mapping))

    def test_independent_download_verification_is_closed_and_consistent(self) -> None:
        verification = self.load(self.verification_path)
        attestation = self.load(self.attestation_path)
        self.assertTrue(verification["validation"]["all_checks_pass"])
        self.assertFalse(
            verification["validation"]["independent_external_review"]
        )
        self.assertEqual(
            verification["artifact"]["downloaded_zip_sha256"],
            attestation["artifact_zip_sha256"],
        )
        self.assertTrue(
            verification["artifact"]["provider_digest_matches_download"]
        )
        self.assertEqual(
            verification["privacy_checks"]["ethereum_address_patterns_found"],
            0,
        )
        self.assertFalse(
            verification["privacy_checks"]["raw_response_bodies_present"]
        )
        self.assertFalse(verification["market_data_ingested"])
        self.assertIsNone(verification["empirical_result"])
        self.assertTrue(
            all(
                value is False
                for value in verification["authorizations"].values()
            )
        )

    def test_run_lineage_preserves_failures_and_one_final_candidate(self) -> None:
        lineage = self.load(self.lineage_path)
        runs = lineage["runs"]
        self.assertEqual(
            [row["lineage_order"] for row in runs],
            [1, 2, 3, 4],
        )
        self.assertFalse(runs[0]["network_executed"])
        self.assertFalse(runs[1]["network_executed"])
        self.assertEqual(
            runs[0]["classification"],
            "FAILED_PRE_NETWORK_PACKAGING",
        )
        self.assertEqual(
            runs[1]["classification"],
            "FAILED_PRE_NETWORK_AST_TEST_FALSE_POSITIVE",
        )
        accepted = [
            row for row in runs if row["accepted_for_final_attestation"]
        ]
        self.assertEqual(len(accepted), 1)
        self.assertEqual(
            accepted[0]["head_commit"],
            "facd8b26778eb483a4917fc4418069c35b981e8b",
        )
        self.assertEqual(
            accepted[0]["technical_route_result"],
            "PUBLIC_PROBE_PASS",
        )
        self.assertIsNone(lineage["empirical_result"])
        self.assertTrue(
            all(
                value is False
                for value in lineage["authorizations"].values()
            )
        )

    def test_clean_context_review_keeps_market_claims_closed(self) -> None:
        review = (EVIDENCE_ROOT / "CLEAN_CONTEXT_REVIEW.md").read_text()
        for token in (
            "CLEAN_CONTEXT_REVIEW_PASS",
            "independent external scientific",
            "ROUTES_CONFIRMED_ACCESS_RESTRICTED",
            "No archive object was listed or downloaded",
            "No alpha, profitability, paper, shadow, live, leverage",
        ):
            self.assertIn(token, review)


if __name__ == "__main__":
    unittest.main()
