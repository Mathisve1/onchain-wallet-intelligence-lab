# Technical probe evidence

This directory stores exact, reviewed outputs of bounded public technical probes.
It never stores raw account, fill, order-book or ledger response bodies.

Every committed run file must be referenced by
`../TECHNICAL_PROBE_EVIDENCE.json`, match its SHA-256, and pass
`governance/validate_probe_evidence.py`.

A run file is technical capability evidence only. It is not a market dataset,
wallet-performance result, backtest or trading authorization.
