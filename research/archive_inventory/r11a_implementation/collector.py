from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import shutil
import struct
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Iterator, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.archive_inventory.r10_implementation import collector as transport_base
from research.archive_inventory.r11a_implementation import diagnostic, identity, schema, storage
from research.archive_inventory.r11a_implementation.limits import DEFAULT_LIMITS, R11ALimits

BASE = ROOT / "research/archive_inventory"
PREREGISTRATION = BASE / "r11a/R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_PREREGISTRATION.json"
SELECTION = BASE / "r11/R11_72H_SELECTION.json"
PRIOR_RESULT = BASE / "r11_evidence/run-31436753081/r11-result.json"
IMPLEMENTATION_CONTRACT = BASE / "r11a_implementation/R11A_IMPLEMENTATION_CONTRACT.json"
RELEASE_PATH = BASE / "r11a_runtime/R11A_EXECUTION_RELEASE.json"

DIAGNOSTIC_ID = "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-001"
PREREGISTRATION_MERGE = "5103c846be8a53732d8559a281ac8b57ce4d7aac"
PARENT_EVIDENCE_MERGE = "f7aa612d2a5638cce0fd197f57efea4b787f87f1"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-identity-r11a"
EXPECTED_ACCOUNT_ID = "630956766927"
EXPECTED_SESSION_NAME = "HLArchiveR11AIdentity"
REGIONAL_ENDPOINT = "hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com"
BLOCK_PAYLOAD = struct.Struct(">HQ")
EVENT_PAYLOAD = struct.Struct(">HQI")
MAX_RECORD_BYTES = 32 * 1024 * 1024


class R11ACollectorError(ValueError):
    """Raised when R11A cannot preserve its exact fail-closed contract."""


@dataclass(frozen=True, slots=True)
class Target:
    object_ordinal_zero_based: int
    path_hour_utc: str
    object_key: str
    expected_size_bytes: int
    expected_etag: str
    expected_compressed_sha256: str
    prior_decompressed_byte_count: int
    prior_block_record_count: int
    prior_event_pair_count: int

    @property
    def source(self) -> identity.SourceObject:
        return identity.SourceObject(
            self.object_ordinal_zero_based,
            self.object_key,
            self.expected_compressed_sha256,
            self.path_hour_utc,
        )


@dataclass(frozen=True, slots=True)
class ParseSummary:
    pass_ordinal_one_based: int
    decompressed_byte_count: int
    decompressed_stream_sha256: str
    raw_record_count: int
    raw_event_observation_count: int
    valid_tid_observation_count: int
    tid_schema_violation_observation_count: int
    valid_coin_observation_count: int
    coin_schema_violation_observation_count: int
    valid_wallet_observation_count: int
    wallet_schema_violation_observation_count: int
    block_index_record_count: int
    legacy_weak_key_index_record_count: int
    schema_violation_index_record_count: int
    ordered_raw_record_sha256_stream_sha256: str
    index_commitment_sha256: str

    def equality_projection(self) -> tuple[object, ...]:
        return tuple(
            value
            for field, value in dataclasses.asdict(self).items()
            if field != "pass_ordinal_one_based"
        )


@dataclass(frozen=True, slots=True)
class ObjectRun:
    target: Target
    compressed_path: Path
    first_pass: ParseSummary
    second_pass: ParseSummary | None = None

    def ledger_row(self, status: str) -> dict[str, object]:
        return {
            "record_type": "OBJECT_TRANSPORT_AND_TWO_PASS_CONSERVATION",
            "object_ordinal_zero_based": self.target.object_ordinal_zero_based,
            "processing_status": status,
            "path_hour_utc": self.target.path_hour_utc,
            "source_object_key": self.target.object_key,
            "expected_etag": self.target.expected_etag,
            "observed_etag": self.target.expected_etag,
            "expected_content_length": self.target.expected_size_bytes,
            "observed_content_length": self.target.expected_size_bytes,
            "expected_compressed_object_sha256": self.target.expected_compressed_sha256,
            "observed_compressed_object_sha256": self.target.expected_compressed_sha256,
            "get_object_request_count": 1,
            "retry_count": 0,
            "first_local_parse": dataclasses.asdict(self.first_pass),
            "second_local_parse": dataclasses.asdict(self.second_pass) if self.second_pass else None,
        }


@dataclass(slots=True)
class Discovery:
    repeated_block_locators: set[tuple[int, int]]
    repeated_observation_locators: set[tuple[int, int, int]]
    schema_block_locators: set[tuple[int, int]]
    reducer_rows: list[dict[str, object]]
    repeated_block_group_count: int
    repeated_block_observation_count: int
    legacy_repeat_group_count: int
    legacy_repeat_observation_count: int

    @property
    def interesting_blocks(self) -> set[tuple[int, int]]:
        result = set(self.repeated_block_locators)
        result.update(self.schema_block_locators)
        result.update((object_ordinal, record_ordinal) for object_ordinal, record_ordinal, _ in self.repeated_observation_locators)
        return result


@dataclass(frozen=True, slots=True)
class ExecutionOutcome:
    return_code: int
    terminal_class: str
    root_cause_claim_status: str
    artifact_directory: Path
    result: Mapping[str, object]


def _strict_dict(path: Path) -> dict[str, object]:
    value = identity.strict_json_loads(path.read_bytes())
    if not isinstance(value, dict):
        raise R11ACollectorError(f"JSON root must be object: {path}")
    return value


