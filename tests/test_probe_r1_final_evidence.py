from __future__ import annotations

import base64
import gzip
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE_ROOT = ROOT / "research/wallet_copyability/probe_r1"
EVIDENCE_ROOT = PROBE_ROOT / "evidence"
RUN_ROOT = EVIDENCE_ROOT / "run-31193129277"
sys.path.insert(0, str(PROBE_ROOT))

import contract
import validate_attestation
import validate_attestation_strict
import validate_evidence


class ProbeR1FinalEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract_path = PROBE_ROOT / "PROBE_CONTRACT.json"
        self.encoded_output_path = RUN_ROOT / "hl-public-probe-r1.json.gz.b64"
        self.encoding_path = RUN_ROOT / "EVIDENCE_ENCODING.json"
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

    def raw_output_bytes(self) -> bytes:
        metadata = self.load(self.encoding_path)
        encoded = self.encoded_output_path.read_bytes()
        self.assertEqual(len(encoded), metadata["encoded_size_in_bytes"])
        self.assertEqual(
            hashlib.sha256(encoded).hexdigest(),
            metadata["encoded_sha256"],
        )
        compressed = base64.b64decode(encoded.strip(), validate=True)
        self.assertEqual(len(compressed), metadata["gzip_size_in_bytes"])
        self.assertEqual(
            hashlib.sha256(compressed).hexdigest(),
            metadata["gzip_sha256"],
        )
        raw = gzip.decompress(compressed)
        self.assertEqual(len(raw), metadata["raw_size_in_bytes"])
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            metadata["raw_sha256"],
        )
        return raw

    def raw_output(self) -> dict:
        value = json.loads(
            self.raw_output_bytes(),
            object_pairs_hook=validate_evidence.strict_object,
            parse_constant=lambda token: (_ for _ in ()).throw(
                validate_evidence.EvidenceError(
                    f"non-finite retained evidence value: {token}"
                )
            ),
        )
        self.assertIsInstance(value, dict)
        return value

    def test_exact_probe_output_remains_valid(self) -> None:
        evidence = self.raw_output()
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
        self.assertEqual(evidence["total_request_attempts"], 16)
        self.assertEqual(evidence["total_declared_request_weight"], 586)
        self.assertEqual(evidence["remaining_declared_weight_margin"], 614)
        self.assertFalse(evidence["market_data_ingested"])
        self.assertIsNone(evidence["empirical_result"])

    def test_strict_final_attestation_binds_exact_output(self) -> None:
        record = self.load(self.attestation_path)
        evidence_bytes = self.raw_output_bytes()
        evidence = self.raw_output()
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
            "9f35a87a65b9b80db544d07ce4e68c33c8343e3b",
        )
        self.assertEqual(record["workflow_run_id"], 31193129277)
        self.assertEqual(record["workflow_job_id"], 92914689054)
        self.assertEqual(record["artifact_id"], 8999652912)
        self.assertEqual(
            record["artifact_zip_sha256"],
            "5a30c6e9a2b80e49eac6d341e0c93f9e182a408b1f10f81270795054eee5534e",
        )
        self.assertEqual(
            record["review_status"],
            "CLEAN_CONTEXT_REVIEW_PASS",
        )
        self.assertFalse(record["independent_external_review"])

    def test_artifact_file_ledger_matches_retained_files(self) -> None:
        mapping: dict[str, bytes] = {
            "hl-public-probe-r1.json": self.raw_output_bytes(),
            "probe-run-context.json": self.context_path.read_bytes(),
            "probe-validation.log": (RUN_ROOT / "probe-validation.log").read_bytes(),
            "probe-validation.rc": (RUN_ROOT / "probe-validation.rc").read_bytes(),
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
            actual = hashlib.sha256(mapping[name]).hexdigest()
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
        self.assertTrue(
            verification["checked_out_commit_matches_reviewed_commit"]
        )
        self.assertEqual(
            verification["checked_out_commit"],
            verification["reviewed_commit"],
        )
        self.assertTrue(
            verification["probe_output"]["request_hashes_match_frozen_contract"]
        )
        self.assertTrue(
            verification["probe_output"]["response_classes_match_frozen_contract"]
        )
        self.assertTrue(
            verification["validation"]["request_hashes_recomputed"]
        )
        self.assertTrue(
            verification["validation"][
                "terminal_and_archive_states_independently_derived"
            ]
        )
        self.assertEqual(
            verification["privacy_checks"]["ethereum_address_patterns_found"],
            0,
        )
        self.assertFalse(
            verification["privacy_checks"]["raw_response_bodies_present"]
        )
        self.assertFalse(
            verification["privacy_checks"]["credential_or_secret_material_found"]
        )
        self.assertTrue(
            verification["privacy_checks"][
                "observations_contain_only_structural_metadata"
            ]
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
            [1, 2, 3, 4, 5],
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
        self.assertFalse(runs[3]["accepted_for_final_attestation"])
        self.assertEqual(
            runs[3]["classification"],
            "SUPERSEDED_EQUIVALENT_PR_MERGE_REF_PASS_EXACT_SOURCE_HEAD_REQUIRED",
        )
        accepted = [
            row for row in runs if row["accepted_for_final_attestation"]
        ]
        self.assertEqual(len(accepted), 1)
        self.assertEqual(
            accepted[0]["head_commit"],
            "9f35a87a65b9b80db544d07ce4e68c33c8343e3b",
        )
        self.assertEqual(
            accepted[0]["checked_out_commit"],
            accepted[0]["head_commit"],
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
            "9f35a87a65b9b80db544d07ce4e68c33c8343e3b",
            "31193129277",
            "independent external scientific",
            "ROUTES_CONFIRMED_ACCESS_RESTRICTED",
            "No archive object was listed or downloaded",
            "No alpha, profitability, paper, shadow, live, leverage",
        ):
            self.assertIn(token, review)


if __name__ == "__main__":
    unittest.main()
