from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.archive_inventory.r10_implementation import collector as base

BASE = ROOT / "research/archive_inventory"
PREREGISTRATION = BASE / "r10d/R10D_RECORD_ANCHORED_BOUNDARY_REPAIR_PREREGISTRATION.json"
APPROVAL_JSON = BASE / "r10d_approval/APPROVE_HL_ARCHIVE_R10D_RECORD_ANCHORED_MULTI_HOUR_FEATURE_REPAIR_001.json"
APPROVAL_TEXT = BASE / "r10d_approval/APPROVE_HL_ARCHIVE_R10D_RECORD_ANCHORED_MULTI_HOUR_FEATURE_REPAIR_001.txt"
IMPLEMENTATION = BASE / "r10d_implementation/R10D_IMPLEMENTATION_CONTRACT.json"

PILOT_ID = "HL-ARCHIVE-R10D-RECORD-ANCHORED-MULTI-HOUR-FEATURE-REPAIR-001"
PREREGISTRATION_MERGE = "b8e8d1080be27ff9db3fb639804b4040fdc7c2a0"
APPROVAL_MERGE = "95bc1a8c2f929e9266f0ae8c43e7cc2b38b40f11"
APPROVAL_ID = "APPROVE_HL_ARCHIVE_R10D_RECORD_ANCHORED_MULTI_HOUR_FEATURE_REPAIR_001"
APPROVAL_SHA = "d8d1466a5da40c4fe32523ba81bfa165e0b88221cc70534f0f0a118870c1275f"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
HOUR9_SHA = "42fa96f9d693eb93d184c24a830483cea2e4aa526fc2ffb999619d24e41cc339"
RULE_ID = "RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1"

TARGETS = [
    {"path_hour_utc":"2025-07-27T09:00:00Z","key":"node_fills_by_block/hourly/20250727/9.lz4","size":18147822,"etag":'"5a9941a240118a57f77a4c3ee95b8430-3"',"known_sha256":HOUR9_SHA},
    {"path_hour_utc":"2025-07-27T10:00:00Z","key":"node_fills_by_block/hourly/20250727/10.lz4","size":21349239,"etag":'"cb25fba5dc3be80fd8c46dde03144655-3"',"known_sha256":None},
    {"path_hour_utc":"2025-07-27T11:00:00Z","key":"node_fills_by_block/hourly/20250727/11.lz4","size":17582600,"etag":'"758da733bb2d3913d0fdd8088b6fb63d-3"',"known_sha256":None},
    {"path_hour_utc":"2025-07-27T12:00:00Z","key":"node_fills_by_block/hourly/20250727/12.lz4","size":21672141,"etag":'"d6ee46b1bdfad4026e21d4285ed0cbc5-3"',"known_sha256":None},
    {"path_hour_utc":"2025-07-27T13:00:00Z","key":"node_fills_by_block/hourly/20250727/13.lz4","size":20840630,"etag":'"c3c9db0101ff278b5ced13ab278a2b85-3"',"known_sha256":None},
    {"path_hour_utc":"2025-07-27T14:00:00Z","key":"node_fills_by_block/hourly/20250727/14.lz4","size":21407266,"etag":'"3c6ab944be1ed8bd12932eb390267a21-3"',"known_sha256":None},
]


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise base.R10ContractError(f"JSON root must be object: {path}")
    return value


