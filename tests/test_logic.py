#!/usr/bin/env python3
"""
Pure logic tests. No network, no clock - every input is injected.

These guard the rules that decide things: what votes, what does not, and what
happens when a source degrades. They must stay fast and offline so CI can run
them on every push without touching a rate-limited API.

Run: python -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))

import dimensions
import resilience
import report
import ladder


class TestRegistry(unittest.TestCase):
    """The gate's shape is a spec commitment, not an implementation detail."""

    def test_exactly_nine_tier_a_signals(self):
        self.assertEqual(len(dimensions.TIER_A_SIGNALS), 9)

    def test_every_signal_maps_to_a_known_dimension(self):
        for key, (dim, tier) in dimensions.SIGNAL_REGISTRY.items():
            self.assertIn(dim, dimensions.DIMENSION_NAMES, key)
            self.assertIn(tier, ("A", "B", "track"), key)

    def test_threshold_not_above_tier_a_count(self):
        # a threshold above the available votes could never fire
        self.assertLessEqual(dimensions.TIER_A_THRESHOLD,
                             len(dimensions.TIER_A_SIGNALS))


class TestTally(unittest.TestCase):

    def _signals(self, votes):
        return {k: {"vote": v, "status": "ok"} for k, v in votes.items()}

    def test_none_votes_shrink_denominator_not_numerator(self):
        s = self._signals({"fear_greed": True, "nvt": None, "mvrv_z_score": False})
        t = dimensions.tally(s, "2026-08-31")
        self.assertEqual(t["fired"], 1)
        self.assertEqual(t["checkable"], 2)  # the None is excluded entirely
        self.assertIn("nvt", t["unavailable"])

    def test_shadow_mode_before_adoption_date(self):
        t = dimensions.tally(self._signals({}), "2026-08-29")
        self.assertFalse(t["authoritative"])

    def test_authoritative_on_and_after_adoption_date(self):
        self.assertTrue(dimensions.tally(self._signals({}),
                                         dimensions.ADOPTED_FROM)["authoritative"])
        self.assertTrue(dimensions.tally(self._signals({}),
                                         "2026-12-01")["authoritative"])

    def test_would_fire_requires_threshold(self):
        keys = dimensions.TIER_A_SIGNALS
        under = self._signals({k: True for k in keys[:dimensions.TIER_A_THRESHOLD - 1]})
        self.assertFalse(dimensions.tally(under, "2026-08-31")["would_fire"])
        at = self._signals({k: True for k in keys[:dimensions.TIER_A_THRESHOLD]})
        self.assertTrue(dimensions.tally(at, "2026-08-31")["would_fire"])

    def test_tier_b_never_counts_toward_threshold(self):
        s = {k: {"vote": True, "status": "ok"}
             for k, (_, t) in dimensions.SIGNAL_REGISTRY.items() if t == "B"}
        t = dimensions.tally(s, "2026-08-31")
        self.assertEqual(t["fired"], 0)
        self.assertFalse(t["would_fire"])

    def test_tracked_signals_never_count(self):
        s = {k: {"vote": True, "status": "ok"}
             for k, (_, t) in dimensions.SIGNAL_REGISTRY.items() if t == "track"}
        self.assertEqual(dimensions.tally(s, "2026-08-31")["fired"], 0)


