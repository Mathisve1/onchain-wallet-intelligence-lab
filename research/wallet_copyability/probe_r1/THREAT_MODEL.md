# Threat Model — Hyperliquid Public Probe R1

## Protected assets

- repository/workflow integrity;
- exact reviewed commit and point-in-time evidence identity;
- absence of credentials, private keys and signed actions;
- raw-response confidentiality and minimization;
- correct separation between route availability and economic evidence.

## Trust boundaries

1. reviewed repository bytes;
2. pinned GitHub-hosted runner actions;
3. three public HTTPS origins;
4. in-memory untrusted response bytes;
5. minimized immutable workflow artifact;
6. later human attestation and clean-context review.

## Threats and controls

| Threat | Control | Residual limitation |
|---|---|---|
| hidden credential use | no secret references, read-only permission, no persisted checkout credential, no auth/cookie construction | hosted-runner isolation remains trusted |
| accidental execution | exact `/info` and S3 routes only; no `/exchange`, signing, orders or withdrawals | future source changes still require review |
| origin escape | three-origin allowlist and same-origin redirects | DNS/TLS infrastructure remains external |
| resource exhaustion | byte, timeout, retry, request-count and declared-weight ceilings | remote endpoint can consume full timeout |
| raw wallet-data leak | response bodies stay in memory and are discarded | schema existence/counts remain visible |
| fabricated PASS | exact order/coverage and states independently re-derived | reviewed source/platform compromise remains possible |
| selective omission | all 16 probe IDs and order are frozen | unregistered routes remain outside R1 |
| later evidence insertion | per-request timestamps and commit/run/artifact/output hashes | server provides no cryptographic time attestation |
| S3 error misread as completeness | separate archive-access state | inventory still requires requester-pays/access design |
| identity overclaim | fixture addresses are technical examples; natural-person claims forbidden | operational control may change or be shared |
| understated API weight | response-rich endpoints receive conservative declared weights; exact two-attempt sum is checked | official rate rules may later change |
| technical PASS promoted to trade signal | data/result/authorization gates remain closed | human governance failure remains possible |

## Terminal incident rule

Credentials, a non-allowlisted origin, cross-origin redirect, `/exchange`, signing, order/withdrawal capability, missing observation, unexplained hash mismatch, capacity excess or core response-class failure produces `PUBLIC_PROBE_FAIL`. Repair requires a new exact commit and run; historical evidence is never overwritten.
