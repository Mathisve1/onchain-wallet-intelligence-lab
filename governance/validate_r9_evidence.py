from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import statistics
import zipfile
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R9 = ROOT / "research/archive_inventory/r9"
EVIDENCE = R9 / "evidence"
RUN = EVIDENCE / "run-31336490854"
RECONSTRUCTION = RUN / "ARTIFACT_RECONSTRUCTION.json"
VERIFICATION = RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json"
RESULT_COPY = RUN / "r9-result.json"
CONTEXT_COPY = RUN / "r9-context.json"
RC_COPY = RUN / "r9.rc"
LEDGER_COPY = RUN / "R9_FILES.sha256"
DIAGNOSTICS = EVIDENCE / "R9_AGGREGATE_DIAGNOSTICS.json"
ATTESTATION = EVIDENCE / "HL-ARCHIVE-MODERN-WALLET-FEATURE-PILOT-R9-001-ATTESTATION.json"
CONCLUSION = EVIDENCE / "R9_RESEARCH_CONCLUSION.md"
BOUNDARY = EVIDENCE / "R9_BOUNDARY_TIME_REFINEMENT.md"
CONSUMPTION = R9 / "R9_EXECUTION_RELEASE_CONSUMPTION.json"
ACTIVATION = R9 / "R9_EXECUTION_RELEASE_CANONICALIZATION.json"

ZIP_SHA = "00c049def4ef2db334067f7f6ff00abaee7761fbc3de2e07dd742019119a3459"
FEATURE_SHA = "e8bf51556d3d2e08d3d79c6b23a20f9d1ef76018364c701c06f6abf9d993fec5"
ADDRESS_RE = re.compile(r"^0x[0-9a-f]{40}$")
FIELDS = [
    "wallet_address",
    "fill_count",
    "first_fill_time",
    "last_fill_time",
    "distinct_coin_count",
    "side_a_count",
    "side_b_count",
    "crossed_true_count",
    "liquidation_associated_fill_count",
    "duplicate_tid_count",
    "sum_abs_px_times_sz_notional_proxy",
    "sum_closed_pnl_fill_statistic",
]
ENTRY_HASHES = {
    "r9-context.json": (1621, "daa8b40bf915f3c399b6574351b5c9130e61e1bedc8b50e7c4c6e5968f7a1812"),
    "r9-result.json": (3919, "319f0830605447d290dc23d81b79ff1a0248161b050cb0e3aaeb79f89a118621"),
    "r9-wallet-features.ndjson": (334216, FEATURE_SHA),
    "r9.rc": (2, "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa"),
    "R9_FILES.sha256": (327, "7f6bca0e7cc6faeb99a52c50a6b655adc8f84bf4a3f45c31d3f64a53676014c8"),
}
PART_HASHES = [
    ("artifact/r9-modern-wallet-features-31336490854.zip.b64.part00", 16000, "cf18a8d02e0fdbce03004e77410824e77371a50e63a7f9ab844b852b5866b4db"),
    ("artifact/r9-modern-wallet-features-31336490854.zip.b64.part01", 16000, "75d77a4b2cd44caa9587a45d8ac95cedcac972e97fea7a3f41bb36e3a70f2cab"),
    ("artifact/r9-modern-wallet-features-31336490854.zip.b64.part02", 16000, "c5c04e28ab53d3a841ba0c3823cf0346783c61a8ae13250c918ba7d2d8816c3d"),
    ("artifact/r9-modern-wallet-features-31336490854.zip.b64.part03", 16000, "16e612048d7942b17696505c268cb9b79013bd7ddac00296a3bb7014dae8fb12"),
    ("artifact/r9-modern-wallet-features-31336490854.zip.b64.part04", 448, "64f4d6dc1f8c96f24b352526f9d3e8019952dabbc1e0e07113adf799d1bb90f2"),
]


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def reconstruct_zip() -> bytes:
    pieces: list[bytes] = []
    for relative, size, digest in PART_HASHES:
        payload = (RUN / relative).read_bytes()
        assert len(payload) == size, relative
        assert sha(payload) == digest, relative
        pieces.append(payload)
    encoded = b"".join(pieces)
    assert len(encoded) == 64448
    decoded = base64.b64decode(encoded, validate=True)
    assert len(decoded) == 48334
    assert sha(decoded) == ZIP_SHA
    return decoded


