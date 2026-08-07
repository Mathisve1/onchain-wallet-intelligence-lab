# Cost-Controlled Architecture

## Phase-specific cost discipline

### Public technical probe

The R1 probe performs exactly 18 requests, retains no raw response body and uses
only GitHub-hosted CI already available to the repository. Its expected marginal
cash cost is zero apart from negligible private-repository Actions and artifact
storage usage within the account plan.

The workflow retains one small JSON artifact for 30 days. No AWS credential,
requester-pays download or server is authorized in this phase.

### Archive inventory

Before downloading any historical object, the inventory phase must estimate:

- S3 request and requester-pays transfer costs;
- compressed and estimated expanded bytes;
- temporary compute and scratch storage;
- permanent raw retention;
- derived Parquet storage;
- backup and egress; and
- rerun costs.

No bulk command may run until a maximum euro budget and a hard byte ceiling are
frozen.

## Discovery

Process each venue event once. Extract participating addresses and update compact
wallet state. Never poll every possible address.

## Tiers

### Cold

Address, first/last seen, event counts, estimated volume and basic service flags.

### Warm

Rolling P&L, funding, fees, holding periods, drawdown, leverage, concentration,
liquidations and style features.

### Hot

Only qualified wallets/clusters receive low-latency fills, current positions,
copy markouts and signal review.

## Candidate generation

Never compare all wallet pairs. Candidate cluster edges require direct graph or
behavioural evidence and are generated with local neighborhoods or approximate
similarity methods before exact scoring.

## AI usage

No LLM per fill. Deterministic filters reduce the stream to a small review queue.
AI may then assess hidden-hedge arguments, market context and reasons not to
copy. An unavailable AI review leaves the candidate pending and cannot create an
execution authorization.

## Infrastructure progression

1. bounded public technical probe;
2. metadata-only archive inventory and cost estimate;
3. separately released small raw-data pilot;
4. bounded live watchlist;
5. research-grade analytical server;
6. non-validator node only when measured latency value justifies its cost; and
7. redundancy only after shadow evidence.
