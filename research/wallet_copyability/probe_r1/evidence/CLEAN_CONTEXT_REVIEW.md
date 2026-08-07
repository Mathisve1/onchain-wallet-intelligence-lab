# HL-PUBLIC-PROBE-001R1 clean-context evidence review

Status: `CLEAN_CONTEXT_REVIEW_PASS`

Review date: 2026-08-07

Review class: separate-context AI-assisted evidence review plus independent byte/hash verification of the downloaded GitHub Actions artifact. This is not an independent external scientific, legal, financial or security audit.

## Canonical run reviewed

- canonical reviewed commit: `c11046bf288687c6945fe9b8f17141204d24aae6`;
- workflow run: `31200124642`, attempt `1`;
- workflow job: `92937868268`, conclusion `success`;
- artifact: `9002459643` / `hyperliquid-public-probe-r1-31200124642-1`;
- provider artifact digest: `sha256:388ad766d0e71f315533362ed0605b6d6d6cf13895656e84b9aa0afc80cf8fe6`;
- independently downloaded artifact ZIP SHA-256: `388ad766d0e71f315533362ed0605b6d6d6cf13895656e84b9aa0afc80cf8fe6`;
- probe-output SHA-256: `cce83a5eb5f960bc1274b949fdcd532b9168af7ff270b4d71ba6f521995bed89`;
- contract SHA-256: `d89f0400756ab6a4a566404290e33cf68a1a75b8fcb26b9832bc0c8d3041546a`;
- collector-bundle SHA-256: `0c3f7245bb805365f6f7ba52949c00617b112acc62dbac70a23647a9b0cd8479`.

## Identity checks

The workflow logs and retained run context prove before public network access that:

```text
github.ref = refs/heads/main
inputs.reviewed_commit = c11046bf288687c6945fe9b8f17141204d24aae6
github.sha = c11046bf288687c6945fe9b8f17141204d24aae6
git rev-parse HEAD = c11046bf288687c6945fe9b8f17141204d24aae6
```

The canonical execution therefore does not rely on a temporary pull-request merge ref or moving branch identity.

## Independent artifact checks

The downloaded ZIP was hashed independently and matched the provider digest exactly. The ZIP contained exactly five files. The four files covered by `ARTIFACT_FILES.sha256` independently matched their registered hashes:

- `hl-public-probe-r1.json` — `cce83a5eb5f960bc1274b949fdcd532b9168af7ff270b4d71ba6f521995bed89`;
- `probe-run-context.json` — `d5f9e02be449dbbaf6d39b40e743b48813151607c383a2be9c7004b1634778ae`;
- `probe-validation.log` — `9170376f6626bfa5aba7e5982f18756aa87d5b975b01a58a2a59ae10bc849f32`;
- `probe-validation.rc` — `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`.

The artifact file-ledger itself hashes to `86d4c8b69bfeb2acbe131a55886ee5542a4c5a458d8d7f992e441a4a7e29f12e`.

## Accepted technical conclusion

The canonical run supports only the following route-level technical statement:

```text
terminal_status = PUBLIC_PROBE_PASS
pass_count = 16
fail_count = 0
total_request_attempts = 16
total_declared_request_weight = 586
remaining_declared_weight_margin = 614
archive_access_status = ROUTES_CONFIRMED_ACCESS_RESTRICTED
```

All thirteen `/info` probes produced their preregistered coarse JSON response class. All three official S3 archive routes produced recognized S3 access-error responses with HTTP 403. This confirms route behavior but not listing permission, archive completeness, object counts, retrievable bytes, requester-pays configuration or affordable historical access.

## Material limitations

- the historical fills, funding and non-funding-ledger fixture queries returned empty arrays, so non-empty event schemas and pagination remain unproven;
- no archive object was listed or downloaded;
- no analytical market partition was opened;
- no wallet ledger, P&L, ranking, copyability result or entity cluster exists;
- no natural-person identity inference follows from the fixture addresses;
- no alpha, profitability, paper, shadow, live, leverage or capital-allocation conclusion follows.

## Review decision

No unresolved integrity blocker remains for accepting this exact technical evidence. The only allowed successor is a separately preregistered and reviewed archive-inventory proposal. Any paid requester-pays or object-body retrieval remains separately gated.
