# Retention policy

The preregistration retains only contracts, source maps, deterministic planning code and tests.

For a future approved metadata canary, raw S3 listing responses should be transient transport evidence. Canonical retained data should be normalized to the fields frozen in `INVENTORY_CONTRACT.json` plus request/page ledger, pricing evidence, hashes, run context and validation logs.

Credentials, signed Authorization headers, session tokens, object bodies and decompressed archive content must never be retained in GitHub or workflow artifacts.

Large inventories should not be committed directly to Git. A later retention decision should keep a content-addressed canonical manifest/summary and place bulky immutable metadata in an approved artifact/object store.
