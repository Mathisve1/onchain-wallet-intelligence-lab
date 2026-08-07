#!/usr/bin/env python3
"""Independent fail-closed validator for HL-PUBLIC-PROBE-001R2 evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "research/wallet_copyability/PROBE_CONTRACT_R2.json"
INDEX_PATH = ROOT / "research/wallet_copyability/TECHNICAL_PROBE_EVIDENCE_R2.json"
R1_ATTESTATION_PATH = ROOT / "research/wallet_copyability/evidence/r1/HL-PUBLIC-PROBE-001R1-ATTESTATION.json"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
TERMINAL = {"PUBLIC_PROBE_PASS", "PUBLIC_PROBE_PARTIAL", "PUBLIC_PROBE_FAIL"}
PARSE_OK = {"VALID_JSON", "VALID_XML"}
AUTH_KEYS = {
    "integration_authorized",
    "paper_authorized",
    "shadow_authorized",
    "live_authorized",
    "leverage_authorized",
    "capital_allocation_authorized",
}
ALLOWED_OBSERVATION_FIELDS = {
    "probe_id", "sequence", "required", "failure_impact", "method",
    "request_origin", "request_path", "request_type", "request_sha256",
    "declared_base_weight", "attempt_count", "http_status", "elapsed_ms",
    "body_length", "body_sha256", "selected_headers", "parser",
    "parse_status", "parse_error", "top_level_type", "top_level_keys",
    "element_count", "sample_item_types", "sample_item_keys", "schema_paths",
    "schema_fingerprint_sha256", "timestamp_fields", "timestamp_count",
    "min_time_ms", "max_time_ms", "xml_root", "xml_child_tags",
    "xml_key_count", "xml_contents_count", "xml_is_truncated",
    "xml_error_code", "xml_sample_key_sha256", "xml_invalid_reason",
    "assertion_status", "assertion_reason", "assertion_details", "outcome",
    "outcome_reason", "transport_error_class", "transport_error_message",
    "raw_response_bytes_retained", "response_values_retained"
}


class EvidenceError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(token: str) -> Any:
    raise EvidenceError(f"non-finite JSON constant: {token}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=strict_pairs,
            parse_constant=reject_constant,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"invalid JSON {path}: {exc}") from exc
    require(isinstance(value, dict), f"JSON root must be object: {path}")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_false_authorizations(record: dict[str, Any], label: str) -> None:
    require(set(record) == AUTH_KEYS, f"{label} authorization key drift")
    require(all(record[key] is False for key in AUTH_KEYS), f"{label} authorization opened")


def contract_by_id(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    probes = contract.get("probes")
    require(isinstance(probes, list) and len(probes) == 18, "contract probe count drift")
    result = {probe["probe_id"]: probe for probe in probes}
    require(len(result) == 18, "duplicate contract probe ID")
    require(list(result) == sorted(result), "contract probes not ordered")
    return result


def expected_outcome(observation: dict[str, Any], probe: dict[str, Any]) -> str:
    http_ok = observation.get("http_status") in set(probe["expected_http_statuses"])
    parser_ok = observation.get("parse_status") in PARSE_OK
    if not http_ok or not parser_ok:
        return "FAIL"
    if observation.get("assertion_status") == "PASS":
        return "PASS"
    if probe.get("failure_impact") == "DEGRADE":
        return "DEGRADED"
    return "FAIL"


def validate_r1_attestation() -> None:
    r1 = load_json(R1_ATTESTATION_PATH)
    require(r1.get("status") == "IMMUTABLE_FAILED_R1_SUCCESSOR_REQUIRED", "R1 disposition drift")
    require(r1.get("reviewed_commit") == "6a204c928301613830dbdaa0678cca33917bb3bc", "R1 commit drift")
    workflow = r1.get("workflow", {})
    require(workflow.get("run_id") == 31167864088, "R1 run drift")
    require(workflow.get("job_id") == 92832736953, "R1 job drift")
    require(workflow.get("artifact_id") == 8989720791, "R1 artifact drift")
    require(workflow.get("artifact_sha256") == "c7d2b60fbd2edf15a5edb4b687b17c45685ea0b129a97ed77eddd5e0d40096f9", "R1 artifact hash drift")
    require(r1.get("market_data_ingested") is False and r1.get("empirical_result") is None, "R1 evidence boundary drift")
    require_false_authorizations({key: r1[key] for key in AUTH_KEYS}, "R1")


def validate_pending(index: dict[str, Any], contract: dict[str, Any]) -> None:
    expected_keys = {
        "schema_version", "study_id", "probe_id", "contract_id", "status",
        "supersedes_probe_id", "reviewed_commit", "workflow_run_id",
        "workflow_job_id", "artifact_id", "artifact_sha256", "output_sha256",
        "observations", "market_data_ingested", "empirical_result", *AUTH_KEYS
    }
    require(set(index) == expected_keys, "pending R2 evidence key drift")
    require(index["schema_version"] == "1.0", "pending schema drift")
    require(index["study_id"] == contract["study_id"], "pending study drift")
    require(index["probe_id"] == contract["probe_id"], "pending probe drift")
    require(index["contract_id"] == contract["contract_id"], "pending contract drift")
    require(index["status"] == "PENDING_PUBLIC_PROBE_R2", "pending status drift")
    require(index["supersedes_probe_id"] == "HL-PUBLIC-PROBE-001R1", "successor lineage drift")
    for key in ("reviewed_commit", "workflow_run_id", "workflow_job_id", "artifact_id", "artifact_sha256", "output_sha256"):
        require(index[key] is None, f"pending evidence prematurely sets {key}")
    require(index["observations"] == [], "pending evidence contains observations")
    require(index["market_data_ingested"] is False and index["empirical_result"] is None, "pending empirical boundary drift")
    require_false_authorizations({key: index[key] for key in AUTH_KEYS}, "pending R2")


def validate_output(payload: dict[str, Any], contract: dict[str, Any], path: Path) -> None:
    require(payload.get("schema_version") == "1.0", "output schema drift")
    require(payload.get("study_id") == contract["study_id"], "output study drift")
    require(payload.get("probe_id") == contract["probe_id"], "output probe drift")
    require(payload.get("contract_id") == contract["contract_id"], "output contract drift")
    require(payload.get("scope") == "READ_ONLY_PUBLIC_SCHEMA_RELATIONSHIP_LIMIT_AND_ARCHIVE_AVAILABILITY_PROBE", "output scope drift")
    require(SHA40_RE.fullmatch(str(payload.get("reviewed_commit", ""))) is not None, "reviewed commit invalid")
    workflow = payload.get("workflow")
    require(isinstance(workflow, dict), "workflow identity absent")
    require(workflow.get("repository") == "Mathisve1/onchain-wallet-intelligence-lab", "repository identity drift")
    require(isinstance(workflow.get("run_id"), int) and workflow["run_id"] > 0, "workflow run ID invalid")
    require(isinstance(workflow.get("run_attempt"), int) and workflow["run_attempt"] > 0, "workflow attempt invalid")
    require(isinstance(workflow.get("job_name"), str) and workflow["job_name"], "workflow job absent")

    hashes = payload.get("input_hashes")
    require(isinstance(hashes, dict), "input hashes absent")
    require(hashes.get("contract_sha256") == sha256_file(CONTRACT_PATH), "contract byte hash drift")
    for key, value in hashes.items():
        require(SHA256_RE.fullmatch(str(value)) is not None, f"invalid input hash: {key}")

    probes = contract_by_id(contract)
    observations = payload.get("observations")
    require(isinstance(observations, list) and len(observations) == 18, "output observation count drift")
    require([item.get("probe_id") for item in observations] == list(probes), "observation identity/order drift")
    outcomes: list[str] = []
    for sequence, observation in enumerate(observations, 1):
        require(isinstance(observation, dict), "observation is not object")
        unknown = set(observation) - ALLOWED_OBSERVATION_FIELDS
        require(not unknown, f"unknown observation fields for {observation.get('probe_id')}: {sorted(unknown)}")
        probe = probes[observation["probe_id"]]
        require(observation.get("sequence") == sequence, f"sequence drift: {observation['probe_id']}")
        require(observation.get("required") is probe["required"], f"required drift: {observation['probe_id']}")
        require(observation.get("failure_impact") == probe["failure_impact"], f"failure impact drift: {observation['probe_id']}")
        require(observation.get("method") == probe["method"], f"method drift: {observation['probe_id']}")
        require(SHA256_RE.fullmatch(str(observation.get("request_sha256", ""))) is not None, f"request hash invalid: {observation['probe_id']}")
        require(SHA256_RE.fullmatch(str(observation.get("body_sha256", ""))) is not None, f"body hash invalid: {observation['probe_id']}")
        require(SHA256_RE.fullmatch(str(observation.get("schema_fingerprint_sha256", ""))) is not None, f"schema hash invalid: {observation['probe_id']}")
        require(observation.get("raw_response_bytes_retained") is False, f"raw bytes retained: {observation['probe_id']}")
        require(observation.get("response_values_retained") is False, f"response values retained: {observation['probe_id']}")
        expected = expected_outcome(observation, probe)
        require(observation.get("outcome") == expected, f"outcome drift: {observation['probe_id']}")
        outcomes.append(expected)

    pass_count = outcomes.count("PASS")
    degraded_count = outcomes.count("DEGRADED")
    fail_count = outcomes.count("FAIL")
    terminal = "PUBLIC_PROBE_FAIL" if fail_count else ("PUBLIC_PROBE_PARTIAL" if degraded_count else "PUBLIC_PROBE_PASS")
    derived = payload.get("derived")
    require(isinstance(derived, dict), "derived result absent")
    require(derived.get("terminal_status") == terminal, "terminal status drift")
    require(derived.get("pass_count") == pass_count, "pass count drift")
    require(derived.get("degraded_count") == degraded_count, "degraded count drift")
    require(derived.get("fail_count") == fail_count, "fail count drift")
    require(derived.get("required_failures") == [item["probe_id"] for item in observations if item["required"] and item["outcome"] == "FAIL"], "required failure list drift")
    require(derived.get("degraded_probes") == [item["probe_id"] for item in observations if item["outcome"] == "DEGRADED"], "degraded list drift")
    require(derived.get("optional_failures") == [item["probe_id"] for item in observations if not item["required"] and item["outcome"] == "FAIL"], "optional failure list drift")

    controls = payload.get("controls")
    require(isinstance(controls, dict) and controls, "controls absent")
    require(all(value is False for value in controls.values()), "forbidden capability used")
    require(payload.get("market_data_ingested") is False and payload.get("empirical_result") is None, "empirical boundary drift")
    require_false_authorizations(payload.get("authorizations", {}), "R2 output")
    require(SHA256_RE.fullmatch(hashlib.sha256(path.read_bytes()).hexdigest()) is not None, "output hash calculation failed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        contract = load_json(CONTRACT_PATH)
        require(contract.get("contract_id") == "HYPERLIQUID_PUBLIC_TECHNICAL_PROBE_CONTRACT_R2", "active R2 contract missing")
        require(contract.get("probe_id") == "HL-PUBLIC-PROBE-001R2", "active R2 probe missing")
        require_false_authorizations(contract.get("authorizations", {}), "R2 contract")
        validate_r1_attestation()
        if args.output is None:
            validate_pending(load_json(INDEX_PATH), contract)
        else:
            validate_output(load_json(args.output), contract, args.output)
    except EvidenceError as exc:
        print(f"PROBE_R2_EVIDENCE_VALIDATION_FAIL: {exc}")
        return 1
    print("PROBE_R2_EVIDENCE_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
