#!/usr/bin/env python3
"""
Event study: the 2021 altseasons scored against the CURRENT signal set.

SHADOW ONLY. This governs nothing. It is an audit of the framework's own
evidence base, in the same spirit as montecarlo.py and forward_study.py:
measure the thing, publish the cost, change no decision.

The question
------------
This framework justifies itself by reference to two altseasons - February 2021
(and the run into May) and September-November 2021. Every threshold in
fetch_signals.THRESHOLDS and every rung in ladder.py is calibrated on an
intuition about those two episodes. So: if the current signal set had been
running in 2021, what would it have said?

The answer, stated before the tables so nobody has to hunt for it
-----------------------------------------------------------------
It would have said nothing, on every day of both windows, because it could not
read itself. Only 2 of the 9 Tier A signals can be reconstructed for 2021 from
anything on disk. The gate needs 5 of 9 to fire (dimensions.TIER_A_THRESHOLD),
so with at most 2 scoreable signals the 2021 tally is not merely low - it is
arithmetically incapable of reaching the threshold. The ladder is worse: 1 of
its 8 rotation signals is reconstructable, giving 1/7 coverage in
dimension-capped units against a 70% floor. It would have been frozen for all
365 days of 2021.

That is a finding about the DESIGN, not about the year. A gate calibrated on
two events it structurally cannot score is a gate calibrated on memory.

Why the absences are shown and not omitted
------------------------------------------
A table that silently drops the seven unreadable signals looks like a signal
set that was quiet in 2021. It was not quiet; it was blind. Every Tier A
signal keeps its column on every date, and an unreadable one prints `--`, so
the reader counts the blanks instead of trusting a summary of them.

Two kinds of absence are separated, because they have different fixes:

  NO HISTORY ON DISK   the metric existed in 2021, this repo just never
                       archived it. BGeometrics allows 10 requests/HOUR, so
                       backfilling four years of daily on-chain history is not
                       something this study can do - but it is fixable work.
  DID NOT EXIST        eth_etf_flows. US spot ETH ETFs began trading
                       2024-07-23. No archive, no budget and no provider can
                       produce a 2021 value, because there was no instrument.
                       That signal is permanently unscoreable against 2021.

What CAN be said about 2021
---------------------------
ETH/BTC daily closes go back to 2019-01 (analysis/ethbtc.json), so the study
always reports what the ROTATION DID in each window even where the inputs
cannot be scored. The reader gets the outcome even when the framework has no
opinion to compare it against. That asymmetry is the point of the exercise.

Honest limits
-------------
- No network. Everything is read from analysis/. Nothing is re-fetched, and no
  absent series is replaced by a proxy - an absent signal reduces the
  denominator and prints as absent.
- The builder for analysis/ethbtc.json is not in this repo, so the venue and
  close convention behind those prices are unverified here. The levels are
  used only for percentage changes within that same series, which is the use
  least sensitive to the convention.
- eth_btc_momentum is reconstructed as the change from t-14 CALENDAR days to
  t. The live fetcher takes CoinGecko's last 14 daily points from a different
  vendor. Same rule, not the same bytes; a reading within a point or two of
  the 10% threshold should be read as ambiguous rather than decided.
- fear_greed comes from the alternative.me response already cached under
  analysis/.cache/. It genuinely covers 2021 - it is the one signal in the set
  with a free complete archive - and that is exactly why its presence must not
  be read as reassurance about the other eight.

Run: python scripts/event_study.py
"""

import datetime
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dimensions
import ladder

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.join(HERE, "..", "analysis")
OUT_PATH = os.path.join(ANALYSIS, "event_study_2021.txt")

# Thresholds are duplicated from fetch_signals.THRESHOLDS rather than imported,
# because importing that module pulls in its network-facing fetchers and this
# study must stay offline and rate-limit-free. Duplication risks drift, so
# tests/test_event_study.py asserts these still match the rules the ladder and
# the gate actually apply, and fails the moment somebody retunes one and not
# the other.
MOMENTUM_THRESHOLD = 10.0   # fetch_signals eth_btc_momentum_14d_above_pct
FEAR_GREED_THRESHOLD = 60   # fetch_signals fear_greed_above
MOMENTUM_WINDOW_DAYS = 14

