#!/usr/bin/env python3
"""
Pivot Ladder mechanics - SHADOW ONLY.

Status
------
This computes the ladder's T score and state. It GOVERNS NOTHING. The Pivot
Ladder v1 proposal is a versioned strategy update (it introduces a 25% ETH
allocation cap that does not exist in the locked strategy), and by the rule in
Passation section 1 it does not apply until signed. Three decisions are
outstanding; see LADDER_PENDING_DECISIONS below.

Why it is implemented anyway: the same reason the 10-dimension gate ran in
shadow first. Measuring costs nothing and banks history, so that if it is
signed, it activates with evidence behind it.

Why this design won
-------------------
Monte Carlo, 1000 paths x 730 days, block-bootstrapped from 1366 real days
(analysis/montecarlo.txt):

  rule                      changes/yr   whipsaws/yr
  binary  >=2 of 4              92.3         87.6
  weighted (correlation)       92.3         87.6
  binary  >=3 of 4              18.5         15.4
  ladder  (this design)         12.5          0.0

The correlation weighting added NOTHING over the naive binary rule - identical
to two decimal places. That is the empirical proof of the Pivot Ladder's
central critique: lowering a signal's weight changes the amplitude of its
contribution, not the memorylessness of the rule. Churn comes from having no
state, and only hysteresis plus a minimum dwell fixes it.

The ladder's 0.00 whipsaws is structural, not luck: a minimum dwell of 14 days
makes a sub-14-day round trip impossible by construction.

Known cost, measured
--------------------
The coverage floor freezes the ladder when data thins out:

  outage 5%  -> frozen 11.6% of days
  outage 15% -> frozen 49.2% of days

Frozen half the time at 15% outage is the real price of refusing to decide on
a thin base. That is a deliberate trade, but it must be stated: this design
buys zero whipsaw with periods of enforced inaction.

One property worth naming: T is a RATIO over measurable weight, so it does not
drift as sources drop out. The binary gates do - their fire rate fell from
36.6% to 15.6% as outages rose from 0% to 15%, becoming silently more
conservative without announcing it. The ladder held ~35%.
"""

# Entry costs more than staying: a 0.10 dead band on each rung.
T_ENTER_ETH = 0.55
T_EXIT_ETH = 0.45
T_ENTER_ALT = 0.70
T_EXIT_ALT = 0.60

MIN_DWELL_DAYS = 14        # two weeks, matching the rule that governs Demand
COVERAGE_FLOOR = 0.70      # below this, T is not measurable and the ladder holds
MAX_SOURCE_AGE_DAYS = 3    # a signal older than this does not count as measurable

STATES = ["USDT", "BTC", "ETH", "ALT"]

LADDER_PENDING_DECISIONS = [
    "Sign the versioned strategy update: 25% ETH cap, four-state ladder",
    "Confirm the six thresholds: 0.55/0.45 ETH, 0.70/0.60 ALT, 2 weeks, 70% floor",
    "Confirm the ladder can never enter USDT on its own authority",
]

# Per-dimension caps. Weights inside a dimension normalise to its cap, so four
# correlated momentum signals cannot outweigh the dimension that contains them.
#
# This is structurally better than the per-signal weights it replaces. A weight
# says "this signal matters less"; a cap says "this QUESTION gets one vote,
# however many ways you ask it". The Monte Carlo showed per-signal weighting
# achieved nothing; the cap addresses the double-count at its source.
DIMENSION_CAPS = {1: 3.0, 5: 1.0, 6: 1.0, 7: 1.0, 9: 1.0}

