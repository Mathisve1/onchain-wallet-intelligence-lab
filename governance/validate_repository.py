#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHA_ROW = re.compile(r"^([0-9a-f]{64})  (.+)$")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"REPOSITORY_VALIDATION_FAIL: {message}")


def load_json(relative_path: str) -> dict:
    path = ROOT / relative_path
    return json.loads(path.read_text())


def validate_manifest() -> None:
    manifest = ROOT / "governance/REPOSITORY_MANIFEST.sha256"
    seen: set[str] = set()
    for line in manifest.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        match = SHA_ROW.fullmatch(line)
        require(match is not None, f"invalid manifest row: {line}")
        expected, rel = match.groups()
        require(rel not in seen, f"duplicate manifest path: {rel}")
        seen.add(rel)
        path = ROOT / rel
        require(path.is_file(), f"missing manifest target: {rel}")
        observed = hashlib.sha256(path.read_bytes()).hexdigest()
        require(observed == expected, f"manifest mismatch: {rel}")

    required_new_paths = {
        "AI_HANDOVER.md",
        "governance/BOUND_AUTONOMY_POLICY.json",
        "governance/RESEARCH_REGISTRY.json",
        "governance/adr/ADR-BOUND-AUTONOMY-001.md",
        "research/bounded_autonomy/EXPERIMENT_CONTRACT.json",
        "research/bounded_autonomy/PREREGISTRATION.md",
        "research/bounded_autonomy/THREAT_MODEL.md",
        "research/bounded_autonomy/EXECUTION_ARCHITECTURE.md",
        "research/bounded_autonomy/AUTHORIZATION_MATRIX.json",
        "research/bounded_autonomy/TRADE_INTENT_CONTRACT.json",
        "tests/test_bounded_autonomy_governance.py",
    }
    require(
        required_new_paths.issubset(seen),
        "bounded-autonomy paths absent from manifest",
    )


def validate_parent_contract() -> None:
    contract = load_json("research/wallet_copyability/DATA_CONTRACT.json")
    require(contract["market_data_ingested"] is False, "market-data gate opened")
    require(contract["empirical_result"] is None, "empirical result created")
    require(
        contract["execution_boundary"]["read_only"] is True,
        "read-only gate disabled",
    )
    require(
        all(value is False for value in contract["authorizations"].values()),
        "parent authorization opened",
    )


def validate_research_registry() -> None:
    registry = load_json("governance/RESEARCH_REGISTRY.json")
    require(
        registry["program_id"] == "ONCHAIN-WALLET-INTELLIGENCE",
        "wrong research program",
    )
    require(
        registry["current_active_gate"]["gate_id"] == "HL-PUBLIC-PROBE-001R1",
        "active technical gate changed",
    )
    require(
        all(value is False for value in registry["authorizations"].values()),
        "registry authorization opened",
    )
    studies = {item["study_id"]: item for item in registry["studies"]}
    require(
        set(studies)
        == {"WALLET-COPYABILITY-STUDY-001", "DEX-COPY-AUTONOMY-001"},
        "research registry study set changed",
    )
    require(
        studies["WALLET-COPYABILITY-STUDY-001"]["parent_study"] is None,
        "parent study unexpectedly linked",
    )
    require(
        studies["DEX-COPY-AUTONOMY-001"]["parent_study"]
        == "WALLET-COPYABILITY-STUDY-001",
        "autonomy study parent mismatch",
    )
    require(
        studies["DEX-COPY-AUTONOMY-001"]["empirical_result"] is None,
        "autonomy empirical result created",
    )


def validate_bounded_autonomy_policy() -> None:
    policy = load_json("governance/BOUND_AUTONOMY_POLICY.json")
    require(policy["policy_id"] == "BOUND-AUTONOMY-POLICY-001", "wrong policy id")
    require(
        policy["research_track"] == "DEX-COPY-AUTONOMY-001",
        "wrong research track",
    )
    require(
        policy["current_maximum_stage"] == "RESEARCH",
        "execution stage opened",
    )
    require(
        policy["execution_controls"]["unknown_state_behavior"] == "BLOCK",
        "unknown state not blocked",
    )
    require(
        policy["execution_controls"]["llm_direct_key_access"] is False,
        "LLM key access opened",
    )
    require(
        policy["execution_controls"]["llm_direct_action_endpoint_access"] is False,
        "LLM action endpoint opened",
    )
    require(
        policy["live_risk_parameters"]["state"] == "UNSET_LIVE_BLOCKER",
        "live risk parameters unexpectedly set",
    )

    authorizations = policy["current_authorizations"]
    require(
        authorizations["governance_research_authorized"] is True,
        "governance research not authorized",
    )
    for key, value in authorizations.items():
        if key != "governance_research_authorized":
            require(value is False, f"execution authorization opened: {key}")

    forbidden = set(policy["ai_boundary"]["always_forbidden"])
    required_forbidden = {
        "ACCESS_MASTER_PRIVATE_KEY",
        "DIRECTLY_CALL_ACTION_ENDPOINT",
        "TRANSFER_FUNDS",
        "WITHDRAW_FUNDS",
        "CHANGE_LEVERAGE_OR_MARGIN_MODE",
        "CHANGE_POLICY_OR_RISK_LIMIT",
        "CHANGE_ALLOWLIST",
        "OVERRIDE_BLOCK",
    }
    require(
        required_forbidden.issubset(forbidden),
        "AI forbidden-capability set incomplete",
    )


