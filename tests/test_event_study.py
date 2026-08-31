#!/usr/bin/env python3
"""
Tests for the 2021 event study. No network, no clock, no rate budget.

What these guard is narrower than it looks. The study's headline - "the signal
set cannot be evaluated against 2021" - is a claim about data that does not
exist, and you cannot unit-test an absence into being true. What you CAN test
is that the study reports absence honestly: that a missing series never
acquires a vote, that a blank never collapses into a "no", that the
denominators are the ones the pipeline itself uses, and that the thresholds
being applied are still the live ones.

Every test injects its inputs. The two that read analysis/ are marked and skip
themselves when the files are not there, so a fresh clone still runs green.

Run: python -m unittest discover -s tests
"""

import contextlib
import datetime
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))

import dimensions
import event_study
import ladder
import montecarlo

ANALYSIS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "analysis")


def _contiguous_series(n, start=datetime.date(2021, 1, 1)):
    """A gapless daily series in montecarlo's list-of-levels shape.

    Values are deterministic and chosen to cross every threshold in play, so a
    comparison against montecarlo.to_votes exercises both branches of each
    rule rather than agreeing trivially on a constant.
    """
    dates = [(start + datetime.timedelta(days=i)).isoformat() for i in range(n)]
    return dates, {
        "mvrv_z_score": [2.0 + (i % 7) * 0.5 for i in range(n)],
        "nvt": [50.0 + (i % 11) * 3.0 for i in range(n)],
        "fear_greed": [40.0 + (i % 25) for i in range(n)],
        "stablecoin_supply_ratio": [10.0 + (i % 13) for i in range(n)],
    }


class TestThresholdsHaveNotDrifted(unittest.TestCase):
    """The study duplicates two thresholds to stay offline. That duplication
    is only safe while something fails when it drifts - this is that thing."""

    def test_momentum_threshold_matches_the_ladder_rule(self):
        rule = ladder.LADDER_RULES["eth_btc_momentum"]
        just_over = {"signal": event_study.MOMENTUM_THRESHOLD + 0.01}
        just_under = {"signal": event_study.MOMENTUM_THRESHOLD - 0.01}
        self.assertTrue(rule(just_over))
        self.assertFalse(rule(just_under))

    def test_mvrv_z_threshold_matches_the_rule_the_gate_applies(self):
        """MVRV Z is scored from a BARE value - `val > 3.0` in fetch_signals,
        the same shape as fear_greed > 60. It was previously grouped with NVT
        and SSR and blanked under a justification about reference windows that
        is false for it. montecarlo.to_votes applies the live rule, so the
        boundary is checked against that rather than against a copy."""
        dates, raw = _contiguous_series(95)
        raw["mvrv_z_score"][-1] = event_study.MVRV_Z_THRESHOLD + 0.01
        self.assertTrue(montecarlo.to_votes(raw, dates)[-1]["mvrv_z_score"])
        raw["mvrv_z_score"][-1] = event_study.MVRV_Z_THRESHOLD - 0.01
        self.assertFalse(montecarlo.to_votes(raw, dates)[-1]["mvrv_z_score"])

    def test_reference_windows_match_the_ones_the_gate_uses(self):
        """A shorter window would be a different rule wearing the same name."""
        self.assertEqual(event_study.NVT_AVG_DAYS, 90)
        self.assertEqual(event_study.SSR_LOOKBACK_DAYS, 30)

    def test_fear_greed_threshold_is_a_plausible_index_level(self):
        # F&G is bounded 0-100; a threshold outside that would silently make
        # the signal fire always or never, and the table would look normal.
        self.assertTrue(0 < event_study.FEAR_GREED_THRESHOLD < 100)

    def test_every_tier_a_signal_is_accounted_for(self):
        """No Tier A signal may be quietly dropped from the study. A signal
        with neither a column nor an absence reason would vanish from the
        coverage arithmetic without anyone noticing."""
        columns = {k for k, _ in event_study.COLUMNS}
        self.assertEqual(columns, set(dimensions.TIER_A_SIGNALS))
        for key in dimensions.TIER_A_SIGNALS:
            self.assertIn(key, columns, key)

    def test_absence_reasons_only_describe_real_signals(self):
        for key in event_study.ABSENCE_REASONS:
            self.assertIn(key, dimensions.TIER_A_SIGNALS, key)

    def test_every_rotation_signal_is_accounted_for(self):
        """The ladder side, which the Tier A dicts do not cover.

        Three of ladder.ROTATION_SIGNALS - btc_dominance, alt_dominance,
        altseason_index - are not Tier A at all, so ABSENCE_REASONS never
        mentions them. An earlier version of this study printed 14.29% ladder
        coverage without naming them anywhere in a 390-line report: three
        signals asserted unreadable and never explained. Every rotation signal
        must now be either reconstructable or carry a written reason.
        """
        for key in ladder.ROTATION_SIGNALS:
            reason = event_study.absence_reason(key)
            if reason is None:
                # Reconstructable signals legitimately have no reason. The
                # only forbidden state is "neither readable nor explained",
                # which the paired test below pins against the real archive.
                continue
            kind, why = reason
            self.assertTrue(kind.strip(), key)
            self.assertTrue(why.strip(), key)

    def test_rotation_only_reasons_are_not_tier_a_signals(self):
        """Kept in a separate dict on purpose: a key in both would give one
        signal two different stories about why it is blank."""
        for key in event_study.ROTATION_ONLY_ABSENCE:
            self.assertIn(key, ladder.ROTATION_SIGNALS, key)
            self.assertNotIn(key, dimensions.TIER_A_SIGNALS, key)
            self.assertNotIn(key, event_study.ABSENCE_REASONS, key)


