#!/usr/bin/env python3
from __future__ import annotations

import hashlib
from pathlib import Path

import validate_evidence

ROOT = Path(__file__).resolve().parent


def collector_bundle_sha256() -> str:
    digest = hashlib.sha256()
    for name in ("contract.py", "http_client.py", "probe.py", "validate_evidence.py"):
        data = (ROOT / name).read_bytes()
        digest.update(name.encode() + b"\0" + len(data).to_bytes(8, "big") + data)
    return digest.hexdigest()


def main() -> int:
    validate_evidence.collector_sha256 = collector_bundle_sha256
    return validate_evidence.main()


if __name__ == "__main__":
    raise SystemExit(main())
