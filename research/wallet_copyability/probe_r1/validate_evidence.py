#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any

from contract import collector_sha256, contract_sha256, load_contract, resolve_value, sha256

SHA256 = re.compile(r"^[0-9a-f]{64}$")
TERMINAL = {"PUBLIC_PROBE_PASS", "PUBLIC_PROBE_PARTIAL", "PUBLIC_PROBE_FAIL"}


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
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        return sha256(encoded)
    return sha256((row["path"] + "?" + row["query"]).encode())


def derive(observations: list[dict[str, Any]], contract: dict[str, Any]) -> str:
    if [x["probe_id"] for x in observations] != [x["id"] for x in contract["probes"]]:
        return "PUBLIC_PROBE_FAIL"
    if any(x["status"] != "PASS" for x in observations if x["core"]):
        return "PUBLIC_PROBE_FAIL"
    if any(x["status"] != "PASS" for x in observations):
        return "PUBLIC_PROBE_PARTIAL"
    return "PUBLIC_PROBE_PASS"


def validate_pending(evidence: dict[str, Any], contract: dict[str, Any]) -> None:
    expected = {
        "schema_version", "study_id", "probe_id", "status", "observations",
        "output_sha256", "reviewed_commit", "workflow_run_id", "workflow_job_id",
        "artifact_id", "artifact_digest", "market_data_ingested", "empirical_result",
        "authorizations",
    }
    require(set(evidence) == expected, "pending evidence field drift")
    require(evidence["status"] == "PENDING_PUBLIC_PROBE_R1", "pending status drift")
    require(evidence["observations"] == [], "pending file contains observations")
    for key in ("output_sha256", "reviewed_commit", "workflow_run_id", "workflow_job_id", "artifact_id", "artifact_digest"):
        require(evidence[key] is None, f"pending evidence unexpectedly binds {key}")
    require(evidence["market_data_ingested"] is False and evidence["empirical_result"] is None, "pending pre-data boundary opened")
    require(all(value is False for value in evidence["authorizations"].values()), "pending authorization opened")
    require(evidence["study_id"] == contract["study_id"] and evidence["probe_id"] == contract["probe_id"], "pending identity drift")


def validate_result(evidence: dict[str, Any], contract: dict[str, Any]) -> None:
    top = {
        "schema_version", "study_id", "probe_id", "contract_sha256",
        "collector_bundle_sha256", "collected_at_utc", "completed_at_utc", "scope",
        "terminal_status", "registered_probe_count", "observation_count", "pass_count",
        "fail_count", "total_request_attempts", "total_declared_request_weight",
        "observations", "security_assertions", "market_data_ingested",
        "empirical_result", "authorizations",
    }
    require(set(evidence) == top, f"result evidence field drift: {sorted(set(evidence) ^ top)}")
    require(evidence["schema_version"] == "1.0", "evidence schema drift")
    require(evidence["study_id"] == contract["study_id"] and evidence["probe_id"] == contract["probe_id"], "result identity drift")
    require(evidence["contract_sha256"] == contract_sha256(), "contract hash drift")
    require(evidence["collector_bundle_sha256"] == collector_sha256(), "collector bundle hash drift")
    require(evidence["terminal_status"] in TERMINAL, "unknown terminal status")
    started = utc(evidence["collected_at_utc"], "collected_at_utc")
    completed = utc(evidence["completed_at_utc"], "completed_at_utc")
    require(completed >= started, "run completion precedes start")
    observations = evidence["observations"]
    require(isinstance(observations, list), "observations must be array")
    require(len(observations) == len(contract["probes"]), "observation coverage incomplete")
    fields = {
        "probe_id", "core", "method", "request_origin", "request_path",
        "request_sha256", "declared_weight", "attempts", "started_at_utc",
        "completed_at_utc", "http_status", "elapsed_ms", "transport_error_class",
        "transport_error_message", "expected_shape", "status", "body_length",
        "body_sha256", "content_type", "json_status", "top_level_type",
        "top_level_keys", "element_count", "sample_item_types",
    }
    for observed, registered in zip(observations, contract["probes"], strict=True):
        require(isinstance(observed, dict) and set(observed) == fields, f"observation field drift: {registered['id']}")
        require(observed["probe_id"] == registered["id"], "observation ordering drift")
        for key in ("core", "method", "declared_weight"):
            require(observed[key] == registered[key], f"observation contract drift {registered['id']}:{key}")
        require(observed["request_origin"] == registered["origin"], "origin drift")
        require(observed["request_path"] == registered["path"], "path drift")
        require(observed["request_sha256"] == expected_request_sha(registered, contract), "request hash drift")
        require(observed["expected_shape"] == registered["expected"], "expected shape drift")
        require(observed["status"] in {"PASS", "FAIL"}, "observation status drift")
        require(isinstance(observed["attempts"], int) and 1 <= observed["attempts"] <= contract["limits"]["maximum_attempts_per_probe"], "attempt count drift")
        require(isinstance(observed["body_length"], int) and 0 <= observed["body_length"] <= contract["limits"]["maximum_response_bytes"], "body length drift")
        require(isinstance(observed["body_sha256"], str) and SHA256.fullmatch(observed["body_sha256"]), "body hash invalid")
        require(isinstance(observed["top_level_keys"], list) and observed["top_level_keys"] == sorted(set(observed["top_level_keys"])), "top-level keys invalid")
        require(isinstance(observed["sample_item_types"], list) and observed["sample_item_types"] == sorted(set(observed["sample_item_types"])), "item types invalid")
        require(utc(observed["completed_at_utc"], "observation completion") >= utc(observed["started_at_utc"], "observation start"), "observation time reversal")
    require(evidence["registered_probe_count"] == len(contract["probes"]), "registered count drift")
    require(evidence["observation_count"] == len(observations), "observation count drift")
    require(evidence["pass_count"] == sum(x["status"] == "PASS" for x in observations), "pass count drift")
    require(evidence["fail_count"] == sum(x["status"] == "FAIL" for x in observations), "fail count drift")
    require(evidence["pass_count"] + evidence["fail_count"] == len(observations), "terminal count mismatch")
    attempts = sum(x["attempts"] for x in observations)
    weight = sum(x["attempts"] * x["declared_weight"] for x in observations)
    require(evidence["total_request_attempts"] == attempts <= contract["limits"]["maximum_total_requests"], "request ceiling drift")
    require(evidence["total_declared_request_weight"] == weight <= contract["limits"]["maximum_declared_request_weight"], "weight ceiling drift")
    require(evidence["terminal_status"] == derive(observations, contract), "terminal status was not derived")
    require(all(value is False for value in evidence["security_assertions"].values()), "forbidden capability observed")
    require(evidence["market_data_ingested"] is False and evidence["empirical_result"] is None, "probe promoted market result")
    require(evidence["authorizations"] == contract["authorizations"] and all(value is False for value in evidence["authorizations"].values()), "authorization drift")


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
    print(f"PROBE_R1_EVIDENCE_VALID:{evidence['terminal_status']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvidenceError as exc:
        print(f"PROBE_R1_EVIDENCE_INVALID:{exc}", file=sys.stderr)
        raise SystemExit(2)
