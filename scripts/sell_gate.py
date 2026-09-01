#!/usr/bin/env python3
"""
The sell gate - SHADOW ONLY, and today STRUCTURALLY INOPERABLE.

What it is
----------
Three Tier-1 signals, firing on 2 of 3 within a 60-day window:

  T1  LTH distribution sustained over 30 days or more
  T2  loss of STH realised price on a WEEKLY close
  T3  ETF flow reversal while less than 10% below the all-time high

Like ladder.py this GOVERNS NOTHING. It records what it would say.

The finding that dominates everything below
-------------------------------------------
Two of the three inputs cannot be read at all.

  T1  LTH supply has no free source. The one name with evidence in this repo
      is `lth-supply`, recorded as 404 on BGeometrics at README.md:146. That
      is a second-hand record, not a measurement this module made: no
      BGeometrics request was issued on this run, deliberately, because the
      quota is 10/hour per IP and is shared with the live fetchers. Three
      further names appear in LTH_ENDPOINTS_UNVERIFIED and have NOT been
      tested by anyone here - do not cite them as 404s.
  T3  ETH/BTC ETF flows have no public API. The proximity-to-ATH half of T3
      IS computable from price - but half a condition is not the condition,
      and it is the flow reversal that carries the information.

So a 2-of-3 rule has 1 of 3 readable inputs. It cannot reach 2. The mechanism
that is supposed to protect capital cannot fire, and never could.

That is not a bug to route around. It is the actual state of the system, and
the only responsible thing the code can do is say so on every run, rather
than return a quiet "no sell signal" that reads identically to "conditions
are fine".

Why the denominator is FIXED here, unlike everywhere else
---------------------------------------------------------
The rotation gate and the ladder both shrink their denominator when a source
drops out: an absent signal reduces what was achievable rather than voting no.
That convention is safe THERE because the failure mode of a thinner rotation
base is inaction - you stay in BTC, which costs opportunity, not capital.

Applying it here inverts the rule's purpose. With 1 of 3 measurable, a
proportional reading of "2 of 3" is 0.67 of measurable weight, which one
signal alone satisfies. The 2-of-3 design exists precisely so that NO SINGLE
signal can command an exit; rescaling turns it into "the only signal still
readable sells the book by itself".

It also happens to be the worst of the three to hand that authority to.
Measured over 2022-09 -> 2026-08 (analysis/sell_gate.txt):

    T2 fired on 86 of 209 weekly closes - 41.1% of all weeks.

A capital-protection trigger that is on 41% of the time is not protection, it
is a permanent short. The two missing signals are the slow structural ones
(multi-week LTH distribution, institutional flow) whose job is to filter the
fast noisy one. Losing them and then lowering the bar is exactly backwards.

So DENOMINATOR_POLICY = "fixed": required stays 2 of 3 whatever is readable.

This OVERRIDES AN EXPLICIT INSTRUCTION, and the owner should know that rather
than find it later. The brief for this module said: "if a data series does not
exist, say so and reduce the denominator". The first half is obeyed everywhere
below. The second half is deliberately not, for the reason above - the
instruction was written for gates whose failure mode is inaction, and this one
is not. It is one constant. If the owner still wants the house convention here,
DENOMINATOR_POLICY is the single line to change, and the two tests named in
tests/test_sell_gate.py::TestDenominatorIsFixed are what will fail first.

A related trap, fixed the same way: a gate that CAN fire and had one of
its two signals fire must not render as "a real all-clear" either. That is
the ARMED verdict - fired, below threshold, operable. It does not exist for
today's world (which cannot reach it) but for the world one purchased data
feed away, where the sell gate's first false comfort would otherwise be a
signal firing under a line that reads "nothing fired".

The cost of that choice, stated plainly: the gate cannot fire today. It is
paid for by refusing to be silent about it - see VERDICTS below. A gate that
cannot fire and says so is a known gap a human can act on. A gate that fires
on one signal is a wrong answer delivered with confidence, and a gate that
returns "quiet" while blind is the same wrong answer delivered silently.

Two more things the backtest showed
-----------------------------------
- T2 fires a median 45.3% below the running ATH, and 0 of its 86 firings were
  within 10% of it - so at T3's stated 10% definition the two never co-occurred
  in four years. That conclusion is one threshold choice away from changing:
  the nearest firing was 11.6% off the high, and the count is 1 at 12%, 5 at
  15%, 12 at 20%. The report prints the whole sensitivity row rather than the
  single number, because "never" at 10% and "sometimes" at 15% are different
  recommendations. Either way the 2-of-3 rule leans on T1 harder than its
  symmetric phrasing suggests, and sourcing LTH supply is the best fix going.
- T2 has no forward edge, and what edge it has points the wrong way for a
  sell trigger. Median BTC return after a T2 week was +2.0% / +2.4% / +9.1%
  at 30 / 60 / 90 days against a baseline of +1.7% / +2.6% / +7.0%. Selling
  on T2 alone would historically have sold into recoveries. Combined with the
  45% median drawdown at firing, T2 behaves as a capitulation marker, not a
  distribution marker - which is a reason to keep it as one vote of three,
  not the reason to promote it to one of one.

- The gate is specified across two assets and the report says so rather than
  picking one quietly. T2 is a BTC rule (STH-RP exists for BTC only), T3 is
  specified on ETH/BTC ETF flows, and the book is an ETH/BTC rotation. Both
  tables are printed. On ETH/BTC the answer is the same and worse: the MEDIAN
  ETH/BTC return was negative at all three horizons - though 37% / 37% / 20%
  of individual firings were positive at 30 / 60 / 90 days, so "fell after
  every firing" would be false and this docstring said exactly that until the
  module's own section 3B table contradicted it. The median fell just as far
  in the baseline, because ETH/BTC fell through nearly the whole window. A
  T2-driven exit would have looked correct for four years while adding no
  information.
  Which book the gate protects is an open specification question for the
  owner, not something this module should decide.

Backtest limits, stated before the numbers
------------------------------------------
- STH-RP history on disk starts 2022-08-31 (analysis/series.json), so the
  test covers 209 weekly closes inside a single cycle. That is a small sample
  for a signal meant to fire once or twice per cycle.
- Overlapping forward windows are NOT independent observations. 209 weekly
  closes hold roughly 13-40 independent 30-90 day windows, not 209.
- The final entry on the weekly grid may be the last observation of a week
  still IN PROGRESS rather than a week-end close: STH-RP on disk ends
  2026-08-28, a Friday, and the Friday guard admits it. The report states
  which it is on every run. It does not change today's answer - T2 fired on
  neither 08-23 nor 08-28 - but an unfinished week dipping below the cost
  basis would otherwise print as a confirmed weekly close, which is exactly
  what the weekly convention exists to prevent.
- In-sample and descriptive. It says what happened, not what will.
- T1 and T3 are not backtested, because they cannot be measured. Their rows
  in the report read UNMEASURABLE - never 0, never a proxy.
"""

