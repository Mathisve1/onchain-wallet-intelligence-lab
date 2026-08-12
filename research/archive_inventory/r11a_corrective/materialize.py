from __future__ import annotations

import dataclasses
import struct
from pathlib import Path

from .canonical import canonical_json_bytes
from .identity import BlockObservation, EventObservation, frame
from .index import CandidateDatabase, CandidateDiscovery, SharedPartitionWriter
from .limits import R11ALimits
from .storage_r7 import WorkspaceMeter

_BLOCK_MAX_BYTES = 250_000_000
_WEAK_MAX_BYTES = 700_000_000
_PROTOCOL_MAX_BYTES = 500_000_000
_MAX_PROTOCOL_KEYS_PER_BLOCK = 100_000


class MaterializationBoundaryError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True, slots=True)
class MaterializedIndexes:
    block_directory: Path
    weak_directory: Path
    protocol_directory: Path
    block_stats: tuple[tuple[int, int], ...]
    weak_stats: tuple[tuple[int, int], ...]
    protocol_stats: tuple[tuple[int, int], ...]
    retained_block_observation_count: int
    retained_legacy_observation_count: int
    retained_protocol_member_count: int
    cap_fallback_required: bool


class CandidateMaterializer:
    """Second pass retains only exact repeated candidates and required context."""

    def __init__(
        self,
        meter: WorkspaceMeter,
        limits: R11ALimits,
        discovery: CandidateDiscovery,
    ) -> None:
        self.meter = meter
        self.limits = limits
        self.discovery = discovery
        self.block_directory = meter.root / "materialized-blocks"
        self.weak_directory = meter.root / "materialized-legacy-repeats"
        self.protocol_directory = meter.root / "materialized-protocol-per-block"
        self.block_writer = SharedPartitionWriter(
            self.block_directory,
            meter,
            maximum_total_bytes=_BLOCK_MAX_BYTES,
            label="materialized repeated block observations",
        )
        self.weak_writer = SharedPartitionWriter(
            self.weak_directory,
            meter,
            maximum_total_bytes=_WEAK_MAX_BYTES,
            label="materialized legacy repeat observations",
        )
        self.protocol_writer = SharedPartitionWriter(
            self.protocol_directory,
            meter,
            maximum_total_bytes=_PROTOCOL_MAX_BYTES,
            label="materialized protocol groups per raw block",
        )
        self.retained_blocks = 0
        self.retained_legacy = 0
        self.retained_protocol = 0
        self.cap_fallback = discovery.cap_fallback_required
        self._closed = False

    @staticmethod
    def _selected_fill(event: EventObservation) -> dict[str, object] | None:
        if event.immutable_fill_payload is None:
            return None
        result: dict[str, object] = {}
        for field in (
            "coin",
            "side",
            "time",
            "px",
            "sz",
            "closedPnl",
            "tid",
            "crossed",
            "liquidation",
        ):
            if field in event.immutable_fill_payload:
                result[field] = event.immutable_fill_payload[field]
        return result

    @staticmethod
    def event_mapping(event: EventObservation, object_ordinal_zero_based: int) -> dict[str, object]:
        errors = set(event.schema_errors)
        return {
            "record_type": "R11A_V2_MATERIALIZED_EVENT_OBSERVATION",
            "object_ordinal_zero_based": object_ordinal_zero_based,
            "raw_locator": event.locator_mapping(),
            "raw_block_key_hex": event.raw_locator.block.key_bytes().hex(),
            "block_number": event.block_number,
            "exact_raw_local_time": event.exact_raw_local_time,
            "exact_raw_block_time": event.exact_raw_block_time,
            "canonical_wallet": event.canonical_wallet,
            "exact_raw_coin_string": event.exact_raw_coin_string,
            "validated_tid": event.validated_tid,
            "exact_raw_side_string": event.exact_raw_side_string,
            "legacy_weak_key_hex": event.legacy_weak_key_bytes.hex(),
            "protocol_trade_key_hex": (
                None
                if event.protocol_trade_identity is None
                else event.protocol_trade_identity.key_bytes().hex()
            ),
            "wallet_fill_key_hex": (
                None
                if event.wallet_fill_identity is None
                else event.wallet_fill_identity.key_bytes().hex()
            ),
            "full_event_sha256": event.full_event_sha256,
            "fill_payload_sha256": event.fill_payload_sha256,
            "tid_schema_valid": not any(value.startswith("TID_") for value in errors),
            "coin_schema_valid": "COIN_NOT_VALID_EXACT_STRING" not in errors,
            "wallet_schema_valid": not any(value.startswith("WALLET_") for value in errors),
            "schema_errors": list(event.schema_errors),
            "selected_fill_payload": CandidateMaterializer._selected_fill(event),
        }

    @staticmethod
    def block_mapping(block: BlockObservation, object_ordinal_zero_based: int) -> dict[str, object]:
        return {
            "record_type": "R11A_V2_MATERIALIZED_BLOCK_OBSERVATION",
            "object_ordinal_zero_based": object_ordinal_zero_based,
            "raw_locator": block.locator_mapping(),
            "raw_block_key_hex": block.raw_locator.key_bytes().hex(),
            "block_number": block.block_number,
            "exact_raw_local_time": block.exact_raw_local_time,
            "exact_raw_block_time": block.exact_raw_block_time,
            "ordered_event_count": block.ordered_event_count,
            "ordered_event_fingerprint_sha256": block.ordered_event_fingerprint,
            "raw_record_fingerprint_sha256": block.raw_record_fingerprint,
        }

    def _cap(self, *, additional_blocks: int = 0, additional_events: int = 0) -> bool:
        if self.retained_blocks + additional_blocks > self.limits.maximum_repeated_observations_retained:
            return True
        combined = self.retained_legacy + self.retained_protocol + additional_events
        return combined > self.limits.maximum_repeated_observations_retained

    def add_block(self, block: BlockObservation, object_ordinal_zero_based: int) -> None:
        if self._closed:
            raise MaterializationBoundaryError("materializer is closed")
        if self.cap_fallback:
            return
        self.meter.runtime_guard.check_scientific_phase("materialize block before")
        block_candidate = self.discovery.candidates.contains_block(block.block_number)
        weak_events = tuple(
            event
            for event in block.events
            if self.discovery.candidates.contains_weak_hash(event.legacy_weak_key_sha256)
        )
        if not block_candidate and not weak_events:
            return
        protocol_keys = {
            event.protocol_trade_identity.key_bytes()
            for event in weak_events
            if event.protocol_trade_identity is not None
        }
        if len(protocol_keys) > _MAX_PROTOCOL_KEYS_PER_BLOCK:
            raise MaterializationBoundaryError("candidate protocol keys in one block exceed bound")
        protocol_events = tuple(
            event
            for event in block.events
            if event.protocol_trade_identity is not None
            and event.protocol_trade_identity.key_bytes() in protocol_keys
        )
        if self._cap(
            additional_blocks=int(block_candidate),
            additional_events=len(weak_events) + len(protocol_events),
        ):
            self.cap_fallback = True
            return
        if block_candidate:
            self.block_writer.write(
                struct.pack(">Q", block.block_number),
                canonical_json_bytes(
                    self.block_mapping(block, object_ordinal_zero_based),
                    final_newline=False,
                ),
            )
            self.retained_blocks += 1
        for event in weak_events:
            self.weak_writer.write(
                event.legacy_weak_key_bytes,
                canonical_json_bytes(
                    self.event_mapping(event, object_ordinal_zero_based),
                    final_newline=False,
                ),
            )
            self.retained_legacy += 1
        raw_block_key = block.raw_locator.key_bytes()
        for event in protocol_events:
            if event.protocol_trade_identity is None:
                raise MaterializationBoundaryError("protocol context lost protocol identity")
            equality_key = frame(raw_block_key, event.protocol_trade_identity.key_bytes())
            self.protocol_writer.write(
                equality_key,
                canonical_json_bytes(
                    self.event_mapping(event, object_ordinal_zero_based),
                    final_newline=False,
                ),
            )
            self.retained_protocol += 1
        self.meter.runtime_guard.check_scientific_phase("materialize block after")

    def close(self) -> MaterializedIndexes:
        if self._closed:
            raise MaterializationBoundaryError("materializer already closed")
        self.block_writer.close()
        self.weak_writer.close()
        self.protocol_writer.close()
        self._closed = True
        return MaterializedIndexes(
            block_directory=self.block_directory,
            weak_directory=self.weak_directory,
            protocol_directory=self.protocol_directory,
            block_stats=self.block_writer.partition_stats(),
            weak_stats=self.weak_writer.partition_stats(),
            protocol_stats=self.protocol_writer.partition_stats(),
            retained_block_observation_count=self.retained_blocks,
            retained_legacy_observation_count=self.retained_legacy,
            retained_protocol_member_count=self.retained_protocol,
            cap_fallback_required=self.cap_fallback,
        )

    def abort(self) -> None:
        if self._closed:
            return
        errors: list[BaseException] = []
        for writer in (self.block_writer, self.weak_writer, self.protocol_writer):
            try:
                writer.abort()
            except BaseException as exc:
                errors.append(exc)
        self._closed = True
        if errors:
            raise MaterializationBoundaryError("materializer cleanup failed") from errors[0]
