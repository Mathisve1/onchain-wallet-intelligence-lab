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


#: The L2 approval texts, pinned the way APPROVAL_SHA256 pins L1's. A change to
#: an approval and its decision row in one edit passes the validator, which
#: binds one against the other; it does not pass these, so the diff a reviewer
#: reads has to touch a test constant too. That is the point of the literals.
TWO_ARM_SHA256 = "3ac5e20aac54837419743c2f094578418f2eacb7601b164e17108f874694a8b4"
ARM_A_WINDOW_SHA256 = "df082701ec412fcb112660f125b37ace095180a2cefdd00051f7896ee08ecc96"
FORWARD_STUDY_SHA256 = "7caa6b249fdf28dda63d91595acb77948a8884cf52178eac81f9b5faab373deb"
RETAINED_APPROVALS = {
    "APPROVE_HL_LIVE_DATA_COLLECTION_L1_001": APPROVAL_SHA256,
    "APPROVE_HL_LIVE_DATA_L2_FORWARD_STUDY_001": FORWARD_STUDY_SHA256,
    "APPROVE_HL_LIVE_DATA_L2_TWO_ARM_STUDY_001": TWO_ARM_SHA256,
    "APPROVE_HL_LIVE_DATA_L2_ARM_A_WINDOW_001": ARM_A_WINDOW_SHA256,
}


