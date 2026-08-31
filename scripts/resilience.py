#!/usr/bin/env python3
"""
Degradation policy: what the pipeline does when a source fails.

Why this exists
---------------
Seven signals (MVRV Z, NVT, SSR, STH-RP, Puell, Mayer, SOPR) come from one
provider, BGeometrics. The funding signal has a four-deep fallback chain; these
had none. Finding a second free provider for on-chain Bitcoin metrics is not
realistic, so resilience here is achieved differently: by never silently
losing a value that was known yesterday.

Three guarantees:

1. LAST-GOOD CARRY-FORWARD. If a source fails this run but succeeded recently,
   reuse the last good value, clearly marked `stale: true` with its age. A
   value known to be two days old beats a null.

2. STALENESS IS EXPLICIT. Carried-forward values NEVER vote. A stale reading
   reduces the gate denominator exactly like a missing one. This is the
   important half: carry-forward improves reporting without letting an old
   number quietly drive a decision.

3. UPSTREAM FREEZE DETECTION. A source can return HTTP 200 forever while its
   `as_of` date stops advancing. That failure is invisible to status checks,
   so as_of is compared against today independently of HTTP success.

All functions here are pure - no network, no clock reads beyond what is passed
in - so they are unit-testable without touching an API.
"""

from datetime import datetime, timedelta

CARRY_FORWARD_MAX_DAYS = 3
FAILED_STATUSES = ("error", "http_error")


def _parse_date(value):
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def check_staleness(signals, today, max_age_days):
    """Flag any signal whose own as_of has stopped advancing.

    Catches the upstream-freeze case: HTTP 200, valid JSON, stale content.
    A frozen source is demoted so it cannot vote on old data.
    """
    today_date = _parse_date(today)
    if today_date is None:
        return signals
    for payload in signals.values():
        if not isinstance(payload, dict):
            continue
        as_of = _parse_date(payload.get("as_of"))
        if as_of is None:
            continue
        age = (today_date - as_of).days
        payload["source_age_days"] = age
        if age > max_age_days:
            payload["stale"] = True
            payload["status"] = "stale"
            payload["vote"] = None  # a frozen source must not vote
            payload["note"] = (
                "source has not advanced in %d days (max %d) - demoted, not voting"
                % (age, max_age_days)
            )
    return signals


def carry_forward(signals, previous, today):
    """Reuse the last good value for any signal that failed this run.

    Carried values are marked stale and stripped of their vote, so they inform
    the reader without influencing the gate.
    """
    if not previous:
        return signals
    prev_signals = previous.get("signals")
    if not isinstance(prev_signals, dict):
        return signals

    today_date = _parse_date(today)
    prev_date = _parse_date(previous.get("date"))

    for key, payload in signals.items():
        if not isinstance(payload, dict):
            continue
        if payload.get("status") not in FAILED_STATUSES:
            continue

        prior = prev_signals.get(key)
        if not isinstance(prior, dict):
            continue
        if prior.get("signal") is None:
            continue
        # never chain a carry-forward onto another carry-forward
        if prior.get("stale"):
            continue

        age = None
        if today_date and prev_date:
            age = (today_date - prev_date).days
            if age > CARRY_FORWARD_MAX_DAYS:
                continue

        payload["signal"] = prior.get("signal")
        payload["carried_from"] = previous.get("date")
        payload["carried_age_days"] = age
        payload["stale"] = True
        payload["vote"] = None  # stale values never vote
        payload["status"] = "carried_forward"
        payload["note"] = (
            "live fetch failed (%s); reusing last good value from %s - not voting"
            % (payload.get("error", payload.get("status", "unknown"))[:60],
               previous.get("date"))
        )
    return signals


def health(signals):
    """Summarise source health so a silent partial failure is visible.

    `degraded` is the flag worth alerting on: it means the run technically
    succeeded while losing live data.
    """
    ok, failed, stale, unavailable = [], [], [], []
    for key, payload in signals.items():
        if not isinstance(payload, dict):
            continue
        status = payload.get("status")
        if status == "ok":
            ok.append(key)
        elif status in FAILED_STATUSES:
            failed.append(key)
        elif status in ("stale", "carried_forward"):
            stale.append(key)
        else:
            unavailable.append(key)  # no_key / no_api / not_implemented

    total_live = len(ok)
    return {
        "ok": total_live,
        "failed": len(failed),
        "stale": len(stale),
        "structurally_unavailable": len(unavailable),
        "failed_signals": failed,
        "stale_signals": stale,
        "degraded": bool(failed or stale),
        "note": "degraded=true means the run completed but lost live data - "
                "check failed_signals before trusting the tally",
    }
