# Signal snapshot — 2026-09-03

**v2.0 — instrument qui gouverne : `gate_legacy`**

| Instrument | Statut | Rôle |
|---|---|---|
| `gate_legacy` | **GOUVERNE** | gouverne jusqu a ADOPTED_FROM, par continuite |
| `gate_new` | ombre | gouverne a partir de ADOPTED_FROM |
| `ladder_shadow` | ombre | ombre indefinie - mise a jour de strategie non signee |
| `evidence_gate` | ombre | ombre par construction - portee, pas decision |

Generated 2026-09-03T10:11:41.373549+00:00 · schema v5

> **DEGRADED RUN** — 0 failed, 0 stale. Check provenance before using these numbers.

## For the weekly brief composite

| Dimension | Value | Provenance |
|---|---|---|
| Regime · STH-RP | — | FAILED (frozen_excluded) |
| Valuation · MVRV Z | 0.8197 | live |
| Miners · Puell | 0.8946 | live |
| Sentiment · F&G | 65 | live |
| Supply · ETH netflow 7d | -69,425 | live |
| BTC dominance % | 59.56 | live |

Not automatable: ETF net flows (no public API), LTH supply (no free source found).

## Rotation ladder (shadow — governs nothing)

| | |
|---|---|
| State | **BTC** |
| T | **0.2** |
| Coverage | 71.43% (floor 70%) |
| Measurable | yes |
| Reason | held - 12 of 14 minimum days in state |

Unsigned strategy update: this ladder does not govern. Pending: Sign the versioned strategy update: 25% ETH cap, four-state ladder; Confirm the six thresholds: 0.55/0.45 ETH, 0.70/0.60 ALT, 2 weeks, 70% floor; Confirm the ladder can never enter USDT on its own authority

## Gates

- **10-dimension (shadow):** 1 of 6 fired, threshold 5 → would not fire
  - grade **D** — no actionable signal (1.0 of 5.6 achievable this run)
  - reading: rotation-favourable only
  - not counted: eth_etf_flows, sth_realized_price
- **Legacy (retained for continuity):** 2 of 5 — fear_greed, exchange_netflows

## All signals

| Signal | Dim | Tier | Value | Vote | Provenance |
|---|---|---|---|---|---|
| eth_btc_momentum | 1 | A | -2.92 | no | live |
| btc_dominance | 1 | track | 59.56 | no | live |
| alt_dominance | 1 | track | 29.28 | — | FAILED (building) |
| altseason_index | 1 | track | — | — | not automated |
| mvrv_z_score | 2 | A | 0.8197 | no | live |
| nvt | 2 | A | 21.49 | no | live |
| mvrv_ratio | 2 | track | 1.454 | — | live |
| mayer_multiple | 2 | track | 1.1093 | — | live |
| puell_multiple | 2 | track | 0.8946 | — | live |
| nupl | 2 | track | 0.3169 | — | live |
| lth_share | 9 | track | 0.807 | — | live |
| peak_indicators | 4 | track | — | — | not automated |
| fear_greed | 3 | track | 65 | YES | live |
| social_volume | 3 | track | — | — | not automated |
| eth_etf_flows | 5 | A | — | — | not automated |
| stablecoin_supply_ratio | 6 | A | 6.0848 | no | live |
| alt_funding_rates | 7 | A | 5.26 | no | live |
| exchange_netflows | 9 | A | -69424.6 | YES | live |
| sopr | 9 | track | 1.0009 | — | live |
| sth_realized_price | 10 | A | — | — | FAILED (frozen_excluded) |
