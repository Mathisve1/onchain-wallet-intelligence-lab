#!/usr/bin/env python3
"""Validate the L1 live-data collection record: preregistration, approval, release.

The contract in ``L1_LIVE_DATA_COLLECTION_PREREGISTRATION.json`` makes claims
about what ``src/live_data`` can and cannot do. This validator refuses to take
those claims on trust: every numeric bound, endpoint, request type and import
restriction is re-derived from the source and compared. Drift in either
direction is a failure, so a widened envelope cannot be slipped past a stale
document and a tightened document cannot silently misdescribe live code.

The owner approval is checked the same way. Its exact text is hashed and
every ``key=value`` line in it is compared with the contract and the code, so
the approval binds what actually runs rather than a paraphrase of it. The
single-use release it grants is tracked from released to consumed, and a
consumed release must point at retained session evidence.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/wallet_copyability/live_data"
PREREG = BASE / "L1_LIVE_DATA_COLLECTION_PREREGISTRATION.json"
APPROVAL_TEXT = BASE / "APPROVE_HL_LIVE_DATA_COLLECTION_L1_001.txt"
DECISION = BASE / "L1_OWNER_DECISION_001.json"
CORE = ROOT / "src/live_data"
COLLECTOR = ROOT / "research/wallet_copyability/live_data_collector"

PILOT_ID = "HL-LIVE-DATA-COLLECTION-L1-001"
APPROVAL_ID = "APPROVE_HL_LIVE_DATA_COLLECTION_L1_001"
DECISION_ID = "L1-OWNER-DECISION-001"
RELEASE_ID = "RELEASE_HL_LIVE_DATA_COLLECTION_L1_001"
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_PATHS = {
    "research/wallet_copyability/live_data/README.md",
    "research/wallet_copyability/live_data/STATUS.md",
    "research/wallet_copyability/live_data/HUMAN_APPROVAL_TEMPLATE.md",
    "research/wallet_copyability/live_data/L1_LIVE_DATA_COLLECTION_PREREGISTRATION.md",
    "research/wallet_copyability/live_data/L1_LIVE_DATA_COLLECTION_PREREGISTRATION.json",
    "research/wallet_copyability/live_data/APPROVE_HL_LIVE_DATA_COLLECTION_L1_001.txt",
    "research/wallet_copyability/live_data/L1_OWNER_DECISION_001.json",
    "src/live_data/__init__.py",
    "src/live_data/cli.py",
    "src/live_data/config.py",
    "src/live_data/hyperliquid_rest.py",
    "src/live_data/hyperliquid_ws.py",
    "src/live_data/ingest.py",
    "src/live_data/models.py",
    "src/live_data/rate_limit.py",
    "src/live_data/results.py",
    "src/live_data/schema.py",
    "src/live_data/storage.py",
    "src/live_data/trades.py",
    "src/live_data/watch.py",
    "research/wallet_copyability/live_data_collector/__init__.py",
    "research/wallet_copyability/live_data_collector/__main__.py",
    "research/wallet_copyability/live_data_collector/transports.py",
}

EXPECTED_TOP_LEVEL_KEYS = {
    "created_by_this_preregistration",
    "downstream_authorizations",
    "exact_network_target",
    "governance_gates",
    "layering_boundary",
    "owner_approval_status",
    "parent_bindings",
    "pilot_id",
    "proposed_request_envelope",
    "read_only_boundary",
    "rest_request_type_allowlist",
    "rest_request_type_denylist_present_in_code",
    "research_question",
    "retained_schema",
    "retention_and_privacy",
    "schema_version",
    "status",
    "stop_conditions",
    "study_id",
    "study_role",
    "trading_authorizations",
    "websocket_subscription_allowlist",
}

EXPECTED_GATES_GRANTED = ["OWNER_APPROVAL", "IMPLEMENTATION_REVIEW", "SINGLE_USE_EXECUTION_RELEASE"]
RELEASE_STATUSES = {"RELEASED_NOT_YET_CONSUMED", "CONSUMED"}

#: The database itself never enters the repository; only its hash does.
FORBIDDEN_EXECUTION_ARTIFACTS = ("research/live_data",)


class ValidationError(SystemExit):
    def __init__(self, message: str) -> None:
        super().__init__(f"L1_PREREGISTRATION_INVALID: {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON root is not an object: {path.name}")
    return value


def load_core_constants() -> Any:
    """Import the deterministic core so its real constants can be compared."""
    sys.path.insert(0, str(ROOT / "src"))
    try:
        from live_data import cli as core_cli
        from live_data import config as core_config
        from live_data import hyperliquid_rest as core_rest
        from live_data import hyperliquid_ws as core_ws
        from live_data import storage as core_storage
    finally:
        sys.path.pop(0)
    return core_config, core_rest, core_ws, core_cli, core_storage


def validate_required_paths() -> None:
    for relative in sorted(REQUIRED_PATHS):
        require((ROOT / relative).is_file(), f"missing required path: {relative}")
    for relative in FORBIDDEN_EXECUTION_ARTIFACTS:
        require(not (ROOT / relative).exists(), f"observation database inside the repository: {relative}")
    for path in BASE.rglob("*"):
        require(path.suffix not in {".sqlite3", ".sqlite", ".db"}, f"database committed under {BASE.name}: {path.name}")


def validate_identity(contract: dict) -> None:
    require(set(contract) == EXPECTED_TOP_LEVEL_KEYS, "contract top-level key set drift")
    require(contract["pilot_id"] == PILOT_ID, "pilot identity drift")
    require(contract["status"] == "PREREGISTERED_NO_EXECUTION", "pilot status drift")
    require(contract["study_id"] == "WALLET-COPYABILITY-STUDY-001", "study identity drift")
    require(contract["schema_version"] == "1.0", "contract schema version drift")


def validate_preregistration_created_nothing(contract: dict) -> None:
    gates = contract["governance_gates"]
    require(gates["owner_approval_required_before_execution"] is True, "approval gate disabled")
    require(gates["single_use_release_required_before_execution"] is True, "release gate disabled")
    require(gates["canonical_implementation_merge_is_not_execution_release"] is True, "merge/release separation disabled")
    require(gates["exact_head_ci_required_before_merge"] is True, "exact-head CI gate disabled")
    require(gates["workflow_installation_authorized"] is False, "workflow installation opened")
    require(gates["scheduled_or_unattended_execution_authorized"] is False, "unattended execution opened")
    # Runtime authority lives in the owner decision, never in the preregistration.
    require(gates["manual_operator_run_authorized"] is False, "preregistration grants runtime authority")

    created = contract["created_by_this_preregistration"]
    for key in ("network_requests_executed", "rest_requests_executed", "websocket_connections_opened", "database_rows_written"):
        require(created[key] == 0, f"preregistration claims executed work: {key}")
    require(created["market_data_ingested"] is False, "preregistration market-data gate opened")
    require(created["empirical_result"] is None, "preregistration empirical result created")
    require(created["wallet_ranking_produced"] is False, "wallet ranking produced")
    require(created["copyability_claim_produced"] is False, "copyability claim produced")
    require(all(v is False for v in contract["downstream_authorizations"].values()), "downstream authorization opened")
    require(all(v is False for v in contract["trading_authorizations"].values()), "trading authorization opened")
    envelope = contract["proposed_request_envelope"]
    require(envelope["maximum_one_time_budget_eur"] == 0, "one-time budget opened")
    require(envelope["maximum_monthly_budget_eur"] == 0, "monthly budget opened")


def parse_approval_text() -> tuple[str, dict[str, str]]:
    raw = APPROVAL_TEXT.read_bytes()
    require(b"\r" not in raw, "approval text is not LF-only")
    require(raw.endswith(b"\n") and not raw.endswith(b"\n\n"), "approval text must end in exactly one LF")
    lines = raw.decode("utf-8").split("\n")[:-1]
    require(lines and lines[0] == APPROVAL_ID, "approval text does not start with the approval id")
    values: dict[str, str] = {}
    for line in lines[1:]:
        require("=" in line, f"approval line is not key=value: {line!r}")
        key, value = line.split("=", 1)
        require(key not in values, f"duplicate approval key: {key}")
        values[key] = value
    return sha256_of(APPROVAL_TEXT), values


def validate_owner_decision(contract: dict, core_config: Any) -> dict[str, Any]:
    text_sha, values = parse_approval_text()
    approval = contract["owner_approval_status"]
    require(approval["approval_id"] == APPROVAL_ID, "approval id drift")
    require(approval["approval_present"] is True, "approval recorded as absent")
    require(approval["approval_text_path"] == APPROVAL_TEXT.relative_to(ROOT).as_posix(), "approval text path drift")
    require(approval["approval_text_sha256"] == text_sha, "approval text hash does not match the retained text")
    require(approval["approval_timestamp_utc"] == "2026-09-03", "approval timestamp drift")
    commit = approval["bound_preregistration_commit"]
    require(isinstance(commit, str) and COMMIT_RE.match(commit) is not None, "bound commit is not a 40-hex sha")
    require(values.get("preregistration_commit") == commit, "approval text binds a different commit than recorded")
    require(approval["owner_decision_path"] == DECISION.relative_to(ROOT).as_posix(), "owner decision path drift")

    decision = load_json(DECISION)
    require(decision["decision_id"] == DECISION_ID and decision["pilot_id"] == PILOT_ID, "decision identity drift")
    require(decision["approval_id"] == APPROVAL_ID, "decision approval id drift")
    canonical = decision["canonical_text"]
    require(canonical["path"] == approval["approval_text_path"], "decision text path drift")
    require(canonical["sha256"] == text_sha, "decision text hash does not match the retained text")
    require(canonical["line_count"] == len(values) + 1, "decision line count drift")
    require(decision["bound_preregistration_commit"] == commit, "decision binds a different commit")
    require(decision["gates_granted_in_this_decision"] == EXPECTED_GATES_GRANTED, "granted gate set drift")
    precedent = decision["precedent"]
    require(precedent["applies_only_to_this_envelope"] is True, "precedent scope widened")
    for key in ("precedent_for_archive_track", "precedent_for_any_scope_that_costs_money",
                "precedent_for_any_scope_that_requires_authentication", "precedent_for_any_scope_that_trades"):
        require(precedent[key] is False, f"precedent opened: {key}")
    require(decision["risk_policy"]["integration_remains_false"] is True, "integration flag claimed")
    require(all(v is False for v in decision["trading_authorizations"].values()), "decision opens trading")
    require(decision["created_by_this_decision"]["network_requests_executed"] == 0, "decision claims executed requests")
    require(decision["created_by_this_decision"]["empirical_result"] is None, "decision claims empirical result")

    release = decision["execution_release"]
    require(release["release_id"] == RELEASE_ID, "release id drift")
    require(release["single_use"] is True, "release is not single-use")
    require(release["status"] in RELEASE_STATUSES, f"unknown release status {release['status']!r}")
    require(release["database_committed"] is False, "database committed")
    require(release["rerun_authorized"] is False, "rerun authorized")
    if release["status"] == "CONSUMED":
        require(isinstance(release["evidence_path"], str) and (ROOT / release["evidence_path"]).is_file(), "consumed release without retained evidence")
        require(release["consumed_by"] is not None, "consumed release names no session")
    else:
        require(release["evidence_path"] is None and release["consumed_by"] is None, "unconsumed release carries evidence")

    validate_approval_binds_the_code(values, contract, core_config)
    return decision


def validate_approval_binds_the_code(values: dict[str, str], contract: dict, core_config: Any) -> None:
    """Every key=value line the owner signed must equal what the code enforces."""
    target = contract["exact_network_target"]
    envelope = contract["proposed_request_envelope"]
    expected: dict[str, str] = {
        "venue": target["venue"],
        "rest_endpoint": core_config.DEFAULT_REST_BASE_URL + core_config.INFO_PATH,
        "websocket_endpoint": core_config.DEFAULT_WS_URL,
        "authentication": "NONE" if target["authentication_required"] is False else "REQUIRED",
        "maximum_one_time_budget_eur": str(envelope["maximum_one_time_budget_eur"]),
        "maximum_monthly_budget_eur": str(envelope["maximum_monthly_budget_eur"]),
        "enforced_weight_budget_per_minute": str(core_config.DEFAULT_WEIGHT_PER_MINUTE),
        "maximum_retries_per_request": str(core_config.LiveDataConfig().max_retries),
        "retryable_http_statuses": ",".join(str(s) for s in sorted(envelope["retryable_http_statuses"])),
        "retries_charged_against_weight_budget": str(envelope["retries_charged_against_weight_budget"]).lower(),
        "request_timeout_seconds": str(int(core_config.LiveDataConfig().request_timeout_seconds)),
        "maximum_tracked_wallets": str(core_config.MAX_WS_TRACKED_USERS),
        "snapshot_interval_seconds": str(int(core_config.DEFAULT_SNAPSHOT_INTERVAL_SECONDS)),
        "websocket_heartbeat_seconds": str(int(core_config.DEFAULT_WS_HEARTBEAT_SECONDS)),
        "maximum_watch_iterations": str(envelope["default_maximum_watch_iterations"]),
        "http_redirect_following_authorized": str(envelope["http_redirect_following_authorized"]).lower(),
        "rest_request_types": ",".join(sorted(contract["rest_request_type_allowlist"])),
        "order_endpoint_authorized": str(contract["read_only_boundary"]["order_endpoint_allowed"]).lower(),
        "signed_action_authorized": str(contract["read_only_boundary"]["signed_actions_allowed"]).lower(),
        "credential_use_authorized": str(contract["read_only_boundary"]["exchange_credentials_allowed"]).lower(),
        "workflow_installation_authorized": str(contract["governance_gates"]["workflow_installation_authorized"]).lower(),
        "scheduled_execution_authorized": str(contract["governance_gates"]["scheduled_or_unattended_execution_authorized"]).lower(),
        "wallet_ranking_authorized": str(contract["downstream_authorizations"]["wallet_ranking_authorized"]).lower(),
        "copyability_claim_authorized": str(contract["downstream_authorizations"]["copyability_claim_authorized"]).lower(),
        "trading_authorizations": "ALL_FALSE" if all(v is False for v in contract["trading_authorizations"].values()) else "OPENED",
    }
    require(set(values) == set(expected) | {"preregistration_commit"}, f"approval key set drift: {sorted(set(values) ^ (set(expected) | {'preregistration_commit'}))}")
    for key, value in expected.items():
        require(values[key] == value, f"approval line {key}={values[key]} does not match enforced {value}")


def validate_read_only_boundary(contract: dict, core_config: Any) -> None:
    boundary = contract["read_only_boundary"]
    require(boundary["read_only"] is True, "read-only boundary disabled")
    for key in ("exchange_credentials_allowed", "wallet_private_keys_allowed", "signed_actions_allowed",
                "order_endpoint_allowed", "order_submission_allowed", "live_orders_allowed",
                "paper_orders_allowed", "write_path_present_in_codebase"):
        require(boundary[key] is False, f"read-only boundary opened: {key}")
    require(core_config.READ_ONLY_REST_PATHS == frozenset({core_config.INFO_PATH}), "REST path allowlist is no longer exactly the info path")
    require(core_config.INFO_PATH == "/info", "info path drift")
    for path in sorted(CORE.glob("*.py")):
        require("/exchange" not in path.read_text(encoding="utf-8"), f"venue write path string present in core: {path.name}")
    target = contract["exact_network_target"]
    require(target["rest_base_url"] == core_config.DEFAULT_REST_BASE_URL, "REST base URL drift")
    require(target["websocket_url"] == core_config.DEFAULT_WS_URL, "websocket URL drift")
    require(target["rest_path_allowlist"] == [core_config.INFO_PATH], "declared REST allowlist drift")
    for key in ("authentication_required", "requester_pays", "aws_involved", "cloud_credentials_involved"):
        require(target[key] is False, f"network target opened: {key}")


def validate_envelope_matches_code(contract: dict, core_config: Any, core_rest: Any, core_cli: Any) -> None:
    envelope = contract["proposed_request_envelope"]
    require(envelope["documented_ip_weight_budget_per_minute"] == envelope["enforced_weight_budget_per_minute"] == core_config.DEFAULT_WEIGHT_PER_MINUTE, "weight budget drift between contract and code")
    require(envelope["maximum_tracked_wallets"] == core_config.MAX_WS_TRACKED_USERS, "tracked wallet cap drift")
    require(envelope["default_snapshot_interval_seconds"] == core_config.DEFAULT_SNAPSHOT_INTERVAL_SECONDS, "snapshot interval drift")
    require(envelope["websocket_heartbeat_seconds"] == core_config.DEFAULT_WS_HEARTBEAT_SECONDS, "heartbeat drift")
    require(envelope["websocket_server_timeout_seconds"] == core_config.WS_SERVER_TIMEOUT_SECONDS, "server timeout drift")
    require(envelope["websocket_heartbeat_seconds"] < envelope["websocket_server_timeout_seconds"], "heartbeat does not fire inside the server timeout")
    require(envelope["default_maximum_watch_iterations"] == core_cli.DEFAULT_MAX_WATCH_ITERATIONS, "watch iteration cap drift")
    require(envelope["maximum_fills_per_response"] == core_rest.MAX_FILLS_PER_RESPONSE, "fills-per-response cap drift")
    require(sorted(envelope["retryable_http_statuses"]) == sorted(core_rest.RETRYABLE_STATUSES), "retryable status set drift")
    require(envelope["retries_charged_against_weight_budget"] is True, "retry charging disabled")
    require(envelope["http_redirect_following_authorized"] is False, "redirect following opened")
    defaults = core_config.LiveDataConfig()
    require(envelope["maximum_retries_per_request"] == defaults.max_retries, "retry cap drift")
    require(envelope["request_timeout_seconds"] == defaults.request_timeout_seconds, "request timeout drift")
    declared_weights = dict(envelope["request_weights"])
    require(declared_weights.pop("unlisted_request_type_default") == core_rest.DEFAULT_REQUEST_WEIGHT, "default request weight drift")
    require(declared_weights == core_rest.INFO_REQUEST_WEIGHTS, "per-request weight table drift")
    snapshot_weight = core_rest.INFO_REQUEST_WEIGHTS["clearinghouseState"]
    expected_worst_case = core_config.MAX_WS_TRACKED_USERS * snapshot_weight
    require(envelope["worst_case_snapshot_weight_per_minute"] == expected_worst_case, "worst-case snapshot weight does not equal wallets x clearinghouseState weight")
    require(expected_worst_case <= core_config.DEFAULT_WEIGHT_PER_MINUTE, "worst-case snapshot cost exceeds the weight budget")


def validate_request_type_scope(contract: dict, core_rest: Any, core_ws: Any) -> None:
    require(sorted(contract["rest_request_type_allowlist"]) == sorted(core_rest.SUPPORTED_REQUEST_TYPES), "declared REST request type allowlist does not match the supported set")
    excluded = set(core_rest.INFO_REQUEST_WEIGHTS) - set(core_rest.SUPPORTED_REQUEST_TYPES)
    require(sorted(contract["rest_request_type_denylist_present_in_code"]) == sorted(excluded), "declared excluded request types do not match the code")
    require(sorted(contract["websocket_subscription_allowlist"]) == sorted(core_ws.SUBSCRIPTION_TYPES), "declared websocket subscription allowlist drift")


def validate_layering(contract: dict) -> None:
    layering = contract["layering_boundary"]
    require(layering["core_constructs_transports"] is False, "core declared to build transports")
    require(layering["transports_injected_by_caller"] is True, "transport injection disabled")
    require(layering["core_has_executable_entry_point"] is False, "core entry point declared")
    require(layering["core_import_side_effects"] is False, "core import side effects declared")
    require(layering["deterministic_core_path"] == CORE.relative_to(ROOT).as_posix(), f"declared core path is not {CORE.relative_to(ROOT).as_posix()}")
    require(layering["network_transport_path"] == COLLECTOR.relative_to(ROOT).as_posix(), f"declared transport path is not {COLLECTOR.relative_to(ROOT).as_posix()}")
    require(CORE.is_dir() and COLLECTOR.is_dir(), "layer path missing")
    forbidden = set(layering["forbidden_core_import_roots"])
    for path in sorted(CORE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".", 1)[0] for alias in node.names}
                require(roots.isdisjoint(forbidden), f"forbidden import in deterministic core: {path.name} imports {sorted(roots & forbidden)}")
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                require(node.module.split(".", 1)[0] not in forbidden, f"forbidden import in deterministic core: {path.name} imports {node.module}")
        for node in tree.body:
            if isinstance(node, ast.If):
                require("__main__" not in ast.dump(node.test), f"executable entry point in deterministic core: {path.name}")


def validate_retained_schema(contract: dict, core_config: Any, core_storage: Any) -> None:
    schema = contract["retained_schema"]
    require(schema["schema_version"] == core_storage.SCHEMA_VERSION, "storage schema version drift")
    require(schema["default_database_path"] == core_config.LiveDataConfig().database_path.as_posix(), "default database path drift")
    source = (CORE / "schema.py").read_text(encoding="utf-8")
    actual = {line.split("CREATE TABLE ", 1)[1].split()[0] for line in source.splitlines() if "CREATE TABLE " in line}
    require(set(schema["tables"]) == actual, f"declared tables {sorted(schema['tables'])} != created tables {sorted(actual)}")
    require(schema["idempotent_deduplication_required"] is True, "deduplication requirement dropped")
    require(schema["run_coverage_recorded"] is True, "coverage recording requirement dropped")
    require(schema["raw_response_bodies_retained"] is False, "raw body retention opened")
    privacy = contract["retention_and_privacy"]
    require(privacy["public_data_only"] is True, "non-public data admitted")
    require(privacy["real_world_identity_claim_allowed"] is False, "identity claim opened")
    require(privacy["personal_data_collected"] is False, "personal data collection opened")
    require(privacy["third_party_redistribution_authorized"] is False, "redistribution opened")


def validate_parent_bindings(contract: dict) -> None:
    parent = contract["parent_bindings"]
    require(parent["parent_probe_status"] == "ATTESTED_PUBLIC_PROBE_PASS", "parent probe gate drift")
    require(parent["parent_probe_run_id"] == 31200124642, "parent probe run drift")
    require(parent["archive_track_dependency"] is False, "archive dependency declared")
    require(parent["blocked_by_r11_unresolved"] is False, "R11 blockage declared")
    data_contract = load_json(ROOT / "research/wallet_copyability/DATA_CONTRACT.json")
    require(data_contract["market_data_ingested"] is False, "parent market-data release gate opened")
    require(data_contract["empirical_result"] is None, "parent empirical result created")
    require(data_contract["execution_boundary"]["read_only"] is True, "parent read-only gate disabled")
    require(all(v is False for v in data_contract["authorizations"].values()), "parent trading authorization opened")
    risk_policy = (ROOT / "RISK_POLICY.md").read_text(encoding="utf-8")
    require("| integration | `false` |" in risk_policy, "integration authorization changed")


def validate_session_evidence(decision: dict) -> dict[str, Any] | None:
    release = decision["execution_release"]
    if release["status"] != "CONSUMED":
        return None
    evidence = load_json(ROOT / release["evidence_path"])
    require(evidence["release_id"] == RELEASE_ID, "evidence release id drift")
    require(evidence["session_id"] == release["consumed_by"], "evidence session id drift")
    require(evidence["envelope_breached"] is False, "session breached the envelope")
    require(SHA256_RE.match(evidence["database"]["sha256"]) is not None, "database hash malformed")
    require(evidence["database"]["committed"] is False, "evidence claims a committed database")
    for key in ("wallets_discovered", "wallets_backfilled", "fills", "funding", "positions_snapshot", "trades", "mids"):
        require(isinstance(evidence["counts"][key], int) and evidence["counts"][key] >= 0, f"evidence count malformed: {key}")
    require(isinstance(evidence["request_weight"]["total"], int) and evidence["request_weight"]["total"] >= 0, "weight malformed")
    require(evidence["counts"]["wallets_backfilled"] <= 10, "more wallets backfilled than the envelope allows")
    for command in evidence["commands"]:
        require(command.get("max_iterations", 0) <= 1000, "watch exceeded the approved iteration cap")
    require(evidence["empirical_result"] is None, "evidence claims an empirical result")
    require(evidence["wallet_ranking_produced"] is False, "evidence claims a wallet ranking")
    return evidence


def validate_project_state(decision: dict) -> None:
    text = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
    consumed = decision["execution_release"]["status"] == "CONSUMED"
    for token in (
        "`HL-LIVE-DATA-COLLECTION-L1-001`",
        "l1_owner_approval_present = true",
        f"l1_approval_text_sha256 = {decision['canonical_text']['sha256']}",
        "l1_execution_release_present = true",
        f"l1_execution_release_consumed = {'true' if consumed else 'false'}",
        "l1_workflow_installed = false",
        "l1_scheduled_execution_authorized = false",
        "l1_rerun_authorized = false",
        "l1_database_committed = false",
        "l1_rest_requests_executed = ",
        "l1_websocket_connections_opened = ",
        "market_data_ingested = false",
        "empirical_result = null",
    ):
        require(token in text, f"project state L1 boundary missing: {token}")


def main() -> int:
    core_config, core_rest, core_ws, core_cli, core_storage = load_core_constants()
    contract = load_json(PREREG)

    validate_required_paths()
    validate_identity(contract)
    validate_preregistration_created_nothing(contract)
    decision = validate_owner_decision(contract, core_config)
    validate_read_only_boundary(contract, core_config)
    validate_envelope_matches_code(contract, core_config, core_rest, core_cli)
    validate_request_type_scope(contract, core_rest, core_ws)
    validate_layering(contract)
    validate_retained_schema(contract, core_config, core_storage)
    validate_parent_bindings(contract)
    evidence = validate_session_evidence(decision)
    validate_project_state(decision)

    release = decision["execution_release"]
    print(f"L1_PILOT:{PILOT_ID}")
    print(f"L1_STATUS:{contract['status']}")
    print(f"L1_OWNER_APPROVAL:PRESENT:{decision['canonical_text']['sha256']}")
    print(f"L1_BOUND_COMMIT:{decision['bound_preregistration_commit']}")
    print(f"L1_EXECUTION_RELEASE:{release['status']}")
    if evidence is not None:
        print(f"L1_SESSION_REQUEST_WEIGHT:{evidence['request_weight']['total']}")
        print(f"L1_SESSION_DATABASE_SHA256:{evidence['database']['sha256']}")
    print("L1_PREREGISTRATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
