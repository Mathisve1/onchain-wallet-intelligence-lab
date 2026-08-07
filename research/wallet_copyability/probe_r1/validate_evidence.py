#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any

from contract import (
    AUTHORIZATION_FIELDS,
    CONTRACT_PATH,
    ProbeContractError,
    collector_bundle_sha256,
    contract_sha256,
    load_contract,
    resolve_value,
    sha256,
)

SHA256 = re.compile(r"^[0-9a-f]{64}$")
TERMINAL = {
    "PUBLIC_PROBE_PASS",
    "PUBLIC_PROBE_PARTIAL",
    "PUBLIC_PROBE_FAIL",
}
ARCHIVE_STATUS = {
    "LISTINGS_AVAILABLE",
    "ROUTES_CONFIRMED_ACCESS_RESTRICTED",
    "ARCHIVE_ROUTE_FAILURE",
}
ARCHIVE_IDS = (
    "node_fill_archive_listing",
    "market_data_archive_listing",
    "asset_context_archive_listing",
)
SECURITY_ASSERTION_FIELDS = {
    "credentials_used",
    "authorization_header_used",
    "cookies_used",
    "private_keys_used",
    "signed_actions_used",
    "exchange_action_endpoint_used",
    "orders_used",
    "withdrawals_used",
    "raw_response_values_persisted",
}


class EvidenceError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=strict_object,
            parse_constant=lambda token: (_ for _ in ()).throw(
                EvidenceError(f"non-finite value: {token}")
            ),
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"invalid JSON {path}: {exc}") from exc
    require(isinstance(value, dict), "evidence root must be object")
    return value


def utc(value: Any, label: str) -> dt.datetime:
    require(
        isinstance(value, str) and value.endswith("Z"),
        f"{label} must be a UTC Z string",
    )
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise EvidenceError(f"invalid {label}: {value}") from exc
    require(parsed.tzinfo is not None, f"{label} timezone absent")
    return parsed


def expected_request_sha(
    row: dict[str, Any],
    contract: dict[str, Any],
) -> str:
    if row["method"] == "POST":
        payload = resolve_value(row["payload"], contract)
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return sha256(encoded)
    return sha256((row["path"] + "?" + row["query"]).encode("utf-8"))


def derive_observation_status(
    observed: dict[str, Any],
    registered: dict[str, Any],
) -> str:
    expected = registered["expected"]
    http_status = observed["http_status"]
    response_class = observed["response_class"]
    top_level_type = observed["top_level_type"]
    json_status = observed["json_status"]

    if expected == "s3_listing_or_error":
        if (
            response_class == "S3_LISTING"
            and http_status == 200
            and top_level_type == "xml"
            and json_status == "NOT_APPLICABLE"
        ):
            return "PASS"
        if (
            response_class == "S3_ERROR_RESPONSE"
            and http_status in {400, 403, 404}
            and top_level_type == "xml"
            and json_status == "NOT_APPLICABLE"
        ):
            return "PASS"
        return "FAIL"

    if not (
        isinstance(http_status, int)
        and 200 <= http_status < 300
        and response_class == "JSON"
        and json_status == "VALID_JSON"
    ):
        return "FAIL"

    accepted = {
        "json_object": top_level_type == "object",
        "json_array": top_level_type == "array",
        "json_array_or_null": top_level_type in {"array", "null"},
        "json_object_or_null": top_level_type in {"object", "null"},
    }.get(expected, False)
    return "PASS" if accepted else "FAIL"


def derive_terminal(
    observations: list[dict[str, Any]],
    contract: dict[str, Any],
) -> str:
    expected_ids = [row["id"] for row in contract["probes"]]
    if [row.get("probe_id") for row in observations] != expected_ids:
        return "PUBLIC_PROBE_FAIL"
    if any(row.get("status") != "PASS" for row in observations if row.get("core")):
        return "PUBLIC_PROBE_FAIL"
    if any(row.get("status") != "PASS" for row in observations):
        return "PUBLIC_PROBE_PARTIAL"
    return "PUBLIC_PROBE_PASS"


