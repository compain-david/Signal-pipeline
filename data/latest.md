# Signal snapshot — 2026-09-04

**v2.0 — instrument qui gouverne : `gate_legacy`**

| Instrument | Statut | Rôle |
|---|---|---|
| `gate_legacy` | **GOUVERNE** | gouverne jusqu a ADOPTED_FROM, par continuite |
| `gate_new` | ombre | gouverne a partir de ADOPTED_FROM |
| `ladder_shadow` | ombre | ombre indefinie - mise a jour de strategie non signee |
| `evidence_gate` | ombre | ombre par construction - portee, pas decision |

Generated 2026-09-04T10:01:53.318325+00:00 · schema v5

> **DEGRADED RUN** — 0 failed, 0 stale. Check provenance before using these numbers.

## For the weekly brief composite

| Dimension | Value | Provenance |
|---|---|---|
| Regime · STH-RP | — | FAILED (frozen_excluded) |
| Valuation · MVRV Z | 0.8098 | live |
| Miners · Puell | 1.0738 | live |
| Sentiment · F&G | 74 | live |
| Supply · ETH netflow 7d | -35,551 | live |
| BTC dominance % | 59.74 | live |

Not automatable: ETF net flows (no public API), LTH supply (no free source found).

## Rotation ladder (shadow — governs nothing)

| | |
|---|---|
| State | **BTC** |
| T | **0.4** |
| Coverage | 71.43% (floor 70%) |
| Measurable | yes |
| Reason | held - 13 of 14 minimum days in state |

Unsigned strategy update: this ladder does not govern. Pending: Sign the versioned strategy update: 25% ETH cap, four-state ladder; Confirm the six thresholds: 0.55/0.45 ETH, 0.70/0.60 ALT, 2 weeks, 70% floor; Confirm the ladder can never enter USDT on its own authority

## Gates

- **10-dimension (shadow):** 2 of 6 fired, threshold 5 → would not fire
  - grade **C** — watch - some evidence, below the historical bar (2.0 of 5.6 achievable this run)
  - reading: rotation-favourable only
  - not counted: eth_etf_flows, sth_realized_price
- **Legacy (retained for continuity):** 2 of 5 — fear_greed, exchange_netflows

## All signals

| Signal | Dim | Tier | Value | Vote | Provenance |
|---|---|---|---|---|---|
| eth_btc_momentum | 1 | A | 1.02 | no | live |
| btc_dominance | 1 | track | 59.74 | no | live |
| alt_dominance | 1 | track | 28.97 | — | FAILED (building) |
| altseason_index | 1 | track | — | — | not automated |
| mvrv_z_score | 2 | A | 0.8098 | no | live |
| nvt | 2 | A | 19.83 | no | live |
| mvrv_ratio | 2 | track | 1.529 | — | live |
| mayer_multiple | 2 | track | 1.1677 | — | live |
| puell_multiple | 2 | track | 1.0738 | — | live |
| nupl | 2 | track | 0.3514 | — | live |
| lth_share | 9 | track | 0.807 | — | live |
| peak_indicators | 4 | track | — | — | not automated |
| fear_greed | 3 | track | 74 | YES | live |
| social_volume | 3 | track | — | — | not automated |
| eth_etf_flows | 5 | A | — | — | not automated |
| stablecoin_supply_ratio | 6 | A | 6.4055 | no | live |
| alt_funding_rates | 7 | A | 5.68 | YES | live |
| exchange_netflows | 9 | A | -35551.2 | YES | live |
| sopr | 9 | track | 1.0082 | — | live |
| sth_realized_price | 10 | A | — | — | FAILED (frozen_excluded) |
