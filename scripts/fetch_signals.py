#!/usr/bin/env python3
"""
Daily signal fetcher for the crypto rotation gate.

Two gates run side by side:

  LEGACY  - the original flat gate. Stays AUTHORITATIVE until ADOPTED_FROM.
  NEW     - the 10-dimension MECE gate in dimensions.py. Runs in SHADOW mode
            until ADOPTED_FROM, logging what it would have said.

Collecting a signal is not voting on it. Nothing here changes a decision
before dimensions.ADOPTED_FROM.

Design principles
-----------------
1. KEYLESS FIRST. Every signal that can be sourced without an API key is.
2. Keys are UPGRADES, not requirements.
3. FALLBACK CHAINS. Exchange APIs geo-block datacenter IPs; GitHub runners
   are datacenter IPs. Verified: Binance 451 and Bybit 403 from runners.
4. RESPECT RATE BUDGETS. BGeometrics allows 10 requests/hour. Its fetches
   never retry, because retrying a 429 spends the budget that is already
   exhausted.
5. NEVER CRASH. One dead source degrades to a status field.

Output: data/signals_YYYY-MM-DD.json  and  data/signals_history.jsonl
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dimensions
import resilience
import report
import ladder

UA = {"User-Agent": "signal-pipeline/3.0 (personal use)"}
TIMEOUT = 20

# -- TUNE HERE ---------------------------------------------------------------
THRESHOLDS = {
    # legacy gate (unchanged - these still govern until ADOPTED_FROM)
    "fear_greed_above": 60,
    "btc_dominance_below": 54.0,
    "mvrv_ratio_above": 3.0,
    "alt_funding_apr_above": 25.0,
    "eth_netflow_7d_below": 0.0,
    # new 10-dimension gate
    "eth_btc_momentum_14d_above_pct": 10.0,
    "mvrv_z_above": 3.0,
    "nvt_above_own_90d_avg": True,
    "ssr_falling_over_days": 30,
    "funding_must_be_rising": True,
    # a source whose as_of is older than this is reported stale, not fresh
    "max_source_age_days": 3,
}

CM_API = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
BG_API = "https://bitcoin-data.com/api/v1"
ALTS = ["ETHUSDT", "SOLUSDT", "XRPUSDT", "HYPEUSDT"]
# HYPE lists only on some venues; providers return what they have and the
# average is taken over whatever came back, so a missing symbol is not fatal.


def _get(url, headers=None, retries=3):
    """GET + JSON with backoff on rate limits and transient 5xx."""
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={**UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 418, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            raise
        except Exception as e:
            last = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    raise last


def _post(url, payload, headers=None, retries=3):
    """POST + JSON with the same backoff policy as _get."""
    body = json.dumps(payload).encode()
    hdrs = {**UA, "Content-Type": "application/json", **(headers or {})}
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 418, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            raise
        except Exception as e:
            last = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    raise last


def safe_fetch(fn):
    """Wrap any fetch so one failing source never kills the whole run."""
    try:
        result = fn()
        result["status"] = result.get("status", "ok")
        return result
    except urllib.error.HTTPError as e:
        return {"status": "http_error", "code": e.code, "signal": None,
                "vote": None, "fired_rotation_gate": None}
    except Exception as e:
        return {"status": "error", "error": str(e)[:200], "signal": None,
                "vote": None, "fired_rotation_gate": None}


def _previous_run():
    """Last entry of the history log, for rate-of-change signals."""
    try:
        with open("data/signals_history.jsonl") as f:
            lines = [l for l in f if l.strip()]
        return json.loads(lines[-1]) if lines else None
    except Exception:
        return None


def _coinmetrics(assets, metric, days=25):
    """Daily series from the CoinMetrics community tier. No key required."""
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    url = (f"{CM_API}?assets={assets}&metrics={metric}&frequency=1d"
           f"&start_time={start}&end_time={end}&sort=time&page_size=10000")
    data = _get(url)
    if "error" in data:
        raise ValueError("coinmetrics: " + str(data["error"].get("message", "unknown")))
    series = {}
    for row in data.get("data", []):
        if row.get(metric) is not None:
            series.setdefault(row["asset"], []).append(
                (row["time"][:10], float(row[metric]))
            )
    return series


# ============================================================================
# DIMENSION 1 - RELATIVE MOMENTUM
# ============================================================================

def fetch_eth_btc_momentum():
    """ETH/BTC 14-day change. Replaces the old vague 'turning up weekly'
    with the numeric rule from the spec: +10% over 14 days."""
    data = _get("https://api.coingecko.com/api/v3/coins/ethereum/market_chart"
                "?vs_currency=btc&days=14")
    prices = [p[1] for p in data.get("prices", []) if p and p[1]]
    if len(prices) < 2:
        raise ValueError("coingecko returned insufficient ETH/BTC history")
    first, last = prices[0], prices[-1]
    change = (last / first - 1) * 100
    thr = THRESHOLDS["eth_btc_momentum_14d_above_pct"]
    return {
        "signal": round(change, 2),
        "eth_btc_start": round(first, 6),
        "eth_btc_now": round(last, 6),
        "window_days": 14,
        "source": "coingecko (keyless)",
        "vote": change > thr,
        "note": "vote fires above +%.0f%% over 14d" % thr,
    }


def fetch_alt_dominance(dominance, history_path="data/signals_history.jsonl"):
    """Dominance outside the top 2, rising over 30 days.

    Free coverage: derived entirely from btc_dominance_pct and
    eth_dominance_pct, both already fetched. No new source, no new key, no new
    rate budget. Identified by the Pivot Ladder review as the single cheapest
    way to lift measurable coverage back over the 70% floor.

    The 30-day series is accumulated from this repo's own history log, so it
    reports `building` honestly until enough days exist rather than voting on
    a window it does not have.
    """
    btc = dominance.get("btc_dominance_pct")
    eth = dominance.get("eth_dominance_pct")
    if btc is None or eth is None:
        raise ValueError("dominance unavailable, cannot derive alt dominance")
    current = 100.0 - btc - eth

    series = []
    try:
        with open(history_path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                d = (row.get("signals") or {}).get("btc_dominance") or {}
                b, e = d.get("btc_dominance_pct"), d.get("eth_dominance_pct")
                if b is not None and e is not None:
                    series.append((row.get("date"), 100.0 - b - e))
    except FileNotFoundError:
        pass

    # one point per day, last write wins
    by_date = {}
    for d, v in series:
        if d:
            by_date[d] = v
    ordered = [by_date[d] for d in sorted(by_date)]

    if len(ordered) < 30:
        return {
            "status": "building",
            "signal": round(current, 2),
            "vote": None,
            "days_available": len(ordered),
            "days_required": 30,
            "source": "derived (btc + eth dominance, keyless)",
            "note": "accumulating the 30-day window from this repo's own "
                    "history; votes once %d days exist" % 30,
        }

    ref = ordered[-30]
    return {
        "signal": round(current, 2),
        "ref_30d": round(ref, 2),
        "change_pct": round(current - ref, 2),
        "source": "derived (btc + eth dominance, keyless)",
        "vote": current > ref,
        "note": "votes when dominance outside the top 2 is rising over 30 days",
    }


def fetch_altseason_index():
    """TRACKED ONLY. % of the top 100 outperforming BTC over 90 days,
    computed directly rather than taken from a third-party index."""
    data = _get("https://api.coingecko.com/api/v3/coins/markets"
                "?vs_currency=usd&order=market_cap_desc&per_page=100&page=1"
                "&price_change_percentage=90d")
    field = "price_change_percentage_90d_in_currency"
    btc = next((c for c in data if c.get("id") == "bitcoin"), None)
    if not btc or btc.get(field) is None:
        # The keyless tier silently drops price_change_percentage=90d: it
        # returns 200 with 24h fields only. A free demo key restores it.
        return {"status": "needs_key", "signal": None, "vote": None,
                "source": "coingecko",
                "note": "90d window requires COINGECKO_API_KEY - the keyless "
                        "tier returns 200 but omits the 90d field"}
    btc_perf = float(btc[field])
    peers = [c for c in data
             if c.get("id") != "bitcoin" and c.get(field) is not None]
    if not peers:
        raise ValueError("coingecko: no peer 90d data")
    outperformers = [c for c in peers if float(c[field]) > btc_perf]
    pct = len(outperformers) / len(peers) * 100
    return {
        "signal": round(pct, 1),
        "btc_90d_pct": round(btc_perf, 2),
        "sample_size": len(peers),
        "outperforming": len(outperformers),
        "source": "coingecko (keyless, computed)",
        "vote": None,  # tracked only - never votes
        "note": "tracked only; promotion to Tier A requires evidence per Part D/E",
    }


# ============================================================================
# DIMENSION 2 - VALUATION  (BGeometrics, keyless, 10 req/hour budget)
# ============================================================================

def _bg(endpoint):
    """BGeometrics fetch. retries=1 on purpose: the free tier allows 10
    requests/hour, so retrying a 429 spends budget that is already gone."""
    return _get(f"{BG_API}/{endpoint}", retries=1)


def fetch_mvrv_z_score():
    """True MVRV Z-Score. The spec listed this as needing a BGeometrics key;
    it does not - the endpoint is free."""
    d = _bg("mvrv-zscore/last")
    val = float(d["mvrvZscore"])
    return {
        "signal": round(val, 4),
        "as_of": d.get("d"),
        "metric": "mvrv_z_score",
        "source": "bgeometrics (keyless)",
        "vote": val > THRESHOLDS["mvrv_z_above"],
    }


def fetch_nvt():
    """NVT vs its own 90-day average."""
    hist = _bg("nvt")
    series = [float(r["nvt"]) for r in hist if r.get("nvt") is not None]
    if len(series) < 90:
        raise ValueError("bgeometrics returned only %d NVT points" % len(series))
    window = series[-90:]
    avg90 = sum(window) / len(window)
    latest = series[-1]
    return {
        "signal": round(latest, 3),
        "avg_90d": round(avg90, 3),
        "as_of": hist[-1].get("d"),
        "source": "bgeometrics (keyless)",
        "vote": latest > avg90,
        "note": "votes when NVT sits above its own 90-day average",
    }


def fetch_puell_multiple():
    """TRACKED ONLY for the rotation gate, but this feeds the WEEKLY BRIEF's
    Miners dimension, which has been frozen on an estimate for four editions.
    Keyless - no reason for it to stay unverified."""
    d = _bg("puell-multiple/last")
    return {
        "signal": round(float(d["puellMultiple"]), 4),
        "as_of": d.get("d"),
        "source": "bgeometrics (keyless)",
        "vote": None,
        "note": "feeds the brief's Miners dimension; replaces the frozen estimate",
    }


def fetch_mayer_multiple():
    """TRACKED ONLY - second valuation basis, no vote."""
    d = _bg("mayer-multiple/last")
    return {
        "signal": round(float(d["mayerMultiple"]), 4),
        "as_of": d.get("d"),
        "source": "bgeometrics (keyless)",
        "vote": None,
    }


# ============================================================================
# DIMENSION 3 - SENTIMENT
# ============================================================================

def fetch_fear_greed():
    """alternative.me - canonical F&G per protocol, NOT CFGI."""
    data = _get("https://api.alternative.me/fng/?limit=1&format=json")
    entry = data["data"][0]
    val = int(entry["value"])
    fired = val > THRESHOLDS["fear_greed_above"]
    return {
        "signal": val,
        "classification": entry["value_classification"],
        "source": "alternative.me",
        "vote": fired,
        "fired_rotation_gate": fired,  # legacy gate
    }


def fetch_social_volume():
    """TRACKED ONLY. LunarCrush - no credible free replacement exists.

    Deliberately NOT implemented. An earlier version shipped a fetch written
    from documentation that had never executed against a live key. Code that
    looks functional but is unverified is worse than an honest stub: it reads
    as working capability in review, and fails at the first real use.

    To implement: obtain a key, run the call once by hand, confirm the actual
    response shape, then write the parser against what you observed.
    """
    if os.environ.get("LUNARCRUSH_API_KEY"):
        return {"status": "not_implemented", "signal": None, "vote": None,
                "note": "key present but no verified parser exists - see docstring"}
    return {"status": "no_key", "signal": None, "vote": None,
            "note": "paid-only; the one signal with no free equivalent"}


# ============================================================================
# DIMENSION 5 - INSTITUTIONAL DEMAND
# ============================================================================

def fetch_eth_etf_flows():
    """Farside/SoSoValue have no stable public API. Honest stub by design:
    pull this in the weekly brief's web_search step rather than shipping a
    scraper that rots silently."""
    return {"status": "no_api", "signal": None, "vote": None,
            "note": "no stable public API - weekly web_search item, "
                    "reduces the denominator rather than voting no"}


# ============================================================================
# DIMENSION 6 - LIQUIDITY
# ============================================================================

def fetch_stablecoin_supply_ratio():
    """SSR falling = stablecoin buying power growing relative to BTC cap.

    Note the endpoint is `ssr`; `stablecoin-supply-ratio` 404s.
    """
    hist = _bg("ssr")
    # field is `ssrStablecoin`; the endpoint named `stablecoin-supply-ratio` 404s
    series = [(r.get("d"), float(r["ssrStablecoin"]))
              for r in hist if r.get("ssrStablecoin") is not None]
    if len(series) < 2:
        raise ValueError("bgeometrics returned insufficient SSR history")
    lookback = THRESHOLDS["ssr_falling_over_days"]
    latest = series[-1][1]
    ref = series[-min(lookback, len(series))][1]
    return {
        "signal": round(latest, 4),
        "ref_value": round(ref, 4),
        "lookback_days": lookback,
        "as_of": series[-1][0],
        "change_pct": round((latest / ref - 1) * 100, 2) if ref else None,
        "source": "bgeometrics (keyless)",
        "vote": latest < ref,
        "note": "votes when SSR is falling over the lookback window",
    }


# ============================================================================
# DIMENSION 7 - DERIVATIVES POSITIONING
# ============================================================================

def _funding_binance():
    data = _get("https://fapi.binance.com/fapi/v1/premiumIndex")
    rates = {d["symbol"]: float(d["lastFundingRate"]) for d in data}
    return {s: rates[s] for s in ALTS if s in rates}, "binance", 3


def _funding_bybit():
    out = {}
    for sym in ALTS:
        d = _get("https://api.bybit.com/v5/market/tickers"
                 "?category=linear&symbol=" + sym)
        lst = d.get("result", {}).get("list") or []
        if lst and lst[0].get("fundingRate") not in (None, ""):
            out[sym] = float(lst[0]["fundingRate"])
    return out, "bybit", 3


def _funding_okx():
    out = {}
    for sym in ALTS:
        inst = sym.replace("USDT", "-USDT-SWAP")
        d = _get("https://www.okx.com/api/v5/public/funding-rate?instId=" + inst)
        rows = d.get("data") or []
        if rows and rows[0].get("fundingRate"):
            out[sym] = float(rows[0]["fundingRate"])
    return out, "okx", 3


def _funding_hyperliquid():
    """Last-resort fallback. A DEX, so no geo-blocking - which matters because
    Binance (451) and Bybit (403) both refuse GitHub runner IPs.
    NOTE: funding settles HOURLY here, not 8-hourly."""
    meta, ctxs = _post("https://api.hyperliquid.xyz/info",
                       {"type": "metaAndAssetCtxs"})
    wanted = {s.replace("USDT", ""): s for s in ALTS}
    out = {}
    for i, coin in enumerate(meta.get("universe", [])):
        name = coin.get("name")
        if name in wanted and not coin.get("isDelisted") and i < len(ctxs):
            funding = ctxs[i].get("funding")
            if funding is not None:
                out[wanted[name]] = float(funding)
    return out, "hyperliquid", 24


def fetch_funding_rates(previous=None):
    """Perp funding for the alt basket.

    Spec rule is 'positive AND rising', so the vote needs the prior run.
    Each provider declares settlements-per-day so APR is comparable across
    venues (CEXes 8-hourly, Hyperliquid hourly).
    """
    errors = []
    for provider in (_funding_binance, _funding_bybit,
                     _funding_okx, _funding_hyperliquid):
        try:
            rates, source, per_day = provider()
            if not rates:
                errors.append(provider.__name__ + ": empty")
                continue
            per_sym = {
                s: {
                    "rate_pct": round(r * 100, 6),
                    "settlements_per_day": per_day,
                    "apr_pct": round(r * per_day * 365 * 100, 2),
                }
                for s, r in rates.items()
            }
            avg_apr = round(
                sum(v["apr_pct"] for v in per_sym.values()) / len(per_sym), 2
            )

            prev_apr = None
            if previous:
                pf = previous.get("signals", {}).get("alt_funding_rates", {})
                if isinstance(pf, dict):
                    prev_apr = pf.get("alt_avg_funding_apr_pct")

            rising = None if prev_apr is None else avg_apr > prev_apr
            vote = None if rising is None else (avg_apr > 0 and rising)

            return {
                "signal": avg_apr,
                "alt_avg_funding_apr_pct": avg_apr,
                "previous_apr_pct": prev_apr,
                "rising": rising,
                "per_symbol": per_sym,
                "source": source + " (keyless)",
                "fallbacks_tried": errors or None,
                "vote": vote,
                "fired_rotation_gate": avg_apr > THRESHOLDS["alt_funding_apr_above"],
                "note": "vote needs positive AND rising; None on the first run "
                        "of a fresh history log, when there is no prior value",
            }
        except Exception as e:
            errors.append(provider.__name__ + ": " + str(e)[:80])
    raise RuntimeError("all funding providers failed: " + "; ".join(errors))


# ============================================================================
# DIMENSION 9 - SUPPLY SIDE
# ============================================================================

def fetch_exchange_netflows():
    """Day-over-day change in exchange-held supply = net flow.
    Negative = coins leaving exchanges (accumulation)."""
    series = _coinmetrics("btc,eth", "SplyExNtv")
    out = {}
    for asset in ("btc", "eth"):
        pts = series.get(asset, [])
        if len(pts) < 2:
            out[asset] = {"held_native": None, "netflow_1d": None, "netflow_7d": None}
            continue
        held = pts[-1][1]
        d7 = held - pts[-8][1] if len(pts) >= 8 else None
        out[asset] = {
            "as_of": pts[-1][0],
            "held_native": round(held, 2),
            "netflow_1d": round(held - pts[-2][1], 2),
            "netflow_7d": round(d7, 2) if d7 is not None else None,
        }
    eth7 = out["eth"]["netflow_7d"]
    fired = eth7 is not None and eth7 < THRESHOLDS["eth_netflow_7d_below"]
    return {
        "signal": eth7,
        "btc": out["btc"],
        "eth": out["eth"],
        "source": "coinmetrics (community, keyless)",
        "interpretation": "negative = net outflow from exchanges = accumulation",
        "vote": None if eth7 is None else fired,
        "fired_rotation_gate": fired,  # legacy gate
    }


def fetch_sopr():
    """TRACKED ONLY - spent output profit ratio."""
    d = _bg("sopr/last")
    return {
        "signal": round(float(d["sopr"]), 4),
        "as_of": d.get("d"),
        "source": "bgeometrics (keyless)",
        "vote": None,
    }


# ============================================================================
# DIMENSION 10 - INFLECTION / PHASE CHANGE
# ============================================================================

def fetch_sth_realized_price(btc_price=None):
    """Short-term-holder cost basis. Votes when price closes above it.

    BTC only - no free ETH equivalent has been found. That remains the one
    genuinely unresolved gap in the spec.
    """
    d = _bg("sth-realized-price/last")
    sth = float(d["sthRealizedPrice"])
    if btc_price is None:
        return {"signal": round(sth, 2), "as_of": d.get("d"),
                "btc_price_usd": None, "vote": None,
                "source": "bgeometrics (keyless)",
                "status": "no_price",
                "note": "BTC price unavailable this run, cannot compare"}
    return {
        "signal": round(sth, 2),
        "sth_realized_price_usd": round(sth, 2),
        "btc_price_usd": btc_price,
        "premium_pct": round((btc_price / sth - 1) * 100, 2),
        "as_of": d.get("d"),
        "source": "bgeometrics (keyless)",
        "vote": btc_price > sth,
        "note": "BTC only - no free ETH equivalent found (open gap)",
    }


# ============================================================================
# LEGACY SIGNALS (still authoritative until ADOPTED_FROM)
# ============================================================================

def fetch_btc_dominance():
    """CoinGecko /global + /simple/price. Dominance is TRACKED under the new
    gate but still votes in the legacy gate until ADOPTED_FROM."""
    key = os.environ.get("COINGECKO_API_KEY")
    headers = {"x-cg-demo-api-key": key} if key else {}
    base = "https://api.coingecko.com/api/v3"

    glob = _get(base + "/global", headers=headers)
    mcap = glob["data"]["market_cap_percentage"]
    btc_dom, eth_dom = mcap.get("btc"), mcap.get("eth")

    time.sleep(2.0)  # courtesy spacing; the keyless tier is unforgiving

    prices = _get(base + "/simple/price?ids=bitcoin,ethereum&vs_currencies=usd",
                  headers=headers)
    btc_price = prices["bitcoin"]["usd"]
    eth_price = prices["ethereum"]["usd"]
    fired = btc_dom is not None and btc_dom < THRESHOLDS["btc_dominance_below"]

    return {
        "signal": round(btc_dom, 2) if btc_dom is not None else None,
        "btc_dominance_pct": round(btc_dom, 2) if btc_dom is not None else None,
        "eth_dominance_pct": round(eth_dom, 2) if eth_dom is not None else None,
        "btc_price_usd": btc_price,
        "eth_price_usd": eth_price,
        "eth_btc_ratio": round(eth_price / btc_price, 5) if btc_price else None,
        "source": "coingecko" + (" (demo key)" if key else " (keyless)"),
        # Tracked-only for the 10-dimension GATE (it carries no Tier A vote
        # there), but the ladder's ROTATION AXIS needs it as a live vote at
        # weight 1.0. Leaving vote=None made it unmeasurable for the ladder
        # and dropped coverage to 56.25% - the ladder then froze for a reason
        # that was an integration bug, not a data gap. dimensions.tally and
        # dimensions.grade both iterate TIER_A_SIGNALS only, so a vote here
        # cannot leak into the gate tally.
        "vote": fired,
        "fired_rotation_gate": fired,  # legacy gate
    }


def fetch_mvrv_ratio():
    """CoinMetrics MVRV ratio. TRACKED under the new gate (superseded by the
    true Z-Score) but still votes in the legacy gate."""
    series = _coinmetrics("btc", "CapMVRVCur")
    points = series.get("btc", [])
    if not points:
        raise ValueError("coinmetrics returned no MVRV data for btc")
    as_of, val = points[-1]
    fired = val > THRESHOLDS["mvrv_ratio_above"]
    return {
        "signal": round(val, 3),
        "metric": "mvrv_ratio",
        "as_of": as_of,
        "source": "coinmetrics (community, keyless)",
        "vote": None,
        "fired_rotation_gate": fired,  # legacy gate
        "note": "ratio, not Z-Score - see mvrv_z_score for the Tier A signal",
    }


# ============================================================================
# ORCHESTRATION
# ============================================================================

def legacy_tally(signals):
    """The original flat gate. Unchanged, and authoritative until ADOPTED_FROM."""
    fired, checkable = [], []
    for name, val in signals.items():
        if not isinstance(val, dict) or "fired_rotation_gate" not in val:
            continue
        if val["fired_rotation_gate"] is None:
            continue
        checkable.append(name)
        if val["fired_rotation_gate"]:
            fired.append(name)
    return {
        "fired": len(fired),
        "checkable_today": len(checkable),
        "fired_signals": fired,
        "note": "only counts signals this run could verify - missing sources "
                "reduce the denominator, not the numerator",
    }


def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    previous = _previous_run()

    # dominance first: it supplies the BTC price the STH-RP comparison needs
    dominance = safe_fetch(fetch_btc_dominance)
    btc_price = dominance.get("btc_price_usd")

    signals = {
        # dimension 1
        "eth_btc_momentum": safe_fetch(fetch_eth_btc_momentum),
        "btc_dominance": dominance,
        "alt_dominance": safe_fetch(lambda: fetch_alt_dominance(dominance)),
        "altseason_index": safe_fetch(fetch_altseason_index),
        # dimension 2
        "mvrv_z_score": safe_fetch(fetch_mvrv_z_score),
        "nvt": safe_fetch(fetch_nvt),
        "mvrv_ratio": safe_fetch(fetch_mvrv_ratio),
        "mayer_multiple": safe_fetch(fetch_mayer_multiple),
        "puell_multiple": safe_fetch(fetch_puell_multiple),
        # dimension 3
        "fear_greed": safe_fetch(fetch_fear_greed),
        "social_volume": safe_fetch(fetch_social_volume),
        # dimension 5
        "eth_etf_flows": safe_fetch(fetch_eth_etf_flows),
        # dimension 6
        "stablecoin_supply_ratio": safe_fetch(fetch_stablecoin_supply_ratio),
        # dimension 7
        "alt_funding_rates": safe_fetch(lambda: fetch_funding_rates(previous)),
        # dimension 9
        "exchange_netflows": safe_fetch(fetch_exchange_netflows),
        "sopr": safe_fetch(fetch_sopr),
        # dimension 10
        "sth_realized_price": safe_fetch(lambda: fetch_sth_realized_price(btc_price)),
    }

    # Degradation policy, in order: recover what we can, then demote anything
    # that is not genuinely fresh. Both steps strip votes from stale values,
    # so nothing old can quietly drive the gate.
    resilience.carry_forward(signals, previous, today)
    resilience.check_staleness(signals, today, THRESHOLDS["max_source_age_days"])
    # freezing is a temporary state with an expiry, never a stable one
    resilience.track_freeze_streak(signals, previous, dimensions.MAX_FROZEN_RUNS)

    dimensions.annotate(signals)

    snapshot = {
        "date": today,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": 4,
        "thresholds": THRESHOLDS,
        "signals": signals,
        "health": resilience.health(signals),
        "gate_legacy": legacy_tally(signals),
        "gate_new": dimensions.tally(signals, today),
        "gate_grade": dimensions.grade(signals),
        "ladder_shadow": ladder.evaluate(signals, previous),
    }

    os.makedirs("data", exist_ok=True)
    with open("data/signals_" + today + ".json", "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)
    with open("data/signals_history.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot) + "\n")
    # fixed-path artefacts so a consumer never has to construct a dated path
    report.write_all(snapshot)

    h = snapshot["health"]
    if h["failed"]:
        print("WARNING: %d source(s) failed: %s"
              % (h["failed"], h["failed_signals"]), file=sys.stderr)
    if h["stale"]:
        print("WARNING: %d source(s) stale/carried: %s"
              % (h["stale"], h["stale_signals"]), file=sys.stderr)

    print(json.dumps(snapshot, indent=2))
    return 1 if snapshot["gate_legacy"]["checkable_today"] == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