class TestCarryForward(unittest.TestCase):

    def _prev(self, date, signal=42.0, stale=False):
        p = {"date": date, "signals": {"nvt": {"signal": signal, "status": "ok"}}}
        if stale:
            p["signals"]["nvt"]["stale"] = True
        return p

    def test_failed_signal_reuses_last_good_value(self):
        s = {"nvt": {"status": "error", "error": "boom", "signal": None, "vote": True}}
        resilience.carry_forward(s, self._prev("2026-08-30"), "2026-08-31")
        self.assertEqual(s["nvt"]["signal"], 42.0)
        self.assertTrue(s["nvt"]["stale"])
        self.assertEqual(s["nvt"]["status"], "carried_forward")

    def test_carried_value_never_votes(self):
        """The critical guarantee: old data informs, it does not decide."""
        s = {"nvt": {"status": "error", "signal": None, "vote": True}}
        resilience.carry_forward(s, self._prev("2026-08-30"), "2026-08-31")
        self.assertIsNone(s["nvt"]["vote"])

    def test_healthy_signal_is_untouched(self):
        s = {"nvt": {"status": "ok", "signal": 99.0, "vote": True}}
        resilience.carry_forward(s, self._prev("2026-08-30"), "2026-08-31")
        self.assertEqual(s["nvt"]["signal"], 99.0)
        self.assertTrue(s["nvt"]["vote"])

    def test_does_not_chain_stale_onto_stale(self):
        s = {"nvt": {"status": "error", "signal": None, "vote": None}}
        resilience.carry_forward(s, self._prev("2026-08-30", stale=True), "2026-08-31")
        self.assertIsNone(s["nvt"]["signal"])

    def test_refuses_to_carry_beyond_max_age(self):
        s = {"nvt": {"status": "error", "signal": None, "vote": None}}
        resilience.carry_forward(s, self._prev("2026-08-01"), "2026-08-31")
        self.assertIsNone(s["nvt"]["signal"])

    def test_no_previous_run_is_safe(self):
        s = {"nvt": {"status": "error", "signal": None, "vote": None}}
        resilience.carry_forward(s, None, "2026-08-31")
        self.assertIsNone(s["nvt"]["signal"])


class TestStaleness(unittest.TestCase):
    """Upstream freeze: HTTP 200 forever, as_of stops advancing."""

    def test_frozen_source_is_demoted_and_loses_its_vote(self):
        s = {"puell_multiple": {"status": "ok", "signal": 0.97,
                                "as_of": "2026-08-01", "vote": True}}
        resilience.check_staleness(s, "2026-08-31", 3)
        self.assertEqual(s["puell_multiple"]["status"], "stale")
        self.assertIsNone(s["puell_multiple"]["vote"])
        self.assertEqual(s["puell_multiple"]["source_age_days"], 30)

    def test_fresh_source_keeps_its_vote(self):
        s = {"puell_multiple": {"status": "ok", "signal": 0.97,
                                "as_of": "2026-08-30", "vote": True}}
        resilience.check_staleness(s, "2026-08-31", 3)
        self.assertEqual(s["puell_multiple"]["status"], "ok")
        self.assertTrue(s["puell_multiple"]["vote"])

    def test_signal_without_as_of_is_left_alone(self):
        s = {"fear_greed": {"status": "ok", "signal": 73, "vote": True}}
        resilience.check_staleness(s, "2026-08-31", 3)
        self.assertTrue(s["fear_greed"]["vote"])


class TestHealth(unittest.TestCase):

    def test_degraded_when_a_source_failed(self):
        h = resilience.health({"a": {"status": "ok"}, "b": {"status": "error"}})
        self.assertTrue(h["degraded"])
        self.assertIn("b", h["failed_signals"])

    def test_not_degraded_when_only_structurally_unavailable(self):
        """no_api / no_key are known limits, not failures - they must not
        raise a degraded alarm every single day."""
        h = resilience.health({"a": {"status": "ok"}, "b": {"status": "no_api"},
                               "c": {"status": "no_key"}})
        self.assertFalse(h["degraded"])
        self.assertEqual(h["structurally_unavailable"], 2)

    def test_carried_forward_counts_as_stale_and_degraded(self):
        h = resilience.health({"a": {"status": "carried_forward"}})
        self.assertTrue(h["degraded"])


