#!/usr/bin/env python3
"""
Tests for the pre-registration registry. No network, no clock.

Every date, threshold and file path is injected. The registry's whole job is to
refuse things, so most of these tests assert a refusal: that a locked field
cannot be rewritten, that a post-hoc result cannot be adopted, that a test which
could never have concluded is not reported as a near miss.

Six groups are load-bearing beyond the code they cover:

  TestOneDecisionAboutTheNull is the group that would have caught the defect
  this file was rewritten for. measure() and render_report() each decided which
  null draws a mean could be built from, under two DIFFERENT tests, and one run
  published 62% in its table against 47.6% in its JSON for the same cell. These
  assert the decision is taken once and copied - and
  TestReportMatchesThePersistedRegistry compares the two real artefacts line by
  line.

  TestWithdrawnTargets pins the refusal that is not statistical. HEAD's
  build_rotations.py withdrew the alt results because the index holds none of
  this cycle's majors, and a registry that let a good p-value promote one of
  them would be counting draws impeccably while answering another question.

  TestMeasurementLayer runs the real walk over the real JSONs and pins the
  numbers this run reproduced - F&G = 1/9, the control = 5/5, a data end of
  2026-08-31. Everything else in this file could pass on hand-written
  dictionaries while measure() returned nonsense; this is the group that would
  notice.

  TestFingerprint covers the identity field added after analysis/dominance.json
  was regenerated MID-RUN - different basket, different universe, same dates -
  while the old comparison key could not tell the two experiments apart.

  TestOfflineLoading patches urlopen to raise and asserts the module still
  builds its inputs. Being offline because a cache file happens to exist is not
  the same property as being offline by construction.

  TestReport asserts the alt-basket caveat is on the alt ROWS, not only in a
  trailing block. A bias that survives quotation out of context is a control; a
  bias that does not is decoration.

Run: python -m unittest discover -s tests -v
"""

import os
import re
import sys
import tempfile
import unittest
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))

import registry
import walkforward as wf

HAVE_FNG = os.path.exists(registry.FNG_CACHE)
HAVE_REGISTRY = os.path.exists(registry.REGISTRY_PATH)
HAVE_REPORT = os.path.exists(registry.REPORT_PATH)
HAVE_BASKET = os.path.exists(os.path.join(registry.ANALYSIS, "basket_log.txt"))
NO_FNG = "cache F&G absent (analysis/.cache est gitignore)"
NO_REGISTRY = "analysis/registry.json absent - lancer scripts/registry.py"
NO_REPORT = "analysis/registry_report.txt absent - lancer scripts/registry.py"
NO_BASKET = "analysis/basket_log.txt absent - lancer scripts/build_rotations.py"

# One row of the report's shuffle table, anchored on the END so the free-form
# "plis obtenus" cell in the middle cannot shift the columns that matter.
# Groups: id, target, mode, draws, usable, degenerate, folds seen, real folds,
# matched, basis, mean, gap.
NULL_ROW = re.compile(
    r"^\s+(H\d+)\s+(\S+)\s+(melange|decalage)\s+(\d+)\s+(\d+)\s+(\d+)\s+"
    r"(.+?)\s+(\d+)\s+(\d+)\s+(\S+\(\d+\)|n=\d+ insuff\.)\s+(\S+)\s+(\S+)\s*$")


def entry(direction=1, threshold=0.70, registered_on="2026-01-01",
          target="eth_btc"):
    reg = registry.new_registry("2026-01-01")
    return registry.register(reg, "H", "signal", target, direction,
                             threshold, registered_on, "test")


def null_summary(matched=200, usable=240, draws=250, real_rate=100.0,
                 mean=50.0):
    """A null summary shaped exactly as summarise_null() returns one."""
    comparable = matched >= registry.MIN_MATCHED_NULLS
    ref_n = matched if comparable else usable
    return {"draws": draws, "usable": usable, "degenerate": draws - usable,
            "matched": matched, "fold_min": 0, "fold_max": 7, "fold_median": 2,
            "mean_all": mean, "mean_matched": mean, "rates_matched": [],
            "rates_all": [], "comparable": comparable,
            "ref_basis": "apparies" if comparable else "tous",
            "ref_n": ref_n,
            "ref_mean": mean if ref_n >= registry.MIN_MATCHED_NULLS else None,
            "gap": (real_rate - mean
                    if ref_n >= registry.MIN_MATCHED_NULLS else None)}


def measurement(**kw):
    """A measurement that passes every statistical criterion by default.

    Tests then break exactly one field, so a failure names its own cause.
    """
    m = {"folds": 10, "agree": 10, "agreement": 1.0, "attempts": 12,
         "null_mean": 50.0, "null_mean_basis": "apparies", "null_mean_n": 200,
         "gap": 50.0, "p": 0.004, "p_basis": "apparies", "p_n": 200,
         "floor": registry.resolution_floor(10, 200),
         "direction": 1, "dir_votes": [10, 0], "direction_insample": 1,
         "prereg": "PRE", "data_end": "2027-06-01",
         "shuffles": 250, "null_usable": 240, "null_degenerate": 10,
         "null_matched": 200, "null_comparable": True,
         "window": 365, "train_days": 365, "test_days": 180, "horizon": 90,
         "signal_days": 2800, "signal_days_in_target": 2710,
         "outside_target_days": 90, "before_target_days": 0,
         "calendar": {"n": 2710, "span": 2710, "missing": 0,
                      "first": "2019-01-01", "last": "2026-05-31"},
         "signal_fingerprint": "aaaaaaaaaaaa",
         "target_fingerprint": "bbbbbbbbbbbb",
         "comparison_key": "H|eth_btc|365|365|180|2027-06-01|aaa|bbb",
         "nulls": {mode: null_summary() for mode in registry.NULL_MODES}}
    m.update(kw)
    return m


class TestRegistryFile(unittest.TestCase):
    """The file is the artifact; these are its invariants."""

    def test_registry_governs_nothing(self):
        self.assertIn("rien", registry.new_registry("2026-01-01")["governs"])

    def test_schema_version_is_stamped(self):
        self.assertEqual(registry.new_registry("2026-01-01")["schema_version"],
                         registry.SCHEMA_VERSION)

    def test_registration_stores_the_expected_direction(self):
        e = entry(direction=-1)
        self.assertEqual(e["expected_direction"], -1)
        self.assertEqual(e["status"], "enregistree")
        self.assertEqual(e["results"], [])

    def test_direction_must_be_plus_or_minus_one(self):
        reg = registry.new_registry("2026-01-01")
        for bad in (0, 2, None, "up"):
            with self.assertRaises(ValueError):
                registry.register(reg, "X", "s", "eth_btc", bad, 0.7,
                                  "2026-01-01", "why")

    def test_threshold_must_be_a_fraction(self):
        reg = registry.new_registry("2026-01-01")
        for bad in (0.0, -0.1, 1.5):
            with self.assertRaises(ValueError):
                registry.register(reg, "X", "s", "eth_btc", 1, bad,
                                  "2026-01-01", "why")

    def test_identical_reregistration_is_idempotent(self):
        reg = registry.new_registry("2026-01-01")
        for _ in range(3):
            registry.register(reg, "H", "s", "eth_btc", 1, 0.7,
                              "2026-01-01", "why")
        self.assertEqual(len(reg["entries"]), 1)

    def test_expected_direction_cannot_be_rewritten(self):
        """The single most important refusal in the module: a direction
        editable after the measurement is not a prediction."""
        reg = registry.new_registry("2026-01-01")
        registry.register(reg, "H", "s", "eth_btc", 1, 0.7, "2026-01-01", "w")
        with self.assertRaises(ValueError) as ctx:
            registry.register(reg, "H", "s", "eth_btc", -1, 0.7,
                              "2026-01-01", "w")
        self.assertIn("expected_direction", str(ctx.exception))

    def test_target_and_threshold_are_locked_too(self):
        reg = registry.new_registry("2026-01-01")
        registry.register(reg, "H", "s", "eth_btc", 1, 0.7, "2026-01-01", "w")
        with self.assertRaises(ValueError):
            registry.register(reg, "H", "s", "alt_eth", 1, 0.7,
                              "2026-01-01", "w")
        with self.assertRaises(ValueError):
            registry.register(reg, "H", "s", "eth_btc", 1, 0.5,
                              "2026-01-01", "w")

    def test_rationale_is_not_locked(self):
        """The prose may be improved; the prediction may not."""
        reg = registry.new_registry("2026-01-01")
        registry.register(reg, "H", "s", "eth_btc", 1, 0.7, "2026-01-01", "a")
        registry.register(reg, "H", "s", "eth_btc", 1, 0.7, "2026-01-01", "b")
        self.assertEqual(len(reg["entries"]), 1)

    def test_save_and_load_round_trip(self):
        reg = registry.new_registry("2026-01-01")
        registry.register(reg, "H", "s", "eth_btc", -1, 0.8, "2026-01-01", "w")
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "sub", "registry.json")
            registry.save(reg, p)
            back = registry.load(p)
        self.assertEqual(back["entries"][0]["expected_direction"], -1)
        self.assertEqual(back["entries"][0]["success_threshold"], 0.8)

    def test_load_missing_file_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(registry.load(os.path.join(d, "nope.json")))

    def test_migration_moves_the_stamp_and_nothing_else(self):
        """Rewriting old results into the new shape would make them look as if
        they had been measured the new way."""
        old = {"schema_version": 1, "created_on": "2026-01-01",
               "entries": [{"id": "H", "results": [{"verdict": "REJETE"}]}]}
        new = registry.migrate(dict(old))
        self.assertEqual(new["schema_version"], registry.SCHEMA_VERSION)
        self.assertEqual(new["entries"], old["entries"])
        self.assertEqual(new["comparisons"], [])


