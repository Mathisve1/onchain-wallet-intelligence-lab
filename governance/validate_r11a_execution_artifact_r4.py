#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.archive_inventory.r11a_corrective.artifact_r3 import (  # noqa: E402
    CONSERVATION_FILE,
    CONTEXT_FILE,
    OBJECT_LEDGER_FILE,
    REDUCER_LEDGER_FILE,
    RESOURCE_LEDGER_FILE,
    RESULT_FILE,
    SCIENCE_CONTAINERS,
    validate_artifact,
)
from research.archive_inventory.r11a_corrective.canonical import (  # noqa: E402
    FrozenObject,
    NumberToken,
    canonical_json_bytes,
    strict_json_loads,
)
from research.archive_inventory.r11a_corrective.limits import DEFAULT_LIMITS  # noqa: E402


class ValidationError(AssertionError):
    pass


def object_value(value: object, label: str) -> FrozenObject:
    if not isinstance(value, FrozenObject):
        raise ValidationError(f"{label} must be object")
    return value


def array_value(value: object, label: str) -> tuple[object, ...]:
    if not isinstance(value, tuple):
        raise ValidationError(f"{label} must be array")
    return value


def integer(value: object, label: str) -> int:
    if isinstance(value, NumberToken) and value.is_integer_token:
        return int(value.token, 10)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise ValidationError(f"{label} must be exact integer")


