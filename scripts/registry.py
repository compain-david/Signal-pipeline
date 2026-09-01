#!/usr/bin/env python3
"""
Pre-registration registry for rotation hypotheses - SHADOW ONLY.

The problem this exists to price
--------------------------------
Seven analyses were run over the same four years of data and one of them
produced a perfect 4/4 monotone gradient. It dissolved out of sample
(analysis/oos_test.txt). That is not bad luck, it is arithmetic: run enough
hypotheses over one dataset and the best one looks excellent whether or not
anything real is there. The twentieth hypothesis that "works" is, absent a
counter, indistinguishable from the twentieth draw.

Nothing in this repository counted the draws. Every study wrote down what it
found; none wrote down what it looked for, or how many times. This file is
that counter, and the adoption rule that reads it.

What it stores, and why the ORDER of writing matters
----------------------------------------------------
Each hypothesis carries the direction it is EXPECTED to show, written before
the result is known. A direction recorded afterwards costs nothing and proves
nothing: any outcome confirms a prediction made after the outcome. The whole
value of analysis/registry.json is that the expected direction is immutable
once written - register() refuses to overwrite it, and that refusal is the
single most important line in this module.

How pre-registration is decided, and why it is not a self-declaration
---------------------------------------------------------------------
A flag saying "I promise I registered this first" is worthless. The status is
COMPUTED instead: a hypothesis counts as pre-registered only if its
registration date falls far enough AFTER the last day of the data it is
tested on to leave a full unseen fold. Register today against data that ends
yesterday and the registry files it as post-hoc, whatever the author believes.
The same entry becomes eligible for PRE status later, once new data has
accumulated past its registration date - so the file gets more valuable by
sitting still, which is the only honest way a registry can gain value.

Every hypothesis measured today is POST-HOC. All of them. That is recorded.

The multiplicity bar, its choice, and its weakness
--------------------------------------------------
The bar is Bonferroni: alpha / (number of distinct comparisons ever scored).
It is chosen for one reason - it is the only correction that can be recomputed
from a count alone, with no assumption the data would have to support. Its
weaknesses are real and must be read alongside every verdict:

  - it assumes the comparisons are independent. Here they are not: BTC
    dominance and ETH dominance are near-mirror images of one observation, and
    alt_btc follows alt_eth times eth_btc, so the true family is smaller than
    the count and the bar is too strict.
  - it only counts what was WRITTEN DOWN. Every window width swept, every
    threshold tried by hand and abandoned, is a comparison that never reached
    the file. So the count is a FLOOR on the family, and the bar a ceiling on
    how demanding it should be. An uncounted search is not corrected by any
    arithmetic.
  - it corrects the false-positive rate by destroying power. With a family of
    twenty, a real but modest signal has almost no chance of clearing it. That
    is the price, and it is worth paying only because the alternative here -
    no counter at all - already produced one dissolved gradient.

What the shuffled null actually is, measured rather than assumed
----------------------------------------------------------------
The adoption rule demands that a signal beat its own shuffle. An earlier
version of this module asserted, in a comment, that shuffling "preserves the
fold structure and the value distribution, and destroys only the date-to-value
mapping". The first half of that sentence is FALSE, and this run measures it:
a shuffled series produces far fewer usable folds than the real one, because
wf.direction() returns None on ties and on bands holding fewer than ten
observations, and a scrambled series lands in that state constantly. Section
"LE MELANGE NE CONSERVE PAS LES PLIS" of the report prints the fold
distribution of every null next to the real fold count, so the mismatch is
visible instead of asserted away.

Two consequences are handled rather than mentioned:
  - a draw that yields zero folds produces no test at all. Those draws are
    COUNTED and printed. A null that fails to produce a test on a tenth of its
    draws is itself a result about the design.
  - the p-value is computed only over draws whose fold count MATCHES the real
    one, so the comparison is like for like. When too few draws match, the
    verdict is SOUS_RESOLU: the design could not produce a valid comparison,
    which is neither a pass nor a failure.

A circular-shift null is measured alongside, and only alongside. It preserves
autocorrelation - so it preserves the fold structure much better - and it is
the null rotation_matrix.py uses. It is reported, never a criterion, because
the rule this module was asked for is a shuffle control.

One decision, one number, two artefacts
---------------------------------------
Which null draws a mean and a gap may be built from is decided ONCE, in
summarise_null(), and everything else copies the answer. A previous version
took that decision twice under two different tests - measure() asked "at least
MIN_MATCHED_NULLS matched draws", the report asked "at least one" - and so the
same run published two different numbers for the same cell: the table said 62%
where registry.json said 47.6% on H11, 71% against 54.7% on H10. Criterion 4
turns on 15 points, and nothing told the reader which of the two the rule had
read. A test now compares the report's `ecart` column against registry.json's
`gap` field line by line, because two artefacts of one run disagreeing about
one measurement is worse than either number being wrong.

The same rule refuses to print a mean at all under MIN_MATCHED_NULLS draws.
The old table printed "moyenne 71%" from a single matched draw, next to a
column reading "apparies 1", with nothing connecting the two. A mean of one
observation is not a mean.

The reference the accords are read against
-------------------------------------------
H03 registers the ETH/BTC level as a predictor of the ETH/BTC level. It is a
degenerate predictor and it wins: it takes the highest fold agreement of the
run. That is not a curiosity, it is the calibration this design needed. The
implicit reference for a walk-forward agreement is 50% - two directions
coinciding by chance - and this run measures that the implicit reference is
wrong here, because the whole sample sits inside one ETH/BTC downtrend and a
gradient direction that never changes reproduces itself fold after fold with
no information in play. So agreement is read against the self-prediction
control, never against 50%. An earlier version measured that control and never
drew the conclusion from it, which was the most useful thing this run had to
publish.

The resolution floor: tests that could never have succeeded
------------------------------------------------------------
Two hard limits cap how small a p-value this design can even produce:

  - fold count. Walk-forward agreement is a sequence of coin flips; k folds
    all agreeing has probability 0.5**k under the null. Four folds bottom out
    at 0.0625, so a PERFECT 4/4 run cannot reach 0.05 by itself, ever.
  - the number of null draws that actually produced a comparable test. A
    permutation p cannot go below 1/(S+1), and S here is the REALISED matched
    count, never the nominal draw count. Using the nominal count would claim a
    resolution the run never had, and the floor is the one number that decides
    SOUS_RESOLU against REJETE.

Direction: measured out of sample, on purpose
----------------------------------------------
Criterion 2 compares the registered direction against the MAJORITY SIGN OF THE
PER-FOLD TEST DIRECTIONS - each one measured on a slice the fold's own fit
never saw. The previous version used the gradient over the whole sample, test
folds included, and then placed that in-sample number beside walk-forward
statistics as if it were one of them. The full-sample direction is still
printed, marked in-sample, for one reason: this run it points the OPPOSITE way
on H03 (+1 over the whole sample, -1 across the test folds) and is
unidentifiable on hypotheses where the fold majority is not. The report counts
those two sets rather than naming them from memory. It is the cheapest
demonstration available of why it is not the criterion.

The majority itself is descriptive. It is a vote count, not a test, and the
report prints the split so a 4-3 majority cannot be read as a 4-0 one.

Offline by construction, not by luck
-------------------------------------
forward_study.load_fear_greed() fetches from the network when its cache is
missing. Inheriting that here would mean this module is offline only while one
gitignored file happens to exist. load_fear_greed_offline() reads the cache and
raises if it is absent, so a missing cache is a loud error rather than a silent
HTTP call.

What this governs
-----------------
Nothing. Like ladder.py and the shadow gate, this measures and records; it
changes no allocation. Its output is a verdict list, and the only verdict it
can currently issue for anything measured today is "post-hoc candidate".

What it costs to run
--------------------
Minutes, not seconds: SHUFFLES draws per null mode per scored hypothesis, each
draw a full walk. The measured wall time and the realised draw count are
printed in the report header of every run rather than quoted here, so the
figure cannot go stale. Raising SHUFFLES buys resolution linearly in runtime
and buys nothing against the fold-count floor.

Run: python scripts/registry.py
"""

import datetime
import hashlib
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.join(HERE, "..", "analysis")
sys.path.insert(0, HERE)

import band_study as bs
# For TOP_N only, and only so the basket size cannot be restated here and
# drift from the generator that decides it. Importing is safe: build_rotations
# reaches the network in main(), never at import.
import build_rotations as br
import forward_study as fs
import walkforward as wf
# Imported for two shared constants and one shared null. The alt-basket caveat
# has to be the SAME STRING in both reports: a bias restated in the author's
# own words drifts, and a drifted caveat is how a bias quietly weakens.
import rotation_matrix as rm

SCHEMA_VERSION = 2

# Stamped on every result written. Results already in the file from method 1
# were produced with a null that shuffled over dates the target never covered
# and with an in-sample direction criterion; they stay in the file because
# nothing here is ever rewritten, and they carry no stamp, which is how a
# reader tells them apart from these.
METHOD_VERSION = 2

REGISTRY_PATH = os.path.join(ANALYSIS, "registry.json")
REPORT_PATH = os.path.join(ANALYSIS, "registry_report.txt")
FNG_CACHE = os.path.join(ANALYSIS, ".cache", "fng.json")

ALT_BASKET_CAVEAT = rm.ALT_BASKET_CAVEAT
ALT_MARK = rm.ALT_MARK

FAMILY_ALPHA = 0.05

# A fold is one train/test direction comparison. Below four, 0.5**k already
# exceeds any usable alpha, so the test cannot conclude and is not scored.
MIN_FOLDS = 4

# Floor on agreement, under any entry's own threshold. An entry may demand
# MORE than this; effective_threshold() refuses to let it demand less, because
# a per-hypothesis threshold relaxed after the fact is exactly the free
# parameter this module exists to count.
MIN_AGREEMENT = 0.70

# Points of agreement above the signal's own shuffled control, and it is only
# read when the shuffle produced draws with the SAME fold count as the real
# walk. Comparing a 9-fold agreement rate against the mean of 1-to-5-fold rates
# would be arithmetic on two different experiments: with two folds a rate can
# only be 0, 50 or 100, so a short-fold null is coarse and over-dispersed as
# well as wrong.
MIN_GAP_PTS = 15.0

# Below this many matched draws the null mean is dominated by draw noise and
# the permutation floor sits above any usable bar anyway (1/21 = 0.048). The
# threshold is a judgement call and it is printed with every verdict that it
# decides, so it can be argued with rather than discovered.
MIN_MATCHED_NULLS = 20

# 250 draws per null, per mode. Raising it buys resolution linearly in runtime,
# buys nothing at all against the fold-count floor, and - as this run shows -
# buys nothing against a null that lands on the wrong fold count.
SHUFFLES = 250
SEED = 20260901

# One primary configuration. Sweeping window widths and then reporting the best
# is itself multiple comparison, and it is the mechanism that manufactured the
# original 4/4 gradient. If a sweep is wanted, every arm must be registered and
# counted as its own comparison.
WINDOW, TRAIN_DAYS, TEST_DAYS = 365, 365, 180
HORIZON = 90

NULL_MODES = ("melange", "decalage")

VERDICTS = ("ADOPTE", "CANDIDAT", "REJETE", "SOUS_RESOLU", "NON_TESTABLE")

