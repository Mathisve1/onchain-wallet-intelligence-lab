from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r5"
RUN = BASE / "evidence/run-31321019885"
RESULT = RUN / "r5-format-result.json"
CONTEXT = RUN / "r5-format-context.json"
RC = RUN / "r5-format.rc"
LEDGER = RUN / "R5_FORMAT_FILES.sha256"
VERIFY = RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json"
ATTEST = BASE / "evidence/HL-ARCHIVE-LEGACY-FORMAT-FINGERPRINT-R5-001-ATTESTATION.json"
CONSUMPTION = BASE / "R5_EXECUTION_RELEASE_CONSUMPTION.json"
ACTIVATION = BASE / "R5_EXECUTION_RELEASE_CANONICALIZATION.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    context = load(CONTEXT)
    result = load(RESULT)
    verification = load(VERIFY)
    attestation = load(ATTEST)
    consumption = load(CONSUMPTION)
    activation = load(ACTIVATION)

    assert sha256(CONTEXT) == "41df652baff731b2e819e6221c5298cba4803e459876f72a73a7d18948fca1df"
    assert sha256(RESULT) == "aa54715a3ecd464cbeb3fb9291040fb69d461fa1e50142ca9934ca3fa6512f0b"
    assert sha256(RC) == "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa"
    assert sha256(LEDGER) == "7f8686bbae7d5e8a85f9c645b6a8418811f1aafbaf8cf74b3a3da263be7b9251"
    assert RC.read_text(encoding="utf-8") == "0\n"

    assert context["workflow_run_id"] == 31321019885
    assert context["workflow_run_attempt"] == 1
    assert context["dispatch_sha"] == "5eb6c8fad622832bc63a6503add8026be7ebd5a0"
    assert context["checked_out_commit"] == context["dispatch_sha"]
    assert context["dispatch_ref"] == "refs/heads/main"
    assert context["event_name"] == "workflow_dispatch"
    assert context["configure_aws_outcome"] == "success"
    assert context["execution_release_id"] == "RELEASE_HL_ARCHIVE_LEGACY_FORMAT_FINGERPRINT_R5_001"
    assert context["implementation_commit"] == "40bc4d138c71a4367c9415982f58bcd24c5a57eb"
    assert context["maximum_get_object_requests"] == 1
    assert context["maximum_retries_per_request"] == 0
    assert context["payload_retention_authorized"] is False
    assert context["wallet_analysis_authorized"] is False
    assert context["market_data_ingestion_authorized"] is False

    assert result["terminal_status"] == "R5_LEGACY_FORMAT_FINGERPRINT_COMPLETE"
    assert result["technical_result"] == "LEGACY_FORMAT_RESOLVED_AS_NDJSON_PAIR_STRING_OBJECT"
    assert result["research_conclusion"] == result["technical_result"]
    assert result["format_class"] == "UTF8_NDJSON_PAIR_STRING_OBJECT"
    assert result["request_attempt_count"] == 1
    assert result["s3_http_request_count"] == 1
    assert result["successful_request_count"] == 1
    assert result["failed_request_count"] == 0
    assert result["compressed_bytes"] == 12726384
    assert result["decompressed_bytes"] == 62169139
    assert result["runtime_seconds"] == 28.735337
    assert result["retries_used"] == 0
    assert result["requester_pays_requested"] is True
    assert result["http_redirects_followed"] is False
    assert result["failure_class"] is None
    assert result["object_key"] == "node_fills/hourly/20250727/8.lz4"
    assert result["expected_content_length"] == result["compressed_bytes"]
    assert result["compressed_sha256"] == result["expected_compressed_sha256"] == "f12d33da9733dbb71f02f9910fc187b9dd4b8f9dae1102b7dfe7690094542622"
    assert result["expected_decompressed_byte_count"] == result["decompressed_bytes"]
    assert result["expected_etag"] == '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"'

    structural = result["structural_evidence"]
    assert structural["nonempty_record_count"] == 162815
    assert structural["json_root_type_counts"] == {"array": 162815}
    assert structural["array_arity_histogram"] == {"2": 162815}
    assert structural["array_element_type_signature_counts"] == {"string,object": 162815}
    assert structural["maximum_observed_nesting_depth"] == 4
    assert structural["resolved_format_class"] == "UTF8_NDJSON_PAIR_STRING_OBJECT"
    assert structural["structural_signature_hash_counts"] == {
        "67bd92e8a68448200dee809c42bca37256b7db99ef54c5c056e36fc7f6edf27f": 162815
    }
    assert structural["object_field_path_names"] == [
        "/*", "/*/builder", "/*/builderFee", "/*/cloid", "/*/closedPnl", "/*/coin",
        "/*/crossed", "/*/dir", "/*/fee", "/*/feeToken", "/*/hash", "/*/liquidation",
        "/*/liquidation/liquidatedUser", "/*/liquidation/markPx", "/*/liquidation/method",
        "/*/oid", "/*/px", "/*/side", "/*/startPosition", "/*/sz", "/*/tid", "/*/time"
    ]
    assert structural["object_field_path_type_sets"]["/*"] == ["object", "string"]
    assert structural["object_field_path_type_sets"]["/*/crossed"] == ["bool"]
    assert structural["object_field_path_type_sets"]["/*/liquidation"] == ["object"]
    for name in ("/*/oid", "/*/tid", "/*/time"):
        assert structural["object_field_path_type_sets"][name] == ["integer"]

    for key in (
        "raw_compressed_object_persisted", "raw_decompressed_payload_retained",
        "record_payload_retained", "wallet_addresses_retained_from_body",
        "payload_values_retained", "string_values_retained", "numeric_values_retained",
        "semantic_wallet_or_user_label_inferred", "schema_equivalence_inferred",
        "semantic_equivalence_inferred", "wallet_reconstruction_performed",
        "entity_clustering_performed", "copyability_analysis_performed",
        "pnl_or_alpha_analysis_performed", "market_data_ingested",
    ):
        assert result[key] is False, key

    assert verification["provider_sha256"] == "3cb113e6729918dc647c182bddb86a2bd42de157b3c8131746103b3166981df4"
    assert verification["independently_downloaded_zip_sha256"] == verification["provider_sha256"]
    assert verification["provider_digest_matches_independent_download"] is True
    assert verification["internal_ledger_matches_all_retained_raw_files"] is True
    assert verification["return_code_value"] == 0
    assert verification["verification_result"] == "ALL_CHECKS_PASS"

    assert attestation["release_consumed"] is True
    assert attestation["rerun_authorized"] is False
    assert consumption["release_consumed"] is True
    assert consumption["rerun_authorized"] is False
    assert consumption["future_r5_dispatch_authorized"] is False
    assert consumption["future_r5_rerun_authorized"] is False
    assert activation["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R5_RUN"

    assert all(value is False for value in attestation["trading_authorizations_after_run"].values())
    assert all(value is False for value in consumption["trading_authorizations_after_run"].values())

    print("R5_LEGACY_FORMAT_EVIDENCE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
