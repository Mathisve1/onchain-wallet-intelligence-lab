# Hyperliquid Public Probe R1

`HL-PUBLIC-PROBE-001R1` is the first executable technical gate of `WALLET-COPYABILITY-STUDY-001`.

It tests only public, read-only Hyperliquid information and official archive routes. It never authenticates, signs or submits an action. Raw response values are not persisted; evidence contains only hashes, coarse response classes, timing, counts and bounded error metadata.

## Final capacity-safe scope

- 16 total registered requests;
- no unbounded `userFills` request;
- fills, funding and non-funding ledger use one fixed 24-hour window;
- declared base API weight: `586`;
- two-attempt worst-case declared API weight: `1,172`;
- published planning budget captured by the contract: `1,200` per minute;
- safety margin: `28` weight units;
- S3 routes do not consume the `/info` API budget.

The declared weights are conservative governance estimates for keeping this exact probe below the published budget. They are not a claim about future rate-limit rules or actual billing.

## Package

- `PROBE_CONTRACT.json` — routes, fixtures, response classes, weights, limits and security boundary;
- `METHODOLOGY.md` — claim ceiling and derived decision rules;
- `CAPACITY_MODEL.md` — exact request/weight arithmetic;
- `OFFICIAL_SOURCE_MAP.md` — official source hierarchy and deferred questions;
- `THREAT_MODEL.md` — assets, attacks and fail-closed controls;
- `DATA_MINIMIZATION.md` — in-memory raw-response and artifact policy;
- `contract.py` — strict contract loader and request binding;
- `http_client.py` — bounded same-origin transport and response classifier;
- `probe.py` — public collector and derived states;
- `validate_evidence.py` — independent evidence validator;
- `validate_attestation.py` / `validate_attestation_strict.py` — exact later run/artifact binding;
- `PENDING_EVIDENCE.json` / `ATTESTATION_TEMPLATE.json` — explicit non-result placeholders;
- `RUNBOOK.md`, `INCIDENT_RESPONSE.md`, `EVIDENCE_DICTIONARY.md`, `DECISION_RECORD.md` and `STATUS.md` — operational governance.

## Terminal states

- `PUBLIC_PROBE_PASS`
- `PUBLIC_PROBE_PARTIAL`
- `PUBLIC_PROBE_FAIL`

Archive access is derived separately as `LISTINGS_AVAILABLE`, `ROUTES_CONFIRMED_ACCESS_RESTRICTED` or `ARCHIVE_ROUTE_FAILURE`.

A successful R1 result permits only a separately reviewed archive-inventory proposal. It does not release market data, calculate wallet P&L, prove copyable alpha or authorize trading.