def main() -> int:
    reconstruction = load(RECONSTRUCTION)
    verification = load(VERIFICATION)
    diagnostics = load(DIAGNOSTICS)
    attestation = load(ATTESTATION)
    consumption = load(CONSUMPTION)
    activation = load(ACTIVATION)

    assert reconstruction["workflow_run_id"] == 31336490854
    assert reconstruction["workflow_job_id"] == 93303097917
    assert reconstruction["artifact_id"] == 9044483094
    assert reconstruction["artifact_size_bytes"] == 48334
    assert reconstruction["artifact_zip_sha256"] == ZIP_SHA
    assert reconstruction["base64_character_count"] == 64448

    zip_bytes = reconstruct_zip()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        assert archive.namelist() == list(ENTRY_HASHES)
        retained: dict[str, bytes] = {}
        for name, (size, digest) in ENTRY_HASHES.items():
            data = archive.read(name)
            assert len(data) == size, name
            assert sha(data) == digest, name
            retained[name] = data

    assert CONTEXT_COPY.read_bytes() == retained["r9-context.json"]
    assert RESULT_COPY.read_bytes() == retained["r9-result.json"]
    assert RC_COPY.read_bytes() == retained["r9.rc"] == b"0\n"
    assert LEDGER_COPY.read_bytes() == retained["R9_FILES.sha256"]

    ledger_expected = "".join(
        f"{digest}  {name}\n"
        for name, (_, digest) in ENTRY_HASHES.items()
        if name != "R9_FILES.sha256"
    )
    assert retained["R9_FILES.sha256"].decode("utf-8") == ledger_expected

    context = json.loads(retained["r9-context.json"])
    result = json.loads(retained["r9-result.json"])
    assert context["workflow_run_id"] == 31336490854
    assert context["workflow_run_attempt"] == 1
    assert context["dispatch_sha"] == context["checked_out_commit"] == "42791333fccee2262aa0d35fea85997eeb0dc332"
    assert context["dispatch_ref"] == "refs/heads/main"
    assert context["configure_aws_outcome"] == "success"
    assert context["boundary_fixture_role"] == "SERIALIZER_AND_FEATURE_PIPELINE_FIXTURE_ONLY"
    assert context["canonical_cross_format_history_use_authorized"] is False
    assert context["historical_multi_hour_ingestion_authorized"] is False
    assert context["wallet_ranking_authorized"] is False
    assert context["candidate_shortlisting_authorized"] is False
    assert context["pnl_or_alpha_analysis_authorized"] is False
    assert context["copyability_analysis_authorized"] is False

    assert result["terminal_status"] == "R9_MODERN_WALLET_FEATURE_STUDY_COMPLETE"
    assert result["technical_result"] == "MODERN_WALLET_FEATURE_PIPELINE_COMPLETE"
    assert result["research_conclusion"] == "MODERN_WALLET_FEATURE_PIPELINE_COMPLETE"
    assert result["request_attempt_count"] == 1
    assert result["s3_http_request_count"] == 1
    assert result["successful_request_count"] == 1
    assert result["failed_request_count"] == 0
    assert result["retries_used"] == 0
    assert result["http_redirects_followed"] is False
    assert result["compressed_bytes"] == 1517603
    assert result["compressed_sha256"] == "928e1cd6bd7d69ad7243c263bacee48e53e4762ae9e99ef75f45007f6c0e6105"
    assert result["decompressed_bytes"] == 7380378

    summary = result["wallet_feature_summary"]
    assert summary["top_level_block_record_count"] == 4345
    assert summary["valid_event_pair_count"] == 17516
    assert summary["wallet_feature_row_count"] == 887
    assert summary["wallet_feature_bytes"] == 334216
    assert summary["wallet_feature_sha256"] == FEATURE_SHA
    assert summary["wallet_feature_fields_only"] == FIELDS
    assert summary["sum_fill_count"] == 17516
    assert summary["sum_side_count"] == 17516
    assert summary["wallet_feature_sort_order"] == "WALLET_ADDRESS_LEXICOGRAPHIC_ASCENDING"

    for key in (
        "raw_block_records_retained",
        "raw_compressed_object_persisted",
        "raw_decompressed_payload_retained",
        "raw_event_pairs_retained",
        "raw_fill_objects_retained",
        "coin_values_retained",
        "side_values_retained",
        "individual_time_values_retained",
        "individual_price_values_retained",
        "individual_size_values_retained",
        "individual_closed_pnl_values_retained",
        "trade_id_values_retained",
        "crossed_values_retained",
        "liquidation_payload_values_retained",
        "wallet_ranking_performed",
        "candidate_shortlisting_performed",
        "pnl_or_alpha_analysis_performed",
        "copyability_analysis_performed",
        "public_api_enrichment_performed",
        "entity_clustering_performed",
        "market_data_ingested",
        "strategy_inference_performed",
        "historical_multi_hour_ingestion_performed",
        "legacy_modern_merged_history_performed",
        "sum_closed_pnl_interpreted_as_exact_account_return",
        "sum_closed_pnl_used_as_wallet_ranking_score",
        "notional_proxy_interpreted_as_copyable_notional",
        "boundary_fixture_historical_representativeness_inferred",
        "canonical_cross_format_history_used",
    ):
        assert result[key] is False, key

    rows = [json.loads(line) for line in retained["r9-wallet-features.ndjson"].decode("utf-8").splitlines() if line]
    assert len(rows) == 887
    addresses: list[str] = []
    fill_total = side_total = crossed_total = liquidation_total = duplicate_total = 0
    notional_total = Decimal("0")
    closed_total = Decimal("0")
    positive = zero = negative = 0
    fill_counts: list[int] = []
    coin_counts: list[int] = []
    first_times: list[int] = []
    last_times: list[int] = []

    for row in rows:
        assert list(row) == FIELDS
        address = row["wallet_address"]
        assert isinstance(address, str) and ADDRESS_RE.fullmatch(address)
        addresses.append(address)
        for name in (
            "fill_count", "first_fill_time", "last_fill_time", "distinct_coin_count", "side_a_count",
            "side_b_count", "crossed_true_count", "liquidation_associated_fill_count", "duplicate_tid_count",
        ):
            assert isinstance(row[name], int) and not isinstance(row[name], bool), (address, name)
        assert row["fill_count"] >= 1
        assert row["first_fill_time"] <= row["last_fill_time"]
        assert row["distinct_coin_count"] >= 1
        assert row["side_a_count"] + row["side_b_count"] == row["fill_count"]
        assert 0 <= row["crossed_true_count"] <= row["fill_count"]
        assert 0 <= row["liquidation_associated_fill_count"] <= row["fill_count"]
        assert 0 <= row["duplicate_tid_count"] <= row["fill_count"]
        notional = Decimal(row["sum_abs_px_times_sz_notional_proxy"])
        closed = Decimal(row["sum_closed_pnl_fill_statistic"])
        assert notional >= 0
        fill_total += row["fill_count"]
        side_total += row["side_a_count"] + row["side_b_count"]
        crossed_total += row["crossed_true_count"]
        liquidation_total += row["liquidation_associated_fill_count"]
        duplicate_total += row["duplicate_tid_count"]
        notional_total += notional
        closed_total += closed
        positive += closed > 0
        zero += closed == 0
        negative += closed < 0
        fill_counts.append(row["fill_count"])
        coin_counts.append(row["distinct_coin_count"])
        first_times.append(row["first_fill_time"])
        last_times.append(row["last_fill_time"])

    assert addresses == sorted(addresses)
    assert len(set(addresses)) == 887
    assert fill_total == side_total == 17516
    assert crossed_total == 8758
    assert liquidation_total == 0
    assert duplicate_total == 0
    assert notional_total == Decimal("41195607.73093746")
    assert closed_total == Decimal("-8612.81910500")
    assert (positive, zero, negative) == (278, 301, 308)
    assert (min(fill_counts), statistics.median(fill_counts), max(fill_counts)) == (1, 3, 970)
    assert (min(coin_counts), statistics.median(coin_counts), max(coin_counts)) == (1, 1, 161)
    assert min(first_times) == 1753606210273
    assert max(last_times) == 1753606799895
    assert max(last_times) - min(first_times) == 589622

    assert diagnostics["wallet_feature_row_count"] == 887
    assert diagnostics["sum_fill_count"] == 17516
    assert diagnostics["sum_side_count"] == 17516
    assert diagnostics["crossed_true_count_total"] == 8758
    assert diagnostics["liquidation_associated_fill_count_total"] == 0
    assert diagnostics["duplicate_tid_count_total"] == 0
    assert diagnostics["sum_abs_px_times_sz_notional_proxy_total"] == "41195607.73093746"
    assert diagnostics["sum_closed_pnl_fill_statistic_total"] == "-8612.81910500"
    assert diagnostics["global_first_retained_fill_time_ms"] == 1753606210273
    assert diagnostics["global_last_retained_fill_time_ms"] == 1753606799895
    assert diagnostics["observed_feature_time_span_ms"] == 589622
    assert all(v is False for v in diagnostics["interpretation_boundaries"].values())
    assert all(v is False for v in diagnostics["downstream_actions_performed"].values())

    assert verification["verification_status"] == "PASS"
    assert verification["artifact_zip_sha256"] == ZIP_SHA or verification["observed_artifact_zip_sha256"] == ZIP_SHA
    assert all(verification["checks"].values())

    assert consumption["status"] == "CONSUMED_BY_CANONICAL_R9_RUN"
    assert consumption["release_consumed"] is True
    assert consumption["workflow_run_id"] == 31336490854
    assert consumption["workflow_job_id"] == 93303097917
    assert consumption["artifact_id"] == 9044483094
    assert consumption["artifact_zip_sha256"] == ZIP_SHA
    assert consumption["successful_get_object_requests"] == 1
    assert consumption["remaining_get_object_budget"] == 0
    assert consumption["future_r9_dispatch_authorized"] is False
    assert consumption["rerun_authorized"] is False
    assert all(v is False for v in consumption["downstream_authorizations"].values())
    assert all(v is False for v in consumption["trading_authorizations"].values())

    assert activation["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R9_RUN"
    assert activation["canonical_dispatch_ref_required"] == "refs/heads/main"
    assert activation["rerun_authorized"] is False

    assert attestation["status"] == "ATTESTED_COMPLETE"
    assert attestation["execution_identity"]["workflow_run_id"] == 31336490854
    assert attestation["technical_result"] == "MODERN_WALLET_FEATURE_PIPELINE_COMPLETE"
    assert attestation["release_consumed"] is True
    assert attestation["rerun_authorized"] is False
    assert attestation["all_trading_and_capital_authorizations_remain_false"] is True

    conclusion = CONCLUSION.read_text(encoding="utf-8")
    boundary = BOUNDARY.read_text(encoding="utf-8")
    assert "MODERN_WALLET_FEATURE_PIPELINE_COMPLETE" in conclusion
    assert "2025-07-27T08:50:10.273Z" in conclusion
    assert "2025-07-27T08:59:59.895Z" in conclusion
    assert "wallet ranking" in conclusion.lower()
    assert "not prove" in conclusion.lower()
    assert "2025-07-27T08:50:10.273Z" in boundary
    assert "2025-07-27T08:59:59.895Z" in boundary
    assert "censored" in boundary.lower()

    print("R9_EVIDENCE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
