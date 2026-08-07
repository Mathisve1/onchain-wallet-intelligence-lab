#!/usr/bin/env python3
from __future__ import annotations

import base64
import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

from regenerate_manifest import render_manifest

ROOT = Path(__file__).resolve().parents[1]
SHA_ROW = re.compile(r"^([0-9a-f]{64})  (.+)$")
PROBE_ROOT = ROOT / "research/wallet_copyability/probe_r1"
EVIDENCE_ROOT = PROBE_ROOT / "evidence"
FINAL_ATTESTATION = EVIDENCE_ROOT / "HL-PUBLIC-PROBE-001R1-ATTESTATION.json"
CANONICAL_RUN_ID = 31200124642
CANONICAL_JOB_ID = 92937868268
CANONICAL_ARTIFACT_ID = 9002459643
CANONICAL_REVIEWED_COMMIT = "c11046bf288687c6945fe9b8f17141204d24aae6"
CANONICAL_RUN_ROOT = EVIDENCE_ROOT / f"run-{CANONICAL_RUN_ID}"
REQUIRED_PROBE_PATHS = {
    ".github/workflows/hyperliquid-public-probe-r1.yml",
    "research/wallet_copyability/probe_r1/ATTESTATION_TEMPLATE.json",
    "research/wallet_copyability/probe_r1/PENDING_EVIDENCE.json",
    "research/wallet_copyability/probe_r1/PROBE_CONTRACT.json",
    "research/wallet_copyability/probe_r1/contract.py",
    "research/wallet_copyability/probe_r1/http_client.py",
    "research/wallet_copyability/probe_r1/probe.py",
    "research/wallet_copyability/probe_r1/validate_attestation.py",
    "research/wallet_copyability/probe_r1/validate_attestation_strict.py",
    "research/wallet_copyability/probe_r1/validate_evidence.py",
}

sys.path.insert(0, str(PROBE_ROOT))
import contract as probe_contract  # noqa: E402
import validate_attestation  # noqa: E402
import validate_attestation_strict  # noqa: E402
import validate_evidence  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"REPOSITORY_VALIDATION_FAIL: {message}")


def load_json(relative: str | Path) -> dict:
    path = relative if isinstance(relative, Path) else ROOT / relative
    value = validate_evidence.load_json(path)
    require(isinstance(value, dict), f"JSON root not object: {path}")
    return value


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_manifest() -> int:
    manifest = ROOT / "governance/REPOSITORY_MANIFEST.sha256"
    observed_manifest = manifest.read_text(encoding="utf-8")
    expected_manifest = render_manifest(ROOT)
    if observed_manifest != expected_manifest:
        print("EXPECTED_MANIFEST_BEGIN")
        print(expected_manifest, end="")
        print("EXPECTED_MANIFEST_END")
        require(False, "repository manifest is incomplete or stale")

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
        require(sha256(path.read_bytes()) == expected, f"manifest mismatch: {rel}")
    return len(seen)


def validate_parent_contract() -> None:
    contract = load_json("research/wallet_copyability/DATA_CONTRACT.json")
    require(contract["market_data_ingested"] is False, "market-data gate opened")
    require(contract["empirical_result"] is None, "empirical result created")
    require(contract["execution_boundary"]["read_only"] is True, "read-only gate disabled")
    require(
        all(value is False for value in contract["authorizations"].values()),
        "authorization opened",
    )


def validate_common_probe_contract() -> dict:
    for relative in REQUIRED_PROBE_PATHS:
        require((ROOT / relative).is_file(), f"missing probe path: {relative}")
    require(not (ROOT / "research/archive_inventory").exists(), "archive inventory opened")

    contract = probe_contract.load_contract(PROBE_ROOT / "PROBE_CONTRACT.json")
    require(contract["status"] == "FROZEN_READ_ONLY_PUBLIC_PROBE", "probe contract status drift")
    require(
        contract["market_data_ingested"] is False and contract["empirical_result"] is None,
        "probe contract creates market result",
    )
    require(
        all(value is False for value in contract["authorizations"].values()),
        "probe contract opens authorization",
    )

    pending = load_json(PROBE_ROOT / "PENDING_EVIDENCE.json")
    validate_evidence.validate_pending(pending, contract)
    template = load_json(PROBE_ROOT / "ATTESTATION_TEMPLATE.json")
    validate_attestation_strict.validate_field_set(template)
    validate_attestation.validate_pending(template, contract)
    return contract


