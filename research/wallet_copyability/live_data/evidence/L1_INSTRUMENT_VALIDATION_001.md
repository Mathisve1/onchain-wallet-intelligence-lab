# L1 instrument validation 001

**What this says and does not say.** Seven wallets, one seven-day window, a sample chosen
with hindsight from a fifteen-minute tape, funding costs truncated for five of the seven and
the three most active candidates missing. These numbers test whether the measuring
instrument works on real data. They say nothing about whether any wallet is worth copying,
and no such claim is made. Costs marked `>=` are lower bounds; nets marked `<=` are ceilings.

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

## Outcomes per wallet per latency (equal capital, return space)

| wallet | class | trunc | latency | deployed | return | net | drawdown | turnover | vs no-trade | vs hold | vs momentum | vs matched |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `0x091159a8…` | DIRE | LB | 1 s | 11909355.7711 | 3.29% | <= 391454.7906 | 0.49% | 1.7878 | 3.29% | 0.34% | 56.03% | n/a |
| `0x091159a8…` | DIRE | LB | 5 s | 11905634.8884 | 3.25% | <= 386944.3265 | 0.46% | 1.7880 | 3.25% | 0.30% | 55.97% | n/a |
| `0x091159a8…` | DIRE | LB | 30 s | 11905957.5377 | 3.23% | <= 384413.6775 | 0.47% | 1.7883 | 3.23% | 0.28% | 55.95% | n/a |
| `0x091159a8…` | DIRE | LB | 2 min | 11908034.4720 | 3.19% | <= 380147.3629 | 0.46% | 1.7879 | 3.19% | 0.25% | 55.93% | n/a |
| `0x091159a8…` | DIRE | LB | 5 min | 11913829.9462 | 3.05% | <= 362791.7742 | 0.74% | 1.7874 | 3.05% | 0.10% | 55.80% | n/a |
| `0x091159a8…` | DIRE | LB | 15 min | 11903968.7780 | 3.08% | <= 367234.5959 | 0.61% | 1.7879 | 3.08% | 0.14% | 55.80% | n/a |
| `0x65408685…` | PROB | LB | 1 s | 193549.1289 | -3.37% | <= -6517.6269 | 3.60% | 54.7164 | -3.37% | -7.49% | 1.86% | n/a |
| `0x65408685…` | PROB | LB | 5 s | 193543.8186 | -3.56% | <= -6898.5465 | 3.78% | 54.7172 | -3.56% | -7.68% | 1.66% | n/a |
| `0x65408685…` | PROB | LB | 30 s | 193525.0323 | -3.66% | <= -7086.7417 | 3.89% | 54.6663 | -3.66% | -7.78% | 1.56% | n/a |
| `0x65408685…` | PROB | LB | 2 min | 189352.4008 | -3.11% | <= -5887.3674 | 3.34% | 55.6463 | -3.11% | -7.23% | 2.10% | n/a |
| `0x65408685…` | PROB | LB | 5 min | 189389.5233 | -3.26% | <= -6171.0229 | 3.46% | 55.1702 | -3.26% | -7.38% | 1.95% | n/a |
| `0x65408685…` | PROB | LB | 15 min | 189557.5840 | -3.32% | <= -6286.6135 | 3.43% | 54.0660 | -3.32% | -7.44% | 1.89% | n/a |
| `0x6e8bc7cd…` | PROB | - | 1 s | 1234865.0229 | -1.24% | -15252.5031 | 2.04% | 70.9439 | -1.24% | -5.26% | 8.37% | n/a |
| `0x6e8bc7cd…` | PROB | - | 5 s | 1234856.7238 | -1.24% | -15325.4422 | 2.03% | 70.9440 | -1.24% | -5.26% | 8.36% | n/a |
| `0x6e8bc7cd…` | PROB | - | 30 s | 1234787.2387 | -1.04% | -12825.4967 | 1.87% | 70.9483 | -1.04% | -5.06% | 8.57% | n/a |
| `0x6e8bc7cd…` | PROB | - | 2 min | 1234659.2600 | -0.91% | -11197.2506 | 1.83% | 70.8570 | -0.91% | -4.93% | 8.70% | n/a |
| `0x6e8bc7cd…` | PROB | - | 5 min | 1234416.8445 | -0.96% | -11847.7618 | 1.79% | 70.5898 | -0.96% | -4.98% | 8.64% | n/a |
| `0x6e8bc7cd…` | PROB | - | 15 min | 1234210.1273 | -0.68% | -8407.8743 | 1.53% | 70.1777 | -0.68% | -4.70% | 8.92% | n/a |
| `0xa775d1bd…` | PROB | - | 1 s | 81721.9718 | -21.39% | -17479.5051 | 21.40% | 368.7657 | -21.39% | -25.53% | -16.75% | n/a |
| `0xa775d1bd…` | PROB | - | 5 s | 81688.3845 | -23.03% | -18809.8671 | 23.04% | 368.9224 | -23.03% | -27.17% | -18.39% | n/a |
| `0xa775d1bd…` | PROB | - | 30 s | 81796.1128 | -24.43% | -19982.9871 | 24.45% | 368.3672 | -24.43% | -28.57% | -19.80% | n/a |
| `0xa775d1bd…` | PROB | - | 2 min | 81935.0184 | -20.98% | -17186.6547 | 20.98% | 367.6652 | -20.98% | -25.12% | -16.34% | n/a |
| `0xa775d1bd…` | PROB | - | 5 min | 81936.8243 | -21.98% | -18012.5015 | 22.03% | 366.7545 | -21.98% | -26.13% | -17.35% | n/a |
| `0xa775d1bd…` | PROB | - | 15 min | 81374.7553 | -24.12% | -19629.1618 | 24.12% | 367.8505 | -24.12% | -28.26% | -19.49% | n/a |
| `0xb83de012…` | DIRE | LB | 1 s | 21865341.1694 | -0.04% | <= -9449.4307 | 1.99% | 1.7019 | -0.04% | -1.94% | 97.22% | n/a |
| `0xb83de012…` | DIRE | LB | 5 s | 21858608.3422 | -0.05% | <= -9957.6977 | 2.00% | 1.7021 | -0.05% | -1.94% | 97.19% | n/a |
| `0xb83de012…` | DIRE | LB | 30 s | 21841578.6998 | -0.05% | <= -11482.3965 | 1.97% | 1.7026 | -0.05% | -1.95% | 97.11% | n/a |
| `0xb83de012…` | DIRE | LB | 2 min | 21759249.1738 | -0.06% | <= -12000.2246 | 1.96% | 1.7053 | -0.06% | -1.96% | 96.76% | n/a |
| `0xb83de012…` | DIRE | LB | 5 min | 21663833.4828 | -0.07% | <= -14650.1136 | 1.95% | 1.7083 | -0.07% | -1.98% | 96.35% | n/a |
| `0xb83de012…` | DIRE | LB | 15 min | 21132984.2587 | -0.08% | <= -17510.1643 | 1.90% | 1.7250 | -0.08% | -2.05% | 94.11% | n/a |
| `0xd4c1f7e8…` | DIRE | LB | 1 s | 7927999.7048 | -2.76% | <= -218770.9855 | 3.00% | 1.5990 | -2.76% | -6.11% | 34.85% | n/a |
| `0xd4c1f7e8…` | DIRE | LB | 5 s | 7927813.9423 | -2.77% | <= -219473.7635 | 3.00% | 1.5990 | -2.77% | -6.12% | 34.84% | n/a |
| `0xd4c1f7e8…` | DIRE | LB | 30 s | 7920842.5185 | -2.77% | <= -219802.0126 | 2.91% | 1.5993 | -2.77% | -6.12% | 34.80% | n/a |
| `0xd4c1f7e8…` | DIRE | LB | 2 min | 7909195.9758 | -2.75% | <= -217802.5943 | 2.91% | 1.5992 | -2.75% | -6.10% | 34.78% | n/a |
| `0xd4c1f7e8…` | DIRE | LB | 5 min | 7826057.5852 | -2.69% | <= -210782.8614 | 2.96% | 1.6031 | -2.69% | -6.05% | 34.50% | n/a |
| `0xd4c1f7e8…` | DIRE | LB | 15 min | 7583747.5724 | -2.70% | <= -204717.8024 | 2.95% | 1.6171 | -2.70% | -6.08% | 33.50% | n/a |
| `0xf5d81a13…` | PROB | LB | 1 s | 1534792.5493 | -2.35% | <= -36031.4158 | 2.35% | 39.0994 | -2.35% | -6.38% | 8.60% | n/a |
| `0xf5d81a13…` | PROB | LB | 5 s | 1534691.6394 | -2.48% | <= -38131.3389 | 2.48% | 39.0995 | -2.48% | -6.52% | 8.47% | n/a |
| `0xf5d81a13…` | PROB | LB | 30 s | 1534563.3895 | -2.70% | <= -41370.7207 | 2.73% | 39.0738 | -2.70% | -6.73% | 8.25% | n/a |
| `0xf5d81a13…` | PROB | LB | 2 min | 1534667.5224 | -2.66% | <= -40826.0529 | 2.67% | 38.8888 | -2.66% | -6.69% | 8.29% | n/a |
| `0xf5d81a13…` | PROB | LB | 5 min | 1534884.8520 | -2.38% | <= -36554.5545 | 2.38% | 38.1736 | -2.38% | -6.41% | 8.57% | n/a |
| `0xf5d81a13…` | PROB | LB | 15 min | 1533756.0071 | -2.40% | <= -36865.1492 | 2.40% | 36.6885 | -2.40% | -6.44% | 8.54% | n/a |

