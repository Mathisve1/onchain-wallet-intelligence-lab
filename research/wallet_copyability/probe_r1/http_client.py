from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from contract import sha256


class ProbeTransportError(RuntimeError):
    pass


class SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        old = urllib.parse.urlsplit(req.full_url)
        new = urllib.parse.urlsplit(urllib.parse.urljoin(req.full_url, newurl))
        if (old.scheme, old.netloc) != (new.scheme, new.netloc):
            raise urllib.error.HTTPError(req.full_url, code, "cross-origin redirect blocked", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, new.geturl())


@dataclass(frozen=True)
class ResponseRecord:
    http_status: int | None
    body: bytes
    content_type: str | None
    elapsed_ms: float
    transport_error_class: str | None
    transport_error_message: str | None


def _read_bounded(response: Any, maximum_bytes: int) -> bytes:
    body = response.read(maximum_bytes + 1)
    if len(body) > maximum_bytes:
        raise ProbeTransportError(f"response exceeds {maximum_bytes} bytes")
    return body


def request_once(request: urllib.request.Request, timeout: int, maximum_bytes: int) -> ResponseRecord:
    opener = urllib.request.build_opener(SameOriginRedirectHandler())
    started = time.monotonic()
    try:
        with opener.open(request, timeout=timeout) as response:
            return ResponseRecord(int(response.status), _read_bounded(response, maximum_bytes), response.headers.get("Content-Type"), round((time.monotonic() - started) * 1000, 3), None, None)
    except urllib.error.HTTPError as exc:
        try:
            body = _read_bounded(exc, maximum_bytes)
        except Exception:
            body = b""
        return ResponseRecord(int(exc.code), body, exc.headers.get("Content-Type") if exc.headers else None, round((time.monotonic() - started) * 1000, 3), type(exc).__name__, str(exc.reason)[:300])
    except Exception as exc:
        return ResponseRecord(None, b"", None, round((time.monotonic() - started) * 1000, 3), type(exc).__name__, str(exc)[:300])


def should_retry(record: ResponseRecord) -> bool:
    return record.http_status is None or record.http_status == 429 or (record.http_status is not None and record.http_status >= 500)


def json_shape(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {"response_class": "JSON", "top_level_type": "object", "top_level_keys": sorted(str(key) for key in value), "element_count": len(value), "sample_item_types": []}
    if isinstance(value, list):
        item_types = sorted({type(item).__name__ for item in value[:100]})
        first_keys = sorted(str(key) for key in value[0]) if value and isinstance(value[0], dict) else []
        return {"response_class": "JSON", "top_level_type": "array", "top_level_keys": first_keys, "element_count": len(value), "sample_item_types": item_types}
    if value is None:
        return {"response_class": "JSON", "top_level_type": "null", "top_level_keys": [], "element_count": 0, "sample_item_types": []}
    return {"response_class": "JSON", "top_level_type": type(value).__name__, "top_level_keys": [], "element_count": 1, "sample_item_types": []}


def _classify_s3(record: ResponseRecord, base: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    stripped = record.body.lstrip()
    if record.http_status == 200 and b"<ListBucketResult" in stripped:
        base.update({"response_class": "S3_LISTING", "top_level_type": "xml", "json_status": "NOT_APPLICABLE"})
        return "PASS", base
    if record.http_status in {400, 403, 404} and b"<Error" in stripped and b"<Code>" in stripped:
        base.update({"response_class": "S3_ERROR_RESPONSE", "top_level_type": "xml", "json_status": "NOT_APPLICABLE"})
        return "PASS", base
    base.update({"response_class": "UNSUPPORTED", "top_level_type": "bytes"})
    return "FAIL", base


def classify_body(expected: str, record: ResponseRecord) -> tuple[str, dict[str, Any]]:
    base: dict[str, Any] = {
        "body_length": len(record.body), "body_sha256": sha256(record.body), "content_type": record.content_type,
        "response_class": "UNSUPPORTED", "json_status": "NOT_APPLICABLE", "top_level_type": "bytes",
        "top_level_keys": [], "element_count": None, "sample_item_types": [],
    }
    if expected == "s3_listing_or_error":
        return _classify_s3(record, base)
    if not (record.http_status is not None and 200 <= record.http_status < 300):
        return "FAIL", base
    try:
        parsed = json.loads(record.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        base["json_status"] = "INVALID_JSON"
        return "FAIL", base
    base["json_status"] = "VALID_JSON"
    base.update(json_shape(parsed))
    observed = base["top_level_type"]
    accepted = {
        "json_object": observed == "object",
        "json_array": observed == "array",
        "json_array_or_null": observed in {"array", "null"},
        "json_object_or_null": observed in {"object", "null"},
    }.get(expected, False)
    return ("PASS" if accepted else "FAIL", base)
