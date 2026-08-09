from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R4 = ROOT / "research/archive_inventory/r4"
sys.path.insert(0, str(R4))

from lz4_frame import LZ4_FRAME_MAGIC, LZ4FrameError, LZ4FrameLimit, iter_lz4_frame, xxh32  # noqa: E402


def frame(payload: bytes, *, linked: bool = False, block_checksum: bool = True, content_checksum: bool = True) -> bytes:
    flg = 0x40
    if not linked:
        flg |= 0x20
    if block_checksum:
        flg |= 0x10
    flg |= 0x08
    if content_checksum:
        flg |= 0x04
    bd = 0x40
    descriptor = bytes((flg, bd)) + len(payload).to_bytes(8, "little")
    header_checksum = bytes(((xxh32(descriptor) >> 8) & 0xFF,))
    encoded = bytearray(LZ4_FRAME_MAGIC + descriptor + header_checksum)
    for start in range(0, len(payload), 64 * 1024):
        block = payload[start : start + 64 * 1024]
        encoded.extend((len(block) | 0x80000000).to_bytes(4, "little"))
        encoded.extend(block)
        if block_checksum:
            encoded.extend(xxh32(block).to_bytes(4, "little"))
    encoded.extend((0).to_bytes(4, "little"))
    if content_checksum:
        encoded.extend(xxh32(payload).to_bytes(4, "little"))
    return bytes(encoded)


def linked_two_block_frame() -> bytes:
    flg = 0x40 | 0x08 | 0x04
    bd = 0x40
    decoded = b"abc" + b"abcabc"
    descriptor = bytes((flg, bd)) + len(decoded).to_bytes(8, "little")
    encoded = bytearray(LZ4_FRAME_MAGIC + descriptor + bytes(((xxh32(descriptor) >> 8) & 0xFF,)))
    first = b"abc"
    encoded.extend((len(first) | 0x80000000).to_bytes(4, "little"))
    encoded.extend(first)
    second = b"\x02\x03\x00"
    encoded.extend(len(second).to_bytes(4, "little"))
    encoded.extend(second)
    encoded.extend((0).to_bytes(4, "little"))
    encoded.extend(xxh32(decoded).to_bytes(4, "little"))
    return bytes(encoded)


class R4Lz4Tests(unittest.TestCase):
    def test_xxh32_fixed_reference_vectors(self) -> None:
        self.assertEqual(xxh32(b""), 0x02CC5D05)
        self.assertEqual(xxh32(b"a"), 0x550D7456)
        self.assertEqual(xxh32(b"abc"), 0x32D153FF)

    def test_uncompressed_frame_round_trips_with_checksums(self) -> None:
        payload = (b'{"a":1}\n' * 20000) + b'{"z":true}\n'
        encoded = frame(payload)
        self.assertEqual(b"".join(iter_lz4_frame(encoded, len(payload) + 1)), payload)

    def test_linked_compressed_block_uses_only_previous_64k_history(self) -> None:
        self.assertEqual(b"".join(iter_lz4_frame(linked_two_block_frame(), 1024)), b"abcabcabc")

    def test_header_and_content_checksum_corruption_fail_closed(self) -> None:
        encoded = bytearray(frame(b'{"a":1}\n'))
        encoded[14] ^= 0x01
        with self.assertRaises(LZ4FrameError):
            b"".join(iter_lz4_frame(bytes(encoded), 1024))
        encoded = bytearray(frame(b'{"a":1}\n'))
        encoded[-1] ^= 0x01
        with self.assertRaises(LZ4FrameError):
            b"".join(iter_lz4_frame(bytes(encoded), 1024))

    def test_unknown_magic_has_no_fallback(self) -> None:
        with self.assertRaises(LZ4FrameError):
            b"".join(iter_lz4_frame(b"not-lz4", 1024))

    def test_declared_decompressed_size_over_cap_is_censored_before_blocks(self) -> None:
        encoded = frame(b"x" * 100)
        with self.assertRaises(LZ4FrameLimit) as caught:
            b"".join(iter_lz4_frame(encoded, 99))
        self.assertEqual(caught.exception.status, "SCHEMA_CENSORED_BY_DECOMPRESSED_BYTE_LIMIT")


if __name__ == "__main__":
    unittest.main()