class TestPreregistrationStatus(unittest.TestCase):
    """PRE is a subtraction of two dates, never a self-declaration."""

    def test_unseen_window_is_one_test_fold_plus_one_horizon(self):
        self.assertEqual(registry.MIN_UNSEEN_DAYS,
                         registry.TEST_DAYS + registry.HORIZON)

    def test_registered_after_the_data_ends_is_post_hoc(self):
        self.assertEqual(
            registry.preregistration_status("2026-09-01", "2026-08-31"), "POST")

    def test_registered_one_day_early_is_still_post_hoc(self):
        self.assertEqual(
            registry.preregistration_status("2026-01-01", "2026-01-02"), "POST")

    def test_a_full_unseen_fold_earns_pre(self):
        self.assertEqual(
            registry.preregistration_status("2026-01-01", "2027-06-01"), "PRE")

    def test_boundary_is_inclusive(self):
        import datetime
        d = (datetime.date(2026, 1, 1)
             + datetime.timedelta(days=registry.MIN_UNSEEN_DAYS)).isoformat()
        self.assertEqual(
            registry.preregistration_status("2026-01-01", d), "PRE")

    def test_every_hypothesis_registered_today_is_post_hoc(self):
        """The claim the report makes about its own run, checked rather than
        trusted."""
        self.assertEqual(
            registry.preregistration_status(registry.TODAY, "2026-08-31"),
            "POST")


class TestStatistics(unittest.TestCase):

    def test_bonferroni_divides_alpha_by_the_count(self):
        self.assertAlmostEqual(registry.bonferroni_bar(10, alpha=0.05), 0.005)

    def test_bonferroni_survives_an_empty_family(self):
        self.assertAlmostEqual(registry.bonferroni_bar(0, alpha=0.05), 0.05)

    def test_permutation_p_can_never_be_zero(self):
        """A finite number of draws cannot establish impossibility."""
        self.assertGreater(registry.permutation_p(100.0, [0.0] * 100), 0.0)

    def test_permutation_p_counts_ties_against_the_signal(self):
        self.assertAlmostEqual(registry.permutation_p(50.0, [50.0] * 9), 1.0)

    def test_permutation_p_without_a_null_is_uninformative(self):
        self.assertEqual(registry.permutation_p(100.0, []), 1.0)

    def test_resolution_floor_is_the_worse_of_folds_and_draws(self):
        self.assertAlmostEqual(registry.resolution_floor(4, 1000), 0.0625)
        self.assertAlmostEqual(registry.resolution_floor(20, 9), 0.1)

    def test_four_perfect_folds_cannot_reach_alpha(self):
        """The finding that makes SOUS_RESOLU a distinct verdict."""
        self.assertGreater(registry.resolution_floor(4, 10 ** 6), 0.05)

    def test_the_floor_reads_matched_draws_not_the_nominal_count(self):
        """The parameter was called `shuffles` and only the docstring said it
        had to receive the MATCHED count. A caller passing the module constant
        got 1/251 of advertised resolution where the run had 1/15, silently.

        Renaming it does not make that confusion raise, so this pins the two
        apart on the numbers of a really scored hypothesis instead - and on the
        direction of the error, which always FLATTERS the test.
        """
        folds, matched = 5, 14
        wrong = registry.resolution_floor(folds, registry.SHUFFLES)
        right = registry.resolution_floor(folds, matched)
        self.assertNotAlmostEqual(wrong, right)
        self.assertLess(wrong, right)

    def test_entry_threshold_can_tighten_but_never_loosen(self):
        self.assertAlmostEqual(registry.effective_threshold(0.9), 0.9)
        self.assertAlmostEqual(registry.effective_threshold(0.1),
                               registry.MIN_AGREEMENT)


class TestOneDecisionAboutTheNull(unittest.TestCase):
    """Which draws a mean may rest on is decided ONCE, in summarise_null.

    The defect this group exists for: measure() asked "matched >=
    MIN_MATCHED_NULLS" and the report asked "matched > 0", so one run published
    two different numbers for the same cell - 62% in the table against 47.6% in
    the JSON - with nothing saying which one the adoption rule had read.
    """

    def _draws(self, rates_and_folds, degenerate=0):
        return {"draws": len(rates_and_folds) + degenerate,
                "rates": rates_and_folds,
                "fold_counts": ([f for _, f in rates_and_folds]
                                + [0] * degenerate),
                "degenerate": degenerate}

    def test_enough_matched_draws_uses_the_matched_subset(self):
        nd = self._draws([(40.0, 5)] * registry.MIN_MATCHED_NULLS
                         + [(90.0, 2)] * 50)
        s = registry.summarise_null(nd, 5, 100.0)
        self.assertTrue(s["comparable"])
        self.assertEqual(s["ref_basis"], "apparies")
        self.assertEqual(s["ref_n"], registry.MIN_MATCHED_NULLS)
        self.assertAlmostEqual(s["ref_mean"], 40.0)
        self.assertAlmostEqual(s["gap"], 60.0)

    def test_too_few_matched_draws_falls_back_and_says_so(self):
        nd = self._draws([(40.0, 5)] * 3 + [(90.0, 2)] * 60)
        s = registry.summarise_null(nd, 5, 100.0)
        self.assertFalse(s["comparable"])
        self.assertEqual(s["ref_basis"], "tous")
        self.assertEqual(s["ref_n"], 63)
        # The fallback mean is the ALL-draws mean, never the 3 matched ones.
        self.assertNotAlmostEqual(s["ref_mean"], 40.0)

    def test_a_mean_is_refused_below_the_minimum_number_of_draws(self):
        """A mean of one draw is not a mean, and neither is the gap under it."""
        nd = self._draws([(71.0, 7)])
        s = registry.summarise_null(nd, 7, 43.0)
        self.assertEqual(s["matched"], 1)
        self.assertIsNone(s["ref_mean"])
        self.assertIsNone(s["gap"])

    def test_the_basis_and_the_count_travel_with_the_mean(self):
        """A mean without the subset it rests on is the cell that started
        this: 62% and 47.6% are both means, of different things."""
        for matched in (0, 1, 14, 200):
            nd = self._draws([(40.0, 5)] * matched + [(90.0, 2)] * 60)
            s = registry.summarise_null(nd, 5, 100.0)
            self.assertEqual(s["comparable"],
                             s["matched"] >= registry.MIN_MATCHED_NULLS)
            self.assertEqual(s["ref_n"],
                             s["matched"] if s["comparable"] else s["usable"])
            if s["ref_mean"] is not None:
                self.assertGreaterEqual(s["ref_n"], registry.MIN_MATCHED_NULLS)

    def test_a_gap_the_summary_refused_cannot_reject(self):
        """Criterion 4 must never read a gap that was not computed."""
        m = measurement(gap=None, null_comparable=False, null_matched=1,
                        null_mean=None)
        v = registry.adoption_verdict(entry(), m, 0.05)
        self.assertNotIn("ecart au melange", " ".join(v["reasons"]))


