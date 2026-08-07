# Project State

Verified: 2026-08-07 against repository `main` at
`c08f7dc9419857770e53cd760f447394ecfa1bae` and the frozen R1 probe branch.

## Current status

| Dimension | State |
|---|---|
| program | `ONCHAIN-WALLET-INTELLIGENCE` |
| current study | `WALLET-COPYABILITY-STUDY-001` |
| research status | `REQUIRES_FURTHER_TESTING` |
| lifecycle stage | `PRE_DATA` |
| experiment status | `PREREGISTERED_PUBLIC_PROBE_R1_PENDING` |
| technical probe | `HL-PUBLIC-PROBE-001R1` |
| empirical result | `null` |
| market data ingested | `false` |
| integration authorized | `false` |
| paper authorized | `false` |
| shadow authorized | `false` |
| live authorized | `false` |
| leverage authorized | `false` |
| capital allocation authorized | `false` |

## Active gate — public technical probe R1

The exact next operation is the bounded, public, read-only probe defined by:

- `research/wallet_copyability/PROBE_CONTRACT.json`;
- `research/wallet_copyability/PROBE_METHODOLOGY.md`;
- `research/wallet_copyability/scripts/probe_public_api.py`; and
- `.github/workflows/hyperliquid-public-probe.yml`.

The probe contains exactly 18 registered requests and may contact only:

```text
https://api.hyperliquid.xyz
https://hl-mainnet-node-data.s3.amazonaws.com
https://hyperliquid-archive.s3.amazonaws.com
```

It tests public response shape, documented role/subaccount/vault relationships,
a bounded active fill-limit diagnostic and archive access behavior. It records
hashes, schemas and aggregate counts only. Raw response values are not retained.

## Fail-closed outcomes

- `PUBLIC_PROBE_PASS`: proceed to archive object inventory, not to a backtest.
- `PUBLIC_PROBE_PARTIAL`: repair or separately govern archive access and rerun.
- `PUBLIC_PROBE_FAIL`: stop archive and ledger work.

No outcome opens the analytical market-data partition automatically.

## Subsequent gates

1. Freeze the exact probe output, workflow run, numeric job, artifact ID and
   artifact digest.
2. Re-run repository CI on the final evidence commit.
3. Inventory official archive objects, formats, coverage, gaps and requester
   cost without retaining an analytical market dataset.
4. Freeze a raw-retention and schema-version contract.
5. Build and reconcile a deterministic wallet ledger on a separately approved
   small pilot partition.
6. Only after ledger reconciliation decide whether point-in-time performance and
   follower-copyability testing may open.

Entity-resolution research remains downstream of individual-wallet copyability.
No probabilistic wallet merge may create false consensus in the first study.