# Rotation-axis signals only. MVRV Z and NVT are deliberately ABSENT: they
# answer "should we be exposed at all", which belongs to the risk axis and the
# sell gate. Mixing them in was the double-count - one print moving two
# decisions. Separating the questions is the fix; weighting was not.
# Dimension 3 (sentiment) is DELIBERATELY ABSENT from the ladder.
#
# Fear & Greed was removed because it already votes in the six-dimension
# composite. The same daily print moving two decisions is the overlap the
# two-axis design exists to prevent - and unlike the MVRV/SSR case it cannot
# be fixed by a weight, because it is literally one series read twice.
#
# social_volume left with it: LunarCrush is paid, so a D3 containing only an
# unavailable signal would permanently drag coverage without ever voting.
#
# Consequence, measured: possible weight falls 8.0 -> 7.0 while measurable
# stays 5.0, so coverage rises from 62.5% to 71.4% - above the 70% floor.
# Removing two signals UNFREEZES the ladder, because both were dead weight in
# the denominator. That is the correct behaviour, not a trick: coverage asks
# "how much of what I rely on can I actually read", and a signal you can never
# read should not be something you rely on.
ROTATION_SIGNALS = {
    "eth_btc_momentum": (1, 1.0),
    "btc_dominance": (1, 1.0),
    "alt_dominance": (1, 0.5),
    "altseason_index": (1, 0.5),
    "eth_etf_flows": (5, 1.0),
    "stablecoin_supply_ratio": (6, 1.0),
    "alt_funding_rates": (7, 1.0),   # now the alt-minus-BTC SPREAD
    "exchange_netflows": (9, 1.0),
}


# The ladder evaluates its OWN thresholds from the raw `signal` value.
#
# It must never read `vote`. `vote` is computed in fetch_signals against the
# GATE's thresholds, for a different instrument answering a different
# question. Consuming it made the ladder silently inherit the gate's
# calibration - the precise coupling the two-axis design exists to break.
# One print must not move two decisions, and that includes not sharing the
# comparison that turns a number into a boolean.
#
# Each rule returns True, False, or None. None means "this signal carries no
# readable value", which reduces the denominator rather than voting no.

def _above(payload, threshold):
    v = payload.get("signal")
    return None if v is None else v > threshold


def _below(payload, threshold):
    v = payload.get("signal")
    return None if v is None else v < threshold


def _rising_vs(payload, ref_field):
    v, ref = payload.get("signal"), payload.get(ref_field)
    return None if (v is None or ref is None) else v > ref


def _falling_vs(payload, ref_field):
    v, ref = payload.get("signal"), payload.get(ref_field)
    return None if (v is None or ref is None) else v < ref


def _funding_spread_positive(payload):
    """Alt funding ABOVE BTC funding - see FUNDING_SPREAD note below."""
    spread = payload.get("alt_minus_btc_apr_pct")
    rising = payload.get("rising")
    if spread is None or rising is None:
        return None
    return spread > 0 and rising


LADDER_RULES = {
    "eth_btc_momentum":        lambda p: _above(p, 10.0),
    "btc_dominance":           lambda p: _below(p, 54.0),
    "alt_dominance":           lambda p: _rising_vs(p, "ref_30d"),
    "altseason_index":         lambda p: _above(p, 75.0),
    # D3 (fear_greed, social_volume) intentionally absent - see
    # ROTATION_SIGNALS for why.
    "eth_etf_flows":           lambda p: _above(p, 0.0),
    "stablecoin_supply_ratio": lambda p: _falling_vs(p, "ref_value"),
    "alt_funding_rates":       lambda p: _funding_spread_positive(p),
    "exchange_netflows":       lambda p: _below(p, 0.0),
}


def _fresh(payload):
    """Structural availability only - says nothing about the reading."""
    if not isinstance(payload, dict):
        return False
    if payload.get("status") != "ok":
        return False
    age = payload.get("source_age_days")
    return not (age is not None and age > MAX_SOURCE_AGE_DAYS)


def _measurable(payload, key=None):
    """Fresh AND carrying a value the ladder's own rule can evaluate."""
    if not _fresh(payload):
        return False
    rule = LADDER_RULES.get(key) if key else None
    if rule is None:
        return payload.get("signal") is not None
    try:
        return rule(payload) is not None
    except Exception:
        return False


