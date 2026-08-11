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


def exact_json_equal(actual: object, expected: object) -> bool:
    """Compare JSON values without Python's bool/int equality shortcut."""

    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        assert isinstance(actual, dict)
        return set(actual) == set(expected) and all(
            exact_json_equal(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        assert isinstance(actual, list)
        return len(actual) == len(expected) and all(
            exact_json_equal(left, right) for left, right in zip(actual, expected, strict=True)
        )
    return actual == expected


def require_exact_mapping(actual: object, expected: dict, label: str) -> None:
    require(isinstance(actual, dict), f"{label} must be an object")
    assert isinstance(actual, dict)
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    require(not missing and not extra, f"{label} schema drift: missing={missing}, extra={extra}")
    require(exact_json_equal(actual, expected), f"{label} exact value or type drift")


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
    archive, entries = decode_retained_zip(root)
    ledger = parse_ledger(entries["R11_FILES.sha256"])
    for name in HASHED_ENTRIES:
        require(sha256(entries[name]) == ledger[name], f"internal ledger hash mismatch: {name}")
    require(entries["r11-wallet-features.ndjson"] == b"", "unresolved R11 feature output must be empty")
    require(entries["r11.rc"] == b"0\n", "R11 return-code evidence drift")

    context = json.loads(entries["r11-context.json"])
    result = json.loads(entries["r11-result.json"])
    require(isinstance(context, dict), "retained context root must be an object")
    require(isinstance(result, dict), "retained result root must be an object")
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
    require(verification["duplicate_wallet_tid_observation_exists"] is True, "retained failure-path duplicate observation drift")
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

    expected_claims_proven = {
        "all_72_exact_objects_completed_under_single_use_release": (
            context["selected_hour_count"] == result["completed_hour_count"] == len(hours) == 72
        ),
        "all_72_getobject_requests_succeeded": (
            result["request_attempt_count"]
            == result["successful_request_count"]
            == result["s3_http_request_count"]
            == context["maximum_get_object_requests"]
            == 72
            and result["failed_request_count"] == 0
        ),
        "at_least_one_repeated_normalized_tid_within_one_wallet_state_was_observed": verification[
            "duplicate_wallet_tid_observation_exists"
        ],
        "blind_deduplication_was_not_performed": (
            result["aggregate_wallet_feature_summary"] is None
            and result["wallet_feature_retained"] is False
            and entries["r11-wallet-features.ndjson"] == b""
        ),
        "wallet_feature_output_was_not_retained_after_unresolved_duplicate_condition": (
            result["aggregate_wallet_feature_summary"] is None
            and result["wallet_feature_retained"] is False
            and len(entries["r11-wallet-features.ndjson"]) == 0
            and ledger["r11-wallet-features.ndjson"] == EMPTY_SHA256
        ),
        "zero_after_path_hour_fills": sums["fill_time_after_path_hour_count"] == 0,
        "zero_failed_requests": result["failed_request_count"] == 0,
        "zero_record_anchored_alignment_violations": sums["record_anchored_alignment_violation_count"] == 0,
        "zero_retries": result["retries_used"] == 0,
    }
    require(all(value is True for value in expected_claims_proven.values()), "raw evidence does not prove every attested claim")
    require_exact_mapping(attestation.get("claims_proven"), expected_claims_proven, "attestation claims_proven")

    expected_execution_summary = {
        "aggregate_wallet_feature_summary": result["aggregate_wallet_feature_summary"],
        "block_record_count": sums["block_record_count"],
        "completed_day_count": result["completed_day_count"],
        "completed_hour_count": result["completed_hour_count"],
        "event_pair_count": sums["event_pair_count"],
        "failed_get_object_requests": result["failed_request_count"],
        "fill_time_after_path_hour_count": sums["fill_time_after_path_hour_count"],
        "fill_time_before_path_hour_count": sums["fill_time_before_path_hour_count"],
        "fill_time_inside_path_hour_count": sums["fill_time_inside_path_hour_count"],
        "http_redirects_followed": result["http_redirects_followed"],
        "record_anchored_alignment_violation_count": sums["record_anchored_alignment_violation_count"],
        "request_attempt_count": result["request_attempt_count"],
        "retries_used": result["retries_used"],
        "selected_hour_count": context["selected_hour_count"],
        "successful_get_object_requests": result["successful_request_count"],
        "total_compressed_bytes": result["total_compressed_bytes"],
        "total_decompressed_bytes": result["total_decompressed_bytes"],
        "wallet_feature_bytes": len(entries["r11-wallet-features.ndjson"]),
        "wallet_feature_retained": result["wallet_feature_retained"],
    }
    require_exact_mapping(
        attestation.get("exact_execution_summary"),
        expected_execution_summary,
        "attestation exact_execution_summary",
    )
    require(exact_json_equal(attestation.get("per_day_summaries"), days), "attestation per-day summaries drift from raw result")

    require(release["release_consumed"] is False, "immutable pre-run release snapshot was rewritten")
    require(release["rerun_authorized"] is False, "immutable release permits rerun")
    expected_consumption = {
        "schema_version": "1.0",
        "execution_release_id": release["execution_release_id"],
        "pilot_id": result["pilot_id"],
        "status": "CONSUMED_UNRESOLVED_DUPLICATE_WALLET_TID",
        "release_consumed": True,
        "canonical_dispatch_sha": context["dispatch_sha"],
        "workflow_run_id": context["workflow_run_id"],
        "workflow_job_id": verification["job_id"],
        "workflow_run_attempt": context["workflow_run_attempt"],
        "artifact_id": verification["artifact_id"],
        "artifact_name": verification["artifact_name"],
        "artifact_size_bytes": len(archive),
        "artifact_zip_sha256": sha256(archive),
        "terminal_status": result["terminal_status"],
        "technical_result": result["technical_result"],
        "research_conclusion": result["research_conclusion"],
        "failure_class": result["failure_class"],
        "request_attempt_count": result["request_attempt_count"],
        "successful_get_object_requests": result["successful_request_count"],
        "failed_get_object_requests": result["failed_request_count"],
        "retries_used": result["retries_used"],
        "http_redirects_followed": result["http_redirects_followed"],
        "compressed_bytes_downloaded": result["total_compressed_bytes"],
        "decompressed_bytes": result["total_decompressed_bytes"],
        "completed_hour_count": result["completed_hour_count"],
        "completed_day_count": result["completed_day_count"],
        "wallet_feature_retained": result["wallet_feature_retained"],
        "wallet_feature_bytes": len(entries["r11-wallet-features.ndjson"]),
        "wallet_feature_sha256": ledger["r11-wallet-features.ndjson"],
        "preregistered_duplicate_wallet_tid_count_retention_met": diagnostics[
            "duplicate_wallet_tid_count_retention_met"
        ],
        "duplicate_wallet_tid_count_known": verification[
            "duplicate_wallet_tid_count_known_from_retained_evidence"
        ],
        "duplicate_wallet_tid_locations_known": verification[
            "duplicate_wallet_tid_locations_known_from_retained_evidence"
        ],
        "duplicate_root_cause_known": False,
        "future_r11_dispatch_authorized": False,
        "rerun_authorized": False,
        "remaining_get_object_budget_from_consumed_release": (
            release["maximum_get_object_requests"] - result["request_attempt_count"]
        ),
        "new_network_request_requires_new_preregistration_owner_approval_and_release": True,
        "downstream_authorizations": release["downstream_authorizations"],
        "trading_authorizations": release["trading_authorizations"],
    }
    require_exact_mapping(consumption, expected_consumption, "R11 release consumption")

    expected_attestation_bindings = {
        "artifact_id": verification["artifact_id"],
        "artifact_name": verification["artifact_name"],
        "artifact_zip_sha256": sha256(archive),
        "canonical_dispatch_sha": context["dispatch_sha"],
        "failure_class": result["failure_class"],
        "pilot_id": result["pilot_id"],
        "record_anchored_rule_id": result["record_anchored_rule_id"],
        "release_consumed": consumption["release_consumed"],
        "remaining_get_object_budget_from_consumed_release": consumption[
            "remaining_get_object_budget_from_consumed_release"
        ],
        "rerun_authorized": consumption["rerun_authorized"],
        "preregistered_duplicate_wallet_tid_count_retention_met": diagnostics[
            "duplicate_wallet_tid_count_retention_met"
        ],
        "research_conclusion": result["research_conclusion"],
        "technical_result": result["technical_result"],
        "terminal_status": result["terminal_status"],
        "workflow_job_id": verification["job_id"],
        "workflow_run_attempt": context["workflow_run_attempt"],
        "workflow_run_id": context["workflow_run_id"],
    }
    for key, expected in expected_attestation_bindings.items():
        require(key in attestation and exact_json_equal(attestation[key], expected), f"attestation {key} drift")

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
