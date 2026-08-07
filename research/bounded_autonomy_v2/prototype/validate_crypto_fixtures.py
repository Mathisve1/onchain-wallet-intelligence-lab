from __future__ import annotations

import json
from pathlib import Path

from crypto_fixture_oracle import action_hash, agent_digest

ROOT = Path(__file__).resolve().parents[1]
PINNED_SDK = "2fdb18f9517675ea03695a0962bd19eece9c83f0"


class CryptoFixtureValidationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CryptoFixtureValidationError(message)


def load(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


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
    require(sources.get("selection_status") == "UNSCORED", "sources:premature_selection")
    require(sources.get("testnet_authorized") is False, "sources:testnet_open")
    require(sources.get("live_authorized") is False, "sources:live_open")
    require(all(candidate.get("authorization") is False for candidate in sources.get("candidates", [])), "sources:candidate_open")

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

    print("BOUNDED_AUTONOMY_CRYPTO_FIXTURE_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
