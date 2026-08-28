#!/usr/bin/env python3
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).absolute().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))
import difflib as _r11a_bytecode_boundary  # noqa: E402,F401

try:
    from governance.r11a_stage_common_r4 import (
        ACTIVATION_RELATIVE,
        RELEASE_CANDIDATE_RELATIVE,
        RELEASE_DIGEST_RELATIVE,
        RELEASE_RELATIVE,
        REVIEW_EVIDENCE_PATHS,
        ROOT,
        WORKFLOW_NAME,
        WORKFLOW_RELATIVE,
        load,
        read_bytes,
        require,
        require_exact,
        require_gate_review,
        require_int,
        require_sha256,
        sha256,
        stage_authority,
        successor_permissions,
        trading_authority,
    )
    from governance.validate_r11a_execution_release_r4 import validate as validate_release
except ModuleNotFoundError:
    from r11a_stage_common_r4 import (
        ACTIVATION_RELATIVE,
        RELEASE_CANDIDATE_RELATIVE,
        RELEASE_DIGEST_RELATIVE,
        RELEASE_RELATIVE,
        REVIEW_EVIDENCE_PATHS,
        ROOT,
        WORKFLOW_NAME,
        WORKFLOW_RELATIVE,
        load,
        read_bytes,
        require,
        require_exact,
        require_gate_review,
        require_int,
        require_sha256,
        sha256,
        stage_authority,
        successor_permissions,
        trading_authority,
    )
    from validate_r11a_execution_release_r4 import validate as validate_release

ACTIVATION = ROOT / ACTIVATION_RELATIVE
RELEASE = ROOT / RELEASE_RELATIVE
RELEASE_DIGEST = ROOT / RELEASE_DIGEST_RELATIVE
EXECUTION_RELEASE_REVIEW_GATE = "R11A_EXECUTION_RELEASE_REVIEW"
ACTIVATION_KEYS = frozenset(
    {
        "schema_version",
        "activation_id",
        "status",
        "execution_release_id",
        "execution_release_candidate_sha256",
        "execution_release_blob_sha256",
        "dispatch_ref_required",
        "workflow_name",
        "workflow_path",
        "workflow_sha256",
        "execution_release_review_evidence_sha256",
        "automatic_dispatch_authorized",
        "reusable_activation_authorized",
        "maximum_runs",
        "single_workflow_dispatch_authorized",
        "workflow_run_attempt_required",
        "rerun_authorized",
        "release_consumed",
        "runtime_binding_present",
        "single_use_window_start_utc",
        "explicit_owner_dispatch_required",
        "network_requests_executed_by_activation",
        "object_bytes_downloaded_by_activation",
        "aws_iam_mutations_executed_by_activation",
        "downstream_authorizations",
        "trading_authorizations",
    }
)