def frozen_targets() -> tuple[Target, ...]:
    selection = _strict_dict(SELECTION)
    prior = _strict_dict(PRIOR_RESULT)
    selected = selection.get("exact_targets")
    prior_rows = prior.get("per_hour_summaries")
    if not isinstance(selected, list) or not isinstance(prior_rows, list):
        raise R11ACollectorError("selection or prior result rows absent")
    if len(selected) != 72 or len(prior_rows) != 72:
        raise R11ACollectorError("R11A exact selection cardinality drift")
    prior_by_key = {row["object_key"]: row for row in prior_rows if isinstance(row, dict)}
    targets: list[Target] = []
    for ordinal, row in enumerate(selected):
        if not isinstance(row, dict):
            raise R11ACollectorError("selection target must be object")
        key = row["key"]
        observed = prior_by_key.get(key)
        if not isinstance(observed, dict):
            raise R11ACollectorError(f"prior result missing target: {key}")
        target = Target(
            object_ordinal_zero_based=ordinal,
            path_hour_utc=row["path_hour_utc"],
            object_key=key,
            expected_size_bytes=row["expected_size_bytes"],
            expected_etag=row["expected_etag"],
            expected_compressed_sha256=observed["compressed_sha256"],
            prior_decompressed_byte_count=observed["decompressed_byte_count"],
            prior_block_record_count=observed["block_record_count"],
            prior_event_pair_count=observed["event_pair_count"],
        )
        if observed["path_hour_utc"] != target.path_hour_utc:
            raise R11ACollectorError("selection/prior path-hour drift")
        if observed["expected_etag"] != target.expected_etag:
            raise R11ACollectorError("selection/prior ETag drift")
        if observed["expected_content_length"] != target.expected_size_bytes:
            raise R11ACollectorError("selection/prior content-length drift")
        targets.append(target)
    if sum(row.expected_size_bytes for row in targets) != DEFAULT_LIMITS.maximum_total_compressed_bytes:
        raise R11ACollectorError("selection compressed-byte conservation drift")
    if len({row.object_key for row in targets}) != 72:
        raise R11ACollectorError("duplicate selection object key")
    return tuple(targets)


def validate_static_inputs(*, require_release: bool) -> None:
    prereg = _strict_dict(PREREGISTRATION)
    if prereg.get("diagnostic_id") != DIAGNOSTIC_ID or prereg.get("status") != "PREREGISTERED_NO_EXECUTION":
        raise R11ACollectorError("R11A preregistration identity drift")
    closure = prereg.get("canonical_r11_evidence_closure_binding")
    if not isinstance(closure, dict) or closure.get("canonical_merge_commit_sha") != PARENT_EVIDENCE_MERGE:
        raise R11ACollectorError("R11 evidence closure binding drift")
    if prereg.get("owner_approval_status") != "NOT_PRESENT" or prereg.get("execution_authorized_now") is not False:
        raise R11ACollectorError("preregistration unexpectedly opens execution")
    if not all(value is False for value in prereg.get("current_runtime_authority", {}).values()):
        raise R11ACollectorError("preregistration runtime authority drift")
    envelope = prereg.get("proposed_request_envelope")
    if not isinstance(envelope, dict):
        raise R11ACollectorError("R11A request envelope absent")
    expected = {
        "maximum_get_object_requests": DEFAULT_LIMITS.maximum_get_object_requests,
        "maximum_requests_per_object": DEFAULT_LIMITS.maximum_requests_per_object,
        "maximum_retries_per_request": DEFAULT_LIMITS.maximum_retries_per_request,
        "maximum_total_compressed_bytes": DEFAULT_LIMITS.maximum_total_compressed_bytes,
        "maximum_individual_compressed_bytes": DEFAULT_LIMITS.maximum_individual_compressed_bytes,
        "maximum_total_decompressed_bytes_processed_across_two_local_passes": DEFAULT_LIMITS.maximum_total_decompressed_bytes_across_two_passes,
        "maximum_individual_decompressed_bytes_per_pass": DEFAULT_LIMITS.maximum_individual_decompressed_bytes_per_pass,
        "maximum_ephemeral_workspace_bytes": DEFAULT_LIMITS.maximum_ephemeral_workspace_bytes,
        "minimum_free_workspace_bytes_before_oidc": DEFAULT_LIMITS.minimum_free_workspace_bytes_before_oidc,
        "maximum_retained_artifact_bytes": DEFAULT_LIMITS.maximum_retained_artifact_bytes,
        "maximum_runtime_seconds": DEFAULT_LIMITS.maximum_runtime_seconds,
    }
    for key, value in expected.items():
        if envelope.get(key) != value:
            raise R11ACollectorError(f"frozen request envelope drift: {key}")
    targets = frozen_targets()
    if require_release:
        if not IMPLEMENTATION_CONTRACT.is_file():
            raise R11ACollectorError("canonical R11A implementation contract absent")
        contract = _strict_dict(IMPLEMENTATION_CONTRACT)
        if contract.get("status") != "IMPLEMENTED_AWAITING_OWNER_APPROVAL_NO_EXECUTION":
            raise R11ACollectorError("implementation status drift")
        if contract.get("preregistration_merge_commit") != PREREGISTRATION_MERGE:
            raise R11ACollectorError("implementation preregistration binding drift")
        if not RELEASE_PATH.is_file():
            raise R11ACollectorError("R11A runtime release absent; network execution forbidden")
        release = _strict_dict(RELEASE_PATH)
        if release.get("status") != "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R11A_RUN":
            raise R11ACollectorError("R11A execution release status drift")
        if release.get("single_workflow_dispatch_authorized") is not True:
            raise R11ACollectorError("R11A release does not authorize dispatch")
        if release.get("rerun_authorized") is not False or release.get("release_consumed") is not False:
            raise R11ACollectorError("R11A release single-use state drift")
        if release.get("role_arn") != ROLE_ARN:
            raise R11ACollectorError("R11A release role drift")
        if release.get("maximum_get_object_requests") != len(targets):
            raise R11ACollectorError("R11A release target count drift")


