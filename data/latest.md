# Signal snapshot — 2026-11-11

**v2.0 — instrument qui gouverne : `gate_new`**

| Instrument | Statut | Rôle |
|---|---|---|
| `gate_legacy` | ombre | gouverne jusqu a ADOPTED_FROM, par continuite |
| `gate_new` | **GOUVERNE** | gouverne a partir de ADOPTED_FROM |
| `ladder_shadow` | ombre | ombre indefinie - mise a jour de strategie non signee |
| `evidence_gate` | ombre | ombre par construction - portee, pas decision |

Generated 2026-11-11T13:01:41.361345+00:00 · schema v5

> **DEGRADED RUN** — 0 failed, 0 stale. Check provenance before using these numbers.

## For the weekly brief composite

| Dimension | Value | Provenance |
|---|---|---|
| Regime · STH-RP | — | FAILED (frozen_excluded) |
| Valuation · MVRV Z | — | FAILED (frozen_excluded) |
| Miners · Puell | — | FAILED (frozen_excluded) |
| Sentiment · F&G | 29 | live |
| Supply · ETH netflow 7d | 81,789 | live |
| BTC dominance % | 60.47 | live |

Not automatable: ETF net flows (no public API), LTH supply (no free source found).

## Rotation ladder (shadow — governs nothing)

| | |
|---|---|
| State | **ETH** |
| T | **0.3636** |
| Coverage | 78.57% (floor 70%) |
| Measurable | yes |
| Reason | held - 9 of 14 minimum days in state |

Unsigned strategy update: this ladder does not govern. Pending: Sign the versioned strategy update: 25% ETH cap, four-state ladder; Confirm the six thresholds: 0.55/0.45 ETH, 0.70/0.60 ALT, 2 weeks, 70% floor; Confirm the ladder can never enter USDT on its own authority

## Gates

- **10-dimension (AUTHORITATIVE):** 2 of 4 fired, threshold 5 → would not fire
  - grade **D** — no actionable signal (1.8 of 3.8 achievable this run)
  - reading: rotation-favourable only
  - not counted: mvrv_z_score, nvt, eth_etf_flows, sth_realized_price
- **Legacy (retained for continuity):** 0 of 5 — none

## All signals

| Signal | Dim | Tier | Value | Vote | Provenance |
|---|---|---|---|---|---|
| eth_btc_momentum | 1 | A | -4.07 | no | live |
| btc_dominance | 1 | track | 60.47 | no | live |
| alt_dominance | 1 | track | 29.32 | no | live |
| altseason_index | 1 | track | — | — | not automated |
| mvrv_z_score | 2 | A | — | — | FAILED (frozen_excluded) |
| nvt | 2 | A | — | — | FAILED (frozen_excluded) |
| mvrv_ratio | 2 | track | 1.367 | — | live |
| mayer_multiple | 2 | track | 1.0086 | — | live |
| puell_multiple | 2 | track | — | — | FAILED (frozen_excluded) |
| nupl | 2 | track | — | — | FAILED (frozen_excluded) |
| lth_share | 9 | track | 0.794 | — | live |
| peak_indicators | 4 | track | — | — | not automated |
| fear_greed | 3 | track | 29 | no | live |
| social_volume | 3 | track | — | — | not automated |
| eth_etf_flows | 5 | A | — | — | not automated |
| stablecoin_supply_ratio | 6 | A | 6.0077 | YES | live |
| alt_funding_rates | 7 | A | 8.94 | YES | live |
| exchange_netflows | 9 | A | 81789.05 | no | live |
| sopr | 9 | track | — | — | FAILED (frozen_excluded) |
| sth_realized_price | 10 | A | — | — | FAILED (frozen_excluded) |
