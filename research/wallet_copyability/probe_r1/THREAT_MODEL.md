# Threat Model — Hyperliquid Public Probe R1

## Protected assets

- repository and workflow integrity;
- exact reviewed commit and point-in-time evidence identity;
- absence of private keys, credentials and signed actions;
- raw-response confidentiality and data minimization;
- the distinction between route availability and economic evidence.

## Trust boundaries

1. reviewed GitHub repository bytes;
2. pinned GitHub-hosted runner actions;
3. three public HTTPS origins;
4. in-memory untrusted response bytes;
5. minimized immutable workflow artifact;
6. later human attestation and clean-context review.

The public endpoint is untrusted input. An HTTP 200 response is not presumed complete, economically meaningful or stable.

## Threats and controls

| Threat | Primary control | Residual limitation |
|---|---|---|
| Hidden credential use | no secret reference, read-only permission, checkout credentials not persisted, no Authorization/Cookie construction | hosted-runner isolation remains trusted |
| Accidental execution | only exact `/info` and S3 routes are constructible; no `/exchange`, signing, orders or withdrawals | future source changes still require review |
| Redirect to attacker origin | same-origin redirect handler | DNS/TLS infrastructure remains external |
| Resource exhaustion | response-byte, timeout, retry, request-count and weight ceilings | a remote route may consume the full timeout |
| Raw wallet data leakage | bodies remain in memory and are discarded; artifact stores hashes and coarse classes | schema existence and element counts are retained |
| Fabricated PASS | exact ordered coverage and terminal state are independently re-derived | compromised reviewed source/platform remains possible |
| Selective omission | all 17 probe IDs and order are frozen | unregistered routes remain outside R1 scope |
| Later data inserted into old run | per-request timestamps plus commit/run/artifact/output hashes | server does not cryptographically attest its response time |
| S3 error mistaken for archive completeness | separate `archive_access_status`; route PASS is not listing access | archive inventory still requires a later requester-pays/access design |
| Wallet identity overclaim | fixture addresses are documentation examples; natural-person identity claims forbidden | operational control may change or be shared |
| Technical PASS promoted to trading signal | market data, empirical result and every authorization remain closed | human governance failure remains possible |

## Terminal incident rule

Credentials, Authorization/Cookie headers, a non-allowlisted origin, cross-origin redirect, `/exchange`, signed action, order/withdrawal path, missing observation, unexplained hash mismatch, excess capacity or a core route-class failure produces `PUBLIC_PROBE_FAIL`. Repair requires a new exact commit and run; prior evidence is immutable.
