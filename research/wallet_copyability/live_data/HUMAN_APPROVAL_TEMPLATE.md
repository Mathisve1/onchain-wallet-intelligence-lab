# L1 human approval template

Approval is a human act. Nothing in this repository may write, generate or infer
it. To approve, the owner sends the exact approval text below, unmodified, and
that text is then recorded with its SHA-256 and the preregistration commit it
binds to.

An approval that does not bind an exact 40-character commit is not an approval.
An approval whose envelope differs in any value from the preregistration is not
an approval for that preregistration.

## Exact approval text

Replace `<PREREGISTRATION_COMMIT>` with the exact 40-character commit of the
canonical `L1_LIVE_DATA_COLLECTION_PREREGISTRATION.json`. Change nothing else.

```
APPROVE_HL_LIVE_DATA_COLLECTION_L1_001
preregistration_commit=<PREREGISTRATION_COMMIT>
venue=HYPERLIQUID_PUBLIC_MAINNET
rest_endpoint=https://api.hyperliquid.xyz/info
websocket_endpoint=wss://api.hyperliquid.xyz/ws
authentication=NONE
maximum_one_time_budget_eur=0
maximum_monthly_budget_eur=0
enforced_weight_budget_per_minute=1200
maximum_retries_per_request=3
retryable_http_statuses=429
retries_charged_against_weight_budget=true
request_timeout_seconds=10
maximum_tracked_wallets=10
snapshot_interval_seconds=60
websocket_heartbeat_seconds=50
maximum_watch_iterations=1000
http_redirect_following_authorized=false
rest_request_types=allMids,clearinghouseState,meta,openOrders,userFills,userFillsByTime,userFunding
order_endpoint_authorized=false
signed_action_authorized=false
credential_use_authorized=false
workflow_installation_authorized=false
scheduled_execution_authorized=false
wallet_ranking_authorized=false
copyability_claim_authorized=false
trading_authorizations=ALL_FALSE
```

## What this approval opens

Exactly one thing: the implementation review and single-use release stage for a
read-only observation session inside the envelope above.

## What it does not open

It does not authorize a run by itself; a separate single-use execution release
bound to the canonical implementation commit is still required. It does not
install a workflow, authorize scheduled or unattended execution, permit any
authenticated or signed request, or open any wallet-ranking, copyability or
trading authorization. It grants no AWS, S3, Requester Pays or archive authority
of any kind, and it does not touch the R11 or R11A envelopes.

## Recording an approval

Once the exact text is received, record it as a new `DEC-` row in
`DECISION_LOG.md` with the approval text SHA-256 and the bound commit, add the
matching rows to `PROJECT_STATE.md`, and update the `owner_approval_status`
block of `L1_LIVE_DATA_COLLECTION_PREREGISTRATION.json` in the same reviewed
change. Do not backfill an approval into an existing row.
