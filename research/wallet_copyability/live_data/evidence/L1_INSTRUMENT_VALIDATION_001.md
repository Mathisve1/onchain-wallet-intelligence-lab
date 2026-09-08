# L1 instrument validation 001

**What this says and does not say.** Seven wallets, one seven-day window, a sample chosen
with hindsight from a fifteen-minute tape, funding costs truncated for five of the seven and
the three most active candidates missing. These numbers test whether the measuring
instrument works on real data. They say nothing about whether any wallet is worth copying,
and no such claim is made. Each row states the share of the follower's funding hours the
rate schedule priced; unpriced hours were charged as zero, in either direction, so those
nets are uncertain rather than bounded. Slippage rests on assumed liquidity throughout.

Authorised by DEC-041 (`APPROVE_HL_L1_PILOT_INSTRUMENT_VALIDATION_001`, bound to `f318e81`).
Results stay in the repository.

## Wallets

| wallet | class | fills | coins | maker share | two-sided | median hold | funding truncated |
|---|---|---|---|---|---|---|---|
| `0x091159a8…` | DIRECTIONAL | 4240 | 12 | 0.403 | 0.000 | 61053 s | yes |
| `0x65408685…` | PROBABLE_MARKET_MAKER | 12005 | 4 | 1.000 | 0.984 | 37 s | yes |
| `0x6e8bc7cd…` | PROBABLE_MARKET_MAKER | 12011 | 1 | 0.996 | 0.834 | 408 s | no |
| `0xa775d1bd…` | PROBABLE_MARKET_MAKER | 11961 | 2 | 0.879 | 0.936 | 65 s | no |
| `0xb83de012…` | DIRECTIONAL | 23105 | 8 | 0.094 | 0.000 | 28297 s | yes |
| `0xd4c1f7e8…` | DIRECTIONAL | 18344 | 15 | 0.018 | 0.054 | 9286 s | yes |
| `0xf5d81a13…` | PROBABLE_MARKET_MAKER | 22211 | 15 | 0.357 | 0.964 | 74 s | yes |

## Outcomes per wallet per latency (equal capital, return space, common decision cutoff)