def _iter_decompressed_records(compressed: bytes, *, limits: R11ALimits) -> tuple[Iterator[bytes], dict[str, object]]:
    state = {"decompressed_bytes": 0, "stream_sha256": hashlib.sha256()}

    def iterator() -> Iterator[bytes]:
        pending = bytearray()
        try:
            chunks: Iterable[bytes] = transport_base.iter_lz4_frame(
                compressed,
                limits.maximum_individual_decompressed_bytes_per_pass,
            )
            for chunk in chunks:
                state["decompressed_bytes"] += len(chunk)
                if state["decompressed_bytes"] > limits.maximum_individual_decompressed_bytes_per_pass:
                    raise R11ACollectorError("individual decompressed pass cap exceeded")
                state["stream_sha256"].update(chunk)
                pending.extend(chunk)
                while True:
                    newline = pending.find(b"\n")
                    if newline < 0:
                        break
                    line = bytes(pending[:newline])
                    del pending[: newline + 1]
                    if not line.strip():
                        raise R11ACollectorError("blank or whitespace-only NDJSON record")
                    if len(line) > MAX_RECORD_BYTES:
                        raise R11ACollectorError("record byte cap exceeded")
                    yield line
                if len(pending) > MAX_RECORD_BYTES:
                    raise R11ACollectorError("record byte cap exceeded before newline")
            if pending:
                line = bytes(pending)
                if not line.strip():
                    raise R11ACollectorError("blank final NDJSON record")
                yield line
        except (transport_base.LZ4FrameError, transport_base.LZ4FrameLimit) as exc:
            raise R11ACollectorError(f"LZ4 decompression failure: {exc}") from exc

    return iterator(), state


def _light_scan_record(
    raw_record: bytes,
    *,
    target: Target,
    record_ordinal: int,
    block_partitions: storage.PartitionSet | None,
    weak_partitions: storage.PartitionSet | None,
    schema_partitions: storage.PartitionSet | None,
    index_commitment,
) -> tuple[int, int, int, int, int, int, int, int, int]:
    parsed = identity.strict_json_loads(raw_record)
    if not isinstance(parsed, dict):
        raise R11ACollectorError("block wrapper must be object")
    for field in ("local_time", "block_time", "block_number", "events"):
        if field not in parsed:
            raise R11ACollectorError(f"block wrapper missing {field}")
    if type(parsed["local_time"]) is not str or not parsed["local_time"]:
        raise R11ACollectorError("local_time must be nonempty string")
    if type(parsed["block_time"]) is not str or not parsed["block_time"]:
        raise R11ACollectorError("block_time must be nonempty string")
    block_number = parsed["block_number"]
    if type(block_number) is not int or not 0 <= block_number <= identity.UINT64_MAX:
        raise R11ACollectorError("block_number must be uint64")
    events = parsed["events"]
    if not isinstance(events, list):
        raise R11ACollectorError("events must be array")
    block_key = block_number.to_bytes(8, "big")
    block_payload = BLOCK_PAYLOAD.pack(target.object_ordinal_zero_based, record_ordinal)
    encoded_block = storage.PartitionSet.encode_record(block_key, block_payload)
    index_commitment.update(b"B" + struct.pack(">I", len(encoded_block)) + encoded_block)
    if block_partitions is not None:
        block_partitions.write(block_key, block_payload)
    valid_tid = tid_invalid = valid_coin = coin_invalid = valid_wallet = wallet_invalid = weak_records = schema_records = 0
    for event_ordinal, event in enumerate(events):
        if not isinstance(event, list) or len(event) != 2 or not isinstance(event[1], dict):
            raise R11ACollectorError("event must be [wallet, fill object]")
        wallet_raw, fill = event
        for field in ("time", "side", "px", "sz", "closedPnl", "crossed"):
            if field not in fill:
                raise R11ACollectorError(f"fill missing {field}")
        if type(fill["time"]) is not int or not 0 <= fill["time"] <= identity.UINT64_MAX:
            raise R11ACollectorError("fill.time must be uint64")
        if type(fill["side"]) is not str or fill["side"] not in {"A", "B"}:
            raise R11ACollectorError("fill.side must be A or B")
        for field in ("px", "sz", "closedPnl"):
            if type(fill[field]) is not str or not fill[field]:
                raise R11ACollectorError(f"fill.{field} must be nonempty string")
        if type(fill["crossed"]) is not bool:
            raise R11ACollectorError("fill.crossed must be boolean")
        wallet = identity.validate_wallet(wallet_raw)
        tid_raw = fill.get("tid", identity.MISSING)
        coin_raw = fill.get("coin", identity.MISSING)
        tid = identity.validate_tid(tid_raw)
        coin = identity.validate_coin(coin_raw)
        valid_tid += tid.status == "VALID_UINT50"
        tid_invalid += tid.status != "VALID_UINT50"
        valid_coin += coin.status == "VALID_EXACT_RAW_NONEMPTY_STRING"
        coin_invalid += coin.status != "VALID_EXACT_RAW_NONEMPTY_STRING"
        valid_wallet += wallet.status == "VALID_EXACT_LOWERCASE_0X40HEX"
        wallet_invalid += wallet.status != "VALID_EXACT_LOWERCASE_0X40HEX"
        legacy_tid = identity.historical_legacy_typed_tid(tid_raw)
        if type(wallet.canonical_value) is str and legacy_tid is not None:
            weak_key = identity.canonical_typed_bytes([wallet.canonical_value, list(legacy_tid)])
            weak_payload = EVENT_PAYLOAD.pack(
                target.object_ordinal_zero_based,
                record_ordinal,
                event_ordinal,
            )
            encoded_weak = storage.PartitionSet.encode_record(weak_key, weak_payload)
            index_commitment.update(b"W" + struct.pack(">I", len(encoded_weak)) + encoded_weak)
            if weak_partitions is not None:
                weak_partitions.write(weak_key, weak_payload)
            weak_records += 1
        violations = (
            tid.status != "VALID_UINT50",
            coin.status != "VALID_EXACT_RAW_NONEMPTY_STRING",
            wallet.status != "VALID_EXACT_LOWERCASE_0X40HEX",
        )
        for unit_ordinal, active in enumerate(violations):
            if not active:
                continue
            schema_key = BLOCK_PAYLOAD.pack(target.object_ordinal_zero_based, record_ordinal)
            schema_payload = bytes([unit_ordinal])
            encoded_schema = storage.PartitionSet.encode_record(schema_key, schema_payload)
            index_commitment.update(b"S" + struct.pack(">I", len(encoded_schema)) + encoded_schema)
            if schema_partitions is not None:
                schema_partitions.write(schema_key, schema_payload)
            schema_records += 1
    return (
        len(events),
        valid_tid,
        tid_invalid,
        valid_coin,
        coin_invalid,
        valid_wallet,
        wallet_invalid,
        weak_records,
        schema_records,
    )


