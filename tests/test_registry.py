#!/usr/bin/env python3
"""
Tests for the pre-registration registry. No network, no clock.

Every date, threshold and file path is injected. The registry's whole job is to
refuse things, so most of these tests assert a refusal: that a locked field
cannot be rewritten, that a post-hoc result cannot be adopted, that a test which
could never have concluded is not reported as a near miss.

Four groups are load-bearing beyond the code they cover:

  TestMeasurementLayer runs the real walk over the real JSONs and pins the
  numbers this run reproduced - H04 = 1/9, H03 = 5/5, H11 = 4/5, H10 = 3/7, and
  a data end of 2026-08-31. Everything else in this file could pass on
  hand-written dictionaries while measure() returned nonsense; this is the group
  that would notice.

  TestPersistedRegistry reads analysis/registry.json and checks that the inputs
  of each verdict are IN the file - the realised shuffle count above all. A
  conclusion whose inputs were not persisted cannot be audited later, which
  defeats the point of keeping a registry at all.

  TestOfflineLoading patches urlopen to raise and asserts the module still
  builds its inputs. Being offline because a cache file happens to exist is not
  the same property as being offline by construction.

  TestReport asserts the alt-basket caveat is on the alt ROWS, not only in a
  trailing block. A bias that survives quotation out of context is a control; a
  bias that does not is decoration.

Run: python -m unittest discover -s tests -v
"""

import json
import os
import shutil
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
NO_FNG = "cache F&G absent (analysis/.cache est gitignore)"
NO_REGISTRY = "analysis/registry.json absent - lancer scripts/registry.py"


def entry(direction=1, threshold=0.70, registered_on="2026-01-01"):
    reg = registry.new_registry("2026-01-01")
    return registry.register(reg, "H", "signal", "eth_btc", direction,
                             threshold, registered_on, "test")


def measurement(**kw):
    """A measurement that passes every statistical criterion by default.

    Tests then break exactly one field, so a failure names its own cause.
    """
    m = {"folds": 10, "agree": 10, "agreement": 1.0, "attempts": 12,
         "null_mean": 50.0, "gap": 50.0, "p": 0.004,
         "floor": registry.resolution_floor(10, 200),
         "direction": 1, "dir_votes": [10, 0], "direction_insample": 1,
         "prereg": "PRE", "data_end": "2027-06-01",
         "shuffles": 250, "null_usable": 240, "null_degenerate": 10,
         "null_matched": 200, "null_comparable": True,
         "window": 365, "train_days": 365, "test_days": 180, "horizon": 90,
         "signal_days": 2800, "signal_days_in_target": 2710,
         "outside_target_days": 90, "before_target_days": 0,
         "comparison_key": "H|eth_btc|365|365|180|2027-06-01",
         "nulls": {}}
    m.update(kw)
    return m