class TestAdoptionRule(unittest.TestCase):

    def _verdict(self, m, e=None, bar=0.05):
        return registry.adoption_verdict(e or entry(), m, bar)

    def test_fear_greed_measured_today_is_rejected(self):
        """The verdict the whole module is checked against: 1 fold in 9,
        against a shuffle at roughly a coin flip."""
        m = measurement(folds=9, agree=1, agreement=1 / 9, direction=1,
                        dir_votes=[6, 3], gap=-34.5, null_mean=46.0,
                        null_comparable=False, null_matched=0, p=0.69,
                        floor=1.0, prereg="POST", data_end="2026-08-31")
        v = self._verdict(m)
        self.assertEqual(v["verdict"], "REJETE")
        self.assertTrue(any("accord" in r for r in v["reasons"]))

    def test_a_flawless_post_hoc_result_is_only_a_candidate(self):
        v = self._verdict(measurement(prereg="POST"))
        self.assertEqual(v["verdict"], "CANDIDAT")

    def test_the_same_result_pre_registered_is_adopted(self):
        self.assertEqual(self._verdict(measurement())["verdict"], "ADOPTE")

    def test_nothing_post_hoc_is_ever_adopted(self):
        """The ceiling that makes the module expensive, and the only one that
        holds: no analysis run today can promote anything today."""
        for extra in ({}, {"p": 0.0}, {"agreement": 1.0}, {"gap": 99.0}):
            m = measurement(prereg="POST", **extra)
            self.assertNotEqual(self._verdict(m)["verdict"], "ADOPTE")

    def test_direction_opposite_to_the_registered_one_is_fatal(self):
        v = self._verdict(measurement(direction=-1, dir_votes=[0, 10]))
        self.assertEqual(v["verdict"], "REJETE")
        self.assertTrue(any("fausse" in r for r in v["reasons"]))

    def test_the_rejection_reason_carries_the_vote_split(self):
        """A 5-4 majority must not read like a 9-0 one."""
        v = self._verdict(measurement(direction=-1, dir_votes=[4, 5]))
        self.assertIn("4 plis +1", " ".join(v["reasons"]))

    def test_an_unidentifiable_direction_does_not_confirm_anything(self):
        v = self._verdict(measurement(direction=None, dir_votes=[5, 5]))
        self.assertEqual(v["verdict"], "REJETE")

    def test_the_direction_criterion_reads_the_out_of_sample_field(self):
        """direction_insample is printed, never judged on. Here the two
        disagree and the verdict must follow the out-of-sample one."""
        good = measurement(direction=1, direction_insample=-1)
        self.assertEqual(self._verdict(good)["verdict"], "ADOPTE")
        bad = measurement(direction=-1, dir_votes=[0, 10],
                          direction_insample=1)
        self.assertEqual(self._verdict(bad)["verdict"], "REJETE")

    def test_agreement_below_the_registered_threshold_is_rejected(self):
        self.assertEqual(
            self._verdict(measurement(agree=6, agreement=0.6))["verdict"],
            "REJETE")

    def test_a_lax_entry_threshold_cannot_undercut_the_floor(self):
        e = entry(threshold=0.20)
        m = measurement(agree=5, agreement=0.5)
        self.assertEqual(self._verdict(m, e)["verdict"], "REJETE")

    def test_beating_the_shuffle_by_too_little_is_rejected(self):
        m = measurement(gap=registry.MIN_GAP_PTS - 1)
        self.assertEqual(self._verdict(m)["verdict"], "REJETE")

    def test_a_thin_gap_cannot_reject_when_the_null_is_not_comparable(self):
        """Rejecting on an incomparable null would be the module committing
        the error it audits."""
        m = measurement(gap=-30.0, null_comparable=False, null_matched=2,
                        floor=1.0, p=0.4)
        v = self._verdict(m)
        self.assertEqual(v["verdict"], "SOUS_RESOLU")
        self.assertFalse(any("ecart au melange" in r for r in v["reasons"]))

    def test_an_incomparable_null_is_undecidable_even_with_a_tiny_p(self):
        m = measurement(null_comparable=False, null_matched=0, p=0.0001)
        self.assertEqual(self._verdict(m)["verdict"], "SOUS_RESOLU")

    def test_a_failure_on_the_substance_still_outranks_undecidability(self):
        """A wrong direction is evidence against; an unresolved test is not.
        The first must win, or a falsified hypothesis hides behind the second."""
        m = measurement(direction=-1, dir_votes=[0, 10],
                        null_comparable=False, null_matched=0)
        self.assertEqual(self._verdict(m)["verdict"], "REJETE")

    def test_too_few_folds_is_not_a_failure_but_a_non_test(self):
        v = self._verdict(measurement(folds=registry.MIN_FOLDS - 1))
        self.assertEqual(v["verdict"], "NON_TESTABLE")
        self.assertFalse(v["scored"])

    def test_an_undecidable_test_is_not_reported_as_a_near_miss(self):
        m = measurement(p=0.5, floor=0.0625, folds=4, agree=4)
        self.assertEqual(self._verdict(m, bar=0.0083)["verdict"], "SOUS_RESOLU")

    def test_a_test_with_the_resolution_to_conclude_is_plainly_rejected(self):
        m = measurement(p=0.5, floor=0.001)
        self.assertEqual(self._verdict(m, bar=0.0083)["verdict"], "REJETE")

    def test_every_failed_criterion_is_reported_not_just_the_first(self):
        """A single-reason rejection invites 'so fix that one thing'."""
        m = measurement(agree=5, agreement=0.5, direction=-1,
                        dir_votes=[0, 10], gap=1.0)
        self.assertGreaterEqual(len(self._verdict(m)["reasons"]), 3)

    def test_verdict_is_always_one_of_the_declared_values(self):
        for m in (measurement(), measurement(prereg="POST"),
                  measurement(folds=1), measurement(agreement=0.1),
                  measurement(null_comparable=False, null_matched=0)):
            self.assertIn(self._verdict(m)["verdict"], registry.VERDICTS)

    def test_a_scored_verdict_always_carries_its_comparison_key(self):
        v = self._verdict(measurement())
        self.assertTrue(v["scored"])
        self.assertTrue(v["comparison_key"])

    def test_the_verdict_carries_every_input_it_was_judged_on(self):
        """A conclusion whose inputs were not persisted cannot be audited."""
        m = measurement()
        v = self._verdict(m)
        for k in m:
            self.assertIn(k, v, k)


class TestWithdrawnTargets(unittest.TestCase):
    """A refusal about the QUESTION, not about the strength of the evidence.

    HEAD's build_rotations.py rebuilt the alt index and its commit withdrew the
    alt results outright: CoinMetrics community carries none of this cycle's
    majors, so the index measures a 2017-2021 basket. A p-value cannot reopen
    that, and the rule must not let it.
    """

    def test_the_alt_targets_are_the_withdrawn_ones(self):
        self.assertEqual(set(registry.WITHDRAWN_TARGETS),
                         {"alt_eth", "alt_btc"})
        self.assertNotIn("eth_btc", registry.WITHDRAWN_TARGETS)

    def test_a_perfect_result_on_a_withdrawn_target_is_still_refused(self):
        """Every statistical criterion passes here. It changes nothing."""
        v = registry.adoption_verdict(entry(target="alt_eth"),
                                      measurement(), 0.05)
        self.assertEqual(v["verdict"], "NON_TESTABLE")
        self.assertIn("univers invalide", " ".join(v["reasons"]))

    def test_a_withdrawn_result_never_enters_the_family_counter(self):
        """Scoring it would count it as a comparison about the question and
        print a p-value the reader could weigh. There is nothing to weigh."""
        v = registry.adoption_verdict(entry(target="alt_btc"),
                                      measurement(), 0.05)
        self.assertFalse(v["scored"])

    def test_the_withdrawal_is_checked_before_the_fold_count(self):
        """Two refusals with different lifetimes: too few folds is a sample
        limit that time fixes, a wrong universe is not."""
        v = registry.adoption_verdict(entry(target="alt_eth"),
                                      measurement(folds=1), 0.05)
        self.assertIn("univers invalide", " ".join(v["reasons"]))
        self.assertNotIn("requis", " ".join(v["reasons"]))

    def test_withdrawn_hypotheses_stay_registered_rather_than_deleted(self):
        """A withdrawn hypothesis that disappears leaves no trace of having
        been asked - the exact forgetting this file exists to prevent."""
        alt = [h for h in registry.HYPOTHESES
               if h[2] in registry.WITHDRAWN_TARGETS]
        self.assertTrue(alt)


