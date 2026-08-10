from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.archive_inventory.r10_implementation import collector as base
from research.archive_inventory.r10d_implementation import collector as r10d

BASE = ROOT / "research/archive_inventory"
PREREGISTRATION = BASE / "r11/R11_72H_PERSISTENCE_SCALING_PREREGISTRATION.json"
SELECTION = BASE / "r11/R11_72H_SELECTION.json"
APPROVAL_JSON = BASE / "r11_approval/APPROVE_HL_ARCHIVE_R11_72H_PERSISTENCE_SCALING_001.json"
APPROVAL_TEXT = BASE / "r11_approval/APPROVE_HL_ARCHIVE_R11_72H_PERSISTENCE_SCALING_001.txt"
IMPLEMENTATION = BASE / "r11_implementation/R11_IMPLEMENTATION_CONTRACT.json"
PERMISSION_POLICY = BASE / "r11_implementation/R11_PERMISSION_POLICY.json"

PILOT_ID = "HL-ARCHIVE-R11-72H-PERSISTENCE-SCALING-001"
PREREGISTRATION_MERGE = "dc63f2846652e50755369aa95d0f01ec2e174b02"
APPROVAL_MERGE = "86333a6759a492e5452bc565802fefce55a9fd6f"
APPROVAL_SHA = "1c3ec861d5df30dbdeef4dece7422bc05fab50d59aa58aa36cf3b7f8fea0d3ca"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-scaling-r11"
RULE_ID = "RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1"
MAX_REQUESTS = 72
MAX_TOTAL_COMPRESSED_BYTES = 2107738436
MAX_INDIVIDUAL_COMPRESSED_BYTES = 76616104
MAX_TOTAL_DECOMPRESSED_BYTES = 17179869184
MAX_INDIVIDUAL_DECOMPRESSED_BYTES = 536870912
MAX_RUNTIME_SECONDS = 5400
MAX_ROWS = 250000
MAX_OUTPUT_BYTES = 134217728
MAX_BLOCKS = 10000000
MAX_EVENTS = 30000000
OUTPUT_FIELDS = [
    "wallet_address", "fill_count", "active_hour_count", "active_day_count", "first_fill_time", "last_fill_time",
    "distinct_coin_count", "side_a_count", "side_b_count", "crossed_true_count",
    "liquidation_associated_fill_count", "duplicate_tid_count", "sum_abs_px_times_sz_notional_proxy",
    "sum_closed_pnl_fill_statistic",
]

# R10D's proven record-level parser uses these fail-closed processing caps from the shared base module.
# R11 raises only cardinality/output safety caps needed for the separately approved 72-hour mechanics pilot.
base.MAX_BLOCKS = MAX_BLOCKS
base.MAX_EVENTS = MAX_EVENTS
base.MAX_ROWS = MAX_ROWS
base.MAX_OUTPUT_BYTES = MAX_OUTPUT_BYTES


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise base.R10ContractError(f"JSON root must be object: {path}")
    return value


def frozen_targets() -> list[dict]:
    selection = load_json(SELECTION)
    rows = selection.get("exact_targets")
    if not isinstance(rows, list) or len(rows) != MAX_REQUESTS:
        raise base.R10ContractError("R11 exact selection cardinality drift")
    result: list[dict] = []
    for row in rows:
        result.append({
            "path_hour_utc": row["path_hour_utc"],
            "key": row["key"],
            "size": row["expected_size_bytes"],
            "etag": row["expected_etag"],
            "known_sha256": None,
        })
    return result