class TestMomentum(unittest.TestCase):

    def test_percent_change_over_fourteen_calendar_days(self):
        prices = {"2021-02-01": 0.02, "2021-02-15": 0.022}
        self.assertAlmostEqual(
            event_study.momentum_14d(prices, "2021-02-15"), 10.0, places=6)

    def test_missing_start_returns_none_not_a_nearest_neighbour(self):
        """A gap must stay a gap. Reaching for the nearest available day would
        silently lengthen the window and change the rule under test."""
        prices = {"2021-02-10": 0.02, "2021-02-15": 0.03}
        self.assertIsNone(event_study.momentum_14d(prices, "2021-02-15"))

    def test_missing_end_returns_none(self):
        prices = {"2021-02-01": 0.02}
        self.assertIsNone(event_study.momentum_14d(prices, "2021-02-15"))

    def test_zero_start_returns_none_rather_than_dividing(self):
        prices = {"2021-02-01": 0.0, "2021-02-15": 0.02}
        self.assertIsNone(event_study.momentum_14d(prices, "2021-02-15"))


class TestBuildSignals(unittest.TestCase):
    """The core honesty property: absent means absent, not false."""

    def _prices(self, start_val, end_val):
        return {"2021-02-01": start_val, "2021-02-15": end_val}

    def test_absent_signal_carries_no_value_and_no_vote(self):
        s = event_study.build_signals("2021-02-15", self._prices(0.02, 0.03),
                                      {}, {})
        for key in ("mvrv_z_score", "nvt", "stablecoin_supply_ratio",
                    "sth_realized_price", "eth_etf_flows", "alt_funding_rates",
                    "exchange_netflows"):
            self.assertIsNone(s[key]["signal"], key)
            self.assertIsNone(s[key]["vote"], key)
            self.assertEqual(s[key]["status"], "no_data", key)

    def test_absent_signal_is_present_as_a_row_not_omitted(self):
        """The whole point of the study. A dropped key would let a reader
        count seven blanks as a quiet signal set rather than a blind one."""
        s = event_study.build_signals("2021-02-15", self._prices(0.02, 0.03),
                                      {}, {})
        for key in dimensions.TIER_A_SIGNALS:
            self.assertIn(key, s, key)
        for key in ladder.ROTATION_SIGNALS:
            self.assertIn(key, s, key)

    def test_momentum_votes_only_against_its_own_threshold(self):
        over = event_study.build_signals("2021-02-15",
                                         self._prices(0.02, 0.0230), {}, {})
        self.assertTrue(over["eth_btc_momentum"]["vote"])
        under = event_study.build_signals("2021-02-15",
                                          self._prices(0.02, 0.0201), {}, {})
        self.assertFalse(under["eth_btc_momentum"]["vote"])

    def test_fear_greed_read_from_the_archive_not_invented(self):
        s = event_study.build_signals("2021-02-15", {}, {}, {"2021-02-15": 77.0})
        self.assertEqual(s["fear_greed"]["signal"], 77.0)
        self.assertTrue(s["fear_greed"]["vote"])
        s2 = event_study.build_signals("2021-02-15", {}, {}, {"2021-02-15": 40.0})
        self.assertFalse(s2["fear_greed"]["vote"])

    def test_a_value_without_its_reference_window_is_reported_not_scored(self):
        """NVT votes against its own 90-day average and SSR against a 30-day
        reference. Given one bare value neither window exists, so the value
        must print with no vote - never a vote derived from a shorter window.
        The note must say WHICH of the two kinds of blank this is, because a
        missing reference and a missing series cost different work to fix."""
        series = {"nvt": {"2021-02-15": 40.0},
                  "stablecoin_supply_ratio": {"2021-02-15": 12.0}}
        s = event_study.build_signals("2021-02-15", {}, series, {})
        for key in ("nvt", "stablecoin_supply_ratio"):
            self.assertIsNotNone(s[key]["signal"], key)
            self.assertIsNone(s[key]["vote"], key)
            self.assertIn("value on disk", s[key]["note"], key)

    def test_sth_needs_both_legs_before_it_scores(self):
        series = {"sth_realized_price": {"2021-02-15": 30000.0}}
        without = event_study.build_signals("2021-02-15", {}, series, {})
        self.assertIsNone(without["sth_realized_price"]["vote"])
        withclose = event_study.build_signals("2021-02-15", {}, series, {},
                                              {"2021-02-15": 47000.0})
        self.assertTrue(withclose["sth_realized_price"]["vote"])
        below = event_study.build_signals("2021-02-15", {}, series, {},
                                          {"2021-02-15": 20000.0})
        self.assertFalse(below["sth_realized_price"]["vote"])


