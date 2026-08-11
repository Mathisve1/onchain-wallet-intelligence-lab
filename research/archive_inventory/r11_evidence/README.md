# R11 72-hour persistence execution evidence

Canonical run `31436753081` executed once from `main` commit `baca1925c23ef6b0136aa3d96d6d479ac7717bdf` and consumed the single-use R11 release.

Transport, integrity, and the record-anchored alignment rule all completed cleanly across the exact 72 approved hourly objects. All 72 GetObject requests succeeded with zero retries and zero failed requests. The run processed three complete UTC days, 3,283,391 block records and 26,384,234 event pairs. It observed 490 pre-hour fills, all located in previous-prefix block records, zero after-hour fills, and zero record-anchored alignment violations.

The final research result is nevertheless `R11_72H_PERSISTENCE_PIPELINE_UNRESOLVED`. The aggregator observed at least one repeated normalized `tid` within the same wallet state. The retained evidence does not contain the duplicate count, locations, or the repeated payloads, so it cannot distinguish duplicated archive observations from legitimate distinct fills that share a `tid`. Blind deduplication is therefore forbidden.

The missing count is a recorded contract deviation, not merely an inconvenient omission: the R11 preregistration required that count to be retained. The unresolved handler discarded it with the aggregate summary. A separate consumption record permanently closes the original release, while the original release snapshot remains immutable.

The original collector is historical evidence and must not be reused as a successor. Its success path contains a read-mutation in active-day tracking, attributes previous-hour fills to source path activity, and mutates shared R10 limit constants when imported. No wallet rows were published, so these defects did not create a retained R11 feature dataset.

No wallet-feature rows were retained. Ranking, PnL/alpha interpretation, copyability, enrichment, clustering, historical expansion, strategy inference, and all trading or capital authority remain closed. Any further network request requires a new preregistration, human approval, and separate single-use release.
