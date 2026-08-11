from __future__ import annotations

import dataclasses
import hashlib
import struct
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO, Final

from .runtime import RuntimeGuard

_MAGIC: Final[bytes] = b"\x04\x22\x4d\x18"
_PRIME32_1: Final[int] = 0x9E3779B1
_PRIME32_2: Final[int] = 0x85EBCA77
_PRIME32_3: Final[int] = 0xC2B2AE3D
_PRIME32_4: Final[int] = 0x27D4EB2F
_PRIME32_5: Final[int] = 0x165667B1
_MASK32: Final[int] = 0xFFFFFFFF


class LZ4FrameError(ValueError):
    pass


def _rotl32(value: int, count: int) -> int:
    return ((value << count) | (value >> (32 - count))) & _MASK32


def _round32(accumulator: int, value: int) -> int:
    accumulator = (accumulator + value * _PRIME32_2) & _MASK32
    accumulator = _rotl32(accumulator, 13)
    return (accumulator * _PRIME32_1) & _MASK32


def xxh32(data: bytes, seed: int = 0) -> int:
    length = len(data)
    offset = 0
    if length >= 16:
        v1 = (seed + _PRIME32_1 + _PRIME32_2) & _MASK32
        v2 = (seed + _PRIME32_2) & _MASK32
        v3 = seed & _MASK32
        v4 = (seed - _PRIME32_1) & _MASK32
        limit = length - 16
        while offset <= limit:
            v1 = _round32(v1, int.from_bytes(data[offset : offset + 4], "little"))
            v2 = _round32(v2, int.from_bytes(data[offset + 4 : offset + 8], "little"))
            v3 = _round32(v3, int.from_bytes(data[offset + 8 : offset + 12], "little"))
            v4 = _round32(v4, int.from_bytes(data[offset + 12 : offset + 16], "little"))
            offset += 16
        result = (
            _rotl32(v1, 1) + _rotl32(v2, 7) + _rotl32(v3, 12) + _rotl32(v4, 18)
        ) & _MASK32
    else:
        result = (seed + _PRIME32_5) & _MASK32
    result = (result + length) & _MASK32
    while offset + 4 <= length:
        result = (result + int.from_bytes(data[offset : offset + 4], "little") * _PRIME32_3) & _MASK32
        result = (_rotl32(result, 17) * _PRIME32_4) & _MASK32
        offset += 4
    while offset < length:
        result = (result + data[offset] * _PRIME32_5) & _MASK32
        result = (_rotl32(result, 11) * _PRIME32_1) & _MASK32
        offset += 1
    result ^= result >> 15
    result = (result * _PRIME32_2) & _MASK32
    result ^= result >> 13
    result = (result * _PRIME32_3) & _MASK32
    result ^= result >> 16
    return result & _MASK32


def _read_exact(handle: BinaryIO, length: int, label: str) -> bytes:
    data = handle.read(length)
    if len(data) != length:
        raise LZ4FrameError(f"truncated LZ4 {label}")
    return data


def _extended_length(source: bytes, offset: int, initial: int) -> tuple[int, int]:
    length = initial
    if initial != 15:
        return length, offset
    while True:
        if offset >= len(source):
            raise LZ4FrameError("truncated LZ4 extended length")
        value = source[offset]
        offset += 1
        length += value
        if value != 255:
            return length, offset


def decode_lz4_block(source: bytes, history: bytes, maximum_output_bytes: int) -> bytes:
    output = bytearray()
    offset = 0
    while offset < len(source):
        token = source[offset]
        offset += 1
        literal_length, offset = _extended_length(source, offset, token >> 4)
        literal_end = offset + literal_length
        if literal_end > len(source):
            raise LZ4FrameError("literal run exceeds compressed block")
        if len(output) + literal_length > maximum_output_bytes:
            raise LZ4FrameError("decompressed block exceeds frozen block bound")
        output.extend(source[offset:literal_end])
        offset = literal_end
        if offset == len(source):
            break
        if offset + 2 > len(source):
            raise LZ4FrameError("truncated LZ4 match offset")
        match_offset = int.from_bytes(source[offset : offset + 2], "little")
        offset += 2
        if match_offset == 0:
            raise LZ4FrameError("zero LZ4 match offset")
        match_length, offset = _extended_length(source, offset, token & 0x0F)
        match_length += 4
        if len(output) + match_length > maximum_output_bytes:
            raise LZ4FrameError("decompressed block exceeds frozen block bound")
        available = history + bytes(output)
        if match_offset > len(available):
            raise LZ4FrameError("LZ4 match offset exceeds available history")
        source_index = len(available) - match_offset
        for _ in range(match_length):
            available = history + bytes(output)
            if source_index >= len(available):
                source_index = len(available) - match_offset
            output.append(available[source_index])
            source_index += 1
    return bytes(output)


@dataclasses.dataclass(frozen=True, slots=True)
class LZ4PassEvidence:
    decompressed_bytes: int
    record_count: int
    event_count: int
    decompressed_stream_sha256: str


