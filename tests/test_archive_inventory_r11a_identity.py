from __future__ import annotations

import json
import subprocess
import sys
import unittest
from decimal import Decimal
from pathlib import Path

from research.archive_inventory.r11a_implementation import activity, identity

ROOT = Path(__file__).resolve().parents[1]
ADDRESS = "0x" + "1" * 40
SOURCE = identity.SourceObject(
    0,
    "node_fills_by_block/hourly/20250728/0.lz4",
    "a" * 64,
    "2025-07-28T00:00:00Z",
)


def fill(*, tid: object = 7, coin: object = "BTC", side: str = "A", px: str = "100") -> dict[str, object]:
    return {
        "coin": coin,
        "tid": tid,
        "time": 1753660800000,
        "side": side,
        "px": px,
        "sz": "1",
        "closedPnl": "0",
        "crossed": side == "A",
        "liquidation": None,
    }


def block(events: list[list[object]], *, block_number: int = 1, block_time: str = "2025-07-28T00:00:00Z") -> bytes:
    return json.dumps(
        {
            "local_time": block_time,
            "block_time": block_time,
            "block_number": block_number,
            "events": events,
        },
        separators=(",", ":"),
    ).encode()


class R11AIdentityTests(unittest.TestCase):
    def test_frozen_canonical_serialization_golden_vectors(self) -> None:
        vectors = (
            (None, "4e", "8ce86a6ae65d3692e7305e2c58ac62eebd97d3d943e093f577da25c36988246b"),
            (True, "4231", "5b950e77941d01cdf246d00b1ece546bc95234b77d98b44c9187e2733afa696a"),
            (-12, "49333a2d3132", "2eedfdf36c487caa7457f94b188ac00bc3b1d196a5514ae372f770c67ea8b9ce"),
            (Decimal("1.2300"), "44363a313233652d32", "99aa0166b53ea1512ad81c91e5e261960cbb2d65ea8fd33fc01555883525e558"),
            ("é", "53323ac3a9", "52669a268b3de8bd030d5dca3e0171b22b253b2ac8ccc8a7a238985fe419e171"),
            ([1, "x"], "4c313a32343a49313a31343a53313a78", "5f7bb65918827caad1305f9ec7283105338fcc89daa21b36d43629a79331b086"),
            ({"b": 2, "a": 1}, "4d313a32343a53313a61343a49313a31343a53313a62343a49313a32", "eabf326e40ac5de0e41e7c9fd6d87081399c11b576619c71e797b9cb46e35916"),
        )
        for value, encoded_hex, digest in vectors:
            with self.subTest(value=value):
                self.assertEqual(identity.canonical_typed_bytes(value).hex(), encoded_hex)
                self.assertEqual(identity.canonical_sha256(value), digest)

    def test_strict_json_rejects_duplicate_keys_nonfinite_and_invalid_utf8(self) -> None:
        for raw in (
            b'{"a":1,"a":2}',
            b'{"x":NaN}',
            b'{"x":Infinity}',
            b'{"x":-Infinity}',
            b'{"x":"\xff"}',
        ):
            with self.subTest(raw=raw), self.assertRaises(identity.R11AIdentityError):
                identity.strict_json_loads(raw)

    def test_tid_coin_and_wallet_validation_are_strict_without_coercion(self) -> None:
        self.assertEqual(identity.validate_tid(0).status, "VALID_UINT50")
        self.assertEqual(identity.validate_tid((1 << 50) - 1).status, "VALID_UINT50")
        for value in (1 << 50, -1, True, "7", Decimal("7.0"), None):
            with self.subTest(value=value):
                self.assertEqual(identity.validate_tid(value).status, "TID_SCHEMA_VIOLATION")
        self.assertEqual(identity.validate_coin("BTC").canonical_value, "BTC")
        for value in ("", None, 1, True):
            self.assertEqual(identity.validate_coin(value).status, "COIN_SCHEMA_VIOLATION")
        self.assertEqual(identity.validate_wallet(ADDRESS).canonical_value, ADDRESS)
        for value in (ADDRESS.upper(), "0x" + "g" * 40, None, 1):
            self.assertEqual(identity.validate_wallet(value).status, "WALLET_SCHEMA_VIOLATION")

    def test_block_parser_separates_raw_trade_and_wallet_fill_identity(self) -> None:
        parsed = identity.parse_block_record(
            block([[ADDRESS, fill(tid=9, coin="ETH")]]),
            source=SOURCE,
            record_ordinal_zero_based=3,
        )
        self.assertEqual(parsed.block_number, 1)
        self.assertEqual(parsed.locator.record_ordinal_zero_based, 3)
        self.assertEqual(parsed.ordered_event_count, 1)
        row = parsed.observations[0]
        self.assertEqual(row.locator.event_ordinal_zero_based, 0)
        self.assertEqual(row.protocol_trade_identity, ("2025-07-28T00:00:00Z", "ETH", 9))
        self.assertEqual(row.wallet_fill_identity, (ADDRESS, "2025-07-28T00:00:00Z", "ETH", 9))
        self.assertEqual(row.legacy_weak_key, (ADDRESS, ("int", "9")))
        self.assertNotEqual(identity.canonical_sha256(row.locator.as_mapping()), row.full_event_sha256)

    def test_payload_hash_is_not_primary_identity(self) -> None:
        first = identity.parse_block_record(
            block([[ADDRESS, fill(tid=10, px="100")]], block_number=1),
            source=SOURCE,
            record_ordinal_zero_based=0,
        ).observations[0]
        second = identity.parse_block_record(
            block([[ADDRESS, fill(tid=10, px="101")]], block_number=2),
            source=SOURCE,
            record_ordinal_zero_based=1,
        ).observations[0]
        self.assertEqual(first.wallet_fill_identity, second.wallet_fill_identity)
        self.assertNotEqual(first.full_event_sha256, second.full_event_sha256)

    def test_import_does_not_mutate_r10_global_limits(self) -> None:
        code = """
from research.archive_inventory.r10_implementation import collector as base
keys = [name for name in vars(base) if name.startswith('MAX_')]
before = {name: getattr(base, name) for name in keys}
import research.archive_inventory.r11a_implementation
assert before == {name: getattr(base, name) for name in keys}
"""
        done = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