class TestRegistryFile(unittest.TestCase):
    """The file's shape is a commitment, not an implementation detail."""

    def test_registry_governs_nothing(self):
        self.assertIn("rien", registry.new_registry("2026-01-01")["governs"])

    def test_schema_version_is_stamped(self):
        reg = registry.new_registry("2026-01-01")
        self.assertEqual(reg["schema_version"], registry.SCHEMA_VERSION)

    def test_registration_stores_the_expected_direction(self):
        e = entry(direction=-1)
        self.assertEqual(e["expected_direction"], -1)
        self.assertEqual(e["status"], "enregistree")
        self.assertEqual(e["results"], [])

    def test_direction_must_be_plus_or_minus_one(self):
        reg = registry.new_registry("2026-01-01")
        for bad in (0, 2, None, "up"):
            with self.assertRaises(ValueError):
                registry.register(reg, "H", "s", "eth_btc", bad, 0.7,
                                  "2026-01-01", "why")

    def test_threshold_must_be_a_fraction(self):
        reg = registry.new_registry("2026-01-01")
        for bad in (0.0, -0.5, 1.5, 70):
            with self.assertRaises(ValueError):
                registry.register(reg, "H", "s", "eth_btc", 1, bad,
                                  "2026-01-01", "why")

    def test_identical_reregistration_is_idempotent(self):
        reg = registry.new_registry("2026-01-01")
        a = registry.register(reg, "H", "s", "eth_btc", 1, 0.7, "2026-01-01", "w")
        b = registry.register(reg, "H", "s", "eth_btc", 1, 0.7, "2026-01-01", "w")
        self.assertIs(a, b)
        self.assertEqual(len(reg["entries"]), 1)

    def test_expected_direction_cannot_be_rewritten(self):
        """The single property that makes the file worth keeping."""
        reg = registry.new_registry("2026-01-01")
        registry.register(reg, "H", "s", "eth_btc", 1, 0.7, "2026-01-01", "w")
        with self.assertRaises(ValueError):
            registry.register(reg, "H", "s", "eth_btc", -1, 0.7,
                              "2026-01-01", "w")
        self.assertEqual(registry.find(reg, "H")["expected_direction"], 1)

    def test_target_and_threshold_are_locked_too(self):
        """Swapping the target or relaxing the threshold rewrites the
        prediction just as effectively as flipping its sign."""
        reg = registry.new_registry("2026-01-01")
        registry.register(reg, "H", "s", "eth_btc", 1, 0.7, "2026-01-01", "w")
        with self.assertRaises(ValueError):
            registry.register(reg, "H", "s", "alt_eth", 1, 0.7,
                              "2026-01-01", "w")
        with self.assertRaises(ValueError):
            registry.register(reg, "H", "s", "eth_btc", 1, 0.55,
                              "2026-01-01", "w")

    def test_rationale_is_not_locked(self):
        """Prose about WHY may be improved; the prediction may not."""
        reg = registry.new_registry("2026-01-01")
        registry.register(reg, "H", "s", "eth_btc", 1, 0.7, "2026-01-01", "w")
        registry.register(reg, "H", "s", "eth_btc", 1, 0.7, "2026-01-01",
                          "meilleure explication")

    def test_save_and_load_round_trip(self):
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, "sub", "registry.json")
            reg = registry.new_registry("2026-01-01")
            registry.register(reg, "H", "s", "eth_btc", -1, 0.8,
                              "2026-01-01", "w")
            registry.save(reg, path)
            back = registry.load(path)
            self.assertEqual(back["entries"][0]["expected_direction"], -1)
            with open(path, encoding="utf-8") as f:
                json.load(f)   # valid JSON on disk, not just in memory
        finally:
            shutil.rmtree(tmp)

    def test_load_missing_file_returns_none(self):
        tmp = tempfile.mkdtemp()
        try:
            self.assertIsNone(registry.load(os.path.join(tmp, "absent.json")))
        finally:
            shutil.rmtree(tmp)

    def test_migration_moves_the_stamp_and_nothing_else(self):
        """Old results must keep looking old. Rewriting them into the new
        shape would make them look as though they had been measured the new
        way, which is the one thing a registry may never do to its history."""
        old = {"schema_version": 1, "created_on": "2026-01-01",
               "governs": "rien", "entries": [{"id": "H", "results": [{"p": 1}]}],
               "comparisons": ["k"]}
        migrated = registry.migrate(old)
        self.assertEqual(migrated["schema_version"], registry.SCHEMA_VERSION)
        self.assertEqual(migrated["entries"][0]["results"], [{"p": 1}])
        self.assertNotIn("method_version", migrated["entries"][0]["results"][0])


