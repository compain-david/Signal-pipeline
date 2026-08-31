#!/usr/bin/env python3
"""
Monte Carlo comparison of decision rules.

What this tests, and what it does NOT
-------------------------------------
It compares the MECHANICS of competing decision rules: how often each changes
state, how often it changes back (whipsaw), and how it behaves when data goes
missing. It does NOT predict returns. Nothing here says a rule makes money -
there is no forward-return series, and claiming otherwise would be dishonest
about what four years of six signals can support.

Churn is the right target because it is where a rotation rule actually leaks
value in practice: every state change is a transaction, a tax event, and a
behavioural decision. A rule that flips and flips back has cost you twice for
nothing.

Method
------
Block bootstrap over the REAL historical series in analysis/series.json.
Contiguous 30-day blocks are sampled and stitched into synthetic paths, which
preserves both autocorrelation (signals are sticky) and cross-correlation
(MVRV Z and SSR move together at 0.79). A Gaussian simulation would destroy
both and flatter every rule equally.

Rules compared
--------------
  binary_low    fire at >=2 of 4          (the 4/9-equivalent bar)
  binary_high   fire at >=3 of 4          (the 5/9-equivalent bar)
  weighted      correlation-weighted score against band B
  ladder        weighted score + hysteresis + minimum dwell + coverage floor
                (the Pivot Ladder mechanics)

Outage simulation
-----------------
Each signal independently goes unmeasurable with probability p per day, held
for a short run. Sweeping p shows which rules degrade gracefully and which
quietly decide on a thin base.

Run: python scripts/montecarlo.py [n_paths]
Needs analysis/series.json - produced by scripts/analyse_correlation.py.
"""

import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERIES = os.path.join(HERE, "..", "analysis", "series.json")

# Deterministic: a Monte Carlo whose verdict changes between runs cannot be
# used to make a decision, and cannot be reviewed.
SEED = 20260831

BLOCK = 30
PATH_DAYS = 730          # two years per synthetic path
MIN_DWELL = 14           # Pivot Ladder: minimum 2 weeks in a state
HYSTERESIS_IN = 0.55     # Pivot Ladder entry threshold for ETH
HYSTERESIS_OUT = 0.45    # Pivot Ladder exit threshold
COVERAGE_FLOOR = 0.70    # below this the ladder freezes rather than deciding

# Correlation-derived weights (see analyse_correlation.py). The MVRV/SSR pair
# correlates 0.79, so each carries 0.8 rather than 1.0.
WEIGHTS = {
    "mvrv_z_score": 0.8,
    "stablecoin_supply_ratio": 0.8,
    "nvt": 1.0,
    "fear_greed": 1.0,
}
BAND_B = 3.5 / 8.6 * sum(WEIGHTS.values())   # band B, rescaled to this subset


def load_series():
    with open(SERIES, encoding="utf-8") as f:
        d = json.load(f)
    return d["dates"], d["series"]


def to_votes(series, dates):
    """Convert raw levels into the boolean votes the gate actually sees."""
    mvrv = series["mvrv_z_score"]
    nvt = series["nvt"]
    fg = series["fear_greed"]
    ssr = series["stablecoin_supply_ratio"]

    votes = []
    for i in range(len(dates)):
        if i < 90:
            continue
        nvt_avg = sum(nvt[i - 90:i]) / 90
        votes.append({
            "mvrv_z_score": mvrv[i] > 3.0,
            "nvt": nvt[i] > nvt_avg,
            "fear_greed": fg[i] > 60,
            "stablecoin_supply_ratio": ssr[i] < ssr[i - 30],
        })
    return votes


def bootstrap_path(votes, rng, days=PATH_DAYS):
    """Stitch contiguous blocks - preserves stickiness and co-movement."""
    out = []
    while len(out) < days:
        start = rng.randrange(0, max(1, len(votes) - BLOCK))
        out.extend(votes[start:start + BLOCK])
    return out[:days]


def apply_outages(path, rng, p_outage):
    """Mark signals unmeasurable in short runs, as real outages behave."""
    if p_outage <= 0:
        return [{k: (v, True) for k, v in day.items()} for day in path]
    keys = list(WEIGHTS)
    down_until = {k: -1 for k in keys}
    out = []
    for i, day in enumerate(path):
        row = {}
        for k in keys:
            if i > down_until[k] and rng.random() < p_outage:
                down_until[k] = i + rng.randint(1, 4)
            row[k] = (day[k], i > down_until[k])
        out.append(row)
    return out


