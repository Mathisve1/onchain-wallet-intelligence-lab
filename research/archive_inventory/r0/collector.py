from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = ROOT / "research/archive_inventory"
R0_ROOT = ARCHIVE / "r0"
DATASET_REGISTER = ARCHIVE / "DATASET_REGISTER.json"
R0_CONTRACT = ARCHIVE / "METADATA_CANARY_R0_CONTRACT.json"
IMPLEMENTATION_CONTRACT = R0_ROOT / "R0_IMPLEMENTATION_CONTRACT.json"
APPROVAL_JSON = ARCHIVE / "approvals/APPROVE_HL_ARCHIVE_METADATA_CANARY_R0_001.json"
APPROVAL_TEXT = ARCHIVE / "approvals/APPROVE_HL_ARCHIVE_METADATA_CANARY_R0_001.txt"

CANARY_ID = "HL-ARCHIVE-METADATA-CANARY-R0-001"
APPROVAL_ID = "APPROVE_HL_ARCHIVE_METADATA_CANARY_R0_001"
APPROVAL_COMMIT = "9af4b21863e47fb3bb2997ce77b9940eecf4597f"
APPROVAL_TEXT_SHA256 = "d70008eac7521b324f61161bcc0075e28cc3a116dd30f0c52b48d8cf5eb6ed46"
MAX_REQUESTS = 7
MAX_KEYS = 25
MAX_ENTRIES = 175
MAX_RESPONSE_BYTES = 8_388_608
MAX_RUNTIME_SECONDS = 180
AWS_MAX_ATTEMPTS = "1"

EXPECTED_DATASETS = (
    ("node_fills_by_block", "hl-mainnet-node-data", "node_fills_by_block/"),
    ("node_fills_legacy", "hl-mainnet-node-data", "node_fills/"),
    ("node_trades_legacy", "hl-mainnet-node-data", "node_trades/"),
    ("explorer_blocks", "hl-mainnet-node-data", "explorer_blocks/"),
    ("replica_cmds", "hl-mainnet-node-data", "replica_cmds/"),
    ("market_data", "hyperliquid-archive", "market_data/"),
    ("asset_ctxs", "hyperliquid-archive", "asset_ctxs/"),
)

KNOWN_AWS_ERROR_CODES = {
    "AccessDenied",
    "AllAccessDisabled",
    "AuthorizationHeaderMalformed",
    "ExpiredToken",
    "InvalidAccessKeyId",
    "NoSuchBucket",
    "PermanentRedirect",
    "RequestTimeout",
    "SignatureDoesNotMatch",
    "SlowDown",
}


