# Project State

Verified: 2026-08-07 against canonical implementation commit `33683532ca3e6cf7512a728157791d3bfef1375f`.

## Current status

| Dimension | State |
|---|---|
| program | `ONCHAIN-WALLET-INTELLIGENCE` |
| current study | `WALLET-COPYABILITY-STUDY-001` |
| research status | `REQUIRES_FURTHER_TESTING` |
| lifecycle stage | `PRE_DATA` |
| experiment status | `PREREGISTERED_NO_MARKET_RELEASE` |
| public-probe implementation | `INSTALLED_ON_CANONICAL_MAIN` |
| implementation pull request | `#7` |
| implementation commit | `33683532ca3e6cf7512a728157791d3bfef1375f` |
| canonical public-probe result | `PENDING_CANONICAL_MAIN_RUN` |
| empirical result | `null` |
| integration authorized | `false` |
| paper authorized | `false` |
| shadow authorized | `false` |
| live authorized | `false` |
| leverage authorized | `false` |
| capital allocation authorized | `false` |

## Exact next gate

1. Dispatch the installed `Hyperliquid Public Probe R1` workflow from
   `refs/heads/main` with the exact current `main` SHA.
2. The workflow must prove that `inputs.reviewed_commit`, GitHub's dispatch SHA
   and `git rev-parse HEAD` are byte-identical before network access.
3. Independently inspect the workflow, job and immutable artifact and recompute
   the artifact ZIP, internal file and probe-output SHA-256 values.
4. Freeze those exact identities through a separate evidence/attestation pull
   request; no earlier run may be promoted.
5. Only after exact evidence and clean-context review may a separate official
   archive-inventory proposal be considered.

No archive inventory, bulk object download, analytical market partition, wallet
performance calculation or execution stage is currently open.

Entity-resolution research remains downstream of individual-wallet copyability.
No probabilistic wallet merge may create false consensus in the first study.
