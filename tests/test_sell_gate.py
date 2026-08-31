#!/usr/bin/env python3
"""
Sell gate tests. No network, no clock - every input is injected.

The sell gate is the only mechanism here that protects capital, and until
these tests it had none. Two things are guarded above all:

  1. the threshold NEVER rescales to what is readable, so the one signal that
     still has a source can never exit the book alone;
  2. a blind gate never renders as a quiet one, because a reader treats any
     absence of alarm as an all-clear;
  3. neither does an operable gate one vote short of firing - that is ARMED,
     and it is the same misreading in the world where the gate works.

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

    def test_only_the_endpoint_with_evidence_is_recorded_as_404(self):
        """An earlier draft listed four names as measured 404s when only one
        had ever been written down (README.md:146). Guessed names and observed
        results must not share a container - that is how a guess becomes a
        citation two edits later."""
        names = [n for n, _, _ in sell_gate.LTH_ENDPOINTS_404_REPORTED]
        self.assertEqual(names, ["lth-supply"])
        for _, status, source in sell_gate.LTH_ENDPOINTS_404_REPORTED:
            self.assertTrue(source.strip(), "a 404 claim needs a provenance")
        self.assertNotIn("lth-supply", sell_gate.LTH_ENDPOINTS_UNVERIFIED)

    def test_the_report_never_calls_an_untested_name_a_404(self):
        text = sell_gate.render(None)
        for name in sell_gate.LTH_ENDPOINTS_UNVERIFIED:
            line = [ln for ln in text.splitlines() if name in ln]
            self.assertTrue(line, name)
            self.assertNotIn("404", line[0], name)


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


class TestArmedIsNotQuiet(unittest.TestCase):
    """The fifth verdict, and the reason it exists.

    TestBlindIsNotQuiet guards the world where the gate cannot fire. This one
    guards the world where it CAN and simply has not yet: a fired signal below
    the threshold used to render as QUIET, whose text is 'a real all-clear'.
    Today no world reaches that branch because only one input is readable - so
    this is a guard on the world one purchased data feed away, where the sell
    gate's first piece of false comfort would otherwise be printed under a
    line saying nothing fired.
    """

    OPERABLE = {LTH: True}

    def test_fired_below_threshold_while_operable_is_armed(self):
        r = sell_gate.evaluate([ev(ONLY_T2, "2026-08-28")], "2026-08-28",
                               measurable=self.OPERABLE)
        self.assertEqual(r["verdict"], "ARMED")
        self.assertTrue(r["can_fire"])
        self.assertEqual(r["fired"], [ONLY_T2])
        self.assertEqual(r["required"], 2)

    def test_armed_says_a_signal_fired_and_the_gate_was_able_to(self):
        r = sell_gate.evaluate([ev(ONLY_T2, "2026-08-28")], "2026-08-28",
                               measurable=self.OPERABLE)
        self.assertIn("fired", r["reading"])
        self.assertNotIn("all-clear", r["reading"])

    def test_no_verdict_with_a_firing_ever_reads_as_an_all_clear(self):
        """The invariant, checked across every world rather than case by case:
        if anything fired, the reading must not offer reassurance."""
        for over in ({}, {LTH: True}, {LTH: True, ETF: True}):
            r = sell_gate.evaluate([ev(ONLY_T2, "2026-08-28")], "2026-08-28",
                                   measurable=over)
            self.assertTrue(r["fired"], over)
            self.assertNotEqual(r["verdict"], "QUIET", over)
            self.assertNotIn("all-clear", r["reading"], over)

    def test_quiet_still_means_quiet_when_truly_nothing_fired(self):
        r = sell_gate.evaluate([], "2026-08-28", measurable={LTH: True})
        self.assertEqual(r["verdict"], "QUIET")

    def test_armed_is_one_signal_short_of_fire_not_a_different_rule(self):
        """ARMED plus one more DISTINCT signal inside the window is FIRE; the
        same signal again is still ARMED. Otherwise the new verdict would have
        quietly become a second way to reach a sale."""
        base = [ev(ONLY_T2, "2026-08-20")]
        again = sell_gate.evaluate(base + [ev(ONLY_T2, "2026-08-28")],
                                   "2026-08-28", measurable={LTH: True})
        self.assertEqual(again["verdict"], "ARMED")
        other = sell_gate.evaluate(base + [ev(LTH, "2026-08-28")],
                                   "2026-08-28", measurable={LTH: True})
        self.assertEqual(other["verdict"], "FIRE")


class TestReachableVerdicts(unittest.TestCase):
    """Section 2 claims which outcomes are possible. It is a claim about the
    code path, so it is computed from the readable count - and here it is
    checked against what evaluate() actually emits, because a computed claim
    that disagrees with the code is no better than a typed one."""

    def test_no_readable_input_can_only_be_blind_quiet(self):
        self.assertEqual(sell_gate.reachable_verdicts(0), ["BLIND_QUIET"])

    def test_one_readable_input_cannot_reach_fire(self):
        self.assertEqual(sell_gate.reachable_verdicts(1),
                         ["ESCALATE", "BLIND_QUIET"])

    def test_two_or_three_readable_inputs_reach_the_operable_set(self):
        for n in (2, 3):
            self.assertEqual(sell_gate.reachable_verdicts(n),
                             ["FIRE", "ARMED", "QUIET"], n)

    def test_default_argument_follows_the_registry(self):
        n = sum(1 for v in sell_gate.measurability().values() if v)
        self.assertEqual(sell_gate.reachable_verdicts(),
                         sell_gate.reachable_verdicts(n))

    def test_every_name_returned_is_a_declared_verdict(self):
        for n in range(4):
            for name in sell_gate.reachable_verdicts(n):
                self.assertIn(name, sell_gate.VERDICTS, n)

    def test_the_set_matches_what_evaluate_actually_produces(self):
        keys = [ONLY_T2, LTH, ETF]
        for n in range(4):
            # every key pinned, so measurability() cannot leak the registry in
            over = {k: (i < n) for i, k in enumerate(keys)}
            seen = set()
            for take in range(4):
                events = [ev(k, "2026-08-28") for k in keys[:take]]
                seen.add(sell_gate.evaluate(events, "2026-08-28",
                                            measurable=over)["verdict"])
            self.assertEqual(seen, set(sell_gate.reachable_verdicts(n)), n)


class TestSectionOneIsComputedNotTyped(unittest.TestCase):
    """Section 1 carries the module's central finding, and it used to be typed.

    Marking one source measurable produced a report whose section 0 said
    'can fire: yes' four lines above a section 1 still saying the threshold
    was unreachable by construction, with the signal table between them
    agreeing with neither. A finding that does not move with the registry is
    a sentence that used to be true.
    """

    def _text(self, **over):
        verdict = sell_gate.evaluate([], "2026-08-28", measurable=over)
        return sell_gate.render(None, verdict=verdict)

    def test_todays_world_is_one_readable_and_unreachable(self):
        text = self._text()
        self.assertIn("Readable inputs: 1 of 3", text)
        self.assertIn("unreachable by construction", text)
        self.assertIn("No. It never could.", text)

    def test_an_operable_world_flips_every_derived_line(self):
        text = self._text(**{LTH: True})
        self.assertIn("CAN THE GATE FIRE?   Yes", text)
        self.assertIn("Readable inputs: 2 of 3", text)
        self.assertNotIn("It never could", text)
        self.assertNotIn("unreachable by construction", text)
        self.assertNotIn("Readable inputs: 1 of 3", text)
        # section 6 flips too, or the report ends by prescribing a fix to a
        # problem its own section 1 has just said no longer exists
        self.assertIn("Already changed", text)

    def test_sections_zero_and_one_can_never_disagree(self):
        for over in ({}, {LTH: True}, {LTH: True, ETF: True}):
            verdict = sell_gate.evaluate([], "2026-08-28", measurable=over)
            text = sell_gate.render(None, verdict=verdict)
            self.assertEqual("can fire     : yes" in text,
                             "CAN THE GATE FIRE?   Yes" in text, over)
            self.assertIn("Readable inputs: %d of 3" % verdict["readable_count"],
                          text, over)

    def test_a_registry_edit_alone_moves_section_one(self):
        """render() with no verdict falls back to measurability(), so editing
        TIER_1 must move it too - that is the exact edit that exposed the
        hardcoded strings."""
        saved = sell_gate.TIER_1[LTH]["measurable"]
        self.addCleanup(sell_gate.TIER_1[LTH].__setitem__, "measurable", saved)
        sell_gate.TIER_1[LTH]["measurable"] = True
        text = sell_gate.render(None)
        self.assertIn("Readable inputs: 2 of 3", text)
        self.assertNotIn("It never could", text)


class TestSectionTwoReachableSetIsRendered(unittest.TestCase):

    def test_todays_world_lists_two_outcomes_and_says_never_fire(self):
        text = sell_gate.render(None,
                                verdict=sell_gate.evaluate([], "2026-08-28"))
        self.assertIn("ESCALATE, BLIND_QUIET", text)
        self.assertIn("Never FIRE", text)

    def test_an_operable_world_lists_fire_and_drops_that_line(self):
        v = sell_gate.evaluate([], "2026-08-28", measurable={LTH: True})
        text = sell_gate.render(None, verdict=v)
        self.assertIn("FIRE, ARMED, QUIET", text)
        self.assertNotIn("Never FIRE", text)

    def test_the_rescaling_argument_quotes_the_world_it_is_arguing_about(self):
        """Section 2 rejects rescaling the denominator. The rejection is only
        honest if the number it rejects is the one rescaling would actually
        demand here, so that number is computed as well."""
        text = sell_gate.render(None,
                                verdict=sell_gate.evaluate([], "2026-08-28"))
        self.assertIn("2 of 3 rescaled onto 1", text)
        self.assertIn("one signal exits the entire book", text)
        v = sell_gate.evaluate([], "2026-08-28", measurable={LTH: True})
        other = sell_gate.render(None, verdict=v)
        self.assertIn("2 of 3 rescaled onto 2", other)
        self.assertIn("asks for 2", other)
        self.assertNotIn("one signal exits the entire book", other)

    def test_the_required_line_states_the_invariant_not_a_literal(self):
        text = sell_gate.render(None)
        self.assertIn("Required stays %d of %d whatever is readable"
                      % (sell_gate.FIRE_THRESHOLD, len(sell_gate.TIER_1)), text)

    def test_the_verdict_count_in_the_prose_is_the_dict_length(self):
        text = sell_gate.render(None)
        self.assertIn("%d distinct verdicts" % len(sell_gate.VERDICTS), text)
        for name in sell_gate.VERDICTS:
            self.assertIn(name, text)


class TestFinalWeekIsDisclosed(unittest.TestCase):
    """The weekly grid keeps the last observation of each ISO week and the
    Friday guard admits a Friday, so the newest row can be a week still
    running. On the shipped data it is: STH-RP ends 2026-08-28, a Friday,
    while the price cache runs to the Sunday - and section 0's live verdict is
    computed on that partial row. Harmless while T2 is quiet, and wrong the
    first time an unfinished week dips below the cost basis, because a
    mid-week print is exactly what the weekly convention rejects.
    """

    @staticmethod
    def _bt(last_day):
        import datetime
        prices, sth = {}, {}
        d = datetime.date(2026, 1, 4)                 # a Sunday
        end = datetime.date.fromisoformat(last_day)
        while d <= end:
            prices[d.isoformat()] = 100.0
            sth[d.isoformat()] = 90.0                 # T2 never fires
            d += datetime.timedelta(days=1)
        return sell_gate.backtest_t2(prices, sth)

    def test_a_sunday_end_is_a_real_weekly_close(self):
        bt = self._bt("2026-03-01")                   # Sunday
        self.assertTrue(bt["last_week_complete"])
        self.assertEqual(bt["last_close_weekday"], "Sunday")
        self.assertEqual(bt["last_week_ends"], "2026-03-01")

    def test_a_friday_end_is_an_unfinished_week_with_its_real_end_named(self):
        bt = self._bt("2026-02-27")                   # Friday
        self.assertFalse(bt["last_week_complete"])
        self.assertEqual(bt["last_close_weekday"], "Friday")
        self.assertEqual(bt["last_week_ends"], "2026-03-01")

    def test_the_report_says_the_newest_row_is_partial(self):
        bt = self._bt("2026-02-27")
        text = sell_gate.render(bt, verdict=sell_gate.evaluate([], bt["last_day"]))
        self.assertIn("still in progress", text)      # section 0
        self.assertIn("UNFINISHED", text)             # section 3
        self.assertIn("PARTIAL week", text)           # section 5
        self.assertIn("2026-03-01", text)             # the week's real end

    def test_the_report_says_so_when_the_grid_ends_complete(self):
        bt = self._bt("2026-03-01")
        text = sell_gate.render(bt, verdict=sell_gate.evaluate([], bt["last_day"]))
        self.assertIn("Sunday close", text)
        self.assertNotIn("UNFINISHED", text)
        self.assertNotIn("PARTIAL week", text)

    def test_the_shipped_shape_is_the_partial_one(self):
        """The real files, reproduced without touching them: STH-RP stops on a
        Friday, the price cache runs two days past it. This is the condition
        that made the disclosure necessary."""
        import datetime
        prices, sth = {}, {}
        d = datetime.date(2026, 1, 4)
        while d <= datetime.date(2026, 3, 1):
            prices[d.isoformat()] = 100.0
            if d <= datetime.date(2026, 2, 27):
                sth[d.isoformat()] = 90.0
            d += datetime.timedelta(days=1)
        bt = sell_gate.backtest_t2(prices, sth)
        self.assertEqual(bt["last_day"], "2026-02-27")
        self.assertFalse(bt["last_week_complete"])


class TestPriceProvenance(unittest.TestCase):
    """load_btc_price() returns any cache it finds with no age or coverage
    check. That is right for the derivation - CapMrktCurUSD / SplyCur for 2019
    will never change - and wrong for section 0, which is dated off the data:
    a months-old cache would otherwise produce a confident TODAY about a week
    long past. resilience.py keeps a frozen source and marks it stale with its
    age; this does the same."""

    SERIES = {"2026-08-28": 100.0, "2026-01-01": 90.0}

    def test_age_is_measured_against_an_injected_system_date(self):
        st = sell_gate.price_provenance(self.SERIES, "cache",
                                        system_date="2026-08-31")
        self.assertEqual(st["first_date"], "2026-01-01")
        self.assertEqual(st["last_date"], "2026-08-28")
        self.assertEqual(st["n_days"], 2)
        self.assertEqual(st["source_age_days"], 3)
        self.assertFalse(st["stale"])

    def test_a_months_old_cache_is_flagged(self):
        st = sell_gate.price_provenance(self.SERIES, "cache",
                                        system_date="2026-12-01")
        self.assertTrue(st["stale"])
        self.assertGreater(st["source_age_days"],
                           sell_gate.PRICE_STALENESS_MAX_DAYS)

    def test_the_boundary_is_inclusive_of_the_limit(self):
        import datetime
        edge = (datetime.date(2026, 8, 28)
                + datetime.timedelta(sell_gate.PRICE_STALENESS_MAX_DAYS))
        self.assertFalse(sell_gate.price_provenance(
            self.SERIES, "c", system_date=edge.isoformat())["stale"])
        self.assertTrue(sell_gate.price_provenance(
            self.SERIES, "c",
            system_date=(edge + datetime.timedelta(1)).isoformat())["stale"])

    def test_an_empty_series_is_stale_not_fresh(self):
        """No data is not fresh data. A None age must never compare as young."""
        st = sell_gate.price_provenance({}, "none", system_date="2026-08-31")
        self.assertIsNone(st["source_age_days"])
        self.assertIsNone(st["last_date"])
        self.assertTrue(st["stale"])

    def test_the_report_prints_the_source_its_date_and_the_flag(self):
        v = sell_gate.evaluate([], "2026-08-28")
        st = sell_gate.price_provenance(self.SERIES, "cache under test",
                                        system_date="2026-12-01")
        text = sell_gate.render(None, verdict=v, price_status=st)
        self.assertIn("cache under test", text)
        self.assertIn("2026-08-28", text)
        self.assertIn("STALE", text)

    def test_a_fresh_cache_is_dated_without_the_stale_line(self):
        v = sell_gate.evaluate([], "2026-08-28")
        st = sell_gate.price_provenance(self.SERIES, "cache under test",
                                        system_date="2026-08-31")
        text = sell_gate.render(None, verdict=v, price_status=st)
        self.assertIn("trails the system date 2026-08-31", text)
        self.assertNotIn("STALE", text)

    def test_no_price_status_omits_the_block_rather_than_guessing(self):
        text = sell_gate.render(None,
                                verdict=sell_gate.evaluate([], "2026-08-28"))
        self.assertNotIn("BTC price    :", text)


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
        repeating itself, not the second confirmation the rule demands.

        ARMED, not QUIET. An earlier version of this test asserted QUIET here
        and so locked in the bug: a signal HAD fired, and the gate reported
        'a real all-clear'. One vote short of a sell is the last place to
        print reassurance.
        """
        events = [ev(ONLY_T2, d) for d in ("2026-07-19", "2026-07-26",
                                           "2026-08-02", "2026-08-09")]
        r = sell_gate.evaluate(events, "2026-08-31", measurable=self.ALL)
        self.assertEqual(r["fired_count"], 1)
        self.assertEqual(r["verdict"], "ARMED")
        self.assertNotIn("all-clear", r["reading"])

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

    def test_no_price_data_still_renders_the_measurability_audit(self):
        """The finding this module exists for - 2 of 3 inputs unreadable -
        needs no price series. A dead network must not take it down with the
        backtest, which is exactly what an unguarded fetch used to do."""
        text = sell_gate.render(None, no_backtest_reason="NOT RUN - BTC price "
                                "unavailable and no cache")
        self.assertIn("BTC price unavailable", text)
        for section in ("1. CAN THE GATE FIRE", "2. WHAT THE GATE DOES",
                        "5. LIMITS", "6. WHAT WOULD CHANGE THE ANSWER"):
            self.assertIn(section, text)


