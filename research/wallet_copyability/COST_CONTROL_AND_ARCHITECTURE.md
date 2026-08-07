# Cost-Controlled Architecture

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

1. public API and official archives;
2. bounded live watchlist;
3. research-grade analytical server;
4. non-validator node only when measured latency value justifies its cost;
5. redundancy only after shadow evidence.
