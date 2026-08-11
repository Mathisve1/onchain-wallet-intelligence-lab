# R10D to R11A governance and evidence-closure checklist

## Status and scope

This is an offline governance note. It records the supplied 2026-08-11 audit snapshot and the fail-closed sequence required before an owner can approve R11A. It is not a preregistration, approval, release, workflow installation, activation or empirical result.

Canonical update: Gate 0 was completed by PR #139 at reviewed head `91bf625fbb436bb7eee3fea6571be825c7af1d51`, green Research CI run `31477160451` / job `93733410472`, and merge `f7aa612d2a5638cce0fd197f57efea4b787f87f1`. The original R11 release is now canonically consumed-unresolved with zero remaining request budget. The audit-snapshot bullets below remain historical provenance, not current branch state.

At the audited snapshot:

- canonical `main` was `baca1925c23ef6b0136aa3d96d6d479ac7717bdf`;
- canonical lineage PRs 122 through 138 were merged and their exact PR heads had green CI;
- `research/r11-execution-evidence` was at `6733e798d903ef99a17cfd7dd1cb91e3d7fca6cc`, five commits ahead and zero behind `main`;
- that branch had no pull request and no branch CI, and its five-file evidence delta did not yet contain complete raw-artifact retention, release consumption, a dedicated validator and tests, or manifest/state integration.

Those facts identify the audit snapshot only. They do not claim that a later branch or pull request has the same state.

## Gate 0 — complete: original R11 evidence and release closure; research remains unresolved

The canonical evidence-closure pull request attests only the retained original-run facts and the unresolved conclusion. Its merged contract includes all of the following:

- the exact artifact ZIP bytes, or a deterministic repository reconstruction whose decoded SHA-256 is `45ee57df7a63561bef1772d8612d5fe32b06b9c407d9c1464ce0a02b65a15cc5`;
- the exact ZIP entries `r11-context.json`, `r11-result.json`, `r11-wallet-features.ndjson`, `r11.rc` and `R11_FILES.sha256`;
- byte-for-byte copies of those raw entries, an internal-ledger check, reconstruction metadata and independent provider/artifact verification;
- immutable run identity: run `31436753081`, job `93612467250`, artifact `9082810554`, attempt 1 and dispatch SHA `baca1925c23ef6b0136aa3d96d6d479ac7717bdf`;
- exact retained mechanics: 72 completed hours, 3 completed UTC days, 72 successful requests, zero failures, zero retries, 2,107,738,436 compressed bytes, 10,539,979,245 decompressed bytes, 3,283,391 block-record observations and 26,384,234 event-pair observations;
- record-anchored conservation: 3,283,297 path-hour block records plus 94 previous-hour block records, and 490 before-hour plus 26,383,744 inside-hour plus zero after-hour event pairs, with zero alignment violations;
- an empty wallet-feature entry and the unresolved terminal conclusion `R11_72H_PERSISTENCE_PIPELINE_UNRESOLVED`;
- an explicit record that the preregistered duplicate wallet-plus-`tid` count was not retained on the terminal failure path, so neither the duplicate count nor duplicate locations nor root cause are known from the retained artifact;
- a dedicated evidence validator and negative mutation tests covering artifact identity, entry membership, raw-entry equality, ledger integrity, run identity, cardinalities, conservation, unresolved output, release consumption and closed downstream authority;
- a regenerated repository manifest only after the complete evidence delta is final and the validator/tests pass on the exact pull-request head.

The evidence closure must preserve the preregistration deviation. It must not infer or reconstruct the missing duplicate count from aggregate totals, and it must not call the run closed, successful for its research question, or ready for R12.

## Release-consumption closure

The immutable pre-run release remains an historical pre-dispatch snapshot and must not be rewritten to say it was consumed. A separate consumption record must bind the original release to the exact run, job, artifact, dispatch SHA and artifact SHA-256, and must record:

- `release_consumed = true`;
- remaining request budget `0`;
- future R11 dispatch and rerun authority `false`;
- the preregistered duplicate-count retention promise was not met;
- duplicate count and duplicate root cause remain unknown;
- every downstream, wallet-selection, interpretation and trading authorization remains `false`.