STUDY_YEAR = "2021"

# The two episodes this framework reasons about. Window A deliberately runs to
# the May top rather than stopping at the end of February: the claim being
# audited is "February 2021 and the run into May", and a window that stopped in
# February would flatter the framework by ending before the reversal.
WINDOWS = [
    ("A", "2021-02-01", "2021-05-31",
     "February 2021 altseason and the run into the May top"),
    ("B", "2021-09-01", "2021-11-30",
     "September - November 2021 altseason"),
]

# The gate's Tier A set in a fixed printing order, so columns do not reshuffle
# between runs, with the short header used in the dated table.
COLUMNS = [
    ("eth_btc_momentum", "MOM"),
    ("fear_greed", "FNG"),
    ("mvrv_z_score", "MVRVZ"),
    ("nvt", "NVT"),
    ("stablecoin_supply_ratio", "SSR"),
    ("sth_realized_price", "STH"),
    ("eth_etf_flows", "ETF"),
    ("alt_funding_rates", "FUND"),
    ("exchange_netflows", "FLOW"),
]

# Why each Tier A signal cannot be reconstructed for 2021. Held as data rather
# than prose so the tests can assert the study accounts for all nine signals
# and the report can print a reason beside every blank column.
ABSENCE_REASONS = {
    "mvrv_z_score": ("NO HISTORY ON DISK",
                     "analysis/series.json starts 2022-08-31; BGeometrics "
                     "backfill costs 10 req/hour"),
    "nvt": ("NO HISTORY ON DISK",
            "analysis/series.json starts 2022-08-31"),
    "stablecoin_supply_ratio": ("NO HISTORY ON DISK",
                                "analysis/series.json starts 2022-08-31"),
    # The vote needs BOTH legs: the STH cost basis and a daily BTC close to
    # compare it against. The BTC close IS archived (analysis/.cache), so only
    # one leg is missing - worth stating precisely, because "half the input
    # exists" and "no input exists" imply different amounts of remaining work.
    "sth_realized_price": ("NO HISTORY ON DISK",
                           "series.json STH starts 2022-08-31; the BTC close "
                           "leg IS on disk, so only the cost basis is missing"),
    "alt_funding_rates": ("NO HISTORY ON DISK",
                          "the four funding fetchers are point-in-time only. "
                          "HYPE also did not list until Nov 2024, so the "
                          "basket itself is not the 2021 basket"),
    "exchange_netflows": ("NO HISTORY ON DISK",
                          "point-in-time fetch only, no archive in this repo"),
    "eth_etf_flows": ("DID NOT EXIST",
                      "US spot ETH ETFs began trading 2024-07-23 - no "
                      "provider can produce a 2021 value"),
}


# -- loading, offline only ---------------------------------------------------
#
# Every loader returns (data, note). A missing file is reported, never
# substituted. This study is allowed to say "this does not exist"; it is not
# allowed to quietly stand something else in its place.

def load_ethbtc(path=None):
    path = path or os.path.join(ANALYSIS, "ethbtc.json")
    if not os.path.exists(path):
        return {}, "MISSING: %s" % path
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError) as exc:
        return {}, "UNREADABLE: %s (%s)" % (path, exc)
    out = {d: v["ethbtc"] for d, v in raw.items()
           if isinstance(v, dict) and v.get("ethbtc") is not None}
    return out, "%d days, %s -> %s" % (len(out), min(out), max(out))


def load_series(path=None):
    path = path or os.path.join(ANALYSIS, "series.json")
    if not os.path.exists(path):
        return {}, "MISSING: %s" % path
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError) as exc:
        return {}, "UNREADABLE: %s (%s)" % (path, exc)
    dates = raw.get("dates", [])
    out = {}
    for name, values in raw.get("series", {}).items():
        out[name] = {d: v for d, v in zip(dates, values) if v is not None}
    if not dates:
        return out, "no dates"
    return out, "%d days, %s -> %s" % (len(dates), dates[0], dates[-1])