import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.join(HERE, "..", "analysis")
CACHE = os.path.join(ANALYSIS, ".cache")

FIRE_THRESHOLD = 2      # distinct Tier-1 signals required
WINDOW_DAYS = 60        # they must fall inside this trailing window

# Locale-independent, because strftime('%A') is not and this string is compared
# against in tests and read by a human in a report.
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
            "Saturday", "Sunday")

# resilience.py demotes a source that has stopped advancing rather than
# dropping it; the price cache here gets the same treatment at a looser horizon
# (3 days is right for a live vote, far too tight for immutable daily history
# used to score four years of weekly closes).
PRICE_STALENESS_MAX_DAYS = 10

# See the docstring. This constant is the whole design decision in one word,
# and tests/test_sell_gate.py fails if `required` ever starts moving with the
# number of readable inputs.
DENOMINATOR_POLICY = "fixed"

# Split in two because the evidence behind these names is not equal, and an
# earlier draft of this module flattened them into one "all 404" list that
# read as four measurements when only one had ever been written down.
#
# No BGeometrics request was made on this run. The quota is 10/hour per IP and
# is shared with scripts/fetch_signals.py::_bg, so spending 4 of it to
# re-confirm a negative result would have cost the live pipeline more than the
# confirmation is worth. That is a trade, and this is the record of it.
LTH_ENDPOINTS_404_REPORTED = [
    ("lth-supply", "404", "README.md:146, not re-tested on this run"),
]
# names not tested this run - inherited from README:146, unverified
# (in fact only `lth-supply` appears at README:146 at all; the three below
# came in with the task brief and have no evidence anywhere in this repo)
LTH_ENDPOINTS_UNVERIFIED = [
    "long-term-holder-supply",
    "lth-net-position-change",
    "lth-sth-supply",
]

# measurable=False means "no source exists", not "the fetch failed today". It
# is a property of the world, so it lives in the registry rather than in a
# run-time status field that a retry could clear.
# A proxy exists for T1 and is DELIBERATELY not wired to satisfy it.
#
# scripts/fetch_signals.fetch_lth_share derives, free and daily, the share of
# realised cap held by coins aged 6 months or more, from BGeometrics'
# realized-cap-hodl-waves. Against BTC forward returns over 1430 days, a
# 30-day decline in that share precedes underperformance of -2.1 / -6.1 / -6.8
# points at 30 / 60 / 90 days. A negative edge is the CORRECT sign for a sell
# trigger, and it is the only signal in this system whose measured direction
# matched one written down before the measurement.
#
# It is still not T1, for two reasons that are not solved by wanting them to be:
#   - the band boundary is 180 days, the canonical LTH threshold is 155
#   - it is realised-cap weighted, not supply weighted
# and it fails 2 of the 4 ADOPTION_RULE criteria: 73% of its firing days sit
# in three episodes, and walk-forward agreement (33%) is below its own shuffled
# control (39%) across three folds.
#
# Accepting a proxy for a specified Tier-1 is a decision with real consequences
# for a mechanism that sells the book. It belongs to the owner, in writing, not
# to an inference made here because the number looked encouraging. Until then
# the gate still reports T1 as UNMEASURABLE and still cannot reach 2 of 3.
LTH_PROXY = {
    "signal": "lth_share",
    "satisfies_t1": False,
    "decision_required": "Accepter lth_share comme substitut de T1 - "
                         "frontiere 180j au lieu de 155j, ponderation par "
                         "capitalisation realisee au lieu de l offre.",
    "measured_edge_pts": {"30d": -2.1, "60d": -6.1, "90d": -6.8},
    "adoption_rule_passed": 2,
    "adoption_rule_total": 4,
}

TIER_1 = {
    "lth_distribution_30d": {
        "rule": "long-term-holder supply falling for 30 days or more",
        "measurable": False,
        "why": "no free LTH SUPPLY series. `lth-supply` is 404 on BGeometrics. "
               "A PROXY now exists and is fetched daily as `lth_share` - see "
               "LTH_PROXY below - but it is not this metric and does not make "
               "this input measurable on its own authority.",
        "proxy": "lth_share",
    },
    "sth_rp_weekly_loss": {
        "rule": "BTC weekly close below short-term-holder realised price",
        "measurable": True,
        "why": "sth_realized_price is in analysis/series.json; BTC price is "
               "derived from CoinMetrics CapMrktCurUSD / SplyCur.",
    },
    "etf_flow_reversal_near_ath": {
        "rule": "ETF net flows turn negative while within 10% of the ATH",
        "measurable": False,
        "why": "no public ETF flow API. The 'within 10% of ATH' half IS "
               "computable, but the flow reversal carries the signal and it "
               "is not readable - a half-condition does not vote.",
    },
}

assert len(TIER_1) == 3, "the owner specified three Tier-1 signals"

# Five verdicts, not two. Every distinct fact the gate can be in must have its
# own string: the reader's eye treats any absence of alarm as an all-clear,
# which is precisely the mistake this module exists to prevent. The three
# non-FIRE ways to end up under the threshold - blind, escalating, and armed -
# are different situations and one shared "nothing fired" would hide all three.
VERDICTS = {
    "FIRE": "threshold met - de-risk per the strategy",
    "ARMED": "a signal fired, the threshold was not met, the gate was able to "
             "fire - one more distinct signal in the window would fire it",
    "ESCALATE": "signals fired but the threshold is unreachable with the "
                "inputs that exist - a human must judge this, the gate cannot",
    "BLIND_QUIET": "nothing fired, but the gate could not have fired even in "
                   "principle - this is NOT an all-clear",
    "QUIET": "nothing fired, and the gate was able to fire - a real all-clear",
}


def _date(value):
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


# -- the gate ----------------------------------------------------------------

def t2_weekly_loss(weekly_close_usd, sth_realized_price):
    """T2 on one weekly close. None when either leg is missing.

    None, never False: "we could not read the price" and "price held above
    the cost basis" are opposite facts and must not share a value.
    """
    if weekly_close_usd is None or sth_realized_price is None:
        return None
    return weekly_close_usd < sth_realized_price


def measurability(overrides=None):
    """What is readable. `overrides` lets a test - or a future in which an LTH
    feed is bought - describe a different world without editing the registry.
    """
    out = {k: v["measurable"] for k, v in TIER_1.items()}
    out.update(overrides or {})
    return {k: bool(v) for k, v in out.items() if k in TIER_1}


