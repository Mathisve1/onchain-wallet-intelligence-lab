from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r4/role_attestation"
RUN = BASE / "evidence/run-31312067367"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    context = load(RUN / "r4-role-preflight-context.json")
    result = load(RUN / "r4-role-preflight-result.json")
    verification = load(RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
    attestation = load(BASE / "HL-ARCHIVE-R4-DEDICATED-ROLE-STS-PREFLIGHT-001-ATTESTATION.json")
    consumption = load(BASE / "R4_ROLE_STS_PREFLIGHT_RELEASE_CONSUMPTION.json")
    release = load(BASE / "R4_ROLE_STS_PREFLIGHT_RELEASE.json")

    assert context["workflow_run_id"] == 31312067367
    assert context["workflow_run_attempt"] == 1
    assert context["dispatch_sha"] == "700aa435b6db2513877ef94f499cf44dddb16471"
    assert context["dispatch_ref"] == "refs/heads/main"
    assert context["configure_aws_outcome"] == "success"
    assert context["s3_http_request_count"] == 0
    assert context["body_release_consumed_by_preflight"] is False

    assert result["terminal_status"] == "R4_ROLE_STS_PREFLIGHT_PASS"
    assert result["technical_result"] == "DEDICATED_R4_ROLE_ASSUMEABLE_FROM_CANONICAL_MAIN"
    assert result["account_id"] == "630956766927"
    assert result["explicit_sts_caller_identity_calls"] == 1
    assert result["s3_http_request_count"] == 0
    assert result["object_bytes_downloaded"] == 0
    assert result["requester_pays_requested"] is False
    assert result["decompression_performed"] is False
    assert result["body_release_consumed_by_preflight"] is False
    assert result["body_execution_activation_authorized"] is False

    ledger_lines = (RUN / "R4_ROLE_PREFLIGHT_FILES.sha256").read_text(encoding="utf-8").splitlines()
    observed = {}
    for line in ledger_lines:
        digest, name = line.split("  ", 1)
        observed[name] = digest
    for name in ("r4-role-preflight-context.json", "r4-role-preflight-result.json", "r4-role-preflight.rc"):
        assert hashlib.sha256((RUN / name).read_bytes()).hexdigest() == observed[name]
        assert verification["internal_ledger"][name] == observed[name]
    assert (RUN / "r4-role-preflight.rc").read_text(encoding="utf-8") == "0\n"

    assert verification["provider_sha256"] == "6d30969525156ad3354c4a9abdb5d661cfc1b7b2d1a6cfd07eb02f4300f20376"
    assert verification["independently_downloaded_zip_sha256"] == verification["provider_sha256"]
    assert verification["provider_digest_matches_independent_download"] is True
    assert verification["verification_result"] == "ALL_CHECKS_PASS"

    assert attestation["operator_attestation_independently_verified_by_preflight"] is True
    assert attestation["preflight_release_consumed"] is True
    assert attestation["rerun_authorized"] is False
    assert attestation["body_execution_activation_authorized_by_this_attestation"] is False

    assert consumption["status"] == "CONSUMED_SUCCESS"
    assert consumption["preflight_release_consumed"] is True
    assert consumption["rerun_authorized"] is False
    assert consumption["s3_requests_executed"] == 0
    assert consumption["body_release_consumed_by_preflight"] is False
    assert consumption["body_execution_activation_authorized_by_this_file"] is False

    assert release["rerun_authorized"] is False
    assert release["s3_requests_authorized"] is False
    print("R4_ROLE_STS_PREFLIGHT_EVIDENCE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