class TestPreregistrationStatus(unittest.TestCase):
    """PRE is computed from dates, never declared by the author."""

    def test_unseen_window_is_one_test_fold_plus_one_horizon(self):
        self.assertEqual(registry.MIN_UNSEEN_DAYS,
                         registry.TEST_DAYS + registry.HORIZON)

    def test_registered_after_the_data_ends_is_post_hoc(self):
        self.assertEqual(
            registry.preregistration_status("2026-09-01", "2026-08-31"), "POST")

    def test_registered_one_day_early_is_still_post_hoc(self):
        """A timestamp is not a commitment: without a full unseen fold the
        author could have seen essentially all of the test data."""
        self.assertEqual(
            registry.preregistration_status("2026-08-30", "2026-08-31"), "POST")

    def test_a_full_unseen_fold_earns_pre(self):
        self.assertEqual(
            registry.preregistration_status("2026-09-01", "2027-05-29"), "PRE")

    def test_boundary_is_inclusive(self):
        self.assertEqual(
            registry.preregistration_status("2026-01-01", "2026-01-11",
                                            min_unseen=10), "PRE")
        self.assertEqual(
            registry.preregistration_status("2026-01-01", "2026-01-10",
                                            min_unseen=10), "POST")

    def test_every_hypothesis_registered_today_is_post_hoc(self):
        """Today's results are all post-hoc and the module must say so."""
        for hid, _, _, _, _, _ in registry.HYPOTHESES:
            self.assertEqual(
                registry.preregistration_status(registry.TODAY, "2026-08-31"),
                "POST", hid)


class TestStatistics(unittest.TestCase):

    def test_bonferroni_divides_alpha_by_the_count(self):
        self.assertAlmostEqual(registry.bonferroni_bar(1), 0.05)
        self.assertAlmostEqual(registry.bonferroni_bar(10), 0.005)

    def test_bonferroni_survives_an_empty_family(self):
        self.assertAlmostEqual(registry.bonferroni_bar(0), 0.05)

    def test_permutation_p_can_never_be_zero(self):
        """250 draws cannot establish impossibility, so the +1 stays."""
        self.assertGreater(registry.permutation_p(100.0, [50.0] * 250), 0.0)
        self.assertAlmostEqual(registry.permutation_p(100.0, [50.0] * 250),
                               1.0 / 251)

    def test_permutation_p_counts_ties_against_the_signal(self):
        p_tie = registry.permutation_p(60.0, [60.0, 10.0, 10.0])
        p_strict = registry.permutation_p(60.0, [59.9, 10.0, 10.0])
        self.assertGreater(p_tie, p_strict)

    def test_permutation_p_without_a_null_is_uninformative(self):
        self.assertEqual(registry.permutation_p(100.0, []), 1.0)

    def test_resolution_floor_is_the_worse_of_folds_and_draws(self):
        self.assertAlmostEqual(registry.resolution_floor(4, 250), 0.0625)
        self.assertAlmostEqual(registry.resolution_floor(20, 250), 1.0 / 251)

    def test_resolution_floor_reads_the_draws_that_actually_ran(self):
        """The floor decides SOUS_RESOLU against REJETE. Feeding it the number
        of draws REQUESTED rather than the number that produced a comparable
        test advertises a resolution the run never had."""
        self.assertAlmostEqual(registry.resolution_floor(20, 217), 1.0 / 218)
        self.assertNotAlmostEqual(registry.resolution_floor(20, 217),
                                  registry.resolution_floor(20, 250))

    def test_four_perfect_folds_cannot_reach_alpha(self):
        """The arithmetic that makes SOUS_RESOLU a distinct verdict."""
        self.assertGreater(registry.resolution_floor(4, 10000),
                           registry.FAMILY_ALPHA)

    def test_entry_threshold_can_tighten_but_never_loosen(self):
        self.assertAlmostEqual(registry.effective_threshold(0.90), 0.90)
        self.assertAlmostEqual(registry.effective_threshold(0.30),
                               registry.MIN_AGREEMENT)