class ApprovalsBoundToTheDecisionLogTests(unittest.TestCase):
    """DEC-045's known issue: an approval text nothing binds is a text an edit can widen.

    The L2 approval's own ``additional_rest_request_types=`` line decides which
    request types the collector may make and which schema widening is retained,
    so a silent edit to it is a silent widening.

    Most cases here assert the guard directly rather than through ``main()``. A
    malformed decision row should fail these two or three tests by name, not
    every test in the module that happens to call the validator.
    """

    L2_APPROVAL = BASE / "APPROVE_HL_LIVE_DATA_L2_TWO_ARM_STUDY_001.txt"
    ARM_A_APPROVAL = BASE / "APPROVE_HL_LIVE_DATA_L2_ARM_A_WINDOW_001.txt"
    DECISION_LOG = ROOT / "DECISION_LOG.md"

    @staticmethod
    def sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def assert_guard_refuses(self, edits: dict, *, expect: str) -> None:
        """Mutate real files, assert the guard refuses, and always restore them."""
        originals = {path: (path.read_bytes() if path.exists() else None) for path in edits}
        try:
            for path, content in edits.items():
                path.write_bytes(content)
            with self.assertRaises(validator.ValidationError) as caught:
                validator.validate_approvals_match_their_record()
            self.assertIn(expect, str(caught.exception))
        finally:
            for path, original in originals.items():
                if original is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(original)
        validator.validate_approvals_match_their_record()

    @staticmethod
    def row(dec: str, text: str, status: str = "accepted") -> bytes:
        return f"| {dec} | 2026-01-01 | {status} | {text} |\n".encode("utf-8")

    def test_every_retained_approval_hashes_to_its_pinned_literal(self) -> None:
        on_disk = {path.stem: path for path in BASE.glob("APPROVE_*.txt")}
        # A new approval is added deliberately, with its literal, or this fails.
        self.assertEqual(set(on_disk), set(RETAINED_APPROVALS),
                         "the set of retained approvals changed: add the new one to RETAINED_APPROVALS above "
                         "with its SHA-256, or remove the one that went")
        for approval_id, expected in RETAINED_APPROVALS.items():
            with self.subTest(approval=approval_id):
                self.assertEqual(self.sha256(on_disk[approval_id]), expected)

    def test_the_log_binds_every_retained_approval_to_that_same_hash(self) -> None:
        bindings = validator.recorded_approval_hashes()
        for approval_id, expected in RETAINED_APPROVALS.items():
            with self.subTest(approval=approval_id):
                self.assertIn(approval_id, bindings, "no accepted row binds this approval")
                recorded, row = bindings[approval_id]
                self.assertEqual(recorded, expected)
                self.assertRegex(row, r"^DEC-\d{3}$")
        self.assertEqual(validator.validate_approvals_match_their_record(), len(RETAINED_APPROVALS))

    def test_an_edit_to_the_l2_approval_is_refused_rather_than_obeyed(self) -> None:
        # The line the collector's request-type scope and retained schema hang on.
        raw = self.L2_APPROVAL.read_bytes()
        self.assertIn(b"additional_rest_request_types=candleSnapshot\n", raw)
        self.assertEqual(validator.additional_rest_request_types(), {"candleSnapshot"})
        self.assert_guard_refuses(
            {self.L2_APPROVAL: raw.replace(b"additional_rest_request_types=candleSnapshot\n",
                                           b"additional_rest_request_types=candleSnapshot,l2Book\n")},
            expect="not the one the owner approved")

    def test_a_narrowed_approval_is_refused_too_so_the_record_cannot_drift_either_way(self) -> None:
        raw = self.L2_APPROVAL.read_bytes()
        self.assert_guard_refuses(
            {self.L2_APPROVAL: raw.replace(b"maximum_candidate_wallets=600\n", b"maximum_candidate_wallets=300\n")},
            expect="not the one the owner approved")

    def test_a_second_row_cannot_re_authorise_a_rewritten_approval(self) -> None:
        # The substitution the first draft of this guard allowed: leave DEC-044
        # untouched and append a row recording the rewritten text's hash.
        rewritten = self.ARM_A_APPROVAL.read_bytes().replace(b"decisive_arm=B\n", b"decisive_arm=A\n")
        self.assertNotEqual(rewritten, self.ARM_A_APPROVAL.read_bytes())
        fresh = hashlib.sha256(rewritten).hexdigest()
        self.assert_guard_refuses(
            {self.ARM_A_APPROVAL: rewritten,
             self.DECISION_LOG: self.DECISION_LOG.read_bytes() + self.row(
                 "DEC-990", f"`APPROVE_HL_LIVE_DATA_L2_ARM_A_WINDOW_001` SHA-256 `{fresh}`")},
            expect="One approval has one hash")

    def test_a_binding_written_where_it_would_not_be_read_is_refused_not_ignored(self) -> None:
        """Hiding a binding must fail, because ignoring it is what made hiding work.

        Both rounds of review walked the same path: put the re-authorising hash
        somewhere the parser looks away from, and the rendered log is unchanged.
        So anything carrying an approval name beside a SHA-256 has to be a real
        row of the table, wherever it sits.
        """
        rewritten = self.ARM_A_APPROVAL.read_bytes().replace(b"decisive_arm=B\n", b"decisive_arm=A\n")
        fresh = hashlib.sha256(rewritten).hexdigest()
        binding = f"`APPROVE_HL_LIVE_DATA_L2_ARM_A_WINDOW_001` SHA-256 `{fresh}`"
        log = self.DECISION_LOG.read_bytes()
        for label, addition in (
            ("a one-line HTML comment", f"<!-- {binding} -->\n".encode("utf-8")),
            ("a multi-line HTML comment", f"<!--\n| DEC-991 | d | accepted | {binding} |\n-->\n".encode("utf-8")),
            ("a backtick fence", f"```\n| DEC-992 | d | accepted | {binding} |\n```\n".encode("utf-8")),
            ("a tilde fence", f"~~~\n| DEC-993 | d | accepted | {binding} |\n~~~\n".encode("utf-8")),
            ("a blockquote", f"> | DEC-994 | d | accepted | {binding} |\n".encode("utf-8")),
            ("an indented line", f"    | DEC-995 | d | accepted | {binding} |\n".encode("utf-8")),
            ("prose after the table", f"\nSee {binding} for the detail.\n".encode("utf-8")),
        ):
            with self.subTest(written_in=label):
                self.assert_guard_refuses({self.ARM_A_APPROVAL: rewritten, self.DECISION_LOG: log + addition},
                                          expect="is not a row of the decision table")

    def test_a_row_that_carries_a_binding_but_does_not_read_as_accepted_is_refused(self) -> None:
        """Disabling a row is the same attack from the other end.

        A status cell that renders as ``accepted`` but does not compare equal
        would stop a real row binding, leaving the approval unrecorded and the
        way clear for a second row. Each of these renders as an ordinary row.
        """
        text = self.DECISION_LOG.read_text(encoding="utf-8")
        real = "| DEC-044 | 2026-09-04 | accepted |"
        self.assertIn(real, text)
        for label, status in (
            ("a zero-width space", "accepted\u200b"),
            ("a capital letter", "Accepted"),
            ("emphasis", "**accepted**"),
        ):
            # These render as an ordinary accepted row, so they still bind: the
            # status is compared the way a reader sees it, not as it is typed.
            with self.subTest(renders_as_accepted=label):
                original = self.DECISION_LOG.read_bytes()
                try:
                    self.DECISION_LOG.write_bytes(
                        text.replace(real, f"| DEC-044 | 2026-09-04 | {status} |").encode("utf-8"))
                    self.assertEqual(
                        validator.recorded_approval_hashes()["APPROVE_HL_LIVE_DATA_L2_ARM_A_WINDOW_001"],
                        (ARM_A_WINDOW_SHA256, "DEC-044"))
                finally:
                    self.DECISION_LOG.write_bytes(original)
        for status in ("superseded", "rejected", "withdrawn"):
            # A status that reads as something else does not bind, and says so
            # rather than leaving the approval quietly unrecorded.
            with self.subTest(status=status):
                self.assert_guard_refuses(
                    {self.DECISION_LOG: text.replace(real, f"| DEC-044 | 2026-09-04 | {status} |").encode("utf-8")},
                    expect="not 'accepted'")

    def test_prose_that_names_an_approval_plainly_is_not_an_attempt_to_bind(self) -> None:
        # The refusal above is aimed at a binding written where it would not be
        # read. A note that happens to mention an approval and a hash, without
        # writing the name as the log writes a binding, is not that.
        original = self.DECISION_LOG.read_bytes()
        try:
            self.DECISION_LOG.write_bytes(
                original + f"\nThe approval APPROVE_HL_LIVE_DATA_L2_TWO_ARM_STUDY_001 was reviewed; the database "
                           f"of that session had SHA-256 `{'e' * 64}`.\n".encode("utf-8"))
            self.assertEqual(validator.validate_approvals_match_their_record(), len(RETAINED_APPROVALS))
        finally:
            self.DECISION_LOG.write_bytes(original)

    def test_a_row_the_table_does_not_contain_cannot_bind(self) -> None:
        # Wrapping a real row in a fence used to remove it from the scan, which
        # unbound it silently; now the row is still seen, and refused.
        text = self.DECISION_LOG.read_text(encoding="utf-8")
        fenced = text.replace("| DEC-044 |", "```\n| DEC-044 |", 1).replace(" |\n| DEC-045 |", " |\n```\n| DEC-045 |", 1)
        self.assertNotEqual(fenced, text)
        self.assert_guard_refuses({self.DECISION_LOG: fenced.encode("utf-8")},
                                  expect="is not a row of the decision table")

    def test_a_character_that_splits_a_line_invisibly_is_refused(self) -> None:
        # A form feed makes one physical line act as two, so a binding can be
        # injected inside an existing cell without adding a line to the file.
        text = self.DECISION_LOG.read_text(encoding="utf-8")
        injected = text.replace("| DEC-045 |", "\x0c| DEC-996 | d | accepted | x |\x0c| DEC-045 |", 1)
        self.assert_guard_refuses({self.DECISION_LOG: injected.encode("utf-8")},
                                  expect="can make one line act as several")

    def test_an_approval_text_no_row_records_is_refused(self) -> None:
        stray = BASE / "APPROVE_HL_LIVE_DATA_L2_NOT_RECORDED_001.txt"
        self.assert_guard_refuses(
            {stray: b"APPROVE_HL_LIVE_DATA_L2_NOT_RECORDED_001\nscheduled_execution_authorized=true\n"},
            expect="no accepted row in DECISION_LOG.md names this approval")

    def test_a_row_that_records_a_live_data_approval_with_no_retained_text_is_refused(self) -> None:
        self.assert_guard_refuses(
            {self.DECISION_LOG: self.DECISION_LOG.read_bytes() + self.row(
                "DEC-995", f"`APPROVE_HL_LIVE_DATA_L2_ABSENT_001`, SHA-256 `{'a' * 64}`")},
            expect="no text is retained for it")

    def test_another_track_records_its_own_approvals_without_failing_this_one(self) -> None:
        # Archive-track rows name approvals retained with that track, not here.
        original = self.DECISION_LOG.read_bytes()
        try:
            self.DECISION_LOG.write_bytes(original + self.row(
                "DEC-996", f"`APPROVE_HL_ARCHIVE_SOMETHING_001`, retained with that track, SHA-256 `{'c' * 64}`"))
            self.assertEqual(validator.validate_approvals_match_their_record(), len(RETAINED_APPROVALS))
        finally:
            self.DECISION_LOG.write_bytes(original)

    def test_a_row_naming_an_approval_without_a_hash_binds_nothing(self) -> None:
        # DEC-045 refers back to the L2 approval in prose; not a binding.
        original = self.DECISION_LOG.read_bytes()
        try:
            self.DECISION_LOG.write_bytes(original + self.row(
                "DEC-997", "This confirms `APPROVE_HL_LIVE_DATA_L2_TWO_ARM_STUDY_001` still governs."))
            bindings = validator.recorded_approval_hashes()
            self.assertEqual(bindings["APPROVE_HL_LIVE_DATA_L2_TWO_ARM_STUDY_001"][1], "DEC-043")
        finally:
            self.DECISION_LOG.write_bytes(original)

    def test_a_row_may_also_record_a_hash_that_is_not_an_approvals(self) -> None:
        # Row A of L2_OPERATOR_SESSIONS.md is completed with the session tool's
        # SHA-256; a hash no approval name introduces must not bind.
        original = self.DECISION_LOG.read_bytes()
        try:
            self.DECISION_LOG.write_bytes(original + self.row(
                "DEC-998", f"Accept the owner's exact `APPROVE_HL_LIVE_DATA_L2_TWO_ARM_STUDY_001`, SHA-256 "
                           f"`{TWO_ARM_SHA256}`. The revised tool is recorded with SHA-256 `{'d' * 64}`."))
            bindings = validator.recorded_approval_hashes()
            self.assertEqual(bindings["APPROVE_HL_LIVE_DATA_L2_TWO_ARM_STUDY_001"][0], TWO_ARM_SHA256)
            self.assertEqual(validator.validate_approvals_match_their_record(), len(RETAINED_APPROVALS))
        finally:
            self.DECISION_LOG.write_bytes(original)

    def test_the_owner_can_record_a_new_approval_and_the_validator_accepts_it(self) -> None:
        # What the owner does next, per L2_OPERATOR_SESSIONS.md: a new amending
        # approval text beside the others and a row that records it.
        text = (b"APPROVE_HL_LIVE_DATA_L2_TEST_ONLY_999\n"
                b"bound_commit=" + b"a" * 40 + b"\n"
                b"amends=APPROVE_HL_LIVE_DATA_L2_TWO_ARM_STUDY_001\n"
                b"operator=OWNER\n")
        path = BASE / "APPROVE_HL_LIVE_DATA_L2_TEST_ONLY_999.txt"
        # Never a name a real approval could occupy: this fixture is deleted at
        # the end, and an approval the owner retained must not be deletable here.
        self.assertFalse(path.exists(), "the test fixture collides with a retained approval")
        original = self.DECISION_LOG.read_bytes()
        try:
            path.write_bytes(text)
            self.DECISION_LOG.write_bytes(original + self.row(
                "DEC-999", f"Accept the owner's exact `APPROVE_HL_LIVE_DATA_L2_TEST_ONLY_999` (four lines, "
                           f"retained beside the other approvals, SHA-256 `{hashlib.sha256(text).hexdigest()}`)"))
            self.assertEqual(validator.validate_approvals_match_their_record(), len(RETAINED_APPROVALS) + 1)
        finally:
            path.unlink(missing_ok=True)
            self.DECISION_LOG.write_bytes(original)

    def test_every_approval_is_parsed_as_strictly_as_the_l1_one(self) -> None:
        raw = self.L2_APPROVAL.read_bytes()
        for label, mutation, expect in (
            ("crlf", raw.replace(b"\n", b"\r\n"), "not LF-only"),
            ("a lone CR inside a value", raw.replace(b"bound_commit=", b"bound_commit=\r"), "not LF-only"),
            ("no trailing newline", raw.rstrip(b"\n"), "exactly one LF"),
            ("two trailing newlines", raw + b"\n", "exactly one LF"),
            ("a UTF-8 BOM", b"\xef\xbb\xbf" + raw, "UTF-8 BOM"),
            ("bytes that are not UTF-8", raw + b"k=\xff\xfe\n", "not UTF-8"),
            ("wrong first line", b"NOT_THE_APPROVAL_ID\n" + raw.split(b"\n", 1)[1], "does not start with"),
            ("a line that is not key=value", raw + b"a bare sentence\n", "not key=value"),
            ("a duplicated key", raw + b"bound_commit=3edfbf3\n", "duplicate approval key"),
        ):
            with self.subTest(mutation=label):
                original = self.L2_APPROVAL.read_bytes()
                self.L2_APPROVAL.write_bytes(mutation)
                try:
                    with self.assertRaises(validator.ValidationError) as caught:
                        validator.parse_approval_file(self.L2_APPROVAL, self.L2_APPROVAL.stem)
                    self.assertIn(expect, str(caught.exception))
                finally:
                    self.L2_APPROVAL.write_bytes(original)

    def test_the_guard_itself_parses_every_approval_not_only_hashes_it(self) -> None:
        # Without the parse call in the guard, a well-hashed but malformed text
        # would pass; the hash is recomputed here so only the parse can fail.
        raw = self.L2_APPROVAL.read_bytes()
        malformed = raw + b"a bare sentence\n"
        original_log = self.DECISION_LOG.read_bytes()
        rebound = original_log.replace(TWO_ARM_SHA256.encode(), hashlib.sha256(malformed).hexdigest().encode())
        self.assert_guard_refuses({self.L2_APPROVAL: malformed, self.DECISION_LOG: rebound},
                                  expect="not key=value")

    def test_the_l2_request_type_scope_is_read_through_the_strict_parser(self) -> None:
        raw = self.L2_APPROVAL.read_bytes()
        original = self.L2_APPROVAL.read_bytes()
        try:
            self.L2_APPROVAL.write_bytes(raw.replace(b"\n", b"\r\n"))
            with self.assertRaises(validator.ValidationError):
                validator.additional_rest_request_types()
        finally:
            self.L2_APPROVAL.write_bytes(original)
        self.assertEqual(validator.additional_rest_request_types(), {"candleSnapshot"})

    def test_the_whole_hash_is_compared_not_a_prefix(self) -> None:
        raw = self.L2_APPROVAL.read_bytes()
        original_log = self.DECISION_LOG.read_bytes()
        # A recorded hash that shares its first 32 characters with the real one.
        near_miss = TWO_ARM_SHA256[:32] + ("0" * 32)
        self.assertNotEqual(near_miss, TWO_ARM_SHA256)
        self.assert_guard_refuses(
            {self.DECISION_LOG: original_log.replace(TWO_ARM_SHA256.encode(), near_miss.encode())},
            expect="not the one the owner approved")
        self.assertEqual(len(raw), len(self.L2_APPROVAL.read_bytes()))

    def test_the_l1_approval_keeps_its_own_binding_as_well(self) -> None:
        raw = APPROVAL_TEXT.read_bytes()
        self.assert_guard_refuses(
            {APPROVAL_TEXT: raw.replace(b"maximum_watch_iterations=1000", b"maximum_watch_iterations=100000")},
            expect="not the one the owner approved")


    def test_the_validator_itself_refuses_a_tampered_approval(self) -> None:
        # The one case that goes through main(): without it, removing the call
        # from the entry point would leave every other test here still green.
        raw = self.L2_APPROVAL.read_bytes()
        original = self.L2_APPROVAL.read_bytes()
        try:
            self.L2_APPROVAL.write_bytes(raw.replace(b"maximum_candidate_wallets=600\n",
                                                     b"maximum_candidate_wallets=6000\n"))
            with self.assertRaises(SystemExit) as caught:
                validator.main()
            self.assertIn("L1_PREREGISTRATION_INVALID", str(caught.exception))
            self.assertIn("not the one the owner approved", str(caught.exception))
        finally:
            self.L2_APPROVAL.write_bytes(original)
        self.assertEqual(validator.main(), 0)

    def test_only_a_backticked_name_binds_so_prose_cannot_authorise_a_text(self) -> None:
        # A decision that discusses an approval in prose and states some hash
        # nearby must not thereby bind it; the log writes a binding in backticks.
        stray = BASE / "APPROVE_HL_LIVE_DATA_L2_PROSE_001.txt"
        text = b"APPROVE_HL_LIVE_DATA_L2_PROSE_001\nkey=value\n"
        self.assert_guard_refuses(
            {stray: text,
             self.DECISION_LOG: self.DECISION_LOG.read_bytes() + self.row(
                 "DEC-989", f"The approval APPROVE_HL_LIVE_DATA_L2_PROSE_001 was discussed, "
                            f"SHA-256 `{hashlib.sha256(text).hexdigest()}`")},
            expect="no accepted row in DECISION_LOG.md names this approval")

    def test_a_hash_far_from_the_name_is_not_that_approvals_hash(self) -> None:
        # A row may run long and mention a hash that belongs to something else.
        # Only a hash stated for the approval, near its name, binds it.
        stray = BASE / "APPROVE_HL_LIVE_DATA_L2_DISTANT_001.txt"
        text = b"APPROVE_HL_LIVE_DATA_L2_DISTANT_001\nkey=value\n"
        filler = "The row goes on about the pipeline and the ledger and the closing sweep. " * 8
        self.assertGreater(len(filler), 400)
        self.assert_guard_refuses(
            {stray: text,
             self.DECISION_LOG: self.DECISION_LOG.read_bytes() + self.row(
                 "DEC-988", f"`APPROVE_HL_LIVE_DATA_L2_DISTANT_001` is accepted. {filler} "
                            f"The database is recorded with SHA-256 `{hashlib.sha256(text).hexdigest()}`")},
            expect="no accepted row in DECISION_LOG.md names this approval")

    def test_the_validator_reports_what_it_verified(self) -> None:
        self.assertEqual(validator.validate_approvals_match_their_record(), len(RETAINED_APPROVALS))
        self.assertEqual(validator.main(), 0)


if __name__ == "__main__":
    unittest.main()
