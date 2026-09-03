#!/usr/bin/env python3
"""Validate the L1 live-data collection preregistration.

The contract in ``L1_LIVE_DATA_COLLECTION_PREREGISTRATION.json`` makes claims
about what ``src/live_data`` can and cannot do. This validator refuses to take
those claims on trust: every numeric bound, endpoint, request type and import
restriction is re-derived from the source and compared. Drift in either
direction is a failure, so a widened envelope cannot be slipped past a stale
document and a tightened document cannot silently misdescribe live code.

It also checks that no gate has opened: no approval, no release, no workflow,
no executed request and no retained observation.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/wallet_copyability/live_data"
PREREG = BASE / "L1_LIVE_DATA_COLLECTION_PREREGISTRATION.json"
CORE = ROOT / "src/live_data"
COLLECTOR = ROOT / "research/wallet_copyability/live_data_collector"

PILOT_ID = "HL-LIVE-DATA-COLLECTION-L1-001"

REQUIRED_PATHS = {
    "research/wallet_copyability/live_data/README.md",
    "research/wallet_copyability/live_data/STATUS.md",
    "research/wallet_copyability/live_data/HUMAN_APPROVAL_TEMPLATE.md",
    "research/wallet_copyability/live_data/L1_LIVE_DATA_COLLECTION_PREREGISTRATION.md",
    "research/wallet_copyability/live_data/L1_LIVE_DATA_COLLECTION_PREREGISTRATION.json",
    "src/live_data/__init__.py",
    "src/live_data/cli.py",
    "src/live_data/config.py",
    "src/live_data/hyperliquid_rest.py",
    "src/live_data/hyperliquid_ws.py",
    "src/live_data/ingest.py",
    "src/live_data/models.py",
    "src/live_data/rate_limit.py",
    "src/live_data/results.py",
    "src/live_data/storage.py",
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

#: Paths that would prove an execution stage had begun without its gates.
FORBIDDEN_EXECUTION_ARTIFACTS = (
    "research/wallet_copyability/live_data/L1_EXECUTION_RELEASE.json",
    "research/wallet_copyability/live_data/evidence",
    "research/wallet_copyability/live_data/outputs",
    "research/live_data",
)


class ValidationError(SystemExit):
    def __init__(self, message: str) -> None:
        super().__init__(f"L1_PREREGISTRATION_INVALID: {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def load_core_constants() -> Any:
    """Import the deterministic core so its real constants can be compared."""
    sys.path.insert(0, str(ROOT / "src"))
    try:
        from live_data import config as core_config
        from live_data import hyperliquid_rest as core_rest
        from live_data import hyperliquid_ws as core_ws
        from live_data import cli as core_cli
        from live_data import storage as core_storage
    finally:
        sys.path.pop(0)
    return core_config, core_rest, core_ws, core_cli, core_storage


def validate_required_paths() -> None:
    for relative in sorted(REQUIRED_PATHS):
        require((ROOT / relative).is_file(), f"missing required path: {relative}")
    for relative in FORBIDDEN_EXECUTION_ARTIFACTS:
        require(
            not (ROOT / relative).exists(),
            f"execution artifact exists before approval and release: {relative}",
        )


def validate_identity(contract: dict) -> None:
    require(set(contract) == EXPECTED_TOP_LEVEL_KEYS, "contract top-level key set drift")
    require(contract["pilot_id"] == PILOT_ID, "pilot identity drift")
    require(contract["status"] == "PREREGISTERED_NO_EXECUTION", "pilot status drift")
    require(contract["study_id"] == "WALLET-COPYABILITY-STUDY-001", "study identity drift")
    require(contract["schema_version"] == "1.0", "contract schema version drift")


def validate_gates_closed(contract: dict) -> None:
    approval = contract["owner_approval_status"]
    require(approval["approval_present"] is False, "owner approval recorded by preregistration")
    require(approval["approval_text_sha256"] is None, "approval hash present without approval")
    require(approval["approval_timestamp_utc"] is None, "approval timestamp present without approval")
    require(approval["bound_preregistration_commit"] is None, "approval commit bound without approval")

    gates = contract["governance_gates"]
    require(gates["owner_approval_required_before_execution"] is True, "approval gate disabled")
    require(gates["single_use_release_required_before_execution"] is True, "release gate disabled")
    require(
        gates["canonical_implementation_merge_is_not_execution_release"] is True,
        "merge/release separation disabled",
    )
    require(gates["exact_head_ci_required_before_merge"] is True, "exact-head CI gate disabled")
    for key in (
        "workflow_installation_authorized",
        "scheduled_or_unattended_execution_authorized",
        "manual_operator_run_authorized",
    ):
        require(gates[key] is False, f"execution gate opened: {key}")

    created = contract["created_by_this_preregistration"]
    for key in (
        "network_requests_executed",
        "rest_requests_executed",
        "websocket_connections_opened",
        "database_rows_written",
    ):
        require(created[key] == 0, f"preregistration claims executed work: {key}")
    require(created["market_data_ingested"] is False, "market-data gate opened")
    require(created["empirical_result"] is None, "empirical result created")
    require(created["wallet_ranking_produced"] is False, "wallet ranking produced")
    require(created["copyability_claim_produced"] is False, "copyability claim produced")

    require(
        all(value is False for value in contract["downstream_authorizations"].values()),
        "downstream authorization opened",
    )
    require(
        all(value is False for value in contract["trading_authorizations"].values()),
        "trading authorization opened",
    )

    envelope = contract["proposed_request_envelope"]
    require(envelope["maximum_one_time_budget_eur"] == 0, "one-time budget opened")
    require(envelope["maximum_monthly_budget_eur"] == 0, "monthly budget opened")


def validate_read_only_boundary(contract: dict, core_config: Any) -> None:
    boundary = contract["read_only_boundary"]
    require(boundary["read_only"] is True, "read-only boundary disabled")
    for key in (
        "exchange_credentials_allowed",
        "wallet_private_keys_allowed",
        "signed_actions_allowed",
        "order_endpoint_allowed",
        "order_submission_allowed",
        "live_orders_allowed",
        "paper_orders_allowed",
        "write_path_present_in_codebase",
    ):
        require(boundary[key] is False, f"read-only boundary opened: {key}")

    # The claim "the write path is absent, not disabled" has to be true of the
    # source, not merely asserted in the document.
    require(
        core_config.READ_ONLY_REST_PATHS == frozenset({core_config.INFO_PATH}),
        "REST path allowlist is no longer exactly the info path",
    )
    require(core_config.INFO_PATH == "/info", "info path drift")
    for path in sorted(CORE.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        require("/exchange" not in text, f"venue write path string present in core: {path.name}")

    target = contract["exact_network_target"]
    require(target["rest_base_url"] == core_config.DEFAULT_REST_BASE_URL, "REST base URL drift")
    require(target["websocket_url"] == core_config.DEFAULT_WS_URL, "websocket URL drift")
    require(target["rest_path_allowlist"] == [core_config.INFO_PATH], "declared REST allowlist drift")
    require(target["authentication_required"] is False, "authentication declared required")
    require(target["requester_pays"] is False, "requester pays declared")
    require(target["aws_involved"] is False, "AWS declared involved")
    require(target["cloud_credentials_involved"] is False, "cloud credentials declared involved")


def validate_envelope_matches_code(
    contract: dict, core_config: Any, core_rest: Any, core_cli: Any
) -> None:
    envelope = contract["proposed_request_envelope"]
    require(
        envelope["documented_ip_weight_budget_per_minute"]
        == envelope["enforced_weight_budget_per_minute"]
        == core_config.DEFAULT_WEIGHT_PER_MINUTE,
        "weight budget drift between contract and code",
    )
    require(
        envelope["maximum_tracked_wallets"] == core_config.MAX_WS_TRACKED_USERS,
        "tracked wallet cap drift",
    )
    require(
        envelope["default_snapshot_interval_seconds"]
        == core_config.DEFAULT_SNAPSHOT_INTERVAL_SECONDS,
        "snapshot interval drift",
    )
    require(
        envelope["websocket_heartbeat_seconds"] == core_config.DEFAULT_WS_HEARTBEAT_SECONDS,
        "heartbeat drift",
    )
    require(
        envelope["websocket_server_timeout_seconds"] == core_config.WS_SERVER_TIMEOUT_SECONDS,
        "server timeout drift",
    )
    require(
        envelope["websocket_heartbeat_seconds"] < envelope["websocket_server_timeout_seconds"],
        "heartbeat does not fire inside the server timeout",
    )
    require(
        envelope["default_maximum_watch_iterations"] == core_cli.DEFAULT_MAX_WATCH_ITERATIONS,
        "watch iteration cap drift",
    )
    require(
        envelope["maximum_fills_per_response"] == core_rest.MAX_FILLS_PER_RESPONSE,
        "fills-per-response cap drift",
    )
    require(
        sorted(envelope["retryable_http_statuses"]) == sorted(core_rest.RETRYABLE_STATUSES),
        "retryable status set drift",
    )
    require(envelope["retries_charged_against_weight_budget"] is True, "retry charging disabled")
    require(envelope["http_redirect_following_authorized"] is False, "redirect following opened")

    defaults = core_config.LiveDataConfig()
    require(envelope["maximum_retries_per_request"] == defaults.max_retries, "retry cap drift")
    require(
        envelope["request_timeout_seconds"] == defaults.request_timeout_seconds,
        "request timeout drift",
    )

    declared_weights = dict(envelope["request_weights"])
    require(
        declared_weights.pop("unlisted_request_type_default") == core_rest.DEFAULT_REQUEST_WEIGHT,
        "default request weight drift",
    )
    require(declared_weights == core_rest.INFO_REQUEST_WEIGHTS, "per-request weight table drift")

    # The advertised worst case has to be arithmetic, not a hopeful number.
    snapshot_weight = core_rest.INFO_REQUEST_WEIGHTS["clearinghouseState"]
    expected_worst_case = core_config.MAX_WS_TRACKED_USERS * snapshot_weight
    require(
        envelope["worst_case_snapshot_weight_per_minute"] == expected_worst_case,
        "worst-case snapshot weight does not equal wallets x clearinghouseState weight",
    )
    require(
        expected_worst_case <= core_config.DEFAULT_WEIGHT_PER_MINUTE,
        "worst-case snapshot cost exceeds the weight budget",
    )


def validate_request_type_scope(contract: dict, core_rest: Any, core_ws: Any) -> None:
    require(
        sorted(contract["rest_request_type_allowlist"]) == sorted(core_rest.SUPPORTED_REQUEST_TYPES),
        "declared REST request type allowlist does not match the supported set",
    )
    excluded = set(core_rest.INFO_REQUEST_WEIGHTS) - set(core_rest.SUPPORTED_REQUEST_TYPES)
    require(
        sorted(contract["rest_request_type_denylist_present_in_code"]) == sorted(excluded),
        "declared excluded request types do not match the code",
    )
    require(
        sorted(contract["websocket_subscription_allowlist"]) == sorted(core_ws.SUBSCRIPTION_TYPES),
        "declared websocket subscription allowlist drift",
    )


def validate_layering(contract: dict) -> None:
    layering = contract["layering_boundary"]
    require(layering["core_constructs_transports"] is False, "core declared to build transports")
    require(layering["transports_injected_by_caller"] is True, "transport injection disabled")
    require(layering["core_has_executable_entry_point"] is False, "core entry point declared")
    require(layering["core_import_side_effects"] is False, "core import side effects declared")
    # The declared paths are what the import scan below is applied to, so they
    # must name the real core and the real transport layer. A contract that
    # points "core" at the transport package would otherwise describe a
    # restriction that was never checked against the code it governs.
    require(
        layering["deterministic_core_path"] == CORE.relative_to(ROOT).as_posix(),
        f"declared core path is not {CORE.relative_to(ROOT).as_posix()}",
    )
    require(
        layering["network_transport_path"] == COLLECTOR.relative_to(ROOT).as_posix(),
        f"declared transport path is not {COLLECTOR.relative_to(ROOT).as_posix()}",
    )
    require(CORE.is_dir(), "core path missing")
    require(COLLECTOR.is_dir(), "transport path missing")

    forbidden = set(layering["forbidden_core_import_roots"])
    for path in sorted(CORE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".", 1)[0] for alias in node.names}
                require(
                    roots.isdisjoint(forbidden),
                    f"forbidden import in deterministic core: {path.name} imports {sorted(roots & forbidden)}",
                )
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                root = node.module.split(".", 1)[0]
                require(
                    root not in forbidden,
                    f"forbidden import in deterministic core: {path.name} imports {root}",
                )
        # A module-level ``if __name__ == "__main__"`` block would make the core
        # runnable, which is exactly the dependency it refuses to take.
        for node in tree.body:
            if isinstance(node, ast.If):
                source = ast.dump(node.test)
                require(
                    "__main__" not in source,
                    f"executable entry point in deterministic core: {path.name}",
                )


def validate_retained_schema(contract: dict, core_config: Any, core_storage: Any) -> None:
    schema = contract["retained_schema"]
    require(schema["schema_version"] == core_storage.SCHEMA_VERSION, "storage schema version drift")
    require(
        schema["default_database_path"] == core_config.LiveDataConfig().database_path.as_posix(),
        "default database path drift",
    )
    declared = set(schema["tables"])
    source = (CORE / "storage.py").read_text(encoding="utf-8")
    actual = {
        line.split("CREATE TABLE ", 1)[1].split()[0]
        for line in source.splitlines()
        if "CREATE TABLE " in line
    }
    require(declared == actual, f"declared tables {sorted(declared)} != created tables {sorted(actual)}")
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

    # The parent study contract must not have been moved to accommodate L1.
    data_contract = json.loads(
        (ROOT / "research/wallet_copyability/DATA_CONTRACT.json").read_text(encoding="utf-8")
    )
    require(data_contract["market_data_ingested"] is False, "parent market-data gate opened")
    require(data_contract["empirical_result"] is None, "parent empirical result created")
    require(data_contract["execution_boundary"]["read_only"] is True, "parent read-only gate disabled")
    require(
        all(value is False for value in data_contract["authorizations"].values()),
        "parent trading authorization opened",
    )


def validate_project_state() -> None:
    text = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
    for token in (
        "`HL-LIVE-DATA-COLLECTION-L1-001`",
        "`PREREGISTERED_NO_EXECUTION`",
        "l1_owner_approval_present = false",
        "l1_execution_release_present = false",
        "l1_rest_requests_executed = 0",
        "l1_websocket_connections_opened = 0",
        "market_data_ingested = false",
        "empirical_result = null",
    ):
        require(token in text, f"project state L1 boundary missing: {token}")


def main() -> int:
    core_config, core_rest, core_ws, core_cli, core_storage = load_core_constants()
    contract = json.loads(PREREG.read_text(encoding="utf-8"))

    validate_required_paths()
    validate_identity(contract)
    validate_gates_closed(contract)
    validate_read_only_boundary(contract, core_config)
    validate_envelope_matches_code(contract, core_config, core_rest, core_cli)
    validate_request_type_scope(contract, core_rest, core_ws)
    validate_layering(contract)
    validate_retained_schema(contract, core_config, core_storage)
    validate_parent_bindings(contract)
    validate_project_state()

    print(f"L1_PILOT:{PILOT_ID}")
    print(f"L1_STATUS:{contract['status']}")
    print("L1_OWNER_APPROVAL:NOT_PRESENT")
    print("L1_EXECUTION_RELEASE:ABSENT")
    print("L1_NETWORK_REQUESTS_EXECUTED:0")
    print("L1_PREREGISTRATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