def scan_pass(
    compressed: bytes,
    *,
    target: Target,
    pass_ordinal: int,
    block_partitions: storage.PartitionSet | None = None,
    weak_partitions: storage.PartitionSet | None = None,
    schema_partitions: storage.PartitionSet | None = None,
    materialize_blocks: set[tuple[int, int]] | None = None,
    limits: R11ALimits = DEFAULT_LIMITS,
) -> tuple[ParseSummary, tuple[identity.BlockObservation, ...]]:
    if pass_ordinal not in {1, 2}:
        raise R11ACollectorError("pass ordinal must be one or two")
    records, stream_state = _iter_decompressed_records(compressed, limits=limits)
    raw_records = raw_events = 0
    valid_tid = tid_invalid = valid_coin = coin_invalid = valid_wallet = wallet_invalid = 0
    weak_count = schema_count = 0
    raw_record_digest = hashlib.sha256()
    index_commitment = hashlib.sha256()
    materialized: list[identity.BlockObservation] = []
    for record_ordinal, raw_record in enumerate(records):
        raw_records += 1
        raw_record_digest.update(hashlib.sha256(raw_record).digest())
        (
            event_count,
            row_valid_tid,
            row_tid_invalid,
            row_valid_coin,
            row_coin_invalid,
            row_valid_wallet,
            row_wallet_invalid,
            row_weak,
            row_schema,
        ) = _light_scan_record(
            raw_record,
            target=target,
            record_ordinal=record_ordinal,
            block_partitions=block_partitions,
            weak_partitions=weak_partitions,
            schema_partitions=schema_partitions,
            index_commitment=index_commitment,
        )
        raw_events += event_count
        valid_tid += row_valid_tid
        tid_invalid += row_tid_invalid
        valid_coin += row_valid_coin
        coin_invalid += row_coin_invalid
        valid_wallet += row_valid_wallet
        wallet_invalid += row_wallet_invalid
        weak_count += row_weak
        schema_count += row_schema
        if materialize_blocks is not None and (target.object_ordinal_zero_based, record_ordinal) in materialize_blocks:
            materialized.append(
                identity.parse_block_record(
                    raw_record,
                    source=target.source,
                    record_ordinal_zero_based=record_ordinal,
                )
            )
    if stream_state["decompressed_bytes"] != target.prior_decompressed_byte_count:
        raise R11ACollectorError("decompressed byte count differs from retained R11 result")
    if raw_records != target.prior_block_record_count or raw_events != target.prior_event_pair_count:
        raise R11ACollectorError("record/event count differs from retained R11 result")
    summary = ParseSummary(
        pass_ordinal_one_based=pass_ordinal,
        decompressed_byte_count=stream_state["decompressed_bytes"],
        decompressed_stream_sha256=stream_state["stream_sha256"].hexdigest(),
        raw_record_count=raw_records,
        raw_event_observation_count=raw_events,
        valid_tid_observation_count=valid_tid,
        tid_schema_violation_observation_count=tid_invalid,
        valid_coin_observation_count=valid_coin,
        coin_schema_violation_observation_count=coin_invalid,
        valid_wallet_observation_count=valid_wallet,
        wallet_schema_violation_observation_count=wallet_invalid,
        block_index_record_count=raw_records,
        legacy_weak_key_index_record_count=weak_count,
        schema_violation_index_record_count=schema_count,
        ordered_raw_record_sha256_stream_sha256=raw_record_digest.hexdigest(),
        index_commitment_sha256=index_commitment.hexdigest(),
    )
    return summary, tuple(materialized)


