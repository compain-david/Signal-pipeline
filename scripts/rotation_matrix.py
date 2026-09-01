#!/usr/bin/env python3
"""
Rotation bench: every signal against every rotation target, one method throughout.

SHADOW ONLY. Like ladder.py, this measures and governs nothing.

The question
------------
forward_study.py and band_study.py both asked "is this signal any good?" against
a single target, ETH/BTC. That question hides the finding that motivated this
bench: the sign of several signals FLIPS depending on which rotation you are
trying to time. A signal that is stably positive for eth_btc and absent or
inverted for alt_eth is a better object than a signal that is mediocre against
all three, because the first one is a statement about a specific trade and the
second one is noise spread thin.

So the unit of analysis here is the PAIR (signal, target), not the signal, and
the deliverable is a matrix plus a per-signal verdict: target-specific,
generalist, or useless.

One method everywhere, and what that costs
------------------------------------------
Every signal is reduced to its ROLLING PERCENTILE inside its own trailing
window before anything is measured. oos_test.py established why: fitted levels
do not transfer, because BTC dominance drifted structurally upward and three of
five fixed bands came up EMPTY in the test period. A rolling percentile is
stationary by construction.

It costs the first PCT_WINDOW days of every series - a real loss on the series
that only start 2022-08 - and it destroys level information on purpose. A rule
like "dominance below 54%" cannot be expressed here. That is deliberate: on a
basket-derived dominance series, an absolute level is not portable anyway.

Equal-WIDTH bands, not equal-COUNT quantiles - and the price of that
-------------------------------------------------------------------
The bands here are cut at fixed percentile widths (0-20, 20-40, ... 80-100) so
they match walkforward.direction() exactly and the descriptive table cannot
silently measure a different object than the walk-forward test. band_study.py
does the opposite: it cuts equal-COUNT quantiles, so its five bands always hold
a fifth of the sample each. The two modules therefore disagree by construction,
and this one is the loser on balance.

On a drifting series a value is often the largest in its own trailing window,
so its percentile pins at 100 and the top band swells far past a fifth of the
days. Section 2 prints the occupancy of every band for exactly this reason:
"top band" here is not a synonym for "top quintile", and calling it one would
be a misreport. The consequence is measured rather than assumed - a fat top
band is spread over many episodes AND contains a few very long runs, so the two
independence gates both stop discriminating, in opposite directions.

The baseline trap this module refuses to fall into
--------------------------------------------------
Comparing a 2022-2026 signal against a 2019-2026 baseline manufactures edge out
of nothing but the difference between two periods. Every baseline below is
restricted to the dates the pair could see - same signal, same target, same
horizon. forward_study.py applies a correction of the same KIND but not the
same one, and the difference is measured rather than waved through; see below.

That baseline CONTAINS the firing days, and it spans the WHOLE percentile
window of the pair. forward_study.py restricts its own baseline more tightly,
to [first fire, last fire], so the two modules do NOT share a convention - this
one is strictly wider. The difference is not cosmetic: measured on the 18 pairs
of this run it reaches 8.6 points of median on ssr / alt_eth and 7.9 on
mvrv_z_score / alt_eth, both larger than the ~6 point effect this bench can
actually detect. So section 2 prints BOTH columns for every pair rather than
naming a convention and hoping the reader assumes the same one.

A third figure travels alongside: the same edge against the NON-fire days of
the window. The fire set dilutes any baseline that contains it, and on a top
band holding a third of the sample that dilution is large.

Multiplicity, which is the real risk of a bench this wide
---------------------------------------------------------
Six signals x three targets x three horizons is 54 comparisons. Some of them
will look excellent for no reason at all. Rather than assert that in the
abstract, the bench measures it: the signal series is circularly ROTATED
against the targets, many times, and the whole 54-cell matrix is recomputed
each time. Rotation is used instead of a plain shuffle on purpose - it destroys
the alignment between signal and forward return while preserving the signal's
autocorrelation, so the null keeps the clustering that makes real financial
series produce false positives. A plain shuffle would flatter the bench by
pretending every day is an independent draw.

Two corrections are computed on those same draws, and both are printed:

  - Westfall-Young min-p, the standard distribution-free procedure. Each draw's
    null edge is ranked inside ITS OWN cell's null, giving a p-value per cell
    per draw; the minimum across the matrix is that draw's statistic, and a
    cell's adjusted p is how often that minimum beat the cell's raw p. This is
    the headline number, and it carries the name because it is the method.

  - A max-z variant, kept alongside because it was the first thing tried here
    and it is materially HARSHER: it divides each cell by a robust spread, and
    the null of a thin cell is fat-tailed and multimodal, so a single wild draw
    sets the bar for the whole bench. It is reported as a variant, never as
    Westfall-Young.

The bench also prints its MINIMUM DETECTABLE EFFECT, because a unanimous "no"
is worthless without knowing what size of effect could have survived. This
bench is not sensitive; the number says how insensitive.

No cell is called a winner without also surviving walk-forward.

Declared construction biases - these are not caveats, they are properties
------------------------------------------------------------------------
- The alt basket behind alt_eth and alt_btc EXCLUDES SOL, SUI and HYPE. Any
  statement about "alt rotation" made here is a statement about the basket that
  was measurable, not about the trade a human would actually put on. Every
  alt figure printed below carries that marker, because a number quoted out of
  the table loses its footnote.
- Dominance is derived from a small basket whose size varies day to day, so its
  LEVEL is biased; percentiles are invariant to that, its level is not.
- Forward windows overlap, so folds and observations are not independent. Every
  episode count below exists because of this.
- The three targets are arithmetically linked (alt_btc moves with alt_eth times
  eth_btc), so "confirmation across targets" is weaker evidence than it looks.

Run: python scripts/rotation_matrix.py
"""

import bisect
import datetime
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.join(HERE, "..", "analysis")
sys.path.insert(0, HERE)

import forward_study as fs
import walkforward as wf

# This module decides nothing. Kept as a module constant so a test can assert
# it, the same way ladder.py's shadow status is asserted rather than promised.
GOVERNS_NOTHING = True

OUT_PATH = os.path.join(ANALYSIS, "rotation_matrix.txt")

TARGETS = ("eth_btc", "alt_eth", "alt_btc")
HORIZONS = (30, 60, 90)
DECISION_HORIZON = 90          # the horizon the verdict is pronounced on
N_BANDS = 5
BAND_WIDTH = 100 // N_BANDS
TOP_BAND_MIN = 100 - BAND_WIDTH   # a day fires when its percentile reaches this
PCT_WINDOW = 365               # trailing window for the rolling percentile
MIN_OBS = 30                   # below this a median is decoration
MIN_EPISODES = 4               # forward_study.py's bar, kept identical
DOMINANCE_ALARM = 50.0         # % of the fire set allowed in its 3 top episodes
MIN_EDGE_PTS = 3.0             # forward_study.py's bar, kept identical
MONO_MIN = 0.75                # band_study.py's bar: 3 of 4 pairs aligned
WF_GAP_MIN = 15.0              # walkforward.py's flag: real minus its own null
WF_MIN_FOLDS = 3               # walkforward.py refuses to read fewer, so do we
WF_TRAIN, WF_TEST = 365, 180
NULL_DRAWS = 2000
# Deliberately NOT walkforward.SHUFFLES (40). At 40 draws the walk-forward null
# mean carries a standard error of roughly 2 points of agreement, so the +15
# gate below sat inside the noise: re-running dominance ETH / alt_eth with five
# different seeds moved its gap from -3 to +21, i.e. the gate flipped between
# PASS and FAIL on the seed alone. That is the same defect already fixed for
# NULL_DRAWS and it has no business being inherited here.
WF_NULL_DRAWS = 500
ALPHA = 0.05
SEED = 20260901

ALT_BASKET_CAVEAT = "panier alt SANS SOL/SUI/HYPE - biais de construction"
# Thresholds for the two structural checks below. They are hard failures, not
# assertions: `python -O` strips assert statements, and a control that vanishes
# under an optimisation flag is not a control. Both raise with the measured
# number in the message, because "it failed" without the value is a second
# investigation.
REF_MIN_CORR = 0.99
REF_MAX_DIFF = 1.0
IDENTITY_TOL = 1e-9
EXPECTED_CANDIDATES = ("dominance BTC", "dominance ETH", "Fear & Greed",
                       "mvrv_z_score", "ssr", "nvt")
ALT_MARK = "*"

# Present in series.json and deliberately NOT on the bench. Printed in the
# report: the reader cannot audit the claim "54 comparisons" without knowing
# what was available and left out, and an unannounced exclusion is how a bench
# width quietly becomes a choice made after seeing results.
EXCLUDED_BY_DESIGN = (
    ("puell_multiple",
     "mineurs, pas rotation - aucune these de rotation ne le mobilise"),
    ("sth_realized_price",
     "prix, pas oscillateur - son percentile suivrait la tendance BTC"),
    ("fear_greed (dans series.json)",
     "double emploi : la version longue vient du cache F&G, 2018 -> 2026"),
)


# -- loading. Strictly offline: a bench that could silently refetch would make
# -- two runs incomparable, and the whole point here is reproducibility. -----

def _read(name):
    with open(os.path.join(ANALYSIS, name), encoding="utf-8") as f:
        return json.load(f)


def load_rotations():
    return _read("rotations.json")


def load_dominance():
    return _read("dominance.json")


def load_series():
    d = _read("series.json")
    dates = d["dates"]
    return {n: {dt: v for dt, v in zip(dates, vals) if v is not None}
            for n, vals in d["series"].items()}


def load_ethbtc_reference():
    """The ETH/BTC series the REST of the project measures on.

    Loaded only to be checked against rotations.json['eth_btc']. See
    reference_agreement below for why that check has to exist.
    """
    return {d: v["ethbtc"] for d, v in _read("ethbtc.json").items()}