def validate_experiment_contract() -> None:
    contract = load_json("research/bounded_autonomy/EXPERIMENT_CONTRACT.json")
    require(
        contract["contract_id"] == "DEX_COPY_AUTONOMY_EXPERIMENT_CONTRACT_V1",
        "wrong experiment contract",
    )
    require(
        contract["study_id"] == "DEX-COPY-AUTONOMY-001",
        "wrong experiment study",
    )
    require(
        contract["parent_study"] == "WALLET-COPYABILITY-STUDY-001",
        "wrong experiment parent",
    )
    require(contract["stage"] == "RESEARCH", "experiment stage opened")
    require(
        contract["data_boundary"]["empirical_result"] is None,
        "autonomy result created",
    )
    require(
        contract["data_boundary"]["market_data_ingested_under_this_contract"]
        is False,
        "autonomy market-data gate opened",
    )
    require(
        all(value is False for value in contract["authorizations"].values()),
        "autonomy experiment authorization opened",
    )
    require(
        contract["latency_arms_milliseconds"]
        == [
            200,
            1000,
            3000,
            5000,
            10000,
            15000,
            30000,
            60000,
            120000,
            300000,
        ],
        "latency grid changed",
    )
    require(
        contract["ai_incremental_value_boundary"]["ai_arm_can_raise_risk_or_size"]
        is False,
        "AI can raise risk or size",
    )
    require(
        contract["parent_immutability"]["parent_signal_set_can_be_rewritten"]
        is False,
        "parent signal set can be rewritten",
    )
    require(
        contract["live_risk_parameters"]["state"] == "UNSET_LIVE_BLOCKER",
        "experiment live limits unexpectedly set",
    )


def validate_authorization_matrix() -> None:
    matrix = load_json("research/bounded_autonomy/AUTHORIZATION_MATRIX.json")
    require(
        matrix["current_maximum_stage"] == "RESEARCH",
        "matrix stage opened",
    )
    require(
        matrix["automatic_promotion"] is False,
        "automatic promotion enabled",
    )
    require(
        matrix["positive_result_can_change_authorization"] is False,
        "positive result can promote authorization",
    )
    require(
        matrix["missing_state_behavior"] == "DENY",
        "missing state not denied",
    )

    states = matrix["states"]
    allowed_true = {
        "governance_and_architecture_research",
        "public_read_only_probe",
    }
    for key, record in states.items():
        if key in allowed_true:
            require(
                record["authorized"] is True,
                f"expected research scope closed: {key}",
            )
        else:
            require(record["authorized"] is False, f"execution scope opened: {key}")


def validate_trade_intent_contract() -> None:
    contract = load_json("research/bounded_autonomy/TRADE_INTENT_CONTRACT.json")
    require(
        contract["status"] == "DESIGN_ONLY_NO_EXECUTION_AUTHORIZATION",
        "trade-intent contract represented as executable",
    )
    require(
        contract["additional_fields_allowed"] is False,
        "open intent schema",
    )
    require(
        contract["allowed_values"]["order_type"] == ["IOC_LIMIT"],
        "unbounded order type allowed",
    )
    forbidden = set(contract["always_forbidden_action_types"])
    required = {
        "TRANSFER",
        "WITHDRAW",
        "APPROVE_AGENT",
        "UPDATE_LEVERAGE",
        "ARBITRARY_EXCHANGE_ACTION",
    }
    require(required.issubset(forbidden), "forbidden action set incomplete")
    require(
        contract["permit_rules"]["single_use"] is True,
        "reusable permit allowed",
    )
    require(
        contract["permit_rules"]["mutation_invalidates_permit"] is True,
        "permit mutation not invalidating",
    )


def validate_sources_and_docs() -> None:
    register = load_json("research/bounded_autonomy/OFFICIAL_SOURCE_REGISTER.json")
    require(
        register["status"]
        == "CAPABILITY_CLAIMS_ONLY_NO_VENDOR_SECURITY_OR_PROFITABILITY_PROOF",
        "vendor sources promoted beyond capability claims",
    )
    require(
        register["rules"]["vendor_claim_is_independent_audit"] is False,
        "vendor claim treated as independent audit",
    )
    require(
        register["rules"]["vendor_claim_is_profitability_evidence"] is False,
        "vendor claim treated as profitability evidence",
    )
    sources = register["sources"]
    require(len(sources) >= 10, "official source register incomplete")
    require(
        len({item["source_id"] for item in sources}) == len(sources),
        "duplicate bounded-autonomy source id",
    )

    decisions = (ROOT / "DECISION_LOG.md").read_text()
    for decision_id in (
        "DEC-010",
        "DEC-011",
        "DEC-012",
        "DEC-013",
        "DEC-014",
        "DEC-015",
    ):
        require(decision_id in decisions, f"missing decision: {decision_id}")

    adr = (ROOT / "governance/adr/ADR-BOUND-AUTONOMY-001.md").read_text()
    require(
        "Live execution authorization" in adr and "`false`" in adr,
        "ADR live boundary missing",
    )
    require(
        "Silence, elapsed time" in adr,
        "ADR promotion semantics incomplete",
    )

    handover = (ROOT / "AI_HANDOVER.md").read_text()
    require(
        "HL-PUBLIC-PROBE-001R1" in handover,
        "handover lost active technical gate",
    )
    require(
        "No profitability, copyable-alpha or execution claim exists" in handover,
        "handover overstates empirical state",
    )
    require(
        "no positive backtest represented as authorization" in handover,
        "handover promotion prohibition missing",
    )


def main() -> int:
    validate_manifest()
    validate_parent_contract()
    validate_research_registry()
    validate_bounded_autonomy_policy()
    validate_experiment_contract()
    validate_authorization_matrix()
    validate_trade_intent_contract()
    validate_sources_and_docs()
    print("REPOSITORY_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