def _decode_block_payload(payload: bytes) -> tuple[int, int]:
    if len(payload) != BLOCK_PAYLOAD.size:
        raise R11ACollectorError("block index payload size drift")
    return BLOCK_PAYLOAD.unpack(payload)


def _decode_event_payload(payload: bytes) -> tuple[int, int, int]:
    if len(payload) != EVENT_PAYLOAD.size:
        raise R11ACollectorError("event index payload size drift")
    return EVENT_PAYLOAD.unpack(payload)


def discover(
    *,
    block_partitions: storage.PartitionSet,
    weak_partitions: storage.PartitionSet,
    schema_partitions: storage.PartitionSet,
    workspace: Path,
    meter: storage.WorkspaceMeter,
    limits: R11ALimits = DEFAULT_LIMITS,
) -> Discovery:
    block_locators: set[tuple[int, int]] = set()
    event_locators: set[tuple[int, int, int]] = set()
    schema_blocks: set[tuple[int, int]] = set()
    reducer_rows: list[dict[str, object]] = []
    block_group_count = block_obs_count = weak_group_count = weak_obs_count = 0
    for reducer_id, partitions in (
        ("BLOCK_NUMBER", block_partitions),
        ("HISTORICAL_LEGACY_WEAK_KEY", weak_partitions),
        ("SCHEMA_BLOCK_LOCATOR", schema_partitions),
    ):
        for ordinal in range(256):
            source = partitions.path(ordinal)
            if not source.exists():
                if reducer_id != "SCHEMA_BLOCK_LOCATOR":
                    reducer_rows.append({
                        "record_type": "REDUCER_PARTITION_CONSERVATION",
                        "reducer_id": reducer_id,
                        "partition_ordinal_zero_based": ordinal,
                        "processing_status": "COMPLETE",
                        "record_count": 0,
                        "logical_input_bytes": 0,
                        "unsorted_record_stream_sha256": hashlib.sha256(b"").hexdigest(),
                        "sorted_record_stream_sha256": hashlib.sha256(b"").hexdigest(),
                        "discovered_repeat_group_count": 0,
                        "discovered_repeat_observation_count": 0,
                    })
                continue
            destination = source.with_suffix(".sorted")
            result = storage.external_sort_framed(
                source,
                destination,
                temporary_root=workspace / f"sort-{reducer_id.lower()}-{ordinal:03d}",
                memory_limit_bytes=limits.external_sort_memory_bytes,
                meter=meter,
            )
            group_count = observation_count = 0
            for _, payloads in storage.group_sorted_records(destination):
                if reducer_id == "SCHEMA_BLOCK_LOCATOR":
                    for payload in payloads:
                        if len(payload) != 1:
                            raise R11ACollectorError("schema payload size drift")
                    continue
                if len(payloads) <= 1:
                    continue
                group_count += 1
                observation_count += len(payloads)
                if reducer_id == "BLOCK_NUMBER":
                    for payload in payloads:
                        block_locators.add(_decode_block_payload(payload))
                else:
                    for payload in payloads:
                        event_locators.add(_decode_event_payload(payload))
            if reducer_id == "SCHEMA_BLOCK_LOCATOR":
                for record in storage.iter_framed(destination):
                    key, _ = storage.PartitionSet.decode_record(record)
                    if len(key) != BLOCK_PAYLOAD.size:
                        raise R11ACollectorError("schema block locator key size drift")
                    schema_blocks.add(BLOCK_PAYLOAD.unpack(key))
            if reducer_id == "BLOCK_NUMBER":
                block_group_count += group_count
                block_obs_count += observation_count
            elif reducer_id == "HISTORICAL_LEGACY_WEAK_KEY":
                weak_group_count += group_count
                weak_obs_count += observation_count
            if reducer_id != "SCHEMA_BLOCK_LOCATOR":
                reducer_rows.append({
                    "record_type": "REDUCER_PARTITION_CONSERVATION",
                    "reducer_id": reducer_id,
                    "partition_ordinal_zero_based": ordinal,
                    "processing_status": "COMPLETE",
                    "record_count": result.record_count,
                    "logical_input_bytes": result.logical_input_bytes,
                    "unsorted_record_stream_sha256": result.unsorted_record_stream_sha256,
                    "sorted_record_stream_sha256": result.sorted_record_stream_sha256,
                    "discovered_repeat_group_count": group_count,
                    "discovered_repeat_observation_count": observation_count,
                })
            source.unlink(missing_ok=True)
            meter.checkpoint(f"reduce {reducer_id} partition {ordinal}")
    return Discovery(
        repeated_block_locators=block_locators,
        repeated_observation_locators=event_locators,
        schema_block_locators=schema_blocks,
        reducer_rows=reducer_rows,
        repeated_block_group_count=block_group_count,
        repeated_block_observation_count=block_obs_count,
        legacy_repeat_group_count=weak_group_count,
        legacy_repeat_observation_count=weak_obs_count,
    )