class TestReferenceWindows(unittest.TestCase):
    """The three signals whose blanks used to be hardcoded.

    `vote: None` was written into build_signals for mvrv_z_score, nvt and
    stablecoin_supply_ratio rather than made conditional on the reference
    window existing. That meant a real backfill would have left section 2
    printing "ABSENT [NO HISTORY ON DISK]" above rows showing live values,
    with every test still green - the exact drift the measured-availability
    tables were built to end. These tests inject the window and require the
    vote to appear, and withhold it and require the vote to stay None.
    """

    def test_mvrv_scores_from_a_bare_value_with_no_window_at_all(self):
        s = event_study.build_signals(
            "2021-02-15", {}, {"mvrv_z_score": {"2021-02-15": 3.5}}, {})
        self.assertTrue(s["mvrv_z_score"]["vote"])
        s = event_study.build_signals(
            "2021-02-15", {}, {"mvrv_z_score": {"2021-02-15": 2.5}}, {})
        self.assertFalse(s["mvrv_z_score"]["vote"])

    def _nvt(self, n_prior):
        day = datetime.date(2021, 2, 15)
        hist = {(day - datetime.timedelta(days=k)).isoformat(): 10.0
                for k in range(1, n_prior + 1)}
        hist[day.isoformat()] = 20.0
        return event_study.build_signals("2021-02-15", {}, {"nvt": hist}, {})

    def test_nvt_scores_once_all_ninety_prior_days_are_on_disk(self):
        s = self._nvt(event_study.NVT_AVG_DAYS)
        self.assertTrue(s["nvt"]["vote"])
        self.assertAlmostEqual(s["nvt"]["avg_90d"], 10.0)

    def test_nvt_one_day_short_reports_the_value_and_no_vote(self):
        """All-or-nothing on the window. Averaging over the 89 days that did
        survive would quietly shorten the window and change the rule."""
        s = self._nvt(event_study.NVT_AVG_DAYS - 1)
        self.assertEqual(s["nvt"]["signal"], 20.0)
        self.assertIsNone(s["nvt"]["vote"])
        self.assertIn("prior daily points", s["nvt"]["note"])

    def _ssr(self, ref_day_present):
        hist = {"2021-02-15": 10.0}
        if ref_day_present:
            back = (datetime.date(2021, 2, 15)
                    - datetime.timedelta(days=event_study.SSR_LOOKBACK_DAYS))
            hist[back.isoformat()] = 12.0
        return event_study.build_signals(
            "2021-02-15", {}, {"stablecoin_supply_ratio": hist}, {})

    def test_ssr_scores_once_the_single_reference_point_is_on_disk(self):
        s = self._ssr(True)["stablecoin_supply_ratio"]
        self.assertTrue(s["vote"])          # 10 < 12, SSR is falling
        self.assertEqual(s["ref_value"], 12.0)

    def test_ssr_without_its_reference_point_is_reported_not_scored(self):
        s = self._ssr(False)["stablecoin_supply_ratio"]
        self.assertEqual(s["signal"], 10.0)
        self.assertIsNone(s["vote"])
        self.assertIn("days earlier", s["note"])

    def test_a_scored_ssr_also_counts_toward_ladder_coverage(self):
        """SSR is the one backfillable signal on the ROTATION axis, and
        ladder.LADDER_RULES reads its `ref_value` field. Filling that field is
        what makes the two axes agree about whether SSR is readable."""
        signals = self._ssr(True)
        self.assertTrue(ladder._measurable(
            signals["stablecoin_supply_ratio"], "stablecoin_supply_ratio"))
        self.assertFalse(ladder._measurable(
            self._ssr(False)["stablecoin_supply_ratio"],
            "stablecoin_supply_ratio"))

    def test_votes_agree_with_montecarlo_over_a_contiguous_series(self):
        """The strongest cross-check available offline.

        montecarlo.to_votes is the live vote code for these four signals. Over
        a gapless daily series its index-based windows and this study's
        calendar-based ones must produce identical booleans on every day; a
        retune of any threshold or window length in one and not the other
        fails here.
        """
        dates, raw = _contiguous_series(150)
        votes = montecarlo.to_votes(raw, dates)
        series = {k: dict(zip(dates, v)) for k, v in raw.items()
                  if k != "fear_greed"}
        fng = dict(zip(dates, raw["fear_greed"]))
        offset = len(dates) - len(votes)
        for j, expected in enumerate(votes):
            day = dates[offset + j]
            got = event_study.build_signals(day, {}, series, fng)
            for key, want in expected.items():
                self.assertEqual(got[key]["vote"], want, "%s on %s" % (key, day))