This consumption record is necessary even though the original release document correctly remains `release_consumed = false` as an immutable release-time statement.

## Gate 1 — record R10D backward consistency

The R10D backward-consistency report and machine-readable decision may be proposed as a separate inert pull request after, or independently from, the R11 evidence closure. The supported classification is only `C_R10D_UNCERTAIN_UNDER_CANONICAL_IDENTITY`:

- R10D mechanics, alignment and exact source-observation aggregates remain historical evidence;
- the zero repeat count remains valid only for the six selected objects under the legacy wallet-plus-typed-`tid` detector;
- R10D retained no occurrence-level block-overlap ledger or canonical wallet-fill provenance ledger;
- therefore neither exact reproduction nor demonstrable correction under the canonical identity model is proven;
- the historical R10D evidence is not rewritten and no rerun or downstream authority is opened.

## Gate 2 — freeze the R11A scientific question, still inert

Only after the original R11 evidence is canonically closed should the R11A identity dossier and preregistration be reviewed for approval. A clean-context review must verify that the contract:

- separates raw observation, archive block, protocol matched trade and wallet user-fill identity;
- treats `(exact block_time, exact unmodified raw source coin string, validated integer tid)` as the matched-trade key and adds the validated wallet only for the user-fill key;
- accepts `tid` only as a raw JSON integer in `[0, 2^50)`, with no string, float, decimal or Boolean coercion and no time tolerance;
- uses hashes only as integrity/equality invariants, never as unproved semantic identity;
- binds exactly the existing 72 selected R11 objects and their exact keys, ETags, lengths and already observed compressed SHA-256 values;
- requires complete occurrence-level raw and block provenance for every repeated weak-key group;
- classifies exact replay, scope false positives, conflicts, intra-block repeats, schema violations and unclassifiable groups without performing a repair;
- retains no wallet feature, ranking, economic interpretation or trading output;
- leaves every network, OIDC, object-read, decompression, diagnostic and artifact authority closed.

Resource ceilings present in an inert implementation are proposals until the owner explicitly freezes them in the preregistration. Implementation file hashes, workflow blob identity, dependency identity and the dedicated-role reuse/successor decision must be resolved before approval.

## Gate 3 — review implementation separately, still inert

The implementation pull request must remain separable from both the preregistration and any activation. It may contain bounded collectors, identity/classification helpers, immutable limits, a workflow candidate outside `.github/workflows`, validators and tests. It must not install a dispatch route, create a runtime release, reuse the role, mutate IAM, perform a request or claim an empirical result.

The implementation review must fail closed on cap overflow, unknown taxonomy, incomplete provenance, schema violations, object/ETag/length/SHA mismatch, reducer disagreement, artifact overflow or insufficient workspace.

## Gate 4 — owner approval prerequisites

Owner approval is eligible for consideration only when all preceding gates are merged on canonical `main`, repository state files no longer describe an obsolete pre-R11 state, and CI validates the exact approval candidate. The approval must explicitly bind:

- the final preregistration and identity decision;
- the exact implementation and dependency hashes;
- the final frozen resource envelope;
- the exact 72-object input binding;
- the role reuse or successor-role decision;
- the diagnostic-only output and no-repair boundary;
- single-use execution and zero-rerun semantics.

Approval alone still does not install or dispatch a workflow. A later release candidate, canonical activation, single dispatch and evidence pull request remain separate gates. R11B repair design is not eligible until complete R11A evidence is retained, independently validated and explicitly approved for interpretation.

## Repository-state integration

The supplied audit found `PROJECT_STATE.md`, `README.md`, `ROADMAP.md`, `DECISION_LOG.md` and `SYSTEM_ARCHITECTURE.md` stale past R2. Their eventual updates must describe the exact merged state, including the unresolved R11 result and closed downstream authority. They must not be updated in advance to imply R11 closure, R11A approval, R12 readiness or a chosen repair.
