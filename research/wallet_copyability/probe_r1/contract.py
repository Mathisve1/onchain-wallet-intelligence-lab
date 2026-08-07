from __future__ import annotations

import hashlib
import json
import urllib.parse
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
CONTRACT_PATH = ROOT / "PROBE_CONTRACT.json"
COLLECTOR_FILES = ("contract.py", "http_client.py", "probe.py", "validate_evidence.py")


class ProbeContractError(ValueError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProbeContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_object,
            parse_constant=lambda token: (_ for _ in ()).throw(ProbeContractError(f"non-finite JSON constant: {token}")),
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProbeContractError(f"invalid contract: {exc}") from exc
    if not isinstance(value, dict):
        raise ProbeContractError("contract root must be an object")
    validate_contract(value)
    return value


def contract_sha256(path: Path = CONTRACT_PATH) -> str:
    return sha256(path.read_bytes())


def collector_bundle_sha256() -> str:
    digest = hashlib.sha256()
    for name in COLLECTOR_FILES:
        data = (ROOT / name).read_bytes()
        digest.update(name.encode("utf-8") + b"\0" + len(data).to_bytes(8, "big") + data)
    return digest.hexdigest()


def validate_contract(contract: dict[str, Any]) -> None:
    required_top = {
        "schema_version", "study_id", "probe_id", "status", "purpose", "venue",
        "allowed_origins", "documentation_fixtures", "fixed_window", "limits",
        "security_boundary", "terminal_rule", "probes", "authorizations",
        "market_data_ingested", "empirical_result",
    }
    if set(contract) != required_top:
        raise ProbeContractError(f"contract top-level field drift: {sorted(set(contract) ^ required_top)}")
    if contract["schema_version"] != "1.1":
        raise ProbeContractError("contract schema drift")
    if contract["study_id"] != "WALLET-COPYABILITY-STUDY-001" or contract["probe_id"] != "HL-PUBLIC-PROBE-001R1":
        raise ProbeContractError("probe identity drift")
    if contract["status"] != "FROZEN_READ_ONLY_PUBLIC_PROBE":
        raise ProbeContractError("probe status drift")
    if contract["market_data_ingested"] is not False or contract["empirical_result"] is not None:
        raise ProbeContractError("pre-data boundary opened")
    auth_expected = {
        "integration_authorized", "paper_authorized", "shadow_authorized",
        "live_authorized", "leverage_authorized", "capital_allocation_authorized",
    }
    if set(contract["authorizations"]) != auth_expected or not all(value is False for value in contract["authorizations"].values()):
        raise ProbeContractError("authorization field/value drift")
    security = contract["security_boundary"]
    if security.get("read_only") is not True or any(value is not False for key, value in security.items() if key != "read_only"):
        raise ProbeContractError("forbidden security capability enabled")
    origins = contract["allowed_origins"]
    if len(origins) != 3 or len(origins) != len(set(origins)):
        raise ProbeContractError("allowed-origin set drift")
    for origin in origins:
        parsed = urllib.parse.urlsplit(origin)
        if parsed.scheme != "https" or not parsed.netloc or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            raise ProbeContractError(f"invalid allowed origin: {origin}")
    fixtures = contract["documentation_fixtures"]
    if fixtures.get("identity_claim_allowed") is not False:
        raise ProbeContractError("identity claim opened")
    for key in ("master", "subaccount", "vault"):
        value = fixtures.get(key)
        if not isinstance(value, str) or len(value) != 42 or not value.startswith("0x"):
            raise ProbeContractError(f"invalid fixture address: {key}")
    probes = contract["probes"]
    if not isinstance(probes, list) or len(probes) != 17:
        raise ProbeContractError("registered probe count drift")
    identifiers = [row.get("id") for row in probes]
    if len(identifiers) != len(set(identifiers)) or not all(isinstance(x, str) and x for x in identifiers):
        raise ProbeContractError("probe identifiers invalid or duplicated")
    expected_shapes = {"json_object", "json_array", "json_array_or_null", "json_object_or_null", "s3_listing_or_error"}
    total_weight = 0
    for row in probes:
        expected_fields = {"id", "method", "origin", "path", "expected", "core", "declared_weight"}
        if row["method"] == "POST":
            expected_fields.add("payload")
        elif row["method"] == "GET":
            expected_fields.add("query")
        else:
            raise ProbeContractError(f"unsupported method for {row['id']}")
        if set(row) != expected_fields:
            raise ProbeContractError(f"probe field drift for {row['id']}")
        if row["origin"] not in origins:
            raise ProbeContractError(f"probe origin outside allowlist: {row['id']}")
        if row["method"] == "POST" and row["path"] != "/info":
            raise ProbeContractError(f"POST route outside /info: {row['id']}")
        if row["method"] == "GET" and row["path"] != "/":
            raise ProbeContractError(f"GET archive route drift: {row['id']}")
        if row["expected"] not in expected_shapes:
            raise ProbeContractError(f"unsupported response class: {row['id']}")
        if not isinstance(row["core"], bool) or not isinstance(row["declared_weight"], int) or row["declared_weight"] < 0:
            raise ProbeContractError(f"probe metadata invalid: {row['id']}")
        total_weight += row["declared_weight"]
    limits = contract["limits"]
    for key in ("timeout_seconds", "maximum_response_bytes", "maximum_total_requests", "maximum_attempts_per_probe", "maximum_declared_request_weight"):
        if not isinstance(limits.get(key), int) or limits[key] <= 0:
            raise ProbeContractError(f"invalid limit: {key}")
    if limits["maximum_total_requests"] < len(probes) * limits["maximum_attempts_per_probe"]:
        raise ProbeContractError("request ceiling below worst registered coverage")
    if total_weight * limits["maximum_attempts_per_probe"] > limits["maximum_declared_request_weight"]:
        raise ProbeContractError("declared retry-weight ceiling exceeded")
    if contract["terminal_rule"]["core_probe_ids"] != [row["id"] for row in probes if row["core"]]:
        raise ProbeContractError("core probe ordering drift")


def resolve_value(value: Any, contract: dict[str, Any]) -> Any:
    fixtures = contract["documentation_fixtures"]
    window = contract["fixed_window"]
    replacements: dict[str, Any] = {
        "$master": fixtures["master"], "$subaccount": fixtures["subaccount"], "$vault": fixtures["vault"],
        "$start_ms": window["start_ms"], "$end_ms": window["end_ms"],
    }
    if isinstance(value, str) and value in replacements:
        return replacements[value]
    if isinstance(value, dict):
        return {key: resolve_value(item, contract) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_value(item, contract) for item in value]
    return value