class TestReport(unittest.TestCase):

    def _snap(self, status, signal=0.97):
        return {
            "date": "2026-08-31", "fetched_at": "x", "schema_version": 4,
            "signals": {"puell_multiple": {"signal": signal, "status": status,
                                           "dimension": 2, "tier": "track"}},
            "health": {"degraded": status != "ok", "failed": 0, "stale": 1},
            "gate_legacy": {"fired": 1, "checkable_today": 2, "fired_signals": ["x"]},
            "gate_new": {"authoritative": False, "fired": 1, "checkable": 3,
                         "threshold": 5, "would_fire": False, "unavailable": []},
        }

    def test_stale_value_is_never_rendered_as_live(self):
        md = report.render_markdown(self._snap("carried_forward"))
        self.assertIn("STALE", md)
        self.assertNotIn("| live |", md)

    def test_live_value_is_marked_live(self):
        self.assertIn("live", report.render_markdown(self._snap("ok")))

    def test_degraded_run_carries_a_visible_banner(self):
        self.assertIn("DEGRADED RUN", report.render_markdown(self._snap("error")))

    def test_missing_value_renders_as_dash_not_zero(self):
        md = report.render_markdown(self._snap("error", signal=None))
        self.assertIn("—", md)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestWeightedGrade(unittest.TestCase):
    """Weights come from measured correlation, so the grade must reflect that
    a correlated pair is not two independent observations."""

    def _sig(self, fired):
        return {k: {"vote": (k in fired), "status": "ok"}
                for k in dimensions.TIER_A_SIGNALS}

    def test_correlated_pair_is_discounted(self):
        """MVRV Z + SSR correlate 0.79 - together they must score under 2.0."""
        g = dimensions.grade(self._sig({"mvrv_z_score",
                                        "stablecoin_supply_ratio"}))
        self.assertLess(g["score"], 2.0)
        self.assertAlmostEqual(g["score"], 1.6, places=1)

    def test_two_independent_signals_score_full(self):
        g = dimensions.grade(self._sig({"fear_greed", "exchange_netflows"}))
        self.assertAlmostEqual(g["score"], 2.0, places=1)

    def test_no_votes_grades_d(self):
        self.assertEqual(dimensions.grade(self._sig(set()))["grade"], "D")

    def test_froth_alone_can_never_reach_a_strong_grade(self):
        """Structural property worth asserting: all three froth signals
        together weigh 2.8, below band B (3.5). Froth alone cannot produce a
        strong reading no matter what - the cap below is a second defence,
        not the only one."""
        froth = {k for k, v in dimensions.SEMANTIC.items() if v == "froth"}
        g = dimensions.grade(self._sig(froth))
        self.assertLess(g["score"], dimensions.GRADE_BANDS[1][1])
        self.assertIn(g["grade"], ("C", "D"))

    def test_froth_majority_caps_a_mixed_grade(self):
        """The case the cap actually exists for: enough total evidence to
        reach B, but most of it is froth - so it must not read as permission
        to rotate."""
        froth = {k for k, v in dimensions.SEMANTIC.items() if v == "froth"}
        g = dimensions.grade(self._sig(froth | {"exchange_netflows"}))
        self.assertGreaterEqual(g["score"], dimensions.GRADE_BANDS[1][1])
        self.assertTrue(g["capped_for_froth_majority"])
        self.assertEqual(g["grade"], "C")

    def test_rotation_majority_is_not_capped(self):
        rot = {k for k, v in dimensions.SEMANTIC.items() if v == "rotation"}
        g = dimensions.grade(self._sig(rot))
        self.assertFalse(g["capped_for_froth_majority"])
        self.assertIn(g["grade"], ("A", "B"))

    def test_possible_shrinks_when_signals_unavailable(self):
        """Denominator honesty must survive into the grade."""
        s = self._sig({"fear_greed"})
        s["nvt"]["vote"] = None
        s["eth_etf_flows"]["vote"] = None
        g = dimensions.grade(s)
        self.assertLess(g["possible_this_run"], g["max_possible"])

    def test_weights_cover_every_tier_a_signal(self):
        for k in dimensions.TIER_A_SIGNALS:
            self.assertIn(k, dimensions.WEIGHTS, k)


