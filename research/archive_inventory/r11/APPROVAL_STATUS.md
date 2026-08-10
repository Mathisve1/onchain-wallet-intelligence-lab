# R11 approval status

Status: `AWAITING_SEPARATE_HUMAN_APPROVAL`

Pilot: `HL-ARCHIVE-R11-72H-PERSISTENCE-SCALING-001`

R11 is a static preregistration only. It performs no AWS/IAM/OIDC action, no Requester Pays request, no object download, no decompression, no wallet-feature processing and no trading action.

The proposed future pilot covers exactly 72 modern hourly objects spanning the three complete UTC days 2025-07-28 through 2025-07-30. It extends the proven R10D record-anchored reducer only by `active_day_count`. The three-day window is explicitly a scale/persistence mechanics test, not sufficient performance history and not a wallet-ranking study.

Human approval is required before implementation. Approval would also permit creation of a new dedicated R11 role, but would still not authorize the data execution; operator attestation, S3-denied STS preflight, a separate execution release and separate canonical activation remain mandatory.
