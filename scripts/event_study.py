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
read itself. Only two Tier A signals can be reconstructed for 2021 from
anything on disk.

Counts are read from dimensions at runtime and never written as literals in
this file. fear_greed was demoted from Tier A on walk-forward evidence and
every hardcoded "9" here became wrong on the same day, which is why the size
of the Tier A set is now always computed.

With at most 2 scoreable signals the 2021 tally is not merely low - it is
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
  VALUE ON DISK,       a number exists for the day but the reference window
  NOT SCOREABLE        its vote rule needs does not: NVT wants the 90 prior
                       daily points, SSR the value 30 days back, STH-RP a BTC
                       close. Empty in 2021 today, because series.json reaches
                       no day of it - but MEASURED each run, so a partial
                       backfill prints this reason instead of inheriting the
                       hand-written "no history" one.

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
  the 10% threshold should be read as ambiguous rather than decided. This
  caveat is PRINTED in section 1 of the report as well as stated here - a
  caveat only the author reads is not a caveat.
- fear_greed comes from the alternative.me response already cached under
  analysis/.cache/. It genuinely covers 2021 - it is the one signal in the set
  with a free complete archive - and that is exactly why its presence must not
  be read as reassurance about the other eight.
- analysis/.cache/ is GITIGNORED, so the F&G archive and the daily BTC close
  are local-only inputs and the headline depends on them. A fresh checkout
  measures one readable Tier A signal, not two. Section 1 of the report states
  this with both figures measured, and the CI workflow skips regenerating the
  report when its F&G fetch fails, so a thin run cannot overwrite a committed
  thicker one.

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
MVRV_Z_THRESHOLD = 3.0      # fetch_signals mvrv_z_above
MOMENTUM_WINDOW_DAYS = 14
# The two reference windows the gate's own rules use. Held here so the
# reconstruction below applies the SAME window the live fetcher does; a study
# that quietly used a shorter one would be testing a different rule.
NVT_AVG_DAYS = 90           # fetch_signals: NVT vs its own 90-day average
SSR_LOOKBACK_DAYS = 30      # fetch_signals ssr_falling_over_days

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

# The ladder's rotation axis is NOT the gate's Tier A set. Three of
# ladder.ROTATION_SIGNALS - btc_dominance, alt_dominance, altseason_index -
# are not Tier A signals at all, so ABSENCE_REASONS above never mentions them.
# An earlier version of this study asserted 14.29% ladder coverage in 2021
# without naming them anywhere, which is the same silent-omission failure the
# study exists to criticise. They get their own reasons here, and section 2R
# prints the rotation set with the same blank-counting discipline as Tier A.
ROTATION_ONLY_ABSENCE = {
    "btc_dominance": ("NO HISTORY ON DISK",
                      "CoinGecko /global is point-in-time only; this repo "
                      "archives no dominance history"),
    "alt_dominance": ("NO HISTORY ON DISK",
                      "derived from the same point-in-time /global call"),
    "altseason_index": ("NO HISTORY ON DISK",
                        "needs CoinGecko price_change_percentage=90d, which "
                        "the keyless tier silently omits - the signal degrades "
                        "to needs_key TODAY, let alone in 2021"),
}