def validate_static_inputs() -> None:
    prereg = load_json(PREREGISTRATION)
    approval = load_json(APPROVAL_JSON)
    impl = load_json(IMPLEMENTATION)
    if hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest() != APPROVAL_SHA:
        raise base.R10ContractError("R10D approval text hash drift")
    if prereg.get("pilot_id") != PILOT_ID or prereg.get("status") != "PREREGISTERED_NO_EXECUTION":
        raise base.R10ContractError("R10D preregistration drift")
    if prereg.get("parent_r10c_evidence_merge_commit") != "83842a3947e8eec518fa4a05ca71a2b81079976b":
        raise base.R10ContractError("R10C lineage drift")
    if prereg.get("parent_r10c_result") != "EXACT_TWO_PRE_HOUR_FILLS_COLOCATE_WITH_SINGLE_PREVIOUS_BLOCK_TIME_RECORD":
        raise base.R10ContractError("R10C empirical parent drift")
    if approval.get("approval_id") != APPROVAL_ID or approval.get("reviewed_commit") != PREREGISTRATION_MERGE:
        raise base.R10ContractError("R10D approval identity drift")
    if approval.get("exact_approval_text_sha256") != APPROVAL_SHA:
        raise base.R10ContractError("R10D approval hash drift")
    if approval.get("status") != "OWNER_APPROVED_IMPLEMENTATION_NO_EXECUTION":
        raise base.R10ContractError("R10D approval status drift")
    if approval.get("execution_authorized_by_this_approval") is not False:
        raise base.R10ContractError("R10D approval self-opens execution")
    if not all(value is False for value in approval.get("current_runtime_authority", {}).values()):
        raise base.R10ContractError("R10D approval self-opens runtime")
    if impl.get("pilot_id") != PILOT_ID or impl.get("status") != "IMPLEMENTED_AWAITING_SEPARATE_EXECUTION_RELEASE":
        raise base.R10ContractError("R10D implementation identity drift")
    if impl.get("r10d_preregistration_merge_commit") != PREREGISTRATION_MERGE:
        raise base.R10ContractError("R10D implementation preregistration binding drift")
    if impl.get("r10d_approval_merge_commit") != APPROVAL_MERGE or impl.get("approval_text_sha256") != APPROVAL_SHA:
        raise base.R10ContractError("R10D implementation approval binding drift")
    if impl.get("role_arn") != ROLE_ARN or impl.get("role_reused_without_mutation") is not True:
        raise base.R10ContractError("R10D role reuse drift")
    if impl.get("new_role_created") is not False:
        raise base.R10ContractError("R10D implementation unexpectedly creates role")
    if not all(value is False for value in impl.get("current_runtime_authority", {}).values()):
        raise base.R10ContractError("R10D implementation self-opens runtime")
    if not all(value is False for value in impl.get("downstream_authorizations", {}).values()):
        raise base.R10ContractError("R10D implementation opens downstream authority")
    if not all(value is False for value in impl.get("trading_authorizations", {}).values()):
        raise base.R10ContractError("R10D implementation opens trading authority")

    p_targets = prereg.get("exact_future_network_targets")
    i_targets = impl.get("exact_network_targets")
    if not isinstance(p_targets, list) or not isinstance(i_targets, list) or len(p_targets) != 6 or len(i_targets) != 6:
        raise base.R10ContractError("R10D target cardinality drift")
    for index, frozen in enumerate(TARGETS):
        p = p_targets[index]
        i = i_targets[index]
        if p.get("path_hour_utc") != frozen["path_hour_utc"] or p.get("key") != frozen["key"]:
            raise base.R10ContractError("R10D preregistered target drift")
        if p.get("expected_size_bytes") != frozen["size"] or p.get("expected_etag") != frozen["etag"]:
            raise base.R10ContractError("R10D preregistered object identity drift")
        if p.get("known_compressed_sha256") != frozen["known_sha256"]:
            raise base.R10ContractError("R10D preregistered known SHA drift")
        if i != {
            "path_hour_utc": frozen["path_hour_utc"],
            "key": frozen["key"],
            "expected_size_bytes": frozen["size"],
            "expected_etag": frozen["etag"],
            "known_compressed_sha256": frozen["known_sha256"],
        }:
            raise base.R10ContractError("R10D implementation target drift")

    env = impl.get("execution_envelope", {})
    p_env = prereg.get("proposed_request_envelope", {})
    for key in (
        "maximum_one_time_budget_eur", "maximum_monthly_budget_eur", "maximum_get_object_requests",
        "maximum_requests_per_object", "maximum_retries_per_request", "maximum_total_compressed_bytes",
        "maximum_individual_compressed_bytes", "maximum_total_decompressed_bytes",
        "maximum_individual_decompressed_bytes", "maximum_runtime_seconds", "request_order",
        "stop_after_first_failed_or_mismatched_object", "requester_pays_required", "if_match_etag_required",
        "exact_content_length_required", "exact_response_etag_required",
        "compressed_sha256_computed_and_retained_per_object", "hour9_preknown_compressed_sha256_required",
        "preknown_compressed_sha256_required_for_all_six_objects", "head_object_authorized", "range_get_authorized",
        "list_objects_v2_authorized", "list_object_versions_authorized", "list_all_my_buckets_authorized",
        "get_object_attributes_authorized", "get_object_version_authorized", "http_redirect_following_authorized",
    ):
        if env.get(key) != p_env.get(key):
            raise base.R10ContractError(f"R10D execution envelope drift: {key}")

    rule = impl.get("record_anchored_alignment_rule", {})
    p_rule = prereg.get("record_anchored_alignment_rule", {})
    if rule != p_rule:
        raise base.R10ContractError("R10D record-anchored rule drift")
    if rule.get("rule_id") != RULE_ID or rule.get("numeric_tolerance_authorized") is not False:
        raise base.R10ContractError("R10D numeric tolerance boundary drift")
    if rule.get("fill_time_numeric_tolerance_milliseconds") is not None:
        raise base.R10ContractError("R10D numeric tolerance unexpectedly present")


