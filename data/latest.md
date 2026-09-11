# Signal snapshot — 2026-09-11

**v2.0 — instrument qui gouverne : `gate_legacy`**

| Instrument | Statut | Rôle |
|---|---|---|
| `gate_legacy` | **GOUVERNE** | gouverne jusqu a ADOPTED_FROM, par continuite |
| `gate_new` | ombre | gouverne a partir de ADOPTED_FROM |
| `ladder_shadow` | ombre | ombre indefinie - mise a jour de strategie non signee |
| `evidence_gate` | ombre | ombre par construction - portee, pas decision |

Generated 2026-09-11T10:04:28.613427+00:00 · schema v5

> **DEGRADED RUN** — 0 failed, 2 stale. Check provenance before using these numbers.

## For the weekly brief composite

| Dimension | Value | Provenance |
|---|---|---|
| Regime · STH-RP | $71,168 | live |
| Valuation · MVRV Z | 0.8394 | live |
| Miners · Puell | 0.8894 | live |
| Sentiment · F&G | 56 | live |
| Supply · ETH netflow 7d | -113,523 | live |
| BTC dominance % | 58.46 | live |

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
- **Legacy (retained for continuity):** 1 of 5 — exchange_netflows

## All signals

| Signal | Dim | Tier | Value | Vote | Provenance |
|---|---|---|---|---|---|
| eth_btc_momentum | 1 | A | 1.78 | no | live |
| btc_dominance | 1 | track | 58.46 | no | live |
| alt_dominance | 1 | track | 30.15 | — | FAILED (building) |
| altseason_index | 1 | track | — | — | not automated |
| mvrv_z_score | 2 | A | 0.8394 | no | live |
| nvt | 2 | A | 23.56 | no | live |
| mvrv_ratio | 2 | track | 1.441 | — | live |
| mayer_multiple | 2 | track | 1.0959 | — | live |
| puell_multiple | 2 | track | 0.8894 | — | live |
| nupl | 2 | track | 0.3387 | — | STALE (stale) |
| lth_share | 9 | track | 0.807 | — | live |
| peak_indicators | 4 | track | — | — | not automated |
| fear_greed | 3 | track | 56 | no | live |
| social_volume | 3 | track | — | — | not automated |
| eth_etf_flows | 5 | A | — | — | not automated |
| stablecoin_supply_ratio | 6 | A | 6.029 | no | live |
| alt_funding_rates | 7 | A | 1.33 | no | live |
| exchange_netflows | 9 | A | -113522.86 | YES | live |
| sopr | 9 | track | 1.004 | — | STALE (stale) |
| sth_realized_price | 10 | A | 71168.03 | YES | live |
