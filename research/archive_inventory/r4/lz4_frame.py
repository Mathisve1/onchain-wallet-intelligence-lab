from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

MASK32 = 0xFFFFFFFF
PRIME32_1 = 0x9E3779B1
PRIME32_2 = 0x85EBCA77
PRIME32_3 = 0xC2B2AE3D
PRIME32_4 = 0x27D4EB2F
PRIME32_5 = 0x165667B1

LZ4_FRAME_MAGIC = b"\x04\x22\x4d\x18"
BLOCK_MAX_BYTES = {
    4: 64 * 1024,
    5: 256 * 1024,
    6: 1024 * 1024,
    7: 4 * 1024 * 1024,
}


class LZ4FrameError(RuntimeError):
    pass


class LZ4FrameLimit(LZ4FrameError):
    def __init__(self, status: str):
        super().__init__(status)
        self.status = status


@dataclass(frozen=True)
class FrameMetadata:
    block_independent: bool
    block_checksum: bool
    content_checksum: bool
    declared_content_size: int | None
    maximum_block_size: int


def _rotl32(value: int, count: int) -> int:
    return ((value << count) | (value >> (32 - count))) & MASK32


def _round32(accumulator: int, lane: int) -> int:
    accumulator = (accumulator + lane * PRIME32_2) & MASK32
    accumulator = _rotl32(accumulator, 13)
    return (accumulator * PRIME32_1) & MASK32


class XXH32:
    def __init__(self, seed: int = 0):
        self.seed = seed & MASK32
        self.total_length = 0
        self.memory = bytearray()
        self.v1 = (self.seed + PRIME32_1 + PRIME32_2) & MASK32
        self.v2 = (self.seed + PRIME32_2) & MASK32
        self.v3 = self.seed
        self.v4 = (self.seed - PRIME32_1) & MASK32

    def _stripe(self, block: bytes) -> None:
        if len(block) != 16:
            raise ValueError("XXH32 stripe must be 16 bytes")
        self.v1 = _round32(self.v1, int.from_bytes(block[0:4], "little"))
        self.v2 = _round32(self.v2, int.from_bytes(block[4:8], "little"))
        self.v3 = _round32(self.v3, int.from_bytes(block[8:12], "little"))
        self.v4 = _round32(self.v4, int.from_bytes(block[12:16], "little"))

    def update(self, data: bytes) -> None:
        if not data:
            return
        self.total_length += len(data)
        if self.memory:
            needed = 16 - len(self.memory)
            if len(data) < needed:
                self.memory.extend(data)
                return
            self.memory.extend(data[:needed])
            self._stripe(bytes(self.memory))
            self.memory.clear()
            data = data[needed:]

        position = 0
        while position + 16 <= len(data):
            self._stripe(data[position : position + 16])
            position += 16
        self.memory.extend(data[position:])

    def intdigest(self) -> int:
        if self.total_length >= 16:
            value = (
                _rotl32(self.v1, 1)
                + _rotl32(self.v2, 7)
                + _rotl32(self.v3, 12)
                + _rotl32(self.v4, 18)
            ) & MASK32
        else:
            value = (self.seed + PRIME32_5) & MASK32

        value = (value + self.total_length) & MASK32
        tail = bytes(self.memory)
        position = 0
        while position + 4 <= len(tail):
            lane = int.from_bytes(tail[position : position + 4], "little")
            value = (value + lane * PRIME32_3) & MASK32
            value = (_rotl32(value, 17) * PRIME32_4) & MASK32
            position += 4
        while position < len(tail):
            value = (value + tail[position] * PRIME32_5) & MASK32
            value = (_rotl32(value, 11) * PRIME32_1) & MASK32
            position += 1

        value ^= value >> 15
        value = (value * PRIME32_2) & MASK32
        value ^= value >> 13
        value = (value * PRIME32_3) & MASK32
        value ^= value >> 16
        return value & MASK32


def xxh32(data: bytes, seed: int = 0) -> int:
    state = XXH32(seed)
    state.update(data)
    return state.intdigest()


def decode_lz4_block(source: bytes, dictionary: bytes, maximum_output_bytes: int) -> bytes:
    position = 0
    output = bytearray()

    def extended_length(base: int) -> int:
        nonlocal position
        length = base
        if base == 15:
            while True:
                if position >= len(source):
                    raise LZ4FrameError("truncated extended length")
                value = source[position]
                position += 1
                length += value
                if value != 255:
                    break
        return length

    while position < len(source):
        token = source[position]
        position += 1

        literal_length = extended_length(token >> 4)
        if position + literal_length > len(source):
            raise LZ4FrameError("literal overruns compressed block")
        if len(output) + literal_length > maximum_output_bytes:
            raise LZ4FrameError("decoded block exceeds declared maximum block size")
        output.extend(source[position : position + literal_length])
        position += literal_length

        if position == len(source):
            break
        if position + 2 > len(source):
            raise LZ4FrameError("truncated match offset")
        offset = source[position] | (source[position + 1] << 8)
        position += 2
        if offset == 0:
            raise LZ4FrameError("zero LZ4 match offset")

        available_history = len(dictionary) + len(output)
        if offset > available_history:
            raise LZ4FrameError("LZ4 match offset escapes available history")

        match_length = extended_length(token & 0x0F) + 4
        if len(output) + match_length > maximum_output_bytes:
            raise LZ4FrameError("decoded block exceeds declared maximum block size")

        if offset <= len(output):
            seed = bytes(output[-offset:])
        else:
            required_dictionary = offset - len(output)
            if required_dictionary > len(dictionary):
                raise LZ4FrameError("dependent block dictionary underflow")
            seed = dictionary[-required_dictionary:] + bytes(output)
            if len(seed) != offset:
                raise LZ4FrameError("invalid dependent block seed")

        repeats = (match_length + len(seed) - 1) // len(seed)
        output.extend((seed * repeats)[:match_length])

    return bytes(output)


