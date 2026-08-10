from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import zipfile
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
EVIDENCE = BASE / "r10d_evidence"
RUN = EVIDENCE / "run-31420197671"
RECON = RUN / "ARTIFACT_RECONSTRUCTION.json"
VERIFY = RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json"
ATTEST = EVIDENCE / "HL-ARCHIVE-R10D-RECORD-ANCHORED-MULTI-HOUR-FEATURE-REPAIR-001-ATTESTATION.json"
DIAG = EVIDENCE / "R10D_AGGREGATE_DIAGNOSTICS.json"
CONSUMPTION = BASE / "r10d_runtime/R10D_EXECUTION_RELEASE_CONSUMPTION.json"
RELEASE = BASE / "r10d_runtime/R10D_EXECUTION_RELEASE.json"
ZIP_SHA = "4e63afc141f98ee05030ce19effc88f3bbd1eab59796c716a5d3c671eb2476ae"
FEATURE_SHA = "ea83c15398ed7b3c76d0be52aed0d9472ace3c975ac416fcd4a6d95760c4c991"
ADDRESS_RE = re.compile(r"^0x[0-9a-f]{40}$")
FIELDS = [
    "wallet_address", "fill_count", "active_hour_count", "first_fill_time", "last_fill_time",
    "distinct_coin_count", "side_a_count", "side_b_count", "crossed_true_count",
    "liquidation_associated_fill_count", "duplicate_tid_count",
    "sum_abs_px_times_sz_notional_proxy", "sum_closed_pnl_fill_statistic",
]
PER_HOUR = [
    ("2025-07-27T09:00:00Z", 36029, 223950, 2, 223948, 0, 36028, 1, "42fa96f9d693eb93d184c24a830483cea2e4aa526fc2ffb999619d24e41cc339"),
    ("2025-07-27T10:00:00Z", 35587, 259912, 0, 259912, 0, 35586, 1, "0c2384598e14285ac15ae407ffbd026c65358c62a0c39a31ad86568cb3aa9add"),
    ("2025-07-27T11:00:00Z", 31037, 214154, 0, 214154, 0, 31035, 2, "00c71819e479c2a122756649c6b8829e8ff7f1dcd7c07a9436b8057c6c6b863d"),
    ("2025-07-27T12:00:00Z", 44723, 266614, 0, 266614, 0, 44723, 0, "8e60a9ea850c5f40e5c8d09b0915b6cf9d0fbbe3f34083562af9b530f63e7397"),
    ("2025-07-27T13:00:00Z", 47121, 257604, 0, 257604, 0, 47121, 0, "651b19b905d0bbb37aa908275d327dec0cfcd7c2ae2bb35b498d0294a8414fad"),
    ("2025-07-27T14:00:00Z", 46917, 264308, 8, 264300, 0, 46916, 1, "f612995d9f83b7a902890f18faaf61b2eaa0ed7a45f59f859315ed3bfe5021e7"),
]

def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def reconstruct() -> tuple[bytes, dict[str, bytes]]:
    meta = load(RECON)
    assert meta["workflow_run_id"] == 31420197671
    assert meta["workflow_job_id"] == 93558813495
    assert meta["artifact_id"] == 9075129362
    assert meta["artifact_size_bytes"] == 918968
    assert meta["artifact_zip_sha256"] == ZIP_SHA
    pieces = []
    for row in meta["base64_parts"]:
        payload = (RUN / row["path"]).read_bytes()
        assert len(payload) == row["character_count"]
        assert sha(payload) == row["sha256"]
        pieces.append(payload)
    encoded = b"".join(pieces)
    assert len(encoded) == meta["base64_character_count"] == 1225292
    decoded = base64.b64decode(encoded, validate=True)
    assert len(decoded) == 918968 and sha(decoded) == ZIP_SHA
    retained = {}
    with zipfile.ZipFile(io.BytesIO(decoded)) as z:
        assert z.namelist() == [row["name"] for row in meta["zip_entries"]]
        for row in meta["zip_entries"]:
            data = z.read(row["name"])
            assert len(data) == row["size_bytes"]
            assert sha(data) == row["sha256"]
            retained[row["name"]] = data
    return decoded, retained

