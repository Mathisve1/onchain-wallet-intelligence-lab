# R11 72-hour persistence execution evidence

Canonical run `31436753081` executed once from `main` commit `baca1925c23ef6b0136aa3d96d6d479ac7717bdf` and consumed the single-use R11 release.

Transport, integrity, and the record-anchored alignment rule all completed cleanly across the exact 72 approved hourly objects. All 72 GetObject requests succeeded with zero retries and zero failed requests. The run processed three complete UTC days, 3,283,391 block records and 26,384,234 event pairs. It observed 490 pre-hour fills, all located in previous-prefix block records, zero after-hour fills, and zero record-anchored alignment violations.

The final research result is nevertheless `R11_72H_PERSISTENCE_PIPELINE_UNRESOLVED`. The aggregator observed at least one repeated normalized `tid` within the same wallet state. The retained evidence does not contain the duplicate count, locations, or the repeated payloads, so it cannot distinguish duplicated archive observations from legitimate distinct fills that share a `tid`. Blind deduplication is therefore forbidden.

No wallet-feature rows were retained. Ranking, PnL/alpha interpretation, copyability, enrichment, clustering, historical expansion, strategy inference, and all trading or capital authority remain closed. Any further network request requires a new preregistration, human approval, and separate single-use release.
