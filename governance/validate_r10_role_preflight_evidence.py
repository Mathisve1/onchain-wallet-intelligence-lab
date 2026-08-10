from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
PREFLIGHT = BASE / "r10_role_preflight"
RUN = PREFLIGHT / "evidence/run-31372438333"
RUNTIME = BASE / "r10_runtime"
DATA_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-feature-r10.yml"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    context = load(RUN / "r10-sts-context.json")
    result = load(RUN / "r10-sts-result.json")
    verification = load(RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
    attestation = load(PREFLIGHT / "HL-ARCHIVE-R10-DEDICATED-ROLE-STS-PREFLIGHT-001-ATTESTATION.json")
    consumption = load(RUNTIME / "R10_STS_PREFLIGHT_RELEASE_CONSUMPTION.json")
    release = load(RUNTIME / "R10_STS_PREFLIGHT_RELEASE.json")

    assert context["workflow_run_id"] == 31372438333
    assert context["workflow_run_attempt"] == 1
    assert context["event_name"] == "workflow_dispatch"
    assert context["dispatch_sha"] == "8316f05f8fdfd444073e69e292cb89766ac89d7b"
    assert context["checked_out_commit"] == context["dispatch_sha"]
    assert context["dispatch_ref"] == "refs/heads/main"
    assert context["configure_aws_outcome"] == "success"
    assert context["expected_account_id"] == "630956766927"
    assert context["expected_role_arn"] == "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
    assert context["s3_requests_authorized"] is False
    assert context["s3_requests_executed"] == 0

    assert result["terminal_status"] == "R10_STS_PREFLIGHT_PASS"
    assert result["technical_result"] == "STS_IDENTITY_MATCH"
    assert result["expected_account_id"] == "630956766927"
    assert result["observed_account_id"] == "630956766927"
    assert result["expected_role_arn"] == "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
    assert result["observed_arn"] == "arn:aws:sts::630956766927:assumed-role/onchain-wallet-intelligence-hl-archive-multihour-r10/HLArchiveR10STSPreflight"
    assert result["s3_requests_executed"] == 0

    ledger_lines = (RUN / "R10_STS_FILES.sha256").read_text(encoding="utf-8").splitlines()
    observed = {}
    for line in ledger_lines:
        digest, name = line.split("  ", 1)
        observed[name] = digest
    expected_ledger = {
        "r10-sts-context.json": "328d0dd43e9ffac5d0bf8bda05f44500f503100da1adb2516e861d13a5da3e80",
        "r10-sts-result.json": "9524f1a383dddf73f525fef978f81df0a2399adec694dceebe616fc1c305bbd2",
        "r10-sts.rc": "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa",
    }
    assert observed == expected_ledger
    for name, digest in expected_ledger.items():
        assert hashlib.sha256((RUN / name).read_bytes()).hexdigest() == digest
        assert verification["internal_ledger"][name] == digest
    assert (RUN / "r10-sts.rc").read_text(encoding="utf-8") == "0\n"

    assert verification["run_id"] == 31372438333
    assert verification["job_id"] == 93404183373
    assert verification["artifact_id"] == 9056594122
    assert verification["artifact_name"] == "r10-sts-preflight-31372438333"
    assert verification["artifact_size_bytes"] == 1425
    assert verification["provider_sha256"] == "e2b5e68709eb8858f3d7b1fc4f17522b021f83c5aeacd04d719479a3703b5a26"
    assert verification["independently_downloaded_zip_sha256"] == verification["provider_sha256"]
    assert verification["provider_digest_matches_independent_download"] is True
    assert verification["internal_ledger_matches_all_retained_raw_files"] is True
    assert verification["return_code_value"] == 0
    assert verification["job_conclusion"] == "success"
    assert verification["configure_aws_outcome"] == "success"
    assert verification["single_use_gate_outcome"] == "success"
    assert verification["final_exact_result_gate_outcome"] == "success"
    assert verification["verified_terminal_status"] == "R10_STS_PREFLIGHT_PASS"
    assert verification["verified_technical_result"] == "STS_IDENTITY_MATCH"
    assert verification["verified_account_id"] == "630956766927"
    assert verification["explicit_sts_caller_identity_calls"] == 1
    assert verification["s3_requests_authorized"] is False
    assert verification["s3_http_request_count"] == 0
    assert verification["object_bytes_downloaded"] == 0
    assert verification["data_workflow_installed"] is False
    assert verification["data_execution_release_present"] is False
    assert verification["data_execution_activation_authorized"] is False
    assert verification["verification_result"] == "ALL_CHECKS_PASS"

    assert attestation["operator_attestation_independently_verified_by_preflight"] is True
    assert attestation["preflight_release_consumed"] is True
    assert attestation["rerun_authorized"] is False
    assert attestation["data_workflow_installed"] is False
    assert attestation["data_execution_release_present"] is False
    assert attestation["data_execution_activation_authorized_by_this_attestation"] is False
    assert attestation["wallet_ranking_authorized"] is False
    assert attestation["pnl_or_alpha_analysis_authorized"] is False
    assert attestation["copyability_analysis_authorized"] is False
    assert all(value is False for value in attestation["trading_authorizations_after_preflight"].values())

    assert consumption["status"] == "CONSUMED_SUCCESS"
    assert consumption["preflight_release_consumed"] is True
    assert consumption["rerun_authorized"] is False
    assert consumption["s3_requests_executed"] == 0
    assert consumption["object_bytes_downloaded"] == 0
    assert consumption["data_workflow_installed"] is False
    assert consumption["data_execution_release_present"] is False
    assert consumption["data_execution_activation_authorized_by_this_file"] is False

    # The single-use release is an immutable pre-run snapshot. Consumption is
    # represented only by the separate consumption record above.
    assert release["status"] == "RELEASED_FOR_EXACTLY_ONE_R10_STS_ONLY_PREFLIGHT"
    assert release["release_consumed"] is False
    assert release["rerun_authorized"] is False
    assert release["s3_access_authorized_during_preflight"] is False
    assert release["s3_requests_executed"] == 0
    assert not DATA_WORKFLOW.exists()

    print("R10_ROLE_STS_PREFLIGHT_EVIDENCE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