# Targets whose UNIVERSE is wrong, not whose result is weak. HEAD's
# build_rotations.py rebuilt the alt index and its commit withdrew the alt
# results outright - "retires, pas seulement nuances" - because CoinMetrics
# community carries none of this cycle's major alts, so the index measures a
# 2017-2021 basket whatever the statistics say about it.
#
# This is a different kind of refusal from every other one in this module, and
# it is checked FIRST for that reason. Every other criterion asks how strong
# the evidence is; this one asks whether the measurement is about the question
# at all. A signal can beat its null, clear the corrected bar and still be
# describing the wrong market - and a registry that let a good p-value promote
# it would be counting draws impeccably while pointing the wrong way.
#
# Kept as measured entries rather than deleted, because this file never removes
# anything: a withdrawn hypothesis that disappears leaves no trace that it was
# ever asked, which is the exact failure the registry exists to prevent.
WITHDRAWN_TARGETS = {
    "alt_eth": "univers invalide - l indice alt ne couvre aucun major de ce "
               "cycle (build_rotations.py, HEAD)",
    "alt_btc": "univers invalide - l indice alt ne couvre aucun major de ce "
               "cycle (build_rotations.py, HEAD)",
}


# --- registry file ---------------------------------------------------------

def new_registry(created_on):
    return {"schema_version": SCHEMA_VERSION,
            "created_on": created_on,
            "governs": "rien - shadow, comme ladder.py",
            "entries": [],
            # Unique comparison keys, ever. The family size is len() of this,
            # so re-running the identical test does not inflate the bar while
            # a genuinely new one does.
            "comparisons": []}


def migrate(reg):
    """Raise an older file to the current schema without touching its content.

    Only the version stamp moves. Rewriting old results to the new shape would
    make them look as if they had been measured the new way, which is the one
    thing a registry must never do to its own history.
    """
    if reg.get("schema_version", 1) < SCHEMA_VERSION:
        reg["schema_version"] = SCHEMA_VERSION
    reg.setdefault("comparisons", [])
    reg.setdefault("entries", [])
    return reg


def load(path=REGISTRY_PATH):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return migrate(json.load(f))


def save(reg, path=REGISTRY_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=2, sort_keys=True)
        f.write("\n")


def find(reg, hyp_id):
    for e in reg["entries"]:
        if e["id"] == hyp_id:
            return e
    return None


def register(reg, hyp_id, signal, target, expected_direction,
             success_threshold, registered_on, rationale):
    """Write a hypothesis down. Immutable in its predictive content.

    Re-registering identical content is allowed so the script stays
    re-runnable. Changing the expected direction, the target or the threshold
    is refused: those three fields ARE the prediction, and a prediction
    editable after the measurement is not a prediction. This costs flexibility
    on purpose - fixing a genuine typo means retiring the entry and
    registering a new id, which leaves the abandoned one visible in the file.
    That visibility is the point, not a side effect.
    """
    if expected_direction not in (1, -1):
        raise ValueError("direction attendue: +1 ou -1, recu %r"
                         % (expected_direction,))
    if not 0.0 < success_threshold <= 1.0:
        raise ValueError("seuil de succes hors (0,1]: %r" % (success_threshold,))

    existing = find(reg, hyp_id)
    if existing:
        locked = {"signal": signal, "target": target,
                  "expected_direction": expected_direction,
                  "success_threshold": success_threshold}
        for k, v in locked.items():
            if existing[k] != v:
                raise ValueError(
                    "%s: %s est verrouille (%r), reenregistrement refuse"
                    % (hyp_id, k, existing[k]))
        return existing

    entry = {"id": hyp_id, "signal": signal, "target": target,
             "expected_direction": expected_direction,
             "success_threshold": success_threshold,
             "registered_on": registered_on,
             "rationale": rationale,
             "status": "enregistree",
             "results": []}
    reg["entries"].append(entry)
    return entry


# A hypothesis only counts as pre-registered if enough data arrived AFTER it
# was written to build at least one test slice it could not have seen: one
# test window plus one forward horizon. Anything less and "pre-registered"
# would be a technicality - a rule registered one day before the data ends is
# post-hoc in everything but timestamp.
MIN_UNSEEN_DAYS = TEST_DAYS + HORIZON


def preregistration_status(registered_on, data_end, min_unseen=MIN_UNSEEN_DAYS):
    """PRE only if the data outran the registration by a full unseen fold.

    Not a self-declaration - a subtraction of two dates. A flag saying "I
    promise I wrote this first" is worth nothing, and a criterion that depends
    on the author's memory is not a criterion. The cost of computing it this
    way is that every hypothesis starts POST and can only earn PRE by waiting,
    which is exactly the incentive wanted.
    """
    a = datetime.date.fromisoformat(registered_on)
    b = datetime.date.fromisoformat(data_end)
    return "PRE" if (b - a).days >= min_unseen else "POST"


def unseen_days(registered_on, data_end):
    return (datetime.date.fromisoformat(data_end)
            - datetime.date.fromisoformat(registered_on)).days


def fingerprint(series):
    """A short, stable digest of the VALUES a comparison was measured on.

    This exists because of something that happened to this module during the
    run that produced it. analysis/dominance.json was regenerated underneath it
    - a different basket, a different universe size, different numbers - while
    every field the registry keyed on stayed identical: same hypothesis id,
    same target name, same window widths, same 2026-08-31 cutoff. The old
    results and the new ones therefore collided on one comparison key, and the
    file would have shown a single comparison where two different experiments
    had been run.

    That is the module's own failure mode, one level up: it counts draws, and
    it could not see that the deck had been changed. A date range does not
    identify data. The digest does, so re-measuring a hypothesis on regenerated
    data now counts as the second look it is - and the corrected bar tightens
    accordingly, which is the whole point of keeping a counter.

    Twelve hex characters, not a full digest: it must be readable in a report
    and compared by eye. That is a collision risk taken knowingly, and it buys
    nothing against a deliberate collision - this detects accidents, not
    tampering.
    """
    h = hashlib.sha256()
    for d in sorted(series):
        h.update(("%s=%.10g;" % (d, series[d])).encode("utf-8"))
    return h.hexdigest()[:12]


def comparison_key(hyp_id, target, window, train_days, test_days, data_end,
                   signal_fp="", target_fp=""):
    """Identity of one comparison. The digests are part of it, not metadata.

    Defaulting them to empty keeps every key already in analysis/registry.json
    parseable and un-rewritten; those entries simply carry no digest, which is
    exactly true of them - they were written by a version that did not know
    what it had measured.
    """
    return "|".join(str(x) for x in
                    (hyp_id, target, window, train_days, test_days, data_end,
                     signal_fp, target_fp))


def record_result(reg, hyp_id, result, evaluated_on):
    """Append an outcome, unless the identical outcome is already the last one.

    The measurement is deterministic, so re-running the script produces the
    same numbers on the same day. Appending them again would grow the file with
    repetitions that read like repeated experiments, and a registry whose whole
    job is to count draws must not miscount its own. Nothing is ever REMOVED or
    edited here; a run that changes any field still appends.
    """
    entry = find(reg, hyp_id)
    if entry is None:
        raise KeyError(hyp_id)
    row = dict(result, evaluated_on=evaluated_on,
               method_version=METHOD_VERSION)
    if not entry["results"] or entry["results"][-1] != row:
        entry["results"].append(row)
    entry["status"] = result["verdict"]
    if result.get("scored") and result["comparison_key"] not in reg["comparisons"]:
        reg["comparisons"].append(result["comparison_key"])
    return entry


def family_size(reg):
    """Only SCORED comparisons enter the bar.

    A test that never reached MIN_FOLDS produced no p-value and so could not
    have produced a false positive. The opposite convention is defensible -
    the decision to attempt it was still part of the search - and it would
    make the bar stricter. The report prints both counts so that the choice is
    visible and arguable rather than buried in here.
    """
    return len(reg["comparisons"])


# --- statistics ------------------------------------------------------------

def bonferroni_bar(n_comparisons, alpha=FAMILY_ALPHA):
    return alpha / max(n_comparisons, 1)


def permutation_p(real_rate, null_rates):
    """(1 + #{null >= real}) / (1 + S).

    The +1 is not cosmetic: without it an empty count claims p = 0, that is,
    impossible under the null - which a finite number of draws can never
    establish.
    """
    if not null_rates:
        return 1.0
    ge = sum(1 for x in null_rates if x >= real_rate)
    return (1 + ge) / (1 + len(null_rates))


def resolution_floor(folds, matched):
    """Smallest p this design can emit. Above the bar means undecidable.

    The parameter is named `matched` because that is the only quantity it may
    receive: the count of draws that ACTUALLY landed on the real fold count and
    so produced a comparable test. It was called `shuffles` and only the
    docstring said otherwise, which meant a caller passing the module constant
    SHUFFLES got a silently wrong floor - 1/251 advertised where the run had
    1/12 of resolution. Renaming it does not make that call fail loudly, so a
    test pins the two apart on real numbers as well.
    """
    return max(0.5 ** folds, 1.0 / (matched + 1))


def effective_threshold(success_threshold):
    return max(success_threshold, MIN_AGREEMENT)


# --- the adoption rule -----------------------------------------------------

def adoption_verdict(entry, measurement, bar):
    """The rule. It refuses everything that has not survived a walk-forward
    with a shuffled control, and refuses to ADOPT anything post-hoc at all.

    A post-hoc result that clears every statistical test is still only a
    CANDIDAT: it earns the right to be pre-registered and tested against data
    that does not exist yet, and nothing more. That ceiling is the expensive
    part - it means no analysis performed today can promote anything today.
    The alternative is the 4/4 gradient that evaporated, which cost more.
    """
    reasons = []
    # The whole measurement is carried into the verdict rather than a chosen
    # subset of its keys. A hand-maintained key list silently dropped the
    # realised shuffle count and the run configuration from analysis/
    # registry.json, so the file recorded conclusions whose inputs it did not
    # hold. Copying everything makes that class of omission impossible.
    out = dict(measurement)
    out.update({"verdict": None, "reasons": reasons, "bar": bar,
                "scored": False})

    # Checked before the fold count, and before anything statistical. An
    # withdrawn universe is not a weak result to be scored and then rejected:
    # scoring it would enter it in the family counter as if it had been a
    # comparison about the question, and print a p-value the reader could
    # weigh. There is nothing to weigh.
    if entry["target"] in WITHDRAWN_TARGETS:
        reasons.append("%s - resultat retire, aucune statistique ne le rouvre"
                       % WITHDRAWN_TARGETS[entry["target"]])
        out["verdict"] = "NON_TESTABLE"
        return out

    folds = measurement.get("folds") or 0
    if folds < MIN_FOLDS:
        # Nothing else is even measured in this case, so nothing else is
        # reported. NON_TESTABLE is not a soft rejection: it says the
        # experiment never happened.
        reasons.append("%d plis < %d requis - non concluant" % (folds, MIN_FOLDS))
        out["verdict"] = "NON_TESTABLE"
        return out

    out["scored"] = True
    thr = effective_threshold(entry["success_threshold"])
    comparable = bool(measurement.get("null_comparable"))

    # Every failed criterion is listed, not just the first. Short-circuiting
    # would hide that a signal fails on three counts rather than one, and a
    # single-reason rejection invites the reply "so fix that one thing".
    if measurement["agreement"] < thr:
        reasons.append("accord %.0f%% < seuil %.0f%%"
                       % (measurement["agreement"] * 100, thr * 100))
    if measurement["direction"] is None:
        reasons.append("direction hors echantillon non identifiable "
                       "(%d plis +1, %d plis -1) - la direction %+d "
                       "enregistree n est pas confirmee"
                       % (measurement["dir_votes"][0], measurement["dir_votes"][1],
                          entry["expected_direction"]))
    elif measurement["direction"] != entry["expected_direction"]:
        reasons.append("direction hors echantillon %+d contre %+d attendue "
                       "(%d plis +1, %d plis -1) - l hypothese ecrite est fausse"
                       % (measurement["direction"], entry["expected_direction"],
                          measurement["dir_votes"][0], measurement["dir_votes"][1]))
    # The gap is only allowed to reject when the null it is measured against
    # ran on the same number of folds as the real walk. Rejecting on an
    # incomparable null would be the module committing the error it audits.
    # `is not None` is belt and braces - a comparable null always has a gap by
    # construction - but it is the guard that keeps criterion 4 from ever
    # reading a gap the null summary refused to compute.
    if comparable and measurement["gap"] is not None \
            and measurement["gap"] < MIN_GAP_PTS:
        reasons.append("ecart au melange %+.0f pts < %.0f requis"
                       % (measurement["gap"], MIN_GAP_PTS))
    if reasons:
        out["verdict"] = "REJETE"
        return out

    # Distinguishing "failed" from "could not have succeeded" matters: the
    # first is evidence against, the second is evidence about the experiment.
    # Merging them would let an undecidable test be read as a near miss, which
    # is how a dead hypothesis gets kept alive.
    undecidable = []
    if not comparable:
        undecidable.append(
            "%d melanges sur %d atteignent les %d plis reels (min %d requis) - "
            "aucune comparaison valide n a pu etre construite"
            % (measurement["null_matched"], measurement["shuffles"], folds,
               MIN_MATCHED_NULLS))
    if measurement["p"] > bar and measurement["floor"] > bar:
        undecidable.append(
            "p plancher %.4f > barre %.4f - le test ne pouvait pas conclure, "
            "%d plis / %d melanges apparies"
            % (measurement["floor"], bar, folds, measurement["null_matched"]))
    if undecidable:
        reasons.extend(undecidable)
        out["verdict"] = "SOUS_RESOLU"
        return out

    if measurement["p"] > bar:
        reasons.append("p %.4f > barre corrigee %.4f" % (measurement["p"], bar))
        out["verdict"] = "REJETE"
        return out

    if measurement.get("prereg") != "PRE":
        reasons.append("post-hoc: enregistree le %s, donnees jusqu au %s - "
                       "candidat a preenregistrer, jamais adopte"
                       % (entry["registered_on"], measurement.get("data_end")))
        out["verdict"] = "CANDIDAT"
        return out

    reasons.append("preenregistree, walk-forward %d/%d, p %.4f <= %.4f sur "
                   "%d melanges apparies"
                   % (measurement["agree"], folds, measurement["p"], bar,
                      measurement["null_matched"]))
    out["verdict"] = "ADOPTE"
    return out


