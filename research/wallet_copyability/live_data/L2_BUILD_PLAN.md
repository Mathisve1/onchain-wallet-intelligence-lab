# L2 build plan (phased, for execution by `do`)

Governing: `L2_ANALYSIS_PLAN.md` (FROZEN, commit `1833f34`), DEC-043, DEC-044.
Owner constraints: no new governance artefacts; `src/` stdlib-only and network-free;
transports only under `research/wallet_copyability/live_data_collector/`; every file
under 500 lines; every new collection module gets a code review before its first
request; loader/poller/backfill/candle fetch may be delegated, analysis and audit
may not. Nothing here inspects a study result.

## Phase 0 — allowed APIs (from documentation discovery, verified against source)

Copy from, never invent:

- REST client: `src/live_data/hyperliquid_rest.py:193-251` — `HyperliquidRestClient.request(request_type, **params)` spends `request_weight(type)` per attempt via `TokenBucket.acquire` (`rate_limit.py:76-97`), retries only `is_retryable` statuses (429 or 5xx, `:85-87`), backoff `backoff_base_seconds * 2**attempt` (`:249`). `build_info_body` (`:120-181`) rejects unknown types and params; timestamps via `_positive_time` (`:112-117`). Weights table `:34-44`; `SUPPORTED_REQUEST_TYPES = frozenset(INFO_REQUEST_WEIGHTS) - {"l2Book"}` (`:49`).
- Ingest: `ingest.py:79-130` `_collect_fills` returns `(pages, seen, written, forced, exhausted, covered_until_ms)`; `:132-140` `_collect_funding` returns `(seen, written, exhausted)` from ONE `userFunding` call; `backfill_wallet` writes coverage `{window, fills, funding, positions, requests}`; `MAX_FUNDING_PER_RESPONSE = 500` (`:32`); `DEFAULT_MAX_PAGES = 200` (`:29`).
- Watch: `watch.py` coverage keys `fills, mids, trades, positions{tracked_wallets, interval_seconds, snapshots, written}, connection{reconnects}, requests`.
- Storage: `schema.py` `SCHEMA_VERSION = 3`, `_SCHEMA_STATEMENTS`, `_MIGRATIONS = {2: (...), 3: (...)}`; `storage.py` `write_fills/write_funding/write_mids/write_trades/write_position_snapshot(…, ingested_at_ms=)` all `ON CONFLICT DO NOTHING`, `count(table)` allowlist, `start_run/finish_run(coverage=)`, `recent_runs`, `most_active_wallets(limit)`, `upsert_wallet(address, observed_at_ms=, label=)`.
- Models: `models.py` `require_mapping/require_list/require_str/require_int/require_bool/require_decimal/require_event_time_ms`; `Fill.parse(row, wallet)`, `parse_funding(payload, wallet)`, `parse_all_mids(payload)`.
- CLI: `cli.py` `build_parser()` subcommands `init-db, backfill, watch, status, wallets`; `Dependencies(transport, connection_factory)`; `_build_orchestrator(config, store, dependencies, with_ws=)`; commands are pure functions `(args, dependencies) -> int`; no `__main__` in `src/`.
- Collector: `live_data_collector/__main__.py` `build_dependencies()`; `transports.py` `build_urllib_transport()`; `candle_probe.py` `candles(coin, interval, start_ms, end_ms)` and `summarize(rows)` (probe only; endpoint from `src.live_data.config`).
- Simulator: `src/copyability/loader.py` `load_fills(store, wallets=)`, `load_fill_prices(store, coins, exclude_wallet=)`, `load_trade_prices`, `load_prices` (mids), `load_funding_rates`, `load_funding_truncation`, `load_coverage`, `build_market(store, coins, liquidity, price_source=, exclude_wallet=)`, `PRICE_SOURCES`; `simulate.run_study(fills_by_wallet=, market=, ledger=, config=, funding_truncated=, wallets=, window=, market_for=)`, `StudyConfig(follower, cost_model, benchmark_coin, momentum_lookback_ms, momentum_step_ms, random_seed, random_sample_size, latencies_ms=, thresholds=, max_price_age_ms=)`; `classify.profile_wallet(interval, fills, thresholds)`; `coverage.CoverageLedger(observed).certify(wallet, start, end)`; `inputs.LiquidityProfile(coin, half_spread_bps, depth_notional, impact_bps_per_depth, source="ASSUMED")`; `execution.LATENCY_GRID_MS`.
- Test fakes: `tests/test_live_data_ingest.py:63-101` `ScriptedTransport(payloads)` (auto-answers `clearinghouseState`), `FakeConnection(inbound)`, `fill_payload(tid, time_ms, **overrides)`, `clearinghouse_payload()`; `IngestTestCase.build(payloads, config=, ws_connection=)` (`:113-143`); `tests/test_live_data_coverage.py:38-47` `FUNDING_ROW`.
- Guard: `tests/test_live_data_read_only_guard.py` pins core set (13 files) and collector set (`__init__.py, __main__.py, transports.py, candle_probe.py`); collector files may contain no `https://`/`wss://`/`http://`/`ws://`; every `"/…"` literal must be `"/info"`; forbidden tokens `:34-46`; 500-line cap.
- L1 validator: `governance/validate_l1_live_data_preregistration.py:240-273` compares `rest_request_types` in the approval text with `sorted(contract["rest_request_type_allowlist"])`, and `validate_request_type_scope` compares the contract allowlist with `SUPPORTED_REQUEST_TYPES`.

