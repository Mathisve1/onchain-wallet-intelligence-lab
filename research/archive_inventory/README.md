# HL-ARCHIVE-INVENTORY-001

This directory preregisters the metadata/access/cost inventory that follows the
attested `HL-PUBLIC-PROBE-001R1`.

The current phase is **proposal and deterministic implementation only**. No AWS
identity is bound, no Requester Pays charge is accepted, no S3 listing is
executed, and no object body is requested or downloaded.

## Research purpose

Before any historical market partition is released, establish:

1. whether authenticated Requester Pays `ListObjectsV2` can enumerate the exact
   official Hyperliquid archive prefixes;
2. the observed key/layout families and their temporal coverage;
3. bounded object counts and compressed byte totals where enumeration is
   complete;
4. gaps or overlaps that can be proven from complete metadata partitions;
5. the cost envelope for a later, separately approved schema/data pilot.

Metadata-only inventory cannot establish the internal record schema of an LZ4,
CSV, JSON, or binary object. Internal schema inspection requires a later,
separately reviewed object-body authorization.

## Hard boundary

- allowed in this PR: contracts, planning, parsers for listing metadata, cost
  guards, IAM policy templates, tests;
- not allowed: AWS credentials, `ListObjectsV2` execution, `GetObject`, range
  GET, object-body downloads, decompression of archive objects, market-data
  ingestion, wallet P&L, ranking, clustering, alpha claims, or trading.
