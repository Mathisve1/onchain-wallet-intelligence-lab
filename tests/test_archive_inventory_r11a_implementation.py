from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from governance import validate_r11a_implementation as validator
from research.archive_inventory.r11a_implementation import collector, limits

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
IMPL = BASE / "r11a_implementation"


class R11AImplementationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = validator.strict_load(validator.CONTRACT)
        cls.prereg = validator.strict_load(validator.PREREG)
        cls.selection = validator.strict_load(validator.SELECTION)

    def test_dedicated_validator_passes_in_normal_and_optimized_mode(self) -> None:
        for flags in ([], ["-O"]):
            with self.subTest(flags=flags):
                completed = subprocess.run(
                    [sys.executable, *flags, "governance/validate_r11a_implementation.py"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                self.assertIn("R11A_IMPLEMENTATION_VALID_INERT_NO_EXECUTION", completed.stdout)

    def test_contract_is_sealed_and_all_runtime_authority_remains_closed(self) -> None:
        self.assertTrue(self.contract["implementation_sealed"])
        self.assertEqual(self.contract["status"], "IMPLEMENTED_AWAITING_OWNER_APPROVAL_NO_EXECUTION")
        self.assertEqual(self.contract["owner_approval_status"], "NOT_PRESENT")
        self.assertFalse(self.contract["workflow_installed_under_dot_github"])
        self.assertFalse(self.contract["execution_release_present"])
        self.assertFalse(self.contract["canonical_activation_present"])
        self.assertFalse(self.contract["single_workflow_dispatch_authorized"])
        self.assertFalse(self.contract["rerun_authorized"])
        self.assertTrue(all(value is False for value in self.contract["current_runtime_authority"].values()))
        self.assertTrue(all(value is False for value in self.contract["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in self.contract["trading_authorizations"].values()))
        self.assertFalse(self.contract["r11_closed"])
        self.assertFalse(self.contract["r12_ready"])
        self.assertIsNone(self.contract["empirical_result"])

    def test_limits_are_instance_scoped_and_exactly_preregistered(self) -> None:
        limits.DEFAULT_LIMITS.validate()
        self.assertEqual(
            limits.DEFAULT_LIMITS.as_contract_mapping(),
            self.contract["resource_envelope"],
        )
        self.assertEqual(limits.DEFAULT_LIMITS.maximum_get_object_requests, 72)
        self.assertEqual(limits.DEFAULT_LIMITS.maximum_retries_per_request, 0)
        self.assertEqual(limits.DEFAULT_LIMITS.maximum_total_compressed_bytes, 2_107_738_436)
        self.assertEqual(limits.DEFAULT_LIMITS.maximum_total_decompressed_bytes_across_two_passes, 21_079_958_490)
        self.assertEqual(limits.DEFAULT_LIMITS.maximum_ephemeral_workspace_bytes, 5_368_709_120)
        self.assertEqual(limits.DEFAULT_LIMITS.maximum_retained_artifact_bytes, 134_217_728)
        self.assertEqual(limits.DEFAULT_LIMITS.maximum_runtime_seconds, 21_600)

    def test_exact_72_target_binding_and_successor_permission_policy(self) -> None:
        targets = collector.frozen_targets()
        self.assertEqual(len(targets), 72)
        self.assertEqual(len({row.object_key for row in targets}), 72)
        self.assertEqual(sum(row.expected_size_bytes for row in targets), 2_107_738_436)
        permission = json.loads((IMPL / "R11A_PERMISSION_POLICY.json").read_text())
        resources = permission["Statement"][0]["Resource"]
        expected = [
            f"arn:aws:s3:::hl-mainnet-node-data/{row['key']}"
            for row in self.selection["exact_targets"]
        ]
        self.assertEqual(resources, expected)
        self.assertTrue(all("*" not in row for row in resources))
        self.assertEqual(permission["Statement"][0]["Action"], "s3:GetObject")

    def test_network_entrypoint_stops_before_transport_without_release(self) -> None:
        calls = 0

        def forbidden_transport(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            raise AssertionError("transport must not be reached")

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(collector.R11ACollectorError):
                collector.execute_network(
                    workspace=Path(directory) / "workspace",
                    artifact_directory=Path(directory) / "artifact",
                    transport=forbidden_transport,
                )
        self.assertEqual(calls, 0)

    def test_workflow_candidate_is_inert_and_not_installed(self) -> None:
        candidate = IMPL / "workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic.yml"
        installed = ROOT / ".github/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic.yml"
        runtime_release = BASE / "r11a_runtime/R11A_EXECUTION_RELEASE.json"
        self.assertTrue(candidate.is_file())
        self.assertFalse(installed.exists())
        self.assertFalse(runtime_release.exists())
        text = candidate.read_text()
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("\nschedule:", text)
        self.assertNotIn("\npush:", text)
        self.assertIn("R11A_EXECUTION_RELEASE.json", text)
        self.assertIn("role-duration-seconds: 21600", text)
        self.assertNotIn("aws s3 ", text.lower())
        self.assertNotIn("aws s3api ", text.lower())
        self.assertNotIn("pip install", text.lower())

    def test_role_decision_does_not_mutate_or_reuse_consumed_r11_role(self) -> None:
        role = json.loads((IMPL / "R11A_ROLE_DECISION.json").read_text())
        self.assertEqual(role["decision"], "CREATE_NEW_DEDICATED_R11A_ROLE_ONLY_AFTER_EXACT_OWNER_APPROVAL")
        self.assertFalse(role["existing_r11_role"]["reuse_authorized_now"])
        self.assertFalse(role["existing_r11_role"]["trust_mutation_authorized"])
        self.assertFalse(role["existing_r11_role"]["permission_mutation_authorized"])
        self.assertTrue(all(value is False for value in role["current_authority"].values()))
        self.assertEqual(role["network_or_iam_actions_executed_by_this_decision"], 0)

    def test_resource_report_is_cautious_not_a_success_claim(self) -> None:
        resource = json.loads((IMPL / "R11A_RESOURCE_FEASIBILITY.json").read_text())
        self.assertTrue(resource["conclusion"]["bounded_fail_closed_execution_feasible"])
        self.assertFalse(resource["conclusion"]["successful_complete_terminal_guaranteed"])
        self.assertFalse(resource["offline_test_scope"]["full_21gb_wall_clock_benchmark_performed"])
        self.assertTrue(resource["worst_case_boundaries"]["successful_complete_terminal_within_workspace_is_not_proven_before_execution"])
        self.assertIsNone(resource["empirical_result"])

    def test_contract_mutations_that_open_authority_fail(self) -> None:
        mutations = (
            lambda value: value.__setitem__("owner_approval_status", "APPROVED"),
            lambda value: value.__setitem__("single_workflow_dispatch_authorized", True),
            lambda value: value["current_runtime_authority"].__setitem__("get_object", True),
            lambda value: value["downstream_authorizations"].__setitem__("r11b_repair", True),
            lambda value: value["trading_authorizations"].__setitem__("live", True),
            lambda value: value.__setitem__("r12_ready", True),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                changed = copy.deepcopy(self.contract)
                mutate(changed)
                with self.assertRaises(validator.R11AImplementationValidationError):
                    validator.validate_contract(changed, self.prereg)

    def test_seal_rejects_code_or_workflow_drift(self) -> None:
        original = copy.deepcopy(self.contract)
        original["implementation_file_hashes"][
            "research/archive_inventory/r11a_implementation/collector.py"
        ] = "0" * 64
        with self.assertRaises(validator.R11AImplementationValidationError):
            validator.validate_seal(original)
        changed = copy.deepcopy(self.contract)
        changed["workflow_candidate_git_blob_sha"] = "0" * 40
        with self.assertRaises(validator.R11AImplementationValidationError):
            validator.validate_seal(changed)


if __name__ == "__main__":
    unittest.main()
