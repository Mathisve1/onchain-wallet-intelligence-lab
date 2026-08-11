# System Architecture

```text
official archives / public event streams
                  |
                  v
        immutable raw object store
                  |
                  v
         schema and gap validator
                  |
                  v
       deterministic wallet ledger
                  |
        +---------+----------+
        |                    |
        v                    v
wallet performance      entity graph
        |                    |
        +---------+----------+
                  v
          copyability engine
                  |
                  v
       independent cluster consensus
                  |
                  v
       AI-supported evidence memo
                  |
                  v
           human research decision
```

## Separation of duties

The collector, ledger, P&L engine, cluster features, execution simulator and risk
controls are deterministic and testable. A language model may provide summaries,
counterarguments and anomaly hypotheses, but cannot be the canonical calculator
or merge authority.

## Scaling principle

The system processes the venue event stream once. It does not poll millions of
wallets. Wallets begin as compact cold records, become warm only after activity
and materiality filters, and enter the hot watchlist only after sufficient
history and copyability evidence.

## Archive identity gates

Archive observations must pass four distinct identity layers before any wallet ledger can be built:

| Layer | Key or locator | Purpose |
|---|---|---|
| raw observation | object key, verified compressed SHA-256, record ordinal, event ordinal | lossless source provenance |
| archive block | block number plus exact wrapper time and ordered event-vector invariants | exact replay versus conflicting replay |
| protocol matched trade | exact wrapper `block_time`, exact source `coin`, strict JSON uint50 `tid` | documented trade identity |
| wallet user fill | validated wallet plus the protocol matched-trade key | one wallet side of a trade |

Source-object path hour is storage provenance, not event-time identity. Hashes prove equality or conflict but never replace semantic identity. Unknown, incomplete or conflicting groups fail closed. R11A is diagnostic only: deduplication, canonicalization, feature generation and downstream interpretation remain later evidence-gated stages.
