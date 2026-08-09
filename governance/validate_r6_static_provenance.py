from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "research/archive_inventory/r6/STATIC_PROVENANCE_REPORT.json"


def load() -> dict:
    value = json.loads(REPORT.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def main() -> int:
    report = load()

    assert report["study_id"] == "HL-ARCHIVE-LEGACY-USER-KEY-PROVENANCE-R6-001"
    assert report["study_class"] == "STATIC_PRIMARY_SOURCE_PROVENANCE"
    assert report["status"] == "STATIC_RESEARCH_COMPLETE_NO_EXECUTION"

    parent = report["parent_r5"]
    assert parent["canonical_evidence_merge_commit"] == "4400963aa972ed878650116202cc72880e667849"
    assert parent["run_id"] == 31321019885
    assert parent["terminal_status"] == "R5_LEGACY_FORMAT_FINGERPRINT_COMPLETE"
    assert parent["format_class"] == "UTF8_NDJSON_PAIR_STRING_OBJECT"
    assert parent["nonempty_record_count"] == 162815
    assert parent["semantic_wallet_or_user_label_inferred_by_r5"] is False

    boundary = report["method_boundary"]
    assert boundary == {
        "public_primary_sources_only": True,
        "new_archive_request_performed": False,
        "s3_request_performed": False,
        "aws_role_or_policy_mutated": False,
        "object_body_downloaded": False,
        "payload_value_inspected": False,
        "wallet_address_from_archive_retained": False,
        "market_data_ingested": False,
        "trading_or_capital_authority_opened": False,
    }

    sources = {item["source_id"]: item for item in report["primary_source_evidence"]}
    assert sources["HL-NODE-WRITE-FILLS-COMMIT-20250527"]["commit"] == "c4933f2273e4dfca6915971229d22149712641e0"
    assert sources["HL-NODE-WRITE-FILLS-COMMIT-20250527"]["predates_target_object"] is True
    assert sources["HL-NODE-BATCH-BY-BLOCK-COMMIT-20250627"]["commit"] == "247aea04898c23f2cd8948ad0e70a5f47d8b43bc"
    assert sources["HL-NODE-BATCH-BY-BLOCK-COMMIT-20250627"]["predates_target_object"] is True

    for source_id in (
        "HL-PYSDK-0160-TYPES",
        "HL-PYSDK-0160-INFO-USER-FILLS",
        "HL-PYSDK-0160-WS-USER-FILLS",
    ):
        assert sources[source_id]["tag"] == "0.16.0"
        assert sources[source_id]["tag_commit"] == "3ad503fd1ad6b609aad42d9be183306b9213cdb0"
        assert sources[source_id]["predates_target_object"] is True
        assert sources[source_id]["immutable"] is True

    correspondence = report["r5_structural_correspondence"]
    assert correspondence["all_observed_records_are_pair_string_object"] is True
    assert correspondence["all_observed_record_count"] == 162815
    assert correspondence["correspondence_to_historical_sdk_fill_shape"] == "STRONG"
    assert correspondence["archive_string_value_or_lexical_shape_observed_by_r6"] is False

    assert report["terminal_result"] == "LEADING_STRING_USER_ADDRESS_SEMANTICS_HIGH_CONFIDENCE_STATIC_INFERENCE"
    assert report["semantic_label"] == "HYPERLIQUID_USER_ADDRESS"
    assert report["semantic_label_status"] == "SUPPORTED_INFERENCE_NOT_DIRECT_SERIALIZER_PROOF"
    assert report["confidence_class"] == "HIGH"

    not_proven = report["claims_not_proven"]
    assert any("serializer" in item for item in not_proven)
    assert any("42-character" in item for item in not_proven)
    assert any("specific wallet address" in item for item in not_proven)

    authorizations = report["current_authorizations"]
    assert authorizations
    assert all(value is False for value in authorizations.values())

    next_gate = report["next_minimum_empirical_gate_if_required"]
    assert next_gate["gate_id"] == "HL-ARCHIVE-LEGACY-USER-KEY-LEXICAL-R6A-001"
    assert next_gate["status"] == "PROPOSED_NOT_AUTHORIZED"
    assert next_gate["proposed_value_retention"] is False
    assert next_gate["proposed_wallet_address_retention"] is False
    assert next_gate["proposed_payload_retention"] is False
    assert next_gate["new_paid_request_required"] is True
    assert next_gate["separate_human_scope_and_budget_approval_required"] is True
    assert next_gate["execution_release_required"] is True

    print("R6_STATIC_PROVENANCE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
