#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any

from contract import collector_bundle_sha256, contract_sha256, load_contract, resolve_value, sha256
from probe import ARCHIVE_IDS, derive_archive_access, derive_terminal

SHA256 = re.compile(r"^[0-9a-f]{64}$")
TERMINAL = {"PUBLIC_PROBE_PASS", "PUBLIC_PROBE_PARTIAL", "PUBLIC_PROBE_FAIL"}
ARCHIVE_STATUS = {"LISTINGS_AVAILABLE", "ROUTES_CONFIRMED_ACCESS_RESTRICTED", "ARCHIVE_ROUTE_FAILURE"}


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
            parse_constant=lambda token: (_ for _ in ()).throw(EvidenceError(f"non-finite value: {token}")),
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"invalid JSON {path}: {exc}") from exc
    require(isinstance(value, dict), "evidence root must be object")
    return value


def utc(value: Any, label: str) -> dt.datetime:
    require(isinstance(value, str) and value.endswith("Z"), f"{label} must be UTC Z string")
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise EvidenceError(f"invalid {label}: {value}") from exc
    require(parsed.tzinfo is not None, f"{label} timezone absent")
    return parsed


def expected_request_sha(row: dict[str, Any], contract: dict[str, Any]) -> str:
    if row["method"] == "POST":
        payload = resolve_value(row["payload"], contract)
        return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    return sha256((row["path"] + "?" + row["query"]).encode("utf-8"))


def validate_pending(evidence: dict[str, Any], contract: dict[str, Any]) -> None:
    expected = {
        "schema_version", "study_id", "probe_id", "status", "observations", "output_sha256",
        "reviewed_commit", "workflow_run_id", "workflow_job_id", "artifact_id", "artifact_digest",
        "market_data_ingested", "empirical_result", "authorizations",
    }
    require(set(evidence) == expected, "pending evidence field drift")
    require(evidence["schema_version"] == "1.0", "pending schema drift")
    require(evidence["status"] == "PENDING_PUBLIC_PROBE_R1", "pending status drift")
    require(evidence["observations"] == [], "pending file contains observations")
    for key in ("output_sha256", "reviewed_commit", "workflow_run_id", "workflow_job_id", "artifact_id", "artifact_digest"):
        require(evidence[key] is None, f"pending evidence unexpectedly binds {key}")
    require(evidence["market_data_ingested"] is False and evidence["empirical_result"] is None, "pending pre-data boundary opened")
    require(evidence["authorizations"] == contract["authorizations"], "pending authorization field drift")
    require(all(value is False for value in evidence["authorizations"].values()), "pending authorization opened")
    require(evidence["study_id"] == contract["study_id"] and evidence["probe_id"] == contract["probe_id"], "pending identity drift")


def validate_observation(observed: dict[str, Any], registered: dict[str, Any], contract: dict[str, Any]) -> None:
    fields = {
        "probe_id", "core", "method", "request_origin", "request_path", "request_sha256",
        "declared_weight", "attempts", "started_at_utc", "completed_at_utc", "http_status", "elapsed_ms",
        "transport_error_class", "transport_error_message", "expected_shape", "status", "body_length",
        "body_sha256", "content_type", "response_class", "json_status", "top_level_type",
        "top_level_keys", "element_count", "sample_item_types",
    }
    require(isinstance(observed, dict) and set(observed) == fields, f"observation field drift: {registered['id']}")
    require(observed["probe_id"] == registered["id"], "observation ordering drift")
    for key in ("core", "method", "declared_weight"):
        require(observed[key] == registered[key], f"observation contract drift {registered['id']}:{key}")
    require(observed["request_origin"] == registered["origin"] and observed["request_path"] == registered["path"], f"route drift: {registered['id']}")
    require(observed["request_sha256"] == expected_request_sha(registered, contract), f"request hash drift: {registered['id']}")
    require(observed["expected_shape"] == registered["expected"], f"expected shape drift: {registered['id']}")
    require(observed["status"] in {"PASS", "FAIL"}, f"observation status drift: {registered['id']}")
    require(isinstance(observed["attempts"], int) and 1 <= observed["attempts"] <= contract["limits"]["maximum_attempts_per_probe"], f"attempt count drift: {registered['id']}")
    require(isinstance(observed["declared_weight"], int) and observed["declared_weight"] >= 0, f"weight invalid: {registered['id']}")
    require(observed["http_status"] is None or isinstance(observed["http_status"], int), f"HTTP status invalid: {registered['id']}")
    require(isinstance(observed["elapsed_ms"], (int, float)) and observed["elapsed_ms"] >= 0, f"elapsed time invalid: {registered['id']}")
    require(isinstance(observed["body_length"], int) and 0 <= observed["body_length"] <= contract["limits"]["maximum_response_bytes"], f"body length drift: {registered['id']}")
    require(isinstance(observed["body_sha256"], str) and SHA256.fullmatch(observed["body_sha256"]) is not None, f"body hash invalid: {registered['id']}")
    require(observed["response_class"] in {"JSON", "S3_LISTING", "S3_ERROR_RESPONSE", "UNSUPPORTED"}, f"response class invalid: {registered['id']}")
    require(observed["json_status"] in {"VALID_JSON", "INVALID_JSON", "NOT_APPLICABLE"}, f"JSON status invalid: {registered['id']}")
    require(isinstance(observed["top_level_keys"], list) and observed["top_level_keys"] == sorted(set(observed["top_level_keys"])), f"top-level keys invalid: {registered['id']}")
    require(isinstance(observed["sample_item_types"], list) and observed["sample_item_types"] == sorted(set(observed["sample_item_types"])), f"item types invalid: {registered['id']}")
    require(utc(observed["completed_at_utc"], f"{registered['id']} completion") >= utc(observed["started_at_utc"], f"{registered['id']} start"), f"observation time reversal: {registered['id']}")
    if observed["status"] == "PASS" and registered["expected"] == "s3_listing_or_error":
        require(observed["response_class"] in {"S3_LISTING", "S3_ERROR_RESPONSE"}, f"accepted S3 class invalid: {registered['id']}")
    if observed["status"] == "PASS" and registered["expected"].startswith("json_"):
        require(observed["response_class"] == "JSON" and observed["json_status"] == "VALID_JSON", f"accepted JSON class invalid: {registered['id']}")