def load_fear_greed_cache():
    """Cache only. forward_study.load_fear_greed falls back to the network when
    the cache is missing; here that fallback is a bug, not a convenience."""
    path = os.path.join(ANALYSIS, ".cache", "fng.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
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


# -- measurement primitives -------------------------------------------------

def pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def reference_agreement(target_px, reference_px, horizon=DECISION_HORIZON):
    """Is rotations.json['eth_btc'] the same TRADE as analysis/ethbtc.json?

    It is not the same SERIES: the two differ by a constant factor of roughly
    six in level, because they are built from different bases. Every other
    module in this project (forward_study, band_study, walkforward, oos_test)
    measures ETH/BTC on the other one, so a reader comparing this bench to
    those has every right to ask whether the numbers are commensurable.

    A constant factor cancels in a ratio of returns, so the answer should be
    yes - but "should" is what an unverified assumption sounds like, and the
    cost of being wrong here is that every eth_btc row in this report is
    incomparable with the rest of the project without anyone noticing. So it is
    measured, printed, and asserted rather than reasoned about.
    """
    fa = fs.forward_map(target_px, horizon)
    fb = fs.forward_map(reference_px, horizon)
    common = sorted(set(fa) & set(fb))
    if len(common) < MIN_OBS:
        return None
    xs = [fa[d] for d in common]
    ys = [fb[d] for d in common]
    lvl = [target_px[d] / reference_px[d]
           for d in sorted(set(target_px) & set(reference_px))
           if reference_px[d]]
    return {"n": len(common),
            "corr": pearson(xs, ys),
            "median_abs_diff": fs.median([abs(a - b) for a, b in zip(xs, ys)]),
            "level_ratio": fs.median(lvl)}


def reference_fold_comparison(here_agree, here_folds, raw_series, reference_fwd,
                              window=PCT_WINDOW, train=WF_TRAIN, test=WF_TEST):
    """Fold counts here against wf.walk on the REFERENCE price series.

    Extracted from section 5's reconciliation so that registry.py runs the same
    comparison rather than a second one written from memory. Two modules
    printing "we do not reproduce walkforward.py" from two independent pieces
    of arithmetic can disagree about how far apart they are, and then the
    disagreement is about the audit rather than about the data.

    What it costs to read this honestly: `here_agree`/`here_folds` come from
    the caller's own walk, so this function cannot verify they were produced
    under the same window widths it is passed. The caller owns that; the
    defaults exist so the common case cannot drift.
    """
    there_agree, there_folds = wf.walk(raw_series, reference_fwd,
                                       window, train, test)
    return {"here_agree": here_agree, "here_folds": here_folds,
            "there_agree": there_agree, "there_folds": there_folds,
            "folds_match": here_folds == there_folds,
            "agree_match": here_agree == there_agree}


def rolling_percentile(series, dates, window=PCT_WINDOW):
    """Rank of today inside its own STRICTLY PRIOR window.

    The trailing window never contains today. That is the difference between a
    bench and a backtest that peeks: including today would let a value rank
    itself, which inflates the extreme bands exactly where the fire set lives.

    Costs the first `window` dates of every series. Sorted-window bisect rather
    than the naive rescan, because this runs once per signal but is walked over
    hundreds of null draws afterwards.
    """
    out = {}
    win = []
    for i, d in enumerate(dates):
        v = series[d]
        if i >= window:
            out[d] = bisect.bisect_left(win, v) / len(win) * 100
            old = series[dates[i - window]]
            del win[bisect.bisect_left(win, old)]
        bisect.insort(win, v)
    return out


def band_dates(dates, pct):
    """Split into N_BANDS of equal percentile WIDTH - not equal count.

    The cuts are walkforward.direction()'s cuts, deliberately, so the table and
    the walk-forward test cannot drift apart. The cost is that band occupancy
    is not a fifth each and must be printed rather than assumed; see the module
    docstring and section 2 of the report.
    """
    bands = []
    for i in range(N_BANDS):
        lo, hi = i * BAND_WIDTH, (i + 1) * BAND_WIDTH
        bands.append([d for d in dates
                      if d in pct and ((lo <= pct[d] < hi)
                                       or (i == N_BANDS - 1
                                           and pct[d] >= TOP_BAND_MIN))])
    return bands


def band_occupancy(bands):
    """Share of the sample in each band. An equal-count cut would give 20%
    everywhere; every departure from 20% here is the drift of the underlying
    series showing through the percentile."""
    total = sum(len(b) for b in bands)
    if not total:
        return []
    return [(len(b), len(b) / total * 100) for b in bands]


def monotonicity(meds):
    """How many adjacent band pairs move the same way.

    One band out of five beating the baseline is what noise looks like when you
    run five bands; an ordered gradient is much harder to fake. Returns None
    when too few bands survived the sample floor to make the score meaningful.
    """
    m = [x for x in meds if x is not None]
    if len(m) < 3:
        return None
    ups = sum(1 for a, b in zip(m, m[1:]) if b > a)
    downs = sum(1 for a, b in zip(m, m[1:]) if b < a)
    pairs = len(m) - 1
    return {"aligned": max(ups, downs), "pairs": pairs,
            "score": max(ups, downs) / pairs,
            "rising": ups > downs}


def episode_stats(dates):
    """Distinct episodes and how much of the fire set sits in the 3 biggest.

    Overlapping forward windows mean a 400-day bucket is not 400 observations.
    This is the test that killed most apparent edges in forward_study.py and it
    is applied here unchanged - but see section 2: on a band this fat, it stops
    discriminating, and that is a finding about the bench, not about a signal.
    """
    eps = fs.episodes(sorted(dates))
    biggest = sorted(eps, key=len, reverse=True)[:3]
    share = (sum(len(e) for e in biggest) / len(dates) * 100) if dates else 0.0
    return {"episodes": len(eps), "top3_share": share, "biggest": biggest}


def firing_window(fire, window_dates):
    """forward_study.assess()'s baseline span: first fire day to last.

    Kept as its own function because it is the ONLY difference between this
    module's headline edge and forward_study.py's, and a difference that big
    (see edge_cell) should be nameable, callable and testable rather than
    inlined into one branch of a formula.
    """
    if not fire:
        return []
    lo, hi = min(fire), max(fire)
    return [d for d in window_dates if lo <= d <= hi]


def edge_cell(fire, window_dates, fwd):
    """Median forward return of the fire set against the SAME-WINDOW baseline.

    `window_dates` is not the whole history: it is exactly the dates this pair
    could see. Widening it to the whole history is the mistake that fabricates
    edge out of a period difference, and it is silent when made.

    THREE edges come back, because "restricted baseline" names two different
    restrictions and this module used to claim the wrong one:

    - `edge`      : baseline = the whole percentile window of the pair, fire
                    days included. This is the headline, and it is WIDER than
                    forward_study.py's.
    - `edge_firewin`: baseline = [first fire, last fire] only. This is
                    forward_study.assess()'s actual convention. The two agree
                    when the fire set reaches both ends of the window and
                    diverge by up to 8.6 points of median when it does not,
                    which is more than this bench can detect - so both are
                    printed and neither is called "the" convention.
    - `edge_excl` : baseline = the window MINUS the fire days. The fire set
                    dilutes any baseline containing it; this is the undiluted
                    separation.
    """
    vals = [fwd[d] for d in fire if d in fwd]
    base = [fwd[d] for d in window_dates if d in fwd]
    if len(vals) < MIN_OBS or len(base) < MIN_OBS:
        return None
    fire_set = set(fire)
    rest = [fwd[d] for d in window_dates if d in fwd and d not in fire_set]
    fwin = [fwd[d] for d in firing_window(fire, window_dates) if d in fwd]
    med = fs.median(vals)
    base_med = fs.median(base)
    return {"n": len(vals), "median": med, "base": base_med,
            "edge": med - base_med,
            "edge_excl": (med - fs.median(rest)) if len(rest) >= MIN_OBS
            else None,
            "edge_firewin": (med - fs.median(fwin)) if len(fwin) >= MIN_OBS
            else None,
            "n_rest": len(rest), "n_firewin": len(fwin),
            "hit": sum(1 for v in vals if v > 0) / len(vals) * 100}


def rotate(values, offset):
    """Circular rotation - the null that keeps autocorrelation.

    A plain shuffle destroys clustering and so understates how often a real,
    persistent series lines up with forward returns by accident. It would make
    this bench look more discriminating than it is.

    The price is one artificial discontinuity per draw, at the join. That is a
    single break against the roughly n/2 a shuffle would create, so the null
    stays slightly optimistic - but only slightly, and in the direction that
    makes a finding harder rather than easier to claim.
    """
    if not values:
        return values
    k = offset % len(values)
    return values[k:] + values[:k]


def walk_folds(pct, dates, fwd, train=WF_TRAIN, test=WF_TEST):
    """Fit direction on one window, check it on the next, roll forward.

    Direction rather than magnitude, exactly as walkforward.py argues: at this
    sample size magnitudes are noise and only the sign is actionable.

    wf.direction is IMPORTED, so the band cuts and the sign rule cannot drift.
    The date preparation is NOT shared, and the two modules therefore DO give
    different answers - do not read the import as a guarantee of agreement:

      walkforward.walk  computes the rolling percentile over dates ALREADY
                        filtered by `fwd`, so its trailing window holds 365
                        dates that have a forward return.
      walk_folds (here) receives a percentile computed over EVERY date of the
                        signal, then drops the dates without a forward return.

    On Fear & Greed, whose history runs well past the target's, that changes
    which days are usable and so where the folds cut: wf.walk returns 1 fold
    agreeing out of 9, this returns 2 out of 9, on the identical forward map.
    Section 5 prints that reconciliation rather than letting a reader assume
    the established 1-in-9 result was reproduced here.

    Neither preparation is wrong. This one keeps the percentile identical to
    the one the descriptive table and the null matrix use, which is the
    identity this module is built to protect; walkforward.py keeps its window
    homogeneous in tradeable days. They cannot both be had.
    """
    usable = [d for d in dates if d in pct and d in fwd]
    folds = agree = 0
    start = 0
    while start + train + test <= len(usable):
        tr = usable[start:start + train]
        te = usable[start + train:start + train + test]
        dtr, dte = wf.direction(tr, pct, fwd), wf.direction(te, pct, fwd)
        if dtr is not None and dte is not None:
            folds += 1
            agree += int(dtr == dte)
        start += test
    return agree, folds


def wf_null_rate(pct, dates, fwd, rng, mode, draws=WF_NULL_DRAWS):
    """Walk-forward agreement under a null, by shuffle or by circular shift.

    Both exist because the two nulls in this module were INCOHERENT and that
    had to be measured rather than argued away: the edge null is a circular
    shift (it keeps autocorrelation), while walkforward.py's null - which this
    module inherited - is a plain shuffle, inside a module whose central claim
    is that a shuffle flatters a bench. Running both is the only way to say
    whether the inconsistency moved any verdict. Section 5 reports the answer.

    Returns the mean WITH its standard error, never a bare number. The mean
    alone invites exactly the error this module spent NULL_DRAWS fixing
    elsewhere: a gate compared against a Monte-Carlo estimate whose own noise
    is larger than the distance to the threshold. The caller needs the error
    bar to know whether its verdict is a measurement or a seed.
    """
    vals = [pct[d] for d in dates]
    if not vals:
        return None
    rates = []
    for _ in range(draws):
        if mode == "melange":
            v = list(vals)
            rng.shuffle(v)
        else:
            v = rotate(vals, rng.randrange(len(vals)))
        na, nf = walk_folds(dict(zip(dates, v)), dates, fwd)
        if nf:
            rates.append(na / nf * 100)
    if not rates:
        return None
    n = len(rates)
    mean = sum(rates) / n
    var = sum((r - mean) ** 2 for r in rates) / (n - 1) if n > 1 else 0.0
    return {"mean": mean, "se": math.sqrt(var / n) if n else None,
            "draws": draws, "used": n}


def gap_is_undecided(gap, se, bar=WF_GAP_MIN):
    """Is this gap within Monte-Carlo noise of the gate it is being judged by?

    Printed as a `~` next to every such pair. A gap of +16 against a null whose
    own error bar is +-2 has not cleared a +15 bar; it has landed on it, and
    re-seeding decides the verdict. Saying so is cheap; the alternative is a
    report whose conclusions change when nobody changed anything.
    """
    if gap is None or se is None:
        return False
    return abs(gap - bar) < 2 * se


# -- the pair measurement ---------------------------------------------------

def measure_pair(pct, pct_dates, fwds, rng):
    """Everything the bench knows about one (signal, target) pair."""
    window = {h: [d for d in pct_dates if d in fwds[h]] for h in HORIZONS}
    bands = band_dates(pct_dates, pct)
    fire = bands[-1]

    row = {"n_window": len(pct_dates), "fire_n": len(fire), "edges": {},
           "bands": {}, "mono": {}, "sign": {},
           "occupancy": band_occupancy(bands)}
    row.update(episode_stats(fire))
    row["window_span"] = ((min(pct_dates), max(pct_dates)) if pct_dates
                          else (None, None))

    for h in HORIZONS:
        fwd = fwds[h]
        row["edges"][h] = edge_cell(fire, window[h], fwd)
        meds = []
        for b in bands:
            v = [fwd[d] for d in b if d in fwd]
            meds.append(fs.median(v) if len(v) >= MIN_OBS else None)
        row["bands"][h] = meds
        row["mono"][h] = monotonicity(meds)
        # The sign is the deliverable, not a footnote: it is what inverts
        # between targets, and a signal read with the wrong sign is worse than
        # no signal at all.
        if meds[0] is not None and meds[-1] is not None:
            row["sign"][h] = 1 if meds[-1] > meds[0] else -1
        else:
            row["sign"][h] = None

    fwd = fwds[DECISION_HORIZON]
    a, f = walk_folds(pct, pct_dates, fwd)
    row["wf"] = {"agree": a, "folds": f,
                 "rate": (a / f * 100) if f else None}

    for mode in ("decalage", "melange"):
        nl = wf_null_rate(pct, pct_dates, fwd, rng, mode)
        row["wf"]["null_" + mode] = None if nl is None else nl["mean"]
        row["wf"]["se_" + mode] = None if nl is None else nl["se"]
        row["wf"]["gap_" + mode] = (None if nl is None or row["wf"]["rate"] is None
                                    else row["wf"]["rate"] - nl["mean"])
    # The primary null is the circular shift, to match the edge null. The
    # shuffle is carried alongside so the disagreement stays visible.
    row["wf"]["null"] = row["wf"]["null_decalage"]
    row["wf"]["gap"] = row["wf"]["gap_decalage"]
    row["wf"]["se"] = row["wf"]["se_decalage"]
    # The real walk is a single deterministic count, so all the Monte-Carlo
    # error sits in the null mean; the gap inherits it unchanged.
    row["wf"]["undecided"] = gap_is_undecided(row["wf"]["gap"], row["wf"]["se"])
    return row


# -- multiplicity -----------------------------------------------------------

def build_index(signal_dates, pct, fwds_by_target):
    """Positions and pre-aligned forward returns, so the null loop is arithmetic.

    Recomputing `[d for d in dates if d in fwd]` inside 2000 draws is what made
    a 200-draw null the affordable choice, and a 200-draw null has a resolution
    floor of 1/200 - which is coarser than the p-values it was being asked to
    print. So the per-cell date sets and the baseline medians, none of which
    depend on the draw, are computed once here.

    The three targets are asserted to share a date set. They do, being three
    ratios over the same daily grid; if they ever stop, this raises instead of
    silently measuring three different windows and comparing them.
    """
    idx, fwd_vals, base_med = {}, {}, {}
    for h in HORIZONS:
        sets = [set(fwds_by_target[t][h]) for t in fwds_by_target]
        common = set.intersection(*sets) if sets else set()
        for t in fwds_by_target:
            if set(fwds_by_target[t][h]) != common:
                raise ValueError(
                    "cible %s : grille de dates differente a %dj" % (t, h))
        idx[h] = [i for i, d in enumerate(signal_dates) if d in common]
        for t, fwds in fwds_by_target.items():
            fwd_vals[(t, h)] = [fwds[h][signal_dates[i]] for i in idx[h]]
            base_med[(t, h)] = fs.median(fwd_vals[(t, h)])
    return {"pct_vals": [pct[d] for d in signal_dates],
            "idx": idx, "fwd": fwd_vals, "base": base_med}


def matrix_edges(indexes, offset_frac):
    """The whole matrix at one rotation offset. offset_frac 0.0 is the real one.

    Same code path for the observation and for every null draw. If the two
    diverged by even a date, the null would be answering a question the
    observation never asked, and nothing downstream would notice.
    """
    out = {}
    for sname, ix in indexes.items():
        vals = ix["pct_vals"]
        n = len(vals)
        rot = rotate(vals, int(offset_frac * n))
        for h in HORIZONS:
            positions = ix["idx"][h]
            keep = [j for j, i in enumerate(positions) if rot[i] >= TOP_BAND_MIN]
            if len(keep) < MIN_OBS:
                continue
            for (t, hh), fv in ix["fwd"].items():
                if hh != h:
                    continue
                sel = [fv[j] for j in keep]
                out[(sname, t, h)] = fs.median(sel) - ix["base"][(t, h)]
    return out


def null_matrix(indexes, rng, draws=NULL_DRAWS):
    """Recompute the WHOLE 54-cell matrix under rotation, `draws` times.

    One offset per draw, applied to every signal, because the signals are
    correlated with each other and independent offsets would break that
    correlation. Preserving it makes the null harder to beat, which is the
    direction an honest null should err in: it is how several cells light up
    together by accident.

    Returns, per cell, a list of EXACTLY `draws` entries, using None for a draw
    in which that cell fell below MIN_OBS and was not scored. The padding is
    the whole point. A cell is skipped whenever the rotation leaves its top
    band too thin, so an append-only list silently COMPACTS: cell A's entry 300
    would be draw 300 while cell B's entry 300 was draw 312. Both corrections
    downstream index these lists positionally to build a per-draw statistic, so
    they would have been maximising over edges from different draws and nothing
    would have raised. In this run every cell happens to survive all 2000 draws
    and the bug is dormant; a shorter candidate or a higher MIN_OBS wakes it.

    Also returns, per draw, how many cells cleared the raw edge bar - the
    plain-language version of the same warning.
    """
    per_cell, counts = {}, []
    for t in range(draws):
        m = matrix_edges(indexes, rng.random())
        for key in m:
            per_cell.setdefault(key, [None] * t)
        for key, lst in per_cell.items():
            # Every list grows by exactly one entry per draw, so position i is
            # draw i in every cell, for good.
            lst.append(m.get(key))
        counts.append(sum(1 for e in m.values() if e >= MIN_EDGE_PTS))
    return {"per_cell": per_cell, "counts": counts, "draws": draws}


def quantile(xs, q):
    if not xs:
        return None
    s = sorted(xs)
    i = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[i]


def raw_p_value(nulls, observed):
    """(hits + 1) / (draws + 1) - the add-one is not decoration.

    A cell beaten by zero draws has not got p = 0; it has got "smaller than
    this null can resolve". The add-one says so, and the Monte-Carlo interval
    printed beside it says how coarse the resolution is. Quoting a raw p to
    three decimals off a few hundred draws is quoting the grain of the rng.
    """
    nulls = [x for x in nulls if x is not None]
    if not nulls:
        return None
    hits = sum(1 for x in nulls if x >= observed)
    p = (hits + 1) / (len(nulls) + 1)
    se = math.sqrt(max(p * (1 - p), 0.0) / len(nulls))
    return {"p": p, "se": se, "hits": hits, "draws": len(nulls),
            "floor": 1.0 / (len(nulls) + 1)}


def westfall_young_minp(per_cell, real_edges):
    """The real Westfall-Young min-p procedure, on the module's own draws.

    Each null edge is ranked inside the null of the cell it came from, which
    turns every cell onto the same p-value scale without assuming anything
    about the shape of its distribution - that is the whole point of the
    method, and the reason it can cope with a null that is fat-tailed and
    multimodal. The statistic of a draw is the SMALLEST such p anywhere in the
    matrix; a cell's adjusted p is how often that bench-wide minimum came in at
    or below the cell's own raw p.

    This controls the family-wise error rate for the 54 comparisons together.
    It costs power on purpose: a real but modest effect dies here, and that is
    the bill for having looked 54 times.
    """
    scored = {k: [x for x in v if x is not None] for k, v in per_cell.items()}
    keys = [k for k in per_cell if real_edges.get(k) is not None
            and len(scored[k]) >= 10]
    if not keys:
        return {"adjusted": {}, "raw": {}, "min_p": [], "cells": 0,
                "draws": 0, "floor": None, "critical_p": None}

    # Lists are draw-aligned and equal-length by construction (see
    # null_matrix), so position i is draw i everywhere. A cell scored in only
    # some draws contributes to those draws and abstains from the rest, rather
    # than sliding its later draws forward onto other cells' draws.
    draws = min(len(per_cell[k]) for k in keys)
    raw = {}
    ranks = {}
    for k in keys:
        nulls = scored[k]
        n_k = len(nulls)
        raw[k] = (sum(1 for x in nulls if x >= real_edges[k]) + 1) / (n_k + 1)
        # p of each null draw inside its own cell's null, LEAVING ITSELF OUT
        # and over the same denominator as the raw p above. Both details
        # matter: a draw counted in its own reference set can never reach the
        # floor the observation can reach, and a correction whose statistic
        # cannot reach the observed scale would report adjusted p-values
        # SMALLER than the raw ones - the one thing a correction must never do.
        srt = sorted(nulls)
        ranks[k] = [None if x is None
                    else (n_k - bisect.bisect_left(srt, x)) / (n_k + 1)
                    for x in per_cell[k][:draws]]

    min_p = []
    for i in range(draws):
        here = [ranks[k][i] for k in keys if ranks[k][i] is not None]
        if here:
            min_p.append(min(here))
    draws = len(min_p)
    if not draws:
        return {"adjusted": {}, "raw": raw, "min_p": [], "cells": len(keys),
                "draws": 0, "floor": None, "critical_p": None}
    adjusted = {k: sum(1 for m in min_p if m <= raw[k]) / draws for k in keys}
    # The smallest adjusted p this bench could ever return, whatever the data.
    # It is roughly (number of cells) / (number of draws), because each cell
    # contributes one draw sitting at the top of its own null. If it ever
    # approached ALPHA, the procedure would be incapable of passing anything
    # and the "no survivor" verdict would be an artefact of the draw count.
    adj_floor = (sum(1 for m in min_p if m <= 1.0 / (draws + 1)) / draws)
    return {"adjusted": adjusted, "raw": raw, "min_p": min_p,
            "cells": len(keys), "draws": draws, "floor": adj_floor,
            "critical_p": quantile(min_p, ALPHA)}


def standardise(nulls):
    """Centre and robust spread of one cell's null edges.

    A robust spread, not a standard deviation: the null of a thin cell has fat
    tails and one extreme draw would shrink every z-score in the matrix. Returns
    None when the cell's null has no spread at all, which is the honest answer -
    such a cell cannot be scored, and pretending otherwise divides by zero.
    """
    if len(nulls) < 10:
        return None
    centre = quantile(nulls, 0.50)
    spread = (quantile(nulls, 0.84) - quantile(nulls, 0.16)) / 2.0
    if spread <= 0:
        return None
    return {"centre": centre, "spread": spread}


def max_z_correction(per_cell, real_edges):
    """A max-statistic variant, NOT Westfall-Young, and harsher than it.

    It puts every cell on its own robust spread and asks how often the largest
    z anywhere in the matrix beat a cell. That is a legitimate family-wise
    correction only if the standardised nulls are roughly exchangeable, and
    here they are not: a thin cell's null is fat-tailed, so one draw with an
    enormous z sets the bar for all 54 and the adjusted p roughly doubles
    against the distribution-free method. It is kept because it is what the
    first version of this module used, and dropping it silently would hide that
    the headline number moved.
    """
    scales, z_real, n_draws = {}, {}, 0
    for key, raw_nulls in per_cell.items():
        nulls = [x for x in raw_nulls if x is not None]
        sc = standardise(nulls)
        if sc is None or real_edges.get(key) is None:
            continue
        scales[key] = sc
        z_real[key] = (real_edges[key] - sc["centre"]) / sc["spread"]
        n_draws = max(n_draws, len(raw_nulls))

    max_z = []
    for i in range(n_draws):
        # Same draw index in every cell, and a cell that abstained at draw i
        # contributes nothing to draw i - it does not lend it a z from one of
        # its other draws.
        zs = [(per_cell[k][i] - scales[k]["centre"]) / scales[k]["spread"]
              for k in scales
              if i < len(per_cell[k]) and per_cell[k][i] is not None]
        if zs:
            max_z.append(max(zs))
    if not max_z:
        return {"adjusted": {}, "z": z_real, "scales": scales,
                "max_z": [], "critical_z": None}
    adjusted = {k: sum(1 for m in max_z if m >= z) / len(max_z)
                for k, z in z_real.items()}
    return {"adjusted": adjusted, "z": z_real, "scales": scales,
            "max_z": max_z, "critical_z": quantile(max_z, 1 - ALPHA)}


def mde_maxz(scale, critical_z):
    """Smallest edge that would clear the max-z bar, in points of median.

    A unanimous rejection is only informative next to this number. Without it
    "nothing passed" is compatible with both "there is nothing" and "this bench
    could not have seen anything short of a miracle", and those are different
    findings.
    """
    if scale is None or critical_z is None:
        return None
    return scale["centre"] + critical_z * scale["spread"]


def mde_minp(nulls, critical_p):
    """Same question under the min-p procedure: the edge whose raw p would be
    small enough that the bench-wide minimum beats it only ALPHA of the time."""
    nulls = [x for x in nulls if x is not None]
    if not nulls or critical_p is None:
        return None
    draws = len(nulls)
    # An observed edge x gets raw p (#{null >= x} + 1) / (draws + 1), so it
    # clears the bar only while at most `allowed` null draws reach it. The
    # smallest such x is the (allowed)-th largest null - one rank ABOVE the
    # allowed-th, which is where an off-by-one here would quietly report a bar
    # that does not in fact clear the correction.
    allowed = int(critical_p * (draws + 1)) - 1
    if allowed < 1:
        return None
    desc = sorted(nulls, reverse=True)
    return desc[min(allowed - 1, draws - 1)]


# -- verdicts ---------------------------------------------------------------

def gates(row, adjusted_p):
    """Every bar a pair must clear. All of them, or it is not a finding.

    Each gate exists because something already failed on it in this project:
    the edge bar and the episode bar come from forward_study.py, the
    concentration alarm from the F&G-2021 illusion, monotonicity from
    band_study.py, walk-forward from the F&G instability, and the multiplicity
    gate from this bench being 54 comparisons wide.

    The fold floor is a real bar, not a formality - an agreement of 100% over
    two folds is one coin landing the same way twice - but section 5 prints
    which pairs it actually stops, because asserting that it does the work when
    it does not would be exactly the kind of claim this module exists to refuse.
    """
    e = row["edges"].get(DECISION_HORIZON)
    wfr = row["wf"]
    return {
        "edge": e is not None and e["edge"] >= MIN_EDGE_PTS,
        "episodes": row["episodes"] >= MIN_EPISODES,
        "concentration": row["top3_share"] <= DOMINANCE_ALARM,
        "monotonie": (row["mono"].get(DECISION_HORIZON) is not None
                      and row["mono"][DECISION_HORIZON]["score"] >= MONO_MIN),
        "walkforward": (wfr.get("folds", 0) >= WF_MIN_FOLDS
                        and wfr.get("gap") is not None
                        and wfr["gap"] >= WF_GAP_MIN),
        "multiplicite": adjusted_p is not None and adjusted_p <= ALPHA,
    }


def drop_k_survivors(all_gates, k):
    """How many pairs would pass if k gates were removed - every combination.

    Drop-1 was the first thing this module printed and it was worthless: two
    gates each failed on all 18 pairs, so removing any single gate could not
    possibly produce a survivor. That is a theorem about the failure counts,
    not a measurement, and printing it as reassurance was misleading. Drop-2 is
    the smallest question with an informative answer, and its answer is not
    zero.
    """
    if not all_gates:
        return []
    names = sorted(next(iter(all_gates.values())))
    combos = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)) if k == 2 else range(i, i + 1):
            dropped = (names[i],) if k == 1 else (names[i], names[j])
            survivors = [p for p, g in all_gates.items()
                         if all(v for n, v in g.items() if n not in dropped)]
            combos.append({"dropped": dropped, "n": len(survivors),
                           "pairs": survivors})
    return combos


