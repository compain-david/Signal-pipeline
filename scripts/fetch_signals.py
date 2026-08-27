#!/usr/bin/env python3
"""
Daily signal fetcher for David's crypto rotation gate.

Design principle: never crash on a missing key. Every keyed source checks for
its env var first and writes status="no_key" if absent, so the pipeline
produces a valid (partial) output from commit day one and fills in as keys
are added to GitHub Secrets. Keyless sources (CoinGecko, alternative.me)
always attempt a real fetch.

Output: data/signals_YYYY-MM-DD.json (snapshot) and appends one line to
data/signals_history.jsonl (running log the dashboard/brief can read).
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

UA = {"User-Agent": "signal-pipeline/1.0 (personal use)"}
TIMEOUT = 15


def _get(url, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read())


def safe_fetch(name, fn):
    """Wrap any fetch so one failing source never kills the whole run."""
    try:
        result = fn()
        result["status"] = result.get("status", "ok")
        return result
    except urllib.error.HTTPError as e:
        return {"status": "http_error", "code": e.code, "signal": None}
    except Exception as e:
        return {"status": "error", "error": str(e)[:200], "signal": None}


# ── KEYLESS SOURCES — always attempted ──────────────────────────────────────

def fetch_fear_greed():
    """alternative.me — canonical F&G per protocol, NOT CFGI."""
    data = _get("https://api.alternative.me/fng/?limit=1&format=json")
    entry = data["data"][0]
    return {
        "signal": int(entry["value"]),
        "classification": entry["value_classification"],
        "source": "alternative.me",
        "fired_rotation_gate": int(entry["value"]) > 60,
    }


def fetch_dominance_and_prices():
    """CoinGecko /global for dominance, /simple/price for BTC + ETH."""
    glob = _get("https://api.coingecko.com/api/v3/global")
    btc_dom = glob["data"]["market_cap_percentage"].get("btc")
    eth_dom = glob["data"]["market_cap_percentage"].get("eth")

    time.sleep(1.5)  # keyless rate limit courtesy delay

    prices = _get(
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=bitcoin,ethereum&vs_currencies=usd"
    )
    btc_price = prices["bitcoin"]["usd"]
    eth_price = prices["ethereum"]["usd"]
    eth_btc_ratio = round(eth_price / btc_price, 5) if btc_price else None

    return {
        "signal": round(btc_dom, 2) if btc_dom else None,
        "btc_dominance_pct": round(btc_dom, 2) if btc_dom else None,
        "eth_dominance_pct": round(eth_dom, 2) if eth_dom else None,
        "btc_price_usd": btc_price,
        "eth_price_usd": eth_price,
        "eth_btc_ratio": eth_btc_ratio,
        "source": "coingecko",
        "fired_rotation_gate": bool(btc_dom and btc_dom < 54),
    }


# ── KEYED SOURCES — degrade gracefully if secret not set ───────────────────

def fetch_glassnode_mvrv():
    """MVRV Z-Score, NUPL, Puell — needs GLASSNODE_API_KEY (free tier exists)."""
    key = os.environ.get("GLASSNODE_API_KEY")
    if not key:
        return {"status": "no_key", "signal": None,
                "note": "set GLASSNODE_API_KEY in GitHub Secrets — free tier at glassnode.com"}
    url = (
        "https://api.glassnode.com/v1/metrics/market/mvrv_z_score"
        f"?a=BTC&api_key={key}&i=24h"
    )
    data = _get(url)
    latest = data[-1] if data else {}
    val = latest.get("v")
    return {
        "signal": val,
        "source": "glassnode",
        "fired_rotation_gate": bool(val and val > 3),
        # NOTE: confirm exact response schema against current Glassnode docs
        # before relying on this in production — written against the
        # documented pattern, not tested live from this environment.
    }


def fetch_cryptoquant_netflows():
    """ETH/alt exchange netflows — needs CRYPTOQUANT_API_KEY."""
    key = os.environ.get("CRYPTOQUANT_API_KEY")
    if not key:
        return {"status": "no_key", "signal": None,
                "note": "set CRYPTOQUANT_API_KEY in GitHub Secrets — check cryptoquant.com for current free-tier terms"}
    return {"status": "not_implemented", "signal": None,
            "note": "endpoint shape needs confirming against current CryptoQuant API docs at signup time"}


def fetch_coinglass_funding():
    """Alt perpetual funding rates — needs COINGLASS_API_KEY."""
    key = os.environ.get("COINGLASS_API_KEY")
    if not key:
        return {"status": "no_key", "signal": None,
                "note": "set COINGLASS_API_KEY in GitHub Secrets — free tier at coinglass.com"}
    return {"status": "not_implemented", "signal": None,
            "note": "endpoint shape needs confirming against current Coinglass API docs at signup time"}


def fetch_lunarcrush_social():
    """Social volume — needs LUNARCRUSH_API_KEY (paid tier required for real use)."""
    key = os.environ.get("LUNARCRUSH_API_KEY")
    if not key:
        return {"status": "no_key", "signal": None,
                "note": "set LUNARCRUSH_API_KEY in GitHub Secrets — free tier too rate-limited for weekly automation, budget decision"}
    return {"status": "not_implemented", "signal": None,
            "note": "endpoint shape needs confirming against current LunarCrush API docs at signup time"}


def fetch_alt_etf_flows():
    """ETH/SOL/XRP/HYPE ETF flows — no clean public API (Farside/SoSoValue).
    This one is realistically a web_search job inside the weekly Claude task,
    not a scraper GitHub Actions can run reliably long-term. Left as a stub
    that documents the honest state rather than a broken scraper."""
    return {"status": "no_api", "signal": None,
            "note": "Farside/SoSoValue have no stable public API — pull this via the weekly brief's web_search step, not this pipeline"}


# ── ORCHESTRATION ────────────────────────────────────────────────────────────

def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    signals = {
        "date": today,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "fear_greed": safe_fetch("fear_greed", fetch_fear_greed),
        "dominance_and_prices": safe_fetch("dominance_and_prices", fetch_dominance_and_prices),
        "mvrv_z_score": safe_fetch("mvrv_z_score", fetch_glassnode_mvrv),
        "alt_exchange_netflows": safe_fetch("alt_netflows", fetch_cryptoquant_netflows),
        "alt_funding_rates": safe_fetch("alt_funding", fetch_coinglass_funding),
        "social_volume": safe_fetch("social_volume", fetch_lunarcrush_social),
        "alt_etf_flows": safe_fetch("alt_etf_flows", fetch_alt_etf_flows),
    }

    # rotation gate tally — only counts sources that actually returned a value
    votes_possible = 0
    votes_fired = 0
    for key, val in signals.items():
        if isinstance(val, dict) and "fired_rotation_gate" in val:
            votes_possible += 1
            if val["fired_rotation_gate"]:
                votes_fired += 1
    signals["gate_tally"] = {
        "fired": votes_fired,
        "checkable_today": votes_possible,
        "note": "only counts signals this run could actually verify — missing keys reduce the denominator, not the numerator",
    }

    os.makedirs("data", exist_ok=True)

    with open(f"data/signals_{today}.json", "w") as f:
        json.dump(signals, f, indent=2)

    with open("data/signals_history.jsonl", "a") as f:
        f.write(json.dumps(signals) + "\n")

    # data health check — surfaces broken sources instead of hiding them
    broken = [k for k, v in signals.items()
              if isinstance(v, dict) and v.get("status") in ("error", "http_error")]
    if broken:
        print(f"WARNING: {len(broken)} source(s) failed this run: {broken}", file=sys.stderr)

    no_key = [k for k, v in signals.items()
              if isinstance(v, dict) and v.get("status") == "no_key"]
    if no_key:
        print(f"INFO: {len(no_key)} source(s) skipped, no key set: {no_key}", file=sys.stderr)

    print(json.dumps(signals, indent=2))


if __name__ == "__main__":
    main()
