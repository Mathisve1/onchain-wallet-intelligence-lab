from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE = ROOT / "research/archive_inventory/r11a_implementation"
CONTRACT = BASE / "R11A_D1_CLOSURE_REPAIR_CONTRACT.json"
STATUS = BASE / "R11A_D1_CLOSURE_STATUS.json"
WORKFLOW = BASE / "workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic-r2.yml"
INSTALLED = ROOT / ".github/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic-r2.yml"
RELEASE = ROOT / "research/archive_inventory/r11a_runtime/R11A_EXECUTION_RELEASE.json"
ROLE_ATTESTATION = ROOT / "research/archive_inventory/r11a_role_attestation/R11A_ROLE_ATTESTATION.json"

D1_MERGE = "8e778fdf6e7b5ef5475791bd4292b2d04055afcd"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-identity-r11a"


class ClosureValidationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ClosureValidationError(message)


def load(path: Path) -> dict:
    def pairs(pairs_: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs_:
            if key in value:
                raise ClosureValidationError(f"duplicate JSON key in {path}: {key}")
            value[key] = item
        return value

    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=pairs,
        parse_constant=lambda token: (_ for _ in ()).throw(
            ClosureValidationError(f"nonfinite JSON constant in {path}: {token}")
        ),
    )
    require(isinstance(value, dict), f"JSON root must be object: {path}")
    return value  # type: ignore[return-value]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


