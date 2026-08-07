# Pre-Run Checklist — Hyperliquid Public Probe R1

## Implementation merge gate

- [x] exact 16-request contract;
- [x] fixed one-day historical window;
- [x] unbounded `userFills` absent;
- [x] three HTTPS origins only;
- [x] credential, signing and action capabilities absent;
- [x] bounded time, bytes, retries, requests and declared weight;
- [x] pending evidence and attestation templates contain no invented identities;
- [x] previous failed/noncanonical runs preserved as negative lineage;
- [x] no final attestation or workflow-run evidence in the implementation PR;
- [x] no archive inventory or market-data release;
- [x] all authorizations false.

## Canonical manual-run gate

Before dispatching after implementation merge:

- [ ] read the exact current `main` SHA;
- [ ] confirm the workflow file exists on that exact commit;
- [ ] enter that SHA in `reviewed_commit`;
- [ ] confirm no newer commit has changed the implementation;
- [ ] confirm repository CI on that SHA is green;
- [ ] confirm no secret or credential is configured for the probe;
- [ ] confirm only public route access is intended.

## Post-run evidence gate

- [ ] workflow checked out the exact supplied SHA;
- [ ] `git rev-parse HEAD` equality check passed;
- [ ] all static gates passed before network access;
- [ ] artifact exists and is not expired;
- [ ] provider digest and downloaded ZIP hash are recomputed;
- [ ] internal artifact ledger matches every file;
- [ ] output passes the independent validator;
- [ ] terminal and archive-access states are independently derived;
- [ ] no raw response, credential or unauthorized field is retained;
- [ ] separate clean-context review is complete;
- [ ] evidence is submitted through a distinct PR.

No archive-inventory or later research stage opens automatically.
