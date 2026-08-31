#!/usr/bin/env python3
"""
Sell gate tests. No network, no clock - every input is injected.

The sell gate is the only mechanism here that protects capital, and until
these tests it had none. Two things are guarded above all:

  1. the threshold NEVER rescales to what is readable, so the one signal that
     still has a source can never exit the book alone;
  2. a blind gate never renders as a quiet one, because a reader treats any
     absence of alarm as an all-clear.

Run: python -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))

import sell_gate


ONLY_T2 = "sth_rp_weekly_loss"
LTH = "lth_distribution_30d"
ETF = "etf_flow_reversal_near_ath"


def ev(key, date):
    return {"signal": key, "date": date}


class TestRegistry(unittest.TestCase):
    """The gate's shape is a commitment from the owner, not an implementation
    detail: three Tier-1 signals, 2 of 3, 60 days."""

    def test_exactly_three_tier_one_signals(self):
        self.assertEqual(len(sell_gate.TIER_1), 3)

    def test_rule_is_two_of_three_in_sixty_days(self):
        self.assertEqual(sell_gate.FIRE_THRESHOLD, 2)
        self.assertEqual(sell_gate.WINDOW_DAYS, 60)

    def test_only_one_input_is_measurable_today(self):
        """If this ever fails because a source was FOUND, that is the good
        news case - update the registry and delete the ESCALATE expectations
        below. It failing because someone marked an unsourced signal
        measurable is the bad case, and it is the one worth catching."""
        readable = [k for k, v in sell_gate.measurability().items() if v]
        self.assertEqual(readable, [ONLY_T2])

    def test_unmeasurable_signals_carry_a_stated_reason(self):
        for key, meta in sell_gate.TIER_1.items():
            if not meta["measurable"]:
                self.assertTrue(meta["why"].strip(), key)

    def test_the_404_endpoints_are_recorded(self):
        # spending the 10/hour BGeometrics budget rediscovering these is the
        # cost this list exists to prevent
        self.assertIn("lth-supply", sell_gate.LTH_ENDPOINTS_TRIED_404)
        self.assertEqual(len(sell_gate.LTH_ENDPOINTS_TRIED_404), 4)


class TestDenominatorIsFixed(unittest.TestCase):
    """The central design decision, and the one a future edit is most likely
    to undo 'for consistency' with the rotation gate and the ladder."""

    def test_required_does_not_move_with_readable_count(self):
        for over in ({}, {LTH: True}, {LTH: True, ETF: True}):
            r = sell_gate.evaluate([], "2026-08-31", measurable=over)
            self.assertEqual(r["required"], 2, over)
            self.assertEqual(r["of_total"], 3, over)

    def test_one_readable_signal_firing_never_fires_the_gate(self):
        r = sell_gate.evaluate([ev(ONLY_T2, "2026-08-30")], "2026-08-31")
        self.assertNotEqual(r["verdict"], "FIRE")
        self.assertEqual(r["verdict"], "ESCALATE")
        self.assertEqual(r["fired_count"], 1)

    def test_gate_reports_it_cannot_fire(self):
        r = sell_gate.evaluate([], "2026-08-31")
        self.assertFalse(r["can_fire"])
        self.assertTrue(r["blind"])
        self.assertEqual(r["readable_count"], 1)

    def test_policy_constant_is_declared(self):
        self.assertEqual(sell_gate.DENOMINATOR_POLICY, "fixed")


class TestBlindIsNotQuiet(unittest.TestCase):
    """'No sell signal' and 'cannot see' must never share a rendering."""

    def test_nothing_fired_while_blind_is_its_own_verdict(self):
        r = sell_gate.evaluate([], "2026-08-31")
        self.assertEqual(r["verdict"], "BLIND_QUIET")
        self.assertIn("NOT an all-clear", r["reading"])

    def test_nothing_fired_while_operable_is_a_real_all_clear(self):
        r = sell_gate.evaluate([], "2026-08-31",
                               measurable={LTH: True, ETF: True})
        self.assertEqual(r["verdict"], "QUIET")
        self.assertNotIn("NOT an all-clear", r["reading"])

    def test_every_verdict_has_distinct_text(self):
        texts = list(sell_gate.VERDICTS.values())
        self.assertEqual(len(set(texts)), len(texts))

    def test_inoperable_note_names_the_shortfall(self):
        note = sell_gate.evaluate([], "2026-08-31")["note"]
        self.assertIn("INOPERABLE", note)
        self.assertIn("1 of 3", note)


class TestFiringRule(unittest.TestCase):
    """The 2-of-3-in-60-days mechanics, tested in the hypothetical world
    where all three inputs have sources."""

    ALL = {LTH: True, ETF: True}

    def test_two_distinct_signals_inside_the_window_fire(self):
        r = sell_gate.evaluate([ev(LTH, "2026-07-10"), ev(ONLY_T2, "2026-08-30")],
                               "2026-08-31", measurable=self.ALL)
        self.assertEqual(r["verdict"], "FIRE")
        self.assertEqual(r["fired_count"], 2)

    def test_one_signal_firing_twice_is_not_two_votes(self):
        """Six consecutive weekly closes below the cost basis is one signal
        repeating itself, not the second confirmation the rule demands."""
        events = [ev(ONLY_T2, d) for d in ("2026-07-19", "2026-07-26",
                                           "2026-08-02", "2026-08-09")]
        r = sell_gate.evaluate(events, "2026-08-31", measurable=self.ALL)
        self.assertEqual(r["fired_count"], 1)
        self.assertEqual(r["verdict"], "QUIET")

    def test_window_boundary_included_and_excluded(self):
        inside = [ev(LTH, "2026-07-03"), ev(ETF, "2026-08-31")]   # 60 days
        self.assertEqual(sell_gate.evaluate(inside, "2026-08-31",
                                            measurable=self.ALL)["verdict"],
                         "FIRE")
        outside = [ev(LTH, "2026-07-02"), ev(ETF, "2026-08-31")]  # 61 days
        self.assertEqual(sell_gate.evaluate(outside, "2026-08-31",
                                            measurable=self.ALL)["fired_count"],
                         1)

    def test_events_in_the_future_are_ignored(self):
        r = sell_gate.evaluate([ev(LTH, "2026-09-05"), ev(ETF, "2026-08-30")],
                               "2026-08-31", measurable=self.ALL)
        self.assertEqual(r["fired"], [ETF])

    def test_events_from_unmeasurable_sources_are_ignored_not_trusted(self):
        """A stray event must not conjure a vote out of a source that does
        not exist - it is reported separately so the anomaly stays visible."""
        r = sell_gate.evaluate([ev(LTH, "2026-08-30"), ev(ONLY_T2, "2026-08-30")],
                               "2026-08-31")
        self.assertEqual(r["fired"], [ONLY_T2])
        self.assertEqual(r["ignored_events_from_unmeasurable_sources"], [LTH])
        self.assertNotEqual(r["verdict"], "FIRE")

    def test_unknown_keys_and_bad_dates_do_not_vote(self):
        junk = [ev("moon_phase", "2026-08-30"), ev(LTH, "not-a-date"),
                ev(ETF, None), "garbage"]
        r = sell_gate.evaluate(junk, "2026-08-31", measurable=self.ALL)
        self.assertEqual(r["fired_count"], 0)

    def test_unparseable_today_fires_nothing(self):
        r = sell_gate.evaluate([ev(LTH, "2026-08-30"), ev(ETF, "2026-08-30")],
                               "whenever", measurable=self.ALL)
        self.assertEqual(r["fired_count"], 0)

    def test_gate_governs_nothing(self):
        self.assertFalse(sell_gate.evaluate([], "2026-08-31")["governs"])


class TestT2Rule(unittest.TestCase):

    def test_close_below_cost_basis_fires(self):
        self.assertTrue(sell_gate.t2_weekly_loss(60000.0, 69000.0))

    def test_close_above_cost_basis_does_not(self):
        self.assertFalse(sell_gate.t2_weekly_loss(80000.0, 69000.0))

    def test_missing_leg_is_none_not_false(self):
        """'Unreadable' and 'price held' are opposite facts; sharing a value
        would let a dead feed read as safety."""
        self.assertIsNone(sell_gate.t2_weekly_loss(None, 69000.0))
        self.assertIsNone(sell_gate.t2_weekly_loss(60000.0, None))


class TestWeeklyCloses(unittest.TestCase):

    def test_last_observation_of_each_week_is_the_close(self):
        # 2026-08-24 Mon .. 2026-08-30 Sun
        days = ["2026-08-24", "2026-08-26", "2026-08-30"]
        self.assertEqual(sell_gate.weekly_closes(days), ["2026-08-30"])

    def test_week_ending_before_friday_is_dropped(self):
        """A Wednesday is a data gap, not a weekly close. Treating it as one
        would let a mid-week print pass as a confirmed weekly signal."""
        self.assertEqual(sell_gate.weekly_closes(["2026-08-24", "2026-08-26"]),
                         [])

    def test_midweek_dip_that_recovers_does_not_fire(self):
        """The whole value of the weekly-close convention, in one case."""
        prices = {"2026-08-26": 60000.0, "2026-08-30": 80000.0}
        sth = {"2026-08-26": 69000.0, "2026-08-30": 69000.0}
        weeks = sell_gate.weekly_closes(set(prices) & set(sth))
        fired = [w for w in weeks
                 if sell_gate.t2_weekly_loss(prices[w], sth[w])]
        self.assertEqual(weeks, ["2026-08-30"])
        self.assertEqual(fired, [])

    def test_bad_dates_are_skipped(self):
        self.assertEqual(sell_gate.weekly_closes(["oops", "2026-08-30"]),
                         ["2026-08-30"])


class TestEpisodes(unittest.TestCase):

    def test_consecutive_weeks_collapse_to_one_episode(self):
        weeks = ["2026-08-02", "2026-08-09", "2026-08-16", "2026-08-23"]
        self.assertEqual(sell_gate.episodes(weeks), ["2026-08-02"])

    def test_a_gap_opens_a_new_episode(self):
        weeks = ["2026-01-04", "2026-01-11", "2026-06-07"]
        self.assertEqual(sell_gate.episodes(weeks),
                         ["2026-01-04", "2026-06-07"])

    def test_empty_input(self):
        self.assertEqual(sell_gate.episodes([]), [])


class TestBacktestArithmetic(unittest.TestCase):
    """Pure functions, injected data - no file, no network."""

    def test_median_odd_and_even(self):
        self.assertEqual(sell_gate.median([3, 1, 2]), 2)
        self.assertEqual(sell_gate.median([1, 2, 3, 4]), 2.5)
        self.assertIsNone(sell_gate.median([]))

    def test_forward_return_is_a_percentage(self):
        prices = {"2026-01-01": 100.0, "2026-01-31": 110.0}
        self.assertAlmostEqual(
            sell_gate.forward_return_pct(prices, "2026-01-01", 30), 10.0)

    def test_truncated_window_is_dropped_not_padded(self):
        """Padding with the last known price would manufacture a 0% return
        exactly where the sample is thinnest."""
        prices = {"2026-01-01": 100.0}
        self.assertIsNone(
            sell_gate.forward_return_pct(prices, "2026-01-01", 30))

    def test_running_ath_uses_history_before_the_window(self):
        prices = {"2021-11-08": 120.0, "2026-08-30": 60.0}
        ath = sell_gate.running_ath(prices, {"2026-08-30"})
        self.assertEqual(ath, {"2026-08-30": 120.0})

    def test_backtest_end_to_end_on_injected_data(self):
        prices, sth = {}, {}
        import datetime
        d = datetime.date(2026, 1, 4)          # a Sunday
        for i in range(30):
            day = (d + datetime.timedelta(days=7 * i)).isoformat()
            prices[day] = 100.0 + i
            sth[day] = 105.0                   # first weeks close below it
        bt = sell_gate.backtest_t2(prices, sth)
        self.assertEqual(len(bt["weeks"]), 30)
        self.assertEqual(len(bt["fired"]), 5)  # 100..104 are below 105
        # five consecutive weeks, so one episode - the collapse that keeps a
        # single drawdown from entering the sample five times
        self.assertEqual(bt["episodes"], ["2026-01-04"])

    def test_backtest_returns_none_without_overlap(self):
        self.assertIsNone(sell_gate.backtest_t2({"2026-01-04": 1.0},
                                                {"2026-02-01": 1.0}))

    def test_report_states_the_gate_cannot_fire(self):
        text = sell_gate.render(None)
        self.assertIn("SHADOW", text)
        self.assertIn("UNMEASURABLE", text)
        self.assertIn("NOT RUN", text)


if __name__ == "__main__":
    unittest.main()
