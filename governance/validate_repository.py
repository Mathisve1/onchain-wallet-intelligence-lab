#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHA_ROW = re.compile(r"^([0-9a-f]{64})  (.+)$")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"REPOSITORY_VALIDATION_FAIL: {message}")


def main() -> int:
    manifest = ROOT / "governance/REPOSITORY_MANIFEST.sha256"
    seen: set[str] = set()
    for line in manifest.read_text().splitlines():
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

    contract = json.loads((ROOT / "research/wallet_copyability/DATA_CONTRACT.json").read_text())
    require(contract["market_data_ingested"] is False, "market-data gate opened")
    require(contract["empirical_result"] is None, "empirical result created")
    require(contract["execution_boundary"]["read_only"] is True, "read-only gate disabled")
    require(all(value is False for value in contract["authorizations"].values()), "authorization opened")
    print("REPOSITORY_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
