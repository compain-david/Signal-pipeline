# Signal snapshot — 2026-09-06

**v2.0 — instrument qui gouverne : `gate_legacy`**

| Instrument | Statut | Rôle |
|---|---|---|
| `gate_legacy` | **GOUVERNE** | gouverne jusqu a ADOPTED_FROM, par continuite |
| `gate_new` | ombre | gouverne a partir de ADOPTED_FROM |
| `ladder_shadow` | ombre | ombre indefinie - mise a jour de strategie non signee |
| `evidence_gate` | ombre | ombre par construction - portee, pas decision |

Generated 2026-09-06T09:45:22.570345+00:00 · schema v5

> **DEGRADED RUN** — 0 failed, 0 stale. Check provenance before using these numbers.

## For the weekly brief composite

| Dimension | Value | Provenance |
|---|---|---|
| Regime · STH-RP | — | FAILED (frozen_excluded) |
| Valuation · MVRV Z | 0.8941 | live |
| Miners · Puell | 1.0010 | live |
| Sentiment · F&G | 73 | live |
| Supply · ETH netflow 7d | -35,537 | live |
| BTC dominance % | 59.19 | live |

Not automatable: ETF net flows (no public API), LTH supply (no free source found).

## Rotation ladder (shadow — governs nothing)

| | |
|---|---|
| State | **BTC** |
| T | **0.4** |
| Coverage | 71.43% (floor 70%) |
| Measurable | yes |
| Reason | T 0.40, no rung crossed |

Unsigned strategy update: this ladder does not govern. Pending: Sign the versioned strategy update: 25% ETH cap, four-state ladder; Confirm the six thresholds: 0.55/0.45 ETH, 0.70/0.60 ALT, 2 weeks, 70% floor; Confirm the ladder can never enter USDT on its own authority

## Gates

- **10-dimension (shadow):** 3 of 6 fired, threshold 5 → would not fire
  - grade **C** — watch - some evidence, below the historical bar (3.0 of 5.6 achievable this run)
  - reading: mixed: 2 rotation, 1 froth
  - not counted: eth_etf_flows, sth_realized_price
- **Legacy (retained for continuity):** 2 of 5 — fear_greed, exchange_netflows

## All signals

| Signal | Dim | Tier | Value | Vote | Provenance |
|---|---|---|---|---|---|
| eth_btc_momentum | 1 | A | -0.73 | no | live |
| btc_dominance | 1 | track | 59.19 | no | live |
| alt_dominance | 1 | track | 29.57 | — | FAILED (building) |
| altseason_index | 1 | track | — | — | not automated |
| mvrv_z_score | 2 | A | 0.8941 | no | live |
| nvt | 2 | A | 29.87 | YES | live |
| mvrv_ratio | 2 | track | 1.501 | — | live |
| mayer_multiple | 2 | track | 1.1454 | — | live |
| puell_multiple | 2 | track | 1.001 | — | live |
| nupl | 2 | track | 0.3393 | — | live |
| lth_share | 9 | track | 0.805 | — | live |
| peak_indicators | 4 | track | — | — | not automated |
| fear_greed | 3 | track | 73 | YES | live |
| social_volume | 3 | track | — | — | not automated |
| eth_etf_flows | 5 | A | — | — | not automated |
| stablecoin_supply_ratio | 6 | A | 6.2726 | no | live |
| alt_funding_rates | 7 | A | 9.73 | YES | live |
| exchange_netflows | 9 | A | -35536.86 | YES | live |
| sopr | 9 | track | 1.0069 | — | live |
| sth_realized_price | 10 | A | — | — | FAILED (frozen_excluded) |