# --- measurement -----------------------------------------------------------

def restrict(series, fwd):
    """The signal on the dates its target can actually score.

    Both the walk and its null must see the same universe. Without this the
    shuffle permutes over every date the SIGNAL has - for Fear & Greed that
    includes hundreds of 2018 days no rotation target covers - and so injects
    out-of-window values into the tested window while pushing in-window values
    out. The null would then be drawn from a wider period than the signal's
    own, which is the error forward_study.assess() spends a paragraph guarding
    against for its baseline. Costs nothing on the real walk: wf.walk already
    ignores dates absent from fwd.
    """
    return {d: v for d, v in series.items() if d in fwd}


def walk_folds(series, fwd, window=WINDOW, train_days=TRAIN_DAYS,
               test_days=TEST_DAYS):
    """wf.walk's loop, keeping the per-fold directions it aggregates away.

    Reimplemented rather than imported because wf.walk returns two integers and
    the out-of-sample direction criterion needs the sign of each TEST fold. A
    test pins this against wf.walk on real data, so the two cannot drift: if
    they ever disagree, the fault is here and the test says so.
    """
    dates = sorted(d for d in series if d in fwd)
    pct = wf.rolling_percentile(series, dates, window)
    usable = [d for d in dates if d in pct]
    out = []
    attempts = 0
    start = 0
    while start + train_days + test_days <= len(usable):
        attempts += 1
        tr = usable[start:start + train_days]
        te = usable[start + train_days:start + train_days + test_days]
        out.append((wf.direction(tr, pct, fwd), wf.direction(te, pct, fwd)))
        start += test_days
    return out, attempts


def usable_folds(pairs):
    return [(a, b) for a, b in pairs if a is not None and b is not None]


def oos_direction(pairs):
    """Majority sign of the TEST-side directions, and the split behind it.

    Out of sample because every test slice sits outside the window its own
    fold fitted on. It is a vote, not a test: nothing here says a 5-4 majority
    is distinguishable from noise, which is why the split is returned with it
    and printed everywhere the direction is printed.
    """
    tests = [b for _, b in usable_folds(pairs)]
    up = sum(1 for t in tests if t == 1)
    down = sum(1 for t in tests if t == -1)
    if up == down:
        return None, (up, down)
    return (1 if up > down else -1), (up, down)


def insample_direction(series, fwd, window=WINDOW):
    """Quintile gradient over the WHOLE sample, test folds included.

    Reported, never a criterion. Kept because it disagrees with the
    out-of-sample majority on two hypotheses this run, which is the cheapest
    demonstration available of what an in-sample criterion buys you.
    """
    dates = sorted(d for d in series if d in fwd)
    pct = wf.rolling_percentile(series, dates, window)
    return wf.direction([d for d in dates if d in pct], pct, fwd)


def null_draws(series, fwd, rng, mode, draws=SHUFFLES):
    """Agreement rates under a null, with the fold count of every draw kept.

    Two modes, and the difference between them is measured rather than argued:
      melange  - a plain shuffle, the control the adoption rule requires. It
                 destroys autocorrelation, and with it most of the fold
                 structure, because wf.direction() needs ten observations in a
                 band and no tie to return a sign.
      decalage - rotation_matrix.rotate, a circular shift. It keeps
                 autocorrelation and therefore lands much closer to the real
                 fold count. Reported alongside so that the shuffle's fold
                 collapse can be seen for what it is - an artefact of the null,
                 not a property of the data.
    """
    dates = sorted(series)
    vals = [series[d] for d in dates]
    rates, fold_counts, degenerate = [], [], 0
    for _ in range(draws):
        if mode == "melange":
            v = list(vals)
            rng.shuffle(v)
        else:
            # randrange(1, n), not randrange(n): offset 0 rotates a series onto
            # itself, so the draw would BE the real series entered as a null
            # observation. With 250 draws the chance of at least one identity
            # was about 9 in 10 - harmless here, since the shift is never a
            # criterion, but a null containing its own alternative is not
            # something to leave undeclared in a module about honest controls.
            v = rm.rotate(vals, rng.randrange(1, max(len(vals), 2)))
        pairs, _ = walk_folds(dict(zip(dates, v)), fwd)
        good = usable_folds(pairs)
        fold_counts.append(len(good))
        if not good:
            # A draw with no identifiable fold produced NO TEST. Counted, not
            # skipped: a null that fails to run a tenth of the time is a fact
            # about this design, and the earlier version discarded it in
            # silence.
            degenerate += 1
            continue
        agree = sum(1 for a, b in good if a == b)
        rates.append((agree / len(good) * 100, len(good)))
    return {"draws": draws, "rates": rates, "fold_counts": fold_counts,
            "degenerate": degenerate}


def summarise_null(nd, real_folds, real_rate):
    """Collapse a null into the numbers a verdict may read - ONE decision.

    Which draws a mean and a gap may be built from is decided here, once, and
    every consumer reads the answer rather than recomputing it. The previous
    version took the decision twice under two different tests: measure() asked
    `matched >= MIN_MATCHED_NULLS`, the report asked `matched > 0`. The same run
    then published two contradictory numbers for the same cell - 62% against
    47.6% on H11, 71% against 54.7% on H10 - with nothing telling the reader
    which one criterion 4 had actually read. A number that two artefacts of one
    run disagree about is not a measurement, and the fix is not to align two
    formulas but to delete one of them.

    Three fields carry the answer, and they travel together on purpose:
      ref_mean   the null mean a verdict or a table may print
      ref_basis  the subset it was computed on - "apparies" or "tous"
      ref_n      how many draws are behind it

    ref_mean is None when ref_n is under MIN_MATCHED_NULLS, because a mean of
    one draw is not a mean. Printing "71%" beside a matched count of 1, as the
    old table did, invites the reader to treat a single coin flip as a null
    distribution; a blank refuses that outright, and costs only a cell.
    """
    usable = [r for r, _ in nd["rates"]]
    matched = [r for r, f in nd["rates"] if f == real_folds]
    counts = nd["fold_counts"]
    comparable = len(matched) >= MIN_MATCHED_NULLS
    # The fallback to all usable draws is DESCRIPTIVE, never a criterion: it
    # compares a k-fold real walk against a null run at other fold counts. The
    # verdict knows this through `comparable`, which is why criterion 4 stops
    # being able to reject as soon as this branch is taken.
    ref_rates = matched if comparable else usable
    ref_basis = "apparies" if comparable else "tous"
    ref_mean = ((sum(ref_rates) / len(ref_rates))
                if len(ref_rates) >= MIN_MATCHED_NULLS else None)
    return {"draws": nd["draws"],
            "usable": len(usable),
            "degenerate": nd["degenerate"],
            "matched": len(matched),
            "fold_min": min(counts) if counts else None,
            "fold_max": max(counts) if counts else None,
            "fold_median": fs.median(counts),
            "mean_all": (sum(usable) / len(usable)) if usable else None,
            "mean_matched": (sum(matched) / len(matched)) if matched else None,
            "rates_matched": matched,
            "rates_all": usable,
            "comparable": comparable,
            "ref_basis": ref_basis,
            "ref_n": len(ref_rates),
            "ref_mean": ref_mean,
            "gap": (real_rate - ref_mean) if ref_mean is not None else None}


