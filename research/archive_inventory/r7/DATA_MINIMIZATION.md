# R7 data minimization

R7 is a **wallet-index reconstruction correctness pilot**, not a profitability or copy-trading study.

If a later separately approved release is executed, the exact one-hour legacy object may be processed in memory. The only record-derived value permitted to survive processing is the normalized leading address itself. The only derived per-address metric permitted to survive is `fill_count`.

The retained wallet index is therefore limited to:

```text
wallet_address,fill_count
```

`wallet_address` must be the exact lowercase `0x` + 40-hex leading string. `fill_count` must be a positive integer. Rows must be unique by address and sorted lexicographically.

No fill object may be persisted. No `coin`, `px`, `sz`, `side`, `time`, `closedPnl`, `fee`, `hash`, `oid`, `tid`, `cloid`, liquidation field, builder field or other fill payload value may be retained. Raw compressed bytes, decompressed bytes and record payloads may not be retained.

R7 also does not infer that multiple addresses belong to one person or that one address represents one unique person. Entity clustering is a separate future research gate.

A successful R7 result proves only that the legacy stream can be deterministically indexed by its working Hyperliquid user-address key under the frozen one-hour sample. It does not prove profitability, copyability, strategy quality or trading suitability.