class TestCoverageArithmetic(unittest.TestCase):
    """Coverage is computed by dimensions.tally and ladder.compute_t, not by
    this study. These tests pin that delegation, because a study that
    reimplemented the arithmetic would be measuring itself."""

    def _row(self, **kw):
        return event_study.score_date("2021-02-15",
                                      kw.get("prices", {}),
                                      kw.get("series", {}),
                                      kw.get("fng", {}),
                                      kw.get("btc"))

    def test_gate_coverage_denominator_is_the_full_tier_a_set(self):
        """Nine, always. Shrinking the denominator to what happened to be
        readable would turn 2-of-9 into 2-of-2 and report 100% coverage."""
        r = self._row(prices={"2021-02-01": 0.02, "2021-02-15": 0.03},
                      fng={"2021-02-15": 77.0})
        self.assertEqual(r["gate_total"], 9)
        self.assertEqual(r["gate_checkable"], 2)
        self.assertAlmostEqual(r["gate_coverage_pct"], 200 / 9, places=6)

    def test_nothing_readable_is_zero_coverage_not_zero_signal(self):
        r = self._row()
        self.assertEqual(r["gate_checkable"], 0)
        self.assertEqual(r["gate_fired"], 0)
        self.assertFalse(r["gate_reachable"])

    def test_gate_reachable_separates_blind_from_quiet(self):
        """`would_fire` False means two different things - not enough evidence,
        or not enough EYES. Only `gate_reachable` tells them apart, and
        conflating them is how 2021 gets read as a correct all-clear."""
        blind = self._row(prices={"2021-02-01": 0.02, "2021-02-15": 0.03},
                          fng={"2021-02-15": 77.0})
        self.assertFalse(blind["gate_would_fire"])
        self.assertFalse(blind["gate_reachable"])
        self.assertLess(blind["gate_checkable"], dimensions.TIER_A_THRESHOLD)

    def test_ladder_coverage_is_one_of_seven_capped_units(self):
        """Momentum alone carries weight 1.0 of the 7.0 possible capped units
        (D1 caps at 3.0, plus four dimensions at 1.0 each)."""
        r = self._row(prices={"2021-02-01": 0.02, "2021-02-15": 0.03},
                      fng={"2021-02-15": 77.0})
        self.assertAlmostEqual(r["ladder_coverage"], round(1.0 / 7.0, 4),
                               places=4)

    def test_fear_greed_does_not_lift_ladder_coverage(self):
        """D3 is deliberately absent from the ladder, so the one extra signal
        the 2021 archive provides helps the gate and not the ladder. If this
        ever passes, someone has re-added sentiment to the rotation axis."""
        with_fng = self._row(prices={"2021-02-01": 0.02, "2021-02-15": 0.03},
                             fng={"2021-02-15": 77.0})
        without = self._row(prices={"2021-02-01": 0.02, "2021-02-15": 0.03})
        self.assertEqual(with_fng["ladder_coverage"], without["ladder_coverage"])

    def test_ladder_is_not_measurable_below_the_floor(self):
        r = self._row(prices={"2021-02-01": 0.02, "2021-02-15": 0.03})
        self.assertLess(r["ladder_coverage"], ladder.COVERAGE_FLOOR)
        self.assertFalse(r["ladder_measurable"])


class TestRotationOutcome(unittest.TestCase):
    """The half of the study that always works, because it needs no signal."""

    PRICES = {
        "2021-02-01": 0.04,
        "2021-02-02": 0.05,   # peak
        "2021-02-03": 0.03,   # post-peak low
        "2021-02-04": 0.044,
    }

    def test_window_change_open_to_close(self):
        out = event_study.rotation_outcome(self.PRICES, "2021-02-01",
                                           "2021-02-04")
        self.assertAlmostEqual(out["change_pct"], 10.0, places=6)

    def test_drawdown_is_measured_after_the_peak_not_across_the_window(self):
        """A window low that PRECEDES the peak is not a drawdown anyone took."""
        out = event_study.rotation_outcome(self.PRICES, "2021-02-01",
                                           "2021-02-04")
        self.assertEqual(out["peak_date"], "2021-02-02")
        self.assertEqual(out["drawdown_low_date"], "2021-02-03")
        self.assertAlmostEqual(out["drawdown_from_peak_pct"], -40.0, places=6)

    def test_peak_on_the_last_day_is_flagged_not_reported_as_zero(self):
        """Reporting 0.0% would be a fabricated reassurance: the window simply
        ended before any post-peak observation existed."""
        rising = {"2021-02-01": 0.04, "2021-02-02": 0.05}
        out = event_study.rotation_outcome(rising, "2021-02-01", "2021-02-02")
        self.assertTrue(out["peak_is_last_day"])

    def test_single_priced_day_returns_none(self):
        self.assertIsNone(
            event_study.rotation_outcome({"2021-02-01": 0.04},
                                         "2021-02-01", "2021-02-01"))

    def test_follow_through_needs_both_ends(self):
        self.assertIsNone(event_study.follow_through(self.PRICES, "2021-02-04"))
        prices = dict(self.PRICES)
        prices["2021-03-06"] = 0.088
        ft = event_study.follow_through(prices, "2021-02-04", days=30)
        self.assertAlmostEqual(ft["change_pct"], 100.0, places=6)