def absence_reason(key):
    """Recorded reason a signal cannot be reconstructed, or None.

    One lookup over both dicts so a signal that sits in both the gate and the
    ladder cannot end up with two different stories about why it is blank.
    """
    return ABSENCE_REASONS.get(key) or ROTATION_ONLY_ABSENCE.get(key)


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

    Every matching cache file is merged, LAST-WINS by sorted path. That does
    NOT remove the dependence on filename ordering: on a day where two cache
    files disagree, the alphabetically last file still decides. An earlier
    version of this docstring claimed the merge removed that dependence, which
    was wrong. So the merge counts disagreements instead of hiding them, and
    the count is reported in the note that section 1 of the report prints.

    On the files currently on disk (fng.json and a URL-named copy of the same
    download, different md5) the conflict count is 0 across all shared days,
    so no number in this study depends on the ordering. The counter exists so
    that stops being an assumption nobody checks.
    """
    cache_dir = cache_dir or os.path.join(ANALYSIS, ".cache")
    hits = sorted(glob.glob(os.path.join(cache_dir, "*fng*.json")))
    if not hits:
        return {}, "MISSING: no *fng*.json in %s - F&G counts as absent" % cache_dir
    out = {}
    conflicts = []
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
                val = float(entry["value"])
            except (KeyError, TypeError, ValueError):
                continue
            if day in out and out[day] != val:
                conflicts.append((day, out[day], val, os.path.basename(path)))
            out[day] = val
    if not out:
        return out, "cache present but unreadable - F&G counts as absent"
    # Both branches FORMAT the count. The no-conflict branch used to print the
    # literal string "0 disagreements", which was only ever correct because the
    # branch below overwrote the whole note - reorder or merge those two
    # statements and the report prints a fabricated zero, with the test that
    # asserts on the same literal still green.
    note = "%d days, %s -> %s (%d cache file(s), %d disagreements)" % (
        len(out), min(out), max(out), len(hits), len(conflicts))
    if conflicts:
        day, old, new, fname = conflicts[0]
        note = ("%d days, %s -> %s (%d cache file(s), %d disagreements)  "
                "** WARNING: %d day(s) disagree between cache files; resolved "
                "LAST-WINS by sorted filename, so those days depend on how a "
                "sibling script named its download. First: %s %s -> %s from "
                "%s **"
                % (len(out), min(out), max(out), len(hits), len(conflicts),
                   len(conflicts), day, old, new, fname))
    return out, note


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


def _shift(date, days):
    """`date` moved by `days`, or None if `date` is not an ISO date.

    Returns None rather than raising so a caller can feed the result straight
    into a dict lookup: a bad date becomes a missing reference, never a
    silently substituted one.
    """
    try:
        return (datetime.date.fromisoformat(date)
                + datetime.timedelta(days=days)).isoformat()
    except (TypeError, ValueError):
        return None


def _prior_window(dated, date, days):
    """The `days` daily values immediately BEFORE `date`, or None if any is missing.

    All-or-nothing on purpose. Averaging over whatever days survived would
    quietly shorten the window and therefore change the rule being tested -
    the same reason momentum_14d refuses to reach for a nearest neighbour.
    The cost is that one missing day inside three months blanks the vote; that
    is the honest reading, not a conservative one.
    """
    out = []
    for back in range(days, 0, -1):
        val = dated.get(_shift(date, -back))
        if val is None:
            return None
        out.append(val)
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
    # Seed every key this module can PRINT, not only those that can VOTE.
    #
    # These were the same set until fear_greed was demoted from Tier A on
    # walk-forward evidence. COLUMNS still prints it - correctly, since a
    # signal that stopped voting is still context worth seeing on a dated
    # table - but build_row seeded only Tier A plus the rotation axis, so
    # render() raised KeyError on a column it was asked to draw.
    #
    # Deriving the seed set from COLUMNS as well means a future promotion or
    # demotion changes what VOTES without breaking what is DISPLAYED.
    signals = {}
    for key in (set(dimensions.TIER_A_SIGNALS)
                | set(ladder.ROTATION_SIGNALS)
                | {k for k, _ in COLUMNS}):
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

    # Everything below reads analysis/series.json, which starts 2022-08-31 and
    # so covers no day of either 2021 window today. The paths are written for
    # the data, not for the year: each one scores as soon as its own inputs are
    # on disk, so a real backfill moves the verdict without an edit here. A
    # `vote: None` hardcoded per signal would instead leave section 2 printing
    # "ABSENT [NO HISTORY ON DISK]" above rows showing live values - exactly
    # the drift the measured-availability tables exist to end.

    # MVRV Z needs no reference window at all: fetch_signals scores it as
    # `val > THRESHOLDS['mvrv_z_above']`, a bare scalar comparison of the same
    # shape as fear_greed > 60, which this study already scores. Grouping it
    # with NVT and SSR was wrong about the rule, not merely conservative.
    mvrv = series.get("mvrv_z_score", {}).get(date)
    if mvrv is not None:
        signals["mvrv_z_score"] = {
            "status": "ok", "source_age_days": 0,
            "signal": mvrv,
            "vote": mvrv > MVRV_Z_THRESHOLD,
            "note": "scored against the bare %.1f threshold - no reference "
                    "window needed" % MVRV_Z_THRESHOLD,
        }

    # NVT votes against its OWN trailing 90-day average, rebuilt here from the
    # 90 prior daily points. "Value on disk but window short" is a different
    # blank from "no value at all", and the note says which one produced it,
    # because the two cost different amounts of work to fix.
    nvt = series.get("nvt", {}).get(date)
    if nvt is not None:
        prior = _prior_window(series.get("nvt", {}), date, NVT_AVG_DAYS)
        if prior is None:
            signals["nvt"] = {
                "status": "ok", "source_age_days": 0,
                "signal": nvt, "vote": None,
                "note": "value on disk, but the %d prior daily points its "
                        "average needs are not - reported, not scored"
                        % NVT_AVG_DAYS,
            }
        else:
            avg = sum(prior) / len(prior)
            signals["nvt"] = {
                "status": "ok", "source_age_days": 0,
                "signal": nvt, "avg_90d": round(avg, 3),
                "vote": nvt > avg,
                "note": "scored against its own %d-day average, rebuilt from "
                        "the %d prior days on disk"
                        % (NVT_AVG_DAYS, NVT_AVG_DAYS),
            }

    # SSR votes falling-over-30-days: today against the value 30 calendar days
    # back. One prior point, not a window - far less history than NVT needs,
    # which is worth separating rather than lumping both into "no reference".
    # `ref_value` is the field the live fetcher returns and the field
    # ladder.LADDER_RULES reads, so filling it here also lets SSR count toward
    # ladder coverage instead of only toward the gate.
    ssr_map = series.get("stablecoin_supply_ratio", {})
    ssr = ssr_map.get(date)
    if ssr is not None:
        ref = ssr_map.get(_shift(date, -SSR_LOOKBACK_DAYS))
        if ref is None:
            signals["stablecoin_supply_ratio"] = {
                "status": "ok", "source_age_days": 0,
                "signal": ssr, "vote": None,
                "note": "value on disk, but the value %d days earlier that its "
                        "falling test compares against is not - reported, not "
                        "scored" % SSR_LOOKBACK_DAYS,
            }
        else:
            signals["stablecoin_supply_ratio"] = {
                "status": "ok", "source_age_days": 0,
                "signal": ssr, "ref_value": ref,
                "lookback_days": SSR_LOOKBACK_DAYS,
                "vote": ssr < ref,
                "note": "scored against the value %d days earlier, both on "
                        "disk" % SSR_LOOKBACK_DAYS,
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


# -- measured availability ---------------------------------------------------
#
# ABSENCE_REASONS is hand-maintained prose. Deriving the PRESENT/ABSENT table
# from it would mean the table keeps printing "ABSENT" after a backfill lands,
# while the dated rows below it show live values and nothing complains. So the
# tables are MEASURED from the same build_signals() the dated rows use, and the
# hand-written dict supplies only the REASON beside a blank it did not create.
# The tests assert the measured set and the dict still agree, which is the one
# place a drift can be caught.

def measure_tier_a_availability(prices, series, fng, btc=None, windows=None):
    """Tier A keys carrying a scoreable vote on at least one day of a window.

    A vote, not a value: mvrv_z_score, nvt and ssr can print a number whose
    vote rule needs a reference window this study does not archive, and a
    number nobody can score does not make the gate readable.
    """
    windows = WINDOWS if windows is None else windows
    present = set()
    for _, start, end, _ in windows:
        for day in daterange(start, end):
            signals = build_signals(day, prices, series, fng, btc)
            for key in dimensions.TIER_A_SIGNALS:
                if signals[key].get("vote") is not None:
                    present.add(key)
    return present


def measure_tier_a_values(prices, series, fng, btc=None, windows=None):
    """Tier A keys carrying a VALUE but no scoreable vote, with the reason.

    The gap between this and measure_tier_a_availability() is the second kind
    of blank: the number is on disk, the reference window its vote rule needs
    is not. Section 2 prints that differently from "no history at all",
    because the two cost different amounts of work to fix - and because
    printing the hand-written "series.json starts 2022-08-31" over a row that
    visibly shows a value is precisely the drift this study criticises.
    """
    windows = WINDOWS if windows is None else windows
    out = {}
    for _, start, end, _ in windows:
        for day in daterange(start, end):
            signals = build_signals(day, prices, series, fng, btc)
            for key in dimensions.TIER_A_SIGNALS:
                payload = signals[key]
                if (payload.get("signal") is not None
                        and payload.get("vote") is None):
                    out.setdefault(key, payload.get("note")
                                   or "value on disk, no scoreable vote")
    return out


# The backfill section 7 prescribes, applied to a COPY of the series so the
# study can MEASURE what that work would buy instead of asserting a number. An
# earlier version of this report claimed the scoreable count would go 2 -> 6
# and the module itself refuted it: with the vote paths as they then were, the
# same injection moved it to 3.
#
# The filled values are constants. They are never printed, never scored into
# any verdict above, and never returned to the caller. The only question asked
# of them is "would this key then carry a scoreable vote", which depends on
# the SHAPE of the history - whether the day and its reference window exist -
# and not on the levels. Using them for anything else would be the silent
# proxy this module refuses to make.
BACKFILL_KEYS = ("mvrv_z_score", "nvt", "stablecoin_supply_ratio",
                 "sth_realized_price")
BACKFILL_PLACEHOLDER = 1.0


def synthetic_backfill(series, windows=None, pad_days=None):
    """Copy of `series` with BACKFILL_KEYS filled across the windows.

    Padded back by `pad_days` (default: NVT's 90-day average window) so the
    reference windows of the first days in each window exist too. Without the
    pad the measurement would understate the backfill by blanking NVT and SSR
    on exactly the days the study looks at.
    """
    windows = WINDOWS if windows is None else windows
    pad = NVT_AVG_DAYS if pad_days is None else pad_days
    out = {k: dict(v) for k, v in series.items()}
    for _, start, end, _ in windows:
        first = _shift(start, -pad) or start
        for day in daterange(first, end):
            for key in BACKFILL_KEYS:
                out.setdefault(key, {}).setdefault(day, BACKFILL_PLACEHOLDER)
    return out


def montecarlo_basis():
    """Days and start date behind ladder.py's Monte Carlo - derived, not quoted.

    Section 7 used to state "1366 days starting 2022-11" as prose. That was
    correct when written and would have gone stale silently as series.json
    grows, which is the same fault the measured-availability tables were built
    to remove. Returns None when series.json is absent or malformed, and the
    caller then cites analysis/montecarlo.txt as the source of record rather
    than printing a number it could not check.
    """
    try:
        import montecarlo
        dates, raw = montecarlo.load_series()
        votes = montecarlo.to_votes(raw, dates)
    except Exception:
        return None
    if not votes or len(votes) > len(dates):
        return None
    return {"days": len(votes), "first": dates[len(dates) - len(votes)]}


def measure_rotation_availability(prices, series, fng, btc=None, windows=None):
    """Rotation keys the LADDER could measure on at least one day of a window.

    Uses ladder._measurable, the ladder's own test, rather than a second
    definition of availability that could disagree with the coverage figure
    printed two columns away.
    """
    windows = WINDOWS if windows is None else windows
    present = set()
    for _, start, end, _ in windows:
        for day in daterange(start, end):
            signals = build_signals(day, prices, series, fng, btc)
            for key in ladder.ROTATION_SIGNALS:
                if ladder._measurable(signals.get(key), key):
                    present.add(key)
    return present


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

    # Measured, not asserted: which signals actually produce a scoreable vote
    # somewhere in the two windows, using the same builder the dated rows use.
    present = measure_tier_a_availability(prices, series, fng, btc)
    reconstructable = [k for k, _ in COLUMNS if k in present]
    rot_present = measure_rotation_availability(prices, series, fng, btc)
    # Blanks of the second kind: a value on disk whose vote rule's reference
    # window is not. Empty today - series.json reaches no day of 2021 - but
    # measured rather than assumed, so a partial backfill prints its own
    # reason instead of inheriting the hand-written "no history" one.
    values_only = measure_tier_a_values(prices, series, fng, btc)

    # What a fresh checkout would report. analysis/.cache is gitignored, so the
    # F&G archive and the BTC close are local-only inputs and the headline
    # below depends on them. Measured by re-running the same scan with both
    # caches emptied, because a caveat carrying a number somebody guessed is
    # not much better than no caveat.
    present_no_cache = measure_tier_a_availability(prices, series, {}, {})

    # What the backfill section 7 prescribes would actually buy, measured on a
    # synthetic copy. See synthetic_backfill() for why constants are safe here
    # and nowhere else.
    bf_series = synthetic_backfill(series)
    bf_present = measure_tier_a_availability(prices, bf_series, fng, btc)
    bf_best = max((ladder.compute_t(build_signals(d, prices, bf_series, fng, btc))
                   for _, st, en, _ in WINDOWS for d in daterange(st, en)),
                  key=lambda t: t["coverage"])

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
    add("   WHERE THESE INPUTS LIVE - the headline below depends on a "
        "GITIGNORED directory")
    add("   " + "-" * 114)
    add("     analysis/ethbtc.json and analysis/series.json are COMMITTED, so "
        "every reader sees the same bytes.")
    add("     The Fear & Greed archive and the daily BTC close are read from "
        "analysis/.cache/, which is not -")
    add("     .gitignore excludes that directory.")
    # Both figures are measured, so they can legitimately coincide - and when
    # they do, the "instead of" phrasing degenerates into "1 of 8 instead of
    # the 1 of 8", which reads as an unproofread template rather than a
    # measurement. Branch on the comparison instead of asserting a gap that
    # may not exist. It stopped existing the day fear_greed left Tier A.
    if len(present_no_cache) == len(reconstructable):
        add("     A fresh checkout has neither file - but on THIS checkout "
            "that costs nothing:")
        add("     %d of %d readable Tier A signals either way, so the figure "
            "in section 2 already IS"
            % (len(reconstructable), n_total))
        add("     the fresh-checkout figure. Both are measured, not quoted.")
    else:
        add("     A fresh checkout has neither file, and this same study then "
            "measures")
        add("     %d of %d readable Tier A signals instead of the %d of %d "
            "printed in section 2 below - a worse"
            % (len(present_no_cache), n_total, len(reconstructable), n_total))
        add("     number for a reason that has nothing to do with 2021. Both "
            "figures are measured, not quoted.")
    add("     CI repopulates F&G by curl from alternative.me (keyless, and NOT "
        "the rate-limited BGeometrics")
    add("     host) before running, and skips this report entirely if that "
        "fetch fails, so a thin run cannot")
    add("     overwrite a committed thicker one. Nothing repopulates the BTC "
        "close: it is a local-only input")
    add("     today. That costs no printed number yet, because series.json "
        "holds no 2021 STH cost basis to")
    add("     pair it with - but it would the day a backfill lands, and that "
        "is when the workflow must fetch it.")

    add("")
    add("   Reach back into %s:" % STUDY_YEAR)
    add("     %-36s %3d of 365 days" % (
        "ethbtc.json", len([d for d in prices if d.startswith(STUDY_YEAR)])))
    add("     %-36s %3d of 365 days" % (
        ".cache fear_greed",
        len([d for d in fng if d.startswith(STUDY_YEAR)])))
    for name, data in sorted(series.items()):
        n = len([d for d in data if d.startswith(STUDY_YEAR)])
        add("     %-36s %3d of 365 days   (series starts %s)"
            % ("series.json " + name, n, min(data) if data else "-"))

    # -- 1b. how eth_btc_momentum is reconstructed -------------------------
    #
    # This caveat used to live only in the module docstring, so a reader of
    # the .txt saw "MOM 19.26 FIRE" with nothing telling them the number came
    # from a different vendor than the live fetcher uses. A caveat only the
    # author reads is not a caveat.
    add("")
    add("   HOW eth_btc_momentum IS RECONSTRUCTED HERE - read before trusting "
        "any MOM cell below")
    add("   " + "-" * 114)
    add("     This study computes it as the percent change from t-%d CALENDAR "
        "days to t, straight off" % MOMENTUM_WINDOW_DAYS)
    add("     analysis/ethbtc.json. The LIVE fetcher instead takes CoinGecko's "
        "last %d DAILY POINTS." % MOMENTUM_WINDOW_DAYS)
    add("     Same rule, different bytes: the builder of ethbtc.json is not in "
        "this repo, so its venue and its")
    add("     close convention are unverified here, and a missing day shifts "
        "CoinGecko's window but not this one.")
    add("     Consequence: a reading within a point or two of the %.1f%% "
        "threshold is AMBIGUOUS, not decided."
        % MOMENTUM_THRESHOLD)
    add("     Readings far from the threshold are safe; the FIRE/. call on a "
        "near-threshold day is not.")

    # -- 2. availability ---------------------------------------------------
    add("")
    add("2. TIER A SIGNAL AVAILABILITY IN %s  ->  %d of %d = %.1f%%"
        % (STUDY_YEAR, len(reconstructable), n_total,
           len(reconstructable) / n_total * 100))
    add("-" * 118)
    add("   PRESENT/ABSENT is MEASURED by scanning both windows for a "
        "scoreable vote, not read off a list.")
    add("   The bracketed reason is the only hand-written part; if a backfill "
        "lands, the verdict moves on its own.")
    for key, short in COLUMNS:
        if key in present:
            add("   %-24s %-5s PRESENT  reconstructed from data on disk"
                % (key, short))
            continue
        if key in values_only:
            # The second kind of blank, and it wins over the hand-written
            # reason: a row that visibly shows a value must never be captioned
            # "NO HISTORY ON DISK". The text comes from the payload the dated
            # rows below were built from, so the two cannot disagree.
            add("   %-24s %-5s ABSENT   [VALUE ON DISK, NOT SCOREABLE] %s"
                % (key, short, values_only[key]))
            continue
        reason = absence_reason(key)
        if reason is None:
            # A blank nobody has explained: either an input this checkout does
            # not have (analysis/.cache is gitignored, so a CI run without the
            # F&G archive lands here) or a reason someone deleted. The print
            # states the fact and refuses to guess which; section 1's loader
            # notes above say whether a file was missing.
            add("   %-24s %-5s ABSENT   [UNEXPLAINED] no scoreable vote on any "
                "day of either window, and no reason recorded - see the loader "
                "notes in section 1" % (key, short))
            continue
        kind, why = reason
        add("   %-24s %-5s ABSENT   [%s] %s" % (key, short, kind, why))
    add("")
    add("   The gate needs %d of %d Tier A signals to fire "
        "(dimensions.TIER_A_THRESHOLD)."
        % (dimensions.TIER_A_THRESHOLD, n_total))
    add("   With %d scoreable, the maximum possible %s tally is %d. The "
        "threshold is unreachable by ARITHMETIC,"
        % (len(reconstructable), STUDY_YEAR, len(reconstructable)))
    add("   not by market conditions. No 2021 reading, however extreme, could "
        "have fired this gate.")

    # -- 2R. rotation availability -----------------------------------------
    #
    # The ladder runs on a DIFFERENT set. Printing its coverage without ever
    # naming the three signals that are unique to it would repeat, on the
    # ladder side, exactly the omission this study criticises on the gate side.
    n_rot = len(ladder.ROTATION_SIGNALS)
    add("")
    add("2R. LADDER ROTATION SIGNAL AVAILABILITY IN %s  ->  %d of %d"
        % (STUDY_YEAR, len(rot_present), n_rot))
    add("-" * 118)
    add("   The ladder's rotation axis is NOT the gate's Tier A set: three of "
        "these signals are not Tier A at all")
    add("   and appear nowhere in section 2. Same measured discipline - "
        "PRESENT means ladder._measurable said so.")
    for key in sorted(ladder.ROTATION_SIGNALS,
                      key=lambda k: (k not in rot_present, k)):
        dim, weight = ladder.ROTATION_SIGNALS[key]
        tag = "D%d w%.1f" % (dim, weight)
        if key in rot_present:
            add("   %-24s %-9s PRESENT  reconstructed from data on disk"
                % (key, tag))
            continue
        reason = absence_reason(key)
        if reason is None:
            add("   %-24s %-9s ABSENT   [UNEXPLAINED] not measurable on any "
                "day of either window, and no reason recorded - see the loader "
                "notes in section 1" % (key, tag))
            continue
        kind, why = reason
        add("   %-24s %-9s ABSENT   [%s] %s" % (key, tag, kind, why))
    add("")
    # Measured, not asserted, and not hardcoded either: the same compute_t the
    # FROZEN column uses, over the same days.
    best = max((ladder.compute_t(build_signals(d, prices, series, fng, btc))
                for _, s, e, _ in WINDOWS for d in daterange(s, e)),
               key=lambda t: t["coverage"])
    add("   Weights are dimension-CAPPED, so the count above does not equal "
        "the coverage figure: D1 holds four")
    add("   signals summing to 3.0 and caps at 3.0. Best coverage measured on "
        "any day of either window:")
    add("     %-36s %.4f of %.4f capped units = %.1f%%   (floor %.0f%%)"
        % ("ladder.compute_t coverage", best["measurable_weight"],
           best["total_weight"], best["coverage"] * 100,
           ladder.COVERAGE_FLOOR * 100))
    add("   That is where the FROZEN column in every dated row below comes "
        "from.")

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
        add("        ?    value readable but NOT scoreable, for one of two "
            "reasons named in the row's note:")
        add("             its reference window is missing (NVT needs the %d "
            "prior days, SSR the value %d days back)"
            % (NVT_AVG_DAYS, SSR_LOOKBACK_DAYS))
        add("             or its second leg is missing (STH-RP needs a BTC "
            "close). MVRV Z needs neither and scores")
        add("             from a bare value, so a '?' can never appear in its "
            "column.")
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
                kind = (absence_reason(key) or ("UNEXPLAINED",))[0]
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
    add("   days the gate could reach %d of %d       %d"
        % (scan["gate_threshold"], len(dimensions.TIER_A_SIGNALS),
           scan["days_gate_could_reach_threshold"]))
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
        "%.1f%%, against a gate that needs %d of %d"
        % (len(reconstructable) / n_total * 100,
           dimensions.TIER_A_THRESHOLD, n_total))
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
    # Derived, not quoted. The literals "1366 days starting 2022-11" were
    # correct when written and would have gone stale silently as series.json
    # grows - the same fault the measured tables above exist to remove.
    basis = montecarlo_basis()
    if basis:
        basis_lines = [
            "       a 2021-shaped move. It is block-bootstrapped from %d real "
            "days starting %s - derived here" % (basis["days"], basis["first"]),
            "       by running montecarlo.to_votes over analysis/series.json, "
            "the same input the Monte Carlo reads.",
        ]
    else:
        basis_lines = [
            "       a 2021-shaped move. Its bootstrap window is the one "
            "recorded in analysis/montecarlo.txt:",
            "       series.json is not readable from here, so no day count is "
            "quoted rather than one nobody checked.",
        ]
    add("   (b) The ladder is frozen every day of the year, so ladder.py's "
        "Monte Carlo has never been exposed to")
    for line in basis_lines:
        add(line)
    add("       Its 0.00 whipsaws/yr is a property of the 14-day dwell, not "
        "evidence it survives an altseason")
    add("       it has never seen.")
    add("")
    add("   (c) One Tier A signal, eth_etf_flows, is PERMANENTLY unscoreable "
        "against 2021: US spot ETH ETFs did")
    add("       not exist until 2024-07-23. No backfill fixes that. Any future "
        "claim that this framework 'would")
    add("       have caught 2021' is capped at %d of %d signals before the work "
        "even starts." % (n_total - 1, n_total))
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
    add("   work. What it would buy is MEASURED here, not estimated: the same "
        "availability scan is re-run against")
    add("   a COPY of series.json filled with placeholder values across both "
        "windows and the %d prior days NVT's"
        % NVT_AVG_DAYS)
    add("   average needs. Only the SHAPE of that history decides the answer; "
        "no placeholder value is printed,")
    add("   scored, or carried into any figure above. An earlier version of "
        "this report asserted a number here")
    add("   that the module itself refuted, which is why it is computed now.")
    add("")
    add("     %-46s %d of %d" % ("scoreable Tier A signals today",
                                 len(reconstructable), n_total))
    add("     %-46s %d of %d   (gained: %s)"
        % ("after the backfill above", len(bf_present), n_total,
           ", ".join(sorted(bf_present - present)) or "nothing"))
    add("     %-46s %d of %d needed  ->  %s"
        % ("gate threshold", dimensions.TIER_A_THRESHOLD, n_total,
           "REACHABLE" if len(bf_present) >= dimensions.TIER_A_THRESHOLD
           else "STILL UNREACHABLE BY ARITHMETIC"))
    add("     %-46s %.1f%% vs the %.0f%% floor  ->  %s"
        % ("best ladder coverage after the backfill",
           bf_best["coverage"] * 100, ladder.COVERAGE_FLOOR * 100,
           "the floor becomes testable"
           if bf_best["coverage"] >= ladder.COVERAGE_FLOOR
           else "STILL FROZEN, the floor stays untestable"))
    add("")
    if bf_best["coverage"] < ladder.COVERAGE_FLOOR:
        add("   Read that second pair carefully: the prescribed backfill is a "
            "GATE fix, not a ladder fix. Of the four")
        add("   series it adds, only SSR sits on the rotation axis, so ladder "
            "coverage rises but stays under the")
        add("   %.0f%% floor and the ladder would still have been frozen "
            "through both altseasons. Making the floor"
            % (ladder.COVERAGE_FLOOR * 100))
        add("   testable against 2021 needs the rotation-only signals - "
            "dominance history and a funding archive -")
        add("   which is the harder and possibly unpurchasable half.")
    else:
        add("   That backfill would make both the gate's threshold and the "
            "ladder's floor testable against 2021.")
    add("")
    add("   Funding, netflow and dominance archives are the half that may not "
        "be purchasable at any price. If they")
    add("   are not, the spec should say so, rather than leaving them standing "
        "as assumed evidence.")
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

    # btc is the second leg of the STH-RP vote. Dropping it here (an earlier
    # version did) changed no printed number only because series.json has no
    # 2021 STH cost basis to pair it with - a silent undercount waiting for a
    # backfill to expose it, which is precisely the failure mode this study
    # was written to document.
    text = "\n".join(render(prices, series, fng, notes, btc)) + "\n"

    os.makedirs(ANALYSIS, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(text)

    print(text)
    print("written to %s" % os.path.normpath(OUT_PATH))
    return 0


if __name__ == "__main__":
    sys.exit(main())
