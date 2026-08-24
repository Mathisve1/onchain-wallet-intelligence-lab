from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO, Final

from .runtime import RuntimeGuard
from .storage_r7 import cleanup_checked_binary_reader

_MAGIC: Final[bytes] = b"\x04\x22\x4d\x18"
_P1: Final[int] = 0x9E3779B1
_P2: Final[int] = 0x85EBCA77
_P3: Final[int] = 0xC2B2AE3D
_P4: Final[int] = 0x27D4EB2F
_P5: Final[int] = 0x165667B1
_MASK: Final[int] = 0xFFFFFFFF
_MAX_RECORD_BYTES: Final[int] = 16 << 20


class LZ4StreamError(ValueError):
    pass


def _rotl(value: int, count: int) -> int:
    return ((value << count) | (value >> (32 - count))) & _MASK


def _round(accumulator: int, value: int) -> int:
    accumulator = (accumulator + value * _P2) & _MASK
    accumulator = _rotl(accumulator, 13)
    return (accumulator * _P1) & _MASK


@dataclasses.dataclass(slots=True)
class XXH32:
    seed: int = 0
    total_length: int = 0
    memory: bytearray = dataclasses.field(default_factory=bytearray)
    v1: int = dataclasses.field(init=False)
    v2: int = dataclasses.field(init=False)
    v3: int = dataclasses.field(init=False)
    v4: int = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        self.seed &= _MASK
        self.v1 = (self.seed + _P1 + _P2) & _MASK
        self.v2 = (self.seed + _P2) & _MASK
        self.v3 = self.seed
        self.v4 = (self.seed - _P1) & _MASK

    def _stripe(self, stripe: bytes) -> None:
        if len(stripe) != 16:
            raise LZ4StreamError("XXH32 stripe must be 16 bytes")
        self.v1 = _round(self.v1, int.from_bytes(stripe[0:4], "little"))
        self.v2 = _round(self.v2, int.from_bytes(stripe[4:8], "little"))
        self.v3 = _round(self.v3, int.from_bytes(stripe[8:12], "little"))
        self.v4 = _round(self.v4, int.from_bytes(stripe[12:16], "little"))

    def update(self, data: bytes) -> None:
        if not data:
            return
        self.total_length += len(data)
        offset = 0
        if self.memory:
            needed = 16 - len(self.memory)
            if len(data) < needed:
                self.memory.extend(data)
                return
            self.memory.extend(data[:needed])
            self._stripe(bytes(self.memory))
            self.memory.clear()
            offset = needed
        while offset + 16 <= len(data):
            self._stripe(data[offset : offset + 16])
            offset += 16
        if offset < len(data):
            self.memory.extend(data[offset:])

    def intdigest(self) -> int:
        if self.total_length >= 16:
            result = (
                _rotl(self.v1, 1)
                + _rotl(self.v2, 7)
                + _rotl(self.v3, 12)
                + _rotl(self.v4, 18)
            ) & _MASK
        else:
            result = (self.seed + _P5) & _MASK
        result = (result + self.total_length) & _MASK
        data = bytes(self.memory)
        offset = 0
        while offset + 4 <= len(data):
            result = (result + int.from_bytes(data[offset : offset + 4], "little") * _P3) & _MASK
            result = (_rotl(result, 17) * _P4) & _MASK
            offset += 4
        while offset < len(data):
            result = (result + data[offset] * _P5) & _MASK
            result = (_rotl(result, 11) * _P1) & _MASK
            offset += 1
        result ^= result >> 15
        result = (result * _P2) & _MASK
        result ^= result >> 13
        result = (result * _P3) & _MASK
        result ^= result >> 16
        return result & _MASK


def xxh32(data: bytes, seed: int = 0) -> int:
    state = XXH32(seed=seed)
    state.update(data)
    return state.intdigest()


def _read_exact(handle: BinaryIO, length: int, label: str) -> bytes:
    value = handle.read(length)
    if len(value) != length:
        raise LZ4StreamError(f"truncated LZ4 {label}")
    return value


def _extended_length(source: bytes, offset: int, initial: int) -> tuple[int, int]:
    length = initial
    if initial != 15:
        return length, offset
    while True:
        if offset >= len(source):
            raise LZ4StreamError("truncated LZ4 extended length")
        value = source[offset]
        offset += 1
        length += value
        if value != 255:
            return length, offset


def decode_block(source: bytes, history: bytes, maximum_output_bytes: int) -> bytes:
    if len(history) > 65536:
        raise LZ4StreamError("LZ4 history exceeds 64 KiB")
    output = bytearray()
    offset = 0
    while offset < len(source):
        token = source[offset]
        offset += 1
        literal_length, offset = _extended_length(source, offset, token >> 4)
        literal_end = offset + literal_length
        if literal_end > len(source):
            raise LZ4StreamError("literal run exceeds compressed block")
        if len(output) + literal_length > maximum_output_bytes:
            raise LZ4StreamError("decompressed block exceeds block maximum")
        output.extend(source[offset:literal_end])
        offset = literal_end
        if offset == len(source):
            break
        if offset + 2 > len(source):
            raise LZ4StreamError("truncated LZ4 match offset")
        match_offset = int.from_bytes(source[offset : offset + 2], "little")
        offset += 2
        if match_offset == 0:
            raise LZ4StreamError("zero LZ4 match offset")
        match_length, offset = _extended_length(source, offset, token & 0x0F)
        match_length += 4
        if len(output) + match_length > maximum_output_bytes:
            raise LZ4StreamError("decompressed block exceeds block maximum")
        if match_offset > len(history) + len(output):
            raise LZ4StreamError("match offset exceeds available history")
        for _ in range(match_length):
            combined_index = len(history) + len(output) - match_offset
            if combined_index < len(history):
                output.append(history[combined_index])
            else:
                output.append(output[combined_index - len(history)])
    return bytes(output)


