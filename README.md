# signal-pipeline

Daily crypto signals, fetched and committed by a GitHub Action.

Runs **06:00 UTC daily**, plus on any push to `scripts/` or the workflow.
No input required — it has been running unattended since 28 August 2026.

Output:
- **`data/latest.json`** — most recent snapshot at a fixed path
- **`data/latest.md`** — the same values rendered for the weekly brief
- `data/signals_YYYY-MM-DD.json` — one snapshot per day
- `data/signals_history.jsonl` — append-only log, one line per **run**

Consumers should read `latest.json` / `latest.md`. They never require
constructing a dated path or knowing whether today's run has happened yet.

---

## Two gates run side by side

> **The JSON is the source of truth for which gate governs, not this table.**
> Read `gate_new.authoritative` in `data/latest.json`. An earlier version of
> this README hardcoded "SHADOW" and went stale the moment `ADOPTED_FROM`
> passed, so the README and the JSON disagreed on the same day. A prose
> description of a state that changes by date will always drift; only the
> computed field can be trusted.

| Gate | Governs |
|---|---|
| **Legacy** — flat 5-signal gate | decisions before `ADOPTED_FROM` |
| **New** — 10-dimension MECE gate | decisions from `ADOPTED_FROM` onward |

`ADOPTED_FROM` is **2026-08-30**, so as of 31 August the new gate is
**authoritative** and the legacy gate is retained for continuity only.

Collecting a signal is not voting on it. Before `ADOPTED_FROM` the new gate
logged what it *would* have said each day, so that it activated with real
history behind it rather than from zero. That shadow period has now ended.

**Consequence worth stating plainly:** the new gate went authoritative by
calendar alone, not through the Part D/E ceremony the spec called for, and
three of its thresholds were provisional defaults at that moment. If that
ceremony has not happened, move `ADOPTED_FROM` forward rather than leaving
an unvalidated gate governing.

Flip the switch by editing one constant in
[`scripts/dimensions.py`](scripts/dimensions.py):

```python
ADOPTED_FROM = "2026-08-30"   # new gate becomes authoritative on this date
TIER_A_THRESHOLD = 5          # 5 of 9 Tier A votes
```

The date is set to the 30 August monthly edition so the new gate's first
month is itself logged and graded through the normal Part D / Part E cycle,
rather than adopted mid-week outside the cadence.

---

## The 10 dimensions

| # | Dimension | Tier A signal | Status |
|---|---|---|---|
| 1 | Relative momentum | ETH/BTC 14d change > +10% | live, keyless |
| 2 | Valuation | MVRV Z-Score > 3 | live, keyless |
| 2 | Valuation | NVT vs own 90d average | live, keyless |
| 3 | Sentiment | Fear & Greed > 60 | live, keyless |
| 5 | Institutional demand | ETH ETF net flows | **no public API** |
| 6 | Liquidity | Stablecoin Supply Ratio falling | live, keyless |
| 7 | Derivatives positioning | Alt funding positive AND rising | live, keyless |
| 9 | Supply side | ETH exchange netflows | live, keyless |
| 10 | Inflection | Price above STH realized price | live, keyless (BTC only) |

**8 of 9 Tier A signals are automated, none requiring a paid key.**
Dimensions 4 and 8 carry Tier B / tracked signals only, by design.

Also tracked, no vote: BTC dominance, altseason index, MVRV ratio, Mayer
multiple, **Puell multiple**, SOPR, social volume.

### Sources

Everything below is keyless and verified live from a GitHub runner:

- **alternative.me** — Fear & Greed
- **CoinGecko** — dominance, prices, ETH/BTC history
- **CoinMetrics community** — MVRV ratio, exchange-held supply
- **BGeometrics** (`bitcoin-data.com`) — MVRV Z-Score, NVT, SSR, STH realized
  price, Puell, Mayer, SOPR
- **Binance → Bybit → OKX → Hyperliquid** — alt perp funding, fallback chain

No Glassnode, CryptoQuant, or Coinglass subscription is needed. The original
spec assumed BGeometrics required a key; it does not.

---

## ⚠️ Not connected to the weekly brief

**The brief does not read this pipeline.** The Action writes JSON to this
repo; the brief is written separately. Nothing links them.

That gap has a cost: the brief carried Puell as a frozen estimate (~0.55) for
four editions while the measured value was freely available daily.

To close it, have the brief step fetch:

```
https://api.github.com/repos/compain-david/Signal-pipeline/contents/data/signals_<YYYY-MM-DD>.json
```

Use the **contents API**, not `raw.githubusercontent.com` — the raw host is
CDN-cached and will serve a stale file for several minutes after a run.

