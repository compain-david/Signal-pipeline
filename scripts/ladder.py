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
DIMENSION_CAPS = {1: 3.0, 3: 1.0, 5: 1.0, 6: 1.0, 7: 1.0, 9: 1.0}

# Rotation-axis signals only. MVRV Z and NVT are deliberately ABSENT: they
# answer "should we be exposed at all", which belongs to the risk axis and the
# sell gate. Mixing them in was the double-count - one print moving two
# decisions. Separating the questions is the fix; weighting was not.
ROTATION_SIGNALS = {
    "eth_btc_momentum": (1, 1.0),
    "btc_dominance": (1, 1.0),
    "alt_dominance": (1, 0.5),
    "altseason_index": (1, 0.5),
    "fear_greed": (3, 0.5),
    "social_volume": (3, 0.5),
    "eth_etf_flows": (5, 1.0),
    "stablecoin_supply_ratio": (6, 1.0),
    "alt_funding_rates": (7, 1.0),
    "exchange_netflows": (9, 1.0),
}


def _measurable(payload):
    """A signal counts only if it is fresh AND actually succeeded."""
    if not isinstance(payload, dict):
        return False
    if payload.get("status") != "ok":
        return False
    age = payload.get("source_age_days")
    if age is not None and age > MAX_SOURCE_AGE_DAYS:
        return False
    return payload.get("vote") is not None


def compute_t(signals):
    """T over MEASURABLE weight, with per-dimension caps applied.

    An absent source reduces the denominator - it does not vote no. This is
    the same denominator-honesty rule the gate uses, applied to a ratio.
    """
    by_dim_total, by_dim_fired = {}, {}
    measured, total = 0.0, 0.0

    for key, (dim, weight) in ROTATION_SIGNALS.items():
        total += weight
        payload = signals.get(key)
        if not _measurable(payload):
            continue
        measured += weight
        by_dim_total[dim] = by_dim_total.get(dim, 0.0) + weight
        if payload.get("vote"):
            by_dim_fired[dim] = by_dim_fired.get(dim, 0.0) + weight

    # normalise each dimension to its cap so a crowded dimension cannot
    # outvote a sparse one purely by having more ways to ask the question
    fired_capped, measurable_capped = 0.0, 0.0
    for dim, dim_total in by_dim_total.items():
        cap = DIMENSION_CAPS.get(dim, dim_total)
        scale = min(1.0, cap / dim_total) if dim_total else 0.0
        measurable_capped += dim_total * scale
        fired_capped += by_dim_fired.get(dim, 0.0) * scale

    coverage = measured / total if total else 0.0
    t = (fired_capped / measurable_capped) if measurable_capped else None

    return {
        "t": round(t, 4) if t is not None else None,
        "coverage": round(coverage, 4),
        "coverage_floor": COVERAGE_FLOOR,
        "measurable": bool(t is not None and coverage >= COVERAGE_FLOOR),
        "measurable_weight": round(measurable_capped, 2),
        "total_weight": round(total, 2),
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
