#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from contract import (
    CONTRACT_PATH,
    canonical_json,
    collector_bundle_sha256,
    contract_sha256,
    load_contract,
    resolve_value,
    sha256,
)
from http_client import classify_body, request_once, should_retry

USER_AGENT = "onchain-wallet-intelligence-lab-read-only-probe/1.1"
ARCHIVE_IDS = (
    "node_fill_archive_listing",
    "market_data_archive_listing",
    "asset_context_archive_listing",
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def make_request(row: dict[str, Any], contract: dict[str, Any]) -> tuple[urllib.request.Request, str]:
    origin = row["origin"]
    if origin not in contract["allowed_origins"]:
        raise RuntimeError(f"unapproved origin: {origin}")
    if row["method"] == "POST":
        payload = resolve_value(row["payload"], contract)
        encoded = canonical_json(payload)
        request = urllib.request.Request(
            origin + row["path"],
            data=encoded,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
        )
        return request, sha256(encoded)
    query = row["query"]
    request = urllib.request.Request(
        origin + row["path"] + ("?" + query if query else ""),
        method="GET",
        headers={
            "Accept": "application/xml,text/xml,*/*",
            "User-Agent": USER_AGENT,
        },
    )
    return request, sha256((row["path"] + "?" + query).encode("utf-8"))


def run_observation(row: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    limits = contract["limits"]
    request, request_sha = make_request(row, contract)
    started_at = utc_now()
    attempts = 0
    record = None
    while attempts < limits["maximum_attempts_per_probe"]:
        attempts += 1
        record = request_once(
            request,
            limits["timeout_seconds"],
            limits["maximum_response_bytes"],
        )
        if not should_retry(record) or attempts >= limits["maximum_attempts_per_probe"]:
            break
        time.sleep(min(2 ** (attempts - 1), 2))
    if record is None:
        raise RuntimeError("probe produced no transport record")
    status, body_summary = classify_body(row["expected"], record)
    parsed = urllib.parse.urlsplit(request.full_url)
    return {
        "probe_id": row["id"],
        "core": row["core"],
        "method": row["method"],
        "request_origin": f"{parsed.scheme}://{parsed.netloc}",
        "request_path": parsed.path,
        "request_sha256": request_sha,
        "declared_weight": row["declared_weight"],
        "attempts": attempts,
        "started_at_utc": started_at,
        "completed_at_utc": utc_now(),
        "http_status": record.http_status,
        "elapsed_ms": record.elapsed_ms,
        "transport_error_class": record.transport_error_class,
        "transport_error_message": record.transport_error_message,
        "expected_shape": row["expected"],
        "status": status,
        **body_summary,
    }


def derive_terminal(observations: list[dict[str, Any]], contract: dict[str, Any]) -> str:
    if [row["probe_id"] for row in observations] != [row["id"] for row in contract["probes"]]:
        return "PUBLIC_PROBE_FAIL"
    if any(row["status"] != "PASS" for row in observations if row["core"]):
        return "PUBLIC_PROBE_FAIL"
    if any(row["status"] != "PASS" for row in observations):
        return "PUBLIC_PROBE_PARTIAL"
    return "PUBLIC_PROBE_PASS"


def derive_archive_access(observations: list[dict[str, Any]]) -> str:
    by_id = {row["probe_id"]: row for row in observations}
    if any(probe_id not in by_id or by_id[probe_id]["status"] != "PASS" for probe_id in ARCHIVE_IDS):
        return "ARCHIVE_ROUTE_FAILURE"
    classes = [by_id[probe_id]["response_class"] for probe_id in ARCHIVE_IDS]
    if all(value == "S3_LISTING" for value in classes):
        return "LISTINGS_AVAILABLE"
    if all(value in {"S3_LISTING", "S3_ERROR_RESPONSE"} for value in classes):
        return "ROUTES_CONFIRMED_ACCESS_RESTRICTED"
    return "ARCHIVE_ROUTE_FAILURE"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    args = parser.parse_args()

    contract = load_contract(args.contract)
    observations = [run_observation(row, contract) for row in contract["probes"]]
    total_attempts = sum(row["attempts"] for row in observations)
    total_weight = sum(row["declared_weight"] * row["attempts"] for row in observations)
    terminal = derive_terminal(observations, contract)
    if (
        total_attempts > contract["limits"]["maximum_total_requests"]
        or total_weight > contract["limits"]["maximum_declared_request_weight"]
    ):
        terminal = "PUBLIC_PROBE_FAIL"

    output = {
        "schema_version": "1.1",
        "study_id": contract["study_id"],
        "probe_id": contract["probe_id"],
        "contract_sha256": contract_sha256(args.contract),
        "collector_bundle_sha256": collector_bundle_sha256(),
        "collected_at_utc": observations[0]["started_at_utc"],
        "completed_at_utc": utc_now(),
        "scope": "READ_ONLY_PUBLIC_SCHEMA_AND_ARCHIVE_ROUTE_BEHAVIOR",
        "terminal_status": terminal,
        "archive_access_status": derive_archive_access(observations),
        "registered_probe_count": len(contract["probes"]),
        "observation_count": len(observations),
        "pass_count": sum(row["status"] == "PASS" for row in observations),
        "fail_count": sum(row["status"] == "FAIL" for row in observations),
        "total_request_attempts": total_attempts,
        "total_declared_request_weight": total_weight,
        "observations": observations,
        "security_assertions": {
            "credentials_used": False,
            "authorization_header_used": False,
            "cookies_used": False,
            "private_keys_used": False,
            "signed_actions_used": False,
            "exchange_action_endpoint_used": False,
            "orders_used": False,
            "withdrawals_used": False,
            "raw_response_values_persisted": False,
        },
        "market_data_ingested": False,
        "empirical_result": None,
        "authorizations": contract["authorizations"],
    }
    encoded = json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    print(f"PROBE_OUTPUT={args.output}")
    print(f"PROBE_OUTPUT_SHA256={sha256(encoded)}")
    print(f"TERMINAL_STATUS={terminal}")
    print(f"ARCHIVE_ACCESS_STATUS={output['archive_access_status']}")
    print(f"PASS_COUNT={output['pass_count']}")
    print(f"FAIL_COUNT={output['fail_count']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"PROBE_FATAL={type(exc).__name__}:{exc}", file=sys.stderr)
        raise