### Brief composite coverage

| Brief dimension | Pipeline |
|---|---|
| Regime · STH-RP | exact daily value |
| Valuation · MVRV Z | exact daily value |
| Miners · Puell | exact daily value |
| Sentiment · F&G | exact daily value |
| Demand · ETF flows | **not automatable** |
| Supply · LTH | **not sourced** |

---

## What still needs you

Nothing is blocking. In priority order:

1. **Wire the brief to read the pipeline** — highest value left. Measuring
   signals nothing reads is half a system.
2. **CoinGecko demo key** — the only signal it unlocks is the altseason
   index. The keyless tier returns HTTP 200 for
   `price_change_percentage=90d` but silently omits the field, so the signal
   degrades to `needs_key` rather than failing loudly. Free at the
   [developer dashboard](https://www.coingecko.com/en/developers/dashboard),
   then add `COINGECKO_API_KEY` under Settings → Secrets and variables →
   Actions.
3. **LunarCrush key** — paid, tracked-only, genuine budget call.

### Open gaps

- **ETH ETF flows** — Farside/SoSoValue have no stable public API. Stays a
  weekly `web_search` item. Reduces the Tier A denominator rather than
  voting no.
- **LTH supply** — no free source found (`lth-supply` 404s on BGeometrics).
- **ETH STH-RP** — BGeometrics covers BTC only; no free ETH equivalent found.
- **HYPE** — funding covers ETH/SOL/XRP only.

---

## Tests

```bash
python -m unittest discover -s tests        # offline, ~5ms, no network
RUN_LIVE_TESTS=1 python -m unittest tests.test_sources   # live contracts
```

**Offline logic tests** run on every push and gate the fetch job — a broken
edit cannot write bad data. They cover vote counting, tier rules, adoption
date behaviour, carry-forward, staleness demotion and report rendering.

**Live contract tests** assert each upstream still returns the exact field the
parser depends on. Both bugs found in development were silent field-name
mismatches that returned HTTP 200 and looked healthy:

- BGeometrics SSR returns `ssrStablecoin`, not `ssr`
- CoinGecko's keyless tier accepts `price_change_percentage=90d`, returns 200,
  and omits the field

Neither raised an error. Only a live assertion catches that class of failure.
They run **weekly** rather than per-push, because BGeometrics allows 10
requests/hour and the pipeline already uses 7.

## Degradation policy

Seven signals come from one provider (BGeometrics). There is no realistic
second free source for on-chain Bitcoin metrics, so resilience is achieved by
never silently losing a known value:

1. **Carry-forward** — if a source fails but succeeded within 3 days, the last
   good value is reused, marked `stale`, with its age.
2. **Stale values never vote.** A carried value reduces the gate denominator
   exactly like a missing one. This is the half that matters: carry-forward
   improves reporting without letting old data drive a decision.
3. **Freeze detection** — a source can return 200 forever while its `as_of`
   stops advancing. `as_of` is checked against today independently of HTTP
   status, and a frozen source is demoted and stripped of its vote.

`health.degraded` flags any run that completed while losing live data. Check
`failed_signals` before trusting a tally.

## Operational notes

**BGeometrics allows 10 requests/hour, per IP.** The pipeline uses 7 per run,
which fits a daily schedule comfortably. Its fetches use `retries=1` on
purpose — retrying a 429 spends budget that is already gone. If you push
twice in an hour, the second run's BGeometrics signals may degrade to
`http_error`; the run still succeeds and the next scheduled run recovers.

**Exchange geo-blocking is real and reproducible.** From GitHub runners,
Binance returns 451 and Bybit 403 on every run. OKX serves the data;
Hyperliquid is the DEX backstop. A single-exchange implementation would have
shipped a permanently dead signal that passed local testing.

**Funding needs a prior run.** The "positive AND rising" rule compares
against the previous history entry, so `vote` is `null` on the first run
after any schema change. It self-heals on the next run.

**History is one line per run, not per day.** Editing the pipeline triggers
extra runs. If you build anything on `signals_history.jsonl`, dedupe by
`date` taking the last entry, or you will double-count edit days.

**Thresholds** live in one dict at the top of
[`scripts/fetch_signals.py`](scripts/fetch_signals.py). Three of the new ones
are provisional defaults chosen during setup, not rules you set — review
before trusting them:

```python
"eth_btc_momentum_14d_above_pct": 10.0,   # from spec
"mvrv_z_above": 3.0,                      # from spec
"ssr_falling_over_days": 30,              # PROVISIONAL
```

## Local run

```bash
python scripts/fetch_signals.py
```

Stdlib only, no dependencies.
