from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
REPORT = BASE / "r10d_evidence/R10D_BACKWARD_CONSISTENCY.json"
REPORT_MD = BASE / "r10d_evidence/R10D_BACKWARD_CONSISTENCY_REPORT.md"
RESULT = BASE / "r10d_evidence/run-31420197671/r10d-result.json"
DIAGNOSTICS = BASE / "r10d_evidence/R10D_AGGREGATE_DIAGNOSTICS.json"
R11A_DOSSIER = BASE / "r11a/R11A_IDENTITY_DECISION_DOSSIER.json"
R11A_PREREGISTRATION = BASE / "r11a/R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_PREREGISTRATION.json"

EXPECTED_REPORT_SEMANTIC_SHA256 = "b5417a6aa422d5ba8a3f78e373cda3fc0d40fc5102a59836796ddeb51526b05b"
EXPECTED_RESULT_SEMANTIC_SHA256 = "257d21a3297eaeb703a2b46dec685fcdba314ee200216ab08084821566f42c5d"
EXPECTED_DIAGNOSTICS_SEMANTIC_SHA256 = "32b6c770b9d0ea6764f8dda84e8a12989fd381fdd65809773e241e933d6c6bdc"
EXPECTED_HUMAN_REPORT_SHA256 = "7a8b06db0bd79497aca78c8a2e9f1e4abdc561326be738e5acdb07752efbf02a"

EXPECTED_IDENTITY_MODEL = {
    "raw_observation_key": [
        "object_key",
        "verified_compressed_sha256",
        "decompressed_record_ordinal",
        "event_ordinal",
    ],
    "archive_block_locator": "block_number",
    "archive_block_equality_invariants": [
        "exact_raw_block_time",
        "ordered_event_count",
        "ordered_event_fingerprint",
    ],
    "protocol_matched_trade_key": [
        "exact_raw_block_time",
        "exact_raw_coin_string",
        "validated_json_integer_tid",
    ],
    "wallet_user_fill_key": [
        "canonical_lowercase_wallet_address",
        "exact_raw_block_time",
        "exact_raw_coin_string",
        "validated_json_integer_tid",
    ],
}
EXPECTED_IDENTITY_AUTHORITY_BINDING = {
    "decision_id": "R11A-CANONICAL-IDENTITY-MODEL-001",
    "dossier_path": "research/archive_inventory/r11a/R11A_IDENTITY_DECISION_DOSSIER.json",
    "preregistration_path": (
        "research/archive_inventory/r11a/"
        "R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_PREREGISTRATION.json"
    ),
    "exact_binding_scope": [
        "raw_observation_key",
        "archive_block_locator",
        "archive_block_equality_invariants",
        "protocol_matched_trade_key",
        "wallet_user_fill_key",
    ],
    "live_dossier_and_preregistration_identity_models_must_match_report_exactly": True,
}