| wallet | class | funding priced | latency | deployed | return | net | drawdown | turnover | stale skips | vs no-trade | vs hold | vs momentum | vs matched |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `0x091159a8…` | DIRE | 0% | 1 s | 9723998.9650 | 2.74% | 265964.7458 | 0.12% | 1.0000 | 118 | 2.74% | 0.50% | 43.38% | n/a |
| `0x091159a8…` | DIRE | 0% | 5 s | 9712250.7221 | 2.61% | 253310.3283 | 0.14% | 1.0000 | 118 | 2.61% | 0.37% | 43.21% | n/a |
| `0x091159a8…` | DIRE | 0% | 30 s | 9716777.9345 | 2.58% | 250532.7149 | 0.12% | 1.0000 | 118 | 2.58% | 0.34% | 43.19% | n/a |
| `0x091159a8…` | DIRE | 0% | 2 min | 9719924.1070 | 2.57% | 249572.8934 | 0.22% | 1.0000 | 118 | 2.57% | 0.33% | 43.19% | n/a |
| `0x091159a8…` | DIRE | 0% | 5 min | 9726761.5615 | 2.43% | 236423.5748 | 0.22% | 1.0000 | 118 | 2.43% | 0.19% | 43.08% | n/a |
| `0x091159a8…` | DIRE | 0% | 15 min | 9715580.1417 | 2.48% | 240869.3637 | 0.04% | 1.0000 | 118 | 2.48% | 0.24% | 43.09% | n/a |
| `0x65408685…` | PROB | 32% | 1 s | 189700.1729 | -3.03% | -5753.9116 | 3.36% | 50.5758 | 909 | -3.03% | -7.15% | 2.29% | n/a |
| `0x65408685…` | PROB | 32% | 5 s | 184647.8885 | -3.22% | -5952.3914 | 3.55% | 51.9511 | 904 | -3.22% | -7.34% | 2.08% | n/a |
| `0x65408685…` | PROB | 32% | 30 s | 199035.3946 | -3.38% | -6737.0911 | 3.71% | 48.3102 | 888 | -3.38% | -7.50% | 1.98% | n/a |
| `0x65408685…` | PROB | 32% | 2 min | 211146.3220 | -2.83% | -5985.0398 | 3.15% | 45.7384 | 841 | -2.83% | -6.95% | 2.58% | n/a |
| `0x65408685…` | PROB | 32% | 5 min | 206130.5923 | -3.04% | -6268.7455 | 3.33% | 47.0773 | 817 | -3.04% | -7.16% | 2.35% | n/a |
| `0x65408685…` | PROB | 31% | 15 min | 171412.2232 | -3.25% | -5574.6973 | 3.35% | 57.3340 | 838 | -3.25% | -7.37% | 2.00% | n/a |
| `0x6e8bc7cd…` | PROB | 100% | 1 s | 1121328.2484 | -3.29% | -36904.8045 | 3.31% | 49.5551 | 5026 | -3.29% | -7.31% | 1.66% | n/a |
| `0x6e8bc7cd…` | PROB | 95% | 5 s | 1197971.3586 | -3.29% | -39437.6732 | 3.33% | 46.4661 | 5036 | -3.29% | -7.31% | 1.90% | n/a |
| `0x6e8bc7cd…` | PROB | 100% | 30 s | 1293853.3284 | -3.65% | -47281.1652 | 3.79% | 43.1628 | 5044 | -3.65% | -7.66% | 1.83% | n/a |
| `0x6e8bc7cd…` | PROB | 100% | 2 min | 1585760.2018 | -3.90% | -61834.6729 | 4.15% | 35.1920 | 5119 | -3.90% | -7.87% | 2.49% | n/a |
| `0x6e8bc7cd…` | PROB | 100% | 5 min | 2231184.8932 | -3.84% | -85710.9097 | 4.18% | 24.5602 | 5248 | -3.84% | -7.75% | 4.55% | n/a |
| `0x6e8bc7cd…` | PROB | 100% | 15 min | 1183757.1865 | -3.62% | -42805.3520 | 3.77% | 45.0944 | 5419 | -3.62% | -7.63% | 1.53% | n/a |
| `0xa775d1bd…` | PROB | 100% | 1 s | 226881.6692 | -3.24% | -7355.7698 | 3.24% | 85.7254 | 4453 | -3.24% | -7.37% | 1.97% | n/a |
| `0xa775d1bd…` | PROB | 100% | 5 s | 204744.9440 | -4.30% | -8807.3694 | 4.30% | 95.1576 | 4442 | -4.30% | -8.43% | 0.83% | n/a |
| `0xa775d1bd…` | PROB | 100% | 30 s | 175154.8562 | -6.05% | -10604.7248 | 6.05% | 111.8700 | 4403 | -6.05% | -10.19% | -1.05% | n/a |
| `0xa775d1bd…` | PROB | 100% | 2 min | 152952.1489 | -6.81% | -10410.7045 | 6.81% | 128.5273 | 4390 | -6.81% | -10.94% | -1.89% | n/a |
| `0xa775d1bd…` | PROB | 100% | 5 min | 88935.6509 | -14.79% | -13151.2648 | 14.89% | 219.6517 | 4441 | -14.79% | -18.93% | -10.12% | n/a |
| `0xa775d1bd…` | PROB | 100% | 15 min | 92989.6788 | -14.50% | -13483.5221 | 14.51% | 206.6381 | 4530 | -14.50% | -18.64% | -9.82% | n/a |
| `0xb83de012…` | DIRE | 58% | 1 s | 9656022.5722 | -0.77% | -74052.2499 | 2.74% | 1.2788 | 4010 | -0.77% | -3.94% | 44.68% | n/a |
| `0xb83de012…` | DIRE | 58% | 5 s | 9631821.1741 | -0.76% | -73036.9946 | 2.74% | 1.2795 | 4025 | -0.76% | -3.93% | 44.59% | n/a |
| `0xb83de012…` | DIRE | 58% | 30 s | 9566884.7093 | -0.75% | -71508.7305 | 2.68% | 1.2818 | 4059 | -0.75% | -3.93% | 44.34% | n/a |
| `0xb83de012…` | DIRE | 58% | 2 min | 9265475.3278 | -0.68% | -62641.6839 | 2.54% | 1.2893 | 4232 | -0.68% | -3.89% | 43.17% | n/a |
| `0xb83de012…` | DIRE | 58% | 5 min | 8771957.8722 | -0.56% | -49022.5151 | 2.36% | 1.3086 | 4502 | -0.56% | -3.82% | 41.27% | n/a |
| `0xb83de012…` | DIRE | 58% | 15 min | 9065483.3285 | -0.58% | -52458.6708 | 2.28% | 1.4034 | 3773 | -0.58% | -3.81% | 42.45% | n/a |
| `0xd4c1f7e8…` | DIRE | 40% | 1 s | 4782845.1152 | 0.12% | 5761.6371 | 0.37% | 1.8023 | 6256 | 0.12% | -3.56% | 24.87% | n/a |
| `0xd4c1f7e8…` | DIRE | 40% | 5 s | 4783104.8626 | 0.11% | 5233.3300 | 0.39% | 1.8023 | 6256 | 0.11% | -3.57% | 24.86% | n/a |
| `0xd4c1f7e8…` | DIRE | 41% | 30 s | 4779034.2251 | 0.10% | 4541.9150 | 0.38% | 1.8040 | 6248 | 0.10% | -3.58% | 24.83% | n/a |
| `0xd4c1f7e8…` | DIRE | 41% | 2 min | 4800384.9040 | 0.09% | 4557.9752 | 0.37% | 1.7967 | 6200 | 0.09% | -3.58% | 24.92% | n/a |
| `0xd4c1f7e8…` | DIRE | 41% | 5 min | 4865056.3920 | 0.14% | 6815.1292 | 0.37% | 1.7706 | 6171 | 0.14% | -3.53% | 25.23% | n/a |
| `0xd4c1f7e8…` | DIRE | 41% | 15 min | 4869341.8888 | -0.14% | -6737.6883 | 0.34% | 1.8008 | 5808 | -0.14% | -3.81% | 24.97% | n/a |
| `0xf5d81a13…` | PROB | 19% | 1 s | 1572398.4484 | -2.25% | -35303.7325 | 2.25% | 35.0055 | 1422 | -2.25% | -6.27% | 8.85% | n/a |
| `0xf5d81a13…` | PROB | 19% | 5 s | 1572239.1183 | -2.29% | -36068.5033 | 2.29% | 35.0015 | 1434 | -2.29% | -6.32% | 8.80% | n/a |
| `0xf5d81a13…` | PROB | 19% | 30 s | 1624982.1528 | -2.39% | -38882.7318 | 2.42% | 33.8289 | 1444 | -2.39% | -6.42% | 8.91% | n/a |
| `0xf5d81a13…` | PROB | 19% | 2 min | 1510319.5581 | -2.52% | -38075.8745 | 2.53% | 36.3492 | 1429 | -2.52% | -6.56% | 8.33% | n/a |
| `0xf5d81a13…` | PROB | 16% | 5 min | 1545837.1759 | -2.25% | -34818.1118 | 2.25% | 35.4390 | 1431 | -2.25% | -6.28% | 8.74% | n/a |
| `0xf5d81a13…` | PROB | 8% | 15 min | 1559637.8251 | -2.26% | -35245.0524 | 2.26% | 35.1553 | 1731 | -2.26% | -6.29% | 8.79% | n/a |

