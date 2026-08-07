# Hyperliquid Public Probe R1

`HL-PUBLIC-PROBE-001R1` is the first executable gate of `WALLET-COPYABILITY-STUDY-001`.

It checks only public, read-only Hyperliquid information and archive routes. It never authenticates, signs or submits an action. Raw response values are not persisted; evidence contains response hashes, coarse shapes, timing and bounded aggregate metadata only.

## Package

- `PROBE_CONTRACT.json` — frozen routes, limits, evidence and security boundary;
- `METHODOLOGY.md` — estimand and decision rules;
- `contract.py` — strict contract loading, hashing and placeholder resolution;
- `http_client.py` — bounded same-origin HTTP transport;
- `probe.py` — public network collector;
- `validate_evidence.py` — independent fail-closed validator;
- `PENDING_EVIDENCE.json` — non-result placeholder.

## Terminal states

- `PUBLIC_PROBE_PASS`
- `PUBLIC_PROBE_PARTIAL`
- `PUBLIC_PROBE_FAIL`

A pass does not release market data or prove copyable alpha. It only permits a separately reviewed archive-inventory proposal.
