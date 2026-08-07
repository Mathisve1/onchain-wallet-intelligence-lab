from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE_ROOT = ROOT / "research/wallet_copyability/probe_r1"
sys.path.insert(0, str(PROBE_ROOT))

import contract
import validate_evidence


class ProbeR1EvidenceValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract_path = PROBE_ROOT / "PROBE_CONTRACT.json"
        self.contract = contract.load_contract(self.contract_path)

    def observation(self, row: dict, index: int) -> dict:
        started = f"2026-08-07T12:00:{index:02d}.000000Z"
        completed = f"2026-08-07T12:00:{index:02d}.100000Z"
        if row["expected"] == "s3_listing_or_error":
            response_class = "S3_ERROR_RESPONSE"
            top_level_type = "xml"
            json_status = "NOT_APPLICABLE"
            http_status = 403
            body = b"<Error><Code>AccessDenied</Code></Error>"
            element_count = None
        else:
            response_class = "JSON"
            json_status = "VALID_JSON"
            http_status = 200
            if row["expected"] in {"json_array", "json_array_or_null"}:
                top_level_type = "array"
                body = b"[]"
                element_count = 0
            else:
                top_level_type = "object"
                body = b"{}"
                element_count = 0
        return {
            "probe_id": row["id"],
            "core": row["core"],
            "method": row["method"],
            "request_origin": row["origin"],
            "request_path": row["path"],
            "request_sha256": validate_evidence.expected_request_sha(
                row,
                self.contract,
            ),
            "declared_weight": row["declared_weight"],
            "weight_basis": row["weight_basis"],
            "attempts": 1,
            "started_at_utc": started,
            "completed_at_utc": completed,
            "http_status": http_status,
            "elapsed_ms": 100.0,
            "transport_error_class": (
                "HTTPError" if http_status == 403 else None
            ),
            "transport_error_message": (
                "Forbidden" if http_status == 403 else None
            ),
            "expected_shape": row["expected"],
            "status": "PASS",
            "body_length": len(body),
            "body_sha256": contract.sha256(body),
            "content_type": (
                "application/xml"
                if http_status == 403
                else "application/json"
            ),
            "response_class": response_class,
            "json_status": json_status,
            "top_level_type": top_level_type,
            "top_level_keys": [],
            "element_count": element_count,
            "sample_item_types": [],
        }

    def valid_result(self) -> dict:
        observations = [
            self.observation(row, index)
            for index, row in enumerate(self.contract["probes"])
        ]
        weight = sum(row["declared_weight"] for row in observations)
        return {
            "schema_version": "1.2",
            "study_id": self.contract["study_id"],
            "probe_id": self.contract["probe_id"],
            "contract_sha256": contract.contract_sha256(
                self.contract_path
            ),
            "collector_bundle_sha256": contract.collector_bundle_sha256(),
            "collected_at_utc": observations[0]["started_at_utc"],
            "completed_at_utc": observations[-1]["completed_at_utc"],
            "scope": "READ_ONLY_PUBLIC_SCHEMA_AND_ARCHIVE_ROUTE_BEHAVIOR",
            "terminal_status": "PUBLIC_PROBE_PASS",
            "archive_access_status": "ROUTES_CONFIRMED_ACCESS_RESTRICTED",
            "published_ip_budget_per_minute": 1200,
            "registered_probe_count": 16,
            "observation_count": 16,
            "pass_count": 16,
            "fail_count": 0,
            "total_request_attempts": 16,
            "total_declared_request_weight": weight,
            "remaining_declared_weight_margin": 1200 - weight,
            "observations": observations,
            "security_assertions": {
                "credentials_used": False,
                "authorization_header_used": False,
                "cookies_used": False,
                "private_keys_used": False,
                "signed_actions_used": False,
                "exchange_action_endpoint_used": False,
                "orders_used": False,
                "withdrawals_used": False,
                "raw_response_values_persisted": False,
            },
            "market_data_ingested": False,
            "empirical_result": None,
            "authorizations": self.contract["authorizations"],
        }

    def test_valid_synthetic_result_passes(self) -> None:
        validate_evidence.validate_result(
            self.valid_result(),
            self.contract,
            self.contract_path,
        )

    def test_terminal_status_cannot_be_self_declared(self) -> None:
        result = self.valid_result()
        result["terminal_status"] = "PUBLIC_PROBE_PARTIAL"
        with self.assertRaises(validate_evidence.EvidenceError):
            validate_evidence.validate_result(
                result,
                self.contract,
                self.contract_path,
            )

    def test_request_hash_mutation_fails(self) -> None:
        result = self.valid_result()
        result["observations"][0]["request_sha256"] = "0" * 64
        with self.assertRaises(validate_evidence.EvidenceError):
            validate_evidence.validate_result(
                result,
                self.contract,
                self.contract_path,
            )

    def test_opened_security_assertion_fails(self) -> None:
        result = self.valid_result()
        result["security_assertions"]["orders_used"] = True
        with self.assertRaises(validate_evidence.EvidenceError):
            validate_evidence.validate_result(
                result,
                self.contract,
                self.contract_path,
            )

    def test_extra_field_fails(self) -> None:
        result = self.valid_result()
        result["alpha_claim"] = json.dumps({"positive": True})
        with self.assertRaises(validate_evidence.EvidenceError):
            validate_evidence.validate_result(
                result,
                self.contract,
                self.contract_path,
            )


if __name__ == "__main__":
    unittest.main()