def derive_archive_access(observations: list[dict[str, Any]]) -> str:
    by_id = {row.get("probe_id"): row for row in observations}
    if any(
        probe_id not in by_id or by_id[probe_id].get("status") != "PASS"
        for probe_id in ARCHIVE_IDS
    ):
        return "ARCHIVE_ROUTE_FAILURE"
    classes = [by_id[probe_id].get("response_class") for probe_id in ARCHIVE_IDS]
    if all(value == "S3_LISTING" for value in classes):
        return "LISTINGS_AVAILABLE"
    if all(value in {"S3_LISTING", "S3_ERROR_RESPONSE"} for value in classes):
        return "ROUTES_CONFIRMED_ACCESS_RESTRICTED"
    return "ARCHIVE_ROUTE_FAILURE"


def validate_pending(
    evidence: dict[str, Any],
    contract: dict[str, Any],
) -> None:
    expected = {
        "schema_version",
        "study_id",
        "probe_id",
        "status",
        "observations",
        "output_sha256",
        "reviewed_commit",
        "workflow_run_id",
        "workflow_job_id",
        "artifact_id",
        "artifact_digest",
        "market_data_ingested",
        "empirical_result",
        "authorizations",
    }
    require(set(evidence) == expected, "pending evidence field drift")
    require(evidence["schema_version"] == "1.0", "pending schema drift")
    require(
        evidence["status"] == "PENDING_PUBLIC_PROBE_R1",
        "pending status drift",
    )
    require(evidence["observations"] == [], "pending file contains observations")
    for key in (
        "output_sha256",
        "reviewed_commit",
        "workflow_run_id",
        "workflow_job_id",
        "artifact_id",
        "artifact_digest",
    ):
        require(evidence[key] is None, f"pending evidence unexpectedly binds {key}")
    require(
        evidence["market_data_ingested"] is False
        and evidence["empirical_result"] is None,
        "pending pre-data boundary opened",
    )
    require(
        set(evidence["authorizations"]) == AUTHORIZATION_FIELDS
        and evidence["authorizations"] == contract["authorizations"]
        and all(value is False for value in evidence["authorizations"].values()),
        "pending authorization field/value drift",
    )
    require(
        evidence["study_id"] == contract["study_id"]
        and evidence["probe_id"] == contract["probe_id"],
        "pending identity drift",
    )