class RecordAnchoredAggregator(base.MultiHourAggregator):
    def add_line(self, raw_line: bytes, target: dict, per_hour: dict) -> None:
        if raw_line.endswith(b"\r"):
            raw_line = raw_line[:-1]
        if not raw_line.strip():
            return
        if len(raw_line) > base.MAX_RECORD_BYTES:
            raise base.R10FeatureUnresolved("block record byte cap exceeded")
        try:
            block = base.strict_loads(raw_line.decode("utf-8", errors="strict"))
        except (UnicodeDecodeError, base.R10JSONError) as exc:
            raise base.R10FeatureUnresolved("strict modern block parse failed") from exc
        if not isinstance(block, dict):
            raise base.R10FeatureUnresolved("top-level record is not object")
        for key, expected_type in {"local_time": str, "block_time": str, "block_number": int, "events": list}.items():
            field = block.get(key)
            if expected_type is int:
                if isinstance(field, bool) or not isinstance(field, int):
                    raise base.R10FeatureUnresolved(f"block field type mismatch: {key}")
            elif not isinstance(field, expected_type):
                raise base.R10FeatureUnresolved(f"block field type mismatch: {key}")

        self.total_blocks += 1
        per_hour["block_record_count"] += 1
        if self.total_blocks > base.MAX_BLOCKS:
            raise base.R10FeatureUnresolved("global block cap exceeded")

        start = base.parse_utc(target["path_hour_utc"])
        start_ms = int(start.timestamp() * 1000)
        end_ms = int((start + timedelta(hours=1)).timestamp() * 1000)
        previous_start_ms = int((start - timedelta(hours=1)).timestamp() * 1000)
        path_prefix = start.strftime("%Y-%m-%dT%H:")
        previous_prefix = (start - timedelta(hours=1)).strftime("%Y-%m-%dT%H:")

        local_time = block["local_time"]
        block_time = block["block_time"]
        if not local_time.startswith(path_prefix):
            per_hour["record_anchored_alignment_violation_count"] += 1
            raise base.R10FeatureUnresolved("local_time raw prefix differs from source path hour")
        if block_time.startswith(path_prefix):
            block_bucket = "MATCHES_PATH_DATE_HOUR_PREFIX"
            per_hour["local_path_block_path_record_count"] += 1
        elif block_time.startswith(previous_prefix):
            block_bucket = "MATCHES_PREVIOUS_DATE_HOUR_PREFIX"
            per_hour["local_path_block_previous_record_count"] += 1
        else:
            per_hour["record_anchored_alignment_violation_count"] += 1
            raise base.R10FeatureUnresolved("block_time raw prefix is neither path hour nor immediately previous hour")

        for pair in block["events"]:
            self.total_events += 1
            per_hour["event_pair_count"] += 1
            if self.total_events > base.MAX_EVENTS:
                raise base.R10FeatureUnresolved("global event-pair cap exceeded")
            if not (isinstance(pair, list) and len(pair) == 2 and isinstance(pair[0], str) and isinstance(pair[1], dict)):
                raise base.R10FeatureUnresolved("event differs from [string, object] contract")
            address, fill = pair
            if base.ADDRESS_RE.fullmatch(address) is None:
                raise base.R10FeatureUnresolved("leading string violates lowercase address contract")
            for required_field in ("coin", "side", "time", "px", "sz", "closedPnl", "tid", "crossed"):
                if required_field not in fill:
                    raise base.R10FeatureUnresolved(f"required selected field absent: {required_field}")
            coin = fill["coin"]
            side = fill["side"]
            fill_time = fill["time"]
            crossed = fill["crossed"]
            if not isinstance(coin, str) or not coin:
                raise base.R10FeatureUnresolved("coin must be nonempty string")
            if side not in {"A", "B"}:
                raise base.R10FeatureUnresolved("side must be A or B")
            if isinstance(fill_time, bool) or not isinstance(fill_time, int) or fill_time < 0:
                raise base.R10FeatureUnresolved("fill time must be nonnegative integer")
            if fill_time < start_ms:
                partition = "BEFORE_PATH_HOUR"
                per_hour["fill_time_before_path_hour_count"] += 1
            elif fill_time < end_ms:
                partition = "INSIDE_PATH_HOUR"
                per_hour["fill_time_inside_path_hour_count"] += 1
            else:
                partition = "AFTER_PATH_HOUR"
                per_hour["fill_time_after_path_hour_count"] += 1

            if block_bucket == "MATCHES_PATH_DATE_HOUR_PREFIX":
                if partition != "INSIDE_PATH_HOUR":
                    per_hour["record_anchored_alignment_violation_count"] += 1
                    raise base.R10FeatureUnresolved("path-hour block record contains non-inside fill")
            else:
                if partition != "BEFORE_PATH_HOUR":
                    per_hour["record_anchored_alignment_violation_count"] += 1
                    raise base.R10FeatureUnresolved("previous-hour block record contains non-before fill")
                if fill_time < previous_start_ms:
                    per_hour["record_anchored_alignment_violation_count"] += 1
                    raise base.R10FeatureUnresolved("previous-hour block record contains fill older than immediately previous epoch hour")
                per_hour["before_fills_in_local_path_block_previous_records"] += 1

            if partition == "AFTER_PATH_HOUR":
                per_hour["record_anchored_alignment_violation_count"] += 1
                raise base.R10FeatureUnresolved("after-path-hour fill is forbidden")
            if not isinstance(crossed, bool):
                raise base.R10FeatureUnresolved("crossed must be boolean")
            px = base._decimal(fill["px"], "px")
            sz = base._decimal(fill["sz"], "sz")
            closed_pnl = base._decimal(fill["closedPnl"], "closedPnl")
            tid = base._tid_key(fill["tid"])

            state = self.states[address]
            state["fill_count"] += 1
            state["active_hours"].add(target["path_hour_utc"])
            if state["first_fill_time"] is None or fill_time < state["first_fill_time"]:
                state["first_fill_time"] = fill_time
            if state["last_fill_time"] is None or fill_time > state["last_fill_time"]:
                state["last_fill_time"] = fill_time
            state["coins"].add(coin)
            if side == "A":
                state["side_a_count"] += 1
            else:
                state["side_b_count"] += 1
            if crossed:
                state["crossed_true_count"] += 1
            if fill.get("liquidation") is not None:
                state["liquidation_associated_fill_count"] += 1
            if tid in state["tids"]:
                state["duplicate_tid_count"] += 1
                self.total_duplicates += 1
            else:
                state["tids"].add(tid)
            state["sum_notional"] += abs(px * sz)
            state["sum_closed_pnl"] += closed_pnl
            if len(self.states) > base.MAX_ROWS:
                raise base.R10FeatureUnresolved("wallet row cap exceeded")


