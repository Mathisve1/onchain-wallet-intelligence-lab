from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "governance"))

from validate_probe_evidence import (  # noqa: E402
    ValidationError,
    canonical_bytes,
    load_json,
    sha256_file,
    validate_contract,
    validate_evidence_index,
    validate_probe_output,
    validate_static_probe_script,
)

CONTRACT_PATH = ROOT / "research/wallet_copyability/PROBE_CONTRACT.json"
SOURCE_REGISTER_PATH = ROOT / "research/wallet_copyability/OFFICIAL_SOURCE_REGISTER.json"
SCRIPT_PATH = ROOT / "research/wallet_copyability/scripts/probe_public_api.py"
INDEX_PATH = ROOT / "research/wallet_copyability/TECHNICAL_PROBE_EVIDENCE.json"


def request_type(probe: dict) -> str | None:
    payload = probe.get("payload")
    return payload.get("type") if isinstance(payload, dict) else None


def valid_assertion_details(probe: dict) -> dict:
    assertion = probe["assertion"]
    details: dict = {
        "assertion": assertion,
        "expected_top_level": probe["expected_top_level"],
        "actual_top_level": probe["expected_top_level"],
    }
    if assertion == "ROLE_EQUALS":
        details.update({"actual_role": probe["expected_role"], "expected_role": probe["expected_role"]})
    elif assertion == "SUBACCOUNT_RELATION_PRESENT":
        details.update({"relation_present": True, "matching_relation_count": 1, "reported_subaccount_count": 1})
    elif assertion == "SUBACCOUNT_ROLE_AND_MASTER":
        details.update({"actual_role": "subAccount", "role_match": True, "master_match": True})
    elif assertion == "ACTIVE_FILL_LIMIT_DIAGNOSTIC":
        details.update(
            {
                "event_count": 501,
                "time_field_count": 501,
                "minimum_event_time_ms": 1,
                "maximum_event_time_ms": 2,
                "limit_observation": "MORE_THAN_500_RECORDS_OBSERVED",
            }
        )
    elif assertion == "S3_LISTING_OR_ACCESS_CONTROL":
        details.update(
            {
                "xml_root": "ListBucketResult",
                "xml_key_count": 1,
                "xml_contents_count": 1,
                "xml_is_truncated": False,
                "xml_error_code": None,
            }
        )
    return details


def build_valid_output(contract: dict) -> dict:
    observations = []
    for sequence, probe in enumerate(contract["probes"], 1):
        top_type = probe["expected_top_level"]
        parser = probe["parser"]
        schema_paths = [f"$:{top_type}"]
        observation = {
            "probe_id": probe["probe_id"],
            "sequence": sequence,
            "required": probe["required"],
            "failure_impact": probe.get("failure_impact", "FAIL"),
            "method": probe["method"],
            "request_origin": probe["origin"],
            "request_path": probe["path"],
            "request_type": request_type(probe),
            "request_sha256": "1" * 64,
            "declared_base_weight": probe["base_weight"],
            "attempt_count": 1,
            "http_status": 200,
            "elapsed_ms": 1.0,
            "body_length": 2,
            "body_sha256": "2" * 64,
            "selected_headers": {"content-type": "application/json" if parser == "JSON" else "application/xml"},
            "parser": parser,
            "parse_status": "VALID_JSON" if parser == "JSON" else "VALID_XML",
            "parse_error": None,
            "top_level_type": top_type,
            "top_level_keys": [],
            "element_count": 1,
            "sample_item_types": [],
            "sample_item_keys": [],
            "schema_paths": schema_paths,
            "schema_fingerprint_sha256": hashlib.sha256(canonical_bytes(schema_paths)).hexdigest(),
            "assertion_status": "PASS",
            "assertion_reason": "synthetic valid fixture",
            "assertion_details": valid_assertion_details(probe),
            "outcome": "PASS",
            "outcome_reason": "synthetic valid fixture",
            "transport_error_class": None,
            "transport_error_message": None,
            "raw_response_bytes_retained": False,
            "response_values_retained": False,
        }
        observations.append(observation)

    return {
        "schema_version": "1.0",
        "study_id": contract["study_id"],
        "probe_id": contract["probe_id"],
        "contract_id": contract["contract_id"],
        "scope": "READ_ONLY_PUBLIC_SCHEMA_RELATIONSHIP_LIMIT_AND_ARCHIVE_AVAILABILITY_PROBE",
        "collected_at_utc": "2026-08-07T00:00:00Z",
        "anchor_time_ms": 1786060800000,
        "reviewed_commit": "a" * 40,
        "workflow": {
            "repository": "Mathisve1/onchain-wallet-intelligence-lab",
            "run_id": 1,
            "run_attempt": 1,
            "job_name": "public-probe",
            "ref": "research/test",
        },
        "environment": {
            "python_version": "3.12.13",
            "python_implementation": "CPython",
            "platform_system": "Linux",
            "platform_machine": "x86_64",
        },
        "input_hashes": {
            "contract_sha256": sha256_file(CONTRACT_PATH),
            "source_register_sha256": sha256_file(SOURCE_REGISTER_PATH),
            "script_sha256": sha256_file(SCRIPT_PATH),
        },
        "network_projection": {
            "allowed_origins": sorted(contract["network_policy"]["allowed_origins"]),
            "request_count": len(observations),
            "declared_base_weight": sum(row["declared_base_weight"] for row in observations),
            "cross_origin_redirects_allowed": False,
            "maximum_response_bytes": contract["network_policy"]["maximum_response_bytes"],
        },
        "observations": observations,
        "derived": {
            "terminal_status": "PUBLIC_PROBE_PASS",
            "pass_count": len(observations),
            "degraded_count": 0,
            "fail_count": 0,
            "required_failures": [],
            "degraded_probes": [],
            "optional_failures": [],
            "documentation_limit_observation": "MORE_THAN_500_RECORDS_OBSERVED",
        },
        "controls": {
            "credentials_used": False,
            "authorization_headers_used": False,
            "environment_secrets_used": False,
            "signed_actions_used": False,
            "exchange_action_endpoint_used": False,
            "orders_used": False,
            "withdrawals_used": False,
            "raw_response_bytes_retained": False,
            "response_values_retained": False,
        },
        "market_data_ingested": False,
        "empirical_result": None,
        "authorizations": dict(contract["authorizations"]),
    }


class ProbeEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = load_json(CONTRACT_PATH)

    def test_frozen_contract_and_pending_index_pass(self) -> None:
        validate_contract(self.contract)
        validate_evidence_index(load_json(INDEX_PATH), self.contract)

    def test_synthetic_complete_output_passes(self) -> None:
        validate_probe_output(build_valid_output(self.contract), self.contract)

    def test_manual_terminal_pass_relabel_fails(self) -> None:
        output = build_valid_output(self.contract)
        output["observations"][13]["outcome"] = "DEGRADED"
        output["observations"][13]["assertion_status"] = "DEGRADED"
        with self.assertRaises(ValidationError):
            validate_probe_output(output, self.contract)

    def test_missing_or_unknown_probe_fails(self) -> None:
        output = build_valid_output(self.contract)
        output["observations"].pop()
        with self.assertRaises(ValidationError):
            validate_probe_output(output, self.contract)

        output = build_valid_output(self.contract)
        output["observations"][0]["probe_id"] = "P999_HIDDEN"
        with self.assertRaises(ValidationError):
            validate_probe_output(output, self.contract)

    def test_false_relationship_pass_fails(self) -> None:
        output = build_valid_output(self.contract)
        output["observations"][3]["assertion_details"]["relation_present"] = False
        with self.assertRaises(ValidationError):
            validate_probe_output(output, self.contract)

    def test_hidden_output_field_fails(self) -> None:
        output = build_valid_output(self.contract)
        output["hidden_order_payload"] = {"submit": True}
        with self.assertRaises(ValidationError):
            validate_probe_output(output, self.contract)

    def test_schema_fingerprint_tamper_fails(self) -> None:
        output = build_valid_output(self.contract)
        output["observations"][0]["schema_paths"].append("$.hidden:string")
        with self.assertRaises(ValidationError):
            validate_probe_output(output, self.contract)

    def test_duplicate_json_keys_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"status":"PENDING_PUBLIC_PROBE","status":"PUBLIC_PROBE_PASS"}\n')
            with self.assertRaises(ValidationError):
                load_json(path)

    def test_static_exchange_endpoint_mutation_fails(self) -> None:
        original = SCRIPT_PATH.read_text()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "probe.py"
            path.write_text(original + '\nFORBIDDEN = "https://api.hyperliquid.xyz/exchange"\n')
            with self.assertRaises(ValidationError):
                validate_static_probe_script(self.contract, path)

    def test_static_extra_network_origin_fails(self) -> None:
        original = SCRIPT_PATH.read_text()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "probe.py"
            path.write_text(original + '\nOTHER = "https://example.com/data"\n')
            with self.assertRaises(ValidationError):
                validate_static_probe_script(self.contract, path)


if __name__ == "__main__":
    unittest.main()
