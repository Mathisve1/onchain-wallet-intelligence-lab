# Metadata-only gap detection

A listing inventory can establish key-level coverage only where pagination is complete.

Documented layouts:

```text
market_data/YYYYMMDD/HOUR/DATATYPE/COIN.lz4
asset_ctxs/YYYYMMDD.csv.lz4
```

Node-data key layouts are treated as empirically discoverable metadata families until listing evidence establishes them. Filename/path inference is never presented as internal schema.

Gap states:

- `PROVEN_KEY_GAP`: a completely enumerated partition is missing an expected key defined by a preregistered expectation;
- `SUSPECTED_GAP`: neighboring keys imply a possible missing interval but enumeration is incomplete;
- `CENSORED_BY_LIMIT`: a technical canary limit stopped enumeration;
- `UNRESOLVED_LAYOUT`: key grammar is not stable enough to define expectations;
- `NO_GAP_CLAIM`: default.

No object-body completeness claim can be made in this metadata-only study.