def text(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{label} must be text")
    return value


def rows(path: Path):  # type: ignore[no-untyped-def]
    with path.open("rb") as handle:
        for ordinal, raw in enumerate(handle):
            if not raw.endswith(b"\n"):
                raise ValidationError(f"NDJSON row lacks newline: {path}:{ordinal}")
            yield object_value(strict_json_loads(raw), f"{path.name}:{ordinal}")


def validate_objects(path: Path) -> dict[str, int]:
    count = 0
    requested = 0
    successful = 0
    compressed = 0
    pass1_decompressed = 0
    pass2_decompressed = 0
    seen_ordinals: set[int] = set()
    for row in rows(path):
        ordinal = integer(row["object_ordinal_zero_based"], "object ordinal")
        if ordinal in seen_ordinals or not 0 <= ordinal < 72:
            raise ValidationError("object ledger ordinal is duplicate or outside exact scope")
        seen_ordinals.add(ordinal)
        count += 1
        requests = integer(row["request_count"], "request_count")
        if requests not in {0, 1}:
            raise ValidationError("request count is outside one-request envelope")
        requested += requests
        if row["body_status"] == "COMPLETE_SHA256_VERIFIED":
            successful += 1
            compressed += integer(row["body_bytes_received"], "body bytes")
        first = row["first_pass"]
        second = row["second_pass"]
        if first is not None:
            pass1_decompressed += integer(object_value(first, "first_pass")["decompressed_bytes"], "first decompressed bytes")
        if second is not None:
            pass2_decompressed += integer(object_value(second, "second_pass")["decompressed_bytes"], "second decompressed bytes")
    if count != 72 or seen_ordinals != set(range(72)):
        raise ValidationError("object ledger is not exact 72-object scope")
    return {
        "object_count": count,
        "request_count": requested,
        "successful_object_count": successful,
        "compressed_bytes": compressed,
        "first_pass_decompressed_bytes": pass1_decompressed,
        "second_pass_decompressed_bytes": pass2_decompressed,
    }


def validate_primary_reducers(path: Path) -> None:
    observed: set[tuple[str, int]] = set()
    for row in rows(path):
        key = (
            text(row["reducer_id"], "reducer_id"),
            integer(row["partition_ordinal_zero_based"], "partition ordinal"),
        )
        if key in observed:
            raise ValidationError("duplicate primary reducer row")
        observed.add(key)
        if row["processing_status"] == "COMPLETE":
            if row["source_multiset_commitment"] != row["destination_multiset_commitment"]:
                raise ValidationError("primary reducer multiset commitment mismatch")
    expected = {
        (reducer, partition)
        for reducer in ("BLOCK_NUMBER", "LEGACY_WEAK_KEY_HASH")
        for partition in range(256)
    }
    if observed != expected:
        raise ValidationError("primary reducer ledger is not exact 512-row scope")


def validate_layer_conservation(resource_path: Path) -> dict[str, object]:
    matches: list[FrozenObject] = []
    for row in rows(resource_path):
        if row["phase"] == "SCIENCE_COMPLETE_BEFORE_PACKAGING":
            matches.append(row)
    if len(matches) != 1:
        raise ValidationError("exactly one final scientific resource row is required")
    aggregate = object_value(matches[0]["aggregate_parse_conservation"], "aggregate conservation")
    if aggregate["status"] != "EXACT_TWO_PASS_LAYER_CONSERVATION_PASS":
        raise ValidationError("aggregate layer conservation did not pass")
    first = object_value(aggregate["first_pass_totals"], "first pass totals")
    second = object_value(aggregate["second_pass_totals"], "second pass totals")
    if first != second:
        raise ValidationError("aggregate first and second pass totals differ")
    raw_events = integer(first["raw_event_observation_count"], "raw event count")
    for valid, invalid in (
        ("valid_wallet_occurrence_count", "invalid_wallet_occurrence_count"),
        ("valid_coin_occurrence_count", "invalid_coin_occurrence_count"),
        ("valid_tid_occurrence_count", "invalid_tid_occurrence_count"),
    ):
        if integer(first[valid], valid) + integer(first[invalid], invalid) != raw_events:
            raise ValidationError(f"aggregate layer partition failed: {valid}")
    if integer(first["block_time_other_prefix_count"], "other block prefix") != 0:
        raise ValidationError("block_time outside path or immediately previous hour")
    return {key: value for key, value in first.items()}


def validate_scientific_joins(artifact: Path, conservation: FrozenObject) -> None:
    with tempfile.TemporaryDirectory(prefix="r11a-artifact-validator-") as temp:
        database = Path(temp) / "joins.sqlite"
        connection = sqlite3.connect(database)
        try:
            connection.execute("PRAGMA journal_mode=OFF")
            connection.execute("PRAGMA synchronous=FULL")
            connection.executescript(
                """
                CREATE TABLE units(unit_id TEXT PRIMARY KEY, universe TEXT NOT NULL, taxon TEXT NOT NULL, occurrences INTEGER NOT NULL);
                CREATE TABLE proofs(proof_id TEXT PRIMARY KEY, proof_type TEXT NOT NULL);
                CREATE TABLE refs(unit_id TEXT NOT NULL, proof_id TEXT NOT NULL, proof_type TEXT NOT NULL, UNIQUE(unit_id,proof_id,proof_type));
                CREATE TABLE duplicate_refs(row_id TEXT PRIMARY KEY, unit_id TEXT NOT NULL);
                """
            )
            group_counts: dict[str, int] = {}
            occurrence_counts: dict[str, int] = {}
            unclassifiable_groups: dict[str, int] = {}
            unclassifiable_occurrences: dict[str, int] = {}
            for row in rows(artifact / "r11a-taxonomy-units.ndjson"):
                unit_id = text(row["taxonomy_unit_id"], "taxonomy unit ID")
                if re.fullmatch(r"[0-9a-f]{64}", unit_id) is None:
                    raise ValidationError("taxonomy unit ID is not SHA-256")
                universe = text(row["unit_universe"], "unit universe")
                taxon = text(row["primary_taxon"], "taxon")
                occurrences = integer(row["occurrence_count"], "occurrence count")
                try:
                    connection.execute("INSERT INTO units VALUES(?,?,?,?)", (unit_id, universe, taxon, occurrences))
                except sqlite3.IntegrityError as exc:
                    raise ValidationError("duplicate taxonomy unit ID") from exc
                group_counts[universe] = group_counts.get(universe, 0) + 1
                occurrence_counts[universe] = occurrence_counts.get(universe, 0) + occurrences
                if taxon == "UNCLASSIFIABLE":
                    unclassifiable_groups[universe] = unclassifiable_groups.get(universe, 0) + 1
                    unclassifiable_occurrences[universe] = unclassifiable_occurrences.get(universe, 0) + occurrences
                for reference in array_value(row["proof_references"], "proof references"):
                    reference_object = object_value(reference, "proof reference")
                    try:
                        connection.execute(
                            "INSERT INTO refs VALUES(?,?,?)",
                            (
                                unit_id,
                                text(reference_object["proof_id"], "proof ID"),
                                text(reference_object["proof_type"], "proof type"),
                            ),
                        )
                    except sqlite3.IntegrityError as exc:
                        raise ValidationError("duplicate proof reference") from exc
            for filename, proof_type in (
                ("r11a-exact-block-replay-proofs.ndjson", "EXACT_BLOCK_REPLAY_PROOF"),
                ("r11a-expected-counterparty-pair-proofs.ndjson", "EXPECTED_COUNTERPARTY_PAIR_PROOF"),
            ):
                for row in rows(artifact / filename):
                    proof_id = text(row["proof_id"], "proof ID")
                    try:
                        connection.execute("INSERT INTO proofs VALUES(?,?)", (proof_id, proof_type))
                    except sqlite3.IntegrityError as exc:
                        raise ValidationError("duplicate proof ID") from exc
            for filename in (
                "r11a-duplicate-observations.ndjson",
                "r11a-block-overlap-matrix.ndjson",
                "r11a-protocol-trade-group-members.ndjson",
            ):
                for row in rows(artifact / filename):
                    unit_id = text(row["taxonomy_unit_id"], "taxonomy unit reference")
                    row_id = __import__("hashlib").sha256(
                        canonical_json_bytes(row, final_newline=False)
                    ).hexdigest()
                    try:
                        connection.execute("INSERT INTO duplicate_refs VALUES(?,?)", (row_id, unit_id))
                    except sqlite3.IntegrityError as exc:
                        raise ValidationError("duplicate retained scientific row identity") from exc
            connection.commit()
            dangling_refs = connection.execute(
                """
                SELECT COUNT(*) FROM refs r
                LEFT JOIN units u ON u.unit_id=r.unit_id
                LEFT JOIN proofs p ON p.proof_id=r.proof_id AND p.proof_type=r.proof_type
                WHERE u.unit_id IS NULL OR p.proof_id IS NULL
                """
            ).fetchone()[0]
            dangling_rows = connection.execute(
                "SELECT COUNT(*) FROM duplicate_refs d LEFT JOIN units u ON u.unit_id=d.unit_id WHERE u.unit_id IS NULL"
            ).fetchone()[0]
            if dangling_refs != 0 or dangling_rows != 0:
                raise ValidationError("one or more exact-once foreign keys do not resolve")
            universe_rows = array_value(conservation["universe_rows"], "universe rows")
            if len(universe_rows) != 4:
                raise ValidationError("conservation must contain four unit universes")
            for raw in universe_rows:
                row = object_value(raw, "universe conservation row")
                universe = text(row["unit_universe"], "unit universe")
                if integer(row["group_count"], "group_count") != group_counts.get(universe, 0):
                    raise ValidationError("universe group count differs from taxonomy units")
                if integer(row["occurrence_count"], "occurrence_count") != occurrence_counts.get(universe, 0):
                    raise ValidationError("universe occurrence count differs from taxonomy units")
                if integer(row["unclassifiable_group_count"], "unclassifiable group count") != unclassifiable_groups.get(universe, 0):
                    raise ValidationError("universe unclassifiable group count mismatch")
                if integer(row["unclassifiable_occurrence_count"], "unclassifiable occurrence count") != unclassifiable_occurrences.get(universe, 0):
                    raise ValidationError("universe unclassifiable occurrence count mismatch")
        finally:
            connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--expected-run-id", type=int)
    arguments = parser.parse_args()
    validate_artifact(arguments.artifact_dir, DEFAULT_LIMITS)
    result = object_value(strict_json_loads((arguments.artifact_dir / RESULT_FILE).read_bytes()), "result")
    context = object_value(strict_json_loads((arguments.artifact_dir / CONTEXT_FILE).read_bytes()), "context")
    if arguments.expected_run_id is not None and integer(context["workflow_run_id"], "workflow_run_id") != arguments.expected_run_id:
        raise ValidationError("artifact run ID differs from current workflow run")
    if integer(context["workflow_run_attempt"], "workflow_run_attempt") != 1:
        raise ValidationError("artifact was produced by rerun")
    terminal = text(result["terminal_class"], "terminal_class")
    allowed = {
        "R11A_ROOT_CAUSE_TAXONOMY_COMPLETE": 0,
        "R11A_DIAGNOSTIC_INCOMPLETE": 20,
        "R11A_ARTIFACT_CAP_EXCEEDED": 21,
    }
    if terminal not in allowed or integer(result["return_code"], "return_code") != allowed[terminal]:
        raise ValidationError("terminal class and return code are not preregistered pair")
    for key in (
        "deduplication_performed",
        "block_replay_suppression_performed",
        "wallet_feature_publication_performed",
        "wallet_ranking_performed",
        "pnl_or_alpha_analysis_performed",
        "copyability_analysis_performed",
        "strategy_inference_performed",
        "trading_authority_opened",
    ):
        if result[key] is not False:
            raise ValidationError(f"forbidden semantic or authority flag opened: {key}")
    object_counts = validate_objects(arguments.artifact_dir / OBJECT_LEDGER_FILE)
    validate_primary_reducers(arguments.artifact_dir / REDUCER_LEDGER_FILE)
    conservation = object_value(
        strict_json_loads((arguments.artifact_dir / CONSERVATION_FILE).read_bytes()),
        "taxonomy conservation",
    )
    if result["scientific_container_status"] == "FULLY_MATERIALIZED":
        aggregate = validate_layer_conservation(arguments.artifact_dir / RESOURCE_LEDGER_FILE)
        validate_scientific_joins(arguments.artifact_dir, conservation)
        if terminal == "R11A_ROOT_CAUSE_TAXONOMY_COMPLETE":
            if object_counts["request_count"] != 72 or object_counts["successful_object_count"] != 72:
                raise ValidationError("complete taxonomy lacks 72 successful requests")
            if object_counts["compressed_bytes"] != DEFAULT_LIMITS.maximum_total_compressed_bytes:
                raise ValidationError("complete taxonomy compressed-byte conservation drift")
            if object_counts["first_pass_decompressed_bytes"] != object_counts["second_pass_decompressed_bytes"]:
                raise ValidationError("complete taxonomy decompressed passes differ")
            if object_counts["first_pass_decompressed_bytes"] * 2 > DEFAULT_LIMITS.maximum_total_decompressed_bytes_across_two_passes:
                raise ValidationError("complete taxonomy exceeds decompressed processing cap")
            if conservation["all_proof_references_resolve"] is not True:
                raise ValidationError("complete taxonomy proof-resolution claim is false")
            if aggregate["block_time_other_prefix_count"] != 0:
                raise ValidationError("complete taxonomy has invalid block-time prefix")
    else:
        if any((arguments.artifact_dir / name).stat().st_size != 0 for name in SCIENCE_CONTAINERS):
            raise ValidationError("empty failure artifact contains scientific bytes")
    print("R11A_EXECUTION_ARTIFACT_R4_VALID_BEFORE_UPLOAD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