class TestLadder(unittest.TestCase):
    """The mechanics the Monte Carlo showed matter: hysteresis, dwell, floor."""

    def _ok(self, votes):
        s = {}
        for k in ladder.ROTATION_SIGNALS:
            s[k] = {"status": "ok", "vote": votes.get(k, False),
                    "source_age_days": 0}
        return s

    def test_stale_source_is_not_measurable(self):
        s = self._ok({})
        s["fear_greed"]["source_age_days"] = 99
        self.assertFalse(ladder._measurable(s["fear_greed"]))

    def test_coverage_floor_freezes_rather_than_deciding(self):
        s = self._ok({})
        for k in list(ladder.ROTATION_SIGNALS)[:6]:
            s[k]["status"] = "error"
        info = ladder.compute_t(s)
        self.assertLess(info["coverage"], ladder.COVERAGE_FLOOR)
        self.assertFalse(info["measurable"])
        state, reason = ladder.next_state("BTC", info, 999)
        self.assertEqual(state, "BTC")
        self.assertIn("frozen", reason)

    def test_minimum_dwell_blocks_an_early_move(self):
        info = {"measurable": True, "t": 0.99, "coverage": 1.0}
        state, reason = ladder.next_state("BTC", info, 3)
        self.assertEqual(state, "BTC")
        self.assertIn("held", reason)

    def test_hysteresis_band_holds_the_state(self):
        """Between exit 0.45 and entry 0.55 nothing moves, in either direction."""
        info = {"measurable": True, "t": 0.50, "coverage": 1.0}
        self.assertEqual(ladder.next_state("BTC", info, 99)[0], "BTC")
        self.assertEqual(ladder.next_state("ETH", info, 99)[0], "ETH")

    def test_entry_requires_the_higher_threshold(self):
        info = {"measurable": True, "t": 0.56, "coverage": 1.0}
        self.assertEqual(ladder.next_state("BTC", info, 99)[0], "ETH")

    def test_one_rung_at_a_time(self):
        """No BTC -> ALT jump even at maximum score."""
        info = {"measurable": True, "t": 1.0, "coverage": 1.0}
        self.assertEqual(ladder.next_state("BTC", info, 99)[0], "ETH")

    def test_ladder_can_never_enter_usdt(self):
        """De-risking belongs to the sell gate; two authorities over one exit
        is the collision the design exists to avoid."""
        for t in (0.0, 0.3, 0.5, 0.9):
            info = {"measurable": True, "t": t, "coverage": 1.0}
            for state in ("BTC", "ETH", "ALT"):
                self.assertNotEqual(ladder.next_state(state, info, 99)[0], "USDT")

    def test_d1_weights_currently_sit_exactly_at_their_cap(self):
        """D1 holds 4 signals weighing 3.0 against a cap of 3.0, so the cap is
        not binding today - it is a guard that engages the moment a fifth
        momentum signal is added. Asserting this pins the invariant: if
        someone adds to D1 without raising the cap, the normalisation below
        silently starts shrinking every D1 signal."""
        d1 = [k for k, (d, _) in ladder.ROTATION_SIGNALS.items() if d == 1]
        self.assertEqual(len(d1), 4)
        self.assertAlmostEqual(sum(ladder.ROTATION_SIGNALS[k][1] for k in d1),
                               ladder.DIMENSION_CAPS[1])

    def test_cap_binds_when_a_dimension_is_overweight(self):
        """The mechanism itself: an overweight dimension is scaled back so it
        cannot outvote the rest by asking one question four ways."""
        original = dict(ladder.ROTATION_SIGNALS)
        try:
            ladder.ROTATION_SIGNALS["extra_momentum"] = (1, 3.0)
            s = self._ok({k: True for k in ladder.ROTATION_SIGNALS})
            info = ladder.compute_t(s)
            # every signal fires, so T must still be 1.0 - capping rescales
            # numerator and denominator together, it does not distort the ratio
            self.assertAlmostEqual(info["t"], 1.0)
            # but D1's contribution to measurable weight is held at its cap
            self.assertLessEqual(info["measurable_weight"],
                                 sum(ladder.DIMENSION_CAPS.values()) + 1e-9)
        finally:
            ladder.ROTATION_SIGNALS.clear()
            ladder.ROTATION_SIGNALS.update(original)

    def test_evaluate_never_governs(self):
        self.assertFalse(ladder.evaluate(self._ok({}))["governs"])

    def test_risk_signals_are_absent_from_the_rotation_axis(self):
        """MVRV Z and NVT answer 'should we be exposed at all' - risk axis.
        Including them here was the double-count."""
        self.assertNotIn("mvrv_z_score", ladder.ROTATION_SIGNALS)
        self.assertNotIn("nvt", ladder.ROTATION_SIGNALS)