def measure(entry, series, fwd, data_end, shuffles=SHUFFLES, seed=SEED):
    """Walk-forward plus its nulls. Offline, deterministic, self-describing."""
    restricted = restrict(series, fwd)
    # Digested BEFORE the walk, from the same dicts the walk reads, so the
    # recorded identity cannot describe different numbers from the measured
    # ones.
    sig_fp, tgt_fp = fingerprint(restricted), fingerprint(fwd)
    pairs, attempts = walk_folds(restricted, fwd)
    good = usable_folds(pairs)
    folds = len(good)
    agree = sum(1 for a, b in good if a == b)
    direction, votes = oos_direction(pairs)

    m = {"folds": folds, "agree": agree, "attempts": attempts,
         "data_end": data_end,
         "prereg": preregistration_status(entry["registered_on"], data_end),
         "comparison_key": comparison_key(entry["id"], entry["target"], WINDOW,
                                          TRAIN_DAYS, TEST_DAYS, data_end,
                                          sig_fp, tgt_fp),
         "signal_fingerprint": sig_fp,
         "target_fingerprint": tgt_fp,
         "window": WINDOW, "train_days": TRAIN_DAYS, "test_days": TEST_DAYS,
         "horizon": HORIZON,
         "signal_days": len(series),
         "signal_days_in_target": len(restricted),
         "outside_target_days": len(series) - len(restricted),
         # Split out because the two exclusions have different meanings: dates
         # before the target starts would have been PERMUTED INTO the tested
         # window by an unrestricted shuffle, while the tail dates merely have
         # no forward return yet.
         "before_target_days": (sum(1 for d in series if d < min(fwd))
                                if fwd else 0),
         # The window widths in this report are counted in OBSERVATIONS. On a
         # series with holes, 365 observations reach further back than 365
         # days, so the size of the holes is recorded next to every result
         # rather than left for a reader to assume is zero.
         "calendar": calendar_gaps(restricted),
         "direction": direction, "dir_votes": list(votes),
         "direction_insample": insample_direction(restricted, fwd),
         "shuffles": 0, "null_matched": 0, "null_degenerate": 0,
         "null_usable": 0, "null_comparable": False,
         "agreement": (agree / folds) if folds else None,
         "null_mean": None, "null_mean_basis": None, "null_mean_n": 0,
         "gap": None, "p": None, "p_basis": None, "p_n": 0,
         "floor": resolution_floor(folds, 0),
         "nulls": {}}

    if folds < MIN_FOLDS or entry["target"] in WITHDRAWN_TARGETS:
        # Shuffling a test that cannot conclude burns minutes to produce a
        # number nobody is allowed to use. Skipped, and the skip stays visible
        # in the record as shuffles = 0 rather than as a missing field.
        #
        # A withdrawn target is the same case for a different reason, and it
        # gets the same treatment for consistency: the verdict refuses it
        # before reading any statistic, so drawing 500 nulls for it would buy
        # a p-value the rule is forbidden to look at. The walk itself is still
        # run and recorded - what was asked, and what came back, stays in the
        # file - only the nulls are skipped. In this run that is 1000 of 3000
        # draws and rather more than half the wall time.
        return m

    real = agree / folds * 100
    rng = random.Random(seed)
    for mode in NULL_MODES:
        m["nulls"][mode] = summarise_null(
            null_draws(restricted, fwd, rng, mode, shuffles), folds, real)

    mel = m["nulls"]["melange"]
    # Copied, not recomputed. Every one of these fields already exists in
    # m["nulls"]["melange"], and a test asserts the two stay identical: the
    # top-level names are for readers of registry.json, not a second opinion.
    comparable = mel["comparable"]
    # When too few draws matched, p falls back to every usable draw. It is then
    # DESCRIPTIVE - two experiments compared - and the verdict says so.
    # The floor does not follow it: it counts matched draws only, so a run
    # with nothing to compare against reports a resolution of 1/(0+1) = 1,
    # which is the truth. Letting it read the fallback count would advertise
    # p = 0.004 of resolution for a comparison that was never valid.
    rates = mel["rates_matched"] if comparable else mel["rates_all"]
    m.update({"shuffles": shuffles,
              "null_usable": mel["usable"],
              "null_degenerate": mel["degenerate"],
              "null_matched": mel["matched"],
              "null_comparable": comparable,
              "null_mean": mel["ref_mean"],
              "null_mean_basis": mel["ref_basis"],
              "null_mean_n": mel["ref_n"],
              "gap": mel["gap"],
              "p": permutation_p(real, rates),
              # The p and the mean can rest on DIFFERENT subsets: p falls back
              # to all usable draws whenever the matched count is short, while
              # the mean additionally refuses to be computed at all under
              # MIN_MATCHED_NULLS draws. Printing one basis for both would be
              # the same conflation this run was rejected for, one level down.
              "p_basis": "apparies" if comparable else "tous",
              "p_n": len(rates),
              "floor": resolution_floor(folds, mel["matched"])})
    return m


# --- the hypotheses actually measured today --------------------------------

TODAY = "2026-09-01"

# H03 asks whether the ETH/BTC level predicts the ETH/BTC level. It is not a
# hypothesis, it is the ruler: whatever fold agreement a DEGENERATE predictor
# reaches in this design is the number every real signal has to be read
# against. Named as a constant because the report's control section must not
# be able to point at a different id than the one that was registered as the
# control, and because a control that only a rationale string identifies is a
# control nobody can find.
CONTROL_ID = "H03"

# Every one of these was written down AFTER the study that suggested it. The
# registry will stamp them POST and it will be right. They are entered anyway
# so that the count exists, and so that they become pre-registerable against
# data that does not exist yet.
HYPOTHESES = [
    ("H01", "dominance BTC", "eth_btc", 1, 0.70,
     "band_study: gradient 4/4, dominance haute -> ETH/BTC meilleur (post-hoc)"),
    ("H02", "dominance ETH", "eth_btc", 1, 0.70,
     "walkforward: accord eleve, constate apres coup"),
    ("H03", "niveau ETH/BTC", "eth_btc", 1, 0.70,
     "controle: le niveau se predit-il lui-meme"),
    ("H04", "Fear & Greed", "eth_btc", 1, 0.70,
     "regle Tier A en vigueur: la cupidite precederait la rotation"),
    ("H05", "mvrv_z_score", "eth_btc", 1, 0.70, "regle Tier A en vigueur"),
    ("H06", "nvt", "eth_btc", 1, 0.70, "regle Tier A en vigueur"),
    ("H07", "stablecoin_supply_ratio", "eth_btc", -1, 0.70,
     "regle Tier A: ssr en baisse = rotation, donc ssr haut = pire"),
    ("H08", "dominance BTC", "alt_eth", -1, 0.70,
     "le signe s inverse selon la rotation ciblee - ecrit avant mesure"),
    ("H09", "dominance ETH", "alt_eth", -1, 0.70, "meme inversion attendue"),
    ("H10", "Fear & Greed", "alt_eth", 1, 0.70, "regle Tier A, cible alt"),
    ("H11", "dominance BTC", "alt_btc", 1, 0.70,
     "meme sens attendu que sur eth_btc"),
]


# The gate's own name for each signal this registry judges. Only the four that
# exist on both sides are here; dominance and the ETH/BTC level are rotation
# inputs, not gate signals, and inventing keys for them would fabricate a
# correspondence.
GATE_KEYS = {"Fear & Greed": "fear_greed",
             "mvrv_z_score": "mvrv_z_score",
             "nvt": "nvt",
             "stablecoin_supply_ratio": "stablecoin_supply_ratio"}


def downstream_tiers():
    """What the live gate does with the signals this registry judged.

    A registry that issues verdicts nobody reads is a diary. This reads
    dimensions.SIGNAL_REGISTRY at runtime and prints the tier each judged
    signal actually sits in, so the report shows whether its own conclusions
    were acted on - or, just as usefully, that they were not.

    Imported lazily: dimensions is the gate, and a measurement module that
    fails to load because the thing it measures moved would be the wrong
    dependency direction.
    """
    try:
        import dimensions
    except Exception:
        return None
    out = {}
    for label, key in sorted(GATE_KEYS.items()):
        spec = dimensions.SIGNAL_REGISTRY.get(key)
        out[label] = spec[1] if spec else None
    return out


def by_hyp_id(hyp_id):
    for h in HYPOTHESES:
        if h[0] == hyp_id:
            return h
    return None


def load_rotations():
    with open(os.path.join(ANALYSIS, "rotations.json"), encoding="utf-8") as f:
        return json.load(f)


