# Threat Model — Hyperliquid Public Probe R1

## Protected assets

- exact reviewed commit and point-in-time evidence identity;
- repository and workflow integrity;
- absence of credentials, private keys and signed actions;
- raw-response confidentiality and minimization;
- correct separation between technical route evidence and market/economic
  claims.

## Trust boundaries

1. reviewed repository bytes;
2. pinned GitHub-hosted actions and runner;
3. the explicitly supplied canonical commit SHA;
4. three public HTTPS origins;
5. in-memory untrusted response bytes;
6. minimized immutable workflow artifact;
7. later independent inspection and attestation.

## Threats and controls

| Threat | Control | Residual limitation |
|---|---|---|
| wrong commit executed | required 40-character SHA, exact checkout and `git rev-parse HEAD` equality | GitHub platform remains trusted |
| hidden credentials | no secret references, no auth/cookie construction, no persisted checkout credential | hosted-runner isolation remains external |
| accidental execution | `/info` and S3 roots only; no action endpoint or signing | future source changes require review |
| origin escape | three-origin allowlist and same-origin redirects | DNS/TLS infrastructure remains external |
| resource exhaustion | byte, timeout, retry, request-count and weight ceilings | remote endpoints may use the full timeout |
| raw data leak | body discarded after hashing/classification | structural metadata remains visible |
| fabricated PASS | exact coverage plus independent status re-derivation | reviewed source/platform compromise remains possible |
| selective omission | exact 16-probe order frozen | unregistered routes remain outside R1 |
| S3 error misread as inventory | separate archive-access status | requester-pays access remains unresolved |
| identity overclaim | fixture addresses are technical examples only | operational control can change or be shared |
| technical PASS promoted to alpha | project, evidence and authorization gates remain closed | human governance failure remains possible |

## Terminal incident rule

The run fails on any credential capability, unapproved origin, cross-origin
redirect, action endpoint, signing/order capability, missing or reordered
observation, unexplained hash mismatch, capacity excess or core response-class
failure.

Repairs require a new exact commit and distinct run. Historical evidence is not
overwritten or silently reclassified.
