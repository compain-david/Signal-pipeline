#!/usr/bin/env python3
"""
Band study: does POSITION WITHIN A RANGE inform allocation?

Why this exists, and why it is a better test than the last one
--------------------------------------------------------------
forward_study.py asked a timing question: "the signal crossed a threshold -
did the rotation pay over the next 30/60/90 days?" That is the right question
for a trigger and the wrong one for a dial. It also throws away the gradient:
"F&G > 60" puts 61 and 95 in the same bucket.

This asks the positioning question instead: given where a measure sits inside
its own historical range, what is the distribution of what follows? A dial,
not a trigger.

The test that matters here is MONOTONICITY, not any single band beating the
baseline. One bucket out of five clearing a bar is what noise looks like when
you run five buckets. A consistent gradient across all five - low band worst,
high band best, in order - is much harder to produce by chance, and it is the
only pattern that would justify positioning by range.

So each signal gets a monotonicity score: how many of the four adjacent band
pairs move in the same direction. 4/4 or 0/4 is a clean gradient. 2/4 is noise.

Bands are QUANTILES of each series' own history, never absolute levels. That
is deliberate: the dominance series here is derived from a basket whose size
VARIES day to day, so its level is biased high against any all-coin figure and
the bias is not even constant. The range and the median level are recomputed
and printed by main() rather than quoted here - this docstring carried "25
assets" for a long time, analysis/dominance.json has never held 25, and a
number nobody recomputes is a number nobody owns.
Quantiles are invariant to that bias; absolute thresholds are not, and
using "< 54%" on this series would be meaningless.

Regime split
------------
Spot BTC ETFs launched 2024-01-11 and changed who the marginal buyer is. Every
signal is therefore also reported for the post-ETF era alone. The sample gets
much thinner - roughly 600 days - so those rows are read as suggestion, never
as evidence.

Run: python scripts/band_study.py
"""

import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.join(HERE, "..", "analysis")
sys.path.insert(0, HERE)

import forward_study as fs

HORIZONS = (30, 60, 90)
N_BANDS = 5
ETF_ERA_START = "2024-01-11"   # spot BTC ETF launch


def load_dominance():
    with open(os.path.join(ANALYSIS, "dominance.json"), encoding="utf-8") as f:
        return json.load(f)


def quantile_bands(series, n=N_BANDS):
    """Split dates into n bands by the value's rank in its own history."""
    items = sorted(series.items(), key=lambda kv: kv[1])
    size = len(items) / n
    bands = []
    for i in range(n):
        lo, hi = int(i * size), int((i + 1) * size)
        chunk = items[lo:hi]
        if chunk:
            bands.append((chunk[0][1], chunk[-1][1], [d for d, _ in chunk]))
    return bands


def rate_of_change(series, window):
    """Change over `window` days - a dial on momentum rather than level."""
    dates = sorted(series)
    out = {}
    for i, d in enumerate(dates):
        if i >= window:
            prev = series[dates[i - window]]
            if prev:
                out[d] = (series[d] / prev - 1) * 100
    return out


def band_table(label, series, fwd, universe, era=None):
    """Median forward return per band, plus a monotonicity score."""
    if era:
        series = {d: v for d, v in series.items() if d >= era}
    series = {d: v for d, v in series.items() if d in universe}
    if len(series) < N_BANDS * 40:
        return None

    bands = quantile_bands(series)
    rows = []
    for lo, hi, dates in bands:
        vals = [fwd[d] for d in dates if d in fwd]
        if len(vals) < 20:
            rows.append(None)
            continue
        eps = fs.episodes(sorted(dates))
        rows.append({"lo": lo, "hi": hi, "n": len(vals),
                     "median": fs.median(vals),
                     "hit": sum(1 for v in vals if v > 0) / len(vals) * 100,
                     "episodes": len(eps)})

    meds = [r["median"] for r in rows if r]
    ups = sum(1 for a, b in zip(meds, meds[1:]) if b > a)
    downs = sum(1 for a, b in zip(meds, meds[1:]) if b < a)
    pairs = max(len(meds) - 1, 1)
    return {"label": label, "rows": rows, "up": ups, "down": downs,
            "pairs": pairs, "mono": max(ups, downs) / pairs}


def render(title, table):
    if not table:
        print("\n  %s : echantillon insuffisant" % title)
        return
    print("\n  %s" % title)
    print("    %-22s %6s %5s %10s %8s" % ("bande (valeur)", "n", "ep.", "median", "hit"))
    for i, r in enumerate(table["rows"], 1):
        if not r:
            print("    %-22s      -" % ("bande %d" % i))
            continue
        print("    %-22s %6d %5d %9.1f%% %7.0f%%"
              % ("%d. %.2f -> %.2f" % (i, r["lo"], r["hi"]),
                 r["n"], r["episodes"], r["median"], r["hit"]))
    direction = "croissante" if table["up"] > table["down"] else "decroissante"
    verdict = ("GRADIENT %s" % direction if table["mono"] >= 0.75
               else "pas de gradient")
    print("    monotonie : %d/%d paires dans le meme sens  ->  %s"
          % (max(table["up"], table["down"]), table["pairs"], verdict))


def main():
    prices = fs.load_ethbtc()
    series = fs.load_series()
    fng = fs.load_fear_greed()
    dom_raw = load_dominance()
    universe = set(prices)

    dom = {d: v["btc_dom"] for d, v in dom_raw.items()}
    eth_dom = {d: v["eth_dom"] for d, v in dom_raw.items()}

    print("Etude par fourchettes - positionnement, pas declenchement")
    sizes = [v["n_assets"] for v in dom_raw.values() if v.get("n_assets")]
    print("  dominance derivee d un panier de %d a %d actifs selon le jour"
          % (min(sizes), max(sizes)))
    print("  (%d jours mesures, mediane %.0f) : mediane btc_dom %.1f%% sur ce"
          % (len(sizes), fs.median(sizes), fs.median(list(dom.values()))))
    print("  panier restreint. Le NIVEAU est donc biaise haut contre une")
    print("  dominance tous-actifs, la DYNAMIQUE non.")
    print("  Toutes les bandes sont des quantiles, jamais des seuils absolus.")

    candidates = [
        ("dominance BTC (niveau)", dom),
        ("dominance BTC (var. 30j)", rate_of_change(dom, 30)),
        ("dominance BTC (var. 90j)", rate_of_change(dom, 90)),
        ("dominance ETH (niveau)", eth_dom),
        ("Fear & Greed", fng),
    ]
    for name in ("mvrv_z_score", "stablecoin_supply_ratio", "nvt"):
        if name in series:
            candidates.append((name, series[name]))

    for h in (90,):
        fwd = fs.forward_map(prices, h)
        print("\n\n=== HORIZON %d JOURS - rendement forward ETH/BTC ===" % h)
        print("\n--- historique complet ---")
        for label, s in candidates:
            render(label, band_table(label, s, fwd, universe))

        print("\n\n--- ere post-ETF seulement (depuis %s) ---" % ETF_ERA_START)
        print("  echantillon bien plus mince : suggestion, jamais preuve.")
        for label, s in candidates:
            render(label, band_table(label, s, fwd, universe, era=ETF_ERA_START))

    print("\n\nLecture : une bande isolee qui bat la baseline sur cinq bandes")
    print("est ce a quoi ressemble le bruit. Seul un gradient monotone")
    print("justifierait de positionner selon la fourchette.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
