#!/usr/bin/env python3
"""Fail-closed validation for Hyperliquid public technical probe R1 evidence."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "research/wallet_copyability/PROBE_CONTRACT.json"
SOURCE_REGISTER_PATH = ROOT / "research/wallet_copyability/OFFICIAL_SOURCE_REGISTER.json"
SCRIPT_PATH = ROOT / "research/wallet_copyability/scripts/probe_public_api.py"
INDEX_PATH = ROOT / "research/wallet_copyability/TECHNICAL_PROBE_EVIDENCE.json"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
ARTIFACT_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

AUTH_KEYS = {
    "integration_authorized",
    "paper_authorized",
    "shadow_authorized",
    "live_authorized",
    "leverage_authorized",
    "capital_allocation_authorized",
}
ALLOWED_TERMINAL = {
    "PUBLIC_PROBE_PASS",
    "PUBLIC_PROBE_PARTIAL",
    "PUBLIC_PROBE_FAIL",
}
ALLOWED_OUTCOMES = {"PASS", "DEGRADED", "FAIL"}
ALLOWED_PARSERS = {"JSON", "XML"}
ALLOWED_PARSE_STATUS = {
    "VALID_JSON",
    "INVALID_JSON",
    "VALID_XML",
    "INVALID_XML",
    "EMPTY_BODY",
    "NOT_ATTEMPTED",
}
INDEX_FIELDS = {
    "schema_version",
    "study_id",
    "probe_id",
    "probe_contract_path",
    "probe_contract_sha256",
    "status",
    "evidence_path",
    "output_sha256",
    "reviewed_commit",
    "workflow_run_id",
    "workflow_job_id",
    "artifact_id",
    "artifact_digest",
    "observation_count",
    "pass_count",
    "degraded_count",
    "fail_count",
    "terminal_status",
    "market_data_ingested",
    "empirical_result",
    "authorizations",
}
OUTPUT_FIELDS = {
    "schema_version",
    "study_id",
    "probe_id",
    "contract_id",
    "scope",
    "collected_at_utc",
    "anchor_time_ms",
    "reviewed_commit",
    "workflow",
    "environment",
    "input_hashes",
    "network_projection",
    "observations",
    "derived",
    "controls",
    "market_data_ingested",
    "empirical_result",
    "authorizations",
}
WORKFLOW_FIELDS = {"repository", "run_id", "run_attempt", "job_name", "ref"}
INPUT_HASH_FIELDS = {"contract_sha256", "source_register_sha256", "script_sha256"}
NETWORK_FIELDS = {
    "allowed_origins",
    "request_count",
    "declared_base_weight",
    "cross_origin_redirects_allowed",
    "maximum_response_bytes",
}
DERIVED_FIELDS = {
    "terminal_status",
    "pass_count",
    "degraded_count",
    "fail_count",
    "required_failures",
    "degraded_probes",
    "optional_failures",
    "documentation_limit_observation",
}
CONTROL_FIELDS = {
    "credentials_used",
    "authorization_headers_used",
    "environment_secrets_used",
    "signed_actions_used",
    "exchange_action_endpoint_used",
    "orders_used",
    "withdrawals_used",
    "raw_response_bytes_retained",
    "response_values_retained",
}
OBSERVATION_FIELDS = {
    "probe_id",
    "sequence",
    "required",
    "failure_impact",
    "method",
    "request_origin",
    "request_path",
    "request_type",
    "request_sha256",
    "declared_base_weight",
    "attempt_count",
    "http_status",
    "elapsed_ms",
    "body_length",
    "body_sha256",
    "selected_headers",
    "parser",
    "parse_status",
    "parse_error",
    "top_level_type",
    "top_level_keys",
    "element_count",
    "sample_item_types",
    "sample_item_keys",
    "schema_paths",
    "schema_fingerprint_sha256",
    "assertion_status",
    "assertion_reason",
    "assertion_details",
    "outcome",
    "outcome_reason",
    "transport_error_class",
    "transport_error_message",
    "raw_response_bytes_retained",
    "response_values_retained",
}
ALLOWED_IMPORT_ROOTS = {
    "__future__",
    "argparse",
    "datetime",
    "hashlib",
    "json",
    "platform",
    "re",
    "sys",
    "time",
    "urllib",
    "xml",
    "pathlib",
    "typing",
}
FORBIDDEN_STRING_FRAGMENTS = {
    "api.hyperliquid.xyz/exchange",
    "private_key",
    "privatekey",
    "secret_key",
    "secretkey",
    "api_key",
    "apikey",
    "sign_l1_action",
    "send-signed-action",
    "market_open",
    "market_close",
    "cancel_order",
    "withdraw3",
}
FORBIDDEN_CALL_NAMES = {"eval", "exec", "compile", "__import__"}


class ValidationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(token: str) -> Any:
    raise ValidationError(f"non-finite JSON constant: {token}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=strict_pairs,
            parse_constant=reject_constant,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"invalid JSON {path}: {exc}") from exc
    require(isinstance(value, dict), f"JSON root must be object: {path}")
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_fields(record: dict[str, Any], expected: set[str], label: str) -> None:
    require(set(record) == expected, f"{label} field drift: {sorted(set(record) ^ expected)}")


def false_authorizations(record: dict[str, Any], label: str) -> None:
    require(set(record) == AUTH_KEYS, f"{label} authorization key drift")
    for key in AUTH_KEYS:
        require(record[key] is False, f"{label} authorization opened: {key}")


def validate_static_probe_script(contract: dict[str, Any], script_path: Path = SCRIPT_PATH) -> None:
    text = script_path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(script_path))
    allowed_origins = set(contract["network_policy"]["allowed_origins"])

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                require(root in ALLOWED_IMPORT_ROOTS, f"probe imports forbidden module: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            require(root in ALLOWED_IMPORT_ROOTS, f"probe imports forbidden module: {node.module}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                require(node.func.id not in FORBIDDEN_CALL_NAMES, f"probe uses dynamic execution: {node.func.id}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            lowered = node.value.lower()
            for fragment in FORBIDDEN_STRING_FRAGMENTS:
                require(fragment not in lowered, f"probe contains forbidden capability token: {fragment}")
            if node.value.startswith("https://") and node.value != "https://" and "{" not in node.value:
                from urllib.parse import urlsplit

                parsed = urlsplit(node.value)
                require(parsed.hostname is not None, f"probe contains malformed URL literal: {node.value}")
                origin = f"https://{parsed.hostname}" if parsed.port in (None, 443) else f"https://{parsed.hostname}:{parsed.port}"
                require(origin in allowed_origins, f"probe contains non-allowlisted URL: {origin}")

    require('"Authorization"' not in text and "'Authorization'" not in text, "probe contains authorization header capability")
    require("urllib.request" in text, "probe must use standard-library HTTP client")
    require("SafeRedirectHandler" in text, "probe must enforce redirect policy")
    require("ResponseTooLarge" in text, "probe must enforce response byte ceiling")
    require("raw_response_bytes_retained\": False" in text, "probe does not assert raw-byte non-retention")
    require("response_values_retained\": False" in text, "probe does not assert value non-retention")


def validate_contract(contract: dict[str, Any]) -> None:
    require(contract.get("schema_version") == "1.0", "probe contract schema drift")
    require(contract.get("contract_id") == "HYPERLIQUID_PUBLIC_TECHNICAL_PROBE_CONTRACT_R1", "probe contract ID drift")
    require(contract.get("study_id") == "WALLET-COPYABILITY-STUDY-001", "probe contract study drift")
    require(contract.get("probe_id") == "HL-PUBLIC-PROBE-001R1", "probe contract probe ID drift")
    require(contract.get("status") == "FROZEN_PRE_EXECUTION", "probe contract not frozen")
    require(contract.get("market_data_ingested") is False, "probe contract claims market ingest")
    require(contract.get("empirical_result") is None, "probe contract creates result")
    false_authorizations(contract["authorizations"], "probe contract")

    execution = contract["execution_boundary"]
    require(execution.get("read_only") is True, "probe contract read-only false")
    for key, value in execution.items():
        if key != "read_only":
            require(value is False, f"probe contract execution capability opened: {key}")

    policy = contract["network_policy"]
    require(policy["allowed_methods"] == ["GET", "POST"], "allowed method drift")
    require(policy["cross_origin_redirects_allowed"] is False, "cross-origin redirects enabled")
    require(policy["maximum_request_count"] == len(contract["probes"]), "request count drift")
    require(len(contract["probes"]) == 18, "registered probe count drift")
    ids = [probe["probe_id"] for probe in contract["probes"]]
    require(len(ids) == len(set(ids)), "duplicate probe ID")
    require(ids == [f"P{i:03d}_{suffix}" for i, suffix in enumerate([
        "META",
        "ALL_MIDS",
        "MASTER_USER_ROLE",
        "MASTER_SUBACCOUNTS",
        "SUBACCOUNT_USER_ROLE",
        "SUBACCOUNT_STATE",
        "MASTER_USER_FEES",
        "SUBACCOUNT_RECENT_FILLS",
        "SUBACCOUNT_FILLS_BY_TIME_FIXED",
        "SUBACCOUNT_FUNDING_FIXED",
        "SUBACCOUNT_NON_FUNDING_LEDGER_FIXED",
        "VAULT_USER_ROLE",
        "VAULT_DETAILS",
        "VAULT_FILLS_BY_TIME_RECENT_24H",
        "L2_BOOK_BTC",
        "NODE_FILL_ARCHIVE_LISTING",
        "MARKET_DATA_ARCHIVE_LISTING",
        "ASSET_CTXS_ARCHIVE_LISTING",
    ], 1)], "probe order or identity drift")
    total_weight = sum(int(probe["base_weight"]) for probe in contract["probes"])
    require(total_weight <= int(policy["maximum_declared_base_weight"]), "declared weight exceeds ceiling")
    for probe in contract["probes"]:
        require(probe["origin"] in policy["allowed_origins"], f"probe origin drift: {probe['probe_id']}")
        require(probe["method"] in policy["allowed_methods"], f"probe method drift: {probe['probe_id']}")
        require("/exchange" not in probe["path"].lower(), f"exchange endpoint in contract: {probe['probe_id']}")



def validate_source_register(register: dict[str, Any]) -> None:
    exact_fields(
        register,
        {
            "schema_version",
            "study_id",
            "status",
            "captured_at_utc",
            "sources",
            "documentation_conflicts_to_probe",
            "authorizations",
        },
        "official source register",
    )
    require(register["schema_version"] == "2.0", "source register schema drift")
    require(register["study_id"] == "WALLET-COPYABILITY-STUDY-001", "source register study drift")
    require(register["status"] == "OFFICIAL_SOURCE_REGISTER_PRE_DATA", "source register status drift")
    false_authorizations(register["authorizations"], "official source register")
    sources = register["sources"]
    require(isinstance(sources, list) and len(sources) == 8, "official source count drift")
    expected_ids = [f"HL-OFFICIAL-{index:03d}" for index in range(1, 9)]
    require([source.get("source_id") for source in sources] == expected_ids, "official source ID/order drift")
    for source in sources:
        exact_fields(
            source,
            {"source_id", "publisher", "source_class", "title", "url", "claims_used"},
            f"official source {source.get('source_id')}",
        )
        url = source["url"]
        require(isinstance(url, str) and url.startswith("https://"), "official source URL is not HTTPS")
        from urllib.parse import urlsplit

        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        require(host in {"hyperliquid.gitbook.io", "github.com"}, f"non-official source host: {host}")
        if host == "github.com":
            require(parsed.path.startswith("/hyperliquid-dex/"), "GitHub source is not hyperliquid-dex")
        require(isinstance(source["claims_used"], list) and source["claims_used"], f"source claims absent: {source['source_id']}")
    conflicts = register["documentation_conflicts_to_probe"]
    require(isinstance(conflicts, list) and len(conflicts) == 3, "documentation conflict count drift")
    ids = [item.get("conflict_id") for item in conflicts]
    require(len(ids) == len(set(ids)), "duplicate documentation conflict ID")
    for conflict in conflicts:
        require(conflict.get("analytical_release_allowed") is False, f"documentation conflict opens release: {conflict.get('conflict_id')}")
        require(isinstance(conflict.get("status"), str) and conflict["status"], f"documentation conflict status absent: {conflict.get('conflict_id')}")

def expected_request_type(probe: dict[str, Any]) -> str | None:
    payload = probe.get("payload")
    return payload.get("type") if isinstance(payload, dict) else None


def validate_observation(
    observation: dict[str, Any],
    probe: dict[str, Any],
    contract: dict[str, Any],
    sequence: int,
) -> None:
    exact_fields(observation, OBSERVATION_FIELDS, f"observation {sequence}")
    require(observation["probe_id"] == probe["probe_id"], f"probe ID mismatch at {sequence}")
    require(observation["sequence"] == sequence, f"sequence mismatch for {probe['probe_id']}")
    require(observation["required"] is probe["required"], f"required flag drift for {probe['probe_id']}")
    require(observation["failure_impact"] == probe.get("failure_impact", "FAIL"), f"failure impact drift for {probe['probe_id']}")
    require(observation["method"] == probe["method"], f"method drift for {probe['probe_id']}")
    require(observation["request_origin"] == probe["origin"], f"origin drift for {probe['probe_id']}")
    require(observation["request_path"] == probe["path"], f"path drift for {probe['probe_id']}")
    require(observation["request_type"] == expected_request_type(probe), f"request type drift for {probe['probe_id']}")
    require(SHA256_RE.fullmatch(observation["request_sha256"]) is not None, f"invalid request hash for {probe['probe_id']}")
    require(observation["declared_base_weight"] == probe["base_weight"], f"weight drift for {probe['probe_id']}")
    require(isinstance(observation["attempt_count"], int) and 1 <= observation["attempt_count"] <= contract["network_policy"]["maximum_attempts"], f"attempt count drift for {probe['probe_id']}")
    require(observation["http_status"] is None or isinstance(observation["http_status"], int), f"HTTP status invalid for {probe['probe_id']}")
    require(isinstance(observation["elapsed_ms"], (int, float)) and observation["elapsed_ms"] >= 0, f"elapsed time invalid for {probe['probe_id']}")
    require(isinstance(observation["body_length"], int) and 0 <= observation["body_length"] <= contract["network_policy"]["maximum_response_bytes"], f"body length invalid for {probe['probe_id']}")
    require(SHA256_RE.fullmatch(observation["body_sha256"]) is not None, f"invalid body hash for {probe['probe_id']}")
    require(set(observation["selected_headers"]).issubset(set(contract["data_minimization"]["selected_response_headers"])), f"header allowlist drift for {probe['probe_id']}")
    require(observation["parser"] == probe["parser"] and observation["parser"] in ALLOWED_PARSERS, f"parser drift for {probe['probe_id']}")
    require(observation["parse_status"] in ALLOWED_PARSE_STATUS, f"parse status drift for {probe['probe_id']}")
    require(isinstance(observation["top_level_keys"], list), f"top-level keys invalid for {probe['probe_id']}")
    require(isinstance(observation["sample_item_types"], list), f"sample item types invalid for {probe['probe_id']}")
    require(isinstance(observation["sample_item_keys"], list), f"sample item keys invalid for {probe['probe_id']}")
    require(isinstance(observation["schema_paths"], list), f"schema paths invalid for {probe['probe_id']}")
    require(len(observation["schema_paths"]) <= contract["data_minimization"]["maximum_schema_paths"], f"schema path ceiling exceeded for {probe['probe_id']}")
    schema_fingerprint = hashlib.sha256(canonical_bytes(observation["schema_paths"])).hexdigest()
    require(observation["schema_fingerprint_sha256"] == schema_fingerprint, f"schema fingerprint mismatch for {probe['probe_id']}")
    require(observation["assertion_status"] in ALLOWED_OUTCOMES, f"assertion status drift for {probe['probe_id']}")
    require(observation["outcome"] in ALLOWED_OUTCOMES, f"outcome drift for {probe['probe_id']}")
    require(observation["raw_response_bytes_retained"] is False, f"raw bytes retained for {probe['probe_id']}")
    require(observation["response_values_retained"] is False, f"response values retained for {probe['probe_id']}")
    if observation["outcome"] in {"PASS", "DEGRADED"}:
        required_parse = "VALID_JSON" if probe["parser"] == "JSON" else "VALID_XML"
        require(observation["parse_status"] == required_parse, f"non-failing probe lacks valid parse: {probe['probe_id']}")
    if probe["assertion"] == "ROLE_EQUALS" and observation["outcome"] == "PASS":
        require(observation["assertion_details"].get("actual_role") == probe["expected_role"], f"role pass without role match: {probe['probe_id']}")
    if probe["assertion"] == "SUBACCOUNT_RELATION_PRESENT" and observation["outcome"] == "PASS":
        require(observation["assertion_details"].get("relation_present") is True, "subaccount pass without relation")
    if probe["assertion"] == "SUBACCOUNT_ROLE_AND_MASTER" and observation["outcome"] == "PASS":
        require(observation["assertion_details"].get("role_match") is True, "subaccount role pass mismatch")
        require(observation["assertion_details"].get("master_match") is True, "subaccount master pass mismatch")
    if probe["assertion"] == "S3_LISTING_OR_ACCESS_CONTROL" and observation["outcome"] == "DEGRADED":
        require(observation["http_status"] == 403, f"archive degraded without HTTP 403: {probe['probe_id']}")
        require(observation["assertion_details"].get("xml_error_code") in {"AccessDenied", "InvalidRequest"}, f"archive degraded without expected error: {probe['probe_id']}")


def derive_terminal(observations: list[dict[str, Any]]) -> tuple[str, list[str], list[str], list[str]]:
    required_failures = [row["probe_id"] for row in observations if row["required"] and row["outcome"] == "FAIL"]
    degraded = [row["probe_id"] for row in observations if row["outcome"] == "DEGRADED"]
    optional_failures = [row["probe_id"] for row in observations if not row["required"] and row["outcome"] == "FAIL"]
    if required_failures:
        terminal = "PUBLIC_PROBE_FAIL"
    elif degraded or optional_failures:
        terminal = "PUBLIC_PROBE_PARTIAL"
    else:
        terminal = "PUBLIC_PROBE_PASS"
    return terminal, required_failures, degraded, optional_failures


def validate_probe_output(output: dict[str, Any], contract: dict[str, Any]) -> None:
    exact_fields(output, OUTPUT_FIELDS, "probe output")
    require(output["schema_version"] == "1.0", "output schema drift")
    require(output["study_id"] == contract["study_id"], "output study drift")
    require(output["probe_id"] == contract["probe_id"], "output probe drift")
    require(output["contract_id"] == contract["contract_id"], "output contract drift")
    require(SHA40_RE.fullmatch(output["reviewed_commit"]) is not None, "output reviewed commit invalid")
    require(isinstance(output["anchor_time_ms"], int) and output["anchor_time_ms"] > 0, "output anchor time invalid")

    exact_fields(output["workflow"], WORKFLOW_FIELDS, "output workflow")
    require(isinstance(output["workflow"]["run_id"], int) and output["workflow"]["run_id"] > 0, "workflow run ID invalid")
    require(isinstance(output["workflow"]["run_attempt"], int) and output["workflow"]["run_attempt"] > 0, "workflow run attempt invalid")
    require(all(isinstance(output["workflow"][key], str) and output["workflow"][key] for key in ("repository", "job_name", "ref")), "workflow text identity invalid")

    exact_fields(output["input_hashes"], INPUT_HASH_FIELDS, "input hashes")
    require(output["input_hashes"]["contract_sha256"] == sha256_file(CONTRACT_PATH), "contract hash mismatch")
    require(output["input_hashes"]["source_register_sha256"] == sha256_file(SOURCE_REGISTER_PATH), "source register hash mismatch")
    require(output["input_hashes"]["script_sha256"] == sha256_file(SCRIPT_PATH), "script hash mismatch")

    exact_fields(output["network_projection"], NETWORK_FIELDS, "network projection")
    require(output["network_projection"]["allowed_origins"] == sorted(contract["network_policy"]["allowed_origins"]), "allowed-origin projection mismatch")
    require(output["network_projection"]["request_count"] == len(contract["probes"]), "request-count projection mismatch")
    require(output["network_projection"]["declared_base_weight"] == sum(probe["base_weight"] for probe in contract["probes"]), "weight projection mismatch")
    require(output["network_projection"]["cross_origin_redirects_allowed"] is False, "redirect projection opened")
    require(output["network_projection"]["maximum_response_bytes"] == contract["network_policy"]["maximum_response_bytes"], "response ceiling projection mismatch")

    observations = output["observations"]
    require(isinstance(observations, list) and len(observations) == len(contract["probes"]), "observation coverage drift")
    for sequence, (observation, probe) in enumerate(zip(observations, contract["probes"], strict=True), 1):
        require(isinstance(observation, dict), f"observation {sequence} is not object")
        validate_observation(observation, probe, contract, sequence)

    exact_fields(output["derived"], DERIVED_FIELDS, "derived output")
    terminal, required_failures, degraded, optional_failures = derive_terminal(observations)
    require(output["derived"]["terminal_status"] == terminal, "terminal status not derived")
    require(output["derived"]["terminal_status"] in ALLOWED_TERMINAL, "terminal status invalid")
    require(output["derived"]["pass_count"] == sum(row["outcome"] == "PASS" for row in observations), "pass count mismatch")
    require(output["derived"]["degraded_count"] == sum(row["outcome"] == "DEGRADED" for row in observations), "degraded count mismatch")
    require(output["derived"]["fail_count"] == sum(row["outcome"] == "FAIL" for row in observations), "fail count mismatch")
    require(output["derived"]["required_failures"] == required_failures, "required failures mismatch")
    require(output["derived"]["degraded_probes"] == degraded, "degraded probe list mismatch")
    require(output["derived"]["optional_failures"] == optional_failures, "optional failure list mismatch")
    limit_observation = next(row for row in observations if row["probe_id"] == "P014_VAULT_FILLS_BY_TIME_RECENT_24H")["assertion_details"].get("limit_observation")
    require(output["derived"]["documentation_limit_observation"] == limit_observation, "documentation limit observation mismatch")

    exact_fields(output["controls"], CONTROL_FIELDS, "output controls")
    require(all(value is False for value in output["controls"].values()), "output control claims unsafe capability")
    require(output["market_data_ingested"] is False, "output claims market data ingest")
    require(output["empirical_result"] is None, "output creates empirical result")
    false_authorizations(output["authorizations"], "probe output")


def validate_evidence_index(index: dict[str, Any], contract: dict[str, Any]) -> None:
    exact_fields(index, INDEX_FIELDS, "probe evidence index")
    require(index["schema_version"] == "2.0", "evidence index schema drift")
    require(index["study_id"] == contract["study_id"], "evidence index study drift")
    require(index["probe_id"] == contract["probe_id"], "evidence index probe drift")
    require(index["probe_contract_path"] == CONTRACT_PATH.relative_to(ROOT).as_posix(), "evidence contract path drift")
    require(index["probe_contract_sha256"] == sha256_file(CONTRACT_PATH), "evidence contract hash mismatch")
    require(index["market_data_ingested"] is False, "evidence claims market ingest")
    require(index["empirical_result"] is None, "evidence creates empirical result")
    false_authorizations(index["authorizations"], "probe evidence index")

    status = index["status"]
    if status == "PENDING_PUBLIC_PROBE":
        for key in (
            "evidence_path",
            "output_sha256",
            "reviewed_commit",
            "workflow_run_id",
            "workflow_job_id",
            "artifact_id",
            "artifact_digest",
            "terminal_status",
        ):
            require(index[key] is None, f"pending evidence has premature field: {key}")
        for key in ("observation_count", "pass_count", "degraded_count", "fail_count"):
            require(index[key] == 0, f"pending evidence has nonzero count: {key}")
        return

    require(status in ALLOWED_TERMINAL, "evidence status invalid")
    require(index["terminal_status"] == status, "evidence terminal/status mismatch")
    require(isinstance(index["evidence_path"], str) and index["evidence_path"], "final evidence path absent")
    evidence_path = ROOT / index["evidence_path"]
    require(evidence_path.is_file(), "final evidence file absent")
    require(SHA256_RE.fullmatch(index["output_sha256"]) is not None, "final output hash invalid")
    require(sha256_file(evidence_path) == index["output_sha256"], "final output hash mismatch")
    require(SHA40_RE.fullmatch(index["reviewed_commit"]) is not None, "final reviewed commit invalid")
    for key in ("workflow_run_id", "workflow_job_id", "artifact_id"):
        require(isinstance(index[key], int) and index[key] > 0, f"final evidence ID invalid: {key}")
    require(isinstance(index["artifact_digest"], str) and ARTIFACT_DIGEST_RE.fullmatch(index["artifact_digest"]) is not None, "artifact digest invalid")

    output = load_json(evidence_path)
    validate_probe_output(output, contract)
    require(output["reviewed_commit"] == index["reviewed_commit"], "reviewed commit index/output mismatch")
    require(output["workflow"]["run_id"] == index["workflow_run_id"], "run ID index/output mismatch")
    require(output["derived"]["terminal_status"] == index["terminal_status"], "terminal index/output mismatch")
    require(len(output["observations"]) == index["observation_count"], "observation count index/output mismatch")
    require(output["derived"]["pass_count"] == index["pass_count"], "pass count index/output mismatch")
    require(output["derived"]["degraded_count"] == index["degraded_count"], "degraded count index/output mismatch")
    require(output["derived"]["fail_count"] == index["fail_count"], "fail count index/output mismatch")


def validate_repository_probe() -> None:
    contract = load_json(CONTRACT_PATH)
    register = load_json(SOURCE_REGISTER_PATH)
    validate_contract(contract)
    validate_source_register(register)
    validate_static_probe_script(contract)
    index = load_json(INDEX_PATH)
    validate_evidence_index(index, contract)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        contract = load_json(CONTRACT_PATH)
        register = load_json(SOURCE_REGISTER_PATH)
        validate_contract(contract)
        validate_source_register(register)
        validate_static_probe_script(contract)
        if args.output is None:
            index = load_json(INDEX_PATH)
            validate_evidence_index(index, contract)
            label = "PROBE_EVIDENCE_VALIDATION_PASS"
        else:
            output = load_json(args.output.resolve())
            validate_probe_output(output, contract)
            label = "PROBE_OUTPUT_VALIDATION_PASS"
    except ValidationError as exc:
        print(f"PROBE_EVIDENCE_VALIDATION_FAIL: {exc}")
        return 1
    print(label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
