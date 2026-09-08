from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

from src.live_data.schema import SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/wallet_copyability/live_data"
PREREG = BASE / "L1_LIVE_DATA_COLLECTION_PREREGISTRATION.json"
APPROVAL_TEXT = BASE / "APPROVE_HL_LIVE_DATA_COLLECTION_L1_001.txt"
DECISION = BASE / "L1_OWNER_DECISION_001.json"
APPROVAL_TEMPLATE = BASE / "HUMAN_APPROVAL_TEMPLATE.md"
STATUS = BASE / "STATUS.md"
VALIDATOR = ROOT / "governance/validate_l1_live_data_preregistration.py"

SPEC = importlib.util.spec_from_file_location("validate_l1_live_data_preregistration", VALIDATOR)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)

APPROVAL_SHA256 = "d87df45cd8b0afa597f8ee0848b6f75baf4ca79b0dcd59c2bb4b9fd3b5dede1b"
BOUND_COMMIT = "e3610cd494211f6a399caffd7741a2f526b3287a"


def load(path: Path = PREREG) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class L1PreregistrationTests(unittest.TestCase):
    def test_the_preregistration_itself_created_nothing(self) -> None:
        c = load()
        self.assertEqual(c["pilot_id"], "HL-LIVE-DATA-COLLECTION-L1-001")
        self.assertEqual(c["status"], "PREREGISTERED_NO_EXECUTION")
        created = c["created_by_this_preregistration"]
        self.assertEqual(created["network_requests_executed"], 0)
        self.assertEqual(created["database_rows_written"], 0)
        self.assertFalse(created["market_data_ingested"])
        self.assertIsNone(created["empirical_result"])
        self.assertFalse(c["governance_gates"]["manual_operator_run_authorized"])

    def test_envelope_is_free_and_bounded(self) -> None:
        e = load()["proposed_request_envelope"]
        self.assertEqual(e["maximum_one_time_budget_eur"], 0)
        self.assertEqual(e["maximum_monthly_budget_eur"], 0)
        self.assertEqual(e["enforced_weight_budget_per_minute"], 1200)
        self.assertEqual(e["maximum_retries_per_request"], 3)
        self.assertEqual(e["retryable_http_statuses"], [429])
        self.assertTrue(e["retries_charged_against_weight_budget"])
        self.assertEqual(e["maximum_tracked_wallets"], 10)
        self.assertEqual(e["default_maximum_watch_iterations"], 1000)
        self.assertFalse(e["http_redirect_following_authorized"])
        self.assertEqual(e["worst_case_snapshot_weight_per_minute"], 20)

    def test_read_only_boundary_and_no_venue_write_path(self) -> None:
        b = load()["read_only_boundary"]
        self.assertTrue(b["read_only"])
        for key in (
            "exchange_credentials_allowed", "wallet_private_keys_allowed", "signed_actions_allowed",
            "order_endpoint_allowed", "order_submission_allowed", "live_orders_allowed",
            "paper_orders_allowed", "write_path_present_in_codebase",
        ):
            self.assertFalse(b[key], key)
        for path in sorted((ROOT / "src/live_data").glob("*.py")):
            self.assertNotIn("/exchange", path.read_text(encoding="utf-8"), path.name)

    def test_scope_is_public_and_shares_nothing_with_the_archive_track(self) -> None:
        c = load()
        target = c["exact_network_target"]
        self.assertEqual(target["rest_base_url"], "https://api.hyperliquid.xyz")
        self.assertEqual(target["rest_path_allowlist"], ["/info"])
        self.assertEqual(target["websocket_url"], "wss://api.hyperliquid.xyz/ws")
        for key in ("authentication_required", "requester_pays", "aws_involved", "cloud_credentials_involved"):
            self.assertFalse(target[key], key)
        self.assertFalse(c["parent_bindings"]["archive_track_dependency"])

    def test_downstream_and_trading_authorizations_remain_closed(self) -> None:
        c = load()
        self.assertTrue(all(v is False for v in c["downstream_authorizations"].values()))
        self.assertTrue(all(v is False for v in c["trading_authorizations"].values()))

    def test_retained_schema_names_the_tape(self) -> None:
        schema = load()["retained_schema"]
        # The L1 declaration is historical and stays at its own version; the
        # code sits one version ahead under the DEC-043 schema widening.
        self.assertEqual(schema["schema_version"], 3)
        self.assertIn("trades", schema["tables"])
        self.assertLessEqual(set(schema["tables"]), validator.created_table_names())
        self.assertEqual(SCHEMA_VERSION, 4)
        self.assertEqual(validator.retained_schema_widening()["schema_version"], SCHEMA_VERSION)
        self.assertEqual(validator.retained_schema_widening()["tables"], ("candles",))
        self.assertFalse(schema["raw_response_bodies_retained"])

    def test_deterministic_core_really_has_no_network_or_process_imports(self) -> None:
        forbidden = set(load()["layering_boundary"]["forbidden_core_import_roots"])
        self.assertTrue({"urllib", "socket", "subprocess"} <= forbidden)
        roots: set[str] = set()
        for path in sorted((ROOT / "src/live_data").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots |= {alias.name.split(".", 1)[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    roots.add(node.module.split(".", 1)[0])
        self.assertEqual(roots & forbidden, set(), f"core reaches the network via {roots & forbidden}")


class L1OwnerDecisionTests(unittest.TestCase):
    def test_the_approval_text_is_retained_byte_exactly(self) -> None:
        raw = APPROVAL_TEXT.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), APPROVAL_SHA256)
        self.assertNotIn(b"\r", raw)
        self.assertTrue(raw.endswith(b"\n") and not raw.endswith(b"\n\n"))
        lines = raw.decode("utf-8").splitlines()
        self.assertEqual(len(lines), 27)
        self.assertEqual(lines[0], "APPROVE_HL_LIVE_DATA_COLLECTION_L1_001")
        self.assertIn(f"preregistration_commit={BOUND_COMMIT}", lines)
        self.assertIn("trading_authorizations=ALL_FALSE", lines)

    def test_the_contract_records_the_approval_and_the_decision(self) -> None:
        approval = load()["owner_approval_status"]
        self.assertTrue(approval["approval_present"])
        self.assertEqual(approval["approval_text_sha256"], APPROVAL_SHA256)
        self.assertEqual(approval["bound_preregistration_commit"], BOUND_COMMIT)
        self.assertEqual(approval["approval_timestamp_utc"], "2026-09-03")
        self.assertEqual(
            approval["owner_decision_path"],
            "research/wallet_copyability/live_data/L1_OWNER_DECISION_001.json",
        )

    def test_one_decision_grants_exactly_three_gates_without_precedent(self) -> None:
        d = load(DECISION)
        self.assertEqual(d["decision_id"], "L1-OWNER-DECISION-001")
        self.assertEqual(d["canonical_text"]["sha256"], APPROVAL_SHA256)
        self.assertEqual(d["bound_preregistration_commit"], BOUND_COMMIT)
        self.assertEqual(
            d["gates_granted_in_this_decision"],
            ["OWNER_APPROVAL", "IMPLEMENTATION_REVIEW", "SINGLE_USE_EXECUTION_RELEASE"],
        )
        precedent = d["precedent"]
        self.assertTrue(precedent["applies_only_to_this_envelope"])
        self.assertFalse(precedent["precedent_for_archive_track"])
        self.assertFalse(precedent["precedent_for_any_scope_that_costs_money"])
        self.assertFalse(precedent["precedent_for_any_scope_that_requires_authentication"])
        self.assertFalse(precedent["precedent_for_any_scope_that_trades"])
        self.assertTrue(d["risk_policy"]["integration_remains_false"])
        self.assertTrue(all(v is False for v in d["trading_authorizations"].values()))

    def test_the_release_is_single_use_and_never_reruns(self) -> None:
        release = load(DECISION)["execution_release"]
        self.assertEqual(release["release_id"], "RELEASE_HL_LIVE_DATA_COLLECTION_L1_001")
        self.assertTrue(release["single_use"])
        self.assertFalse(release["rerun_authorized"])
        self.assertFalse(release["database_committed"])
        self.assertIn(release["status"], {"RELEASED_NOT_YET_CONSUMED", "CONSUMED"})
        if release["status"] == "CONSUMED":
            self.assertTrue((ROOT / release["evidence_path"]).is_file())
        else:
            self.assertIsNone(release["evidence_path"])

    def test_risk_policy_integration_is_still_false(self) -> None:
        text = (ROOT / "RISK_POLICY.md").read_text(encoding="utf-8")
        self.assertIn("| integration | `false` |", text)
        self.assertIn("| historical/public research | `true` |", text)

    def test_approval_template_stays_a_template(self) -> None:
        text = APPROVAL_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("preregistration_commit=<PREREGISTRATION_COMMIT>", text)
        self.assertNotIn(BOUND_COMMIT, text)

    def test_no_database_is_committed(self) -> None:
        self.assertFalse((ROOT / "research/live_data").exists())
        self.assertEqual([p for p in BASE.rglob("*.sqlite3")], [])

    def test_validator_passes(self) -> None:
        self.assertEqual(validator.main(), 0)


class L1ValidatorRejectsDriftTests(unittest.TestCase):
    """The validator is only worth having if it fails on a widened envelope."""

    def _reject_mutated(self, path: Path, mutate) -> None:
        contract = load(path)
        mutate(contract)
        original = path.read_bytes()
        path.write_bytes((json.dumps(contract, indent=2) + "\n").encode("utf-8"))
        try:
            with self.assertRaises(SystemExit) as caught:
                validator.main()
            self.assertIn("L1_PREREGISTRATION_INVALID", str(caught.exception))
        finally:
            path.write_bytes(original)
        self.assertEqual(validator.main(), 0)

    def _reject(self, mutate) -> None:
        self._reject_mutated(PREREG, mutate)

    def _reject_decision(self, mutate) -> None:
        self._reject_mutated(DECISION, mutate)

    def _reject_approval_text(self, replacement: bytes) -> None:
        original = APPROVAL_TEXT.read_bytes()
        APPROVAL_TEXT.write_bytes(replacement)
        try:
            with self.assertRaises(SystemExit):
                validator.main()
        finally:
            APPROVAL_TEXT.write_bytes(original)
        self.assertEqual(validator.main(), 0)

    # -- approval and decision -------------------------------------------------------

    def test_rejects_a_recorded_hash_that_does_not_match_the_retained_text(self) -> None:
        self._reject(lambda c: c["owner_approval_status"].update(approval_text_sha256="0" * 64))

    def test_rejects_a_bound_commit_that_differs_from_the_signed_line(self) -> None:
        self._reject(lambda c: c["owner_approval_status"].update(bound_preregistration_commit="f" * 40))

    def test_rejects_an_approval_text_whose_envelope_line_was_widened(self) -> None:
        raw = APPROVAL_TEXT.read_bytes()
        self._reject_approval_text(raw.replace(b"maximum_tracked_wallets=10", b"maximum_tracked_wallets=50"))

    def test_rejects_an_approval_text_with_a_widened_request_type_list(self) -> None:
        raw = APPROVAL_TEXT.read_bytes()
        self._reject_approval_text(raw.replace(b"userFunding\n", b"userFunding,l2Book\n"))

    def test_rejects_an_approval_text_that_opens_trading(self) -> None:
        raw = APPROVAL_TEXT.read_bytes()
        self._reject_approval_text(raw.replace(b"trading_authorizations=ALL_FALSE", b"trading_authorizations=paper"))

    def test_rejects_an_approval_text_with_crlf_endings(self) -> None:
        self._reject_approval_text(APPROVAL_TEXT.read_bytes().replace(b"\n", b"\r\n"))

    def test_rejects_a_decision_that_grants_a_fourth_gate(self) -> None:
        self._reject_decision(lambda d: d["gates_granted_in_this_decision"].append("SCHEDULED_EXECUTION"))

    def test_rejects_a_decision_that_claims_precedent(self) -> None:
        self._reject_decision(lambda d: d["precedent"].update(precedent_for_archive_track=True))

    def test_rejects_a_rerunnable_release(self) -> None:
        self._reject_decision(lambda d: d["execution_release"].update(rerun_authorized=True))

    def test_rejects_a_consumed_release_without_evidence(self) -> None:
        self._reject_decision(
            lambda d: d["execution_release"].update(status="CONSUMED", evidence_path=None, consumed_by="x")
        )

    def test_rejects_a_committed_database_claim(self) -> None:
        self._reject_decision(lambda d: d["execution_release"].update(database_committed=True))

    # -- session evidence ------------------------------------------------------------

    EVIDENCE = BASE / "evidence/L1_SESSION_001.json"

    def _reject_evidence(self, mutate) -> None:
        self._reject_mutated(self.EVIDENCE, mutate)

    def _watch_steps(self, evidence: dict) -> list[dict]:
        steps = [c for c in evidence["commands"] if c["command"].startswith("watch")]
        self.assertTrue(steps, "fixture has no watch command to mutate")
        return steps

    def test_rejects_a_watch_that_omits_its_iteration_cap(self) -> None:
        """`command.get("max_iterations", 0) <= 1000` let a watch with no
        recorded cap through: the default of 0 satisfied the bound."""
        self._reject_evidence(lambda e: self._watch_steps(e)[0].pop("max_iterations"))

    def test_rejects_a_watch_over_the_iteration_cap(self) -> None:
        self._reject_evidence(lambda e: self._watch_steps(e)[0].update(max_iterations=1001))

    def test_rejects_a_non_integer_iteration_cap_as_a_validation_error(self) -> None:
        """A string cap used to raise TypeError from the comparison instead of
        the validator's own exit; a boolean is not an integer either."""
        self._reject_evidence(lambda e: self._watch_steps(e)[0].update(max_iterations="1000"))
        self._reject_evidence(lambda e: self._watch_steps(e)[0].update(max_iterations=True))

    def test_a_non_watch_command_may_omit_the_iteration_cap(self) -> None:
        evidence = load(self.EVIDENCE)
        self.assertTrue(any("max_iterations" not in c for c in evidence["commands"]))
        self.assertEqual(validator.main(), 0)

    # -- envelope versus code -------------------------------------------------------

    def test_rejects_an_opened_trading_authorization(self) -> None:
        self._reject(lambda c: c["trading_authorizations"].update(paper_authorized=True))

    def test_rejects_an_opened_budget(self) -> None:
        self._reject(lambda c: c["proposed_request_envelope"].update(maximum_one_time_budget_eur=5))

    def test_rejects_a_weight_budget_that_does_not_match_the_code(self) -> None:
        self._reject(lambda c: c["proposed_request_envelope"].update(enforced_weight_budget_per_minute=5000))

    def test_rejects_a_wallet_cap_that_does_not_match_the_code(self) -> None:
        self._reject(lambda c: c["proposed_request_envelope"].update(maximum_tracked_wallets=250))

    def test_rejects_an_undeclared_rest_request_type(self) -> None:
        self._reject(lambda c: c["rest_request_type_allowlist"].append("l2Book"))

    def test_the_widening_only_covers_types_the_l2_approval_names(self) -> None:
        """``candleSnapshot`` passes because DEC-043's approval names it, nothing else.

        With the parsed additional set emptied, the code supports a type no
        approval covers and the validator must refuse it. That is what makes
        the widening a reading of a signed document rather than a hole.
        """
        self.assertIn("candleSnapshot", validator.additional_rest_request_types())
        original = validator.additional_rest_request_types
        validator.additional_rest_request_types = lambda: set()
        try:
            with self.assertRaises(SystemExit) as caught:
                validator.main()
            self.assertIn("L1_PREREGISTRATION_INVALID", str(caught.exception))
        finally:
            validator.additional_rest_request_types = original
        self.assertEqual(validator.main(), 0)

    def test_a_table_outside_the_enumerated_widening_is_refused(self) -> None:
        """The widening admits the candles table only, not any table the code grows."""
        original = validator.created_table_names
        validator.created_table_names = lambda: original() | {"orders"}
        try:
            with self.assertRaises(SystemExit) as caught:
                validator.main()
            self.assertIn("L1_PREREGISTRATION_INVALID", str(caught.exception))
        finally:
            validator.created_table_names = original
        self.assertEqual(validator.main(), 0)

    def test_the_schema_widening_is_what_admits_version_four(self) -> None:
        original = validator.L2_RETAINED_SCHEMA_WIDENING
        validator.L2_RETAINED_SCHEMA_WIDENING = {}
        try:
            with self.assertRaises(SystemExit) as caught:
                validator.main()
            self.assertIn("L1_PREREGISTRATION_INVALID", str(caught.exception))
        finally:
            validator.L2_RETAINED_SCHEMA_WIDENING = original
        self.assertEqual(validator.main(), 0)

    def test_the_widening_reads_the_approval_line_from_the_l2_text(self) -> None:
        text = validator.L2_APPROVAL_TEXT.read_text(encoding="utf-8")
        self.assertIn("additional_rest_request_types=candleSnapshot", text)

    def test_rejects_a_claimed_executed_request(self) -> None:
        self._reject(lambda c: c["created_by_this_preregistration"].update(rest_requests_executed=1))

    def test_rejects_runtime_authority_inside_the_preregistration(self) -> None:
        self._reject(lambda c: c["governance_gates"].update(manual_operator_run_authorized=True))

    def test_rejects_an_installed_workflow_authorization(self) -> None:
        self._reject(lambda c: c["governance_gates"].update(workflow_installation_authorized=True))

    def test_rejects_a_dropped_top_level_key(self) -> None:
        self._reject(lambda c: c.pop("stop_conditions"))

    def test_rejects_a_core_path_pointing_at_the_transport_layer(self) -> None:
        self._reject(
            lambda c: c["layering_boundary"].update(
                deterministic_core_path="research/wallet_copyability/live_data_collector"
            )
        )

    def test_rejects_a_storage_schema_version_that_does_not_match_the_code(self) -> None:
        self._reject(lambda c: c["retained_schema"].update(schema_version=99))

    def test_rejects_an_undeclared_storage_table(self) -> None:
        self._reject(lambda c: c["retained_schema"].update(tables=[t for t in c["retained_schema"]["tables"] if t != "trades"]))


if __name__ == "__main__":
    unittest.main()
