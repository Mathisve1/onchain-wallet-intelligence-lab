#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BASE = ROOT / "research/archive_inventory"
IMPL = BASE / "r11a_implementation"
CONTRACT = IMPL / "R11A_IMPLEMENTATION_CONTRACT.json"
PREREG = BASE / "r11a/R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_PREREGISTRATION.json"
SELECTION = BASE / "r11/R11_72H_SELECTION.json"
DEPENDENCIES = IMPL / "R11A_DEPENDENCIES.json"
ROLE_DECISION = IMPL / "R11A_ROLE_DECISION.json"
TRUST = IMPL / "R11A_OIDC_TRUST_POLICY.json"
PERMISSION = IMPL / "R11A_PERMISSION_POLICY.json"
RESOURCE = IMPL / "R11A_RESOURCE_FEASIBILITY.json"
RESOURCE_MD = IMPL / "R11A_RESOURCE_FEASIBILITY.md"
WORKFLOW = IMPL / "workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic.yml"
INSTALLED_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic.yml"
RUNTIME_RELEASE = BASE / "r11a_runtime/R11A_EXECUTION_RELEASE.json"
APPROVAL_ROOT = BASE / "r11a_approval"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-identity-r11a"
WORKFLOW_NAME = "Hyperliquid Archive R11A Identity Boundary Diagnostic"
PREREG_MERGE = "5103c846be8a53732d8559a281ac8b57ce4d7aac"
EVIDENCE_MERGE = "f7aa612d2a5638cce0fd197f57efea4b787f87f1"
TAXA = [
    "TID_SCOPE_FALSE_POSITIVE",
    "EXPECTED_COUNTERPARTY_PAIR",
    "EXACT_BLOCK_REPLAY_ACROSS_OBJECTS",
    "EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY",
    "CONFLICTING_BLOCK_REPLAY",
    "CONFLICTING_USER_FILL",
    "INTRA_BLOCK_REPEAT",
    "TID_SCHEMA_VIOLATION",
    "UNCLASSIFIABLE",
]


class R11AImplementationValidationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise R11AImplementationValidationError(message)


