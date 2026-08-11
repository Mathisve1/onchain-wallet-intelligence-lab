from __future__ import annotations

import base64
import hashlib
import io
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = Path("research/archive_inventory")
EVIDENCE = BASE / "r11_evidence"
RUN = EVIDENCE / "run-31436753081"
CONSUMPTION = BASE / "r11_runtime/R11_EXECUTION_RELEASE_CONSUMPTION.json"
RELEASE = BASE / "r11_runtime/R11_EXECUTION_RELEASE.json"
PREREGISTRATION = BASE / "r11/R11_72H_PERSISTENCE_SCALING_PREREGISTRATION.json"

RUN_ID = 31436753081
JOB_ID = 93612467250
ARTIFACT_ID = 9082810554
DISPATCH_SHA = "baca1925c23ef6b0136aa3d96d6d479ac7717bdf"
ARTIFACT_SHA256 = "45ee57df7a63561bef1772d8612d5fe32b06b9c407d9c1464ce0a02b65a15cc5"
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
EXPECTED_ENTRIES = (
    "r11-context.json",
    "r11-result.json",
    "r11-wallet-features.ndjson",
    "r11.rc",
    "R11_FILES.sha256",
)
HASHED_ENTRIES = EXPECTED_ENTRIES[:-1]


class R11EvidenceError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise R11EvidenceError(message)


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON root must be an object: {path}")
    return value


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_retained_zip(root: Path) -> tuple[bytes, dict[str, bytes]]:
    run = root / RUN
    reconstruction = load_json(run / "ARTIFACT_RECONSTRUCTION.json")
    encoded = (run / "artifact/r11-72h-persistence-31436753081.zip.b64").read_bytes()
    try:
        archive = base64.b64decode(b"".join(encoded.split()), validate=True)
    except Exception as exc:  # pragma: no cover - exact decoder exception is implementation detail
        raise R11EvidenceError("retained artifact base64 is invalid") from exc
    require(len(archive) == 10866 == reconstruction["decoded_size_bytes"], "artifact size drift")
    require(sha256(archive) == ARTIFACT_SHA256 == reconstruction["decoded_sha256"], "artifact SHA-256 drift")
    with zipfile.ZipFile(io.BytesIO(archive), "r") as bundle:
        names = tuple(info.filename for info in bundle.infolist())
        require(len(names) == len(set(names)), "artifact contains duplicate entry names")
        require(set(names) == set(EXPECTED_ENTRIES), "artifact entry set drift")
        require(all(not name.startswith(("/", "\\")) and ".." not in Path(name).parts for name in names), "unsafe artifact entry")
        entries = {name: bundle.read(name) for name in names}
    require(reconstruction["exact_zip_entry_names"] == list(EXPECTED_ENTRIES), "reconstruction entry contract drift")
    for name, data in entries.items():
        require((run / name).read_bytes() == data, f"retained raw entry differs from ZIP: {name}")
    return archive, entries


def parse_ledger(data: bytes) -> dict[str, str]:
    ledger: dict[str, str] = {}
    for raw in data.decode("utf-8", errors="strict").splitlines():
        digest, separator, name = raw.partition("  ")
        require(separator == "  " and len(digest) == 64 and name, "malformed internal ledger row")
        require(name not in ledger, "duplicate internal ledger path")
        ledger[name] = digest
    require(set(ledger) == set(HASHED_ENTRIES), "internal ledger entry set drift")
    return ledger


