#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

from validate_probe_evidence import ValidationError, validate_repository_probe

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_REL = "governance/REPOSITORY_MANIFEST.sha256"
SHA_ROW = re.compile(r"^([0-9a-f]{64})  ([^\s].*)$")
PINNED_ACTION = re.compile(r"^\s*-?\s*uses:\s*[^@\s]+@[0-9a-f]{40}\s*$")
SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
EXPECTED_ACTIONS = {
    "actions/checkout": "11d5960a326750d5838078e36cf38b85af677262",
    "actions/setup-python": "a26af69be951a213d495a4c3e4e4022e16d87065",
    "actions/upload-artifact": "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"REPOSITORY_VALIDATION_FAIL: {message}")


def git_ls_files() -> set[str]:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    return {line for line in result.stdout.splitlines() if line}


def validate_manifest() -> None:
    manifest = ROOT / MANIFEST_REL
    seen: set[str] = set()
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        match = SHA_ROW.fullmatch(line)
        require(match is not None, f"invalid manifest row: {line}")
        expected, rel = match.groups()
        path = Path(rel)
        require(not path.is_absolute() and ".." not in path.parts, f"unsafe manifest path: {rel}")
        require(rel != MANIFEST_REL, "manifest cannot hash itself")
        require(rel not in seen, f"duplicate manifest path: {rel}")
        seen.add(rel)
        full = ROOT / rel
        require(full.is_file(), f"missing manifest target: {rel}")
        observed = hashlib.sha256(full.read_bytes()).hexdigest()
        require(observed == expected, f"manifest mismatch: {rel}")

    tracked = git_ls_files()
    expected_coverage = tracked - {MANIFEST_REL}
    require(seen == expected_coverage, f"manifest coverage drift: {sorted(seen ^ expected_coverage)}")


def validate_workflows() -> None:
    observed_actions: set[str] = set()
    for workflow in sorted((ROOT / ".github/workflows").glob("*.y*ml")):
        text = workflow.read_text(encoding="utf-8")
        require("permissions:\n  contents: read" in text, f"workflow lacks read-only contents permission: {workflow.name}")
        for number, line in enumerate(text.splitlines(), 1):
            if "uses:" not in line:
                continue
            require(PINNED_ACTION.fullmatch(line) is not None, f"unpinned action {workflow}:{number}: {line.strip()}")
            reference = line.split("uses:", 1)[1].strip()
            action, sha = reference.rsplit("@", 1)
            require(action in EXPECTED_ACTIONS, f"unexpected action identity: {action}")
            require(sha == EXPECTED_ACTIONS[action], f"unapproved action SHA for {action}")
            observed_actions.add(action)
    require("actions/checkout" in observed_actions, "checkout action absent")
    require("actions/setup-python" in observed_actions, "setup-python action absent")
    require("actions/upload-artifact" in observed_actions, "probe artifact action absent")


def validate_secret_hygiene() -> None:
    for rel in sorted(git_ls_files()):
        path = ROOT / rel
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in SECRET_PATTERNS:
            require(pattern.search(text) is None, f"secret-like token in {rel}")
    require(not (ROOT / ".env").exists(), "tracked or local root .env forbidden")


def validate_data_boundary() -> None:
    contract = json.loads(
        (ROOT / "research/wallet_copyability/DATA_CONTRACT.json").read_text(encoding="utf-8")
    )
    require(contract["market_data_ingested"] is False, "market-data gate opened")
    require(contract["empirical_result"] is None, "empirical result created")
    require(contract["execution_boundary"]["read_only"] is True, "read-only gate disabled")
    require(all(value is False for value in contract["authorizations"].values()), "authorization opened")
    probe = contract["technical_probe"]
    evidence = json.loads(
        (ROOT / "research/wallet_copyability/TECHNICAL_PROBE_EVIDENCE.json").read_text(encoding="utf-8")
    )
    require(probe["status"] == evidence["status"], "data-contract/evidence probe status drift")
    require(probe["status"] in {"PENDING_PUBLIC_PROBE", "PUBLIC_PROBE_PASS", "PUBLIC_PROBE_PARTIAL", "PUBLIC_PROBE_FAIL"}, "technical probe status invalid")
    require(probe["raw_response_bytes_retained"] is False, "raw probe bytes retained")
    require(probe["response_values_retained"] is False, "probe values retained")
    require(probe["analytical_market_partition_opened"] is False, "analytical partition opened")


def main() -> int:
    try:
        validate_manifest()
        validate_workflows()
        validate_secret_hygiene()
        validate_data_boundary()
        validate_repository_probe()
    except (ValidationError, subprocess.CalledProcessError) as exc:
        print(f"REPOSITORY_VALIDATION_FAIL: {exc}")
        return 1
    print("REPOSITORY_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