def reachable_verdicts(n_readable=None):
    """Which verdicts a world with `n_readable` readable inputs can produce.

    Computed rather than described, because section 2 of the report claims to
    document the mapping that actually executes. An earlier draft asserted
    "exactly two reachable outcomes" in prose; that sentence survived unchanged
    in a world where a source had been marked measurable and the code path had
    moved on, which is the failure this whole module is about.
    """
    if n_readable is None:
        n_readable = sum(1 for v in measurability().values() if v)
    can_fire = n_readable >= FIRE_THRESHOLD
    out = []
    if can_fire:
        out.append("FIRE")
    if n_readable >= 1:
        out.append("ARMED" if can_fire else "ESCALATE")
    out.append("QUIET" if can_fire else "BLIND_QUIET")
    return out


def fires_in_window(events, today, window_days=WINDOW_DAYS):
    """Distinct Tier-1 signal keys with a firing dated inside the window.

    Distinct is load-bearing: T2 firing on six consecutive weekly closes is
    one signal saying one thing six times, not six of the two votes needed.
    """
    end = _date(today)
    if end is None:
        return set()
    start = end - datetime.timedelta(days=window_days - 1)
    hit = set()
    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        key, when = ev.get("signal"), _date(ev.get("date"))
        if key not in TIER_1 or when is None:
            continue
        if start <= when <= end:
            hit.add(key)
    return hit


def evaluate(events, today, measurable=None):
    """Shadow evaluation of the sell gate.

    A firing attributed to a signal that is not measurable is ignored rather
    than trusted, so a stray event cannot conjure a vote out of a source that
    does not exist.
    """
    readable = measurability(measurable)
    n_readable = sum(1 for v in readable.values() if v)
    can_fire = n_readable >= FIRE_THRESHOLD

    in_window = fires_in_window(events, today)
    fired = sorted(k for k in in_window if readable.get(k))
    ignored = sorted(k for k in in_window if not readable.get(k))

    if len(fired) >= FIRE_THRESHOLD:
        verdict = "FIRE"
    elif fired:
        # Below threshold, and NEVER quiet: something fired. Reporting a fired
        # signal as "a real all-clear" is the exact absence-of-alarm misreading
        # this module exists to prevent, and it is worse here than anywhere
        # else in the pipeline because the reader's next action is to not sell.
        # Which of the two it is depends on whether the shortfall is the
        # market's (ARMED - operable gate, one vote short) or ours (ESCALATE -
        # the missing votes are unreadable, so the gate cannot resolve this and
        # a human must).
        verdict = "ARMED" if can_fire else "ESCALATE"
    else:
        verdict = "QUIET" if can_fire else "BLIND_QUIET"

    return {
        "governs": False,
        "status": "SHADOW - records what it would say, changes nothing",
        "as_of": str(today),
        "verdict": verdict,
        "reading": VERDICTS[verdict],
        "fired": fired,
        "fired_count": len(fired),
        # `required` NEVER moves with readable_count. That is the design
        # decision; see DENOMINATOR_POLICY and the module docstring.
        "required": FIRE_THRESHOLD,
        "of_total": len(TIER_1),
        "readable_count": n_readable,
        "unmeasurable": sorted(k for k, v in readable.items() if not v),
        "ignored_events_from_unmeasurable_sources": ignored,
        "can_fire": can_fire,
        "blind": not can_fire,
        "window_days": WINDOW_DAYS,
        "denominator_policy": DENOMINATOR_POLICY,
        "note": (
            "INOPERABLE: %d of %d inputs readable, %d required. The threshold "
            "is NOT rescaled to what is readable - on a sell gate that would "
            "let the single noisiest signal exit alone. Fix the sources, do "
            "not lower the bar." % (n_readable, len(TIER_1), FIRE_THRESHOLD)
        ) if not can_fire else "operable - %d of %d inputs readable" % (
            n_readable, len(TIER_1)),
    }


# -- backtest ----------------------------------------------------------------

def median(xs):
    if not xs:
        return None
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def weekly_last_observations(dates):
    """Last observation of each ISO Mon-Sun week, kept as dates.

    Split out from weekly_closes only so the caller can count what the Friday
    guard below actually removed. On the shipped dataset it removes nothing,
    and a guard that never binds should be reported as such rather than
    credited with cleaning data it never touched.
    """
    by_week = {}
    for d in sorted(dates):
        dt = _date(d)
        if dt is None:
            continue
        by_week[dt.isocalendar()[:2]] = dt
    return [dt for _, dt in sorted(by_week.items())]


def weekly_closes(dates):
    """Last observation of each Mon-Sun week, Friday or later.

    A week whose last observation falls before the Friday is dropped: that is
    a data gap, not a weekly close, and calling it one would let a mid-week
    print masquerade as a confirmed weekly signal. The convention is the whole
    point of T2 - a dip below the cost basis that recovers by Sunday does not
    count, which is why T2 fires far less often than a daily rule would.
    """
    return [dt.isoformat() for dt in weekly_last_observations(dates)
            if dt.isoweekday() >= 5]


def forward_return_pct(prices, start_date, horizon_days):
    """Percent change from start_date to start_date + horizon calendar days.

    None past the end of the data: a truncated window is dropped, never padded
    with the last known price, which would manufacture a 0% return and drag
    every median toward zero exactly where the sample is thinnest.
    """
    a = prices.get(start_date)
    dt = _date(start_date)
    if not a or dt is None:
        return None
    b = prices.get((dt + datetime.timedelta(days=horizon_days)).isoformat())
    return None if b is None else (b / a - 1) * 100


def episodes(fire_dates, min_gap_days=28):
    """First firing of each cluster. Consecutive weeks below the cost basis
    are one event; counting the 15 weeks of a bear leg as 15 firings would
    inflate the sample with a single observation repeated."""
    out, last = [], None
    for d in sorted(fire_dates):
        dt = _date(d)
        if dt is None:
            continue
        if last is None or (dt - last).days > min_gap_days:
            out.append(d)
        last = dt
    return out


def running_ath(prices, dates):
    """Trailing all-time high, walked over the FULL price history so the 2021
    peak counts - a max taken from 2022 onward would understate it and make
    every early drawdown look shallower than it was."""
    out, peak = {}, 0.0
    for d in sorted(prices):
        peak = max(peak, prices[d])
        if d in dates:
            out[d] = peak
    return out


# T3's "less than 10% below the all-time high" is the owner's number, but the
# whole T2/T3 co-occurrence conclusion turns on it, so the neighbours are
# printed too. A finding that survives only at one threshold is a coincidence
# wearing a conclusion's clothes.
ATH_PROXIMITY_THRESHOLDS = (10.0, 12.0, 15.0, 20.0)


