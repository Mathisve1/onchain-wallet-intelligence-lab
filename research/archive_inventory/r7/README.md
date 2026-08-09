# R7 — bounded wallet-index reconstruction

R7 is the first stage that proposes retaining actual Hyperliquid address values from the legacy archive. It exists only because canonical R6 plus R6A now provide convergent high-confidence evidence that the leading string in each legacy `[string, fill_object]` record is the Hyperliquid user/onchain address.

The stage is intentionally tiny. A future separately approved execution may read exactly the same single one-hour object already used by R5/R6A and produce only a deterministic address index containing `wallet_address` and `fill_count`.

R7 is **not currently executable**. This preregistration performs no AWS/S3 request and retains no address. Implementation is forbidden until a new human approval is recorded against the eventual canonical R7 preregistration merge commit. Approval will still not execute anything; reviewed implementation and a separate single-use execution release remain required.

## What R7 may prove

- every retained wallet key is a lowercase `0x` + 40-hex address;
- each wallet appears exactly once in the output index;
- each wallet has a positive fill count;
- the sum of all wallet fill counts is exactly `162815`;
- the same exact one-hour stream can therefore be deterministically grouped by wallet key.

## What R7 may not prove

R7 cannot claim that one address equals one person, cannot cluster addresses, cannot calculate PnL/alpha, cannot rank wallets, cannot decide copyability, cannot ingest broader historical data and cannot authorize any trading stage.

The expected roadmap after a successful R7 is: first design a bounded historical coverage expansion, then construct point-in-time wallet performance and copyability metrics, and only later rank candidate wallets. Each material expansion remains separately gated.
