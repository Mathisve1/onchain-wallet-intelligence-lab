from __future__ import annotations

import dataclasses
import struct
from collections.abc import Mapping
from pathlib import Path

from .canonical import canonical_json_bytes
from .identity import BlockObservation, EventObservation, frame
from .index import CandidateDiscovery, _SharedPartitionWriter
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
    """Retain only complete second-pass observations selected by first-pass candidates."""

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
        self.block_writer = _SharedPartitionWriter(
            self.block_directory,
            meter,
            maximum_total_bytes=300_000_000,
            label="materialized repeated block observations",
        )
        self.weak_writer = _SharedPartitionWriter(
            self.weak_directory,
            meter,
            maximum_total_bytes=500_000_000,
            label="materialized exact legacy weak-key observations",
        )
        self.wallet_writer = _SharedPartitionWriter(
            self.wallet_directory,
            meter,
            maximum_total_bytes=350_000_000,
            label="materialized wallet-fill observations",
        )
        self.protocol_writer = _SharedPartitionWriter(
            self.protocol_directory,
            meter,
            maximum_total_bytes=350_000_000,
            label="materialized protocol-trade observations",
        )
        self.retained_blocks = 0
        self.retained_events = 0
        self.cap_fallback = discovery.cap_fallback_required

    @staticmethod
    def _event_mapping(event: EventObservation) -> dict[str, object]:
        protocol_key = (
            None
            if event.protocol_trade_identity is None
            else event.protocol_trade_identity.key_bytes().hex()
        )
        wallet_fill_key = (
            None if event.wallet_fill_identity is None else event.wallet_fill_identity.key_bytes().hex()
        )
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
            "protocol_trade_key_hex": protocol_key,
            "wallet_fill_key_hex": wallet_fill_key,
            "full_event_sha256": event.full_event_sha256,
            "fill_payload_sha256": event.fill_payload_sha256,
            "schema_errors": list(event.schema_errors),
            "selected_fill_payload": selected_fill,
        }

    @staticmethod
    def _block_mapping(block: BlockObservation) -> dict[str, object]:
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
        weak_candidate_events = [
            event
            for event in block.events
            if event.legacy_weak_key_sha256 in self.discovery.repeated_weak_hashes
        ]
        block_candidate = block.block_number in self.discovery.repeated_block_numbers
        if not block_candidate and not weak_candidate_events:
            return
        self.meter.runtime_guard.check_scientific_phase("materialize candidate block")
        if self.retained_blocks + 1 > self.limits.maximum_repeated_observations_retained:
            self.cap_fallback = True
            return
        block_payload = canonical_json_bytes(self._block_mapping(block), final_newline=False)
        self.block_writer.write(struct.pack(">Q", block.block_number), block_payload)
        self.retained_blocks += 1

        # Full block context is retained whenever any weak candidate is present so
        # expected counterparty-pair proofs never depend on an omitted neighbour.
        events_to_materialize = block.events if weak_candidate_events or block_candidate else ()
        for event in events_to_materialize:
            if self.retained_events + 1 > self.limits.maximum_repeated_observations_retained:
                self.cap_fallback = True
                return
            payload = canonical_json_bytes(self._event_mapping(event), final_newline=False)
            if event.legacy_weak_key_sha256 in self.discovery.repeated_weak_hashes:
                self.weak_writer.write(event.legacy_weak_key_bytes, payload)
                if event.wallet_fill_identity is not None:
                    self.wallet_writer.write(event.wallet_fill_identity.key_bytes(), payload)
            if event.protocol_trade_identity is not None:
                self.protocol_writer.write(event.protocol_trade_identity.key_bytes(), payload)
            self.retained_events += 1

    def close(self) -> MaterializedIndexes:
        self.block_writer.close()
        self.weak_writer.close()
        self.wallet_writer.close()
        self.protocol_writer.close()
        if self.cap_fallback:
            # No scientific result may be derived from a truncated materialization.
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
                cap_fallback_required=True,
            )
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
            cap_fallback_required=False,
        )
