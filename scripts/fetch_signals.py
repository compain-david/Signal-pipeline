#!/usr/bin/env python3
"""
Daily signal fetcher for the crypto rotation gate.

Design principles
-----------------
1. KEYLESS FIRST. Every signal that can be sourced without an API key is.
   Five of seven signals now need no secrets at all.
2. Keys are UPGRADES, not requirements. Where a paid source is genuinely
   better (Glassnode's true MVRV Z-Score), the key path is tried first and
   silently falls back to the keyless equivalent on any failure.
3. FALLBACK CHAINS. Funding rates try Binance -> Bybit -> OKX, because
   exchange APIs geo-block some datacenter IP ranges and GitHub-hosted
   runners move between them.
4. NEVER CRASH. One dead source degrades to a status field; the run still
   produces a valid snapshot.

Output: data/signals_YYYY-MM-DD.json  (snapshot)
        data/signals_history.jsonl    (append-only log)

Thresholds live in THRESHOLDS below - tune them in one place.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

UA = {"User-Agent": "signal-pipeline/2.0 (personal use)"}
TIMEOUT = 20

# -- TUNE HERE ---------------------------------------------------------------
# "fired" means: this reading is consistent with a late-cycle / alt-rotation
# window. Mixed semantics are intentional and inherited from the original gate
# (froth indicators + alts-leading indicators counted together).
THRESHOLDS = {
    "fear_greed_above": 60,          # original rule
    "btc_dominance_below": 54.0,     # original rule
    "mvrv_z_above": 3.0,             # original rule (Glassnode Z-Score only)
    "mvrv_ratio_above": 3.0,         # PROVISIONAL - ratio, NOT the same as Z-Score
    "alt_funding_apr_above": 25.0,   # PROVISIONAL - crowded longs in alts
    "eth_netflow_7d_below": 0.0,     # PROVISIONAL - net ETH leaving exchanges
}

CM_API = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
ALTS = ["ETHUSDT", "SOLUSDT", "XRPUSDT"]


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
                "fired_rotation_gate": None}
    except Exception as e:
        return {"status": "error", "error": str(e)[:200], "signal": None,
                "fired_rotation_gate": None}


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


# -- 1. FEAR & GREED - keyless ----------------------------------------------

def fetch_fear_greed():
    """alternative.me - canonical F&G per protocol, NOT CFGI."""
    data = _get("https://api.alternative.me/fng/?limit=1&format=json")
    entry = data["data"][0]
    val = int(entry["value"])
    return {
        "signal": val,
        "classification": entry["value_classification"],
        "source": "alternative.me",
        "fired_rotation_gate": val > THRESHOLDS["fear_greed_above"],
    }


# -- 2. DOMINANCE + PRICES - keyless, optional demo key lifts rate limits ----

def fetch_dominance_and_prices():
    """CoinGecko /global + /simple/price.

    A free demo key (COINGECKO_API_KEY) is optional but strongly recommended:
    the keyless public API rate-limits datacenter IPs hard, and GitHub runners
    are datacenter IPs.
    """
    key = os.environ.get("COINGECKO_API_KEY")
    headers = {"x-cg-demo-api-key": key} if key else {}
    base = "https://api.coingecko.com/api/v3"

    glob = _get(base + "/global", headers=headers)
    mcap = glob["data"]["market_cap_percentage"]
    btc_dom, eth_dom = mcap.get("btc"), mcap.get("eth")

    time.sleep(2.0)  # courtesy spacing; the keyless tier is unforgiving

    prices = _get(
        base + "/simple/price?ids=bitcoin,ethereum&vs_currencies=usd",
        headers=headers,
    )
    btc_price = prices["bitcoin"]["usd"]
    eth_price = prices["ethereum"]["usd"]

    return {
        "signal": round(btc_dom, 2) if btc_dom is not None else None,
        "btc_dominance_pct": round(btc_dom, 2) if btc_dom is not None else None,
        "eth_dominance_pct": round(eth_dom, 2) if eth_dom is not None else None,
        "btc_price_usd": btc_price,
        "eth_price_usd": eth_price,
        "eth_btc_ratio": round(eth_price / btc_price, 5) if btc_price else None,
        "source": "coingecko" + (" (demo key)" if key else " (keyless)"),
        "fired_rotation_gate": (
            btc_dom is not None and btc_dom < THRESHOLDS["btc_dominance_below"]
        ),
    }


# -- 3. MVRV - keyless via CoinMetrics, Glassnode Z-Score if key present -----

def fetch_mvrv():
    """Prefer Glassnode MVRV Z-Score when a key exists; else CoinMetrics ratio.

    IMPORTANT: these are DIFFERENT metrics with different scales. The ratio is
    market cap / realised cap. The Z-Score is (market cap - realised cap) over
    the stddev of market cap. The `metric` field records which one you got.
    """
    key = os.environ.get("GLASSNODE_API_KEY")
    if key:
        try:
            data = _get(
                "https://api.glassnode.com/v1/metrics/market/mvrv_z_score"
                "?a=BTC&i=24h&api_key=" + key
            )
            latest = data[-1] if data else {}
            val = latest.get("v")
            if val is not None:
                val = float(val)
                return {
                    "signal": round(val, 3),
                    "metric": "mvrv_z_score",
                    "source": "glassnode",
                    "fired_rotation_gate": val > THRESHOLDS["mvrv_z_above"],
                }
        except Exception:
            pass  # fall through to keyless rather than losing the signal

    series = _coinmetrics("btc", "CapMVRVCur")
    points = series.get("btc", [])
    if not points:
        raise ValueError("coinmetrics returned no MVRV data for btc")
    as_of, val = points[-1]
    return {
        "signal": round(val, 3),
        "metric": "mvrv_ratio",
        "as_of": as_of,
        "source": "coinmetrics (community, keyless)",
        "fired_rotation_gate": val > THRESHOLDS["mvrv_ratio_above"],
        "note": "MVRV ratio, not Z-Score - threshold differs; "
                "set GLASSNODE_API_KEY for the Z-Score",
    }


# -- 4. EXCHANGE NETFLOWS - keyless via exchange-held supply deltas ----------

def fetch_exchange_netflows():
    """Day-over-day change in exchange-held supply = net flow.

    Negative = coins leaving exchanges (accumulation). This replaces the
    CryptoQuant dependency entirely; CoinMetrics publishes SplyExNtv free.
    """
    series = _coinmetrics("btc,eth", "SplyExNtv")
    out = {}
    for asset in ("btc", "eth"):
        pts = series.get(asset, [])
        if len(pts) < 2:
            out[asset] = {"held_native": None, "netflow_1d": None, "netflow_7d": None}
            continue
        held = pts[-1][1]
        d1 = held - pts[-2][1]
        d7 = held - pts[-8][1] if len(pts) >= 8 else None
        out[asset] = {
            "as_of": pts[-1][0],
            "held_native": round(held, 2),
            "netflow_1d": round(d1, 2),
            "netflow_7d": round(d7, 2) if d7 is not None else None,
        }

    eth7 = out["eth"]["netflow_7d"]
    return {
        "signal": eth7,
        "btc": out["btc"],
        "eth": out["eth"],
        "source": "coinmetrics (community, keyless)",
        "interpretation": "negative = net outflow from exchanges = accumulation",
        "fired_rotation_gate": (
            eth7 is not None and eth7 < THRESHOLDS["eth_netflow_7d_below"]
        ),
    }


# -- 5. ALT FUNDING RATES - keyless, three-exchange fallback chain -----------

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
    """Last-resort fallback. Hyperliquid is a DEX with no geo-blocking, which
    matters because Binance (451) and Bybit (403) both refuse GitHub runner
    IPs. NOTE: funding settles HOURLY here, not 8-hourly."""
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


def fetch_funding_rates():
    """Perp funding for the alt basket.

    Each provider declares its settlements-per-day so the APR is comparable
    across venues: CEX perps settle every 8h (3/day), Hyperliquid hourly.
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
            return {
                "signal": avg_apr,
                "alt_avg_funding_apr_pct": avg_apr,
                "per_symbol": per_sym,
                "source": source + " (keyless)",
                "fallbacks_tried": errors or None,
                "fired_rotation_gate": avg_apr > THRESHOLDS["alt_funding_apr_above"],
            }
        except Exception as e:
            errors.append(provider.__name__ + ": " + str(e)[:80])
    raise RuntimeError("all funding providers failed: " + "; ".join(errors))


