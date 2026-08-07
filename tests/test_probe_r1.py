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

    def minimal_observation(self, row: dict, status: str = "PASS", response_class: str = "JSON") -> dict:
        return {"probe_id": row["id"], "core": row["core"], "status": status, "response_class": response_class}

    def test_contract_is_closed_and_bounded(self) -> None:
        self.assertEqual(self.contract["schema_version"], "1.1")
        self.assertEqual(len(self.contract["probes"]), 17)
        self.assertFalse(self.contract["market_data_ingested"])
        self.assertIsNone(self.contract["empirical_result"])
        self.assertTrue(all(value is False for value in self.contract["authorizations"].values()))
        security = self.contract["security_boundary"]
        self.assertTrue(security["read_only"])
        self.assertTrue(all(value is False for key, value in security.items() if key != "read_only"))
        worst = len(self.contract["probes"]) * self.contract["limits"]["maximum_attempts_per_probe"]
        self.assertLessEqual(worst, self.contract["limits"]["maximum_total_requests"])

    def test_routes_and_constructed_requests_are_allowlisted(self) -> None:
        for row in self.contract["probes"]:
            request, fingerprint = probe.make_request(row, self.contract)
            self.assertRegex(fingerprint, r"^[0-9a-f]{64}$")
            headers = {key.lower() for key in request.headers}
            self.assertNotIn("authorization", headers)
            self.assertNotIn("cookie", headers)
            parsed = urllib.parse.urlsplit(request.full_url)
            self.assertIn(f"{parsed.scheme}://{parsed.netloc}", self.contract["allowed_origins"])
            self.assertEqual(row["path"], "/info" if row["method"] == "POST" else "/")

    def test_terminal_and_archive_states_are_derived(self) -> None:
        observations = []
        for row in self.contract["probes"]:
            cls = "S3_LISTING" if row["id"] in probe.ARCHIVE_IDS else "JSON"
            observations.append(self.minimal_observation(row, response_class=cls))
        self.assertEqual(probe.derive_terminal(observations, self.contract), "PUBLIC_PROBE_PASS")
        self.assertEqual(probe.derive_archive_access(observations), "LISTINGS_AVAILABLE")
        optional = copy.deepcopy(observations)
        optional[next(i for i, row in enumerate(optional) if not row["core"])]["status"] = "FAIL"
        self.assertEqual(probe.derive_terminal(optional, self.contract), "PUBLIC_PROBE_PARTIAL")
        core = copy.deepcopy(observations)
        core[next(i for i, row in enumerate(core) if row["core"])]["status"] = "FAIL"
        self.assertEqual(probe.derive_terminal(core, self.contract), "PUBLIC_PROBE_FAIL")
        restricted = copy.deepcopy(observations)
        restricted[next(i for i, row in enumerate(restricted) if row["probe_id"] in probe.ARCHIVE_IDS)]["response_class"] = "S3_ERROR_RESPONSE"
        self.assertEqual(probe.derive_archive_access(restricted), "ROUTES_CONFIRMED_ACCESS_RESTRICTED")
        self.assertEqual(probe.derive_terminal(observations[:-1], self.contract), "PUBLIC_PROBE_FAIL")

    def test_pending_evidence_is_non_result(self) -> None:
        evidence = validate_evidence.load_json(PROBE_ROOT / "PENDING_EVIDENCE.json")
        validate_evidence.validate_pending(evidence, self.contract)
        self.assertEqual(evidence["observations"], [])
        self.assertIsNone(evidence["output_sha256"])

    def test_contract_mutations_fail_closed(self) -> None:
        mutations = []
        auth = copy.deepcopy(self.contract); auth["authorizations"]["paper_authorized"] = True; mutations.append(auth)
        origin = copy.deepcopy(self.contract); origin["allowed_origins"].append("https://example.com"); mutations.append(origin)
        route = copy.deepcopy(self.contract); route["probes"][0]["path"] = "/exchange"; mutations.append(route)
        requests = copy.deepcopy(self.contract); requests["limits"]["maximum_total_requests"] = 1; mutations.append(requests)
        weight = copy.deepcopy(self.contract); weight["limits"]["maximum_declared_request_weight"] = 1; mutations.append(weight)
        identity = copy.deepcopy(self.contract); identity["documentation_fixtures"]["identity_claim_allowed"] = True; mutations.append(identity)
        for mutation in mutations:
            with self.subTest(), self.assertRaises(contract.ProbeContractError):
                contract.validate_contract(mutation)

    def test_strict_json_rejects_duplicate_and_nonfinite_values(self) -> None:
        with self.assertRaises(validate_evidence.EvidenceError):
            json.loads('{"x":1,"x":2}', object_pairs_hook=validate_evidence.strict_object)
        with self.assertRaises(contract.ProbeContractError):
            json.loads('{"x":NaN}', parse_constant=lambda token: (_ for _ in ()).throw(contract.ProbeContractError(token)))

    def test_response_classification_is_fail_closed(self) -> None:
        valid = http_client.ResponseRecord(200, b'{"a":1}', "application/json", 1.0, None, None)
        status, summary = http_client.classify_body("json_object", valid)
        self.assertEqual((status, summary["response_class"], summary["top_level_keys"]), ("PASS", "JSON", ["a"]))
        listing = http_client.ResponseRecord(200, b"<ListBucketResult></ListBucketResult>", "application/xml", 1.0, None, None)
        self.assertEqual(http_client.classify_body("s3_listing_or_error", listing)[1]["response_class"], "S3_LISTING")
        denied = http_client.ResponseRecord(403, b"<Error><Code>AccessDenied</Code></Error>", "application/xml", 1.0, "HTTPError", "Forbidden")
        self.assertEqual(http_client.classify_body("s3_listing_or_error", denied)[1]["response_class"], "S3_ERROR_RESPONSE")
        html = http_client.ResponseRecord(404, b"<html>not-s3</html>", "text/html", 1.0, "HTTPError", "Not Found")
        self.assertEqual(http_client.classify_body("s3_listing_or_error", html)[0], "FAIL")

    def test_cross_origin_redirect_fails(self) -> None:
        handler = http_client.SameOriginRedirectHandler()
        request = urllib.request.Request("https://api.hyperliquid.xyz/info")
        with self.assertRaises(urllib.error.HTTPError):
            handler.redirect_request(request, None, 302, "Found", {}, "https://example.com/other")

    def test_collector_bundle_hash_is_bound(self) -> None:
        self.assertRegex(contract.collector_bundle_sha256(), r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
