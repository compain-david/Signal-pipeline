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
