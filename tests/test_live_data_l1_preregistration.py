from __future__ import annotations

import ast
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/wallet_copyability/live_data"
PREREG = BASE / "L1_LIVE_DATA_COLLECTION_PREREGISTRATION.json"
APPROVAL_TEMPLATE = BASE / "HUMAN_APPROVAL_TEMPLATE.md"
STATUS = BASE / "STATUS.md"
VALIDATOR = ROOT / "governance/validate_l1_live_data_preregistration.py"

SPEC = importlib.util.spec_from_file_location("validate_l1_live_data_preregistration", VALIDATOR)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def load() -> dict:
    return json.loads(PREREG.read_text(encoding="utf-8"))


class L1PreregistrationTests(unittest.TestCase):
    def test_pilot_is_preregistered_and_unexecuted(self) -> None:
        c = load()
        self.assertEqual(c["pilot_id"], "HL-LIVE-DATA-COLLECTION-L1-001")
        self.assertEqual(c["status"], "PREREGISTERED_NO_EXECUTION")
        self.assertEqual(c["study_id"], "WALLET-COPYABILITY-STUDY-001")
        created = c["created_by_this_preregistration"]
        self.assertEqual(created["network_requests_executed"], 0)
        self.assertEqual(created["rest_requests_executed"], 0)
        self.assertEqual(created["websocket_connections_opened"], 0)
        self.assertEqual(created["database_rows_written"], 0)
        self.assertFalse(created["market_data_ingested"])
        self.assertIsNone(created["empirical_result"])

    def test_no_owner_approval_or_release_exists(self) -> None:
        c = load()
        approval = c["owner_approval_status"]
        self.assertEqual(approval["approval_id"], "APPROVE_HL_LIVE_DATA_COLLECTION_L1_001")
        self.assertFalse(approval["approval_present"])
        self.assertIsNone(approval["approval_text_sha256"])
        self.assertIsNone(approval["approval_timestamp_utc"])
        self.assertIsNone(approval["bound_preregistration_commit"])
        self.assertFalse((BASE / "L1_EXECUTION_RELEASE.json").exists())
        self.assertFalse((BASE / "evidence").exists())
        self.assertFalse((BASE / "outputs").exists())

    def test_execution_gates_are_closed(self) -> None:
        gates = load()["governance_gates"]
        self.assertTrue(gates["owner_approval_required_before_execution"])
        self.assertTrue(gates["single_use_release_required_before_execution"])
        self.assertTrue(gates["canonical_implementation_merge_is_not_execution_release"])
        self.assertTrue(gates["exact_head_ci_required_before_merge"])
        self.assertFalse(gates["workflow_installation_authorized"])
        self.assertFalse(gates["scheduled_or_unattended_execution_authorized"])
        self.assertFalse(gates["manual_operator_run_authorized"])

    def test_envelope_is_free_and_bounded(self) -> None:
        e = load()["proposed_request_envelope"]
        self.assertEqual(e["maximum_one_time_budget_eur"], 0)
        self.assertEqual(e["maximum_monthly_budget_eur"], 0)
        self.assertEqual(e["enforced_weight_budget_per_minute"], 1200)
        self.assertEqual(e["maximum_retries_per_request"], 3)
        self.assertEqual(e["retryable_http_statuses"], [429])
        self.assertTrue(e["retries_charged_against_weight_budget"])
        self.assertEqual(e["maximum_tracked_wallets"], 10)
        self.assertEqual(e["default_snapshot_interval_seconds"], 60.0)
        self.assertEqual(e["websocket_heartbeat_seconds"], 50.0)
        self.assertEqual(e["websocket_server_timeout_seconds"], 60.0)
        self.assertEqual(e["default_maximum_watch_iterations"], 1000)
        self.assertEqual(e["maximum_fills_per_response"], 500)
        self.assertFalse(e["http_redirect_following_authorized"])
        self.assertEqual(e["worst_case_snapshot_weight_per_minute"], 20)

    def test_read_only_boundary_and_no_venue_write_path(self) -> None:
        b = load()["read_only_boundary"]
        self.assertTrue(b["read_only"])
        for key in (
            "exchange_credentials_allowed",
            "wallet_private_keys_allowed",
            "signed_actions_allowed",
            "order_endpoint_allowed",
            "order_submission_allowed",
            "live_orders_allowed",
            "paper_orders_allowed",
            "write_path_present_in_codebase",
        ):
            self.assertFalse(b[key], key)
        self.assertTrue(b["write_path_absence_is_structural"])
        for path in sorted((ROOT / "src/live_data").glob("*.py")):
            self.assertNotIn("/exchange", path.read_text(encoding="utf-8"), path.name)

    def test_scope_is_public_and_shares_nothing_with_the_archive_track(self) -> None:
        c = load()
        target = c["exact_network_target"]
        self.assertEqual(target["rest_base_url"], "https://api.hyperliquid.xyz")
        self.assertEqual(target["rest_path_allowlist"], ["/info"])
        self.assertEqual(target["websocket_url"], "wss://api.hyperliquid.xyz/ws")
        self.assertFalse(target["authentication_required"])
        self.assertFalse(target["requester_pays"])
        self.assertFalse(target["aws_involved"])
        self.assertFalse(target["cloud_credentials_involved"])
        parent = c["parent_bindings"]
        self.assertFalse(parent["archive_track_dependency"])
        self.assertFalse(parent["blocked_by_r11_unresolved"])

    def test_downstream_and_trading_authorizations_remain_closed(self) -> None:
        c = load()
        self.assertTrue(all(v is False for v in c["downstream_authorizations"].values()))
        self.assertTrue(all(v is False for v in c["trading_authorizations"].values()))
        self.assertEqual(
            set(c["trading_authorizations"]),
            {
                "capital_allocation_authorized",
                "integration_authorized",
                "leverage_authorized",
                "live_authorized",
                "paper_authorized",
                "shadow_authorized",
            },
        )

    def test_approval_template_is_exact_and_unsigned(self) -> None:
        text = APPROVAL_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("APPROVE_HL_LIVE_DATA_COLLECTION_L1_001", text)
        self.assertIn("preregistration_commit=<PREREGISTRATION_COMMIT>", text)
        self.assertIn("maximum_one_time_budget_eur=0", text)
        self.assertIn("trading_authorizations=ALL_FALSE", text)
        # The template must stay a template: no approval may be pre-filled.
        self.assertNotIn("approval_text_sha256=", text)

    def test_status_reports_no_execution(self) -> None:
        text = STATUS.read_text(encoding="utf-8")
        self.assertIn("`PREREGISTERED_NO_EXECUTION`", text)
        self.assertIn("| owner approval | `NOT_PRESENT` |", text)
        self.assertIn("| REST requests executed | `0` |", text)

    def test_project_state_records_the_l1_boundary(self) -> None:
        text = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
        for token in (
            "`HL-LIVE-DATA-COLLECTION-L1-001`",
            "l1_owner_approval_present = false",
            "l1_execution_release_present = false",
            "l1_workflow_installed = false",
            "l1_rest_requests_executed = 0",
            "l1_websocket_connections_opened = 0",
            "l1_maximum_one_time_budget_eur = 0",
        ):
            self.assertIn(token, text, token)

    def test_validator_passes(self) -> None:
        self.assertEqual(validator.main(), 0)


