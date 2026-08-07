# Hyperliquid Public Probe R1

`HL-PUBLIC-PROBE-001R1` is the first executable gate of `WALLET-COPYABILITY-STUDY-001`.

It checks only public, read-only Hyperliquid information and archive routes. It never authenticates, signs or submits an action. Raw account and market response values are not persisted; the evidence file stores response hashes, response shapes, timing and bounded aggregate metadata only.

## Files

- `PROBE_CONTRACT.json` — frozen route, limit, evidence and security contract;
- `METHODOLOGY.md` — estimand, evidence minimization and decision rules;
- `contract.py` — strict contract loading and placeholder resolution;
- `probe.py` — bounded public network collector;
- `validate_evidence.py` — independent fail-closed evidence validation;
- `PENDING_EVIDENCE.json` — non-result placeholder before the governed run.

## Terminal states

- `PUBLIC_PROBE_PASS`
- `PUBLIC_PROBE_PARTIAL`
- `PUBLIC_PROBE_FAIL`

A pass does not open a market-data partition or prove copyable alpha. It only permits a separate archive-inventory proposal.

## Local checks

```bash
python -m unittest discover -s tests -v
python research/wallet_copyability/probe_r1/validate_evidence.py \
  --contract research/wallet_copyability/probe_r1/PROBE_CONTRACT.json \
  --evidence research/wallet_copyability/probe_r1/PENDING_EVIDENCE.json \
  --allow-pending
python governance/validate_repository.py
```

The public network probe is executed only through the dedicated read-only GitHub Actions workflow or an equivalently reviewed environment.