def validate_encoded_output() -> tuple[bytes, dict]:
    meta = load_json(CANONICAL_RUN_ROOT / "EVIDENCE_ENCODING.json")
    encoded_path = CANONICAL_RUN_ROOT / meta["encoded_file"]
    require(encoded_path.is_file(), "encoded canonical probe output missing")
    encoded = encoded_path.read_bytes()
    require(len(encoded) == meta["encoded_size_in_bytes"], "encoded output size mismatch")
    require(sha256(encoded) == meta["encoded_sha256"], "encoded output hash mismatch")
    try:
        compressed = base64.b64decode(encoded.strip(), validate=True)
    except Exception as exc:
        raise SystemExit(f"REPOSITORY_VALIDATION_FAIL: invalid base64 evidence: {exc}") from exc
    require(len(compressed) == meta["gzip_size_in_bytes"], "gzip size mismatch")
    require(sha256(compressed) == meta["gzip_sha256"], "gzip hash mismatch")
    try:
        raw = gzip.decompress(compressed)
    except Exception as exc:
        raise SystemExit(f"REPOSITORY_VALIDATION_FAIL: invalid gzip evidence: {exc}") from exc
    require(len(raw) == meta["raw_size_in_bytes"], "raw output size mismatch")
    require(sha256(raw) == meta["raw_sha256"], "raw output hash mismatch")
    value = json.loads(
        raw,
        object_pairs_hook=validate_evidence.strict_object,
        parse_constant=lambda token: (_ for _ in ()).throw(
            validate_evidence.EvidenceError(f"non-finite retained evidence value: {token}")
        ),
    )
    require(isinstance(value, dict), "decoded canonical output is not object")
    return raw, value


def validate_artifact_ledger(raw_output: bytes) -> None:
    mapping = {
        "hl-public-probe-r1.json": raw_output,
        "probe-run-context.json": (CANONICAL_RUN_ROOT / "probe-run-context.json").read_bytes(),
        "probe-validation.log": (CANONICAL_RUN_ROOT / "probe-validation.log").read_bytes(),
        "probe-validation.rc": (CANONICAL_RUN_ROOT / "probe-validation.rc").read_bytes(),
    }
    observed: set[str] = set()
    for line in (CANONICAL_RUN_ROOT / "ARTIFACT_FILES.sha256").read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        expected, original = line.split("  ", 1)
        name = Path(original).name
        require(name in mapping, f"unexpected artifact-ledger file: {name}")
        require(name not in observed, f"duplicate artifact-ledger file: {name}")
        require(sha256(mapping[name]) == expected, f"artifact-ledger hash mismatch: {name}")
        observed.add(name)
    require(observed == set(mapping), "artifact ledger incomplete")


