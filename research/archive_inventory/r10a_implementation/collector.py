from __future__ import annotations

import argparse
import hashlib
import hmac
import http.client
import json
import os
import re
import ssl
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[3]
from research.archive_inventory.r4.lz4_frame import LZ4FrameError, LZ4FrameLimit, iter_lz4_frame

PREREG = ROOT / "research/archive_inventory/r10a/R10A_TIMESTAMP_PARTITION_PREREGISTRATION.json"
APPROVAL_JSON = ROOT / "research/archive_inventory/r10a_approval/APPROVE_HL_ARCHIVE_R10A_TIMESTAMP_PARTITION_DIAGNOSTIC_001.json"
APPROVAL_TEXT = ROOT / "research/archive_inventory/r10a_approval/APPROVE_HL_ARCHIVE_R10A_TIMESTAMP_PARTITION_DIAGNOSTIC_001.txt"
IMPLEMENTATION = ROOT / "research/archive_inventory/r10a_implementation/R10A_IMPLEMENTATION_CONTRACT.json"

DIAGNOSTIC_ID = "HL-ARCHIVE-R10A-TIMESTAMP-PARTITION-DIAGNOSTIC-001"
PREREG_MERGE = "7db55db0be5efeeadb569abb5faaadf3bc78254a"
APPROVAL_MERGE = "b67e4a0ca91a411230f3c1b8cebac047d6c69261"
APPROVAL_SHA = "c990a1636b745908d9f58c4b119998dfa91b4e8740764081bbb19cb8ad8904f1"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
TARGET = {
    "bucket": "hl-mainnet-node-data",
    "region": "ap-northeast-1",
    "key": "node_fills_by_block/hourly/20250727/9.lz4",
    "path_hour_utc": "2025-07-27T09:00:00Z",
    "size": 18_147_822,
    "etag": '"5a9941a240118a57f77a4c3ee95b8430-3"',
}
REGIONAL_ENDPOINT = f"{TARGET['bucket']}.s3.{TARGET['region']}.amazonaws.com"
EMPTY_PAYLOAD_SHA256 = hashlib.sha256(b"").hexdigest()
MAX_COMPRESSED = 18_147_822
MAX_DECOMPRESSED = 268_435_456
MAX_RUNTIME_SECONDS = 120
MAX_RECORD_BYTES = 16_777_216
MAX_BLOCKS = 500_000
MAX_EVENTS = 2_000_000
ADDRESS_RE = re.compile(r"^0x[0-9a-f]{40}$")
EXPLICIT_ZONE_RE = re.compile(r"(?:Z|[+-]\d{2}:\d{2})$")


class ContractError(RuntimeError):
    pass


class TransportIntegrityError(RuntimeError):
    pass


class DiagnosticUnresolved(RuntimeError):
    pass


class StrictJSONError(ValueError):
    pass


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ContractError(f"JSON root must be object: {path}")
    return value


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _strict_object(pairs: list[tuple[str, object]]) -> dict:
    out: dict = {}
    for key, value in pairs:
        if key in out:
            raise StrictJSONError("duplicate JSON object key")
        out[key] = value
    return out


def _reject_nonfinite(_token: str) -> object:
    raise StrictJSONError("non-finite JSON constant")


