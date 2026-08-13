from __future__ import annotations

import dataclasses
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from research.archive_inventory.r11a_corrective import canonical
from research.archive_inventory.r11a_corrective.activity import PureActivityTracker
from research.archive_inventory.r11a_corrective.canonical import (
    CanonicalJSONError,
    FrozenObject,
    NumberToken,
    canonical_json_bytes,
    mathematically_integral_number,
    strict_json_loads,
)
from research.archive_inventory.r11a_corrective.identity import parse_block_record
from research.archive_inventory.r11a_corrective.limits import DEFAULT_LIMITS
from research.archive_inventory.r11a_corrective.lz4stream import LZ4LineReader, xxh32
from research.archive_inventory.r11a_corrective.pricing import PricingError, PricingSnapshot
from research.archive_inventory.r11a_corrective.runtime import (
    ExecutionEvidenceState,
    RuntimeGuard,
    RuntimeTarget,
)


class CanonicalFoundationTests(unittest.TestCase):
    def test_strict_decoder_rejects_duplicate_nonfinite_and_invalid_utf8(self) -> None:
        for raw in (
            b'{"a":1,"a":2}',
            b'{"x":NaN}',
            b'{"x":Infinity}',
            b'"\xff"',
        ):
            with self.assertRaises((CanonicalJSONError, UnicodeError)):
                strict_json_loads(raw)

    def test_canonical_mapping_order_is_utf8_byte_order_and_deeply_immutable(self) -> None:
        left = strict_json_loads('{"z":{"b":2,"a":1},"a":0}'.encode())
        right = strict_json_loads('{"a":0,"z":{"a":1,"b":2}}'.encode())
        self.assertEqual(canonical_json_bytes(left), canonical_json_bytes(right))
        self.assertIsInstance(left, FrozenObject)
        with self.assertRaises(TypeError):
            left["new"] = "value"  # type: ignore[index]

    def test_integral_exponent_normalizer_never_uses_decimal_quantize(self) -> None:
        token = NumberToken("1.2300e3", False)
        self.assertEqual(mathematically_integral_number(token), "1230")
        self.assertNotIn("quantize", canonical.mathematically_integral_number.__code__.co_names)
        with self.assertRaises(CanonicalJSONError):
            mathematically_integral_number(NumberToken("1e5000", False))


class IdentityAndActivityTests(unittest.TestCase):
    def test_four_identity_layers_and_deep_payload_snapshot(self) -> None:
        raw = (
            b'{"events":[["0x1111111111111111111111111111111111111111",'
            b'{"tid":7,"coin":"BTC","side":"A","px":"100","sz":"1"}]],'
            b'"block_number":9,"block_time":"2025-07-28T00:00:00.000",'
            b'"local_time":"2025-07-28T00:00:00.001"}'
        )
        block = parse_block_record(
            strict_json_loads(raw),
            object_key="node_fills_by_block/hourly/20250728/0.lz4",
            verified_compressed_sha256="1" * 64,
            record_ordinal_zero_based=0,
        )
        event = block.events[0]
        self.assertIsNotNone(event.protocol_trade_identity)
        self.assertIsNotNone(event.wallet_fill_identity)
        self.assertNotEqual(event.legacy_weak_key_bytes, event.wallet_fill_identity.key_bytes())
        self.assertIsInstance(event.immutable_fill_payload, FrozenObject)
        with self.assertRaises(TypeError):
            event.immutable_fill_payload["px"] = "999"  # type: ignore[index]

    def test_activity_reads_never_mutate(self) -> None:
        tracker = PureActivityTracker()
        self.assertIsNone(tracker.snapshot("0x" + "1" * 40))
        self.assertEqual(tracker.wallet_count(), 0)
        tracker.record("0x" + "1" * 40, "2025-07-28T00:00:00Z")
        before = tracker.snapshots()
        self.assertIsNone(tracker.snapshot("0x" + "2" * 40))
        self.assertEqual(tracker.snapshots(), before)
        self.assertEqual(tracker.snapshot("0x" + "1" * 40).active_day_count, 1)


