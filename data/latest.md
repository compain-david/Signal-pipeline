# Signal snapshot — 2026-08-31

Generated 2026-08-31T16:59:54.859655+00:00 · schema v4

## For the weekly brief composite

| Dimension | Value | Provenance |
|---|---|---|
| Regime · STH-RP | $69,980 | live |
| Valuation · MVRV Z | 0.8486 | live |
| Miners · Puell | 1.0780 | live |
| Sentiment · F&G | 62 | live |
| Supply · ETH netflow 7d | -172,203 | live |
| BTC dominance % | 59.20 | live |

Not automatable: ETF net flows (no public API), LTH supply (no free source found).

## Gates

- **Legacy (authoritative):** 2 of 5 — fear_greed, exchange_netflows
- **10-dimension (AUTHORITATIVE):** 4 of 8 fired, threshold 5 → would not fire
  - not counted: eth_etf_flows

## All signals

| Signal | Dim | Tier | Value | Vote | Provenance |
|---|---|---|---|---|---|
| eth_btc_momentum | 1 | A | 5.71 | no | live |
| btc_dominance | 1 | track | 59.2 | — | live |
| altseason_index | 1 | track | — | — | not automated |
| mvrv_z_score | 2 | A | 0.8486 | no | live |
| nvt | 2 | A | 26.28 | no | live |
| mvrv_ratio | 2 | track | 1.464 | — | live |
| mayer_multiple | 2 | track | 1.1289 | — | live |
| puell_multiple | 2 | track | 1.078 | — | live |
| fear_greed | 3 | A | 62 | YES | live |
| social_volume | 3 | track | — | — | not automated |
| eth_etf_flows | 5 | A | — | — | not automated |
| stablecoin_supply_ratio | 6 | A | 6.163 | no | live |
| alt_funding_rates | 7 | A | 1.67 | YES | live |
| exchange_netflows | 9 | A | -172202.96 | YES | live |
| sopr | 9 | track | 1.0029 | — | live |
| sth_realized_price | 10 | A | 69979.57 | YES | live |
