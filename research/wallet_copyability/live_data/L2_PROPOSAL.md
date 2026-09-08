# L2 proposal: a second measurement that can answer the question

Status: `PROPOSED_NOT_BUILT`. Nothing here is implemented; it waits on the owner's answer.

## What L1 taught

Three faults pushed L1 toward a false positive, and the instrument run made each visible in
the data: funding truncated for the busiest wallets, the busiest candidates dropped on 429,
and a sample picked from a fifteen-minute tape that turned out to be mostly market makers
(4 of 7) whose last fifteen minutes held up to 1865 fills. Two more surfaced only on real
data: matched-random found zero peers because every wallet had its own private window, and
the fill-derived BTC price series had a 50.8-hour hole. L2 is designed around those five.

## Design

**Selection set, then a hard wall, then evaluation set.** The L1 seven days plus one
selection session become the characterisation set. From it, per wallet: classification
(market maker / directional, with the L1 thresholds), median holding period, coins,
leverage proxy (peak deployed / account value from the snapshot). Selection is frozen at a
recorded UTC instant `T0` and hashed into the repository. Every evaluation fill must have
`time_ms > T0`, enforced by the coverage ledger issuing evaluation intervals that start at
`T0` and nowhere earlier, so the point-in-time split is a certified interval rather than a
promise. The look-ahead probe runs on the selector with the evaluation fills as the "future".

**One common window.** All wallets share `[T0, T0 + 14 days]`. Coverage is certified against
that window, not against each backfill's own start, so matched-random has peers.

**Sample size.** The ten-wallet cap is a websocket cap on user-scoped subscriptions; it does
not bind REST. Characterisation and evaluation both run over REST: `userFillsByTime` at 20
weight per page, so at 1200 weight per minute one sweep of 300 wallets costs at most 6000
weight when quiet, about five minutes, well inside the budget for a fifteen-minute polling
cadence. Copy latency is simulated from venue fill timestamps, so polling cadence does not
limit the latency grid; it only sets how late we learn a fill happened, which is not the
question. Target: **300 candidates** discovered over three tape sessions on twelve coins,
characterised, then **the directional subset (expected 60 to 120)** evaluated forward. With
100 directional wallets and a per-wallet return spread like L1's (roughly 3 to 5 percentage
points at 7 days), a difference of 1.5 points from the matched-random baseline is
detectable; with 7 it is not. If fewer than 40 directional wallets survive characterisation
the study is declared a case study in advance, not after the fact.

**Fixes that go in first.** (1) Charge response-size weight locally: the venue's observed
weight for a 2000-row page exceeds the documented 20; charge 20 plus one per 60 rows and back
off 5 s on the first 429. (2) Page `userFunding` by `startTime` past its 500-row cap, with
the same truncation flag if a page is ever full at the end. (3) Keep the public tape
connected for the twelve evaluation coins for the whole window so prices come from the tape,
never from the sampled wallets' fills. (4) Record `T0`, the selection hash and the window in
the evidence before the first evaluation request.

## Cost and gate

Build: two working days (rate-limit and funding paging with tests, T0-certified ledger,
forward-polling collector, selection freeze). Collection: three tape sessions of 15 minutes,
one characterisation sweep, then fourteen days of unattended-free polling — every sweep is
operator-initiated because scheduled execution stays unauthorised; roughly four sweeps a day,
five minutes each. Total request weight over the study: about 2.5 million, still EUR 0.

Gate needed from the owner: one decision, same shape as `L1-OWNER-DECISION-001`, covering
approval, review and a single-use release for the L2 envelope: the same endpoints and
authentication (none), the same per-command bounds, a 300-wallet REST characterisation cap,
a 14-day forward window, and explicit permission for operator-initiated repeated sweeps.
Wallet ranking on the evaluation set would be authorised for the L2 report only; copyability
claims stay closed until L2 has run and the disclosure says the sample was clean.

## Where I disagree with the direction

Nothing in substance. One addition: the leverage proxy from a single snapshot is weak; the
tracking watch's 60-second snapshots over the whole evaluation window give a leverage series,
and it costs 2 weight per wallet per minute, which fits for the ten most interesting
directional wallets only. I would spend that on the top ten by characterisation score, not on
all.
