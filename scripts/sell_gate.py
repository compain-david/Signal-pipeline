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

  T1  LTH supply has no free source. Four BGeometrics endpoint names were
      tried and all returned 404: lth-supply, long-term-holder-supply,
      lth-net-position-change, lth-sth-supply. Nothing free replaces them.
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

The cost of that choice, stated plainly: the gate cannot fire today. It is
paid for by refusing to be silent about it - see VERDICTS below. A gate that
cannot fire and says so is a known gap a human can act on. A gate that fires
on one signal is a wrong answer delivered with confidence, and a gate that
returns "quiet" while blind is the same wrong answer delivered silently.

Two more things the backtest showed
-----------------------------------
- T2 fires a median 45.3% below the running ATH, and 0 of its 86 firings were
  within 10% of it. T3 requires being within 10% of the ATH. So even with a
  working ETF feed, T2 and T3 never co-occurred once in four years: the
  2-of-3 rule leans on T1 far harder than its symmetric phrasing suggests.
  Sourcing LTH supply is the highest-value fix available.
- T2 has no forward edge, and what edge it has points the wrong way for a
  sell trigger. Median BTC return after a T2 week was +2.0% / +2.4% / +9.1%
  at 30 / 60 / 90 days against a baseline of +1.7% / +2.6% / +7.0%. Selling
  on T2 alone would historically have sold into recoveries. Combined with the
  45% median drawdown at firing, T2 behaves as a capitulation marker, not a
  distribution marker - which is a reason to keep it as one vote of three,
  not the reason to promote it to one of one.

Backtest limits, stated before the numbers
------------------------------------------
- STH-RP history on disk starts 2022-08-31 (analysis/series.json), so the
  test covers 209 weekly closes inside a single cycle. That is a small sample
  for a signal meant to fire once or twice per cycle.
- Overlapping forward windows are NOT independent observations. 209 weekly
  closes hold roughly 13-40 independent 30-90 day windows, not 209.
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

# See the docstring. This constant is the whole design decision in one word,
# and tests/test_sell_gate.py fails if `required` ever starts moving with the
# number of readable inputs.
DENOMINATOR_POLICY = "fixed"

# Endpoint names tried for T1 that returned 404. Kept in the module so the
# next person does not spend the BGeometrics hourly budget rediscovering it.
LTH_ENDPOINTS_TRIED_404 = [
    "lth-supply",
    "long-term-holder-supply",
    "lth-net-position-change",
    "lth-sth-supply",
]

