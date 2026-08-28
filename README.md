# signal-pipeline

Daily crypto rotation-gate signals, committed to this repo by a GitHub Action.

Runs at **06:00 UTC daily**, or on demand from the **Actions** tab
(*Daily Signal Fetch* → *Run workflow*).

Output:
- `data/signals_YYYY-MM-DD.json` — one snapshot per day
- `data/signals_history.jsonl` — append-only log, one line per run

---

## Signal status

Five of seven signals need **no API key at all**.

| Signal | Source | Key | Verified live |
|---|---|---|---|
| Fear & Greed | alternative.me | none | yes |
| BTC/ETH dominance + prices | CoinGecko | optional | yes |
| MVRV | CoinMetrics community | none | yes |
| Exchange netflows | CoinMetrics community | none | yes |
| Alt funding rates | Binance → Bybit → OKX → Hyperliquid | none | yes |
| Social volume | LunarCrush | **required, paid** | no |
| Alt ETF flows | — | no public API | n/a |

"Verified live" = actually returned real data during setup, not just written
against docs.

### Verified from a GitHub runner

Confirmed end-to-end on run
[33171527807](https://github.com/compain-david/Signal-pipeline/actions):
**5 of 5 checkable signals returned real data**, and the runner committed its
snapshot back to `data/`.

That run also proved why the funding fallback chain exists:

```
binance: HTTP Error 451     <- geo-blocked from the runner IP
bybit:   HTTP Error 403     <- blocked
okx:     ok
```

Two of three exchanges refuse GitHub's datacenter IPs. A single-exchange
implementation would have shipped a permanently dead signal that looked fine
in local testing. Hyperliquid was added afterwards as a fourth link — it's a
DEX with no geo-blocking, so it should survive even if OKX starts refusing
runner traffic too.

CoinGecko's keyless tier **did** work from the runner, so the demo key below
is insurance against future throttling rather than an urgent fix.

### What changed from v1

The first version required paid keys for four signals, and three of those
returned `not_implemented` *even with a valid key*. Keyless equivalents were
found for three of them:

- **MVRV** — Glassnode → CoinMetrics `CapMVRVCur`. Note this is the MVRV
  **ratio**, not the **Z-Score**. Different scales. Setting `GLASSNODE_API_KEY`
  switches back to the true Z-Score automatically; the `metric` field in the
  output always records which one you got.
- **Exchange netflows** — CryptoQuant → day-over-day delta of CoinMetrics
  `SplyExNtv` (exchange-held supply). Negative = coins leaving exchanges.
- **Alt funding** — Coinglass → exchange APIs directly, with a three-provider
  fallback chain.

CryptoQuant and Coinglass are no longer referenced anywhere. Don't pay for them
on this pipeline's account.

---

## What you need to do

**Nothing is required.** It runs today as-is. In priority order:

### 1. ~~Confirm it works from a runner~~ — done

Already verified (see above): 5 of 5 checkable signals, snapshot committed.
Nothing needed from you here.

### 2. Add a free CoinGecko demo key (3 min, recommended — not urgent)

Insurance, not a fix: the keyless tier worked from the runner, but CoinGecko
throttles datacenter traffic and that can change without notice.

1. Sign up at <https://www.coingecko.com/en/developers/dashboard> (free tier)
2. Create a Demo API key
3. Repo **Settings → Secrets and variables → Actions → New repository secret**
4. Name: `COINGECKO_API_KEY`, value: your key

The code picks it up automatically and reports `coingecko (demo key)` in the
output.

### 3. Optional upgrades

- `GLASSNODE_API_KEY` — swaps MVRV ratio for the true Z-Score. Check their
  current free tier actually includes MVRV Z-Score before relying on it; if the
  call fails the code falls back to CoinMetrics silently, so a bad key
  degrades rather than breaks.
- `LUNARCRUSH_API_KEY` — paid. The only signal with no free equivalent. Its
  response shape is written from docs and **has never been run against a live
  key** — treat the first keyed run as a test.

### 4. Alt ETF flows stay manual

Farside and SoSoValue have no stable public API. Scraping them breaks silently,
which is worse than not having the number. Pull this in the weekly brief's
`web_search` step instead.

---

## Tuning the gate

All thresholds are in one dict at the top of
[`scripts/fetch_signals.py`](scripts/fetch_signals.py):

```python
THRESHOLDS = {
    "fear_greed_above": 60,          # original rule
    "btc_dominance_below": 54.0,     # original rule
    "mvrv_z_above": 3.0,             # original rule (Glassnode Z-Score only)
    "mvrv_ratio_above": 3.0,         # PROVISIONAL
    "alt_funding_apr_above": 25.0,   # PROVISIONAL
    "eth_netflow_7d_below": 0.0,     # PROVISIONAL
}
```

The three marked **PROVISIONAL** are defaults chosen during setup for the newly
added signals, not rules you set. Review them before trusting the tally.

`mvrv_ratio_above` especially: 3.0 was carried over from the Z-Score rule
because the two metrics happen to have similar cycle-top ranges, but they are
**not** the same measure. Current ratio is ~1.51.

### Reading `gate_tally`

```json
"gate_tally": {"fired": 2, "checkable_today": 5, "fired_signals": [...]}
```

`checkable_today` is the denominator — signals that actually returned a value
this run. Missing sources shrink the denominator rather than counting as "not
fired", so a 2/5 never silently reads as 2/7.

Semantics are mixed by design and inherited from the original gate: froth
indicators (F&G high, MVRV high) and alts-leading indicators (dominance low)
are counted in the same tally. It's a "late-cycle / rotation window" count,
not a directional buy signal.

---

## Local run

```bash
python scripts/fetch_signals.py
```

Stdlib only, no dependencies. Exits non-zero only if *zero* signals were
checkable.

## Caveats

- Funding APR is annualised using each venue's settlement frequency (CEXes
  8-hourly, Hyperliquid hourly), recorded per symbol as
  `settlements_per_day`. A few individual pairs deviate from their venue's
  default, so the APR is indicative rather than exact.
- Because the venue can change between runs via the fallback chain, compare
  `source` before reading too much into a day-over-day funding move.
- Exchange-held supply is an estimate from labelled addresses, and is a proxy
  for netflow rather than a direct measurement of it.
- Scheduled workflows are disabled after 60 days of repository inactivity. The
  daily commits normally keep this alive, but if runs start failing
  continuously, nothing commits and the schedule can eventually stop.
