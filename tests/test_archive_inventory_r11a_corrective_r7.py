from __future__ import annotations

import hashlib
import io
import inspect
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from decimal import Decimal
from pathlib import Path
from unittest import mock

from governance.validate_r11a_execution_artifact_r7 import (
    EvidenceValidationError,
    validate_science,
)
from governance.validate_r11a_runtime_binding_r7 import (
    BINDING,
    RuntimeBindingError,
    validate as validate_runtime_binding,
)
from research.archive_inventory.r11a_corrective.artifact import (
    ArtifactBoundaryError,
    SharedMetadataWriter,
    StreamingScientificEmitter,
    ArtifactSession,
    validate_artifact,
)
from research.archive_inventory.r11a_corrective.artifact_schema import (
    AUTHORITATIVE_UNIT_UNIVERSES,
    BOUNDARY_FILE,
    CONSERVATION_FILE,
    CONTEXT_FILE,
    HASH_MANIFEST_FILE,
    DIAGNOSTIC_ID,
    IMPLEMENTATION_ID,
    OBJECT_LEDGER_FILE,
    REDUCER_LEDGER_FILE,
    RESOURCE_LEDGER_FILE,
    RESULT_FILE,
    RETURN_CODE_FILE,
    SCIENCE_CONTAINERS,
    STOP_LEDGER_FILE,
    TAXA,
    WALLET_FEATURE_FILE,
    zero_taxon_counts,
)
from research.archive_inventory.r11a_corrective.canonical import (
    CanonicalJSONError,
    NumberToken,
    canonical_json_bytes,
    mathematically_integral_number,
    strict_json_loads,
)
from research.archive_inventory.r11a_corrective.identity import frame
from research.archive_inventory.r11a_corrective.join_r7 import (
    DiskJoinLedger,
    JoinBoundaryError,
    JoinValidationResult,
)
from research.archive_inventory.r11a_corrective.limits import (
    DEFAULT_LIMITS,
    PREREGISTRATION_PATH,
    SELECTION_PATH,
)
from research.archive_inventory.r11a_corrective.locator_order import (
    canonical_object_locator_ranks,
    raw_locator_order_key,
)
from research.archive_inventory.r11a_corrective.lz4stream import xxh32
from research.archive_inventory.r11a_corrective.meter_r7 import R7WorkspaceMeter
from research.archive_inventory.r11a_corrective.network import AWSCredentials
from research.archive_inventory.r11a_corrective.preflight_artifact_r7 import (
    write_preflight_failure_artifact,
)
from research.archive_inventory.r11a_corrective.runtime import (
    ExecutionEvidenceState,
    RuntimeBoundaryError,
    RuntimeGuard,
)
from research.archive_inventory.r11a_corrective.pricing import PricingSnapshot
from research.archive_inventory.r11a_corrective.selection import (
    DEFAULT_SELECTION,
    R11_RESULT_PATH,
    SelectionError,
    load_selection,
)
from research.archive_inventory.r11a_corrective.storage_r7 import (
    AtomicArtifactDirectory,
    ExactSQLiteMultiplicityLedger,
    MeteredSQLite,
    ReservedBinaryWriter,
    StorageBoundaryError,
    StorageCleanupError,
    directory_size,
    encode_keyed_record,
    external_sort_partition,
    iter_equality_group_spools,
    write_frame,
)
from research.archive_inventory.r11a_corrective.terminal_propagation import (
    TerminalPropagationError,
    validated_terminal_return_code,
)
from research.archive_inventory.r11a_corrective.taxonomy import (
    TaxonomyResult,
    Taxon,
    UnitUniverse,
)

UNIT_FILE = "r11a-v2-taxonomy-units.ndjson"
LEGACY_ROWS_FILE = "r11a-v2-duplicate-observations.ndjson"
PAIR_PROOF_FILE = "r11a-v2-expected-counterparty-pair-proofs.ndjson"
PROTOCOL_ROWS_FILE = "r11a-v2-protocol-trade-group-members.ndjson"


def synthetic_lz4_frame(payload: bytes) -> bytes:
    """One standards-compliant, uncompressed LZ4 frame for synthetic transport."""

    flg = 0x68  # v1, independent blocks, declared content size
    bd = 0x40  # 64 KiB block maximum
    descriptor = bytes((flg, bd)) + len(payload).to_bytes(8, "little")
    header_checksum = bytes(((xxh32(descriptor) >> 8) & 0xFF,))
    block = (0x80000000 | len(payload)).to_bytes(4, "little") + payload
    return b"\x04\x22\x4d\x18" + descriptor + header_checksum + block + b"\0\0\0\0"


def synthetic_object_frame(target: object, *, incomplete: bool) -> bytes:
    ordinal = int(getattr(target, "object_ordinal_zero_based"))
    source_hour = str(getattr(target, "source_path_hour_utc"))
    if ordinal in {0, 1}:
        block_time = DEFAULT_SELECTION.targets[0].source_path_hour_utc
        events: list[object] = [
            [
                "0x" + "1" * 40,
                {"coin": "BTC", "side": "A", "tid": 7},
            ]
        ]
        if not incomplete:
            events.append(
                [
                    "0x" + "2" * 40,
                    {"coin": "BTC", "side": "B", "tid": 7},
                ]
            )
        block_number = ordinal + 1 if incomplete else 1
    else:
        block_time = source_hour
        events = []
        block_number = 1_000 + ordinal
    record = canonical_json_bytes(
        {
            "block_number": block_number,
            "block_time": block_time,
            "events": events,
            "local_time": source_hour,
        }
    )
    return synthetic_lz4_frame(record)


def synthetic_pricing_snapshot() -> PricingSnapshot:
    return PricingSnapshot(
        status="BOUND_CURRENT_OFFICIAL_SNAPSHOT",
        region="ap-northeast-1",
        currency="USD",
        get_request_usd_per_1000=Decimal(0),
        data_transfer_out_usd_per_gib=Decimal(0),
        usd_per_eur=Decimal(1),
        contingency_multiplier=Decimal(1),
        aws_pricing_source_url="https://example.invalid/aws-test-boundary",
        aws_pricing_source_sha256="1" * 64,
        ecb_fx_source_url="https://example.invalid/ecb-test-boundary",
        ecb_fx_source_sha256="2" * 64,
        snapshot_sha256="3" * 64,
        observed_at_utc="2026-01-01T00:00:00Z",
    )


def execute_public_synthetic_route(
    workspace: Path,
    *,
    incomplete: bool,
) -> tuple[int, Path]:
    """Exercise the workflow's public entrypoint; replace only external inputs.

    Pricing remains a deliberately unbound future stage, so the test injects a
    zero-cost deterministic snapshot.  The download replacement is the external
    transport boundary; all state, storage, parsing, reducer, proof, artifact,
    and terminal code remains production code.
    """

    from research.archive_inventory.r11a_corrective import entrypoint

    workspace.parent.mkdir(parents=True, exist_ok=True)
    context_path = workspace.parent / f"{workspace.name}-context.json"
    principal_path = workspace.parent / f"{workspace.name}-principal.json"
    digest = "4" * 64
    context_path.write_bytes(
        canonical_json_bytes(
            {
                "event_name": "workflow_dispatch",
                "dispatch_ref": "refs/heads/main",
                "dispatch_sha": "a" * 40,
                "checked_out_commit": "a" * 40,
                "workflow_run_id": 1,
                "workflow_run_attempt": 1,
                "workflow_start_epoch_ns": time.time_ns() - 1_000_000_000,
                "repository": "Mathisve1/onchain-wallet-intelligence-lab",
                "workflow_name": (
                    "Hyperliquid Archive R11A Identity Boundary Diagnostic"
                ),
                "approval_id": "SYNTHETIC_TEST_ONLY",
                "approval_text_sha256": digest,
                "execution_release_id": "SYNTHETIC_TEST_ONLY",
                "execution_release_blob_sha256": digest,
                "activation_id": "SYNTHETIC_TEST_ONLY",
                "implementation_contract_sha256": digest,
                "workflow_sha256": digest,
                "collector_sha256": digest,
                "validator_sha256": digest,
                "selection_sha256": digest,
                "pricing_snapshot_sha256": digest,
                "single_use_window_start_utc": "2026-01-01T00:00:00Z",
            }
        )
    )
    principal_path.write_bytes(
        canonical_json_bytes(
            {
                "Account": "630956766927",
                "Arn": (
                    "arn:aws:sts::630956766927:assumed-role/"
                    "onchain-wallet-intelligence-hl-archive-identity-r11a/"
                    "HLArchiveR11AIdentityBoundary"
                ),
                "UserId": "AROA:HLArchiveR11AIdentityBoundary",
            }
        )
    )

    def synthetic_download(
        *,
        target: object,
        destination: Path,
        credentials: AWSCredentials,
        state: ExecutionEvidenceState,
        meter: R7WorkspaceMeter,
        runtime_guard: RuntimeGuard,
        budget_guard: object,
        **_: object,
    ) -> Path:
        del credentials
        getattr(budget_guard, "authorize_request")(
            request_ordinal_zero_based=state.network_request_count,
            expected_response_bytes=int(getattr(target, "expected_size_bytes")),
        )
        ordinal = int(getattr(target, "object_ordinal_zero_based"))
        expected_size = int(getattr(target, "expected_size_bytes"))
        expected_etag = str(getattr(target, "expected_etag"))
        expected_sha = str(getattr(target, "expected_compressed_sha256"))
        state.request_sent(ordinal)
        state.response_metadata(
            ordinal,
            http_status=200,
            etag=expected_etag,
            content_length=expected_size,
            requester_charged="requester",
        )
        with ReservedBinaryWriter(
            destination,
            meter,
            maximum_bytes=expected_size,
            label=f"synthetic external transport {ordinal}",
            buffer_bytes=1,
        ) as writer:
            writer.write(synthetic_object_frame(target, incomplete=incomplete))
        # The external transport mock supplies already integrity-verified body
        # evidence; downstream production code never receives a bypass flag.
        state.body_progress(ordinal, expected_size)
        state.body_complete(ordinal, expected_sha)
        runtime_guard.check_scientific_phase("synthetic transport complete")
        return destination

    environment = {
        "AWS_ACCESS_KEY_ID": "SYNTHETIC",
        "AWS_SECRET_ACCESS_KEY": "SYNTHETIC",
        "AWS_SESSION_TOKEN": "SYNTHETIC",
    }
    with mock.patch.object(
        entrypoint.PricingSnapshot,
        "load",
        return_value=synthetic_pricing_snapshot(),
    ), mock.patch.dict(os.environ, environment, clear=False), mock.patch(
        "research.archive_inventory.r11a_corrective."
        "_runner_core_r7.download_exact_object",
        side_effect=synthetic_download,
    ), redirect_stdout(io.StringIO()):
        return_code = entrypoint.execute(
            workspace,
            context_path,
            principal_path,
        )
    return return_code, workspace / "r11a-v2-artifact"


def read_ndjson(path: Path) -> list[dict[str, object]]:
    return [json.loads(raw) for raw in path.read_bytes().splitlines()]


def exception_graph(root: BaseException) -> tuple[BaseException, ...]:
    pending = [root]
    observed: list[BaseException] = []
    visited: set[int] = set()
    while pending:
        current = pending.pop(0)
        if id(current) in visited:
            continue
        visited.add(id(current))
        observed.append(current)
        for child in (current.__cause__, current.__context__):
            if child is not None:
                pending.append(child)
    return tuple(observed)


def write_ndjson(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_bytes(b"".join(canonical_json_bytes(row) for row in rows))


def refresh_artifact_bindings(artifact: Path) -> None:
    """Rebind a deliberately mutated artifact before adversarial validation."""

    result_path = artifact / RESULT_FILE
    result = json.loads(result_path.read_bytes())
    scientific_files = result.get("scientific_files")
    if isinstance(scientific_files, dict):
        for name in SCIENCE_CONTAINERS:
            payload = (artifact / name).read_bytes()
            evidence = scientific_files[name]
            evidence["byte_count"] = len(payload)
            evidence["row_count"] = len(payload.splitlines())
            evidence["sha256"] = hashlib.sha256(payload).hexdigest()
    result_path.write_bytes(canonical_json_bytes(result))

    names = sorted(
        (
            path.name
            for path in artifact.iterdir()
            if path.is_file()
            and path.name not in {HASH_MANIFEST_FILE, BOUNDARY_FILE}
        ),
        key=lambda value: value.encode("utf-8"),
    )
    (artifact / HASH_MANIFEST_FILE).write_bytes(
        (
            "\n".join(
                f"{hashlib.sha256((artifact / name).read_bytes()).hexdigest()}  {name}"
                for name in names
            )
            + "\n"
        ).encode("ascii")
    )

    boundary_path = artifact / BOUNDARY_FILE
    boundary = json.loads(boundary_path.read_bytes().rstrip(b" \n") + b"\n")
    preboundary = [
        path for path in artifact.iterdir() if path.name != BOUNDARY_FILE
    ]
    boundary["preboundary_file_count"] = len(preboundary)
    boundary["preboundary_bytes"] = sum(path.stat().st_size for path in preboundary)
    boundary["metadata_bytes"] = sum(
        path.stat().st_size
        for path in preboundary
        if path.name not in SCIENCE_CONTAINERS
    )
    encoded = canonical_json_bytes(boundary, final_newline=False)
    if len(encoded) + 1 > DEFAULT_LIMITS.package_boundary_bytes:
        raise AssertionError("mutated test boundary exceeds exact package size")
    boundary_path.write_bytes(
        encoded
        + b" " * (DEFAULT_LIMITS.package_boundary_bytes - len(encoded) - 1)
        + b"\n"
    )


def copy_artifact(source: Path, root: Path, name: str) -> Path:
    destination = root / name
    shutil.copytree(source, destination)
    return destination


def one_record_zero_event_conservation() -> dict[str, int]:
    return {
        "raw_block_observation_count": 1,
        "raw_event_observation_count": 0,
        "valid_wallet_occurrence_count": 0,
        "invalid_wallet_occurrence_count": 0,
        "valid_coin_occurrence_count": 0,
        "invalid_coin_occurrence_count": 0,
        "valid_tid_occurrence_count": 0,
        "invalid_tid_occurrence_count": 0,
        "protocol_trade_identity_occurrence_count": 0,
        "wallet_fill_identity_occurrence_count": 0,
        "local_time_path_prefix_match_count": 1,
        "block_time_path_prefix_match_count": 1,
        "block_time_previous_prefix_match_count": 0,
        "block_time_other_prefix_count": 0,
    }


def fixture_unit_projection(
    *,
    occurrence_count: int = 1,
    key_value: str = "fixture",
    unit_universe: str = "LEGACY_REPEAT_OCCURRENCE",
    primary_taxon: str = "TID_SCOPE_FALSE_POSITIVE",
) -> bytes:
    return canonical_json_bytes(
        {
            "diagnostic_id": DIAGNOSTIC_ID,
            "unit_universe": unit_universe,
            "key_projection": {"fixture": key_value},
            "primary_taxon": primary_taxon,
            "occurrence_count": occurrence_count,
        },
        final_newline=False,
    )


def zero_universe_rows() -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "unit_universe": universe,
            "group_count": 0,
            "occurrence_count": 0,
            "primary_taxon_group_counts": zero_taxon_counts(),
            "primary_taxon_occurrence_counts": zero_taxon_counts(),
            "unclassifiable_group_count": 0,
            "unclassifiable_occurrence_count": 0,
        }
        for universe in AUTHORITATIVE_UNIT_UNIVERSES
    )


