# Risk Policy

Current authorizations:

| Authorization | State |
|---|---|
| historical/public research | `true` |
| integration | `false` |
| paper | `false` |
| shadow | `false` |
| live | `false` |
| leverage | `false` |
| capital allocation | `false` |

A positive retrospective or technical result cannot change these states
automatically.

## Research risks

The current technical phase explicitly treats the following as blocking risks:

- public endpoint schema drift;
- response and pagination limits that differ from documentation;
- missing, delayed or access-controlled archive objects;
- false confidence from a successful current-state snapshot;
- deposits or transfers misclassified as trading P&L;
- hidden positions on other wallets or venues;
- source-wallet profit that disappears after follower latency and costs; and
- false consensus caused by related wallets counted independently.

A `PUBLIC_PROBE_PASS` means only that the registered public routes passed the
technical capability contract. It is not evidence of historical completeness,
copyable alpha or execution readiness.

No monthly income objective is an optimization criterion. Research optimizes for
net expectancy subject to drawdown, tail loss, turnover, liquidity, copy latency
and capacity constraints. `NO_TRADE` is preferable to weak or cost-dominated
signals.