class TestLoadersRefuseToGuess(unittest.TestCase):

    def test_missing_files_report_missing_and_return_empty(self):
        missing = os.path.join(os.path.dirname(__file__), "_no_such_dir")
        data, note = event_study.load_ethbtc(os.path.join(missing, "x.json"))
        self.assertEqual(data, {})
        self.assertIn("MISSING", note)
        data, note = event_study.load_series(os.path.join(missing, "y.json"))
        self.assertEqual(data, {})
        self.assertIn("MISSING", note)
        data, note = event_study.load_fear_greed(missing)
        self.assertEqual(data, {})
        self.assertIn("MISSING", note)
        data, note = event_study.load_btc_price(missing)
        self.assertEqual(data, {})
        self.assertIn("MISSING", note)


class TestAvailabilityIsMeasuredNotAsserted(unittest.TestCase):
    """The PRESENT/ABSENT tables must come from the data, not from the prose.

    Deriving them from ABSENCE_REASONS would mean that after a backfill the
    tables keep printing 'ABSENT [NO HISTORY ON DISK]' while the dated rows
    below show live values, and nothing anywhere fails. These tests inject a
    backfill that does not exist on disk and require the verdict to move.
    """

    WINDOW = [("T", "2021-02-14", "2021-02-16", "test window")]

    def test_measured_set_is_empty_when_nothing_is_readable(self):
        self.assertEqual(
            event_study.measure_tier_a_availability({}, {}, {},
                                                    windows=self.WINDOW),
            set())

    def test_a_backfill_moves_the_verdict_without_touching_the_dict(self):
        series = {"sth_realized_price": {"2021-02-15": 1000.0}}
        btc = {"2021-02-15": 2000.0}
        measured = event_study.measure_tier_a_availability(
            {}, series, {}, btc, windows=self.WINDOW)
        self.assertIn("sth_realized_price", measured)
        # ABSENCE_REASONS still claims it is absent - which is exactly the
        # drift the real-data test below catches and a human then fixes.
        self.assertIn("sth_realized_price", event_study.ABSENCE_REASONS)

    def test_a_value_without_a_vote_does_not_count_as_available(self):
        """NVT prints a number whose vote rule needs a 90-day reference this
        study does not archive. A number nobody can score does not make the
        gate readable, and must not be counted as though it did."""
        series = {"nvt": {"2021-02-15": 40.0}}
        measured = event_study.measure_tier_a_availability(
            {}, series, {}, windows=self.WINDOW)
        self.assertNotIn("nvt", measured)

    def test_rotation_availability_uses_the_ladders_own_test(self):
        prices = {"2021-02-01": 0.02, "2021-02-15": 0.03}
        measured = event_study.measure_rotation_availability(
            prices, {}, {}, windows=self.WINDOW)
        self.assertEqual(measured, {"eth_btc_momentum"})


class TestFearGreedCacheConflicts(unittest.TestCase):
    """Merging is last-wins by sorted path, so on a disagreeing day the answer
    depends on how a sibling script named its download. That is tolerable only
    while it is visible, so the loader counts disagreements and says so."""

    def _write(self, d, name, pairs):
        path = os.path.join(d, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"data": [{"timestamp": str(ts), "value": str(v)}
                                for ts, v in pairs]}, f)

    def test_agreeing_files_report_zero_disagreements(self):
        with tempfile.TemporaryDirectory() as d:
            self._write(d, "a_fng.json", [(1612137600, 70)])
            self._write(d, "b_fng.json", [(1612137600, 70)])
            data, note = event_study.load_fear_greed(d)
            self.assertEqual(len(data), 1)
            self.assertIn("0 disagreements", note)
            self.assertNotIn("WARNING", note)

    def test_disagreeing_files_warn_and_name_the_last_wins_rule(self):
        with tempfile.TemporaryDirectory() as d:
            self._write(d, "a_fng.json", [(1612137600, 70)])
            self._write(d, "b_fng.json", [(1612137600, 20)])
            data, note = event_study.load_fear_greed(d)
            self.assertIn("WARNING", note)
            self.assertIn("LAST-WINS", note)
            self.assertEqual(list(data.values()), [20.0])  # b_ sorts last

    def test_the_count_is_formatted_in_both_branches_not_a_literal_zero(self):
        """The no-conflict note used to carry the literal string "0
        disagreements", correct only because the conflict branch overwrote the
        whole note. Reorder or merge those statements and a fabricated zero
        ships, with the agreeing-files test above still green because it
        asserts on that same literal. Both branches must FORMAT the count."""
        with tempfile.TemporaryDirectory() as d:
            self._write(d, "a_fng.json", [(1612137600, 70)])
            self._write(d, "b_fng.json", [(1612137600, 20)])
            _, note = event_study.load_fear_greed(d)
            self.assertIn("1 disagreements", note)
            self.assertNotIn("0 disagreements", note)