def compute_t(signals):
    """T and coverage, both on the SAME dimension-capped basis.

    The earlier version computed coverage on raw weights and T on capped
    weights. With D1 weighing exactly its cap the two agreed by coincidence,
    so the divergence was invisible - it would have appeared the first time a
    fifth momentum signal was added. Both now share one basis, and a test
    fails if they ever drift apart again.

    An absent source reduces the denominator; it does not vote no.
    """
    dim_possible, dim_measurable, dim_fired = {}, {}, {}

    for key, (dim, weight) in ROTATION_SIGNALS.items():
        dim_possible[dim] = dim_possible.get(dim, 0.0) + weight
        payload = signals.get(key)
        if not isinstance(payload, dict) or not _measurable(payload, key):
            continue
        dim_measurable[dim] = dim_measurable.get(dim, 0.0) + weight
        rule = LADDER_RULES.get(key)
        if rule and rule(payload):
            dim_fired[dim] = dim_fired.get(dim, 0.0) + weight

    # One scale factor per dimension, applied to possible, measurable and
    # fired alike - so every figure below is expressed in capped units.
    possible = measurable = fired = 0.0
    for dim, poss in dim_possible.items():
        cap = DIMENSION_CAPS.get(dim, poss)
        scale = min(1.0, cap / poss) if poss else 0.0
        possible += poss * scale
        measurable += dim_measurable.get(dim, 0.0) * scale
        fired += dim_fired.get(dim, 0.0) * scale

    coverage = measurable / possible if possible else 0.0
    t = (fired / measurable) if measurable else None

    return {
        "t": round(t, 4) if t is not None else None,
        "coverage": round(coverage, 4),
        "coverage_floor": COVERAGE_FLOOR,
        "measurable": bool(t is not None and coverage >= COVERAGE_FLOOR),
        "measurable_weight": round(measurable, 4),
        "total_weight": round(possible, 4),
        "basis": "dimension-capped (coverage and T share one basis)",
    }


def next_state(current, t_info, days_held):
    """One rung at a time, with hysteresis and a minimum dwell.

    The ladder can never enter USDT: de-risking belongs to the sell gate. Two
    systems commanding the same exit would be two authorities over one
    decision.
    """
    if not t_info["measurable"]:
        return current, "frozen - coverage %.2f%% below the %.0f%% floor" % (
            t_info["coverage"] * 100, COVERAGE_FLOOR * 100)

    if days_held < MIN_DWELL_DAYS:
        return current, "held - %d of %d minimum days in state" % (
            days_held, MIN_DWELL_DAYS)

    t = t_info["t"]
    if current == "BTC" and t >= T_ENTER_ETH:
        return "ETH", "T %.2f >= %.2f, entering ETH" % (t, T_ENTER_ETH)
    if current == "ETH":
        if t < T_EXIT_ETH:
            return "BTC", "T %.2f < %.2f, back to BTC" % (t, T_EXIT_ETH)
        if t >= T_ENTER_ALT:
            return "ALT", "T %.2f >= %.2f, entering ALT" % (t, T_ENTER_ALT)
    if current == "ALT" and t < T_EXIT_ALT:
        return "ETH", "T %.2f < %.2f, back to ETH" % (t, T_EXIT_ALT)

    return current, "T %.2f, no rung crossed" % t


def evaluate(signals, previous=None):
    """Full shadow evaluation. Never governs; records what it would do."""
    prev_state, days_held = "BTC", MIN_DWELL_DAYS
    if previous:
        prior = previous.get("ladder_shadow") or {}
        prev_state = prior.get("state", "BTC")
        days_held = (prior.get("days_held") or 0) + 1

    t_info = compute_t(signals)
    new_state, reason = next_state(prev_state, t_info, days_held)

    return {
        "governs": False,
        "status": "SHADOW - unsigned strategy update, governs nothing",
        "state": new_state,
        "previous_state": prev_state,
        "days_held": 0 if new_state != prev_state else days_held,
        "reason": reason,
        "pending_decisions": LADDER_PENDING_DECISIONS,
        **t_info,
    }
