from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
PREFLIGHT = BASE / "r11_role_preflight"
RUN = PREFLIGHT / "evidence/run-31433889087"
RUNTIME = BASE / "r11_runtime"
DATA_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r11-72h-persistence.yml"

RUN_ID = 31433889087
JOB_ID = 93603513466
ARTIFACT_ID = 9080202425
DISPATCH_SHA = "efad3f278e458a5c35fbfcc11de2b97bbe7cb388"
ARTIFACT_SHA = "1de9b92dba9ee74152166e4a9890a5a788b36f104499c9323b66e2aa9374eb79"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-scaling-r11"
SESSION_ARN = "arn:aws:sts::630956766927:assumed-role/onchain-wallet-intelligence-hl-archive-scaling-r11/HLArchiveR11STSPreflight"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    context = load(RUN / "r11-sts-context.json")
    result = load(RUN / "r11-sts-result.json")
    verification = load(RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
    attestation = load(PREFLIGHT / "HL-ARCHIVE-R11-DEDICATED-ROLE-STS-PREFLIGHT-001-ATTESTATION.json")
    consumption = load(RUNTIME / "R11_STS_PREFLIGHT_RELEASE_CONSUMPTION.json")
    release = load(RUNTIME / "R11_STS_PREFLIGHT_RELEASE.json")
    operator = load(BASE / "r11_role_attestation/R11_DEDICATED_ROLE_OPERATOR_ATTESTATION.json")

    assert context["workflow_run_id"] == RUN_ID
    assert context["workflow_run_attempt"] == 1
    assert context["dispatch_sha"] == DISPATCH_SHA
    assert context["checked_out_commit"] == DISPATCH_SHA
    assert context["dispatch_ref"] == "refs/heads/main"
    assert context["configure_aws_outcome"] == "success"
    assert context["expected_account_id"] == "630956766927"
    assert context["expected_role_arn"] == ROLE_ARN
    assert context["s3_requests_authorized"] is False
    assert context["s3_requests_executed"] == 0
    assert context["object_bytes_downloaded"] == 0

    assert result["preflight_id"] == "HL-ARCHIVE-R11-DEDICATED-ROLE-STS-PREFLIGHT-001"
    assert result["terminal_status"] == "R11_STS_PREFLIGHT_PASS"
    assert result["technical_result"] == "DEDICATED_R11_ROLE_ASSUMEABLE_FROM_CANONICAL_MAIN"
    assert result["expected_account_id"] == result["observed_account_id"] == "630956766927"
    assert result["expected_role_arn"] == ROLE_ARN
    assert result["observed_arn"] == SESSION_ARN
    assert result["s3_http_request_count"] == 0
    assert result["object_bytes_downloaded"] == 0

    ledger_lines = (RUN / "R11_STS_FILES.sha256").read_text(encoding="utf-8").splitlines()
    observed: dict[str, str] = {}
    for line in ledger_lines:
        digest, name = line.split("  ", 1)
        observed[name] = digest
    expected_ledger = {
        "r11-sts-context.json": "49b4d03180f9b8cb720daa9c24e107a984a95d51f7117c8307f30009ddbc421f",
        "r11-sts-result.json": "dee1413bf81200d168904a18a53d88019810475e2de20e3057630487ba77e8eb",
        "r11-sts.rc": "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa",
    }
    assert observed == expected_ledger
    for name, digest in expected_ledger.items():
        assert hashlib.sha256((RUN / name).read_bytes()).hexdigest() == digest
        assert verification["internal_ledger"][name] == digest
    assert (RUN / "r11-sts.rc").read_text(encoding="utf-8") == "0\n"

    assert verification["run_id"] == RUN_ID
    assert verification["job_id"] == JOB_ID
    assert verification["artifact_id"] == ARTIFACT_ID
    assert verification["artifact_name"] == "r11-sts-preflight-31433889087"
    assert verification["artifact_size_bytes"] == 1427
    assert verification["provider_sha256"] == ARTIFACT_SHA
    assert verification["independently_downloaded_zip_sha256"] == ARTIFACT_SHA
    assert verification["provider_digest_matches_independent_download"] is True
    assert verification["artifact_files"] == [
        "r11-sts-context.json",
        "r11-sts-result.json",
        "r11-sts.rc",
        "R11_STS_FILES.sha256",
    ]
    assert verification["internal_ledger_matches_all_retained_raw_files"] is True
    assert verification["return_code_value"] == 0
    assert verification["dispatch_sha"] == DISPATCH_SHA
    assert verification["dispatch_ref"] == "refs/heads/main"
    assert verification["event_name"] == "workflow_dispatch"
    assert verification["workflow_run_attempt"] == 1
    assert verification["job_conclusion"] == "success"
    assert verification["configure_aws_outcome"] == "success"
    assert verification["single_use_gate_outcome"] == "success"
    assert verification["final_exact_result_gate_outcome"] == "success"
    assert verification["verified_terminal_status"] == "R11_STS_PREFLIGHT_PASS"
    assert verification["verified_technical_result"] == "DEDICATED_R11_ROLE_ASSUMEABLE_FROM_CANONICAL_MAIN"
    assert verification["verified_account_id"] == "630956766927"
    assert verification["verified_role_session_arn"] == SESSION_ARN
    assert verification["explicit_sts_caller_identity_calls"] == 1
    assert verification["s3_requests_authorized"] is False
    assert verification["s3_http_request_count"] == 0
    assert verification["object_bytes_downloaded"] == 0
    assert verification["requester_pays_requested"] is False
    assert verification["decompression_performed"] is False
    assert verification["raw_oidc_token_retained"] is False
    assert verification["aws_credentials_retained"] is False
    assert verification["raw_caller_identity_retained"] is False
    assert verification["operator_attestation_independently_verified"] is True
    assert verification["data_workflow_installed"] is False
    assert verification["data_execution_release_present"] is False
    assert verification["data_execution_activation_authorized"] is False
    assert verification["verification_result"] == "ALL_CHECKS_PASS"

    assert attestation["run_id"] == RUN_ID
    assert attestation["job_id"] == JOB_ID
    assert attestation["artifact_id"] == ARTIFACT_ID
    assert attestation["artifact_sha256"] == ARTIFACT_SHA
    assert attestation["terminal_status"] == "R11_STS_PREFLIGHT_PASS"
    assert attestation["technical_result"] == "DEDICATED_R11_ROLE_ASSUMEABLE_FROM_CANONICAL_MAIN"
    assert attestation["observed_role_session_arn"] == SESSION_ARN
    assert attestation["operator_attestation_independently_verified_by_preflight"] is True
    assert attestation["preflight_release_consumed"] is True
    assert attestation["rerun_authorized"] is False
    assert attestation["data_workflow_installed"] is False
    assert attestation["data_execution_release_present"] is False
    assert attestation["data_execution_activation_authorized_by_this_attestation"] is False
    for key in (
        "historical_window_beyond_three_days_authorized",
        "full_population_historical_ingestion_authorized",
        "public_api_enrichment_authorized",
        "entity_clustering_authorized",
        "wallet_ranking_authorized",
        "candidate_shortlisting_authorized",
        "pnl_or_alpha_analysis_authorized",
        "copyability_analysis_authorized",
        "market_data_ingestion_authorized",
        "strategy_inference_authorized",
    ):
        assert attestation[key] is False, key
    assert all(v is False for v in attestation["trading_authorizations_after_preflight"].values())

    assert consumption["status"] == "CONSUMED_SUCCESS"
    assert consumption["run_id"] == RUN_ID
    assert consumption["job_id"] == JOB_ID
    assert consumption["artifact_id"] == ARTIFACT_ID
    assert consumption["preflight_release_consumed"] is True
    assert consumption["rerun_authorized"] is False
    assert consumption["s3_requests_executed"] == 0
    assert consumption["object_bytes_downloaded"] == 0
    assert consumption["data_workflow_installed"] is False
    assert consumption["data_execution_release_present"] is False
    assert consumption["data_execution_activation_authorized_by_this_file"] is False

    # Historical operator attestation and the release remain immutable pre-run snapshots.
    assert operator["operator_attested"] is True
    assert operator["independently_verified_via_r11_sts_preflight"] is False
    assert operator["sts_only_preflight_completed"] is False
    assert release["status"] == "RELEASED_FOR_EXACTLY_ONE_R11_STS_ONLY_PREFLIGHT"
    assert release["release_consumed"] is False
    assert release["rerun_authorized"] is False
    assert release["s3_access_authorized_during_preflight"] is False
    assert release["s3_requests_executed"] == 0
    assert not DATA_WORKFLOW.exists()

    print("R11_ROLE_STS_PREFLIGHT_EVIDENCE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
