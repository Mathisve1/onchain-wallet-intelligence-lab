from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R7 = ROOT / "research/archive_inventory/r7"
RUN = R7 / "evidence/run-31330248235"
CONTEXT = RUN / "r7-context.json"
RESULT = RUN / "r7-result.json"
INDEX = RUN / "r7-wallet-index.ndjson"
RC = RUN / "r7.rc"
LEDGER = RUN / "R7_FILES.sha256"
VERIFY = RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json"
ATTESTATION = R7 / "evidence/HL-ARCHIVE-WALLET-INDEX-RECONSTRUCTION-R7-001-ATTESTATION.json"
CONSUMPTION = R7 / "R7_EXECUTION_RELEASE_CONSUMPTION.json"
ACTIVATION = R7 / "R7_EXECUTION_RELEASE_CANONICALIZATION.json"

RUN_ID = 31330248235
JOB_ID = 93287248593
ARTIFACT_ID = 9042711108
DISPATCH_SHA = "ce57bc637e4f5934201ebf09b578d1552c80c3ea"
ARTIFACT_SHA = "fb36478cdff956f83efdd1d7ae8c7bb8b3a82e8226d3868ea877a99ffac46ea7"
OBJECT_SHA = "f12d33da9733dbb71f02f9910fc187b9dd4b8f9dae1102b7dfe7690094542622"
INDEX_SHA = "2b8cbf709075aeda25394f22ee04b08656d5d165105976ed5d7e0890479e2d6d"
ADDRESS_RE = re.compile(r"^0x[0-9a-f]{40}$")
EXPECTED_FILE_HASHES = {
    "r7-context.json": "646f4ca4458bfefee882653f012cc3220aff863f5128bcee6df86a4266f7e1e8",
    "r7-result.json": "cc84f0942dc9f93296fb532c4c47b3555e241aee63b5cf27d6a1eb3a0f90fbb6",
    "r7-wallet-index.ndjson": INDEX_SHA,
    "r7.rc": "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa",
    "R7_FILES.sha256": "1ef362a938fb3e6728c5ae44b2afb7d3d4a951fb1ecfaa126c4009cee836d2b1",
}


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    for name, expected in EXPECTED_FILE_HASHES.items():
        path = RUN / name
        assert path.is_file(), path
        assert sha(path) == expected, name

    ledger_lines = LEDGER.read_text(encoding="utf-8").splitlines()
    expected_ledger = [
        f"{EXPECTED_FILE_HASHES[name]}  {name}"
        for name in ("r7-context.json", "r7-result.json", "r7-wallet-index.ndjson", "r7.rc")
    ]
    assert ledger_lines == expected_ledger
    assert RC.read_text(encoding="utf-8") == "0\n"

    context = load(CONTEXT)
    result = load(RESULT)
    verify = load(VERIFY)
    attestation = load(ATTESTATION)
    consumption = load(CONSUMPTION)
    activation = load(ACTIVATION)

    assert context["pilot_id"] == "HL-ARCHIVE-WALLET-INDEX-RECONSTRUCTION-R7-001"
    assert context["release_id"] == "RELEASE_HL_ARCHIVE_WALLET_INDEX_RECONSTRUCTION_R7_001"
    assert context["workflow_run_id"] == RUN_ID
    assert context["workflow_run_attempt"] == 1
    assert context["event_name"] == "workflow_dispatch"
    assert context["dispatch_ref"] == "refs/heads/main"
    assert context["dispatch_sha"] == context["checked_out_commit"] == DISPATCH_SHA
    assert context["configure_aws_outcome"] == "success"
    assert context["maximum_get_object_requests"] == 1
    assert context["maximum_retries_per_request"] == 0
    assert context["wallet_address_retention_authorized"] is True
    assert context["per_wallet_fill_count_retention_authorized"] is True
    assert context["retained_wallet_index_fields_only"] == ["wallet_address", "fill_count"]
    for key in (
        "entity_clustering_authorized", "copyability_analysis_authorized",
        "pnl_or_alpha_analysis_authorized", "market_data_ingestion_authorized",
        "historical_multi_hour_ingestion_authorized", "strategy_inference_authorized",
    ):
        assert context[key] is False, key

    assert result["pilot_id"] == context["pilot_id"]
    assert result["terminal_status"] == "R7_WALLET_INDEX_STUDY_COMPLETE"
    assert result["technical_result"] == "WALLET_INDEX_RECONSTRUCTION_COMPLETE"
    assert result["research_conclusion"] == "WALLET_INDEX_RECONSTRUCTION_COMPLETE"
    assert result["request_attempt_count"] == 1
    assert result["s3_http_request_count"] == 1
    assert result["successful_request_count"] == 1
    assert result["failed_request_count"] == 0
    assert result["retries_used"] == 0
    assert result["http_redirects_followed"] is False
    assert result["compressed_bytes"] == 12726384
    assert result["compressed_sha256"] == OBJECT_SHA
    assert result["decompressed_bytes"] == 62169139
    assert result["wallet_addresses_retained"] is True
    assert result["leading_string_values_retained"] is True
    assert result["per_wallet_fill_counts_retained"] is True
    assert result["wallet_index_retained"] is True
    for key in (
        "raw_compressed_object_persisted", "raw_decompressed_payload_retained",
        "record_payload_retained", "fill_object_retained", "payload_values_retained",
        "coin_values_retained", "price_values_retained", "size_values_retained",
        "side_values_retained", "time_values_retained", "closed_pnl_values_retained",
        "fee_values_retained", "transaction_hashes_retained", "order_ids_retained",
        "trade_ids_retained", "client_order_ids_retained", "entity_clustering_performed",
        "copyability_analysis_performed", "pnl_or_alpha_analysis_performed",
        "market_data_ingested", "historical_multi_hour_ingestion_performed",
        "strategy_inference_performed",
    ):
        assert result[key] is False, key

    summary = result["wallet_index_summary"]
    assert summary["nonempty_record_count"] == 162815
    assert summary["pair_string_object_record_count"] == 162815
    assert summary["unique_wallet_count"] == 4637
    assert summary["sum_fill_count"] == 162815
    assert summary["wallet_index_bytes"] == 368036
    assert summary["wallet_index_sha256"] == INDEX_SHA
    assert summary["wallet_index_fields_only"] == ["wallet_address", "fill_count"]
    assert summary["wallet_index_format"] == "UTF8_NDJSON"
    assert summary["wallet_index_sort_order"] == "LEXICOGRAPHIC_ASCENDING"

    data = INDEX.read_bytes()
    assert len(data) == 368036
    assert hashlib.sha256(data).hexdigest() == INDEX_SHA
    addresses: list[str] = []
    total = 0
    for raw in data.splitlines():
        row = json.loads(raw.decode("utf-8"))
        assert isinstance(row, dict)
        assert list(row.keys()) == ["wallet_address", "fill_count"]
        address = row["wallet_address"]
        count = row["fill_count"]
        assert isinstance(address, str) and ADDRESS_RE.fullmatch(address)
        assert isinstance(count, int) and not isinstance(count, bool) and count > 0
        addresses.append(address)
        total += count
    assert len(addresses) == 4637
    assert addresses == sorted(addresses)
    assert len(addresses) == len(set(addresses))
    assert total == 162815

    assert verify["run_id"] == RUN_ID
    assert verify["job_id"] == JOB_ID
    assert verify["artifact_id"] == ARTIFACT_ID
    assert verify["artifact_zip_sha256"] == ARTIFACT_SHA
    assert verify["artifact_size_bytes"] == 119412
    assert verify["verification_status"] == "PASS"
    assert all(value is True for value in verify["checks"].values())

    assert attestation["run_id"] == RUN_ID
    assert attestation["job_id"] == JOB_ID
    assert attestation["artifact_id"] == ARTIFACT_ID
    assert attestation["artifact_sha256"] == ARTIFACT_SHA
    assert attestation["canonical_dispatch_commit"] == DISPATCH_SHA
    assert attestation["terminal_status"] == result["terminal_status"]
    assert attestation["research_conclusion"] == result["research_conclusion"]
    assert attestation["wallet_index"]["sha256"] == INDEX_SHA
    assert attestation["wallet_index"]["unique_wallet_count"] == 4637
    assert attestation["wallet_index"]["sum_fill_count"] == 162815
    assert attestation["release_consumed"] is True
    assert attestation["rerun_authorized"] is False
    assert all(value is False for value in attestation["trading_authorizations_after_run"].values())

    assert consumption["run_id"] == RUN_ID
    assert consumption["job_id"] == JOB_ID
    assert consumption["artifact_id"] == ARTIFACT_ID
    assert consumption["activation_merge_commit"] == DISPATCH_SHA
    assert consumption["release_consumed"] is True
    assert consumption["future_r7_dispatch_authorized"] is False
    assert consumption["rerun_authorized"] is False
    assert consumption["remaining_approved_get_object_budget"] == 0
    assert consumption["unique_wallet_count"] == 4637
    assert consumption["sum_fill_count"] == 162815
    assert all(value is False for value in consumption["downstream_authorizations_after_run"].values())
    assert all(value is False for value in consumption["trading_authorizations_after_run"].values())

    assert activation["release_id"] == consumption["release_id"]
    assert activation["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R7_RUN"
    assert activation["single_workflow_dispatch_authorized"] is True
    assert activation["rerun_authorized"] is False
    assert activation["release_consumed"] is False  # immutable pre-run activation snapshot

    print("R7_EVIDENCE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