def aggregate_lz4_object(compressed: bytes, target: dict, aggregate: RecordAnchoredAggregator) -> dict:
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
        chunks: Iterable[bytes] = base.iter_lz4_frame(compressed, base.MAX_INDIVIDUAL_DECOMPRESSED_BYTES)
        for chunk in chunks:
            per_hour["decompressed_byte_count"] += len(chunk)
            if per_hour["decompressed_byte_count"] > base.MAX_INDIVIDUAL_DECOMPRESSED_BYTES:
                raise base.R10TransportIntegrityError("individual decompressed byte cap exceeded")
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
        raise base.R10FeatureUnresolved("block-prefix aggregate conservation failed")
    if (
        per_hour["fill_time_before_path_hour_count"]
        + per_hour["fill_time_inside_path_hour_count"]
        + per_hour["fill_time_after_path_hour_count"]
        != per_hour["event_pair_count"]
    ):
        raise base.R10FeatureUnresolved("fill-partition aggregate conservation failed")
    if per_hour["fill_time_after_path_hour_count"] != 0 or per_hour["record_anchored_alignment_violation_count"] != 0:
        raise base.R10FeatureUnresolved("record-anchored alignment rule not clean")

    if target["path_hour_utc"] == "2025-07-27T09:00:00Z":
        fixture = {
            "block_record_count": 36029,
            "event_pair_count": 223950,
            "fill_time_before_path_hour_count": 2,
            "fill_time_inside_path_hour_count": 223948,
            "fill_time_after_path_hour_count": 0,
            "local_path_block_path_record_count": 36028,
            "local_path_block_previous_record_count": 1,
            "before_fills_in_local_path_block_previous_records": 2,
        }
        for key, expected in fixture.items():
            if per_hour[key] != expected:
                raise base.R10FeatureUnresolved(f"hour9 R10C fixture mismatch: {key}")
    return per_hour


