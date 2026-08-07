#!/usr/bin/env python3
"""Bounded read-only public Hyperliquid schema and availability probe."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

INFO_ENDPOINT = "https://api.hyperliquid.xyz/info"
DOCUMENTED_USER = "0x0000000000000000000000000000000000000000"
TIMEOUT_SECONDS = 20

POST_PROBES: tuple[tuple[str, dict[str, Any]], ...] = (
    ("meta", {"type": "meta"}),
    ("user_role", {"type": "userRole", "user": DOCUMENTED_USER}),
    ("subaccounts", {"type": "subAccounts", "user": DOCUMENTED_USER}),
    ("account_state", {"type": "clearinghouseState", "user": DOCUMENTED_USER}),
)

GET_PROBES: tuple[tuple[str, str], ...] = (
    (
        "node_fill_archive_listing",
        "https://hl-mainnet-node-data.s3.amazonaws.com/"
        "?list-type=2&prefix=node_fills_by_block/&max-keys=5",
    ),
    (
        "market_data_archive_listing",
        "https://hyperliquid-archive.s3.amazonaws.com/"
        "?list-type=2&prefix=market_data/&max-keys=5",
    ),
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def shape(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {"type": "object", "keys": sorted(value), "count": len(value)}
    if isinstance(value, list):
        keys = sorted(value[0]) if value and isinstance(value[0], dict) else []
        return {"type": "array", "keys": keys, "count": len(value)}
    return {"type": type(value).__name__, "keys": [], "count": 1}


def request_summary(probe_id: str, request: urllib.request.Request, *, json_expected: bool) -> dict[str, Any]:
    started = time.monotonic()
    status = None
    body = b""
    error = None
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            status = int(response.status)
            body = response.read()
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        body = exc.read()
        error = f"HTTPError:{exc.reason}"
    except Exception as exc:
        error = f"{type(exc).__name__}:{str(exc)[:200]}"

    result: dict[str, Any] = {
        "probe_id": probe_id,
        "http_status": status,
        "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
        "body_length": len(body),
        "body_sha256": sha256(body),
        "error": error,
        "status": "PASS" if status is not None and 200 <= status < 300 else "FAIL",
    }
    if json_expected and body:
        try:
            result.update(shape(json.loads(body)))
            result["json_status"] = "VALID_JSON"
        except json.JSONDecodeError:
            result["json_status"] = "INVALID_JSON"
    return result


def post_probe(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    request = urllib.request.Request(
        INFO_ENDPOINT,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "wallet-intelligence-read-only-probe/1.0"},
    )
    result = request_summary(name, request, json_expected=True)
    result["request_type"] = payload["type"]
    result["request_sha256"] = sha256(data)
    return result


def get_probe(name: str, url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "wallet-intelligence-read-only-probe/1.0"})
    result = request_summary(name, request, json_expected=False)
    parsed = urllib.parse.urlsplit(url)
    result["request_origin"] = f"{parsed.scheme}://{parsed.netloc}"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    observations = [post_probe(name, payload) for name, payload in POST_PROBES]
    observations.extend(get_probe(name, url) for name, url in GET_PROBES)
    output = {
        "schema_version": "1.0",
        "study_id": "WALLET-COPYABILITY-STUDY-001",
        "probe_id": "HL-PUBLIC-PROBE-001",
        "collected_at_utc": utc_now(),
        "scope": "READ_ONLY_PUBLIC_SCHEMA_AND_AVAILABILITY_PROBE",
        "observations": observations,
        "pass_count": sum(row["status"] == "PASS" for row in observations),
        "fail_count": sum(row["status"] == "FAIL" for row in observations),
        "market_data_ingested": False,
        "empirical_result": None,
        "signed_actions_used": False,
        "orders_used": False,
        "credentials_used": False,
    }
    encoded = (json.dumps(output, indent=2, sort_keys=True) + "\n").encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    print(f"PROBE_SHA256={sha256(encoded)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
