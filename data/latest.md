# Signal snapshot — 2026-09-09

**v2.0 — instrument qui gouverne : `gate_legacy`**

| Instrument | Statut | Rôle |
|---|---|---|
| `gate_legacy` | **GOUVERNE** | gouverne jusqu a ADOPTED_FROM, par continuite |
| `gate_new` | ombre | gouverne a partir de ADOPTED_FROM |
| `ladder_shadow` | ombre | ombre indefinie - mise a jour de strategie non signee |
| `evidence_gate` | ombre | ombre par construction - portee, pas decision |

Generated 2026-09-09T10:12:26.991474+00:00 · schema v5

## For the weekly brief composite

| Dimension | Value | Provenance |
|---|---|---|
| Regime · STH-RP | $70,956 | live |
| Valuation · MVRV Z | 0.8725 | live |
| Miners · Puell | 0.8901 | live |
| Sentiment · F&G | 66 | live |
| Supply · ETH netflow 7d | -77,946 | live |
| BTC dominance % | 58.96 | live |

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

- **10-dimension (shadow):** 2 of 7 fired, threshold 5 → would not fire
  - grade **C** — watch - some evidence, below the historical bar (2.0 of 6.6 achievable this run)
  - reading: rotation-favourable only
  - not counted: eth_etf_flows
- **Legacy (retained for continuity):** 2 of 5 — fear_greed, exchange_netflows

## All signals

| Signal | Dim | Tier | Value | Vote | Provenance |
|---|---|---|---|---|---|
| eth_btc_momentum | 1 | A | 0.64 | no | live |
| btc_dominance | 1 | track | 58.96 | no | live |
| alt_dominance | 1 | track | 29.74 | — | FAILED (building) |
| altseason_index | 1 | track | — | — | not automated |
| mvrv_z_score | 2 | A | 0.8725 | no | live |
| nvt | 2 | A | 26.18 | no | live |
| mvrv_ratio | 2 | track | 1.475 | — | live |
| mayer_multiple | 2 | track | 1.1226 | — | live |
| puell_multiple | 2 | track | 0.8901 | — | live |
| nupl | 2 | track | 0.3276 | — | live |
| lth_share | 9 | track | 0.806 | — | live |
| peak_indicators | 4 | track | — | — | not automated |
| fear_greed | 3 | track | 66 | YES | live |
| social_volume | 3 | track | — | — | not automated |
| eth_etf_flows | 5 | A | — | — | not automated |
| stablecoin_supply_ratio | 6 | A | 6.1628 | no | live |
| alt_funding_rates | 7 | A | -2.18 | no | live |
| exchange_netflows | 9 | A | -77946.39 | YES | live |
| sopr | 9 | track | 1.0022 | — | live |
| sth_realized_price | 10 | A | 70955.89 | YES | live |