class R10DValidationError(AssertionError):
    """Raised when the retained R10D evidence or its interpretation drifts."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise R10DValidationError(message)


def strict_json_loads(text: str, label: str) -> object:
    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise R10DValidationError(f"{label} contains duplicate key {key}")
            value[key] = item
        return value

    def reject_constant(token: str) -> object:
        raise R10DValidationError(f"{label} contains non-finite constant {token}")

    def finite_float(token: str) -> float:
        value = float(token)
        if not math.isfinite(value):
            raise R10DValidationError(f"{label} contains non-finite number {token}")
        return value

    return json.loads(
        text,
        object_pairs_hook=reject_duplicate_keys,
        parse_constant=reject_constant,
        parse_float=finite_float,
    )


def load(path: Path) -> dict:
    value = strict_json_loads(path.read_text(encoding="utf-8"), str(path))
    require(isinstance(value, dict), f"JSON root must be an object: {path}")
    return value  # type: ignore[return-value]


def semantic_digest(value: object) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def byte_digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def exact_json_equal(actual: object, expected: object) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return set(actual) == set(expected) and all(
            exact_json_equal(actual[key], expected_value)
            for key, expected_value in expected.items()
        )
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return False
        return len(actual) == len(expected) and all(
            exact_json_equal(actual_item, expected_item)
            for actual_item, expected_item in zip(actual, expected, strict=True)
        )
    return actual == expected


def dossier_identity_model(dossier: dict) -> dict:
    layers = dossier["identity_layers"]
    return {
        "raw_observation_key": layers["raw_observation"]["canonical_key"],
        "archive_block_locator": layers["archive_block"]["locator"],
        "archive_block_equality_invariants": layers["archive_block"]["equality_invariants"],
        "protocol_matched_trade_key": layers["protocol_matched_trade"]["canonical_key"],
        "wallet_user_fill_key": layers["wallet_user_fill"]["canonical_key"],
    }


def preregistration_identity_model(preregistration: dict) -> dict:
    identity = preregistration["identity_contract"]
    return {
        "raw_observation_key": identity["raw_observation_key"],
        "archive_block_locator": identity["archive_block_locator"],
        "archive_block_equality_invariants": identity["archive_block_equality_invariants"],
        "protocol_matched_trade_key": identity["protocol_matched_trade_key"],
        "wallet_user_fill_key": identity["wallet_user_fill_key"],
    }


def validate_report(
    report: dict,
    result: dict,
    diagnostics: dict,
    dossier: dict,
    preregistration: dict,
    human_report: bytes,
) -> None:
    # These full-document semantic bindings reject missing, extra, type-drifted,
    # authority-opening, and interpretation-changing fields even under python -O.
    require(
        semantic_digest(report) == EXPECTED_REPORT_SEMANTIC_SHA256,
        "R10D backward-consistency report mapping drift",
    )
    require(
        semantic_digest(result) == EXPECTED_RESULT_SEMANTIC_SHA256,
        "retained R10D result mapping drift",
    )
    require(
        semantic_digest(diagnostics) == EXPECTED_DIAGNOSTICS_SEMANTIC_SHA256,
        "retained R10D diagnostics mapping drift",
    )

    source_basis = report["source_basis"]
    require(
        source_basis["human_report_path"]
        == "research/archive_inventory/r10d_evidence/R10D_BACKWARD_CONSISTENCY_REPORT.md",
        "human report path drift",
    )
    require(
        source_basis["human_report_sha256"]
        == EXPECTED_HUMAN_REPORT_SHA256
        == byte_digest(human_report),
        "human report byte binding drift",
    )
    try:
        human_report_text = human_report.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise R10DValidationError("human report is not strict UTF-8") from exc
    for required_prose in (
        "R10D is classified as `C_R10D_UNCERTAIN_UNDER_CANONICAL_IDENTITY`.",
        "option A, exact reproduction under the new identity architecture, is not proven",
        "option B, a demonstrable correction to the R10D aggregate, is not proven",
        "option C, uncertainty for canonical unique block and wallet-fill semantics, is the only evidence-supported classification",
        "They must not be presented as a proven canonical unique-fill ledger",
    ):
        require(required_prose in human_report_text, f"human report prose drift: {required_prose}")
    for forbidden_prose in (
        "A_R10D_EXACTLY_REPRODUCED",
        "B_R10D_DEMONSTRABLY_CORRECTED",
        "may be presented as a proven canonical unique-fill ledger",
    ):
        require(forbidden_prose not in human_report_text, f"human report authority overclaim: {forbidden_prose}")

    require(report["schema_version"] == "1.0", "report schema version drift")
    require(
        report["report_id"] == "R10D-BACKWARD-CONSISTENCY-AFTER-R11-IDENTITY-AUDIT-001",
        "report identity drift",
    )
    require(
        report["status"] == "OFFLINE_REVIEW_COMPLETE_R10D_CANONICAL_IDENTITY_UNRESOLVED",
        "report status drift",
    )

    classification = report["backward_consistency_classification"]
    require(
        classification == {
            "classification": "C_R10D_UNCERTAIN_UNDER_CANONICAL_IDENTITY",
            "scope": "CANONICAL_UNIQUE_BLOCK_AND_WALLET_USER_FILL_SEMANTICS",
            "option_a_exact_reproduction_proven": False,
            "option_b_demonstrable_correction_proven": False,
            "option_c_r10d_uncertain": True,
            "reason": "R10D retains exact legacy observation aggregates and a zero repeat count under wallet plus typed tid, but it has no occurrence-level block overlap ledger or canonical wallet-fill provenance with which to recompute the six hours under the documented block_time plus coin plus tid scope.",
        },
        "R10D canonical-identity classification drift",
    )

    require(result["terminal_status"] == "R10D_MULTI_HOUR_FEATURE_REPAIR_STUDY_COMPLETE", "terminal drift")
    require(
        result["technical_result"]
        == result["research_conclusion"]
        == "R10D_MULTI_HOUR_FEATURE_PIPELINE_COMPLETE",
        "technical result drift",
    )
    require(result["completed_hour_count"] == 6, "completed-hour drift")
    require(
        result["request_attempt_count"]
        == result["s3_http_request_count"]
        == result["successful_request_count"]
        == 6,
        "request conservation drift",
    )
    require(result["failed_request_count"] == result["retries_used"] == 0, "failure/retry drift")
    require(result["http_redirects_followed"] is False, "redirect drift")
    require(
        result["record_anchored_rule_id"] == "RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1",
        "record-alignment rule drift",
    )
    require(result["numeric_tolerance_authorized"] is False, "numeric tolerance opened")

    hours = result["per_hour_summaries"]
    require(len(hours) == 6, "per-hour cardinality drift")
    for index, row in enumerate(hours):
        require(row["record_anchored_alignment_violation_count"] == 0, f"hour {index} alignment drift")
        require(row["fill_time_after_path_hour_count"] == 0, f"hour {index} after-hour drift")
        require(
            row["local_path_block_path_record_count"] + row["local_path_block_previous_record_count"]
            == row["block_record_count"],
            f"hour {index} block conservation drift",
        )
        require(
            row["fill_time_before_path_hour_count"]
            + row["fill_time_inside_path_hour_count"]
            + row["fill_time_after_path_hour_count"]
            == row["event_pair_count"],
            f"hour {index} fill-time conservation drift",
        )

    observed = {
        "terminal_status": result["terminal_status"],
        "technical_result": result["technical_result"],
        "completed_hour_count": result["completed_hour_count"],
        "request_attempt_count": result["request_attempt_count"],
        "successful_request_count": result["successful_request_count"],
        "failed_request_count": result["failed_request_count"],
        "retries_used": result["retries_used"],
        "http_redirects_followed": result["http_redirects_followed"],
        "total_compressed_bytes": result["total_compressed_bytes"],
        "total_decompressed_bytes": result["total_decompressed_bytes"],
        "block_record_observation_count": sum(row["block_record_count"] for row in hours),
        "path_block_record_observation_count": sum(row["local_path_block_path_record_count"] for row in hours),
        "previous_block_record_observation_count": sum(
            row["local_path_block_previous_record_count"] for row in hours
        ),
        "event_pair_observation_count": sum(row["event_pair_count"] for row in hours),
        "before_path_hour_observation_count": sum(row["fill_time_before_path_hour_count"] for row in hours),
        "inside_path_hour_observation_count": sum(row["fill_time_inside_path_hour_count"] for row in hours),
        "after_path_hour_observation_count": sum(row["fill_time_after_path_hour_count"] for row in hours),
        "record_anchored_alignment_violation_count": sum(
            row["record_anchored_alignment_violation_count"] for row in hours
        ),
        "record_anchored_rule_id": result["record_anchored_rule_id"],
        "numeric_tolerance_authorized": result["numeric_tolerance_authorized"],
    }
    require(report["retained_mechanics_result"] == observed, "retained mechanics are not derived from result")

    summary = result["aggregate_wallet_feature_summary"]
    legacy = report["retained_legacy_wallet_aggregate"]
    require(
        summary["wallet_feature_row_count"]
        == diagnostics["wallet_feature_row_count"]
        == legacy["wallet_feature_row_count"]
        == 16410,
        "wallet-row cross-binding drift",
    )
    require(
        summary["sum_fill_count"]
        == diagnostics["sum_fill_count"]
        == legacy["sum_fill_count"]
        == 1486542,
        "fill-count cross-binding drift",
    )
    require(
        summary["sum_side_count"]
        == diagnostics["sum_side_count"]
        == legacy["sum_side_count"]
        == 1486542,
        "side-count cross-binding drift",
    )
    require(
        summary["duplicate_wallet_tid_count"]
        == diagnostics["duplicate_tid_count_total"]
        == legacy["duplicate_wallet_typed_tid_repeat_count"]
        == 0,
        "legacy duplicate-count cross-binding drift",
    )
    require(
        summary["wallet_feature_sha256"]
        == diagnostics["wallet_feature_sha256"]
        == legacy["wallet_feature_sha256"],
        "wallet-feature digest cross-binding drift",
    )
    require(
        legacy["semantic_status"]
        == "HISTORICAL_LEGACY_OBSERVATION_AGGREGATE_NOT_CANONICAL_UNIQUE_FILL_LEDGER",
        "legacy aggregate promoted to canonical ledger",
    )

    identity_model = report["canonical_identity_model_under_review"]
    require(exact_json_equal(identity_model, EXPECTED_IDENTITY_MODEL), "R10D identity-model drift")
    require(
        exact_json_equal(report["canonical_identity_authority_binding"], EXPECTED_IDENTITY_AUTHORITY_BINDING),
        "R11A identity authority-binding drift",
    )
    require(
        dossier["decision_id"] == preregistration["identity_contract"]["decision_id"]
        == EXPECTED_IDENTITY_AUTHORITY_BINDING["decision_id"],
        "R11A identity decision-id drift",
    )
    require(
        dossier["status"] == "FROZEN_FOR_DIAGNOSTIC_DESIGN_NO_REPAIR_DECISION",
        "R11A dossier authority status drift",
    )
    require(
        preregistration["status"] == "PREREGISTERED_NO_EXECUTION",
        "R11A preregistration authority status drift",
    )
    require(
        exact_json_equal(dossier_identity_model(dossier), identity_model),
        "R10D report/R11A dossier identity-model split",
    )
    require(
        exact_json_equal(preregistration_identity_model(preregistration), identity_model),
        "R10D report/R11A preregistration identity-model split",
    )

    matrix = report["evidence_matrix"]
    require(matrix["legacy_wallet_typed_tid_repeat_count_zero"] == "PROVEN_FOR_R10D_RUN", "legacy proof drift")
    require(matrix["wallet_plus_tid_is_semantically_valid_identity"] == "DISPROVEN", "identity finding drift")
    for key in (
        "canonical_unique_block_count_equals_block_record_observation_count",
        "canonical_unique_wallet_fill_count_equals_1486542",
        "r10d_contains_cross_object_exact_block_replay",
        "new_identity_model_exactly_reproduces_r10d_wallet_rows",
        "new_identity_model_demonstrably_corrects_r10d_wallet_rows",
        "source_path_active_hour_counts_equal_event_time_active_hour_counts",
        "all_r10d_tids_are_json_integer_uint50",
    ):
        require(matrix[key] == "UNKNOWN", f"unsupported R10D claim opened: {key}")

    require(
        all(value is False for value in report["execution_and_downstream_boundaries"].values()),
        "execution or downstream authority opened",
    )
    require(
        all(value is False for value in diagnostics["interpretation_boundaries"].values()),
        "diagnostic interpretation authority opened",
    )
    require(
        all(value is False for value in diagnostics["downstream_actions_performed"].values()),
        "diagnostic downstream action overclaim",
    )


def main() -> int:
    validate_report(
        load(REPORT),
        load(RESULT),
        load(DIAGNOSTICS),
        load(R11A_DOSSIER),
        load(R11A_PREREGISTRATION),
        REPORT_MD.read_bytes(),
    )
    print("R10D_BACKWARD_CONSISTENCY_VALID_C_UNCERTAIN_UNDER_CANONICAL_IDENTITY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