# measurable=False means "no source exists", not "the fetch failed today". It
# is a property of the world, so it lives in the registry rather than in a
# run-time status field that a retry could clear.
TIER_1 = {
    "lth_distribution_30d": {
        "rule": "long-term-holder supply falling for 30 days or more",
        "measurable": False,
        "why": "no free LTH supply series; 4 BGeometrics endpoints 404 "
               "(see LTH_ENDPOINTS_TRIED_404). Glassnode/CryptoQuant are paid.",
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

# Four verdicts, not two. A blind gate and a quiet gate must never render as
# the same string: the reader's eye treats any absence of alarm as an
# all-clear, which is precisely the mistake this module exists to prevent.
VERDICTS = {
    "FIRE": "threshold met - de-risk per the strategy",
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
        # Below threshold. If the threshold was reachable this is an ordinary
        # quiet reading; if it was not, the shortfall is our blindness rather
        # than the market's calm, and that difference is escalated to a human
        # instead of being resolved by the gate in either direction.
        verdict = "QUIET" if can_fire else "ESCALATE"
    else:
        verdict = "QUIET" if can_fire else "BLIND_QUIET"

    return {
        "governs": False,
        "status": "SHADOW - records what it would say, changes nothing",
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


def weekly_closes(dates):
    """Last observation of each Mon-Sun week.

    A week whose last observation falls before the Friday is dropped: that is
    a data gap, not a weekly close, and calling it one would let a mid-week
    print masquerade as a confirmed weekly signal. The convention is the whole
    point of T2 - a dip below the cost basis that recovers by Sunday does not
    count, which is why T2 fires far less often than a daily rule would.
    """
    by_week = {}
    for d in sorted(dates):
        dt = _date(d)
        if dt is None:
            continue
        by_week[dt.isocalendar()[:2]] = dt
    return [dt.isoformat() for _, dt in sorted(by_week.items())
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


def backtest_t2(prices, sth):
    """T2 only. T1 and T3 have no data and are not simulated with a proxy."""
    common = sorted(set(prices) & set(sth))
    if not common:
        return None
    weeks = weekly_closes(common)
    fired = [w for w in weeks if t2_weekly_loss(prices[w], sth[w])]
    ath = running_ath(prices, set(weeks))

    rows = {}
    for h in (30, 60, 90):
        buckets = {"all_firings": fired,
                   "first_of_episode": episodes(fired),
                   "baseline": weeks}
        rows[h] = {name: [v for v in
                          (forward_return_pct(prices, d, h) for d in dates)
                          if v is not None]
                   for name, dates in buckets.items()}

    drawdowns = [(1 - prices[d] / ath[d]) * 100 for d in fired if ath.get(d)]
    return {
        "first_day": common[0],
        "last_day": common[-1],
        "weeks": weeks,
        "fired": fired,
        "episodes": episodes(fired),
        "rows": rows,
        "drawdown_at_firing_pct": drawdowns,
        "near_ath_firings": sum(1 for x in drawdowns if x < 10.0),
    }


# -- data loading ------------------------------------------------------------

def load_sth():
    with open(os.path.join(ANALYSIS, "series.json"), encoding="utf-8") as f:
        s = json.load(f)
    if "sth_realized_price" not in s.get("series", {}):
        return {}
    return dict(zip(s["dates"], s["series"]["sth_realized_price"]))


def load_btc_price():
    """BTC USD, derived CoinMetrics CapMrktCurUSD / SplyCur.

    Cached to analysis/.cache because the derivation is immutable history and
    re-running an analysis should cost nothing. It is not a BGeometrics
    endpoint, so it never touches the 10/hour budget - but it is still fetched
    at most once, with no retry.
    """
    path = os.path.join(CACHE, "btc_price_usd.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    import urllib.request
    url = ("https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
           "?assets=btc&metrics=CapMrktCurUSD,SplyCur&frequency=1d"
           "&start_time=2013-01-01&sort=time&page_size=10000")
    req = urllib.request.Request(
        url, headers={"User-Agent": "signal-pipeline/4.0 (personal use)"})
    with urllib.request.urlopen(req, timeout=60) as r:   # one attempt only
        data = json.loads(r.read())
    out = {}
    for row in data.get("data", []):
        cap, sply = row.get("CapMrktCurUSD"), row.get("SplyCur")
        if cap and sply:
            out[row["time"][:10]] = round(float(cap) / float(sply), 4)
    os.makedirs(CACHE, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f)
    return out


# -- report ------------------------------------------------------------------

# Below this many windows a median is a curiosity, not a measurement. The
# episode bucket lands here on purpose rather than by accident: four years
# produced 7 clusters, and 7 is the honest sample size for "how often does
# this signal start". It is printed, and it is marked unreadable.
MIN_READABLE_SAMPLE = 30


def _horizon_block(rows, h):
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
    out = ["  BTC forward return, horizon %d days" % h,
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


def render(bt):
    L = []
    A = L.append
    A("SELL GATE - measurability audit and T2 backtest")
    A("=" * 68)
    A("")
    A("SHADOW ONLY. This gate governs nothing, exactly like the ladder.")
    A("")
    A("1. CAN THE GATE FIRE?   No. It never could.")
    A("-" * 68)
    for key, meta in TIER_1.items():
        A("  %-28s %s" % (key, "MEASURABLE" if meta["measurable"]
                          else "UNMEASURABLE"))
        A("      rule : %s" % meta["rule"])
        A("      why  : %s" % meta["why"])
    A("")
    A("  The rule is 2 of 3 within %d days. Readable inputs: 1 of 3."
      % WINDOW_DAYS)
    A("  1 < 2, so the threshold is unreachable by construction. The only")
    A("  mechanism in this framework that protects capital cannot fire, and")
    A("  no run has ever reported that.")
    A("")
    A("  Endpoints tried for T1, all 404: %s"
      % ", ".join(LTH_ENDPOINTS_TRIED_404))
    A("")
    A("2. WHAT THE GATE DOES IN THAT STATE")
    A("-" * 68)
    A("  Denominator policy: %s. Required stays 2 of 3." % DENOMINATOR_POLICY)
    A("")
    A("  Rejected alternative - shrink the denominator, as the rotation gate")
    A("  and the ladder do. There it is safe: a thin base makes them abstain,")
    A("  and abstention costs opportunity. Here, 2 of 3 rescaled onto 1")
    A("  readable input means ONE signal exits the entire book - and the")
    A("  surviving signal is the noisiest of the three, per section 3.")
    A("")
    A("  Also rejected - fire nothing and stay silent. That is the default")
    A("  behaviour of a 2-of-3 counter with 1 input, and it renders as 'no")
    A("  sell signal', which a reader cannot distinguish from an all-clear.")
    A("")
    A("  What it does instead: four distinct verdicts, so blindness can never")
    A("  be read as calm.")
    for name, meaning in VERDICTS.items():
        A("    %-12s %s" % (name, meaning))
    A("")
    A("  Today, with only T2 readable: T2 quiet -> BLIND_QUIET, T2 firing ->")
    A("  ESCALATE. Never FIRE. Not a sale, not a silence: a human decision,")
    A("  logged as owed.")
    A("")

    if bt is None:
        A("3. T2 BACKTEST - NOT RUN")
        A("-" * 68)
        A("  No overlap between the STH-RP series and the BTC price series.")
        return "\n".join(L)

    n_weeks, n_fired = len(bt["weeks"]), len(bt["fired"])
    A("3. T2 BACKTEST (the only computable signal)")
    A("-" * 68)
    A("  Window        : %s -> %s" % (bt["first_day"], bt["last_day"]))
    A("  Weekly closes : %d" % n_weeks)
    A("  T2 fired      : %d weeks (%.1f%% of all weekly closes)"
      % (n_fired, 100.0 * n_fired / n_weeks if n_weeks else 0))
    A("  Episodes      : %d clusters more than 28 days apart"
      % len(bt["episodes"]))
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
    A("  Reading it: no edge, and the little there is points the wrong way")
    A("  for a sell trigger. Median BTC return after a T2 week is POSITIVE at")
    A("  all three horizons and at or above the baseline. Selling on T2 alone")
    A("  would mostly have sold into recoveries. The episode bucket (n=%d)"
      % len(bt["episodes"]))
    A("  is printed for completeness only; that many clusters cannot separate")
    A("  skill from luck at any horizon.")
    A("")
    A("4. T2 AND T3 BARELY CO-EXIST")
    A("-" * 68)
    dd = bt["drawdown_at_firing_pct"]
    if dd:
        A("  Drawdown from the running ATH when T2 fired:")
        A("    median %.1f%%    min %.1f%%    max %.1f%%"
          % (median(dd), min(dd), max(dd)))
        A("    firings within 10%% of the ATH: %d of %d"
          % (bt["near_ath_firings"], len(dd)))
    A("")
    A("  T2 firing a median 45% off the highs, never once within 10% of them,")
    A("  says what T2 actually is: a capitulation marker, not a distribution")
    A("  marker. That is an argument for keeping it as one vote of three, and")
    A("  the opposite of an argument for promoting it to one of one.")
    A("")
    A("  T3 requires being within 10% of the ATH; T2 fires deep in drawdowns.")
    A("  Even with a working ETF feed the pair would rarely co-occur, so the")
    A("  2-of-3 rule leans on T1 far harder than its symmetric phrasing")
    A("  admits. Sourcing LTH supply is the highest-value fix available.")
    A("")
    A("5. LIMITS")
    A("-" * 68)
    A("  - STH-RP history on disk starts 2022-08-31: %d weeks inside one"
      % n_weeks)
    A("    cycle. Small for a signal meant to fire once or twice per cycle.")
    A("  - Overlapping windows; in-sample; descriptive, not predictive.")
    A("  - T1 and T3 appear in no table above. They are not zero, not")
    A("    neutral, not proxied - they are unmeasured.")
    A("  - BTC USD is derived CapMrktCurUSD / SplyCur, a daily UTC close; it")
    A("    will not tick-match an exchange print.")
    A("")
    A("6. WHAT WOULD CHANGE THE ANSWER")
    A("-" * 68)
    A("  One sourced LTH supply series makes the gate operable: 2 of 3 becomes")
    A("  reachable, and T1 is the signal T2 most needs beside it - slow,")
    A("  structural, and not a drawdown artefact. That is one purchase, not a")
    A("  redesign. Until it exists the correct output is ESCALATE or")
    A("  BLIND_QUIET, never a number that looks like a decision.")
    return "\n".join(L)


def main():
    sth = load_sth()
    if not sth:
        print("analysis/series.json carries no sth_realized_price - cannot run")
        return 1
    text = render(backtest_t2(load_btc_price(), sth))
    os.makedirs(ANALYSIS, exist_ok=True)
    out = os.path.join(ANALYSIS, "sell_gate.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)
    print("\nWrote %s" % os.path.normpath(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