class R11AActivityTests(unittest.TestCase):
    def test_reads_never_create_wallet_or_add_ambient_day(self) -> None:
        tracker = activity.ActivityTracker()
        missing = "0x" + "2" * 40
        self.assertIsNone(tracker.snapshot(missing))
        self.assertFalse(tracker.contains(missing))
        self.assertEqual(tracker.wallet_count(), 0)
        self.assertEqual(tracker.snapshots(), ())
        self.assertEqual(dict(tracker.immutable_mapping()), {})
        self.assertEqual(tracker.wallet_count(), 0)

    def test_explicit_record_is_only_mutation_and_snapshot_is_immutable(self) -> None:
        tracker = activity.ActivityTracker()
        tracker.record(
            ADDRESS,
            path_hour_utc="2025-07-28T01:00:00Z",
            block_time_exact="2025-07-28T01:00:00Z",
            fill_time_ms=1,
        )
        tracker.record(
            ADDRESS,
            path_hour_utc="2025-07-29T02:00:00Z",
            block_time_exact="2025-07-29T02:00:00Z",
            fill_time_ms=2,
        )
        before = tracker.snapshot(ADDRESS)
        self.assertEqual(before.path_days, ("2025-07-28", "2025-07-29"))
        for _ in range(10):
            self.assertEqual(tracker.snapshot(ADDRESS), before)
            self.assertEqual(tracker.snapshots(), (before,))
        mapping = tracker.immutable_mapping()
        with self.assertRaises(TypeError):
            mapping[ADDRESS] = before
        self.assertEqual(tracker.snapshot(ADDRESS), before)

    def test_malformed_record_fails_without_partial_state(self) -> None:
        tracker = activity.ActivityTracker()
        with self.assertRaises(activity.ActivityError):
            tracker.record(
                ADDRESS.upper(),
                path_hour_utc="2025-07-28T01:00:00Z",
                block_time_exact="x",
                fill_time_ms=1,
            )
        self.assertEqual(tracker.wallet_count(), 0)


if __name__ == "__main__":
    unittest.main()