def strict_load(path: Path) -> dict:
    def object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise R11AImplementationValidationError(f"duplicate key in {path}: {key}")
            result[key] = value
        return result

    def reject_constant(token: str) -> object:
        raise R11AImplementationValidationError(f"non-finite constant in {path}: {token}")

    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=object_pairs,
        parse_constant=reject_constant,
    )
    require(isinstance(value, dict), f"JSON root must be object: {path}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def validate_seal(contract: dict) -> None:
    from governance import seal_r11a_implementation as seal

    require(contract["implementation_sealed"] is True, "implementation is not sealed")
    expected = seal.expected_hashes()
    require(contract["implementation_file_hashes"] == expected, "implementation file hashes drift")
    require(contract["workflow_candidate_git_blob_sha"] == git_blob_sha(WORKFLOW), "workflow blob drift")
    require(CONTRACT.read_text(encoding="utf-8") == seal.render_sealed(), "contract seal is stale")


def validate_contract(contract: dict, prereg: dict) -> None:
    require(contract["schema_version"] == "1.0", "contract schema drift")
    require(
        contract["implementation_id"]
        == "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-IMPLEMENTATION-001",
        "implementation ID drift",
    )
    require(
        contract["diagnostic_id"] == prereg["diagnostic_id"]
        == "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-001",
        "diagnostic ID drift",
    )
    require(
        contract["status"] == "IMPLEMENTED_AWAITING_OWNER_APPROVAL_NO_EXECUTION",
        "implementation status drift",
    )
    require(contract["preregistration_merge_commit"] == PREREG_MERGE, "preregistration merge drift")
    require(contract["r11_evidence_closure_merge_commit"] == EVIDENCE_MERGE, "evidence merge drift")
    require(contract["r11_parent_run_id"] == 31436753081, "parent run drift")
    require(contract["r11_parent_artifact_id"] == 9082810554, "parent artifact drift")
    require(
        contract["r11_parent_artifact_sha256"]
        == "45ee57df7a63561bef1772d8612d5fe32b06b9c407d9c1464ce0a02b65a15cc5",
        "parent artifact digest drift",
    )
    require(
        contract["exact_selection_sha256"]
        == "7c134f4b62f547904126a5f810c177484dceeffa246d53c5c35944367d563eb2",
        "selection digest drift",
    )
    require(contract["selected_object_count"] == 72, "selection count drift")
    require(contract["workflow_installed_under_dot_github"] is False, "workflow installation overclaim")
    require(contract["owner_approval_status"] == "NOT_PRESENT", "owner approval overclaim")
    require(contract["execution_release_present"] is False, "release overclaim")
    require(contract["canonical_activation_present"] is False, "activation overclaim")
    require(contract["single_workflow_dispatch_authorized"] is False, "dispatch authority opened")
    require(contract["rerun_authorized"] is False, "rerun authority opened")
    require(contract["duplicate_taxonomy"] == TAXA, "taxonomy drift")
    require(contract["identity_model"]["deduplication_authorized"] is False, "dedup authority opened")
    require(
        contract["identity_model"]["protocol_matched_trade_key"]
        == ["exact_raw_block_time", "exact_raw_coin_string", "validated_json_integer_tid"],
        "protocol identity drift",
    )
    require(
        contract["identity_model"]["wallet_user_fill_key"]
        == [
            "canonical_lowercase_wallet_address",
            "exact_raw_block_time",
            "exact_raw_coin_string",
            "validated_json_integer_tid",
        ],
        "wallet-fill identity drift",
    )
    require(all(value is False for value in contract["current_runtime_authority"].values()), "runtime authority opened")
    require(all(value is False for value in contract["downstream_authorizations"].values()), "downstream authority opened")
    require(all(value is False for value in contract["trading_authorizations"].values()), "trading authority opened")
    require(contract["new_role_creation_authorized_now"] is False, "role creation authority opened")
    require(contract["existing_r11_role_reuse_authorized"] is False, "R11 role reuse opened")
    require(contract["existing_r11_role_mutation_authorized"] is False, "R11 role mutation opened")
    require(contract["network_requests_executed_by_implementation"] == 0, "network activity overclaim")
    require(contract["aws_iam_mutations_executed_by_implementation"] == 0, "IAM mutation overclaim")
    require(contract["diagnostic_rows_created_by_implementation"] == 0, "diagnostic result overclaim")
    require(contract["wallet_feature_rows_created_by_implementation"] == 0, "wallet feature overclaim")
    require(contract["r11_closed"] is False and contract["r12_ready"] is False, "lifecycle overclaim")
    require(contract["empirical_result"] is None, "empirical result created")
    require(prereg["status"] == "PREREGISTERED_NO_EXECUTION", "preregistration no longer inert")
    require(prereg["owner_approval_status"] == "NOT_PRESENT", "preregistration approval drift")
    require(prereg["execution_authorized_now"] is False, "preregistration execution opened")
    require(prereg["duplicate_taxonomy"] == TAXA, "contract/prereg taxonomy split")


def validate_limits(contract: dict, prereg: dict) -> None:
    from research.archive_inventory.r11a_implementation.limits import DEFAULT_LIMITS

    expected = DEFAULT_LIMITS.as_contract_mapping()
    require(contract["resource_envelope"] == expected, "contract limits differ from implementation")
    proposed = prereg["proposed_request_envelope"]
    crosswalk = {
        "maximum_one_time_budget_eur_micros": int(proposed["maximum_one_time_budget_eur"] * 1_000_000),
        "maximum_monthly_budget_eur_micros": int(proposed["maximum_monthly_budget_eur"] * 1_000_000),
        "maximum_get_object_requests": proposed["maximum_get_object_requests"],
        "maximum_requests_per_object": proposed["maximum_requests_per_object"],
        "maximum_retries_per_request": proposed["maximum_retries_per_request"],
        "maximum_total_compressed_bytes": proposed["maximum_total_compressed_bytes"],
        "maximum_individual_compressed_bytes": proposed["maximum_individual_compressed_bytes"],
        "maximum_total_decompressed_bytes_across_two_passes": proposed[
            "maximum_total_decompressed_bytes_processed_across_two_local_passes"
        ],
        "maximum_individual_decompressed_bytes_per_pass": proposed[
            "maximum_individual_decompressed_bytes_per_pass"
        ],
        "maximum_ephemeral_workspace_bytes": proposed["maximum_ephemeral_workspace_bytes"],
        "minimum_free_workspace_bytes_before_oidc": proposed["minimum_free_workspace_bytes_before_oidc"],
        "maximum_retained_artifact_bytes": proposed["maximum_retained_artifact_bytes"],
        "reserved_non_scientific_package_metadata_bytes": proposed[
            "reserved_non_scientific_package_metadata_bytes"
        ],
        "maximum_retained_scientific_output_bytes": proposed["maximum_retained_scientific_output_bytes"],
        "maximum_runtime_seconds": proposed["maximum_runtime_seconds"],
        "maximum_repeated_legacy_key_groups_retained": prereg["retention_and_privacy"][
            "maximum_repeated_legacy_key_groups_retained"
        ],
        "maximum_repeated_observations_retained": prereg["retention_and_privacy"][
            "maximum_repeated_observations_retained"
        ],
        "maximum_repeated_block_groups_retained": prereg["retention_and_privacy"][
            "maximum_repeated_block_groups_retained"
        ],
    }
    for key, value in crosswalk.items():
        require(expected[key] == value, f"implementation/preregistration cap drift: {key}")
    require(expected["post_measurement_packaging_reservation_seconds"] == 300, "packaging reserve drift")
    require(expected["minimum_upload_window_seconds"] == 60, "upload window drift")
    require(expected["partition_count"] == 256, "partition count drift")
    require(expected["package_boundary_bytes"] == 1024, "package boundary drift")


def validate_role_and_policy(selection: dict) -> None:
    role = strict_load(ROLE_DECISION)
    trust = strict_load(TRUST)
    permission = strict_load(PERMISSION)
    require(
        role["status"] == "FROZEN_INERT_SUCCESSOR_ROLE_CANDIDATE_NO_IAM_MUTATION",
        "role decision status drift",
    )
    require(
        role["decision"] == "CREATE_NEW_DEDICATED_R11A_ROLE_ONLY_AFTER_EXACT_OWNER_APPROVAL",
        "role decision drift",
    )
    successor = role["successor_role"]
    require(successor["role_arn"] == ROLE_ARN, "role ARN drift")
    require(successor["workflow_name"] == WORKFLOW_NAME, "role workflow name drift")
    require(successor["maximum_session_duration_seconds"] == 21600, "role duration drift")
    require(successor["persistent_get_object_resource_count"] == 72, "role resource count drift")
    require(all(value is False for value in role["current_authority"].values()), "role decision opens authority")
    require(role["network_or_iam_actions_executed_by_this_decision"] == 0, "role decision action overclaim")
    statement = trust["Statement"][0]
    equals = statement["Condition"]["StringEquals"]
    require(statement["Action"] == "sts:AssumeRoleWithWebIdentity", "trust action drift")
    require(equals["token.actions.githubusercontent.com:workflow"] == WORKFLOW_NAME, "trust workflow drift")
    require(equals["token.actions.githubusercontent.com:ref"] == "refs/heads/main", "trust ref drift")
    require(equals["token.actions.githubusercontent.com:repository_id"] == "1326362646", "repository ID drift")
    require(equals["token.actions.githubusercontent.com:repository_owner_id"] == "163474992", "owner ID drift")
    resources = permission["Statement"][0]["Resource"]
    exact = [
        f"arn:aws:s3:::hl-mainnet-node-data/{row['key']}"
        for row in selection["exact_targets"]
    ]
    require(permission["Statement"][0]["Action"] == "s3:GetObject", "permission action drift")
    require(resources == exact, "permission resources differ from exact selection")
    require(len(resources) == len(set(resources)) == 72, "permission cardinality drift")
    require(all("*" not in value for value in resources), "persistent wildcard resource opened")
    denied = {
        action
        for statement in permission["Statement"][1:]
        for action in statement["Action"]
    }
    for action in (
        "s3:GetObjectVersion",
        "s3:GetObjectAttributes",
        "s3:ListBucket",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:RestoreObject",
    ):
        require(action in denied, f"required deny absent: {action}")


def validate_dependencies() -> None:
    dependencies = strict_load(DEPENDENCIES)
    require(
        dependencies["status"] == "FROZEN_INERT_IMPLEMENTATION_NO_INSTALLATION",
        "dependency status drift",
    )
    require(dependencies["python_runtime"]["exact_version"] == "3.12.13", "Python version drift")
    require(dependencies["python_runtime"]["third_party_python_packages_required_by_collector"] == [], "third-party dependency opened")
    require(dependencies["network_dependency_installation_authorized"] is False, "network install opened")
    require(dependencies["pip_install_authorized"] is False, "pip install opened")
    require(dependencies["apt_install_authorized"] is False, "apt install opened")
    rows = dependencies["repository_local_runtime_dependencies"]
    require(len(rows) == 1, "repository dependency count drift")
    row = rows[0]
    dependency_path = ROOT / row["path"]
    require(dependency_path.is_file(), "repository dependency missing")
    require(sha256(dependency_path) == row["sha256"], "repository dependency hash drift")
    require(row["global_limit_mutation_authorized"] is False, "base global mutation opened")


def validate_resource_report() -> None:
    resource = strict_load(RESOURCE)
    require(
        resource["status"] == "OFFLINE_STATIC_BOUND_COMPLETE_FULL_SCALE_SUCCESS_CONDITIONAL",
        "resource status drift",
    )
    source = resource["source_counts"]
    model = resource["implementation_index_model"]
    require(source["selected_compressed_bytes"] == 2107738436, "compressed source drift")
    require(source["one_pass_decompressed_bytes"] == 10539979245, "one-pass source drift")
    require(source["two_pass_decompressed_processing_bytes"] == 21079958490, "two-pass source drift")
    require(source["raw_block_observations"] == 3283391, "block count drift")
    require(source["raw_event_observations"] == 26384234, "event count drift")
    require(
        model["block_index_projected_bytes"]
        == source["raw_block_observations"] * model["block_index_framed_bytes_per_record"],
        "block index formula drift",
    )
    require(
        model["representative_integer_tid_weak_index_projected_bytes"]
        == source["raw_event_observations"] * model["representative_integer_tid_weak_index_bytes_per_record"],
        "weak index formula drift",
    )
    require(
        model["representative_presort_workspace_bytes_excluding_schema_index"]
        == source["selected_compressed_bytes"]
        + model["block_index_projected_bytes"]
        + model["representative_integer_tid_weak_index_projected_bytes"],
        "workspace formula drift",
    )
    require(
        model["representative_presort_margin_bytes_excluding_schema_index"]
        == model["workspace_cap_bytes"]
        - model["representative_presort_workspace_bytes_excluding_schema_index"],
        "workspace margin drift",
    )
    require(resource["conclusion"]["bounded_fail_closed_execution_feasible"] is True, "bounded execution finding drift")
    require(resource["conclusion"]["successful_complete_terminal_guaranteed"] is False, "success guarantee overclaim")
    require(resource["network_requests_executed_by_report"] == 0, "resource report network overclaim")
    require(resource["empirical_result"] is None, "resource report empirical result overclaim")
    text = RESOURCE_MD.read_text(encoding="utf-8")
    for required in (
        "bounded fail-closed execution design",
        "does not pretend that a complete R11A result is guaranteed",
        "No sampling or silent cap increase is permitted",
        "R11 closure and R12 readiness: still false",
    ):
        require(required in text, f"resource report prose drift: {required}")


def assigned_attribute(node: ast.AST) -> str | None:
    if isinstance(node, ast.Attribute):
        prefix = assigned_attribute(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def validate_source_static() -> None:
    paths = {
        name: IMPL / name
        for name in (
            "activity.py",
            "collector.py",
            "diagnostic.py",
            "identity.py",
            "limits.py",
            "schema.py",
            "storage.py",
        )
    }
    for name, path in paths.items():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    label = assigned_attribute(target)
                    require(
                        label not in {
                            "transport_base.MAX_BLOCKS",
                            "transport_base.MAX_EVENTS",
                            "transport_base.MAX_ROWS",
                            "transport_base.MAX_OUTPUT_BYTES",
                        },
                        f"R10 global mutation in {name}: {label}",
                    )
        for forbidden_import in (
            "import boto3",
            "from boto3",
            "import botocore",
            "from botocore",
            "import requests",
            "from requests",
        ):
            require(
                forbidden_import not in source,
                f"unexpected dependency import in {name}: {forbidden_import}",
            )
    activity = paths["activity.py"].read_text(encoding="utf-8")
    activity_tree = ast.parse(activity)
    method_names = {
        node.name
        for node in ast.walk(activity_tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    require("__getitem__" not in method_names, "activity tracker reintroduces read mutation hook")
    imports_defaultdict = any(
        (
            isinstance(node, ast.ImportFrom)
            and node.module == "collections"
            and any(alias.name == "defaultdict" for alias in node.names)
        )
        or (
            isinstance(node, ast.Import)
            and any(alias.name == "collections.defaultdict" for alias in node.names)
        )
        for node in ast.walk(activity_tree)
    )
    calls_setdefault = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "setdefault"
        for node in ast.walk(activity_tree)
    )
    require(
        not imports_defaultdict and not calls_setdefault,
        "activity tracker lazy-read mutation pattern",
    )
    require("def record(" in activity and "def snapshot(" in activity, "explicit activity API missing")
    collector = paths["collector.py"].read_text(encoding="utf-8")
    require("R11A runtime release absent; network execution forbidden" in collector, "release fail gate missing")
    require(collector.index("validate_static_inputs(require_release=True)") < collector.index("build_signed_request"), "release gate occurs after request construction")
    require("deduplication_authorized" in collector, "collector lacks no-dedup boundary")
    require("drop_duplicates" not in collector, "blind deduplication introduced")
    diagnostic_source = paths["diagnostic.py"].read_text(encoding="utf-8")
    for taxon in TAXA:
        require(taxon in diagnostic_source, f"diagnostic taxon absent: {taxon}")
    require("deduplication_authorized\": False" in diagnostic_source, "duplicate rows do not deny deduplication")
    identity_source = paths["identity.py"].read_text(encoding="utf-8")
    require("UINT50_MAX_EXCLUSIVE = 1 << 50" in identity_source, "uint50 identity boundary missing")
    require("binary float forbidden" in identity_source, "binary-float failure boundary missing")
    require("validate_golden_vectors()" in identity_source, "canonical serialization golden gate missing")


def validate_workflow() -> None:
    require(WORKFLOW.is_file(), "workflow candidate missing")
    require(not INSTALLED_WORKFLOW.exists(), "R11A workflow installed before approval")
    text = WORKFLOW.read_text(encoding="utf-8")
    require(text.startswith(f"name: {WORKFLOW_NAME}\n"), "workflow name drift")
    require("run-name: R11A identity and boundary diagnostic" in text, "run name drift")
    require("workflow_dispatch:" in text, "manual dispatch trigger absent")
    require("\nschedule:" not in text and "\npush:" not in text, "automatic trigger introduced")
    require("persist-credentials: false" in text, "checkout credentials persist")
    require("id-token: write" in text and "actions: read" in text, "workflow permissions drift")
    require(f"role-to-assume: {ROLE_ARN}" in text, "workflow role drift")
    require("role-duration-seconds: 21600" in text, "workflow role duration drift")
    require("retry-max-attempts: 1" in text, "OIDC retry drift")
    require("R11A_EXECUTION_RELEASE.json" in text, "release path absent")
    require("6442450944" in text, "pre-OIDC space gate absent")
    require(text.index("insufficient free workspace before OIDC") < text.index("aws-actions/configure-aws-credentials"), "space gate occurs after OIDC")
    require("research.archive_inventory.r11a_implementation.collector" in text, "collector invocation absent")
    require("aws s3 " not in text.lower() and "aws s3api " not in text.lower(), "AWS CLI S3 route introduced")
    for date in ("20250728", "20250729", "20250730"):
        require(f"node_fills_by_block/hourly/{date}/*" in text, f"session prefix absent: {date}")


def validate_absent_authority() -> None:
    require(not INSTALLED_WORKFLOW.exists(), "installed workflow unexpectedly present")
    require(not RUNTIME_RELEASE.exists(), "runtime release unexpectedly present")
    require(not APPROVAL_ROOT.exists(), "owner approval directory unexpectedly present")
    for forbidden in (
        BASE / "r11a_runtime/R11A_EXECUTION_RELEASE_CANDIDATE.json",
        BASE / "r11a_runtime/R11A_EXECUTION_RELEASE_CONSUMPTION.json",
        BASE / "r11a_evidence",
    ):
        require(not forbidden.exists(), f"later-stage artifact prematurely present: {forbidden.relative_to(ROOT)}")


def main() -> int:
    contract = strict_load(CONTRACT)
    prereg = strict_load(PREREG)
    selection = strict_load(SELECTION)
    validate_contract(contract, prereg)
    validate_limits(contract, prereg)
    validate_role_and_policy(selection)
    validate_dependencies()
    validate_resource_report()
    validate_source_static()
    validate_workflow()
    validate_absent_authority()
    validate_seal(contract)

    from research.archive_inventory.r11a_implementation import identity
    from research.archive_inventory.r11a_implementation.activity import ActivityTracker

    identity.validate_golden_vectors()
    tracker = ActivityTracker()
    before = tracker.wallet_count()
    require(tracker.snapshot("0x" + "1" * 40) is None, "read of absent wallet returned state")
    require(tracker.wallet_count() == before, "read created wallet state")
    print("R11A_IMPLEMENTATION_VALID_INERT_NO_EXECUTION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
