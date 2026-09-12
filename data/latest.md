# Signal snapshot — 2026-09-12

**v2.0 — instrument qui gouverne : `gate_legacy`**

| Instrument | Statut | Rôle |
|---|---|---|
| `gate_legacy` | **GOUVERNE** | gouverne jusqu a ADOPTED_FROM, par continuite |
| `gate_new` | ombre | gouverne a partir de ADOPTED_FROM |
| `ladder_shadow` | ombre | ombre indefinie - mise a jour de strategie non signee |
| `evidence_gate` | ombre | ombre par construction - portee, pas decision |

Generated 2026-09-12T09:40:19.657457+00:00 · schema v5

> **DEGRADED RUN** — 0 failed, 5 stale. Check provenance before using these numbers.

## For the weekly brief composite

| Dimension | Value | Provenance |
|---|---|---|
| Regime · STH-RP | $70,869 | STALE (stale) |
| Valuation · MVRV Z | 0.8941 | STALE (stale) |
| Miners · Puell | 1.0010 | STALE (stale) |
| Sentiment · F&G | 63 | live |
| Supply · ETH netflow 7d | -42,564 | live |
| BTC dominance % | 58.19 | live |

Not automatable: ETF net flows (no public API), LTH supply (no free source found).

## Rotation ladder (shadow — governs nothing)

| | |
|---|---|
| State | **BTC** |
| T | **0.2** |
| Coverage | 71.43% (floor 70%) |
| Measurable | yes |
| Reason | T 0.20, no rung crossed |

Unsigned strategy update: this ladder does not govern. Pending: Sign the versioned strategy update: 25% ETH cap, four-state ladder; Confirm the six thresholds: 0.55/0.45 ETH, 0.70/0.60 ALT, 2 weeks, 70% floor; Confirm the ladder can never enter USDT on its own authority

## Gates

- **10-dimension (shadow):** 1 of 5 fired, threshold 5 → would not fire
  - grade **D** — no actionable signal (1.0 of 4.8 achievable this run)
  - reading: rotation-favourable only
  - not counted: mvrv_z_score, eth_etf_flows, sth_realized_price
- **Legacy (retained for continuity):** 2 of 5 — fear_greed, exchange_netflows

## All signals

| Signal | Dim | Tier | Value | Vote | Provenance |
|---|---|---|---|---|---|
| eth_btc_momentum | 1 | A | 4.5 | no | live |
| btc_dominance | 1 | track | 58.19 | no | live |
| alt_dominance | 1 | track | 30.23 | — | FAILED (building) |
| altseason_index | 1 | track | — | — | not automated |
| mvrv_z_score | 2 | A | 0.8941 | — | STALE (stale) |
| nvt | 2 | A | 23.84 | no | live |
| mvrv_ratio | 2 | track | 1.451 | — | live |
| mayer_multiple | 2 | track | 1.1018 | — | live |
| puell_multiple | 2 | track | 1.001 | — | STALE (stale) |
| nupl | 2 | track | 0.3393 | — | STALE (stale) |
| lth_share | 9 | track | 0.806 | — | live |
| peak_indicators | 4 | track | — | — | not automated |
| fear_greed | 3 | track | 63 | YES | live |
| social_volume | 3 | track | — | — | not automated |
| eth_etf_flows | 5 | A | — | — | not automated |
| stablecoin_supply_ratio | 6 | A | 6.0733 | no | live |
| alt_funding_rates | 7 | A | 1.79 | no | live |
| exchange_netflows | 9 | A | -42563.51 | YES | live |
| sopr | 9 | track | 1.0069 | — | STALE (stale) |
| sth_realized_price | 10 | A | 70868.57 | — | STALE (stale) |
