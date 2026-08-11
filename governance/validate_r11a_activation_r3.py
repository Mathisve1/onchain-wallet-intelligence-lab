#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone

from r11a_stage_common import RUNTIME_DIR, load, require, require_commit, require_sha256, sha256
from validate_r11a_execution_release_r3 import RELEASE, RELEASE_DIGEST, main as validate_release

ACTIVATION = RUNTIME_DIR / "R11A_CANONICAL_ACTIVATION.json"


def main() -> int:
    validate_release()
    activation = load(ACTIVATION)
    require(activation["activation_id"] == "ACTIVATE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001", "activation ID drift")
    require(activation["status"] == "ACTIVATED_FOR_EXACTLY_ONE_CANONICAL_R11A_RUN", "activation status drift")
    require(activation["execution_release_id"] == "RELEASE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001", "activation release ID drift")
    require_sha256(activation["execution_release_blob_sha256"], "execution_release_blob_sha256")
    require(activation["execution_release_blob_sha256"] == sha256(RELEASE), "activation release blob binding drift")
    require(activation["execution_release_blob_sha256"] == RELEASE_DIGEST.read_text(encoding="ascii").strip(), "activation detached release binding drift")
    require_commit(activation["activation_base_commit"], "activation_base_commit")
    require_commit(activation["canonical_activation_merge_commit"], "canonical_activation_merge_commit")
    require(activation["single_workflow_dispatch_authorized"] is True, "activation does not authorize one dispatch")
    require(activation["workflow_run_attempt_required"] == 1, "activation attempt requirement drift")
    require(activation["rerun_authorized"] is False, "activation opens rerun")
    require(activation["release_consumed"] is False, "pre-run activation marked consumed")
    start = activation["single_use_window_start_utc"]
    require(isinstance(start, str), "single-use window start must be text")
    parsed = datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone(timezone.utc)
    require(parsed.isoformat().endswith("+00:00"), "single-use window start is not UTC")
    require(activation["owner_dispatch_required"] is True, "owner dispatch requirement missing")
    require(activation["network_requests_executed_by_activation"] == 0, "activation executed network request")
    require(activation["object_bytes_downloaded_by_activation"] == 0, "activation downloaded object bytes")
    require(all(value is False for value in activation["downstream_authorizations"].values()), "activation opens downstream authority")
    require(all(value is False for value in activation["trading_authorizations"].values()), "activation opens trading authority")
    print("R11A_CANONICAL_ACTIVATION_R3_VALID_SINGLE_USE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