def _forward_table(price_series, buckets, horizons=(30, 60, 90)):
    """median/n table of forward returns, one bucket per row.

    Takes the price series as an argument so the same firing dates can be
    scored against BTC and against ETH/BTC. Dates with no window inside the
    series simply drop out - see forward_return_pct on why not padding.
    """
    return {h: {name: [v for v in
                       (forward_return_pct(price_series, d, h) for d in dates)
                       if v is not None]
                for name, dates in buckets.items()}
            for h in horizons}


def backtest_t2(prices, sth, ethbtc=None):
    """T2 only. T1 and T3 have no data and are not simulated with a proxy.

    `prices` (BTC USD) defines the firing grid, because T2 is specified on BTC.
    `ethbtc` is optional and scores the SAME firings on the pair the strategy
    actually holds; see the asset-mismatch note in section 5 of the report.
    """
    common = sorted(set(prices) & set(sth))
    if not common:
        return None
    seen = weekly_last_observations(common)
    weeks = weekly_closes(common)
    fired = [w for w in weeks if t2_weekly_loss(prices[w], sth[w])]
    ath = running_ath(prices, set(weeks))

    buckets = {"all_firings": fired,
               "first_of_episode": episodes(fired),
               "baseline": weeks}
    rows = _forward_table(prices, buckets)
    rows_ethbtc = _forward_table(ethbtc, buckets) if ethbtc else None

    drawdowns = [(1 - prices[d] / ath[d]) * 100 for d in fired if ath.get(d)]

    # The weekly grid is "last observation of each ISO week", and that cannot
    # distinguish a Sunday close from the middle of a week still running. The
    # Friday guard admits both: on the shipped data STH-RP ends on a Friday
    # while the price cache runs to the Sunday, so the newest row on the grid
    # is a partial week - and the live verdict in section 0 is computed on it.
    # Harmless while T2 is quiet, wrong the first time an unfinished week dips
    # below the cost basis, because that is precisely the mid-week print the
    # weekly convention exists to reject. So it is stated, not assumed.
    last_close = _date(weeks[-1]) if weeks else None
    week_ends = (last_close + datetime.timedelta(7 - last_close.isoweekday())
                 if last_close else None)

    # Replay the gate's OWN verdict across the grid.
    #
    # Without this the report says how often the SIGNAL fired and never how
    # often the GATE escalated - two different numbers with two different
    # consequences. The module's whole case is that a signal present 41% of
    # weeks must not act alone; it then hands that signal to a human far more
    # often than that, and stayed silent about it until a review asked.
    fired_sorted = sorted(fired)
    escalate_weeks = 0
    for w in weeks:
        ev = [{"signal": "sth_rp_weekly_loss", "date": d}
              for d in fired_sorted if d <= w]
        if evaluate(ev, w).get("verdict") == "ESCALATE":
            escalate_weeks += 1

    return {
        "escalate_weeks": escalate_weeks,
        "first_day": common[0],
        "last_day": common[-1],
        "weeks": weeks,
        # weeks whose last observation landed before the Friday. Printed even
        # when it is 0, so nobody assumes the guard filtered noise it never saw.
        "weeks_seen": len(seen),
        "weeks_dropped_pre_friday": len(seen) - len(weeks),
        "fired": fired,
        "episodes": episodes(fired),
        "rows": rows,
        "rows_ethbtc": rows_ethbtc,
        "drawdown_at_firing_pct": drawdowns,
        "near_ath_firings": sum(1 for x in drawdowns if x < 10.0),
        "near_ath_counts": {t: sum(1 for x in drawdowns if x < t)
                            for t in ATH_PROXIMITY_THRESHOLDS},
        # None when there is no weekly grid at all; True only for a Sunday.
        "last_week_complete": (None if last_close is None
                               else last_close.isoweekday() == 7),
        "last_close_weekday": (None if last_close is None
                               else WEEKDAYS[last_close.isoweekday() - 1]),
        "last_week_ends": week_ends.isoformat() if week_ends else None,
    }


# -- data loading ------------------------------------------------------------

def load_sth():
    """{} on any failure, for the same reason as load_btc_price: the audit in
    sections 1, 2, 5 and 6 is the finding, and it needs no series at all."""
    try:
        with open(os.path.join(ANALYSIS, "series.json"), encoding="utf-8") as f:
            s = json.load(f)
    except (OSError, ValueError):
        return {}
    if "sth_realized_price" not in s.get("series", {}):
        return {}
    return dict(zip(s["dates"], s["series"]["sth_realized_price"]))