## What broke on real data

- The certified backfill window begins before the first fill-derived price exists: the L1 backfill window opened 12 hours before the earliest BTC fill in the dataset, so buy-and-hold could not enter 'at the start'. Fixed: baselines enter on the first quote inside the interval, and the entry time is recorded.
- Matched-random found zero eligible peers for every wallet. Each backfill window starts at its own run time, so the seven certified intervals are offset from one another by 10 to 90 seconds and no peer's coverage contains another's window; the ledger refused, correctly. A study needs one common window fixed before collection, not seven private ones.
- Skipped fills grow steeply with latency (up to 1865 at 15 min for one wallet) because they fall in the final minutes of the window, where a 15-minute copy cannot land before the interval ends. That the last fifteen minutes hold so many fills is the selection bias itself: these wallets were chosen for being busy in exactly that quarter hour.
- 42406 of the fills carry a negative fee, i.e. maker rebates. The source wallets' own economics include income the follower can never earn; SourcePnl reports it, FollowerPnl never sees it, which is the separation working, but it means source net and follower net differ by construction for any resting wallet.
- The pooled fill-price series for BTC has a 50.8-hour hole: none of the seven wallets traded BTC for two days, so every mark and baseline step inside that hole used a two-day-old price. A price source independent of the sampled wallets is required (the public tape, kept connected, or candles).
- Coins with no price series at all (fills exist, nothing to mark them against): none.
- Coins with fewer than 50 price points over seven days: 5 wallet-coin pairs; their copies are priced against stale quotes.
- Spot index coins (`@nnn`) appeared in fills: ['@107']. HIP-3 equity perps (`xyz:`): ['xyz:CRCL', 'xyz:GOLD', 'xyz:SILVER', 'xyz:SKHX', 'xyz:SPCX', 'xyz:UNITREE']. Funding and liquidity assumptions built for crypto perps were applied to them unchanged.
- Coins with no funding rate observed at all: 2; funding on positions in them is charged as zero, which is another lower bound.
- Fills skipped because no price existed at the copy moment, by wallet and latency: {'0x091159a8106b077c13e89bc09701117e8b5f129a': {'1000': 0, '5000': 0, '30000': 0, '120000': 0, '300000': 0, '900000': 0}, '0x654086857e1fad6dcf05cf6695cce51ea3984268': {'1000': 1, '5000': 3, '30000': 16, '120000': 57, '300000': 151, '900000': 404}, '0x6e8bc7cd0978397b06a14af2a8c31f5daeffea79': {'1000': 0, '5000': 0, '30000': 3, '120000': 17, '300000': 60, '900000': 188}, '0xa775d1bd91ee2cc4cae6113e5fd9c0c17b355277': {'1000': 0, '5000': 1, '30000': 3, '120000': 17, '300000': 53, '900000': 196}, '0xb83de012dba672c76a7dbbbf3e459cb59d7d6e36': {'1000': 2, '5000': 5, '30000': 15, '120000': 65, '300000': 138, '900000': 476}, '0xd4c1f7e8d876c4749228d515473d36f919583d1d': {'1000': 1, '5000': 1, '30000': 7, '120000': 34, '300000': 110, '900000': 424}, '0xf5d81a135f756ca16544e53c20fc20643ec3ad53': {'1000': 0, '5000': 4, '30000': 33, '120000': 193, '300000': 722, '900000': 1865}}.
- Largest gap in the pooled BTC fill-price series: 50.8 h.
- Fills with zero fee: 0; negative fee (rebates): 42406.
- Runtime per wallet: {'0x091159a8106b077c13e89bc09701117e8b5f129a': 8.5, '0x654086857e1fad6dcf05cf6695cce51ea3984268': 18.0, '0x6e8bc7cd0978397b06a14af2a8c31f5daeffea79': 19.4, '0xa775d1bd91ee2cc4cae6113e5fd9c0c17b355277': 21.6, '0xb83de012dba672c76a7dbbbf3e459cb59d7d6e36': 39.7, '0xd4c1f7e8d876c4749228d515473d36f919583d1d': 41.1, '0xf5d81a135f756ca16544e53c20fc20643ec3ad53': 43.7} seconds; the whole instrument runs in under a minute per wallet on this dataset.

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