def load_fear_greed(cache_dir=None):
    """Read the alternative.me archive already cached on disk.

    Deliberately no fetch fallback. A study whose job is to report what was
    knowable must not quietly become the thing that makes it knowable.

    Every matching cache file is merged rather than the first one picked,
    because the cache holds the same archive under more than one filename and
    an alphabetical pick would make the answer depend on how a sibling script
    happened to name its download.
    """
    cache_dir = cache_dir or os.path.join(ANALYSIS, ".cache")
    hits = sorted(glob.glob(os.path.join(cache_dir, "*fng*.json")))
    if not hits:
        return {}, "MISSING: no *fng*.json in %s - F&G counts as absent" % cache_dir
    out = {}
    for path in hits:
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, ValueError):
            continue  # a sibling script may be mid-write; skip, never guess
        for entry in raw.get("data", []):
            try:
                ts = int(entry["timestamp"])
                day = datetime.datetime.fromtimestamp(
                    ts, datetime.timezone.utc).strftime("%Y-%m-%d")
                out[day] = float(entry["value"])
            except (KeyError, TypeError, ValueError):
                continue
    if not out:
        return out, "cache present but unreadable - F&G counts as absent"
    return out, "%d days, %s -> %s (%d cache file(s))" % (
        len(out), min(out), max(out), len(hits))


def load_btc_price(cache_dir=None):
    """Daily BTC close, if a sibling script has already archived one.

    Only used as the second leg of the sth_realized_price vote. On its own it
    scores nothing, and it is never substituted for a missing cost basis.
    """
    cache_dir = cache_dir or os.path.join(ANALYSIS, ".cache")
    hits = sorted(glob.glob(os.path.join(cache_dir, "btc_price*.json")))
    if not hits:
        return {}, "MISSING: no btc_price*.json in %s" % cache_dir
    out = {}
    for path in hits:
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, ValueError):
            continue
        if not isinstance(raw, dict):
            continue
        for day, val in raw.items():
            try:
                out[str(day)[:10]] = float(val)
            except (TypeError, ValueError):
                continue
    if not out:
        return out, "cache present but unreadable"
    return out, "%d days, %s -> %s" % (len(out), min(out), max(out))


# -- reconstruction ----------------------------------------------------------

def daterange(start, end):
    a = datetime.date.fromisoformat(start)
    b = datetime.date.fromisoformat(end)
    out = []
    while a <= b:
        out.append(a.isoformat())
        a += datetime.timedelta(days=1)
    return out


def momentum_14d(prices, date, window=MOMENTUM_WINDOW_DAYS):
    """ETH/BTC percent change over `window` calendar days ending on `date`.

    Returns None when either end is missing, rather than reaching for the
    nearest available day. A gap in the price series is a gap; silently
    widening the window would change the rule being tested.
    """
    try:
        end = datetime.date.fromisoformat(date)
    except ValueError:
        return None
    start = (end - datetime.timedelta(days=window)).isoformat()
    a, b = prices.get(start), prices.get(date)
    if a is None or b is None or not a:
        return None
    return (b / a - 1) * 100