class TestAdoptionRule(unittest.TestCase):

    def _verdict(self, m, e=None, bar=0.05):
        return registry.adoption_verdict(e or entry(), m, bar)["verdict"]

    def test_fear_greed_measured_today_is_rejected(self):
        """1 fold out of 9 against a shuffle near 50%. If this ever passes, the
        rule is wrong - which is the entire reason this test exists. The
        numbers here are the ones TestMeasurementLayer reproduces from disk."""
        m = measurement(folds=9, agree=1, agreement=1 / 9.0, null_mean=46.0,
                        gap=-35.0, p=0.69,
                        floor=registry.resolution_floor(9, 0),
                        direction=1, dir_votes=[6, 3],
                        null_matched=0, null_comparable=False)
        v = registry.adoption_verdict(entry(), m, 0.05)
        self.assertEqual(v["verdict"], "REJETE")
        self.assertTrue(any("accord" in r for r in v["reasons"]))

    def test_a_flawless_post_hoc_result_is_only_a_candidate(self):
        self.assertEqual(self._verdict(measurement(prereg="POST")), "CANDIDAT")

    def test_the_same_result_pre_registered_is_adopted(self):
        self.assertEqual(self._verdict(measurement(prereg="PRE")), "ADOPTE")

    def test_nothing_post_hoc_is_ever_adopted(self):
        """The ceiling that makes today's analyses unable to promote anything.
        Swept across every statistical shape that would otherwise pass."""
        for p in (0.0001, 0.001, 0.004):
            for folds in (10, 40):
                m = measurement(prereg="POST", p=p, folds=folds, agree=folds,
                                floor=registry.resolution_floor(folds, 200))
                self.assertNotEqual(self._verdict(m), "ADOPTE")

    def test_direction_opposite_to_the_registered_one_is_fatal(self):
        v = registry.adoption_verdict(entry(direction=1),
                                      measurement(direction=-1,
                                                  dir_votes=[2, 8]), 0.05)
        self.assertEqual(v["verdict"], "REJETE")
        self.assertTrue(any("direction" in r for r in v["reasons"]))

    def test_the_rejection_reason_carries_the_vote_split(self):
        """A direction is a majority of fold-test signs, not a measurement with
        an error bar. Printing 8-2 next to it stops a thin majority reading
        like a unanimous one."""
        v = registry.adoption_verdict(entry(direction=1),
                                      measurement(direction=-1,
                                                  dir_votes=[4, 5]), 0.05)
        self.assertTrue(any("4 plis +1, 5 plis -1" in r for r in v["reasons"]))

    def test_an_unidentifiable_direction_does_not_confirm_anything(self):
        self.assertEqual(self._verdict(measurement(direction=None,
                                                   dir_votes=[3, 3])), "REJETE")

    def test_the_direction_criterion_reads_the_out_of_sample_field(self):
        """Criterion 2 must never fall back on the full-sample gradient: that
        number has seen every test fold. Here the in-sample direction agrees
        with the registered one and the out-of-sample direction does not, and
        the verdict has to follow the out-of-sample one."""
        v = registry.adoption_verdict(
            entry(direction=1),
            measurement(direction=-1, dir_votes=[1, 9], direction_insample=1),
            0.05)
        self.assertEqual(v["verdict"], "REJETE")

    def test_agreement_below_the_registered_threshold_is_rejected(self):
        e = entry(threshold=0.90)
        self.assertEqual(self._verdict(measurement(agreement=0.80), e),
                         "REJETE")
        self.assertEqual(self._verdict(measurement(agreement=0.95), e),
                         "ADOPTE")

    def test_a_lax_entry_threshold_cannot_undercut_the_floor(self):
        e = entry(threshold=0.30)
        self.assertEqual(self._verdict(measurement(agreement=0.50), e),
                         "REJETE")

    def test_beating_the_shuffle_by_too_little_is_rejected(self):
        self.assertEqual(self._verdict(measurement(gap=10.0)), "REJETE")

    def test_a_thin_gap_cannot_reject_when_the_null_is_not_comparable(self):
        """The gap is measured against a null whose draws produced a different
        number of folds. Rejecting on it would be this module committing the
        error it was written to audit, so the verdict says undecidable."""
        m = measurement(gap=2.0, null_matched=3, null_comparable=False)
        v = registry.adoption_verdict(entry(), m, 0.05)
        self.assertEqual(v["verdict"], "SOUS_RESOLU")
        self.assertFalse(any("ecart au melange" in r for r in v["reasons"]))

    def test_an_incomparable_null_is_undecidable_even_with_a_tiny_p(self):
        m = measurement(p=0.0001, null_matched=0, null_comparable=False)
        v = registry.adoption_verdict(entry(), m, 0.05)
        self.assertEqual(v["verdict"], "SOUS_RESOLU")
        self.assertTrue(any("atteignent les 10 plis reels" in r
                            for r in v["reasons"]))

    def test_a_failure_on_the_substance_still_outranks_undecidability(self):
        """An 11% agreement rate is a refusal regardless of the null's shape.
        Order matters here: were it reversed, Fear & Greed would come out
        SOUS_RESOLU and the rule would have lost its only proven catch."""
        m = measurement(agreement=0.11, agree=1, folds=9,
                        null_matched=0, null_comparable=False)
        self.assertEqual(self._verdict(m), "REJETE")

    def test_too_few_folds_is_not_a_failure_but_a_non_test(self):
        v = registry.adoption_verdict(
            entry(), measurement(folds=3, agree=3), 0.05)
        self.assertEqual(v["verdict"], "NON_TESTABLE")
        self.assertFalse(v["scored"])

    def test_an_undecidable_test_is_not_reported_as_a_near_miss(self):
        """5 perfect folds: floor 0.031, bar 0.008. Nothing failed; nothing
        could have succeeded either."""
        m = measurement(folds=5, agree=5, p=0.22,
                        floor=registry.resolution_floor(5, 200))
        self.assertEqual(self._verdict(m, bar=0.0083), "SOUS_RESOLU")

    def test_a_test_with_the_resolution_to_conclude_is_plainly_rejected(self):
        m = measurement(folds=40, agree=40, p=0.02,
                        floor=registry.resolution_floor(40, 200))
        self.assertEqual(self._verdict(m, bar=0.0083), "REJETE")

    def test_every_failed_criterion_is_reported_not_just_the_first(self):
        m = measurement(agreement=0.10, gap=-40.0, direction=-1,
                        dir_votes=[1, 9])
        v = registry.adoption_verdict(entry(), m, 0.05)
        self.assertEqual(v["verdict"], "REJETE")
        self.assertGreaterEqual(len(v["reasons"]), 3)

    def test_verdict_is_always_one_of_the_declared_values(self):
        cases = [measurement(), measurement(prereg="POST"),
                 measurement(folds=2, agree=2), measurement(direction=-1),
                 measurement(null_comparable=False, null_matched=1),
                 measurement(folds=5, agree=5, p=0.2,
                             floor=registry.resolution_floor(5, 200))]
        for m in cases:
            self.assertIn(self._verdict(m, bar=0.0083), registry.VERDICTS)

    def test_a_scored_verdict_always_carries_its_comparison_key(self):
        v = registry.adoption_verdict(entry(), measurement(), 0.05)
        self.assertTrue(v["scored"])
        self.assertTrue(v["comparison_key"])

    def test_the_verdict_carries_every_input_it_was_judged_on(self):
        """A conclusion whose inputs were not kept cannot be re-examined. An
        earlier version copied a hand-maintained list of nine keys and silently
        dropped the realised shuffle count and the whole configuration."""
        m = measurement()
        v = registry.adoption_verdict(entry(), m, 0.05)
        for k in m:
            self.assertIn(k, v, k)
        for k in ("shuffles", "null_matched", "window", "train_days",
                  "test_days", "horizon"):
            self.assertEqual(v[k], m[k], k)


