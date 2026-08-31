#!/usr/bin/env python3
"""
Forward-return study: does each signal precede ETH outperforming BTC?

This is the analysis the framework never had. Everything before it measured
mechanics - correlation, churn, firing frequency. None of it asked the only
question that matters for a rotation gate: when a signal fires, does the
rotation actually pay?

Two tests per signal, and BOTH must pass before a result means anything
--------------------------------------------------------------------
1. EDGE. Median forward ETH/BTC change when the signal fires, against the
   unconditional baseline over the same period. Median, not mean: crypto
   forward returns are heavily skewed and one 2021-style window drags a mean
   anywhere you like. Hit rate reported alongside, because a good median with
   a coin-flip hit rate is one lucky window.

2. INDEPENDENCE. How many DISTINCT episodes the firing days come from. This
   is the test that kills most apparent edges. A bucket of 149 days is not 149
   observations if 90 of them sit inside two clusters - it is closer to two.
   A signal whose edge rests on one remembered episode has not been validated;
   it has been described.

Test 2 exists because test 1 alone produced a spectacular and misleading
result: F&G > 80 shows +12.9 points of edge at 90 days, which looks like a
strong rule until you see that 60% of its firing days come from Nov 2020 to
Feb 2021 - the 2021 altseason, counted twice.

Honest limits
-------------
- ETH/BTC proxies "alt rotation". It is the cleanest long free series, but
  rotation into SOL/XRP/HYPE is not the same trade.
- Only Fear & Greed reaches back to 2019. Every other series starts 2022-08,
  so no other signal can be tested against the 2021 altseason at all.
- Entirely in-sample. This describes what happened; it does not test a rule
  chosen after seeing it.

Run: python scripts/forward_study.py
"""

import datetime
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.join(HERE, "..", "analysis")
UA = {"User-Agent": "signal-pipeline/4.0 (personal use)"}
HORIZONS = (30, 60, 90)
EPISODE_GAP = 7          # days of quiet that separate two episodes
DOMINANCE_ALARM = 50.0   # % of a bucket sitting in its 3 largest episodes
MIN_EPISODES = 4
MIN_EDGE_PTS = 3.0


def _get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def load_ethbtc():
    with open(os.path.join(ANALYSIS, "ethbtc.json"), encoding="utf-8") as f:
        return {d: v["ethbtc"] for d, v in json.load(f).items()}


def load_series():
    with open(os.path.join(ANALYSIS, "series.json"), encoding="utf-8") as f:
        d = json.load(f)
    dates = d["dates"]
    return {name: dict(zip(dates, vals)) for name, vals in d["series"].items()}


def load_fear_greed():
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


def forward_map(prices, horizon):
    pd = sorted(prices)
    idx = {d: i for i, d in enumerate(pd)}
    out = {}
    for d, i in idx.items():
        j = i + horizon
        if j < len(pd) and prices[d]:
            out[d] = (prices[pd[j]] / prices[d] - 1) * 100
    return out


def episodes(dates, gap_days=EPISODE_GAP):
    """Group consecutive firing days into distinct episodes."""
    if not dates:
        return []
    dates = sorted(dates)
    out, cur = [], [dates[0]]
    for a, b in zip(dates, dates[1:]):
        da = datetime.date.fromisoformat(a)
        db = datetime.date.fromisoformat(b)
        if (db - da).days <= gap_days:
            cur.append(b)
        else:
            out.append(cur)
            cur = [b]
    out.append(cur)
    return out


# -- signal definitions ------------------------------------------------------

def _above_own_avg(series, window):
    dates = sorted(series)
    out = []
    for i, d in enumerate(dates):
        if i < window:
            continue
        avg = sum(series[dates[j]] for j in range(i - window, i)) / window
        if series[d] > avg:
            out.append(d)
    return out


def _falling_over(series, window):
    dates = sorted(series)
    out = []
    for i, d in enumerate(dates):
        if i >= window and series[d] < series[dates[i - window]]:
            out.append(d)
    return out


def build_signals(series, fng):
    """label -> (firing dates, the rule in words)."""
    sig = {}
    if "mvrv_z_score" in series:
        s = series["mvrv_z_score"]
        sig["mvrv_z > 3"] = ([d for d in s if s[d] > 3.0], "regle Tier A actuelle")
        sig["mvrv_z > 2"] = ([d for d in s if s[d] > 2.0], "variante moins stricte")
    if "nvt" in series:
        sig["nvt > moy 90j"] = (_above_own_avg(series["nvt"], 90),
                                "regle Tier A actuelle")
    if "stablecoin_supply_ratio" in series:
        sig["ssr baisse 30j"] = (_falling_over(series["stablecoin_supply_ratio"], 30),
                                 "regle Tier A actuelle")
    if "puell_multiple" in series:
        p = series["puell_multiple"]
        sig["puell < 0.5"] = ([d for d in p if p[d] < 0.5], "bande d achat")
        sig["puell > 1.0"] = ([d for d in p if p[d] > 1.0], "sortie de bande")
    if fng:
        sig["F&G > 60"] = ([d for d in fng if fng[d] > 60], "regle Tier A actuelle")
        sig["F&G > 80"] = ([d for d in fng if fng[d] > 80], "seuil propose")
        sig["F&G < 20"] = ([d for d in fng if fng[d] < 20], "queue opposee, controle")
    return sig


