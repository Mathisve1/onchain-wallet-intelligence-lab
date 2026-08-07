# Threat Model — Hyperliquid Public Probe R1

## Protected assets

- repository integrity;
- GitHub workflow identity and exact reviewed commit;
- absence of private keys, credentials and signed actions;
- point-in-time evidence integrity;
- response privacy and data minimization;
- the distinction between technical availability and economic evidence.

## Trust boundaries

1. GitHub repository and pinned workflow source;
2. GitHub-hosted runner;
3. public HTTPS endpoints on three allowlisted origins;
4. in-memory raw response bytes;
5. minimized evidence artifact;
6. later human review and attestation.

The public endpoint is an untrusted data source. A successful TLS/HTTP response is not assumed to be complete, economically meaningful or stable.

## Threats and controls

| Threat | Control | Residual risk |
|---|---|---|
| Hidden credential use | workflow has no secrets reference, checkout credentials are not persisted, Authorization/Cookie headers are absent | runner platform is still trusted for process isolation |
| Accidental order submission | only `/info` and exact S3 routes are constructible; `/exchange`, signed actions, withdrawals and orders are forbidden by contract/tests | future files must remain under review and CI |
| Redirect to attacker origin | custom same-origin redirect handler blocks origin changes | DNS/TLS infrastructure remains externally trusted |
| Unbounded response or resource exhaustion | hard response-byte, timeout, retry, request-count and declared-weight ceilings | remote server can remain slow until timeout |
| Raw wallet information leaking into artifacts | raw bodies are parsed in memory and discarded; artifact keeps hashes and coarse shapes only | top-level keys and element counts can still reveal schema existence |
| Manually fabricated PASS | terminal state is independently re-derived from exact ordered observations | workflow platform or reviewed source compromise remains possible |
| Selective omission of failed probes | exact 17-probe ordered coverage is required | a documented route not registered in R1 remains outside scope |
| Response replay or later evidence insertion | each observation records request start/completion and output is bound to commit/run/artifact hashes | public endpoint does not provide cryptographic server attestation |
| S3 denial interpreted as complete archive access | R1 claims route/response-class evidence only; inventory and completeness are separate gates | a route-level PASS can coexist with requester-pays or access work still required |
| Wallet identity overclaim | fixture addresses are documentation examples and real-world identity claims are forbidden | address ownership may change or be operationally shared |
| Technical PASS promoted to trading signal | status documents explicitly keep market data, empirical result and every authorization closed | human governance failure remains possible and requires review |

## Incident rule

Any appearance of credentials, an Authorization/Cookie header, a non-allowlisted origin, `/exchange`, a signed action, an order/withdrawal path, incomplete evidence coverage or unexplained hash mismatch is a terminal `PUBLIC_PROBE_FAIL`. Repair requires a new exact commit and rerun; historical evidence is not overwritten.