# -- rules -------------------------------------------------------------------

def rule_binary(path, threshold):
    """Fire on a raw count. No memory, no hysteresis - the current design."""
    states = []
    for day in path:
        n = sum(1 for v, ok in day.values() if ok and v)
        states.append(1 if n >= threshold else 0)
    return states


def rule_weighted(path):
    """Correlation-weighted score against band B. Still memoryless."""
    states = []
    for day in path:
        score = sum(WEIGHTS[k] for k, (v, ok) in day.items() if ok and v)
        states.append(1 if score >= BAND_B else 0)
    return states


def rule_ladder(path):
    """Pivot Ladder mechanics: hysteresis + minimum dwell + coverage floor.

    Returns (states, frozen_days). A frozen day holds the previous state
    rather than deciding on an insufficient base.
    """
    states, frozen = [], 0
    state, held = 0, 0
    total_w = sum(WEIGHTS.values())

    for day in path:
        measurable = sum(WEIGHTS[k] for k, (_, ok) in day.items() if ok)
        coverage = measurable / total_w if total_w else 0.0

        if coverage < COVERAGE_FLOOR or measurable == 0:
            frozen += 1
            states.append(state)      # freeze, do not decide
            held += 1
            continue

        fired = sum(WEIGHTS[k] for k, (v, ok) in day.items() if ok and v)
        t = fired / measurable        # T is computed on MEASURABLE weight

        if held < MIN_DWELL:
            held += 1
            states.append(state)
            continue

        new = state
        if state == 0 and t >= HYSTERESIS_IN:
            new = 1
        elif state == 1 and t < HYSTERESIS_OUT:
            new = 0

        if new != state:
            state, held = new, 0
        else:
            held += 1
        states.append(state)
    return states, frozen


# -- metrics -----------------------------------------------------------------

def metrics(states):
    transitions = sum(1 for i in range(1, len(states)) if states[i] != states[i - 1])
    idx = [i for i in range(1, len(states)) if states[i] != states[i - 1]]
    whipsaw = sum(1 for a, b in zip(idx, idx[1:]) if b - a < MIN_DWELL)
    years = len(states) / 365.0
    return {
        "fire_pct": sum(states) / len(states) * 100,
        "transitions_per_year": transitions / years,
        "whipsaws_per_year": whipsaw / years,
    }


def main():
    n_paths = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    if not os.path.exists(SERIES):
        print("Missing %s - run scripts/analyse_correlation.py first." % SERIES)
        return 1

    dates, series = load_series()
    votes = to_votes(series, dates)
    print("Monte Carlo: %d paths x %d days, block bootstrap from %d real days"
          % (n_paths, PATH_DAYS, len(votes)))
    print("Seed %d (deterministic)\n" % SEED)

    for p_outage in (0.0, 0.05, 0.15):
        rng = random.Random(SEED)
        acc = {}
        frozen_total = 0
        for _ in range(n_paths):
            raw = bootstrap_path(votes, rng)
            path = apply_outages(raw, rng, p_outage)
            runs = {
                "binary_low  (>=2 of 4)": rule_binary(path, 2),
                "binary_high (>=3 of 4)": rule_binary(path, 3),
                "weighted    (band B)": rule_weighted(path),
            }
            lad, fz = rule_ladder(path)
            runs["ladder      (Pivot)"] = lad
            frozen_total += fz
            for name, st in runs.items():
                m = metrics(st)
                a = acc.setdefault(name, {k: 0.0 for k in m})
                for k, v in m.items():
                    a[k] += v

        print("=== outage probability %.0f%% ===" % (p_outage * 100))
        print("  %-24s %9s %14s %13s" % ("rule", "fire %", "changes/yr", "whipsaws/yr"))
        for name, a in acc.items():
            print("  %-24s %8.1f%% %13.2f %13.2f"
                  % (name, a["fire_pct"] / n_paths,
                     a["transitions_per_year"] / n_paths,
                     a["whipsaws_per_year"] / n_paths))
        if p_outage > 0:
            print("  ladder frozen: %.1f%% of days"
                  % (frozen_total / (n_paths * PATH_DAYS) * 100))
        print()

    print("Whipsaws are the number that matters: a state change reversed inside")
    print("%d days is a round trip that cost two transactions and gained nothing." % MIN_DWELL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