class TestRender(unittest.TestCase):
    """render() had no test at all, which is how a dropped argument shipped.

    main() used to call render(prices, series, fng, notes) and silently drop
    the BTC close it had just loaded. It changed no printed number only
    because series.json holds no 2021 STH cost basis to pair the close with -
    a latent undercount that a backfill would have exposed as a wrong report
    rather than a crash.
    """

    SERIES = {"sth_realized_price": {"2021-02-15": 1000.0}}
    BTC = {"2021-02-15": 2000.0}

    def _render(self, btc):
        return "\n".join(event_study.render({}, self.SERIES, {}, [], btc))

    def _dated_rows(self, text):
        """Only the rows of the dated tables. The prose above them mentions
        FIRE while explaining the legend, so a whole-text search would pass
        for the wrong reason."""
        return [ln for ln in text.splitlines()
                if ln.startswith("   2021-") and len(ln) > 60]

    def test_sth_renders_a_value_and_a_fire_when_both_legs_are_passed(self):
        text = self._render(self.BTC)
        rows = self._dated_rows(text)
        hit = [ln for ln in rows if ln.startswith("   2021-02-15")]
        self.assertEqual(len(hit), 1, "expected exactly one dated row")
        self.assertIn("1000.00", hit[0])
        self.assertIn("FIRE", hit[0])
        # No prices and no F&G were injected, so STH is the only signal that
        # can fire anywhere in the tables. One fired row, and it is this one.
        self.assertEqual([ln for ln in rows if "FIRE" in ln], hit)

    def test_dropping_btc_downgrades_the_same_row_to_reported_not_scored(self):
        rows = self._dated_rows(self._render(None))
        hit = [ln for ln in rows if ln.startswith("   2021-02-15")][0]
        self.assertIn("1000.00", hit)      # the value is still reported
        self.assertIn("?", hit)            # readable, not scoreable
        self.assertNotIn("FIRE", hit)      # and nothing was scored from it
        self.assertEqual([ln for ln in rows if "FIRE" in ln], [])

    def test_availability_table_follows_the_data_not_the_dict(self):
        with_btc = self._render(self.BTC)
        without = self._render(None)
        self.assertIn("sth_realized_price       STH   PRESENT", with_btc)
        self.assertIn("sth_realized_price       STH   ABSENT", without)

    def test_the_rotation_section_names_all_eight_rotation_signals(self):
        text = self._render(self.BTC)
        self.assertIn("2R. LADDER ROTATION SIGNAL AVAILABILITY", text)
        for key in ladder.ROTATION_SIGNALS:
            self.assertIn(key, text, key)

    def test_the_momentum_reconstruction_caveat_is_printed_not_just_docstringed(self):
        """A caveat only the author reads is not a caveat. A reader of the
        .txt sees 'MOM 19.26 FIRE' and must be told it is a 14-calendar-day
        change off an unverified series, not the live fetcher's bytes."""
        text = self._render(self.BTC)
        self.assertIn("CALENDAR", text)
        self.assertIn("AMBIGUOUS", text)
        self.assertIn("ethbtc.json", text)


class TestSyntheticBackfill(unittest.TestCase):
    """Section 7 used to ASSERT what a backfill would buy. It now measures it.

    The claim was "2 -> 6 of 9". Injecting the prescribed backfill against the
    module as it then stood moved the count to 3, because three of the four
    backfilled signals had `vote: None` hardcoded. The number is now computed
    from the same availability scan the rest of the report uses, so it cannot
    disagree with the module that prints it.
    """

    WINDOW = [("T", "2021-02-14", "2021-02-16", "test window")]

    def test_the_copy_never_mutates_the_series_it_was_given(self):
        """The placeholders exist to answer one availability question. Leaking
        them into the caller's series would put invented levels into the dated
        tables - the silent proxy this whole study refuses to make."""
        series = {"nvt": {"2022-09-01": 40.0}}
        before = json.dumps(series, sort_keys=True)
        event_study.synthetic_backfill(series, windows=self.WINDOW)
        self.assertEqual(json.dumps(series, sort_keys=True), before)

    def test_the_backfill_carries_its_own_reference_windows(self):
        """Filling only the window days would blank NVT on every one of them
        and understate what the backfill buys."""
        filled = event_study.synthetic_backfill({}, windows=self.WINDOW)
        for key in event_study.BACKFILL_KEYS:
            self.assertIn(key, filled)
        pad = event_study.NVT_AVG_DAYS
        first = event_study._shift("2021-02-14", -pad)
        self.assertIn(first, filled["nvt"])

    def test_all_four_backfilled_signals_become_scoreable(self):
        """The gain is measured end to end: four keys in, four keys scoreable.
        STH-RP needs its second leg, so a BTC close is supplied as section 7
        prescribes - without it the honest answer is three, not four."""
        filled = event_study.synthetic_backfill({}, windows=self.WINDOW)
        btc = {d: 1.0 for d in event_study.daterange("2021-02-14", "2021-02-16")}
        measured = event_study.measure_tier_a_availability(
            {}, filled, {}, btc, windows=self.WINDOW)
        self.assertEqual(measured, set(event_study.BACKFILL_KEYS))

    def test_without_the_btc_close_sth_stays_unscoreable(self):
        filled = event_study.synthetic_backfill({}, windows=self.WINDOW)
        measured = event_study.measure_tier_a_availability(
            {}, filled, {}, {}, windows=self.WINDOW)
        self.assertNotIn("sth_realized_price", measured)

    def test_the_backfill_leaves_the_ladder_below_its_floor(self):
        """The finding the measurement produced: of the four series section 7
        prescribes, only SSR is on the rotation axis, so the backfill is a
        GATE fix and the ladder stays frozen. If this ever fails, someone has
        widened the backfill and section 7's conclusion needs rewriting."""
        filled = event_study.synthetic_backfill({}, windows=self.WINDOW)
        prices = {d: 0.02 for d in
                  event_study.daterange("2021-01-01", "2021-03-31")}
        best = max((ladder.compute_t(
            event_study.build_signals(d, prices, filled, {}, {}))
            for _, st, en, _ in self.WINDOW
            for d in event_study.daterange(st, en)),
            key=lambda t: t["coverage"])
        self.assertLess(best["coverage"], ladder.COVERAGE_FLOOR)