@dataclasses.dataclass(frozen=True, slots=True)
class PassEvidence:
    decompressed_bytes: int
    record_count: int
    event_count: int
    decompressed_stream_sha256: str


class LZ4LineReader:
    """One-frame LZ4 reader that never retains the complete decompressed object."""

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
        self._stream_sha256 = hashlib.sha256()

    @property
    def evidence(self) -> PassEvidence:
        return PassEvidence(
            decompressed_bytes=self._decompressed_bytes,
            record_count=self._record_count,
            event_count=self._event_count,
            decompressed_stream_sha256=self._stream_sha256.hexdigest(),
        )

    def add_event_count(self, count: int) -> None:
        if count < 0:
            raise LZ4StreamError("event count cannot be negative")
        self._event_count += count

    def __iter__(self) -> Iterator[bytes]:
        line_buffer = bytearray()
        content_checksum_state: XXH32 | None = None
        with cleanup_checked_binary_reader(
            self.path,
            label="LZ4 object",
        ) as handle:
            if _read_exact(handle, 4, "magic") != _MAGIC:
                raise LZ4StreamError("unsupported LZ4 magic")
            flg = _read_exact(handle, 1, "FLG")[0]
            bd = _read_exact(handle, 1, "BD")[0]
            if (flg >> 6) != 0b01:
                raise LZ4StreamError("unsupported LZ4 frame version")
            block_independent = bool(flg & 0x20)
            block_checksum_enabled = bool(flg & 0x10)
            content_size_present = bool(flg & 0x08)
            content_checksum_enabled = bool(flg & 0x04)
            dictionary_present = bool(flg & 0x01)
            if dictionary_present:
                raise LZ4StreamError("dictionary-bound LZ4 frame is unsupported")
            block_maximum = {4: 64 << 10, 5: 256 << 10, 6: 1 << 20, 7: 4 << 20}.get(
                (bd >> 4) & 0x07
            )
            if block_maximum is None:
                raise LZ4StreamError("invalid LZ4 maximum block-size code")
            descriptor = bytearray([flg, bd])
            declared_content_size: int | None = None
            if content_size_present:
                raw_size = _read_exact(handle, 8, "content size")
                descriptor.extend(raw_size)
                declared_content_size = int.from_bytes(raw_size, "little")
                if declared_content_size > self.maximum_decompressed_bytes:
                    raise LZ4StreamError("declared content size exceeds object cap")
            header_checksum = _read_exact(handle, 1, "header checksum")[0]
            if ((xxh32(bytes(descriptor)) >> 8) & 0xFF) != header_checksum:
                raise LZ4StreamError("LZ4 header checksum mismatch")
            if content_checksum_enabled:
                content_checksum_state = XXH32()

            history = b""
            while True:
                self.runtime_guard.check_scientific_phase("decode LZ4 block")
                encoded_size = int.from_bytes(_read_exact(handle, 4, "block header"), "little")
                if encoded_size == 0:
                    break
                uncompressed = bool(encoded_size & 0x80000000)
                block_size = encoded_size & 0x7FFFFFFF
                if block_size == 0 or block_size > block_maximum:
                    raise LZ4StreamError("compressed block size exceeds descriptor maximum")
                compressed = _read_exact(handle, block_size, "block body")
                if block_checksum_enabled:
                    expected = int.from_bytes(_read_exact(handle, 4, "block checksum"), "little")
                    if xxh32(compressed) != expected:
                        raise LZ4StreamError("LZ4 block checksum mismatch")
                decoded = (
                    compressed
                    if uncompressed
                    else decode_block(compressed, b"" if block_independent else history, block_maximum)
                )
                if self._decompressed_bytes + len(decoded) > self.maximum_decompressed_bytes:
                    raise LZ4StreamError("decompressed object exceeds frozen cap")
                self._decompressed_bytes += len(decoded)
                self._stream_sha256.update(decoded)
                if content_checksum_state is not None:
                    content_checksum_state.update(decoded)
                history = b"" if block_independent else (history + decoded)[-65536:]
                line_buffer.extend(decoded)
                while True:
                    newline = line_buffer.find(b"\n")
                    if newline < 0:
                        break
                    line = bytes(line_buffer[:newline])
                    del line_buffer[: newline + 1]
                    if not line or line.endswith(b"\r"):
                        raise LZ4StreamError("empty or CRLF archive record is forbidden")
                    self._record_count += 1
                    yield line
                if len(line_buffer) > _MAX_RECORD_BYTES:
                    raise LZ4StreamError("one decompressed archive record exceeds bounded line buffer")
            if line_buffer:
                if line_buffer.endswith(b"\r"):
                    raise LZ4StreamError("trailing CR archive record is forbidden")
                self._record_count += 1
                yield bytes(line_buffer)
            if content_checksum_state is not None:
                expected = int.from_bytes(_read_exact(handle, 4, "content checksum"), "little")
                if content_checksum_state.intdigest() != expected:
                    raise LZ4StreamError("LZ4 content checksum mismatch")
            if declared_content_size is not None and declared_content_size != self._decompressed_bytes:
                raise LZ4StreamError("declared content size does not match decoded bytes")
            if handle.read(1):
                raise LZ4StreamError("trailing bytes after one LZ4 frame")
