# HL-PUBLIC-PROBE-001R1 packaging repair

Status: additive repair pending exact-head remote validation.

## Immutable failed evidence

The first PR #5 exact-head runs on `2689e1b7b3ef46909b298230ee53499b30d13772`
failed before any public Hyperliquid request was executed.

- Research CI: run `31177378135`, job `92862280886`;
- public-probe workflow: run `31177376738`, job `92862275918`;
- failure artifact: `8993336751`;
- provider digest:
  `sha256:53e8e890f0cd73491645bb113e412a0617ca90f02aeaa87bc6b8cb165bbed591`;
- classification: `FAILED_PRE_NETWORK_PACKAGING`.

The failed workflow created no route result. It may never be relabelled as
`PUBLIC_PROBE_FAIL`, because the network execution step was skipped.

## Root cause

The frozen contract and tests referenced two files that were absent from the
review branch:

- `probe.py`;
- `validate_evidence.py`.

Consequently test discovery could not import the collector and attestation
validator, and the public-probe workflow stopped at the static safety gate.

## Additive repair

The repair adds:

1. a bounded collector that constructs only contract-registered public requests;
2. same-origin, byte, timeout, retry, request-count and declared-weight limits;
3. independent terminal and archive-access derivation;
4. a strict pending/final evidence validator;
5. request-fingerprint, contract-hash and collector-bundle verification;
6. explicit package boundaries; and
7. the immutable machine-readable finding under `evidence/`.

The frozen 16-route request surface, one-day window, declared capacity model,
privacy boundary, no-result status and all authorization booleans are unchanged.

## Required successor evidence

Only new runs on the repaired exact head can carry technical weight. Required:

- unit and mutation tests PASS;
- repository validation PASS;
- network workflow reaches the public request step;
- output independently validates;
- artifact and ZIP hashes are recomputed;
- exact run/job/artifact identities are attested;
- clean-context review has no unresolved blocker.

Until then:

```text
market_data_ingested=false
empirical_result=null
integration/paper/shadow/live/leverage/capital authorization=false
```
