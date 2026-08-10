# R11 — 72-hour persistence scaling preregistration

R11 is the first post-R10D historical scaling gate. It selects three complete, contiguous, post-boundary modern UTC days (2025-07-28 through 2025-07-30), exactly 72 immutable hourly objects from the canonical R3 inventory.

The purpose is to prove ingestion scale, record-anchored alignment and deterministic cross-day persistence mechanics. It adds `active_day_count` to the R10D aggregate row but does not rank wallets or claim account return, alpha or copyability.

No network request or IAM mutation occurs in this preregistration.
