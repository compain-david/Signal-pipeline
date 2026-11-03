# Signal snapshot — 2026-11-03

**v2.0 — instrument qui gouverne : `gate_new`**

| Instrument | Statut | Rôle |
|---|---|---|
| `gate_legacy` | ombre | gouverne jusqu a ADOPTED_FROM, par continuite |
| `gate_new` | **GOUVERNE** | gouverne a partir de ADOPTED_FROM |
| `ladder_shadow` | ombre | ombre indefinie - mise a jour de strategie non signee |
| `evidence_gate` | ombre | ombre par construction - portee, pas decision |

Generated 2026-11-03T13:05:30.142089+00:00 · schema v5

> **DEGRADED RUN** — 0 failed, 3 stale. Check provenance before using these numbers.

## For the weekly brief composite

| Dimension | Value | Provenance |
|---|---|---|
| Regime · STH-RP | — | FAILED (frozen_excluded) |
| Valuation · MVRV Z | 0.8725 | STALE (stale) |
| Miners · Puell | — | FAILED (frozen_excluded) |
| Sentiment · F&G | 26 | live |
| Supply · ETH netflow 7d | -563,814 | live |
| BTC dominance % | 59.21 | live |

Not automatable: ETF net flows (no public API), LTH supply (no free source found).

## Rotation ladder (shadow — governs nothing)

| | |
|---|---|
| State | **ETH** |
| T | **0.4545** |
| Coverage | 78.57% (floor 70%) |
| Measurable | yes |
| Reason | held - 1 of 14 minimum days in state |

Unsigned strategy update: this ladder does not govern. Pending: Sign the versioned strategy update: 25% ETH cap, four-state ladder; Confirm the six thresholds: 0.55/0.45 ETH, 0.70/0.60 ALT, 2 weeks, 70% floor; Confirm the ladder can never enter USDT on its own authority

## Gates

- **10-dimension (AUTHORITATIVE):** 2 of 4 fired, threshold 5 → would not fire
  - grade **D** — no actionable signal (1.8 of 3.8 achievable this run)
  - reading: rotation-favourable only
  - not counted: mvrv_z_score, nvt, eth_etf_flows, sth_realized_price
- **Legacy (retained for continuity):** 1 of 5 — exchange_netflows

## All signals

| Signal | Dim | Tier | Value | Vote | Provenance |
|---|---|---|---|---|---|
| eth_btc_momentum | 1 | A | 0.36 | no | live |
| btc_dominance | 1 | track | 59.21 | no | live |
| alt_dominance | 1 | track | 30.18 | YES | live |
| altseason_index | 1 | track | — | — | not automated |
| mvrv_z_score | 2 | A | 0.8725 | — | STALE (stale) |
| nvt | 2 | A | — | — | FAILED (frozen_excluded) |
| mvrv_ratio | 2 | track | 1.42 | — | live |
| mayer_multiple | 2 | track | 1.0494 | — | live |
| puell_multiple | 2 | track | — | — | FAILED (frozen_excluded) |
| nupl | 2 | track | 0.3323 | — | STALE (stale) |
| lth_share | 9 | track | 0.796 | — | live |
| peak_indicators | 4 | track | — | — | not automated |
| fear_greed | 3 | track | 26 | no | live |
| social_volume | 3 | track | — | — | not automated |
| eth_etf_flows | 5 | A | — | — | not automated |
| stablecoin_supply_ratio | 6 | A | 6.14 | YES | live |
| alt_funding_rates | 7 | A | 7.02 | no | live |
| exchange_netflows | 9 | A | -563814.26 | YES | live |
| sopr | 9 | track | 1.0 | — | STALE (stale) |
| sth_realized_price | 10 | A | — | — | FAILED (frozen_excluded) |
