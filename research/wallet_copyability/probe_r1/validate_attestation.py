#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from contract import (
    AUTHORIZATION_FIELDS,
    collector_bundle_sha256,
    contract_sha256,
    load_contract,
    sha256,
)
from validate_evidence import (
    EvidenceError,
    load_json,
    require,
    validate_result,
)

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
FINAL_STATUS = {
    "ATTESTED_PUBLIC_PROBE_PASS": "PUBLIC_PROBE_PASS",
    "ATTESTED_PUBLIC_PROBE_PARTIAL": "PUBLIC_PROBE_PARTIAL",
    "ATTESTED_PUBLIC_PROBE_FAIL": "PUBLIC_PROBE_FAIL",
}


def positive_int(value: Any, label: str) -> int:
    require(
        isinstance(value, int)
        and not isinstance(value, bool)
        and value > 0,
        f"{label} must be a positive integer",
    )
    return value


def validate_pending(
    record: dict[str, Any],
    contract: dict[str, Any],
) -> None:
    require(
        record.get("status") == "PENDING_EXACT_WORKFLOW_EVIDENCE",
        "attestation is not pending",
    )
    require(
        record.get("study_id") == contract["study_id"]
        and record.get("probe_id") == contract["probe_id"],
        "pending attestation identity drift",
    )
    for key in (
        "reviewed_commit",
        "workflow_run_id",
        "workflow_run_attempt",
        "workflow_job_id",
        "workflow_conclusion",
        "artifact_id",
        "artifact_name",
        "artifact_digest",
        "artifact_zip_sha256",
        "probe_output_sha256",
        "probe_terminal_status",
        "archive_access_status",
        "probe_pass_count",
        "probe_fail_count",
        "contract_sha256",
        "collector_bundle_sha256",
        "independent_validation_status",
    ):
        require(record.get(key) is None, f"pending attestation invents {key}")
    require(
        record.get("market_data_ingested") is False
        and record.get("empirical_result") is None,
        "pending attestation creates market result",
    )
    require(
        record.get("independent_external_review") is False,
        "pending attestation claims external review",
    )
    require(
        set(record.get("authorizations", {})) == AUTHORIZATION_FIELDS
        and record["authorizations"] == contract["authorizations"]
        and all(value is False for value in record["authorizations"].values()),
        "pending attestation authorization drift",
    )
    require(
        record.get("next_gate")
        == "DO_NOT_OPEN_ARCHIVE_INVENTORY_UNTIL_EXACT_EVIDENCE_AND_REVIEW_PASS",
        "pending next gate opened",
    )