def _base_result() -> dict:
    return {
        "schema_version": "1.0",
        "pilot_id": PILOT_ID,
        "record_anchored_rule_id": RULE_ID,
        "numeric_tolerance_authorized": False,
        "observed_at_utc": None,
        "terminal_status": None,
        "technical_result": None,
        "research_conclusion": None,
        "request_attempt_count": 0,
        "s3_http_request_count": 0,
        "successful_request_count": 0,
        "failed_request_count": 0,
        "retries_used": 0,
        "http_redirects_followed": False,
        "requester_pays_requested": True,
        "completed_hour_count": 0,
        "per_hour_summaries": [],
        "total_compressed_bytes": 0,
        "total_decompressed_bytes": 0,
        "aggregate_wallet_feature_summary": None,
        "wallet_feature_retained": False,
        "metadata_timezone_parsing_performed": False,
        "metadata_timezone_inference_performed": False,
        "metadata_datetime_conversion_performed": False,
        "raw_compressed_objects_retained": False,
        "raw_decompressed_payloads_retained": False,
        "raw_block_records_retained": False,
        "raw_event_pairs_retained": False,
        "raw_fill_objects_retained": False,
        "individual_selected_values_retained": False,
        "historical_window_beyond_six_hours_performed": False,
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
        "local_time_interpreted_as_partition_semantics": False,
        "block_time_interpreted_as_partition_semantics": False,
        "fill_time_interpreted_as_partition_semantics": False,
        "failure_class": None,
        "runtime_seconds": None
    }


