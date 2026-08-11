from __future__ import annotations

import dataclasses
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .canonical import strict_json_loads
from .identity import BlockObservation, IdentityError, parse_block_record
from .limits import R11ALimits
from .lz4stream import LZ4LineReader, PassEvidence
from .runtime import RuntimeGuard, RuntimeTarget


class ParseError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True, slots=True)
class ParseConservation:
    raw_block_observation_count: int
    raw_event_observation_count: int
    valid_wallet_occurrence_count: int
    invalid_wallet_occurrence_count: int
    valid_coin_occurrence_count: int
    invalid_coin_occurrence_count: int
    valid_tid_occurrence_count: int
    invalid_tid_occurrence_count: int
    protocol_trade_identity_occurrence_count: int
    wallet_fill_identity_occurrence_count: int
    local_time_path_prefix_match_count: int
    block_time_path_prefix_match_count: int
    block_time_previous_prefix_match_count: int
    block_time_other_prefix_count: int

    def validate(self) -> None:
        if self.raw_event_observation_count != (
            self.valid_wallet_occurrence_count + self.invalid_wallet_occurrence_count
        ):
            raise ParseError("wallet valid/invalid partition does not conserve raw events")
        if self.raw_event_observation_count != (
            self.valid_coin_occurrence_count + self.invalid_coin_occurrence_count
        ):
            raise ParseError("coin valid/invalid partition does not conserve raw events")
        if self.raw_event_observation_count != (
            self.valid_tid_occurrence_count + self.invalid_tid_occurrence_count
        ):
            raise ParseError("TID valid/invalid partition does not conserve raw events")
        if self.protocol_trade_identity_occurrence_count > self.valid_tid_occurrence_count:
            raise ParseError("protocol identities exceed valid TIDs")
        if self.wallet_fill_identity_occurrence_count > self.protocol_trade_identity_occurrence_count:
            raise ParseError("wallet-fill identities exceed protocol identities")
        if self.raw_block_observation_count != self.local_time_path_prefix_match_count:
            raise ParseError("not every record local_time matches source path hour")
        if self.raw_block_observation_count != (
            self.block_time_path_prefix_match_count
            + self.block_time_previous_prefix_match_count
            + self.block_time_other_prefix_count
        ):
            raise ParseError("block-time prefix partition does not conserve raw blocks")
        if self.block_time_other_prefix_count != 0:
            raise ParseError("block_time outside path or immediately previous hour")

    def as_mapping(self) -> dict[str, int]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True, slots=True)
class ObjectPassResult:
    transport: PassEvidence
    conservation: ParseConservation

    def exact_match(self, other: "ObjectPassResult") -> bool:
        return self == other


def _prefixes(source_hour_utc: str) -> tuple[str, str]:
    try:
        parsed = datetime.strptime(source_hour_utc, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise ParseError("source path hour is not exact UTC hour text") from exc
    path_prefix = parsed.strftime("%Y-%m-%dT%H")
    previous_prefix = (parsed - timedelta(hours=1)).strftime("%Y-%m-%dT%H")
    return path_prefix, previous_prefix


def parse_object_pass(
    *,
    compressed_path: Path,
    target: RuntimeTarget,
    limits: R11ALimits,
    runtime_guard: RuntimeGuard,
    on_block: Callable[[BlockObservation], None],
) -> ObjectPassResult:
    path_prefix, previous_prefix = _prefixes(target.source_path_hour_utc)
    reader = LZ4LineReader(
        compressed_path,
        runtime_guard,
        maximum_decompressed_bytes=limits.maximum_individual_decompressed_bytes_per_pass,
    )
    raw_blocks = 0
    raw_events = 0
    valid_wallet = 0
    invalid_wallet = 0
    valid_coin = 0
    invalid_coin = 0
    valid_tid = 0
    invalid_tid = 0
    protocol = 0
    wallet_fill = 0
    local_match = 0
    block_path = 0
    block_previous = 0
    block_other = 0

    for record_ordinal, line in enumerate(reader):
        runtime_guard.check_scientific_phase(
            f"parse object {target.object_ordinal_zero_based} record {record_ordinal}"
        )
        try:
            value = strict_json_loads(line)
            block = parse_block_record(
                value,
                object_key=target.object_key,
                verified_compressed_sha256=target.expected_compressed_sha256,
                record_ordinal_zero_based=record_ordinal,
            )
        except (ValueError, IdentityError) as exc:
            raise ParseError(
                f"strict source parse failed at object {target.object_ordinal_zero_based} record {record_ordinal}"
            ) from exc
        raw_blocks += 1
        if block.exact_raw_local_time.startswith(path_prefix):
            local_match += 1
        else:
            raise ParseError("local_time raw prefix does not match source path hour")
        if block.exact_raw_block_time.startswith(path_prefix):
            block_path += 1
        elif block.exact_raw_block_time.startswith(previous_prefix):
            block_previous += 1
        else:
            block_other += 1
        for event in block.events:
            raw_events += 1
            if event.canonical_wallet is None:
                invalid_wallet += 1
            else:
                valid_wallet += 1
            if event.exact_raw_coin_string is None:
                invalid_coin += 1
            else:
                valid_coin += 1
            if event.validated_tid is None:
                invalid_tid += 1
            else:
                valid_tid += 1
            if event.protocol_trade_identity is not None:
                protocol += 1
            if event.wallet_fill_identity is not None:
                wallet_fill += 1
        reader.add_event_count(len(block.events))
        on_block(block)

    conservation = ParseConservation(
        raw_block_observation_count=raw_blocks,
        raw_event_observation_count=raw_events,
        valid_wallet_occurrence_count=valid_wallet,
        invalid_wallet_occurrence_count=invalid_wallet,
        valid_coin_occurrence_count=valid_coin,
        invalid_coin_occurrence_count=invalid_coin,
        valid_tid_occurrence_count=valid_tid,
        invalid_tid_occurrence_count=invalid_tid,
        protocol_trade_identity_occurrence_count=protocol,
        wallet_fill_identity_occurrence_count=wallet_fill,
        local_time_path_prefix_match_count=local_match,
        block_time_path_prefix_match_count=block_path,
        block_time_previous_prefix_match_count=block_previous,
        block_time_other_prefix_count=block_other,
    )
    conservation.validate()
    if reader.evidence.record_count != raw_blocks or reader.evidence.event_count != raw_events:
        raise ParseError("line reader and strict parser conservation differ")
    return ObjectPassResult(reader.evidence, conservation)
