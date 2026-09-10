# Signal snapshot — 2026-09-10

**v2.0 — instrument qui gouverne : `gate_legacy`**

| Instrument | Statut | Rôle |
|---|---|---|
| `gate_legacy` | **GOUVERNE** | gouverne jusqu a ADOPTED_FROM, par continuite |
| `gate_new` | ombre | gouverne a partir de ADOPTED_FROM |
| `ladder_shadow` | ombre | ombre indefinie - mise a jour de strategie non signee |
| `evidence_gate` | ombre | ombre par construction - portee, pas decision |

Generated 2026-09-10T10:07:10.839460+00:00 · schema v5

> **DEGRADED RUN** — 0 failed, 7 stale. Check provenance before using these numbers.

## For the weekly brief composite

| Dimension | Value | Provenance |
|---|---|---|
| Regime · STH-RP | $71,088 | live |
| Valuation · MVRV Z | 0.8725 | STALE (carried_forward) |
| Miners · Puell | 0.8901 | STALE (carried_forward) |
| Sentiment · F&G | 69 | live |
| Supply · ETH netflow 7d | -122,465 | live |
| BTC dominance % | 58.56 | live |

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

- **10-dimension (shadow):** 2 of 4 fired, threshold 5 → would not fire
  - grade **C** — watch - some evidence, below the historical bar (2.0 of 4.0 achievable this run)
  - reading: rotation-favourable only
  - not counted: mvrv_z_score, nvt, eth_etf_flows, stablecoin_supply_ratio
- **Legacy (retained for continuity):** 2 of 5 — fear_greed, exchange_netflows

## All signals

| Signal | Dim | Tier | Value | Vote | Provenance |
|---|---|---|---|---|---|
| eth_btc_momentum | 1 | A | 0.73 | no | live |
| btc_dominance | 1 | track | 58.56 | no | live |
| alt_dominance | 1 | track | 30.18 | — | FAILED (building) |
| altseason_index | 1 | track | — | — | not automated |
| mvrv_z_score | 2 | A | 0.8725 | — | STALE (carried_forward) |
| nvt | 2 | A | 26.18 | — | STALE (carried_forward) |
| mvrv_ratio | 2 | track | 1.47 | — | live |
| mayer_multiple | 2 | track | 1.1226 | — | STALE (carried_forward) |
| puell_multiple | 2 | track | 0.8901 | — | STALE (carried_forward) |
| nupl | 2 | track | 0.3276 | — | STALE (carried_forward) |
| lth_share | 9 | track | 0.806 | — | live |
| peak_indicators | 4 | track | — | — | not automated |
| fear_greed | 3 | track | 69 | YES | live |
| social_volume | 3 | track | — | — | not automated |
| eth_etf_flows | 5 | A | — | — | not automated |
| stablecoin_supply_ratio | 6 | A | 6.1628 | — | STALE (carried_forward) |
| alt_funding_rates | 7 | A | 3.13 | no | live |
| exchange_netflows | 9 | A | -122465.07 | YES | live |
| sopr | 9 | track | 1.0022 | — | STALE (carried_forward) |
| sth_realized_price | 10 | A | 71088.01 | YES | live |