def build_signals(date, prices, series, fng, btc=None):
    """The signal dict as it WOULD have looked on `date`, from disk only.

    Absent signals get status 'no_data' with signal and vote None - the same
    shape a failed live fetch produces. ladder.compute_t and dimensions.tally
    then see a genuinely thin day and reduce their denominators exactly as they
    would in production. Reusing their code instead of reimplementing the
    coverage arithmetic is the whole point: a study that computed coverage its
    own way would be measuring itself rather than the pipeline.
    """
    signals = {}
    for key in set(dimensions.TIER_A_SIGNALS) | set(ladder.ROTATION_SIGNALS):
        signals[key] = {"status": "no_data", "signal": None, "vote": None}

    mom = momentum_14d(prices, date)
    if mom is not None:
        signals["eth_btc_momentum"] = {
            "status": "ok", "source_age_days": 0,
            "signal": round(mom, 2),
            "vote": mom > MOMENTUM_THRESHOLD,
        }

    if date in fng:
        val = fng[date]
        signals["fear_greed"] = {
            "status": "ok", "source_age_days": 0,
            "signal": val,
            "vote": val > FEAR_GREED_THRESHOLD,
        }

    # Anything in series.json that happens to cover this date. Nothing does in
    # 2021; the lookup is written generally so that re-running this study after
    # a real backfill picks the new history up without an edit here.
    #
    # Note these arrive with vote None on purpose. The gate's rules for NVT and
    # SSR compare against a 90-day average and a 30-day reference that this
    # study does not archive, so the value can be REPORTED but not SCORED.
    # Giving it a vote invented from a shorter window would be exactly the
    # silent proxy this module refuses to make.
    for key in ("mvrv_z_score", "nvt", "stablecoin_supply_ratio"):
        hit = series.get(key, {}).get(date)
        if hit is not None:
            signals[key] = {
                "status": "ok", "source_age_days": 0,
                "signal": hit, "vote": None,
                "note": "value present, but its vote rule needs a reference "
                        "window this study does not archive - reported, "
                        "not scored",
            }

    # STH-RP is the one signal needing two legs: the cost basis and a BTC
    # close to compare it against. The close is archived, the basis is not, so
    # the vote stays None until a real backfill lands - at which point this
    # path scores it without an edit here. A basis without a close is reported
    # and not scored; inventing the missing leg is the failure this whole
    # study is about.
    sth = series.get("sth_realized_price", {}).get(date)
    if sth is not None:
        close = (btc or {}).get(date)
        signals["sth_realized_price"] = {
            "status": "ok", "source_age_days": 0,
            "signal": sth,
            "btc_price_usd": close,
            "vote": None if close is None else close > sth,
            "note": ("scored against the archived BTC close" if close is not None
                     else "no BTC close on disk for this date - reported, "
                          "not scored"),
        }
    return signals


def score_date(date, prices, series, fng, btc=None):
    """One dated row: values, fires, and the coverage that existed AT THE TIME."""
    signals = build_signals(date, prices, series, fng, btc)
    tally = dimensions.tally(signals, date)
    t_info = ladder.compute_t(signals)

    n_checkable = tally["checkable"]
    n_total = len(dimensions.TIER_A_SIGNALS)

    return {
        "date": date,
        "ethbtc": prices.get(date),
        "signals": signals,
        "gate_checkable": n_checkable,
        "gate_total": n_total,
        "gate_coverage_pct": n_checkable / n_total * 100 if n_total else 0.0,
        "gate_fired": tally["fired"],
        "gate_would_fire": tally["would_fire"],
        # Not "did it fire" but "could it have": with fewer readable signals
        # than the threshold, a zero tally is a measurement failure, not a
        # market observation, and the two must never print the same.
        "gate_reachable": n_checkable >= dimensions.TIER_A_THRESHOLD,
        "ladder_coverage": t_info["coverage"],
        "ladder_t": t_info["t"],
        "ladder_measurable": t_info["measurable"],
    }


# -- rotation outcome --------------------------------------------------------

def rotation_outcome(prices, start, end):
    """What ETH/BTC actually did, independent of whether anything was readable.

    This is the half of the study that always works, and it is reported first
    in each window for that reason: the reader gets the outcome even where the
    framework has no opinion to compare it against.
    """
    days = [d for d in daterange(start, end) if d in prices]
    if len(days) < 2:
        return None
    first, last = prices[days[0]], prices[days[-1]]
    peak_day = max(days, key=lambda d: prices[d])
    trough_day = min(days, key=lambda d: prices[d])
    # Worst level AFTER the peak, not the window low. That is the drawdown a
    # holder who rode the rotation would actually have taken; the window range
    # would flatter or damn the episode depending only on where it was cut.
    after = [d for d in days if d >= peak_day]
    low_after = min(after, key=lambda d: prices[d]) if after else peak_day
    return {
        "days": len(days),
        "start_date": days[0], "start": first,
        "end_date": days[-1], "end": last,
        "change_pct": (last / first - 1) * 100 if first else None,
        "peak_date": peak_day, "peak": prices[peak_day],
        "peak_gain_pct": (prices[peak_day] / first - 1) * 100 if first else None,
        "trough_date": trough_day, "trough": prices[trough_day],
        "drawdown_from_peak_pct": (
            (prices[low_after] / prices[peak_day] - 1) * 100
            if prices.get(peak_day) else None),
        "drawdown_low_date": low_after,
        # When the window closes on its own high there is no post-peak
        # observation inside it. Reporting that as a 0.0% drawdown would be a
        # fabricated reassurance, so the flag makes the caller say "not yet
        # observed" instead.
        "peak_is_last_day": low_after == peak_day,
    }


