# R11A dedicated-role decision

## Decision

R11A will use a **new dedicated successor role** named
`onchain-wallet-intelligence-hl-archive-identity-r11a` if and only if a later
owner approval explicitly authorizes its creation and a separate operator
attestation proves that its installed trust and permission documents match the
canonical repository bytes.

The existing R11 role is not reused and is not mutated.

## Why a successor role is preferred

The existing R11 role is bound by its OIDC trust policy to the workflow name
`Hyperliquid Archive 72H Persistence Scaling R11`. Reusing it would require the
R11A workflow to impersonate that historical workflow name, or would require a
trust-policy mutation. The former weakens provenance and the latter changes a
consumed parent execution identity. A distinct role keeps the R11A diagnostic,
its future session name, its release and its evidence lineage independently
identifiable.

The successor role does **not** widen object access. Its persistent permission
candidate contains the exact same 72 object ARNs as the canonical R11
selection. The future session policy may allow only `s3:GetObject` on the three
already approved date prefixes, which can only intersect the exact persistent
72-object allowlist.

## Current authority

This decision is an inert implementation choice only.

- role creation: not authorized;
- trust or permission mutation: not authorized;
- AWS OIDC or STS: not authorized;
- S3 access: not authorized;
- existing R11 role mutation: forbidden;
- owner approval: absent;
- workflow installation, release and activation: absent.

A later approval must bind the exact role name, ARN, trust-policy SHA-256,
permission-policy SHA-256, 72-resource count, session duration and zero
additional policy condition. A separate S3-denied STS-only preflight should be
performed before any R11A object request.