def classify(cells):
    """Target-specific, generalist, or useless - and whether the sign holds.

    `cells` maps target -> {"passes": bool, "sign": +1/-1/None}. Kept pure so
    the taxonomy can be tested without touching a data file, because this is
    the sentence a reader will quote and it must not depend on today's numbers.
    """
    winners = [t for t in cells if cells[t]["passes"]]
    signs = [cells[t]["sign"] for t in cells if cells[t]["sign"] is not None]
    unstable = len(set(signs)) > 1
    if not winners:
        return {"verdict": "INUTILE", "targets": [], "sign_unstable": unstable}
    if len(winners) == 1:
        return {"verdict": "SPECIFIQUE A %s" % winners[0],
                "targets": winners, "sign_unstable": unstable}
    wsigns = {cells[t]["sign"] for t in winners}
    if len(wsigns) == 1:
        return {"verdict": "GENERALISTE", "targets": winners,
                "sign_unstable": unstable}
    return {"verdict": "GENERALISTE AU SIGNE INSTABLE", "targets": winners,
            "sign_unstable": True}


def candidate_series(dom, series, fng):
    """The bench's candidate list, in one place so a test can pin its width.

    The target's own level is added per target further down as a mean-reversion
    CONTROL - it is not a candidate, and counting it among the candidates would
    inflate the bench width for free. Anything in series.json that is not here
    is listed in EXCLUDED_BY_DESIGN and printed: the "54 comparisons" claim is
    only auditable if the reader can see what was on offer and what was left.
    """
    return [
        ("dominance BTC", {d: v["btc_dom"] for d, v in dom.items()}),
        ("dominance ETH", {d: v["eth_dom"] for d, v in dom.items()}),
        ("Fear & Greed", dict(fng)),
        ("mvrv_z_score", series.get("mvrv_z_score", {})),
        ("ssr", series.get("stablecoin_supply_ratio", {})),
        ("nvt", series.get("nvt", {})),
    ]