class TestFamilyCounter(unittest.TestCase):
    """The counter is the point: an uncounted draw corrects nothing."""

    def _reg(self):
        reg = registry.new_registry("2026-01-01")
        registry.register(reg, "H", "s", "eth_btc", 1, 0.7, "2026-01-01", "w")
        return reg

    def test_a_scored_result_enters_the_family(self):
        reg = self._reg()
        v = registry.adoption_verdict(entry(), measurement(), 0.05)
        registry.record_result(reg, "H", v, "2026-01-02")
        self.assertEqual(registry.family_size(reg), 1)

    def test_rerunning_the_identical_test_does_not_inflate_the_bar(self):
        """Re-running the script is not a new comparison. Counting it would
        let the bar tighten for free and quietly reject everything - and
        logging it five times would make a registry miscount its own draws."""
        reg = self._reg()
        v = registry.adoption_verdict(entry(), measurement(), 0.05)
        for _ in range(5):
            registry.record_result(reg, "H", v, "2026-01-02")
        self.assertEqual(registry.family_size(reg), 1)
        self.assertEqual(len(registry.find(reg, "H")["results"]), 1)

    def test_a_result_that_differs_in_any_field_is_still_appended(self):
        """Deduplication must never swallow a changed outcome: that would be
        the file editing its own history, which is the one thing it may not
        do."""
        reg = self._reg()
        v = registry.adoption_verdict(entry(), measurement(), 0.05)
        registry.record_result(reg, "H", v, "2026-01-02")
        registry.record_result(reg, "H", v, "2026-06-01")
        w = registry.adoption_verdict(entry(), measurement(agreement=0.10,
                                                           direction=-1), 0.05)
        registry.record_result(reg, "H", w, "2026-06-01")
        results = registry.find(reg, "H")["results"]
        self.assertEqual(len(results), 3)
        self.assertEqual(results[-1]["verdict"], "REJETE")

    def test_a_different_configuration_is_a_different_comparison(self):
        reg = self._reg()
        base = measurement()
        alt = measurement(comparison_key=registry.comparison_key(
            "H", "eth_btc", 730, 540, 180, "2027-06-01"))
        for m in (base, alt):
            registry.record_result(
                reg, "H", registry.adoption_verdict(entry(), m, 0.05),
                "2026-01-02")
        self.assertEqual(registry.family_size(reg), 2)

    def test_an_unscored_result_never_enters_the_family(self):
        reg = self._reg()
        v = registry.adoption_verdict(entry(), measurement(folds=1, agree=1),
                                      0.05)
        registry.record_result(reg, "H", v, "2026-01-02")
        self.assertEqual(registry.family_size(reg), 0)

    def test_the_bar_tightens_as_the_family_grows(self):
        self.assertLess(registry.bonferroni_bar(20),
                        registry.bonferroni_bar(5))

    def test_recording_the_result_updates_the_status(self):
        reg = self._reg()
        v = registry.adoption_verdict(entry(), measurement(prereg="POST"), 0.05)
        registry.record_result(reg, "H", v, "2026-01-02")
        self.assertEqual(registry.find(reg, "H")["status"], "CANDIDAT")

    def test_every_written_result_is_stamped_with_its_method(self):
        """Results already in the file were produced by a null that permuted
        over dates the target never covered. They stay, unrewritten; the stamp
        is what lets a reader tell them from these."""
        reg = self._reg()
        v = registry.adoption_verdict(entry(), measurement(), 0.05)
        registry.record_result(reg, "H", v, "2026-01-02")
        self.assertEqual(registry.find(reg, "H")["results"][-1]["method_version"],
                         registry.METHOD_VERSION)

    def test_recording_against_an_unknown_id_is_an_error(self):
        with self.assertRaises(KeyError):
            registry.record_result(self._reg(), "INCONNU",
                                   {"verdict": "REJETE", "scored": False,
                                    "comparison_key": None}, "2026-01-02")


