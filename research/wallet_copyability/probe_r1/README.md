# Hyperliquid Public Probe R1

`HL-PUBLIC-PROBE-001R1` is the first executable technical gate of `WALLET-COPYABILITY-STUDY-001`.

It tests only public, read-only Hyperliquid information and archive routes. It never authenticates, signs or submits an action. Raw response values are not persisted; evidence contains hashes, coarse response classes, timing, counts and bounded error metadata only.

## Package

- `PROBE_CONTRACT.json` — frozen routes, fixtures, limits, decision rule and security boundary;
- `METHODOLOGY.md` — precise claim, evidence and failure semantics;
- `OFFICIAL_SOURCE_MAP.md` — official source hierarchy and unresolved documentation questions;
- `THREAT_MODEL.md` — assets, trust boundaries, attacks and fail-closed controls;
- `DATA_MINIMIZATION.md` — raw-response and artifact policy;
- `contract.py` — strict contract loader and request binding;
- `http_client.py` — bounded same-origin transport and response classifier;
- `probe.py` — public network collector and derived terminal result;
- `validate_evidence.py` — independent evidence validator;
- `PENDING_EVIDENCE.json` — explicit non-result placeholder;
- `ATTESTATION_TEMPLATE.json` — exact future workflow/run/job/artifact binding;
- `STATUS.md` — current closed gate.

## Terminal states

- `PUBLIC_PROBE_PASS`
- `PUBLIC_PROBE_PARTIAL`
- `PUBLIC_PROBE_FAIL`

`archive_access_status` is separately derived. A route-level `PASS` can coexist with `ROUTES_CONFIRMED_ACCESS_RESTRICTED`; that is not an archive inventory.

A successful R1 result permits only a separately reviewed archive-inventory proposal. It does not release market data, calculate wallet P&L or prove copyable alpha.
