# R11A corrective implementation R3

This directory is the only active implementation lane for the R11A identity and archive-boundary diagnostic after the independent review of PR #141 returned `RED`.

The historical PR #141 implementation remains immutable evidence of a rejected design. It is not an execution candidate and its hashes are not owner-approval eligible. PR #142 remains a quarantined failed closure attempt in Git history. PR #143 restored the repository to a coherent inert baseline.

## Purpose

R11A must empirically explain every repeated legacy `(wallet, typed tid)` projection observed across the exact 72 immutable Hyperliquid archive objects used by the original R11 run. It may classify observations and retain bounded provenance. It may not suppress duplicates, repair data, produce wallet features, rank wallets, interpret profitability, infer strategies, or open trading authority.

## Corrective architecture

The R3 implementation is rebuilt around the following layers:

1. **Strict source decoding**
   - UTF-8 only;
   - duplicate JSON keys rejected at every depth;
   - non-finite constants rejected;
   - JSON numeric tokens retained losslessly;
   - no binary-float coercion.

2. **Four independent identity layers**
   - raw observation locator;
   - archive block locator and equality proof;
   - protocol matched-trade identity;
   - wallet user-fill identity.

3. **Compact first-pass candidate indexes**
   - a block-number reducer;
   - a legacy weak-key hash reducer;
   - hashes are used only for partition routing and candidate discovery;
   - exact semantic equality is re-established from complete bytes in the second pass.

4. **Independent second pass**
   - every object is parsed again;
   - per-object source commitments must match the first pass;
   - only preregistered repeated candidates are materialized;
   - materialization is refused before it begins when frozen retention or artifact caps cannot hold.

5. **Bounded equality-group processing**
   - equality groups are spooled inside the measured workspace;
   - no complete group is required to reside in memory;
   - group-wide predicates are evaluated by bounded repeated passes.

6. **Exact taxonomy and proofs**
   - all nine preregistered taxa are implemented with frozen precedence;
   - every authoritative unit universe is conserved independently;
   - every proof foreign key is validated exactly once;
   - no proof claim is hard-coded.

7. **Fail-closed artifacts**
   - every allowed failure produces a deterministic minimal package;
   - true early stop or cap fallback has seven exactly empty scientific containers;
   - fully materialized but unresolved science remains logically complete and is never mislabeled as empty;
   - artifact validation precedes upload.

8. **Single measured workspace**
   - downloads, partitions, sort runs, equality-group spools, artifact staging and final artifact directory share one 5 GiB meter;
   - every mutating boundary reserves bytes before writing;
   - cleanup failures are terminal and retained in minimized stop evidence.

9. **Separate lifecycle validators**
   - inert implementation validation;
   - future approval validation;
   - future role and STS preflight validation;
   - future workflow installation validation;
   - future release and activation validation;
   - future execution-evidence validation.

## Current authority

This directory currently authorizes no execution. The workflow candidate remains outside `.github/workflows`. No owner approval, IAM mutation, OIDC, STS, S3 request, runtime release, activation, diagnostic result, deduplication, repair, wallet feature, ranking, PnL/alpha analysis, copyability analysis or trading action exists.

## Merge boundary

The corrective PR may not merge until all 21 findings in `R11A_RED_REVIEW_FINDINGS.json` are closed by code, validators and adversarial tests; exact-head Research CI is green; the implementation is hash-sealed; and a separate clean-context review returns approval eligibility. Even after that merge, a distinct owner-approval gate remains mandatory before any role or network work.