# -- 6. SOCIAL VOLUME - genuinely needs a paid key ---------------------------

def fetch_social_volume():
    """LunarCrush. No credible free replacement exists - left honest.

    UNVERIFIED: written against the documented v4 shape but never run against
    a live key. Treat the first keyed run as the test.
    """
    key = os.environ.get("LUNARCRUSH_API_KEY")
    if not key:
        return {"status": "no_key", "signal": None, "fired_rotation_gate": None,
                "note": "LunarCrush is paid-only for automation. This is the one "
                        "signal with no free equivalent - budget decision."}
    data = _get("https://lunarcrush.com/api4/public/coins/ETH/v1",
                headers={"Authorization": "Bearer " + key})
    d = data.get("data", {})
    return {
        "signal": d.get("social_volume_24h"),
        "galaxy_score": d.get("galaxy_score"),
        "alt_rank": d.get("alt_rank"),
        "source": "lunarcrush",
        "fired_rotation_gate": None,
        "note": "UNVERIFIED response shape - confirm on first keyed run",
    }


# -- 7. ALT ETF FLOWS - no stable public API --------------------------------

def fetch_alt_etf_flows():
    """Farside/SoSoValue have no stable public API. Honest stub by design:
    pull this in the weekly brief's web_search step, not from a scraper that
    will silently rot."""
    return {"status": "no_api", "signal": None, "fired_rotation_gate": None,
            "note": "no stable public API - pull via the weekly brief web_search step"}


