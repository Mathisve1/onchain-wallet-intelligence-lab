from __future__ import annotations

import ast
import json
from pathlib import Path

from crypto_fixture_oracle import action_hash, agent_digest

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "prototype"
PINNED_SDK = "2fdb18f9517675ea03695a0962bd19eece9c83f0"
OFFLINE_PROVIDER_TOOLS = [
    "signature_backend_adapter.py",
    "provider_fixture_harness.py",
    "public_key_adapter.py",
    "provider_evidence_builder.py",
    "provider_evidence_cli.py",
]
FORBIDDEN_PROVIDER_IMPORT_ROOTS = {
    "requests", "urllib", "httpx", "socket", "websocket", "websockets",
    "boto3", "botocore", "google", "azure", "hyperliquid", "eth_account", "web3",
}


class CryptoFixtureValidationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CryptoFixtureValidationError(message)


def load(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def _scan_offline_provider_tool(name: str) -> None:
    source = (PROTOTYPE / name).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            require(node.func.id not in {"eval", "exec"}, f"provider_tool:dynamic_execution:{name}")
    forbidden = imports.intersection(FORBIDDEN_PROVIDER_IMPORT_ROOTS)
    require(not forbidden, f"provider_tool:network_or_provider_import:{name}:{sorted(forbidden)}")


def _block_committed_ephemeral_capture_instances() -> None:
    for path in ROOT.rglob("*.json"):
        name = path.name.lower()
        if "capture" in name and not name.endswith(".schema.json"):
            raise CryptoFixtureValidationError(f"ephemeral_capture_committed:{path.relative_to(ROOT)}")


def main() -> int:
    contract = load("CRYPTO_PARITY_CONTRACT.json")
    require(contract.get("schema_version") == "0.2-design", "contract:schema")
    require(contract.get("status") == "LOCAL_FIXTURE_PARITY_NO_SIGNER_AUTHORIZATION", "contract:status")
    require(contract.get("official_reference", {}).get("commit") == PINNED_SDK, "contract:sdk_pin")
    promotion = contract.get("promotion_constraints", {})
    for field in (
        "fixture_code_may_be_used_as_production_signer",
        "private_key_may_be_added_to_runtime",
        "provider_network_call_authorized",
        "testnet_action_authorized",
        "mainnet_action_authorized",
        "cloud_kms_backend_authorized",
        "mpc_backend_authorized",
    ):
        require(promotion.get(field) is False, f"contract:authorization_open:{field}")

    sources = load("SIGNER_BACKEND_SOURCE_REGISTER.json")
    require(sources.get("schema_version") == "0.2", "sources:schema")
    require(sources.get("status") == "DOCUMENTED_PREHASHED_PATHS_HANDS_ON_PARITY_NOT_RUN", "sources:status")
    require(sources.get("selection_status") == "UNSCORED", "sources:premature_selection")
    require(sources.get("provider_network_call_authorized") is False, "sources:provider_network_open")
    require(sources.get("testnet_authorized") is False, "sources:testnet_open")
    require(sources.get("live_authorized") is False, "sources:live_open")
    require(all(candidate.get("authorization") is False for candidate in sources.get("candidates", [])), "sources:candidate_open")

    authorization = load("SIGNER_PROVIDER_RUN_AUTHORIZATION.json")
    require(authorization.get("status") == "NOT_AUTHORIZED", "provider_authorization:status")
    require(authorization.get("provider_network_call_authorized") is False, "provider_authorization:network_open")
    require(all(value is False for value in authorization.get("providers", {}).values()), "provider_authorization:provider_open")
    require(authorization.get("budget", {}).get("maximum_one_time_spend") is None, "provider_authorization:budget_invented")
    require(authorization.get("budget", {}).get("maximum_recurring_spend") == "0", "provider_authorization:recurring_budget_open")
    require(authorization.get("credential_scope", {}).get("credentials_registered") is False, "provider_authorization:credentials_registered")
    require(authorization.get("hyperliquid_testnet_authorized") is False, "provider_authorization:testnet_open")
    require(authorization.get("hyperliquid_mainnet_authorized") is False, "provider_authorization:mainnet_open")
    require(authorization.get("capital_allocation_authorized") is False, "provider_authorization:capital_open")

    cost_proposal = load("SIGNER_PROVIDER_COST_PROPOSAL.json")
    require(cost_proposal.get("status") == "PROPOSAL_ONLY_NOT_AUTHORIZED", "cost_proposal:status")
    require(cost_proposal.get("provider_network_call_authorized") is False, "cost_proposal:provider_network_open")
    require(cost_proposal.get("provider_spend_authorized") is False, "cost_proposal:spend_open")
    require(cost_proposal.get("human_governor_approval_required") is True, "cost_proposal:human_gate_missing")
    envelope = cost_proposal.get("hard_proposed_envelope", {})
    require(envelope.get("currency") == "EUR", "cost_proposal:currency")
    require(envelope.get("maximum_total_one_time_spend") == "5.00", "cost_proposal:microbudget_drift")
    require(envelope.get("maximum_recurring_spend") == "0", "cost_proposal:recurring_open")
    require(envelope.get("maximum_sign_requests_per_provider") == 150, "cost_proposal:request_cap_drift")
    require(envelope.get("maximum_sign_requests_total") == 450, "cost_proposal:total_request_cap_drift")
    require(cost_proposal.get("proposal_does_not_authorize", {}).get("provider_network_calls") is True, "cost_proposal:network_semantics")
    require(cost_proposal.get("proposal_does_not_authorize", {}).get("provider_spend") is True, "cost_proposal:spend_semantics")
    require(cost_proposal.get("proposal_does_not_authorize", {}).get("hyperliquid_testnet") is True, "cost_proposal:testnet_semantics")

    capture_schema = load("SIGNER_BACKEND_CAPTURE_INPUT.schema.json")
    require(capture_schema.get("$id", "").endswith("capture-input:0.3"), "capture_schema:id")
    require(capture_schema.get("additionalProperties") is False, "capture_schema:not_closed")
    require(set(capture_schema["properties"]["public_key_format"]["enum"]) == {"SPKI_DER_BASE64", "JWK_XY_BASE64URL"}, "capture_schema:public_key_formats")

    evidence_schema = load("SIGNER_BACKEND_EVIDENCE.schema.json")
    require(evidence_schema.get("$id", "").endswith("evidence:0.4"), "evidence_schema:id")
    require(evidence_schema.get("additionalProperties") is False, "evidence_schema:not_closed")
    require(evidence_schema["properties"]["provider_network_call_authorized_after_evidence"].get("const") is False, "evidence_schema:provider_network_open")
    require(evidence_schema["properties"]["testnet_action_authorized"].get("const") is False, "evidence_schema:testnet_open")
    require(evidence_schema["properties"]["live_action_authorized"].get("const") is False, "evidence_schema:live_open")

    fixture_doc = load("PROVIDER_PARITY_FIXTURES.json")
    require(fixture_doc.get("official_sdk_pin") == PINNED_SDK, "fixtures:sdk_pin")
    require(fixture_doc.get("provider_network_call_authorized") is False, "fixtures:provider_network_open")
    require(fixture_doc.get("hyperliquid_testnet_authorized") is False, "fixtures:testnet_open")
    require(fixture_doc.get("hyperliquid_mainnet_authorized") is False, "fixtures:mainnet_open")

    fixtures = fixture_doc.get("fixtures", [])
    require(len(fixtures) == 8, "fixtures:unexpected_count")
    identifiers = [fixture.get("id") for fixture in fixtures]
    require(len(set(identifiers)) == len(identifiers), "fixtures:duplicate_id")

    for fixture in fixtures:
        action = fixture["action"]
        nonce = fixture["nonce"]
        vault = fixture["vault_address"]
        expires = fixture["expires_after"]
        is_mainnet = fixture["network"] == "MAINNET"
        require(fixture["network"] in {"MAINNET", "TESTNET"}, f"fixtures:network:{fixture['id']}")
        observed_action_hash = action_hash(action, vault, nonce, expires).hex()
        require(observed_action_hash == fixture["action_hash"], f"fixtures:action_hash:{fixture['id']}")
        observed_digest = agent_digest(bytes.fromhex(observed_action_hash), is_mainnet).hex()
        require(observed_digest == fixture["eip712_digest"], f"fixtures:digest:{fixture['id']}")

    for name in OFFLINE_PROVIDER_TOOLS:
        require((PROTOTYPE / name).is_file(), f"provider_tool:missing:{name}")
        _scan_offline_provider_tool(name)

    _block_committed_ephemeral_capture_instances()

    print("BOUNDED_AUTONOMY_CRYPTO_FIXTURE_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
