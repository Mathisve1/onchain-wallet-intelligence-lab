from __future__ import annotations

import dataclasses
import struct
from pathlib import Path

from .canonical import canonical_json_bytes
from .identity import BlockObservation, EventObservation
from .index_r3 import CandidateDiscovery, SharedPartitionWriter
from .limits import R11ALimits
from .storage import WorkspaceMeter


class MaterializationError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True, slots=True)
class MaterializedIndexes:
    block_directory: Path
    weak_directory: Path
    wallet_fill_directory: Path
    protocol_trade_directory: Path
    block_commitments: tuple[dict[str, object], ...]
    weak_commitments: tuple[dict[str, object], ...]
    wallet_fill_commitments: tuple[dict[str, object], ...]
    protocol_trade_commitments: tuple[dict[str, object], ...]
    retained_block_observation_count: int
    retained_event_observation_count: int
    cap_fallback_required: bool


class CandidateMaterializer:
    """Second-pass retention limited to first-pass repeated candidates.

    A cap decision is made from first-pass counts before construction. Any later
    reservation breach is terminal and cannot publish partially retained science.
    """

    def __init__(
        self,
        meter: WorkspaceMeter,
        limits: R11ALimits,
        discovery: CandidateDiscovery,
    ) -> None:
        self.meter = meter
        self.limits = limits
        self.discovery = discovery
        self.block_directory = meter.root / "materialized-block-number"
        self.weak_directory = meter.root / "materialized-exact-weak-key"
        self.wallet_directory = meter.root / "materialized-wallet-fill"
        self.protocol_directory = meter.root / "materialized-protocol-trade"
        self.cap_fallback = discovery.cap_fallback_required
        # The four reservations total 1.4 GB after primary indexes are deleted.
        self.block_writer = SharedPartitionWriter(
            self.block_directory,
            meter,
            maximum_total_bytes=250_000_000,
            label="materialized repeated block observations",
        )
        self.weak_writer = SharedPartitionWriter(
            self.weak_directory,
            meter,
            maximum_total_bytes=450_000_000,
            label="materialized exact legacy weak-key observations",
        )
        self.wallet_writer = SharedPartitionWriter(
            self.wallet_directory,
            meter,
            maximum_total_bytes=350_000_000,
            label="materialized wallet-fill observations",
        )
        self.protocol_writer = SharedPartitionWriter(
            self.protocol_directory,
            meter,
            maximum_total_bytes=350_000_000,
            label="materialized protocol-trade observations",
        )
        self.retained_blocks = 0
        self.retained_events = 0

    @staticmethod
    def event_mapping(event: EventObservation) -> dict[str, object]:
        selected_fill: dict[str, object] | None = None
        if event.immutable_fill_payload is not None:
            selected_fill = {}
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
                    selected_fill[field] = event.immutable_fill_payload[field]
        return {
            "record_type": "MATERIALIZED_EVENT_OBSERVATION",
            "raw_locator": event.locator_mapping(),
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
            "schema_errors": list(event.schema_errors),
            "selected_fill_payload": selected_fill,
        }

    @staticmethod
    def block_mapping(block: BlockObservation) -> dict[str, object]:
        return {
            "record_type": "MATERIALIZED_BLOCK_OBSERVATION",
            "raw_locator": block.locator_mapping(),
            "block_number": block.block_number,
            "exact_raw_local_time": block.exact_raw_local_time,
            "exact_raw_block_time": block.exact_raw_block_time,
            "ordered_event_count": block.ordered_event_count,
            "ordered_event_fingerprint": block.ordered_event_fingerprint,
            "raw_record_fingerprint": block.raw_record_fingerprint,
        }

    def add_block(self, block: BlockObservation) -> None:
        if self.cap_fallback:
            return
        weak_candidate_events = tuple(
            event
            for event in block.events
            if event.legacy_weak_key_sha256 in self.discovery.repeated_weak_hashes
        )
        block_candidate = block.block_number in self.discovery.repeated_block_numbers
        if not block_candidate and not weak_candidate_events:
            return
        self.meter.runtime_guard.check_scientific_phase("materialize candidate block")
        if self.retained_blocks + 1 > self.limits.maximum_repeated_observations_retained:
            self.cap_fallback = True
            return
        self.block_writer.write(
            struct.pack(">Q", block.block_number),
            canonical_json_bytes(self.block_mapping(block), final_newline=False),
        )
        self.retained_blocks += 1

        # The full raw block event vector is retained when any candidate occurs in the
        # block so protocol counterparty proofs cannot depend on omitted neighbours.
        for event in block.events:
            if self.retained_events + 1 > self.limits.maximum_repeated_observations_retained:
                self.cap_fallback = True
                return
            payload = canonical_json_bytes(self.event_mapping(event), final_newline=False)
            is_weak_candidate = event.legacy_weak_key_sha256 in self.discovery.repeated_weak_hashes
            if is_weak_candidate:
                self.weak_writer.write(event.legacy_weak_key_bytes, payload)
                if event.wallet_fill_identity is not None:
                    self.wallet_writer.write(event.wallet_fill_identity.key_bytes(), payload)
            # Protocol groups need complete block context for expected maker/taker pairs.
            if event.protocol_trade_identity is not None:
                self.protocol_writer.write(event.protocol_trade_identity.key_bytes(), payload)
            self.retained_events += 1

    def close(self) -> MaterializedIndexes:
        self.block_writer.close()
        self.weak_writer.close()
        self.wallet_writer.close()
        self.protocol_writer.close()
        return MaterializedIndexes(
            block_directory=self.block_directory,
            weak_directory=self.weak_directory,
            wallet_fill_directory=self.wallet_directory,
            protocol_trade_directory=self.protocol_directory,
            block_commitments=self.block_writer.commitments(),
            weak_commitments=self.weak_writer.commitments(),
            wallet_fill_commitments=self.wallet_writer.commitments(),
            protocol_trade_commitments=self.protocol_writer.commitments(),
            retained_block_observation_count=self.retained_blocks,
            retained_event_observation_count=self.retained_events,
            cap_fallback_required=self.cap_fallback,
        )

    def abort(self) -> None:
        errors: list[BaseException] = []
        for writer in (
            self.block_writer,
            self.weak_writer,
            self.wallet_writer,
            self.protocol_writer,
        ):
            try:
                writer.abort()
            except BaseException as exc:
                errors.append(exc)
        if errors:
            raise MaterializationError("candidate materialization cleanup failed") from errors[0]