def validate() -> None:
    contract = load(CONTRACT)
    status = load(STATUS)
    require(contract["closure_id"] == "R11A-D1-CLOSURE-REPAIR-001", "closure ID drift")
    require(contract["canonical_d1_merge_commit"] == D1_MERGE, "D1 merge binding drift")
    require(contract["status"] == "CLOSED_AWAITING_OWNER_APPROVAL_NO_EXECUTION", "closure status drift")
    require(contract["closure_sealed"] is True, "closure not sealed")
    require(all(value is True for value in contract["review_blockers"].values()), "review blocker not closed")
    require(contract["owner_approval_eligible"] is True, "owner approval eligibility not reached")
    require(contract["owner_approval_status"] == "NOT_PRESENT", "owner approval overclaim")
    require(contract["workflow_installed_under_dot_github"] is False, "workflow installation overclaim")
    require(contract["new_role_created"] is False, "role creation overclaim")
    require(contract["execution_release_present"] is False, "release overclaim")
    require(contract["canonical_activation_present"] is False, "activation overclaim")
    require(contract["single_workflow_dispatch_authorized"] is False, "dispatch authority overclaim")
    require(contract["rerun_authorized"] is False, "rerun authority overclaim")
    require(all(value is False for value in contract["current_runtime_authority"].values()), "runtime authority opened")
    require(all(value is False for value in contract["downstream_authorizations"].values()), "downstream authority opened")
    require(all(value is False for value in contract["trading_authorizations"].values()), "trading authority opened")
    require(contract["network_requests_executed_by_closure_repair"] == 0, "network execution overclaim")
    require(contract["aws_iam_mutations_executed_by_closure_repair"] == 0, "IAM mutation overclaim")
    require(contract["diagnostic_rows_created_by_closure_repair"] == 0, "diagnostic execution overclaim")
    require(contract["wallet_feature_rows_created_by_closure_repair"] == 0, "wallet output overclaim")
    require(contract["r11_closed"] is False and contract["r12_ready"] is False, "lifecycle overclaim")
    require(contract["empirical_result"] is None, "empirical result overclaim")

    hashes = contract["closure_file_hashes"]
    require(isinstance(hashes, dict) and len(hashes) >= 17, "closure hash map incomplete")
    for relative, expected in hashes.items():
        path = ROOT / relative
        require(path.is_file(), f"sealed closure path missing: {relative}")
        require(sha256(path) == expected, f"sealed closure path drift: {relative}")
    require(contract["repaired_workflow_candidate_path"] == str(WORKFLOW.relative_to(ROOT)), "workflow path drift")
    require(contract["repaired_workflow_candidate_git_blob_sha"] == git_blob_sha(WORKFLOW), "workflow blob drift")

    require(status["canonical_d1_merge_commit"] == D1_MERGE, "status D1 binding drift")
    require(status["status"] == "CLOSURE_REPAIRED_AWAITING_OWNER_APPROVAL_NO_EXECUTION", "status record drift")
    require(status["owner_approval_eligible"] is True, "status eligibility drift")
    require(status["known_blockers"] == [], "status blocker residue")
    require(status["repair_pr"] == 142, "repair PR binding drift")
    require(status["owner_approval_present"] is False, "status approval overclaim")
    require(status["workflow_installed"] is False, "status installation overclaim")
    require(status["runtime_release_present"] is False, "status release overclaim")
    require(status["canonical_activation_present"] is False, "status activation overclaim")
    require(status["r11a_execution_authorized"] is False, "status execution authority overclaim")
    require(status["r11_closed"] is False and status["r12_ready"] is False, "status lifecycle overclaim")

    collector = (BASE / "collector.py").read_text(encoding="utf-8")
    runtime_source = (BASE / "runtime.py").read_text(encoding="utf-8")
    failure_source = (BASE / "failure.py").read_text(encoding="utf-8")
    network_source = (BASE / "network.py").read_text(encoding="utf-8")
    runner_source = (BASE / "runner.py").read_text(encoding="utf-8")
    for path in (
        BASE / "collector.py",
        BASE / "runtime.py",
        BASE / "failure.py",
        BASE / "network.py",
        BASE / "runner.py",
        BASE / "entrypoint.py",
    ):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    require("runtime.GuardedWorkspaceMeter" in collector, "guarded local workspace absent")
    require("maximum_materialized_blocks" in collector, "prematerialization cap gate absent")
    require("_expanded_reducer_rows" in collector, "complete reducer projection absent")
    require("stop_rows=state.stop_rows()" in collector, "exact stop ledger projection absent")
    require("state.mark_first_parse" in collector and "state.mark_second_parse" in collector, "two-pass object evidence absent")
    require("runtime_guard=guard" in runner_source, "runner does not pass runtime guard")
    require("evidence_state=state" in runner_source, "runner does not pass object evidence state")
    require("network.https_get_to_file" in runner_source, "metadata-bound network transport absent")
    require("failure.seal_minimal_failure_artifact" in runner_source, "runtime failure artifact absent")
    require("class GuardedWorkspaceMeter" in runtime_source, "guarded workspace class absent")
    require("def stop_rows(" in runtime_source, "stop evidence state absent")
    require("seven" not in failure_source.lower() or "scientific" in failure_source.lower(), "failure artifact boundary absent")
    require("r11a-wallet-features.ndjson" in failure_source and "b\"\"" in failure_source, "failure wallet output not empty")

    network_tree = ast.parse(network_source)
    calls = [node for node in ast.walk(network_tree) if isinstance(node, ast.Call)]
    require(any(isinstance(node.func, ast.Attribute) and node.func.attr == "getresponse" for node in calls), "HTTP response metadata path absent")
    require(any(isinstance(node.func, ast.Attribute) and node.func.attr == "read" for node in calls), "stream body read absent")
    require("metadata.content_length != expected_content_length" in network_source, "Content-Length metadata gate absent")
    require(network_source.index("metadata.content_length != expected_content_length") < network_source.index("response.read("), "body read occurs before Content-Length gate")
    require(network_source.index("metadata.etag != expected_etag") < network_source.index("response.read("), "body read occurs before ETag gate")
    require("maximum_body_bytes" in network_source and ".partial" in network_source, "stream cap or partial cleanup absent")

    workflow = WORKFLOW.read_text(encoding="utf-8")
    require(workflow.startswith("name: Hyperliquid Archive R11A Identity Boundary Diagnostic R2\n"), "workflow name drift")
    require("workflow_dispatch:" in workflow, "manual trigger absent")
    require("schedule:" not in workflow and "\npush:" not in workflow, "automatic trigger opened")
    require("persist-credentials: false" in workflow, "checkout credentials persisted")
    require(f"role-to-assume: {ROLE_ARN}" in workflow, "successor role drift")
    require("role-duration-seconds: 21600" in workflow, "role duration drift")
    require("retry-max-attempts: 1" in workflow, "OIDC retry drift")
    require("validate_r11a_d1_closure.py" in workflow, "closure gate absent")
    require("research.archive_inventory.r11a_implementation.entrypoint" in workflow, "repaired entrypoint absent")
    require("Seal failure evidence when execution did not create an artifact" in workflow, "precollector failure evidence step absent")
    require("if: always()" in workflow, "always-upload or terminal enforcement absent")
    require("aws s3 " not in workflow.lower() and "aws s3api " not in workflow.lower(), "unreviewed AWS CLI S3 route present")
    require("pip install" not in workflow.lower() and "apt install" not in workflow.lower(), "runtime dependency installation present")
    require(not INSTALLED.exists(), "repaired workflow installed before owner approval")
    require(not RELEASE.exists(), "R11A release exists before owner approval")
    require(not ROLE_ATTESTATION.exists(), "R11A role attestation exists before approval")

    for forbidden in ("drop_duplicates", "first_seen_wins", "last_seen_wins"):
        require(forbidden not in collector + runner_source, f"forbidden repair heuristic: {forbidden}")


def main() -> int:
    validate()
    print("R11A_D1_CLOSURE_VALID_AWAITING_OWNER_APPROVAL_NO_EXECUTION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
