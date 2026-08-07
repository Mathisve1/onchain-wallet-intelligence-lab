#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import validate_attestation
from contract import AUTHORIZATION_FIELDS, load_contract
from validate_evidence import EvidenceError, load_json, require

ATTESTATION_FIELDS = {
    "schema_version",
    "attestation_id",
    "study_id",
    "probe_id",
    "status",
    "reviewed_commit",
    "workflow_name",
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
    "review_status",
    "independent_external_review",
    "market_data_ingested",
    "empirical_result",
    "authorizations",
    "next_gate",
}


def validate_field_set(record: dict) -> None:
    require(
        set(record) == ATTESTATION_FIELDS,
        f"attestation field drift: {sorted(set(record) ^ ATTESTATION_FIELDS)}",
    )
    require(
        set(record.get("authorizations", {})) == AUTHORIZATION_FIELDS,
        "attestation authorization field drift",
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
    validate_field_set(record)
    if record.get("status") == "PENDING_EXACT_WORKFLOW_EVIDENCE":
        require(args.allow_pending, "pending attestation not allowed")
        validate_attestation.validate_pending(record, contract)
        print("PROBE_R1_STRICT_PENDING_ATTESTATION_VALID")
        return 0
    require(
        args.evidence is not None,
        "final attestation requires exact evidence file",
    )
    evidence_bytes = args.evidence.read_bytes()
    evidence = load_json(args.evidence)
    validate_attestation.validate_final(
        record,
        evidence,
        evidence_bytes,
        contract,
        args.contract,
    )
    print(f"PROBE_R1_STRICT_ATTESTATION_VALID:{record['status']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"PROBE_R1_STRICT_ATTESTATION_INVALID:{exc}", file=sys.stderr)
        raise SystemExit(2)