@unittest.skipUnless(HAVE_BASKET, NO_BASKET)
class TestTheWithdrawalIsMeasuredNotAsserted(unittest.TestCase):
    """The reason for the withdrawal is read off the index that was built,
    not quoted from the commit message that announced it."""

    def test_no_cycle_major_ever_entered_the_alt_index(self):
        absent, present, ever = registry.absent_majors()
        self.assertEqual(set(absent), set(registry.CYCLE_MAJORS))
        self.assertEqual(present, ())
        self.assertGreater(ever, 0)

    def test_the_measurement_would_reopen_the_question_if_it_changed(self):
        """An asset the index DOES hold must come back as present, or the
        measurement is not measuring anything and the withdrawal rests on a
        function that always says yes."""
        absent, present, _ = registry.absent_majors(
            majors=("xrp", "definitely_not_an_asset"))
        self.assertEqual(present, ("xrp",))
        self.assertEqual(absent, ("definitely_not_an_asset",))


class TestFingerprint(unittest.TestCase):
    """Added because the data was regenerated UNDER this module mid-run.

    Same hypothesis id, same target name, same windows, same 2026-08-31 cutoff -
    and a different basket behind all of it. The old key could not tell the two
    experiments apart, so a date range was doing the work of an identity.
    """

    def test_identical_series_give_identical_digests(self):
        a = {"2026-01-01": 1.0, "2026-01-02": 2.0}
        self.assertEqual(registry.fingerprint(a), registry.fingerprint(dict(a)))

    def test_key_order_does_not_change_the_digest(self):
        a = {"2026-01-02": 2.0, "2026-01-01": 1.0}
        b = {"2026-01-01": 1.0, "2026-01-02": 2.0}
        self.assertEqual(registry.fingerprint(a), registry.fingerprint(b))

    def test_one_changed_value_changes_the_digest(self):
        a = {"2026-01-01": 1.0, "2026-01-02": 2.0}
        b = {"2026-01-01": 1.0, "2026-01-02": 2.5}
        self.assertNotEqual(registry.fingerprint(a), registry.fingerprint(b))

    def test_regenerated_data_is_a_different_comparison(self):
        """The point: same everything except the numbers, and the family
        counter must see two draws rather than one."""
        base = ("H01", "eth_btc", 365, 365, 180, "2026-08-31")
        k1 = registry.comparison_key(*base, signal_fp="aaa", target_fp="bbb")
        k2 = registry.comparison_key(*base, signal_fp="ccc", target_fp="bbb")
        self.assertNotEqual(k1, k2)

    def test_older_keys_without_a_digest_stay_parseable(self):
        """Entries already in the file were written by a version that did not
        know what it had measured. That is true of them, and not rewritten."""
        k = registry.comparison_key("H01", "eth_btc", 365, 365, 180,
                                    "2026-08-31")
        self.assertTrue(k.endswith("||"))


class TestFamilyCounter(unittest.TestCase):
    """The bar depends on a count, so the count is where the module can lie."""

    def _reg(self):
        reg = registry.new_registry("2026-01-01")
        registry.register(reg, "H", "s", "eth_btc", 1, 0.7, "2026-01-01", "w")
        return reg

    def test_a_scored_result_enters_the_family(self):
        reg = self._reg()
        v = registry.adoption_verdict(entry(), measurement(), 0.05)
        registry.record_result(reg, "H", v, "2026-09-01")
        self.assertEqual(registry.family_size(reg), 1)

    def test_rerunning_the_identical_test_does_not_inflate_the_bar(self):
        reg = self._reg()
        v = registry.adoption_verdict(entry(), measurement(), 0.05)
        for _ in range(4):
            registry.record_result(reg, "H", v, "2026-09-01")
        self.assertEqual(registry.family_size(reg), 1)
        self.assertEqual(len(reg["entries"][0]["results"]), 1)

    def test_a_result_that_differs_in_any_field_is_still_appended(self):
        """Nothing is ever removed or edited; a changed run appends."""
        reg = self._reg()
        v1 = registry.adoption_verdict(entry(), measurement(), 0.05)
        v2 = registry.adoption_verdict(entry(), measurement(p=0.001), 0.05)
        registry.record_result(reg, "H", v1, "2026-09-01")
        registry.record_result(reg, "H", v2, "2026-09-01")
        self.assertEqual(len(reg["entries"][0]["results"]), 2)

    def test_a_different_configuration_is_a_different_comparison(self):
        reg = self._reg()
        a = measurement(comparison_key="H|eth_btc|365|365|180|X||")
        b = measurement(comparison_key="H|eth_btc|730|540|180|X||")
        for m in (a, b):
            registry.record_result(
                reg, "H", registry.adoption_verdict(entry(), m, 0.05),
                "2026-09-01")
        self.assertEqual(registry.family_size(reg), 2)

    def test_an_unscored_result_never_enters_the_family(self):
        reg = self._reg()
        v = registry.adoption_verdict(entry(), measurement(folds=1), 0.05)
        registry.record_result(reg, "H", v, "2026-09-01")
        self.assertEqual(registry.family_size(reg), 0)

    def test_the_bar_tightens_as_the_family_grows(self):
        self.assertGreater(registry.bonferroni_bar(1),
                           registry.bonferroni_bar(20))

    def test_recording_the_result_updates_the_status(self):
        reg = self._reg()
        v = registry.adoption_verdict(entry(), measurement(prereg="POST"), 0.05)
        registry.record_result(reg, "H", v, "2026-09-01")
        self.assertEqual(reg["entries"][0]["status"], "CANDIDAT")

    def test_every_written_result_is_stamped_with_its_method(self):
        reg = self._reg()
        v = registry.adoption_verdict(entry(), measurement(), 0.05)
        registry.record_result(reg, "H", v, "2026-09-01")
        self.assertEqual(reg["entries"][0]["results"][-1]["method_version"],
                         registry.METHOD_VERSION)

    def test_recording_against_an_unknown_id_is_an_error(self):
        with self.assertRaises(KeyError):
            registry.record_result(
                self._reg(), "NOPE",
                registry.adoption_verdict(entry(), measurement(), 0.05),
                "2026-09-01")


class TestComparisonKey(unittest.TestCase):

    def test_key_separates_configurations_and_data_cutoffs(self):
        a = registry.comparison_key("H", "eth_btc", 365, 365, 180, "2026-08-31")
        b = registry.comparison_key("H", "eth_btc", 730, 365, 180, "2026-08-31")
        c = registry.comparison_key("H", "eth_btc", 365, 365, 180, "2026-12-31")
        d = registry.comparison_key("H", "alt_eth", 365, 365, 180, "2026-08-31")
        self.assertEqual(len({a, b, c, d}), 4)


