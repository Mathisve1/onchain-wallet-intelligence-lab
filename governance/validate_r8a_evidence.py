from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R8 = ROOT / "research/archive_inventory/r8"
R7 = ROOT / "research/archive_inventory/r7/evidence/run-31330248235/r7-wallet-index.ndjson"
RUN = R8 / "evidence/run-31333421763"
CONSUMPTION = R8 / "R8A_EXECUTION_RELEASE_CONSUMPTION.json"
ATTESTATION = R8 / "evidence/HL-ARCHIVE-MODERN-WALLET-INDEX-BRIDGE-R8A-001-ATTESTATION.json"
COMPARISON = R8 / "evidence/R8A_LEGACY_MODERN_BRIDGE_COMPARISON.json"
CONCLUSION = R8 / "evidence/R8A_RESEARCH_CONCLUSION.md"
ACTIVATION = R8 / "R8A_EXECUTION_RELEASE_CANONICALIZATION.json"

RUN_ID = 31333421763
JOB_ID = 93295166161
ARTIFACT_ID = 9043584172
DISPATCH_SHA = "2f8237de806dcf149579aefc6ece1ae537ef7aeb"
ARTIFACT_ZIP_SHA256 = "185037463a1eab27b35c5f8b6edad810a28bce599101e4d26734020717a392c8"
ARTIFACT_SIZE_BYTES = 25269
EXPECTED_FILE_HASHES = {
    "r8a-context.json": "a967cd8061d61064f6cb234c031527145d3698703af78b5c2d882934ed07722c",
    "r8a-result.json": "c99f29b443110bc3840c8d2f12b6617a874c5af70fc07894b55d1d19bdf1de6c",
    "r8a-wallet-index.ndjson": "e7f208c7e4150e88ae98daab055d183739140698a4f6e310e37fc814f463013e",
    "r8a.rc": "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa",
    "R8A_FILES.sha256": "c81dd3758cadea0e944998026b62f68e50f52e47ccdadec6595cfc06ad24e12d",
}
ADDRESS_RE = re.compile(r"^0x[0-9a-f]{40}$")


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_index(path: Path) -> dict[str, int]:
    rows: dict[str, int] = {}
    previous: str | None = None
    for raw in path.read_bytes().splitlines():
        row = json.loads(raw.decode("utf-8"))
        assert list(row.keys()) == ["wallet_address", "fill_count"]
        address = row["wallet_address"]
        count = row["fill_count"]
        assert isinstance(address, str) and ADDRESS_RE.fullmatch(address)
        assert isinstance(count, int) and count > 0
        assert address not in rows
        if previous is not None:
            assert previous < address
        rows[address] = count
        previous = address
    return rows


def recompute_comparison(legacy: dict[str, int], modern: dict[str, int]) -> dict:
    legacy_keys = set(legacy)
    modern_keys = set(modern)
    overlap = legacy_keys & modern_keys
    modern_only = modern_keys - legacy_keys
    legacy_only = legacy_keys - modern_keys
    equal = sum(modern[a] == legacy[a] for a in overlap)
    modern_lt = sum(modern[a] < legacy[a] for a in overlap)
    modern_gt = sum(modern[a] > legacy[a] for a in overlap)
    return {
        "schema_version": "1.0",
        "comparison_id": "R8A_LEGACY_MODERN_WALLET_INDEX_BRIDGE_COMPARISON_001",
        "legacy_index_source": "research/archive_inventory/r7/evidence/run-31330248235/r7-wallet-index.ndjson",
        "modern_index_source": "research/archive_inventory/r8/evidence/run-31333421763/r8a-wallet-index.ndjson",
        "legacy_unique_wallet_count": len(legacy),
        "legacy_sum_fill_count": sum(legacy.values()),
        "modern_unique_wallet_count": len(modern),
        "modern_sum_fill_count": sum(modern.values()),
        "overlapping_wallet_count": len(overlap),
        "modern_only_wallet_count": len(modern_only),
        "legacy_only_wallet_count": len(legacy_only),
        "modern_address_set_subset_of_legacy": len(modern_only) == 0,
        "overlap_wallets_with_equal_fill_count": equal,
        "overlap_wallets_with_modern_fill_count_lt_legacy": modern_lt,
        "overlap_wallets_with_modern_fill_count_gt_legacy": modern_gt,
        "modern_fill_count_sum_on_overlap": sum(modern[a] for a in overlap),
        "legacy_fill_count_sum_on_overlap": sum(legacy[a] for a in overlap),
        "exact_fill_identity_inferred": False,
        "temporal_subset_inferred": False,
        "schema_equivalence_inferred": False,
        "semantic_equivalence_inferred": False,
        "wallet_ranking_performed": False,
        "copyability_analysis_performed": False,
        "pnl_or_alpha_analysis_performed": False,
    }