## What broke on real data

- The certified backfill window begins before the first fill-derived price exists: the L1 backfill window opened 12 hours before the earliest BTC fill in the dataset, so buy-and-hold could not enter 'at the start'. Fixed: baselines enter on the first quote inside the interval, and the entry time is recorded.
- Matched-random found zero eligible peers for every wallet. Each backfill window starts at its own run time, so the seven certified intervals are offset from one another by 10 to 90 seconds and no peer's coverage contains another's window; the ledger refused, correctly. A study needs one common window fixed before collection, not seven private ones.
- Skipped fills grow steeply with latency (up to 1865 at 15 min for one wallet) because they fall in the final minutes of the window, where a 15-minute copy cannot land before the interval ends. That the last fifteen minutes hold so many fills is the selection bias itself: these wallets were chosen for being busy in exactly that quarter hour.
- 42406 of the fills carry a negative fee, i.e. maker rebates. The source wallets' own economics include income the follower can never earn; SourcePnl reports it, FollowerPnl never sees it, which is the separation working, but it means source net and follower net differ by construction for any resting wallet.
- The pooled fill-price series for BTC has a 50.8-hour hole: none of the seven wallets traded BTC for two days, so every mark and baseline step inside that hole used a two-day-old price. A price source independent of the sampled wallets is required (the public tape, kept connected, or candles).
- With the scored wallet's own fills excluded from its price series, most of its copies have no price to execute against: on this sample 1734 to 16710 copies per wallet were skipped at 1 s, and thousands more had only a quote older than 15 minutes. The first instrument run had priced those copies at the source's own fill, which is why latency looked irrelevant. A fills-derived price series cannot support a copy study; L2 polls allMids.
- Funding coverage is uneven and never complete for the wallets that hold across hour boundaries: 0 to 100 percent of the expected settlements were priced per wallet. Market makers that never hold across an hour expect no settlements and show no coverage figure, which is correct and says their funding cost is genuinely near zero.
- The first coverage count double-counted a settlement inside a sub-hour position and produced a share above 1. Expected settlements are now the hour marks inside the holding span, and priced never exceeds expected.
- Coins with no price series at all (fills exist, nothing to mark them against): {'0x091159a8106b077c13e89bc09701117e8b5f129a': ['AERO', 'GRAM', 'HMSTR', 'ZORA'], '0xa775d1bd91ee2cc4cae6113e5fd9c0c17b355277': ['xyz:UNITREE'], '0xd4c1f7e8d876c4749228d515473d36f919583d1d': ['LINK', 'LTC'], '0xf5d81a135f756ca16544e53c20fc20643ec3ad53': ['MEGA']}.
- Coins with fewer than 50 price points over seven days: 14 wallet-coin pairs; their copies are priced against stale quotes.
- Spot index coins (`@nnn`) appeared in fills: ['@107']. HIP-3 equity perps (`xyz:`): ['xyz:CRCL', 'xyz:GOLD', 'xyz:SILVER', 'xyz:SKHX', 'xyz:SPCX', 'xyz:UNITREE']. Funding and liquidity assumptions built for crypto perps were applied to them unchanged.
- Coins with no funding rate observed at all: 2; funding on positions in them is charged as zero, which is another lower bound.
- Fills skipped because no price existed at the copy moment, by wallet and latency: {'0x091159a8106b077c13e89bc09701117e8b5f129a': {'1000': 3723, '5000': 3723, '30000': 3723, '120000': 3723, '300000': 3723, '900000': 3723}, '0x654086857e1fad6dcf05cf6695cce51ea3984268': {'1000': 2239, '5000': 2234, '30000': 2218, '120000': 2169, '300000': 2134, '900000': 2106}, '0x6e8bc7cd0978397b06a14af2a8c31f5daeffea79': {'1000': 5026, '5000': 5036, '30000': 5044, '120000': 5119, '300000': 5248, '900000': 5419}, '0xa775d1bd91ee2cc4cae6113e5fd9c0c17b355277': {'1000': 4771, '5000': 4760, '30000': 4721, '120000': 4708, '300000': 4759, '900000': 4848}, '0xb83de012dba672c76a7dbbbf3e459cb59d7d6e36': {'1000': 16710, '5000': 16725, '30000': 16759, '120000': 16932, '300000': 17202, '900000': 16458}, '0xd4c1f7e8d876c4749228d515473d36f919583d1d': {'1000': 8490, '5000': 8490, '30000': 8482, '120000': 8434, '300000': 8401, '900000': 8008}, '0xf5d81a135f756ca16544e53c20fc20643ec3ad53': {'1000': 1734, '5000': 1746, '30000': 1756, '120000': 1733, '300000': 1721, '900000': 1978}}.
- Largest gap in the pooled BTC fill-price series: 50.8 h.
- Fills with zero fee: 0; negative fee (rebates): 42406.
- Runtime per wallet: {'0x091159a8106b077c13e89bc09701117e8b5f129a': 4.5, '0x654086857e1fad6dcf05cf6695cce51ea3984268': 13.7, '0x6e8bc7cd0978397b06a14af2a8c31f5daeffea79': 12.7, '0xa775d1bd91ee2cc4cae6113e5fd9c0c17b355277': 11.2, '0xb83de012dba672c76a7dbbbf3e459cb59d7d6e36': 16.3, '0xd4c1f7e8d876c4749228d515473d36f919583d1d': 21.4, '0xf5d81a135f756ca16544e53c20fc20643ec3ad53': 29.9} seconds; the whole instrument runs in under a minute per wallet on this dataset.

## Assumptions

```json
{
  "tier1": {
    "coins": [
      "BTC",
      "ETH"
    ],
    "half_spread_bps": "0.5",
    "depth_notional_usd": "2000000"
  },
  "tier2": {
    "coins": [
      "AAVE",
      "ADA",
      "APT",
      "ARB",
      "ATOM",
      "AVAX",
      "BNB",
      "DOGE",
      "ENA",
      "HYPE",
      "LINK",
      "LTC",
      "NEAR",
      "PAXG",
      "SOL",
      "SUI",
      "TAO",
      "TRX",
      "UNI",
      "WLD",
      "XLM",
      "XRP",
      "kPEPE"
    ],
    "half_spread_bps": "1.5",
    "depth_notional_usd": "300000"
  },
  "tier3": {
    "coins": "everything else, including @-indexed spot pairs and xyz: HIP-3 equities",
    "half_spread_bps": "5",
    "depth_notional_usd": "50000"
  },
  "impact_bps_per_full_depth": "10",
  "fees_bps": {
    "taker": "4.5",
    "maker": "1.5"
  },
  "price_source": "fills pooled across all backfilled wallets (last fill per ms)",
  "benchmark_coin": "BTC",
  "momentum": "1h lookback, 10 min step"
}
```