Anti-patterns: no `candleSnapshot` params other than `req={coin, interval, startTime, endTime}` (the venue nests them under `req`); no scheduler or sleep loop that runs unattended; no URL literal in the collector; no reading of a study result inside a collection command; no new validator, approval template or tamper test.

## Phase 1 — response-size weight and backoff (`src/live_data/hyperliquid_rest.py`, `tests/test_live_data_hyperliquid_rest.py`)

Implement: `response_weight(request_type, row_count)` = base weight + `row_count // 60`; `request()` charges the base before the attempt (as now) and charges the surcharge after decoding a list response (`bucket.acquire(surcharge)` when surcharge > 0), adds both to `consumed_weight`; first 429 backs off `max(backoff_base_seconds, 5.0)` seconds then doubles; `max_retries` unchanged. Add `SIZE_WEIGHT_ROWS_PER_UNIT = 60` and cite the three 429 measurements in the docstring.
Acceptance: tests prove a 2000-row page costs 20 + 33, a 5000-row page 20 + 83, a dict response costs base only, first-429 sleep is 5 s, three retries then `RestHttpError`; existing tests pass.

## Phase 2 — `userFunding` paging (`src/live_data/ingest.py`, `tests/test_live_data_coverage.py`)

Implement: `_collect_funding` pages by `start_time = last event_time_ms + 1` while a page is full (`>= MAX_FUNDING_PER_RESPONSE`), up to `max_pages`; returns `(seen, written, exhausted, pages)`; `backfill_wallet` coverage funding gains `pages` and keeps `completed = exhausted`, `truncated_at_response_cap = not exhausted`. Keep `ingest.py` under 500 lines (move `backfill_wallet_fills`/`backfill_days`/`backfill_wallet_funding` into `src/live_data/legacy_backfill.py` as a mixin if needed and add it to the guard's core set).
Acceptance: a scripted transport with 500 + 500 + 120 funding rows yields seen 1120, exhausted True, pages 3; 500 + 500 with `max_pages=2` yields exhausted False; funding coverage records match.

## Phase 3 — `candleSnapshot` (`config.py` untouched; `hyperliquid_rest.py`, `models.py`, `schema.py` v4, `storage.py`, `ingest.py` or new `src/live_data/candles.py`, `cli.py`, guard sets, L1 validator + its tests)

Implement: `INFO_REQUEST_WEIGHTS["candleSnapshot"] = 20`, supported; `build_info_body("candleSnapshot", coin=, interval=, start_time=, end_time=)` emits `{"type":"candleSnapshot","req":{"coin","interval","startTime","endTime"}}`, interval validated against `("1m","5m","15m","1h","4h","1d")`. `Candle` model in `models.py` (or `candles.py`) parsing `t,T,o,h,l,c,v,n,i,s` with `require_*`. Schema v4: `candles(coin, interval, open_time_ms, close_time_ms, open, high, low, close, volume, trade_count, raw_payload, ingested_at_ms, PRIMARY KEY (coin, interval, open_time_ms))` with migration 4; `write_candles`. `fetch_candles(coin, interval, start_ms, end_ms, *, max_pages)` walks backwards by `end_time = first open_time_ms - 1` while a page has 5000 rows, records coverage `{candles: {coin, interval, pages, rows, written, first_open_ms, last_open_ms, max_gap_ms, exhausted}}`. CLI `candles --coins … --interval 15m --days 52`. Guard: add any new core module to the pinned set. L1 validator: in `validate_request_type_scope` and `validate_approval_binds_the_code`, accept `SUPPORTED_REQUEST_TYPES` equal to the L1 allowlist plus the types listed under `additional_rest_request_types` in `APPROVE_HL_LIVE_DATA_L2_TWO_ARM_STUDY_001.txt` (parse that file; document the widening in the validator docstring); update `tests/test_live_data_l1_preregistration.py` so the tamper test that appends `l2Book` still fails and a test proves `candleSnapshot` is accepted only because that approval names it.
Acceptance: paging test with a 5000-row page then a short page; PK dedup; migration v3 to v4 in place; validator green with `candleSnapshot` present and red with an unlisted type.

## Phase 4 — arm B sweep (`src/live_data/sweep.py` new core mixin or module, `cli.py`, collector `__main__`, tests)

Implement: `sweep(cohort_wallets, coins, *, funding_pages)` = one bounded run: `allMids` once (weight 2) written to `mids` for the given coins; for each wallet `userFillsByTime` from `latest_fill_time_ms(wallet) + 1` (or the cohort's T0 for a wallet with no fills) to now, paged; `userFunding` paged from the wallet's latest funding time; `clearinghouseState` for the top-10 wallets only (the owner's snapshot rule); coverage per wallet and a `sweep` run row with `requests`. CLI `sweep --cohort path --coins … [--snapshot-top N]`. A sweep never loops; the operator starts each one. Document the cadence: one sweep per five minutes is not required — the copy latency is simulated from venue timestamps; a sweep every few hours is enough for fills, and `allMids` every 5 minutes is a separate light command `mids --coins …` (weight 2) the operator runs in a loop of their own choosing (no scheduler in the repo).
Acceptance: scripted test covering two wallets, one with prior fills; the sweep issues exactly the expected request sequence (`ScriptedTransport.bodies`); coverage rows written; weight accounted.

## Phase 5 — discovery, characterisation, cohort freeze (collector-layer scripts + `src/copyability/cohort.py` for the pure logic)

Implement pure logic in `src/copyability/cohort.py`: `characterise(wallet, fills, *, window)` using `profile_wallet` on `[T0-90d, T0-60d]`; `rebate_dependence(fills)` = negative-fee income / gross closed P&L; `in_scope(coin)` = not `@`-prefixed, not `xyz:`, not in the unmeasured set, has a funding rate in the schedule, has a complete 15-minute candle series over `[T0-52d, T0-7d]` (from the candles table, max gap ≤ 15 min); `scope_share(fills)` = in-scope notional share; `select_cohort(candidates, …) -> CohortSelection` with counts per stage (`discovered, prefiltered_directional, rebate_excluded, scope_excluded, coverage_excluded, evaluable`). Collector scripts: `discover` runs N tape sessions over a coin list via the existing `watch --coins` and unions `most_active_wallets(600)`; `characterise` runs `backfill --days 90` per candidate through the existing CLI (phases 1–2 in force), paced by the bucket; `freeze` writes `research/wallet_copyability/live_data/evidence/L2_COHORT_T0.json` with `T0` (UTC ms), the sorted cohort, its SHA-256, the frozen plan commit `1833f34`, the stage counts, and exits non-zero without writing the evaluable list when `evaluable < 200` (hard stop). All evaluation intervals are `[T0-52d, T0-7d]` for every wallet.
Acceptance: unit tests for every filter with synthetic fills; a freeze test that refuses at 199 and accepts at 200; counts per stage present.

## Phase 6 — arm A candle fetch at T0 (collector script over phase 3)

Implement: for every in-scope coin, `candles --interval 15m` over `[T0-52d, T0]` (one page of ≤ 5000), paced 2.5 s between requests, coverage recorded; a post-check prints per-coin rows and max gap and lists coins that fail the 15-minute gap bound (they leave scope; the cohort file records them).
Acceptance: dry run with the scripted transport; on the live run, `candles` count per coin ≈ 4992 and max gap 15 min.

## Phase 7 — opening positions and the arm A runner (`src/copyability/execution.py`, `loader.py`, new `research/wallet_copyability/live_data_collector/arm_a_runner.py`)

Implement: `simulate_follower(..., opening_positions: Mapping[str, Decimal] | None)` — the follower opens the source's net position per coin at the first usable price inside the interval (a synthetic catch-up fill, counted in `catch_up_fills`), so a source fill that closes a pre-window position is a real close for the follower; `loader.replay_positions(fills, until_ms)` builds that map from fills before the interval. Runner: `load_candle_prices(store, coins, interval="15m")` in `loader.py` (`PriceSeries` from `close` at `close_time_ms`), `PRICE_SOURCES["candles"]`; `run_study(window=(T0-52d, T0-7d), market_for=lambda w: build_market(price_source="candles"))`, `max_price_age_ms=900_000`; survivorship measurements per the plan; output `evidence/L2_ARM_A_001.json` with rows, refusals, stage counts and diagnostics. The runner writes and does not print any return; arm A's window is closed at T0, so the report may read the file afterwards.
Acceptance: opening-position test (source long from before the window, closes inside: follower realises a close, not an inverted open); candle price loader test; runner dry run on a synthetic store.

## Phase 8 — arm B operational health (collector script)

Implement: `health --cohort path` prints per wallet: last sweep time, fills since T0, funding pages, coverage gaps; per coin: mids gap max, candle gap max; counts of unscorable wallets; never a return or a P&L.
Acceptance: runs on the L1 database without error and prints counts only.

## Phase 9 — review and verification

`code-review` (high) on every file touched in phases 1–8 before any live request; verify each finding against the code; fix; full suite; manifest; commit. Then, in order: discovery sessions, characterisation backfill (background), candle fetch, **first `mids` run and first arm B sweep**, freeze (hard stop check), arm A runner, health check.

The mids poll precedes the freeze deliberately. T0 is the freeze instant, arm B's window opens at T0, and its first usable quote must sit within the 15-minute freshness bound of it. A series that starts after that cannot be repaired once the window is open, so the decisive arm would be unrunnable and nobody would learn it until day 56. The freeze refuses a T0 the poller has not reached, which is what makes this order binding rather than advisory.
