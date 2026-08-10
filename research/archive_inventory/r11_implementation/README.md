# R11 implementation

This directory freezes the owner-approved implementation of `HL-ARCHIVE-R11-72H-PERSISTENCE-SCALING-001`.

It contains a dedicated GitHub OIDC trust policy, a deterministic exact-72-object persistent permission policy generator, role-creation runbook and operator-attestation template, an inert STS-only preflight workflow candidate, an inert 72-hour data workflow candidate, and the record-anchored R11 collector with `active_day_count`.

No R11 role is created by this implementation PR. No workflow is installed under `.github/workflows/`, no OIDC/STS/S3 request is executed, no object is downloaded, and no wallet feature is empirically retained. After canonical merge the next gate is manual creation of the exact dedicated R11 role and a separate operator attestation. Only after that may a separately released S3-denied STS preflight be considered.

The three-day window remains a scaling/persistence mechanics test only. Wallet ranking, candidate shortlisting, PnL/alpha, copyability, enrichment, clustering, strategy work and all trading/leverage/capital authority remain closed.
