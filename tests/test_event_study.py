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

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))

import dimensions
import event_study
import ladder

ANALYSIS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "analysis")


class TestThresholdsHaveNotDrifted(unittest.TestCase):
    """The study duplicates two thresholds to stay offline. That duplication
    is only safe while something fails when it drifts - this is that thing."""

    def test_momentum_threshold_matches_the_ladder_rule(self):
        rule = ladder.LADDER_RULES["eth_btc_momentum"]
        just_over = {"signal": event_study.MOMENTUM_THRESHOLD + 0.01}
        just_under = {"signal": event_study.MOMENTUM_THRESHOLD - 0.01}
        self.assertTrue(rule(just_over))
        self.assertFalse(rule(just_under))

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
        reference. Neither is archived, so a bare value must print with a
        value and no vote - never a vote derived from a shorter window."""
        series = {"nvt": {"2021-02-15": 40.0},
                  "stablecoin_supply_ratio": {"2021-02-15": 12.0}}
        s = event_study.build_signals("2021-02-15", {}, series, {})
        for key in ("nvt", "stablecoin_supply_ratio"):
            self.assertIsNotNone(s[key]["signal"], key)
            self.assertIsNone(s[key]["vote"], key)

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

    def test_the_headline_percentage_is_what_the_study_prints(self):
        """22.2% is quoted in the module docstring and the report. If a
        backfill lands, this fails and the prose gets corrected rather than
        silently outliving the data it describes."""
        row = event_study.score_date("2021-02-15", self.prices, self.series,
                                     self.fng, self.btc)
        self.assertAlmostEqual(row["gate_coverage_pct"], 22.2, places=1)


if __name__ == "__main__":
    unittest.main()
