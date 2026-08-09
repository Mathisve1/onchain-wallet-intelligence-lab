# R8B — legacy/modern cutover forensics

## Result

**`HIGH_CONFIDENCE_WITHIN_HOUR_FORMAT_CUTOVER_OR_SEPARATE_BOUNDARY_COVERAGE_INFERENCE`**

No new S3 request was made. This study reuses canonical R3 metadata, R7 legacy wallet-index evidence, R8A modern wallet-index evidence, and official Hyperliquid documentation that predates the boundary.

## What is directly proven

- The complete R3 inventory shows `node_fills` ending at path hour `2025-07-27T08:00:00Z` and `node_fills_by_block` beginning at that exact same path hour.
- The modern `20250727/8` object is **1,517,603 bytes**, the single smallest object in the complete 9,070-object modern family inventory.
- The immediately following modern hour is **18,147,822 bytes**; the boundary object is only **8.36%** of that size. Relative to the median of the next 24 modern hours it is **6.69%**.
- The legacy `20250727/8` object is **12,726,384 bytes**, or **97.31%** of the immediately previous legacy hour and **89.90%** of the median of the previous eight legacy hours.
- R7 found **162,815** legacy fill records across **4,637** wallets. R8A found **17,516** modern event pairs across **887** wallets.
- The address sets are not nested: **688** overlap, **199** are modern-only, and **3,949** are legacy-only.

## What the official writer documentation adds

The official node repository documented `--write-fills` before this boundary as the API-format fill stream, then documented `--batch-by-block` before the boundary as writing those streams one block per line. Current official historical-data documentation identifies `node_fills_by_block` as the newer `--write-fills --batch-by-block` archive and `node_fills` as older fill data in a different format.

This makes a migration/cutover explanation substantially stronger than an interpretation that the two `20250727/8` objects are supposed to be two complete, identical copies of the same market-time hour.

## What is still not proven

We did not retain the boundary objects' minimum/maximum event timestamps, so the exact within-hour cutover timestamp, any fill-level overlap, and any fill-level gap remain unproven. The public node repository does not expose enough serializer/uploader implementation to prove those facts statically.

## Canonical fail-closed rule

The shared path hour `2025-07-27T08` is now treated as **transition-censored** for cross-format historical research:

- use legacy path hours through `2025-07-27T07`;
- use modern path hours from `2025-07-27T09`;
- use neither boundary object in a canonical merged history;
- never concatenate both boundary objects or claim they form a complete hour.

This deliberately sacrifices one ambiguous path hour rather than risk double-counting or silent gaps.

## Consequence for the project

We **do not need another paid request just to solve the cutover hour before moving on**. The modern family can be used for the next bounded feature-pipeline pilot from an unambiguous post-boundary hour or, for serializer/feature mechanics only, the already fingerprinted boundary object under a clearly non-historical role.

Any exact continuity study of the transition hour remains a separate future gate.