class R0ContractError(RuntimeError):
    pass


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise R0ContractError("json root must be object")
    return value


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_static_inputs() -> list[dict]:
    approval_raw = APPROVAL_TEXT.read_bytes()
    approval = load_json(APPROVAL_JSON)
    contract = load_json(R0_CONTRACT)
    implementation = load_json(IMPLEMENTATION_CONTRACT)
    register = load_json(DATASET_REGISTER)

    if sha256_bytes(approval_raw) != APPROVAL_TEXT_SHA256:
        raise R0ContractError("approval text hash drift")
    if approval.get("approval_id") != APPROVAL_ID:
        raise R0ContractError("approval id drift")
    if approval.get("reviewed_commit") != APPROVAL_COMMIT:
        raise R0ContractError("approval commit drift")
    if approval.get("exact_approval_text_sha256") != APPROVAL_TEXT_SHA256:
        raise R0ContractError("approval record hash drift")
    if approval.get("approval_status") != "APPROVED_SCOPE_AND_BUDGET_AWAITING_IMPLEMENTATION":
        raise R0ContractError("approval status drift")
    if approval.get("maximum_one_time_budget_eur") != 1.0 or approval.get("maximum_monthly_budget_eur") != 0:
        raise R0ContractError("approval budget drift")
    if approval.get("maximum_list_requests") != MAX_REQUESTS:
        raise R0ContractError("approval request cap drift")
    if approval.get("maximum_keys_per_request") != MAX_KEYS:
        raise R0ContractError("approval max keys drift")
    if approval.get("maximum_total_entries") != MAX_ENTRIES:
        raise R0ContractError("approval entry cap drift")
    if approval.get("maximum_total_response_bytes") != MAX_RESPONSE_BYTES:
        raise R0ContractError("approval response-byte cap drift")
    if approval.get("maximum_runtime_seconds") != MAX_RUNTIME_SECONDS:
        raise R0ContractError("approval runtime cap drift")
    if approval.get("maximum_retries_per_request") != 0 or approval.get("pagination_authorized") is not False:
        raise R0ContractError("approval retry/pagination drift")
    if approval.get("requester_pays_scope_approved") is not True or approval.get("list_objects_v2_scope_approved") is not True:
        raise R0ContractError("approval list scope not approved")
    if not all(approval.get("forbidden_capabilities", {}).values()):
        raise R0ContractError("approval forbidden capability drift")

    if contract.get("canary_id") != CANARY_ID or contract.get("operation") != "ListObjectsV2":
        raise R0ContractError("R0 contract identity drift")
    if contract.get("request_payer") != "requester":
        raise R0ContractError("R0 request payer drift")
    if contract.get("dataset_family_count") != MAX_REQUESTS:
        raise R0ContractError("R0 family count drift")
    if contract.get("max_keys_per_request") != MAX_KEYS:
        raise R0ContractError("R0 contract max keys drift")
    if contract.get("max_total_list_requests") != MAX_REQUESTS:
        raise R0ContractError("R0 contract request cap drift")
    if contract.get("max_total_entries") != MAX_ENTRIES:
        raise R0ContractError("R0 contract entry cap drift")
    if contract.get("max_total_response_bytes") != MAX_RESPONSE_BYTES:
        raise R0ContractError("R0 contract response-byte cap drift")
    if contract.get("max_runtime_seconds") != MAX_RUNTIME_SECONDS:
        raise R0ContractError("R0 contract runtime drift")
    if contract.get("max_retries_per_request") != 0:
        raise R0ContractError("R0 retries opened")
    if contract.get("pagination_allowed") is not False or contract.get("continuation_token_follow_allowed") is not False:
        raise R0ContractError("R0 pagination opened")

    if implementation.get("canary_id") != CANARY_ID:
        raise R0ContractError("implementation canary drift")
    if implementation.get("human_approval_text_sha256") != APPROVAL_TEXT_SHA256:
        raise R0ContractError("implementation approval binding drift")
    if implementation.get("maximum_list_requests") != MAX_REQUESTS:
        raise R0ContractError("implementation request cap drift")
    if implementation.get("maximum_keys_per_request") != MAX_KEYS:
        raise R0ContractError("implementation max keys drift")
    if implementation.get("aws_cli_max_attempts") != 1:
        raise R0ContractError("implementation retry setting drift")
    if implementation.get("pagination_authorized") is not False:
        raise R0ContractError("implementation pagination opened")
    if implementation.get("market_data_ingestion_authorized") is not False:
        raise R0ContractError("implementation market-data gate opened")
    if not all(value is False for value in implementation.get("authorizations", {}).values()):
        raise R0ContractError("implementation trading authorization opened")

    rows = register.get("datasets")
    if not isinstance(rows, list) or len(rows) != MAX_REQUESTS:
        raise R0ContractError("dataset register count drift")
    observed = [(row.get("family"), row.get("bucket"), row.get("prefix")) for row in rows]
    if tuple(observed) != EXPECTED_DATASETS:
        raise R0ContractError("dataset order/scope drift")
    return rows