def follow_through(prices, end, days=30):
    """ETH/BTC change in the `days` after the window closes.

    Window B ends on its own high, so the window figures alone would leave the
    reader thinking the rotation was still running when it closed. Whether it
    kept running is knowable from the same price series, and withholding it
    because it falls outside a boundary this study chose would be a framing
    choice, not a data limit.
    """
    a = prices.get(end)
    after = (datetime.date.fromisoformat(end)
             + datetime.timedelta(days=days)).isoformat()
    b = prices.get(after)
    if a is None or b is None or not a:
        return None
    return {"from": end, "to": after, "days": days,
            "change_pct": (b / a - 1) * 100, "level": b}


# -- coverage floor scan -----------------------------------------------------

def coverage_floor_scan(year, prices, series, fng, btc=None):
    """Does ladder.COVERAGE_FLOOR hold on ANY day of `year`?

    Scanned over the whole year rather than the two windows, because "frozen
    through both altseasons" is a weaker claim than "frozen every day of the
    year" and the data supports the stronger one.
    """
    days = daterange("%s-01-01" % year, "%s-12-31" % year)
    rows = [score_date(d, prices, series, fng, btc) for d in days]
    covs = [r["ladder_coverage"] for r in rows]
    above = [r for r in rows if r["ladder_coverage"] >= ladder.COVERAGE_FLOOR]
    reachable = [r for r in rows if r["gate_reachable"]]
    return {
        "days": len(rows),
        "floor": ladder.COVERAGE_FLOOR,
        "max_coverage": max(covs) if covs else 0.0,
        "min_coverage": min(covs) if covs else 0.0,
        "days_above_floor": len(above),
        "days_gate_could_reach_threshold": len(reachable),
        "gate_threshold": dimensions.TIER_A_THRESHOLD,
    }


# -- reporting ---------------------------------------------------------------

def _fmt_cell(payload):
    """(value, fire) for one signal cell.

    Three states, never two: a value that fired, a value that did not, and a
    value that exists but carries no scoreable vote ('?'). Collapsing the
    third into 'did not fire' is how an unreadable signal becomes a silent no.
    """
    if payload.get("signal") is None:
        return "     --", "  --"
    val = payload["signal"]
    text = "%7.2f" % val if abs(val) < 100000 else "%7.0f" % val
    vote = payload.get("vote")
    if vote is None:
        return text, "   ?"
    return text, ("FIRE" if vote else "   .")