def main() -> int:
    for name, expected in EXPECTED_FILE_HASHES.items():
        path = RUN / name
        assert path.is_file(), path
        assert sha(path) == expected, name

    ledger = (RUN / "R8A_FILES.sha256").read_text(encoding="utf-8")
    for name in ("r8a-context.json", "r8a-result.json", "r8a-wallet-index.ndjson", "r8a.rc"):
        assert f"{EXPECTED_FILE_HASHES[name]}  {name}\n" in ledger

    context = load(RUN / "r8a-context.json")
    result = load(RUN / "r8a-result.json")
    assert context["workflow_run_id"] == RUN_ID
    assert context["workflow_run_attempt"] == 1
    assert context["event_name"] == "workflow_dispatch"
    assert context["dispatch_ref"] == "refs/heads/main"
    assert context["dispatch_sha"] == context["checked_out_commit"] == DISPATCH_SHA
    assert context["configure_aws_outcome"] == "success"
    assert context["object_key"] == "node_fills_by_block/hourly/20250727/8.lz4"
    assert context["retained_wallet_index_fields_only"] == ["wallet_address", "fill_count"]
    assert context["historical_multi_hour_ingestion_authorized"] is False
    assert context["wallet_ranking_authorized"] is False
    assert context["copyability_analysis_authorized"] is False
    assert context["pnl_or_alpha_analysis_authorized"] is False

    assert (RUN / "r8a.rc").read_text(encoding="utf-8") == "0\n"
    assert result["terminal_status"] == "R8A_MODERN_WALLET_INDEX_STUDY_COMPLETE"
    assert result["technical_result"] == "MODERN_WALLET_INDEX_BRIDGE_COMPLETE"
    assert result["research_conclusion"] == "MODERN_WALLET_INDEX_BRIDGE_COMPLETE"
    assert result["request_attempt_count"] == 1
    assert result["s3_http_request_count"] == 1
    assert result["successful_request_count"] == 1
    assert result["failed_request_count"] == 0
    assert result["retries_used"] == 0
    assert result["http_redirects_followed"] is False
    assert result["compressed_bytes"] == 1517603
    assert result["compressed_sha256"] == "928e1cd6bd7d69ad7243c263bacee48e53e4762ae9e99ef75f45007f6c0e6105"
    assert result["decompressed_bytes"] == 7380378
    summary = result["wallet_index_summary"]
    assert summary["top_level_block_record_count"] == 4345
    assert summary["valid_event_pair_count"] == 17516
    assert summary["unique_wallet_count"] == 887
    assert summary["sum_fill_count"] == 17516
    assert summary["wallet_index_bytes"] == 70343
    assert summary["wallet_index_sha256"] == EXPECTED_FILE_HASHES["r8a-wallet-index.ndjson"]
    assert summary["wallet_index_fields_only"] == ["wallet_address", "fill_count"]
    assert summary["wallet_index_sort_order"] == "LEXICOGRAPHIC_ASCENDING"

    for key in (
        "raw_compressed_object_persisted", "raw_decompressed_payload_retained", "record_payload_retained",
        "fill_object_retained", "payload_values_retained", "performance_field_values_retained",
        "block_number_values_retained", "local_time_values_retained", "block_time_values_retained",
        "coin_values_retained", "price_values_retained", "size_values_retained", "side_values_retained",
        "time_values_retained", "dir_values_retained", "closed_pnl_values_retained", "fee_values_retained",
        "fee_token_values_retained", "start_position_values_retained", "crossed_values_retained",
        "liquidation_values_retained", "transaction_hashes_retained", "order_ids_retained", "trade_ids_retained",
        "client_order_ids_retained", "historical_multi_hour_ingestion_performed", "public_api_enrichment_performed",
        "entity_clustering_performed", "wallet_ranking_performed", "copyability_analysis_performed",
        "pnl_or_alpha_analysis_performed", "market_data_ingested", "strategy_inference_performed",
    ):
        assert result[key] is False, key

    modern = read_index(RUN / "r8a-wallet-index.ndjson")
    assert len(modern) == 887
    assert sum(modern.values()) == 17516
    legacy = read_index(R7)
    comparison = load(COMPARISON)
    assert comparison == recompute_comparison(legacy, modern)

    verification = load(RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
    assert verification["workflow_run_id"] == RUN_ID
    assert verification["workflow_job_id"] == JOB_ID
    assert verification["artifact_id"] == ARTIFACT_ID
    assert verification["artifact_zip_sha256"] == ARTIFACT_ZIP_SHA256
    assert verification["artifact_size_bytes"] == ARTIFACT_SIZE_BYTES
    assert verification["artifact_expired_at_verification"] is False
    assert verification["all_checks_pass"] is True
    assert verification["retained_file_sha256"] == EXPECTED_FILE_HASHES

    activation = load(ACTIVATION)
    consumption = load(CONSUMPTION)
    assert activation["release_id"] == consumption["release_id"]
    assert consumption["status"] == "CONSUMED_BY_CANONICAL_R8A_RUN"
    assert consumption["release_consumed"] is True
    assert consumption["workflow_run_id"] == RUN_ID
    assert consumption["workflow_job_id"] == JOB_ID
    assert consumption["artifact_id"] == ARTIFACT_ID
    assert consumption["canonical_dispatch_sha"] == DISPATCH_SHA
    assert consumption["successful_get_object_requests"] == 1
    assert consumption["remaining_get_object_budget"] == 0
    assert consumption["future_r8a_dispatch_authorized"] is False
    assert consumption["rerun_authorized"] is False
    assert all(value is False for value in consumption["downstream_authorizations"].values())
    assert all(value is False for value in consumption["trading_authorizations"].values())

    attestation = load(ATTESTATION)
    assert attestation["pilot_id"] == "HL-ARCHIVE-MODERN-WALLET-INDEX-BRIDGE-R8A-001"
    assert attestation["workflow_run_id"] == RUN_ID
    assert attestation["workflow_job_id"] == JOB_ID
    assert attestation["artifact_id"] == ARTIFACT_ID
    assert attestation["research_conclusion"] == "MODERN_WALLET_INDEX_BRIDGE_COMPLETE"
    assert attestation["release_consumed"] is True
    assert attestation["wallet_index_summary"] == summary
    assert attestation["bridge_comparison_sha256"] == sha(COMPARISON)
    assert all(value is False for value in attestation["claims_not_authorized"].values())

    conclusion = CONCLUSION.read_text(encoding="utf-8")
    assert "MODERN_WALLET_INDEX_BRIDGE_COMPLETE" in conclusion
    assert "17,516" in conclusion
    assert "887" in conclusion
    assert "does not prove exact fill identity" in conclusion
    assert "No second R8A dispatch" in conclusion

    print("R8A_EVIDENCE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