def validate_result(evidence: dict[str, Any], contract: dict[str, Any]) -> None:
    top = {
        "schema_version", "study_id", "probe_id", "contract_sha256", "collector_bundle_sha256",
        "collected_at_utc", "completed_at_utc", "scope", "terminal_status", "archive_access_status",
        "registered_probe_count", "observation_count", "pass_count", "fail_count",
        "total_request_attempts", "total_declared_request_weight", "observations",
        "security_assertions", "market_data_ingested", "empirical_result", "authorizations",
    }
    require(set(evidence) == top, f"result evidence field drift: {sorted(set(evidence) ^ top)}")
    require(evidence["schema_version"] == "1.1", "evidence schema drift")
    require(evidence["study_id"] == contract["study_id"] and evidence["probe_id"] == contract["probe_id"], "result identity drift")
    require(evidence["contract_sha256"] == contract_sha256(), "contract hash drift")
    require(evidence["collector_bundle_sha256"] == collector_bundle_sha256(), "collector bundle hash drift")
    require(evidence["terminal_status"] in TERMINAL and evidence["archive_access_status"] in ARCHIVE_STATUS, "unknown terminal state")
    require(utc(evidence["completed_at_utc"], "completed_at_utc") >= utc(evidence["collected_at_utc"], "collected_at_utc"), "run time reversal")
    observations = evidence["observations"]
    require(isinstance(observations, list) and len(observations) == len(contract["probes"]), "observation coverage incomplete")
    for observed, registered in zip(observations, contract["probes"], strict=True):
        validate_observation(observed, registered, contract)
    require(evidence["registered_probe_count"] == len(contract["probes"]), "registered count drift")
    require(evidence["observation_count"] == len(observations), "observation count drift")
    require(evidence["pass_count"] == sum(x["status"] == "PASS" for x in observations), "pass count drift")
    require(evidence["fail_count"] == sum(x["status"] == "FAIL" for x in observations), "fail count drift")
    require(evidence["pass_count"] + evidence["fail_count"] == len(observations), "terminal count mismatch")
    attempts = sum(x["attempts"] for x in observations)
    weight = sum(x["attempts"] * x["declared_weight"] for x in observations)
    require(evidence["total_request_attempts"] == attempts <= contract["limits"]["maximum_total_requests"], "request ceiling drift")
    require(evidence["total_declared_request_weight"] == weight <= contract["limits"]["maximum_declared_request_weight"], "weight ceiling drift")
    require(evidence["terminal_status"] == derive_terminal(observations, contract), "terminal status was not derived")
    require(evidence["archive_access_status"] == derive_archive_access(observations), "archive status was not derived")
    expected_security = {
        "credentials_used", "authorization_header_used", "cookies_used", "private_keys_used",
        "signed_actions_used", "exchange_action_endpoint_used", "orders_used", "withdrawals_used",
        "raw_response_values_persisted",
    }
    require(set(evidence["security_assertions"]) == expected_security, "security assertion field drift")
    require(all(value is False for value in evidence["security_assertions"].values()), "forbidden capability observed")
    require(evidence["market_data_ingested"] is False and evidence["empirical_result"] is None, "probe promoted market result")
    require(evidence["authorizations"] == contract["authorizations"] and all(value is False for value in evidence["authorizations"].values()), "authorization drift")
    require(set(ARCHIVE_IDS).issubset({row["probe_id"] for row in observations}), "archive evidence incomplete")


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
    validate_result(evidence, contract)
    if args.require_non_fail:
        require(evidence["terminal_status"] != "PUBLIC_PROBE_FAIL", "core public probe failed")
    print(f"PROBE_R1_EVIDENCE_VALID:{evidence['terminal_status']}:{evidence['archive_access_status']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvidenceError as exc:
        print(f"PROBE_R1_EVIDENCE_INVALID:{exc}", file=sys.stderr)
        raise SystemExit(2)
