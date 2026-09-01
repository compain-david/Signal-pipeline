#!/usr/bin/env python3
"""
Out-of-sample test of the band hypothesis. It FAILED, and that is the result.

What was being tested
---------------------
band_study.py found a 4/4 monotone gradient: higher BTC dominance preceded
better ETH/BTC returns, strongest in the post-ETF era, and surviving a
mean-reversion control. That looked like the one real edge in the whole
system.

But the direction of that rule was chosen AFTER seeing the gradient, across
five measures and two period splits. That is the weakest form of evidence
there is, and the only thing that distinguishes it from a well-told memory is
whether it holds on data the rule was not chosen on.

Two designs, both fail
----------------------
1. FIXED BANDS fitted on 2019-2023, applied to 2024-2026.
   Three of five bands are EMPTY in the test period: BTC dominance drifted
   structurally upward and never returned below the band-4 boundary. The
   series is non-stationary, so fitted levels do not transfer at all. Of the
   two bands that populate, the top one scored +19.2% (hit 84%) in training
   and -7.3% (hit 31%) in test.

2. ROLLING PERCENTILE (365d and 730d), stationary by construction, which
   repairs the non-stationarity. The shape still disagrees between periods:

     window  training 2019-2023        test 2024-2026
     365d    2/4, middle bands best    3/4, top band best
     730d    2/4, p40-60 at +21.0%     3/3, top band best

   Training and test do not agree on the SHAPE of the relationship. A
   gradient that changes shape with the window is regime-dependent at best.

Why this cannot be repaired by trying harder
--------------------------------------------
The post-ETF era IS the test set. Fitting a rule on it and then citing its
post-ETF performance would be circular, and there is no third period to hold
out - spot ETFs launched 2024-01-11 and the data ends 2026-08.

So the honest ceiling on this hypothesis' evidence score is about 5.0, and
the earlier 4.5 assigned to the band-dial option was, if anything, generous.

What survives
-------------
One consistent fact across both rolling-percentile test runs: the top
dominance-percentile band is the LEAST BAD (-5.1% and -6.0%, against -12.9%
and -16.4% at the bottom). That is worth logging and watching. It is not
worth allocating on.

Run: python scripts/oos_test.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import band_study as bs
import forward_study as fs

TRAIN_END = "2023-12-31"
TEST_START = "2024-01-01"     # spot ETF era
HORIZON = 90
N_BANDS = 5


def rolling_percentile(series, dates, window):
    """Rank of today's value inside its own trailing window.

    Stationary by construction - the repair for a series whose level drifts.
    """
    out = {}
    for i, d in enumerate(dates):
        if i < window:
            continue
        hist = [series[dates[j]] for j in range(i - window, i)]
        out[d] = sum(1 for h in hist if h < series[d]) / len(hist) * 100
    return out


def score(dates, fwd, label):
    vals = [fwd[d] for d in dates if d in fwd]
    if len(vals) < 20:
        return None
    return {"n": len(vals), "median": fs.median(vals),
            "hit": sum(1 for v in vals if v > 0) / len(vals) * 100,
            "episodes": len(fs.episodes(sorted(dates))), "label": label}


def monotonicity(meds):
    m = [x for x in meds if x is not None]
    if len(m) < 3:
        return None
    up = sum(1 for a, b in zip(m, m[1:]) if b > a)
    return max(up, len(m) - 1 - up), len(m) - 1


def report(rows):
    meds = []
    for r in rows:
        if not r:
            print("    %-10s echantillon insuffisant" % "-")
            meds.append(None)
            continue
        meds.append(r["median"])
        print("    %-10s n=%4d ep=%3d  median %+7.1f%%  hit %3.0f%%"
              % (r["label"], r["n"], r["episodes"], r["median"], r["hit"]))
    mono = monotonicity(meds)
    if mono:
        print("    monotonie : %d/%d" % mono)


def main():
    px = fs.load_ethbtc()
    dom = {d: v["btc_dom"] for d, v in bs.load_dominance().items()}
    fwd = fs.forward_map(px, HORIZON)
    dates = sorted(d for d in dom if d in px)

    print("Test hors echantillon de l hypothese des fourchettes")
    print("  horizon %d jours, cible ETH/BTC" % HORIZON)
    print("  apprentissage <= %s   test >= %s" % (TRAIN_END, TEST_START))

    # --- 1. fixed bands, fitted on training only ---------------------------
    tr = {d: dom[d] for d in dates if d <= TRAIN_END}
    te = {d: dom[d] for d in dates if d >= TEST_START}
    vals = sorted(tr.values())
    cuts = [vals[int(i * len(vals) / N_BANDS)] for i in range(1, N_BANDS)]
    print("\n\n=== 1. BANDES FIXES apprises sur 2019-2023 ===")
    print("  bornes : %s" % ["%.1f" % c for c in cuts])

    def band_of(v):
        for i, c in enumerate(cuts):
            if v < c:
                return i
        return N_BANDS - 1

    for name, src in (("apprentissage", tr), ("TEST", te)):
        print("\n  %s" % name)
        buckets = {}
        for d, v in src.items():
            buckets.setdefault(band_of(v), []).append(d)
        report([score(buckets.get(i, []), fwd, "bande %d" % (i + 1))
                for i in range(N_BANDS)])
    print("\n  -> trois bandes vides en test: la dominance a derive vers le")
    print("     haut et n est jamais redescendue. Les niveaux ne transferent pas.")

    # --- 2. rolling percentile, stationary by construction -----------------
    for window in (365, 730):
        rp = rolling_percentile(dom, dates, window)
        print("\n\n=== 2. PERCENTILE GLISSANT %dj ===" % window)
        for name, sel in (("apprentissage",
                           [d for d in rp if d <= TRAIN_END]),
                          ("TEST", [d for d in rp if d >= TEST_START])):
            if len(sel) < 200:
                print("\n  %s : insuffisant" % name)
                continue
            print("\n  %s" % name)
            rows = []
            for i in range(N_BANDS):
                lo, hi = i * 20, (i + 1) * 20
                b = [d for d in sel
                     if (lo <= rp[d] < hi) or (i == N_BANDS - 1 and rp[d] >= 80)]
                rows.append(score(b, fwd, "p%02d-%02d" % (lo, hi)))
            report(rows)

    print("\n\n=== VERDICT ===")
    print("  Apprentissage et test ne s accordent pas sur la FORME de la")
    print("  relation. Un gradient qui change de forme selon la fenetre est")
    print("  au mieux dependant du regime.")
    print("\n  L ere post-ETF EST le jeu de test. Y ajuster une regle puis citer")
    print("  sa performance post-ETF serait circulaire, et il n existe pas de")
    print("  troisieme periode a garder de cote.")
    print("\n  Plafond honnete sur la preuve de cette hypothese : ~5,0.")
    print("\n  Ce qui survit : la bande haute est la MOINS MAUVAISE dans les deux")
    print("  runs de test. A journaliser et surveiller. Pas a allouer dessus.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