def validate_final(
    record: dict[str, Any],
    evidence: dict[str, Any],
    evidence_bytes: bytes,
    contract: dict[str, Any],
    contract_path: Path,
) -> None:
    status = record.get("status")
    require(status in FINAL_STATUS, "unknown final attestation status")
    expected_terminal = FINAL_STATUS[status]
    validate_result(evidence, contract, contract_path)
    require(record.get("schema_version") == "1.0", "attestation schema drift")
    require(
        record.get("study_id") == contract["study_id"]
        and record.get("probe_id") == contract["probe_id"],
        "attestation identity drift",
    )
    require(
        record.get("workflow_name") == "Hyperliquid Public Probe R1",
        "workflow name drift",
    )
    require(
        isinstance(record.get("reviewed_commit"), str)
        and SHA40.fullmatch(record["reviewed_commit"]) is not None,
        "reviewed commit invalid",
    )
    positive_int(record.get("workflow_run_id"), "workflow_run_id")
    positive_int(record.get("workflow_run_attempt"), "workflow_run_attempt")
    positive_int(record.get("workflow_job_id"), "workflow_job_id")
    positive_int(record.get("artifact_id"), "artifact_id")
    require(
        record.get("workflow_conclusion") in {"success", "failure"},
        "workflow conclusion invalid",
    )
    require(
        isinstance(record.get("artifact_name"), str)
        and record["artifact_name"],
        "artifact name absent",
    )
    require(
        isinstance(record.get("artifact_digest"), str)
        and DIGEST.fullmatch(record["artifact_digest"]) is not None,
        "artifact digest invalid",
    )
    for key in (
        "artifact_zip_sha256",
        "probe_output_sha256",
        "contract_sha256",
        "collector_bundle_sha256",
    ):
        require(
            isinstance(record.get(key), str)
            and SHA256.fullmatch(record[key]) is not None,
            f"{key} invalid",
        )
    require(
        record["probe_output_sha256"] == sha256(evidence_bytes),
        "attested output hash mismatch",
    )
    require(
        record["contract_sha256"] == contract_sha256(contract_path),
        "attested contract hash mismatch",
    )
    require(
        record["collector_bundle_sha256"] == collector_bundle_sha256(),
        "attested collector hash mismatch",
    )
    require(
        record.get("probe_terminal_status")
        == evidence["terminal_status"]
        == expected_terminal,
        "attested terminal status mismatch",
    )
    require(
        record.get("archive_access_status")
        == evidence["archive_access_status"],
        "attested archive status mismatch",
    )
    require(
        record.get("probe_pass_count") == evidence["pass_count"],
        "attested pass count mismatch",
    )
    require(
        record.get("probe_fail_count") == evidence["fail_count"],
        "attested fail count mismatch",
    )
    require(
        record.get("independent_validation_status") == "PASS",
        "independent validation not passed",
    )
    require(
        record.get("market_data_ingested") is False
        and record.get("empirical_result") is None,
        "attestation creates market result",
    )
    require(
        record.get("independent_external_review") is False,
        "attestation falsely claims external review",
    )
    require(
        set(record.get("authorizations", {})) == AUTHORIZATION_FIELDS
        and record["authorizations"] == contract["authorizations"]
        and all(value is False for value in record["authorizations"].values()),
        "attestation authorization drift",
    )
    if expected_terminal == "PUBLIC_PROBE_FAIL":
        require(
            record["workflow_conclusion"] == "failure",
            "failed core probe cannot have successful workflow conclusion",
        )
        require(
            record.get("next_gate")
            == "ARCHIVE_INVENTORY_BLOCKED_REPAIR_AND_RERUN",
            "failed result opens next gate",
        )
    elif expected_terminal == "PUBLIC_PROBE_PARTIAL":
        require(
            record["workflow_conclusion"] == "success",
            "partial non-core result workflow conclusion drift",
        )
        require(
            record.get("next_gate")
            == "ARCHIVE_INVENTORY_BLOCKED_REPAIR_OR_EXPLICIT_SCOPE_DECISION",
            "partial result opens next gate",
        )
    else:
        require(
            record["workflow_conclusion"] == "success",
            "passed probe workflow conclusion drift",
        )
        require(
            record.get("review_status") == "CLEAN_CONTEXT_REVIEW_PASS",
            "passed probe lacks clean-context review",
        )
        require(
            record.get("next_gate")
            == "ARCHIVE_INVENTORY_PROPOSAL_ALLOWED_SEPARATE_REVIEW_REQUIRED",
            "passed probe next gate drift",
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--attestation", type=Path, required=True)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--allow-pending", action="store_true")
    args = parser.parse_args()

    contract = load_contract(args.contract)
    record = load_json(args.attestation)
    if record.get("status") == "PENDING_EXACT_WORKFLOW_EVIDENCE":
        require(args.allow_pending, "pending attestation not allowed")
        validate_pending(record, contract)
        print("PROBE_R1_PENDING_ATTESTATION_VALID")
        return 0
    require(
        args.evidence is not None,
        "final attestation requires exact evidence file",
    )
    evidence_bytes = args.evidence.read_bytes()
    evidence = load_json(args.evidence)
    validate_final(
        record,
        evidence,
        evidence_bytes,
        contract,
        args.contract,
    )
    print(f"PROBE_R1_ATTESTATION_VALID:{record['status']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"PROBE_R1_ATTESTATION_INVALID:{exc}", file=sys.stderr)
        raise SystemExit(2)