def validate_static_inputs() -> None:
    prereg = load_json(PREREGISTRATION)
    selection = load_json(SELECTION)
    approval = load_json(APPROVAL_JSON)
    impl = load_json(IMPLEMENTATION)
    permission = load_json(PERMISSION_POLICY)

    if hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest() != APPROVAL_SHA:
        raise base.R10ContractError("R11 approval text hash drift")
    if prereg.get("pilot_id") != PILOT_ID or prereg.get("status") != "PREREGISTERED_NO_EXECUTION":
        raise base.R10ContractError("R11 preregistration drift")
    if prereg.get("parent_r10d_evidence_merge_commit") != "0b13a80235ecd43bcd220985383f79f8ccbfb6ca":
        raise base.R10ContractError("R11 parent R10D lineage drift")
    if approval.get("reviewed_commit") != PREREGISTRATION_MERGE or approval.get("exact_approval_text_sha256") != APPROVAL_SHA:
        raise base.R10ContractError("R11 approval binding drift")
    if approval.get("status") != "OWNER_APPROVED_IMPLEMENTATION_AND_DEDICATED_ROLE_CREATION_NO_DATA_EXECUTION":
        raise base.R10ContractError("R11 approval status drift")
    if approval.get("execution_authorized_by_this_approval") is not False:
        raise base.R10ContractError("R11 approval self-opens execution")
    if impl.get("status") != "IMPLEMENTED_AWAITING_OPERATOR_ROLE_CREATION_AND_ATTESTATION":
        raise base.R10ContractError("R11 implementation status drift")
    if impl.get("r11_preregistration_merge_commit") != PREREGISTRATION_MERGE:
        raise base.R10ContractError("R11 implementation preregistration binding drift")
    if impl.get("r11_approval_merge_commit") != APPROVAL_MERGE or impl.get("approval_text_sha256") != APPROVAL_SHA:
        raise base.R10ContractError("R11 implementation approval binding drift")
    if impl.get("dedicated_role", {}).get("role_arn") != ROLE_ARN:
        raise base.R10ContractError("R11 role ARN drift")
    if not all(value is False for value in impl.get("current_runtime_authority", {}).values()):
        raise base.R10ContractError("R11 implementation self-opens runtime")
    if not all(value is False for value in impl.get("downstream_authorizations", {}).values()):
        raise base.R10ContractError("R11 implementation opens downstream authority")
    if not all(value is False for value in impl.get("trading_authorizations", {}).values()):
        raise base.R10ContractError("R11 implementation opens trading authority")

    targets = frozen_targets()
    if selection.get("selected_hour_count") != MAX_REQUESTS:
        raise base.R10ContractError("R11 selected hour count drift")
    if selection.get("aggregate_expected_compressed_bytes") != MAX_TOTAL_COMPRESSED_BYTES:
        raise base.R10ContractError("R11 aggregate compressed byte selection drift")
    if sum(row["size"] for row in targets) != MAX_TOTAL_COMPRESSED_BYTES:
        raise base.R10ContractError("R11 target size conservation drift")
    if len({row["key"] for row in targets}) != MAX_REQUESTS:
        raise base.R10ContractError("R11 duplicate target key")

    allow = permission.get("Statement", [])[0]
    resources = allow.get("Resource")
    expected_resources = [f"arn:aws:s3:::hl-mainnet-node-data/{row['key']}" for row in targets]
    if allow.get("Effect") != "Allow" or allow.get("Action") != "s3:GetObject" or resources != expected_resources:
        raise base.R10ContractError("R11 persistent permission policy is not exact selection allowlist")
    if len(resources) != len(set(resources)) != 72:
        raise base.R10ContractError("R11 persistent permission resource cardinality drift")


class DayTrackingStates(defaultdict):
    def __init__(self) -> None:
        super().__init__(base._new_wallet_state)
        self.current_day: str | None = None

    def __getitem__(self, key: str) -> dict:
        state = super().__getitem__(key)
        state.setdefault("active_days", set())
        if self.current_day is not None:
            state["active_days"].add(self.current_day)
        return state


