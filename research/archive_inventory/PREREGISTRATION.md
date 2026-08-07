# Preregistration — HL-ARCHIVE-INVENTORY-001

## Parent gate

Canonical `HL-PUBLIC-PROBE-001R1` is attested `PUBLIC_PROBE_PASS` on run `31200124642`; its archive routes are `ROUTES_CONFIRMED_ACCESS_RESTRICTED`. This does not prove authenticated listing access, Requester Pays configuration, archive completeness, internal schema, retrievable volume, or affordability.

## Primary question

Can the official Hyperliquid archives be inventoried through a strictly bounded authenticated Requester Pays metadata-only process well enough to preregister a later historical data pilot without downloading any object body?

## Frozen hypotheses

- **H-A listing feasibility:** required archive families can be enumerated with `ListObjectsV2`, `RequestPayer=requester`, and a minimally privileged AWS identity.
- **H-B cost measurability:** listing metadata can bound object counts and compressed byte volume before body retrieval.
- **H-C temporal overlap:** required fills and L2 market data contain a sufficiently overlapping period for a later point-in-time execution study.
- **H-D no hidden body dependency:** a decision about a small schema/data pilot can be made from listing metadata, official documentation and pricing evidence alone. Internal object schemas are explicitly outside this study.

## Dataset scope

Exactly seven official prefix families are registered in `DATASET_REGISTER.json`; no other bucket or prefix may be queried.

## Metadata allowed after later approval

Only bucket, dataset family, key, size, last-modified, ETag if returned, storage class if returned, page/entry ordinals, request timing, pagination evidence and Requester Pays charge indication. `FetchOwner=false`.

## Proposed canary limits — NOT AUTHORIZED

- 300 total `ListObjectsV2` request attempts;
- 40 completed pages per dataset family;
- max 1,000 returned entries per request;
- 250,000 observed keys/common-prefix entries total;
- 256 MiB aggregate HTTP response bytes;
- 15 minutes runtime;
- at most one retry per logical request;
- no GetObject, HeadObject, range GET, Select, restore, write or delete.

Every attempted LIST counts before the network response, including failures/timeouts.

## Decision states

`ARCHIVE_INVENTORY_PASS`, `ARCHIVE_INVENTORY_PARTIAL`, or `ARCHIVE_INVENTORY_FAIL`. None authorizes object-body retrieval automatically.

## Anti-bias and evidence rules

- No period may be selected using known profitable-wallet outcomes.
- No wallet address may determine inventory partitions.
- No internal schema may be inferred from a filename alone.
- Missing keys are not proven gaps unless the relevant partition was completely enumerated.
- Capped/partial listings are censored, never complete.
- Node archive key layouts remain empirical until listing evidence establishes them.
