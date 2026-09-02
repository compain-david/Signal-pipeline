# Signal snapshot — 2026-09-02

**v2.0 — instrument qui gouverne : `gate_legacy`**

| Instrument | Statut | Rôle |
|---|---|---|
| `gate_legacy` | **GOUVERNE** | gouverne jusqu a ADOPTED_FROM, par continuite |
| `gate_new` | ombre | gouverne a partir de ADOPTED_FROM |
| `ladder_shadow` | ombre | ombre indefinie - mise a jour de strategie non signee |
| `evidence_gate` | ombre | ombre par construction - portee, pas decision |

Generated 2026-09-02T15:53:39.913706+00:00 · schema v5

> **DEGRADED RUN** — 0 failed, 1 stale. Check provenance before using these numbers.

## For the weekly brief composite

| Dimension | Value | Provenance |
|---|---|---|
| Regime · STH-RP | — | FAILED (frozen_excluded) |
| Valuation · MVRV Z | 0.8577 | live |
| Miners · Puell | 0.9361 | live |
| Sentiment · F&G | 63 | live |
| Supply · ETH netflow 7d | -182,059 | live |
| BTC dominance % | 59.09 | live |

Not automatable: ETF net flows (no public API), LTH supply (no free source found).

## Rotation ladder (shadow — governs nothing)

| | |
|---|---|
| State | **BTC** |
| T | **0.25** |
| Coverage | 57.14% (floor 70%) |
| Measurable | **no** |
| Reason | frozen - coverage 57.14% below the 70% floor |

> Frozen on coverage, **not** on T. T = 0.25 — read the reason above before concluding there is no signal.

Unsigned strategy update: this ladder does not govern. Pending: Sign the versioned strategy update: 25% ETH cap, four-state ladder; Confirm the six thresholds: 0.55/0.45 ETH, 0.70/0.60 ALT, 2 weeks, 70% floor; Confirm the ladder can never enter USDT on its own authority

## Gates

- **10-dimension (shadow):** 1 of 5 fired, threshold 5 → would not fire
  - grade **D** — no actionable signal (1.0 of 4.8 achievable this run)
  - reading: rotation-favourable only
  - not counted: eth_etf_flows, stablecoin_supply_ratio, sth_realized_price
- **Legacy (retained for continuity):** 2 of 5 — fear_greed, exchange_netflows

## All signals

| Signal | Dim | Tier | Value | Vote | Provenance |
|---|---|---|---|---|---|
| eth_btc_momentum | 1 | A | 1.67 | no | live |
| btc_dominance | 1 | track | 59.09 | no | live |
| alt_dominance | 1 | track | 29.79 | — | FAILED (building) |
| altseason_index | 1 | track | — | — | not automated |
| mvrv_z_score | 2 | A | 0.8577 | no | live |
| nvt | 2 | A | 19.95 | no | live |
| mvrv_ratio | 2 | track | 1.458 | — | live |
| mayer_multiple | 2 | track | 1.114 | — | live |
| puell_multiple | 2 | track | 0.9361 | — | live |
| nupl | 2 | track | 0.32 | — | live |
| lth_share | 9 | track | 0.807 | — | live |
| peak_indicators | 4 | track | — | — | not automated |
| fear_greed | 3 | track | 63 | YES | live |
| social_volume | 3 | track | — | — | not automated |
| eth_etf_flows | 5 | A | — | — | not automated |
| stablecoin_supply_ratio | 6 | A | 6.1029 | — | STALE (carried_forward) |
| alt_funding_rates | 7 | A | 4.89 | no | live |
| exchange_netflows | 9 | A | -182058.94 | YES | live |
| sopr | 9 | track | 1.0024 | — | live |
| sth_realized_price | 10 | A | — | — | FAILED (frozen_excluded) |