def validate(
    root: Path = ROOT,
    *,
    permitted_successor_paths: frozenset[str] = frozenset(),
    _review_lineage: list[object] | None = None,
) -> dict[str, object]:
    lineage = [] if _review_lineage is None else _review_lineage
    permitted = successor_permissions(
        frozenset(permitted_successor_paths)
        | {
            ACTIVATION_RELATIVE,
            REVIEW_EVIDENCE_PATHS[EXECUTION_RELEASE_REVIEW_GATE],
        }
    )
    release = validate_release(
        root,
        permitted_successor_paths=permitted,
        _review_lineage=lineage,
    )
    activation = load(root, ACTIVATION_RELATIVE, missing_label="canonical activation is absent")
    require_exact(activation, ACTIVATION_KEYS, "canonical activation")
    require(activation["schema_version"] == "2.0", "activation schema drift")
    require(
        activation["activation_id"]
        == "ACTIVATE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001",
        "activation ID drift",
    )
    require(
        activation["status"] == "ACTIVATED_FOR_EXACTLY_ONE_CANONICAL_R11A_RUN",
        "activation status drift",
    )
    require(
        activation["execution_release_id"] == release["execution_release_id"],
        "activation release ID drift",
    )
    require_sha256(
        activation["execution_release_candidate_sha256"],
        "execution_release_candidate_sha256",
    )
    require(
        activation["execution_release_candidate_sha256"]
        == sha256(root, RELEASE_CANDIDATE_RELATIVE),
        "activation release-candidate binding drift",
    )
    require_sha256(activation["execution_release_blob_sha256"], "execution_release_blob_sha256")
    release_sha = sha256(root, RELEASE_RELATIVE)
    require(activation["execution_release_blob_sha256"] == release_sha, "activation release blob binding drift")
    require(
        read_bytes(root, RELEASE_DIGEST_RELATIVE) == f"{release_sha}\n".encode("ascii"),
        "activation detached release binding drift",
    )
    require(activation["dispatch_ref_required"] == "refs/heads/main", "activation dispatch ref drift")
    require(activation["workflow_name"] == WORKFLOW_NAME, "activation workflow name drift")
    require(activation["workflow_path"] == WORKFLOW_RELATIVE, "activation workflow path drift")
    require_sha256(activation["workflow_sha256"], "workflow_sha256")
    require(activation["workflow_sha256"] == sha256(root, WORKFLOW_RELATIVE), "activation workflow binding drift")
    require_gate_review(
        root,
        activation,
        "execution_release_review_evidence_sha256",
        EXECUTION_RELEASE_REVIEW_GATE,
        target_files={
            RELEASE_RELATIVE: sha256(root, RELEASE_RELATIVE),
            RELEASE_DIGEST_RELATIVE: sha256(root, RELEASE_DIGEST_RELATIVE),
        },
        predecessor_files={
            RELEASE_CANDIDATE_RELATIVE: sha256(root, RELEASE_CANDIDATE_RELATIVE)
        },
        lineage=lineage,
    )
    require(activation["automatic_dispatch_authorized"] is False, "activation authorizes automatic dispatch")
    require(activation["reusable_activation_authorized"] is False, "activation is reusable")
    require_int(activation["maximum_runs"], "activation maximum runs")
    require(activation["maximum_runs"] == 1, "activation maximum runs drift")
    require(activation["single_workflow_dispatch_authorized"] is True, "activation does not authorize exactly one dispatch")
    require_int(activation["workflow_run_attempt_required"], "activation workflow attempt")
    require(activation["workflow_run_attempt_required"] == 1, "activation attempt requirement drift")
    require(activation["rerun_authorized"] is False, "activation opens rerun")
    require(activation["release_consumed"] is False, "immutable pre-run activation marked release consumed")
    require(activation["runtime_binding_present"] is False, "activation snapshot rewritten after runtime binding")
    start = activation["single_use_window_start_utc"]
    require(isinstance(start, str) and start.endswith("Z"), "single-use window start must be UTC text")
    try:
        parsed = datetime.fromisoformat(start.replace("Z", "+00:00"))
    except ValueError:
        require(False, "single-use window timestamp malformed")
        parsed = datetime.min.replace(tzinfo=timezone.utc)  # unreachable
    require(parsed.tzinfo is not None and parsed.astimezone(timezone.utc) == parsed, "single-use window start is not UTC")
    require(activation["explicit_owner_dispatch_required"] is True, "explicit owner dispatch gate missing")
    require_int(activation["network_requests_executed_by_activation"], "activation network request count")
    require(activation["network_requests_executed_by_activation"] == 0, "activation executed network request")
    require_int(activation["object_bytes_downloaded_by_activation"], "activation downloaded bytes")
    require(activation["object_bytes_downloaded_by_activation"] == 0, "activation downloaded object bytes")
    require_int(activation["aws_iam_mutations_executed_by_activation"], "activation IAM mutation count")
    require(activation["aws_iam_mutations_executed_by_activation"] == 0, "activation mutated IAM")
    stage_authority(activation["downstream_authorizations"], "activation downstream authority")
    trading_authority(activation["trading_authorizations"], "activation trading authority")
    return activation


def main() -> int:
    validate()
    print("R11A_CANONICAL_ACTIVATION_R4_VALID_SINGLE_USE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