def one_legacy_universe_rows() -> tuple[dict[str, object], ...]:
    rows = [dict(row) for row in zero_universe_rows()]
    group_counts = zero_taxon_counts()
    occurrence_counts = zero_taxon_counts()
    group_counts["TID_SCOPE_FALSE_POSITIVE"] = 1
    occurrence_counts["TID_SCOPE_FALSE_POSITIVE"] = 1
    rows[0] = {
        "unit_universe": "LEGACY_REPEAT_OCCURRENCE",
        "group_count": 1,
        "occurrence_count": 1,
        "primary_taxon_group_counts": group_counts,
        "primary_taxon_occurrence_counts": occurrence_counts,
        "unclassifiable_group_count": 0,
        "unclassifiable_occurrence_count": 0,
    }
    return tuple(rows)


def one_universe_rows(
    unit_universe: str,
    primary_taxon: str,
) -> tuple[dict[str, object], ...]:
    rows = [dict(row) for row in zero_universe_rows()]
    ordinal = AUTHORITATIVE_UNIT_UNIVERSES.index(unit_universe)
    group_counts = zero_taxon_counts()
    occurrence_counts = zero_taxon_counts()
    group_counts[primary_taxon] = 1
    occurrence_counts[primary_taxon] = 1
    rows[ordinal] = {
        "unit_universe": unit_universe,
        "group_count": 1,
        "occurrence_count": 1,
        "primary_taxon_group_counts": group_counts,
        "primary_taxon_occurrence_counts": occurrence_counts,
        "unclassifiable_group_count": int(primary_taxon == "UNCLASSIFIABLE"),
        "unclassifiable_occurrence_count": int(primary_taxon == "UNCLASSIFIABLE"),
    }
    return tuple(rows)