class L1ValidatorRejectsDriftTests(unittest.TestCase):
    """The validator is only worth having if it fails on a widened envelope."""

    def _reject(self, mutate) -> None:
        contract = load()
        mutate(contract)
        original = PREREG.read_bytes()
        PREREG.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
        try:
            with self.assertRaises(SystemExit) as caught:
                validator.main()
            self.assertIn("L1_PREREGISTRATION_INVALID", str(caught.exception))
        finally:
            PREREG.write_bytes(original)
        self.assertEqual(validator.main(), 0)

    def test_rejects_a_prefilled_owner_approval(self) -> None:
        self._reject(lambda c: c["owner_approval_status"].update(approval_present=True))

    def test_rejects_an_opened_trading_authorization(self) -> None:
        self._reject(lambda c: c["trading_authorizations"].update(paper_authorized=True))

    def test_rejects_an_opened_budget(self) -> None:
        self._reject(lambda c: c["proposed_request_envelope"].update(maximum_one_time_budget_eur=5))

    def test_rejects_a_weight_budget_that_does_not_match_the_code(self) -> None:
        self._reject(
            lambda c: c["proposed_request_envelope"].update(enforced_weight_budget_per_minute=5000)
        )

    def test_rejects_a_wallet_cap_that_does_not_match_the_code(self) -> None:
        self._reject(lambda c: c["proposed_request_envelope"].update(maximum_tracked_wallets=250))

    def test_rejects_an_undeclared_rest_request_type(self) -> None:
        def mutate(contract: dict) -> None:
            contract["rest_request_type_allowlist"] = contract["rest_request_type_allowlist"] + [
                "l2Book"
            ]

        self._reject(mutate)

    def test_rejects_a_claimed_executed_request(self) -> None:
        self._reject(lambda c: c["created_by_this_preregistration"].update(rest_requests_executed=1))

    def test_rejects_a_disabled_release_gate(self) -> None:
        self._reject(
            lambda c: c["governance_gates"].update(single_use_release_required_before_execution=False)
        )

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
        def mutate(contract: dict) -> None:
            contract["retained_schema"]["tables"] = [
                table for table in contract["retained_schema"]["tables"] if table != "funding"
            ]

        self._reject(mutate)

    def test_deterministic_core_really_has_no_network_or_process_imports(self) -> None:
        forbidden = set(load()["layering_boundary"]["forbidden_core_import_roots"])
        self.assertIn("urllib", forbidden)
        self.assertIn("socket", forbidden)
        self.assertIn("subprocess", forbidden)
        roots: set[str] = set()
        for path in sorted((ROOT / "src/live_data").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots |= {alias.name.split(".", 1)[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    roots.add(node.module.split(".", 1)[0])
        self.assertEqual(roots & forbidden, set(), f"core reaches the network via {roots & forbidden}")


if __name__ == "__main__":
    unittest.main()
