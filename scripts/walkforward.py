#!/usr/bin/env python3
"""
Walk-forward validation: does what a signal taught us keep being true?

The question this answers
-------------------------
A single train/test split answers "did it hold once". That is one coin flip.
Walk-forward asks the question that actually matters for a system meant to run
for years: fit on everything known up to time T, check the next slice, roll
forward, repeat. If the relationship learned in each window keeps holding in
the window after it, the signal is stable. If agreement lands near 50%, the
signal is a coin flip dressed as an indicator, however good any single split
looked.

Method
------
For each fold:
  1. TRAIN on [t0, t1]. Split the signal into quintiles of its own rolling
     percentile and measure the median forward ETH/BTC return per quintile.
     Record the DIRECTION: does the median rise or fall across quintiles?
  2. TEST on [t1, t2] with the SAME quintile definition. Record its direction.
  3. The fold agrees if both directions match.

Direction rather than magnitude on purpose: magnitudes are noisy at this
sample size, and a system only needs the sign to be right to allocate.

The null, and why it is printed
-------------------------------
Two directions agree by chance half the time. So an agreement rate near 50%
is not weak evidence, it is NO evidence. A shuffled control is computed
alongside every real result: the signal's own values are randomly reassigned
to dates, destroying any real relationship while preserving the distribution
and the fold structure. A real signal must beat its own shuffle, not 50% in
the abstract.

Window sizes are swept because the trailing window is a free parameter, and a
free parameter chosen after seeing results is how in-sample findings are
manufactured. If a signal only works at one window width, that is a red flag
rather than a tuning success.

Honest limits
-------------
- Overlapping forward windows: folds are not fully independent.
- ETH/BTC proxies alt rotation and is not SOL/XRP/HYPE.
- The whole sample sits inside one ETH/BTC downtrend.

Run: python scripts/walkforward.py
"""

import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import band_study as bs
import forward_study as fs

HORIZON = 90
N_BANDS = 5
SEED = 20260901
SHUFFLES = 40


def rolling_percentile(series, dates, window):
    out = {}
    for i, d in enumerate(dates):
        if i < window:
            continue
        hist = [series[dates[j]] for j in range(i - window, i)]
        out[d] = sum(1 for h in hist if h < series[d]) / len(hist) * 100
    return out


def direction(dates, pct, fwd):
    """+1 if median forward return rises across quintiles, -1 if it falls."""
    meds = []
    for i in range(N_BANDS):
        lo, hi = i * 20, (i + 1) * 20
        b = [d for d in dates
             if d in pct and ((lo <= pct[d] < hi) or (i == N_BANDS - 1 and pct[d] >= 80))]
        v = [fwd[d] for d in b if d in fwd]
        meds.append(fs.median(v) if len(v) >= 10 else None)
    m = [x for x in meds if x is not None]
    if len(m) < 3:
        return None
    ups = sum(1 for a, b in zip(m, m[1:]) if b > a)
    downs = len(m) - 1 - ups
    if ups == downs:
        return None
    return 1 if ups > downs else -1


def walk(series, fwd, window, train_days, test_days):
    dates = sorted(d for d in series if d in fwd)
    pct = rolling_percentile(series, dates, window)
    usable = [d for d in dates if d in pct]
    folds = agree = 0
    start = 0
    while start + train_days + test_days <= len(usable):
        tr = usable[start:start + train_days]
        te = usable[start + train_days:start + train_days + test_days]
        dtr, dte = direction(tr, pct, fwd), direction(te, pct, fwd)
        if dtr is not None and dte is not None:
            folds += 1
            agree += int(dtr == dte)
        start += test_days
    return agree, folds


def shuffled_null(series, fwd, window, train_days, test_days, rng):
    """Same fold structure, values randomly reassigned to dates."""
    dates = sorted(series)
    vals = [series[d] for d in dates]
    rng.shuffle(vals)
    return walk(dict(zip(dates, vals)), fwd, window, train_days, test_days)


def main():
    px = fs.load_ethbtc()
    dom = {d: v["btc_dom"] for d, v in bs.load_dominance().items()}
    eth_dom = {d: v["eth_dom"] for d, v in bs.load_dominance().items()}
    series = fs.load_series()
    fng = fs.load_fear_greed()
    fwd = fs.forward_map(px, HORIZON)

    candidates = [
        ("dominance BTC", dom),
        ("dominance ETH", eth_dom),
        ("niveau ETH/BTC", px),
        ("Fear & Greed", fng),
    ]
    for name in ("mvrv_z_score", "stablecoin_supply_ratio", "nvt"):
        if name in series:
            candidates.append((name, series[name]))

    print("Validation walk-forward - horizon %d jours, cible ETH/BTC" % HORIZON)
    print("  fit sur une fenetre, verification sur la suivante, on avance.")
    print("  Le controle melange est la seule reference qui compte : deux")
    print("  directions coincident une fois sur deux par hasard.")

    for window, train_days, test_days in ((365, 365, 180), (730, 540, 180)):
        print("\n\n=== percentile glissant %dj | train %dj | test %dj ==="
              % (window, train_days, test_days))
        print("\n  %-24s %10s %12s %10s"
              % ("signal", "accord", "melange", "ecart"))
        print("  " + "-" * 60)
        for label, s in candidates:
            a, f = walk(s, fwd, window, train_days, test_days)
            if f < 3:
                print("  %-24s   %d plis seulement" % (label, f))
                continue
            rng = random.Random(SEED)
            nulls = []
            for _ in range(SHUFFLES):
                na, nf = shuffled_null(s, fwd, window, train_days, test_days, rng)
                if nf:
                    nulls.append(na / nf * 100)
            null = sum(nulls) / len(nulls) if nulls else 50.0
            real = a / f * 100
            gap = real - null
            flag = "  <--" if gap >= 15 else ""
            print("  %-24s %6.0f%% (%d/%d) %8.0f%% %9.0f%s"
                  % (label, real, a, f, null, gap, flag))

    print("\n\nLecture : seul un ecart nettement positif contre le melange")
    print("indique un signal stable. Un accord de 60%% contre un melange a")
    print("58%% ne vaut rien, quelle que soit l allure du gradient brut.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
