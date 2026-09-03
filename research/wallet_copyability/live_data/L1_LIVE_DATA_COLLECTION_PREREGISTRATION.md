# HL-LIVE-DATA-COLLECTION-L1-001

Status: `PREREGISTERED_NO_EXECUTION`.

This document freezes what a read-only live observation session may do before
any such session is authorized to run. Writing it executes nothing: no request
is sent, no database row is written and no authorization is opened. The
machine-readable contract is `L1_LIVE_DATA_COLLECTION_PREREGISTRATION.json` and
it is the binding form; where this prose and that JSON disagree, the JSON wins.

## Why this pilot exists separately

The archive track reconstructs wallet history from the Hyperliquid S3 archive
and is blocked at R11, whose consumed run produced no wallet features and whose
duplicate root cause is still unknown. That blockage is about historical
reconstruction. It says nothing about whether a forward-looking observer can
accumulate the same ledger going forward from a public endpoint.

L1 tests exactly that, and it shares nothing with the archive track: no AWS
identity, no IAM role, no Requester Pays budget, no release and no single-use
window. Its worst case costs EUR 0 because the endpoints are public and
unauthenticated. Progress here does not unblock R11, and R11 does not gate this.

## Exact boundary

The observer contacts two addresses and no others:

- `POST https://api.hyperliquid.xyz/info`
- `wss://api.hyperliquid.xyz/ws`

`/info` is the only REST path the code can build. The allowlist is a
single-element frozen set and no `/exchange` path string exists anywhere in the
package. This matters more than a disabled flag: the write capability is absent
from the codebase rather than switched off in it, so there is no configuration
that turns this observer into a trader.

Seven informational request types are permitted: `allMids`,
`clearinghouseState`, `meta`, `openOrders`, `userFills`, `userFillsByTime` and
`userFunding`. `l2Book` carries a documented weight but is deliberately excluded
from the supported set. Full order-book depth is not needed to build a wallet
ledger, and collecting it would widen the retained surface for no research gain.

Nothing here holds a credential, a private key or a signing routine. There is no
code path that produces a signature, and therefore no code path that the venue
would accept as an action.

## Request envelope

The venue documents an aggregated 1200 weight per minute per IP. The observer
enforces that same figure rather than a looser local one, and it charges retries
against the budget, so a retry storm consumes the allowance instead of hiding
inside it. At most three retries are attempted, and only HTTP 429 is treated as
retryable; every other non-2xx status fails immediately rather than being
hammered.

At most ten wallets may be tracked in one session. That is not a comfort limit:
the venue caps distinct users across user-scoped websocket subscriptions at ten,
and the same cap bounds the position-snapshot cost. At the default 60-second
snapshot cadence, ten wallets cost 10 x 2 = 20 weight per minute against the
1200 budget, roughly 1.7 percent, which leaves the backfill path the room it
needs without approaching the ceiling.

The websocket heartbeat fires at 50 seconds because the server closes a
connection silent for 60. HTTP redirects are never followed.

## What is retained

A local SQLite database at schema version 2, with seven tables: `wallets`,
`fills`, `positions_snapshot`, `mids`, `funding`, `ingest_runs` and
`schema_version`. Writes are idempotent, so re-observing the same fill does not
double-count it, and each run records its own coverage so a gap is visible as a
gap rather than as silence.

Raw response bodies are not retained. Only parsed, typed rows are, which keeps
the retained surface to the fields the study actually declared it needs.

Wallet addresses are public venue identifiers and are stored as such. No
real-world identity claim is made or permitted, no personal data is collected,
and nothing here is authorized for redistribution.

## What this preregistration does not do

It does not approve a run. Execution requires, in order and separately: one
hash-bound owner approval of this exact envelope; one single-use execution
release bound to the canonical implementation commit; and only then one
operator-initiated session. Canonical merge of the implementation is not an
execution release. No workflow may be installed, and no scheduled or unattended
execution is authorized at any point in this stage.

It also creates no research result. Wallet ranking, alpha interpretation,
copyability claims, entity clustering and backtest publication all remain
unauthorized and are gated behind Phase 3 passing on its own terms. Every
trading authorization stays false, and no code in this package sets one to true.

## Stop conditions

A session halts on any of: weight budget exhausted; retry limit reached; maximum
watch iterations reached; a non-retryable HTTP status; a database schema version
newer than the code supports; the tracked-wallet cap exceeded; or any trading
authorization observed open. The last one is deliberate. An externally supplied
`True` fails closed at config construction rather than being trusted.
