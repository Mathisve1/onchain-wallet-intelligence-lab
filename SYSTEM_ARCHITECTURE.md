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