def daily_fixture(days=1400, start=(2022, 1, 3)):
    """A synthetic daily series with slow cycles, so the report has enough
    firings for a readable bucket and few enough episodes for an unreadable
    one. Deterministic and offline; the real numbers live in
    analysis/sell_gate.txt, not here."""
    import datetime
    import math
    d0 = datetime.date(*start)
    prices, sth, ethbtc = {}, {}, {}
    for i in range(days):
        day = (d0 + datetime.timedelta(days=i)).isoformat()
        prices[day] = 100.0 + 30.0 * math.sin(i / 70.0)
        sth[day] = 105.0
        ethbtc[day] = 0.06 - 0.00002 * i
    return prices, sth, ethbtc


class TestRenderWithABacktest(unittest.TestCase):
    """The largest path in the module, and the one a reader of
    analysis/sell_gate.txt actually sees. Previously only render(None) was
    covered, so every table below could have been silently wrong."""

    @classmethod
    def setUpClass(cls):
        prices, sth, ethbtc = daily_fixture()
        cls.bt = sell_gate.backtest_t2(prices, sth, ethbtc=ethbtc)
        cls.text = sell_gate.render(cls.bt)
        cls.lines = cls.text.splitlines()

    def _line(self, needle):
        hits = [ln for ln in self.lines if needle in ln]
        self.assertTrue(hits, "no line containing %r" % needle)
        return hits[0]

    def test_the_fixture_actually_exercises_both_sample_regimes(self):
        """If this fails the two assertions below stop meaning anything, so it
        is checked explicitly rather than assumed from the fixture shape."""
        rows = self.bt["rows"][30]
        self.assertGreaterEqual(len(rows["all_firings"]),
                                sell_gate.MIN_READABLE_SAMPLE)
        self.assertGreaterEqual(len(rows["baseline"]),
                                sell_gate.MIN_READABLE_SAMPLE)
        self.assertLess(len(rows["first_of_episode"]),
                        sell_gate.MIN_READABLE_SAMPLE)

    def test_all_three_horizon_tables_render(self):
        for h in (30, 60, 90):
            self.assertIn("BTC forward return, horizon %d days" % h, self.text)
        self.assertIn("BASELINE (every week)", self.text)

    def test_thin_bucket_is_marked_not_readable(self):
        self.assertIn("not readable", self._line("T2 fired (1st of episode)"))

    def test_thin_bucket_gets_no_edge_line(self):
        """A +2.3 printed next to n=7 gets quoted later without its sample
        size attached. The mark alone does not stop that; withholding the
        number does."""
        self.assertEqual(
            [ln for ln in self.lines if "edge vs baseline, 1st of" in ln], [])

    def test_readable_bucket_does_get_an_edge_line(self):
        self.assertIn("points", self._line("edge vs baseline, every week"))

    def test_readable_bucket_is_not_marked_unreadable(self):
        self.assertNotIn("not readable",
                         self._line("T2 fired (every week)"))

    def test_drawdown_and_ath_sensitivity_render(self):
        """The '0 firings within 10% of the ATH' claim is one threshold from
        flipping, so every threshold is printed, not the flattering one."""
        self.assertIn("Drawdown from the running ATH", self.text)
        for t in sell_gate.ATH_PROXIMITY_THRESHOLDS:
            self.assertIn("%4.0f%%" % t, self.text)
        self.assertEqual(len(self.bt["near_ath_counts"]),
                         len(sell_gate.ATH_PROXIMITY_THRESHOLDS))

    def test_ath_counts_are_monotonic_in_the_threshold(self):
        counts = [self.bt["near_ath_counts"][t]
                  for t in sorted(sell_gate.ATH_PROXIMITY_THRESHOLDS)]
        self.assertEqual(counts, sorted(counts))

    def test_dropped_week_count_is_printed_even_when_zero(self):
        """A guard that never bound must say so, or a reader credits it with
        removing noise it never saw."""
        line = self._line("Weeks dropped for a pre-Friday")
        self.assertIn("of %d" % self.bt["weeks_seen"], line)
        self.assertEqual(self.bt["weeks_dropped_pre_friday"], 0)

    def test_daily_overlap_and_weekly_grid_are_distinguished(self):
        """They differ - the first weekly close lands after the first daily
        observation - and labelling the daily span as the test window
        overstates what the backtest ran on."""
        self.assertIn("Daily overlap", self.text)
        self.assertIn("Weekly grid", self.text)
        self.assertNotEqual(self.bt["first_day"], self.bt["weeks"][0])
        self.assertIn(self.bt["weeks"][0], self._line("Weekly grid"))

    def test_ethbtc_table_is_rendered_alongside_btc(self):
        """The gate mixes assets: T2 is a BTC rule, the book is ETH/BTC. Both
        yardsticks are printed so neither passes as 'the' answer."""
        self.assertIn("ETH/BTC forward return, horizon 30 days", self.text)
        self.assertIn("ASSET MISMATCH", self.text)

    def test_ethbtc_section_says_not_run_when_the_series_is_absent(self):
        prices, sth, _ = daily_fixture()
        text = sell_gate.render(sell_gate.backtest_t2(prices, sth))
        self.assertIn("3B.", text)
        self.assertIn("NOT RUN - analysis/ethbtc.json", text)
        self.assertNotIn("ETH/BTC forward return", text)