def assess(label, fires, rule, fwds, universe):
    fires = sorted(d for d in fires if d in universe)
    eps = episodes(fires)
    biggest = sorted(eps, key=len, reverse=True)[:3]
    share = (sum(len(e) for e in biggest) / len(fires) * 100) if fires else 0.0

    row = {"label": label, "rule": rule, "n": len(fires),
           "episodes": len(eps), "top3_share": share,
           "biggest": biggest, "edges": {}}

    # The baseline MUST be restricted to the signal's own date range.
    #
    # Without this the study compares 2022-2026 signal days against a
    # 2019-2026 baseline, and any signal whose series starts in 2022 inherits
    # the difference between the two periods as fake "edge". ETH/BTC behaved
    # very differently before and after 2022, so that mismatch alone was
    # enough to make well-built rules look inverted. Every edge below is
    # therefore measured against the same window the signal could see.
    lo, hi = (min(fires), max(fires)) if fires else (None, None)
    row["window"] = (lo, hi)
    in_window = [d for d in universe if lo and lo <= d <= hi]

    for h, fwd in fwds.items():
        vals = [fwd[d] for d in fires if d in fwd]
        base = [fwd[d] for d in in_window if d in fwd]
        if len(vals) < 30 or len(base) < 30:
            row["edges"][h] = None
            continue
        med = median(vals)
        row["edges"][h] = {"median": med,
                           "hit": sum(1 for v in vals if v > 0) / len(vals) * 100,
                           "edge": med - median(base)}
    return row


def verdict(row):
    """A signal earns a vote only with edge AND spread across episodes."""
    e90 = row["edges"].get(90)
    if e90 is None:
        return "ECHANTILLON INSUFFISANT"
    if row["episodes"] < MIN_EPISODES:
        return "REJETE - %d episodes seulement" % row["episodes"]
    if row["top3_share"] > DOMINANCE_ALARM:
        return "REJETE - %.0f%% du bucket dans 3 episodes" % row["top3_share"]
    if e90["edge"] < MIN_EDGE_PTS:
        return "PAS D EDGE - %+.1f pts a 90j" % e90["edge"]
    return "RETENU - %+.1f pts sur %d episodes" % (e90["edge"], row["episodes"])


def main():
    prices = load_ethbtc()
    series = load_series()
    fng = load_fear_greed()
    fwds = {h: forward_map(prices, h) for h in HORIZONS}
    universe = set(prices)

    print("Etude forward ETH/BTC - tous les signaux disponibles")
    print("  prix ETH/BTC   : %d jours (%s -> %s)"
          % (len(prices), min(prices), max(prices)))
    if series:
        print("  series signaux : depuis %s"
              % min(min(s) for s in series.values()))
        print("                   aucune ne couvre l altseason 2021")

    rows = [assess(k, v[0], v[1], fwds, universe)
            for k, v in build_signals(series, fng).items()]

    print("\n\n=== EDGE : mediane forward ETH/BTC vs baseline (points) ===\n")
    print("  %-18s %6s %5s %9s %9s %9s %7s"
          % ("signal", "n", "ep.", "30j", "60j", "90j", "hit90"))
    print("  " + "-" * 68)
    for r in sorted(rows, key=lambda x: -((x["edges"].get(90) or {}).get("edge", -99))):
        cells = []
        for h in HORIZONS:
            e = r["edges"].get(h)
            cells.append("%+8.1f" % e["edge"] if e else "       -")
        e90 = r["edges"].get(90)
        hit = "%6.0f%%" % e90["hit"] if e90 else "      -"
        print("  %-18s %6d %5d %s %s %s %s"
              % (r["label"], r["n"], r["episodes"], *cells, hit))

    print("\n\n=== INDEPENDANCE : regularite ou souvenir ? ===\n")
    for r in sorted(rows, key=lambda x: -x["top3_share"]):
        if not r["n"]:
            continue
        flag = "  <-- DOMINE" if r["top3_share"] > DOMINANCE_ALARM else ""
        print("  %-18s %3d ep., 3 plus gros = %5.1f%%%s"
              % (r["label"], r["episodes"], r["top3_share"], flag))
        if r["top3_share"] > DOMINANCE_ALARM and r["biggest"]:
            for e in r["biggest"][:2]:
                print("        %s -> %s (%d j)" % (e[0], e[-1], len(e)))

    print("\n\n=== VERDICT PAR SIGNAL ===")
    print("  Retenu = edge >= %.0f pts a 90j, sur >= %d episodes distincts,"
          % (MIN_EDGE_PTS, MIN_EPISODES))
    print("  sans qu un tiers du bucket domine.\n")
    for r in sorted(rows, key=lambda x: x["label"]):
        print("  %-18s %-24s %s" % (r["label"], r["rule"], verdict(r)))

    print("\n\nRappel : fenetres chevauchantes, etude entierement in-sample,")
    print("et ETH/BTC ne represente pas la rotation vers SOL/XRP/HYPE.")
    print("Un edge ici est une condition necessaire, jamais suffisante.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