def execute(
    transport: Callable[[str, str, dict[str, str], int, float], tuple[int, dict[str, str], bytes]] = base.https_transport,
    request_time: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    env: dict[str, str] | None = None,
) -> tuple[int, dict, bytes]:
    validate_static_inputs()
    started = time.monotonic()
    result = _base_result()
    aggregate = RecordAnchoredAggregator()
    output = b""
    try:
        for target in TARGETS:
            if result["request_attempt_count"] >= base.MAX_REQUESTS:
                raise base.R10TransportIntegrityError("request cap reached")
            if time.monotonic() - started >= base.MAX_RUNTIME_SECONDS:
                raise base.R10TransportIntegrityError("runtime cap reached before next object")
            transport_target = {"path_hour_utc": target["path_hour_utc"], "key": target["key"], "size": target["size"], "etag": target["etag"]}
            host, path, headers = base.build_signed_request(transport_target, request_time(), env)
            if host != base.REGIONAL_ENDPOINT or path != base._aws_quote_path(target["key"]):
                raise base.R10ContractError("signed transport target drift")
            if headers.get("If-Match") != target["etag"] or headers.get("x-amz-request-payer") != "requester":
                raise base.R10ContractError("signed request guard drift")
            result["request_attempt_count"] += 1
            result["s3_http_request_count"] += 1
            remaining = max(1.0, base.MAX_RUNTIME_SECONDS - (time.monotonic() - started))
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
            if len(compressed) > base.MAX_INDIVIDUAL_COMPRESSED_BYTES:
                raise base.R10TransportIntegrityError("individual compressed byte cap exceeded")
            if result["total_compressed_bytes"] + len(compressed) > base.MAX_TOTAL_COMPRESSED_BYTES:
                raise base.R10TransportIntegrityError("total compressed byte cap exceeded")
            compressed_sha = base.sha256_bytes(compressed)
            if target["known_sha256"] is not None and compressed_sha != target["known_sha256"]:
                result["failed_request_count"] += 1
                raise base.R10TransportIntegrityError("preknown compressed SHA-256 mismatch")
            result["successful_request_count"] += 1
            result["total_compressed_bytes"] += len(compressed)
            per_hour = aggregate_lz4_object(compressed, target, aggregate)
            if per_hour["compressed_sha256"] != compressed_sha:
                raise base.R10ContractError("compressed SHA accounting drift")
            if result["total_decompressed_bytes"] + per_hour["decompressed_byte_count"] > base.MAX_TOTAL_DECOMPRESSED_BYTES:
                raise base.R10TransportIntegrityError("total decompressed byte cap exceeded")
            result["total_decompressed_bytes"] += per_hour["decompressed_byte_count"]
            result["per_hour_summaries"].append(per_hour)
            result["completed_hour_count"] += 1
            compressed = b""

        if result["completed_hour_count"] != base.MAX_REQUESTS:
            raise base.R10TransportIntegrityError("not all six exact hours completed")
        output, summary = aggregate.render()
        result["aggregate_wallet_feature_summary"] = summary
        result["wallet_feature_retained"] = True
        result["terminal_status"] = "R10D_MULTI_HOUR_FEATURE_REPAIR_STUDY_COMPLETE"
        result["technical_result"] = "R10D_MULTI_HOUR_FEATURE_PIPELINE_COMPLETE"
        result["research_conclusion"] = "R10D_MULTI_HOUR_FEATURE_PIPELINE_COMPLETE"
        rc = 0
    except base.R10FeatureUnresolved as exc:
        output = b""
        result["wallet_feature_retained"] = False
        result["aggregate_wallet_feature_summary"] = None
        result["terminal_status"] = "R10D_MULTI_HOUR_FEATURE_REPAIR_STUDY_COMPLETE"
        result["technical_result"] = "R10D_MULTI_HOUR_FEATURE_PIPELINE_UNRESOLVED"
        result["research_conclusion"] = "R10D_MULTI_HOUR_FEATURE_PIPELINE_UNRESOLVED"
        result["failure_class"] = str(exc)
        rc = 0
    except (base.R10TransportIntegrityError, base.R10ContractError) as exc:
        output = b""
        result["wallet_feature_retained"] = False
        result["aggregate_wallet_feature_summary"] = None
        result["terminal_status"] = "R10D_TRANSPORT_OR_INTEGRITY_FAIL"
        result["technical_result"] = "R10D_TRANSPORT_OR_INTEGRITY_FAIL"
        result["research_conclusion"] = "R10D_TRANSPORT_OR_INTEGRITY_FAIL"
        result["failure_class"] = str(exc)
        rc = 84
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