def _science_files(report: diagnostic.DiagnosticReport) -> dict[str, bytes]:
    return {
        "r11a-taxonomy-units.ndjson": schema.deterministic_ndjson(report.taxonomy_units),
        "r11a-block-overlap-matrix.ndjson": schema.deterministic_ndjson(report.block_rows),
        "r11a-duplicate-observations.ndjson": schema.deterministic_ndjson(report.duplicate_rows),
        "r11a-exact-block-replay-proofs.ndjson": schema.deterministic_ndjson(report.replay_proofs),
        "r11a-expected-counterparty-pair-proofs.ndjson": schema.deterministic_ndjson(report.pair_proofs),
        "r11a-protocol-trade-group-members.ndjson": schema.deterministic_ndjson(report.protocol_member_rows),
        "r11a-schema-violation-evidence.ndjson": schema.deterministic_ndjson(report.schema_rows),
    }


def _empty_science() -> dict[str, bytes]:
    return {path: b"" for _, path in schema.SCIENTIFIC_CONTAINERS}


def seal_artifact(
    *,
    staging: Path,
    report: diagnostic.DiagnosticReport,
    context: Mapping[str, object],
    object_rows: Sequence[Mapping[str, object]],
    reducer_rows: Sequence[Mapping[str, object]],
    meter: storage.WorkspaceMeter,
    elapsed_runtime_seconds: int,
    limits: R11ALimits = DEFAULT_LIMITS,
) -> tuple[dict[str, object], dict[str, bytes]]:
    science = _science_files(report)
    projected_science = sum(len(value) for value in science.values())
    if projected_science > limits.maximum_retained_scientific_output_bytes:
        report = dataclasses.replace(
            report,
            terminal_class=diagnostic.TerminalClass.ARTIFACT_CAP_EXCEEDED,
            root_cause_claim_status="NOT_PROVEN",
            retention_caps_exceeded=True,
            duplicate_rows=(),
            block_rows=(),
            replay_proofs=(),
            pair_proofs=(),
            taxonomy_units=(),
            schema_rows=(),
            protocol_member_rows=(),
        )
        science = _empty_science()
    logical_status = (
        "COMPLETE"
        if report.terminal_class is diagnostic.TerminalClass.ROOT_CAUSE_TAXONOMY_COMPLETE
        else "RETENTION_CAP_FALLBACK_EMPTY"
        if report.terminal_class is diagnostic.TerminalClass.ARTIFACT_CAP_EXCEEDED
        else "EARLY_STOP_EMPTY"
    )
    files: dict[str, bytes] = {}
    files.update(science)
    files["r11a-context.json"] = schema.deterministic_json_document(context)
    files["r11a-object-two-pass-conservation.ndjson"] = schema.deterministic_ndjson(object_rows)
    files["r11a-reducer-partition-conservation.ndjson"] = schema.deterministic_ndjson(reducer_rows)
    taxonomy = {
        **report.summary(),
        "all_required_units_classified": report.unclassifiable_group_count == 0,
        "all_proof_references_resolve": True,
        "counts_conserve": report.taxonomy_conservation_passed,
    }
    files["r11a-taxonomy-conservation.json"] = schema.deterministic_json_document(taxonomy)
    scientific_entries = [
        schema.file_reference(path, files[path], logical_status=logical_status)
        for _, path in schema.SCIENTIFIC_CONTAINERS
    ]
    resources = {
        "scientific_output_logical_status": logical_status,
        "peak_ephemeral_workspace_bytes": meter.peak_allocated_bytes,
        "elapsed_runtime_milliseconds": elapsed_runtime_seconds * 1000,
        "get_object_request_count": len(object_rows),
        "retry_count": 0,
        "projected_scientific_output_bytes_before_cap_fallback": projected_science,
        "retained_scientific_output_entry_ledger": scientific_entries,
        "total_retained_scientific_output_bytes": sum(len(files[path]) for _, path in schema.SCIENTIFIC_CONTAINERS),
        "reserved_non_scientific_package_metadata_bytes": limits.reserved_non_scientific_package_metadata_bytes,
        "retention_caps_exceeded": report.retention_caps_exceeded,
    }
    files["r11a-resource-cap-conservation.json"] = schema.deterministic_json_document(resources)
    files["r11a-preflight-stop-evidence.json"] = schema.deterministic_json_document({
        "stop_conditions": [],
        "network_execution_was_release_gated": True,
        "rerun_authorized": False,
    })
    files["r11a-wallet-features.ndjson"] = b""
    return_code = {
        diagnostic.TerminalClass.ROOT_CAUSE_TAXONOMY_COMPLETE: 0,
        diagnostic.TerminalClass.ARTIFACT_CAP_EXCEEDED: 20,
        diagnostic.TerminalClass.DIAGNOSTIC_INCOMPLETE: 21,
    }[report.terminal_class]
    files["r11a.rc"] = f"{return_code}\n".encode("ascii")
    references = {}
    for name, path in schema.SCIENTIFIC_CONTAINERS:
        references[name] = schema.file_reference(path, files[path], logical_status=logical_status)
    for name, path in schema.METADATA_CONTAINERS:
        if path == "r11a-result.json":
            continue
        references[name] = schema.file_reference(path, files[path])
    result = {
        "schema_version": "R11A_RESULT_V1",
        "diagnostic_id": DIAGNOSTIC_ID,
        "container_references": references,
        **report.summary(),
    }
    files["r11a-result.json"] = schema.deterministic_json_document(result)
    for path, data in files.items():
        schema.write_bytes_atomic(staging / path, data)
    manifest = schema.render_hash_manifest(files)
    schema.verify_hash_manifest(manifest, files)
    files["R11A_FILES.sha256"] = manifest
    schema.write_bytes_atomic(staging / "R11A_FILES.sha256", manifest)
    metadata_without_boundary = sum(
        len(data) for path, data in files.items() if path not in {item[1] for item in schema.SCIENTIFIC_CONTAINERS}
    )
    stat = os.statvfs(staging)
    unit = stat.f_frsize
    overwrite_reservation = 2 * ((1024 + unit - 1) // unit) * unit
    boundary = schema.render_package_boundary(
        scientific_output_bytes=sum(len(files[path]) for _, path in schema.SCIENTIFIC_CONTAINERS),
        other_metadata_bytes_excluding_this_record=metadata_without_boundary,
        reserved_metadata_limit_bytes=limits.reserved_non_scientific_package_metadata_bytes,
        artifact_limit_bytes=limits.maximum_retained_artifact_bytes,
        preupload_elapsed_runtime_milliseconds=elapsed_runtime_seconds * 1000,
        hard_runtime_limit_milliseconds=limits.maximum_runtime_seconds * 1000,
        minimum_upload_window_milliseconds=limits.minimum_upload_window_seconds * 1000,
        preupload_peak_workspace_bytes=meter.peak_allocated_bytes,
        filesystem_allocation_unit_bytes=unit,
        boundary_overwrite_allocation_reservation_bytes=overwrite_reservation,
        workspace_limit_bytes=limits.maximum_ephemeral_workspace_bytes,
    )
    schema.verify_package_boundary(boundary)
    files["r11a-package-boundary.txt"] = boundary
    schema.write_bytes_atomic(staging / "r11a-package-boundary.txt", boundary)
    final_size = sum(len(value) for value in files.values())
    if final_size > limits.maximum_retained_artifact_bytes:
        raise R11ACollectorError("sealed artifact exceeds frozen cap")
    meter.checkpoint("seal R11A artifact")
    return result, files


def run_from_compressed_files(
    *,
    targets: Sequence[Target],
    compressed_paths: Mapping[str, Path],
    workspace: Path,
    artifact_directory: Path,
    context: Mapping[str, object],
    limits: R11ALimits = DEFAULT_LIMITS,
) -> ExecutionOutcome:
    started = time.monotonic()
    meter = storage.WorkspaceMeter(workspace, limits)
    meter.bootstrap()
    block_partitions = storage.PartitionSet(workspace / "indices", "blocks", limits=limits, meter=meter)
    weak_partitions = storage.PartitionSet(workspace / "indices", "weak", limits=limits, meter=meter)
    schema_partitions = storage.PartitionSet(workspace / "indices", "schema", limits=limits, meter=meter)
    runs: list[ObjectRun] = []
    total_decompressed = 0
    try:
        for target in targets:
            path = compressed_paths.get(target.object_key)
            if path is None or not path.is_file():
                raise R11ACollectorError(f"compressed object absent: {target.object_key}")
            compressed = path.read_bytes()
            if len(compressed) != target.expected_size_bytes:
                raise R11ACollectorError("compressed size mismatch")
            if hashlib.sha256(compressed).hexdigest() != target.expected_compressed_sha256:
                raise R11ACollectorError("compressed SHA mismatch")
            first, _ = scan_pass(
                compressed,
                target=target,
                pass_ordinal=1,
                block_partitions=block_partitions,
                weak_partitions=weak_partitions,
                schema_partitions=schema_partitions,
                limits=limits,
            )
            total_decompressed += first.decompressed_byte_count
            if total_decompressed > limits.maximum_total_decompressed_bytes_across_two_passes:
                raise R11ACollectorError("aggregate decompressed cap exceeded on first pass")
            runs.append(ObjectRun(target, path, first))
            compressed = b""
            meter.checkpoint(f"first pass object {target.object_ordinal_zero_based}")
    finally:
        block_partitions.close()
        weak_partitions.close()
        schema_partitions.close()
    discovery = discover(
        block_partitions=block_partitions,
        weak_partitions=weak_partitions,
        schema_partitions=schema_partitions,
        workspace=workspace,
        meter=meter,
        limits=limits,
    )
    shutil.rmtree(workspace / "indices", ignore_errors=True)
    meter.checkpoint("remove completed index partitions")
    materialized: list[identity.BlockObservation] = []
    completed_runs: list[ObjectRun] = []
    interesting = discovery.interesting_blocks
    for run in runs:
        compressed = run.compressed_path.read_bytes()
        second, blocks = scan_pass(
            compressed,
            target=run.target,
            pass_ordinal=2,
            materialize_blocks=interesting,
            limits=limits,
        )
        total_decompressed += second.decompressed_byte_count
        if total_decompressed > limits.maximum_total_decompressed_bytes_across_two_passes:
            raise R11ACollectorError("aggregate decompressed cap exceeded on second pass")
        if run.first_pass.equality_projection() != second.equality_projection():
            raise R11ACollectorError("two-pass parse/index commitment mismatch")
        materialized.extend(blocks)
        completed_runs.append(dataclasses.replace(run, second_pass=second))
        run.compressed_path.unlink(missing_ok=True)
        compressed = b""
        meter.checkpoint(f"second pass object {run.target.object_ordinal_zero_based}")
    report = diagnostic.classify(materialized, limits=limits)
    report = dataclasses.replace(
        report,
        raw_block_observation_count=sum(item.first_pass.raw_record_count for item in completed_runs),
        raw_event_observation_count=sum(item.first_pass.raw_event_observation_count for item in completed_runs),
    )
    object_rows = [item.ledger_row("COMPLETE_TWO_LOCAL_PASSES") for item in completed_runs]
    elapsed = int(time.monotonic() - started)
    atomic = storage.AtomicOutputDirectory(artifact_directory, meter=meter)
    with atomic as staging:
        result, _ = seal_artifact(
            staging=staging,
            report=report,
            context=context,
            object_rows=object_rows,
            reducer_rows=discovery.reducer_rows,
            meter=meter,
            elapsed_runtime_seconds=elapsed,
            limits=limits,
        )
        atomic.commit()
    final_terminal = diagnostic.TerminalClass(result["terminal_class"])
    return_code = {
        diagnostic.TerminalClass.ROOT_CAUSE_TAXONOMY_COMPLETE: 0,
        diagnostic.TerminalClass.ARTIFACT_CAP_EXCEEDED: 20,
        diagnostic.TerminalClass.DIAGNOSTIC_INCOMPLETE: 21,
    }[final_terminal]
    return ExecutionOutcome(
        return_code=return_code,
        terminal_class=final_terminal.value,
        root_cause_claim_status=str(result["root_cause_claim_status"]),
        artifact_directory=artifact_directory,
        result=result,
    )


def _network_context() -> dict[str, object]:
    return {
        "schema_version": "R11A_EXECUTION_CONTEXT_V1",
        "diagnostic_id": DIAGNOSTIC_ID,
        "event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "git_ref": os.environ.get("GITHUB_REF"),
        "head_sha": os.environ.get("GITHUB_SHA"),
        "run_id": int(os.environ.get("GITHUB_RUN_ID", "0")),
        "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "0")),
        "expected_account_id": EXPECTED_ACCOUNT_ID,
        "expected_role_arn": ROLE_ARN,
        "expected_session_name": EXPECTED_SESSION_NAME,
        "wallet_feature_output_authorized": False,
        "deduplication_authorized": False,
        "r11b_repair_authorized": False,
    }


def execute_network(
    *,
    workspace: Path,
    artifact_directory: Path,
    transport: Callable[[str, str, dict[str, str], int, float], tuple[int, dict[str, str], bytes]] = transport_base.https_transport,
    request_time: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    env: dict[str, str] | None = None,
    limits: R11ALimits = DEFAULT_LIMITS,
) -> ExecutionOutcome:
    validate_static_inputs(require_release=True)
    started = time.monotonic()
    meter = storage.WorkspaceMeter(workspace, limits)
    meter.require_pre_oidc_free_space()
    targets = frozen_targets()
    compressed_root = workspace / "compressed"
    compressed_root.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    request_count = total_compressed = 0
    for target in targets:
        if request_count >= limits.maximum_get_object_requests:
            raise R11ACollectorError("request cap reached")
        if time.monotonic() - started >= limits.maximum_runtime_seconds:
            raise R11ACollectorError("runtime cap reached before next object")
        transport_target = {
            "path_hour_utc": target.path_hour_utc,
            "key": target.object_key,
            "size": target.expected_size_bytes,
            "etag": target.expected_etag,
        }
        host, path, headers = transport_base.build_signed_request(transport_target, request_time(), env)
        if host != REGIONAL_ENDPOINT or headers.get("If-Match") != target.expected_etag:
            raise R11ACollectorError("signed target or If-Match drift")
        if headers.get("x-amz-request-payer") != "requester":
            raise R11ACollectorError("Requester Pays header absent")
        request_count += 1
        remaining = max(1.0, limits.maximum_runtime_seconds - (time.monotonic() - started))
        status, response_headers, compressed = transport(
            host,
            path,
            headers,
            target.expected_size_bytes,
            remaining,
        )
        if status != 200 or response_headers.get("x-amz-request-charged", "").lower() != "requester":
            raise R11ACollectorError("S3 HTTP or Requester Pays failure")
        if response_headers.get("etag") != target.expected_etag:
            raise R11ACollectorError("response ETag mismatch")
        if len(compressed) != target.expected_size_bytes:
            raise R11ACollectorError("response content length mismatch")
        if hashlib.sha256(compressed).hexdigest() != target.expected_compressed_sha256:
            raise R11ACollectorError("response compressed SHA mismatch")
        total_compressed += len(compressed)
        if total_compressed > limits.maximum_total_compressed_bytes:
            raise R11ACollectorError("aggregate compressed cap exceeded")
        object_path = compressed_root / f"{target.object_ordinal_zero_based:03d}.lz4"
        object_path.write_bytes(compressed)
        paths[target.object_key] = object_path
        compressed = b""
        meter.checkpoint(f"retain compressed object {target.object_ordinal_zero_based}")
    return run_from_compressed_files(
        targets=targets,
        compressed_paths=paths,
        workspace=workspace,
        artifact_directory=artifact_directory,
        context=_network_context(),
        limits=limits,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--artifact-directory", required=True)
    args = parser.parse_args(argv)
    try:
        outcome = execute_network(
            workspace=Path(args.workspace),
            artifact_directory=Path(args.artifact_directory),
        )
    except Exception as exc:
        print(f"R11A_FAIL_CLOSED:{type(exc).__name__}:{exc}", file=sys.stderr)
        return 21
    print(outcome.terminal_class)
    return outcome.return_code


if __name__ == "__main__":
    raise SystemExit(main())
