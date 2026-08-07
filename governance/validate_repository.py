#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from regenerate_manifest import render_manifest

ROOT = Path(__file__).resolve().parents[1]
SHA_ROW = re.compile(r"^([0-9a-f]{64})  (.+)$")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"REPOSITORY_VALIDATION_FAIL: {message}")


def main() -> int:
    manifest = ROOT / "governance/REPOSITORY_MANIFEST.sha256"
    observed_manifest = manifest.read_text(encoding="utf-8")
    expected_manifest = render_manifest(ROOT)
    if observed_manifest != expected_manifest:
        print("REPOSITORY_MANIFEST_OUT_OF_DATE")
        print("EXPECTED_MANIFEST_BEGIN")
        print(expected_manifest, end="")
        print("EXPECTED_MANIFEST_END")
        raise SystemExit(
            "REPOSITORY_VALIDATION_FAIL: repository manifest is incomplete, "
            "stale or non-canonical; run "
            "python governance/regenerate_manifest.py --write"
        )

    seen: set[str] = set()
    for line in observed_manifest.splitlines():
        if not line or line.startswith("#"):
            continue
        match = SHA_ROW.fullmatch(line)
        require(match is not None, f"invalid manifest row: {line}")
        expected, rel = match.groups()
        require(rel not in seen, f"duplicate manifest path: {rel}")
        seen.add(rel)
        path = ROOT / rel
        require(path.is_file(), f"missing manifest target: {rel}")
        observed = hashlib.sha256(path.read_bytes()).hexdigest()
        require(observed == expected, f"manifest mismatch: {rel}")

    contract = json.loads(
        (ROOT / "research/wallet_copyability/DATA_CONTRACT.json").read_text()
    )
    require(
        contract["market_data_ingested"] is False,
        "market-data gate opened",
    )
    require(
        contract["empirical_result"] is None,
        "empirical result created",
    )
    require(
        contract["execution_boundary"]["read_only"] is True,
        "read-only gate disabled",
    )
    require(
        all(value is False for value in contract["authorizations"].values()),
        "authorization opened",
    )
    print(f"REPOSITORY_MANIFEST_FILES:{len(seen)}")
    print("REPOSITORY_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
