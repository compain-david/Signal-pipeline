#!/usr/bin/env python3
"""
Forward-return study: do these signals precede ETH outperforming BTC?

This is the analysis the framework never had. Everything before it measured
mechanics - correlation, churn, firing frequency. None of it asked the only
question that matters for a rotation gate: when the signal fires, does the
rotation actually pay?

Method
------
For every historical day, take the signal's reading, then measure the forward
change in ETH/BTC over 30, 60 and 90 days. Compare each conditional bucket
against the UNCONDITIONAL baseline over the same period. A signal is only
useful if its bucket beats the baseline - a bucket showing +8% in a period
where every day averaged +8% has told you nothing.

Reported for each bucket: sample size, median forward return, and hit rate
(share of windows positive). Median rather than mean, because crypto forward
returns are heavily skewed and a single 2021-style window drags a mean
anywhere you like.

Honest limits
-------------
- ETH/BTC is a proxy for "alt rotation". It is the cleanest long series
  available free, but rotation into SOL/XRP/HYPE is not the same trade.
- Overlapping windows are NOT independent observations. 2799 days give far
  fewer than 2799 independent 90-day windows, so treat differences of a few
  points as noise, not signal.
- This is in-sample across the whole history. It describes what happened; it
  is not an out-of-sample test of a rule chosen after seeing it.

Run: python scripts/forward_study.py
"""

import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.join(HERE, "..", "analysis")
UA = {"User-Agent": "signal-pipeline/4.0 (personal use)"}
HORIZONS = (30, 60, 90)


def _get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def load_ethbtc():
    with open(os.path.join(ANALYSIS, "ethbtc.json"), encoding="utf-8") as f:
        raw = json.load(f)
    return {d: v["ethbtc"] for d, v in raw.items()}


def load_fear_greed():
    import datetime
    cache = os.path.join(ANALYSIS, ".cache", "fng.json")
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = _get("https://api.alternative.me/fng/?limit=0&format=json")
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(data, f)
    out = {}
    for e in data.get("data", []):
        try:
            ts = int(e["timestamp"])
            d = datetime.datetime.fromtimestamp(
                ts, datetime.timezone.utc).strftime("%Y-%m-%d")
            out[d] = float(e["value"])
        except (KeyError, TypeError, ValueError):
            pass
    return out


def median(xs):
    if not xs:
        return None
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def forward_returns(prices, dates, horizon):
    """Percent change in ETH/BTC from each date to `horizon` days later."""
    idx = {d: i for i, d in enumerate(dates)}
    out = {}
    for i, d in enumerate(dates):
        j = i + horizon
        if j < len(dates):
            a, b = prices[d], prices[dates[j]]
            if a:
                out[d] = (b / a - 1) * 100
    return out


def report_buckets(name, buckets, fwd, baseline, horizon):
    print("\n  %s - horizon %d jours" % (name, horizon))
    print("    %-22s %6s %10s %9s %10s"
          % ("bucket", "n", "median %", "hit %", "vs base"))
    base_med = median(baseline)
    for label, dates in buckets:
        vals = [fwd[d] for d in dates if d in fwd]
        if len(vals) < 30:
            print("    %-22s %6d   echantillon insuffisant" % (label, len(vals)))
            continue
        med = median(vals)
        hit = sum(1 for v in vals if v > 0) / len(vals) * 100
        edge = med - base_med
        flag = "  <-- " if abs(edge) >= 3 else ""
        print("    %-22s %6d %9.1f%% %8.0f%% %9.1f%s"
              % (label, len(vals), med, hit, edge, flag))
    print("    %-22s %6d %9.1f%% %8.0f%% %9s"
          % ("BASELINE (tous jours)", len(baseline), base_med,
             sum(1 for v in baseline if v > 0) / len(baseline) * 100, "-"))


def main():
    prices = load_ethbtc()
    fng = load_fear_greed()
    dates = sorted(set(prices) & set(fng))
    print("Etude forward ETH/BTC")
    print("  jours communs prix + F&G : %d  (%s -> %s)"
          % (len(dates), dates[0], dates[-1]))

    price_dates = sorted(prices)

    print("\n=== QUESTION : le Fear & Greed predit-il la surperformance ETH ? ===")
    for h in HORIZONS:
        fwd = forward_returns(prices, price_dates, h)
        baseline = [fwd[d] for d in dates if d in fwd]
        buckets = [
            ("F&G < 20 (peur extreme)", [d for d in dates if fng[d] < 20]),
            ("F&G 20-40", [d for d in dates if 20 <= fng[d] < 40]),
            ("F&G 40-60", [d for d in dates if 40 <= fng[d] < 60]),
            ("F&G 60-80 (seuil actuel)", [d for d in dates if 60 <= fng[d] < 80]),
            ("F&G >= 80 (greed extreme)", [d for d in dates if fng[d] >= 80]),
        ]
        report_buckets("Fear & Greed", buckets, fwd, baseline, h)

    print("\n\n=== Le seuil actuel (>60) vs le seuil propose (>80) ===")
    for h in HORIZONS:
        fwd = forward_returns(prices, price_dates, h)
        baseline = [fwd[d] for d in dates if d in fwd]
        buckets = [
            ("F&G > 60 (regle actuelle)", [d for d in dates if fng[d] > 60]),
            ("F&G > 80 (propose)", [d for d in dates if fng[d] > 80]),
        ]
        report_buckets("Seuils", buckets, fwd, baseline, h)

    print("\n\nRappel : fenetres chevauchantes, donc bien moins d'observations")
    print("independantes que de lignes. Un ecart de quelques points est du bruit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