def validate_observation(
    observed: dict[str, Any],
    registered: dict[str, Any],
    contract: dict[str, Any],
) -> None:
    fields = {
        "probe_id",
        "core",
        "method",
        "request_origin",
        "request_path",
        "request_sha256",
        "declared_weight",
        "weight_basis",
        "attempts",
        "started_at_utc",
        "completed_at_utc",
        "http_status",
        "elapsed_ms",
        "transport_error_class",
        "transport_error_message",
        "expected_shape",
        "status",
        "body_length",
        "body_sha256",
        "content_type",
        "response_class",
        "json_status",
        "top_level_type",
        "top_level_keys",
        "element_count",
        "sample_item_types",
    }
    require(
        isinstance(observed, dict) and set(observed) == fields,
        f"observation field drift: {registered['id']}",
    )
    require(observed["probe_id"] == registered["id"], "observation ordering drift")
    for key in ("core", "method", "declared_weight", "weight_basis"):
        require(
            observed[key] == registered[key],
            f"observation contract drift {registered['id']}:{key}",
        )
    require(
        observed["request_origin"] == registered["origin"],
        f"origin drift: {registered['id']}",
    )
    require(
        observed["request_path"] == registered["path"],
        f"path drift: {registered['id']}",
    )
    require(
        observed["request_sha256"] == expected_request_sha(registered, contract),
        f"request hash drift: {registered['id']}",
    )
    require(
        observed["expected_shape"] == registered["expected"],
        f"expected shape drift: {registered['id']}",
    )
    require(
        observed["status"] in {"PASS", "FAIL"},
        f"observation status drift: {registered['id']}",
    )
    require(
        observed["status"] == derive_observation_status(observed, registered),
        f"observation status not independently derived: {registered['id']}",
    )
    require(
        isinstance(observed["attempts"], int)
        and not isinstance(observed["attempts"], bool)
        and 1
        <= observed["attempts"]
        <= contract["limits"]["maximum_attempts_per_probe"],
        f"attempt count drift: {registered['id']}",
    )
    require(
        isinstance(observed["declared_weight"], int)
        and not isinstance(observed["declared_weight"], bool)
        and observed["declared_weight"] >= 0,
        f"weight invalid: {registered['id']}",
    )
    require(
        observed["http_status"] is None
        or (
            isinstance(observed["http_status"], int)
            and not isinstance(observed["http_status"], bool)
        ),
        f"HTTP status invalid: {registered['id']}",
    )
    require(
        isinstance(observed["elapsed_ms"], (int, float))
        and not isinstance(observed["elapsed_ms"], bool)
        and observed["elapsed_ms"] >= 0,
        f"elapsed time invalid: {registered['id']}",
    )
    for key in ("transport_error_class", "transport_error_message", "content_type"):
        require(
            observed[key] is None or isinstance(observed[key], str),
            f"{key} invalid: {registered['id']}",
        )
    require(
        isinstance(observed["body_length"], int)
        and not isinstance(observed["body_length"], bool)
        and 0
        <= observed["body_length"]
        <= contract["limits"]["maximum_response_bytes"],
        f"body length drift: {registered['id']}",
    )
    require(
        isinstance(observed["body_sha256"], str)
        and SHA256.fullmatch(observed["body_sha256"]) is not None,
        f"body hash invalid: {registered['id']}",
    )
    require(
        observed["response_class"]
        in {"JSON", "S3_LISTING", "S3_ERROR_RESPONSE", "UNSUPPORTED"},
        f"response class invalid: {registered['id']}",
    )
    require(
        observed["json_status"]
        in {"VALID_JSON", "INVALID_JSON", "NOT_APPLICABLE"},
        f"JSON status invalid: {registered['id']}",
    )
    require(
        observed["top_level_type"]
        in {"object", "array", "null", "str", "int", "float", "bool", "xml", "bytes"},
        f"top-level type invalid: {registered['id']}",
    )
    require(
        isinstance(observed["top_level_keys"], list)
        and all(isinstance(value, str) for value in observed["top_level_keys"])
        and observed["top_level_keys"]
        == sorted(set(observed["top_level_keys"])),
        f"top-level keys invalid: {registered['id']}",
    )
    require(
        isinstance(observed["sample_item_types"], list)
        and all(isinstance(value, str) for value in observed["sample_item_types"])
        and observed["sample_item_types"]
        == sorted(set(observed["sample_item_types"])),
        f"item types invalid: {registered['id']}",
    )
    require(
        observed["element_count"] is None
        or (
            isinstance(observed["element_count"], int)
            and not isinstance(observed["element_count"], bool)
            and observed["element_count"] >= 0
        ),
        f"element count invalid: {registered['id']}",
    )
    require(
        utc(observed["completed_at_utc"], f"{registered['id']} completion")
        >= utc(observed["started_at_utc"], f"{registered['id']} start"),
        f"observation time reversal: {registered['id']}",
    )


