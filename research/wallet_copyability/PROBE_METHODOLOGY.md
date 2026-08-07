# Hyperliquid public technical probe R1 methodology

## Status and purpose

`HL-PUBLIC-PROBE-001R1` is a bounded pre-data capability test for
`WALLET-COPYABILITY-STUDY-001`.

It answers only whether the registered public, read-only routes are reachable,
parseable and structurally suitable for a later data-quality investigation. It
does not establish historical completeness, wallet skill, copyability, alpha or
execution readiness.

## Frozen questions

The probe tests five questions:

1. Can the public `/info` endpoint return current market metadata, documented
   account roles, confirmed master/subaccount relationships, account state,
   fee structure, fills, funding and non-funding ledger response structures?
2. Does the official documentation example for the master/subaccount
   relationship still resolve consistently in both directions?
3. Does the documented vault address still resolve as a vault and return the
   expected vault-details structure?
4. Can an active public vault response empirically distinguish the general
   500-item time-range statement from the endpoint-specific 2,000-fill statement?
5. Are the named official S3 archive routes anonymously listable, or do they
   require authenticated requester-pays access?

## Registered public identities

The master, subaccount and vault addresses are taken from examples in the
official Hyperliquid info-endpoint documentation. They are used only as public
technical fixtures.

No claim is made about a real-world natural person, beneficial owner or common
controller. A documented master/subaccount relationship is an operational
account relationship, not proof of legal identity.

## Data minimization

The probe reads response bytes in volatile memory only. It writes none of the
raw response bodies to disk.

The retained output contains:

- request and response SHA-256 hashes;
- HTTP status and bounded response length;
- selected non-secret headers;
- top-level response type and keys;
- bounded structural paths and their fingerprint;
- aggregate item counts;
- aggregate minimum and maximum event timestamps where applicable;
- Boolean relationship and field-presence checks; and
- terminal PASS, DEGRADED or FAIL classifications.

The output deliberately omits prices, position sizes, account values, trade
sides, fees paid, funding values, follower identities and raw ledger payloads.

## Network and rate-limit discipline

The contract registers exactly 18 requests and exactly three HTTPS origins.
Cross-origin redirects are rejected. Responses larger than the frozen byte
ceiling fail closed.

The declared base request weight stays below the frozen ceiling and below the
published 1,200-weight-per-minute IP budget. Result-size-dependent weight may
still apply to fill and funding responses; the probe therefore performs one
bounded request per registered route and does not paginate.

## Terminal outcomes

### `PUBLIC_PROBE_PASS`

Every required request returns an expected, parseable and structurally valid
response, every registered relationship check passes, the active fill-limit
probe resolves the documentation conflict, and every archive listing is
available without degradation.

### `PUBLIC_PROBE_PARTIAL`

No required route fails, but at least one capability remains degraded. Examples
include:

- an official archive route responds with an expected access-control or
  requester-pays denial;
- the active vault response contains too few fills to resolve the 500-versus-
  2,000 limit wording; or
- an optional diagnostic request fails while every core request succeeds.

A partial result permits a repair or a separately governed archive-access
investigation. It does not open the analytical market partition.

### `PUBLIC_PROBE_FAIL`

At least one required route fails, a documented relationship is inconsistent,
an unexpected response schema appears, a response exceeds the byte ceiling, or
a security invariant fails.

A failed probe stops archive and ledger work.

## Evidence lifecycle

1. The workflow executes the exact reviewed commit.
2. The script emits one canonical JSON output file.
3. GitHub uploads that single file as an immutable artifact.
4. The artifact ID, artifact digest, run ID and numeric job ID are retrieved.
5. The exact output file is committed under `evidence/`.
6. `TECHNICAL_PROBE_EVIDENCE.json` binds the output hash and workflow identity.
7. Repository validation independently recomputes hashes, coverage, counts and
   terminal status.
8. Full CI reruns on the final evidence commit.

## Non-conclusions

Even `PUBLIC_PROBE_PASS` does not prove that:

- historical archive objects are complete or timely;
- an address's full economic exposure is visible;
- deposits and transfers can already be reconciled into P&L;
- a source wallet is skilled;
- a follower could execute at the source price; or
- the strategy has positive expected value.

Those questions belong to later, separately released phases.
