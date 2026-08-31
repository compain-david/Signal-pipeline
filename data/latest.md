# Signal snapshot — 2026-08-31

Generated 2026-08-31T17:36:59.071110+00:00 · schema v4

## For the weekly brief composite

| Dimension | Value | Provenance |
|---|---|---|
| Regime · STH-RP | $69,980 | live |
| Valuation · MVRV Z | 0.8486 | live |
| Miners · Puell | 1.0780 | live |
| Sentiment · F&G | 62 | live |
| Supply · ETH netflow 7d | -172,203 | live |
| BTC dominance % | 59.19 | live |

Not automatable: ETF net flows (no public API), LTH supply (no free source found).

## Rotation ladder (shadow — governs nothing)

| | |
|---|---|
| State | **BTC** |
| T | **0.4545** |
| Coverage | 68.75% (floor 70%) |
| Measurable | **no** |
| Reason | frozen - coverage 68.75% below the 70% floor |

> Frozen on coverage, **not** on T. T = 0.4545 — read the reason above before concluding there is no signal.

Unsigned strategy update: this ladder does not govern. Pending: Sign the versioned strategy update: 25% ETH cap, four-state ladder; Confirm the six thresholds: 0.55/0.45 ETH, 0.70/0.60 ALT, 2 weeks, 70% floor; Confirm the ladder can never enter USDT on its own authority

## Gates

- **10-dimension (AUTHORITATIVE):** 4 of 8 fired, threshold 5 → would not fire
  - grade **B** — strong - clears the old 4-of-7 bar with margin (4.0 of 7.6 achievable this run)
  - reading: mixed: 3 rotation, 1 froth
  - not counted: eth_etf_flows
- **Legacy (retained for continuity):** 2 of 5 — fear_greed, exchange_netflows

## All signals

| Signal | Dim | Tier | Value | Vote | Provenance |
|---|---|---|---|---|---|
| eth_btc_momentum | 1 | A | 5.59 | no | live |
| btc_dominance | 1 | track | 59.19 | no | live |
| alt_dominance | 1 | track | 29.65 | — | FAILED (building) |
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
| alt_funding_rates | 7 | A | 2.63 | YES | live |
| exchange_netflows | 9 | A | -172202.96 | YES | live |
| sopr | 9 | track | 1.0029 | — | live |
| sth_realized_price | 10 | A | 69979.57 | YES | live |