def validate_result(
    evidence: dict[str, Any],
    contract: dict[str, Any],
    contract_path: Path = CONTRACT_PATH,
) -> None:
    top = {
        "schema_version",
        "study_id",
        "probe_id",
        "contract_sha256",
        "collector_bundle_sha256",
        "collected_at_utc",
        "completed_at_utc",
        "scope",
        "terminal_status",
        "archive_access_status",
        "published_ip_budget_per_minute",
        "registered_probe_count",
        "observation_count",
        "pass_count",
        "fail_count",
        "total_request_attempts",
        "total_declared_request_weight",
        "remaining_declared_weight_margin",
        "observations",
        "security_assertions",
        "market_data_ingested",
        "empirical_result",
        "authorizations",
    }
    require(
        set(evidence) == top,
        f"result evidence field drift: {sorted(set(evidence) ^ top)}",
    )
    require(evidence["schema_version"] == "1.2", "evidence schema drift")
    require(
        evidence["study_id"] == contract["study_id"]
        and evidence["probe_id"] == contract["probe_id"],
        "result identity drift",
    )
    require(
        evidence["contract_sha256"] == contract_sha256(contract_path),
        "contract hash drift",
    )
    require(
        evidence["collector_bundle_sha256"] == collector_bundle_sha256(),
        "collector bundle hash drift",
    )
    require(
        evidence["scope"] == "READ_ONLY_PUBLIC_SCHEMA_AND_ARCHIVE_ROUTE_BEHAVIOR",
        "scope drift",
    )
    require(evidence["terminal_status"] in TERMINAL, "unknown terminal status")
    require(
        evidence["archive_access_status"] in ARCHIVE_STATUS,
        "unknown archive access status",
    )
    collected = utc(evidence["collected_at_utc"], "collected_at_utc")
    completed = utc(evidence["completed_at_utc"], "completed_at_utc")
    require(completed >= collected, "run time reversal")

    observations = evidence["observations"]
    require(
        isinstance(observations, list)
        and len(observations) == len(contract["probes"]),
        "observation coverage incomplete",
    )
    for observed, registered in zip(
        observations,
        contract["probes"],
        strict=True,
    ):
        validate_observation(observed, registered, contract)
    require(
        collected == utc(observations[0]["started_at_utc"], "first observation start"),
        "run start does not bind first observation",
    )
    require(
        completed
        >= max(
            utc(row["completed_at_utc"], f"{row['probe_id']} completion")
            for row in observations
        ),
        "run completion precedes an observation",
    )

    require(
        evidence["published_ip_budget_per_minute"]
        == contract["capacity_contract"]["published_ip_budget_per_minute"],
        "published planning budget drift",
    )
    require(
        evidence["registered_probe_count"] == len(contract["probes"]),
        "registered count drift",
    )
    require(
        evidence["observation_count"] == len(observations),
        "observation count drift",
    )
    require(
        evidence["pass_count"]
        == sum(row["status"] == "PASS" for row in observations),
        "pass count drift",
    )
    require(
        evidence["fail_count"]
        == sum(row["status"] == "FAIL" for row in observations),
        "fail count drift",
    )
    require(
        evidence["pass_count"] + evidence["fail_count"] == len(observations),
        "terminal count mismatch",
    )

    attempts = sum(row["attempts"] for row in observations)
    weight = sum(
        row["attempts"] * row["declared_weight"]
        for row in observations
    )
    published = contract["capacity_contract"]["published_ip_budget_per_minute"]
    require(
        evidence["total_request_attempts"] == attempts
        and attempts <= contract["limits"]["maximum_total_requests"],
        "request ceiling drift",
    )
    require(
        evidence["total_declared_request_weight"] == weight
        and weight <= contract["limits"]["maximum_declared_request_weight"]
        and weight < published,
        "weight ceiling drift",
    )
    require(
        evidence["remaining_declared_weight_margin"] == published - weight
        and evidence["remaining_declared_weight_margin"] > 0,
        "remaining declared weight margin drift",
    )

    expected_terminal = derive_terminal(observations, contract)
    if (
        attempts > contract["limits"]["maximum_total_requests"]
        or weight > contract["limits"]["maximum_declared_request_weight"]
        or weight >= published
    ):
        expected_terminal = "PUBLIC_PROBE_FAIL"
    require(
        evidence["terminal_status"] == expected_terminal,
        "terminal status was not independently derived",
    )
    require(
        evidence["archive_access_status"]
        == derive_archive_access(observations),
        "archive access status was not independently derived",
    )
    require(
        set(evidence["security_assertions"]) == SECURITY_ASSERTION_FIELDS
        and all(value is False for value in evidence["security_assertions"].values()),
        "forbidden capability observed or security field drift",
    )
    require(
        evidence["market_data_ingested"] is False
        and evidence["empirical_result"] is None,
        "probe promoted market result",
    )
    require(
        set(evidence["authorizations"]) == AUTHORIZATION_FIELDS
        and evidence["authorizations"] == contract["authorizations"]
        and all(value is False for value in evidence["authorizations"].values()),
        "authorization drift",
    )
    require(
        set(ARCHIVE_IDS).issubset(
            {row["probe_id"] for row in observations}
        ),
        "archive evidence incomplete",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--allow-pending", action="store_true")
    parser.add_argument("--require-non-fail", action="store_true")
    args = parser.parse_args()

    contract = load_contract(args.contract)
    evidence = load_json(args.evidence)
    if evidence.get("status") == "PENDING_PUBLIC_PROBE_R1":
        require(args.allow_pending, "pending evidence not allowed")
        validate_pending(evidence, contract)
        print("PROBE_R1_PENDING_EVIDENCE_VALID")
        return 0

    validate_result(evidence, contract, args.contract)
    if args.require_non_fail:
        require(
            evidence["terminal_status"] != "PUBLIC_PROBE_FAIL",
            "core public probe failed",
        )
    print(
        "PROBE_R1_EVIDENCE_VALID:"
        f"{evidence['terminal_status']}:"
        f"{evidence['archive_access_status']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, ProbeContractError) as exc:
        print(f"PROBE_R1_EVIDENCE_INVALID:{exc}", file=sys.stderr)
        raise SystemExit(2)
