# R1 Current Status

- study: `WALLET-COPYABILITY-STUDY-001`
- probe: `HL-PUBLIC-PROBE-001R1`
- contract schema: `1.2`
- lifecycle: `PRE_DATA_CANONICAL_IMPLEMENTATION_INSTALLED`
- implementation: `INSTALLED_ON_MAIN_AT_33683532ca3e6cf7512a728157791d3bfef1375f`
- implementation pull request: `#7`
- public network result: `PENDING_CANONICAL_MAIN_RUN`
- archive access result: `PENDING_CANONICAL_MAIN_RUN`
- exact attestation: `PENDING`
- archive inventory: `NOT_OPEN`
- market data ingested: `false`
- empirical result: `null`
- integration authorized: `false`
- paper authorized: `false`
- shadow authorized: `false`
- live authorized: `false`
- leverage authorized: `false`
- capital allocation authorized: `false`

## Next gate

1. read the exact current `main` SHA;
2. dispatch the manual workflow from `refs/heads/main` using that same SHA;
3. independently verify the workflow job and artifact;
4. submit exact immutable evidence and attestation in a separate pull request.

Earlier runs remain non-canonical. No archive, data-release, wallet-analysis or
execution stage is open.
