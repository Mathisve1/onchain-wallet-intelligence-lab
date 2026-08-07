from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ACTIONS = {"PLACE_IOC_LIMIT", "REDUCE_ONLY_IOC", "CANCEL_BY_CLOID"}
EXPECTED_SAFETY_ACTIONS = {"CANCEL_BY_CLOID", "REDUCE_ONLY_IOC"}
REQUIRED_AI_FORBIDDEN = {
    "ACCESS_MASTER_PRIVATE_KEY",
    "DIRECTLY_ACCESS_SIGNER_KEY_MATERIAL",
    "DIRECTLY_CALL_RAW_EXCHANGE_ACTION_ENDPOINT",
    "TRANSFER_FUNDS",
    "WITHDRAW_FUNDS",
    "CHANGE_LEVERAGE_OR_MARGIN_MODE",
    "CHANGE_POLICY_OR_RISK_LIMIT",
    "CHANGE_ALLOWLIST",
    "OVERRIDE_BLOCK",
}
ALLOWED_PROTOTYPE_IMPORT_ROOTS = {
    "__future__", "dataclasses", "decimal", "hashlib", "json", "re", "typing"
}
FORBIDDEN_PROTOTYPE_IMPORT_ROOTS = {
    "urllib", "requests", "httpx", "websocket", "websockets", "socket",
    "subprocess", "hyperliquid", "eth_account", "web3"
}


class DesignValidationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DesignValidationError(message)