class LZ4LineReader:
    def __init__(
        self,
        path: Path,
        runtime_guard: RuntimeGuard,
        *,
        maximum_decompressed_bytes: int,
    ) -> None:
        self.path = path
        self.runtime_guard = runtime_guard
        self.maximum_decompressed_bytes = maximum_decompressed_bytes
        self._decompressed_bytes = 0
        self._record_count = 0
        self._event_count = 0
        self._stream_hash = hashlib.sha256()

    @property
    def evidence(self) -> LZ4PassEvidence:
        return LZ4PassEvidence(
            decompressed_bytes=self._decompressed_bytes,
            record_count=self._record_count,
            event_count=self._event_count,
            decompressed_stream_sha256=self._stream_hash.hexdigest(),
        )

    def add_event_count(self, count: int) -> None:
        if count < 0:
            raise LZ4FrameError("negative event count")
        self._event_count += count

    def __iter__(self) -> Iterator[bytes]:
        line_buffer = bytearray()
        content_hash_bytes = bytearray()
        with self.path.open("rb") as handle:
            if _read_exact(handle, 4, "magic") != _MAGIC:
                raise LZ4FrameError("unknown LZ4 frame magic")
            flg = _read_exact(handle, 1, "FLG")[0]
            bd = _read_exact(handle, 1, "BD")[0]
            if (flg >> 6) != 0b01:
                raise LZ4FrameError("unsupported LZ4 frame version")
            block_independent = bool(flg & 0x20)
            block_checksum = bool(flg & 0x10)
            content_size_present = bool(flg & 0x08)
            content_checksum = bool(flg & 0x04)
            dictionary_present = bool(flg & 0x01)
            if dictionary_present:
                raise LZ4FrameError("dictionary-bound LZ4 frames are unsupported")
            block_code = (bd >> 4) & 0x07
            block_maximum = {4: 64 << 10, 5: 256 << 10, 6: 1 << 20, 7: 4 << 20}.get(
                block_code
            )
            if block_maximum is None:
                raise LZ4FrameError("invalid LZ4 maximum block-size code")
            descriptor = bytearray([flg, bd])
            declared_content_size: int | None = None
            if content_size_present:
                raw_size = _read_exact(handle, 8, "content size")
                descriptor.extend(raw_size)
                declared_content_size = int.from_bytes(raw_size, "little")
                if declared_content_size > self.maximum_decompressed_bytes:
                    raise LZ4FrameError("declared LZ4 content size exceeds frozen object cap")
            expected_header_checksum = _read_exact(handle, 1, "header checksum")[0]
            if ((xxh32(bytes(descriptor)) >> 8) & 0xFF) != expected_header_checksum:
                raise LZ4FrameError("LZ4 header checksum mismatch")

            history = b""
            while True:
                self.runtime_guard.check_scientific_phase("decode LZ4 block")
                block_header = _read_exact(handle, 4, "block header")
                encoded_size = int.from_bytes(block_header, "little")
                if encoded_size == 0:
                    break
                uncompressed = bool(encoded_size & 0x80000000)
                block_size = encoded_size & 0x7FFFFFFF
                if block_size == 0 or block_size > block_maximum:
                    raise LZ4FrameError("LZ4 block size exceeds descriptor bound")
                compressed = _read_exact(handle, block_size, "block body")
                if block_checksum:
                    expected = int.from_bytes(_read_exact(handle, 4, "block checksum"), "little")
                    if xxh32(compressed) != expected:
                        raise LZ4FrameError("LZ4 block checksum mismatch")
                if uncompressed:
                    decoded = compressed
                else:
                    decoded = decode_lz4_block(
                        compressed,
                        b"" if block_independent else history,
                        block_maximum,
                    )
                if self._decompressed_bytes + len(decoded) > self.maximum_decompressed_bytes:
                    raise LZ4FrameError("decompressed object exceeds frozen object cap")
                self._decompressed_bytes += len(decoded)
                self._stream_hash.update(decoded)
                if content_checksum:
                    content_hash_bytes.extend(decoded)
                if block_independent:
                    history = b""
                else:
                    history = (history + decoded)[-65536:]
                line_buffer.extend(decoded)
                while True:
                    newline = line_buffer.find(b"\n")
                    if newline < 0:
                        break
                    line = bytes(line_buffer[:newline])
                    del line_buffer[: newline + 1]
                    if line.endswith(b"\r"):
                        raise LZ4FrameError("CRLF source records are outside the frozen archive contract")
                    if not line:
                        raise LZ4FrameError("empty decompressed archive record")
                    self._record_count += 1
                    yield line
            if line_buffer:
                if line_buffer.endswith(b"\r"):
                    raise LZ4FrameError("trailing CR source record is forbidden")
                self._record_count += 1
                yield bytes(line_buffer)
            if content_checksum:
                expected = int.from_bytes(_read_exact(handle, 4, "content checksum"), "little")
                if xxh32(bytes(content_hash_bytes)) != expected:
                    raise LZ4FrameError("LZ4 content checksum mismatch")
            if declared_content_size is not None and declared_content_size != self._decompressed_bytes:
                raise LZ4FrameError("LZ4 declared content size mismatch")
            if handle.read(1):
                raise LZ4FrameError("trailing bytes after one LZ4 frame are forbidden")
