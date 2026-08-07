from __future__ import annotations

import copy
import json
import sys
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE_ROOT = ROOT / "research/wallet_copyability/probe_r1"
sys.path.insert(0, str(PROBE_ROOT))

import contract
import http_client
import probe
import validate_evidence


class ProbeR1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = contract.load_contract()

    def observation(self, row: dict, status: str = "PASS") -> dict:
        return {"probe_id": row["id"], "core": row["core"], "status": status}

    def test_frozen_contract_is_closed_and_bounded(self) -> None:
        self.assertEqual(self.contract["probe_id"], "HL-PUBLIC-PROBE-001R1")
        self.assertEqual(len(self.contract["probes"]), 17)
        self.assertFalse(self.contract["market_data_ingested"])
        self.assertIsNone(self.contract["empirical_result"])
        self.assertTrue(all(value is False for value in self.contract["authorizations"].values()))
        security = self.contract["security_boundary"]
        self.assertTrue(security["read_only"])
        self.assertTrue(all(value is False for key, value in security.items() if key != "read_only"))

    def test_every_route_is_allowlisted_and_information_only(self) -> None:
        for row in self.contract["probes"]:
            self.assertIn(row["origin"], self.contract["allowed_origins"])
            self.assertEqual(row["path"], "/info" if row["method"] == "POST" else "/")
        combined = (PROBE_ROOT / "probe.py").read_text() + (PROBE_ROOT / "http_client.py").read_text()
        self.assertNotIn("https://api.hyperliquid.xyz/exchange", combined)
        self.assertNotIn('"Authorization"', combined)
        self.assertNotIn('"Cookie"', combined)
        self.assertNotIn("private_key", combined.lower())

    def test_constructed_requests_have_no_credentials(self) -> None:
        for row in self.contract["probes"]:
            request, fingerprint = probe.make_request(row, self.contract)
            self.assertRegex(fingerprint, r"^[0-9a-f]{64}$")
            self.assertNotIn("Authorization", request.headers)
            self.assertNotIn("Cookie", request.headers)
            parsed = urllib.parse.urlsplit(request.full_url)
            self.assertIn(f"{parsed.scheme}://{parsed.netloc}", self.contract["allowed_origins"])

    def test_terminal_status_is_derived(self) -> None:
        passed = [self.observation(row) for row in self.contract["probes"]]
        self.assertEqual(probe.derive_terminal(passed, self.contract), "PUBLIC_PROBE_PASS")
        optional = copy.deepcopy(passed)
        optional[next(i for i, row in enumerate(optional) if not row["core"])]["status"] = "FAIL"
        self.assertEqual(probe.derive_terminal(optional, self.contract), "PUBLIC_PROBE_PARTIAL")
        core = copy.deepcopy(passed)
        core[next(i for i, row in enumerate(core) if row["core"])]["status"] = "FAIL"
        self.assertEqual(probe.derive_terminal(core, self.contract), "PUBLIC_PROBE_FAIL")

    def test_pending_evidence_is_a_non_result(self) -> None:
        evidence = validate_evidence.load_json(PROBE_ROOT / "PENDING_EVIDENCE.json")
        validate_evidence.validate_pending(evidence, self.contract)
        self.assertEqual(evidence["observations"], [])
        self.assertIsNone(evidence["output_sha256"])

    def test_contract_mutations_fail_closed(self) -> None:
        mutations = []
        auth = copy.deepcopy(self.contract)
        auth["authorizations"]["paper_authorized"] = True
        mutations.append(auth)
        origin = copy.deepcopy(self.contract)
        origin["allowed_origins"].append("https://example.com")
        mutations.append(origin)
        route = copy.deepcopy(self.contract)
        route["probes"][0]["path"] = "/exchange"
        mutations.append(route)
        weak = copy.deepcopy(self.contract)
        weak["limits"]["maximum_total_requests"] = 1
        mutations.append(weak)
        for mutation in mutations:
            with self.subTest(), self.assertRaises(contract.ProbeContractError):
                contract.validate_contract(mutation)

    def test_duplicate_json_keys_fail(self) -> None:
        with self.assertRaises(validate_evidence.EvidenceError):
            json.loads('{"x":1,"x":2}', object_pairs_hook=validate_evidence.strict_object)

    def test_response_shape_classification(self) -> None:
        record = http_client.ResponseRecord(200, b'{"a":1}', "application/json", 1.0, None, None)
        status, summary = http_client.classify_body("json_object", record)
        self.assertEqual(status, "PASS")
        self.assertEqual(summary["top_level_keys"], ["a"])
        xml = http_client.ResponseRecord(403, b"<Error><Code>AccessDenied</Code></Error>", "application/xml", 1.0, "HTTPError", "Forbidden")
        self.assertEqual(http_client.classify_body("xml_or_error", xml)[0], "PASS")

    def test_cross_origin_redirect_fails(self) -> None:
        handler = http_client.SameOriginRedirectHandler()
        request = urllib.request.Request("https://api.hyperliquid.xyz/info")
        with self.assertRaises(urllib.error.HTTPError):
            handler.redirect_request(request, None, 302, "Found", {}, "https://example.com/other")

    def test_bundle_hash_is_well_formed(self) -> None:
        self.assertRegex(contract.collector_bundle_sha256(), r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
