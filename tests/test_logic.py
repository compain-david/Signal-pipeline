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
import evidence_gate
import governance


class TestRegistry(unittest.TestCase):
    """The gate's shape is a spec commitment, not an implementation detail."""

    def test_exactly_eight_tier_a_signals(self):
        """Was 9. fear_greed demoted on walk-forward evidence (1/9 folds)."""
        self.assertEqual(len(dimensions.TIER_A_SIGNALS), 8)

    def test_fear_greed_no_longer_votes(self):
        """The demotion must be structural, not a comment. If someone puts it
        back without new evidence, this fails."""
        self.assertNotIn("fear_greed", dimensions.TIER_A_SIGNALS)
        self.assertEqual(dimensions.SIGNAL_REGISTRY["fear_greed"][1], "track")

    def test_adoption_rule_is_stated_and_strict(self):
        r = dimensions.ADOPTION_RULE
        self.assertGreaterEqual(r["min_edge_pts_90d"], 3.0)
        self.assertGreaterEqual(r["min_episodes"], 4)
        self.assertTrue(r["requires_walkforward_vs_shuffle"])
        self.assertTrue(r["requires_preregistered_direction"])

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
        s = self._signals({"exchange_netflows": True, "nvt": None,
                           "mvrv_z_score": False})
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
        g = dimensions.grade(self._sig({"eth_btc_momentum", "exchange_netflows"}))
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

    def test_froth_majority_cap_is_now_structurally_unreachable(self):
        """The cap existed for: enough total evidence to reach B, most of it
        froth. Demoting fear_greed made that state impossible - documented
        here rather than silently left as dead code."""
        froth = {k for k, v in dimensions.SEMANTIC.items() if v == "froth"}
        # STRUCTURAL CONSEQUENCE of demoting fear_greed, asserted rather than
        # worked around: froth can now total only 1.8 (mvrv 0.8 + nvt 1.0).
        # Band B needs 3.5, so any grade of B or better carries at least 1.7 of
        # rotation weight and rotation therefore always exceeds froth. A
        # froth-majority grade at B+ has become unreachable, which makes the
        # cap dead code today.
        #
        # It is kept, not deleted: restoring any froth signal to Tier A brings
        # the case straight back, and a guard that only matters after a future
        # edit is exactly the kind worth keeping. This test fails the day that
        # stops being true, which is the signal to re-examine the cap.
        froth_total = sum(dimensions.WEIGHTS[k] for k in froth
                          if k in dimensions.WEIGHTS)
        self.assertLess(froth_total, dimensions.GRADE_BANDS[1][1],
                        "froth alone can no longer reach band B")

        g = dimensions.grade(self._sig(froth | {"exchange_netflows",
                                                "eth_btc_momentum"}))
        self.assertGreaterEqual(g["score"], dimensions.GRADE_BANDS[1][1])
        self.assertFalse(g["capped_for_froth_majority"],
                         "rotation now necessarily outweighs froth at band B+")

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

    # Build payloads the ladder's OWN rules can read. Deliberately carries no
    # `vote` field at all: if any ladder code path still consulted `vote`,
    # every test in this class would break rather than silently pass.
    def _payload(self, key, fires):
        base = {"status": "ok", "source_age_days": 0}
        if key == "eth_btc_momentum":
            base["signal"] = 20.0 if fires else 1.0        # rule: > 10
        elif key == "btc_dominance":
            base["signal"] = 50.0 if fires else 59.0       # rule: < 54
        elif key == "alt_dominance":
            base.update(signal=30.0, ref_30d=20.0 if fires else 40.0)
        elif key == "altseason_index":
            base["signal"] = 80.0 if fires else 50.0       # rule: > 75
        elif key == "eth_etf_flows":
            base["signal"] = 1.0 if fires else -1.0        # rule: > 0
        elif key == "stablecoin_supply_ratio":
            base.update(signal=5.0, ref_value=9.0 if fires else 1.0)
        elif key == "alt_funding_rates":
            base.update(signal=0.0, alt_minus_btc_apr_pct=1.0 if fires else -1.0,
                        rising=True)
        elif key == "exchange_netflows":
            base["signal"] = -100.0 if fires else 100.0    # rule: < 0
        else:
            base["signal"] = 1.0 if fires else 0.0
        return base

    def _ok(self, votes):
        return {k: self._payload(k, votes.get(k, False))
                for k in ladder.ROTATION_SIGNALS}

    def test_stale_source_is_not_measurable(self):
        s = self._ok({})
        s["btc_dominance"]["source_age_days"] = 99
        self.assertFalse(ladder._measurable(s["btc_dominance"], "btc_dominance"))

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
            ladder.LADDER_RULES["extra_momentum"] = lambda p: True
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
            ladder.LADDER_RULES.pop("extra_momentum", None)

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

    def test_ladder_coverage_ignores_vote_entirely(self):
        """This test previously asserted that removing `vote` lowered ladder
        coverage - i.e. it encoded the coupling. That coupling is the defect
        that has now been removed, so the assertion is inverted: coverage
        depends on the readable `signal`, and `vote` is irrelevant to it."""
        s = {k: {"status": "ok", "signal": 0.0, "source_age_days": 0}
             for k in ladder.ROTATION_SIGNALS}
        s["alt_dominance"]["ref_30d"] = 1.0
        s["stablecoin_supply_ratio"]["ref_value"] = 1.0
        s["alt_funding_rates"].update({"alt_minus_btc_apr_pct": 1.0,
                                       "rising": True})
        base = ladder.compute_t(s)["coverage"]
        s["btc_dominance"]["vote"] = None
        self.assertEqual(ladder.compute_t(s)["coverage"], base)
        s["btc_dominance"]["signal"] = None
        self.assertLess(ladder.compute_t(s)["coverage"], base)


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