def build_command(bucket: str, prefix: str) -> list[str]:
    allowed = {(bucket_name, prefix_name) for _, bucket_name, prefix_name in EXPECTED_DATASETS}
    if (bucket, prefix) not in allowed:
        raise R0ContractError("unregistered bucket/prefix")
    return [
        "aws",
        "s3api",
        "list-objects-v2",
        "--bucket",
        bucket,
        "--prefix",
        prefix,
        "--max-keys",
        str(MAX_KEYS),
        "--request-payer",
        "requester",
        "--no-paginate",
        "--output",
        "json",
        "--no-cli-pager",
        "--cli-connect-timeout",
        "5",
        "--cli-read-timeout",
        "15",
    ]


def classify_cli_error(stderr: bytes, returncode: int) -> str:
    text = stderr.decode("utf-8", errors="replace")
    match = re.search(r"\(([^)]+)\) when calling the ListObjectsV2 operation", text)
    if match and match.group(1) in KNOWN_AWS_ERROR_CODES:
        return f"AWS_{match.group(1)}"
    return f"AWS_CLI_EXIT_{returncode}"


def normalize_success(payload: dict, family: str, bucket: str, prefix: str, request_index: int, response_bytes: int, observed_at: str) -> tuple[dict, int]:
    if payload.get("Name") != bucket:
        raise R0ContractError("response bucket mismatch")
    if payload.get("Prefix") != prefix:
        raise R0ContractError("response prefix mismatch")
    if payload.get("MaxKeys") != MAX_KEYS:
        raise R0ContractError("response MaxKeys mismatch")
    key_count = payload.get("KeyCount")
    if not isinstance(key_count, int) or isinstance(key_count, bool) or not 0 <= key_count <= MAX_KEYS:
        raise R0ContractError("response KeyCount invalid")
    is_truncated = payload.get("IsTruncated")
    if not isinstance(is_truncated, bool):
        raise R0ContractError("response IsTruncated invalid")
    contents = payload.get("Contents", [])
    if not isinstance(contents, list) or len(contents) > MAX_KEYS:
        raise R0ContractError("response Contents invalid")
    if key_count != len(contents):
        raise R0ContractError("KeyCount/Contents mismatch")

    entries: list[dict] = []
    for item in contents:
        if not isinstance(item, dict):
            raise R0ContractError("object metadata row invalid")
        key = item.get("Key")
        size = item.get("Size")
        last_modified = item.get("LastModified")
        etag = item.get("ETag")
        storage_class = item.get("StorageClass")
        if not isinstance(key, str) or not key.startswith(prefix):
            raise R0ContractError("object key escaped prefix")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise R0ContractError("object size invalid")
        if last_modified is not None and not isinstance(last_modified, str):
            raise R0ContractError("last modified invalid")
        if etag is not None and not isinstance(etag, str):
            raise R0ContractError("etag invalid")
        if storage_class is not None and not isinstance(storage_class, str):
            raise R0ContractError("storage class invalid")
        entries.append(
            {
                "key": key,
                "size_bytes": size,
                "last_modified": last_modified,
                "etag": etag,
                "storage_class": storage_class,
            }
        )
    entries.sort(key=lambda row: row["key"])
    token = payload.get("NextContinuationToken")
    observation = {
        "dataset_family_id": family,
        "bucket": bucket,
        "prefix": prefix,
        "request_index": request_index,
        "http_or_sdk_status_class": "SUCCESS",
        "request_charged": payload.get("RequestCharged"),
        "key_count": key_count,
        "is_truncated": is_truncated,
        "next_continuation_token_present": isinstance(token, str) and bool(token),
        "response_bytes": response_bytes,
        "observed_at_utc": observed_at,
        "entries": entries,
    }
    return observation, len(entries)


