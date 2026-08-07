import unittest

from hyperliquid_wire import WireError, normalize_wire_decimal, order_wire, order_action, cancel_by_cloid_action

C = "0x" + "0" * 31 + "1"


class Tests(unittest.TestCase):
    def test_normalization(self):
        self.assertEqual(normalize_wire_decimal("50000.00000000"), "50000")
        self.assertEqual(normalize_wire_decimal("0.01000000"), "0.01")
        self.assertEqual(normalize_wire_decimal("-0.00000000"), "0")

    def test_reject_more_than_8_decimals(self):
        with self.assertRaises(WireError):
            normalize_wire_decimal("0.123456789")

    def test_order_fixture(self):
        wire = order_wire(asset=0, is_buy=True, limit_price="50000", size="0.01", reduce_only=False, cloid=C)
        self.assertEqual(
            wire,
            {"a": 0, "b": True, "p": "50000", "s": "0.01", "r": False, "t": {"limit": {"tif": "Ioc"}}, "c": C},
        )
        self.assertEqual(order_action(wire), {"type": "order", "orders": [wire], "grouping": "na"})

    def test_cancel_fixture(self):
        self.assertEqual(
            cancel_by_cloid_action(asset=0, cloid=C),
            {"type": "cancelByCloid", "cancels": [{"asset": 0, "cloid": C}]},
        )


if __name__ == "__main__":
    unittest.main()