class LZ4StreamingTests(unittest.TestCase):
    @staticmethod
    def frame(payload: bytes) -> bytes:
        flg = 0x60  # version=01, independent blocks
        bd = 0x40   # maximum block 64 KiB
        header_checksum = (xxh32(bytes([flg, bd])) >> 8) & 0xFF
        block_header = (0x80000000 | len(payload)).to_bytes(4, "little")
        return b"\x04\x22\x4d\x18" + bytes([flg, bd, header_checksum]) + block_header + payload + b"\x00\x00\x00\x00"

    def test_xxh32_reference_vectors_and_streaming_line_reader(self) -> None:
        self.assertEqual(xxh32(b""), 0x02CC5D05)
        self.assertEqual(xxh32(b"a"), 0x550D7456)
        payload = b'{"x":1}\n{"x":2}\n'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.lz4"
            path.write_bytes(self.frame(payload))
            guard = RuntimeGuard(DEFAULT_LIMITS, monotonic_ns=lambda: 0)
            reader = LZ4LineReader(path, guard, maximum_decompressed_bytes=1024)
            self.assertEqual(list(reader), [b'{"x":1}', b'{"x":2}'])
            self.assertEqual(reader.evidence.decompressed_bytes, len(payload))
            self.assertEqual(reader.evidence.record_count, 2)


class RuntimeAndPricingTests(unittest.TestCase):
    @staticmethod
    def targets() -> tuple[RuntimeTarget, ...]:
        return tuple(
            RuntimeTarget(
                object_ordinal_zero_based=index,
                object_key=f"node_fills_by_block/hourly/20250728/{index}.lz4",
                expected_size_bytes=1,
                expected_etag='"' + "a" * 32 + '"',
                expected_compressed_sha256="0" * 64,
                source_path_hour_utc=f"2025-07-28T{index % 24:02d}:00:00Z",
            )
            for index in range(72)
        )

    def test_object_lifecycle_is_one_request_and_metadata_precedes_body(self) -> None:
        state = ExecutionEvidenceState(self.targets(), DEFAULT_LIMITS)
        state.request_sent(0)
        with self.assertRaises(Exception):
            state.body_progress(0, 1)
        state.response_metadata(
            0,
            http_status=200,
            etag='"' + "a" * 32 + '"',
            content_length=1,
            requester_charged="requester",
        )
        state.body_progress(0, 1)
        state.body_complete(0, "0" * 64)
        with self.assertRaises(Exception):
            state.request_sent(0)
        rows = state.object_rows()
        self.assertEqual(len(rows), 72)
        self.assertEqual(rows[0]["request"]["count"], 1)
        self.assertEqual(rows[1]["request"]["count"], 0)

    def test_unbound_pricing_snapshot_blocks_approval_and_execution(self) -> None:
        with self.assertRaises(PricingError):
            PricingSnapshot.load()


class GovernanceBoundaryTests(unittest.TestCase):
    def test_corrective_status_and_all_authority_are_closed(self) -> None:
        root = Path(__file__).resolve().parents[1]
        status = json.loads(
            (root / "research/archive_inventory/r11a_corrective/R11A_CORRECTIVE_STATUS.json").read_text()
        )
        self.assertEqual(
            status["status"],
            "CORRECTIVE_IMPLEMENTATION_SEALED_AWAITING_CLEAN_CONTEXT_REVIEW_NO_EXECUTION",
        )
        self.assertTrue(status["implementation_sealed"])
        self.assertEqual(status["closed_red_finding_count"], 20)
        self.assertTrue(status["pricing_binding_pending"])
        self.assertFalse(status["independent_clean_context_review_completed"])
        self.assertIsNone(status["independent_clean_context_review_verdict"])
        self.assertFalse(status["owner_approval_eligible"])
        self.assertTrue(all(value is False for value in status["current_runtime_authority"].values()))
        self.assertTrue(all(value is False for value in status["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in status["trading_authorizations"].values()))
        self.assertFalse(
            (root / ".github/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic.yml").exists()
        )

    def test_all_twenty_one_red_findings_are_frozen(self) -> None:
        root = Path(__file__).resolve().parents[1]
        findings = json.loads(
            (root / "research/archive_inventory/r11a_corrective/R11A_RED_REVIEW_FINDINGS.json").read_text()
        )
        self.assertEqual(findings["verdict"], "RED")
        self.assertEqual(len(findings["findings"]), 21)
        self.assertEqual(
            {row["finding_id"] for row in findings["findings"]},
            {f"R11A-RED-{index:03d}" for index in range(1, 22)},
        )


if __name__ == "__main__":
    unittest.main()
