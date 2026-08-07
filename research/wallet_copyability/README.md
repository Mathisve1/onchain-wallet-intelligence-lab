# WALLET-COPYABILITY-STUDY-001

Status: `PRE_DATA_INTAKE_FROZEN_NO_MARKET_RELEASE`.

The study asks whether a point-in-time-selected directionally trading wallet can
be followed profitably after the follower's real execution disadvantage.

## Initial scope

- venue: Hyperliquid public mainnet data;
- product: perpetuals;
- instruments: BTC, ETH and SOL;
- initial independence handling: confirmed relationships only;
- latency cases: 1 s, 5 s, 30 s, 2 m, 5 m and 15 m;
- market data release: closed;
- empirical result: absent.

## Active pre-data gate

`HL-PUBLIC-PROBE-001R1` is the first executable gate. It verifies 18 registered
public routes covering metadata, market structure, documented account
relationships, current account state, fees, fills, funding, ledger updates,
vault details and official archive access behavior.

The probe does not preserve raw responses or response values. Its exact scope,
terminal decisions and evidence lifecycle are defined in:

- `PROBE_CONTRACT.json`;
- `PROBE_METHODOLOGY.md`;
- `TECHNICAL_PROBE_EVIDENCE.json`; and
- `evidence/README.md`.

The first deliverable is technical and forensic evidence, not a performance
backtest.