def select_candidates(raw, min_len):
    """Keep the signals long enough to survive the percentile window - loudly.

    The silent version of this line removed a candidate from the bench without
    a word, which quietly changed the bench WIDTH, which is the denominator of
    every multiplicity statement in the report. A dropped candidate is now
    returned with its length so the report can announce it.
    """
    kept, dropped = [], []
    for name, s in raw:
        if len(s) > min_len:
            kept.append((name, s))
        else:
            dropped.append((name, len(s)))
    return kept, dropped


# -- rendering --------------------------------------------------------------

class Out(object):
    """Collects the report so stdout and the file cannot disagree."""

    def __init__(self):
        self.lines = []

    def __call__(self, s=""):
        self.lines.append(s)

    def text(self):
        return "\n".join(self.lines) + "\n"


def _sign_mark(s):
    return {1: "+", -1: "-"}.get(s, "?")


def _tmark(t):
    """Every alt column and every alt row carries its own marker. A number
    copied out of this report without the SOL/SUI/HYPE exclusion attached is a
    number about a basket the reader thinks is the alt market and is not."""
    return t + (ALT_MARK if t.startswith("alt") else "")


def main():
    rng = random.Random(SEED)
    out = Out()

    rot = load_rotations()
    dom = load_dominance()
    series = load_series()
    fng = load_fear_greed_cache()

    targets = {t: rot[t] for t in TARGETS if t in rot}
    fwds_by_target = {t: {h: fs.forward_map(px, h) for h in HORIZONS}
                      for t, px in targets.items()}

    raw_candidates = candidate_series(dom, series, fng)
    candidates, dropped = select_candidates(raw_candidates,
                                            PCT_WINDOW + MIN_OBS)

    signals_pct = {}
    for name, s in candidates:
        ds = sorted(s)
        pct = rolling_percentile(s, ds)
        signals_pct[name] = (pct, [d for d in ds if d in pct])

    controls_pct = {}
    for t, px in targets.items():
        ds = sorted(px)
        pct = rolling_percentile(px, ds)
        controls_pct[t] = (pct, [d for d in ds if d in pct])

    # --- header ------------------------------------------------------------
    out("BANC DE ROTATION - chaque signal contre chaque cible")
    out("=" * 74)
    out("Statut : SHADOW. Ce banc ne gouverne rien, comme ladder.py.")
    out("Genere par scripts/rotation_matrix.py - hors ligne, graine %d." % SEED)
    out("%s = %s" % (ALT_MARK, ALT_BASKET_CAVEAT))
    out()
    out("--- perimetre mesure dans ce run ---")
    for t in targets:
        ds = sorted(targets[t])
        out("  cible %-9s %5d jours  %s -> %s%s"
            % (_tmark(t), len(ds), ds[0], ds[-1],
               ("   [%s]" % ALT_BASKET_CAVEAT) if t.startswith("alt") else ""))
    for name, s in candidates:
        ds = sorted(s)
        out("  signal %-14s %5d jours  %s -> %s  (utilisables apres percentile %dj : %d)"
            % (name, len(ds), ds[0], ds[-1], PCT_WINDOW,
               len(signals_pct[name][1])))
    out()
    out("  candidats retenus : %d. Le banc fait %d signaux x %d cibles x %d"
        % (len(candidates), len(candidates), len(targets), len(HORIZONS)))
    out("  horizons = %d comparaisons ; ce compte est verifiable seulement si"
        % (len(candidates) * len(targets) * len(HORIZONS)))
    out("  les ecarts sont annonces, donc les voici.")
    if dropped:
        for name, n in dropped:
            out("  candidat ECARTE : %-16s %d jours < %d requis (percentile %dj"
                % (name, n, PCT_WINDOW + MIN_OBS + 1, PCT_WINDOW))
            out("                    + %d observations minimum)" % MIN_OBS)
    else:
        out("  candidat ECARTE pour longueur insuffisante : aucun.")
    out("  series presentes dans series.json et EXCLUES du banc par choix :")
    for name, why in EXCLUDED_BY_DESIGN:
        out("    %-28s %s" % (name, why))

    # --- coherence with the rest of the project ----------------------------
    ref = reference_agreement(targets["eth_btc"], load_ethbtc_reference())
    out()
    out("--- controle de coherence : eth_btc ici vs analysis/ethbtc.json ---")
    if ref is None:
        out("  recouvrement insuffisant - controle impossible, resultat")
        out("  eth_btc a lire comme incomparable au reste du projet.")
    else:
        out("  rotations.json['eth_btc'] vaut %.2fx le niveau de ethbtc.json :"
            % ref["level_ratio"])
        out("  ce sont deux bases differentes, pas la meme serie. Un facteur")
        out("  constant s annule dans un rendement, ce qui se verifie :")
        out("    correlation des rendements %dj : %.4f sur %d jours communs"
            % (DECISION_HORIZON, ref["corr"], ref["n"]))
        out("    ecart absolu median            : %.2f pt" % ref["median_abs_diff"])
        out("  Les lignes eth_btc de ce banc sont donc comparables a")
        out("  forward_study / band_study / walkforward / oos_test.")
        if not (ref["corr"] > REF_MIN_CORR
                and ref["median_abs_diff"] < REF_MAX_DIFF):
            raise ValueError(
                "eth_btc de rotations.json incommensurable avec ethbtc.json : "
                "correlation %.4f (min %.2f), ecart absolu median %.2f pt "
                "(max %.2f) sur %d jours communs. Toute ligne eth_btc de ce "
                "banc serait incomparable au reste du projet."
                % (ref["corr"], REF_MIN_CORR, ref["median_abs_diff"],
                   REF_MAX_DIFF, ref["n"]))

    # --- measure -----------------------------------------------------------
    rows, indexes = {}, {}
    for name, (pct, pd_) in signals_pct.items():
        usable = [d for d in pd_ if any(d in fwds_by_target[t][h]
                                        for t in targets for h in HORIZONS)]
        indexes[name] = build_index(usable, pct, fwds_by_target)
        for t, fwds in fwds_by_target.items():
            rows[(name, t)] = measure_pair(pct, usable, fwds, rng)

    control_rows = {}
    for t, (pct, pd_) in controls_pct.items():
        fwds = fwds_by_target[t]
        usable = [d for d in pd_ if any(d in fwds[h] for h in HORIZONS)]
        control_rows[t] = measure_pair(pct, usable, fwds, rng)

    real_edges = matrix_edges(indexes, 0.0)
    # The descriptive table and the null must be the same measurement. If they
    # are not, every p-value below is answering a question no cell was asked.
    for (sname, tname), row in rows.items():
        for h in HORIZONS:
            e = row["edges"].get(h)
            if e is not None and (sname, tname, h) in real_edges:
                gap = abs(e["edge"] - real_edges[(sname, tname, h)])
                if gap >= IDENTITY_TOL:
                    raise ValueError(
                        "table descriptive et chemin du null divergent sur "
                        "%s / %s a %dj : %.12f contre %.12f (ecart %.3e > "
                        "%.0e). Chaque p de ce rapport repondrait alors a une "
                        "question qu aucune cellule n a posee."
                        % (sname, tname, h, e["edge"],
                           real_edges[(sname, tname, h)], gap, IDENTITY_TOL))


    # The largest disagreement between the two baseline conventions in THIS
    # run. Computed rather than remembered: the sentence in the bias block
    # quotes it, and a quoted constant is a claim that rots.
    conv_deltas = [abs(e["edge_firewin"] - e["edge"])
                   for r in list(rows.values()) + list(control_rows.values())
                   for e in r["edges"].values()
                   if e is not None and e["edge_firewin"] is not None]
    max_conv_delta = max(conv_deltas) if conv_deltas else 0.0

    out()
    out("--- biais declares, valables pour chaque ligne du rapport ---")
    n_assets = [v.get("n_assets") for v in dom.values() if v.get("n_assets")]
    out("  1. %s. Toute phrase sur la" % ALT_BASKET_CAVEAT)
    out("     'rotation alt' porte sur le panier mesurable, pas sur le trade.")
    out("     Marque %s sur chaque colonne, chaque ligne et chaque paragraphe"
        % ALT_MARK)
    out("     qui cite un chiffre alt.")
    # Marked like every other alt mention, though this line quotes no figure.
    # The guard in the tests is an absolute invariant rather than one with an
    # exemption list, because an exemption list is where the next unmarked
    # number goes.
    out("  2. Les trois cibles sont liees arithmetiquement (alt_btc%s suit"
        % ALT_MARK)
    out("     alt_eth%s x eth_btc) : une confirmation croisee vaut moins qu il"
        % ALT_MARK)
    out("     n y parait.")
    out("  3. Fenetres forward chevauchantes : les observations ne sont pas")
    out("     independantes, d ou le comptage d episodes partout.")
    out("  4. Un percentile glissant %dj coute les %d premiers jours de chaque"
        % (PCT_WINDOW, PCT_WINDOW))
    out("     serie et efface l information de niveau. Aucune regle en seuil")
    out("     absolu n est exprimable ici.")
    out("  5. Panier dominance : %d a %d actifs selon le jour - le NIVEAU est"
        % (min(n_assets), max(n_assets)))
    out("     biaise, le percentile ne l est pas.")
    out("  6. Les bandes sont d egale LARGEUR en percentile, pas d egal")
    out("     EFFECTIF comme dans band_study.py. Occupation reelle en")
    out("     section 2 : la bande haute n est pas un quintile.")
    out("  7. Baseline = la fenetre percentile COMPLETE du couple, jours de")
    out("     tir inclus. Elle est PLUS LARGE que celle de forward_study.py,")
    out("     qui se restreint a [premier tir, dernier tir] : les deux modules")
    out("     ne partagent PAS la meme convention. L ecart mesure sur les 18")
    out("     couples de ce run va jusqu a %.1f pts (voir colonne 'e90 tir'"
        % max_conv_delta)
    out("     en section 2), soit davantage que ce que ce banc sait detecter.")
    out("     Les deux colonnes sont donc imprimees, plus l edge hors jours de")
    out("     tir, et aucune n est designee comme 'la' convention.")
    out("  8. Banc entierement IN-SAMPLE. Aucune periode n est tenue a l ecart.")
    out("     Le walk-forward n est PAS un test hors echantillon : il refait")
    out("     tourner la meme fenetre sur elle-meme. L echec hors echantillon")
    out("     etabli par oos_test.py sur eth_btc n a PAS ete rejoue sur")
    out("     alt_eth%s / alt_btc%s, faute d une troisieme periode disponible."
        % (ALT_MARK, ALT_MARK))
    out("     Ce banc decrit ce qui s est produit ; il ne teste aucune regle")
    out("     choisie apres l avoir vu.")

    nm = null_matrix(indexes, rng)
    null_count_med = quantile(nm["counts"], 0.50)
    null_count_p95 = quantile(nm["counts"], 0.95)

    wy = westfall_young_minp(nm["per_cell"], real_edges)
    mz = max_z_correction(nm["per_cell"], real_edges)
    raw_p = {k: raw_p_value(nm["per_cell"].get(k, []), real_edges[k])
             for k in real_edges}

    n_cells = len(signals_pct) * len(targets) * len(HORIZONS)

    # --- 1. the matrix -----------------------------------------------------
    out()
    out()
    out("=== 1. MATRICE - edge a %dj, en points de mediane ===" % DECISION_HORIZON)
    out()
    out("  Edge = mediane de la BANDE HAUTE du signal (percentile >= %d) MOINS"
        % TOP_BAND_MIN)
    out("  la mediane de la meme fenetre. Baseline restreinte a la fenetre du")
    out("  couple : comparer 2022-2026 a une baseline 2019-2026 fabriquerait")
    out("  de l edge a partir d une simple difference de periode.")
    out("  Le signe entre parentheses est celui du gradient (bande haute vs basse).")
    out("  Colonnes %s : %s." % (ALT_MARK, ALT_BASKET_CAVEAT))
    out()
    out("  %-16s %18s %18s %18s"
        % ("signal", *[_tmark(t) for t in targets]))
    out("  " + "-" * 74)
    for name in signals_pct:
        cells = []
        for t in targets:
            r = rows[(name, t)]
            e = r["edges"].get(DECISION_HORIZON)
            if e is None:
                cells.append("%18s" % "-")
            else:
                cells.append("%14s (%s)" % ("%+.1f pts" % e["edge"],
                                            _sign_mark(r["sign"][DECISION_HORIZON])))
        out("  %-16s %s %s %s" % (name, *cells))
    out("  " + "-" * 74)
    cells = []
    for t in targets:
        r = control_rows[t]
        e = r["edges"].get(DECISION_HORIZON)
        cells.append("%18s" % "-" if e is None
                     else "%14s (%s)" % ("%+.1f pts" % e["edge"],
                                         _sign_mark(r["sign"][DECISION_HORIZON])))
    out("  %-16s %s %s %s" % ("CONTROLE niveau", *cells))
    out("  (le controle est le niveau de la cible elle-meme : retour a la")
    out("   moyenne. Il n est pas un candidat et ne compte pas dans le banc.)")

    # --- 2. detail per target ---------------------------------------------
    out()
    out()
    out("=== 2. DETAIL PAR CIBLE ===")
    out()
    out("--- occupation des bandes (identique d une cible a l autre) ---")
    out()
    out("  Un decoupage a effectif egal donnerait 20% partout. Ici les bandes")
    out("  sont d egale LARGEUR en percentile, donc l occupation mesure la")
    out("  derive de la serie : sur une serie qui monte, la valeur du jour est")
    out("  souvent la plus haute de sa fenetre glissante, son percentile se")
    out("  colle a 100 et la bande haute enfle.")
    out()
    out("  %-17s %8s %8s %8s %8s %8s"
        % ("signal", "b1", "b2", "b3", "b4", "b5 (tir)"))
    out("  " + "-" * 62)
    first_t = next(iter(targets))
    for name in signals_pct:
        occ = rows[(name, first_t)]["occupancy"]
        out("  %-17s %s" % (name,
                            " ".join("%7.0f%%" % s for _, s in occ)))
    occ_ctrl = {t: control_rows[t]["occupancy"] for t in targets}
    for t in targets:
        out("  %-17s %s" % ("CONTROLE " + _tmark(t),
                            " ".join("%7.0f%%" % s for _, s in occ_ctrl[t])))
    out()
    out("  band_study.py utilise des quantiles a EFFECTIF egal ; ce banc non.")
    out("  Les deux modules ne decoupent donc pas le meme objet, et c est ce")
    out("  banc qui s ecarte du quintile - le choix a ete fait pour coller aux")
    out("  coupes de walkforward.direction().")
    out()
    out("  Cette occupation est la cause MECANIQUE du double artefact des deux")
    out("  portes d independance, qui echouent en sens opposes : une bande qui")
    out("  tient un tiers des jours est etalee sur tout l historique (donc le")
    out("  compte d episodes ne rejette plus personne) tout en contenant")
    out("  quelques series tres longues (donc la concentration rejette tout le")
    out("  monde). Les compteurs exacts sont en section 6.")
    for t in targets:
        out()
        out("--- cible %s%s ---"
            % (_tmark(t),
               ("   [%s]" % ALT_BASKET_CAVEAT) if t.startswith("alt") else ""))
        out("  %-16s %5s %4s %6s %8s %8s %8s %9s %9s %6s %5s %5s %11s %10s %9s %7s"
            % ("signal", "n", "ep.", "top3", "e30", "e60", "e90", "e90 tir",
               "e90 hors", "hit90", "mono", "signe", "WF (plis)", "decal.",
               "ecart", "melange"))
        out("  " + "-" * 150)
        allr = [(n, rows[(n, t)]) for n in signals_pct]
        allr.append(("CONTROLE niveau", control_rows[t]))
        for name, r in allr:
            e = [r["edges"].get(h) for h in HORIZONS]
            cells = ["%+8.1f" % x["edge"] if x else "       -" for x in e]
            e90 = r["edges"].get(DECISION_HORIZON)
            mono = r["mono"].get(DECISION_HORIZON)
            wfr = r["wf"]
            # The fold count travels with the rate, always. A bare "100%" over
            # two folds reads as certainty and is worth nothing.
            wf_txt = ("%.0f%% (%d/%d)" % (wfr["rate"], wfr["agree"], wfr["folds"])
                      if wfr["rate"] is not None else "- (0 pli)")
            excl = (("%+9.1f" % e90["edge_excl"])
                    if e90 and e90["edge_excl"] is not None else "        -")
            fwin = (("%+9.1f" % e90["edge_firewin"])
                    if e90 and e90["edge_firewin"] is not None else "        -")
            # The `~` says the gap sits within two Monte-Carlo standard errors
            # of the bar, i.e. the seed decides this pair's verdict.
            gap_txt = ("-" if wfr["gap"] is None
                       else "%+.0f%s" % (wfr["gap"],
                                         "~" if wfr["undecided"] else ""))
            null_txt = ("-" if wfr["null"] is None
                        else "%.0f+-%.0f%%" % (wfr["null"],
                                               2 * (wfr["se"] or 0.0)))
            out("  %-16s %5d %4d %5.0f%% %s %s %s %s %s %8s %6s %5s %11s %10s %9s %6s"
                % (name, r["fire_n"], r["episodes"], r["top3_share"],
                   cells[0], cells[1], cells[2], fwin, excl,
                   "%.0f%%" % e90["hit"] if e90 else "-",
                   "%d/%d" % (mono["aligned"], mono["pairs"]) if mono else "-",
                   _sign_mark(r["sign"][DECISION_HORIZON]),
                   wf_txt, null_txt, gap_txt,
                   "%.0f%%" % wfr["null_melange"]
                   if wfr["null_melange"] is not None else "-"))
        out("  ep. = episodes distincts (%d jours de calme les separent);"
            % fs.EPISODE_GAP)
        out("  top3 = part de la bande haute concentree dans ses 3 plus gros")
        out("  episodes; au-dela de %.0f%% l edge est un souvenir, pas une regle."
            % DOMINANCE_ALARM)
        out("  e90  = baseline sur TOUTE la fenetre percentile du couple.")
        out("  e90 tir = baseline restreinte a [premier tir, dernier tir], la")
        out("  convention reelle de forward_study.py. Les deux sont imprimees")
        out("  parce qu elles different jusqu a %.1f pts sur ce run et qu une"
            % max_conv_delta)
        out("  seule d entre elles annoncee comme 'heritee' serait fausse.")
        out("  e90 hors = meme edge contre les jours NON declenches de la")
        out("  fenetre : la dilution de la baseline par les jours de tir.")
        out("  WF = accord walk-forward AVEC son nombre de plis; moins de %d"
            % WF_MIN_FOLDS)
        out("  plis ne se lit pas. decal./ecart = null par decalage circulaire")
        out("  (le null de reference, coherent avec celui de l edge), sur %d"
            % WF_NULL_DRAWS)
        out("  tirages, imprime avec +-2 erreurs-types de Monte-Carlo; melange")
        out("  = le null de walkforward.py, pour comparaison. Un ecart suivi de")
        out("  '~' est a moins de 2 erreurs-types de la barre de %+.0f : ce"
            % WF_GAP_MIN)
        out("  couple-la est decide par la graine, pas par la mesure.")

    # --- 3. sign inversion -------------------------------------------------
    out()
    out()
    out("=== 3. LE SIGNE S INVERSE-T-IL ENTRE CIBLES ? ===")
    out()
    out("  C est la question qui a motive ce banc. Un signal dont le signe")
    out("  change de cible en cible ne peut pas etre cable une fois pour toutes.")
    out("  Les colonnes %s portent sur le panier alt SANS SOL/SUI/HYPE : une"
        % ALT_MARK)
    out("  inversion lue sur ces colonnes est une inversion contre CE panier.")
    out()
    out("  %-16s %10s %10s %10s   %s"
        % ("signal", *[_tmark(t) for t in targets], "lecture"))
    out("  " + "-" * 74)
    unstable_count = 0
    for name in signals_pct:
        signs = [rows[(name, t)]["sign"][DECISION_HORIZON] for t in targets]
        known = [s for s in signs if s is not None]
        flip = len(set(known)) > 1
        unstable_count += int(flip)
        out("  %-16s %10s %10s %10s   %s"
            % (name, *[_sign_mark(s) for s in signs],
               "SIGNE INSTABLE" if flip else "signe stable"))
    out()
    out("  %d signaux sur %d changent de signe selon la cible."
        % (unstable_count, len(signals_pct)))
    out("  Un signe stable n est PAS une preuve d edge : les trois cibles")
    out("  partagent une jambe, un signe constant peut n etre que ce partage.")

    # --- 4. multiplicity ---------------------------------------------------
    out()
    out()
    out("=== 4. COMPARAISONS MULTIPLES - ce que le hasard produit ici ===")
    out()
    out("  Ce banc contient %d signaux x %d cibles x %d horizons = %d"
        % (len(signals_pct), len(targets), len(HORIZONS), n_cells))
    out("  comparaisons, dont %d portent sur les cibles alt%s. Quelques-unes"
        % (2 * len(signals_pct) * len(HORIZONS), ALT_MARK))
    out("  paraitront excellentes sans raison. Plutot que de l affirmer, on le")
    out("  mesure : la serie du signal est decalee circulairement contre les")
    out("  cibles, %d fois, et toute la matrice est recalculee a chaque tirage."
        % NULL_DRAWS)
    out("  Le decalage detruit l alignement avec le futur mais CONSERVE l")
    out("  autocorrelation - un melange simple pretendrait que chaque jour est")
    out("  un tirage independant et flatterait le banc.")
    out()
    obs_pass = sum(1 for e in real_edges.values() if e >= MIN_EDGE_PTS)
    out("  cellules observees passant edge >= %.0f pts : %d / %d"
        % (MIN_EDGE_PTS, obs_pass, n_cells))
    out("  memes cellules sous decalage, SANS aucun signal dedans :")
    out("      mediane %s cellules, 95e centile %s cellules"
        % (null_count_med, null_count_p95))
    out()
    out("  Autrement dit le banc produit deja, a vide, autant de cellules")
    out("  d apparence excellente qu il n en observe reellement. Compter les")
    out("  cellules qui passent n apprend donc rien.")
    out()
    floor = 1.0 / (NULL_DRAWS + 1)
    raw_hits = sum(1 for p in raw_p.values() if p and p["p"] <= ALPHA)
    wy_hits = sum(1 for p in wy["adjusted"].values() if p <= ALPHA)
    mz_hits = sum(1 for p in mz["adjusted"].values() if p <= ALPHA)
    out("  cellules a p brut <= %.2f              : %d / %d"
        % (ALPHA, raw_hits, n_cells))
    out("  attendu par hasard a ce seuil          : %.1f cellules"
        % (ALPHA * n_cells))
    out("  survivantes, Westfall-Young min-p      : %d / %d" % (wy_hits, n_cells))
    out("  survivantes, variante max-z            : %d / %d" % (mz_hits, n_cells))
    out()
    out("  Tout p brut ici est un comptage sur %d tirages : sa resolution ne"
        % NULL_DRAWS)
    out("  descend pas sous %.4f, et chaque valeur est imprimee avec son" % floor)
    out("  intervalle de Monte-Carlo (+- 2 erreurs-types). Citer un p brut a")
    out("  trois decimales sans cet intervalle, c est citer le grain du tirage.")
    out()
    out("  Deux corrections, sur LES MEMES tirages :")
    out("  - Westfall-Young min-p (la methode standard sans distribution) :")
    out("    chaque tirage est classe dans le null de SA cellule, le minimum")
    out("    sur toute la matrice fait la statistique du tirage. C est le")
    out("    chiffre de reference.")
    if wy["critical_p"] is not None:
        out("    p brut critique : %.4f - en dessous, le minimum du banc ne bat"
            % wy["critical_p"])
        out("    la cellule qu une fois sur vingt.")
    if wy.get("floor") is not None:
        out("    plancher atteignable du p corrige : %.3f, avec %d cellules"
            % (wy["floor"], wy["cells"]))
        out("    scorables sur %d tirages. Il est bien sous le seuil de %.2f,"
            % (wy["draws"], ALPHA))
        out("    donc l absence de survivant n est pas un artefact du nombre")
        out("    de tirages - la procedure POUVAIT laisser passer une cellule.")
    out("  - variante max-z : chaque cellule ramenee a son propre ecart robuste,")
    out("    puis maximum sur le banc. Elle est PLUS DURE ici, parce que le null")
    out("    d une cellule mince a des queues epaisses : un seul tirage extreme")
    out("    fixe la barre des %d. Elle n est pas Westfall-Young et n en porte"
        % n_cells)
    out("    pas le nom.")
    if mz["critical_z"] is not None:
        out("    z critique : %.2f ; z maximum observe sous le null : %.2f"
            % (mz["critical_z"], max(mz["max_z"])))

    # --- minimum detectable effect ----------------------------------------
    best_key = max(real_edges, key=lambda k: real_edges[k]) if real_edges else None
    out()
    out("  --- effet minimum detectable (ce que ce banc NE PEUT PAS voir) ---")
    out()
    if best_key is not None:
        sc = mz["scales"].get(best_key)
        m_z = mde_maxz(sc, mz["critical_z"])
        m_p = mde_minp(nm["per_cell"].get(best_key, []), wy["critical_p"])
        out("  Cellule la mieux placee : %s / %s a %dj, edge observe %+.1f pts."
            % (best_key[0], _tmark(best_key[1]), best_key[2],
               real_edges[best_key]))
        if sc:
            out("  Son null a un ecart robuste de %.2f pts autour de %+.2f."
                % (sc["spread"], sc["centre"]))
        if m_p is not None:
            out("  Barre Westfall-Young (la porte du banc) : il lui faudrait")
            out("  %+.1f pts a %dj, contre %+.1f observes."
                % (m_p, DECISION_HORIZON, real_edges[best_key]))
        if m_z is not None:
            out("  Barre max-z (z critique %.2f, variante plus dure) : %+.1f pts."
                % (mz["critical_z"], m_z))
        out()
        if m_p is not None:
            out("  CE BANC NE PEUT RIEN DETECTER EN DESSOUS DE ~%.0f PTS A %dJ"
                % (m_p, DECISION_HORIZON))
            out("  SOUS WESTFALL-YOUNG, ~%.0f PTS SOUS LA VARIANTE MAX-Z."
                % (m_z if m_z is not None else float("nan")))
            out("  C est la limite honnete du run. Un effet reel de 4 ou 5 pts")
            out("  existerait sans que ce banc puisse le distinguer du bruit,")
            out("  et l absence de survivant ne dit rien contre lui.")
        mdes = [v for v in
                (mde_minp(nm["per_cell"].get(k, []), wy["critical_p"])
                 for k in real_edges) if v is not None]
        if mdes:
            out()
            out("  Sur les %d cellules du banc, cette barre Westfall-Young va"
                % len(mdes))
            out("  de %+.1f a %+.1f pts, mediane %+.1f pts. Une cellule mince"
                % (min(mdes), max(mdes), fs.median(mdes)))
            out("  paie donc bien plus cher qu une cellule epaisse.")
        out()
        out("  Et ces deux barres ne concernent que la porte de multiplicite.")
        out("  La batterie complete n a PAS d effet minimum detectable fini :")
        out("  la porte de concentration est echouee par les %d couples quelle"
            % (len(signals_pct) * len(targets)))
        out("  que soit la taille de l edge (section 6), donc aucun edge, si")
        out("  grand soit-il, ne suffirait a lui seul a faire passer un couple.")
    out()
    out("  Lecture : une cellule qui ne franchit pas ce seuil est")
    out("  indiscernable du bruit de ce banc - ce qui ne veut pas dire qu il")
    out("  n y a rien, seulement que ce banc-ci ne le verrait pas.")
    out("  Aucun gagnant n est designe sans avoir aussi passe le walk-forward.")

    # --- 5. verdicts -------------------------------------------------------
    out()
    out()
    out("=== 5. VERDICT PAR SIGNAL ===")
    out()
    out("  Portes exigees, toutes ensemble, a %dj :" % DECISION_HORIZON)
    out("    edge          >= %.0f pts contre la baseline de la meme fenetre"
        % MIN_EDGE_PTS)
    out("    episodes      >= %d episodes distincts" % MIN_EPISODES)
    out("    concentration <= %.0f%% de la bande haute dans ses 3 plus gros"
        % DOMINANCE_ALARM)
    out("    monotonie     >= %d/4 paires de bandes alignees"
        % round(MONO_MIN * 4))
    out("    walk-forward  >= %+.0f pts d ecart contre son propre null par"
        % WF_GAP_MIN)
    out("                  decalage, sur au moins %d plis" % WF_MIN_FOLDS)
    out("    multiplicite  p Westfall-Young <= %.2f" % ALPHA)
    out()
    verdicts, gate_fails, all_gates = {}, {}, {}
    for name in signals_pct:
        cells = {}
        out("  %s" % name)
        for t in targets:
            r = rows[(name, t)]
            key = (name, t, DECISION_HORIZON)
            g = gates(r, wy["adjusted"].get(key))
            all_gates[(name, t)] = g
            cells[t] = {"passes": all(g.values()),
                        "sign": r["sign"][DECISION_HORIZON]}
            failed = [k for k, v in g.items() if not v]
            for k in failed:
                gate_fails[k] = gate_fails.get(k, 0) + 1
            rp = raw_p.get(key)
            out("    %-10s %-7s p brut %-16s WY %-6s max-z %s"
                % (_tmark(t), "PASSE" if all(g.values()) else "echoue",
                   ("%.4f +-%.4f" % (rp["p"], 2 * rp["se"])) if rp else "-",
                   "%.3f" % wy["adjusted"][key] if key in wy["adjusted"] else "-",
                   "%.3f" % mz["adjusted"][key] if key in mz["adjusted"] else "-"))
            out("               echoue sur : %s"
                % (", ".join(failed) if failed else "aucune"))
        verdicts[name] = classify(cells)
    out()
    out("  %-16s %-34s %s" % ("signal", "verdict", "signe"))
    out("  " + "-" * 74)
    for name in signals_pct:
        v = verdicts[name]
        out("  %-16s %-34s %s"
            % (name, v["verdict"],
               "instable entre cibles" if v["sign_unstable"] else "stable"))
    out()
    out("  Le CONTROLE (niveau de la cible, retour a la moyenne) est juge")
    out("  sans la porte de multiplicite : il n a pas ete tire au sort avec")
    out("  les %d cellules, donc il n a pas de p corrige comparable." % n_cells)
    for t in targets:
        r = control_rows[t]
        g = gates(r, None)
        failed = [k for k, v in g.items() if not v and k != "multiplicite"]
        out("    CONTROLE %-10s %d episodes, %.0f%% dans les 3 plus gros, %s"
            % (_tmark(t), r["episodes"], r["top3_share"],
               "toutes portes ok hors multiplicite" if not failed
               else "echoue sur : " + ", ".join(failed)))

    # --- where the fold floor actually bites -------------------------------
    out()
    out("  Ou mord reellement le plancher de %d plis :" % WF_MIN_FOLDS)
    labelled = {("%s / %s" % (n, _tmark(t))): rows[(n, t)]
                for (n, t) in all_gates}
    labelled.update({("CONTROLE %s" % _tmark(t)): control_rows[t]
                     for t in targets})
    # "Too few folds" and "would otherwise have passed" are different claims,
    # and only the second one means the floor decided anything. Conflating them
    # credits the floor with rejections the gap bar had already made.
    decisive, thin, gap_fails, at_floor = [], [], [], []
    for lbl, r in labelled.items():
        w = r["wf"]
        would = w["gap"] is not None and w["gap"] >= WF_GAP_MIN
        if w["folds"] < WF_MIN_FOLDS:
            (decisive if would else thin).append((lbl, w["agree"], w["folds"],
                                                  w["gap"]))
        else:
            if w["folds"] == WF_MIN_FOLDS and would:
                at_floor.append(lbl)
            if not would:
                gap_fails.append(lbl)
    if decisive:
        out("  DECISIF (le couple aurait franchi l ecart sans le plancher) :")
        for lbl, a, f, g in sorted(decisive):
            out("    %-28s %d/%d pli(s), ecart %+.0f" % (lbl, a, f, g))
    else:
        out("  DECISIF : aucun couple.")
    out("  Plancher atteint mais sans effet (l ecart echouait de toute facon),")
    out("  %d couple(s) : %s"
        % (len(thin), ", ".join("%s (%d/%d)" % (l, a, f)
                                for l, a, f, _ in sorted(thin))))
    out("  Les %d autres echecs walk-forward sont des echecs d ECART contre"
        % len(gap_fails))
    out("  leur propre null, a %d plis ou plus." % WF_MIN_FOLDS)
    if at_floor:
        out("  A noter dans l autre sens : %s"
            % ", ".join("%s%s" % (l, "~" if labelled[l]["wf"]["undecided"]
                                  else "") for l in sorted(at_floor)))
        out("  franchi(ssen)t le plancher a exactement %d plis et PASSE(NT) la"
            % WF_MIN_FOLDS)
        out("  porte walk-forward. Leurs echecs sont ailleurs - dire que le")
        out("  plancher les elimine serait faux. Un '~' signale un ecart a")
        out("  moins de 2 erreurs-types de la barre : ce passage-la tient a la")
        out("  graine et ne doit pas etre lu comme un resultat.")

    # --- reconciliation with walkforward.py --------------------------------
    #
    # Printed because this module IMPORTS wf.direction and could therefore be
    # read as reproducing walkforward.py. It does not, and the established
    # 1-fold-in-9 result for F&G is not what this bench recomputes.
    out()
    out("  Reconciliation avec walkforward.py (les deux ne donnent PAS le")
    out("  meme compte de plis, et l import de wf.direction ne le garantit pas) :")
    for name in ("Fear & Greed", "dominance BTC"):
        if name not in signals_pct:
            continue
        raw = dict(next(s2 for n2, s2 in candidates if n2 == name))
        here = rows[(name, "eth_btc")]["wf"]
        c = reference_fold_comparison(
            here["agree"], here["folds"], raw,
            fwds_by_target["eth_btc"][DECISION_HORIZON])
        out("    %-14s / eth_btc : %d/%d ici, %d/%d par walkforward.walk"
            % (name, c["here_agree"], c["here_folds"],
               c["there_agree"], c["there_folds"]))
    out("    Cause : le percentile est calcule ici sur TOUTES les dates de la")
    out("    serie, et dans walkforward.walk sur les seules dates deja")
    out("    filtrees par le forward. Les jours utilisables different, donc")
    out("    les plis ne coupent pas au meme endroit. Le resultat etabli de")
    out("    walkforward.txt (F&G : 1 pli sur 9) n est pas recalcule ici ; il")
    out("    n est pas contredit non plus, c est un decoupage different.")
    out("    Note : walkforward.py mesure en plus sur analysis/ethbtc.json,")
    out("    pas sur rotations.json['eth_btc'] - seconde source d ecart.")

    # --- the two nulls, measured -------------------------------------------
    out()
    out("  Coherence des deux nulls (l incoherence a ete mesuree, pas plaidee) :")
    out("  le null de l edge est un DECALAGE circulaire, celui du walk-forward")
    out("  herite de walkforward.py est un MELANGE - dans un module dont l")
    out("  argument central est qu un melange flatte un banc. Les deux ont donc")
    out("  ete calcules pour chaque couple.")
    changed, verdict_moved = [], []
    for lbl, r in labelled.items():
        w = r["wf"]
        a = (w["folds"] >= WF_MIN_FOLDS and w["gap_decalage"] is not None
             and w["gap_decalage"] >= WF_GAP_MIN)
        b = (w["folds"] >= WF_MIN_FOLDS and w["gap_melange"] is not None
             and w["gap_melange"] >= WF_GAP_MIN)
        if a != b:
            changed.append(lbl)
    # The gate flipping on a pair is not the same as the PAIR flipping: a pair
    # failing four other gates is unmoved whatever its walk-forward says. Only
    # the second one could change what this report concludes.
    for (n, t), g in all_gates.items():
        others = all(v for k2, v in g.items() if k2 != "walkforward")
        if others and "%s / %s" % (n, _tmark(t)) in changed:
            verdict_moved.append("%s / %s" % (n, _tmark(t)))
    out("    porte walk-forward identique sous les deux nulls : %d / %d couples"
        % (len(labelled) - len(changed), len(labelled)))
    if changed:
        out("    la porte diverge sur : %s" % ", ".join(sorted(changed)))
    # A divergence on a pair whose gap is inside the Monte-Carlo error is not
    # a disagreement between the two nulls; it is the seed talking. Naming it
    # as evidence about the nulls would be the seed-dependent claim this
    # module was rebuilt to stop making.
    undecided = sorted(l for l, r in labelled.items() if r["wf"]["undecided"])
    if undecided:
        out("    dont indecidables (ecart a moins de 2 erreurs-types de la")
        out("    barre %+.0f, donc tranches par la graine et non par la" % WF_GAP_MIN)
        out("    mesure) : %s" % ", ".join(undecided))
    else:
        out("    aucun couple n a d ecart a moins de 2 erreurs-types de la")
        out("    barre : sur %d tirages, cette porte ne depend plus de la graine."
            % WF_NULL_DRAWS)
    out("    couples dont le VERDICT change (toutes les autres portes etant")
    out("    franchies) : %d. L incoherence est reelle, elle a ete mesuree,"
        % len(verdict_moved))
    out("    et elle ne deplace aucune conclusion de ce run. Le decalage reste")
    out("    le null de reference : c est celui qui conserve l autocorrelation.")

    # --- 6. the answer -----------------------------------------------------
    specific = [n for n, v in verdicts.items() if v["verdict"].startswith("SPECIFIQUE")]
    general = [n for n, v in verdicts.items() if v["verdict"].startswith("GENERALISTE")]
    useless = [n for n, v in verdicts.items() if v["verdict"] == "INUTILE"]

    out()
    out()
    out("=== 6. REPONSE : existe-t-il des signaux specifiques a une rotation ? ===")
    out()
    out("  Rappel : deux des trois cibles reposent sur le panier alt%s -"
        % ALT_MARK)
    out("  %s. Tout ce qui suit sur" % ALT_BASKET_CAVEAT)
    out("  alt_eth%s / alt_btc%s porte sur ce panier, pas sur le marche alt."
        % (ALT_MARK, ALT_MARK))
    out()
    if specific:
        out("  Specifiques a une cible : %s" % ", ".join(specific))
    if general:
        out("  Generalistes            : %s" % ", ".join(general))
    out("  Inutiles sur les trois   : %s"
        % (", ".join(useless) if useless else "aucun"))
    out()
    n_pairs = len(signals_pct) * len(targets)

    if not specific and not general:
        out("  Reponse : NON. Aucun des %d couples (signal, cible) ne franchit"
            % n_pairs)
        out("  les six portes.")
        out()
        out("  Ou ils tombent, sur %d couples :" % n_pairs)
        for k, c in sorted(gate_fails.items(), key=lambda kv: -kv[1]):
            out("    %-14s echoue %d fois" % (k, c))
        out()
        out("  Les deux compteurs a lire ensemble : concentration echoue %d/%d"
            % (gate_fails.get("concentration", 0), n_pairs))
        out("  et episodes echoue %d/%d. Ce ne sont pas deux mesures"
            % (gate_fails.get("episodes", 0), n_pairs))
        out("  independantes qui concordent : c est la meme cause mecanique -")
        out("  une bande haute qui tient bien plus d un cinquieme des jours")
        out("  (section 2) est a la fois etalee sur tout l historique et")
        out("  composee de longues series. Les deux portes d independance sont")
        out("  devenues non informatives, en sens opposes.")
        out()
        # Drop-1 cannot inform: two gates each fail on every pair, so removing
        # one of the six can never produce a survivor. That is arithmetic, not
        # evidence, and printing it as reassurance was the previous version's
        # mistake. Drop-2 is the first question whose answer is not forced.
        d1 = drop_k_survivors(all_gates, 1)
        d2 = drop_k_survivors(all_gates, 2)
        blockers = [k for k, c in gate_fails.items() if c == n_pairs]
        out("  Le verdict repose-t-il sur une seule porte trop dure ?")
        out()
        out("  Retirer UNE porte ne peut rien apprendre ici : %s echouent"
            % " et ".join(sorted(blockers)))
        out("  chacune sur les %d couples, donc au moins une survit a toute" % n_pairs)
        out("  suppression unique et bloque tout. C est un theoreme sur les")
        out("  compteurs ci-dessus, pas une mesure - et de fait, drop-1 donne")
        out("  %d couple(s) partout." % max(c["n"] for c in d1))
        out()
        out("  La premiere question informative est donc drop-2 :")
        passing2 = [c for c in d2 if c["n"] > 0]
        for c in sorted(d2, key=lambda x: (-x["n"], x["dropped"])):
            if c["n"] == 0:
                continue
            out("    sans %-30s %d couple(s) : %s"
                % (" + ".join(c["dropped"]), c["n"],
                   ", ".join("%s / %s" % (a, _tmark(b))
                             for a, b in sorted(c["pairs"]))))
        if not passing2:
            out("    aucune paire de portes retiree ne produit de survivant.")
        else:
            out("    les %d autres combinaisons de deux portes : 0 couple."
                % (len(d2) - len(passing2)))
            out()
            out("  Autrement dit le verdict ne tient pas a une porte unique : il")
            out("  faut en retirer deux, et precisement les deux qui echouent")
            out("  partout, pour faire apparaitre un survivant.")
        out()
        best_wy = min(((k, p) for k, p in wy["adjusted"].items()),
                      key=lambda kv: kv[1], default=None)
        if best_wy:
            k, p = best_wy
            out("  Le couple le moins mauvais est %s / %s a %dj,"
                % (k[0], _tmark(k[1]), k[2]))
            if k[1].startswith("alt"):
                out("  cible construite sur le panier alt sans SOL/SUI/HYPE,")
            out("  a p Westfall-Young %.3f contre un seuil de %.2f."
                % (p, ALPHA))
            bar = mde_minp(nm["per_cell"].get(k, []), wy["critical_p"])
            out("  Cela ne signifie PAS que rien n en approche, et le dire")
            out("  serait faux : son edge observe est %+.1f pts et la barre de"
                % real_edges[k])
            if bar is not None:
                out("  detection de ce banc est %+.1f pts (section 4). Il en est"
                    % bar)
                out("  a %.0f%% du chemin, pas a l autre bout du monde. Ce qui"
                    % (100.0 * real_edges[k] / bar))
                out("  manque est de la puissance, pas seulement du signal.")
        best_raw = min(((k, v) for k, v in raw_p.items() if v),
                       key=lambda kv: kv[1]["p"], default=None)
        if best_raw:
            k, rp = best_raw
            out()
            out("  L illustration exacte du piege annonce : %s / %s affiche"
                % (k[0], _tmark(k[1])))
            out("  %+.1f pts a %dj et un p brut de %.4f +-%.4f (plancher de"
                % (real_edges[k], k[2], rp["p"], 2 * rp["se"]))
            out("  resolution %.4f sur %d tirages), ce qui se lirait comme une"
                % (rp["floor"], rp["draws"]))
            out("  decouverte. Corrige pour les %d comparaisons du banc, son p"
                % n_cells)
            out("  devient %.3f (Westfall-Young) et %.3f (variante max-z). C est"
                % (wy["adjusted"].get(k, float("nan")),
                   mz["adjusted"].get(k, float("nan"))))
            out("  la meme cellule, la meme mesure ; seul le nombre de fois ou")
            out("  l on a regarde a change.")
        out()
        out("  Ce qui EST etabli et reste utile :")
        out("  - le signe depend de la cible pour %d des %d signaux. Cabler un"
            % (unstable_count, len(signals_pct)))
        out("    signal sans dire pour quelle rotation est une erreur de type,")
        out("    pas une approximation.")
        out("  - la specificite reste la bonne hypothese a tester ; ce banc dit")
        out("    seulement qu aucun candidat actuel ne la realise A CE NIVEAU DE")
        out("    PUISSANCE, qui est faible.")
        out("  - la prochaine version utile de ce banc n est pas un signal de")
        out("    plus : c est une bande a effectif egal et un horizon unique")
        out("    choisi d avance, pour cesser de payer 54 comparaisons.")
    else:
        out("  ATTENTION : un couple passe les portes. Avant toute conclusion,")
        out("  relire sa ligne walk-forward en section 2 et son p en section 5.")
        out("  Sur %d comparaisons, %s cellules passent le seuil d edge par pur"
            % (n_cells, null_count_med))
        out("  hasard en mediane. Un couple isole n est pas une decouverte.")
    out()
    out("  Ce banc ne gouverne rien. Il ne modifie ni le gate 10 dimensions,")
    out("  ni le Pivot Ladder, ni aucune allocation.")

    text = out.text()
    sys.stdout.write(text)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
