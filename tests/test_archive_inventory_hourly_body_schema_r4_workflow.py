from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-hourly-body-schema-pilot-r4.yml"
ACTIVATION = ROOT / "research/archive_inventory/r4/R4_EXECUTION_RELEASE_CANONICALIZATION.json"
IMPLEMENTATION = "180c89ead78f9a6f4560a1ec12575658e62586ee"


class ArchiveHourlyBodySchemaR4WorkflowTests(unittest.TestCase):
    def text(self) -> str:
        return WORKFLOW.read_text(encoding="utf-8")

    def test_workflow_is_manual_only_and_exact_main_identity_bound(self) -> None:
        text = self.text()
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("push:", text)
        self.assertIn("EVENT_NAME: ${{ github.event_name }}", text)
        self.assertIn("DISPATCH_REF: ${{ github.ref }}", text)
        self.assertIn("DISPATCH_SHA: ${{ github.sha }}", text)
        self.assertIn("refs/heads/main", text)
        self.assertIn("persist-credentials: false", text)
        self.assertNotIn("reviewed_commit:", text)

    def test_implementation_candidate_is_inert_until_separate_release(self) -> None:
        text = self.text()
        if ACTIVATION.exists():
            self.assertIn(f"EXPECTED_IMPLEMENTATION_COMMIT: {IMPLEMENTATION}", text)
            self.assertNotIn("EXPECTED_IMPLEMENTATION_COMMIT: PENDING_CANONICAL_IMPLEMENTATION_MERGE", text)
        else:
            self.assertIn("EXPECTED_IMPLEMENTATION_COMMIT: PENDING_CANONICAL_IMPLEMENTATION_MERGE", text)
        self.assertIn("R4 release gate 45", text)
        self.assertIn("R4_EXECUTION_RELEASE_CANONICALIZATION.json", text)
        self.assertLess(
            text.index("Prove canonical R4 implementation and release before AWS OIDC"),
            text.index("Assume dedicated R4 AWS role with exact-two-object session permissions"),
        )

    def test_oidc_uses_dedicated_role_and_exact_two_getobject_arns_only(self) -> None:
        text = self.text()
        self.assertIn("arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4", text)
        self.assertIn('"Action":"s3:GetObject"', text)
        self.assertIn("arn:aws:s3:::hl-mainnet-node-data/node_fills/hourly/20250727/8.lz4", text)
        self.assertIn("arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250727/8.lz4", text)
        for forbidden in (
            "s3:ListBucket", "s3:GetObjectVersion", "s3:GetObjectAttributes",
            "s3:ListBucketVersions", "s3:ListAllMyBuckets",
        ):
            self.assertNotIn(forbidden, text)
        self.assertIn("role-duration-seconds: 900", text)
        self.assertIn("retry-max-attempts: 1", text)

    def test_approved_caps_and_forbidden_capabilities_are_rechecked_before_oidc(self) -> None:
        text = self.text()
        for assertion in (
            "assert approval['maximum_get_object_requests'] == 2",
            "assert approval['maximum_requests_per_object'] == 1",
            "assert approval['maximum_total_compressed_bytes'] == 14243987",
            "assert approval['maximum_total_decompressed_bytes'] == 536870912",
            "assert approval['maximum_decompressed_bytes_per_object'] == 268435456",
            "assert approval['maximum_runtime_seconds'] == 180",
            "assert approval['maximum_retries_per_request'] == 0",
            "assert release['dedicated_r4_role_operator_attested'] is True",
            "assert release['rerun_authorized'] is False",
            "'wallet_reconstruction_authorized'",
            "'market_data_ingestion_authorized'",
            "assert release[key] is False",
        ):
            self.assertIn(assertion, text)
        pre_oidc = text.index("Prove canonical R4 implementation and release before AWS OIDC")
        oidc = text.index("Assume dedicated R4 AWS role with exact-two-object session permissions")
        self.assertIn("python -m unittest discover -s tests -v", text[pre_oidc:oidc])

    def test_single_use_history_and_rerun_guard_precede_oidc(self) -> None:
        text = self.text()
        self.assertIn("CURRENT_RUN_ATTEMPT", text)
        self.assertIn("Run attempt must be 1; re-runs are forbidden", text)
        self.assertIn("?event=workflow_dispatch&branch=main&per_page=100", text)
        self.assertIn("a previous dispatch already consumed the R4 release", text)
        self.assertIn("single_use_window_start_utc", text)
        self.assertLess(
            text.index("Run attempt must be 1; re-runs are forbidden"),
            text.index("Assume dedicated R4 AWS role with exact-two-object session permissions"),
        )

    def test_artifact_contains_only_minimized_evidence_not_object_payloads(self) -> None:
        text = self.text()
        self.assertIn("python research/archive_inventory/r4/collector.py", text)
        self.assertIn(">/dev/null", text)
        self.assertIn("R4_BODY_FILES.sha256", text)
        self.assertIn("retention-days: 90", text)
        self.assertIn("r4-body-context.json", text)
        self.assertIn("r4-body-result.json", text)
        self.assertNotIn(".lz4\n", text)
        self.assertIn("raw_compressed_object_persisted'] is False", text)
        self.assertIn("raw_decompressed_payload_retained'] is False", text)
        self.assertIn("record_payload_retained'] is False", text)
        self.assertIn("payload_values_retained'] is False", text)

    def test_final_gate_accepts_research_unresolved_but_never_transport_failure(self) -> None:
        text = self.text()
        self.assertIn("R4_BODY_SCHEMA_PILOT_COMPLETE", text)
        self.assertIn("TWO_OBJECT_SCHEMA_COMPARISON_RESOLVED", text)
        self.assertIn("TWO_OBJECT_SCHEMA_CENSORED", text)
        self.assertIn("TWO_OBJECT_BODY_FORMAT_UNRESOLVED", text)
        self.assertIn("SCHEMA_UNRESOLVED", text)
        self.assertIn("assert result['request_attempt_count'] == 2", text)
        self.assertIn("assert result['successful_request_count'] == 2", text)
        self.assertIn("assert result['failed_request_count'] == 0", text)

    def test_permissions_and_actions_are_pinned(self) -> None:
        text = self.text()
        self.assertIn("actions: read", text)
        self.assertIn("contents: read", text)
        self.assertIn("id-token: write", text)
        self.assertIn("actions/checkout@11d5960a326750d5838078e36cf38b85af677262", text)
        self.assertIn("actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065", text)
        self.assertIn("aws-actions/configure-aws-credentials@e6de054238d6b7531b4efff3b6587d9aade6a06c", text)
        self.assertIn("actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a", text)


if __name__ == "__main__":
    unittest.main()