class TestComparisonKey(unittest.TestCase):

    def test_key_separates_configurations_and_data_cutoffs(self):
        a = registry.comparison_key("H", "eth_btc", 365, 365, 180, "2026-08-31")
        b = registry.comparison_key("H", "eth_btc", 730, 365, 180, "2026-08-31")
        c = registry.comparison_key("H", "eth_btc", 365, 365, 180, "2027-08-31")
        d = registry.comparison_key("H", "alt_eth", 365, 365, 180, "2026-08-31")
        self.assertEqual(len({a, b, c, d}), 4)


class TestRegisteredHypotheses(unittest.TestCase):
    """The declared list is a spec commitment, like TIER_A_SIGNALS."""

    def test_ids_are_unique(self):
        ids = [h[0] for h in registry.HYPOTHESES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_direction_is_written_before_any_measurement(self):
        for hid, _, _, direction, thr, why in registry.HYPOTHESES:
            self.assertIn(direction, (1, -1), hid)
            self.assertGreaterEqual(thr, registry.MIN_AGREEMENT, hid)
            self.assertTrue(why.strip(), hid)

    def test_the_sign_inversion_between_targets_is_recorded_as_a_prediction(self):
        """Fact 4 of the project record: the sign flips with the target. It is
        written here as an expectation so a later run can falsify it - and this
        run did NOT re-measure it, both sides having landed under the fold
        minimum. See the report's CE QUE CE RUN NE MONTRE PAS block."""
        by_key = {(h[1], h[2]): h[3] for h in registry.HYPOTHESES}
        self.assertEqual(by_key[("dominance BTC", "eth_btc")], 1)
        self.assertEqual(by_key[("dominance BTC", "alt_eth")], -1)


class TestOfflineLoading(unittest.TestCase):
    """Offline by construction, not because a gitignored file happens to be
    there. analysis/.cache is not in the repository, so on a fresh clone the
    inherited loader would have reached for the API."""

    def test_a_missing_cache_names_the_file_it_wanted(self):
        tmp = tempfile.mkdtemp()
        try:
            missing = os.path.join(tmp, "fng.json")
            with self.assertRaises(FileNotFoundError) as ctx:
                registry.load_fear_greed_offline(missing)
            self.assertIn("fng.json", str(ctx.exception))
        finally:
            shutil.rmtree(tmp)

    @unittest.skipUnless(HAVE_FNG, NO_FNG)
    def test_build_inputs_succeeds_with_the_network_unplugged(self):
        original = urllib.request.urlopen

        def explode(*a, **k):
            raise AssertionError("appel reseau depuis registry.py")

        urllib.request.urlopen = explode
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

    def test_the_dominance_basket_never_holds_twenty_five_assets(self):
        """band_study.py's docstring claimed 25 for months and this module
        repeated the figure. The file has never held it."""
        lo, hi, n = self.ctx["basket"]
        self.assertEqual((lo, hi), (14, 24))
        self.assertEqual(n, 2800)

    def test_the_eth_btc_target_is_not_the_ethbtc_price_series(self):
        """Every other module measures ETH/BTC on analysis/ethbtc.json. The
        header has to say so, because the two are close but not the same."""
        d = self.ctx["divergence"]
        self.assertGreater(d["ratio_hi"] - d["ratio_lo"], 0.1)
        self.assertGreater(d["max_diff"], 1.0)

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
        from a wider period than the signal's own window. It must not move the
        real measurement, or it would be a second free parameter."""
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
        rule cannot pass silently. H04 is the one the adoption rule must keep
        rejecting."""
        expected = {("Fear & Greed", "eth_btc"): (1, 9),
                    ("niveau ETH/BTC", "eth_btc"): (5, 5),
                    ("dominance BTC", "alt_btc"): (4, 5),
                    ("Fear & Greed", "alt_eth"): (3, 7)}
        for (sig, tgt), want in expected.items():
            self.assertEqual(
                wf.walk(self._series(sig, tgt), self.targets[tgt],
                        registry.WINDOW, registry.TRAIN_DAYS,
                        registry.TEST_DAYS), want, "%s -> %s" % (sig, tgt))

    def test_the_in_sample_direction_disagrees_with_the_out_of_sample_one(self):
        """H03: the full-sample gradient says +1, the majority of test folds
        says -1. This is why criterion 2 reads the out-of-sample field, and it
        is measured rather than argued."""
        s = self._series("niveau ETH/BTC", "eth_btc")
        fwd = self.targets["eth_btc"]
        pairs, _ = registry.walk_folds(s, fwd)
        oos, votes = registry.oos_direction(pairs)
        self.assertEqual(oos, -1)
        self.assertEqual(votes, (0, 5))
        self.assertEqual(registry.insample_direction(s, fwd), 1)

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

    def test_fear_and_greed_is_rejected_on_disk_too(self):
        """The verdict the whole module is checked against, read back from the
        artifact rather than from memory."""
        self.assertEqual(self.last["H04"]["verdict"], "REJETE")
        self.assertEqual((self.last["H04"]["agree"], self.last["H04"]["folds"]),
                         (1, 9))

    def test_nothing_is_adopted_and_nothing_is_a_candidate(self):
        for hid, r in self.last.items():
            self.assertNotIn(r["verdict"], ("ADOPTE", "CANDIDAT"), hid)

    def test_the_family_counter_holds_only_scored_comparisons(self):
        scored = [r for r in self.last.values() if r.get("scored")]
        self.assertEqual(len(self.reg["comparisons"]), len(scored))


class TestReport(unittest.TestCase):
    """The report is rendered from data it is handed, so the parts that carry
    a bias declaration can be tested rather than eyeballed."""

    @classmethod
    def setUpClass(cls):
        reg = registry.new_registry("2026-09-01")
        measurements, verdicts = {}, {}
        for hid, sig, tgt, d, thr, why in registry.HYPOTHESES:
            e = registry.register(reg, hid, sig, tgt, d, thr,
                                  registry.TODAY, why)
            m = measurement(comparison_key=registry.comparison_key(
                hid, tgt, 365, 365, 180, "2026-08-31"), data_end="2026-08-31",
                prereg="POST")
            m["nulls"] = {mode: {"draws": 250, "usable": 220, "degenerate": 30,
                                 "matched": 25, "fold_min": 0, "fold_max": 7,
                                 "fold_median": 2, "mean_all": 50.0,
                                 "mean_matched": 48.0, "rates_matched": [],
                                 "rates_all": []}
                          for mode in registry.NULL_MODES}
            measurements[hid] = m
            verdicts[hid] = registry.adoption_verdict(e, m, 0.0083)
            registry.record_result(reg, hid, verdicts[hid], registry.TODAY)
        ctx = {"basket": (14, 24, 2800),
               "divergence": {"n": 2709, "max_diff": 1.63, "mean_diff": 0.31,
                              "median_diff": 0.21, "ratio_lo": 5.965,
                              "ratio_hi": 6.293}}
        cls.text = registry.render_report(measurements, verdicts, reg, 0.0083,
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

    def test_the_basket_size_printed_is_the_measured_one(self):
        self.assertIn("14 a 24 actifs", self.text)
        self.assertNotIn("25 actifs", self.text)

    def test_the_header_warns_the_eth_btc_target_is_the_rebased_index(self):
        self.assertIn("rotations.json", self.text)
        self.assertIn("ethbtc.json", self.text)
        self.assertIn("1.63", self.text)

    def test_the_report_states_it_governs_nothing(self):
        self.assertIn("NE GOUVERNE RIEN", self.text)

    def test_the_report_declares_every_hypothesis_post_hoc(self):
        self.assertIn("POST-HOC", self.text)
        self.assertNotIn("ADOPTE", self.text.split("REGLE D ADOPTION")[-1]
                         .split("VERDICTS")[-1])


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


if __name__ == "__main__":
    unittest.main()
