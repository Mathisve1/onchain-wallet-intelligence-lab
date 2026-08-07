#!/usr/bin/env python3
"""Regenerate or verify the repository-wide SHA-256 manifest."""
from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "governance/REPOSITORY_MANIFEST.sha256"
EXCLUDED = {"governance/REPOSITORY_MANIFEST.sha256"}


def tracked_paths() -> list[str]:
    output = subprocess.check_output(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
    )
    paths = [item.decode("utf-8") for item in output.split(b"\0") if item]
    return sorted(path for path in paths if path not in EXCLUDED)


def render() -> str:
    rows: list[str] = []
    for relative in tracked_paths():
        path = ROOT / relative
        if not path.is_file():
            raise SystemExit(f"MANIFEST_REGEN_FAIL: tracked path is not a file: {relative}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append(f"{digest}  {relative}")
    return "\n".join(rows) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render()
    if args.check:
        observed = MANIFEST.read_text(encoding="utf-8") if MANIFEST.exists() else ""
        if observed != expected:
            print("MANIFEST_CHECK_FAIL")
            return 1
        print("MANIFEST_CHECK_PASS")
        return 0
    MANIFEST.write_text(expected, encoding="utf-8")
    print(f"MANIFEST_REGENERATED_ROWS={len(tracked_paths())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
