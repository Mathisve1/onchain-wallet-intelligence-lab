from __future__ import annotations

import hashlib
import json
import urllib.parse
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
CONTRACT_PATH = ROOT / "PROBE_CONTRACT.json"
COLLECTOR_FILES = (
    "contract.py",
    "http_client.py",
    "probe.py",
    "validate_evidence.py",
)
AUTHORIZATION_FIELDS = {
    "integration_authorized",
    "paper_authorized",
    "shadow_authorized",
    "live_authorized",
    "leverage_authorized",
    "capital_allocation_authorized",
}


class ProbeContractError(ValueError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProbeContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonfinite(token: str) -> Any:
    raise ProbeContractError(f"non-finite JSON constant: {token}")


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_object,
            parse_constant=_reject_nonfinite,
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
        digest.update(
            name.encode("utf-8")
            + b"\0"
            + len(data).to_bytes(8, "big")
            + data
        )
    return digest.hexdigest()


def _positive_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ProbeContractError(f"{label} must be a positive integer")
    return value


def validate_contract(contract: dict[str, Any]) -> None:
    required_top = {
        "schema_version",
        "study_id",
        "probe_id",
        "status",
        "purpose",
        "venue",
        "allowed_origins",
        "documentation_fixtures",
        "fixed_window",
        "capacity_contract",
        "limits",
        "security_boundary",
        "terminal_rule",
        "probes",
        "authorizations",
        "market_data_ingested",
        "empirical_result",
    }
    if set(contract) != required_top:
        raise ProbeContractError(
            f"contract top-level field drift: {sorted(set(contract) ^ required_top)}"
        )
    if contract["schema_version"] != "1.2":
        raise ProbeContractError("contract schema drift")
    if (
        contract["study_id"] != "WALLET-COPYABILITY-STUDY-001"
        or contract["probe_id"] != "HL-PUBLIC-PROBE-001R1"
    ):
        raise ProbeContractError("probe identity drift")
    if contract["status"] != "FROZEN_READ_ONLY_PUBLIC_PROBE":
        raise ProbeContractError("probe status drift")
    if (
        contract["market_data_ingested"] is not False
        or contract["empirical_result"] is not None
    ):
        raise ProbeContractError("pre-data boundary opened")
    if set(contract["authorizations"]) != AUTHORIZATION_FIELDS or not all(
        value is False for value in contract["authorizations"].values()
    ):
        raise ProbeContractError("authorization field/value drift")

    security = contract["security_boundary"]
    expected_security = {
        "read_only",
        "credentials_allowed",
        "authorization_header_allowed",
        "cookies_allowed",
        "private_keys_allowed",
        "signed_actions_allowed",
        "exchange_action_endpoint_allowed",
        "orders_allowed",
        "withdrawals_allowed",
        "repository_write_permission_allowed",
    }
    if set(security) != expected_security:
        raise ProbeContractError("security boundary field drift")
    if security["read_only"] is not True or any(
        value is not False
        for key, value in security.items()
        if key != "read_only"
    ):
        raise ProbeContractError("forbidden security capability enabled")

    origins = contract["allowed_origins"]
    if (
        not isinstance(origins, list)
        or len(origins) != 3
        or len(origins) != len(set(origins))
    ):
        raise ProbeContractError("allowed-origin set drift")
    for origin in origins:
        parsed = urllib.parse.urlsplit(origin)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise ProbeContractError(f"invalid allowed origin: {origin}")

    fixtures = contract["documentation_fixtures"]
    if set(fixtures) != {
        "master",
        "subaccount",
        "vault",
        "identity_claim_allowed",
    }:
        raise ProbeContractError("fixture field drift")
    if fixtures["identity_claim_allowed"] is not False:
        raise ProbeContractError("identity claim opened")
    for key in ("master", "subaccount", "vault"):
        value = fixtures[key]
        if (
            not isinstance(value, str)
            or len(value) != 42
            or not value.startswith("0x")
            or any(char not in "0123456789abcdef" for char in value[2:])
        ):
            raise ProbeContractError(f"invalid fixture address: {key}")

    window = contract["fixed_window"]
    if set(window) != {"start_ms", "end_ms", "label"}:
        raise ProbeContractError("fixed-window field drift")
    if not isinstance(window["start_ms"], int) or not isinstance(
        window["end_ms"], int
    ):
        raise ProbeContractError("window timestamps must be integers")
    if window["end_ms"] - window["start_ms"] != 86_400_000:
        raise ProbeContractError("fixed window must be exactly one UTC day")

    probes = contract["probes"]
    if not isinstance(probes, list) or len(probes) != 16:
        raise ProbeContractError("registered probe count drift")
    identifiers = [row.get("id") for row in probes]
    if len(identifiers) != len(set(identifiers)) or not all(
        isinstance(value, str) and value for value in identifiers
    ):
        raise ProbeContractError("probe identifiers invalid or duplicated")

    expected_shapes = {
        "json_object",
        "json_array",
        "json_array_or_null",
        "json_object_or_null",
        "s3_listing_or_error",
    }
    total_weight = 0
    for row in probes:
        fields = {
            "id",
            "method",
            "origin",
            "path",
            "expected",
            "core",
            "declared_weight",
            "weight_basis",
        }
        if row.get("method") == "POST":
            fields.add("payload")
        elif row.get("method") == "GET":
            fields.add("query")
        else:
            raise ProbeContractError(
                f"unsupported method for {row.get('id')}"
            )
        if set(row) != fields:
            raise ProbeContractError(f"probe field drift for {row['id']}")
        if row["origin"] not in origins:
            raise ProbeContractError(
                f"probe origin outside allowlist: {row['id']}"
            )
        if row["method"] == "POST" and row["path"] != "/info":
            raise ProbeContractError(f"POST route outside /info: {row['id']}")
        if row["method"] == "GET" and row["path"] != "/":
            raise ProbeContractError(f"archive route path drift: {row['id']}")
        if row["expected"] not in expected_shapes:
            raise ProbeContractError(
                f"unsupported response class: {row['id']}"
            )
        if not isinstance(row["core"], bool):
            raise ProbeContractError(f"core flag invalid: {row['id']}")
        if (
            not isinstance(row["declared_weight"], int)
            or isinstance(row["declared_weight"], bool)
            or row["declared_weight"] < 0
        ):
            raise ProbeContractError(
                f"declared weight invalid: {row['id']}"
            )
        if not isinstance(row["weight_basis"], str) or not row["weight_basis"]:
            raise ProbeContractError(f"weight basis absent: {row['id']}")
        total_weight += row["declared_weight"]

    if any(
        row["id"] == "vault_recent_fills"
        or row.get("payload", {}).get("type") == "userFills"
        for row in probes
    ):
        raise ProbeContractError("unbounded userFills request is forbidden")

    capacity = contract["capacity_contract"]
    capacity_fields = {
        "published_ip_budget_per_minute",
        "base_declared_weight",
        "maximum_attempts_multiplier",
        "worst_case_declared_weight",
        "safety_margin_to_published_budget",
        "response_rich_endpoints_use_conservative_weight",
        "unbounded_user_fills_request_allowed",
    }
    if set(capacity) != capacity_fields:
        raise ProbeContractError("capacity-contract field drift")
    published = _positive_int(
        capacity["published_ip_budget_per_minute"],
        "published budget",
    )
    multiplier = _positive_int(
        capacity["maximum_attempts_multiplier"],
        "attempt multiplier",
    )
    if capacity["base_declared_weight"] != total_weight or total_weight != 586:
        raise ProbeContractError("base declared weight drift")
    if capacity["worst_case_declared_weight"] != total_weight * multiplier:
        raise ProbeContractError("worst-case declared weight drift")
    if capacity["worst_case_declared_weight"] != 1172:
        raise ProbeContractError("frozen worst-case weight drift")
    if capacity["safety_margin_to_published_budget"] != published - 1172:
        raise ProbeContractError("capacity safety margin drift")
    if capacity["response_rich_endpoints_use_conservative_weight"] is not True:
        raise ProbeContractError("response-rich weight control disabled")
    if capacity["unbounded_user_fills_request_allowed"] is not False:
        raise ProbeContractError("unbounded user fills opened")
    if 1172 >= published:
        raise ProbeContractError("worst-case weight does not stay below budget")

    limits = contract["limits"]
    required_limits = {
        "timeout_seconds",
        "maximum_response_bytes",
        "maximum_total_requests",
        "maximum_attempts_per_probe",
        "maximum_declared_request_weight",
        "redirect_policy",
        "raw_response_values_persisted",
    }
    if set(limits) != required_limits:
        raise ProbeContractError("limit field drift")
    for key in (
        "timeout_seconds",
        "maximum_response_bytes",
        "maximum_total_requests",
        "maximum_attempts_per_probe",
        "maximum_declared_request_weight",
    ):
        _positive_int(limits[key], key)
    if limits["redirect_policy"] != "SAME_ORIGIN_ONLY":
        raise ProbeContractError("redirect policy drift")
    if limits["raw_response_values_persisted"] is not False:
        raise ProbeContractError("raw response persistence opened")
    if limits["maximum_attempts_per_probe"] != multiplier:
        raise ProbeContractError("attempt multiplier/limit parity drift")
    if limits["maximum_total_requests"] < len(probes) * multiplier:
        raise ProbeContractError(
            "request ceiling below worst registered coverage"
        )
    if not (1172 <= limits["maximum_declared_request_weight"] < published):
        raise ProbeContractError("declared-weight ceiling is not fail-closed")

    core_ids = [row["id"] for row in probes if row["core"]]
    if contract["terminal_rule"]["core_probe_ids"] != core_ids:
        raise ProbeContractError("core probe ordering drift")


def resolve_value(value: Any, contract: dict[str, Any]) -> Any:
    fixtures = contract["documentation_fixtures"]
    window = contract["fixed_window"]
    replacements: dict[str, Any] = {
        "$master": fixtures["master"],
        "$subaccount": fixtures["subaccount"],
        "$vault": fixtures["vault"],
        "$start_ms": window["start_ms"],
        "$end_ms": window["end_ms"],
    }
    if isinstance(value, str) and value in replacements:
        return replacements[value]
    if isinstance(value, dict):
        return {
            key: resolve_value(item, contract)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [resolve_value(item, contract) for item in value]
    return value
