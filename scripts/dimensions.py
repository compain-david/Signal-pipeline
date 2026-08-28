#!/usr/bin/env python3
"""
The 10-dimension MECE rotation gate.

This module holds the NEW gate structure. It is deliberately separate from the
legacy flat gate in fetch_signals.py so that both can run side by side:

  - the legacy gate stays AUTHORITATIVE until ADOPTED_FROM
  - the new gate runs in SHADOW mode meanwhile, logging what it *would* have
    said without changing any decision

Collecting a signal is not voting on it. Nothing here changes the gate's
output before ADOPTED_FROM.

Design notes
------------
Dimensions are grouped so that correlated signals cannot double-count. The
old flat list let dominance / ASI / TOTAL3 vote three times for what is
substantially one observation; here they all sit under dimension 1 and only
the designated Tier A signal carries a vote.

Tiers:
  A       full vote, counts toward the 5-of-9 threshold
  B       confirm-only, never counts toward the threshold, can add urgency
  track   logged for evidence, no vote, candidate for promotion
"""

# Flip the new gate from shadow to authoritative on this date (UTC).
# Set to the 30 August monthly edition so the gate's first month of operation
# is itself logged and graded through the normal Part D / Part E cycle.
ADOPTED_FROM = "2026-08-30"

# Tier A votes required for the gate to fire.
TIER_A_THRESHOLD = 5

DIMENSION_NAMES = {
    1: "relative_momentum",
    2: "valuation",
    3: "sentiment",
    4: "technical_pattern",
    5: "institutional_demand",
    6: "liquidity",
    7: "derivatives_positioning",
    8: "onchain_usage",
    9: "supply_side",
    10: "inflection",
}

# signal key -> (dimension number, tier)
# Tier A total must equal 9; asserted at import so a careless edit fails loudly.
SIGNAL_REGISTRY = {
    # -- Tier A, the voting set ------------------------------------------
    "eth_btc_momentum":      (1, "A"),
    "mvrv_z_score":          (2, "A"),
    "nvt":                   (2, "A"),
    "fear_greed":            (3, "A"),
    "eth_etf_flows":         (5, "A"),
    "stablecoin_supply_ratio": (6, "A"),
    "alt_funding_rates":     (7, "A"),
    "exchange_netflows":     (9, "A"),
    "sth_realized_price":    (10, "A"),

    # -- Tier B, confirm-only --------------------------------------------
    "pi_cycle_top":          (4, "B"),
    "eth_btc_golden_cross":  (1, "B"),

    # -- Tracked only, no vote -------------------------------------------
    "btc_dominance":         (1, "track"),
    "altseason_index":       (1, "track"),
    "mvrv_ratio":            (2, "track"),
    "mayer_multiple":        (2, "track"),
    "puell_multiple":        (2, "track"),
    "social_volume":         (3, "track"),
    "sopr":                  (9, "track"),
}

TIER_A_SIGNALS = [k for k, (_, t) in SIGNAL_REGISTRY.items() if t == "A"]

assert len(TIER_A_SIGNALS) == 9, (
    "Tier A must hold exactly 9 signals, found %d: %s"
    % (len(TIER_A_SIGNALS), TIER_A_SIGNALS)
)


def annotate(signals):
    """Stamp each signal with its dimension and tier, in place."""
    for key, payload in signals.items():
        if not isinstance(payload, dict):
            continue
        entry = SIGNAL_REGISTRY.get(key)
        if entry is None:
            continue
        dim, tier = entry
        payload["dimension"] = dim
        payload["dimension_name"] = DIMENSION_NAMES[dim]
        payload["tier"] = tier
    return signals


def tally(signals, today):
    """Compute the new gate's verdict.

    Returns the tally plus whether it is authoritative yet. Only Tier A
    signals with a boolean `vote` count. A signal that could not be fetched
    reduces the denominator rather than counting as a 'no' - the same
    convention the legacy gate uses.
    """
    fired, checkable, unavailable = [], [], []
    for key in TIER_A_SIGNALS:
        payload = signals.get(key)
        if not isinstance(payload, dict):
            unavailable.append(key)
            continue
        vote = payload.get("vote")
        if vote is None:
            unavailable.append(key)
        else:
            checkable.append(key)
            if vote:
                fired.append(key)

    # Tier B never counts toward the threshold; it can only add urgency once
    # the primary threshold is already met.
    confirms = [
        k for k, (_, t) in SIGNAL_REGISTRY.items()
        if t == "B" and isinstance(signals.get(k), dict)
        and signals[k].get("vote") is True
    ]

    active = today >= ADOPTED_FROM
    would_fire = len(fired) >= TIER_A_THRESHOLD

    return {
        "authoritative": active,
        "adopted_from": ADOPTED_FROM,
        "fired": len(fired),
        "checkable": len(checkable),
        "threshold": TIER_A_THRESHOLD,
        "would_fire": would_fire,
        "fired_signals": fired,
        "unavailable": unavailable,
        "tier_b_confirming": confirms,
        "note": (
            "AUTHORITATIVE - this gate governs" if active else
            "SHADOW MODE - logged only, legacy gate governs until " + ADOPTED_FROM
        ),
    }