def _parse_frame_header(raw: bytes, maximum_decompressed_bytes: int) -> tuple[int, FrameMetadata]:
    if len(raw) < 7 or raw[:4] != LZ4_FRAME_MAGIC:
        raise LZ4FrameError("unrecognized LZ4 frame magic")

    position = 4
    flg = raw[position]
    bd = raw[position + 1]
    position += 2

    if (flg >> 6) != 1:
        raise LZ4FrameError("unsupported LZ4 frame version")
    if flg & 0x02:
        raise LZ4FrameError("reserved FLG bit is set")
    if bd & 0x8F:
        raise LZ4FrameError("reserved BD bits are set")

    maximum_block_code = (bd >> 4) & 0x07
    maximum_block_size = BLOCK_MAX_BYTES.get(maximum_block_code)
    if maximum_block_size is None:
        raise LZ4FrameError("invalid LZ4 maximum block-size code")

    block_independent = bool(flg & 0x20)
    block_checksum = bool(flg & 0x10)
    has_content_size = bool(flg & 0x08)
    content_checksum = bool(flg & 0x04)
    has_dictionary_id = bool(flg & 0x01)

    descriptor = bytearray((flg, bd))
    declared_content_size: int | None = None

    if has_content_size:
        if position + 8 > len(raw):
            raise LZ4FrameError("truncated LZ4 content-size field")
        encoded_size = raw[position : position + 8]
        descriptor.extend(encoded_size)
        position += 8
        declared_content_size = int.from_bytes(encoded_size, "little")
        if declared_content_size > maximum_decompressed_bytes:
            raise LZ4FrameLimit("SCHEMA_CENSORED_BY_DECOMPRESSED_BYTE_LIMIT")

    if has_dictionary_id:
        if position + 4 > len(raw):
            raise LZ4FrameError("truncated LZ4 dictionary-ID field")
        descriptor.extend(raw[position : position + 4])
        raise LZ4FrameError("external LZ4 dictionaries are not authorized")

    if position >= len(raw):
        raise LZ4FrameError("missing LZ4 frame header checksum")
    observed_header_checksum = raw[position]
    position += 1
    expected_header_checksum = (xxh32(bytes(descriptor)) >> 8) & 0xFF
    if observed_header_checksum != expected_header_checksum:
        raise LZ4FrameError("LZ4 frame header checksum mismatch")

    return position, FrameMetadata(
        block_independent=block_independent,
        block_checksum=block_checksum,
        content_checksum=content_checksum,
        declared_content_size=declared_content_size,
        maximum_block_size=maximum_block_size,
    )


def iter_lz4_frame(raw: bytes, maximum_decompressed_bytes: int) -> Iterator[bytes]:
    position, metadata = _parse_frame_header(raw, maximum_decompressed_bytes)
    total_decompressed = 0
    history = b""
    content_hash = XXH32()

    while True:
        if position + 4 > len(raw):
            raise LZ4FrameError("truncated LZ4 block-size field")
        block_field = int.from_bytes(raw[position : position + 4], "little")
        position += 4
        if block_field == 0:
            break

        uncompressed_block = bool(block_field & 0x80000000)
        block_size = block_field & 0x7FFFFFFF
        if block_size == 0 or block_size > metadata.maximum_block_size:
            raise LZ4FrameError("invalid LZ4 block size")
        if position + block_size > len(raw):
            raise LZ4FrameError("truncated LZ4 block")

        encoded_block = raw[position : position + block_size]
        position += block_size

        if metadata.block_checksum:
            if position + 4 > len(raw):
                raise LZ4FrameError("missing LZ4 block checksum")
            observed = int.from_bytes(raw[position : position + 4], "little")
            position += 4
            if observed != xxh32(encoded_block):
                raise LZ4FrameError("LZ4 block checksum mismatch")

        if uncompressed_block:
            decoded = encoded_block
        else:
            decoded = decode_lz4_block(
                encoded_block,
                b"" if metadata.block_independent else history,
                metadata.maximum_block_size,
            )

        if len(decoded) > metadata.maximum_block_size:
            raise LZ4FrameError("decoded block exceeds LZ4 block maximum")
        if total_decompressed + len(decoded) > maximum_decompressed_bytes:
            raise LZ4FrameLimit("SCHEMA_CENSORED_BY_DECOMPRESSED_BYTE_LIMIT")

        total_decompressed += len(decoded)
        content_hash.update(decoded)
        if not metadata.block_independent:
            history = (history + decoded)[-65536:]

        yield decoded

    if metadata.content_checksum:
        if position + 4 > len(raw):
            raise LZ4FrameError("missing LZ4 content checksum")
        observed = int.from_bytes(raw[position : position + 4], "little")
        position += 4
        if observed != content_hash.intdigest():
            raise LZ4FrameError("LZ4 content checksum mismatch")

    if metadata.declared_content_size is not None and total_decompressed != metadata.declared_content_size:
        raise LZ4FrameError("LZ4 declared content size mismatch")
    if position != len(raw):
        raise LZ4FrameError("trailing bytes after single authorized LZ4 frame")