class TestLadderBasisInvariant(unittest.TestCase):
    """Coverage and T must be computed on the SAME set.

    They were not: coverage used raw weights, T used dimension-capped ones.
    With D1 weighing exactly its cap the two agreed by coincidence, so the
    divergence was invisible and would only have surfaced when a fifth
    momentum signal was added. These tests fail if they drift apart again.
    """

    def _all_ok(self, votes=None):
        votes = votes or {}
        out = {}
        for k in ladder.ROTATION_SIGNALS:
            p = {"status": "ok", "source_age_days": 0, "signal": 0.0}
            p.update(votes.get(k, {}))
            out[k] = p
        return out

    def test_full_coverage_is_exactly_one(self):
        """Every signal readable must give coverage 1.0 on any basis."""
        s = self._all_ok({"alt_dominance": {"ref_30d": 1.0},
                          "stablecoin_supply_ratio": {"ref_value": 1.0},
                          "alt_funding_rates": {"alt_minus_btc_apr_pct": 1.0,
                                                "rising": True}})
        self.assertAlmostEqual(ladder.compute_t(s)["coverage"], 1.0)

    def test_coverage_denominator_matches_t_denominator(self):
        """measurable_weight must be the numerator of coverage, so that
        coverage * total == measurable on one shared basis."""
        s = self._all_ok({"alt_dominance": {"ref_30d": 1.0},
                          "stablecoin_supply_ratio": {"ref_value": 1.0},
                          "alt_funding_rates": {"alt_minus_btc_apr_pct": 1.0,
                                                "rising": True}})
        s["eth_etf_flows"]["status"] = "no_api"
        i = ladder.compute_t(s)
        # places=3: compute_t rounds its outputs to 4dp, so the identity holds
        # to rounding, not to machine precision. Asserting tighter would test
        # the rounding, not the invariant.
        self.assertAlmostEqual(i["coverage"] * i["total_weight"],
                               i["measurable_weight"], places=3)

    def test_invariant_holds_when_a_dimension_is_overweight(self):
        """The case that would have exposed the original bug."""
        original = dict(ladder.ROTATION_SIGNALS)
        try:
            ladder.ROTATION_SIGNALS["extra_momentum"] = (1, 3.0)
            s = self._all_ok({"alt_dominance": {"ref_30d": 1.0},
                              "stablecoin_supply_ratio": {"ref_value": 1.0},
                              "alt_funding_rates": {"alt_minus_btc_apr_pct": 1.0,
                                                    "rising": True}})
            s["extra_momentum"] = {"status": "ok", "source_age_days": 0,
                                   "signal": 0.0}
            i = ladder.compute_t(s)
            self.assertAlmostEqual(i["coverage"] * i["total_weight"],
                                   i["measurable_weight"], places=6)
        finally:
            ladder.ROTATION_SIGNALS.clear()
            ladder.ROTATION_SIGNALS.update(original)

    def test_ladder_never_reads_vote(self):
        """Reading `vote` would re-couple the ladder to the gate's thresholds.
        A signal with a vote but no readable value must count as unmeasurable."""
        s = self._all_ok()
        s["btc_dominance"] = {"status": "ok", "source_age_days": 0,
                              "signal": None, "vote": True}
        self.assertFalse(ladder._measurable(s["btc_dominance"], "btc_dominance"))

    def test_ladder_thresholds_are_its_own(self):
        """btc_dominance below 54 fires for the ladder regardless of `vote`."""
        p = {"status": "ok", "source_age_days": 0, "signal": 50.0, "vote": False}
        self.assertTrue(ladder.LADDER_RULES["btc_dominance"](p))
        p["signal"] = 59.0
        self.assertFalse(ladder.LADDER_RULES["btc_dominance"](p))


