from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "prototype"
RUNTIME_FILES = [
    "durable_store.py",
    "permit_service.py",
    "restricted_signer.py",
    "fake_venue.py",
    "offline_executor.py",
    "hyperliquid_wire.py",
]
FIXTURE_ONLY_MODULES = {"crypto_fixture_oracle", "signature_backend_adapter"}
FORBIDDEN_IMPORTS = {
    "requests", "urllib", "httpx", "socket", "websocket", "websockets",
    "hyperliquid", "eth_account", "web3", "boto3", "botocore", "google", "azure",
}
FORBIDDEN_SOURCE_MARKERS = [
    "PRIVATE_KEY",
    "seed phrase",
    "wallet.sign_message",
    "self.post(\"/exchange\"",
]
PINNED_SDK_COMMIT = "2fdb18f9517675ea03695a0962bd19eece9c83f0"


class ValidationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def load(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def scan_runtime_python(name: str) -> set[str]:
    source = (PROTOTYPE / name).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            require(node.func.id not in {"eval", "exec"}, f"{name}:dynamic_execution")
    require(
        not imports.intersection(FORBIDDEN_IMPORTS),
        f"{name}:forbidden_import:{sorted(imports.intersection(FORBIDDEN_IMPORTS))}",
    )
    require(
        not imports.intersection(FIXTURE_ONLY_MODULES),
        f"{name}:fixture_crypto_imported_into_runtime:{sorted(imports.intersection(FIXTURE_ONLY_MODULES))}",
    )
    for marker in FORBIDDEN_SOURCE_MARKERS:
        require(marker not in source, f"{name}:forbidden_marker:{marker}")
    return imports


def scan_fixture_boundaries() -> None:
    crypto = (PROTOTYPE / "crypto_fixture_oracle.py").read_text(encoding="utf-8")
    adapter = (PROTOTYPE / "signature_backend_adapter.py").read_text(encoding="utf-8")
    require("TEST-ONLY" in crypto, "crypto_fixture:not_marked_test_only")
    require("msgpack" in crypto, "crypto_fixture:msgpack_missing")
    require("keccak256" in crypto and "agent_digest" in crypto, "crypto_fixture:parity_primitives_missing")
    require("recover_address" in adapter, "signature_adapter:recovery_missing")
    require("adapt_der_signature" in adapter, "signature_adapter:der_missing")
    require("adapt_p1363_signature" in adapter, "signature_adapter:p1363_missing")
    for forbidden in ("requests", "urllib", "httpx", "websocket", "boto3", "botocore", "google.cloud", "azure."):
        require(forbidden not in crypto and forbidden not in adapter, f"fixture:network_provider_import:{forbidden}")


def main() -> int:
    for name in RUNTIME_FILES:
        require((PROTOTYPE / name).is_file(), f"missing:{name}")
        scan_runtime_python(name)

    permit_contract = load("PERMIT_SERVICE_CONTRACT.json")
    require(permit_contract.get("status") == "DESIGN_ONLY_NO_SIGNING_OR_NETWORK", "permit_contract:status")
    require(all(v is False for v in permit_contract.get("current_authorizations", {}).values()), "permit_contract:authorization_open")
    require(permit_contract.get("single_use") is True, "permit_contract:not_single_use")
    require(
        permit_contract.get("durability_target", {}).get("journal_before_signature_release") is True,
        "permit_contract:journal_order",
    )

    surface = load("HYPERLIQUID_ACTION_SURFACE.json")
    require(all(v is False for v in surface.get("current_authorization", {}).values()), "surface:authorization_open")

    reconciliation = load("RECONCILIATION_CONTRACT.json")
    require(all(v is False for v in reconciliation.get("current_authorizations", {}).values()), "reconciliation:authorization_open")
    require(
        reconciliation.get("risk_gate", {}).get("blind_resubmit_after_uncertainty_allowed") is False,
        "reconciliation:blind_retry",
    )

    crypto_contract = load("CRYPTO_PARITY_CONTRACT.json")
    require(
        crypto_contract.get("status") == "LOCAL_FIXTURE_PARITY_NO_SIGNER_AUTHORIZATION",
        "crypto_contract:status",
    )
    promotion = crypto_contract.get("promotion_constraints", {})
    for field in (
        "fixture_code_may_be_used_as_production_signer",
        "private_key_may_be_added_to_runtime",
        "provider_network_call_authorized",
        "testnet_action_authorized",
        "mainnet_action_authorized",
        "cloud_kms_backend_authorized",
        "mpc_backend_authorized",
    ):
        require(promotion.get(field) is False, f"crypto_contract:authorization_open:{field}")

    backend_sources = load("SIGNER_BACKEND_SOURCE_REGISTER.json")
    require(backend_sources.get("status") == "DOCUMENTED_PREHASHED_PATHS_HANDS_ON_PARITY_NOT_RUN", "backend_sources:status")
    require(backend_sources.get("selection_status") == "UNSCORED", "backend_sources:premature_selection")
    require(backend_sources.get("provider_network_call_authorized") is False, "backend_sources:provider_network_open")
    require(backend_sources.get("testnet_authorized") is False, "backend_sources:testnet_open")
    require(backend_sources.get("live_authorized") is False, "backend_sources:live_open")
    require(all(candidate.get("authorization") is False for candidate in backend_sources.get("candidates", [])), "backend_sources:candidate_authorized")

    provider_gate = load("SIGNER_PROVIDER_RUN_AUTHORIZATION.json")
    require(provider_gate.get("status") == "NOT_AUTHORIZED", "provider_gate:status")
    require(provider_gate.get("provider_network_call_authorized") is False, "provider_gate:network_open")
    require(all(v is False for v in provider_gate.get("providers", {}).values()), "provider_gate:provider_selected_without_auth")
    budget = provider_gate.get("budget", {})
    require(budget.get("maximum_one_time_spend") is None, "provider_gate:one_time_budget_invented")
    require(budget.get("maximum_recurring_spend") == "0", "provider_gate:recurring_budget_open")
    require(budget.get("maximum_provider_sign_requests") is None, "provider_gate:request_budget_invented")
    require(provider_gate.get("credential_scope", {}).get("credentials_registered") is False, "provider_gate:credentials_registered")
    require(provider_gate.get("hyperliquid_testnet_authorized") is False, "provider_gate:testnet_open")
    require(provider_gate.get("hyperliquid_mainnet_authorized") is False, "provider_gate:mainnet_open")
    require(provider_gate.get("capital_allocation_authorized") is False, "provider_gate:capital_open")

    golden = (ROOT / "GOLDEN_HYPERLIQUID_SERIALIZATION.md").read_text(encoding="utf-8")
    require(PINNED_SDK_COMMIT in golden, "golden:sdk_pin_missing")
    require("hashlib.sha3_256" in golden and "not" in golden.lower(), "golden:keccak_warning_missing")
    require("MSGPACK" in golden.upper() and "insertion order" in golden.lower(), "golden:field_order_warning_missing")
    require("G4B" in golden and "OPEN" in golden, "golden:backend_gate_missing")

    signer = (PROTOTYPE / "restricted_signer.py").read_text(encoding="utf-8")
    require("SIMULATED_NON_SIGNATURE_V1" in signer, "signer:not_explicitly_simulated")
    require("eth_account" not in signer and "private_key" not in signer.lower(), "signer:real_key_surface")
    require("crypto_fixture_oracle" not in signer and "signature_backend_adapter" not in signer, "signer:fixture_crypto_leak")

    durable = (PROTOTYPE / "durable_store.py").read_text(encoding="utf-8")
    require("PRAGMA synchronous=FULL" in durable, "store:not_full_sync")
    require("PRAGMA journal_mode=WAL" in durable, "store:not_wal")
    require("audit_events_append_only" in durable, "store:audit_trigger_missing")
    require("UNIQUE(signer_id, nonce)" in durable, "store:nonce_uniqueness_missing")

    wire = (PROTOTYPE / "hyperliquid_wire.py").read_text(encoding="utf-8")
    require("Ioc" in wire and "Gtc" not in wire and "Alo" not in wire, "wire:entry_tif_surface_drift")

    scan_fixture_boundaries()

    print("BOUNDED_AUTONOMY_EXECUTION_SPRINT_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
