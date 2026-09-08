"""Measure what the public ``candleSnapshot`` info request actually provides.

Read-only and unauthenticated, paced by the core's own token bucket against
the documented 1200-weight-per-minute budget. Weight is charged by response
size as well as by request type: a full 5000-row ``candleSnapshot`` costs
``20 + 5000 // 60 = 103``, not 20, which is why a flat 20 at one request per
second drew the three HTTP 429s recorded in ``L2_CANDLE_PROBE_001.json``.

It answers four questions the historical arm of L2 depends on and records the
answers as evidence: which intervals exist, how far back each reaches, what
one response contains, and whether every coin the L1 cohort traded is covered
densely enough for a 15-minute price-age bound.

Run from the repository root::

    python -m research.wallet_copyability.live_data_collector.candle_probe <out.json> [db]
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from src.live_data.config import DEFAULT_REST_BASE_URL, INFO_PATH
from src.live_data.hyperliquid_rest import (
    MAX_CANDLES_PER_RESPONSE,
    request_weight,
    response_weight,
)
from src.live_data.rate_limit import TokenBucket

#: The only endpoint this probe touches, taken from the core's own constants
#: so the collector layer names no venue address of its own.
INFO_URL = DEFAULT_REST_BASE_URL + INFO_PATH
DAY_MS = 86_400_000
INTERVALS = ("1m", "5m", "15m", "1h", "4h", "1d")

#: The venue's documented aggregated budget per IP.
WEIGHT_PER_MINUTE = 1200

#: The request type every call here uses, named once so the weight helpers and
#: the local tally cannot drift apart.
REQUEST_TYPE = "candleSnapshot"

#: How far back the cohort sweep asks for 15-minute candles.
#:
#: Not 90 days. Two independent limits stop a longer ask from returning more:
#: the response cap is ~5000 candles taken backwards from ``endTime``, and the
#: venue's 15-minute retention measured by this probe's own first run was 52.2
#: days (``L2_CANDLE_PROBE_001.json: history_depth_days``). At 96 candles a day
#: 52 days is 4992 rows, just inside the cap. Scoring a response against 90
#: days (8640) instead marks a perfect, gapless series as 58% covered, so the
#: 0.95 gate below could never pass and every coin landed in ``uncovered``.
COHORT_WINDOW_DAYS = 52
CANDLES_PER_DAY_15M = 96


def info(body: dict) -> tuple[int, object, int]:
    raw = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(INFO_URL, data=raw, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = resp.read()
            return resp.status, json.loads(payload), len(payload)
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        return exc.code, payload.decode("utf-8", "replace")[:200], len(payload)


def candles(coin: str, interval: str, start_ms: int, end_ms: int) -> tuple[int, object, int]:
    return info({"type": "candleSnapshot", "req": {"coin": coin, "interval": interval, "startTime": start_ms, "endTime": end_ms}})


def summarize(rows: object) -> dict:
    if not isinstance(rows, list):
        return {"rows": None, "note": str(rows)[:120]}
    if not rows:
        return {"rows": 0}
    sample_keys = sorted(rows[0].keys()) if isinstance(rows[0], dict) else None
    times = sorted(int(r["t"]) for r in rows if isinstance(r, dict) and "t" in r)
    if not times:
        # A non-empty response whose rows carry no "t" is a shape change, not a
        # series. Report it and keep going: indexing times[0] here would raise
        # and discard every request the probe had already paid for.
        return {"rows": len(rows), "note": "no 't' key in any row", "sample_keys": sample_keys}
    gaps = [b - a for a, b in zip(times, times[1:])]
    return {
        "rows": len(rows), "first_t": times[0], "last_t": times[-1],
        "median_gap_ms": sorted(gaps)[len(gaps) // 2] if gaps else None,
        "max_gap_ms": max(gaps) if gaps else None,
        "sample_keys": sample_keys,
    }


def main(out_path: str, db_path: str | None) -> int:
    now = int(time.time() * 1000)
    result: dict = {"probe_id": "L2-CANDLE-PROBE-001", "started_at_ms": now, "requests": 0, "weight_charged_locally": 0,
                    "intervals": {}, "lookback": {}, "cohort_coverage": {}, "errors": []}

    budget = TokenBucket(WEIGHT_PER_MINUTE, WEIGHT_PER_MINUTE / 60.0)

    def call(coin, interval, start, end):
        # Base weight before the call, size surcharge after: the surcharge is
        # only knowable from the response, and spending it afterwards is what
        # paces the *next* request correctly.
        budget.acquire(request_weight(REQUEST_TYPE))
        status, payload, size = candles(coin, interval, start, end)
        rows = len(payload) if isinstance(payload, list) else 0
        charged = response_weight(REQUEST_TYPE, rows)
        surcharge = charged - request_weight(REQUEST_TYPE)
        if surcharge > 0:
            budget.acquire(surcharge)
        result["requests"] += 1
        result["weight_charged_locally"] += charged
        if status != 200:
            result["errors"].append({"coin": coin, "interval": interval, "status": status, "body": str(payload)[:120]})
        return status, payload, size

    # 1. Which intervals exist, over the last 7 days for BTC.
    for interval in INTERVALS:
        status, payload, size = call("BTC", interval, now - 7 * DAY_MS, now)
        result["intervals"][interval] = {"status": status, "bytes": size, **summarize(payload)}

    # 2. How far back each interval reaches: ask from two years ago and read the first candle.
    for interval in ("1m", "5m", "15m", "1h"):
        status, payload, size = call("BTC", interval, now - 730 * DAY_MS, now)
        s = summarize(payload)
        result["lookback"][interval] = {"status": status, "bytes": size, **s,
                                        "earliest_days_ago": None if not s.get("first_t") else round((now - s["first_t"]) / DAY_MS, 1)}

    # 3. Coverage for every coin the L1 cohort traded, at 15m over the retained window.
    coins: list[str] = []
    if db_path:
        con = sqlite3.connect(db_path)
        coins = [r[0] for r in con.execute("SELECT DISTINCT coin FROM fills ORDER BY coin")]
        con.close()
    expected_rows = min(COHORT_WINDOW_DAYS * CANDLES_PER_DAY_15M, MAX_CANDLES_PER_RESPONSE)
    result["cohort_window_days"] = COHORT_WINDOW_DAYS
    result["cohort_expected_rows_15m"] = expected_rows
    for coin in coins:
        status, payload, size = call(coin, "15m", now - COHORT_WINDOW_DAYS * DAY_MS, now)
        s = summarize(payload)
        result["cohort_coverage"][coin] = {
            "status": status, **s,
            "coverage_share": None if s.get("rows") is None else round(s["rows"] / expected_rows, 3),
            "max_gap_minutes": None if not s.get("max_gap_ms") else round(s["max_gap_ms"] / 60_000, 1),
        }

    result["finished_at_ms"] = int(time.time() * 1000)
    result["elapsed_seconds"] = round((result["finished_at_ms"] - now) / 1000, 1)
    covered = [c for c, v in result["cohort_coverage"].items() if (v.get("coverage_share") or 0) >= 0.95 and (v.get("max_gap_minutes") or 1e9) <= 15]
    result["cohort_summary"] = {
        "coins": len(coins), "covered_95pct_and_gap_le_15min": len(covered),
        "uncovered": sorted(c for c in coins if c not in covered),
    }
    Path(out_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("requests", "weight_charged_locally", "elapsed_seconds", "cohort_summary")}, indent=1))
    for interval, v in result["intervals"].items():
        print(interval, v.get("status"), v.get("rows"), "median gap", v.get("median_gap_ms"))
    for interval, v in result["lookback"].items():
        print("lookback", interval, v.get("rows"), "earliest days ago", v.get("earliest_days_ago"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