def render(prices, series, fng, notes, btc=None):
    lines = []
    add = lines.append
    n_total = len(dimensions.TIER_A_SIGNALS)
    reconstructable = [k for k, _ in COLUMNS if k not in ABSENCE_REASONS]

    add("=" * 118)
    add("EVENT STUDY - THE 2021 ALTSEASONS vs THE CURRENT SIGNAL SET")
    add("SHADOW ONLY, governs nothing. Offline: every number below comes from "
        "analysis/. Nothing was fetched.")
    add("=" * 118)

    # -- 1. inventory ------------------------------------------------------
    add("")
    add("1. DATA INVENTORY - what actually exists on disk")
    add("-" * 118)
    for label, note in notes:
        add("   %-27s %s" % (label, note))

    add("")
    add("   Reach back into %s:" % STUDY_YEAR)
    add("     %-34s %3d of 365 days" % (
        "ethbtc.json", len([d for d in prices if d.startswith(STUDY_YEAR)])))
    add("     %-34s %3d of 365 days" % (
        ".cache fear_greed",
        len([d for d in fng if d.startswith(STUDY_YEAR)])))
    for name, data in sorted(series.items()):
        n = len([d for d in data if d.startswith(STUDY_YEAR)])
        add("     %-34s %3d of 365 days   (series starts %s)"
            % ("series.json " + name, n, min(data) if data else "-"))

    # -- 2. availability ---------------------------------------------------
    add("")
    add("2. TIER A SIGNAL AVAILABILITY IN %s  ->  %d of %d = %.1f%%"
        % (STUDY_YEAR, len(reconstructable), n_total,
           len(reconstructable) / n_total * 100))
    add("-" * 118)
    for key, short in COLUMNS:
        if key in ABSENCE_REASONS:
            kind, why = ABSENCE_REASONS[key]
            add("   %-24s %-5s ABSENT   [%s] %s" % (key, short, kind, why))
        else:
            add("   %-24s %-5s PRESENT  reconstructed from data on disk"
                % (key, short))
    add("")
    add("   The gate needs %d of %d Tier A signals to fire "
        "(dimensions.TIER_A_THRESHOLD)."
        % (dimensions.TIER_A_THRESHOLD, n_total))
    add("   With %d scoreable, the maximum possible %s tally is %d. The "
        "threshold is unreachable by ARITHMETIC,"
        % (len(reconstructable), STUDY_YEAR, len(reconstructable)))
    add("   not by market conditions. No 2021 reading, however extreme, could "
        "have fired this gate.")

    # -- windows -----------------------------------------------------------
    for tag, start, end, title in WINDOWS:
        add("")
        add("=" * 118)
        add("WINDOW %s : %s   (%s -> %s)" % (tag, title, start, end))
        add("=" * 118)

        out = rotation_outcome(prices, start, end)
        add("")
        add("   3%s. WHAT THE ROTATION ACTUALLY DID - ETH/BTC, needs no signal "
            "to compute" % tag)
        add("   " + "-" * 114)
        if out is None:
            add("     no ETH/BTC data in this window")
        else:
            add("     %-26s %s   %.6f" % ("open", out["start_date"], out["start"]))
            add("     %-26s %s   %.6f" % ("close", out["end_date"], out["end"]))
            add("     %-26s %+.1f%%" % ("window change", out["change_pct"]))
            add("     %-26s %s   %.6f   (%+.1f%% from open)"
                % ("peak", out["peak_date"], out["peak"], out["peak_gain_pct"]))
            add("     %-26s %s   %.6f" % ("trough", out["trough_date"],
                                          out["trough"]))
            if out["peak_is_last_day"]:
                add("     %-26s not observed - the window closes on its own "
                    "high" % "drawdown after peak")
            else:
                add("     %-26s %+.1f%%   (%s -> %s)"
                    % ("drawdown after peak", out["drawdown_from_peak_pct"],
                       out["peak_date"], out["drawdown_low_date"]))
            add("     %-26s %d" % ("days priced", out["days"]))
            ft = follow_through(prices, end)
            if ft is None:
                add("     %-26s no price %d days after the window"
                    % ("follow-through", 30))
            else:
                add("     %-26s %+.1f%%   (%s -> %s, outside the window, "
                    "shown so the close is not mistaken for the outcome)"
                    % ("follow-through +30d", ft["change_pct"], ft["from"],
                       ft["to"]))

        rows = [score_date(d, prices, series, fng, btc)
                for d in daterange(start, end)]

        # -- dated table ---------------------------------------------------
        add("")
        add("   4%s. DATED TABLE - value, fire, and the coverage that existed "
            "AT THE TIME" % tag)
        add("   " + "-" * 114)
        add("        --   no data for that signal on that date. The column is "
            "kept so the blanks are countable.")
        add("        ?    value readable but not scoreable - its vote rule "
            "needs a reference window not archived here.")
        add("        gate%   Tier A signals carrying a readable vote, out of "
            "9.")
        add("        ladd%   ladder.compute_t coverage in dimension-capped "
            "units; FROZEN when below the 70% floor.")
        add("")

        head1 = "   %-11s %9s" % ("date", "ethbtc")
        head2 = "   %-11s %9s" % ("", "")
        for _, short in COLUMNS:
            head1 += " %7s %4s" % (short, "")
            head2 += " %7s %4s" % ("value", "fire")
        head1 += " %6s %6s %7s" % ("gate%", "ladd%", "ladder")
        head2 += " %6s %6s %7s" % ("", "", "")
        add(head1)
        add(head2)

        for r in rows:
            px = "%9.6f" % r["ethbtc"] if r["ethbtc"] is not None else "       --"
            line = "   %-11s %s" % (r["date"], px)
            for key, _ in COLUMNS:
                val, fire = _fmt_cell(r["signals"][key])
                line += " %7s %4s" % (val, fire)
            line += " %5.1f%% %5.1f%% %7s" % (
                r["gate_coverage_pct"], r["ladder_coverage"] * 100,
                "OK" if r["ladder_measurable"] else "FROZEN")
            add(line)

        # -- window summary ------------------------------------------------
        covs = [r["gate_coverage_pct"] for r in rows]
        lcovs = [r["ladder_coverage"] * 100 for r in rows]
        add("")
        add("   5%s. WINDOW SUMMARY" % tag)
        add("   " + "-" * 114)
        add("     days in window                          %d" % len(rows))
        add("     gate coverage      min / max            %.1f%% / %.1f%%"
            % (min(covs), max(covs)))
        add("     ladder coverage    min / max            %.1f%% / %.1f%%   "
            "(floor %.0f%%)"
            % (min(lcovs), max(lcovs), ladder.COVERAGE_FLOOR * 100))
        add("     days ladder was measurable              %d of %d"
            % (sum(1 for r in rows if r["ladder_measurable"]), len(rows)))
        add("     days gate could REACH its threshold     %d of %d"
            % (sum(1 for r in rows if r["gate_reachable"]), len(rows)))
        add("     days gate would have fired              %d of %d"
            % (sum(1 for r in rows if r["gate_would_fire"]), len(rows)))
        add("")
        add("     Fire rate per signal, over the days it was READABLE. The "
            "denominator is readable days, not")
        add("     window days - a signal absent all window has no rate at all, "
            "and says so rather than showing 0%.")
        for key, _ in COLUMNS:
            readable = [r for r in rows
                        if r["signals"][key].get("vote") is not None]
            if not readable:
                kind = ABSENCE_REASONS.get(key, ("NO DATA",))[0]
                add("       %-24s  n/a - readable on 0 of %d days  [%s]"
                    % (key, len(rows), kind))
                continue
            fired = sum(1 for r in readable if r["signals"][key]["vote"])
            add("       %-24s  %3d of %3d readable days fired (%.0f%%)"
                % (key, fired, len(readable), fired / len(readable) * 100))

    # -- 6. coverage floor -------------------------------------------------
    scan = coverage_floor_scan(STUDY_YEAR, prices, series, fng, btc)
    add("")
    add("=" * 118)
    add("6. COVERAGE FLOOR CHECK - does ladder.COVERAGE_FLOOR (%.0f%%) hold "
        "on ANY day of %s?" % (scan["floor"] * 100, STUDY_YEAR))
    add("=" * 118)
    add("   days examined                           %d (all of %s)"
        % (scan["days"], STUDY_YEAR))
    add("   ladder coverage   min .. max            %.1f%% .. %.1f%%"
        % (scan["min_coverage"] * 100, scan["max_coverage"] * 100))
    add("   days at or above the %.0f%% floor         %d"
        % (scan["floor"] * 100, scan["days_above_floor"]))
    add("   days the gate could reach %d of 9        %d"
        % (scan["gate_threshold"], scan["days_gate_could_reach_threshold"]))
    add("")
    if scan["days_above_floor"] == 0:
        add("   The floor holds on ZERO days. The ladder would have been "
            "FROZEN for the whole of %s, including" % STUDY_YEAR)
        add("   every day of both altseasons. next_state() would have returned")
        add('   "frozen - coverage %.2f%% below the %.0f%% floor" %d times and '
            "never left its starting rung."
            % (scan["max_coverage"] * 100, scan["floor"] * 100, scan["days"]))
        add("")
        add("   This matters more than any individual signal. A design whose "
            "safety rule is 'refuse to act on a")
        add("   thin base' will refuse to act for an entire cycle if the base "
            "was thin for an entire cycle - and")
        add("   the ladder's own docstring priced that at 49.2% of days frozen "
            "under a 15% outage. 2021 is the")
        add("   100%-outage case it never modelled.")
    else:
        add("   The floor holds on %d day(s) - see the dated tables above."
            % scan["days_above_floor"])

    # -- 7. conclusion -----------------------------------------------------
    add("")
    add("=" * 118)
    add("7. CONCLUSION")
    add("=" * 118)
    add("")
    add("   The current signal set CANNOT be evaluated against the 2021 "
        "altseasons. %d of its %d Tier A signals"
        % (n_total - len(reconstructable), n_total))
    add("   have no readable value on any date in either window. Coverage is "
        "%.1f%%, against a gate that needs 5 of 9"
        % (len(reconstructable) / n_total * 100))
    add("   to fire and a ladder that needs 70% to act at all. Both fail on "
        "the inputs, not on the market.")
    add("")
    add("   Three consequences, in increasing order of how much they matter:")
    add("")
    add("   (a) The gate never fires in 2021 - but that is not a result. With "
        "at most %d scoreable signals against"
        % len(reconstructable))
    add("       a threshold of %d, 'did not fire' carries no information about "
        "2021 whatsoever. Nobody should"
        % dimensions.TIER_A_THRESHOLD)
    add("       read the empty column as the gate correctly staying out.")
    add("")
    add("   (b) The ladder is frozen every day of the year, so ladder.py's "
        "Monte Carlo - block-bootstrapped from")
    add("       1366 days starting 2022-11 - has never been exposed to a "
        "2021-shaped move. Its 0.00 whipsaws/yr")
    add("       is a property of the 14-day dwell, not evidence it survives an "
        "altseason it has never seen.")
    add("")
    add("   (c) One Tier A signal, eth_etf_flows, is PERMANENTLY unscoreable "
        "against 2021: US spot ETH ETFs did")
    add("       not exist until 2024-07-23. No backfill fixes that. Any future "
        "claim that this framework 'would")
    add("       have caught 2021' is capped at 8 of 9 signals before the work "
        "even starts.")
    add("")
    add("   What is NOT claimed here: that the thresholds are wrong. This "
        "study cannot tell, and does not guess.")
    add("   It says only that the evidence usually cited for them - two 2021 "
        "episodes - is evidence this signal")
    add("   set has never been tested against, and that the calibration rests "
        "on memory rather than measurement.")
    add("")
    add("   The cheapest fix is bounded: a BGeometrics backfill of MVRV Z, "
        "NVT, SSR and STH-RP to 2021, plus a")
    add("   daily BTC close for the STH comparison. At 10 requests/hour that "
        "is hours of waiting, not weeks of")
    add("   work, and it would take the scoreable count from %d to 6 of 9 - "
        "enough to make the gate's threshold" % len(reconstructable))
    add("   reachable and the ladder's floor testable. Funding and netflow "
        "archives are the harder half and may")
    add("   not be free at all; if they are not, say so in the spec rather "
        "than leaving them as assumed evidence.")
    add("")
    return lines


def main():
    prices, p_note = load_ethbtc()
    series, s_note = load_series()
    fng, f_note = load_fear_greed()
    btc, b_note = load_btc_price()

    notes = [
        ("analysis/ethbtc.json", p_note),
        ("analysis/series.json", s_note),
        ("analysis/.cache F&G", f_note),
        ("analysis/.cache BTC close", b_note),
    ]

    if not prices:
        print("analysis/ethbtc.json is missing. This study needs it and will "
              "not fetch. Aborting.")
        return 1

    text = "\n".join(render(prices, series, fng, notes)) + "\n"

    os.makedirs(ANALYSIS, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(text)

    print(text)
    print("written to %s" % os.path.normpath(OUT_PATH))
    return 0


if __name__ == "__main__":
    sys.exit(main())