class TestRegisteredHypotheses(unittest.TestCase):

    def test_ids_are_unique(self):
        ids = [h[0] for h in registry.HYPOTHESES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_direction_is_written_before_any_measurement(self):
        for h in registry.HYPOTHESES:
            self.assertIn(h[3], (1, -1), h[0])

    def test_the_sign_inversion_between_targets_is_recorded_as_a_prediction(self):
        """Established fact 4 is written down as opposite expected signs, so
        the file can be wrong about it later."""
        by_id = {h[0]: h for h in registry.HYPOTHESES}
        self.assertEqual(by_id["H01"][1], by_id["H08"][1])
        self.assertNotEqual(by_id["H01"][3], by_id["H08"][3])

    def test_the_control_is_registered_and_findable(self):
        """A control that only a rationale string identifies is a control
        nobody can find - and the report's calibration section points at it."""
        h = registry.by_hyp_id(registry.CONTROL_ID)
        self.assertIsNotNone(h)
        self.assertIn("controle", h[5])
        self.assertNotIn(h[2], registry.WITHDRAWN_TARGETS)


class TestOfflineLoading(unittest.TestCase):
    """Offline by construction, not because a gitignored file happens to be
    there."""

    def test_a_missing_cache_names_the_file_it_wanted(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError) as ctx:
                registry.load_fear_greed_offline(os.path.join(d, "fng.json"))
        self.assertIn("fng.json", str(ctx.exception))
        self.assertIn("JAMAIS", str(ctx.exception))

    @unittest.skipUnless(HAVE_FNG, NO_FNG)
    def test_build_inputs_succeeds_with_the_network_unplugged(self):
        def boom(*a, **k):
            raise AssertionError("appel reseau interdit")
        original = urllib.request.urlopen
        urllib.request.urlopen = boom
        try:
            signals, targets, data_end, ctx = registry.build_inputs()
        finally:
            urllib.request.urlopen = original
        self.assertIn("Fear & Greed", signals)
        self.assertTrue(signals["Fear & Greed"])
        self.assertIn("eth_btc", targets)


@unittest.skipUnless(HAVE_FNG, NO_FNG)
class TestMeasurementLayer(unittest.TestCase):
    """The real walk over the real files. Everything above this point would
    pass on fabricated dictionaries even if measure() returned nonsense."""

    @classmethod
    def setUpClass(cls):
        cls.signals, cls.targets, cls.data_end, cls.ctx = registry.build_inputs()

    def _series(self, signal, target):
        return registry.restrict(self.signals[signal], self.targets[target])

    def test_the_data_ends_where_the_report_says_it_does(self):
        self.assertEqual(self.data_end, "2026-08-31")

    def test_n_assets_is_the_universe_and_no_longer_the_basket(self):
        """The quantity changed meaning under the module and the module did not
        notice. dominance.json['n_assets'] was the BASKET while the basket was
        fixed (14 to 24 assets, which the previous report printed as "panier de
        14 a 24 actifs"); since build_rotations.py it is the whole universe.
        Printing the new number under the old sentence multiplies the declared
        basket by five with no line of code changing."""
        lo, hi, n = self.ctx["basket"]
        self.assertEqual((lo, hi), (71, 118))
        self.assertEqual(n, 2800)
        self.assertGreater(lo, 24)

    def test_the_eth_btc_target_is_not_the_ethbtc_price_series(self):
        d = self.ctx["divergence"]
        self.assertGreater(d["ratio_hi"] - d["ratio_lo"], 0.1)
        self.assertGreater(d["max_diff"], 1.0)

    def test_the_divergence_shows_up_in_folds_not_only_in_return_points(self):
        """Points of forward return read as negligible - a median of 0.21. The
        consequence is elsewhere: at an IDENTICAL configuration the two price
        series give different fold counts, and folds are what a verdict is
        built on."""
        rows = dict(self.ctx["reference_folds"])
        self.assertTrue(rows)
        self.assertTrue(any(not c["folds_match"] for c in rows.values()),
                        "aucune divergence de plis mesuree")
        c = rows["niveau ETH/BTC"]
        self.assertEqual((c["here_agree"], c["here_folds"]), (5, 5))
        self.assertEqual((c["there_agree"], c["there_folds"]), (4, 4))

    def test_the_fold_comparison_is_the_shared_one(self):
        """Two modules computing "how far are we from walkforward.py" from two
        independent pieces of arithmetic can disagree about the answer, and
        then the audit needs an audit."""
        import rotation_matrix
        c = rotation_matrix.reference_fold_comparison(
            1, 2, {"2026-01-01": 1.0}, {}, 365, 365, 180)
        self.assertEqual((c["here_agree"], c["here_folds"]), (1, 2))
        self.assertEqual(c["there_folds"], 0)
        self.assertFalse(c["folds_match"])

    def test_the_two_fear_and_greed_sources_agree_where_they_overlap(self):
        """The repository carries two F&G series and had never compared them.
        The cache is chosen for COVERAGE, and this says the values are not the
        reason - so the choice cannot be quietly reversed as a wash."""
        f = self.ctx["fng_sources"]
        self.assertGreater(f["n_cache"], f["n_series"])
        self.assertEqual(f["identical"], f["n_common"])
        self.assertAlmostEqual(f["max_diff"], 0.0)
        self.assertLess(f["cache_first"], f["series_first"])

    def test_walk_folds_reproduces_the_module_it_borrows_from(self):
        """The per-fold detail is a reimplementation of wf.walk's loop. If the
        two ever disagree the fault is here, and this is what says so."""
        for hid, sig, tgt, _, _, _ in registry.HYPOTHESES:
            s = self._series(sig, tgt)
            pairs, _ = registry.walk_folds(s, self.targets[tgt])
            good = registry.usable_folds(pairs)
            agree = sum(1 for a, b in good if a == b)
            self.assertEqual((agree, len(good)),
                             wf.walk(s, self.targets[tgt], registry.WINDOW,
                                     registry.TRAIN_DAYS, registry.TEST_DAYS),
                             hid)

    def test_restricting_to_the_target_universe_changes_no_real_walk(self):
        """The restriction exists for the NULL - it stops the shuffle drawing
        from a wider period than the signal's own. It must not move the real
        measurement, or it would be a second free parameter."""
        for sig in ("Fear & Greed", "dominance BTC"):
            raw, fwd = self.signals[sig], self.targets["eth_btc"]
            self.assertEqual(
                wf.walk(raw, fwd, registry.WINDOW, registry.TRAIN_DAYS,
                        registry.TEST_DAYS),
                wf.walk(registry.restrict(raw, fwd), fwd, registry.WINDOW,
                        registry.TRAIN_DAYS, registry.TEST_DAYS), sig)

    def test_the_restriction_removes_fear_and_greed_s_pre_target_years(self):
        raw = self.signals["Fear & Greed"]
        kept = registry.restrict(raw, self.targets["eth_btc"])
        before = sum(1 for d in raw if d < min(self.targets["eth_btc"]))
        self.assertEqual(before, 331)
        self.assertLess(len(kept), len(raw))

    def test_reproduced_walk_forward_numbers(self):
        """Pinned so that an edit to the walk, the percentile or the direction
        rule cannot pass silently. Fear & Greed is the one the adoption rule
        must keep rejecting."""
        expected = {("Fear & Greed", "eth_btc"): (1, 9),
                    ("niveau ETH/BTC", "eth_btc"): (5, 5),
                    ("dominance BTC", "eth_btc"): (3, 3),
                    ("dominance ETH", "eth_btc"): (1, 3)}
        for (sig, tgt), want in expected.items():
            self.assertEqual(
                wf.walk(self._series(sig, tgt), self.targets[tgt],
                        registry.WINDOW, registry.TRAIN_DAYS,
                        registry.TEST_DAYS), want, "%s -> %s" % (sig, tgt))

    def test_the_control_predicts_itself_better_than_any_real_signal(self):
        """The calibration the report is built on: a DEGENERATE predictor takes
        the top of the table, so a walk-forward agreement has to be read
        against it and not against 50%."""
        ctrl = registry.by_hyp_id(registry.CONTROL_ID)
        agree, folds = wf.walk(self._series(ctrl[1], ctrl[2]),
                               self.targets[ctrl[2]], registry.WINDOW,
                               registry.TRAIN_DAYS, registry.TEST_DAYS)
        self.assertEqual((agree, folds), (5, 5))
        for hid, sig, tgt, _, _, _ in registry.HYPOTHESES:
            if tgt != ctrl[2] or hid == registry.CONTROL_ID:
                continue
            a, f = wf.walk(self._series(sig, tgt), self.targets[tgt],
                           registry.WINDOW, registry.TRAIN_DAYS,
                           registry.TEST_DAYS)
            self.assertLessEqual((a / f) if f else 0.0, agree / folds, hid)

    def test_the_in_sample_direction_disagrees_with_the_out_of_sample_one(self):
        """The control again: the full-sample gradient says +1, the majority of
        test folds says -1. This is why criterion 2 reads the out-of-sample
        field, and it is measured rather than argued."""
        ctrl = registry.by_hyp_id(registry.CONTROL_ID)
        s = self._series(ctrl[1], ctrl[2])
        fwd = self.targets[ctrl[2]]
        pairs, _ = registry.walk_folds(s, fwd)
        oos, votes = registry.oos_direction(pairs)
        self.assertEqual(oos, -1)
        self.assertEqual(votes, (0, 5))
        self.assertEqual(registry.insample_direction(s, fwd), 1)

    def test_the_window_is_counted_in_observations_and_the_holes_are_measured(self):
        """365 POSITIONS in a sorted date list, not 365 calendar days. On a
        series with holes the window reaches further back than its label, so
        the holes are counted rather than assumed to be zero."""
        cal = registry.calendar_gaps(self._series("Fear & Greed", "eth_btc"))
        self.assertEqual(cal["missing"], 1)
        self.assertEqual(cal["span"], cal["n"] + cal["missing"])
        holed = registry.calendar_gaps(self._series("nvt", "eth_btc"))
        self.assertEqual(holed["missing"], 3)

    def test_measure_records_the_draws_it_actually_ran(self):
        """A short run, so the test stays fast; the fields it checks are the
        ones the persisted verdict is audited on."""
        e = registry.register(registry.new_registry("2026-09-01"), "H04",
                              "Fear & Greed", "eth_btc", 1, 0.70,
                              registry.TODAY, "test")
        m = registry.measure(e, self.signals["Fear & Greed"],
                             self.targets["eth_btc"], self.data_end,
                             shuffles=12)
        self.assertEqual((m["agree"], m["folds"]), (1, 9))
        self.assertEqual(m["shuffles"], 12)
        self.assertEqual(m["prereg"], "POST")
        self.assertEqual(set(m["nulls"]), set(registry.NULL_MODES))
        mel = m["nulls"]["melange"]
        self.assertEqual(mel["usable"] + mel["degenerate"], 12)
        # The shuffle cannot reach nine folds; that is the finding, not a bug.
        self.assertLess(mel["fold_max"], m["folds"])
        self.assertEqual(m["null_matched"], 0)
        self.assertFalse(m["null_comparable"])
        # No matched draw means no resolution at all, and the floor says 1.0
        # rather than borrowing the count of the draws it fell back on.
        self.assertAlmostEqual(m["floor"], 1.0)
        self.assertAlmostEqual(m["floor"],
                               registry.resolution_floor(9, mel["matched"]))

    def test_measure_copies_the_null_summary_it_reports(self):
        """The identity the whole rewrite turns on: the top-level fields and
        the summary they came from cannot disagree, because one is a copy of
        the other rather than a second derivation."""
        e = registry.register(registry.new_registry("2026-09-01"), "H03",
                              "niveau ETH/BTC", "eth_btc", 1, 0.70,
                              registry.TODAY, "test")
        m = registry.measure(e, self.signals["niveau ETH/BTC"],
                             self.targets["eth_btc"], self.data_end,
                             shuffles=12)
        mel = m["nulls"]["melange"]
        self.assertEqual(m["null_mean"], mel["ref_mean"])
        self.assertEqual(m["gap"], mel["gap"])
        self.assertEqual(m["null_mean_basis"], mel["ref_basis"])
        self.assertEqual(m["null_mean_n"], mel["ref_n"])
        self.assertEqual(m["null_comparable"], mel["comparable"])

    def test_measure_records_the_identity_of_what_it_walked(self):
        e = registry.register(registry.new_registry("2026-09-01"), "H03",
                              "niveau ETH/BTC", "eth_btc", 1, 0.70,
                              registry.TODAY, "test")
        m = registry.measure(e, self.signals["niveau ETH/BTC"],
                             self.targets["eth_btc"], self.data_end,
                             shuffles=0)
        self.assertEqual(
            m["signal_fingerprint"],
            registry.fingerprint(self._series("niveau ETH/BTC", "eth_btc")))
        self.assertIn(m["signal_fingerprint"], m["comparison_key"])

    def test_a_test_too_short_to_conclude_launches_no_shuffle(self):
        """Shuffling a walk that cannot conclude burns minutes for a number
        nobody is allowed to use. The skip stays visible as shuffles = 0."""
        e = registry.register(registry.new_registry("2026-09-01"), "H06",
                              "nvt", "eth_btc", 1, 0.70, registry.TODAY, "test")
        m = registry.measure(e, self.signals["nvt"], self.targets["eth_btc"],
                             self.data_end, shuffles=12)
        self.assertLess(m["folds"], registry.MIN_FOLDS)
        self.assertEqual(m["shuffles"], 0)
        self.assertEqual(m["nulls"], {})

    def test_a_withdrawn_target_launches_no_shuffle_either(self):
        """The same principle for a different reason: the verdict refuses it
        before reading any statistic, so drawing nulls would buy a number the
        rule is forbidden to look at. The real walk is still measured and kept -
        what was asked, and what came back, stays in the file."""
        e = registry.register(registry.new_registry("2026-09-01"), "H10",
                              "Fear & Greed", "alt_eth", 1, 0.70,
                              registry.TODAY, "test")
        m = registry.measure(e, self.signals["Fear & Greed"],
                             self.targets["alt_eth"], self.data_end,
                             shuffles=12)
        self.assertGreaterEqual(m["folds"], registry.MIN_FOLDS)
        self.assertEqual(m["shuffles"], 0)
        self.assertEqual(m["nulls"], {})


class TestShiftNullNeverDrawsTheRealSeries(unittest.TestCase):
    """rng.randrange(len) can return 0, and a rotation by 0 hands back the REAL
    series as an observation of the null. Over 250 draws that happened about
    nine times in ten. Harmless while the shift is never a criterion, but an
    undeclared identity draw inside a null is not something this module gets to
    leave unsaid."""

    def test_the_offset_range_excludes_zero(self):
        import random
        rng = random.Random(1)
        n = 50
        for _ in range(2000):
            self.assertGreater(rng.randrange(1, max(n, 2)), 0)

    def test_a_nonzero_offset_always_moves_the_series(self):
        import rotation_matrix
        vals = list(range(10))
        for k in range(1, len(vals)):
            self.assertNotEqual(rotation_matrix.rotate(vals, k), vals)
        self.assertEqual(rotation_matrix.rotate(vals, 0), vals)


@unittest.skipUnless(HAVE_REGISTRY, NO_REGISTRY)
class TestPersistedRegistry(unittest.TestCase):
    """What is on disk has to be auditable without re-running anything."""

    @classmethod
    def setUpClass(cls):
        cls.reg = registry.load()
        cls.last = {e["id"]: e["results"][-1] for e in cls.reg["entries"]
                    if e["results"]}

    def test_every_registered_hypothesis_has_a_result(self):
        for hid, _, _, _, _, _ in registry.HYPOTHESES:
            self.assertIn(hid, self.last, hid)

    def test_a_skipped_null_is_recorded_as_zero_not_as_a_missing_field(self):
        self.assertEqual(self.last["H06"]["shuffles"], 0)
        self.assertEqual(self.last["H06"]["verdict"], "NON_TESTABLE")

    def test_a_scored_result_persists_the_draws_that_ran(self):
        h04 = self.last["H04"]
        self.assertEqual(h04["shuffles"], registry.SHUFFLES)
        self.assertEqual(h04["null_matched"], 0)
        self.assertGreater(h04["null_degenerate"], 0)
        self.assertLess(h04["null_usable"], h04["shuffles"])

    def test_every_result_persists_the_configuration_it_was_measured_under(self):
        for hid, r in self.last.items():
            for k in ("window", "train_days", "test_days", "horizon",
                      "shuffles", "data_end"):
                self.assertIn(k, r, "%s.%s" % (hid, k))
            self.assertEqual(r["method_version"], registry.METHOD_VERSION, hid)

    def test_every_result_persists_the_identity_of_its_data(self):
        """Because the data was regenerated under this module once already,
        and nothing in the file could have told."""
        for hid, r in self.last.items():
            self.assertTrue(r.get("signal_fingerprint"), hid)
            self.assertTrue(r.get("target_fingerprint"), hid)
            self.assertIn(r["signal_fingerprint"], r["comparison_key"], hid)

    def test_fear_and_greed_is_rejected_on_disk_too(self):
        """The verdict the whole module is checked against, read back from the
        artifact rather than from memory."""
        self.assertEqual(self.last["H04"]["verdict"], "REJETE")
        self.assertEqual((self.last["H04"]["agree"], self.last["H04"]["folds"]),
                         (1, 9))

    def test_every_withdrawn_target_is_refused_on_disk(self):
        for hid, _, tgt, _, _, _ in registry.HYPOTHESES:
            if tgt in registry.WITHDRAWN_TARGETS:
                self.assertEqual(self.last[hid]["verdict"], "NON_TESTABLE", hid)
                self.assertFalse(self.last[hid].get("scored"), hid)

    def test_nothing_is_adopted_and_nothing_is_a_candidate(self):
        for hid, r in self.last.items():
            self.assertNotIn(r["verdict"], ("ADOPTE", "CANDIDAT"), hid)

    def test_a_signal_rejected_here_is_not_left_in_the_live_tier_a_gate(self):
        """The only test in this file that couples two modules, and the
        coupling is the point: this registry's whole output is verdicts, and a
        verdict the gate ignores has changed nothing.

        Fear & Greed is REJETE here on 1 fold in 9 and sits in "track"
        downstream, so the chain currently holds. If someone re-promotes it
        without new evidence, this is what says so - which is a better place
        to find out than a live allocation.
        """
        tiers = registry.downstream_tiers()
        if tiers is None:
            self.skipTest("dimensions.py illisible")
        for hid, sig, _, _, _, _ in registry.HYPOTHESES:
            if sig not in registry.GATE_KEYS:
                continue
            if self.last[hid]["verdict"] == "REJETE":
                self.assertNotEqual(tiers[sig], "A",
                                    "%s (%s) rejete ici et Tier A dans la "
                                    "porte" % (hid, sig))

    def test_the_family_counter_holds_every_scored_comparison(self):
        """Cumulative across runs, so this is a floor rather than an equality:
        comparisons scored by earlier runs stay counted, which is the point."""
        scored = [r for r in self.last.values() if r.get("scored")]
        self.assertGreaterEqual(len(self.reg["comparisons"]), len(scored))
        for r in scored:
            self.assertIn(r["comparison_key"], self.reg["comparisons"])


@unittest.skipUnless(HAVE_REGISTRY and HAVE_REPORT, NO_REPORT)
class TestReportMatchesThePersistedRegistry(unittest.TestCase):
    """The two artefacts of one run, compared line by line.

    This is the test for the defect that caused the rewrite. render_report()
    computed the null mean as `mean_matched if matched else mean_all` while
    measure() computed it as `mean_matched if matched >= MIN_MATCHED_NULLS else
    mean_all`. The table therefore printed 62% where registry.json held 47.6%
    for the same cell, and 71% against 54.7% for another. Criterion 4 turns on
    15 points, and nothing told the reader which of the two the rule had read.
    """

    @classmethod
    def setUpClass(cls):
        with open(registry.REPORT_PATH, encoding="utf-8") as f:
            cls.text = f.read()
        reg = registry.load()
        cls.last = {e["id"]: e["results"][-1] for e in reg["entries"]
                    if e["results"]}
        cls.rows = [m.groups() for m in
                    (NULL_ROW.match(l) for l in cls.text.splitlines()) if m]

    def test_the_table_has_rows_to_check(self):
        self.assertTrue(self.rows, "aucune ligne de nulle rendue")

    def test_every_printed_gap_is_the_one_stored_for_that_cell(self):
        for (hid, _, mode, _, _, _, _, _, _, _, mean, gap) in self.rows:
            stored = self.last[hid]["nulls"][mode]
            if stored["gap"] is None:
                self.assertEqual(gap, "-", "%s/%s" % (hid, mode))
                continue
            self.assertEqual(gap, "%+.0f" % stored["gap"],
                             "%s/%s: rapport %s contre json %r"
                             % (hid, mode, gap, stored["gap"]))
            self.assertEqual(mean, "%.0f%%" % stored["ref_mean"],
                             "%s/%s" % (hid, mode))

    def test_the_melange_row_is_the_field_criterion_four_reads(self):
        """The top-level gap is what the adoption rule reads and the melange
        row is what the reader sees. They have to be one number."""
        checked = 0
        for (hid, _, mode, _, _, _, _, _, _, _, _, gap) in self.rows:
            if mode != "melange":
                continue
            checked += 1
            top = self.last[hid]["gap"]
            if top is None:
                self.assertEqual(gap, "-", hid)
            else:
                self.assertEqual(gap, "%+.0f" % top, hid)
        self.assertTrue(checked, "aucune ligne melange rendue")

    def test_no_mean_is_printed_from_too_few_draws(self):
        """A mean of one draw is not a mean. The old table printed
        "moyenne 71%" from a single matched draw, with "apparies 1" in the
        next column and nothing connecting the two."""
        for (hid, _, mode, _, _, _, _, _, _, basis, mean, gap) in self.rows:
            n = int(re.search(r"(\d+)", basis).group(1))
            if mean == "-":
                self.assertEqual(gap, "-", "%s/%s" % (hid, mode))
                continue
            self.assertGreaterEqual(
                n, registry.MIN_MATCHED_NULLS,
                "%s/%s: moyenne rendue sur %d tirages" % (hid, mode, n))

    def test_the_basis_column_says_which_subset_each_mean_rests_on(self):
        for (hid, _, mode, _, _, _, _, _, _, basis, _, _) in self.rows:
            stored = self.last[hid]["nulls"][mode]
            if stored["ref_mean"] is None:
                continue
            self.assertTrue(basis.startswith(stored["ref_basis"]),
                            "%s/%s: %s" % (hid, mode, basis))
            self.assertIn(str(stored["ref_n"]), basis)

    def test_the_p_column_declares_its_own_basis_too(self):
        """p and the mean can rest on different subsets, so one basis for both
        would be the same conflation one level down."""
        for hid, r in self.last.items():
            if not r.get("p_basis"):
                continue
            self.assertIn("%s(%d)" % (r["p_basis"], r["p_n"]), self.text, hid)


class TestReport(unittest.TestCase):
    """The report is rendered from data it is handed, so the parts that carry
    a bias declaration can be tested rather than eyeballed."""

    @classmethod
    def setUpClass(cls):
        cls.text = cls._render()

    @staticmethod
    def _render(nulls_for=None):
        reg = registry.new_registry("2026-09-01")
        measurements, verdicts = {}, {}
        for hid, sig, tgt, d, thr, why in registry.HYPOTHESES:
            e = registry.register(reg, hid, sig, tgt, d, thr,
                                  registry.TODAY, why)
            m = measurement(comparison_key=registry.comparison_key(
                hid, tgt, 365, 365, 180, "2026-08-31", "aaa", "bbb"),
                data_end="2026-08-31", prereg="POST")
            if nulls_for and hid in nulls_for:
                m["nulls"] = {mode: nulls_for[hid]
                              for mode in registry.NULL_MODES}
            measurements[hid] = m
            verdicts[hid] = registry.adoption_verdict(e, m, 0.0083)
            registry.record_result(reg, hid, verdicts[hid], registry.TODAY)
        ctx = {"basket": (71, 118, 2800),
               "absent_majors": (registry.CYCLE_MAJORS, (), 45),
               "divergence": {"n": 2709, "max_diff": 1.63, "mean_diff": 0.31,
                              "median_diff": 0.21, "ratio_lo": 5.965,
                              "ratio_hi": 6.293},
               "fng_sources": {"n_cache": 3130, "n_series": 1456,
                               "n_common": 1456, "identical": 1456,
                               "max_diff": 0.0, "median_diff": 0.0,
                               "cache_first": "2018-02-01",
                               "series_first": "2022-08-31"},
               "reference_folds": [("Fear & Greed",
                                    {"here_agree": 1, "here_folds": 9,
                                     "there_agree": 1, "there_folds": 9,
                                     "folds_match": True,
                                     "agree_match": True})],
               "gate_tiers": {label: "track"
                              for label in registry.GATE_KEYS},
               "runtime_s": 65.0, "total_draws": 1000}
        return registry.render_report(measurements, verdicts, reg, 0.0083,
                                      11, "2026-08-31", ctx).text()

    def _rows(self, hid):
        return [l for l in self.text.splitlines() if l.strip().startswith(hid)]

    def test_every_alt_row_carries_the_basket_mark(self):
        """A caveat parked in a trailing block survives exactly until someone
        quotes one line out of the table."""
        for hid, _, tgt, _, _, _ in registry.HYPOTHESES:
            rows = self._rows(hid)
            self.assertTrue(rows, hid)
            for row in rows:
                if tgt.startswith("alt"):
                    self.assertIn(registry.ALT_MARK, row, row)

    def test_the_caveat_is_spelled_out_next_to_the_alt_verdicts(self):
        alt_ids = [h[0] for h in registry.HYPOTHESES if h[2].startswith("alt")]
        for hid in alt_ids:
            verdict_rows = [r for r in self._rows(hid)
                            if any(v in r for v in registry.VERDICTS)]
            self.assertTrue(verdict_rows, hid)
            self.assertTrue(
                any(registry.ALT_BASKET_CAVEAT in r for r in verdict_rows), hid)

    def test_the_caveat_string_is_the_shared_one(self):
        """Restated in the author's own words it drifts, and a drifted caveat
        is how a declared bias quietly weakens."""
        import rotation_matrix
        self.assertEqual(registry.ALT_BASKET_CAVEAT,
                         rotation_matrix.ALT_BASKET_CAVEAT)
        self.assertIn(registry.ALT_BASKET_CAVEAT, self.text)

    def test_the_report_says_the_shared_mark_understates_the_measurement(self):
        """The shared string names three assets; this run measured twelve
        absent. The weaker one must not be left standing alone."""
        self.assertIn("nomme trois actifs", self.text)
        for asset in ("apt", "arb", "ton"):
            self.assertIn(asset, self.text)

    def test_the_universe_size_is_not_printed_as_a_basket_size(self):
        self.assertIn("UNIVERS de 71 a 118", self.text)
        self.assertNotIn("panier de 71", self.text)
        self.assertNotIn("25 actifs", self.text)

    def test_the_header_warns_the_eth_btc_target_is_the_rebased_index(self):
        self.assertIn("rotations.json", self.text)
        self.assertIn("ethbtc.json", self.text)
        self.assertIn("1.63", self.text)

    def test_the_header_declares_the_divergence_in_folds_not_only_in_points(self):
        """Points of forward return read as negligible; fold counts do not."""
        self.assertIn("nombre de PLIS", self.text)
        self.assertIn("wf.walk", self.text)
        self.assertIn("reference_fold_comparison", self.text)

    def test_the_header_declares_what_the_run_cost(self):
        self.assertIn("65 s", self.text)
        self.assertIn("1000 tirages", self.text)

    def test_the_window_is_labelled_in_observations_not_days(self):
        """The configuration line must not say "365j". The body may still
        QUOTE the old label while explaining what was wrong with it, so the
        assertion is scoped to the header rather than to the whole text - a
        blanket ban would forbid the report from naming the defect it fixed."""
        header = self.text.split("QUELLES SERIES")[0]
        self.assertIn("OBSERVATIONS", header)
        self.assertIn("POSITIONS", header)
        self.assertNotIn("percentile glissant %dj" % registry.WINDOW, header)

    def test_the_two_fear_and_greed_sources_are_reconciled(self):
        self.assertIn("DEUX series F&G", self.text)
        self.assertIn("3130", self.text)
        self.assertIn("series.json['fear_greed']", self.text)

    def test_the_withdrawn_targets_get_their_own_section(self):
        self.assertIn("CIBLES RETIREES", self.text)
        self.assertIn("aucune statistique ne le rouvre", self.text)

    def test_the_control_section_reads_agreement_against_the_control(self):
        """The inference this run could publish and the previous one did not."""
        self.assertIn("CONTRE QUOI LIRE UN ACCORD WALK-FORWARD", self.text)
        self.assertIn(registry.CONTROL_ID, self.text)
        self.assertIn("DEGENERE", self.text)
        self.assertIn("pas contre", self.text)

    def test_the_single_regime_bias_points_at_the_control_that_measures_it(self):
        """The bias was declared in the trailing block and demonstrated by a
        measurement nobody connected to it."""
        tail = self.text.split("BIAIS A DECLARER")[-1]
        self.assertIn("tendance baissiere", tail)
        self.assertIn(registry.CONTROL_ID, tail)

    def test_the_floor_section_states_the_real_fallback_trigger(self):
        """The old text said a zero matched count triggered the fallback. The
        trigger is MIN_MATCHED_NULLS, and rows showing 14, 12 or 11 matched
        draws were printing a p computed over hundreds of others."""
        floor = self.text.split("PLANCHER DE RESOLUTION")[-1]
        self.assertIn("sous %d apparies" % registry.MIN_MATCHED_NULLS, floor)
        self.assertIn("base du p", floor)

    def test_a_mean_from_too_few_draws_is_refused_in_the_rendered_table(self):
        """Rendered on a null that produced a single usable draw: no mean, no
        gap, and the cell says how few there were."""
        thin = {"draws": 250, "usable": 1, "degenerate": 249, "matched": 1,
                "fold_min": 0, "fold_max": 7, "fold_median": 2,
                "mean_all": 71.0, "mean_matched": 71.0, "rates_matched": [],
                "rates_all": [], "comparable": False, "ref_basis": "tous",
                "ref_n": 1, "ref_mean": None, "gap": None}
        text = self._render(nulls_for={"H03": thin})
        rows = [m.groups() for m in
                (NULL_ROW.match(l) for l in text.splitlines()) if m]
        thin_rows = [r for r in rows if r[0] == "H03"]
        self.assertTrue(thin_rows)
        for r in thin_rows:
            self.assertIn("insuff.", r[9])
            self.assertEqual(r[10], "-")
            self.assertEqual(r[11], "-")

    def test_the_report_shows_what_the_gate_did_with_its_verdicts(self):
        """A registry whose verdicts nobody reads is a diary."""
        self.assertIn("CE QUE LA PORTE EN A FAIT", self.text)
        for label in registry.GATE_KEYS:
            self.assertIn(label, self.text)

    def test_the_report_states_it_governs_nothing(self):
        self.assertIn("NE GOUVERNE RIEN", self.text)

    def test_the_report_declares_every_hypothesis_post_hoc(self):
        self.assertIn("POST-HOC", self.text)
        self.assertNotIn("ADOPTE", self.text.split("REGLE D ADOPTION")[-1]
                         .split("VERDICTS")[-1])

    def test_no_percent_sign_survives_unformatted(self):
        """A line built with the % operator needs %%, one built without needs
        %. Getting it backwards either raises or prints "50%%" at a reader."""
        self.assertNotIn("%%", self.text)


class TestSourceClaims(unittest.TestCase):
    """One grep, guarding a number rather than a behaviour.

    "25 actifs" was written in band_study.py's docstring, copied into
    registry.py's report, and printed as a measurement for weeks.
    analysis/dominance.json has never contained it. The cheapest guard against
    a fabricated figure travelling between modules a third time is to refuse
    the string itself.
    """

    def _source(self, name):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "scripts", name)
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_no_module_claims_a_twenty_five_asset_basket(self):
        for name in ("band_study.py", "registry.py"):
            src = self._source(name)
            self.assertNotIn("25 actifs", src, name)
            self.assertNotIn("25-asset", src, name)

    def test_the_basket_size_is_read_from_its_generator_not_restated(self):
        """TOP_N lives in build_rotations.py, which decides it. Restating it
        here is how band_study.py came to carry "25" for months."""
        self.assertIn("br.TOP_N", self._source("registry.py"))


if __name__ == "__main__":
    unittest.main()
