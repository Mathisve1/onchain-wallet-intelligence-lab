# Schema discovery boundary

This metadata-only study may identify key path grammar, file extensions, compression suffixes, date/hour partition conventions, filename-level asset/data-type labels and size distributions.

It may not claim to know the internal row/record schema of an object unless that schema is explicitly documented by Hyperliquid. A `.lz4` suffix proves compression naming, not internal schema.

A later `HL-ARCHIVE-SCHEMA-PILOT-001` requires a separately approved object-body/range-download budget, an exact immutable object allowlist, byte and object-count caps, source hashes and a prohibition on wallet-performance analysis during schema discovery.