class CanonicalR7Tests(unittest.TestCase):
    def test_duplicate_json_keys_and_nonfinite_values_fail_closed(self) -> None:
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(CanonicalJSONError):
                strict_json_loads(raw)

    def test_extreme_integral_exponents_are_bounded_before_expansion(self) -> None:
        with self.assertRaises(CanonicalJSONError):
            mathematically_integral_number(
                NumberToken("1e100000000", False)
            )
        self.assertEqual(
            mathematically_integral_number(
                NumberToken("0e-100000000", False)
            ),
            "0",
        )
        self.assertEqual(
            mathematically_integral_number(
                NumberToken("-0.000e+999", False)
            ),
            "0",
        )

    def test_canonical_mapping_is_deeply_immutable_and_utf8_sorted(self) -> None:
        left = strict_json_loads(b'{"z":{"b":2,"a":1},"a":0}')
        right = strict_json_loads(b'{"a":0,"z":{"a":1,"b":2}}')
        self.assertEqual(canonical_json_bytes(left), canonical_json_bytes(right))
        with self.assertRaises(TypeError):
            left["a"] = "mutated"  # type: ignore[index]

    def test_critical_boundaries_remain_active_under_python_optimized_mode(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = """
from research.archive_inventory.r11a_corrective.canonical import CanonicalJSONError, strict_json_loads
from research.archive_inventory.r11a_corrective.artifact_schema import validate_terminal_tuple
for raw in (b'{\"a\":1,\"a\":2}', b'{\"a\":NaN}'):
    try:
        strict_json_loads(raw)
    except CanonicalJSONError:
        pass
    else:
        raise SystemExit('strict JSON boundary disappeared under -O')
try:
    validate_terminal_tuple(
        terminal_class='R11A_V2_ROOT_CAUSE_TAXONOMY_COMPLETE',
        return_code=20,
        scientific_output_status='COMPLETE',
        root_cause_claim_status='PROVEN',
    )
except ValueError:
    pass
else:
    raise SystemExit('terminal boundary disappeared under -O')
"""
        completed = subprocess.run(
            [sys.executable, "-O", "-c", source],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


class SelectionBindingTests(unittest.TestCase):
    def test_exact_72_targets_are_bound_to_prior_r11_compressed_hashes(self) -> None:
        self.assertEqual(len(DEFAULT_SELECTION.targets), 72)
        self.assertEqual(
            sum(target.expected_size_bytes for target in DEFAULT_SELECTION.targets),
            2_107_738_436,
        )
        self.assertEqual(
            len(
                {
                    target.expected_compressed_sha256
                    for target in DEFAULT_SELECTION.targets
                }
            ),
            72,
        )

    def test_tampered_prior_r11_result_is_rejected_before_target_loading(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "r11-result.json"
            tampered.write_bytes(R11_RESULT_PATH.read_bytes() + b"\n")
            with self.assertRaises(SelectionError):
                load_selection(
                    path=SELECTION_PATH,
                    prior_result_path=tampered,
                    preregistration_path=PREREGISTRATION_PATH,
                )


class ExactDiskEvidenceTests(unittest.TestCase):
    def meter(self, root: Path) -> R7WorkspaceMeter:
        guard = RuntimeGuard(DEFAULT_LIMITS)
        meter = R7WorkspaceMeter(root, DEFAULT_LIMITS, guard)
        meter.bootstrap()
        return meter

    def test_exact_sqlite_blob_multiplicity_detects_loss_and_duplication(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            ledger = ExactSQLiteMultiplicityLedger(
                meter.root / "multiplicity.sqlite",
                meter,
                maximum_source_bytes=1024,
            )
            ledger.add_source_batch((b"a", b"a", b"b"))
            ledger.add_destination_batch((b"a", b"b", b"b"))
            with self.assertRaises(StorageBoundaryError):
                ledger.validate()
            ledger.close_delete()

    def test_disk_join_requires_exact_foreign_keys_projections_and_row_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            joins = DiskJoinLedger(meter)
            unit_projection = fixture_unit_projection()
            proof_projection = b"proof"
            joins.add_unit(
                "u",
                "LEGACY_REPEAT_OCCURRENCE",
                1,
                unit_projection,
            )
            joins.add_proof("p", "proof-type", proof_projection)
            joins.add_reference(
                "u",
                "p",
                "proof-type",
                unit_projection,
                proof_projection,
            )
            joins.add_retained_row("r", "u", unit_projection)
            result = joins.validate()
            self.assertTrue(
                result.all_nonnull_proof_references_resolve_exactly_once
            )
            self.assertTrue(result.all_referenced_projections_are_byte_equal)
            self.assertTrue(
                result.all_retained_row_counts_match_unit_occurrence_counts
            )
            joins.close_delete()

    def test_retained_row_loss_is_detected_for_every_unit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            joins = DiskJoinLedger(meter)
            projection = fixture_unit_projection(occurrence_count=2)
            joins.add_unit(
                "u",
                "LEGACY_REPEAT_OCCURRENCE",
                2,
                projection,
            )
            joins.add_retained_row("r1", "u", projection)
            result = joins.validate()
            self.assertFalse(
                result.all_retained_row_counts_match_unit_occurrence_counts
            )
            joins.close_delete()

    def test_wrong_retained_projection_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            joins = DiskJoinLedger(meter)
            projection = fixture_unit_projection()
            joins.add_unit(
                "u",
                "LEGACY_REPEAT_OCCURRENCE",
                1,
                projection,
            )
            joins.add_retained_row("r", "u", b"wrong-projection")
            result = joins.validate()
            self.assertFalse(result.all_referenced_projections_are_byte_equal)
            joins.close_delete()

    def test_dangling_proof_reference_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            joins = DiskJoinLedger(meter)
            projection = fixture_unit_projection()
            joins.add_unit(
                "u",
                "LEGACY_REPEAT_OCCURRENCE",
                1,
                projection,
            )
            joins.add_reference(
                "u",
                "missing",
                "proof-type",
                projection,
                b"missing-proof",
            )
            joins.add_retained_row("r", "u", projection)
            result = joins.validate()
            self.assertFalse(
                result.all_nonnull_proof_references_resolve_exactly_once
            )
            joins.close_delete()

    def test_duplicate_unit_ids_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            joins = DiskJoinLedger(meter)
            joins.add_unit(
                "u",
                "LEGACY_REPEAT_OCCURRENCE",
                1,
                fixture_unit_projection(key_value="one"),
            )
            joins.add_unit(
                "u",
                "LEGACY_REPEAT_OCCURRENCE",
                1,
                fixture_unit_projection(key_value="two"),
            )
            with self.assertRaises(JoinBoundaryError):
                joins.validate()
            joins.database.close_delete()

    def test_extra_retained_row_is_detected_for_every_unit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            joins = DiskJoinLedger(meter)
            projection = fixture_unit_projection()
            joins.add_unit("u", "LEGACY_REPEAT_OCCURRENCE", 1, projection)
            joins.add_retained_row("r1", "u", projection)
            joins.add_retained_row("r2", "u", projection)
            result = joins.validate()
            self.assertFalse(
                result.all_retained_row_counts_match_unit_occurrence_counts
            )
            joins.close_delete()

    def test_duplicate_proof_ids_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            joins = DiskJoinLedger(meter)
            joins.add_proof("p", "proof-type", b"one")
            joins.add_proof("p", "proof-type", b"two")
            with self.assertRaises(JoinBoundaryError):
                joins.validate()
            joins.database.close_delete()

    def test_duplicate_proof_foreign_keys_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            joins = DiskJoinLedger(meter)
            projection = fixture_unit_projection()
            joins.add_unit("u", "LEGACY_REPEAT_OCCURRENCE", 1, projection)
            joins.add_proof("p", "proof-type", b"proof")
            for _ in range(2):
                joins.add_reference(
                    "u",
                    "p",
                    "proof-type",
                    projection,
                    b"proof",
                )
            with self.assertRaises(JoinBoundaryError):
                joins.validate()
            joins.database.close_delete()

    def test_wrong_proof_projection_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            joins = DiskJoinLedger(meter)
            projection = fixture_unit_projection()
            joins.add_unit("u", "LEGACY_REPEAT_OCCURRENCE", 1, projection)
            joins.add_proof("p", "proof-type", b"proof")
            joins.add_reference(
                "u",
                "p",
                "proof-type",
                projection,
                b"wrong-proof",
            )
            joins.add_retained_row("r", "u", projection)
            result = joins.validate()
            self.assertFalse(result.all_referenced_projections_are_byte_equal)
            joins.close_delete()

    def test_unreferenced_proof_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            joins = DiskJoinLedger(meter)
            joins.add_proof("p", "proof-type", b"proof")
            result = joins.validate()
            self.assertFalse(
                result.all_nonnull_proof_references_resolve_exactly_once
            )
            joins.close_delete()


class WorkspaceAccountingTests(unittest.TestCase):
    def meter(self, root: Path) -> R7WorkspaceMeter:
        guard = RuntimeGuard(DEFAULT_LIMITS)
        meter = R7WorkspaceMeter(root, DEFAULT_LIMITS, guard)
        meter.bootstrap()
        return meter

    def write_payload(
        self,
        meter: R7WorkspaceMeter,
        path: Path,
        payload: bytes = b"payload",
    ) -> None:
        with ReservedBinaryWriter(
            path,
            meter,
            maximum_bytes=1024,
            label="atomic fixture",
            packaging=True,
            buffer_bytes=1,
        ) as writer:
            writer.write(payload)

    def test_atomic_rename_preserves_identical_bytes_and_accounting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            atomic = AtomicArtifactDirectory(meter.root, meter, "artifact")
            staging = atomic.__enter__()
            self.write_payload(meter, staging / "payload.bin")
            before = (staging / "payload.bin").read_bytes()
            tracked = meter.verify_actual_usage()
            final = atomic.commit(
                lambda candidate: self.assertEqual(
                    (candidate / "payload.bin").read_bytes(),
                    before,
                )
            )
            self.assertEqual((final / "payload.bin").read_bytes(), before)
            self.assertEqual(meter.known_bytes, tracked)
            self.assertEqual(meter.verify_actual_usage(), directory_size(final))
            meter.checked_rmtree(final)
            self.assertEqual(meter.verify_actual_usage(), 0)

    def test_post_rename_runtime_failure_removes_final_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            atomic = AtomicArtifactDirectory(meter.root, meter, "artifact")
            staging = atomic.__enter__()
            self.write_payload(meter, staging / "payload.bin")
            original = RuntimeGuard.check_packaging_phase

            def fail_after_rename(guard: RuntimeGuard, phase: str) -> None:
                if phase == "artifact rename after":
                    raise RuntimeError("injected post-rename runtime failure")
                original(guard, phase)

            with mock.patch.object(
                RuntimeGuard,
                "check_packaging_phase",
                side_effect=fail_after_rename,
                autospec=True,
            ):
                with self.assertRaises(RuntimeError):
                    atomic.commit(lambda _: None)
            self.assertFalse(atomic.final_path.exists())
            self.assertFalse(atomic.staging_path.exists())
            self.assertEqual(meter.verify_actual_usage(), 0)

    def test_post_rename_workspace_failure_removes_final_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            atomic = AtomicArtifactDirectory(meter.root, meter, "artifact")
            staging = atomic.__enter__()
            self.write_payload(meter, staging / "payload.bin")
            tracked = meter.known_bytes
            with mock.patch.object(
                meter,
                "verify_actual_usage",
                side_effect=(
                    tracked,
                    StorageBoundaryError("injected post-rename workspace failure"),
                    0,
                ),
            ):
                with self.assertRaises(StorageBoundaryError):
                    atomic.commit(lambda _: None)
            self.assertFalse(atomic.final_path.exists())
            self.assertFalse(atomic.staging_path.exists())
            self.assertEqual(meter.verify_actual_usage(), 0)

    def test_final_directory_cleanup_failure_remains_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            atomic = AtomicArtifactDirectory(meter.root, meter, "artifact")
            staging = atomic.__enter__()
            self.write_payload(meter, staging / "payload.bin")
            original = RuntimeGuard.check_packaging_phase

            def fail_after_rename(guard: RuntimeGuard, phase: str) -> None:
                if phase == "artifact rename after":
                    raise RuntimeError("injected post-rename runtime failure")
                original(guard, phase)

            with mock.patch.object(
                RuntimeGuard,
                "check_packaging_phase",
                side_effect=fail_after_rename,
                autospec=True,
            ), mock.patch(
                "research.archive_inventory.r11a_corrective.storage_r7.shutil.rmtree",
                side_effect=OSError("injected cleanup failure"),
            ):
                with self.assertRaises(StorageCleanupError):
                    atomic.commit(lambda _: None)
            self.assertTrue(atomic.final_path.exists())
            meter.checked_rmtree(atomic.final_path)
            self.assertEqual(meter.verify_actual_usage(), 0)

    def test_failed_validation_cleanup_failure_remains_fatal_and_accounted(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            atomic = AtomicArtifactDirectory(meter.root, meter, "artifact")
            staging = atomic.__enter__()
            self.write_payload(meter, staging / "payload.bin")
            validations = 0

            def reject(_: Path) -> None:
                nonlocal validations
                validations += 1
                raise ArtifactBoundaryError("injected artifact validation failure")

            with mock.patch(
                "research.archive_inventory.r11a_corrective.storage_r7.shutil.rmtree",
                side_effect=OSError("injected validation rollback cleanup failure"),
            ):
                with self.assertRaises(StorageCleanupError) as raised:
                    atomic.commit(reject)
            self.assertEqual(validations, 1)
            self.assertFalse(atomic.final_path.exists())
            self.assertTrue(atomic.staging_path.exists())
            self.assertEqual(meter.known_bytes, directory_size(meter.root))
            self.assertEqual(
                meter.verify_actual_usage(),
                directory_size(atomic.staging_path),
            )
            with self.assertRaises(StorageCleanupError) as retry:
                atomic.rollback()
            self.assertTrue(
                any(
                    str(value)
                    == "injected validation rollback cleanup failure"
                    for value in exception_graph(raised.exception)
                )
            )
            self.assertTrue(atomic.staging_path.exists())
            self.assertTrue(
                any(
                    str(value)
                    == "injected validation rollback cleanup failure"
                    for value in exception_graph(retry.exception)
                )
            )
            meter.checked_rmtree(atomic.staging_path)
            self.assertEqual(meter.verify_actual_usage(), 0)

    def test_metadata_close_and_shared_directory_reservations_are_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            staging = meter.root / "staging"
            staging.mkdir()
            science = StreamingScientificEmitter(staging, meter, DEFAULT_LIMITS)
            science.emit(UNIT_FILE, {"fixture": "science"})
            science.close()
            metadata = SharedMetadataWriter(staging, meter, DEFAULT_LIMITS)
            metadata.write("fixture-metadata.json", b"{}\n")
            metadata.close()
            self.assertEqual(meter.known_bytes, directory_size(staging))
            self.assertEqual(meter.verify_actual_usage(), directory_size(staging))
            meter.checked_rmtree(staging)
            self.assertEqual(meter.verify_actual_usage(), 0)

    def test_fail_closed_scientific_replacement_is_exactly_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            session = ArtifactSession(
                meter.root,
                meter,
                DEFAULT_LIMITS,
                meter.runtime_guard,
            )
            session.emitter.emit(UNIT_FILE, {"fixture": "x" * 70_000})
            self.assertGreater((session.staging / UNIT_FILE).stat().st_size, 0)
            evidence = session._discard_science_and_create_empty()
            self.assertTrue(all(item.byte_count == 0 for item in evidence))
            self.assertTrue(
                all((session.staging / name).read_bytes() == b"" for name in SCIENCE_CONTAINERS)
            )
            self.assertEqual(meter.verify_actual_usage(), 0)
            session.abort()

    def test_tracked_bytes_must_equal_actual_disk_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            payload = meter.root / "payload.bin"
            self.write_payload(meter, payload)
            self.assertEqual(meter.verify_actual_usage(), len(b"payload"))
            with payload.open("ab") as handle:
                handle.write(b"unmetered")
            with self.assertRaises(StorageBoundaryError):
                meter.verify_actual_usage()

    def test_sqlite_rollback_failure_is_fatal_and_cleanup_is_sticky(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            database = MeteredSQLite(
                meter.root / "rollback.sqlite",
                meter,
                1_000_000,
                "rollback fault injection",
            )
            real_connection = database.connection
            self.assertIsNotNone(real_connection)

            class RollbackFailingConnection:
                def __getattr__(self, name: str) -> object:
                    return getattr(real_connection, name)

                def rollback(self) -> None:
                    real_connection.rollback()  # type: ignore[union-attr]
                    raise OSError("injected SQLite rollback cleanup failure")

            database.connection = RollbackFailingConnection()  # type: ignore[assignment]
            with self.assertRaises(StorageCleanupError) as raised:
                with database.transaction("rollback fault"):
                    raise RuntimeError("injected transaction failure")
            graph = exception_graph(raised.exception)
            self.assertTrue(
                any(
                    str(value) == "injected SQLite rollback cleanup failure"
                    for value in graph
                )
            )
            self.assertTrue(
                any(str(value) == "injected transaction failure" for value in graph)
            )

            database.connection = real_connection

            class CloseFailingConnection:
                def __getattr__(self, name: str) -> object:
                    return getattr(real_connection, name)

                def close(self) -> None:
                    real_connection.close()  # type: ignore[union-attr]
                    raise OSError("injected SQLite close cleanup failure")

            database.connection = CloseFailingConnection()  # type: ignore[assignment]
            with self.assertRaises(StorageCleanupError) as first:
                database.close_delete()
            with self.assertRaises(StorageCleanupError) as second:
                database.close_delete()
            self.assertIs(first.exception, second.exception)
            self.assertEqual(meter.reserved_bytes, 0)
            self.assertEqual(meter.known_bytes, 0)
            self.assertEqual(meter.verify_actual_usage(), 0)

    def test_external_sort_surfaces_abandoned_reader_cleanup_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            source = meter.root / "source.frames"
            destination = meter.root / "destination.frames"
            scratch = meter.root / "sort-scratch"
            record = encode_keyed_record(b"key", b"payload")
            with ReservedBinaryWriter(
                source,
                meter,
                maximum_bytes=1024,
                label="external sort source fixture",
                buffer_bytes=1,
            ) as writer:
                write_frame(writer, record)

            real_open = Path.open
            real_write = ReservedBinaryWriter.write
            close_faults = 0
            unraisable: list[object] = []

            class CloseFailingReader:
                def __init__(self, handle: object) -> None:
                    self.handle = handle

                def read(self, size: int = -1) -> bytes:
                    return self.handle.read(size)  # type: ignore[no-any-return,union-attr]

                def close(self) -> None:
                    nonlocal close_faults
                    self.handle.close()  # type: ignore[union-attr]
                    if close_faults == 0:
                        close_faults += 1
                        raise OSError("injected sort reader cleanup failure")

            def wrap_run_reader(
                path: Path,
                mode: str = "r",
                *args: object,
                **kwargs: object,
            ) -> object:
                handle = real_open(path, mode, *args, **kwargs)
                if path.name == "run-000000.frames" and mode == "rb":
                    return CloseFailingReader(handle)
                return handle

            def fail_destination_write(
                writer: ReservedBinaryWriter,
                data: bytes,
            ) -> None:
                if writer.path == destination:
                    raise RuntimeError("injected destination write failure")
                real_write(writer, data)

            with mock.patch.object(
                Path,
                "open",
                autospec=True,
                side_effect=wrap_run_reader,
            ), mock.patch.object(
                ReservedBinaryWriter,
                "write",
                autospec=True,
                side_effect=fail_destination_write,
            ), mock.patch.object(
                sys,
                "unraisablehook",
                side_effect=lambda value: unraisable.append(value),
            ):
                with self.assertRaises(StorageCleanupError) as raised:
                    external_sort_partition(
                        source,
                        destination,
                        scratch,
                        meter,
                        source_record_count=1,
                        source_logical_bytes=len(record),
                        maximum_source_bytes=source.stat().st_size,
                    )

            graph = exception_graph(raised.exception)
            self.assertEqual(close_faults, 1)
            self.assertEqual(unraisable, [])
            self.assertTrue(
                any(
                    str(value) == "injected sort reader cleanup failure"
                    for value in graph
                )
            )
            self.assertTrue(
                any(
                    str(value) == "injected destination write failure"
                    for value in graph
                )
            )
            self.assertFalse(destination.exists())
            self.assertFalse(scratch.exists())
            self.assertEqual(meter.reserved_bytes, 0)
            meter.delete_file(source)
            self.assertEqual(meter.known_bytes, 0)
            self.assertEqual(meter.verify_actual_usage(), 0)

    def test_abandoned_group_spool_cleanup_is_synchronous_and_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            sorted_path = meter.root / "sorted.frames"
            spool = meter.root / "groups"
            record = encode_keyed_record(b"key", b"payload")
            with ReservedBinaryWriter(
                sorted_path,
                meter,
                maximum_bytes=1024,
                label="group spool source fixture",
                buffer_bytes=1,
            ) as writer:
                write_frame(writer, record)

            groups = iter_equality_group_spools(
                sorted_path,
                spool,
                meter,
                maximum_group_spool_bytes=1024,
            )
            group = next(groups)
            real_unlink = Path.unlink
            cleanup_faults = 0
            unraisable: list[object] = []

            def fail_group_cleanup(
                path: Path,
                *args: object,
                **kwargs: object,
            ) -> None:
                nonlocal cleanup_faults
                if path == group.path and cleanup_faults == 0:
                    cleanup_faults += 1
                    raise OSError("injected group spool cleanup failure")
                real_unlink(path, *args, **kwargs)

            with mock.patch.object(
                Path,
                "unlink",
                autospec=True,
                side_effect=fail_group_cleanup,
            ), mock.patch.object(
                sys,
                "unraisablehook",
                side_effect=lambda value: unraisable.append(value),
            ):
                with self.assertRaises(StorageCleanupError) as raised:
                    try:
                        raise RuntimeError("injected group consumer failure")
                    finally:
                        meter.close_owned_iterators()

            graph = exception_graph(raised.exception)
            self.assertEqual(cleanup_faults, 1)
            self.assertEqual(unraisable, [])
            self.assertTrue(
                any(
                    str(value) == "injected group spool cleanup failure"
                    for value in graph
                )
            )
            self.assertTrue(
                any(
                    str(value) == "injected group consumer failure"
                    for value in graph
                )
            )
            self.assertEqual(meter.reserved_bytes, 0)
            meter.delete_file(group.path)
            meter.delete_empty_directory(spool)
            meter.delete_file(sorted_path)
            self.assertEqual(meter.known_bytes, 0)
            self.assertEqual(meter.verify_actual_usage(), 0)

    def test_abandoned_taxonomy_cursors_close_before_scratch_database(self) -> None:
        from research.archive_inventory.r11a_corrective import (
            _taxonomy_contract_core_r7 as contract_core,
        )
        from research.archive_inventory.r11a_corrective import (
            _taxonomy_core_r7 as taxonomy_core,
        )

        cases = (
            (taxonomy_core.GroupScratch, "iter_ordered", {"value": 1}),
            (contract_core.BlockScratch, "ordered_rows", {"value": 1}),
            (contract_core.BlockScratch, "raw_keys", (b"raw-key",)),
        )
        for scratch_type, method_name, row in cases:
            with self.subTest(method=method_name), tempfile.TemporaryDirectory() as temporary:
                meter = self.meter(Path(temporary) / "workspace")
                close_order: list[str] = []
                unraisable: list[object] = []

                class Cursor:
                    def __init__(self) -> None:
                        self.rows = iter((row,))

                    def __iter__(self) -> object:
                        return self

                    def __next__(self) -> object:
                        return next(self.rows)

                    def close(self) -> None:
                        close_order.append("cursor")
                        raise OSError("injected taxonomy cursor cleanup failure")

                cursor = Cursor()

                class Connection:
                    row_factory: object = None

                    def execute(self, statement: str) -> Cursor:
                        del statement
                        return cursor

                class Database:
                    def __init__(self) -> None:
                        self.connection = Connection()

                    def close_delete(self) -> None:
                        close_order.append("database")

                scratch = object.__new__(scratch_type)
                scratch._owned_iterators = []
                scratch._cleanup_failure = None
                scratch.database = Database()
                iterator = getattr(scratch, method_name)()
                next(iterator)

                with mock.patch.object(
                    sys,
                    "unraisablehook",
                    side_effect=lambda value: unraisable.append(value),
                ):
                    with self.assertRaises(taxonomy_core.TaxonomyCleanupError) as raised:
                        try:
                            raise RuntimeError("injected taxonomy consumer failure")
                        finally:
                            scratch.close_delete()

                graph = exception_graph(raised.exception)
                self.assertEqual(close_order, ["cursor", "database"])
                self.assertEqual(unraisable, [])
                self.assertTrue(
                    any(
                        str(value) == "injected taxonomy cursor cleanup failure"
                        for value in graph
                    )
                )
                self.assertTrue(
                    any(
                        str(value) == "injected taxonomy consumer failure"
                        for value in graph
                    )
                )
                self.assertEqual(meter.reserved_bytes, 0)
                self.assertEqual(meter.known_bytes, 0)
                self.assertEqual(meter.verify_actual_usage(), 0)


class RuntimeEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls._temporary.name)
        cls.rc0, cls.complete_artifact = execute_public_synthetic_route(
            cls.root / "complete-workspace",
            incomplete=False,
        )
        cls.rc20, cls.incomplete_artifact = execute_public_synthetic_route(
            cls.root / "incomplete-workspace",
            incomplete=True,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def fresh_complete(self, name: str) -> Path:
        return copy_artifact(self.complete_artifact, self.root, name)

    def fresh_incomplete(self, name: str) -> Path:
        return copy_artifact(self.incomplete_artifact, self.root, name)

    def assert_valid_rc21_recovery(
        self,
        *,
        workspace: Path,
        artifact: Path,
        return_code: int,
        conclusion: str = "ROOT_CAUSE_NOT_PROVEN_FAIL_CLOSED_EMPTY_ARTIFACT",
    ) -> None:
        self.assertEqual(return_code, 21)
        self.assertTrue(artifact.is_dir())
        validate_artifact(artifact, DEFAULT_LIMITS)
        validate_science(artifact)
        result = json.loads((artifact / RESULT_FILE).read_bytes())
        self.assertEqual(
            result["terminal_class"],
            "R11A_V2_FAIL_CLOSED_EARLY_STOP",
        )
        self.assertEqual(
            result["research_conclusion"],
            conclusion,
        )
        self.assertEqual(result["scientific_output_status"], "EMPTY")
        self.assertEqual(result["root_cause_claim_status"], "NOT_PROVEN")
        self.assertEqual(result["return_code"], 21)
        self.assertEqual(result["wallet_feature_rows"], 0)
        self.assertFalse(result["rerun_authorized"])
        self.assertFalse(result["R11_CLOSED"])
        self.assertFalse(result["R12_READY"])
        self.assertEqual(len(SCIENCE_CONTAINERS), 7)
        self.assertTrue(
            all((artifact / name).read_bytes() == b"" for name in SCIENCE_CONTAINERS)
        )
        self.assertEqual((artifact / WALLET_FEATURE_FILE).read_bytes(), b"")
        self.assertEqual((artifact / RETURN_CODE_FILE).read_text(encoding="ascii"), "21\n")
        self.assertEqual(
            {path.name for path in workspace.iterdir()},
            {"r11a-v2-artifact"},
        )
        self.assertFalse((workspace / ".r11a-v2-artifact.staging").exists())
        forbidden_suffixes = (
            "-journal",
            "-wal",
            "-shm",
            ".tmp",
            ".temp",
            ".sidecar",
        )
        self.assertFalse(
            any(
                path.name.endswith(forbidden_suffixes)
                for path in workspace.rglob("*")
            )
        )

    @staticmethod
    def preflight_context(start_epoch_ns: int) -> dict[str, object]:
        return {
            "event_name": "workflow_dispatch",
            "dispatch_ref": "refs/heads/main",
            "dispatch_sha": "1" * 40,
            "checked_out_commit": "1" * 40,
            "workflow_run_id": 1,
            "workflow_run_attempt": 1,
            "workflow_start_epoch_ns": start_epoch_ns,
            "repository": "Mathisve1/onchain-wallet-intelligence-lab",
            "workflow_name": (
                "Hyperliquid Archive R11A Identity Boundary Diagnostic"
            ),
            "principal_observed": False,
        }

    def build_preflight(self, name: str) -> Path:
        start = 10_000_000_000
        return write_preflight_failure_artifact(
            workspace=self.root / name,
            context=self.preflight_context(start),
            failure_code="PRE_OIDC_STATIC_GATE_FAILURE",
            execution_phase="PRE_OIDC_STATIC_GATE",
            wall_time_ns=lambda: start + 2_500_000_000,
            monotonic_ns=lambda: 5_000_000_000,
        )

    def test_execution_evidence_pass_complete_reaches_public_facade(self) -> None:
        from research.archive_inventory.r11a_corrective import (
            _artifact_schema_core_r7 as schema_core,
        )

        target = DEFAULT_SELECTION.targets[0]
        state = ExecutionEvidenceState(DEFAULT_SELECTION.targets, DEFAULT_LIMITS)
        state.request_sent(0)
        state.response_metadata(
            0,
            http_status=200,
            etag=target.expected_etag,
            content_length=target.expected_size_bytes,
            requester_charged="requester",
        )
        state.body_progress(0, target.expected_size_bytes)
        state.body_complete(0, target.expected_compressed_sha256)
        conservation = one_record_zero_event_conservation()
        with mock.patch.object(
            schema_core,
            "validate_parse_conservation",
            wraps=schema_core.validate_parse_conservation,
        ) as validator:
            state.pass_complete(
                0,
                pass_number=1,
                decompressed_bytes=10,
                record_count=1,
                event_count=0,
                stream_sha256="5" * 64,
                conservation=conservation,
            )
        self.assertEqual(validator.call_count, 1)
        self.assertEqual(validator.call_args.kwargs["record_count"], 1)
        self.assertEqual(validator.call_args.kwargs["event_count"], 0)
        self.assertEqual(validator.call_args.kwargs["label"], "object_0_pass_1")
        state.pass_complete(
            0,
            pass_number=2,
            decompressed_bytes=10,
            record_count=1,
            event_count=0,
            stream_sha256="5" * 64,
            conservation=conservation,
        )
        self.assertEqual(
            state.object_rows()[0]["terminal_status"],
            "COMPLETE_TWO_LOCAL_PASSES",
        )

    def test_execution_evidence_rejects_mismatched_second_pass(self) -> None:
        target = DEFAULT_SELECTION.targets[0]
        state = ExecutionEvidenceState(DEFAULT_SELECTION.targets, DEFAULT_LIMITS)
        state.request_sent(0)
        state.response_metadata(
            0,
            http_status=200,
            etag=target.expected_etag,
            content_length=target.expected_size_bytes,
            requester_charged="requester",
        )
        state.body_progress(0, target.expected_size_bytes)
        state.body_complete(0, target.expected_compressed_sha256)
        conservation = one_record_zero_event_conservation()
        state.pass_complete(
            0,
            pass_number=1,
            decompressed_bytes=10,
            record_count=1,
            event_count=0,
            stream_sha256="5" * 64,
            conservation=conservation,
        )
        with self.assertRaises(RuntimeBoundaryError):
            state.pass_complete(
                0,
                pass_number=2,
                decompressed_bytes=10,
                record_count=1,
                event_count=0,
                stream_sha256="6" * 64,
                conservation=conservation,
            )

    def test_public_entrypoint_real_full_synthetic_runner_path(self) -> None:
        self.assertEqual(self.rc0, 0)
        validate_artifact(self.complete_artifact, DEFAULT_LIMITS)
        validate_science(self.complete_artifact)
        result = json.loads((self.complete_artifact / RESULT_FILE).read_bytes())
        objects = read_ndjson(self.complete_artifact / OBJECT_LEDGER_FILE)
        reducers = read_ndjson(self.complete_artifact / REDUCER_LEDGER_FILE)
        conservation = json.loads(
            (self.complete_artifact / CONSERVATION_FILE).read_bytes()
        )
        self.assertEqual(len(objects), 72)
        self.assertTrue(
            all(
                row["first_pass"] == row["second_pass"]
                and row["terminal_status"] == "COMPLETE_TWO_LOCAL_PASSES"
                for row in objects
            )
        )
        self.assertEqual(len(reducers), 512)
        self.assertEqual(len(conservation["secondary_reducer_rows"]), 768)
        self.assertTrue(all(conservation["terminal_gates"].values()))
        self.assertGreater(
            len(read_ndjson(self.complete_artifact / UNIT_FILE)),
            0,
        )
        self.assertGreater(
            len(read_ndjson(self.complete_artifact / PAIR_PROOF_FILE)),
            0,
        )
        self.assertEqual(
            result["terminal_class"],
            "R11A_V2_ROOT_CAUSE_TAXONOMY_COMPLETE",
        )
        self.assertEqual(result["return_code"], 0)

    def test_first_internal_validation_failure_recovers_publicly_to_rc21(
        self,
    ) -> None:
        from research.archive_inventory.r11a_corrective import (
            _artifact_contract_core_r7 as contract_core,
            _runner_core_r7 as runner_core,
        )

        workspace = self.root / "first-validation-recovery-workspace"
        real_validate = contract_core.validate_artifact
        real_meter_type = runner_core.WorkspaceMeter
        validation_terminals: list[str] = []
        captured_meters: list[R7WorkspaceMeter] = []

        def fail_first_validation(path: Path, limits: object) -> None:
            terminal = json.loads((path / RESULT_FILE).read_bytes())[
                "terminal_class"
            ]
            validation_terminals.append(terminal)
            if len(validation_terminals) == 1:
                raise ArtifactBoundaryError(
                    "injected first internal artifact validation failure"
                )
            real_validate(path, limits)

        def capture_meter(*args: object, **kwargs: object) -> R7WorkspaceMeter:
            meter = real_meter_type(*args, **kwargs)
            captured_meters.append(meter)
            return meter

        with mock.patch.object(
            contract_core,
            "validate_artifact",
            side_effect=fail_first_validation,
        ), mock.patch.object(
            runner_core,
            "WorkspaceMeter",
            side_effect=capture_meter,
        ):
            return_code, artifact = execute_public_synthetic_route(
                workspace,
                incomplete=False,
            )

        self.assertEqual(
            validation_terminals,
            [
                "R11A_V2_ROOT_CAUSE_TAXONOMY_COMPLETE",
                "R11A_V2_FAIL_CLOSED_EARLY_STOP",
            ],
        )
        self.assert_valid_rc21_recovery(
            workspace=workspace,
            artifact=artifact,
            return_code=return_code,
        )
        stops = json.loads((artifact / STOP_LEDGER_FILE).read_bytes())["entries"]
        self.assertEqual(len(stops), 1)
        self.assertEqual(
            stops[0]["stop_code"],
            "R11A_FAIL_CLOSED_ARTIFACTBOUNDARYERROR",
        )
        self.assertEqual(stops[0]["phase"], "ARTIFACT_PACKAGING")
        self.assertIsNone(stops[0]["object_ordinal_zero_based"])
        context = json.loads((artifact / CONTEXT_FILE).read_bytes())
        self.assertEqual(context["execution_phase"], "ARTIFACT_PACKAGING")
        self.assertEqual(context["s3_requests_executed"], 72)
        self.assertTrue(context["principal_observed"])
        self.assertFalse(context["rerun_authorized"])
        self.assertFalse(context["raw_aws_credentials_retained"])
        self.assertFalse(context["raw_oidc_token_retained"])
        self.assertFalse(context["raw_sts_response_retained"])
        resource = json.loads((artifact / RESOURCE_LEDGER_FILE).read_bytes())
        recovery = resource["measurements"][-1]
        self.assertEqual(recovery["phase"], "FAIL_CLOSED_BEFORE_MINIMAL_ARTIFACT")
        self.assertTrue(recovery["cleanup_completed"])
        self.assertEqual(recovery["tracked_workspace_bytes"], 0)
        self.assertEqual(recovery["reserved_workspace_bytes"], 0)
        self.assertEqual(resource["tracked_workspace_bytes_before_packaging"], 0)
        self.assertEqual(resource["reserved_workspace_bytes_before_packaging"], 0)
        self.assertEqual(len(captured_meters), 1)
        meter = captured_meters[0]
        actual = directory_size(workspace)
        self.assertEqual(meter.known_bytes, actual)
        self.assertEqual(meter.reserved_bytes, 0)
        self.assertEqual(meter.verify_actual_usage(), actual)
        self.assertEqual(actual, directory_size(artifact))
        meter.checked_rmtree(artifact)
        self.assertEqual(meter.verify_actual_usage(), 0)
        self.assertEqual(list(workspace.iterdir()), [])

    def test_one_shot_validation_rollback_cleanup_failure_is_fatal_publicly(
        self,
    ) -> None:
        from research.archive_inventory.r11a_corrective import (
            _artifact_contract_core_r7 as contract_core,
            _runner_core_r7 as runner_core,
            storage_r7 as storage_core,
        )

        workspace = self.root / "fatal-validation-rollback-workspace"
        real_validate = contract_core.validate_artifact
        real_rmtree = storage_core.shutil.rmtree
        real_meter_type = runner_core.WorkspaceMeter
        real_atomic_rollback = storage_core.AtomicArtifactDirectory.rollback
        validation_calls = 0
        staging_cleanup_attempts = 0
        atomic_rollback_calls = 0
        captured_meters: list[R7WorkspaceMeter] = []

        def reject_first(path: Path, limits: object) -> None:
            nonlocal validation_calls
            validation_calls += 1
            if validation_calls == 1:
                raise ArtifactBoundaryError(
                    "injected first artifact validation rejection"
                )
            real_validate(path, limits)

        def fail_first_staging_cleanup(
            path: object,
            *args: object,
            **kwargs: object,
        ) -> object:
            nonlocal staging_cleanup_attempts
            if Path(path).name == ".r11a-v2-artifact.staging":
                staging_cleanup_attempts += 1
                if staging_cleanup_attempts == 1:
                    raise OSError(
                        "injected one-shot rollback cleanup failure"
                    )
            return real_rmtree(path, *args, **kwargs)

        def capture_meter(*args: object, **kwargs: object) -> R7WorkspaceMeter:
            meter = real_meter_type(*args, **kwargs)
            captured_meters.append(meter)
            return meter

        def track_atomic_rollback(owner: object) -> None:
            nonlocal atomic_rollback_calls
            atomic_rollback_calls += 1
            real_atomic_rollback(owner)  # type: ignore[arg-type]

        with mock.patch.object(
            contract_core,
            "validate_artifact",
            side_effect=reject_first,
        ), mock.patch.object(
            runner_core,
            "WorkspaceMeter",
            side_effect=capture_meter,
        ), mock.patch(
            "research.archive_inventory.r11a_corrective.storage_r7.shutil.rmtree",
            side_effect=fail_first_staging_cleanup,
        ), mock.patch.object(
            storage_core.AtomicArtifactDirectory,
            "rollback",
            autospec=True,
            side_effect=track_atomic_rollback,
        ):
            with self.assertRaises(runner_core.RecoveryBoundaryError) as raised:
                execute_public_synthetic_route(workspace, incomplete=False)

        self.assertEqual(validation_calls, 1)
        self.assertEqual(staging_cleanup_attempts, 2)
        self.assertEqual(atomic_rollback_calls, 1)
        self.assertFalse((workspace / "r11a-v2-artifact").exists())
        self.assertFalse((workspace / ".r11a-v2-artifact.staging").exists())
        self.assertEqual(list(workspace.iterdir()), [])
        self.assertEqual(len(captured_meters), 1)
        meter = captured_meters[0]
        self.assertEqual(meter.known_bytes, 0)
        self.assertEqual(meter.reserved_bytes, 0)
        self.assertEqual(meter.verify_actual_usage(), 0)
        self.assertTrue(
            any(
                str(value) == "injected one-shot rollback cleanup failure"
                for value in exception_graph(raised.exception)
            )
        )

    def test_first_pass_parse_failure_recovers_publicly_to_valid_rc21(
        self,
    ) -> None:
        from research.archive_inventory.r11a_corrective import _runner_core_r7 as runner_core

        workspace = self.root / "first-pass-parse-recovery-workspace"
        real_meter_type = runner_core.WorkspaceMeter
        captured_meters: list[R7WorkspaceMeter] = []

        def capture_meter(*args: object, **kwargs: object) -> R7WorkspaceMeter:
            meter = real_meter_type(*args, **kwargs)
            captured_meters.append(meter)
            return meter

        with mock.patch.object(
            runner_core,
            "WorkspaceMeter",
            side_effect=capture_meter,
        ), mock.patch.object(
            runner_core,
            "parse_object_pass",
            side_effect=RuntimeError("injected first-pass parse failure"),
        ):
            return_code, artifact = execute_public_synthetic_route(
                workspace,
                incomplete=False,
            )

        self.assert_valid_rc21_recovery(
            workspace=workspace,
            artifact=artifact,
            return_code=return_code,
        )
        context = json.loads((artifact / CONTEXT_FILE).read_bytes())
        self.assertEqual(context["execution_phase"], "FIRST_LOCAL_PASS")
        self.assertEqual(len(captured_meters), 1)
        meter = captured_meters[0]
        actual = directory_size(artifact)
        self.assertEqual(meter.reserved_bytes, 0)
        self.assertEqual(meter.known_bytes, actual)
        self.assertEqual(meter.verify_actual_usage(), actual)

    def test_second_pass_parse_failure_recovers_publicly_to_valid_rc21(
        self,
    ) -> None:
        from research.archive_inventory.r11a_corrective import _runner_core_r7 as runner_core

        workspace = self.root / "second-pass-parse-recovery-workspace"
        real_meter_type = runner_core.WorkspaceMeter
        real_parse = runner_core.parse_object_pass
        captured_meters: list[R7WorkspaceMeter] = []
        parse_calls = 0

        def capture_meter(*args: object, **kwargs: object) -> R7WorkspaceMeter:
            meter = real_meter_type(*args, **kwargs)
            captured_meters.append(meter)
            return meter

        def fail_first_second_pass(*args: object, **kwargs: object) -> object:
            nonlocal parse_calls
            parse_calls += 1
            if parse_calls == 73:
                raise RuntimeError("injected first second-pass parse failure")
            return real_parse(*args, **kwargs)

        with mock.patch.object(
            runner_core,
            "WorkspaceMeter",
            side_effect=capture_meter,
        ), mock.patch.object(
            runner_core,
            "parse_object_pass",
            side_effect=fail_first_second_pass,
        ):
            return_code, artifact = execute_public_synthetic_route(
                workspace,
                incomplete=False,
            )

        self.assertEqual(parse_calls, 73)
        self.assert_valid_rc21_recovery(
            workspace=workspace,
            artifact=artifact,
            return_code=return_code,
        )
        context = json.loads((artifact / CONTEXT_FILE).read_bytes())
        self.assertEqual(context["execution_phase"], "SECOND_LOCAL_PASS")
        self.assertEqual(len(captured_meters), 1)
        meter = captured_meters[0]
        actual = directory_size(artifact)
        self.assertEqual(meter.reserved_bytes, 0)
        self.assertEqual(meter.known_bytes, actual)
        self.assertEqual(meter.verify_actual_usage(), actual)

    def test_partial_first_pass_index_construction_recovers_to_valid_rc21(
        self,
    ) -> None:
        from research.archive_inventory.r11a_corrective import (
            _runner_core_r7 as runner_core,
            index as index_core,
        )

        workspace = self.root / "partial-index-construction-workspace"
        real_writer = index_core.SharedPartitionWriter
        real_meter_type = runner_core.WorkspaceMeter
        writer_calls = 0
        captured_meters: list[R7WorkspaceMeter] = []

        def fail_second_writer(*args: object, **kwargs: object) -> object:
            nonlocal writer_calls
            writer_calls += 1
            if writer_calls == 2:
                raise RuntimeError("injected second index writer construction failure")
            return real_writer(*args, **kwargs)

        def capture_meter(*args: object, **kwargs: object) -> R7WorkspaceMeter:
            meter = real_meter_type(*args, **kwargs)
            captured_meters.append(meter)
            return meter

        with mock.patch.object(
            runner_core,
            "WorkspaceMeter",
            side_effect=capture_meter,
        ), mock.patch.object(
            index_core,
            "SharedPartitionWriter",
            side_effect=fail_second_writer,
        ):
            return_code, artifact = execute_public_synthetic_route(
                workspace,
                incomplete=False,
            )

        self.assertEqual(writer_calls, 2)
        self.assert_valid_rc21_recovery(
            workspace=workspace,
            artifact=artifact,
            return_code=return_code,
        )
        self.assertEqual(len(captured_meters), 1)
        meter = captured_meters[0]
        actual = directory_size(artifact)
        self.assertEqual(meter.reserved_bytes, 0)
        self.assertEqual(meter.known_bytes, actual)
        self.assertEqual(meter.verify_actual_usage(), actual)

    def test_partial_materializer_construction_recovers_to_valid_rc21(
        self,
    ) -> None:
        from research.archive_inventory.r11a_corrective import (
            _runner_core_r7 as runner_core,
            materialize as materialize_core,
        )

        workspace = self.root / "partial-materializer-construction-workspace"
        real_writer = materialize_core.SharedPartitionWriter
        real_meter_type = runner_core.WorkspaceMeter
        writer_calls = 0
        captured_meters: list[R7WorkspaceMeter] = []

        def fail_third_writer(*args: object, **kwargs: object) -> object:
            nonlocal writer_calls
            writer_calls += 1
            if writer_calls == 3:
                raise RuntimeError("injected third materializer writer construction failure")
            return real_writer(*args, **kwargs)

        def capture_meter(*args: object, **kwargs: object) -> R7WorkspaceMeter:
            meter = real_meter_type(*args, **kwargs)
            captured_meters.append(meter)
            return meter

        with mock.patch.object(
            runner_core,
            "WorkspaceMeter",
            side_effect=capture_meter,
        ), mock.patch.object(
            materialize_core,
            "SharedPartitionWriter",
            side_effect=fail_third_writer,
        ):
            return_code, artifact = execute_public_synthetic_route(
                workspace,
                incomplete=False,
            )

        self.assertEqual(writer_calls, 3)
        self.assert_valid_rc21_recovery(
            workspace=workspace,
            artifact=artifact,
            return_code=return_code,
        )
        self.assertEqual(len(captured_meters), 1)
        meter = captured_meters[0]
        actual = directory_size(artifact)
        self.assertEqual(meter.reserved_bytes, 0)
        self.assertEqual(meter.known_bytes, actual)
        self.assertEqual(meter.verify_actual_usage(), actual)

    def test_partial_candidate_database_construction_recovers_to_valid_rc21(
        self,
    ) -> None:
        from research.archive_inventory.r11a_corrective import (
            _runner_core_r7 as runner_core,
            storage_r7 as storage_core,
        )

        workspace = self.root / "partial-candidate-database-workspace"
        real_meter_type = runner_core.WorkspaceMeter
        captured_meters: list[R7WorkspaceMeter] = []

        def capture_meter(*args: object, **kwargs: object) -> R7WorkspaceMeter:
            meter = real_meter_type(*args, **kwargs)
            captured_meters.append(meter)
            return meter

        with mock.patch.object(
            runner_core,
            "WorkspaceMeter",
            side_effect=capture_meter,
        ), mock.patch.object(
            storage_core.sqlite3,
            "connect",
            side_effect=RuntimeError("injected candidate SQLite construction failure"),
        ):
            return_code, artifact = execute_public_synthetic_route(
                workspace,
                incomplete=False,
            )

        self.assert_valid_rc21_recovery(
            workspace=workspace,
            artifact=artifact,
            return_code=return_code,
        )
        self.assertEqual(len(captured_meters), 1)
        meter = captured_meters[0]
        actual = directory_size(artifact)
        self.assertEqual(meter.reserved_bytes, 0)
        self.assertEqual(meter.known_bytes, actual)
        self.assertEqual(meter.verify_actual_usage(), actual)

    def test_owner_cleanup_error_remains_fatal_after_physical_cleanup(
        self,
    ) -> None:
        from research.archive_inventory.r11a_corrective import (
            _runner_core_r7 as runner_core,
            index as index_core,
        )

        workspace = self.root / "fatal-owner-cleanup-workspace"
        real_abort = index_core.FirstPassIndexes.abort
        abort_calls = 0

        def abort_then_fail(owner: object) -> None:
            nonlocal abort_calls
            abort_calls += 1
            real_abort(owner)  # type: ignore[arg-type]
            raise index_core.IndexCleanupError(
                "injected owner cleanup failure after physical cleanup"
            )

        with mock.patch.object(
            runner_core,
            "parse_object_pass",
            side_effect=RuntimeError("injected first-pass parse failure"),
        ), mock.patch.object(
            index_core.FirstPassIndexes,
            "abort",
            autospec=True,
            side_effect=abort_then_fail,
        ):
            with self.assertRaises(runner_core.RecoveryBoundaryError) as raised:
                execute_public_synthetic_route(workspace, incomplete=False)

        self.assertEqual(abort_calls, 1)
        self.assertFalse((workspace / "r11a-v2-artifact").exists())
        self.assertFalse((workspace / ".r11a-v2-artifact.staging").exists())
        self.assertEqual(list(workspace.iterdir()), [])
        self.assertIsInstance(
            raised.exception.__cause__,
            index_core.IndexCleanupError,
        )
        self.assertEqual(
            str(raised.exception.__cause__),
            "injected owner cleanup failure after physical cleanup",
        )

    def test_processed_object_cleanup_failure_is_fatal_publicly(self) -> None:
        from research.archive_inventory.r11a_corrective import (
            _runner_core_r7 as runner_core,
        )

        workspace = self.root / "fatal-processed-object-cleanup-workspace"
        real_unlink = Path.unlink
        injected = 0

        def fail_first_processed_object_unlink(
            path: Path,
            *args: object,
            **kwargs: object,
        ) -> None:
            nonlocal injected
            if path.name == "object-000.lz4" and injected == 0:
                injected += 1
                raise OSError("injected processed object cleanup failure")
            real_unlink(path, *args, **kwargs)

        with mock.patch.object(
            Path,
            "unlink",
            autospec=True,
            side_effect=fail_first_processed_object_unlink,
        ):
            with self.assertRaises(runner_core.RecoveryBoundaryError) as raised:
                execute_public_synthetic_route(workspace, incomplete=False)

        self.assertEqual(injected, 1)
        self.assertFalse((workspace / "r11a-v2-artifact").exists())
        self.assertFalse((workspace / ".r11a-v2-artifact.staging").exists())
        self.assertEqual(list(workspace.iterdir()), [])
        self.assertTrue(
            any(
                str(value) == "injected processed object cleanup failure"
                for value in exception_graph(raised.exception)
            )
        )

    def test_framed_reader_close_failure_is_fatal_publicly(self) -> None:
        from research.archive_inventory.r11a_corrective import (
            _runner_core_r7 as runner_core,
        )

        workspace = self.root / "fatal-framed-reader-cleanup-workspace"
        real_open = Path.open
        injected = 0

        class CloseFailingReader:
            def __init__(self, handle: object) -> None:
                self.handle = handle

            def read(self, size: int = -1) -> bytes:
                return self.handle.read(size)  # type: ignore[no-any-return,union-attr]

            def close(self) -> None:
                nonlocal injected
                self.handle.close()  # type: ignore[union-attr]
                if injected == 0:
                    injected += 1
                    raise OSError("injected framed reader cleanup failure")

        def wrap_sorted_partition_reader(
            path: Path,
            mode: str = "r",
            *args: object,
            **kwargs: object,
        ) -> object:
            handle = real_open(path, mode, *args, **kwargs)
            if path.name == "sorted-block_number-000.frames" and mode == "rb":
                return CloseFailingReader(handle)
            return handle

        with mock.patch.object(
            Path,
            "open",
            autospec=True,
            side_effect=wrap_sorted_partition_reader,
        ):
            with self.assertRaises(runner_core.RecoveryBoundaryError) as raised:
                execute_public_synthetic_route(workspace, incomplete=False)

        self.assertEqual(injected, 1)
        self.assertFalse((workspace / "r11a-v2-artifact").exists())
        self.assertFalse((workspace / ".r11a-v2-artifact.staging").exists())
        self.assertEqual(list(workspace.iterdir()), [])
        self.assertTrue(
            any(
                str(value) == "injected framed reader cleanup failure"
                for value in exception_graph(raised.exception)
            )
        )

    def test_entrypoint_setup_reader_cleanup_failures_are_fatal(self) -> None:
        from research.archive_inventory.r11a_corrective import entrypoint
        from research.archive_inventory.r11a_corrective.pricing import SNAPSHOT_PATH

        context_path = self.root / "complete-workspace-context.json"
        principal_path = self.root / "complete-workspace-principal.json"
        real_open = Path.open

        class CloseFailingReader:
            def __init__(self, handle: object, message: str) -> None:
                self.handle = handle
                self.message = message
                self.injected = False

            def read(self, size: int = -1) -> bytes:
                return self.handle.read(size)  # type: ignore[no-any-return,union-attr]

            def close(self) -> None:
                self.handle.close()  # type: ignore[union-attr]
                if not self.injected:
                    self.injected = True
                    raise OSError(self.message)

        for label, target in (
            ("principal", principal_path),
            ("pricing", SNAPSHOT_PATH),
        ):
            with self.subTest(label=label):
                workspace = self.root / f"fatal-{label}-reader-cleanup-workspace"
                message = f"injected {label} reader cleanup failure"
                injected = 0

                def wrap_setup_reader(
                    path: Path,
                    mode: str = "r",
                    *args: object,
                    **kwargs: object,
                ) -> object:
                    nonlocal injected
                    handle = real_open(path, mode, *args, **kwargs)
                    if path == target and mode == "rb" and injected == 0:
                        injected += 1
                        return CloseFailingReader(handle, message)
                    return handle

                with mock.patch.object(
                    Path,
                    "open",
                    autospec=True,
                    side_effect=wrap_setup_reader,
                ):
                    with self.assertRaises(StorageCleanupError) as raised:
                        entrypoint.execute(workspace, context_path, principal_path)

                self.assertEqual(injected, 1)
                self.assertFalse(workspace.exists())
                self.assertTrue(
                    any(
                        str(value) == message
                        for value in exception_graph(raised.exception)
                    )
                )

    def test_file_handle_cleanup_failures_are_fatal_across_runtime_layers(
        self,
    ) -> None:
        from research.archive_inventory.r11a_corrective import (
            _runner_core_r7 as runner_core,
        )

        real_open = Path.open
        scenarios = (
            (
                "compressed-reader",
                lambda path, mode: path.name == "object-000.lz4" and mode == "rb",
            ),
            (
                "transport-writer",
                lambda path, mode: path.name == "object-000.lz4" and mode == "xb",
            ),
            (
                "partition-writer",
                lambda path, mode: (
                    "first-pass-block-index" in path.parts and mode == "xb"
                ),
            ),
            (
                "scientific-writer",
                lambda path, mode: (
                    path.name == UNIT_FILE and mode == "xb"
                ),
            ),
            (
                "metadata-writer",
                lambda path, mode: (
                    path.name == CONTEXT_FILE and mode == "xb"
                ),
            ),
            (
                "artifact-validator-reader",
                lambda path, mode: (
                    path.name == CONTEXT_FILE and mode == "rb"
                ),
            ),
        )

        class CloseFailingHandle:
            def __init__(self, handle: object, inject: object) -> None:
                self.handle = handle
                self.inject = inject
                self.closed_once = False

            def __getattr__(self, name: str) -> object:
                return getattr(self.handle, name)

            def close(self) -> None:
                self.handle.close()  # type: ignore[union-attr]
                if not self.closed_once:
                    self.closed_once = True
                    self.inject()  # type: ignore[operator]

        for label, matches in scenarios:
            with self.subTest(label=label):
                workspace = self.root / f"fatal-{label}-cleanup-workspace"
                wrapped = 0
                faults = 0
                message = f"injected {label} cleanup failure"

                def inject() -> None:
                    nonlocal faults
                    faults += 1
                    raise OSError(message)

                def wrap_handle(
                    path: Path,
                    mode: str = "r",
                    *args: object,
                    **kwargs: object,
                ) -> object:
                    nonlocal wrapped
                    handle = real_open(path, mode, *args, **kwargs)
                    if wrapped == 0 and matches(path, mode):
                        wrapped += 1
                        return CloseFailingHandle(handle, inject)
                    return handle

                with mock.patch.object(
                    Path,
                    "open",
                    autospec=True,
                    side_effect=wrap_handle,
                ):
                    with self.assertRaises(
                        runner_core.RecoveryBoundaryError
                    ) as raised:
                        execute_public_synthetic_route(workspace, incomplete=False)

                self.assertEqual(wrapped, 1)
                self.assertEqual(faults, 1)
                self.assertFalse((workspace / "r11a-v2-artifact").exists())
                self.assertFalse(
                    (workspace / ".r11a-v2-artifact.staging").exists()
                )
                self.assertEqual(list(workspace.iterdir()), [])
                self.assertTrue(
                    any(
                        str(value) == message
                        for value in exception_graph(raised.exception)
                    )
                )

    def test_fresh_rc21_validation_cleanup_failure_is_fatal_without_retry(
        self,
    ) -> None:
        from research.archive_inventory.r11a_corrective import (
            _artifact_contract_core_r7 as contract_core,
            _runner_core_r7 as runner_core,
            storage_r7 as storage_core,
        )

        workspace = self.root / "fatal-fresh-rc21-workspace"
        real_rmtree = storage_core.shutil.rmtree
        validation_terminals: list[str] = []
        cleanup_injections = 0
        reject_fresh = False

        def reject_initial_and_fresh(path: Path, limits: object) -> None:
            nonlocal reject_fresh
            terminal = json.loads((path / RESULT_FILE).read_bytes())[
                "terminal_class"
            ]
            validation_terminals.append(terminal)
            if len(validation_terminals) == 2:
                reject_fresh = True
            raise ArtifactBoundaryError(
                f"injected validation rejection {len(validation_terminals)}"
            )

        def fail_fresh_cleanup(
            path: object,
            *args: object,
            **kwargs: object,
        ) -> object:
            nonlocal cleanup_injections
            if (
                reject_fresh
                and Path(path).name == ".r11a-v2-artifact.staging"
                and cleanup_injections == 0
            ):
                cleanup_injections += 1
                raise OSError("injected fresh RC21 cleanup failure")
            return real_rmtree(path, *args, **kwargs)

        with mock.patch.object(
            contract_core,
            "validate_artifact",
            side_effect=reject_initial_and_fresh,
        ), mock.patch(
            "research.archive_inventory.r11a_corrective.storage_r7.shutil.rmtree",
            side_effect=fail_fresh_cleanup,
        ):
            with self.assertRaises(runner_core.RecoveryBoundaryError) as raised:
                execute_public_synthetic_route(workspace, incomplete=False)

        self.assertEqual(
            validation_terminals,
            [
                "R11A_V2_ROOT_CAUSE_TAXONOMY_COMPLETE",
                "R11A_V2_FAIL_CLOSED_EARLY_STOP",
            ],
        )
        self.assertEqual(cleanup_injections, 1)
        self.assertFalse((workspace / "r11a-v2-artifact").exists())
        self.assertFalse((workspace / ".r11a-v2-artifact.staging").exists())
        self.assertEqual(list(workspace.iterdir()), [])
        graph = exception_graph(raised.exception)
        self.assertTrue(
            any(str(value) == "injected validation rejection 2" for value in graph)
        )
        self.assertTrue(
            any(str(value) == "injected fresh RC21 cleanup failure" for value in graph)
        )

    def test_reserved_writer_open_failure_recovers_to_valid_rc21(self) -> None:
        from research.archive_inventory.r11a_corrective import (
            _runner_core_r7 as runner_core,
        )

        workspace = self.root / "reserved-writer-construction-workspace"
        real_open = Path.open
        real_meter_type = runner_core.WorkspaceMeter
        captured_meters: list[R7WorkspaceMeter] = []
        injected = 0

        def fail_first_object_open(
            path: Path,
            mode: str = "r",
            *args: object,
            **kwargs: object,
        ) -> object:
            nonlocal injected
            if path.name == "object-000.lz4" and mode == "xb" and injected == 0:
                injected += 1
                raise OSError("injected reserved writer open failure")
            return real_open(path, mode, *args, **kwargs)

        def capture_meter(*args: object, **kwargs: object) -> R7WorkspaceMeter:
            meter = real_meter_type(*args, **kwargs)
            captured_meters.append(meter)
            return meter

        with mock.patch.object(
            Path,
            "open",
            autospec=True,
            side_effect=fail_first_object_open,
        ), mock.patch.object(
            runner_core,
            "WorkspaceMeter",
            side_effect=capture_meter,
        ):
            return_code, artifact = execute_public_synthetic_route(
                workspace,
                incomplete=False,
            )

        self.assertEqual(injected, 1)
        self.assert_valid_rc21_recovery(
            workspace=workspace,
            artifact=artifact,
            return_code=return_code,
            conclusion="ROOT_CAUSE_NOT_PROVEN_NETWORK_FAIL_CLOSED_EMPTY_ARTIFACT",
        )
        meter = captured_meters[0]
        actual = directory_size(artifact)
        self.assertEqual(meter.reserved_bytes, 0)
        self.assertEqual(meter.known_bytes, actual)

    def test_partial_scientific_emitter_construction_recovers_to_valid_rc21(
        self,
    ) -> None:
        from research.archive_inventory.r11a_corrective import (
            _runner_core_r7 as runner_core,
        )

        workspace = self.root / "partial-science-construction-workspace"
        real_open = Path.open
        real_meter_type = runner_core.WorkspaceMeter
        captured_meters: list[R7WorkspaceMeter] = []
        injected = 0
        target_name = SCIENCE_CONTAINERS[2]

        def fail_third_science_open(
            path: Path,
            mode: str = "r",
            *args: object,
            **kwargs: object,
        ) -> object:
            nonlocal injected
            if path.name == target_name and mode == "xb" and injected == 0:
                injected += 1
                raise OSError("injected science constructor open failure")
            return real_open(path, mode, *args, **kwargs)

        def capture_meter(*args: object, **kwargs: object) -> R7WorkspaceMeter:
            meter = real_meter_type(*args, **kwargs)
            captured_meters.append(meter)
            return meter

        with mock.patch.object(
            Path,
            "open",
            autospec=True,
            side_effect=fail_third_science_open,
        ), mock.patch.object(
            runner_core,
            "WorkspaceMeter",
            side_effect=capture_meter,
        ):
            return_code, artifact = execute_public_synthetic_route(
                workspace,
                incomplete=False,
            )

        self.assertEqual(injected, 1)
        self.assert_valid_rc21_recovery(
            workspace=workspace,
            artifact=artifact,
            return_code=return_code,
            conclusion="ROOT_CAUSE_NOT_PROVEN_NETWORK_FAIL_CLOSED_EMPTY_ARTIFACT",
        )
        meter = captured_meters[0]
        actual = directory_size(artifact)
        self.assertEqual(meter.reserved_bytes, 0)
        self.assertEqual(meter.known_bytes, actual)

    def test_metadata_constructor_failure_recovers_to_valid_rc21(self) -> None:
        from research.archive_inventory.r11a_corrective import (
            _runner_core_r7 as runner_core,
            storage_r7 as storage_core,
        )

        workspace = self.root / "metadata-construction-workspace"
        real_checkpoint = storage_core.WorkspaceMeter.checkpoint_value
        real_meter_type = runner_core.WorkspaceMeter
        captured_meters: list[R7WorkspaceMeter] = []
        injected = 0

        def fail_after_metadata_checkpoint(
            meter: R7WorkspaceMeter,
            reservation: object,
            actual_bytes: int,
            *,
            packaging: bool = False,
            phase: str,
        ) -> int:
            nonlocal injected
            result = real_checkpoint(
                meter,
                reservation,  # type: ignore[arg-type]
                actual_bytes,
                packaging=packaging,
                phase=phase,
            )
            if phase == "create metadata reservation" and injected == 0:
                injected += 1
                raise RuntimeError("injected metadata constructor checkpoint failure")
            return result

        def capture_meter(*args: object, **kwargs: object) -> R7WorkspaceMeter:
            meter = real_meter_type(*args, **kwargs)
            captured_meters.append(meter)
            return meter

        with mock.patch.object(
            storage_core.WorkspaceMeter,
            "checkpoint_value",
            autospec=True,
            side_effect=fail_after_metadata_checkpoint,
        ), mock.patch.object(
            runner_core,
            "WorkspaceMeter",
            side_effect=capture_meter,
        ):
            return_code, artifact = execute_public_synthetic_route(
                workspace,
                incomplete=False,
            )

        self.assertEqual(injected, 1)
        self.assert_valid_rc21_recovery(
            workspace=workspace,
            artifact=artifact,
            return_code=return_code,
        )
        meter = captured_meters[0]
        actual = directory_size(artifact)
        self.assertEqual(meter.reserved_bytes, 0)
        self.assertEqual(meter.known_bytes, actual)

    def test_taxonomy_cleanup_error_remains_fatal_publicly(self) -> None:
        from research.archive_inventory.r11a_corrective import (
            _runner_core_r7 as runner_core,
            join_r7 as join_core,
        )

        workspace = self.root / "fatal-taxonomy-cleanup-workspace"
        real_close = join_core.DiskJoinLedger.close_delete
        cleanup_calls = 0

        def close_then_fail(owner: object) -> None:
            nonlocal cleanup_calls
            cleanup_calls += 1
            real_close(owner)  # type: ignore[arg-type]
            raise StorageCleanupError("injected taxonomy cleanup failure")

        with mock.patch.object(
            join_core.DiskJoinLedger,
            "close_delete",
            autospec=True,
            side_effect=close_then_fail,
        ):
            with self.assertRaises(runner_core.RecoveryBoundaryError) as raised:
                execute_public_synthetic_route(workspace, incomplete=False)

        self.assertEqual(cleanup_calls, 1)
        self.assertFalse((workspace / "r11a-v2-artifact").exists())
        self.assertFalse((workspace / ".r11a-v2-artifact.staging").exists())
        self.assertEqual(list(workspace.iterdir()), [])
        self.assertTrue(
            any(
                str(value) == "injected taxonomy cleanup failure"
                for value in exception_graph(raised.exception)
            )
        )

    def test_partial_taxonomy_construction_recovers_to_valid_rc21(self) -> None:
        from research.archive_inventory.r11a_corrective import (
            _runner_core_r7 as runner_core,
            _taxonomy_contract_core_r7 as taxonomy_core,
        )

        workspace = self.root / "partial-taxonomy-construction-workspace"
        real_meter_type = runner_core.WorkspaceMeter
        captured_meters: list[R7WorkspaceMeter] = []

        def capture_meter(*args: object, **kwargs: object) -> R7WorkspaceMeter:
            meter = real_meter_type(*args, **kwargs)
            captured_meters.append(meter)
            return meter

        with mock.patch.object(
            taxonomy_core,
            "EventScratch",
            side_effect=RuntimeError("injected event scratch construction failure"),
        ), mock.patch.object(
            runner_core,
            "WorkspaceMeter",
            side_effect=capture_meter,
        ):
            return_code, artifact = execute_public_synthetic_route(
                workspace,
                incomplete=False,
            )

        self.assert_valid_rc21_recovery(
            workspace=workspace,
            artifact=artifact,
            return_code=return_code,
        )
        meter = captured_meters[0]
        actual = directory_size(artifact)
        self.assertEqual(meter.reserved_bytes, 0)
        self.assertEqual(meter.known_bytes, actual)

    def test_metadata_finalization_failure_recovers_to_valid_rc21(self) -> None:
        from research.archive_inventory.r11a_corrective import (
            _artifact_contract_core_r7 as contract_core,
        )

        workspace = self.root / "metadata-finalization-recovery-workspace"
        real_close = contract_core.SharedMetadataWriter.close
        closes = 0

        def close_then_fail(writer: SharedMetadataWriter) -> None:
            nonlocal closes
            real_close(writer)
            closes += 1
            if closes == 1:
                raise ArtifactBoundaryError(
                    "injected completed metadata finalization failure"
                )

        with mock.patch.object(
            contract_core.SharedMetadataWriter,
            "close",
            autospec=True,
            side_effect=close_then_fail,
        ):
            return_code, artifact = execute_public_synthetic_route(
                workspace,
                incomplete=False,
            )
        self.assertEqual(closes, 2)
        self.assert_valid_rc21_recovery(
            workspace=workspace,
            artifact=artifact,
            return_code=return_code,
        )

    def test_post_rename_failure_recovers_to_valid_rc21(self) -> None:
        workspace = self.root / "post-rename-recovery-workspace"
        real_check = RuntimeGuard.check_packaging_phase
        injections = 0

        def fail_first_post_rename(guard: RuntimeGuard, phase: str) -> None:
            nonlocal injections
            if phase == "artifact rename after" and injections == 0:
                injections += 1
                raise RuntimeError("injected first post-rename failure")
            real_check(guard, phase)

        with mock.patch.object(
            RuntimeGuard,
            "check_packaging_phase",
            autospec=True,
            side_effect=fail_first_post_rename,
        ):
            return_code, artifact = execute_public_synthetic_route(
                workspace,
                incomplete=False,
            )
        self.assertEqual(injections, 1)
        self.assert_valid_rc21_recovery(
            workspace=workspace,
            artifact=artifact,
            return_code=return_code,
        )

    def test_real_fully_materialized_incomplete_route_is_valid_rc20(self) -> None:
        self.assertEqual(self.rc20, 20)
        validate_artifact(self.incomplete_artifact, DEFAULT_LIMITS)
        validate_science(self.incomplete_artifact)
        result = json.loads((self.incomplete_artifact / RESULT_FILE).read_bytes())
        stops = json.loads(
            (self.incomplete_artifact / STOP_LEDGER_FILE).read_bytes()
        )["entries"]
        conservation = json.loads(
            (self.incomplete_artifact / CONSERVATION_FILE).read_bytes()
        )
        scientific_gate = (
            "every_unit_universe_has_zero_unclassifiable_groups_and_occurrences"
        )
        self.assertEqual(result["terminal_class"], "R11A_V2_DIAGNOSTIC_INCOMPLETE")
        self.assertEqual(result["return_code"], 20)
        self.assertEqual(len(stops), 1)
        self.assertEqual(stops[0]["stop_code"], "FULL_SCOPE_TAXONOMY_INCOMPLETE")
        self.assertFalse(conservation["terminal_gates"][scientific_gate])
        self.assertTrue(
            all(
                value
                for name, value in conservation["terminal_gates"].items()
                if name != scientific_gate
            )
        )

    def test_rc20_zero_object_scope_is_rejected_after_rehash(self) -> None:
        artifact = self.fresh_incomplete("rc20-zero-scope")
        (artifact / OBJECT_LEDGER_FILE).write_bytes(b"")
        refresh_artifact_bindings(artifact)
        with self.assertRaises((ArtifactBoundaryError, ValueError)):
            validate_artifact(artifact, DEFAULT_LIMITS)

    def test_rc20_partial_object_scope_is_rejected_after_rehash(self) -> None:
        artifact = self.fresh_incomplete("rc20-partial-scope")
        rows = read_ndjson(artifact / OBJECT_LEDGER_FILE)
        write_ndjson(artifact / OBJECT_LEDGER_FILE, rows[:-1])
        refresh_artifact_bindings(artifact)
        with self.assertRaises(ArtifactBoundaryError):
            validate_artifact(artifact, DEFAULT_LIMITS)

    def test_rc20_one_pass_scope_is_rejected_after_rehash(self) -> None:
        artifact = self.fresh_incomplete("rc20-one-pass")
        rows = read_ndjson(artifact / OBJECT_LEDGER_FILE)
        rows[0]["second_pass"] = None
        rows[0]["terminal_status"] = "PENDING"
        write_ndjson(artifact / OBJECT_LEDGER_FILE, rows)
        refresh_artifact_bindings(artifact)
        with self.assertRaises(ArtifactBoundaryError):
            validate_artifact(artifact, DEFAULT_LIMITS)

    def test_rc20_mismatched_pass_is_rejected_after_rehash(self) -> None:
        artifact = self.fresh_incomplete("rc20-mismatched-pass")
        rows = read_ndjson(artifact / OBJECT_LEDGER_FILE)
        rows[0]["second_pass"]["decompressed_stream_sha256"] = "f" * 64
        write_ndjson(artifact / OBJECT_LEDGER_FILE, rows)
        refresh_artifact_bindings(artifact)
        with self.assertRaises((ArtifactBoundaryError, ValueError)):
            validate_artifact(artifact, DEFAULT_LIMITS)

    def test_rc20_missing_primary_reducer_is_rejected_after_rehash(self) -> None:
        artifact = self.fresh_incomplete("rc20-missing-reducer")
        rows = read_ndjson(artifact / REDUCER_LEDGER_FILE)
        write_ndjson(artifact / REDUCER_LEDGER_FILE, rows[:-1])
        refresh_artifact_bindings(artifact)
        with self.assertRaises(ArtifactBoundaryError):
            validate_artifact(artifact, DEFAULT_LIMITS)

    def test_rc20_false_gate_requires_real_unclassifiable_units(self) -> None:
        artifact = self.fresh_incomplete("rc20-false-gate-without-unclassified")
        conservation_path = artifact / CONSERVATION_FILE
        conservation = json.loads(conservation_path.read_bytes())
        replacement_taxon = next(taxon for taxon in TAXA if taxon != "UNCLASSIFIABLE")
        for row in conservation["unit_universes"]:
            groups = row["unclassifiable_group_count"]
            occurrences = row["unclassifiable_occurrence_count"]
            row["primary_taxon_group_counts"][replacement_taxon] += groups
            row["primary_taxon_occurrence_counts"][replacement_taxon] += occurrences
            row["primary_taxon_group_counts"]["UNCLASSIFIABLE"] = 0
            row["primary_taxon_occurrence_counts"]["UNCLASSIFIABLE"] = 0
            row["unclassifiable_group_count"] = 0
            row["unclassifiable_occurrence_count"] = 0
        conservation_path.write_bytes(canonical_json_bytes(conservation))
        refresh_artifact_bindings(artifact)
        with self.assertRaises(ArtifactBoundaryError):
            validate_artifact(artifact, DEFAULT_LIMITS)

    def test_target_metadata_mutation_is_rejected_semantically(self) -> None:
        artifact = self.fresh_complete("wrong-target-metadata")
        rows = read_ndjson(artifact / OBJECT_LEDGER_FILE)
        rows[0]["expected_identity"]["etag"] = '"self-consistent-false-etag"'
        rows[0]["response"]["etag"] = '"self-consistent-false-etag"'
        write_ndjson(artifact / OBJECT_LEDGER_FILE, rows)
        refresh_artifact_bindings(artifact)
        with self.assertRaises(ArtifactBoundaryError):
            validate_artifact(artifact, DEFAULT_LIMITS)

    def test_self_consistent_false_pair_proof_is_rejected(self) -> None:
        artifact = self.fresh_complete("false-self-consistent-proof")
        proofs = read_ndjson(artifact / PAIR_PROOF_FILE)
        units = read_ndjson(artifact / UNIT_FILE)
        proof = proofs[0]
        old_id = str(proof["proof_id"])
        proof["projection"]["member_count"] = 3
        projection = canonical_json_bytes(
            proof["projection"],
            final_newline=False,
        )
        proof_type = str(proof["record_type"])
        new_id = hashlib.sha256(
            frame(proof_type.encode("ascii"), projection)
        ).hexdigest()
        proof["proof_id"] = new_id
        proof["proof_projection_sha256"] = hashlib.sha256(projection).hexdigest()
        updated = 0
        for unit in units:
            for reference in unit["proof_references"]:
                if reference["proof_id"] == old_id:
                    reference["proof_id"] = new_id
                    reference["proof_projection_sha256"] = hashlib.sha256(
                        projection
                    ).hexdigest()
                    updated += 1
        self.assertGreater(updated, 0)
        write_ndjson(artifact / PAIR_PROOF_FILE, proofs)
        write_ndjson(artifact / UNIT_FILE, units)
        refresh_artifact_bindings(artifact)
        validate_artifact(artifact, DEFAULT_LIMITS)
        with self.assertRaises(EvidenceValidationError):
            validate_science(artifact)

    def test_self_consistent_missing_raw_provenance_is_rejected(self) -> None:
        artifact = self.fresh_incomplete("missing-raw-record-provenance")
        rows = read_ndjson(artifact / PROTOCOL_ROWS_FILE)
        owner = next(row for row in rows if row["raw_record_value"] is not None)
        owner["raw_record_value"] = None
        owner["retained_row_id"] = hashlib.sha256(
            canonical_json_bytes(
                {
                    key: value
                    for key, value in owner.items()
                    if key != "retained_row_id"
                },
                final_newline=False,
            )
        ).hexdigest()
        write_ndjson(artifact / PROTOCOL_ROWS_FILE, rows)
        refresh_artifact_bindings(artifact)
        validate_artifact(artifact, DEFAULT_LIMITS)
        with self.assertRaises(EvidenceValidationError):
            validate_science(artifact)

    def test_dangling_and_ambiguous_proof_joins_are_rejected(self) -> None:
        dangling = self.fresh_complete("dangling-proof")
        units = read_ndjson(dangling / UNIT_FILE)
        reference = next(
            reference
            for unit in units
            for reference in unit["proof_references"]
        )
        reference["proof_id"] = "f" * 64
        write_ndjson(dangling / UNIT_FILE, units)
        refresh_artifact_bindings(dangling)
        validate_artifact(dangling, DEFAULT_LIMITS)
        with self.assertRaises(EvidenceValidationError):
            validate_science(dangling)

        ambiguous = self.fresh_complete("ambiguous-proof")
        proofs = read_ndjson(ambiguous / PAIR_PROOF_FILE)
        proofs.append(dict(proofs[0]))
        write_ndjson(ambiguous / PAIR_PROOF_FILE, proofs)
        refresh_artifact_bindings(ambiguous)
        validate_artifact(ambiguous, DEFAULT_LIMITS)
        with self.assertRaises(EvidenceValidationError):
            validate_science(ambiguous)

    def test_shuffled_retained_input_preserves_science_and_proof_semantics(self) -> None:
        artifact = self.fresh_complete("shuffled-retained-input")
        unit_bytes = (artifact / UNIT_FILE).read_bytes()
        proof_bytes = (artifact / PAIR_PROOF_FILE).read_bytes()
        terminal_before = json.loads((artifact / RESULT_FILE).read_bytes())[
            "terminal_class"
        ]
        rows = read_ndjson(artifact / PROTOCOL_ROWS_FILE)
        self.assertGreater(len(rows), 1)
        write_ndjson(artifact / PROTOCOL_ROWS_FILE, list(reversed(rows)))
        refresh_artifact_bindings(artifact)
        validate_artifact(artifact, DEFAULT_LIMITS)
        validate_science(artifact)
        self.assertEqual((artifact / UNIT_FILE).read_bytes(), unit_bytes)
        self.assertEqual((artifact / PAIR_PROOF_FILE).read_bytes(), proof_bytes)
        self.assertEqual(
            json.loads((artifact / RESULT_FILE).read_bytes())["terminal_class"],
            terminal_before,
        )

    def test_frozen_locator_order_is_utf8_sha_then_numeric_ordinals(self) -> None:
        digest = "11" * 32
        rows = [
            ("prefix/2.lz4", digest, 0, 0),
            ("prefix/10.lz4", digest, 0, 0),
            ("prefix/10.lz4", digest, 10, 0),
            ("prefix/10.lz4", digest, 2, 0),
        ]
        observed = sorted(
            rows,
            key=lambda row: raw_locator_order_key(
                object_key=row[0],
                verified_compressed_sha256=row[1],
                record_ordinal_zero_based=row[2],
                event_ordinal_zero_based=row[3],
            ),
        )
        self.assertEqual(
            observed,
            [rows[1], rows[3], rows[2], rows[0]],
        )
        ranks = canonical_object_locator_ranks(
            (
                ("prefix/2.lz4", digest),
                ("prefix/10.lz4", "22" * 32),
                ("prefix/10.lz4", digest),
            )
        )
        self.assertEqual(ranks[("prefix/10.lz4", digest)], 0)
        self.assertEqual(ranks[("prefix/10.lz4", "22" * 32)], 1)
        self.assertEqual(ranks[("prefix/2.lz4", digest)], 2)

    def test_preflight_artifact_uses_truthful_cross_step_time_and_meter(self) -> None:
        artifact = self.build_preflight("truthful-preflight")
        validate_artifact(artifact, DEFAULT_LIMITS)
        validate_science(artifact)
        resource = json.loads((artifact / RESOURCE_LEDGER_FILE).read_bytes())
        measurement = resource["measurements"][0]
        self.assertEqual(measurement["elapsed_runtime_seconds_floor"], 2)
        self.assertEqual(resource["packaging_elapsed_seconds_floor"], 2)
        self.assertGreater(resource["peak_bounded_workspace_bytes"], 0)
        self.assertGreaterEqual(
            resource["peak_tracked_workspace_bytes"],
            resource["tracked_workspace_bytes_before_packaging"],
        )
        self.assertEqual((artifact / RETURN_CODE_FILE).read_text(), "21\n")
        self.assertTrue(
            all((artifact / name).read_bytes() == b"" for name in SCIENCE_CONTAINERS)
        )

    def test_rc21_terminal_contradictions_fail_after_full_rehash(self) -> None:
        complete_claim = self.build_preflight("rc21-complete-claim")
        result = json.loads((complete_claim / RESULT_FILE).read_bytes())
        result["research_conclusion"] = "PROVEN_COMPLETE_TAXONOMY_ONLY"
        (complete_claim / RESULT_FILE).write_bytes(canonical_json_bytes(result))
        refresh_artifact_bindings(complete_claim)
        with self.assertRaises((ArtifactBoundaryError, ValueError)):
            validate_artifact(complete_claim, DEFAULT_LIMITS)

        authority_claim = self.build_preflight("rc21-authority-claim")
        result = json.loads((authority_claim / RESULT_FILE).read_bytes())
        result["R11_CLOSED"] = True
        (authority_claim / RESULT_FILE).write_bytes(canonical_json_bytes(result))
        refresh_artifact_bindings(authority_claim)
        with self.assertRaises(ArtifactBoundaryError):
            validate_artifact(authority_claim, DEFAULT_LIMITS)

        gate_claim = self.build_preflight("rc21-complete-gate-claim")
        conservation_path = gate_claim / CONSERVATION_FILE
        conservation = json.loads(conservation_path.read_bytes())
        conservation["terminal_gates"][
            "every_authoritative_unit_receives_exactly_one_primary_taxon"
        ] = True
        conservation_path.write_bytes(canonical_json_bytes(conservation))
        refresh_artifact_bindings(gate_claim)
        with self.assertRaises(ArtifactBoundaryError):
            validate_artifact(gate_claim, DEFAULT_LIMITS)

    def test_rc0_cannot_contain_rehashed_early_stop_evidence(self) -> None:
        artifact = self.fresh_complete("rc0-with-stop")
        stop = json.loads((artifact / STOP_LEDGER_FILE).read_bytes())
        stop["entries"].append(
            {
                "sequence_zero_based": 0,
                "diagnostic_id": DIAGNOSTIC_ID,
                "stop_code": "CONTRADICTORY_EARLY_STOP",
                "phase": "TAXONOMY",
                "object_ordinal_zero_based": None,
                "evidence_sha256": "0" * 64,
            }
        )
        (artifact / STOP_LEDGER_FILE).write_bytes(canonical_json_bytes(stop))
        refresh_artifact_bindings(artifact)
        with self.assertRaises(ArtifactBoundaryError):
            validate_artifact(artifact, DEFAULT_LIMITS)

    def test_terminal_return_codes_propagate_after_validation_and_upload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rc0 = root / "rc0"
            rc20 = root / "rc20"
            rc21 = root / "rc21"
            rc0.write_text("0\n", encoding="ascii")
            rc20.write_text("20\n", encoding="ascii")
            rc21.write_text("21\n", encoding="ascii")
            self.assertEqual(
                validated_terminal_return_code(self.complete_artifact, rc0),
                0,
            )
            self.assertEqual(
                validated_terminal_return_code(self.incomplete_artifact, rc20),
                20,
            )
            preflight = self.build_preflight("terminal-propagation-preflight")
            self.assertEqual(validated_terminal_return_code(preflight, rc21), 21)
            with self.assertRaises(TerminalPropagationError):
                validated_terminal_return_code(self.incomplete_artifact, rc0)

        root = Path(__file__).resolve().parents[1]
        workflow = (
            root
            / "research/archive_inventory/r11a_corrective/workflows/"
            "hyperliquid-archive-r11a-identity-boundary-diagnostic-r7.yml"
        ).read_text(encoding="utf-8")
        validation = workflow.rfind("validate_r11a_execution_artifact_r7.py")
        upload = workflow.rfind("actions/upload-artifact")
        propagation = workflow.rfind("terminal_propagation")
        self.assertLess(validation, upload)
        self.assertLess(upload, propagation)
        self.assertIn("always()", workflow[upload:])

    def test_sqlite_transient_journal_peak_is_metered(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = R7WorkspaceMeter(
                Path(temporary) / "workspace",
                DEFAULT_LIMITS,
                RuntimeGuard(DEFAULT_LIMITS),
            )
            meter.bootstrap()
            database = MeteredSQLite(
                meter.root / "transient.sqlite",
                meter,
                10_000_000,
                "transient peak test",
            )
            try:
                with database.transaction("create transient table") as connection:
                    connection.execute("CREATE TABLE values_table(value BLOB)")
                with database.transaction("seed transient table") as connection:
                    connection.execute(
                        "INSERT INTO values_table VALUES(?)",
                        (b"x" * 1_000_000,),
                    )
                with database.transaction("rewrite transient table") as connection:
                    connection.execute(
                        "UPDATE values_table SET value=?",
                        (b"y" * 1_000_000,),
                    )
                self.assertGreater(meter.peak_known_bytes, meter.known_bytes)
                self.assertGreaterEqual(
                    meter.peak_bounded_bytes,
                    meter.peak_known_bytes,
                )
                self.assertEqual(
                    database.connection.execute("PRAGMA temp_store").fetchone()[0],
                    2,
                )
            finally:
                database.close_delete()
            self.assertEqual(meter.verify_actual_usage(), 0)


class FrozenTaxonomyAndWorkflowTests(unittest.TestCase):
    def test_late_http_error_closes_every_distinct_transport_owner(self) -> None:
        import urllib.error

        from research.archive_inventory.r11a_corrective import network

        class LateHTTPError(urllib.error.HTTPError):
            def __init__(self) -> None:
                super().__init__(
                    "https://example.invalid/late-error",
                    503,
                    "late read failure",
                    {},
                    io.BytesIO(b"late-error"),
                )
                self.close_calls = 0

            def close(self) -> None:
                self.close_calls += 1
                super().close()

        class Response:
            status = 200

            def __init__(self, headers: dict[str, str], late_error: LateHTTPError) -> None:
                self.headers = headers
                self.late_error = late_error
                self.close_calls = 0

            def getcode(self) -> int:
                return self.status

            def read(self, size: int = -1) -> bytes:
                del size
                raise self.late_error

            def close(self) -> None:
                self.close_calls += 1
                try:
                    raise ValueError("injected nested response cleanup cause")
                except ValueError as exc:
                    raise OSError(
                        "injected acquired response cleanup failure"
                    ) from exc

        class Opener:
            def __init__(self, response: Response) -> None:
                self.response = response

            def open(self, request: object, timeout: int) -> Response:
                del request, timeout
                return self.response

        history_error = LateHTTPError()
        history_response = Response(
            {"Content-Length": "1"},
            history_error,
        )
        with self.assertRaises(network.TransportCleanupError) as history_raised:
            network.validate_single_use_history(
                repository="Mathisve1/onchain-wallet-intelligence-lab",
                workflow_file=(
                    "hyperliquid-archive-r11a-identity-boundary-diagnostic.yml"
                ),
                current_run_id=41,
                current_run_attempt=1,
                single_use_window_start_utc="2026-01-01T00:00:00Z",
                token="synthetic",
                opener=Opener(history_response),  # type: ignore[arg-type]
            )
        history_graph = exception_graph(history_raised.exception)
        self.assertEqual(history_response.close_calls, 1)
        self.assertEqual(history_error.close_calls, 1)
        self.assertTrue(any(value is history_error for value in history_graph))
        self.assertTrue(
            any(
                str(value) == "injected nested response cleanup cause"
                for value in history_graph
            )
        )
        self.assertTrue(
            any(
                str(value) == "injected acquired response cleanup failure"
                for value in history_graph
            )
        )

        with tempfile.TemporaryDirectory() as temporary:
            guard = RuntimeGuard(DEFAULT_LIMITS)
            meter = R7WorkspaceMeter(
                Path(temporary) / "workspace",
                DEFAULT_LIMITS,
                guard,
            )
            meter.bootstrap()
            target = DEFAULT_SELECTION.targets[0]
            state = ExecutionEvidenceState(DEFAULT_SELECTION.targets, DEFAULT_LIMITS)
            download_error = LateHTTPError()
            download_response = Response(
                {
                    "ETag": target.expected_etag,
                    "Content-Length": str(target.expected_size_bytes),
                    "x-amz-request-charged": "requester",
                },
                download_error,
            )

            class Budget:
                def authorize_request(
                    self,
                    *,
                    request_ordinal_zero_based: int,
                    expected_response_bytes: int,
                ) -> None:
                    self.observed = (
                        request_ordinal_zero_based,
                        expected_response_bytes,
                    )

            destination = meter.root / "download.lz4"
            with self.assertRaises(network.TransportCleanupError) as download_raised:
                network.download_exact_object(
                    target=target,
                    destination=destination,
                    credentials=AWSCredentials(
                        access_key_id="SYNTHETIC",
                        secret_access_key="SYNTHETIC",
                        session_token="SYNTHETIC",
                    ),
                    state=state,
                    meter=meter,
                    runtime_guard=guard,
                    budget_guard=Budget(),  # type: ignore[arg-type]
                    opener=Opener(download_response),  # type: ignore[arg-type]
                )
            download_graph = exception_graph(download_raised.exception)
            self.assertEqual(download_response.close_calls, 1)
            self.assertEqual(download_error.close_calls, 1)
            self.assertTrue(any(value is download_error for value in download_graph))
            self.assertTrue(
                any(
                    str(value) == "injected acquired response cleanup failure"
                    for value in download_graph
                )
            )
            self.assertFalse(destination.exists())
            self.assertEqual(meter.reserved_bytes, 0)
            self.assertEqual(meter.known_bytes, 0)
            self.assertEqual(meter.verify_actual_usage(), 0)

    def test_history_response_cleanup_is_typed_and_has_fatal_cli_code(self) -> None:
        from research.archive_inventory.r11a_corrective import network

        payload = canonical_json_bytes(
            {
                "workflow_runs": [
                    {
                        "created_at": "2026-01-02T00:00:00Z",
                        "id": 41,
                    }
                ]
            }
        )

        class Response:
            status = 200
            headers = {"Content-Length": str(len(payload))}

            def __init__(self) -> None:
                self.stream = io.BytesIO(payload)
                self.injected = False

            def getcode(self) -> int:
                return self.status

            def read(self, size: int = -1) -> bytes:
                return self.stream.read(size)

            def close(self) -> None:
                self.stream.close()
                if not self.injected:
                    self.injected = True
                    raise OSError("injected history response cleanup failure")

        class Opener:
            def __init__(self, response: Response) -> None:
                self.response = response

            def open(self, request: object, timeout: int) -> Response:
                del request, timeout
                return self.response

        response = Response()
        with self.assertRaises(network.TransportCleanupError) as raised:
            network.validate_single_use_history(
                repository="Mathisve1/onchain-wallet-intelligence-lab",
                workflow_file=(
                    "hyperliquid-archive-r11a-identity-boundary-diagnostic.yml"
                ),
                current_run_id=41,
                current_run_attempt=1,
                single_use_window_start_utc="2026-01-01T00:00:00Z",
                token="synthetic",
                opener=Opener(response),  # type: ignore[arg-type]
            )
        self.assertEqual(
            str(raised.exception.__cause__),
            "injected history response cleanup failure",
        )

        with mock.patch.dict(os.environ, {"GH_TOKEN": "synthetic"}), mock.patch.object(
            network,
            "validate_single_use_history",
            side_effect=network.TransportCleanupError("injected CLI cleanup failure"),
        ):
            self.assertEqual(
                network.main(
                    [
                        "verify-history",
                        "--repository",
                        "Mathisve1/onchain-wallet-intelligence-lab",
                        "--workflow-file",
                        "hyperliquid-archive-r11a-identity-boundary-diagnostic.yml",
                        "--current-run-id",
                        "41",
                        "--current-run-attempt",
                        "1",
                        "--window-start",
                        "2026-01-01T00:00:00Z",
                    ]
                ),
                70,
            )

        with mock.patch.dict(os.environ, {"GH_TOKEN": "synthetic"}), mock.patch.object(
            network,
            "validate_single_use_history",
            side_effect=StorageCleanupError("injected foreign cleanup marker"),
        ):
            self.assertEqual(
                network.main(
                    [
                        "verify-history",
                        "--repository",
                        "Mathisve1/onchain-wallet-intelligence-lab",
                        "--workflow-file",
                        "hyperliquid-archive-r11a-identity-boundary-diagnostic.yml",
                        "--current-run-id",
                        "41",
                        "--current-run-attempt",
                        "1",
                        "--window-start",
                        "2026-01-01T00:00:00Z",
                    ]
                ),
                70,
            )

    def test_history_cleanup_never_opens_pre_oidc_artifact_routes(self) -> None:
        root = Path(__file__).resolve().parents[1]
        workflow = (
            root
            / "research/archive_inventory/r11a_corrective/workflows/"
            "hyperliquid-archive-r11a-identity-boundary-diagnostic-r7.yml"
        ).read_text(encoding="utf-8")
        self.assertIn('echo "fatal_cleanup=true" >> "${GITHUB_OUTPUT}"', workflow)
        self.assertIn('if test "${history_rc}" = 70; then', workflow)
        self.assertEqual(
            workflow.count("steps.static.outputs.fatal_cleanup != 'true'"),
            2,
        )
        producer = workflow.index(
            "Produce and validate phase-truthful pre-OIDC failure artifact"
        )
        uploader = workflow.index("Upload only validated pre-OIDC failure evidence")
        oidc = workflow.index("Assume exact successor role")
        self.assertLess(producer, uploader)
        self.assertLess(uploader, oidc)

    def test_exact_authoritative_universes_and_taxa(self) -> None:
        self.assertEqual(
            tuple(value.value for value in UnitUniverse),
            AUTHORITATIVE_UNIT_UNIVERSES,
        )
        self.assertEqual(tuple(value.value for value in Taxon), TAXA)
        self.assertEqual(
            DIAGNOSTIC_ID,
            "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-002",
        )
        self.assertEqual(
            IMPLEMENTATION_ID,
            "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-CORRECTIVE-R7",
        )

    def test_workflow_has_no_inline_https_and_no_inert_validator(self) -> None:
        root = Path(__file__).resolve().parents[1]
        workflow = (
            root
            / "research/archive_inventory/r11a_corrective/workflows/"
            "hyperliquid-archive-r11a-identity-boundary-diagnostic-r7.yml"
        ).read_text(encoding="utf-8")
        self.assertNotIn("urllib.request", workflow)
        self.assertNotIn(
            "validate_r11a_corrective_implementation",
            workflow,
        )
        self.assertNotIn("validate_r11a_preregistration.py", workflow)
        self.assertIn("validate_r11a_v2_preregistration.py", workflow)
        self.assertIn("validate_r11a_v2_bindings.py", workflow)
        self.assertIn("validate_r11a_runtime_binding_r7.py", workflow)
        self.assertIn("validate_r11a_execution_artifact_r7.py", workflow)
        self.assertIn("R11A_CORRECTIVE_IMPLEMENTATION_CONTRACT_R7.json", workflow)
        self.assertLess(
            workflow.index("validate_r11a_execution_artifact_r7.py"),
            workflow.index("actions/upload-artifact"),
        )

    def test_current_draft_has_no_active_runtime_binding(self) -> None:
        self.assertFalse(BINDING.exists())
        with self.assertRaises(RuntimeBindingError):
            validate_runtime_binding("1" * 40, 1)

    def test_r7_seal_is_distinct_fail_closed_and_covers_private_cores(self) -> None:
        root = Path(__file__).resolve().parents[1]
        contract = json.loads(
            (
                root
                / "research/archive_inventory/r11a_corrective/"
                "R11A_CORRECTIVE_IMPLEMENTATION_CONTRACT_R7.json"
            ).read_bytes()
        )
        status = json.loads(
            (
                root
                / "research/archive_inventory/r11a_corrective/"
                "R11A_CORRECTIVE_STATUS_R7.json"
            ).read_bytes()
        )
        self.assertEqual(contract["implementation_id"], IMPLEMENTATION_ID)
        self.assertFalse(contract["implementation_review_green"])
        self.assertTrue(contract["pricing_binding_pending"])
        self.assertFalse(contract["owner_approval_eligible"])
        authority = contract["authority_reconciliation"]
        self.assertTrue(authority["canonical_amendment_002_present"])
        self.assertTrue(authority["canonical_amendment_002_binding_valid"])
        self.assertEqual(
            authority["canonical_amendment_002_internal_id"],
            "R11A-CORRECTIVE-PREREGISTRATION-AMENDMENT-002",
        )
        self.assertEqual(
            authority["canonical_amendment_002_sha256"],
            "bdd610c678189e8098381d8c4a0fd12296bf2e0cd8e9ec0fed375b073872552f",
        )
        self.assertEqual(
            contract["approval_blockers"],
            [
                "INDEPENDENT_CLEAN_CONTEXT_REVIEW_NOT_COMPLETED",
                "CURRENT_OFFICIAL_PRICING_AND_EUR_BINDING_PENDING",
            ],
        )
        self.assertFalse(status["implementation_review_green"])
        self.assertFalse(status["owner_approval_eligible"])
        self.assertTrue(status["canonical_amendment_002_binding_valid"])
        sealed = set(contract["implementation_file_hashes"])
        for relative in (
            "governance/_validate_r11a_runtime_binding_core_r7.py",
            "research/archive_inventory/r11a_corrective/_artifact_contract_core_r7.py",
            "research/archive_inventory/r11a_corrective/_artifact_core_r7.py",
            "research/archive_inventory/r11a_corrective/_artifact_schema_core_r7.py",
            "research/archive_inventory/r11a_corrective/_runner_core_r7.py",
            "research/archive_inventory/r11a_corrective/_taxonomy_contract_core_r7.py",
            "research/archive_inventory/r11a_corrective/_taxonomy_core_r7.py",
            "research/archive_inventory/r11a_corrective/locator_order.py",
            "research/archive_inventory/r11a_corrective/proof_semantics_r7.py",
            "research/archive_inventory/r11a_corrective/taxonomy_precedence_r7.py",
            "research/archive_inventory/r11a_corrective/terminal_propagation.py",
            "governance/validate_repository.py",
            "governance/regenerate_manifest.py",
        ):
            self.assertIn(relative, sealed)
        self.assertEqual(
            contract["repository_manifest_path"],
            "governance/REPOSITORY_MANIFEST.sha256",
        )

    def test_missing_executed_file_seal_binding_fails_closed(self) -> None:
        import governance.seal_r11a_corrective_r7 as seal

        root = Path(__file__).resolve().parents[1]
        contract = json.loads(
            (
                root
                / "research/archive_inventory/r11a_corrective/"
                "R11A_CORRECTIVE_IMPLEMENTATION_CONTRACT_R7.json"
            ).read_bytes()
        )
        contract["implementation_file_hashes"].pop(
            "research/archive_inventory/r11a_corrective/proof_semantics_r7.py"
        )
        with self.assertRaises(seal.SealError):
            seal.validate_seal_coverage(contract)

    def test_executed_file_mutation_breaks_r7_seal(self) -> None:
        import governance.seal_r11a_corrective_r7 as seal

        original = seal.sha256

        def mutated(relative: str) -> str:
            if relative.endswith("proof_semantics_r7.py"):
                return "0" * 64
            return original(relative)

        with mock.patch.object(seal, "sha256", side_effect=mutated):
            with self.assertRaises(seal.SealError):
                seal.check_all()

    def test_manifest_mutation_breaks_repository_validation(self) -> None:
        import governance.validate_repository as repository_validator

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            governance = root / "governance"
            governance.mkdir()
            payload = root / "payload.txt"
            payload.write_text("bound\n", encoding="utf-8")
            digest = hashlib.sha256(payload.read_bytes()).hexdigest()
            expected = f"{digest}  payload.txt\n"
            manifest = governance / "REPOSITORY_MANIFEST.sha256"
            manifest.write_text(expected, encoding="ascii")
            with mock.patch.object(
                repository_validator,
                "ROOT",
                root,
            ), mock.patch.object(
                repository_validator,
                "render_manifest",
                return_value=expected,
            ):
                self.assertEqual(repository_validator.validate_manifest(), 1)
                manifest.write_text(
                    f"{'0' * 64}  payload.txt\n",
                    encoding="ascii",
                )
                with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
                    repository_validator.validate_manifest()

    def test_taxonomy_uses_disk_backed_group_state_not_first_current_shortcuts(self) -> None:
        import research.archive_inventory.r11a_corrective.taxonomy as taxonomy

        source = inspect.getsource(taxonomy)
        self.assertIn("BlockScratch", source)
        self.assertIn("EventScratch", source)
        self.assertNotIn("first/current", source)
        self.assertNotIn("block_rows: list", source)


if __name__ == "__main__":
    unittest.main()
