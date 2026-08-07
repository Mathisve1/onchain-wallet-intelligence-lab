from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "prototype"
PURE_FILES = [
    "durable_store.py",
    "permit_service.py",
    "restricted_signer.py",
    "fake_venue.py",
    "offline_executor.py",
    "hyperliquid_wire.py",
]
FORBIDDEN_IMPORTS = {
    "requests", "urllib", "httpx", "socket", "websocket", "websockets",
    "hyperliquid", "eth_account", "web3", "boto3", "google", "azure",
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


def scan_python(name: str) -> None:
    source = (PROTOTYPE / name).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            require(node.func.id not in {"eval", "exec"}, f"{name}:dynamic_execution")
    require(not imports.intersection(FORBIDDEN_IMPORTS), f"{name}:forbidden_import:{sorted(imports.intersection(FORBIDDEN_IMPORTS))}")
    for marker in FORBIDDEN_SOURCE_MARKERS:
        require(marker not in source, f"{name}:forbidden_marker:{marker}")


def main() -> int:
    for name in PURE_FILES:
        require((PROTOTYPE / name).is_file(), f"missing:{name}")
        scan_python(name)

    permit_contract = load("PERMIT_SERVICE_CONTRACT.json")
    require(permit_contract.get("status") == "DESIGN_ONLY_NO_SIGNING_OR_NETWORK", "permit_contract:status")
    require(all(v is False for v in permit_contract.get("current_authorizations", {}).values()), "permit_contract:authorization_open")
    require(permit_contract.get("single_use") is True, "permit_contract:not_single_use")
    require(permit_contract.get("durability_target", {}).get("journal_before_signature_release") is True, "permit_contract:journal_order")

    surface = load("HYPERLIQUID_ACTION_SURFACE.json")
    require(all(v is False for v in surface.get("current_authorization", {}).values()), "surface:authorization_open")

    reconciliation = load("RECONCILIATION_CONTRACT.json")
    require(all(v is False for v in reconciliation.get("current_authorizations", {}).values()), "reconciliation:authorization_open")
    require(reconciliation.get("risk_gate", {}).get("blind_resubmit_after_uncertainty_allowed") is False, "reconciliation:blind_retry")

    golden = (ROOT / "GOLDEN_HYPERLIQUID_SERIALIZATION.md").read_text(encoding="utf-8")
    require(PINNED_SDK_COMMIT in golden, "golden:sdk_pin_missing")
    require("hashlib.sha3_256" in golden and "not" in golden.lower(), "golden:keccak_warning_missing")

    signer = (PROTOTYPE / "restricted_signer.py").read_text(encoding="utf-8")
    require("SIMULATED_NON_SIGNATURE_V1" in signer, "signer:not_explicitly_simulated")
    require("eth_account" not in signer and "private_key" not in signer.lower(), "signer:real_key_surface")

    durable = (PROTOTYPE / "durable_store.py").read_text(encoding="utf-8")
    require("PRAGMA synchronous=FULL" in durable, "store:not_full_sync")
    require("PRAGMA journal_mode=WAL" in durable, "store:not_wal")
    require("audit_events_append_only" in durable, "store:audit_trigger_missing")
    require("UNIQUE(signer_id, nonce)" in durable, "store:nonce_uniqueness_missing")

    wire = (PROTOTYPE / "hyperliquid_wire.py").read_text(encoding="utf-8")
    require("Ioc" in wire and "Gtc" not in wire and "Alo" not in wire, "wire:entry_tif_surface_drift")

    print("BOUNDED_AUTONOMY_EXECUTION_SPRINT_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