def main() -> int:
    _, retained = reconstruct()
    for name in ("r10d-context.json", "r10d-result.json", "r10d.rc", "R10D_FILES.sha256"):
        assert (RUN / name).read_bytes() == retained[name]
    assert retained["r10d.rc"] == b"0\n"
    ledger = {}
    for line in retained["R10D_FILES.sha256"].decode().splitlines():
        digest, name = line.split("  ", 1); ledger[name] = digest
    expected = {name: sha(retained[name]) for name in ("r10d-context.json","r10d-result.json","r10d-wallet-features.ndjson","r10d.rc")}
    assert ledger == expected

    context = json.loads(retained["r10d-context.json"])
    result = json.loads(retained["r10d-result.json"])
    assert context["workflow_run_id"] == 31420197671 and context["workflow_run_attempt"] == 1
    assert context["dispatch_sha"] == context["checked_out_commit"] == "c3e893da2e25d993250258f9b4b81aa5ad332e77"
    assert context["dispatch_ref"] == "refs/heads/main" and context["configure_aws_outcome"] == "success"
    assert context["maximum_get_object_requests"] == 6 and context["maximum_retries_per_request"] == 0
    assert context["record_anchored_rule_id"] == "RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1"
    assert context["numeric_tolerance_authorized"] is False
    for key in ("wallet_ranking_authorized","pnl_or_alpha_analysis_authorized","copyability_analysis_authorized","metadata_timezone_parsing_authorized","metadata_timezone_inference_authorized"):
        assert context[key] is False

    assert result["terminal_status"] == "R10D_MULTI_HOUR_FEATURE_REPAIR_STUDY_COMPLETE"
    assert result["technical_result"] == result["research_conclusion"] == "R10D_MULTI_HOUR_FEATURE_PIPELINE_COMPLETE"
    assert result["completed_hour_count"] == 6
    assert result["request_attempt_count"] == result["s3_http_request_count"] == result["successful_request_count"] == 6
    assert result["failed_request_count"] == result["retries_used"] == 0
    assert result["http_redirects_followed"] is False
    assert result["total_compressed_bytes"] == 120999698
    assert result["total_decompressed_bytes"] == 599233794
    assert result["numeric_tolerance_authorized"] is False
    assert result["record_anchored_rule_id"] == "RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1"
    assert len(result["per_hour_summaries"]) == 6
    for hour, expected_hour in zip(result["per_hour_summaries"], PER_HOUR):
        path_hour, blocks, events, before, inside, after, path_records, prev_records, compressed_sha = expected_hour
        assert hour["path_hour_utc"] == path_hour
        assert hour["block_record_count"] == blocks and hour["event_pair_count"] == events
        assert hour["fill_time_before_path_hour_count"] == before
        assert hour["fill_time_inside_path_hour_count"] == inside
        assert hour["fill_time_after_path_hour_count"] == after == 0
        assert hour["local_path_block_path_record_count"] == path_records
        assert hour["local_path_block_previous_record_count"] == prev_records
        assert hour["record_anchored_alignment_violation_count"] == 0
        assert hour["compressed_sha256"] == compressed_sha
        assert path_records + prev_records == blocks
        assert before + inside + after == events
    assert result["per_hour_summaries"][0]["before_fills_in_local_path_block_previous_records"] == 2
    assert result["per_hour_summaries"][5]["before_fills_in_local_path_block_previous_records"] == 8

    summary = result["aggregate_wallet_feature_summary"]
    assert summary["wallet_feature_row_count"] == 16410
    assert summary["wallet_feature_bytes"] == 6557323
    assert summary["wallet_feature_sha256"] == FEATURE_SHA
    assert summary["wallet_feature_fields_only"] == FIELDS
    assert summary["sum_fill_count"] == summary["sum_side_count"] == 1486542
    assert summary["duplicate_wallet_tid_count"] == 0
    feature = retained["r10d-wallet-features.ndjson"]
    assert len(feature) == 6557323 and sha(feature) == FEATURE_SHA
    rows = [json.loads(line) for line in feature.decode().splitlines() if line]
    assert len(rows) == 16410
    addresses=[]; active=Counter(); fills=sides=crossed=liq=dups=0
    notional=Decimal("0"); closed=Decimal("0"); first=[]; last=[]
    for row in rows:
        assert list(row) == FIELDS
        assert ADDRESS_RE.fullmatch(row["wallet_address"]); addresses.append(row["wallet_address"])
        assert 1 <= row["active_hour_count"] <= 6; active[row["active_hour_count"]] += 1
        assert row["fill_count"] >= 1 and row["side_a_count"] + row["side_b_count"] == row["fill_count"]
        assert row["duplicate_tid_count"] == 0 and row["first_fill_time"] <= row["last_fill_time"]
        fills += row["fill_count"]; sides += row["side_a_count"] + row["side_b_count"]
        crossed += row["crossed_true_count"]; liq += row["liquidation_associated_fill_count"]; dups += row["duplicate_tid_count"]
        notional += Decimal(row["sum_abs_px_times_sz_notional_proxy"]); closed += Decimal(row["sum_closed_pnl_fill_statistic"])
        first.append(row["first_fill_time"]); last.append(row["last_fill_time"])
    assert addresses == sorted(addresses) and len(set(addresses)) == 16410
    assert active == Counter({1:8388,2:3305,3:1508,4:981,5:639,6:1589})
    assert fills == sides == 1486542 and crossed == 743271 and liq == 1330 and dups == 0
    assert notional == Decimal("3670148918.05560308")
    assert closed == Decimal("308059.4394867907")
    assert min(first) == 1753606799949 and max(last) == 1753628399848

    for key in ("wallet_ranking_performed","candidate_shortlisting_performed","pnl_or_alpha_analysis_performed","copyability_analysis_performed","public_api_enrichment_performed","entity_clustering_performed","market_data_ingested","strategy_inference_performed","sum_closed_pnl_interpreted_as_exact_account_return","sum_closed_pnl_used_as_wallet_ranking_score","notional_proxy_interpreted_as_copyable_notional","active_hour_count_interpreted_as_wallet_quality_score","local_time_interpreted_as_partition_semantics","block_time_interpreted_as_partition_semantics","fill_time_interpreted_as_partition_semantics"):
        assert result[key] is False

    verify=load(VERIFY)
    assert verify["provider_digest"] == f"sha256:{ZIP_SHA}"
    assert verify["provider_zip_sha256"] == verify["independently_downloaded_zip_sha256"] == ZIP_SHA
    assert verify["provider_digest_matches_independent_download"] is True
    assert verify["internal_ledger_matches_all_retained_files"] is True
    assert verify["artifact_reconstructable_from_repository_parts"] is True
    assert verify["job_conclusion"] == "success"

    diag=load(DIAG)
    assert diag["wallet_feature_row_count"] == 16410 and diag["sum_fill_count"] == diag["sum_side_count"] == 1486542
    assert diag["active_hour_count_distribution"] == {"1":8388,"2":3305,"3":1508,"4":981,"5":639,"6":1589}
    assert diag["crossed_true_count_total"] == 743271 and diag["liquidation_associated_fill_count_total"] == 1330 and diag["duplicate_tid_count_total"] == 0
    assert diag["sum_abs_px_times_sz_notional_proxy_total"] == "3670148918.05560308"
    assert diag["sum_closed_pnl_fill_statistic_total"] == "308059.4394867907"
    assert all(v is False for v in diag["interpretation_boundaries"].values())
    assert all(v is False for v in diag["downstream_actions_performed"].values())

    attest=load(ATTEST)
    assert attest["status"] == "ATTESTED_COMPLETE_R10D_MULTI_HOUR_FEATURE_PIPELINE"
    assert attest["workflow_run_id"] == 31420197671 and attest["workflow_job_id"] == 93558813495 and attest["artifact_id"] == 9075129362
    assert attest["artifact_zip_sha256"] == ZIP_SHA and attest["release_consumed"] is True and attest["rerun_authorized"] is False
    assert all(v is False for v in attest["claims_not_proven"].values())
    assert all(v is False for v in attest["downstream_authorizations"].values())
    assert all(v is False for v in attest["trading_authorizations"].values())

    consumption=load(CONSUMPTION)
    assert consumption["status"] == "CONSUMED_SUCCESS_R10D_MULTI_HOUR_FEATURE_PIPELINE_COMPLETE"
    assert consumption["release_consumed"] is True and consumption["future_r10d_dispatch_authorized"] is False and consumption["rerun_authorized"] is False
    assert consumption["remaining_get_object_budget_from_consumed_release"] == 0
    assert consumption["new_network_request_requires_new_preregistration_approval_and_release"] is True
    assert all(v is False for v in consumption["downstream_authorizations"].values())
    assert all(v is False for v in consumption["trading_authorizations"].values())

    release=load(RELEASE)
    assert release["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R10D_RUN"
    assert release["release_consumed"] is False and release["rerun_authorized"] is False
    print("R10D_EXECUTION_EVIDENCE_VALID_MULTI_HOUR_FEATURE_PIPELINE_COMPLETE")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