class TestMainSurvivesMissingData(unittest.TestCase):
    """main() used to die on an unhandled OSError when the price cache was
    absent and the network was down, taking sections 1, 2, 5 and 6 with it -
    the four that need no data at all and carry the actual finding."""

    def setUp(self):
        import contextlib
        import io
        import shutil
        import tempfile
        # main() prints the whole report; swallow it so the test run stays
        # readable, and so a future assertion failure is not buried in it.
        quiet = contextlib.redirect_stdout(io.StringIO())
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self._saved = (sell_gate.ANALYSIS, sell_gate.CACHE)
        sell_gate.ANALYSIS = self.tmp
        sell_gate.CACHE = os.path.join(self.tmp, ".cache")

    def tearDown(self):
        sell_gate.ANALYSIS, sell_gate.CACHE = self._saved

    def _write_series(self):
        import json
        with open(os.path.join(self.tmp, "series.json"), "w") as f:
            json.dump({"dates": ["2026-08-30"],
                       "series": {"sth_realized_price": [69000.0]}}, f)

    def _no_network(self):
        import urllib.request
        saved = urllib.request.urlopen
        self.addCleanup(setattr, urllib.request, "urlopen", saved)
        urllib.request.urlopen = self._boom

    @staticmethod
    def _boom(*a, **k):
        raise OSError("network down")

    def test_no_cache_and_no_network_still_writes_the_audit(self):
        self._write_series()
        self._no_network()
        self.assertEqual(sell_gate.main(), 0)
        with open(os.path.join(self.tmp, "sell_gate.txt"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("NOT RUN - BTC price unavailable and no cache", text)
        for section in ("1. CAN THE GATE FIRE", "2. WHAT THE GATE DOES",
                        "5. LIMITS", "6. WHAT WOULD CHANGE THE ANSWER"):
            self.assertIn(section, text)

    def test_the_report_names_the_cache_it_read_and_its_last_date(self):
        """main() asks whether a cache exists BEFORE loading, because a fetch
        writes one and every later run would then look like a cache hit."""
        import json
        self._write_series()
        os.makedirs(sell_gate.CACHE, exist_ok=True)
        with open(os.path.join(sell_gate.CACHE, "btc_price_usd.json"),
                  "w") as f:
            json.dump({"2026-08-30": 60000.0}, f)
        self._no_network()
        self.assertEqual(sell_gate.main(), 0)
        with open(os.path.join(self.tmp, "sell_gate.txt"),
                  encoding="utf-8") as f:
            text = f.read()
        self.assertIn("cache analysis/.cache/btc_price_usd.json", text)
        self.assertIn("2026-08-30", text)

    def test_missing_series_file_is_reported_not_raised(self):
        self._no_network()
        self.assertEqual(sell_gate.main(), 0)
        with open(os.path.join(self.tmp, "sell_gate.txt"), encoding="utf-8") as f:
            self.assertIn("no sth_realized_price", f.read())


class TestSectionZeroRunsTheGate(unittest.TestCase):
    """The report used to assert the verdict mapping in prose without ever
    calling evaluate(). Section 0 is that call."""

    def test_section_zero_prints_a_computed_verdict(self):
        prices, sth, _ = daily_fixture()
        bt = sell_gate.backtest_t2(prices, sth)
        events = [{"signal": ONLY_T2, "date": d} for d in bt["fired"]]
        verdict = sell_gate.evaluate(events, bt["last_day"])
        text = sell_gate.render(bt, verdict=verdict)
        self.assertIn("0. TODAY", text)
        self.assertIn(verdict["verdict"], text)
        self.assertIn(bt["last_day"], text)
        self.assertIn("denominator policy: fixed", text)

    def test_section_zero_says_so_when_nothing_was_computed(self):
        self.assertIn("NOT COMPUTED", sell_gate.render(None))

    def test_a_quiet_window_renders_blind_quiet_not_a_verdict_of_calm(self):
        """The other half of the mapping section 2 claims. Fed a backtest
        whose firings are all older than the 60-day window."""
        prices, sth, _ = daily_fixture()
        bt = sell_gate.backtest_t2(prices, sth)
        old = [{"signal": ONLY_T2, "date": d} for d in bt["fired"][:3]]
        verdict = sell_gate.evaluate(old, bt["last_day"])
        self.assertEqual(verdict["verdict"], "BLIND_QUIET")
        self.assertIn("BLIND_QUIET", sell_gate.render(bt, verdict=verdict))


if __name__ == "__main__":
    unittest.main()