class TestTrackedVotesDoNotLeak(unittest.TestCase):
    """btc_dominance votes on the ladder's rotation axis but is tracked-only
    for the gate. The two must not contaminate each other."""

    def test_tracked_signal_vote_never_enters_the_gate_tally(self):
        s = {k: {"vote": None, "status": "ok"} for k in dimensions.TIER_A_SIGNALS}
        s["btc_dominance"] = {"vote": True, "status": "ok"}
        t = dimensions.tally(s, "2026-08-31")
        self.assertEqual(t["fired"], 0)
        self.assertNotIn("btc_dominance", t["fired_signals"])

    def test_tracked_signal_vote_never_enters_the_grade(self):
        s = {k: {"vote": None, "status": "ok"} for k in dimensions.TIER_A_SIGNALS}
        s["btc_dominance"] = {"vote": True, "status": "ok"}
        self.assertEqual(dimensions.grade(s)["score"], 0.0)

    def test_but_it_does_count_for_ladder_coverage(self):
        s = {k: {"status": "ok", "vote": False, "source_age_days": 0}
             for k in ladder.ROTATION_SIGNALS}
        with_vote = ladder.compute_t(s)["coverage"]
        s["btc_dominance"]["vote"] = None
        without = ladder.compute_t(s)["coverage"]
        self.assertGreater(with_vote, without)


class TestReportSurfacesDecisionInstruments(unittest.TestCase):
    """The brief reads latest.md. Anything not rendered there does not exist
    as far as a decision is concerned - which is how the ladder, T and the
    grade were built and then left off the only consumable output."""

    def _snap(self, **over):
        lad = {"state": "BTC", "t": 0.5556, "coverage": 0.6875,
               "coverage_floor": 0.70, "measurable": False,
               "reason": "frozen - coverage below floor",
               "pending_decisions": ["sign the update"]}
        lad.update(over.pop("ladder", {}))
        s = {
            "date": "2026-08-31", "fetched_at": "x", "schema_version": 4,
            "signals": {}, "health": {"degraded": False, "failed": 0, "stale": 0},
            "gate_legacy": {"fired": 2, "checkable_today": 5, "fired_signals": ["a"]},
            "gate_new": {"authoritative": True, "fired": 4, "checkable": 8,
                         "threshold": 5, "would_fire": False, "unavailable": [],
                         "semantic": {"reading": "mixed: 3 rotation, 1 froth"}},
            "gate_grade": {"grade": "B", "label": "strong", "score": 4.0,
                           "possible_this_run": 7.6,
                           "capped_for_froth_majority": False},
            "ladder_shadow": lad,
        }
        s.update(over)
        return s

    def test_ladder_state_and_t_are_rendered(self):
        md = report.render_markdown(self._snap())
        self.assertIn("0.5556", md)
        self.assertIn("BTC", md)

    def test_frozen_but_t_clears_the_rung_is_called_out(self):
        """The dangerous read: state BTC looks like 'no signal' when in fact
        T already clears the next rung and only coverage blocks the move."""
        md = report.render_markdown(self._snap())
        self.assertIn("Frozen on coverage", md)

    def test_measurable_ladder_omits_the_warning(self):
        md = report.render_markdown(self._snap(ladder={"measurable": True}))
        self.assertNotIn("Frozen on coverage", md)

    def test_grade_is_rendered(self):
        self.assertIn("grade **B**", report.render_markdown(self._snap()))

    def test_ladder_states_it_governs_nothing(self):
        self.assertIn("does not govern", report.render_markdown(self._snap()))
