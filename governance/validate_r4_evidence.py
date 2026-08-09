from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r4"
RUN = BASE / "evidence/run-31313913525"
RESULT = RUN / "r4-body-result.json"
CONTEXT = RUN / "r4-body-context.json"
RC = RUN / "r4-body.rc"
LEDGER = RUN / "R4_BODY_FILES.sha256"
VERIFY = RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json"
ATTEST = BASE / "evidence/HL-ARCHIVE-HOURLY-BODY-SCHEMA-PILOT-R4-001-ATTESTATION.json"
CONSUMPTION = BASE / "R4_EXECUTION_RELEASE_CONSUMPTION.json"
ACTIVATION = BASE / "R4_EXECUTION_RELEASE_CANONICALIZATION.json"


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

    assert sha256(CONTEXT) == "2a9685656730d9724b7dd86df396f474828d5738d4a2664e85c837b834d9a93a"
    assert sha256(RESULT) == "e80b30a82ad4e1f2401a3bb726105f7184d4e53a3c256d871a4e6aa045ef4e53"
    assert sha256(RC) == "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa"
    assert sha256(LEDGER) == "e54e8d94442e31fe33a43e191654f599e505585f98771629abce7676ec3f201f"
    assert RC.read_text(encoding="utf-8") == "0\n"

    assert context["workflow_run_id"] == 31313913525
    assert context["workflow_run_attempt"] == 1
    assert context["dispatch_sha"] == "85c7f145a564bdf177568bfc0c329a80c9a9c201"
    assert context["dispatch_ref"] == "refs/heads/main"
    assert context["event_name"] == "workflow_dispatch"
    assert context["configure_aws_outcome"] == "success"

    assert result["terminal_status"] == "R4_BODY_SCHEMA_PILOT_COMPLETE"
    assert result["technical_result"] == "TWO_OBJECT_BODY_FORMAT_UNRESOLVED"
    assert result["schema_comparison_class"] == "SCHEMA_UNRESOLVED"
    assert result["request_attempt_count"] == 2
    assert result["s3_http_request_count"] == 2
    assert result["successful_request_count"] == 2
    assert result["failed_request_count"] == 0
    assert result["total_compressed_bytes"] == 14243987
    assert result["total_decompressed_bytes"] == 69549517
    assert result["runtime_seconds"] == 25.73558
    assert result["retries_used"] == 0
    assert result["requester_pays_requested"] is True

    legacy, modern = result["observations"]
    assert legacy["key"] == "node_fills/hourly/20250727/8.lz4"
    assert legacy["status"] == "OBJECT_PROCESSED"
    assert legacy["http_status"] == 200
    assert legacy["request_charged"] == "requester"
    assert legacy["lz4_frame_recognized"] is True
    assert legacy["decompression_status"] == "LZ4_FRAME_DECOMPRESSED"
    assert legacy["compressed_object_size_bytes"] == 12726384
    assert legacy["decompressed_byte_count"] == 62169139
    assert legacy["compressed_object_sha256"] == "f12d33da9733dbb71f02f9910fc187b9dd4b8f9dae1102b7dfe7690094542622"
    assert legacy["schema_status"] == "BODY_READABLE_SCHEMA_UNRESOLVED"
    assert legacy["failure_class"] == "UTF8_NDJSON_OBJECT_SCHEMA_UNRESOLVED"
    assert legacy["record_count"] == 0

    assert modern["key"] == "node_fills_by_block/hourly/20250727/8.lz4"
    assert modern["status"] == "OBJECT_PROCESSED"
    assert modern["http_status"] == 200
    assert modern["request_charged"] == "requester"
    assert modern["lz4_frame_recognized"] is True
    assert modern["decompression_status"] == "LZ4_FRAME_DECOMPRESSED"
    assert modern["compressed_object_size_bytes"] == 1517603
    assert modern["decompressed_byte_count"] == 7380378
    assert modern["compressed_object_sha256"] == "928e1cd6bd7d69ad7243c263bacee48e53e4762ae9e99ef75f45007f6c0e6105"
    assert modern["schema_status"] == "FULL_SCHEMA_PARSED"
    assert modern["record_count"] == 4345
    assert modern["maximum_observed_nesting_depth"] == 4
    assert len(modern["field_path_names"]) == 23

    for key in (
        "raw_compressed_object_persisted", "raw_decompressed_payload_retained",
        "record_payload_retained", "wallet_addresses_retained_from_body",
        "payload_values_retained", "semantic_equivalence_inferred",
        "wallet_reconstruction_performed", "entity_clustering_performed",
        "copyability_analysis_performed", "pnl_or_alpha_analysis_performed",
        "market_data_ingested",
    ):
        assert result[key] is False, key
    assert result["empirical_result"] is None

    assert verification["provider_sha256"] == "bb865820b7fe2665191e056c69b627cec8fc143394aa75eb476be1127a532d4a"
    assert verification["independently_downloaded_zip_sha256"] == verification["provider_sha256"]
    assert verification["provider_digest_matches_independent_download"] is True
    assert verification["verification_result"] == "ALL_CHECKS_PASS"

    assert attestation["release_consumed"] is True
    assert attestation["rerun_authorized"] is False
    assert consumption["release_consumed"] is True
    assert consumption["rerun_authorized"] is False
    assert consumption["future_r4_dispatch_authorized"] is False
    assert activation["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R4_RUN"

    assert all(value is False for value in attestation["trading_authorizations_after_run"].values())
    assert all(value is False for value in consumption["trading_authorizations_after_run"].values())

    print("R4_BODY_EVIDENCE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
