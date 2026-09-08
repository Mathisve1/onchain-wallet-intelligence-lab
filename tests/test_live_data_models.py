from __future__ import annotations

import unittest
from decimal import Decimal

from src.live_data.models import (
    MAX_TID,
    ClearinghouseState,
    Fill,
    Meta,
    PayloadError,
    parse_all_mids,
    parse_fills,
    parse_funding,
    parse_open_orders,
)

WALLET = "0x" + "ab" * 20


def fill_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "coin": "BTC",
        "px": "64000.5",
        "sz": "0.01",
        "side": "B",
        "time": 1_700_000_000_000,
        "startPosition": "0.0",
        "dir": "Open Long",
        "closedPnl": "0.0",
        "hash": "0x" + "cd" * 32,
        "oid": 987654321,
        "crossed": True,
        "fee": "0.32",
        "tid": 123456789012345,
        "feeToken": "USDC",
    }
    payload.update(overrides)
    return payload


def clearinghouse_payload(**overrides: object) -> dict[str, object]:
    summary = {
        "accountValue": "10000.0",
        "totalNtlPos": "2500.0",
        "totalRawUsd": "7500.0",
        "totalMarginUsed": "250.0",
    }
    payload: dict[str, object] = {
        "marginSummary": dict(summary),
        "crossMarginSummary": dict(summary),
        "withdrawable": "9750.0",
        "time": 1_700_000_000_000,
        "assetPositions": [
            {
                "type": "oneWay",
                "position": {
                    "coin": "ETH",
                    "szi": "-1.5",
                    "entryPx": "3200.0",
                    "positionValue": "4800.0",
                    "unrealizedPnl": "-12.5",
                    "marginUsed": "480.0",
                    "liquidationPx": None,
                },
            }
        ],
    }
    payload.update(overrides)
    return payload


