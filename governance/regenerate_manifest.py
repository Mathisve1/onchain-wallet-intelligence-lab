#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "governance/REPOSITORY_MANIFEST.sha256"
EXCLUDED_DIRECTORY_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "venv",
}


def included_files(root: Path = ROOT) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if path == MANIFEST:
            continue
        if any(part in EXCLUDED_DIRECTORY_NAMES for part in relative.parts):
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def render_manifest(root: Path = ROOT) -> str:
    rows = []
    for path in included_files(root):
        relative = path.relative_to(root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append(f"{digest}  {relative}")
    return "\n".join(rows) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    expected = render_manifest()
    if args.write:
        MANIFEST.write_text(expected, encoding="utf-8")
        print(f"MANIFEST_WRITTEN:{MANIFEST.relative_to(ROOT).as_posix()}")
        return 0
    if args.check:
        observed = MANIFEST.read_text(encoding="utf-8") if MANIFEST.is_file() else ""
        if observed != expected:
            print("REPOSITORY_MANIFEST_OUT_OF_DATE")
            print("EXPECTED_MANIFEST_BEGIN")
            print(expected, end="")
            print("EXPECTED_MANIFEST_END")
            return 1
        print("REPOSITORY_MANIFEST_COMPLETE")
        return 0
    print(expected, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