class R11Aggregator(r10d.RecordAnchoredAggregator):
    def __init__(self) -> None:
        self.states = DayTrackingStates()
        self.total_blocks = 0
        self.total_events = 0
        self.total_duplicates = 0

    def add_line(self, raw_line: bytes, target: dict, per_hour: dict) -> None:
        self.states.current_day = target["path_hour_utc"][:10]
        super().add_line(raw_line, target, per_hour)

    def render(self) -> tuple[bytes, dict]:
        if self.total_events < 1 or not self.states:
            raise base.R10FeatureUnresolved("R11 aggregate is empty")
        if self.total_duplicates != 0:
            raise base.R10FeatureUnresolved("duplicate wallet+tid observations require investigation; blind deduplication forbidden")
        output = bytearray()
        sum_fill_count = 0
        sum_side_count = 0
        for address in sorted(self.states):
            state = self.states[address]
            fill_count = state["fill_count"]
            side_count = state["side_a_count"] + state["side_b_count"]
            if fill_count <= 0 or side_count != fill_count:
                raise base.R10FeatureUnresolved("per-wallet fill/side conservation failed")
            first_fill = state["first_fill_time"]
            last_fill = state["last_fill_time"]
            if first_fill is None or last_fill is None or first_fill > last_fill:
                raise base.R10FeatureUnresolved("per-wallet time range invalid")
            active_hours = len(state["active_hours"])
            active_days = len(state.get("active_days", set()))
            if not 1 <= active_hours <= MAX_REQUESTS:
                raise base.R10FeatureUnresolved("active-hour count outside R11 range")
            if not 1 <= active_days <= 3:
                raise base.R10FeatureUnresolved("active-day count outside R11 range")
            row = {
                "wallet_address": address,
                "fill_count": fill_count,
                "active_hour_count": active_hours,
                "active_day_count": active_days,
                "first_fill_time": first_fill,
                "last_fill_time": last_fill,
                "distinct_coin_count": len(state["coins"]),
                "side_a_count": state["side_a_count"],
                "side_b_count": state["side_b_count"],
                "crossed_true_count": state["crossed_true_count"],
                "liquidation_associated_fill_count": state["liquidation_associated_fill_count"],
                "duplicate_tid_count": state["duplicate_tid_count"],
                "sum_abs_px_times_sz_notional_proxy": base.canonical_decimal(state["sum_notional"]),
                "sum_closed_pnl_fill_statistic": base.canonical_decimal(state["sum_closed_pnl"]),
            }
            if list(row) != OUTPUT_FIELDS:
                raise base.R10ContractError("R11 output field order drift")
            encoded = (json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
            if len(output) + len(encoded) > MAX_OUTPUT_BYTES:
                raise base.R10FeatureUnresolved("R11 wallet feature output byte cap exceeded")
            output.extend(encoded)
            sum_fill_count += fill_count
            sum_side_count += side_count
        if sum_fill_count != self.total_events or sum_side_count != self.total_events:
            raise base.R10FeatureUnresolved("R11 global fill/side conservation failed")
        rendered = bytes(output)
        return rendered, {
            "wallet_feature_row_count": len(self.states),
            "sum_fill_count": sum_fill_count,
            "sum_side_count": sum_side_count,
            "duplicate_wallet_tid_count": self.total_duplicates,
            "wallet_feature_sha256": base.sha256_bytes(rendered),
            "wallet_feature_bytes": len(rendered),
            "wallet_feature_fields_only": OUTPUT_FIELDS,
            "wallet_feature_format": "UTF8_NDJSON",
            "wallet_feature_sort_order": "WALLET_ADDRESS_LEXICOGRAPHIC_ASCENDING",
            "decimal_output_encoding": "CANONICAL_BASE10_STRING_NO_EXPONENT",
        }


def aggregate_lz4_object(compressed: bytes, target: dict, aggregate: R11Aggregator) -> dict:
    per_hour = {
        "path_hour_utc": target["path_hour_utc"],
        "object_key": target["key"],
        "expected_etag": target["etag"],
        "expected_content_length": target["size"],
        "observed_content_length": len(compressed),
        "compressed_sha256": base.sha256_bytes(compressed),
        "decompressed_byte_count": 0,
        "block_record_count": 0,
        "event_pair_count": 0,
        "local_path_block_path_record_count": 0,
        "local_path_block_previous_record_count": 0,
        "fill_time_before_path_hour_count": 0,
        "fill_time_inside_path_hour_count": 0,
        "fill_time_after_path_hour_count": 0,
        "before_fills_in_local_path_block_previous_records": 0,
        "record_anchored_alignment_violation_count": 0,
    }
    pending = bytearray()
    try:
        chunks: Iterable[bytes] = base.iter_lz4_frame(compressed, MAX_INDIVIDUAL_DECOMPRESSED_BYTES)
        for chunk in chunks:
            per_hour["decompressed_byte_count"] += len(chunk)
            if per_hour["decompressed_byte_count"] > MAX_INDIVIDUAL_DECOMPRESSED_BYTES:
                raise base.R10TransportIntegrityError("R11 individual decompressed byte cap exceeded")
            pending.extend(chunk)
            while True:
                newline = pending.find(b"\n")
                if newline < 0:
                    break
                line = bytes(pending[:newline])
                del pending[: newline + 1]
                aggregate.add_line(line, target, per_hour)
            if len(pending) > base.MAX_RECORD_BYTES:
                raise base.R10FeatureUnresolved("record byte cap exceeded before newline")
        if pending:
            aggregate.add_line(bytes(pending), target, per_hour)
    except base.LZ4FrameLimit as exc:
        raise base.R10TransportIntegrityError(exc.status) from exc
    except base.LZ4FrameError as exc:
        raise base.R10TransportIntegrityError(str(exc)) from exc
    if per_hour["block_record_count"] < 1 or per_hour["event_pair_count"] < 1:
        raise base.R10FeatureUnresolved("hour has no parsed blocks or events")
    if per_hour["local_path_block_path_record_count"] + per_hour["local_path_block_previous_record_count"] != per_hour["block_record_count"]:
        raise base.R10FeatureUnresolved("block-prefix conservation failed")
    if per_hour["fill_time_before_path_hour_count"] + per_hour["fill_time_inside_path_hour_count"] + per_hour["fill_time_after_path_hour_count"] != per_hour["event_pair_count"]:
        raise base.R10FeatureUnresolved("fill-partition conservation failed")
    if per_hour["fill_time_after_path_hour_count"] != 0 or per_hour["record_anchored_alignment_violation_count"] != 0:
        raise base.R10FeatureUnresolved("R11 record-anchored alignment rule not clean")
    return per_hour


def base_result() -> dict:
    return {
        "schema_version": "1.0",
        "pilot_id": PILOT_ID,
        "record_anchored_rule_id": RULE_ID,
        "numeric_tolerance_authorized": False,
        "terminal_status": None,
        "technical_result": None,
        "research_conclusion": None,
        "observed_at_utc": None,
        "request_attempt_count": 0,
        "s3_http_request_count": 0,
        "successful_request_count": 0,
        "failed_request_count": 0,
        "retries_used": 0,
        "http_redirects_followed": False,
        "completed_hour_count": 0,
        "completed_day_count": 0,
        "per_hour_summaries": [],
        "per_day_summaries": [],
        "total_compressed_bytes": 0,
        "total_decompressed_bytes": 0,
        "aggregate_wallet_feature_summary": None,
        "wallet_feature_retained": False,
        "metadata_timezone_parsing_performed": False,
        "metadata_timezone_inference_performed": False,
        "metadata_datetime_conversion_performed": False,
        "historical_window_beyond_three_days_performed": False,
        "full_population_historical_ingestion_performed": False,
        "legacy_modern_merged_history_performed": False,
        "public_api_enrichment_performed": False,
        "entity_clustering_performed": False,
        "wallet_ranking_performed": False,
        "candidate_shortlisting_performed": False,
        "pnl_or_alpha_analysis_performed": False,
        "copyability_analysis_performed": False,
        "market_data_ingested": False,
        "strategy_inference_performed": False,
        "sum_closed_pnl_interpreted_as_exact_account_return": False,
        "sum_closed_pnl_used_as_wallet_ranking_score": False,
        "notional_proxy_interpreted_as_copyable_notional": False,
        "active_hour_count_interpreted_as_wallet_quality_score": False,
        "active_day_count_interpreted_as_wallet_quality_score": False,
        "local_time_interpreted_as_partition_semantics": False,
        "block_time_interpreted_as_partition_semantics": False,
        "fill_time_interpreted_as_partition_semantics": False,
        "failure_class": None,
        "runtime_seconds": None,
    }


def execute(
    transport: Callable[[str, str, dict[str, str], int, float], tuple[int, dict[str, str], bytes]] = base.https_transport,
    request_time: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    env: dict[str, str] | None = None,
) -> tuple[int, dict, bytes]:
    validate_static_inputs()
    started = time.monotonic()
    result = base_result()
    aggregate = R11Aggregator()
    output = b""
    try:
        for target in frozen_targets():
            if result["request_attempt_count"] >= MAX_REQUESTS:
                raise base.R10TransportIntegrityError("R11 request cap reached")
            if time.monotonic() - started >= MAX_RUNTIME_SECONDS:
                raise base.R10TransportIntegrityError("R11 runtime cap reached before next object")
            host, path, headers = base.build_signed_request(target, request_time(), env)
            if host != base.REGIONAL_ENDPOINT or path != base._aws_quote_path(target["key"]):
                raise base.R10ContractError("signed transport target drift")
            if headers.get("If-Match") != target["etag"] or headers.get("x-amz-request-payer") != "requester":
                raise base.R10ContractError("signed request guard drift")
            result["request_attempt_count"] += 1
            result["s3_http_request_count"] += 1
            remaining = max(1.0, MAX_RUNTIME_SECONDS - (time.monotonic() - started))
            status, response_headers, compressed = transport(host, path, headers, target["size"], remaining)
            if status != 200:
                result["failed_request_count"] += 1
                raise base.R10TransportIntegrityError(f"S3 HTTP status {status}")
            if response_headers.get("x-amz-request-charged", "").lower() != "requester":
                result["failed_request_count"] += 1
                raise base.R10TransportIntegrityError("missing requester-charged response header")
            if response_headers.get("etag") != target["etag"]:
                result["failed_request_count"] += 1
                raise base.R10TransportIntegrityError("response ETag mismatch")
            try:
                content_length = int(response_headers.get("content-length", ""))
            except ValueError as exc:
                result["failed_request_count"] += 1
                raise base.R10TransportIntegrityError("invalid response content-length") from exc
            if content_length != target["size"] or len(compressed) != target["size"]:
                result["failed_request_count"] += 1
                raise base.R10TransportIntegrityError("compressed content length mismatch")
            if len(compressed) > MAX_INDIVIDUAL_COMPRESSED_BYTES:
                raise base.R10TransportIntegrityError("individual compressed byte cap exceeded")
            if result["total_compressed_bytes"] + len(compressed) > MAX_TOTAL_COMPRESSED_BYTES:
                raise base.R10TransportIntegrityError("total compressed byte cap exceeded")
            result["successful_request_count"] += 1
            result["total_compressed_bytes"] += len(compressed)
            per_hour = aggregate_lz4_object(compressed, target, aggregate)
            if result["total_decompressed_bytes"] + per_hour["decompressed_byte_count"] > MAX_TOTAL_DECOMPRESSED_BYTES:
                raise base.R10TransportIntegrityError("total decompressed byte cap exceeded")
            result["total_decompressed_bytes"] += per_hour["decompressed_byte_count"]
            result["per_hour_summaries"].append(per_hour)
            result["completed_hour_count"] += 1
            compressed = b""

        if result["completed_hour_count"] != MAX_REQUESTS:
            raise base.R10TransportIntegrityError("not all 72 exact hours completed")
        days: dict[str, dict[str, int]] = {}
        for hour in result["per_hour_summaries"]:
            day = hour["path_hour_utc"][:10]
            summary = days.setdefault(day, {"hour_count": 0, "block_record_count": 0, "event_pair_count": 0, "fill_time_before_path_hour_count": 0})
            summary["hour_count"] += 1
            summary["block_record_count"] += hour["block_record_count"]
            summary["event_pair_count"] += hour["event_pair_count"]
            summary["fill_time_before_path_hour_count"] += hour["fill_time_before_path_hour_count"]
        result["per_day_summaries"] = [{"utc_date": day, **days[day]} for day in sorted(days)]
        result["completed_day_count"] = len(result["per_day_summaries"])
        if result["completed_day_count"] != 3 or any(row["hour_count"] != 24 for row in result["per_day_summaries"]):
            raise base.R10FeatureUnresolved("R11 complete-day conservation failed")
        output, summary = aggregate.render()
        result["aggregate_wallet_feature_summary"] = summary
        result["wallet_feature_retained"] = True
        result["terminal_status"] = "R11_72H_PERSISTENCE_STUDY_COMPLETE"
        result["technical_result"] = "R11_72H_PERSISTENCE_PIPELINE_COMPLETE"
        result["research_conclusion"] = "R11_72H_PERSISTENCE_PIPELINE_COMPLETE"
        rc = 0
    except base.R10FeatureUnresolved as exc:
        output = b""
        result["wallet_feature_retained"] = False
        result["aggregate_wallet_feature_summary"] = None
        result["terminal_status"] = "R11_72H_PERSISTENCE_STUDY_COMPLETE"
        result["technical_result"] = "R11_72H_PERSISTENCE_PIPELINE_UNRESOLVED"
        result["research_conclusion"] = "R11_72H_PERSISTENCE_PIPELINE_UNRESOLVED"
        result["failure_class"] = str(exc)
        rc = 0
    except (base.R10TransportIntegrityError, base.R10ContractError) as exc:
        output = b""
        result["wallet_feature_retained"] = False
        result["aggregate_wallet_feature_summary"] = None
        result["terminal_status"] = "R11_TRANSPORT_OR_INTEGRITY_FAIL"
        result["technical_result"] = "R11_TRANSPORT_OR_INTEGRITY_FAIL"
        result["research_conclusion"] = "R11_TRANSPORT_OR_INTEGRITY_FAIL"
        result["failure_class"] = str(exc)
        rc = 83
    result["observed_at_utc"] = base.utc_now()
    result["runtime_seconds"] = round(time.monotonic() - started, 6)
    return rc, result, output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-output", required=True)
    parser.add_argument("--wallet-feature-output", required=True)
    args = parser.parse_args(argv)
    rc, result, output = execute()
    Path(args.result_output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    Path(args.wallet_feature_output).write_bytes(output)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