# -- ORCHESTRATION ----------------------------------------------------------

def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    signals = {
        "date": today,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "thresholds": THRESHOLDS,
        "fear_greed": safe_fetch(fetch_fear_greed),
        "dominance_and_prices": safe_fetch(fetch_dominance_and_prices),
        "mvrv": safe_fetch(fetch_mvrv),
        "exchange_netflows": safe_fetch(fetch_exchange_netflows),
        "alt_funding_rates": safe_fetch(fetch_funding_rates),
        "social_volume": safe_fetch(fetch_social_volume),
        "alt_etf_flows": safe_fetch(fetch_alt_etf_flows),
    }

    fired, checkable, unavailable = [], [], []
    for name, val in signals.items():
        if not isinstance(val, dict) or "fired_rotation_gate" not in val:
            continue
        if val["fired_rotation_gate"] is None:
            unavailable.append(name)
        else:
            checkable.append(name)
            if val["fired_rotation_gate"]:
                fired.append(name)

    signals["gate_tally"] = {
        "fired": len(fired),
        "checkable_today": len(checkable),
        "fired_signals": fired,
        "unavailable": unavailable,
        "note": "only counts signals this run could verify - missing sources "
                "reduce the denominator, not the numerator",
    }

    os.makedirs("data", exist_ok=True)
    with open("data/signals_" + today + ".json", "w") as f:
        json.dump(signals, f, indent=2)
    with open("data/signals_history.jsonl", "a") as f:
        f.write(json.dumps(signals) + "\n")

    broken = [k for k, v in signals.items()
              if isinstance(v, dict) and v.get("status") in ("error", "http_error")]
    if broken:
        print("WARNING: %d source(s) failed: %s" % (len(broken), broken),
              file=sys.stderr)

    print(json.dumps(signals, indent=2))
    return 1 if not checkable else 0


if __name__ == "__main__":
    sys.exit(main())
