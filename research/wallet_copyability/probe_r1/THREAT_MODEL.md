# Threat Model — Hyperliquid Public Probe R1

## Protected assets

- repository and workflow integrity;
- exact reviewed commit and point-in-time evidence identity;
- absence of private keys, credentials and signed actions;
- raw-response confidentiality and minimization;
- the distinction between route availability and economic evidence.

## Trust boundaries

1. reviewed repository bytes;
2. pinned GitHub-hosted runner actions;
3. three public HTTPS origins;
4. in-memory untrusted response bytes;
5. minimized immutable workflow artifact;
6. later human attestation and clean-context review.

## Threats and controls

| Threat | Primary control | Residual limitation |
|---|---|---|
| Hidden credential use | no secret reference, read-only permission, no persisted checkout credential or Authorization/Cookie construction | hosted-runner isolation remains trusted |
| Accidental execution | exact `/info` and S3 routes only; no `/exchange`, signing, order or withdrawal code | future changes still require review |
| Redirect to attacker origin | same-origin redirect handler | DNS/TLS infrastructure remains external |
| Resource exhaustion | byte, timeout, retry, request-count and weight ceilings | a remote route can consume the full timeout |
| Raw wallet data leakage | bodies stay in memory and are discarded; artifacts store hashes and coarse classes | schema existence and counts remain visible |
| Fabricated PASS | exact ordered coverage and terminal state are re-derived | reviewed source/platform compromise remains possible |
| Selective omission | all 17 IDs/order are frozen | unregistered routes remain outside R1 |
| Later data inserted into old run | per-request timestamps plus commit/run/artifact/output hashes | server supplies no cryptographic time attestation |
| S3 error mistaken for completeness | separate archive-access status | inventory still requires requester-pays/access design |
| Wallet identity overclaim | fixtures are documentation examples; natural-person claims forbidden | operational control may change or be shared |
| Technical PASS promoted to trading signal | market data/result/authorizations remain closed | human governance failure remains possible |

Credentials, a non-allowlisted origin, cross-origin redirect, `/exchange`, signing, order/withdrawal path, missing observation, unexplained hash mismatch, capacity excess or core route-class failure produces `PUBLIC_PROBE_FAIL`. Repair requires a new exact commit and run.