def load_json(name: str, root: Path = ROOT) -> dict[str, Any]:
    value = json.loads((root / name).read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{name}:root_not_object")
    return value


def _action_conditional(schema: dict[str, Any], action: str) -> dict[str, Any]:
    for row in schema.get("allOf", []):
        if not isinstance(row, dict):
            continue
        condition = row.get("if", {})
        try:
            if condition["properties"]["action"]["const"] == action:
                return row.get("then", {})
        except (KeyError, TypeError):
            continue
    raise DesignValidationError(f"schema:missing_conditional:{action}")


def _forbidden_required_fields(conditional: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    negative = conditional.get("not", {})
    if "required" in negative:
        result.update(negative["required"])
    for row in negative.get("anyOf", []):
        if isinstance(row, dict):
            result.update(row.get("required", []))
    return result


def _literal_assignment(source: str, name: str) -> Any:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise DesignValidationError(f"prototype:missing_literal_assignment:{name}")


def _validate_static_file(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            require(node.func.id not in {"eval", "exec", "compile"}, f"prototype:dynamic_execution:{path.name}:{node.func.id}")
    require(not (imports & FORBIDDEN_PROTOTYPE_IMPORT_ROOTS), f"prototype:forbidden_imports:{path.name}:{sorted(imports & FORBIDDEN_PROTOTYPE_IMPORT_ROOTS)}")
    require(imports <= ALLOWED_PROTOTYPE_IMPORT_ROOTS, f"prototype:unregistered_imports:{path.name}:{sorted(imports - ALLOWED_PROTOTYPE_IMPORT_ROOTS)}")


def validate_prototype_static(root: Path = ROOT) -> None:
    for rel in ("prototype/bounded_autonomy.py", "prototype/reconciliation.py"):
        _validate_static_file(root / rel)


def validate_documents(root: Path = ROOT) -> None:
    policy = load_json("BOUND_AUTONOMY_POLICY.json", root)
    surface = load_json("HYPERLIQUID_ACTION_SURFACE.json", root)
    experiment = load_json("EXECUTION_EXPERIMENT_CONTRACT.json", root)
    reconciliation = load_json("RECONCILIATION_CONTRACT.json", root)
    risk_schema = load_json("RISK_ENVELOPE.schema.json", root)
    intent_schema = load_json("TRADE_INTENT.schema.json", root)
    permit_schema = load_json("TRADE_PERMIT.schema.json", root)

    require(policy.get("status") == "DESIGN_STAGING_NO_EXECUTION_AUTHORIZATION", "policy:status")
    require(all(value is False for value in policy.get("current_authorizations", {}).values()), "policy:authorization_open")
    require(policy.get("deterministic_authority", {}).get("unknown_state_behavior") == "BLOCK", "policy:unknown_not_block")
    ai_forbidden = set(policy.get("ai", {}).get("always_forbidden", []))
    require(REQUIRED_AI_FORBIDDEN <= ai_forbidden, "policy:ai_forbidden_missing")

    require(surface.get("status") == "DESIGN_ONLY_ALL_ACTIONS_NON_EXECUTING", "surface:status")
    require(all(value is False for value in surface.get("current_authorization", {}).values()), "surface:authorization_open")
    surface_actions = {row["intent"] for row in surface.get("prospective_strategy_actions_after_separate_authorization", [])}
    require(surface_actions == EXPECTED_ACTIONS, f"surface:action_drift:{sorted(surface_actions)}")
    forbidden_surface = set(surface.get("forbidden_actions", []))
    require(not (surface_actions & forbidden_surface), "surface:allowed_forbidden_overlap")

    intent_actions = set(intent_schema["properties"]["action"]["enum"])
    permit_actions = set(permit_schema["properties"]["action"]["enum"])
    risk_actions = set(risk_schema["properties"]["allowed_actions"]["items"]["enum"])
    require(intent_actions == permit_actions == risk_actions == surface_actions == EXPECTED_ACTIONS, "schemas:action_parity")
    require(intent_schema["properties"]["schema_version"]["const"] == "0.3-design", "intent:schema_version")
    require(permit_schema["properties"]["schema_version"]["const"] == "0.3-design", "permit:schema_version")
    require(intent_schema.get("additionalProperties") is False and permit_schema.get("additionalProperties") is False, "schemas:not_closed")

    intent_modes = set(intent_schema["properties"]["decision_mode"]["enum"])
    permit_modes = set(permit_schema["properties"]["decision_mode"]["enum"])
    required_modes = {"DETERMINISTIC_ONLY", "DETERMINISTIC_PLUS_AI_CRITIC", "DETERMINISTIC_SAFETY"}
    require(intent_modes == permit_modes == required_modes, "schemas:decision_mode_parity")

    place_intent = _action_conditional(intent_schema, "PLACE_IOC_LIMIT")
    cancel_intent = _action_conditional(intent_schema, "CANCEL_BY_CLOID")
    cancel_permit = _action_conditional(permit_schema, "CANCEL_BY_CLOID")
    place_modes = set(place_intent["properties"]["decision_mode"]["enum"])
    require("DETERMINISTIC_SAFETY" not in place_modes, "intent:safety_can_open_risk")
    cancel_modes = set(cancel_intent["properties"]["decision_mode"]["enum"])
    require(cancel_modes == {"DETERMINISTIC_ONLY", "DETERMINISTIC_SAFETY"}, "intent:cancel_ai_mode_open")
    require({"side", "reduce_only", "requested_quantity", "limit_price", "max_slippage_bps", "model_version_hash", "ai_assessment"} <= _forbidden_required_fields(cancel_intent), "intent:cancel_dummy_or_ai_fields_not_forbidden")
    require({"side", "reduce_only", "quantity", "limit_price", "max_slippage_bps", "cloid", "venue_expires_after_ms", "model_version_hash"} <= _forbidden_required_fields(cancel_permit), "permit:cancel_dummy_or_ai_fields_not_forbidden")

    require(risk_schema["properties"]["max_unreconciled_actions"]["const"] == 0, "risk:unreconciled_not_zero")
    require(risk_schema["properties"]["human_governor_signature_required_for_activation"]["const"] is True, "risk:human_activation_not_required")

    require(experiment.get("schema_version") == "0.2-design", "experiment:schema_version")
    require(all(value is False for value in experiment.get("current_authorizations", {}).values()), "experiment:authorization_open")
    parent = experiment.get("parent_dependency", {})
    require(parent.get("owned_by_parallel_data_lane") is True, "experiment:parallel_lane_not_owned")
    require(parent.get("may_modify_parent_data_or_results") is False, "experiment:parent_mutation_open")
    require(parent.get("market_release_required_before_replay") is True, "experiment:replay_gate_open")
    require(parent.get("future_information_may_rewrite_historical_eligibility") is False, "experiment:lookahead_open")
    ai_rule = experiment.get("ai_incremental_value_rule", {})
    require(ai_rule.get("ai_can_expand_deterministic_eligible_set") is False, "experiment:ai_expands_eligibility")
    require(ai_rule.get("ai_can_raise_size") is False, "experiment:ai_raises_size")
    require(ai_rule.get("ai_can_widen_slippage") is False, "experiment:ai_widens_slippage")
    require(ai_rule.get("ai_can_extend_expiry") is False, "experiment:ai_extends_expiry")
    require(ai_rule.get("deterministic_safety_actions_bypass_ai_requirement") is True, "experiment:safety_ai_dependency")
    require(set(ai_rule.get("deterministic_safety_action_types", [])) == EXPECTED_SAFETY_ACTIONS, "experiment:safety_action_drift")
    require(ai_rule.get("deterministic_safety_may_open_new_risk") is False, "experiment:safety_can_open_risk")

    require(reconciliation.get("status") == "DESIGN_ONLY_NO_VENUE_ACTION", "reconciliation:status")
    require(all(value is False for value in reconciliation.get("current_authorizations", {}).values()), "reconciliation:authorization_open")
    require(reconciliation.get("risk_gate", {}).get("new_risk_requires_unresolved_risk_increasing_action_count") == 0, "reconciliation:risk_gate")
    require(reconciliation.get("risk_gate", {}).get("blind_resubmit_after_uncertainty_allowed") is False, "reconciliation:blind_retry_open")
    require(reconciliation.get("quantity_rules", {}).get("cancel_action_may_be_risk_increasing") is False, "reconciliation:cancel_risk_open")

    recon_source = (root / "prototype/reconciliation.py").read_text(encoding="utf-8")
    code_terminal = set(_literal_assignment(recon_source, "TERMINAL_STATES"))
    code_uncertain = set(_literal_assignment(recon_source, "UNCERTAIN_STATES"))
    transition_states = set(_literal_assignment(recon_source, "ALLOWED_TRANSITIONS"))
    require(code_terminal == set(reconciliation.get("terminal_states", [])), "reconciliation:terminal_state_parity")
    require(code_uncertain == set(reconciliation.get("uncertain_states", [])), "reconciliation:uncertain_state_parity")
    require(transition_states == set(reconciliation.get("states", [])), "reconciliation:state_surface_parity")

    validate_prototype_static(root)


def main() -> int:
    validate_documents()
    print("BOUNDED_AUTONOMY_DESIGN_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
