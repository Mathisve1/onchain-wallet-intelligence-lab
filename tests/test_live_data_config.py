from __future__ import annotations

import unittest
from pathlib import Path

from src.live_data.config import (
    DEFAULT_REST_BASE_URL,
    DEFAULT_WS_URL,
    INFO_PATH,
    READ_ONLY_REST_PATHS,
    WS_SERVER_TIMEOUT_SECONDS,
    ConfigError,
    LiveDataConfig,
    TradingAuthorizations,
    normalize_coin,
    normalize_wallet_address,
)

VALID_ADDRESS = "0x" + "ab" * 20


class WalletAddressValidationTests(unittest.TestCase):
    def test_checksum_casing_is_canonicalized_to_lowercase(self) -> None:
        self.assertEqual(normalize_wallet_address("0x" + "AB" * 20), VALID_ADDRESS)

    def test_uppercase_prefix_is_canonicalized_not_rejected(self) -> None:
        self.assertEqual(normalize_wallet_address("0X" + "AB" * 20), VALID_ADDRESS)

    def test_malformed_addresses_are_rejected(self) -> None:
        rejected = [
            "",
            "0x",
            "ab" * 20,  # missing 0x prefix
            "0x" + "ab" * 19,  # 38 hex digits
            "0x" + "ab" * 21,  # 42 hex digits
            "0x" + "zz" * 20,  # non-hex
            "0x" + "ab" * 20 + " ",  # trailing whitespace
            " 0x" + "ab" * 20,
        ]
        for candidate in rejected:
            with self.subTest(candidate=candidate):
                with self.assertRaises(ConfigError):
                    normalize_wallet_address(candidate)

    def test_non_string_addresses_are_rejected(self) -> None:
        for candidate in (None, 12345, b"0x" + b"ab" * 20, ["0x" + "ab" * 20]):
            with self.subTest(candidate=candidate):
                with self.assertRaises(ConfigError):
                    normalize_wallet_address(candidate)


class CoinValidationTests(unittest.TestCase):
    def test_valid_symbols_pass_through_unchanged(self) -> None:
        self.assertEqual(normalize_coin("BTC"), "BTC")
        self.assertEqual(normalize_coin("kPEPE"), "kPEPE")

    def test_malformed_symbols_are_rejected(self) -> None:
        for candidate in ("", " BTC", "BTC ", "X" * 33, None, 7):
            with self.subTest(candidate=candidate):
                with self.assertRaises(ConfigError):
                    normalize_coin(candidate)


class TradingAuthorizationTests(unittest.TestCase):
    def test_every_authorization_defaults_to_false(self) -> None:
        authorizations = TradingAuthorizations()
        self.assertEqual(
            set(authorizations.as_dict()),
            {
                "integration_authorized",
                "paper_authorized",
                "shadow_authorized",
                "live_authorized",
                "leverage_authorized",
                "capital_allocation_authorized",
            },
        )
        self.assertTrue(all(state is False for state in authorizations.as_dict().values()))
        authorizations.assert_read_only()

    def test_any_opened_authorization_fails_closed(self) -> None:
        for field_name in TradingAuthorizations().as_dict():
            with self.subTest(field=field_name):
                opened = TradingAuthorizations(**{field_name: True})
                with self.assertRaises(ConfigError):
                    opened.assert_read_only()

    def test_config_construction_rejects_an_opened_authorization(self) -> None:
        with self.assertRaises(ConfigError):
            LiveDataConfig(authorizations=TradingAuthorizations(live_authorized=True))

    def test_non_boolean_authorization_is_rejected(self) -> None:
        with self.assertRaises(ConfigError):
            TradingAuthorizations(paper_authorized="yes")


class LiveDataConfigTests(unittest.TestCase):
    def test_defaults_are_the_documented_read_only_endpoints(self) -> None:
        config = LiveDataConfig()
        self.assertEqual(config.rest_base_url, DEFAULT_REST_BASE_URL)
        self.assertEqual(config.ws_url, DEFAULT_WS_URL)
        self.assertEqual(config.info_url, f"{DEFAULT_REST_BASE_URL}{INFO_PATH}")
        self.assertEqual(READ_ONLY_REST_PATHS, frozenset({"/info"}))
        self.assertEqual(config.weight_per_minute, 1200)

    def test_heartbeat_must_fit_inside_the_server_timeout(self) -> None:
        self.assertLess(LiveDataConfig().ws_heartbeat_seconds, WS_SERVER_TIMEOUT_SECONDS)
        with self.assertRaises(ConfigError):
            LiveDataConfig(ws_heartbeat_seconds=WS_SERVER_TIMEOUT_SECONDS)
        with self.assertRaises(ConfigError):
            LiveDataConfig(ws_heartbeat_seconds=0)

    def test_tracked_wallets_are_validated_and_lowercased(self) -> None:
        config = LiveDataConfig(tracked_wallets=("0x" + "AB" * 20,))
        self.assertEqual(config.tracked_wallets, (VALID_ADDRESS,))

    def test_invalid_tracked_wallet_rejects_the_whole_config(self) -> None:
        with self.assertRaises(ConfigError):
            LiveDataConfig(tracked_wallets=("0xnothex",))

    def test_duplicate_tracked_entries_are_rejected(self) -> None:
        with self.assertRaises(ConfigError):
            LiveDataConfig(tracked_wallets=(VALID_ADDRESS, "0x" + "AB" * 20))
        with self.assertRaises(ConfigError):
            LiveDataConfig(tracked_coins=("BTC", "BTC"))

    def test_insecure_or_malformed_endpoints_are_rejected(self) -> None:
        with self.assertRaises(ConfigError):
            LiveDataConfig(rest_base_url="http://api.hyperliquid.xyz")
        with self.assertRaises(ConfigError):
            LiveDataConfig(rest_base_url="https://api.hyperliquid.xyz/")
        with self.assertRaises(ConfigError):
            LiveDataConfig(ws_url="ws://api.hyperliquid.xyz/ws")

    def test_nonsensical_budgets_are_rejected(self) -> None:
        with self.assertRaises(ConfigError):
            LiveDataConfig(weight_per_minute=0)
        with self.assertRaises(ConfigError):
            LiveDataConfig(request_timeout_seconds=0)
        with self.assertRaises(ConfigError):
            LiveDataConfig(max_retries=-1)

    def test_database_path_is_coerced_to_path(self) -> None:
        config = LiveDataConfig(database_path="research/live_data/x.sqlite3")
        self.assertIsInstance(config.database_path, Path)

    def test_config_is_immutable(self) -> None:
        config = LiveDataConfig()
        with self.assertRaises(Exception):
            config.rest_base_url = "https://example.invalid"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