class FillParsingTests(unittest.TestCase):
    def test_documented_payload_parses_into_exact_decimals(self) -> None:
        fill = Fill.parse(fill_payload(), WALLET)
        self.assertEqual(fill.price, Decimal("64000.5"))
        self.assertEqual(fill.size, Decimal("0.01"))
        self.assertEqual(fill.fee, Decimal("0.32"))
        self.assertEqual(fill.side, "B")
        self.assertEqual(fill.natural_key, (WALLET, "BTC", 123456789012345, 1_700_000_000_000))

    def test_wallet_address_is_canonicalized_on_the_parsed_row(self) -> None:
        fill = Fill.parse(fill_payload(), "0x" + "AB" * 20)
        self.assertEqual(fill.wallet_address, WALLET)

    def test_missing_required_fields_are_rejected(self) -> None:
        for key in (
            "coin",
            "px",
            "sz",
            "side",
            "time",
            "startPosition",
            "dir",
            "closedPnl",
            "hash",
            "oid",
            "crossed",
            "fee",
            "tid",
        ):
            with self.subTest(missing=key):
                payload = fill_payload()
                del payload[key]
                with self.assertRaises(PayloadError):
                    Fill.parse(payload, WALLET)

    def test_wrong_json_types_are_rejected_not_coerced(self) -> None:
        cases = [
            fill_payload(px=64000.5),  # float would import binary rounding
            fill_payload(sz=None),
            fill_payload(time="1700000000000"),
            fill_payload(tid="123"),
            fill_payload(oid=True),  # bool is not an order id
            fill_payload(crossed="true"),
            fill_payload(coin=123),
            fill_payload(feeToken=7),
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(PayloadError):
                    Fill.parse(payload, WALLET)

    def test_out_of_range_values_are_rejected(self) -> None:
        for payload in (
            fill_payload(tid=MAX_TID + 1),
            fill_payload(tid=-1),
            fill_payload(oid=-5),
            fill_payload(px="0"),
            fill_payload(sz="-0.01"),
            fill_payload(time=0),
            fill_payload(time=-1),
            fill_payload(side="X"),
            fill_payload(px="not-a-number"),
            fill_payload(px="NaN"),
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(PayloadError):
                    Fill.parse(payload, WALLET)

    def test_optional_fee_token_may_be_absent(self) -> None:
        payload = fill_payload()
        del payload["feeToken"]
        self.assertIsNone(Fill.parse(payload, WALLET).fee_token)

    def test_fill_list_must_be_an_array_of_objects(self) -> None:
        self.assertEqual(len(parse_fills([fill_payload()], WALLET)), 1)
        for payload in ({"fills": []}, "[]", None, [fill_payload(), "x"]):
            with self.subTest(payload=payload):
                with self.assertRaises(PayloadError):
                    parse_fills(payload, WALLET)


class AllMidsParsingTests(unittest.TestCase):
    def test_flat_and_wrapped_maps_both_parse(self) -> None:
        self.assertEqual(parse_all_mids({"BTC": "64000.5"}), {"BTC": Decimal("64000.5")})
        self.assertEqual(parse_all_mids({"mids": {"ETH": "3200"}}), {"ETH": Decimal("3200")})

    def test_malformed_mids_are_rejected(self) -> None:
        for payload in ({"BTC": 64000.5}, {"BTC": "0"}, {"BTC": "-1"}, {"BTC": None}, [], "x"):
            with self.subTest(payload=payload):
                with self.assertRaises(PayloadError):
                    parse_all_mids(payload)


class MetaParsingTests(unittest.TestCase):
    def test_universe_parses(self) -> None:
        meta = Meta.parse(
            {"universe": [{"name": "BTC", "szDecimals": 5, "maxLeverage": 40, "isDelisted": False}]}
        )
        self.assertEqual(meta.universe[0].name, "BTC")
        self.assertEqual(meta.universe[0].max_leverage, 40)

    def test_malformed_universe_is_rejected(self) -> None:
        cases = [
            {},
            {"universe": {}},
            {"universe": [{"name": "BTC", "szDecimals": 5}]},
            {"universe": [{"name": "BTC", "szDecimals": -1, "maxLeverage": 40}]},
            {"universe": [{"name": "BTC", "szDecimals": 5, "maxLeverage": 0}]},
            {"universe": [{"name": "BTC", "szDecimals": 5, "maxLeverage": 40, "isDelisted": "no"}]},
            {
                "universe": [
                    {"name": "BTC", "szDecimals": 5, "maxLeverage": 40},
                    {"name": "BTC", "szDecimals": 5, "maxLeverage": 40},
                ]
            },
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(PayloadError):
                    Meta.parse(payload)


class ClearinghouseStateParsingTests(unittest.TestCase):
    def test_snapshot_parses_including_a_null_liquidation_price(self) -> None:
        state = ClearinghouseState.parse(clearinghouse_payload(), WALLET)
        self.assertEqual(state.margin_summary.account_value, Decimal("10000.0"))
        self.assertEqual(state.withdrawable, Decimal("9750.0"))
        self.assertEqual(state.positions[0].signed_size, Decimal("-1.5"))
        self.assertIsNone(state.positions[0].liquidation_price)

    def test_missing_sections_are_rejected(self) -> None:
        for key in ("marginSummary", "crossMarginSummary", "withdrawable", "time", "assetPositions"):
            with self.subTest(missing=key):
                payload = clearinghouse_payload()
                del payload[key]
                with self.assertRaises(PayloadError):
                    ClearinghouseState.parse(payload, WALLET)

    def test_position_without_a_position_object_is_rejected(self) -> None:
        payload = clearinghouse_payload(assetPositions=[{"type": "oneWay"}])
        with self.assertRaises(PayloadError):
            ClearinghouseState.parse(payload, WALLET)


class FundingAndOrderParsingTests(unittest.TestCase):
    def test_funding_row_parses(self) -> None:
        rows = [
            {
                "time": 1_700_000_000_000,
                "hash": "0x" + "ef" * 32,
                "delta": {
                    "type": "funding",
                    "coin": "BTC",
                    "usdc": "-0.42",
                    "szi": "0.01",
                    "fundingRate": "0.0000125",
                },
            }
        ]
        deltas = parse_funding(rows, WALLET)
        self.assertEqual(deltas[0].usdc, Decimal("-0.42"))
        self.assertEqual(deltas[0].funding_rate, Decimal("0.0000125"))

    def test_non_funding_delta_type_is_rejected(self) -> None:
        rows = [
            {
                "time": 1,
                "delta": {"type": "deposit", "coin": "BTC", "usdc": "1", "szi": "0", "fundingRate": "0"},
            }
        ]
        with self.assertRaises(PayloadError):
            parse_funding(rows, WALLET)

    def test_open_order_parses_and_validates_side(self) -> None:
        rows = [
            {"coin": "BTC", "limitPx": "60000", "oid": 1, "side": "B", "sz": "0.5", "timestamp": 1}
        ]
        orders = parse_open_orders(rows, WALLET)
        self.assertEqual(orders[0].limit_price, Decimal("60000"))
        rows[0]["side"] = "buy"
        with self.assertRaises(PayloadError):
            parse_open_orders(rows, WALLET)


if __name__ == "__main__":
    unittest.main()