class TestMonteCarloBasisIsDerived(unittest.TestCase):
    """Section 7 used to print "1366 days starting 2022-11" as prose.

    It was correct when written and would have gone stale silently as
    series.json grows - the same fault the measured tables removed everywhere
    else in this module.
    """

    def test_basis_matches_montecarlo_or_is_declined(self):
        basis = event_study.montecarlo_basis()
        if basis is None:
            raise unittest.SkipTest("analysis/series.json not readable")
        dates, raw = montecarlo.load_series()
        votes = montecarlo.to_votes(raw, dates)
        self.assertEqual(basis["days"], len(votes))
        self.assertEqual(basis["first"], dates[len(dates) - len(votes)])

    def test_the_report_prints_no_hardcoded_day_count(self):
        text = "\n".join(event_study.render({}, {}, {}, [], {}))
        self.assertNotIn("1366 days starting 2022-11", text)


class TestGitignoredInputsAreDeclared(unittest.TestCase):
    """The committed report's headline depends on a gitignored directory.

    analysis/.cache/ holds the only F&G archive and the only BTC close. A
    fresh checkout has neither and the same study then measures one readable
    Tier A signal, not two. That caveat previously existed only in a comment
    in .github/workflows/analysis.yml, which the report's reader never opens -
    and this study's own rule is that a caveat only the author reads is not a
    caveat.
    """

    def test_section_one_names_the_gitignored_cache_and_both_figures(self):
        prices = {"2021-02-01": 0.02, "2021-02-15": 0.03}
        text = "\n".join(event_study.render(prices, {}, {"2021-02-15": 77.0},
                                            [], {}))
        self.assertIn("GITIGNORED", text)
        self.assertIn("analysis/.cache/", text)
        # Both counts measured from the same scan: 2 with the cache, 1 without.
        self.assertIn("1 of 9 readable Tier A signals instead of the 2 of 9",
                      text)

    def test_it_says_ci_skips_the_report_when_the_fetch_fails(self):
        text = "\n".join(event_study.render({}, {}, {}, [], {}))
        self.assertIn("skips this report entirely if that fetch fails", text)

    def test_the_workflow_actually_does_what_the_report_claims(self):
        """A claim printed in the report about another file is still a claim.

        Pinned by reading the workflow, because the previous version said the
        curl degraded gracefully with `|| true` - which is what let a thinner
        report overwrite a thicker one, silently and green.
        """
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                            ".github", "workflows", "analysis.yml")
        if not os.path.exists(path):
            raise unittest.SkipTest("workflow not present")
        with open(path, encoding="utf-8") as f:
            wf = f.read()
        body = wf.split("- name: Commit results")[0]
        self.assertNotIn("format=json' || true", body)
        self.assertIn("python scripts/event_study.py", body)
        # The study must run only inside the branch guarded by the fetch.
        guard = body.split("if curl")[1].split("fi")[0]
        self.assertIn("python scripts/event_study.py", guard)
        # And the second gitignored input is at least named, not left silent.
        self.assertIn("btc_price_usd.json", body)


class TestMainSmoke(unittest.TestCase):
    """End to end, against the real archive, writing to a throwaway path."""

    def test_main_writes_a_report_carrying_the_headline_and_the_banner(self):
        prices, _ = event_study.load_ethbtc()
        if not prices:
            raise unittest.SkipTest("analysis/ethbtc.json not present")
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "event_study_2021.txt")
            original = event_study.OUT_PATH
            event_study.OUT_PATH = out
            try:
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = event_study.main()
            finally:
                event_study.OUT_PATH = original
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.getsize(out) > 0)
            with open(out, encoding="utf-8") as f:
                text = f.read()
        self.assertIn("22.2%", text)
        self.assertIn("SHADOW ONLY", text)


