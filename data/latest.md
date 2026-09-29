# Signal snapshot — 2026-09-29

**v2.0 — instrument qui gouverne : `gate_legacy`**

| Instrument | Statut | Rôle |
|---|---|---|
| `gate_legacy` | **GOUVERNE** | gouverne jusqu a ADOPTED_FROM, par continuite |
| `gate_new` | ombre | gouverne a partir de ADOPTED_FROM |
| `ladder_shadow` | ombre | ombre indefinie - mise a jour de strategie non signee |
| `evidence_gate` | ombre | ombre par construction - portee, pas decision |

Generated 2026-09-29T11:39:31.635976+00:00 · schema v5

> **DEGRADED RUN** — 1 failed, 2 stale. Check provenance before using these numbers.

## For the weekly brief composite

| Dimension | Value | Provenance |
|---|---|---|
| Regime · STH-RP | — | FAILED (frozen_excluded) |
| Valuation · MVRV Z | — | FAILED (frozen_excluded) |
| Miners · Puell | — | FAILED (frozen_excluded) |
| Sentiment · F&G | 73 | live |
| Supply · ETH netflow 7d | -187,898 | live |
| BTC dominance % | 58.63 | STALE (carried_forward) |

Not automatable: ETF net flows (no public API), LTH supply (no free source found).

## Rotation ladder (shadow — governs nothing)

| | |
|---|---|
| State | **BTC** |
| T | **0.5** |
| Coverage | 57.14% (floor 70%) |
| Measurable | **no** |
| Reason | frozen - coverage 57.14% below the 70% floor |

> Frozen on coverage, **not** on T. T = 0.5 — read the reason above before concluding there is no signal.

Unsigned strategy update: this ladder does not govern. Pending: Sign the versioned strategy update: 25% ETH cap, four-state ladder; Confirm the six thresholds: 0.55/0.45 ETH, 0.70/0.60 ALT, 2 weeks, 70% floor; Confirm the ladder can never enter USDT on its own authority

## Gates

- **10-dimension (shadow):** 2 of 4 fired, threshold 5 → would not fire
  - grade **C** — watch - some evidence, below the historical bar (2.0 of 3.8 achievable this run)
  - reading: rotation-favourable only
  - not counted: mvrv_z_score, nvt, eth_etf_flows, sth_realized_price
- **Legacy (retained for continuity):** 2 of 4 — fear_greed, exchange_netflows

## All signals

| Signal | Dim | Tier | Value | Vote | Provenance |
|---|---|---|---|---|---|
| eth_btc_momentum | 1 | A | 0.79 | no | live |
| btc_dominance | 1 | track | 58.63 | — | STALE (carried_forward) |
| alt_dominance | 1 | track | 29.93 | — | STALE (carried_forward) |
| altseason_index | 1 | track | — | — | FAILED (http_error) |
| mvrv_z_score | 2 | A | — | — | FAILED (frozen_excluded) |
| nvt | 2 | A | — | — | FAILED (frozen_excluded) |
| mvrv_ratio | 2 | track | 1.559 | — | live |
| mayer_multiple | 2 | track | 1.1739 | — | live |
| puell_multiple | 2 | track | — | — | FAILED (frozen_excluded) |
| nupl | 2 | track | — | — | FAILED (frozen_excluded) |
| lth_share | 9 | track | 0.802 | — | live |
| peak_indicators | 4 | track | — | — | not automated |
| fear_greed | 3 | track | 73 | YES | live |
| social_volume | 3 | track | — | — | not automated |
| eth_etf_flows | 5 | A | — | — | not automated |
| stablecoin_supply_ratio | 6 | A | 6.5364 | no | live |
| alt_funding_rates | 7 | A | 9.34 | YES | live |
| exchange_netflows | 9 | A | -187897.81 | YES | live |
| sopr | 9 | track | — | — | FAILED (frozen_excluded) |
| sth_realized_price | 10 | A | — | — | FAILED (frozen_excluded) |
