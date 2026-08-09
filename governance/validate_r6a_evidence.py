from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r6a"
RUN = BASE / "evidence/run-31328268134"

EXPECTED = {
    "r6a-successor-context.json": "d0dd7e29d36ce19f64dd18ee674d2231d1dc63eb30aa9e31d411b18c70511e8b",
    "r6a-successor-result.json": "96a1e866834d70324f59fc4563c4b591b29156c5e1cdf5894e0cb7b7bb4904bd",
    "r6a-successor.rc": "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa",
    "R6A_SUCCESSOR_FILES.sha256": "083cb3a8f4f3fa68a8ffbd3e515b52084209349375c114bc3673af6f13578b99",
}


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    for name, expected in EXPECTED.items():
        path = RUN / name
        assert path.is_file(), name
        assert digest(path) == expected, name

    ledger = (RUN / "R6A_SUCCESSOR_FILES.sha256").read_text(encoding="utf-8").splitlines()
    observed = {}
    for row in ledger:
        sha, name = row.split("  ", 1)
        observed[name] = sha
    assert observed == {k: v for k, v in EXPECTED.items() if k != "R6A_SUCCESSOR_FILES.sha256"}

    context = load(RUN / "r6a-successor-context.json")
    result = load(RUN / "r6a-successor-result.json")
    verify = load(RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
    consume = load(BASE / "R6A_EXECUTION_RELEASE_002_CONSUMPTION.json")
    attest = load(BASE / "evidence/HL-ARCHIVE-LEGACY-USER-KEY-LEXICAL-R6A-001-ATTESTATION.json")

    assert context["workflow_run_id"] == 31328268134
    assert context["workflow_run_attempt"] == 1
    assert context["dispatch_ref"] == "refs/heads/main"
    assert context["dispatch_sha"] == "161b3ff76c3a1903a633f4b3317386ef1cc7b38b"
    assert context["configure_aws_outcome"] == "success"
    assert context["release_id"] == "RELEASE_HL_ARCHIVE_LEGACY_USER_KEY_LEXICAL_R6A_002"

    assert result["terminal_status"] == "R6A_LEXICAL_CONFIRMATION_COMPLETE"
    assert result["technical_result"] == "ALL_LEADING_STRINGS_MATCH_HYPERLIQUID_ADDRESS_SHAPE"
    assert result["research_conclusion"] == "ALL_LEADING_STRINGS_MATCH_HYPERLIQUID_ADDRESS_SHAPE"
    assert result["request_attempt_count"] == 1
    assert result["s3_http_request_count"] == 1
    assert result["successful_request_count"] == 1
    assert result["failed_request_count"] == 0
    assert result["retries_used"] == 0
    assert result["http_redirects_followed"] is False
    assert result["compressed_bytes"] == 12726384
    assert result["decompressed_bytes"] == 62169139
    assert result["compressed_sha256"] == "f12d33da9733dbb71f02f9910fc187b9dd4b8f9dae1102b7dfe7690094542622"

    lexical = result["lexical_aggregates"]
    assert lexical == {
        "leading_string_0x40hex_count": 162815,
        "leading_string_count": 162815,
        "leading_string_length_42_count": 162815,
        "leading_string_lowercase_0x40hex_count": 162815,
        "leading_string_non_0x40hex_count": 0,
        "nonempty_record_count": 162815,
        "pair_string_object_record_count": 162815,
    }

    for key in (
        "raw_compressed_object_persisted",
        "raw_decompressed_payload_retained",
        "record_payload_retained",
        "payload_values_retained",
        "string_values_retained",
        "numeric_values_retained",
        "leading_string_values_retained",
        "wallet_addresses_retained",
        "leading_string_hashes_retained",
        "distinct_address_set_retained",
        "wallet_reconstruction_performed",
        "entity_clustering_performed",
        "copyability_analysis_performed",
        "pnl_or_alpha_analysis_performed",
        "market_data_ingested",
    ):
        assert result[key] is False, key

    assert verify["workflow_run_id"] == 31328268134
    assert verify["workflow_job_id"] == 93282146403
    assert verify["artifact_id"] == 9042152700
    assert verify["artifact_size_bytes"] == 2360
    assert verify["provider_artifact_zip_sha256"] == "928a5d378a63f2da62d44f939e56a99a578637faa10e52c54b3fdc1556d0d93f"
    assert verify["independently_downloaded_artifact_zip_sha256"] == verify["provider_artifact_zip_sha256"]
    assert verify["provider_and_independent_zip_digest_match"] is True
    assert verify["internal_hash_ledger_verified"] is True
    assert verify["verification_result"] == "PASS_EXACT_SUCCESSOR_ARTIFACT"

    assert consume["release_consumed"] is True
    assert consume["future_r6a_dispatch_authorized"] is False
    assert consume["rerun_authorized"] is False
    assert consume["aggregate_get_object_requests_across_r6a_release_chain_after_run"] == 1
    assert consume["maximum_aggregate_get_object_requests_across_r6a_release_chain"] == 1
    assert consume["remaining_approved_get_object_budget"] == 0
    assert consume["lexical_aggregates"] == lexical
    assert all(value is False for value in consume["trading_authorizations_after_run"].values())

    assert attest["release_consumed"] is True
    assert attest["rerun_authorized"] is False
    assert attest["parent_r6_semantic_label"] == "HYPERLIQUID_USER_ADDRESS"
    assert attest["parent_r6_semantic_label_status"] == "SUPPORTED_INFERENCE_NOT_DIRECT_SERIALIZER_PROOF"
    combined = attest["combined_r6_r6a_interpretation"]
    assert combined["semantic_label"] == "HYPERLIQUID_USER_ADDRESS"
    assert combined["status"] == "HIGH_CONFIDENCE_CONVERGENT_STATIC_AND_LEXICAL_EVIDENCE_NOT_DIRECT_SERIALIZER_PROOF"
    assert all(value is False for value in attest["trading_authorizations_after_run"].values())

    print("R6A_EVIDENCE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