def validate_final_evidence(contract: dict) -> None:
    required = {
        "EVIDENCE_ENCODING.json",
        "hl-public-probe-r1.json.gz.b64",
        "probe-run-context.json",
        "probe-validation.log",
        "probe-validation.rc",
        "ARTIFACT_FILES.sha256",
        "INDEPENDENT_ARTIFACT_VERIFICATION.json",
    }
    require(CANONICAL_RUN_ROOT.is_dir(), "canonical run directory missing")
    require({p.name for p in CANONICAL_RUN_ROOT.iterdir() if p.is_file()} == required, "canonical run file set drift")
    require(len(list(EVIDENCE_ROOT.glob("run-*"))) == 1, "unexpected additional run directory")

    raw, evidence = validate_encoded_output()
    validate_evidence.validate_result(evidence, contract, PROBE_ROOT / "PROBE_CONTRACT.json")
    validate_artifact_ledger(raw)

    context = load_json(CANONICAL_RUN_ROOT / "probe-run-context.json")
    require(context["dispatch_ref"] == "refs/heads/main", "canonical dispatch ref drift")
    for key in ("dispatch_sha", "reviewed_commit", "checked_out_commit"):
        require(context[key] == CANONICAL_REVIEWED_COMMIT, f"canonical context identity drift: {key}")
    require(context["workflow_run_id"] == CANONICAL_RUN_ID, "run context ID drift")
    require(context["workflow_run_attempt"] == 1, "run attempt drift")
    require(context["validation_return_code"] == 0, "canonical validation return code nonzero")
    require(context["output_sha256"] == sha256(raw), "context output hash mismatch")

    attestation = load_json(FINAL_ATTESTATION)
    validate_attestation_strict.validate_field_set(attestation)
    validate_attestation.validate_final(
        attestation,
        evidence,
        raw,
        contract,
        PROBE_ROOT / "PROBE_CONTRACT.json",
    )
    require(attestation["reviewed_commit"] == CANONICAL_REVIEWED_COMMIT, "attested reviewed commit drift")
    require(attestation["workflow_run_id"] == CANONICAL_RUN_ID, "attested run ID drift")
    require(attestation["workflow_job_id"] == CANONICAL_JOB_ID, "attested job ID drift")
    require(attestation["artifact_id"] == CANONICAL_ARTIFACT_ID, "attested artifact ID drift")

    verification = load_json(CANONICAL_RUN_ROOT / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
    require(verification["validation"]["all_checks_pass"] is True, "independent verification not passed")
    require(verification["validation"]["artifact_zip_hash_match"] is True, "artifact ZIP hash not independently matched")
    require(verification["validation"]["internal_ledger_matches"] is True, "artifact ledger not independently matched")
    require(verification["validation"]["run_context_identity_match"] is True, "run context identity not independently matched")
    require(verification["reviewed_commit"] == CANONICAL_REVIEWED_COMMIT, "verification commit drift")
    require(verification["workflow_run_id"] == CANONICAL_RUN_ID, "verification run drift")
    require(verification["workflow_job_id"] == CANONICAL_JOB_ID, "verification job drift")
    require(verification["artifact"]["artifact_id"] == CANONICAL_ARTIFACT_ID, "verification artifact drift")
    require(
        verification["artifact"]["provider_digest"]
        == "sha256:" + verification["artifact"]["downloaded_zip_sha256"],
        "provider/downloaded artifact digest mismatch",
    )

    project_state = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
    require("`PRE_ARCHIVE_INVENTORY`" in project_state, "project state not promoted to pre-archive inventory")
    require(
        "`PUBLIC_TECHNICAL_PROBE_ATTESTED_ARCHIVE_ACCESS_RESTRICTED`" in project_state,
        "project state technical result missing",
    )
    require("market_data_ingested = false" in project_state, "project state market-data boundary missing")


def validate_implementation_only(contract: dict) -> None:
    require(not FINAL_ATTESTATION.exists(), "premature final attestation exists")
    require(not any(EVIDENCE_ROOT.glob("run-*")), "premature workflow run directory exists")
    project_state = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
    require("`PRE_DATA`" in project_state, "implementation-only state left PRE_DATA")
    require("`PREREGISTERED_NO_MARKET_RELEASE`" in project_state, "implementation-only experiment status promoted")


def main() -> int:
    manifest_files = validate_manifest()
    validate_parent_contract()
    contract = validate_common_probe_contract()
    if FINAL_ATTESTATION.exists():
        validate_final_evidence(contract)
        phase = "ATTESTED_CANONICAL_PUBLIC_PROBE"
    else:
        validate_implementation_only(contract)
        phase = "IMPLEMENTATION_ONLY"
    print(f"REPOSITORY_MANIFEST_FILES:{manifest_files}")
    print(f"REPOSITORY_PHASE:{phase}")
    print("REPOSITORY_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