def validate(root: Path = ROOT) -> None:
    _, entries = decode_retained_zip(root)
    ledger = parse_ledger(entries["R11_FILES.sha256"])
    for name in HASHED_ENTRIES:
        require(sha256(entries[name]) == ledger[name], f"internal ledger hash mismatch: {name}")
    require(entries["r11-wallet-features.ndjson"] == b"", "unresolved R11 feature output must be empty")
    require(entries["r11.rc"] == b"0\n", "R11 return-code evidence drift")

    context = json.loads(entries["r11-context.json"])
    result = json.loads(entries["r11-result.json"])
    verification = load_json(root / RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
    attestation = load_json(root / EVIDENCE / "HL-ARCHIVE-R11-72H-PERSISTENCE-SCALING-001-ATTESTATION.json")
    diagnostics = load_json(root / EVIDENCE / "R11_AGGREGATE_DIAGNOSTICS.json")
    consumption = load_json(root / CONSUMPTION)
    release = load_json(root / RELEASE)
    prereg = load_json(root / PREREGISTRATION)

    require(context["workflow_run_id"] == RUN_ID and context["workflow_run_attempt"] == 1, "context run identity drift")
    require(context["dispatch_sha"] == context["checked_out_commit"] == DISPATCH_SHA, "context dispatch identity drift")
    require(context["dispatch_ref"] == "refs/heads/main" and context["event_name"] == "workflow_dispatch", "context dispatch route drift")
    require(context["configure_aws_outcome"] == "success", "AWS configuration outcome drift")
    require(context["maximum_get_object_requests"] == 72 and context["maximum_retries_per_request"] == 0, "context request envelope drift")

    require(result["terminal_status"] == "R11_72H_PERSISTENCE_STUDY_COMPLETE", "terminal status drift")
    require(result["technical_result"] == result["research_conclusion"] == "R11_72H_PERSISTENCE_PIPELINE_UNRESOLVED", "research result drift")
    require(result["failure_class"] == "duplicate wallet+tid observations require investigation; blind deduplication forbidden", "failure class drift")
    require(result["aggregate_wallet_feature_summary"] is None and result["wallet_feature_retained"] is False, "unresolved feature-retention drift")
    require(result["completed_hour_count"] == 72 and result["completed_day_count"] == 3, "completion cardinality drift")
    require(result["request_attempt_count"] == result["successful_request_count"] == result["s3_http_request_count"] == 72, "request conservation drift")
    require(result["failed_request_count"] == result["retries_used"] == 0, "failure/retry drift")
    require(result["http_redirects_followed"] is False, "redirect boundary drift")
    require(result["total_compressed_bytes"] == 2107738436 and result["total_decompressed_bytes"] == 10539979245, "byte totals drift")
    require(result["record_anchored_rule_id"] == "RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1", "alignment rule drift")
    require(result["numeric_tolerance_authorized"] is False, "numeric tolerance reopened")

    hours = result["per_hour_summaries"]
    days = result["per_day_summaries"]
    require(isinstance(hours, list) and len(hours) == 72, "per-hour evidence cardinality drift")
    require(isinstance(days, list) and len(days) == 3, "per-day evidence cardinality drift")
    sums = {
        key: sum(int(row[key]) for row in hours)
        for key in (
            "block_record_count", "event_pair_count", "local_path_block_path_record_count",
            "local_path_block_previous_record_count", "fill_time_before_path_hour_count",
            "fill_time_inside_path_hour_count", "fill_time_after_path_hour_count",
            "before_fills_in_local_path_block_previous_records", "record_anchored_alignment_violation_count",
        )
    }
    require(sums["block_record_count"] == 3283391, "block total drift")
    require(sums["event_pair_count"] == 26384234, "event total drift")
    require(sums["local_path_block_path_record_count"] == 3283297, "path-block total drift")
    require(sums["local_path_block_previous_record_count"] == 94, "previous-block total drift")
    require(sums["fill_time_before_path_hour_count"] == sums["before_fills_in_local_path_block_previous_records"] == 490, "pre-hour fill total drift")
    require(sums["fill_time_inside_path_hour_count"] == 26383744, "inside-hour fill total drift")
    require(sums["fill_time_after_path_hour_count"] == sums["record_anchored_alignment_violation_count"] == 0, "alignment failure drift")
    require(sums["block_record_count"] == sums["local_path_block_path_record_count"] + sums["local_path_block_previous_record_count"], "block-prefix conservation failed")
    require(sums["event_pair_count"] == sums["fill_time_before_path_hour_count"] + sums["fill_time_inside_path_hour_count"] + sums["fill_time_after_path_hour_count"], "fill-partition conservation failed")
    require(sum(day["block_record_count"] for day in days) == sums["block_record_count"], "per-day block conservation failed")
    require(sum(day["event_pair_count"] for day in days) == sums["event_pair_count"], "per-day event conservation failed")
    require(sum(day["fill_time_before_path_hour_count"] for day in days) == 490, "per-day pre-hour conservation failed")

    require(verification["provider_sha256"] == verification["independently_supplied_zip_sha256"] == ARTIFACT_SHA256, "provider artifact binding drift")
    require(verification["artifact_id"] == ARTIFACT_ID and verification["run_id"] == RUN_ID and verification["job_id"] == JOB_ID, "verification identity drift")
    require(verification["internal_ledger"] == ledger and verification["internal_ledger_matches_all_retained_raw_files"] is True, "verification ledger drift")
    require(verification["duplicate_wallet_tid_count_known_from_retained_evidence"] is False, "duplicate count overclaim")
    require(verification["duplicate_wallet_tid_locations_known_from_retained_evidence"] is False, "duplicate location overclaim")

    rules = prereg["cross_object_aggregation_rules"]
    require(rules["duplicate_wallet_tid_count_retained"] is True, "preregistered duplicate-retention promise drift")
    require(attestation["preregistered_duplicate_wallet_tid_count_retention_met"] is False, "attestation hides preregistration deviation")
    require(diagnostics["duplicate_wallet_tid_count_retention_was_preregistered"] is True, "diagnostics hide preregistration promise")
    require(diagnostics["duplicate_wallet_tid_count_retention_met"] is False, "diagnostics hide retention failure")
    require(diagnostics["duplicate_wallet_tid_count_known_from_retained_evidence"] is False, "diagnostics overclaim duplicate count")
    require(diagnostics["duplicate_wallet_tid_locations_known_from_retained_evidence"] is False, "diagnostics overclaim duplicate locations")
    require(diagnostics["event_pair_count"] == sums["event_pair_count"] and diagnostics["block_record_count"] == sums["block_record_count"], "diagnostic totals drift")

    require(release["release_consumed"] is False, "immutable pre-run release snapshot was rewritten")
    require(release["rerun_authorized"] is False, "immutable release permits rerun")
    require(consumption["release_consumed"] is True and consumption["remaining_get_object_budget_from_consumed_release"] == 0, "consumption not fail-closed")
    require(consumption["future_r11_dispatch_authorized"] is False and consumption["rerun_authorized"] is False, "consumption reopens R11")
    require(consumption["workflow_run_id"] == RUN_ID and consumption["workflow_job_id"] == JOB_ID and consumption["artifact_id"] == ARTIFACT_ID, "consumption identity drift")
    require(consumption["canonical_dispatch_sha"] == DISPATCH_SHA and consumption["artifact_zip_sha256"] == ARTIFACT_SHA256, "consumption provenance drift")
    require(consumption["preregistered_duplicate_wallet_tid_count_retention_met"] is False, "consumption hides evidence failure")
    require(consumption["duplicate_wallet_tid_count_known"] is False and consumption["duplicate_root_cause_known"] is False, "consumption overclaims root cause")

    require(all(value is False for value in attestation["claims_not_proven"].values()), "attestation marks an unproven claim true")
    require(all(value is False for value in attestation["downstream_authorizations"].values()), "attestation opens downstream authority")
    require(all(value is False for value in attestation["trading_authorizations"].values()), "attestation opens trading authority")
    require(all(value is False for value in consumption["downstream_authorizations"].values()), "consumption opens downstream authority")
    require(all(value is False for value in consumption["trading_authorizations"].values()), "consumption opens trading authority")
    for name in ("R11_RESEARCH_CONCLUSION.md", "README.md"):
        text = (root / EVIDENCE / name).read_text(encoding="utf-8")
        require("R12_READY" not in text and "R11_CLOSED" not in text, f"closure overclaim in {name}")


def main() -> int:
    validate()
    print("R11_EXECUTION_EVIDENCE_VALID_UNRESOLVED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
