# Hyperliquid Public Probe R1

`HL-PUBLIC-PROBE-001R1` is the first executable technical gate of
`WALLET-COPYABILITY-STUDY-001`.

This directory contains **implementation and preregistration only**. The real
public probe must run later from the exact canonical `main` commit produced by
merging this implementation. No workflow result, artifact identity or terminal
status is accepted in this branch.

## Scope

The collector can construct exactly 16 public read-only requests:

- 13 Hyperliquid `/info` requests;
- three official S3 archive-route requests;
- one fixed UTC day for historical fills, funding and non-funding ledger shape;
- no unbounded `userFills` request.

The frozen planning model is:

```text
base declared /info weight       586
maximum attempts per route         2
worst declared /info weight     1,172
captured planning budget        1,200
contract ceiling                1,180
maximum HTTP requests              36
registered two-attempt worst case  32
```

## Exact-SHA execution

The workflow is manual-only and requires a 40-character `reviewed_commit`
input. It checks out that SHA, runs `git rev-parse HEAD`, and fails unless the
observed commit is exactly equal. `github.sha` and GitHub's temporary pull
request merge ref are not acceptable substitutes.

The intended sequence is:

1. merge this implementation-only PR to `main`;
2. select the exact resulting canonical `main` SHA;
3. manually dispatch `Hyperliquid Public Probe R1` with that SHA;
4. independently inspect and hash the artifact;
5. open a separate evidence/attestation PR;
6. only after that evidence PR passes may an archive-inventory proposal be
   considered.

## Security boundary

- no credentials, secrets, cookies or authorization headers;
- no private keys or signing;
- no `/exchange`, order, cancellation, withdrawal or transfer action;
- three exact HTTPS origins;
- same-origin redirects only;
- bounded time, bytes, retries, request count and declared weight;
- raw response bodies processed in memory and discarded;
- repository workflow permission limited to `contents: read`;
- all market, paper, shadow, live, leverage and capital authorizations false.

## Evidence boundary

Retained output may contain request/response hashes, timing, HTTP status,
response length, content type, coarse JSON/S3 class, top-level keys/counts,
bounded item types, retry count, declared weight and error class.

It may not retain balances, positions, exact fills, prices, sizes, fees,
funding, P&L, transfers, vault participants, raw order-book levels, credentials
or identity claims.

## Files

- `PROBE_CONTRACT.json` — frozen routes, fixtures, limits and status rules;
- `contract.py` — strict contract validation and request binding;
- `http_client.py` — bounded same-origin transport and body classification;
- `probe.py` — collector and derived terminal/access states;
- `validate_evidence.py` — independent result validation;
- `validate_attestation*.py` — exact later commit/run/job/artifact binding;
- `PENDING_EVIDENCE.json` and `ATTESTATION_TEMPLATE.json` — explicit
  non-results;
- `evidence/` — negative engineering lineage only in this implementation PR.

A successful later route-level probe does not prove archive completeness,
wallet skill, copyability, alpha, profitability or execution readiness.