def strict_loads(text: str) -> object:
    try:
        return json.loads(text, object_pairs_hook=_strict_object, parse_constant=_reject_nonfinite)
    except json.JSONDecodeError as exc:
        raise StrictJSONError(str(exc)) from exc


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ms_to_utc(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def explicit_zoned_ms(value: str) -> int | None:
    if not isinstance(value, str) or EXPLICIT_ZONE_RE.search(value) is None:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return int(dt.astimezone(timezone.utc).timestamp() * 1000)


def empty_offset_hist() -> dict[str, int]:
    out = {"UNDERFLOW_LT_NEG24": 0}
    for hour in range(-24, 25):
        out[str(hour)] = 0
    out["OVERFLOW_GT_24"] = 0
    return out


def add_offset(hist: dict[str, int], value_ms: int, start_ms: int) -> None:
    hour = (value_ms - start_ms) // 3_600_000
    if hour < -24:
        hist["UNDERFLOW_LT_NEG24"] += 1
    elif hour > 24:
        hist["OVERFLOW_GT_24"] += 1
    else:
        hist[str(hour)] += 1


def add_partition(summary: dict, prefix: str, value_ms: int, start_ms: int, end_ms: int) -> None:
    if value_ms < start_ms:
        summary[f"{prefix}_before_path_hour_count"] += 1
    elif value_ms >= end_ms:
        summary[f"{prefix}_after_path_hour_count"] += 1
    else:
        summary[f"{prefix}_inside_path_hour_count"] += 1
    add_offset(summary[f"{prefix}_path_hour_offset_histogram"], value_ms, start_ms)


def add_delta(summary: dict, delta_ms: int | None) -> None:
    hist = summary["fill_minus_block_time_delta_histogram"]
    if delta_ms is None:
        hist["UNAVAILABLE"] += 1
        return
    current_min = summary["fill_minus_block_time_delta_min_ms"]
    current_max = summary["fill_minus_block_time_delta_max_ms"]
    summary["fill_minus_block_time_delta_min_ms"] = delta_ms if current_min is None else min(current_min, delta_ms)
    summary["fill_minus_block_time_delta_max_ms"] = delta_ms if current_max is None else max(current_max, delta_ms)
    if delta_ms < -60_000:
        hist["LT_NEG_60000"] += 1
    elif delta_ms < 0:
        hist["NEG_60000_TO_NEG_1"] += 1
    elif delta_ms == 0:
        hist["ZERO"] += 1
    elif delta_ms <= 60_000:
        hist["POS_1_TO_60000"] += 1
    else:
        hist["GT_60000"] += 1


def validate_static_inputs() -> None:
    prereg = load_json(PREREG)
    approval = load_json(APPROVAL_JSON)
    impl = load_json(IMPLEMENTATION)
    if sha256_bytes(APPROVAL_TEXT.read_bytes()) != APPROVAL_SHA:
        raise ContractError("approval text hash drift")
    if prereg.get("diagnostic_id") != DIAGNOSTIC_ID or prereg.get("status") != "PREREGISTERED_NO_EXECUTION":
        raise ContractError("preregistration drift")
    if approval.get("diagnostic_id") != DIAGNOSTIC_ID or approval.get("reviewed_commit") != PREREG_MERGE:
        raise ContractError("approval identity drift")
    if approval.get("exact_approval_text_sha256") != APPROVAL_SHA:
        raise ContractError("approval hash drift")
    if approval.get("execution_authorized_by_this_approval") is not False:
        raise ContractError("approval self-opens execution")
    if impl.get("diagnostic_id") != DIAGNOSTIC_ID or impl.get("status") != "IMPLEMENTED_AWAITING_SEPARATE_EXECUTION_RELEASE":
        raise ContractError("implementation identity drift")
    if impl.get("r10a_preregistration_merge_commit") != PREREG_MERGE or impl.get("r10a_approval_merge_commit") != APPROVAL_MERGE:
        raise ContractError("implementation lineage drift")
    if impl.get("approval_text_sha256") != APPROVAL_SHA or impl.get("role_arn") != ROLE_ARN:
        raise ContractError("implementation approval/role drift")
    if impl.get("role_reused_without_mutation") is not True or impl.get("new_role_created") is not False:
        raise ContractError("role boundary drift")
    target = prereg.get("exact_future_network_target", {})
    expected = {
        "bucket": TARGET["bucket"], "region": TARGET["region"], "key": TARGET["key"],
        "path_hour_utc": TARGET["path_hour_utc"], "expected_size_bytes": TARGET["size"],
        "expected_etag": TARGET["etag"], "storage_class": "STANDARD",
    }
    if target != expected:
        raise ContractError("target drift")
    if impl.get("exact_network_target", {}).get("key") != TARGET["key"]:
        raise ContractError("implementation target drift")
    if impl.get("execution_release_present") is not False or impl.get("single_workflow_dispatch_authorized") is not False:
        raise ContractError("implementation self-opens runtime")
    if impl.get("aws_oidc_authorized_now") is not False or impl.get("get_object_authorized_now") is not False:
        raise ContractError("implementation self-opens AWS")
    if impl.get("network_requests_executed") != 0 or impl.get("aws_iam_mutations_executed") != 0:
        raise ContractError("implementation contains runtime evidence")
    if not all(v is False for v in impl.get("downstream_authorizations", {}).values()):
        raise ContractError("downstream authority opened")
    if not all(v is False for v in impl.get("trading_authorizations", {}).values()):
        raise ContractError("trading authority opened")


def _aws_quote_path(key: str) -> str:
    return "/" + urllib.parse.quote(key, safe="/-_.~")


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def build_signed_request(request_time: datetime, env: dict[str, str] | None = None) -> tuple[str, str, dict[str, str]]:
    source = os.environ if env is None else env
    access_key = source.get("AWS_ACCESS_KEY_ID")
    secret_key = source.get("AWS_SECRET_ACCESS_KEY")
    session_token = source.get("AWS_SESSION_TOKEN")
    if not access_key or not secret_key or not session_token:
        raise ContractError("temporary AWS credentials missing")
    if request_time.tzinfo is None:
        raise ContractError("signing time must be timezone-aware")
    stamp = request_time.astimezone(timezone.utc)
    amz_date = stamp.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = stamp.strftime("%Y%m%d")
    canonical_uri = _aws_quote_path(TARGET["key"])
    canonical_headers = (
        f"host:{REGIONAL_ENDPOINT}\n"
        f"if-match:{TARGET['etag']}\n"
        f"x-amz-content-sha256:{EMPTY_PAYLOAD_SHA256}\n"
        f"x-amz-date:{amz_date}\n"
        "x-amz-request-payer:requester\n"
        f"x-amz-security-token:{session_token}\n"
    )
    signed_headers = "host;if-match;x-amz-content-sha256;x-amz-date;x-amz-request-payer;x-amz-security-token"
    canonical_request = "\n".join(["GET", canonical_uri, "", canonical_headers, signed_headers, EMPTY_PAYLOAD_SHA256])
    scope = f"{date_stamp}/{TARGET['region']}/s3/aws4_request"
    string_to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical_request.encode()).hexdigest()])
    k_date = _sign(("AWS4" + secret_key).encode(), date_stamp)
    k_region = _sign(k_date, TARGET["region"])
    k_service = _sign(k_region, "s3")
    k_signing = _sign(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()
    authorization = f"AWS4-HMAC-SHA256 Credential={access_key}/{scope},SignedHeaders={signed_headers},Signature={signature}"
    return REGIONAL_ENDPOINT, canonical_uri, {
        "Host": REGIONAL_ENDPOINT,
        "If-Match": TARGET["etag"],
        "Authorization": authorization,
        "x-amz-content-sha256": EMPTY_PAYLOAD_SHA256,
        "x-amz-date": amz_date,
        "x-amz-request-payer": "requester",
        "x-amz-security-token": session_token,
    }


def https_transport(host: str, path: str, headers: dict[str, str], expected_size: int, timeout_seconds: float) -> tuple[int, dict[str, str], bytes]:
    connection = http.client.HTTPSConnection(host, timeout=timeout_seconds, context=ssl.create_default_context())
    try:
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        response_headers = {name.lower(): value.strip() for name, value in response.getheaders()}
        if response.status != 200:
            return response.status, response_headers, b""
        return response.status, response_headers, response.read(expected_size + 1)
    finally:
        connection.close()


def new_summary(observed_etag: str, compressed: bytes) -> dict:
    return {
        "object_key": TARGET["key"],
        "expected_etag": TARGET["etag"],
        "observed_etag": observed_etag,
        "compressed_bytes": len(compressed),
        "compressed_sha256": sha256_bytes(compressed),
        "decompressed_bytes": 0,
        "block_record_count": 0,
        "event_pair_count": 0,
        "fill_time_count": 0,
        "fill_time_min_ms": None,
        "fill_time_max_ms": None,
        "fill_time_min_utc": None,
        "fill_time_max_utc": None,
        "fill_time_before_path_hour_count": 0,
        "fill_time_inside_path_hour_count": 0,
        "fill_time_after_path_hour_count": 0,
        "fill_time_path_hour_offset_histogram": empty_offset_hist(),
        "block_time_parseable_count": 0,
        "block_time_unparseable_count": 0,
        "block_time_min_utc": None,
        "block_time_max_utc": None,
        "block_time_before_path_hour_count": 0,
        "block_time_inside_path_hour_count": 0,
        "block_time_after_path_hour_count": 0,
        "block_time_path_hour_offset_histogram": empty_offset_hist(),
        "local_time_parseable_with_explicit_timezone_count": 0,
        "local_time_not_explicitly_zoned_count": 0,
        "local_time_min_utc_when_explicitly_zoned": None,
        "local_time_max_utc_when_explicitly_zoned": None,
        "fill_minus_block_time_delta_min_ms": None,
        "fill_minus_block_time_delta_max_ms": None,
        "fill_minus_block_time_delta_histogram": {
            "LT_NEG_60000": 0, "NEG_60000_TO_NEG_1": 0, "ZERO": 0,
            "POS_1_TO_60000": 0, "GT_60000": 0, "UNAVAILABLE": 0,
        },
        "alignment_classification": None,
    }


class TimestampAggregator:
    def __init__(self, summary: dict) -> None:
        self.summary = summary
        self.start_ms = int(datetime.fromisoformat(TARGET["path_hour_utc"].replace("Z", "+00:00")).timestamp() * 1000)
        self.end_ms = self.start_ms + 3_600_000
        self._block_min_ms: int | None = None
        self._block_max_ms: int | None = None
        self._local_min_ms: int | None = None
        self._local_max_ms: int | None = None

    def add_line(self, raw_line: bytes) -> None:
        if raw_line.endswith(b"\r"):
            raw_line = raw_line[:-1]
        if not raw_line.strip():
            return
        if len(raw_line) > MAX_RECORD_BYTES:
            raise DiagnosticUnresolved("block record byte cap exceeded")
        try:
            block = strict_loads(raw_line.decode("utf-8", errors="strict"))
        except (UnicodeDecodeError, StrictJSONError) as exc:
            raise DiagnosticUnresolved("strict block parse failed") from exc
        if not isinstance(block, dict):
            raise DiagnosticUnresolved("top-level record is not object")
        for key, expected in (("local_time", str), ("block_time", str), ("block_number", int), ("events", list)):
            value = block.get(key)
            if expected is int:
                if isinstance(value, bool) or not isinstance(value, int):
                    raise DiagnosticUnresolved(f"block field type mismatch: {key}")
            elif not isinstance(value, expected):
                raise DiagnosticUnresolved(f"block field type mismatch: {key}")
        self.summary["block_record_count"] += 1
        if self.summary["block_record_count"] > MAX_BLOCKS:
            raise DiagnosticUnresolved("block record cap exceeded")

        block_ms = explicit_zoned_ms(block["block_time"])
        if block_ms is None:
            self.summary["block_time_unparseable_count"] += 1
        else:
            self.summary["block_time_parseable_count"] += 1
            self._block_min_ms = block_ms if self._block_min_ms is None else min(self._block_min_ms, block_ms)
            self._block_max_ms = block_ms if self._block_max_ms is None else max(self._block_max_ms, block_ms)
            add_partition(self.summary, "block_time", block_ms, self.start_ms, self.end_ms)

        local_ms = explicit_zoned_ms(block["local_time"])
        if local_ms is None:
            self.summary["local_time_not_explicitly_zoned_count"] += 1
        else:
            self.summary["local_time_parseable_with_explicit_timezone_count"] += 1
            self._local_min_ms = local_ms if self._local_min_ms is None else min(self._local_min_ms, local_ms)
            self._local_max_ms = local_ms if self._local_max_ms is None else max(self._local_max_ms, local_ms)

        for pair in block["events"]:
            self.summary["event_pair_count"] += 1
            if self.summary["event_pair_count"] > MAX_EVENTS:
                raise DiagnosticUnresolved("event pair cap exceeded")
            if not (isinstance(pair, list) and len(pair) == 2 and isinstance(pair[0], str) and isinstance(pair[1], dict)):
                raise DiagnosticUnresolved("event differs from [string, object] contract")
            if ADDRESS_RE.fullmatch(pair[0]) is None:
                raise DiagnosticUnresolved("leading string violates address shape")
            fill = pair[1]
            fill_time = fill.get("time")
            if isinstance(fill_time, bool) or not isinstance(fill_time, int) or fill_time < 0:
                raise DiagnosticUnresolved("fill time must be nonnegative integer milliseconds")
            self.summary["fill_time_count"] += 1
            current_min = self.summary["fill_time_min_ms"]
            current_max = self.summary["fill_time_max_ms"]
            self.summary["fill_time_min_ms"] = fill_time if current_min is None else min(current_min, fill_time)
            self.summary["fill_time_max_ms"] = fill_time if current_max is None else max(current_max, fill_time)
            add_partition(self.summary, "fill_time", fill_time, self.start_ms, self.end_ms)
            add_delta(self.summary, None if block_ms is None else fill_time - block_ms)

    def finalize(self) -> dict:
        s = self.summary
        if s["block_record_count"] < 1 or s["event_pair_count"] < 1 or s["fill_time_count"] < 1:
            raise DiagnosticUnresolved("diagnostic has no parsed blocks/events/fill times")
        if s["fill_time_min_ms"] is not None:
            s["fill_time_min_utc"] = ms_to_utc(s["fill_time_min_ms"])
            s["fill_time_max_utc"] = ms_to_utc(s["fill_time_max_ms"])
        if self._block_min_ms is not None:
            s["block_time_min_utc"] = ms_to_utc(self._block_min_ms)
            s["block_time_max_utc"] = ms_to_utc(self._block_max_ms)
        if self._local_min_ms is not None:
            s["local_time_min_utc_when_explicitly_zoned"] = ms_to_utc(self._local_min_ms)
            s["local_time_max_utc_when_explicitly_zoned"] = ms_to_utc(self._local_max_ms)
        partition_total = s["fill_time_before_path_hour_count"] + s["fill_time_inside_path_hour_count"] + s["fill_time_after_path_hour_count"]
        if partition_total != s["fill_time_count"]:
            raise DiagnosticUnresolved("fill partition conservation failed")
        if s["fill_time_before_path_hour_count"] == 0 and s["fill_time_after_path_hour_count"] == 0 and s["fill_time_inside_path_hour_count"] == s["fill_time_count"]:
            s["alignment_classification"] = "FILL_TIME_STRICT_PATH_HOUR_ALIGNED"
        else:
            s["alignment_classification"] = "FILL_TIME_SPILLS_OUTSIDE_PATH_HOUR"
        return s


def aggregate_lz4_object(compressed: bytes, observed_etag: str) -> dict:
    summary = new_summary(observed_etag, compressed)
    aggregate = TimestampAggregator(summary)
    pending = bytearray()
    try:
        chunks: Iterable[bytes] = iter_lz4_frame(compressed, MAX_DECOMPRESSED)
        for chunk in chunks:
            summary["decompressed_bytes"] += len(chunk)
            if summary["decompressed_bytes"] > MAX_DECOMPRESSED:
                raise TransportIntegrityError("decompressed byte cap exceeded")
            pending.extend(chunk)
            while True:
                newline = pending.find(b"\n")
                if newline < 0:
                    break
                line = bytes(pending[:newline])
                del pending[: newline + 1]
                aggregate.add_line(line)
            if len(pending) > MAX_RECORD_BYTES:
                raise DiagnosticUnresolved("record byte cap exceeded before newline")
        if pending:
            aggregate.add_line(bytes(pending))
    except LZ4FrameLimit as exc:
        raise TransportIntegrityError(exc.status) from exc
    except LZ4FrameError as exc:
        raise TransportIntegrityError(str(exc)) from exc
    return aggregate.finalize()


def base_result() -> dict:
    return {
        "schema_version": "1.0",
        "diagnostic_id": DIAGNOSTIC_ID,
        "observed_at_utc": None,
        "terminal_status": None,
        "technical_result": None,
        "research_conclusion": None,
        "failure_class": None,
        "request_attempt_count": 0,
        "s3_http_request_count": 0,
        "successful_request_count": 0,
        "failed_request_count": 0,
        "retries_used": 0,
        "http_redirects_followed": False,
        "requester_pays_requested": True,
        "total_compressed_bytes": 0,
        "total_decompressed_bytes": 0,
        "diagnostic_summary": None,
        "raw_object_retained": False,
        "raw_block_event_fill_retained": False,
        "individual_timestamp_retained": False,
        "wallet_address_retained": False,
        "wallet_aggregation_performed": False,
        "economic_fill_field_processing_performed": False,
        "timezone_inference_for_local_time_performed": False,
        "r10_rule_amendment_performed": False,
        "r10_rerun_performed": False,
        "six_hour_execution_performed": False,
        "wallet_ranking_performed": False,
        "candidate_shortlisting_performed": False,
        "pnl_or_alpha_analysis_performed": False,
        "copyability_analysis_performed": False,
        "market_data_ingested": False,
        "strategy_inference_performed": False,
        "runtime_seconds": None,
    }


def execute(
    transport: Callable[[str, str, dict[str, str], int, float], tuple[int, dict[str, str], bytes]] = https_transport,
    request_time: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    env: dict[str, str] | None = None,
) -> tuple[int, dict]:
    validate_static_inputs()
    started = time.monotonic()
    result = base_result()
    try:
        host, path, headers = build_signed_request(request_time(), env)
        if host != REGIONAL_ENDPOINT or path != _aws_quote_path(TARGET["key"]):
            raise ContractError("signed target drift")
        if headers.get("If-Match") != TARGET["etag"] or headers.get("x-amz-request-payer") != "requester":
            raise ContractError("signed request guard drift")
        result["request_attempt_count"] = 1
        result["s3_http_request_count"] = 1
        status, response_headers, compressed = transport(host, path, headers, TARGET["size"], max(1.0, MAX_RUNTIME_SECONDS - (time.monotonic() - started)))
        if status != 200:
            result["failed_request_count"] = 1
            raise TransportIntegrityError(f"S3 HTTP status {status}")
        if response_headers.get("x-amz-request-charged", "").lower() != "requester":
            result["failed_request_count"] = 1
            raise TransportIntegrityError("missing requester-charged response header")
        if response_headers.get("etag") != TARGET["etag"]:
            result["failed_request_count"] = 1
            raise TransportIntegrityError("response ETag mismatch")
        try:
            content_length = int(response_headers.get("content-length", ""))
        except ValueError as exc:
            result["failed_request_count"] = 1
            raise TransportIntegrityError("invalid content-length") from exc
        if content_length != TARGET["size"] or len(compressed) != TARGET["size"] or len(compressed) > MAX_COMPRESSED:
            result["failed_request_count"] = 1
            raise TransportIntegrityError("compressed content length mismatch")
        result["successful_request_count"] = 1
        result["total_compressed_bytes"] = len(compressed)
        summary = aggregate_lz4_object(compressed, response_headers["etag"])
        result["total_decompressed_bytes"] = summary["decompressed_bytes"]
        result["diagnostic_summary"] = summary
        result["terminal_status"] = "R10A_TIMESTAMP_PARTITION_DIAGNOSTIC_COMPLETE"
        result["technical_result"] = summary["alignment_classification"]
        result["research_conclusion"] = summary["alignment_classification"]
        rc = 0
    except DiagnosticUnresolved as exc:
        result["terminal_status"] = "R10A_TIMESTAMP_PARTITION_DIAGNOSTIC_COMPLETE"
        result["technical_result"] = "TIMESTAMP_PARTITION_DIAGNOSTIC_UNRESOLVED"
        result["research_conclusion"] = "TIMESTAMP_PARTITION_DIAGNOSTIC_UNRESOLVED"
        result["failure_class"] = str(exc)
        result["diagnostic_summary"] = None
        rc = 0
    except (TransportIntegrityError, ContractError) as exc:
        result["terminal_status"] = "R10A_TRANSPORT_OR_INTEGRITY_FAIL"
        result["technical_result"] = "R10A_TRANSPORT_OR_INTEGRITY_FAIL"
        result["research_conclusion"] = "R10A_TRANSPORT_OR_INTEGRITY_FAIL"
        result["failure_class"] = str(exc)
        result["diagnostic_summary"] = None
        rc = 83
    result["observed_at_utc"] = utc_now()
    result["runtime_seconds"] = round(time.monotonic() - started, 6)
    return rc, result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-output", required=True)
    args = parser.parse_args(argv)
    rc, result = execute()
    Path(args.result_output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
