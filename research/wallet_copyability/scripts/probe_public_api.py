#!/usr/bin/env python3
"""Bounded read-only Hyperliquid public technical probe R1.

The probe is intentionally incapable of signing actions, using credentials, or
calling Hyperliquid's exchange/action endpoint. It retains only response hashes,
response structure, aggregate counts and aggregate timestamp bounds. Raw response
values are never written to disk.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import platform
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONTRACT = ROOT / "research/wallet_copyability/PROBE_CONTRACT.json"
DEFAULT_SOURCE_REGISTER = ROOT / "research/wallet_copyability/OFFICIAL_SOURCE_REGISTER.json"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
ADDRESS_RE = re.compile(r"^0x[0-9a-f]{40}$")
SAFE_ERROR_RE = re.compile(r"[^A-Za-z0-9 .,:;_()\[\]/+-]")


class ProbeContractError(RuntimeError):
    """Raised when the frozen probe contract or runtime invocation is invalid."""


class ResponseTooLarge(RuntimeError):
    """Raised when a response exceeds the contract's byte ceiling."""


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject cross-origin redirects and redirects to non-allowlisted origins."""

    def __init__(self, allowed_origins: set[str]) -> None:
        super().__init__()
        self.allowed_origins = allowed_origins

    def redirect_request(  # type: ignore[override]
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        old_origin = origin_of(req.full_url)
        new_origin = origin_of(newurl)
        if old_origin != new_origin or new_origin not in self.allowed_origins:
            raise urllib.error.URLError(
                f"redirect blocked: {old_origin} -> {new_origin}"
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProbeContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(token: str) -> Any:
    raise ProbeContractError(f"non-finite JSON constant: {token}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=strict_pairs,
            parse_constant=reject_constant,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProbeContractError(f"invalid JSON {path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ProbeContractError(f"JSON root must be an object: {path}")
    return parsed


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def origin_of(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme.lower() != "https" or not parts.netloc:
        raise ProbeContractError(f"non-HTTPS or malformed URL: {url}")
    host = parts.hostname.lower() if parts.hostname else ""
    port = parts.port
    default_port = port in (None, 443)
    return f"https://{host}" if default_port else f"https://{host}:{port}"


def sanitize_error(value: str | None) -> str | None:
    if value is None:
        return None
    compact = " ".join(value.replace("\r", " ").replace("\n", " ").split())
    return SAFE_ERROR_RE.sub("?", compact)[:240]


def json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def schema_paths(
    value: Any,
    *,
    maximum_depth: int,
    maximum_paths: int,
) -> list[str]:
    paths: set[str] = set()

    def visit(node: Any, path: str, depth: int) -> None:
        if len(paths) >= maximum_paths:
            return
        paths.add(f"{path}:{json_type(node)}")
        if depth >= maximum_depth:
            return
        if isinstance(node, dict):
            for key in sorted(node):
                visit(node[key], f"{path}.{key}", depth + 1)
                if len(paths) >= maximum_paths:
                    break
        elif isinstance(node, list):
            observed_types: set[str] = set()
            for item in node[:20]:
                item_type = json_type(item)
                if item_type in observed_types:
                    continue
                observed_types.add(item_type)
                visit(item, f"{path}[]", depth + 1)
                if len(paths) >= maximum_paths:
                    break

    visit(value, "$", 0)
    return sorted(paths)


def json_shape(
    value: Any,
    *,
    maximum_depth: int,
    maximum_paths: int,
) -> dict[str, Any]:
    top_level_keys: list[str] = []
    sample_item_keys: list[str] = []
    sample_item_types: list[str] = []
    if isinstance(value, dict):
        top_level_keys = sorted(str(key) for key in value)
        element_count: int | None = len(value)
    elif isinstance(value, list):
        element_count = len(value)
        sample_item_types = sorted({json_type(item) for item in value[:100]})
        for item in value[:20]:
            if isinstance(item, dict):
                sample_item_keys = sorted(str(key) for key in item)
                break
    else:
        element_count = 1
    paths = schema_paths(
        value,
        maximum_depth=maximum_depth,
        maximum_paths=maximum_paths,
    )
    return {
        "top_level_type": json_type(value),
        "top_level_keys": top_level_keys,
        "element_count": element_count,
        "sample_item_types": sample_item_types,
        "sample_item_keys": sample_item_keys,
        "schema_paths": paths,
        "schema_fingerprint_sha256": sha256_bytes(canonical_bytes(paths)),
    }


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def xml_shape(body: bytes) -> tuple[dict[str, Any], ET.Element | None, str | None]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        return (
            {
                "top_level_type": "xml",
                "top_level_keys": [],
                "element_count": None,
                "sample_item_types": [],
                "sample_item_keys": [],
                "schema_paths": [],
                "schema_fingerprint_sha256": sha256_bytes(b"[]"),
                "xml_root": None,
                "xml_child_tags": [],
                "xml_key_count": None,
                "xml_is_truncated": None,
                "xml_contents_count": None,
                "xml_error_code": None,
                "xml_sample_key_sha256": [],
            },
            None,
            sanitize_error(str(exc)),
        )

    child_tags = sorted({local_name(child.tag) for child in list(root)})
    paths: set[str] = {f"$:{local_name(root.tag)}"}
    for child in list(root)[:200]:
        paths.add(f"$.{local_name(child.tag)}")
        for grandchild in list(child)[:50]:
            paths.add(
                f"$.{local_name(child.tag)}.{local_name(grandchild.tag)}"
            )
    sorted_paths = sorted(paths)
    values_by_tag: dict[str, list[str]] = {}
    for element in root.iter():
        name = local_name(element.tag)
        text = (element.text or "").strip()
        if text:
            values_by_tag.setdefault(name, []).append(text)

    key_values = values_by_tag.get("Key", [])[:5]
    key_count_text = next(iter(values_by_tag.get("KeyCount", [])), None)
    truncated_text = next(iter(values_by_tag.get("IsTruncated", [])), None)
    error_code = next(iter(values_by_tag.get("Code", [])), None)
    return (
        {
            "top_level_type": "xml",
            "top_level_keys": child_tags,
            "element_count": len(list(root)),
            "sample_item_types": ["xml_element"],
            "sample_item_keys": child_tags,
            "schema_paths": sorted_paths,
            "schema_fingerprint_sha256": sha256_bytes(
                canonical_bytes(sorted_paths)
            ),
            "xml_root": local_name(root.tag),
            "xml_child_tags": child_tags,
            "xml_key_count": int(key_count_text) if key_count_text and key_count_text.isdigit() else None,
            "xml_is_truncated": (
                truncated_text.lower() == "true"
                if isinstance(truncated_text, str)
                and truncated_text.lower() in {"true", "false"}
                else None
            ),
            "xml_contents_count": sum(
                1 for element in root.iter() if local_name(element.tag) == "Contents"
            ),
            "xml_error_code": error_code,
            "xml_sample_key_sha256": [
                sha256_bytes(value.encode("utf-8")) for value in key_values
            ],
        },
        root,
        None,
    )


def integer_times(rows: Iterable[Any]) -> list[int]:
    values: list[int] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw = row.get("time")
        if isinstance(raw, int) and raw >= 0:
            values.append(raw)
    return values


def event_array_details(value: Any) -> dict[str, Any]:
    if not isinstance(value, list):
        return {
            "event_count": None,
            "time_field_count": 0,
            "minimum_event_time_ms": None,
            "maximum_event_time_ms": None,
        }
    times = integer_times(value)
    return {
        "event_count": len(value),
        "time_field_count": len(times),
        "minimum_event_time_ms": min(times) if times else None,
        "maximum_event_time_ms": max(times) if times else None,
    }


def specialized_assertion(
    probe: dict[str, Any],
    value: Any,
    *,
    http_status: int | None,
    xml_summary: dict[str, Any] | None,
    addresses: dict[str, str],
) -> tuple[str, str, dict[str, Any]]:
    assertion = probe["assertion"]
    expected_type = probe["expected_top_level"]
    actual_type = "xml" if xml_summary is not None else json_type(value)
    details: dict[str, Any] = {
        "assertion": assertion,
        "expected_top_level": expected_type,
        "actual_top_level": actual_type,
    }

    if assertion == "S3_LISTING_OR_ACCESS_CONTROL":
        if xml_summary is None:
            return "FAIL", "XML summary absent", details
        details.update(
            {
                "xml_root": xml_summary["xml_root"],
                "xml_key_count": xml_summary["xml_key_count"],
                "xml_contents_count": xml_summary["xml_contents_count"],
                "xml_is_truncated": xml_summary["xml_is_truncated"],
                "xml_error_code": xml_summary["xml_error_code"],
            }
        )
        if http_status is not None and 200 <= http_status < 300:
            if xml_summary["xml_root"] == "ListBucketResult":
                return "PASS", "S3 listing returned", details
            return "FAIL", "unexpected successful S3 XML root", details
        if http_status == 403 and xml_summary["xml_root"] == "Error":
            error_code = xml_summary["xml_error_code"]
            if error_code in {"AccessDenied", "InvalidRequest"}:
                return (
                    "DEGRADED",
                    "archive reachable but anonymous listing is access controlled",
                    details,
                )
        return "FAIL", "unexpected archive response", details

    if actual_type != expected_type:
        return "FAIL", "top-level response type mismatch", details
    if not probe.get("allow_empty", False):
        if value in ({}, [], None, ""):
            return "FAIL", "empty response forbidden", details

    if assertion == "META_CONTAINS_UNIVERSE":
        universe = value.get("universe") if isinstance(value, dict) else None
        names = {
            row.get("name")
            for row in universe
            if isinstance(row, dict) and isinstance(row.get("name"), str)
        } if isinstance(universe, list) else set()
        details["universe_is_array"] = isinstance(universe, list)
        details["universe_count"] = len(universe) if isinstance(universe, list) else None
        details["required_instruments_present"] = {
            coin: coin in names for coin in ("BTC", "ETH", "SOL")
        }
        passed = isinstance(universe, list) and bool(universe)
        return ("PASS", "universe present", details) if passed else ("FAIL", "universe absent", details)

    if assertion == "ALL_MIDS_REQUIRED_INSTRUMENTS_PRESENT":
        required = probe["required_instruments"]
        present = {
            coin: isinstance(value, dict) and coin in value for coin in required
        }
        details["required_instruments_present"] = present
        return (
            ("PASS", "required instruments present", details)
            if all(present.values())
            else ("FAIL", "required instruments missing", details)
        )

    if assertion == "ROLE_EQUALS":
        actual_role = value.get("role") if isinstance(value, dict) else None
        details["actual_role"] = actual_role
        details["expected_role"] = probe["expected_role"]
        return (
            ("PASS", "role matched", details)
            if actual_role == probe["expected_role"]
            else ("FAIL", "role mismatch", details)
        )

    if assertion == "SUBACCOUNT_RELATION_PRESENT":
        relation_present = False
        relation_count = 0
        if isinstance(value, list):
            for row in value:
                if not isinstance(row, dict):
                    continue
                if (
                    str(row.get("subAccountUser", "")).lower()
                    == addresses["subaccount"]
                    and str(row.get("master", "")).lower()
                    == addresses["master"]
                ):
                    relation_present = True
                    relation_count += 1
        details["relation_present"] = relation_present
        details["matching_relation_count"] = relation_count
        details["reported_subaccount_count"] = len(value) if isinstance(value, list) else None
        return (
            ("PASS", "documented subaccount relation present", details)
            if relation_present
            else ("FAIL", "documented subaccount relation absent", details)
        )

    if assertion == "SUBACCOUNT_ROLE_AND_MASTER":
        role = value.get("role") if isinstance(value, dict) else None
        data = value.get("data") if isinstance(value, dict) else None
        master = data.get("master") if isinstance(data, dict) else None
        role_match = role == probe["expected_role"]
        master_match = (
            isinstance(master, str) and master.lower() == addresses["master"]
        )
        details.update(
            {
                "actual_role": role,
                "role_match": role_match,
                "master_match": master_match,
            }
        )
        return (
            ("PASS", "subaccount role and master matched", details)
            if role_match and master_match
            else ("FAIL", "subaccount role or master mismatch", details)
        )

    if assertion == "CLEARINGHOUSE_STATE_FIELDS":
        required = ("marginSummary", "crossMarginSummary", "assetPositions", "time")
        present = {key: isinstance(value, dict) and key in value for key in required}
        details["required_fields_present"] = present
        details["asset_position_count"] = (
            len(value["assetPositions"])
            if isinstance(value, dict) and isinstance(value.get("assetPositions"), list)
            else None
        )
        return (
            ("PASS", "clearinghouse state fields present", details)
            if all(present.values())
            else ("FAIL", "clearinghouse state fields missing", details)
        )

    if assertion == "USER_FEES_FIELDS":
        required = ("feeSchedule", "userCrossRate", "userAddRate")
        present = {key: isinstance(value, dict) and key in value for key in required}
        details["required_fields_present"] = present
        schedule = value.get("feeSchedule") if isinstance(value, dict) else None
        details["fee_schedule_keys"] = sorted(schedule) if isinstance(schedule, dict) else []
        return (
            ("PASS", "user fee fields present", details)
            if all(present.values())
            else ("FAIL", "user fee fields missing", details)
        )

    if assertion == "EVENT_ARRAY_TIME_BOUNDS":
        details.update(event_array_details(value))
        return "PASS", "event array response valid", details

    if assertion == "ACTIVE_FILL_LIMIT_DIAGNOSTIC":
        diagnostics = event_array_details(value)
        count = diagnostics["event_count"] or 0
        if count >= 2000:
            limit_observation = "AT_LEAST_2000_RESPONSE_CAP_OBSERVED"
            outcome = "PASS"
            reason = "active response reached at least 2000 records"
        elif count > 500:
            limit_observation = "MORE_THAN_500_RECORDS_OBSERVED"
            outcome = "PASS"
            reason = "active response disproves a universal 500-record ceiling"
        elif count == 500:
            limit_observation = "EXACTLY_500_RECORDS_INCONCLUSIVE"
            outcome = "DEGRADED"
            reason = "response may be capped at 500 or naturally equal 500"
        else:
            limit_observation = "INSUFFICIENT_ACTIVITY_TO_RESOLVE_LIMIT"
            outcome = "DEGRADED"
            reason = "active response count did not resolve the documentation conflict"
        diagnostics["limit_observation"] = limit_observation
        details.update(diagnostics)
        return outcome, reason, details

    if assertion == "VAULT_DETAILS_ADDRESS":
        address = value.get("vaultAddress") if isinstance(value, dict) else None
        relation = value.get("relationship") if isinstance(value, dict) else None
        address_match = (
            isinstance(address, str) and address.lower() == addresses["vault"]
        )
        details["vault_address_match"] = address_match
        details["relationship_type"] = (
            relation.get("type") if isinstance(relation, dict) else None
        )
        return (
            ("PASS", "vault address matched", details)
            if address_match
            else ("FAIL", "vault address mismatch", details)
        )

    if assertion == "L2_BOOK_FIELDS_NO_VALUES_RETAINED":
        required = ("coin", "levels", "time")
        present = {key: isinstance(value, dict) and key in value for key in required}
        coin_match = isinstance(value, dict) and value.get("coin") == "BTC"
        levels = value.get("levels") if isinstance(value, dict) else None
        side_counts = [len(side) for side in levels] if isinstance(levels, list) and all(isinstance(side, list) for side in levels) else []
        details.update(
            {
                "required_fields_present": present,
                "coin_match": coin_match,
                "book_side_count": len(levels) if isinstance(levels, list) else None,
                "level_counts_by_side": side_counts,
                "price_or_size_values_retained": False,
            }
        )
        passed = all(present.values()) and coin_match and isinstance(levels, list) and len(levels) == 2
        return (
            ("PASS", "L2 book structure valid", details)
            if passed
            else ("FAIL", "L2 book structure invalid", details)
        )

    return "FAIL", f"unknown assertion: {assertion}", details


def replace_tokens(value: Any, replacements: dict[str, Any]) -> Any:
    if isinstance(value, str) and value in replacements:
        return replacements[value]
    if isinstance(value, dict):
        return {key: replace_tokens(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_tokens(item, replacements) for item in value]
    return value


def validate_contract(contract: dict[str, Any]) -> None:
    required_top = {
        "schema_version",
        "contract_id",
        "study_id",
        "probe_id",
        "status",
        "network_policy",
        "data_minimization",
        "execution_boundary",
        "documentation_examples",
        "time_windows",
        "terminal_logic",
        "probes",
        "authorizations",
        "market_data_ingested",
        "empirical_result",
    }
    missing = required_top - set(contract)
    if missing:
        raise ProbeContractError(f"contract missing fields: {sorted(missing)}")
    if contract["schema_version"] != "1.0":
        raise ProbeContractError("unsupported contract schema")
    if contract["status"] != "FROZEN_PRE_EXECUTION":
        raise ProbeContractError("contract is not frozen pre-execution")
    if contract["market_data_ingested"] is not False or contract["empirical_result"] is not None:
        raise ProbeContractError("contract market/result boundary opened")
    if any(value is not False for value in contract["authorizations"].values()):
        raise ProbeContractError("contract authorization opened")
    boundary = contract["execution_boundary"]
    if boundary.get("read_only") is not True:
        raise ProbeContractError("probe must be read-only")
    for key, value in boundary.items():
        if key != "read_only" and value is not False:
            raise ProbeContractError(f"execution capability enabled: {key}")

    policy = contract["network_policy"]
    origins = policy["allowed_origins"]
    if not isinstance(origins, list) or not origins:
        raise ProbeContractError("allowed origin set absent")
    normalized_origins = [origin_of(origin) for origin in origins]
    if len(set(normalized_origins)) != len(normalized_origins):
        raise ProbeContractError("duplicate allowed origin")
    if policy["cross_origin_redirects_allowed"] is not False:
        raise ProbeContractError("cross-origin redirects must be forbidden")
    if policy["maximum_request_count"] != len(contract["probes"]):
        raise ProbeContractError("request count does not match registered probes")
    total_weight = sum(int(probe["base_weight"]) for probe in contract["probes"])
    if total_weight > int(policy["maximum_declared_base_weight"]):
        raise ProbeContractError("declared base weight exceeds ceiling")

    examples = contract["documentation_examples"]
    for key in ("master_address", "subaccount_address", "vault_address"):
        address = examples[key]
        if not isinstance(address, str) or not ADDRESS_RE.fullmatch(address):
            raise ProbeContractError(f"invalid documented address: {key}")

    probe_ids: set[str] = set()
    for probe in contract["probes"]:
        probe_id = probe.get("probe_id")
        if not isinstance(probe_id, str) or probe_id in probe_ids:
            raise ProbeContractError(f"duplicate or invalid probe id: {probe_id}")
        probe_ids.add(probe_id)
        if probe["method"] not in policy["allowed_methods"]:
            raise ProbeContractError(f"forbidden method: {probe_id}")
        if origin_of(probe["origin"]) not in normalized_origins:
            raise ProbeContractError(f"forbidden origin: {probe_id}")
        path = probe["path"]
        if not isinstance(path, str) or not path.startswith("/"):
            raise ProbeContractError(f"invalid path: {probe_id}")
        if "/exchange" in path.lower():
            raise ProbeContractError(f"exchange endpoint forbidden: {probe_id}")
        if probe["method"] == "POST" and probe["origin"] == "https://api.hyperliquid.xyz" and path != policy["info_path"]:
            raise ProbeContractError(f"non-info Hyperliquid path: {probe_id}")


def read_limited(response: Any, maximum_bytes: int) -> bytes:
    body = response.read(maximum_bytes + 1)
    if len(body) > maximum_bytes:
        raise ResponseTooLarge(f"response exceeds {maximum_bytes} bytes")
    return body


def selected_headers(headers: Any, allowed: set[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    if headers is None:
        return result
    for key, value in headers.items():
        lowered = key.lower()
        if lowered in allowed:
            result[lowered] = str(value)[:500]
    return dict(sorted(result.items()))


def execute_request(
    opener: urllib.request.OpenerDirector,
    request: urllib.request.Request,
    *,
    maximum_bytes: int,
    maximum_attempts: int,
    retryable_statuses: set[int],
    backoff_seconds: list[float],
    header_allowlist: set[str],
) -> dict[str, Any]:
    started = time.monotonic()
    final_status: int | None = None
    final_body = b""
    final_headers: dict[str, str] = {}
    error_class: str | None = None
    error_message: str | None = None
    attempts = 0

    for attempt in range(1, maximum_attempts + 1):
        attempts = attempt
        try:
            with opener.open(request, timeout=request.timeout if hasattr(request, "timeout") else None) as response:
                final_status = int(response.status)
                final_headers = selected_headers(response.headers, header_allowlist)
                final_body = read_limited(response, maximum_bytes)
            error_class = None
            error_message = None
        except urllib.error.HTTPError as exc:
            final_status = int(exc.code)
            final_headers = selected_headers(exc.headers, header_allowlist)
            try:
                final_body = read_limited(exc, maximum_bytes)
            except ResponseTooLarge as too_large:
                final_body = b""
                error_class = type(too_large).__name__
                error_message = str(too_large)
                break
            error_class = type(exc).__name__
            error_message = str(exc.reason)
        except Exception as exc:  # transport failures must be recorded, not hidden
            final_status = None
            final_body = b""
            final_headers = {}
            error_class = type(exc).__name__
            error_message = str(exc)

        retryable = (
            final_status in retryable_statuses
            if final_status is not None
            else error_class in {"URLError", "TimeoutError", "ConnectionError"}
        )
        if not retryable or attempt >= maximum_attempts:
            break
        delay = backoff_seconds[min(attempt - 1, len(backoff_seconds) - 1)]
        time.sleep(delay)

    return {
        "attempt_count": attempts,
        "http_status": final_status,
        "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
        "body": final_body,
        "headers": final_headers,
        "error_class": error_class,
        "error_message": sanitize_error(error_message),
    }


def build_request(
    probe: dict[str, Any],
    *,
    user_agent: str,
) -> tuple[urllib.request.Request, str, str, str | None]:
    url = probe["origin"] + probe["path"]
    method = probe["method"]
    request_type: str | None = None
    if method == "POST":
        payload = probe["resolved_payload"]
        data = canonical_bytes(payload)
        request_type = payload.get("type") if isinstance(payload, dict) else None
        request = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": user_agent,
            },
        )
        request_hash = sha256_bytes(
            canonical_bytes({"method": method, "url": url, "payload": payload})
        )
    else:
        request = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Accept": "application/xml,text/xml,*/*",
                "User-Agent": user_agent,
            },
        )
        request_hash = sha256_bytes(
            canonical_bytes({"method": method, "url": url})
        )
    return request, url, request_hash, request_type


def run_probe(
    contract: dict[str, Any],
    *,
    contract_path: Path,
    source_register_path: Path,
    reviewed_commit: str,
    workflow_run_id: int,
    workflow_run_attempt: int,
    workflow_job_name: str,
    repository: str,
    ref: str,
    anchor_time_ms: int | None,
) -> dict[str, Any]:
    validate_contract(contract)
    if not SHA40_RE.fullmatch(reviewed_commit):
        raise ProbeContractError("reviewed commit must be a full lowercase SHA-1")
    if workflow_run_id < 1 or workflow_run_attempt < 1:
        raise ProbeContractError("workflow run identity must be positive")
    if not workflow_job_name or not repository or not ref:
        raise ProbeContractError("workflow identity fields must be non-empty")

    policy = contract["network_policy"]
    allowed_origins = {origin_of(origin) for origin in policy["allowed_origins"]}
    opener = urllib.request.build_opener(SafeRedirectHandler(allowed_origins))
    header_allowlist = set(contract["data_minimization"]["selected_response_headers"])

    now_ms = int(time.time() * 1000) if anchor_time_ms is None else anchor_time_ms
    rounding = int(contract["time_windows"]["anchor_rounding_ms"])
    anchor_end_ms = now_ms - (now_ms % rounding)
    anchor_start_ms = anchor_end_ms - int(contract["time_windows"]["active_vault_lookback_ms"])
    examples = contract["documentation_examples"]
    addresses = {
        "master": examples["master_address"].lower(),
        "subaccount": examples["subaccount_address"].lower(),
        "vault": examples["vault_address"].lower(),
    }
    replacements: dict[str, Any] = {
        "$MASTER": addresses["master"],
        "$SUBACCOUNT": addresses["subaccount"],
        "$VAULT": addresses["vault"],
        "$FIXED_START_MS": int(contract["time_windows"]["fixed_start_ms"]),
        "$FIXED_END_MS": int(contract["time_windows"]["fixed_end_ms"]),
        "$ANCHOR_START_MS": anchor_start_ms,
        "$ANCHOR_END_MS": anchor_end_ms,
    }

    observations: list[dict[str, Any]] = []
    for index, registered_probe in enumerate(contract["probes"]):
        probe = dict(registered_probe)
        probe["resolved_payload"] = replace_tokens(
            registered_probe.get("payload"), replacements
        )
        request, url, request_hash, request_type = build_request(
            probe,
            user_agent=policy["user_agent"],
        )
        request.timeout = int(policy["timeout_seconds"])  # type: ignore[attr-defined]
        response = execute_request(
            opener,
            request,
            maximum_bytes=int(policy["maximum_response_bytes"]),
            maximum_attempts=int(policy["maximum_attempts"]),
            retryable_statuses=set(policy["retryable_http_statuses"]),
            backoff_seconds=[float(value) for value in policy["retry_backoff_seconds"]],
            header_allowlist=header_allowlist,
        )
        body = response.pop("body")
        parser = probe["parser"]
        parse_status = "NOT_ATTEMPTED"
        parsed_value: Any = None
        shape_summary: dict[str, Any]
        xml_summary: dict[str, Any] | None = None
        parse_error: str | None = None
        if body:
            if parser == "JSON":
                try:
                    parsed_value = json.loads(
                        body,
                        object_pairs_hook=strict_pairs,
                        parse_constant=reject_constant,
                    )
                except (json.JSONDecodeError, UnicodeDecodeError, ProbeContractError) as exc:
                    parse_status = "INVALID_JSON"
                    parse_error = sanitize_error(str(exc))
                    shape_summary = {
                        "top_level_type": "unknown",
                        "top_level_keys": [],
                        "element_count": None,
                        "sample_item_types": [],
                        "sample_item_keys": [],
                        "schema_paths": [],
                        "schema_fingerprint_sha256": sha256_bytes(b"[]"),
                    }
                else:
                    parse_status = "VALID_JSON"
                    shape_summary = json_shape(
                        parsed_value,
                        maximum_depth=int(contract["data_minimization"]["maximum_schema_depth"]),
                        maximum_paths=int(contract["data_minimization"]["maximum_schema_paths"]),
                    )
            elif parser == "XML":
                shape_summary, _, parse_error = xml_shape(body)
                xml_summary = shape_summary
                parse_status = "VALID_XML" if parse_error is None else "INVALID_XML"
            else:
                raise ProbeContractError(f"unsupported parser: {parser}")
        else:
            shape_summary = {
                "top_level_type": "empty",
                "top_level_keys": [],
                "element_count": 0,
                "sample_item_types": [],
                "sample_item_keys": [],
                "schema_paths": [],
                "schema_fingerprint_sha256": sha256_bytes(b"[]"),
            }
            parse_status = "EMPTY_BODY"

        if parser == "JSON" and parse_status != "VALID_JSON":
            assertion_status, assertion_reason, assertion_details = (
                "FAIL",
                "JSON response did not parse",
                {"assertion": probe["assertion"]},
            )
        elif parser == "XML" and parse_status != "VALID_XML":
            assertion_status, assertion_reason, assertion_details = (
                "FAIL",
                "XML response did not parse",
                {"assertion": probe["assertion"]},
            )
        else:
            assertion_status, assertion_reason, assertion_details = specialized_assertion(
                probe,
                parsed_value,
                http_status=response["http_status"],
                xml_summary=xml_summary,
                addresses=addresses,
            )

        if response["error_class"] == "ResponseTooLarge":
            outcome = "FAIL"
            outcome_reason = "response exceeded byte ceiling"
        elif parser == "JSON" and not (
            response["http_status"] is not None
            and 200 <= response["http_status"] < 300
        ):
            outcome = "FAIL"
            outcome_reason = "JSON endpoint did not return HTTP 2xx"
        else:
            outcome = assertion_status
            outcome_reason = assertion_reason

        parsed_url = urllib.parse.urlsplit(url)
        observation = {
            "probe_id": probe["probe_id"],
            "sequence": index + 1,
            "required": bool(probe["required"]),
            "failure_impact": probe.get("failure_impact", "FAIL"),
            "method": probe["method"],
            "request_origin": origin_of(url),
            "request_path": parsed_url.path + (f"?{parsed_url.query}" if parsed_url.query else ""),
            "request_type": request_type,
            "request_sha256": request_hash,
            "declared_base_weight": int(probe["base_weight"]),
            "attempt_count": int(response["attempt_count"]),
            "http_status": response["http_status"],
            "elapsed_ms": response["elapsed_ms"],
            "body_length": len(body),
            "body_sha256": sha256_bytes(body),
            "selected_headers": response["headers"],
            "parser": parser,
            "parse_status": parse_status,
            "parse_error": parse_error,
            **shape_summary,
            "assertion_status": assertion_status,
            "assertion_reason": assertion_reason,
            "assertion_details": assertion_details,
            "outcome": outcome,
            "outcome_reason": outcome_reason,
            "transport_error_class": response["error_class"],
            "transport_error_message": response["error_message"],
            "raw_response_bytes_retained": False,
            "response_values_retained": False,
        }
        observations.append(observation)
        if index + 1 < len(contract["probes"]):
            time.sleep(int(policy["inter_request_delay_ms"]) / 1000)

    required_failures = [
        item["probe_id"]
        for item in observations
        if item["required"] and item["outcome"] == "FAIL"
    ]
    degraded_probes = [
        item["probe_id"] for item in observations if item["outcome"] == "DEGRADED"
    ]
    optional_failures = [
        item["probe_id"]
        for item in observations
        if not item["required"] and item["outcome"] == "FAIL"
    ]
    if required_failures:
        terminal_status = "PUBLIC_PROBE_FAIL"
    elif degraded_probes or optional_failures:
        terminal_status = "PUBLIC_PROBE_PARTIAL"
    else:
        terminal_status = "PUBLIC_PROBE_PASS"

    limit_probe = next(
        item
        for item in observations
        if item["probe_id"] == "P014_VAULT_FILLS_BY_TIME_RECENT_24H"
    )
    documentation_limit_observation = limit_probe["assertion_details"].get(
        "limit_observation"
    )
    output = {
        "schema_version": "1.0",
        "study_id": contract["study_id"],
        "probe_id": contract["probe_id"],
        "contract_id": contract["contract_id"],
        "scope": "READ_ONLY_PUBLIC_SCHEMA_RELATIONSHIP_LIMIT_AND_ARCHIVE_AVAILABILITY_PROBE",
        "collected_at_utc": utc_now(),
        "anchor_time_ms": anchor_end_ms,
        "reviewed_commit": reviewed_commit,
        "workflow": {
            "repository": repository,
            "run_id": workflow_run_id,
            "run_attempt": workflow_run_attempt,
            "job_name": workflow_job_name,
            "ref": ref,
        },
        "environment": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform_system": platform.system(),
            "platform_machine": platform.machine(),
        },
        "input_hashes": {
            "contract_sha256": sha256_file(contract_path),
            "source_register_sha256": sha256_file(source_register_path),
            "script_sha256": sha256_file(Path(__file__)),
        },
        "network_projection": {
            "allowed_origins": sorted(allowed_origins),
            "request_count": len(observations),
            "declared_base_weight": sum(
                item["declared_base_weight"] for item in observations
            ),
            "cross_origin_redirects_allowed": False,
            "maximum_response_bytes": int(policy["maximum_response_bytes"]),
        },
        "observations": observations,
        "derived": {
            "terminal_status": terminal_status,
            "pass_count": sum(item["outcome"] == "PASS" for item in observations),
            "degraded_count": sum(item["outcome"] == "DEGRADED" for item in observations),
            "fail_count": sum(item["outcome"] == "FAIL" for item in observations),
            "required_failures": required_failures,
            "degraded_probes": degraded_probes,
            "optional_failures": optional_failures,
            "documentation_limit_observation": documentation_limit_observation,
        },
        "controls": {
            "credentials_used": False,
            "authorization_headers_used": False,
            "environment_secrets_used": False,
            "signed_actions_used": False,
            "exchange_action_endpoint_used": False,
            "orders_used": False,
            "withdrawals_used": False,
            "raw_response_bytes_retained": False,
            "response_values_retained": False,
        },
        "market_data_ingested": False,
        "empirical_result": None,
        "authorizations": dict(contract["authorizations"]),
    }
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument(
        "--source-register", type=Path, default=DEFAULT_SOURCE_REGISTER
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reviewed-commit", required=True)
    parser.add_argument("--workflow-run-id", type=int, required=True)
    parser.add_argument("--workflow-run-attempt", type=int, required=True)
    parser.add_argument("--workflow-job-name", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--anchor-time-ms", type=int)
    args = parser.parse_args()

    contract_path = args.contract.resolve()
    source_register_path = args.source_register.resolve()
    contract = load_json(contract_path)
    output = run_probe(
        contract,
        contract_path=contract_path,
        source_register_path=source_register_path,
        reviewed_commit=args.reviewed_commit,
        workflow_run_id=args.workflow_run_id,
        workflow_run_attempt=args.workflow_run_attempt,
        workflow_job_name=args.workflow_job_name,
        repository=args.repository,
        ref=args.ref,
        anchor_time_ms=args.anchor_time_ms,
    )
    encoded = json.dumps(
        output,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8") + b"\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    output_sha = sha256_bytes(encoded)
    print(f"PROBE_OUTPUT={args.output}")
    print(f"PROBE_OUTPUT_SHA256={output_sha}")
    print(f"PROBE_TERMINAL_STATUS={output['derived']['terminal_status']}")
    print(f"PROBE_PASS_COUNT={output['derived']['pass_count']}")
    print(f"PROBE_DEGRADED_COUNT={output['derived']['degraded_count']}")
    print(f"PROBE_FAIL_COUNT={output['derived']['fail_count']}")
    return 2 if output["derived"]["terminal_status"] == "PUBLIC_PROBE_FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
