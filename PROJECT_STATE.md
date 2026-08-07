# Project State

Verified: 2026-08-07 against canonical `main` and implementation PR #7.

## Current status

| Dimension | State |
|---|---|
| program | `ONCHAIN-WALLET-INTELLIGENCE` |
| current study | `WALLET-COPYABILITY-STUDY-001` |
| research status | `REQUIRES_FURTHER_TESTING` |
| lifecycle stage | `PRE_DATA` |
| experiment status | `PREREGISTERED_NO_MARKET_RELEASE` |
| public-probe implementation | `PENDING_MERGE_TO_CANONICAL_MAIN` |
| canonical public-probe result | `PENDING_CANONICAL_MAIN_RUN` |
| empirical result | `null` |
| integration authorized | `false` |
| paper authorized | `false` |
| shadow authorized | `false` |
| live authorized | `false` |
| leverage authorized | `false` |
| capital allocation authorized | `false` |

## Exact next gate

1. Merge the reviewed read-only `HL-PUBLIC-PROBE-001R1` implementation to
   canonical `main` without adding final run evidence.
2. Dispatch the installed workflow from `refs/heads/main` with the exact current
   `main` SHA, which must equal GitHub's dispatch SHA and the checked-out commit.
3. Freeze the new run, job, artifact and output identities through a separate
   immutable evidence/attestation pull request.
4. Only after exact evidence and clean-context review may a separate official
   archive-inventory proposal be considered.
5. Build and reconcile a deterministic wallet ledger only after a later reviewed
   historical-data release decision.

No archive inventory, bulk object download, analytical market partition, wallet
performance calculation or execution stage is currently open.

Entity-resolution research remains downstream of individual-wallet copyability.
No probabilistic wallet merge may create false consensus in the first study.