def load_fear_greed_offline(path=FNG_CACHE):
    """Cache only, and a loud failure when it is missing.

    forward_study.load_fear_greed() falls back to the API on a cache miss. That
    fallback makes this module offline only for as long as one gitignored file
    survives - which is not a property, it is an accident. Here a missing cache
    is an error naming the file, so a silent HTTP call can never happen.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            "cache Fear & Greed absent: %s - ce module ne va JAMAIS le "
            "chercher en ligne. Regenerer le cache avec un module autorise a "
            "sortir sur le reseau (scripts/forward_study.py)." % path)
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


def basket_span(dom):
    """Size of the UNIVERSE behind the dominance figures, day by day.

    The name of this quantity changed under the module and the module did not
    notice. Until scripts/build_rotations.py existed, dominance.json held a
    fixed list and `n_assets` was the basket - 14 to 24 assets, which is the
    figure the previous report printed as "panier de 14 a 24 actifs". The
    regenerated file writes `n_assets` as the size of the whole CoinMetrics
    universe on that date, 71 to 118, while the alt basket is a fixed top
    `bs_TOP_N` by market cap. Printing the new number under the old sentence
    would have multiplied the declared basket by five without a single line of
    code changing.

    So this returns the universe and the caller prints it as the universe. The
    basket size is not measured here at all: it is br.TOP_N, a constant of the
    generator, and reading it from there is the only way the two cannot drift.
    """
    n = [v.get("n_assets") for v in dom.values() if v.get("n_assets")]
    return (min(n), max(n), len(n)) if n else (None, None, 0)


# The majors this cycle's alt rotation would actually have been about. Checked
# against the index that was really built rather than asserted: the commit
# message that withdrew the alt results lists them, and a list living only in
# a commit message is a claim nobody can re-run.
CYCLE_MAJORS = ("sol", "sui", "hype", "apt", "arb", "op", "ton", "near",
                "inj", "tia", "sei", "avax")


def absent_majors(path=None, majors=CYCLE_MAJORS):
    """Which cycle majors NEVER entered the alt index, measured from its log.

    analysis/basket_log.txt records the composition at every change, so the set
    of assets the index ever held is recoverable. That set is what decides
    whether the alt targets measure this cycle's rotation, and it is cheaper to
    read it than to trust a sentence about it.

    Returns (absent, present, n_assets_ever). An empty `absent` would mean the
    withdrawal below is over-cautious and should be revisited - which is why
    the report prints the measurement next to the withdrawal instead of only
    the conclusion.
    """
    path = path or os.path.join(ANALYSIS, "basket_log.txt")
    if not os.path.exists(path):
        return None
    ever = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.split("  ", 1)
            if len(parts) == 2 and parts[0][:4].isdigit():
                ever.update(a.strip() for a in parts[1].split(",") if a.strip())
    return (tuple(m for m in majors if m not in ever),
            tuple(m for m in majors if m in ever),
            len(ever))


def calendar_gaps(dates):
    """Observations against the calendar span they are spread over.

    wf.rolling_percentile counts 365 POSITIONS in a sorted list of dates, not
    365 calendar days. On a series with no holes the two coincide and the
    distinction is pedantry; on a series with holes the trailing window quietly
    reaches further back than the label claims, and every window width in this
    report is a label. So the holes are counted instead of being assumed away,
    and the configuration line says "observations" rather than "jours".

    Returned rather than asserted: the point is to publish the number, not to
    refuse a series for having gaps.
    """
    ds = sorted(dates)
    if len(ds) < 2:
        return {"n": len(ds), "span": len(ds), "missing": 0,
                "first": ds[0] if ds else None, "last": ds[0] if ds else None}
    span = (datetime.date.fromisoformat(ds[-1])
            - datetime.date.fromisoformat(ds[0])).days + 1
    return {"n": len(ds), "span": span, "missing": span - len(ds),
            "first": ds[0], "last": ds[-1]}


def fng_source_divergence(cache_fng, series_fng):
    """The two Fear & Greed series this repository carries, compared.

    analysis/.cache/fng.json and analysis/series.json['fear_greed'] both hold
    Fear & Greed and had never been put side by side. This module reads the
    cache, which is the right choice - it reaches back to 2018 and the other
    starts in 2022, so the shorter one would drop the years that make F&G the
    only signal covering the 2021 altseason at all. But "the right choice"
    unmeasured is just a preference, and a repository holding two versions of
    one series without knowing whether they agree has a silent fork in it.

    So: how many days each, how many in common, and how far apart they are
    where both exist. If they disagree, the choice of source is a free
    parameter and the report has to say so.
    """
    common = sorted(set(cache_fng) & set(series_fng))
    if not common:
        return {"n_cache": len(cache_fng), "n_series": len(series_fng),
                "n_common": 0, "identical": 0, "max_diff": None,
                "median_diff": None}
    diffs = [abs(cache_fng[d] - series_fng[d]) for d in common]
    return {"n_cache": len(cache_fng), "n_series": len(series_fng),
            "n_common": len(common),
            "identical": sum(1 for x in diffs if x == 0),
            "max_diff": max(diffs),
            "median_diff": fs.median(diffs),
            "cache_first": min(cache_fng), "series_first": min(series_fng)}


def reference_fold_table(signals, targets, reference_px):
    """Fold-by-fold, this module against wf.walk on analysis/ethbtc.json.

    The previous version declared the target divergence in points of forward
    return - median 0.21, max 1.63 - which reads as negligible and let a reader
    conclude the two are interchangeable. They are not, and the unit was wrong:
    what changes between rotations.json['eth_btc'] and analysis/ethbtc.json at
    an IDENTICAL configuration is the number of folds and the agreement built
    on them. analysis/walkforward.txt reports "dominance BTC : 2 plis
    seulement" and "niveau ETH/BTC : 100% (4/4)" where this module gets other
    counts. A gap of 0.21 point cannot be read off as that; only the fold
    counts can, so the fold counts are what gets printed.

    rm.reference_fold_comparison does the arithmetic, shared with
    rotation_matrix.py's section 5 rather than rewritten here: two modules
    computing "how far are we from walkforward.py" independently can disagree
    about the answer, and then the audit needs an audit.
    """
    ref_fwd = fs.forward_map(reference_px, HORIZON)
    rows = []
    for name in ("dominance BTC", "dominance ETH", "niveau ETH/BTC",
                 "Fear & Greed"):
        if name not in signals:
            continue
        raw = signals[name]
        pairs, _ = walk_folds(restrict(raw, targets["eth_btc"]),
                              targets["eth_btc"])
        good = usable_folds(pairs)
        rows.append((name, rm.reference_fold_comparison(
            sum(1 for a, b in good if a == b), len(good), raw, ref_fwd,
            WINDOW, TRAIN_DAYS, TEST_DAYS)))
    return rows


def target_divergence(target_px, reference_px, horizon=HORIZON):
    """How far this eth_btc index sits from analysis/ethbtc.json.

    Every other module in the project - forward_study, band_study, walkforward,
    oos_test - measures ETH/BTC on analysis/ethbtc.json. This one measures it on
    rotations.json['eth_btc'], a rebased index. A reader comparing an H02 or H03
    line here against analysis/walkforward.txt is comparing two series, and is
    entitled to know by how much before doing it. rotation_matrix.
    reference_agreement() asks the same question to assert commensurability;
    here the point is the opposite, so the disagreement is printed rather than
    asserted away.
    """
    fa = fs.forward_map(target_px, horizon)
    fb = fs.forward_map(reference_px, horizon)
    common = sorted(set(fa) & set(fb))
    if not common:
        return None
    diffs = [abs(fa[d] - fb[d]) for d in common]
    ratios = [target_px[d] / reference_px[d]
              for d in sorted(set(target_px) & set(reference_px))
              if reference_px[d]]
    return {"n": len(common), "max_diff": max(diffs),
            "mean_diff": sum(diffs) / len(diffs),
            "median_diff": fs.median(diffs),
            "ratio_lo": min(ratios) if ratios else None,
            "ratio_hi": max(ratios) if ratios else None}


def build_inputs():
    dom = bs.load_dominance()
    series = fs.load_series()
    rot = load_rotations()
    signals = {"dominance BTC": {d: v["btc_dom"] for d, v in dom.items()},
               "dominance ETH": {d: v["eth_dom"] for d, v in dom.items()},
               "niveau ETH/BTC": dict(rot["eth_btc"]),
               "Fear & Greed": load_fear_greed_offline()}
    for name in ("mvrv_z_score", "stablecoin_supply_ratio", "nvt"):
        if name in series:
            signals[name] = series[name]
    targets = {k: fs.forward_map(rot[k], HORIZON) for k in rot}
    # The earliest common end date, so that no hypothesis is judged
    # pre-registered merely because its target series stops sooner.
    data_end = min(max(rot[k]) for k in rot)
    ethbtc = fs.load_ethbtc()
    context = {"basket": basket_span(dom),
               "absent_majors": absent_majors(),
               "gate_tiers": downstream_tiers(),
               "divergence": target_divergence(rot["eth_btc"], ethbtc),
               "fng_sources": fng_source_divergence(
                   signals["Fear & Greed"],
                   series.get("fear_greed", {})),
               "reference_folds": reference_fold_table(signals, targets, ethbtc),
               "rot": rot}
    return signals, targets, data_end, context


# --- report ----------------------------------------------------------------

class Out(object):
    """Collects the report so the file and stdout cannot drift apart."""

    def __init__(self):
        self.lines = []

    def __call__(self, s=""):
        self.lines.append(s)

    def text(self):
        return "\n".join(self.lines) + "\n"

    def flush(self, path):
        text = self.text()
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        sys.stdout.write(text)


def tmark(target):
    """The alt caveat travels with every alt row, not with the report.

    A bias declared once in a trailing block survives exactly until someone
    quotes a single line out of the table. Marking the row means the caveat
    cannot be separated from the number it applies to.
    """
    return target + (ALT_MARK if target.startswith("alt") else "")


def _fmt_dir(d, votes=None):
    if d is None:
        base = "?"
    else:
        base = "%+d" % d
    if votes is None:
        return base
    return "%s (%d+/%d-)" % (base, votes[0], votes[1])


def main():
    signals, targets, data_end, ctx = build_inputs()

    reg = load() or new_registry(TODAY)
    for hid, sig, tgt, direction, thr, why in HYPOTHESES:
        register(reg, hid, sig, tgt, direction, thr, TODAY, why)

    # Two passes. The bar depends on how many comparisons get scored, and a bar
    # that moved while verdicts were being issued would let the ORDER of
    # evaluation decide outcomes. So: measure everything, count, then judge.
    measurements = {}
    attempted = 0
    t0 = time.time()
    for hid, sig, tgt, _, _, _ in HYPOTHESES:
        entry = find(reg, hid)
        if sig not in signals or tgt not in targets:
            measurements[hid] = None
            continue
        attempted += 1
        measurements[hid] = measure(entry, signals[sig], targets[tgt], data_end)
    # Declared in the header for the same reason every other cost in this
    # module is declared: a reader deciding whether to re-run it is entitled to
    # know it takes minutes, and the draw count is what those minutes buy.
    ctx["runtime_s"] = time.time() - t0
    ctx["total_draws"] = sum(
        len(NULL_MODES) * m["shuffles"]
        for m in measurements.values() if m)

    provisional = set(reg["comparisons"])
    for m in measurements.values():
        if m and (m["folds"] or 0) >= MIN_FOLDS:
            provisional.add(m["comparison_key"])
    bar = bonferroni_bar(len(provisional))

    verdicts = {}
    for hid, sig, tgt, _, _, _ in HYPOTHESES:
        entry = find(reg, hid)
        m = measurements.get(hid)
        if m is None:
            v = {"verdict": "NON_TESTABLE", "scored": False, "bar": bar,
                 "reasons": ["serie absente du disque"], "folds": 0,
                 "prereg": preregistration_status(entry["registered_on"],
                                                  data_end),
                 "comparison_key": None}
        else:
            v = adoption_verdict(entry, m, bar)
        verdicts[hid] = v
        record_result(reg, hid, v, TODAY)

    save(reg)

    render_report(measurements, verdicts, reg, bar, attempted, data_end,
                  ctx).flush(REPORT_PATH)
    return 0


def render_report(measurements, verdicts, reg, bar, attempted, data_end, ctx,
                  today=TODAY):
    """Everything the run has to say, built from data it was handed.

    Separated from main() so the report can be exercised without paying for a
    thousand null draws. The alt-basket marking in particular has to be TESTED
    rather than eyeballed: it is a bias declaration, and a bias declaration
    that only survives because nobody edited the table is not a control.
    """
    b_lo, b_hi, b_n = ctx["basket"]
    div = ctx["divergence"]
    first_pre = (datetime.date.fromisoformat(today)
                 + datetime.timedelta(days=MIN_UNSEEN_DAYS)).isoformat()

    o = Out()
    o("REGISTRE DE PREENREGISTREMENT - genere le %s" % today)
    o("=" * 74)
    o("Ce registre NE GOUVERNE RIEN. Il compte les tirages, et il refuse.")
    o("Fichier  : analysis/registry.json (schema v%d, methode v%d)"
      % (SCHEMA_VERSION, METHOD_VERSION))
    o("           Les resultats sans method_version datent d une methode")
    o("           anterieure - nulle non restreinte, direction in-sample -")
    o("           et sont conserves tels quels, jamais reecrits.")
    o("Horsligne: aucun appel reseau. Le cache F&G est lu, jamais complete ;")
    o("           s il manque, le module echoue au lieu de sortir sur le web.")
    o("Config   : percentile glissant sur %d OBSERVATIONS | train %d obs. |"
      % (WINDOW, TRAIN_DAYS))
    o("           test %d obs. | horizon %d jours - une seule configuration,"
      % (TEST_DAYS, HORIZON))
    o("           aucun balayage. OBSERVATIONS, pas jours calendaires :")
    o("           wf.rolling_percentile compte %d POSITIONS dans la liste de"
      % WINDOW)
    o("           dates triee. Les trous de chaque serie sont comptes plus bas")
    o("           (colonne 'trous'), parce qu une fenetre de %d positions sur"
      % WINDOW)
    o("           une serie trouee remonte plus loin que son etiquette.")
    if ctx.get("runtime_s") is not None:
        o("Cout     : %.0f s de calcul mesurees dans ce run, %d tirages de"
          % (ctx["runtime_s"], ctx.get("total_draws", 0)))
        o("           nulle au total (%d par mode, %d modes, par hypothese"
          % (SHUFFLES, len(NULL_MODES)))
        o("           scoree). Augmenter SHUFFLES coute lineairement et")
        o("           n achete rien contre le plancher en plis.")
    o("%s = %s" % (ALT_MARK, ALT_BASKET_CAVEAT))
    o("")
    o("QUELLES SERIES, EXACTEMENT")
    o("-" * 74)
    o("  Cibles : analysis/rotations.json, derniere date commune %s." % data_end)
    o("  ATTENTION - la cible eth_btc de ce rapport est l INDEX rotations.json,")
    o("  pas le prix analysis/ethbtc.json sur lequel forward_study, band_study,")
    o("  walkforward et oos_test ont ete calcules. Mesure dans ce run :")
    if div:
        o("    rapport de niveau entre les deux series : %.3f a %.3f"
          % (div["ratio_lo"], div["ratio_hi"]))
        o("    rendements forward %dj sur %d jours communs : ecart median "
          "%.2f pt," % (HORIZON, div["n"], div["median_diff"]))
        o("    moyen %.2f pt, MAXIMUM %.2f pt."
          % (div["mean_diff"], div["max_diff"]))
    o("  Ces points de rendement sont la MAUVAISE unite pour juger de la")
    o("  consequence, et ils se lisent comme negligeables. Ce qui change")
    o("  vraiment, a configuration IDENTIQUE (%d/%d/%d, horizon %d), c est le"
      % (WINDOW, TRAIN_DAYS, TEST_DAYS, HORIZON))
    o("  nombre de PLIS et l accord construit dessus :")
    o("    %-16s %14s %14s %s"
      % ("signal / eth_btc", "ici", "wf.walk", "sur ethbtc.json"))
    for name, c in (ctx.get("reference_folds") or []):
        o("    %-16s %10d/%-3d %10d/%-3d  %s"
          % (name, c["here_agree"], c["here_folds"],
             c["there_agree"], c["there_folds"],
             "identique" if c["folds_match"] and c["agree_match"]
             else "DIFFERENT"))
    o("  La colonne 'ici' marche sur rotations.json['eth_btc'], la colonne")
    o("  wf.walk sur analysis/ethbtc.json - c est la comparaison que")
    o("  rotation_matrix.py imprime deja en section 5, et c est sa fonction")
    o("  rm.reference_fold_comparison qui la calcule ici, pas une seconde")
    o("  arithmetique ecrite de memoire. Deux sources d ecart se cumulent : la")
    o("  serie de prix, et le fait que le percentile ne voit pas les memes")
    o("  jours utilisables de chaque cote, donc les plis ne coupent pas au")
    o("  meme endroit. Une ligne eth_btc d ici ne se compare donc pas terme a")
    o("  terme a analysis/walkforward.txt, et le nombre de plis est ce qui le")
    o("  montre.")
    o("  Dominance : UNIVERS de %d a %d actifs selon le jour (%d jours"
      % (b_lo, b_hi, b_n))
    o("  mesures). Attention au nom de ce chiffre : dominance.json['n_assets']")
    o("  designait le PANIER tant qu il etait fige (14 a 24 actifs), il")
    o("  designe l UNIVERS depuis build_rotations.py. Le panier alt, lui, est")
    o("  le top %d par capitalisation, reconstitue a chaque date. Le rapport"
      % br.TOP_N)
    o("  precedent imprimait le nouveau nombre sous l ancienne phrase : le")
    o("  panier declare aurait ete multiplie par cinq sans qu une ligne de")
    o("  code change.")
    o("  Le NIVEAU de dominance reste biaise ; seuls les rangs servent ici.")
    fng = ctx.get("fng_sources")
    if fng:
        o("  Fear & Greed : le depot porte DEUX series F&G, jamais comparees")
        o("  jusqu ici. Ce module lit analysis/.cache/fng.json (%d jours,"
          % fng["n_cache"])
        o("  depuis %s) et ignore analysis/series.json['fear_greed'] (%d jours,"
          % (fng.get("cache_first"), fng["n_series"]))
        o("  depuis %s). Le choix se justifie par la couverture : la seconde"
          % fng.get("series_first"))
        o("  commence apres l altseason 2021, la seule periode ou F&G soit le")
        o("  seul signal disponible. Reconciliation mesuree ici :")
        if fng["n_common"]:
            o("    %d jours communs, %d identiques a la valeur pres, ecart"
              % (fng["n_common"], fng["identical"]))
            o("    median %.2f, MAXIMUM %.2f point de F&G."
              % (fng["median_diff"], fng["max_diff"]))
        else:
            o("    aucun jour commun - les deux ne se recoupent pas du tout.")
    o("")
    o("")
    o("CIBLES RETIREES - un refus qui n est pas statistique")
    o("-" * 74)
    o("  Les cibles %s sont RETIREES."
      % ", ".join(tmark(t) for t in sorted(WITHDRAWN_TARGETS)))
    o("  Motif : l indice alt est le top %d par capitalisation d un univers"
      % br.TOP_N)
    o("  CoinMetrics community qui ne contient aucun des majors de ce cycle.")
    am = ctx.get("absent_majors")
    if am:
        absent, present, ever = am
        o("  Mesure sur analysis/basket_log.txt - %d actifs ont appartenu a l"
          % ever)
        o("  indice depuis 2019. Sur les %d majors de ce cycle testes :"
          % len(CYCLE_MAJORS))
        o("    JAMAIS dans l indice : %s"
          % (", ".join(absent) if absent else "aucun"))
        o("    presents             : %s"
          % (", ".join(present) if present else "aucun"))
        if not absent:
            o("  Aucun absent mesure : le retrait ci-dessus serait alors trop")
            o("  prudent et doit etre rouvert. Ce n est pas le cas de ce run.")
    o("  L indice mesure donc un panier 2017-2021, pas la rotation alt qu on")
    o("  chercherait a trader. Le commit HEAD de build_rotations.py retire ces")
    o("  resultats au lieu de les nuancer, et ce module applique le retrait")
    o("  AVANT tout critere statistique : H08 a H11 sont mesurees, ecrites,")
    o("  et rendues NON_TESTABLE quel que soit leur p. Une hypothese qui bat")
    o("  sa nulle sur le mauvais univers reste une reponse a une autre")
    o("  question.")
    o("  Elles restent enregistrees et mesurees : ce fichier n efface rien, et")
    o("  une hypothese retiree qui disparait ne laisse aucune trace d avoir")
    o("  ete posee - l oubli exact que le registre existe pour empecher.")
    o("  Reste mesurable sur donnees gratuites : eth_btc, une seule jambe.")
    o("")
    o("POURQUOI CE FICHIER EXISTE")
    o("-" * 74)
    o("Sept analyses sur les memes quatre ans ont produit un gradient 4/4")
    o("parfait, dissous hors echantillon (analysis/oos_test.txt). Sans")
    o("compteur, la vingtieme hypothese qui marche est le vingtieme tirage,")
    o("et rien dans le depot ne permettait de le savoir. Le registre ecrit la")
    o("direction ATTENDUE avant le resultat : c est la seule chose qu on ne")
    o("peut pas rediger apres coup.")
    o("")
    o("HYPOTHESES ENREGISTREES")
    o("-" * 74)
    o("  %-5s %-24s %-10s %5s %7s %s"
      % ("id", "signal", "cible", "dir.", "seuil", "enregistree"))
    for hid, sig, tgt, d, thr, _ in HYPOTHESES:
        o("  %-5s %-24s %-10s %+5d %6.0f%% %s"
          % (hid, sig, tmark(tgt), d, thr * 100, today))
    o("")
    o("PREENREGISTREE OU POST-HOC - calcule, pas declare")
    o("-" * 74)
    o("  PRE exige %d jours de donnees ARRIVEES APRES l enregistrement"
      % MIN_UNSEEN_DAYS)
    o("  (un pli de test de %dj + un horizon de %dj), sinon POST."
      % (TEST_DAYS, HORIZON))
    o("  Ici : enregistrement %s, donnees jusqu au %s = %d jours inedits."
      % (today, data_end, unseen_days(today, data_end)))
    o("  Donc les %d hypotheses sont POST-HOC. Aucune n a ete ecrite avant"
      % len(HYPOTHESES))
    o("  d avoir vu ces donnees, et le registre le constate au lieu de le")
    o("  croire sur parole. Elles basculeront en PRE au plus tot le %s,"
      % first_pre)
    o("  sans que rien ne soit reecrit : c est la seule facon pour ce fichier")
    o("  de prendre de la valeur, et elle consiste a attendre.")
    o("")
    o("BARRE DE SIGNIFICATIVITE CORRIGEE")
    o("-" * 74)
    o("  hypotheses enregistrees        : %d" % len(reg["entries"]))
    o("  comparaisons tentees ce run    : %d" % attempted)
    o("  comparaisons SCOREES (cumul)   : %d" % family_size(reg))
    o("  dont sans empreinte de donnees : %d (methode anterieure)"
      % sum(1 for k in reg["comparisons"] if k.count("|") < 7))
    o("  alpha famille                  : %.3f" % FAMILY_ALPHA)
    o("  barre Bonferroni alpha/n       : %.4f" % bar)
    o("")
    o("  Bonferroni parce que c est la seule correction recalculable a partir")
    o("  d un simple compteur, sans hypothese que ces donnees ne")
    o("  soutiendraient pas. Ses faiblesses, a lire avec chaque verdict :")
    o("   - elle suppose les tests independants. Dominance BTC et dominance")
    o("     ETH sont quasi le miroir l une de l autre, et alt_btc suit")
    o("     alt_eth x eth_btc : la vraie famille est plus petite que le")
    o("     compteur, donc la barre est trop severe.")
    o("   - elle ne compte que ce qui est ECRIT. Les fenetres balayees et les")
    o("     seuils essayes a la main n ont jamais atteint le fichier. Le")
    o("     compteur est un PLANCHER de la famille reelle : une recherche non")
    o("     comptee n est corrigee par aucune arithmetique.")
    o("   - elle achete le taux de faux positifs en detruisant la puissance.")
    o("     A famille %d, un signal reel mais modeste n a presque aucune"
      % family_size(reg))
    o("     chance de passer. C est le prix, paye parce que l alternative -")
    o("     aucun compteur - a deja produit un gradient dissous.")
    o("   - et elle ne corrige que ce qu elle peut IDENTIFIER. Jusqu a ce run")
    o("     la cle d une comparaison etait (id, cible, fenetres, date de fin)")
    o("     et ne disait rien des VALEURS. analysis/dominance.json a ete")
    o("     regenere pendant ce run - autre panier, autre univers, memes")
    o("     dates - et les deux mesures se seraient ecrasees sur une seule")
    o("     cle. Une plage de dates n identifie pas des donnees. La cle porte")
    o("     desormais une empreinte du signal et de la cible, donc remesurer")
    o("     sur donnees regenerees compte comme le second tirage que c est.")
    o("")
    o("EMPREINTES DES DONNEES MESUREES")
    o("-" * 74)
    o("  %-5s %-24s %-10s %14s %14s" % ("id", "signal", "cible",
                                        "signal", "cible"))
    for hid, sig, tgt, _, _, _ in HYPOTHESES:
        m = measurements.get(hid)
        if not m or not m.get("signal_fingerprint"):
            continue
        o("  %-5s %-24s %-10s %14s %14s"
          % (hid, sig, tmark(tgt), m["signal_fingerprint"],
             m["target_fingerprint"]))
    o("  sha256 tronque a 12 caracteres, sur la serie RESTREINTE effectivement")
    o("  parcourue. Tronque pour etre comparable a l oeil dans un rapport :")
    o("  c est un risque de collision accepte, et il ne protege de rien")
    o("  d intentionnel - il detecte un accident, pas une falsification.")
    o("")
    o("MESURES - walk-forward, direction hors echantillon")
    o("-" * 74)
    o("  %-5s %-24s %-10s %6s %6s %6s %5s %5s %7s %-12s %s"
      % ("id", "signal", "cible", "jours", "trous", "avant", "tent.", "plis",
         "accord", "dir. h-ech.", "in-sample"))
    for hid, sig, tgt, _, _, _ in HYPOTHESES:
        m = measurements.get(hid)
        if not m:
            o("  %-5s %-24s %-10s   serie absente du disque"
              % (hid, sig, tmark(tgt)))
            continue
        acc = ("%6.0f%%" % (m["agreement"] * 100)
               if m["agreement"] is not None else "      -")
        cal = m.get("calendar") or {}
        o("  %-5s %-24s %-10s %6d %6s %6d %5d %5d %s %-12s %s"
          % (hid, sig, tmark(tgt), m["signal_days_in_target"],
             ("%d" % cal["missing"]) if cal else "-",
             m["before_target_days"], m["attempts"], m["folds"], acc,
             _fmt_dir(m["direction"], m["dir_votes"]),
             _fmt_dir(m["direction_insample"])))
    o("")
    o("  trous = jours calendaires ABSENTS de la serie restreinte, entre sa")
    o("  premiere et sa derniere date. C est la mesure qui manquait sous")
    o("  l etiquette 'percentile glissant 365j' : la fenetre compte %d"
      % WINDOW)
    o("  observations, donc sur une serie a trous elle remonte au-dela de %d"
      % WINDOW)
    o("  jours calendaires, d autant plus loin que la colonne est grande.")
    o("  jours = dates du signal que la cible sait noter ; avant = dates du")
    o("  signal ANTERIEURES au debut de la cible, exclues avant tout melange.")
    o("  Sans cette restriction le melange de Fear & Greed injecterait ses")
    o("  jours 2018 dans une fenetre qui commence en 2019, et tirerait sa")
    o("  nulle d une periode plus large que le signal lui-meme.")
    o("  tent. = fenetres train/test decoupees ; plis = celles ou les DEUX")
    o("  cotes donnent une direction identifiable. L ecart entre les deux")
    o("  colonnes est du perdu, pas du bruit ecarte.")
    o("  La colonne in-sample lit tout l echantillon, plis de test compris.")
    o("  Elle n est PAS un critere. Elle est imprimee parce que ce run montre")
    o("  ce qu elle vaut, et le montre sur des identifiants comptes ici :")
    opposed, blind = [], []
    for hid, _, _, _, _, _ in HYPOTHESES:
        m = measurements.get(hid)
        if not m or m["folds"] < MIN_FOLDS:
            continue
        ins, oos = m["direction_insample"], m["direction"]
        if ins is not None and oos is not None and ins != oos:
            opposed.append(hid)
        elif ins is None and oos is not None:
            blind.append(hid)
    o("    signe oppose a la mesure hors echantillon : %s"
      % (", ".join(opposed) if opposed else "aucun"))
    o("    illisible la ou les plis tranchent        : %s"
      % (", ".join(blind) if blind else "aucun"))
    o("  Un critere bati la-dessus aurait valide ou invalide des hypotheses")
    o("  sur un gradient qui a vu ses propres donnees de test.")
    o("")
    o("LE MELANGE NE CONSERVE PAS LES PLIS - mesure, pas suppose")
    o("-" * 74)
    o("  %-5s %-10s %-9s %6s %7s %6s %-14s %5s %8s %-13s %8s %6s"
      % ("id", "cible", "mode", "lances", "utilis.", "degen.", "plis obtenus",
         "reels", "apparies", "base moyenne", "moyenne", "ecart"))
    for hid, sig, tgt, _, _, _ in HYPOTHESES:
        m = measurements.get(hid)
        if not m or not m["nulls"]:
            continue
        for mode in NULL_MODES:
            s = m["nulls"][mode]
            # Read, never recomputed. These are the exact fields the verdict
            # was issued on - for the melange row, m["null_mean"] and m["gap"]
            # are copies of s["ref_mean"] and s["gap"], and a test asserts the
            # report's `ecart` column equals registry.json's `gap` line by
            # line. The previous version derived this cell from a different
            # test than measure() used and the two artefacts of one run
            # disagreed by up to 32 points on the number criterion 4 reads.
            if s["ref_mean"] is None:
                base = "n=%d insuff." % s["ref_n"]
                mean, gap = "       -", "     -"
            else:
                base = "%s(%d)" % (s["ref_basis"], s["ref_n"])
                mean = "%7.0f%%" % s["ref_mean"]
                gap = "%+6.0f" % s["gap"]
            o("  %-5s %-10s %-9s %6d %7d %6d %-14s %5d %8d %-13s %8s %6s"
              % (hid, tmark(tgt), mode, s["draws"], s["usable"],
                 s["degenerate"],
                 "%d..%d (med %.0f)" % (s["fold_min"], s["fold_max"],
                                        s["fold_median"]),
                 m["folds"], s["matched"], base, mean, gap))
    o("")
    o("  Absentes de ce tableau : les hypotheses a moins de %d plis, et celles"
      % MIN_FOLDS)
    o("  dont la cible est retiree (%s)."
      % ", ".join(tmark(t) for t in sorted(WITHDRAWN_TARGETS)))
    o("  Aucune nulle n a ete tiree pour")
    o("  elles - leur verdict les refuse avant toute statistique, et tirer")
    o("  serait payer des minutes pour un chiffre que la regle s interdit de")
    o("  lire. Leur marche reel, lui, est mesure et reste au tableau MESURES.")
    o("  utilis. = tirages ayant produit au moins un pli ; degen. = tirages")
    o("  sans aucun pli identifiable, donc sans test.")
    o("  base moyenne = SUR QUOI la moyenne et l ecart portent, et sur combien")
    o("  de tirages. 'apparies(n)' : les tirages tombes sur le meme nombre de")
    o("  plis que le reel, seul cas ou le critere 4 peut rejeter.")
    o("  'tous(n)' : repli sur tous les tirages exploitables des que les")
    o("  apparies sont sous %d - la cellule compare alors DEUX EXPERIENCES"
      % MIN_MATCHED_NULLS)
    o("  differentes et n est que descriptive. 'n=k insuff.' : moins de %d"
      % MIN_MATCHED_NULLS)
    o("  tirages derriere le chiffre, donc aucune moyenne n est imprimee.")
    o("  Une version precedente affichait ici 'moyenne 71%' calculee sur UN")
    o("  seul tirage apparie, avec la colonne apparies=1 juste a cote et rien")
    o("  qui relie les deux : une moyenne d un tirage n est pas une moyenne,")
    o("  et un ecart qui en decoule n est pas un ecart.")
    o("  Ce que ce tableau dit : un melange produit beaucoup MOINS de plis que")
    o("  la serie reelle. wf.direction() rend None des qu une bande compte")
    o("  moins de dix observations ou que le gradient fait match nul, et une")
    o("  serie melangee y tombe sans arret. Un commentaire de la version")
    o("  precedente affirmait que le melange conservait la structure des plis :")
    o("  les colonnes ci-dessus le dementent.")
    o("  Consequences assumees :")
    o("   - a %d apparies ou plus, le p porte sur les melanges APPARIES (meme"
      % MIN_MATCHED_NULLS)
    o("     nombre de plis que le reel) et le critere 4 peut rejeter. SOUS ce")
    o("     seuil - y compris a 14, 12 ou 11 apparies, pas seulement a zero -")
    o("     le p bascule sur TOUS les melanges exploitables, aucune")
    o("     comparaison valide n existe, et le verdict est SOUS_RESOLU, jamais")
    o("     REJETE. La colonne 'base du p' du tableau suivant dit, ligne par")
    o("     ligne, laquelle des deux a servi.")
    o("   - a deux plis, un taux d accord ne peut valoir que 0, 50 ou 100 :")
    o("     une nulle a plis courts est grossiere autant qu elle est fausse.")
    o("   - le decalage circulaire garde l autocorrelation, donc les plis. Il")
    o("     est imprime pour montrer que l effondrement vient du melange, pas")
    o("     des donnees. Il n est jamais un critere : la regle demandee est un")
    o("     controle par melange.")
    o("")
    o("PLANCHER DE RESOLUTION")
    o("-" * 74)
    o("  p ne peut pas descendre sous max(0.5**plis, 1/(apparies+1)), ou")
    o("  apparies compte les melanges tombes sur le MEME nombre de plis que")
    o("  la serie reelle.")
    o("  Le declencheur du repli, exactement : sous %d apparies, le p est"
      % MIN_MATCHED_NULLS)
    o("  calcule sur TOUS les melanges exploitables, pas sur les apparies.")
    o("  Ce n est donc pas la seule ligne a zero apparie qui bascule - toute")
    o("  ligne sous le seuil bascule, y compris avec 14, 12 ou 11 apparies")
    o("  imprimes sur la meme ligne. La colonne 'base du p' dit laquelle,")
    o("  parce que sans elle un lecteur attribue le p aux apparies affiches a")
    o("  cote, et se trompe de plusieurs centaines de tirages.")
    o("  Le PLANCHER, lui, ne bascule jamais : il compte les melanges")
    o("  REELLEMENT apparies, pas les %d lances ni les exploitables du repli."
      % SHUFFLES)
    o("  Annoncer 1/%d = %.4f serait vendre une resolution qu aucune hypothese"
      % (SHUFFLES + 1, 1.0 / (SHUFFLES + 1)))
    o("  n a atteinte ici. Zero apparie donne donc un plancher de 1.0000 : le")
    o("  design n avait aucune resolution, et le p a cote n est qu une")
    o("  description.")
    o("  %-5s %-10s %5s %9s %9s %9s %-13s %s"
      % ("id", "cible", "plis", "apparies", "plancher", "p", "base du p",
         "barre"))
    for hid, _, tgt, _, _, _ in HYPOTHESES:
        m = measurements.get(hid)
        # Same filter as the table above, for the same reason: a row with no
        # null has no p and no floor, and printing a blank line for it would
        # invite the reader to wonder which number was suppressed.
        if not m or not m["nulls"]:
            continue
        o("  %-5s %-10s %5d %9d %9.4f %9.4f %-13s %.4f"
          % (hid, tmark(tgt), m["folds"], m["null_matched"], m["floor"],
             m["p"], "%s(%d)" % (m["p_basis"], m["p_n"]), bar))
    o("  Avec 4 plis le plancher vaut deja %.4f : un walk-forward PARFAIT a"
      % (0.5 ** 4))
    o("  4 plis ne peut pas atteindre 0.05, meme sans correction. Ces tests")
    o("  sortent SOUS_RESOLU : ils n ont pas echoue, ils ne pouvaient pas")
    o("  conclure. Les lire comme des quasi-succes serait exactement l erreur")
    o("  que ce module combat.")
    o("")
    o("REGLE D ADOPTION")
    o("-" * 74)
    o("  Un signal est ADOPTE seulement si TOUT est vrai :")
    o("   1. >= %d plis de walk-forward" % MIN_FOLDS)
    o("   2. direction HORS ECHANTILLON (majorite des plis de test) egale a la")
    o("      direction ENREGISTREE avant la mesure")
    o("   3. accord >= max(seuil de l hypothese, %.0f%%)" % (MIN_AGREEMENT * 100))
    o("   4. ecart >= %.0f pts contre son PROPRE melange, apparie en plis"
      % MIN_GAP_PTS)
    o("   5. p de permutation <= barre corrigee. Sous %d melanges apparies le"
      % MIN_MATCHED_NULLS)
    o("      p est calcule sur tous les melanges exploitables et ne peut plus")
    o("      rien conclure : le verdict devient SOUS_RESOLU (colonne")
    o("      'base du p').")
    o("   6. PREENREGISTREE : >= %d jours de donnees arrivees APRES elle"
      % MIN_UNSEEN_DAYS)
    o("  Les criteres 2 a 5 sont tous mesures hors echantillon ou contre une")
    o("  nulle. Aucun critere in-sample n entre dans la decision : la colonne")
    o("  in-sample du tableau MESURES est informative et rien d autre.")
    o("  Le critere 4 est neutralise - il ne peut pas rejeter - quand la nulle")
    o("  n est pas appariee, parce que rejeter sur une nulle incomparable")
    o("  serait commettre l erreur que ce module audite.")
    o("  Le critere 3 est un seuil, pas une preuve : la section CONTRE QUOI")
    o("  LIRE UN ACCORD WALK-FORWARD montre qu un predicteur degenere le")
    o("  franchit dans ce design. Passer le critere 3 n est donc jamais un")
    o("  resultat en soi, ce sont les criteres 2, 4 et 5 qui portent la charge.")
    o("  La regle 6 plafonne tout resultat post-hoc a CANDIDAT. Aucune analyse")
    o("  faite aujourd hui ne peut donc promouvoir quoi que ce soit")
    o("  aujourd hui. C est cher, et c est le seul garde-fou qui tienne.")
    o("")
    o("VERDICTS")
    o("-" * 74)
    for hid, sig, tgt, _, _, _ in HYPOTHESES:
        v = verdicts[hid]
        o("  %-5s %-24s %-10s %-13s [%s]%s"
          % (hid, sig, tmark(tgt), v["verdict"], v.get("prereg") or "POST",
             ("  [%s]" % ALT_BASKET_CAVEAT) if tgt.startswith("alt") else ""))
        for r in v["reasons"]:
            o("        %s" % r)
    o("")
    counts = {}
    for v in verdicts.values():
        counts[v["verdict"]] = counts.get(v["verdict"], 0) + 1
    o("  bilan : " + ", ".join("%s=%d" % (k, counts[k])
                               for k in VERDICTS if k in counts))
    o("")
    tiers = ctx.get("gate_tiers")
    if tiers:
        o("CE QUE LA PORTE EN A FAIT - lu dans dimensions.py, pas suppose")
        o("-" * 74)
        o("  Un registre dont personne ne lit les verdicts est un journal")
        o("  intime. Le tier reel de chaque signal juge ici, lu a l execution")
        o("  dans dimensions.SIGNAL_REGISTRY :")
        for label in sorted(tiers):
            hids = [h[0] for h in HYPOTHESES if h[1] == label]
            vs = ", ".join(sorted({verdicts[h]["verdict"] for h in hids}))
            o("    %-24s tier %-6s   ici : %s (%s)"
              % (label, tiers[label] or "absent", vs, ", ".join(hids)))
        o("  Les signaux de rotation (dominance, niveau ETH/BTC) n ont pas de")
        o("  cle dans la porte : ce sont des entrees de rotation, pas des")
        o("  signaux de porte, et leur en inventer une fabriquerait une")
        o("  correspondance.")
        o("")
    o("CONTRE QUOI LIRE UN ACCORD WALK-FORWARD - le controle de soi")
    o("-" * 74)
    ctrl = measurements.get(CONTROL_ID)
    ctrl_h = by_hyp_id(CONTROL_ID)
    if ctrl and ctrl["folds"] and ctrl_h:
        ctrl_tgt = ctrl_h[2]
        o("  %s a ete enregistree comme CONTROLE : \"%s\"."
          % (CONTROL_ID, ctrl_h[5]))
        o("  Elle demande si le niveau ETH/BTC predit le niveau ETH/BTC, sur")
        o("  la cible %s. C est un predicteur DEGENERE : il ne peut rien"
          % tmark(ctrl_tgt))
        o("  apporter, par construction. Les hypotheses de la meme cible,")
        o("  cote a cote, avec le controle au milieu :")
        o("    %-5s %-24s %8s %10s %s"
          % ("id", "signal", "accord", "plis", "verdict"))
        peers = [(h, measurements.get(h[0])) for h in HYPOTHESES
                 if h[2] == ctrl_tgt and measurements.get(h[0])
                 and measurements[h[0]]["folds"]]
        for h, m in peers:
            o("    %-5s %-24s %7.0f%% %7d/%-3d %s%s"
              % (h[0], h[1], m["agreement"] * 100, m["agree"], m["folds"],
                 verdicts[h[0]]["verdict"],
                 "   <-- controle" if h[0] == CONTROL_ID else ""))
        # Computed, not asserted. "The control wins" is the kind of sentence
        # that stays in a report after the numbers move under it; a tie or a
        # defeat has to be able to print itself.
        best = max(m["agreement"] for _, m in peers)
        ties = [h[0] for h, m in peers
                if m["agreement"] >= best and h[0] != CONTROL_ID]
        deeper = [h[0] for h, m in peers
                  if m["agreement"] >= best and m["folds"] > ctrl["folds"]]
        o("")
        o("  Accord du controle : %.0f%% sur %d plis. Aucune hypothese de ce"
          % (ctrl["agreement"] * 100, ctrl["folds"]))
        o("  groupe ne fait mieux ; %d l egalent (%s), aucune sur autant de"
          % (len(ties), ", ".join(ties) if ties else "aucune"))
        o("  plis (%s). Un predicteur degenere tient donc le haut du tableau."
          % (", ".join(deeper) if deeper else "aucune"))
        o("  C est l inference que ce run publie, et elle va contre l intuition")
        o("  qu un accord de plis eleve vaut preuve :")
        o("   - la reference implicite d un accord walk-forward est 50%, deux")
        o("     directions coincidant a pile ou face. C est ce que dit le")
        o("     docstring de walkforward.py, et ce run montre que la reference")
        o("     est fausse dans ce design : un predicteur degenere y atteint")
        o("     %.0f%% sur %d plis." % (ctrl["agreement"] * 100, ctrl["folds"]))
        o("   - la raison est structurelle, pas statistique. Tout l echantillon")
        o("     tient dans UNE SEULE tendance baissiere ETH/BTC. Une direction")
        o("     de gradient qui ne change pas parce que le regime ne change")
        o("     pas se reproduit d un pli au suivant sans qu aucune")
        o("     information ne soit en jeu. L accord mesure alors la")
        o("     persistance du regime, pas le contenu du signal.")
        o("   - donc un accord doit se lire CONTRE LE CONTROLE, pas contre")
        o("     50%%. Aucun signal de ce groupe ne depasse %s, et le depasser"
          % CONTROL_ID)
        o("     serait la seule facon de montrer qu il apporte autre chose que")
        o("     cette persistance.")
        o("   - et cela vaut d abord contre ce run lui-meme : les %d accords"
          % (1 + len(ties)))
        o("     a %.0f%% de ce groupe (%s) ne sont pas %d succes, ce sont un"
          % (best * 100, ", ".join([CONTROL_ID] + ties), 1 + len(ties)))
        o("     controle degenere et %d resultat(s) qui ne s en distinguent"
          % len(ties))
        o("     pas.")
        o("  Le biais 'un seul regime' figure aussi dans le bloc final. Il y")
        o("  est une declaration ; ici il est chiffre par la mesure qui le")
        o("  demontre. C est la difference entre avouer une limite et la")
        o("  rendre lisible.")
        o("  Ce que le controle ne dit PAS : il n annule pas les verdicts. %s"
          % CONTROL_ID)
        o("  est lui-meme %s sur sa propre direction enregistree. Un controle"
          % verdicts[CONTROL_ID]["verdict"])
        o("  qui echoue au reste de la regle reste un etalon d accord, pas un")
        o("  signal, et il n est jamais compte comme une reussite.")
    else:
        o("  Le controle %s n a produit aucun pli dans ce run : il n y a pas"
          % CONTROL_ID)
        o("  d etalon, et les accords ci-dessus n ont donc rien contre quoi")
        o("  etre lus a part 50%, ce qui est insuffisant.")
    o("")
    o("CE QUE CE RUN NE MONTRE PAS")
    o("-" * 74)
    scored_dirs = {}
    for hid, sig, tgt, _, _, _ in HYPOTHESES:
        m = measurements.get(hid)
        if not m or m["folds"] < MIN_FOLDS or m["direction"] is None:
            continue
        scored_dirs.setdefault(sig, []).append((hid, tgt, m["direction"],
                                                m["dir_votes"]))
    pairs = {s: v for s, v in scored_dirs.items() if len(v) >= 2}
    by_id = {h[0]: h for h in HYPOTHESES}
    o("  Le fait etabli n.4 du projet - le signe s inverse selon la cible -")
    o("  est enregistre ici comme PREDICTION : H01 (%+d sur %s) contre H08"
      % (by_id["H01"][3], tmark(by_id["H01"][2])))
    o("  (%+d sur %s). Ce run ne peut pas trancher, et pour DEUX raisons"
      % (by_id["H08"][3], tmark(by_id["H08"][2])))
    o("  differentes qu il ne faut pas confondre :")
    for hid in ("H01", "H08"):
        m = measurements.get(hid)
        o("    %s %-10s %s, %d plis sur %d fenetres decoupees"
          % (hid, tmark(by_id[hid][2]), verdicts[hid]["verdict"],
             m["folds"] if m else 0, m["attempts"] if m else 0))
    o("   - H01 manque de plis : le decoupage n a pas produit assez de")
    o("     fenetres exploitables. C est une limite d echantillon, elle")
    o("     s efface avec le temps.")
    o("   - H08 porte sur une cible RETIREE. Cette limite-la ne s efface pas")
    o("     avec le temps : il faudrait un autre univers d actifs, donc une")
    o("     autre source de donnees.")
    o("  Une inversion exige DEUX cotes mesurables. Aucun des deux cotes ne")
    o("  l est ici, et le fait etabli n.4 reste donc une prediction ecrite,")
    o("  non un resultat de ce run - dans un sens comme dans l autre.")
    if pairs:
        o("  Signaux mesures sur au moins deux cibles avec une direction")
        o("  identifiable de chaque cote (verdict de chaque cote en regard) :")
        for sig, rows in sorted(pairs.items()):
            signs = set(d for _, _, d, _ in rows)
            o("    %-20s %s  ->  %s"
              % (sig,
                 " | ".join("%s %s %s %s"
                            % (hid, tmark(tgt), _fmt_dir(d, v),
                               verdicts[hid]["verdict"])
                            for hid, tgt, d, v in rows),
                 "signes opposes" if len(signs) > 1 else "meme signe"))
        withdrawn_side = sorted({hid for rows in pairs.values()
                                 for hid, tgt, _, _ in rows
                                 if tgt in WITHDRAWN_TARGETS})
        o("  Ces majorites sont DESCRIPTIVES : aucune n a ete testee contre")
        o("  une nulle. Et toute ligne dont un cote est %s porte sur une cible"
          % ALT_MARK)
        if withdrawn_side:
            o("  retiree (%s) : elle ne peut donc etayer NI une inversion NI"
              % ", ".join(withdrawn_side))
            o("  son absence. Lire un signe dans cette colonne serait rouvrir")
            o("  par la bande le resultat que la section CIBLES RETIREES")
            o("  refuse.")
    else:
        o("  Aucun signal n a produit deux directions identifiables sur deux")
        o("  cibles mesurees dans ce run.")
    o("")
    o("BIAIS A DECLARER, VALABLES POUR CHAQUE LIGNE CI-DESSUS")
    o("-" * 74)
    alt_ids = [h[0] for h in HYPOTHESES if h[2].startswith("alt")]
    o("  - %s." % ALT_BASKET_CAVEAT)
    o("    Lignes concernees : %s. Elles portent sur le panier"
      % ", ".join(alt_ids))
    o("    mesurable, pas sur la rotation qu on trade. La marque %s est"
      % ALT_MARK)
    o("    repetee dans chaque tableau pour qu une ligne citee seule la")
    o("    garde avec elle.")
    if am and am[0]:
        o("    Cette marque partagee nomme trois actifs ; ce run en a mesure")
        o("    %d absents de l indice (%s)."
          % (len(am[0]), ", ".join(am[0])))
        o("    Elle est donc plus faible que la mesure, et c est la section")
        o("    CIBLES RETIREES qui porte le chiffre. La chaine reste celle de")
        o("    rotation_matrix.py : la reecrire ici la ferait diverger entre")
        o("    deux rapports, ce qui coute plus qu elle ne rapporte.")
    o("  - fenetres forward chevauchantes : les plis ne sont pas independants,")
    o("    ce qui rend le controle par melange indispensable et laisse le p")
    o("    optimiste malgre tout.")
    o("  - tout l echantillon tient dans une seule tendance baissiere ETH/BTC.")
    o("    Ce biais n est pas seulement declare ici : il est MESURE par le")
    o("    controle %s, qui atteint %s d accord en predisant le niveau par"
      % (CONTROL_ID,
         ("%.0f%%" % (measurements[CONTROL_ID]["agreement"] * 100))
         if measurements.get(CONTROL_ID)
         and measurements[CONTROL_ID]["agreement"] is not None else "-"))
    o("    lui-meme. Voir la section CONTRE QUOI LIRE UN ACCORD WALK-FORWARD :")
    o("    c est la que ce biais cesse d etre un aveu pour devenir un chiffre,")
    o("    et c est ce chiffre - pas 50% - qui est la reference des accords")
    o("    imprimes plus haut.")
    o("  - dominance calculee sur un UNIVERS de %d a %d actifs selon le jour"
      % (b_lo, b_hi))
    o("    (et non un panier de cette taille : le panier alt est le top %d)."
      % br.TOP_N)
    o("    Le niveau est donc biaise ; seuls les rangs sont utilisables.")
    o("  - la cible eth_btc est l index rotations.json, pas analysis/")
    o("    ethbtc.json ; ecart forward maximum mesure %.2f pt (voir en-tete)."
      % (div["max_diff"] if div else float("nan")))
    o("  - toutes les hypotheses ci-dessus sont POST-HOC, et le registre le")
    o("    dit. La premiere date ou l une d elles pourra etre jugee")
    o("    preenregistree est le %s." % first_pre)
    return o


if __name__ == "__main__":
    sys.exit(main())