class TestEvidenceGate(unittest.TestCase):
    """Le gate d'evidence doit rester scope a sa preuve, y compris quand
    quelqu'un voudra l'elargir."""

    def _sig(self, **over):
        base = {"lth_share": {"status": "ok", "signal": 0.808,
                              "change_30d": -0.001, "source_age_days": 0}}
        base.update(over)
        return base

    def test_rotation_decides_nothing(self):
        """Le vide cote rotation est le resultat, pas un oubli. Si quelqu'un
        y ajoute une entree sans que ADOPTION_RULE soit satisfaite, ce test
        est le garde-fou."""
        self.assertEqual(evidence_gate.DECIDING["rotation"], [])
        v = evidence_gate.evaluate(self._sig())
        self.assertEqual(v["rotation"]["verdict"], "AUCUNE DECISION POSSIBLE")

    def test_never_governs(self):
        self.assertFalse(evidence_gate.evaluate(self._sig())["governs"])

    def test_sell_side_is_not_armed_despite_a_measured_edge(self):
        """Le piege exact que ce module doit eviter: un edge encourageant
        n'arme pas un mecanisme qui vend le portefeuille."""
        v = evidence_gate.evaluate(self._sig())
        self.assertTrue(v["sell"]["distributing_30d"])   # le signal tire
        self.assertFalse(v["sell"]["armed"])             # et n arme rien

    def test_adoption_detail_matches_the_summary(self):
        v = evidence_gate.evaluate(self._sig())["sell"]
        passed = sum(1 for x in v["adoption_detail"].values() if x)
        self.assertEqual(v["adoption_passed"],
                         "%d/%d" % (passed, len(v["adoption_detail"])))

    def test_stale_input_is_not_readable(self):
        v = evidence_gate.evaluate(self._sig(
            lth_share={"status": "ok", "signal": 0.8, "change_30d": -0.01,
                       "source_age_days": 99}))
        self.assertFalse(v["sell"]["readable"])
        self.assertIsNone(v["sell"]["distributing_30d"])

    def test_deciding_inputs_are_a_subset_of_known_signals(self):
        for axis in evidence_gate.DECIDING.values():
            for key in axis:
                self.assertIn(key, dimensions.SIGNAL_REGISTRY, key)


class TestGovernance(unittest.TestCase):
    """Un seul instrument gouverne. C'est l'invariant que toute cette
    architecture existe pour tenir - deux autorites sur une decision est la
    collision que le Pivot Ladder avait identifiee."""

    def _snap(self):
        return {k: {} for k, _ in governance.HIERARCHY}

    def test_exactly_one_instrument_governs(self):
        for today in ("2026-09-01", "2026-09-30", "2027-01-01"):
            g = governance.summarise(self._snap(), today)
            self.assertEqual(sum(1 for i in g["instruments"] if i["governs"]), 1,
                             today)

    def test_legacy_governs_before_adoption_and_new_after(self):
        before = governance.summarise(self._snap(), "2026-09-01")
        self.assertEqual(before["governing"], "gate_legacy")
        after = governance.summarise(self._snap(), dimensions.ADOPTED_FROM)
        self.assertEqual(after["governing"], "gate_new")

    def test_ladder_and_evidence_never_govern(self):
        """Le premier exige une signature, le second ne demandera jamais."""
        for today in ("2026-09-01", "2027-06-01", "2030-01-01"):
            g = governance.summarise(self._snap(), today)
            for i in g["instruments"]:
                if i["name"] in ("ladder_shadow", "evidence_gate"):
                    self.assertFalse(i["governs"], "%s / %s" % (i["name"], today))

    def test_governing_is_computed_from_the_date_not_stored(self):
        """La seule chose qui change ce statut est le calendrier. Si quelqu'un
        code le nom en dur, ce test le voit."""
        self.assertEqual(governance.governing("2026-09-29"), "gate_legacy")
        self.assertEqual(governance.governing("2026-09-30"), "gate_new")

    def test_every_instrument_states_what_would_promote_it(self):
        g = governance.summarise(self._snap(), "2026-09-01")
        for i in g["instruments"]:
            if i["name"] != "gate_legacy":
                self.assertTrue(i["to_promote"], i["name"])