def execute_canary(output_path: Path, runner=subprocess.run, monotonic=time.monotonic, now=utc_now) -> dict:
    datasets = validate_static_inputs()
    started = monotonic()
    observations: list[dict] = []
    request_attempt_count = 0
    successful_request_count = 0
    total_entries = 0
    total_response_bytes = 0

    env = os.environ.copy()
    env["AWS_MAX_ATTEMPTS"] = AWS_MAX_ATTEMPTS
    env["AWS_RETRY_MODE"] = "standard"
    env["AWS_PAGER"] = ""
    env["AWS_EC2_METADATA_DISABLED"] = "true"

    hard_failure = False
    for row in datasets:
        elapsed = monotonic() - started
        if elapsed >= MAX_RUNTIME_SECONDS:
            hard_failure = True
            break
        if request_attempt_count >= MAX_REQUESTS:
            hard_failure = True
            break

        family = row["family"]
        bucket = row["bucket"]
        prefix = row["prefix"]
        request_attempt_count += 1
        command = build_command(bucket, prefix)
        remaining = MAX_RUNTIME_SECONDS - elapsed
        timeout_seconds = max(1.0, min(20.0, remaining))

        try:
            completed = runner(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=timeout_seconds,
                env=env,
            )
            stdout = completed.stdout if isinstance(completed.stdout, bytes) else bytes(completed.stdout or b"")
            stderr = completed.stderr if isinstance(completed.stderr, bytes) else bytes(completed.stderr or b"")
            response_bytes = len(stdout)
            total_response_bytes += response_bytes
            observed_at = now()

            if total_response_bytes > MAX_RESPONSE_BYTES:
                observations.append(
                    {
                        "dataset_family_id": family,
                        "bucket": bucket,
                        "prefix": prefix,
                        "request_index": request_attempt_count,
                        "http_or_sdk_status_class": "RESPONSE_BYTE_CAP_EXCEEDED",
                        "request_charged": None,
                        "key_count": 0,
                        "is_truncated": False,
                        "next_continuation_token_present": False,
                        "response_bytes": response_bytes,
                        "observed_at_utc": observed_at,
                        "entries": [],
                    }
                )
                hard_failure = True
                break

            if completed.returncode != 0:
                observations.append(
                    {
                        "dataset_family_id": family,
                        "bucket": bucket,
                        "prefix": prefix,
                        "request_index": request_attempt_count,
                        "http_or_sdk_status_class": classify_cli_error(stderr, completed.returncode),
                        "request_charged": None,
                        "key_count": 0,
                        "is_truncated": False,
                        "next_continuation_token_present": False,
                        "response_bytes": response_bytes,
                        "observed_at_utc": observed_at,
                        "entries": [],
                    }
                )
                continue

            payload = json.loads(stdout.decode("utf-8"))
            if not isinstance(payload, dict):
                raise R0ContractError("AWS CLI output root invalid")
            observation, entry_count = normalize_success(
                payload, family, bucket, prefix, request_attempt_count, response_bytes, observed_at
            )
            total_entries += entry_count
            if total_entries > MAX_ENTRIES:
                observation["http_or_sdk_status_class"] = "ENTRY_CAP_EXCEEDED"
                observations.append(observation)
                hard_failure = True
                break
            observations.append(observation)
            successful_request_count += 1
        except subprocess.TimeoutExpired as exc:
            partial_stdout = exc.stdout if isinstance(exc.stdout, bytes) else b""
            response_bytes = len(partial_stdout)
            total_response_bytes += response_bytes
            observations.append(
                {
                    "dataset_family_id": family,
                    "bucket": bucket,
                    "prefix": prefix,
                    "request_index": request_attempt_count,
                    "http_or_sdk_status_class": "AWS_CLI_TIMEOUT",
                    "request_charged": None,
                    "key_count": 0,
                    "is_truncated": False,
                    "next_continuation_token_present": False,
                    "response_bytes": response_bytes,
                    "observed_at_utc": now(),
                    "entries": [],
                }
            )
        except FileNotFoundError:
            observations.append(
                {
                    "dataset_family_id": family,
                    "bucket": bucket,
                    "prefix": prefix,
                    "request_index": request_attempt_count,
                    "http_or_sdk_status_class": "AWS_CLI_NOT_FOUND",
                    "request_charged": None,
                    "key_count": 0,
                    "is_truncated": False,
                    "next_continuation_token_present": False,
                    "response_bytes": 0,
                    "observed_at_utc": now(),
                    "entries": [],
                }
            )
            hard_failure = True
            break
        except (json.JSONDecodeError, UnicodeDecodeError, R0ContractError):
            observations.append(
                {
                    "dataset_family_id": family,
                    "bucket": bucket,
                    "prefix": prefix,
                    "request_index": request_attempt_count,
                    "http_or_sdk_status_class": "INVALID_SUCCESS_RESPONSE",
                    "request_charged": None,
                    "key_count": 0,
                    "is_truncated": False,
                    "next_continuation_token_present": False,
                    "response_bytes": response_bytes if "response_bytes" in locals() else 0,
                    "observed_at_utc": now(),
                    "entries": [],
                }
            )
            hard_failure = True
            break

    runtime_seconds = monotonic() - started
    if runtime_seconds > MAX_RUNTIME_SECONDS:
        hard_failure = True
    failed_request_count = request_attempt_count - successful_request_count
    passed = (
        not hard_failure
        and request_attempt_count == MAX_REQUESTS
        and successful_request_count == MAX_REQUESTS
        and failed_request_count == 0
        and total_entries <= MAX_ENTRIES
        and total_response_bytes <= MAX_RESPONSE_BYTES
        and runtime_seconds <= MAX_RUNTIME_SECONDS
    )
    result = {
        "schema_version": "1.0",
        "canary_id": CANARY_ID,
        "terminal_status": "R0_METADATA_CANARY_PASS" if passed else "R0_METADATA_CANARY_FAIL",
        "request_attempt_count": request_attempt_count,
        "successful_request_count": successful_request_count,
        "failed_request_count": failed_request_count,
        "total_entries": total_entries,
        "total_response_bytes": total_response_bytes,
        "runtime_seconds": round(runtime_seconds, 6),
        "maximum_list_requests": MAX_REQUESTS,
        "maximum_keys_per_request": MAX_KEYS,
        "maximum_total_entries": MAX_ENTRIES,
        "maximum_total_response_bytes": MAX_RESPONSE_BYTES,
        "maximum_runtime_seconds": MAX_RUNTIME_SECONDS,
        "aws_max_attempts": int(AWS_MAX_ATTEMPTS),
        "retries_used": 0,
        "pagination_followed": False,
        "requester_pays_requested": True,
        "continuation_token_values_retained": False,
        "object_body_requested": False,
        "market_data_ingested": False,
        "empirical_result": None,
        "observations": observations,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def write_pre_network_failure(output_path: Path) -> None:
    result = {
        "schema_version": "1.0",
        "canary_id": CANARY_ID,
        "terminal_status": "R0_PRE_NETWORK_CONTRACT_FAIL",
        "request_attempt_count": 0,
        "successful_request_count": 0,
        "failed_request_count": 0,
        "total_entries": 0,
        "total_response_bytes": 0,
        "runtime_seconds": 0.0,
        "maximum_list_requests": MAX_REQUESTS,
        "maximum_keys_per_request": MAX_KEYS,
        "maximum_total_entries": MAX_ENTRIES,
        "maximum_total_response_bytes": MAX_RESPONSE_BYTES,
        "maximum_runtime_seconds": MAX_RUNTIME_SECONDS,
        "aws_max_attempts": int(AWS_MAX_ATTEMPTS),
        "retries_used": 0,
        "pagination_followed": False,
        "requester_pays_requested": False,
        "continuation_token_values_retained": False,
        "object_body_requested": False,
        "market_data_ingested": False,
        "empirical_result": None,
        "observations": [],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    output_path = Path(sys.argv[1])
    try:
        result = execute_canary(output_path)
    except R0ContractError:
        write_pre_network_failure(output_path)
        return 0
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
