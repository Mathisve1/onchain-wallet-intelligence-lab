# R8 — performance and copyability data design

## Decision

R8 is a **static architecture and data-minimization study**. It does not rank the 4,637 R7 wallets, query their public API state, download another archive object or authorize trading.

The project should not jump from `wallet_address + fill_count` to a profitability leaderboard. One hour of activity is a discovery signal only. The next evidence chain must separate four different questions:

1. **Is the wallet persistently active?**
2. **Does its historical trading evidence look economically attractive?**
3. **Is the account context compatible with a meaningful return calculation?**
4. **Would a follower have been able to copy the trades after latency, fees, spread and slippage?**

A wallet must survive those questions in order. A high absolute PnL number by itself is not enough.

## Why the archive is the first-pass data source

Hyperliquid's official node documentation states that `--write-fills` writes API-format fills, and `--batch-by-block` wraps those events in block records. The official historical-data documentation exposes these fills through `node_fills` and `node_fills_by_block`.

The public `userFills` endpoints are useful for an individual wallet, but they are a poor population-discovery primitive: they are per-address, capped per response, and `userFillsByTime` only exposes the 10,000 most recent fills. The official rate-limit documentation also assigns request weight to these calls. R8 therefore chooses **global archive scan first, per-wallet API enrichment second**.

This is a project architecture inference, not a claim that Hyperliquid officially recommends our exact research pipeline.

## Minimum archive field set

The first historical candidate screen should retain no more record-derived fields than necessary:

| Field | Why it is needed | Allowed initial use |
|---|---|---|
| `wallet_address` | grouping key | wallet-level aggregation |
| `time` | chronology | active hours/days, persistence |
| `coin` | instrument | asset breadth and per-asset statistics |
| `side` | trade side | buy/sell counts; official notation says trade side is aggressing side |
| `dir` | position transition label | open/close direction counts |
| `px` | execution price | notional proxy with `sz` |
| `sz` | base-asset size | notional proxy with `px`, size distribution |
| `startPosition` | pre-fill position context | transition/integrity checks |
| `closedPnl` | fill-level economic statistic | screening statistic only, **not exact account return** |
| `fee` | execution cost evidence | fee diagnostics; do not double-subtract from `closedPnl` without a proven formula |
| `feeToken` | fee denomination | prevent invalid cross-token summation |
| `tid` | trade identifier | deterministic duplicate detection |
| `crossed` | boolean present in fill schema | retain only as an uninterpreted boolean until its exact maker/taker semantics are separately proven |
| liquidation presence | risk/event flag | count associated fills, without retaining liquidation payload values initially |

`hash`, `oid`, `cloid`, `builder`, and `builderFee` are not needed for the first candidate screen and should remain excluded unless a later study demonstrates a concrete need.

## What `closedPnl` can and cannot tell us

Official Hyperliquid documentation describes entry price, unrealized PnL and closed PnL as frontend convenience components; fundamental accounting is based on balances/margin and trades. The documented perp formula also incorporates fees into closed PnL. Therefore:

- summing `closedPnl` can be a **fill-derived candidate statistic**;
- it must not be labeled exact wallet return, ROI or alpha;
- a separate fee series may be useful diagnostically, but it must not automatically be subtracted again from closed PnL;
- account-level performance research eventually needs account-value/PnL context and must consider deposits/withdrawals and other components not represented by a fill-only statistic.

## Shortlist enrichment instead of 4,637-wallet brute force

The official `portfolio` endpoint exposes account-value history, PnL history and volume for several horizons. `clearinghouseState` exposes current perp account and margin state. `userRole` can distinguish roles such as User, Agent, Vault and Subaccount. These endpoints are useful after archive screening, but R8 does not authorize calling them yet.

The API rate-limit documentation makes a full brute-force enrichment pass unattractive: most `info` requests consume weight 20, `userRole` consumes weight 60, and fill-history endpoints have additional returned-item weight. The correct architecture is therefore to shrink the population first and query richer per-wallet endpoints only for a bounded shortlist.

## Performance research must keep separate metric classes

A later preregistration may compute the following **candidate features**, but R8 itself computes none of them:

### Activity and persistence

- active hours and active days;
- first and last observed fill time;
- fills by day/week;
- persistence across multiple market regimes.

### Fill-derived economic statistics

- `px * sz` notional proxy;
- closed-PnL sum as an explicitly labeled fill statistic;
- fees by fee token;
- distributions rather than only totals.

### Behavior and risk

- number of traded assets;
- open/close direction mix;
- buy/sell mix;
- liquidation-associated fill count;
- `crossed` fraction only as an uninterpreted boolean until semantics are proven.

### Account-context enrichment

For a reduced shortlist only:

- portfolio account-value/PnL histories and volume;
- current clearinghouse state;
- account role;
- fee tier/context if needed;
- funding/accounting evidence only if required by the preregistered return definition.

Portfolio histories are sampled and the official documentation explicitly warns they are not precise accounting. Any future drawdown or return metric must therefore state exactly which source and formula it uses.

## Copyability is a separate research problem

A profitable source wallet is not automatically copyable. Copyability eventually requires market/execution evidence such as follower delay, spread, depth, price impact, order size relative to liquidity, turnover, fees and adverse selection. Those inputs are deliberately outside R8.

The future system should first identify robust source-wallet candidates, then run a separate execution/copyability study. It must not train or optimize a follower strategy on metrics that were not available point-in-time.

## Scaling blocker discovered by R8

R3 established that the legacy `node_fills` family ends around the same boundary at which the much larger `node_fills_by_block` family begins. R4 successfully decompressed and structurally parsed the modern boundary object and observed API-fill field paths inside `events`, but it retained no concrete modern address value.

Before spending money on days or months of historical performance data, the project should prove one small thing: **can the modern by-block stream be deterministically reduced to the same address-level wallet-index primitive?**

That becomes R8A: one exact already-known modern boundary object, one Requester Pays `GetObject`, zero retries, and retention limited again to `wallet_address + fill_count`. If R8A succeeds, the data plane is ready for a later bounded multi-hour performance extractor. If it fails, we repair the parser before paying for larger history.

## R8 terminal conclusion

`STATIC_PERFORMANCE_COPYABILITY_DATA_DESIGN_COMPLETE_MODERN_BRIDGE_REQUIRED`

No network, ranking, PnL scoring, copyability scoring, entity clustering or trading authority is opened by this conclusion.