class TestAgainstRealData(unittest.TestCase):
    """The findings themselves, asserted against the files on disk.

    These skip rather than fail when analysis/ is empty: a fresh clone has no
    archive, and a test suite that goes red for that reason teaches people to
    ignore it.
    """

    @classmethod
    def setUpClass(cls):
        cls.prices, _ = event_study.load_ethbtc()
        cls.series, _ = event_study.load_series()
        cls.fng, _ = event_study.load_fear_greed()
        cls.btc, _ = event_study.load_btc_price()
        if not cls.prices:
            raise unittest.SkipTest("analysis/ethbtc.json not present")

    def test_ethbtc_covers_both_windows(self):
        for _, start, end, _ in event_study.WINDOWS:
            days = event_study.daterange(start, end)
            have = [d for d in days if d in self.prices]
            self.assertEqual(len(have), len(days),
                             "ETH/BTC has gaps in %s -> %s" % (start, end))

    def test_the_coverage_floor_never_holds_in_2021(self):
        """The finding that matters most: the ladder would have been frozen
        through both altseasons, so its measured whipsaw record has never been
        exposed to a 2021-shaped move."""
        scan = event_study.coverage_floor_scan(
            "2021", self.prices, self.series, self.fng, self.btc)
        self.assertEqual(scan["days"], 365)
        self.assertEqual(scan["days_above_floor"], 0)
        self.assertLess(scan["max_coverage"], ladder.COVERAGE_FLOOR)

    def test_the_gate_threshold_is_unreachable_in_2021(self):
        """Not 'did not fire' - COULD not fire. With fewer readable signals
        than the threshold, the empty column is a measurement failure and must
        never be read as the gate correctly staying out."""
        scan = event_study.coverage_floor_scan(
            "2021", self.prices, self.series, self.fng, self.btc)
        self.assertEqual(scan["days_gate_could_reach_threshold"], 0)

    def test_at_most_two_signals_are_readable_on_any_2021_date(self):
        for _, start, end, _ in event_study.WINDOWS:
            for day in event_study.daterange(start, end):
                row = event_study.score_date(day, self.prices, self.series,
                                             self.fng, self.btc)
                self.assertLessEqual(row["gate_checkable"], 2, day)

    def test_the_absence_claims_are_true_of_the_archive(self):
        """Every ABSENCE_REASONS entry is a claim about data on disk, and this
        is the only thing that checks it. If a backfill lands, this fails and
        somebody deletes the stale reason instead of the report printing
        'ABSENT [NO HISTORY ON DISK]' above rows showing live values."""
        measured = event_study.measure_tier_a_availability(
            self.prices, self.series, self.fng, self.btc)
        expected = set(dimensions.TIER_A_SIGNALS) - set(
            event_study.ABSENCE_REASONS)
        self.assertEqual(measured, expected)
        self.assertEqual(measured, {"eth_btc_momentum", "fear_greed"})

    def test_every_rotation_signal_is_either_readable_or_explained(self):
        """The ladder-side equivalent. Three rotation signals are not Tier A,
        so nothing in ABSENCE_REASONS covers them; a rotation signal that is
        neither readable nor explained is a blank the report asserts without
        accounting for."""
        measured = event_study.measure_rotation_availability(
            self.prices, self.series, self.fng, self.btc)
        explained = {k for k in ladder.ROTATION_SIGNALS
                     if event_study.absence_reason(k)}
        self.assertEqual(measured | explained, set(ladder.ROTATION_SIGNALS))
        self.assertEqual(measured & explained, set(),
                         "a signal cannot be both readable and explained away")
        self.assertEqual(measured, {"eth_btc_momentum"})

    def test_no_tier_a_signal_shows_a_value_it_cannot_score(self):
        """The second kind of blank, measured against the real archive.

        Empty today: series.json reaches no day of 2021, so no Tier A signal
        prints a number without a vote. Section 2 has a branch for that case
        and this is what tells a reader whether it is currently exercised - if
        a partial backfill lands, this fails and the report starts captioning
        those rows "VALUE ON DISK, NOT SCOREABLE" instead of inheriting the
        hand-written "no history" reason.
        """
        self.assertEqual(
            event_study.measure_tier_a_values(self.prices, self.series,
                                              self.fng, self.btc), {})

    def test_the_printed_backfill_gain_is_the_measured_one(self):
        """Section 7's "after the backfill" figure must be recomputable from
        the module's own functions. An asserted number there was the defect
        this pass exists to remove; a number that disagrees with a fresh
        measurement would be the same defect wearing a computation."""
        expected = event_study.measure_tier_a_availability(
            self.prices, event_study.synthetic_backfill(self.series),
            self.fng, self.btc)
        text = "\n".join(event_study.render(
            self.prices, self.series, self.fng, [], self.btc))
        line = [ln for ln in text.splitlines()
                if "after the backfill above" in ln]
        self.assertEqual(len(line), 1)
        self.assertIn("%d of %d" % (len(expected),
                                    len(dimensions.TIER_A_SIGNALS)), line[0])
        # And the gain must be over the count the same run measured today,
        # not over a remembered one.
        today = event_study.measure_tier_a_availability(
            self.prices, self.series, self.fng, self.btc)
        for key in sorted(expected - today):
            self.assertIn(key, text, key)

    def test_the_headline_percentage_is_what_the_study_prints(self):
        """22.2% is quoted in the module docstring and the report. If a
        backfill lands, this fails and the prose gets corrected rather than
        silently outliving the data it describes."""
        row = event_study.score_date("2021-02-15", self.prices, self.series,
                                     self.fng, self.btc)
        self.assertAlmostEqual(row["gate_coverage_pct"], 22.2, places=1)


if __name__ == "__main__":
    unittest.main()
