from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from governance.validate_probe_evidence_r2 import (  # noqa: E402
    ALLOWED_OBSERVATION_FIELDS,
    EvidenceError,
    contract_by_id,
    expected_outcome,
    load_json,
    require_false_authorizations,
    validate_pending,
    validate_r1_attestation,
)


class PublicProbeR2Tests(unittest.TestCase):
    @property
    def contract(self) -> dict:
        return load_json(ROOT / "research/wallet_copyability/PROBE_CONTRACT_R2.json")

    @property
    def pending(self) -> dict:
        return load_json(ROOT / "research/wallet_copyability/TECHNICAL_PROBE_EVIDENCE_R2.json")

    def test_contract_identity_scope_and_degraded_set(self) -> None:
        contract = self.contract
        self.assertEqual(contract["schema_version"], "1.1")
        self.assertEqual(contract["contract_id"], "HYPERLIQUID_PUBLIC_TECHNICAL_PROBE_CONTRACT_R2")
        self.assertEqual(contract["probe_id"], "HL-PUBLIC-PROBE-001R2")
        probes = contract_by_id(contract)
        self.assertEqual(len(probes), 18)
        degraded = {
            probe_id
            for probe_id, probe in probes.items()
            if probe["failure_impact"] == "DEGRADE"
        }
        self.assertEqual(
            degraded,
            {
                "P003_MASTER_USER_ROLE",
                "P004_MASTER_SUBACCOUNTS",
                "P005_SUBACCOUNT_USER_ROLE",
                "P014_VAULT_FILLS_BY_TIME_RECENT_24H",
                "P016_NODE_FILL_ARCHIVE_LISTING",
                "P017_MARKET_DATA_ARCHIVE_LISTING",
                "P018_ASSET_CTX_ARCHIVE_LISTING",
            },
        )
        self.assertTrue(contract["execution_boundary"]["read_only"])
        self.assertTrue(all(value is False for value in contract["authorizations"].values()))

    def test_pending_index_and_r1_attestation_pass(self) -> None:
        validate_r1_attestation()
        validate_pending(self.pending, self.contract)

    def test_pending_mutations_fail_closed(self) -> None:
        mutations = []
        authorized = copy.deepcopy(self.pending)
        authorized["paper_authorized"] = True
        mutations.append(authorized)
        premature = copy.deepcopy(self.pending)
        premature["workflow_run_id"] = 123
        mutations.append(premature)
        hidden = copy.deepcopy(self.pending)
        hidden["hidden_result"] = {"alpha": True}
        mutations.append(hidden)
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(EvidenceError):
                validate_pending(mutation, self.contract)

    def test_outcome_derivation_distinguishes_drift_from_core_failure(self) -> None:
        probes = contract_by_id(self.contract)
        degraded_observation = {
            "http_status": 200,
            "parse_status": "VALID_JSON",
            "assertion_status": "FAIL",
        }
        self.assertEqual(
            expected_outcome(degraded_observation, probes["P003_MASTER_USER_ROLE"]),
            "DEGRADED",
        )
        self.assertEqual(
            expected_outcome(degraded_observation, probes["P001_META"]),
            "FAIL",
        )
        passing = dict(degraded_observation, assertion_status="PASS")
        self.assertEqual(expected_outcome(passing, probes["P001_META"]), "PASS")
        transport_failure = dict(passing, http_status=500)
        self.assertEqual(expected_outcome(transport_failure, probes["P001_META"]), "FAIL")

    def test_xml_structure_fields_are_explicitly_allowed(self) -> None:
        expected = {
            "xml_child_tags",
            "xml_contents_count",
            "xml_error_code",
            "xml_is_truncated",
            "xml_key_count",
            "xml_root",
            "xml_sample_key_sha256",
        }
        self.assertTrue(expected.issubset(ALLOWED_OBSERVATION_FIELDS))

    def test_authorizations_fail_closed(self) -> None:
        with self.assertRaises(EvidenceError):
            require_false_authorizations(
                {
                    "integration_authorized": False,
                    "paper_authorized": False,
                    "shadow_authorized": False,
                    "live_authorized": False,
                    "leverage_authorized": True,
                    "capital_allocation_authorized": False,
                },
                "mutation",
            )

    def test_wrapper_has_no_network_or_execution_implementation(self) -> None:
        wrapper = (
            ROOT / "research/wallet_copyability/scripts/probe_public_api_r2.py"
        ).read_text(encoding="utf-8")
        self.assertIn("probe_public_api.py", wrapper)
        self.assertIn("module.validate_contract = validate_contract_r2", wrapper)
        for forbidden in (
            "urllib.request",
            "api.hyperliquid.xyz/exchange",
            "Authorization",
            "privateKey",
            "secretKey",
            "sign_l1_action",
            "market_open",
        ):
            self.assertNotIn(forbidden, wrapper)


if __name__ == "__main__":
    unittest.main()
