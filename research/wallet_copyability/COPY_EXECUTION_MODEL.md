# Copy Execution Model

## Source event

A source signal begins only when a public executed fill changes the source
wallet's net position materially. An open order is not a source trade.

## Follower entry

For a source long increase, use the first executable ask after the latency
cutoff. For a source short increase, use the first executable bid. Walk depth for
the frozen follower size and model partial fills. Mid, mark, oracle and source
fill prices are diagnostic only.

## Latency grid

```text
1 second
5 seconds
30 seconds
2 minutes
5 minutes
15 minutes
```

## Exit variants

1. proportional copy of source reductions;
2. exit when source net position reaches zero;
3. proportional partial exits;
4. follower risk stop;
5. maximum holding-period exit;
6. skip when the source reverses before the follower entry can execute.

## Cost identity

```text
follower_net_pnl =
    gross_executable_pnl
  - entry_fee
  - exit_fee
  - spread_and_depth_slippage
  - funding_paid
  + funding_received
```

Costs may not be double counted. Funding is integrated over the follower's own
holding interval, not copied from the source wallet's aggregate funding history.

## Required output

For every source trade and aggregate wallet window, report source P&L, follower
P&L by latency, capture ratio, missed-trade reason, entry and exit markout,
turnover, cost decomposition and capacity.