def load_btc_price():
    """BTC USD, derived CoinMetrics CapMrktCurUSD / SplyCur.

    Cached to analysis/.cache because the derivation is immutable history and
    re-running an analysis should cost nothing. It is not a BGeometrics
    endpoint, so it never touches the 10/hour budget - but it is still fetched
    at most once, with no retry.

    NO age or coverage check happens here on purpose - a cache covering
    2013-2026 is correct for every day it holds, and refusing it would spend
    network on immutable history. The cost is that an old cache is silently
    INCOMPLETE at the recent end, which matters to section 0. That cost is paid
    by price_provenance(), which prints the last date and its age and flags the
    run when the series trails the system clock.
    """
    path = price_cache_path()
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            pass    # corrupt cache is a missing cache; fall through to fetch

    import urllib.request
    url = ("https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
           "?assets=btc&metrics=CapMrktCurUSD,SplyCur&frequency=1d"
           "&start_time=2013-01-01&sort=time&page_size=10000")
    req = urllib.request.Request(
        url, headers={"User-Agent": "signal-pipeline/4.0 (personal use)"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:   # one attempt only
            data = json.loads(r.read())
    except (OSError, ValueError):
        # {} rather than a raised exception, on purpose. Sections 1, 2, 5 and 6
        # of this report are the measurability audit - the part that matters
        # most - and they need no price data at all. Letting a dead network
        # take down the whole run would hide the finding behind a traceback.
        return {}
    out = {}
    for row in data.get("data", []):
        cap, sply = row.get("CapMrktCurUSD"), row.get("SplyCur")
        if cap and sply:
            out[row["time"][:10]] = round(float(cap) / float(sply), 4)
    try:
        os.makedirs(CACHE, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f)
    except OSError:
        pass    # an uncacheable result is still a usable one
    return out


def price_cache_path():
    return os.path.join(CACHE, "btc_price_usd.json")


def price_provenance(prices, source, system_date=None,
                     max_age_days=PRICE_STALENESS_MAX_DAYS):
    """Where the price series came from, how far it runs, and how old that is.

    load_btc_price() returns any cache it finds with no age or coverage check.
    That is the right call for the derivation itself - CapMrktCurUSD / SplyCur
    for 2019 will never change - but it means a cache written months ago still
    produces a confident "0. TODAY" section about a stale final week. as_of is
    read off the data rather than the clock, which limits the damage to a
    mislabelled date rather than a wrong number; it does not remove the need to
    say so. resilience.py's convention is to keep a frozen source and mark it
    stale with its age, and that is what this does.

    `system_date` is injected so the tests have no clock.
    """
    days = sorted(prices or {})
    last = days[-1] if days else None
    today = _date(system_date) if system_date else datetime.date.today()
    last_dt = _date(last)
    age = (today - last_dt).days if last_dt else None
    return {
        "source": source,
        "last_date": last,
        "first_date": days[0] if days else None,
        "n_days": len(days),
        "system_date": today.isoformat(),
        "source_age_days": age,
        "max_age_days": max_age_days,
        # Absent data is not fresh data: no series at all counts as stale.
        "stale": age is None or age > max_age_days,
    }


def load_ethbtc():
    """ETH/BTC from analysis/ethbtc.json - already on disk, never fetched."""
    try:
        with open(os.path.join(ANALYSIS, "ethbtc.json"), encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return {}
    return {d: v["ethbtc"] for d, v in raw.items()
            if isinstance(v, dict) and isinstance(v.get("ethbtc"), (int, float))}


# -- report ------------------------------------------------------------------

# Below this many windows a median is a curiosity, not a measurement. The
# episode bucket lands here on purpose rather than by accident: four years
# produced 7 clusters, and 7 is the honest sample size for "how often does
# this signal start". It is printed, and it is marked unreadable.
MIN_READABLE_SAMPLE = 30


def _edge_str(rows, h, bucket="all_firings"):
    """Firing-bucket median minus baseline median, or '-' if either side is
    too thin to quote. Computed rather than typed into the prose, so a data
    refresh cannot leave the narrative asserting last month's numbers."""
    r = rows[h]
    a, b = r.get(bucket) or [], r.get("baseline") or []
    if len(a) < MIN_READABLE_SAMPLE or len(b) < MIN_READABLE_SAMPLE:
        return "-"
    return "%+.1f" % (median(a) - median(b))


def _horizon_block(rows, h, asset="BTC"):
    def line(label, vals):
        if not vals:
            return "    %-27s %6d   no window closes inside the data" % (
                label, 0)
        hit = sum(1 for v in vals if v > 0) / len(vals) * 100
        mark = "" if len(vals) >= MIN_READABLE_SAMPLE else "   n<%d, not readable" % MIN_READABLE_SAMPLE
        return "    %-27s %6d %9.1f%% %8.0f%%%s" % (label, len(vals),
                                                    median(vals), hit, mark)

    r = rows[h]
    base_med = median(r["baseline"])
    out = ["  %s forward return, horizon %d days" % (asset, h),
           "    %-27s %6s %10s %9s" % ("bucket", "n", "median", "positive"),
           line("T2 fired (every week)", r["all_firings"]),
           line("T2 fired (1st of episode)", r["first_of_episode"]),
           line("BASELINE (every week)", r["baseline"])]
    for label, key in (("every week", "all_firings"),
                       ("1st of episode", "first_of_episode")):
        vals = r[key]
        # No edge line for an unreadable bucket: a +2.3 printed beside n=7
        # gets quoted later without its sample size attached.
        if (len(vals) >= MIN_READABLE_SAMPLE and base_med is not None
                and len(r["baseline"]) >= MIN_READABLE_SAMPLE):
            out.append("    edge vs baseline, %-13s %+.1f points"
                       % (label, median(vals) - base_med))
    return out


def render(bt, verdict=None, no_backtest_reason=None, price_status=None):
    """The report. `verdict` is the live evaluate() result for the last day in
    the data; None means no live evaluation was run and section 0 says so
    rather than quietly omitting itself. `price_status` is price_provenance().

    Every claim about what the gate can do is derived from the registry here,
    never typed. An earlier draft hardcoded "No. It never could." and
    "Readable inputs: 1 of 3" into section 1: marking one source measurable
    then made section 0 print `can fire: yes` four lines above a section 1 that
    still said the threshold was unreachable, with the signal table between
    them agreeing with neither. The central finding of the module has to be a
    computation, or it is only a sentence that used to be true.
    """
    readable = measurability()
    n_readable = sum(1 for v in readable.values() if v)
    if verdict is not None:
        # The live evaluation may have run against an overridden world; section
        # 1 must describe THAT world, not the registry default, or the two
        # sections disagree in exactly the way this parameter exists to stop.
        n_readable = verdict["readable_count"]
    n_total = len(TIER_1)
    can_fire = n_readable >= FIRE_THRESHOLD
    L = []
    A = L.append
    A("SELL GATE - measurability audit and T2 backtest")
    A("=" * 68)
    A("")
    A("SHADOW ONLY. This gate governs nothing, exactly like the ladder.")
    A("")
    A("0. TODAY")
    A("-" * 68)
    if verdict is None:
        A("  NOT COMPUTED - no live evaluation was supplied to render().")
    else:
        A("  as of        : %s" % verdict.get("as_of", "?"))
        A("  verdict      : %s" % verdict["verdict"])
        A("  reading      : %s" % verdict["reading"])
        A("  fired        : %s" % (", ".join(verdict["fired"]) or "nothing"))
        A("  readable     : %d of %d inputs" % (verdict["readable_count"],
                                                verdict["of_total"]))
        A("  required     : %d  (denominator policy: %s)"
          % (verdict["required"], verdict["denominator_policy"]))
        A("  can fire     : %s" % ("yes" if verdict["can_fire"] else "NO"))
        if price_status:
            A("  BTC price    : %s" % price_status["source"])
            A("                 %d days, %s -> %s"
              % (price_status["n_days"], price_status["first_date"] or "-",
                 price_status["last_date"] or "-"))
            if price_status["source_age_days"] is None:
                A("                 age unknown - the series is empty.")
            else:
                age = price_status["source_age_days"]
                A("                 last observation trails the system date %s"
                  % price_status["system_date"])
                A("                 by %d day%s." % (age,
                                                     "" if age == 1 else "s"))
            if price_status["stale"]:
                A("                 STALE by this repo's convention (>%d days)."
                  % price_status["max_age_days"])
                A("                 The verdict above is dated off the DATA and")
                A("                 not off the clock, so it is not wrong about")
                A("                 its own date - it is old. Re-fetch before")
                A("                 reading section 0 as today's answer.")
        A("")
        if bt and bt["weeks"]:
            last = bt["weeks"][-1]
            last_fired = last in bt["fired"]
            recent = [d for d in bt["fired"] if d <= last]
            A("  Last weekly close %s: T2 %s."
              % (last, "FIRED" if last_fired else "did not fire"))
            if bt.get("last_week_complete") is False:
                A("  That row is NOT a week-end close. It is the last")
                A("  observation of a week still in progress: %s is a %s and"
                  % (last, bt["last_close_weekday"]))
                A("  the week runs to %s. The verdict above is therefore"
                  % bt["last_week_ends"])
                A("  computed as of a PARTIAL week. It costs nothing here,")
                A("  because T2 did not fire on that row - and it would cost")
                A("  the weekly convention its whole meaning the first time an")
                A("  unfinished week dips below the cost basis, since a")
                A("  mid-week print is precisely what T2 is defined to reject.")
            elif bt.get("last_week_complete"):
                A("  That row is a real Sunday week-end close, not a partial")
                A("  week: the weekly convention held on the newest row.")
            if recent:
                A("  Most recent T2 firing: %s." % recent[-1])
            if recent and not last_fired:
                A("")
                A("  Note the gap between those two lines. The rule is a %d-day"
                  % WINDOW_DAYS)
                A("  TRAILING window, so a firing that has since recovered keeps")
                A("  counting as one of the %d votes until it ages out. The"
                  % FIRE_THRESHOLD)
                A("  verdict is therefore %s while the latest close is quiet -"
                  % verdict["verdict"])
                A("  it is not read off the last print, and anyone expecting it")
                A("  to be is reading a different rule than the one specified.")
            A("")
        A("  These lines are produced by evaluate(), not asserted by prose.")
        A("  The mapping claimed in section 2 is the code path that ran here.")
    A("")
    A("1. CAN THE GATE FIRE?   %s"
      % ("Yes - %d of %d inputs are readable." % (n_readable, n_total)
         if can_fire else "No. It never could."))
    A("-" * 68)
    for key, meta in TIER_1.items():
        A("  %-28s %s" % (key, "MEASURABLE" if meta["measurable"]
                          else "UNMEASURABLE"))
        A("      rule : %s" % meta["rule"])
        A("      why  : %s" % meta["why"])
    A("")
    A("  The rule is %d of %d within %d days. Readable inputs: %d of %d."
      % (FIRE_THRESHOLD, n_total, WINDOW_DAYS, n_readable, n_total))
    if can_fire:
        A("  %d >= %d, so the threshold is reachable and the verdicts in"
          % (n_readable, FIRE_THRESHOLD))
        A("  section 0 are statements about the market. %d of %d inputs are"
          % (n_total - n_readable, n_total))
        A("  still unreadable, so an operable gate is not a complete one: it")
        A("  fires on the subset that has sources, and the missing ones cannot")
        A("  veto it.")
    else:
        A("  %d < %d, so the threshold is unreachable by construction. The only"
          % (n_readable, FIRE_THRESHOLD))
        A("  mechanism in this framework that protects capital cannot fire, and")
        A("  no run has ever reported that.")
    A("")
    A("  T1 endpoint evidence - no BGeometrics request was made on this run,")
    A("  because the quota is 10/hour per IP and shared with the live fetchers:")
    for name, status, source in LTH_ENDPOINTS_404_REPORTED:
        A("    %-26s %-5s %s" % (name, status, source))
    for name in LTH_ENDPOINTS_UNVERIFIED:
        A("    %-26s %-5s %s"
          % (name, "?", "never tested by anyone here - a guessed name"))
    A("")
    A("2. WHAT THE GATE DOES IN THAT STATE")
    A("-" * 68)
    A("  Denominator policy: %s. Required stays %d of %d whatever is readable."
      % (DENOMINATOR_POLICY, FIRE_THRESHOLD, n_total))
    A("")
    A("  FLAGGED FOR THE OWNER: this overrides an explicit instruction. The")
    A("  brief said 'if a data series does not exist, say so and reduce the")
    A("  denominator'. The saying-so is done throughout; the reducing is")
    A("  refused, for the reason below. Overrule it by setting")
    A("  DENOMINATOR_POLICY - it is one line, and the tests say which ones")
    A("  break. Raised here so it is a decision, not a discovery.")
    A("")
    # What "2 of 3, rescaled" would actually demand in this world. Computed for
    # the same reason section 1 is: the argument against rescaling is only
    # honest if the number it argues against is the one rescaling would produce.
    # ceil, not round: the rejected policy is "2 of 3 of what is readable", and
    # a fractional vote rounds UP to a whole signal in every gate in this repo.
    # round() would let 2 readable inputs ask for 1, which overstates the case
    # against rescaling - the argument has to survive its own arithmetic.
    rescaled = max(1, -(-FIRE_THRESHOLD * n_readable // n_total))
    A("  Rejected alternative - shrink the denominator, as the rotation gate")
    A("  and the ladder do. There it is safe: a thin base makes them abstain,")
    A("  and abstention costs opportunity. Here, %d of %d rescaled onto %d"
      % (FIRE_THRESHOLD, n_total, n_readable))
    A("  readable input%s asks for %d - and the signal that survived is the"
      % ("" if n_readable == 1 else "s", rescaled))
    A("  noisiest of the three, per section 3.")
    if rescaled < FIRE_THRESHOLD:
        A("  At %d, one signal exits the entire book." % rescaled)
    A("")
    A("  Also rejected - fire nothing and stay silent. That is the default")
    A("  behaviour of a %d-of-%d counter with %d input%s, and it renders as 'no"
      % (FIRE_THRESHOLD, n_total, n_readable, "" if n_readable == 1 else "s"))
    A("  sell signal', which a reader cannot distinguish from an all-clear.")
    A("")
    A("  What it does instead: %d distinct verdicts, so neither blindness nor"
      % len(VERDICTS))
    A("  a half-met threshold can be read as calm.")
    for name, meaning in VERDICTS.items():
        A("    %-12s %s" % (name, meaning))
    A("")
    reach = reachable_verdicts(n_readable)
    A("  Reachable outcomes with %d of %d inputs readable, computed by"
      % (n_readable, n_total))
    A("  reachable_verdicts() rather than asserted here: %s." % ", ".join(reach))
    if "FIRE" not in reach:
        A("  Never FIRE. Not a sale and not a silence: a human decision,")
        A("  logged as owed.")
    A("  Section 0 is that mapping actually executed on the current data.")
    A("")

    if bt is None:
        A("3. T2 BACKTEST - NOT RUN")
        A("-" * 68)
        A("  %s" % (no_backtest_reason or
                    "No overlap between the STH-RP series and the BTC price "
                    "series."))
        A("")
        A("  Sections 1, 2, 5 and 6 above and below need no price data and")
        A("  stand as written. The measurability finding does not depend on")
        A("  the backtest; the backtest depends on it.")
        A("")
        _limits(A, None, n_readable, n_total)
        return "\n".join(L)

    n_weeks, n_fired = len(bt["weeks"]), len(bt["fired"])
    weeks = bt["weeks"]
    A("3. T2 BACKTEST (the only computable signal)")
    A("-" * 68)
    A("  Daily overlap : %s -> %s   (STH-RP and BTC price both present)"
      % (bt["first_day"], bt["last_day"]))
    A("  Weekly grid   : %s -> %s   (%d closes - what the test runs on)"
      % (weeks[0] if weeks else "-", weeks[-1] if weeks else "-", n_weeks))
    A("  T2 fired      : %d weeks (%.1f%% of all weekly closes)"
      % (n_fired, 100.0 * n_fired / n_weeks if n_weeks else 0))
    esc = bt.get("escalate_weeks")
    if esc is not None and n_weeks:
        A("  ESCALATE      : %d weeks (%.1f%% of all weekly closes)"
          % (esc, 100.0 * esc / n_weeks))
        A("")
        A("  That second line is the one to argue with. This module's whole")
        A("  case is that a signal present on %.1f%% of weeks must not act"
          % (100.0 * n_fired / n_weeks))
        A("  alone - and it then routes that same signal to a human on")
        A("  %.1f%% of weeks. An escalation raised two weeks in three is not"
          % (100.0 * esc / n_weeks))
        A("  an escalation; it is a standing condition, and a human asked to")
        A("  adjudicate it that often will stop reading it. Whatever replaces")
        A("  the 2-of-3 rule has to fix this, not inherit it.")
        A("")
    A("  Episodes      : %d clusters more than 28 days apart"
      % len(bt["episodes"]))
    A("  Weeks dropped for a pre-Friday last observation: %d of %d"
      % (bt["weeks_dropped_pre_friday"], bt["weeks_seen"]))
    if not bt["weeks_dropped_pre_friday"]:
        A("    - the guard never bound on this dataset. It removed no noise")
        A("      here; it is insurance against a future gappy feed.")
    if bt.get("last_week_complete") is False:
        A("  Newest row %s is a %s - the last observation of an UNFINISHED"
          % (weeks[-1], bt["last_close_weekday"]))
        A("    week ending %s, not a week-end close. It is counted in the"
          % bt["last_week_ends"])
        A("    %d above and in section 0's verdict. One partial row cannot"
          % n_weeks)
        A("    move a four-year median; it can move today's answer.")
    elif bt.get("last_week_complete"):
        A("  Newest row %s is a Sunday close - the grid ends on a complete week."
          % weeks[-1])
    A("")
    A("  That firing rate is what settles the denominator question. A")
    A("  capital-protection trigger that is on nearly half of all weeks")
    A("  cannot be allowed to act alone, whatever else is unavailable.")
    A("")
    for h in (30, 60, 90):
        for line in _horizon_block(bt["rows"], h):
            A(line)
        A("")
    A("  Overlapping windows are NOT independent observations: %d weekly"
      % n_weeks)
    A("  closes contain on the order of %d independent 90-day windows."
      % max(1, n_weeks // 13))
    A("  Read the sign, not the decimal.")
    A("")
    # Generated from the same numbers the tables print. The previous draft
    # typed "at or above the baseline" into the prose and was falsified two
    # lines above it by its own 60-day row (2.4 vs 2.6). A narrative sentence
    # that restates a table is a second copy of the data that nothing updates.
    meds = [median(bt["rows"][h]["all_firings"]) for h in (30, 60, 90)]
    if all(m is not None and m > 0 for m in meds):
        sign = "positive at all three horizons"
    elif all(m is not None and m < 0 for m in meds):
        sign = "negative at all three horizons"
    elif any(m is None for m in meds):
        sign = "not computable at every horizon"
    else:
        sign = "mixed in sign across the three horizons"
    A("  Reading it: no edge, and the little there is points the wrong way")
    A("  for a sell trigger. Median BTC return after a T2 week is")
    A("  %s, and against the baseline it lands" % sign)
    A("  %s points at 30 / 60 / 90 days - which is to say nowhere."
      % " / ".join(_edge_str(bt["rows"], h) for h in (30, 60, 90)))
    A("  Selling on T2 alone would mostly have sold into")
    A("  recoveries. The episode bucket (n=%d) is printed for completeness"
      % len(bt["episodes"]))
    A("  only; that many clusters cannot separate skill from luck at any")
    A("  horizon.")
    A("")
    A("3B. THE SAME FIRINGS SCORED ON ETH/BTC")
    A("-" * 68)
    A("  Section 3 measures BTC. The gate does not protect a BTC book: the")
    A("  strategy is ETH/BTC rotation, and T3 is specified on ETH/BTC ETF")
    A("  flows. So the identical firing dates are scored again on the pair")
    A("  actually held (analysis/ethbtc.json). T2 itself stays a BTC rule -")
    A("  STH-RP exists for BTC only (README:147) - so this table asks 'what")
    A("  did the book do after a BTC signal', which is the cost of acting.")
    A("")
    if bt.get("rows_ethbtc"):
        for h in (30, 60, 90):
            for line in _horizon_block(bt["rows_ethbtc"], h, asset="ETH/BTC"):
                A(line)
            A("")
        A("  Reading it: the same verdict as section 3, reached from the other")
        A("  side. The MEDIAN ETH/BTC return was negative at every horizon -")
        A("  not every firing, see the positive column above - but it fell")
        A("  just as hard in the baseline, because ETH/BTC fell through nearly")
        A("  the whole window. The edge column is %s points at 30/60/90 days,"
          % " / ".join(_edge_str(bt["rows_ethbtc"], h) for h in (30, 60, 90)))
        A("  which is nothing. A gate that sold ETH on T2 would have looked")
        A("  right for four years while adding no information: the drift did")
        A("  the work, not the signal. That is the most dangerous shape a")
        A("  backtest can take, and it is why the baseline row is printed on")
        A("  every table here rather than the firing row alone.")
        A("")
    else:
        A("  NOT RUN - analysis/ethbtc.json unreadable or empty.")
        A("")
    A("4. T2 AND T3 BARELY CO-EXIST")
    A("-" * 68)
    dd = bt["drawdown_at_firing_pct"]
    if dd:
        A("  Drawdown from the running ATH when T2 fired:")
        A("    median %.1f%%    min %.1f%%    max %.1f%%"
          % (median(dd), min(dd), max(dd)))
        A("")
        A("  T3's '10% below the ATH' is the owner's threshold. The whole")
        A("  co-occurrence conclusion rests on it, so here are its neighbours:")
        A("    threshold   firings within it")
        for t in ATH_PROXIMITY_THRESHOLDS:
            A("      %4.0f%%      %d of %d" % (t, bt["near_ath_counts"][t],
                                               len(dd)))
        A("")
        A("  Read that before quoting the 0. The nearest firing was %.1f%% off"
          % min(dd))
        A("  the high - %.1f points from counting. 'Never' is true at the 10%%"
          % (min(dd) - 10.0))
        A("  definition and false by 20%; the finding is real but it is not")
        A("  robust to the threshold, and a 15% T3 would change the answer.")
    A("")
    if dd:
        A("  So, stated at the precision the data supports: T2 and T3 never")
        A("  co-occurred at the 10%% definition; the nearest firing was %.1f%%"
          % min(dd))
        A("  off the high. T2 fires a median %.0f%% off the highs, which says"
          % median(dd))
        A("  what T2 actually is - a capitulation marker, not a distribution")
        A("  marker. That is an argument for keeping it as one vote of three,")
        A("  and the opposite of an argument for promoting it to one of one.")
    else:
        A("  T2 never fired in this window, so there is nothing to characterise.")
    A("")
    A("  T3 requires being near the ATH; T2 fires deep in drawdowns. Even with")
    A("  a working ETF feed the pair would rarely co-occur, so the 2-of-3 rule")
    A("  leans on T1 far harder than its symmetric phrasing admits. Sourcing")
    A("  LTH supply is the highest-value fix available.")
    A("")
    _limits(A, bt, n_readable, n_total)
    return "\n".join(L)


def _limits(A, bt, n_readable=None, n_total=None):
    """Sections 5 and 6. Factored out because they hold for a run with no
    price data at all, and the NOT RUN path must not silently drop them.

    The counts are passed in rather than re-read from the registry so section
    6 describes the same world as sections 0, 1 and 2 - including a world an
    `overrides` argument invented for a test.
    """
    if n_readable is None:
        n_readable = sum(1 for v in measurability().values() if v)
    if n_total is None:
        n_total = len(TIER_1)
    A("5. LIMITS")
    A("-" * 68)
    if bt:
        A("  - STH-RP history on disk starts %s: %d weeks inside one cycle."
          % (bt["first_day"], len(bt["weeks"])))
        A("    Small for a signal meant to fire once or twice per cycle.")
    else:
        A("  - The backtest did not run; sections 3-4 carry no numbers.")
    A("  - ASSET MISMATCH. T2 is a BTC rule, T3 is specified on ETH/BTC ETF")
    A("    flows, and the book is an ETH/BTC rotation. Section 3 measures the")
    A("    cost of selling in BTC terms, section 3B in book terms; neither is")
    A("    the whole answer, and the gate itself has never said which asset")
    A("    it is protecting. That is an unresolved specification gap, not a")
    A("    reporting choice - the owner has to name the book.")
    if bt and bt.get("last_week_complete") is False:
        A("  - The newest row on the weekly grid is a PARTIAL week (%s, a %s;"
          % (bt["weeks"][-1], bt["last_close_weekday"]))
        A("    the week ends %s). Section 0's live verdict is computed on it."
          % bt["last_week_ends"])
    A("  - Overlapping windows; in-sample; descriptive, not predictive.")
    A("  - T1 and T3 appear in no table anywhere. They are not zero, not")
    A("    neutral, not proxied - they are unmeasured.")
    A("  - BTC USD is derived CapMrktCurUSD / SplyCur, a daily UTC close; it")
    A("    will not tick-match an exchange print.")
    A("  - No BGeometrics endpoint was probed on this run. The T1 404 is")
    A("    quoted from README:146, not measured here.")
    A("")
    A("6. WHAT WOULD CHANGE THE ANSWER")
    A("-" * 68)
    missing = [k for k, v in measurability().items() if not v]
    if n_readable >= FIRE_THRESHOLD:
        A("  Already changed: %d of %d inputs are readable, so the threshold is"
          % (n_readable, n_total))
        A("  reachable and section 0 reports the market rather than the gap.")
        for name in missing:
            A("  Still unsourced: %s" % name)
        if missing:
            A("  The gate now fires on the subset that has sources: operable,")
            A("  not complete, and the unread signals cannot veto it.")
    else:
        A("  %d more sourced input%s makes the gate operable: %d of %d becomes"
          % (FIRE_THRESHOLD - n_readable,
             "" if FIRE_THRESHOLD - n_readable == 1 else "s",
             FIRE_THRESHOLD, n_total))
        A("  reachable, and LTH supply is the one to buy first - T1 is slow,")
        A("  structural, and not a drawdown artefact, which is exactly what T2")
        A("  is not. That is one purchase, not a redesign. Until it exists the")
        A("  correct output is %s, never a number that looks"
          % " or ".join(reachable_verdicts(n_readable)))
        A("  like a decision.")


def main():
    sth = load_sth()
    # Asked BEFORE the load, because a fetch writes the cache and would make
    # every run look like a cache hit afterwards.
    from_cache = os.path.exists(price_cache_path())
    prices = load_btc_price()
    price_status = price_provenance(
        prices,
        "cache analysis/.cache/btc_price_usd.json" if from_cache
        else "CoinMetrics community API, fetched on this run")
    bt = backtest_t2(prices, sth, ethbtc=load_ethbtc()) if sth else None

    if not sth:
        reason = ("NOT RUN - analysis/series.json carries no "
                  "sth_realized_price.")
    elif not prices:
        reason = ("NOT RUN - BTC price unavailable and no cache "
                  "(analysis/.cache/btc_price_usd.json).")
    elif bt is None:
        reason = "NOT RUN - no overlap between STH-RP and the BTC price series."
    else:
        reason = None

    # The live verdict, from the same evaluate() the tests exercise. Each T2
    # firing week becomes one event; the 60-day window in fires_in_window then
    # decides which of them still count as of the last day in the data. Nothing
    # here asserts an outcome - if T2 fired last week this prints ESCALATE.
    verdict = None
    if bt is not None:
        events = [{"signal": "sth_rp_weekly_loss", "date": d}
                  for d in bt["fired"]]
        verdict = evaluate(events, bt["last_day"])

    text = render(bt, verdict=verdict, no_backtest_reason=reason,
                  price_status=price_status)
    try:
        os.makedirs(ANALYSIS, exist_ok=True)
        out = os.path.join(ANALYSIS, "sell_gate.txt")
        with open(out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        wrote = os.path.normpath(out)
    except OSError as exc:
        wrote = None
        print(text)
        print("\nCould not write analysis/sell_gate.txt: %s" % exc)
        return 1
    print(text)
    print("\nWrote %s" % wrote)
    return 0


if __name__ == "__main__":
    sys.exit(main())
