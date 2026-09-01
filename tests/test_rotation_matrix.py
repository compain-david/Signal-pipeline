#!/usr/bin/env python3
"""
Pure logic tests for the rotation bench. No network, no clock, no data file.

Every input below is injected. That is not a style preference: this module's
whole output is numbers, and a test that read analysis/*.json would change its
verdict the next time the data is refreshed, which is the one thing a guard
must never do.

What these guard, in order of what would hurt most if it broke silently:
  - the same-window baseline, because a widened baseline fabricates edge and
    says nothing while doing it
  - the strictly-prior percentile window, because letting a value rank itself
    inflates exactly the band the fire set is drawn from
  - the identity between the observed matrix and the null matrix, because if
    they ever measured different things every p-value would be answering a
    question no cell was asked
  - the multiplicity correction, because its entire job is to be harder than
    the raw p-value and a bug there would restore the illusion it exists to
    remove
  - the bench WIDTH, because it is the denominator of every multiplicity
    statement and a silently dropped candidate changes it without a word
  - the gates and the taxonomy, because those are the sentences a reader quotes

Run: python -m unittest discover -s tests -v
"""

import datetime
import io
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))

import forward_study as fs
import rotation_matrix as rm


def days(n, start="2020-01-01"):
    d0 = datetime.date.fromisoformat(start)
    return [(d0 + datetime.timedelta(days=i)).isoformat() for i in range(n)]


def naive_percentile(series, dates, window):
    """The obvious O(n*w) rescan the fast version must reproduce exactly."""
    out = {}
    for i, d in enumerate(dates):
        if i < window:
            continue
        hist = [series[dates[j]] for j in range(i - window, i)]
        out[d] = sum(1 for h in hist if h < series[d]) / len(hist) * 100
    return out


def _synthetic_world(seed=11, n=1300):
    """A complete, self-consistent input set for the whole bench.

    Injected rather than loaded so these tests keep their verdict when
    analysis/*.json is refreshed - the same reason the rest of this file
    injects everything.
    """
    rng = random.Random(seed)
    ds = days(n)
    px, v = {}, 100.0
    for d in ds:
        v *= 1 + rng.gauss(0, 0.02)
        px[d] = v
    targets = {"eth_btc": px,
               "alt_eth": {d: px[d] ** 1.1 for d in ds},
               "alt_btc": {d: px[d] ** 0.9 for d in ds}}
    dom = {d: {"btc_dom": 45 + rng.gauss(0, 3),
               "eth_dom": 18 + rng.gauss(0, 2),
               "n_assets": 28 + (i % 5)}
           for i, d in enumerate(ds)}
    series = {"mvrv_z_score": {d: rng.gauss(1.5, 1.0) for d in ds},
              "stablecoin_supply_ratio": {d: rng.gauss(10.0, 2.0) for d in ds},
              "nvt": {d: rng.gauss(40.0, 8.0) for d in ds}}
    fng = {d: rng.uniform(5, 95) for d in ds}
    return targets, dom, series, fng


_RENDER_CACHE = {}


def _render_on_synthetic_data(break_reference=False):
    """Run rotation_matrix.main() end to end on injected data.

    Every loader is replaced, OUT_PATH is redirected to a temp file so the real
    analysis/rotation_matrix.txt is never touched by a test run, and both null
    draw counts are cut to keep the suite fast. The draw counts change the
    NUMBERS, which is why nothing here asserts on one - only on the report's
    structure and its declarations.
    """
    if not break_reference and "ok" in _RENDER_CACHE:
        return _RENDER_CACHE["ok"]

    import contextlib
    import shutil
    import tempfile

    targets, dom, series, fng = _synthetic_world()
    if break_reference:
        # Same dates, unrelated path: the returns no longer agree, so the
        # eth_btc rows would be incomparable with forward_study / band_study /
        # walkforward / oos_test and the run must stop instead of printing.
        rng = random.Random(7)
        ref = {}
        v = 100.0
        for d in sorted(targets["eth_btc"]):
            v *= 1 + rng.gauss(0, 0.05)
            ref[d] = v
    else:
        # A pure change of base: constant factor, identical returns.
        ref = {d: p / 6.0 for d, p in targets["eth_btc"].items()}

    saved = {n: getattr(rm, n) for n in
             ("load_rotations", "load_dominance", "load_series",
              "load_fear_greed_cache", "load_ethbtc_reference", "OUT_PATH",
              "null_matrix", "wf_null_rate")}
    tmp = tempfile.mkdtemp()
    real_nm, real_wf = rm.null_matrix, rm.wf_null_rate
    try:
        rm.load_rotations = lambda: targets
        rm.load_dominance = lambda: dom
        rm.load_series = lambda: series
        rm.load_fear_greed_cache = lambda: fng
        rm.load_ethbtc_reference = lambda: ref
        rm.OUT_PATH = os.path.join(tmp, "rotation_matrix.txt")
        rm.null_matrix = (lambda ix, rng_, draws=25:
                          real_nm(ix, rng_, draws=draws))
        rm.wf_null_rate = (lambda pct, dates, fwd, rng_, mode, draws=4:
                           real_wf(pct, dates, fwd, rng_, mode, draws=draws))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rm.main()
        text = buf.getvalue()
    finally:
        for name, value in saved.items():
            setattr(rm, name, value)
        shutil.rmtree(tmp, ignore_errors=True)

    if not break_reference:
        _RENDER_CACHE["ok"] = text
    return text


class TestRollingPercentile(unittest.TestCase):
    """The bisect version exists for speed; it must not buy speed with drift."""

    def test_matches_the_naive_rescan_exactly(self):
        rng = random.Random(7)
        ds = days(400)
        s = {d: rng.random() * 100 for d in ds}
        self.assertEqual(rm.rolling_percentile(s, ds, 60),
                         naive_percentile(s, ds, 60))

    def test_matches_naive_when_values_repeat(self):
        """Ties are where a rank implementation usually diverges."""
        ds = days(200)
        s = {d: float(i % 3) for i, d in enumerate(ds)}
        self.assertEqual(rm.rolling_percentile(s, ds, 50),
                         naive_percentile(s, ds, 50))

    def test_today_is_never_inside_its_own_window(self):
        """A value that ranked itself would push the top band up by 1/window
        every day - small, invisible, and concentrated in the fire set."""
        ds = days(120)
        s = {d: float(i) for i, d in enumerate(ds)}   # strictly increasing
        pct = rm.rolling_percentile(s, ds, 30)
        self.assertTrue(all(v == 100.0 for v in pct.values()))

    def test_decreasing_series_ranks_at_the_floor(self):
        ds = days(120)
        s = {d: float(-i) for i, d in enumerate(ds)}
        pct = rm.rolling_percentile(s, ds, 30)
        self.assertTrue(all(v == 0.0 for v in pct.values()))

    def test_costs_exactly_the_first_window_days(self):
        ds = days(100)
        s = {d: float(i) for i, d in enumerate(ds)}
        self.assertEqual(len(rm.rolling_percentile(s, ds, 30)), 70)


class TestBands(unittest.TestCase):

    def test_five_bands_partition_every_dated_value(self):
        ds = days(100)
        pct = {d: float(i) for i, d in enumerate(ds)}
        bands = rm.band_dates(ds, pct)
        self.assertEqual(len(bands), rm.N_BANDS)
        self.assertEqual(sum(len(b) for b in bands), len(ds))

    def test_top_band_keeps_a_perfect_hundred(self):
        """pct == 100 is reachable and must not fall out of every band."""
        ds = days(3)
        pct = {ds[0]: 0.0, ds[1]: 50.0, ds[2]: 100.0}
        self.assertIn(ds[2], rm.band_dates(ds, pct)[-1])

    def test_dates_without_a_percentile_are_dropped_not_guessed(self):
        ds = days(4)
        pct = {ds[0]: 10.0, ds[2]: 90.0}
        self.assertEqual(sum(len(b) for b in rm.band_dates(ds, pct)), 2)


class TestBandOccupancy(unittest.TestCase):
    """These bands are equal-WIDTH, not equal-COUNT. Reporting the top one as a
    'quintile' would be a misreport, so the occupancy is measured and printed;
    these guard that the measurement is real."""

    def test_a_uniform_series_does_fill_five_equal_bands(self):
        ds = days(100)
        pct = {d: float(i) for i, d in enumerate(ds)}
        occ = rm.band_occupancy(rm.band_dates(ds, pct))
        self.assertEqual([n for n, _ in occ], [20] * 5)
        self.assertTrue(all(abs(share - 20.0) < 1e-9 for _, share in occ))

    def test_a_drifting_series_piles_into_the_top_band(self):
        """The mechanical cause of the whole double artefact: on a series that
        keeps making new highs the percentile pins at 100."""
        ds = days(200)
        s = {d: float(i) for i, d in enumerate(ds)}
        pct = rm.rolling_percentile(s, ds, 50)
        occ = rm.band_occupancy(rm.band_dates(sorted(pct), pct))
        self.assertEqual(occ[-1][1], 100.0)
        self.assertEqual(occ[0][1], 0.0)

    def test_shares_always_sum_to_a_hundred(self):
        ds = days(97)
        pct = {d: float(i % 100) for i, d in enumerate(ds)}
        occ = rm.band_occupancy(rm.band_dates(ds, pct))
        self.assertAlmostEqual(sum(share for _, share in occ), 100.0)

    def test_no_bands_is_no_occupancy_rather_than_a_crash(self):
        self.assertEqual(rm.band_occupancy([[], [], [], [], []]), [])


class TestSameWindowBaseline(unittest.TestCase):
    """The regression test for the mistake that was made and corrected once."""

    def _split_world(self):
        # Forward returns are +50 in the old era and -50 in the new one. A
        # signal that only exists in the new era must NOT be charged for that
        # difference: it never had the chance to fire in the old era.
        ds = days(600)
        fwd = {d: (50.0 if i < 300 else -50.0) for i, d in enumerate(ds)}
        return ds, fwd

    def test_late_signal_is_not_charged_for_the_era_it_never_saw(self):
        ds, fwd = self._split_world()
        late = ds[300:]
        cell = rm.edge_cell(late[:100], late, fwd)
        self.assertEqual(cell["edge"], 0.0)

    def test_a_whole_history_baseline_would_have_invented_the_edge(self):
        """Shows the size of the mistake, so nobody removes the correction as
        cosmetic: the same fire set reads -100 points against the wrong
        baseline and 0 against the right one."""
        ds, fwd = self._split_world()
        late = ds[300:]
        right = rm.edge_cell(late[:100], late, fwd)
        wrong = rm.edge_cell(late[:100], ds, fwd)
        self.assertEqual(right["edge"], 0.0)
        self.assertEqual(wrong["edge"], -50.0)

    def test_real_separation_still_registers(self):
        ds = days(400)
        fwd = {d: (10.0 if i % 2 else -10.0) for i, d in enumerate(ds)}
        fire = [d for i, d in enumerate(ds) if i % 2]
        self.assertGreater(rm.edge_cell(fire, ds, fwd)["edge"], 0)

    def test_thin_fire_set_returns_nothing_rather_than_a_number(self):
        ds = days(400)
        fwd = {d: 1.0 for d in ds}
        self.assertIsNone(rm.edge_cell(ds[:5], ds, fwd))

    def test_thin_baseline_returns_nothing_rather_than_a_number(self):
        ds = days(400)
        fwd = {d: 1.0 for d in ds[:10]}
        self.assertIsNone(rm.edge_cell(ds[:10], ds, fwd))


class TestBaselineDilution(unittest.TestCase):
    """The baseline CONTAINS the firing days - forward_study.py's convention.
    On a fat band that dilution is large, so the undiluted figure travels
    alongside instead of being left implicit."""

    def _world(self):
        ds = days(400)
        # half the days fire and are worth +10, the rest -10
        fire = [d for i, d in enumerate(ds) if i % 2]
        fwd = {d: (10.0 if d in set(fire) else -10.0) for d in ds}
        return ds, fire, fwd

    def test_the_included_baseline_understates_the_separation(self):
        ds, fire, fwd = self._world()
        cell = rm.edge_cell(fire, ds, fwd)
        self.assertLess(abs(cell["edge"]), abs(cell["edge_excl"]))

    def test_the_excluded_baseline_is_the_full_separation(self):
        ds, fire, fwd = self._world()
        cell = rm.edge_cell(fire, ds, fwd)
        self.assertEqual(cell["edge_excl"], 20.0)

    def test_no_room_left_outside_the_fire_set_is_none_not_zero(self):
        ds = days(100)
        fwd = {d: 1.0 for d in ds}
        cell = rm.edge_cell(ds, ds, fwd)
        self.assertIsNone(cell["edge_excl"])
        self.assertEqual(cell["n_rest"], 0)


class TestMonotonicity(unittest.TestCase):

    def test_clean_rising_gradient_scores_full(self):
        m = rm.monotonicity([1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertEqual(m["score"], 1.0)
        self.assertTrue(m["rising"])

    def test_clean_falling_gradient_also_scores_full(self):
        m = rm.monotonicity([5.0, 4.0, 3.0, 2.0, 1.0])
        self.assertEqual(m["score"], 1.0)
        self.assertFalse(m["rising"])

    def test_zigzag_scores_at_noise_level(self):
        self.assertEqual(rm.monotonicity([1.0, 5.0, 1.0, 5.0, 1.0])["score"],
                         0.5)

    def test_too_few_surviving_bands_is_unscorable_not_zero(self):
        self.assertIsNone(rm.monotonicity([1.0, None, None, None, 2.0]))


class TestEpisodes(unittest.TestCase):

    def test_two_clusters_far_apart_are_two_observations(self):
        d = days(5) + days(5, "2021-01-01")
        self.assertEqual(rm.episode_stats(d)["episodes"], 2)

    def test_one_long_run_is_one_observation_however_many_days(self):
        st = rm.episode_stats(days(300))
        self.assertEqual(st["episodes"], 1)
        self.assertEqual(st["top3_share"], 100.0)

    def test_concentration_counts_the_three_largest(self):
        d = (days(40) + days(40, "2021-01-01") + days(40, "2022-01-01")
             + days(2, "2023-01-01"))
        st = rm.episode_stats(d)
        self.assertEqual(st["episodes"], 4)
        self.assertGreater(st["top3_share"], 95.0)

    def test_empty_fire_set_does_not_divide_by_zero(self):
        self.assertEqual(rm.episode_stats([])["top3_share"], 0.0)


class TestRotation(unittest.TestCase):
    """The null keeps autocorrelation on purpose. A shuffle would not, and the
    bench would look more discriminating than it is."""

    def test_rotation_preserves_every_value(self):
        v = [1, 2, 3, 4, 5]
        self.assertEqual(sorted(rm.rotate(v, 2)), sorted(v))

    def test_rotation_by_a_full_turn_is_the_identity(self):
        v = [1, 2, 3, 4, 5]
        self.assertEqual(rm.rotate(v, len(v)), v)
        self.assertEqual(rm.rotate(v, 0), v)

    def test_rotation_preserves_local_structure_up_to_one_seam(self):
        v = [0.0] * 50 + [1.0] * 50
        r = rm.rotate(v, 17)
        breaks = sum(1 for a, b in zip(r, r[1:]) if a != b)
        self.assertLessEqual(breaks, 2)

    def test_a_shuffle_would_have_destroyed_that_structure(self):
        v = [0.0] * 50 + [1.0] * 50
        rng = random.Random(3)
        s = list(v)
        rng.shuffle(s)
        breaks = sum(1 for a, b in zip(s, s[1:]) if a != b)
        self.assertGreater(breaks, 10)

    def test_empty_input_is_returned_untouched(self):
        self.assertEqual(rm.rotate([], 5), [])


class TestRawPValue(unittest.TestCase):
    """A count over N draws cannot resolve below 1/N, and quoting it to three
    decimals pretends otherwise."""

    def test_never_returns_zero_however_extreme_the_observation(self):
        p = rm.raw_p_value([0.0] * 200, 99.0)
        self.assertGreater(p["p"], 0.0)
        self.assertEqual(p["p"], 1.0 / 201)

    def test_the_floor_is_the_resolution_of_the_null(self):
        self.assertAlmostEqual(rm.raw_p_value([0.0] * 999, 5.0)["floor"],
                               1.0 / 1000)

    def test_more_draws_buy_a_finer_floor(self):
        coarse = rm.raw_p_value([0.0] * 200, 5.0)["floor"]
        fine = rm.raw_p_value([0.0] * 2000, 5.0)["floor"]
        self.assertLess(fine, coarse)

    def test_monte_carlo_error_shrinks_with_draws(self):
        few = rm.raw_p_value([float(i % 2) for i in range(100)], 0.5)
        many = rm.raw_p_value([float(i % 2) for i in range(4000)], 0.5)
        self.assertLess(many["se"], few["se"])

    def test_an_unremarkable_observation_lands_near_one(self):
        self.assertGreater(rm.raw_p_value(list(range(200)), -1.0)["p"], 0.9)

    def test_no_draws_is_no_p_value(self):
        self.assertIsNone(rm.raw_p_value([], 1.0))


class TestWestfallYoungMinP(unittest.TestCase):
    """The real procedure, and it must behave like a family-wise correction:
    never kinder than the raw p, harsher as the bench widens, and still able to
    pass something that is genuinely overwhelming."""

    def _bench(self, n_cells, draws=400, real=5.0, seed=11):
        rng = random.Random(seed)
        per_cell, real_edges = {}, {}
        for c in range(n_cells):
            key = ("s%d" % c, "t", 90)
            per_cell[key] = [rng.gauss(0, 1) for _ in range(draws)]
            real_edges[key] = real if c == 0 else 0.0
        return per_cell, real_edges

    def test_correction_is_never_kinder_than_the_raw_p_value(self):
        per_cell, real_edges = self._bench(20)
        wy = rm.westfall_young_minp(per_cell, real_edges)
        for k in wy["adjusted"]:
            self.assertGreaterEqual(wy["adjusted"][k] + 1e-9, wy["raw"][k])

    def test_the_same_finding_costs_more_in_a_wider_bench(self):
        narrow = rm.westfall_young_minp(*self._bench(2, real=2.2))
        wide = rm.westfall_young_minp(*self._bench(40, real=2.2))
        k = ("s0", "t", 90)
        self.assertGreater(wide["adjusted"][k], narrow["adjusted"][k])

    def test_an_overwhelming_effect_still_survives(self):
        per_cell, real_edges = self._bench(40, draws=2000, real=20.0)
        wy = rm.westfall_young_minp(per_cell, real_edges)
        self.assertLessEqual(wy["adjusted"][("s0", "t", 90)], rm.ALPHA)

    def test_the_procedure_reports_the_smallest_p_it_could_ever_return(self):
        """With too few draws for the bench width, nothing can pass and the
        verdict would be an artefact of the draw count rather than the data."""
        starved = rm.westfall_young_minp(*self._bench(40, draws=100))
        roomy = rm.westfall_young_minp(*self._bench(40, draws=2000))
        self.assertGreater(starved["floor"], rm.ALPHA)
        self.assertLess(roomy["floor"], rm.ALPHA)

    def test_raw_p_uses_the_add_one_convention_of_the_module(self):
        per_cell, real_edges = self._bench(3, draws=100, real=99.0)
        wy = rm.westfall_young_minp(per_cell, real_edges)
        self.assertEqual(wy["raw"][("s0", "t", 90)], 1.0 / 101)

    def test_cells_without_a_real_edge_are_left_out_not_scored_as_zero(self):
        per_cell, real_edges = self._bench(5)
        real_edges[("s3", "t", 90)] = None
        wy = rm.westfall_young_minp(per_cell, real_edges)
        self.assertNotIn(("s3", "t", 90), wy["adjusted"])

    def test_no_scorable_cell_yields_no_verdict_rather_than_a_default(self):
        wy = rm.westfall_young_minp({("a", "b", 90): [1.0]},
                                    {("a", "b", 90): 5.0})
        self.assertEqual(wy["adjusted"], {})
        self.assertIsNone(wy["critical_p"])

    def test_critical_p_is_a_low_quantile_of_the_bench_minimum(self):
        per_cell, real_edges = self._bench(20)
        wy = rm.westfall_young_minp(per_cell, real_edges)
        self.assertIn(wy["critical_p"], wy["min_p"])
        below = sum(1 for m in wy["min_p"] if m < wy["critical_p"])
        self.assertLessEqual(below / len(wy["min_p"]), rm.ALPHA)


class TestMaxZVariant(unittest.TestCase):
    """Kept, but as a VARIANT. It is not Westfall-Young and here it is harsher,
    because one wild draw in a fat-tailed cell sets the bar for the whole
    bench. Naming it correctly is the point of these."""

    def test_spreadless_null_is_refused_rather_than_scored(self):
        self.assertIsNone(rm.standardise([1.0] * 50))

    def test_short_null_is_refused_rather_than_scored(self):
        self.assertIsNone(rm.standardise([1.0, 2.0, 3.0]))

    def test_it_is_a_separate_function_from_westfall_young(self):
        self.assertIsNot(rm.max_z_correction, rm.westfall_young_minp)

    def test_a_single_wild_cell_raises_the_bar_for_everyone(self):
        """The exact reason it is not the headline: cell 1 is fat-tailed, and
        its worst draw prices cell 0's finding."""
        rng = random.Random(5)
        tame = [rng.gauss(0, 1) for _ in range(400)]
        wild = [rng.gauss(0, 1) for _ in range(400)]
        wild[0] = 400.0
        per_cell = {("s0", "t", 90): list(tame), ("s1", "t", 90): wild}
        real = {("s0", "t", 90): 3.0, ("s1", "t", 90): 0.0}
        mz = rm.max_z_correction(per_cell, real)
        self.assertGreater(mz["critical_z"], 0.0)
        self.assertGreater(max(mz["max_z"]), 50.0)

    def test_no_scorable_cell_yields_no_critical_value(self):
        mz = rm.max_z_correction({("a", "b", 90): [1.0] * 50},
                                 {("a", "b", 90): 5.0})
        self.assertIsNone(mz["critical_z"])


class TestMinimumDetectableEffect(unittest.TestCase):
    """A unanimous rejection means nothing without the size of effect the bench
    could have seen. These guard that the number is a real inverse of the
    correction, not a decoration."""

    def test_maxz_bar_is_the_centre_plus_critical_z_spreads(self):
        self.assertAlmostEqual(
            rm.mde_maxz({"centre": 1.0, "spread": 2.0}, 5.0), 11.0)

    def test_maxz_bar_is_unknown_when_the_cell_cannot_be_scaled(self):
        self.assertIsNone(rm.mde_maxz(None, 5.0))
        self.assertIsNone(rm.mde_maxz({"centre": 0.0, "spread": 1.0}, None))

    def test_minp_bar_is_an_upper_quantile_of_the_cells_own_null(self):
        nulls = [float(i) for i in range(1000)]
        bar = rm.mde_minp(nulls, 0.01)
        self.assertGreater(bar, 980.0)

    def test_a_stricter_critical_p_demands_a_bigger_effect(self):
        nulls = [float(i) for i in range(1000)]
        self.assertGreater(rm.mde_minp(nulls, 0.01),
                           rm.mde_minp(nulls, 0.10))

    def test_a_critical_p_finer_than_the_null_has_no_bar_rather_than_a_fake_one(self):
        """Below 2/(draws+1) no observation could clear the correction at all,
        and inventing a number there would be inventing resolution."""
        self.assertIsNone(rm.mde_minp([float(i) for i in range(1000)], 0.001))

    def test_an_edge_at_the_bar_would_have_cleared_the_correction(self):
        """The bar is only honest if an observation sitting on it really would
        have produced a raw p at or below the critical p."""
        rng = random.Random(2)
        nulls = [rng.gauss(0, 1) for _ in range(2000)]
        critical = 0.01
        bar = rm.mde_minp(nulls, critical)
        self.assertLessEqual(rm.raw_p_value(nulls, bar)["p"], critical)

    def test_no_null_is_no_bar(self):
        self.assertIsNone(rm.mde_minp([], 0.05))


class TestBenchWidthIsAuditable(unittest.TestCase):
    """The bench width is the denominator of every multiplicity statement. A
    candidate dropped in silence changes it without a word, which is how a
    reader loses the ability to check '54 comparisons'."""

    def _fake_inputs(self, n=500):
        ds = days(n)
        dom = {d: {"btc_dom": float(i % 7), "eth_dom": float(i % 5)}
               for i, d in enumerate(ds)}
        series = {"mvrv_z_score": {d: float(i % 11) for i, d in enumerate(ds)},
                  "stablecoin_supply_ratio": {d: float(i % 3)
                                              for i, d in enumerate(ds)},
                  "nvt": {d: float(i % 13) for i, d in enumerate(ds)},
                  "puell_multiple": {d: 1.0 for d in ds},
                  "sth_realized_price": {d: 1.0 for d in ds}}
        fng = {d: float(i % 100) for i, d in enumerate(ds)}
        return dom, series, fng

    def test_the_six_expected_candidates_are_the_ones_measured(self):
        raw = rm.candidate_series(*self._fake_inputs())
        self.assertEqual(tuple(n for n, _ in raw), rm.EXPECTED_CANDIDATES)
        kept, dropped = rm.select_candidates(raw, 100)
        self.assertEqual(tuple(n for n, _ in kept), rm.EXPECTED_CANDIDATES)
        self.assertEqual(dropped, [])

    def test_bench_width_follows_the_candidates_that_survived(self):
        raw = rm.candidate_series(*self._fake_inputs())
        kept, _ = rm.select_candidates(raw, 100)
        self.assertEqual(len(kept) * len(rm.TARGETS) * len(rm.HORIZONS), 54)

    def test_a_short_candidate_is_announced_not_swallowed(self):
        raw = rm.candidate_series(*self._fake_inputs())
        raw.append(("trop court", {d: 1.0 for d in days(10)}))
        kept, dropped = rm.select_candidates(raw, 100)
        self.assertEqual([n for n, _ in dropped], ["trop court"])
        self.assertEqual(dropped[0][1], 10)
        self.assertNotIn("trop court", [n for n, _ in kept])

    def test_a_dropped_candidate_shrinks_the_declared_width(self):
        raw = rm.candidate_series(*self._fake_inputs())
        raw[2] = ("Fear & Greed", {d: 1.0 for d in days(10)})
        kept, dropped = rm.select_candidates(raw, 100)
        self.assertEqual(len(kept) * len(rm.TARGETS) * len(rm.HORIZONS), 45)
        self.assertEqual(len(dropped), 1)

    def test_the_excluded_series_are_named_with_a_reason(self):
        names = [n for n, _ in rm.EXCLUDED_BY_DESIGN]
        self.assertIn("puell_multiple", names)
        self.assertTrue(any(n.startswith("sth_realized_price") for n in names))
        for _, why in rm.EXCLUDED_BY_DESIGN:
            self.assertGreater(len(why), 10)

    def test_no_excluded_series_sneaks_back_in_as_a_candidate(self):
        raw = rm.candidate_series(*self._fake_inputs())
        got = [n for n, _ in raw]
        self.assertNotIn("puell_multiple", got)
        self.assertNotIn("sth_realized_price", got)


class TestMatrixIdentity(unittest.TestCase):
    """The observed matrix and the null matrix must come out of the same code
    path. If they diverged by a single date, every p-value would be comparing
    an apple to a slightly different apple and nothing would say so."""

    def _setup(self, n=500, seed=4):
        rng = random.Random(seed)
        ds = days(n)
        px = {}
        v = 100.0
        for d in ds:
            v *= 1 + rng.gauss(0, 0.02)
            px[d] = v
        targets = {"eth_btc": px,
                   "alt_eth": {d: px[d] ** 1.1 for d in ds},
                   "alt_btc": {d: px[d] ** 0.9 for d in ds}}
        fwds = {t: {h: fs.forward_map(p, h) for h in rm.HORIZONS}
                for t, p in targets.items()}
        pct = {d: (i * 37) % 101 for i, d in enumerate(ds)}
        ix = rm.build_index(ds, pct, fwds)
        return ds, pct, fwds, {"sig": ix}

    def test_the_fast_path_reproduces_the_descriptive_cell_exactly(self):
        ds, pct, fwds, indexes = self._setup()
        fast = rm.matrix_edges(indexes, 0.0)
        fire = rm.band_dates(ds, pct)[-1]
        for t, per_h in fwds.items():
            for h, fwd in per_h.items():
                slow = rm.edge_cell(fire, [d for d in ds if d in fwd], fwd)
                if slow is None:
                    continue
                self.assertAlmostEqual(fast[("sig", t, h)], slow["edge"],
                                       places=9)

    def test_a_full_turn_of_rotation_returns_the_observed_matrix(self):
        _, _, _, indexes = self._setup()
        self.assertEqual(rm.matrix_edges(indexes, 0.0),
                         rm.matrix_edges(indexes, 1.0))

    def test_rotation_moves_the_cells_it_is_supposed_to_move(self):
        _, _, _, indexes = self._setup()
        a = rm.matrix_edges(indexes, 0.0)
        b = rm.matrix_edges(indexes, 0.37)
        self.assertTrue(any(abs(a[k] - b[k]) > 1e-9 for k in a))

    def test_targets_on_different_date_grids_raise_instead_of_mixing(self):
        ds = days(400)
        px = {d: 100.0 + i for i, d in enumerate(ds)}
        short = {d: 100.0 + i for i, d in enumerate(ds[:200])}
        fwds = {"eth_btc": {h: fs.forward_map(px, h) for h in rm.HORIZONS},
                "alt_eth": {h: fs.forward_map(short, h) for h in rm.HORIZONS}}
        pct = {d: 50.0 for d in ds}
        with self.assertRaises(ValueError):
            rm.build_index(ds, pct, fwds)

    def test_every_cell_carries_one_value_per_draw(self):
        _, _, _, indexes = self._setup()
        nm = rm.null_matrix(indexes, random.Random(1), draws=12)
        for vals in nm["per_cell"].values():
            self.assertEqual(len(vals), 12)
        self.assertEqual(len(nm["counts"]), 12)

    def test_one_cell_per_signal_target_horizon(self):
        _, _, _, indexes = self._setup()
        nm = rm.null_matrix(indexes, random.Random(1), draws=5)
        self.assertEqual(len(nm["per_cell"]),
                         len(rm.TARGETS) * len(rm.HORIZONS))

    def test_the_same_seed_reproduces_the_same_bench(self):
        _, _, _, indexes = self._setup()
        a = rm.null_matrix(indexes, random.Random(99), draws=8)
        b = rm.null_matrix(indexes, random.Random(99), draws=8)
        self.assertEqual(a["per_cell"], b["per_cell"])


class TestReferenceAgreement(unittest.TestCase):
    """rotations.json['eth_btc'] and analysis/ethbtc.json differ by a constant
    factor of about six. Every other module measures on the other one, so the
    two have to be shown commensurable rather than assumed to be."""

    def _series(self, n=400, seed=8):
        rng = random.Random(seed)
        ds = days(n)
        out, v = {}, 100.0
        for d in ds:
            v *= 1 + rng.gauss(0, 0.02)
            out[d] = v
        return out

    def test_a_constant_factor_leaves_returns_identical(self):
        a = self._series()
        b = {d: v / 6.09 for d, v in a.items()}
        r = rm.reference_agreement(a, b)
        self.assertAlmostEqual(r["corr"], 1.0, places=9)
        self.assertLess(r["median_abs_diff"], 1e-9)
        self.assertAlmostEqual(r["level_ratio"], 6.09, places=6)

    def test_a_genuinely_different_series_is_caught(self):
        a = self._series(seed=8)
        b = self._series(seed=9)
        r = rm.reference_agreement(a, b)
        self.assertLess(r["corr"], 0.99)

    def test_too_little_overlap_is_no_answer_rather_than_a_wrong_one(self):
        a = self._series()
        b = {d: 1.0 for d in days(5, "2030-01-01")}
        self.assertIsNone(rm.reference_agreement(a, b))


class TestWalkForwardNulls(unittest.TestCase):
    """Two nulls exist here because the module inherited an incoherent pair -
    a shift for the edge, a shuffle for the walk-forward - and the honest fix
    was to compute both and say which one is the reference."""

    def _world(self, n=1400):
        ds = days(n)
        fwd = {}
        pct = {}
        for i, d in enumerate(ds):
            pct[d] = (i * 7) % 101
            fwd[d] = pct[d] - 50.0
        return ds, pct, fwd

    def test_a_relation_that_holds_agrees_on_every_fold(self):
        ds, pct, fwd = self._world()
        a, f = rm.walk_folds(pct, ds, fwd, train=365, test=180)
        self.assertGreater(f, 0)
        self.assertEqual(a, f)

    def test_an_inverted_second_half_costs_agreement(self):
        ds, pct, fwd = self._world()
        half = len(ds) // 2
        for d in ds[half:]:
            fwd[d] = -fwd[d]
        a, f = rm.walk_folds(pct, ds, fwd, train=365, test=180)
        self.assertLess(a, f)

    def test_too_short_a_history_yields_no_fold_rather_than_a_guess(self):
        ds, pct, fwd = self._world(n=200)
        self.assertEqual(rm.walk_folds(pct, ds, fwd, 365, 180), (0, 0))

    def test_both_nulls_are_computed_and_neither_is_a_constant(self):
        ds, pct, fwd = self._world()
        rng = random.Random(3)
        shift = rm.wf_null_rate(pct, ds, fwd, rng, "decalage", draws=6)
        mix = rm.wf_null_rate(pct, ds, fwd, rng, "melange", draws=6)
        self.assertIsNotNone(shift)
        self.assertIsNotNone(mix)
        for v in (shift, mix):
            # An agreement RATE, so bounded - and it arrives with its own
            # Monte-Carlo error rather than as a bare number, because the gate
            # it feeds sits close enough to the noise to be decided by it.
            self.assertGreaterEqual(v["mean"], 0.0)
            self.assertLessEqual(v["mean"], 100.0)

    def test_the_shift_null_keeps_the_structure_the_shuffle_destroys(self):
        """The whole reason the shift is the reference: a shuffle turns a
        persistent series into noise, which is not the null we want."""
        ds, pct, fwd = self._world()
        vals = [pct[d] for d in ds]
        rotated = rm.rotate(vals, 137)
        rng = random.Random(3)
        mixed = list(vals)
        rng.shuffle(mixed)
        jump_rot = sum(abs(a - b) for a, b in zip(rotated, rotated[1:]))
        jump_mix = sum(abs(a - b) for a, b in zip(mixed, mixed[1:]))
        self.assertLess(jump_rot, jump_mix)

    def test_an_empty_series_has_no_null_rather_than_fifty_percent(self):
        self.assertIsNone(rm.wf_null_rate({}, [], {}, random.Random(1),
                                          "decalage", draws=3))


class TestGates(unittest.TestCase):

    def _row(self, edge=10.0, episodes=8, top3=20.0, mono=1.0,
             folds=6, gap=30.0):
        return {"edges": {rm.DECISION_HORIZON: None if edge is None
                          else {"edge": edge, "hit": 60.0, "n": 100,
                                "edge_excl": edge, "n_rest": 100}},
                "episodes": episodes, "top3_share": top3,
                "mono": {rm.DECISION_HORIZON: {"score": mono, "aligned": 4,
                                               "pairs": 4, "rising": True}},
                "wf": {"folds": folds, "gap": gap, "rate": 80.0,
                       "agree": 5, "null": 50.0}}

    def test_a_clean_pair_passes_everything(self):
        self.assertTrue(all(rm.gates(self._row(), 0.01).values()))

    def test_a_thin_edge_is_stopped(self):
        self.assertFalse(rm.gates(self._row(edge=1.0), 0.01)["edge"])

    def test_a_missing_edge_is_stopped_rather_than_treated_as_zero(self):
        self.assertFalse(rm.gates(self._row(edge=None), 0.01)["edge"])

    def test_few_episodes_are_stopped(self):
        self.assertFalse(rm.gates(self._row(episodes=2), 0.01)["episodes"])

    def test_a_remembered_episode_is_stopped(self):
        self.assertFalse(rm.gates(self._row(top3=90.0), 0.01)["concentration"])

    def test_a_zigzag_gradient_is_stopped(self):
        self.assertFalse(rm.gates(self._row(mono=0.5), 0.01)["monotonie"])

    def test_a_coin_flip_walk_forward_is_stopped(self):
        self.assertFalse(rm.gates(self._row(gap=2.0), 0.01)["walkforward"])

    def test_a_perfect_score_on_two_folds_is_stopped(self):
        """100% over two folds is one coin landing the same way twice."""
        self.assertFalse(rm.gates(self._row(folds=2, gap=50.0),
                                  0.01)["walkforward"])

    def test_exactly_the_minimum_folds_is_readable(self):
        """The floor is a bar, not a veto: at three folds a pair with a real
        gap passes, and saying otherwise about such a pair would be false."""
        self.assertTrue(rm.gates(self._row(folds=rm.WF_MIN_FOLDS, gap=40.0),
                                 0.01)["walkforward"])

    def test_a_pair_that_only_looks_good_among_many_is_stopped(self):
        self.assertFalse(rm.gates(self._row(), 0.40)["multiplicite"])

    def test_an_unscorable_multiplicity_is_a_failure_not_a_pass(self):
        self.assertFalse(rm.gates(self._row(), None)["multiplicite"])


class TestDropKSurvivors(unittest.TestCase):
    """Drop-1 was published once as evidence that no single gate carried the
    verdict. It could not be: two gates failed on every pair, so drop-1 was
    forced to zero by arithmetic. These pin the difference."""

    def _gates(self, **over):
        base = {"edge": True, "episodes": True, "concentration": False,
                "monotonie": True, "walkforward": True, "multiplicite": False}
        base.update(over)
        return base

    def _bench(self):
        return {("a", "eth_btc"): self._gates(),
                ("b", "alt_eth"): self._gates(edge=False),
                ("c", "alt_btc"): self._gates(monotonie=False)}

    def test_drop_one_is_forced_to_zero_by_two_universal_failures(self):
        for combo in rm.drop_k_survivors(self._bench(), 1):
            self.assertEqual(combo["n"], 0)

    def test_drop_two_finds_the_pair_that_only_those_gates_stopped(self):
        combos = {c["dropped"]: c for c in rm.drop_k_survivors(self._bench(), 2)}
        hit = combos[("concentration", "multiplicite")]
        self.assertEqual(hit["n"], 1)
        self.assertEqual(hit["pairs"], [("a", "eth_btc")])

    def test_every_other_pair_of_gates_still_finds_nothing(self):
        combos = rm.drop_k_survivors(self._bench(), 2)
        winners = [c for c in combos if c["n"] > 0]
        self.assertEqual(len(winners), 1)

    def test_drop_two_covers_every_unordered_pair_of_gates(self):
        combos = rm.drop_k_survivors(self._bench(), 2)
        self.assertEqual(len(combos), 15)          # C(6,2)
        self.assertEqual(len({c["dropped"] for c in combos}), 15)

    def test_an_empty_bench_produces_no_combination(self):
        self.assertEqual(rm.drop_k_survivors({}, 2), [])


class TestClassify(unittest.TestCase):

    def _cell(self, passes, sign):
        return {"passes": passes, "sign": sign}

    def test_passing_nowhere_is_useless(self):
        c = {t: self._cell(False, 1) for t in rm.TARGETS}
        self.assertEqual(rm.classify(c)["verdict"], "INUTILE")

    def test_passing_on_one_target_only_is_the_finding_we_were_hunting(self):
        c = {"eth_btc": self._cell(True, 1),
             "alt_eth": self._cell(False, -1),
             "alt_btc": self._cell(False, -1)}
        v = rm.classify(c)
        self.assertEqual(v["verdict"], "SPECIFIQUE A eth_btc")
        self.assertTrue(v["sign_unstable"])

    def test_passing_everywhere_with_one_sign_is_generalist(self):
        c = {t: self._cell(True, 1) for t in rm.TARGETS}
        v = rm.classify(c)
        self.assertEqual(v["verdict"], "GENERALISTE")
        self.assertFalse(v["sign_unstable"])

    def test_passing_everywhere_with_opposite_signs_is_flagged_not_praised(self):
        c = {"eth_btc": self._cell(True, 1),
             "alt_eth": self._cell(True, -1),
             "alt_btc": self._cell(True, 1)}
        v = rm.classify(c)
        self.assertEqual(v["verdict"], "GENERALISTE AU SIGNE INSTABLE")
        self.assertTrue(v["sign_unstable"])

    def test_sign_instability_is_reported_even_when_nothing_passes(self):
        c = {"eth_btc": self._cell(False, 1),
             "alt_eth": self._cell(False, -1),
             "alt_btc": self._cell(False, -1)}
        self.assertTrue(rm.classify(c)["sign_unstable"])

    def test_an_unknown_sign_does_not_invent_instability(self):
        c = {"eth_btc": self._cell(False, 1),
             "alt_eth": self._cell(False, None),
             "alt_btc": self._cell(False, 1)}
        self.assertFalse(rm.classify(c)["sign_unstable"])


class TestBarsMatchTheModulesTheyCameFrom(unittest.TestCase):
    """Every bar here was borrowed from a module that already used it. If one
    drifts, two studies silently stop being comparable."""

    def test_edge_bar_is_the_one_forward_study_uses(self):
        self.assertEqual(rm.MIN_EDGE_PTS, fs.MIN_EDGE_PTS)

    def test_episode_bar_is_the_one_forward_study_uses(self):
        self.assertEqual(rm.MIN_EPISODES, fs.MIN_EPISODES)

    def test_concentration_alarm_is_the_one_forward_study_uses(self):
        self.assertEqual(rm.DOMINANCE_ALARM, fs.DOMINANCE_ALARM)

    def test_band_count_matches_the_imported_direction_test(self):
        import walkforward as wfm
        self.assertEqual(rm.N_BANDS, wfm.N_BANDS)

    def test_the_top_band_starts_where_the_direction_test_says_it_does(self):
        self.assertEqual(rm.TOP_BAND_MIN, 100 - 100 // rm.N_BANDS)

    def test_the_null_is_fine_enough_to_resolve_the_alpha_it_prints(self):
        """A 200-draw null cannot resolve a p it quotes to three decimals."""
        self.assertGreaterEqual(rm.NULL_DRAWS, 1000)
        self.assertLess(1.0 / (rm.NULL_DRAWS + 1), rm.ALPHA / 10)


class TestShadowStatus(unittest.TestCase):
    """ladder.py promises in prose that it governs nothing; this asserts it."""

    def test_the_bench_governs_nothing(self):
        self.assertTrue(rm.GOVERNS_NOTHING)

    def test_it_exposes_no_allocation_or_vote(self):
        forbidden = ("allocate", "allocation", "vote", "execute", "order",
                     "rebalance")
        for name in dir(rm):
            self.assertFalse(any(f in name.lower() for f in forbidden), name)

    def test_it_never_reaches_the_network_for_fear_and_greed(self):
        """forward_study.load_fear_greed refetches when the cache is missing.
        Inheriting that here would make two runs incomparable, so the loader is
        cache-only and must fail loudly rather than quietly go online."""
        import shutil
        import tempfile
        tmp = tempfile.mkdtemp()
        old = rm.ANALYSIS
        try:
            rm.ANALYSIS = tmp
            with self.assertRaises(IOError):
                rm.load_fear_greed_cache()
        finally:
            rm.ANALYSIS = old
            shutil.rmtree(tmp, ignore_errors=True)

    def test_no_network_client_is_reachable_from_this_module(self):
        import io
        with io.open(rm.__file__.replace(".pyc", ".py"),
                     encoding="utf-8") as f:
            src = f.read()
        for banned in ("urllib", "requests", "http.client", "socket"):
            self.assertNotIn("import " + banned, src)


class TestTheTwoBaselineConventions(unittest.TestCase):
    """This module's headline baseline is NOT forward_study.py's.

    The report used to say it was "inherited from forward_study.py". It is
    wider: forward_study restricts to [first fire, last fire], this restricts
    to the whole percentile window. On the real data the two differ by up to
    8.6 points of median, which is larger than the effect this bench can
    detect, so the difference is pinned here against forward_study's ACTUAL
    code rather than against a description of it.
    """

    def _world(self):
        # Two eras. The fire set lives entirely inside the second one, so the
        # firing-window baseline sees only that era while the full-window
        # baseline also sees the first - which is exactly the case where the
        # two conventions must disagree.
        ds = days(600)
        fwd = {d: (40.0 if i < 300 else 0.0) for i, d in enumerate(ds)}
        fire = ds[400:500]
        for d in fire:
            fwd[d] = 10.0
        return ds, fire, fwd

    def test_the_firing_window_edge_equals_what_forward_study_computes(self):
        """The strongest available guard: forward_study.assess is CALLED, so
        the claim cannot rot when that module changes."""
        ds, fire, fwd = self._world()
        row = fs.assess("x", fire, "rule", {90: fwd}, set(ds))
        mine = rm.edge_cell(fire, ds, fwd)
        self.assertAlmostEqual(mine["edge_firewin"], row["edges"][90]["edge"],
                               places=9)

    def test_the_headline_edge_is_not_what_forward_study_computes(self):
        """If this ever starts failing, the two conventions have converged and
        the extra column has stopped earning its width."""
        ds, fire, fwd = self._world()
        row = fs.assess("x", fire, "rule", {90: fwd}, set(ds))
        mine = rm.edge_cell(fire, ds, fwd)
        self.assertNotAlmostEqual(mine["edge"], row["edges"][90]["edge"],
                                  places=1)

    def test_the_gap_between_conventions_is_material_not_rounding(self):
        ds, fire, fwd = self._world()
        cell = rm.edge_cell(fire, ds, fwd)
        self.assertGreater(abs(cell["edge"] - cell["edge_firewin"]),
                           rm.MIN_EDGE_PTS)

    def test_they_agree_when_the_fire_set_spans_the_whole_window(self):
        """The conventions are not always different - which is why the gap has
        to be measured per pair rather than assumed either way."""
        ds = days(400)
        fwd = {d: float(i % 7) for i, d in enumerate(ds)}
        fire = [ds[0]] + ds[100:200] + [ds[-1]]
        cell = rm.edge_cell(fire, ds, fwd)
        self.assertAlmostEqual(cell["edge"], cell["edge_firewin"], places=9)

    def test_the_firing_window_never_reaches_outside_the_pair_window(self):
        ds = days(400)
        fire = ds[100:200]
        win = rm.firing_window(fire, ds)
        self.assertEqual(win[0], fire[0])
        self.assertEqual(win[-1], fire[-1])

    def test_no_fire_set_yields_no_window_rather_than_the_whole_history(self):
        self.assertEqual(rm.firing_window([], days(100)), [])


class TestWalkForwardDivergesFromWalkforwardPy(unittest.TestCase):
    """wf.direction is imported; the date preparation is not shared.

    The module docstring used to claim the two "cannot drift apart". They do.
    These tests pin the cause in place so the reconciliation printed in section
    5 stays true, instead of asserting an agreement that does not hold.
    """

    def _series(self, n=1600):
        return {d: float((i * 37) % 101) for i, d in enumerate(days(n))}

    def test_identical_date_sets_give_identical_folds(self):
        """The agreement half of the claim: when every signal date has a
        forward return, the two preparations coincide exactly."""
        import walkforward as wfm
        s = self._series()
        ds = sorted(s)
        fwd = {d: float((i * 13) % 29) - 14 for i, d in enumerate(ds)}
        pct = rm.rolling_percentile(s, ds)
        mine = rm.walk_folds(pct, [d for d in ds if d in pct], fwd)
        theirs = wfm.walk(s, fwd, rm.PCT_WINDOW, rm.WF_TRAIN, rm.WF_TEST)
        self.assertEqual(mine, theirs)

    def test_a_signal_outliving_its_target_makes_the_two_disagree(self):
        """The disagreement half, and the reason section 5 prints a
        reconciliation rather than quoting walkforward.txt as if reproduced.

        Fear & Greed has exactly this shape: it starts years before the target,
        so the trailing window holds different days in each module and the
        folds cut in different places - 2 of 9 here against 1 of 9 there.
        """
        import walkforward as wfm
        s = self._series()
        ds = sorted(s)
        # The target only exists for the last two thirds of the signal.
        fwd = {d: float((i * 13) % 29) - 14
               for i, d in enumerate(ds) if i >= 500}
        pct = rm.rolling_percentile(s, ds)
        mine = rm.walk_folds(pct, [d for d in ds if d in pct], fwd)
        theirs = wfm.walk(s, fwd, rm.PCT_WINDOW, rm.WF_TRAIN, rm.WF_TEST)
        self.assertNotEqual(mine, theirs)

    def test_the_direction_test_really_is_the_imported_one(self):
        """What the import DOES guarantee: the band cuts and the sign rule."""
        import walkforward as wfm
        self.assertIs(rm.wf.direction, wfm.direction)


class TestWalkForwardNullResolution(unittest.TestCase):
    """At walkforward.SHUFFLES = 40 the null mean carries about 2 points of
    Monte-Carlo error, so the +15 gate was decided by the seed: one real pair
    re-run with five seeds moved from -3 to +21. The draw count is therefore
    set here and never inherited."""

    def _world(self, n=1400):
        ds = days(n)
        pct = {d: float((i * 7) % 101) for i, d in enumerate(ds)}
        fwd = {d: pct[d] - 50.0 for d in ds}
        return ds, pct, fwd

    def test_the_draw_count_is_not_inherited_from_walkforward(self):
        import walkforward as wfm
        self.assertNotEqual(rm.WF_NULL_DRAWS, wfm.SHUFFLES)
        self.assertGreaterEqual(rm.WF_NULL_DRAWS, 500)

    def test_the_null_reports_its_own_error_bar(self):
        ds, pct, fwd = self._world()
        nl = rm.wf_null_rate(pct, ds, fwd, random.Random(3), "decalage",
                             draws=30)
        for field in ("mean", "se", "draws", "used"):
            self.assertIn(field, nl)
        self.assertIsNotNone(nl["se"])

    def test_more_draws_shrink_the_error_bar(self):
        """The property that makes the extra runtime worth paying for."""
        ds, pct, fwd = self._world()
        few = rm.wf_null_rate(pct, ds, fwd, random.Random(5), "melange",
                              draws=20)
        many = rm.wf_null_rate(pct, ds, fwd, random.Random(5), "melange",
                               draws=200)
        self.assertLess(many["se"], few["se"])

    def test_a_gap_sitting_on_the_bar_is_flagged_undecided(self):
        self.assertTrue(rm.gap_is_undecided(16.0, 2.0))
        self.assertTrue(rm.gap_is_undecided(14.0, 2.0))

    def test_a_gap_far_from_the_bar_is_not_flagged(self):
        self.assertFalse(rm.gap_is_undecided(48.0, 2.0))
        self.assertFalse(rm.gap_is_undecided(-30.0, 2.0))

    def test_an_unknown_error_bar_is_not_silently_read_as_certainty(self):
        self.assertFalse(rm.gap_is_undecided(16.0, None))
        self.assertFalse(rm.gap_is_undecided(None, 2.0))

    def test_an_empty_series_has_no_null_rather_than_fifty_percent(self):
        self.assertIsNone(rm.wf_null_rate({}, [], {}, random.Random(1),
                                          "decalage", draws=3))


class TestNullDrawsStayAligned(unittest.TestCase):
    """Both corrections build a per-DRAW statistic by indexing the per-cell
    null lists positionally. A cell skipped in some draws must therefore leave
    a hole rather than compact its list - otherwise the maximum for draw i is
    taken over edges that came from different draws, and nothing raises."""

    def _z_of(self, per_cell, key, value):
        sc = rm.standardise([x for x in per_cell[key] if x is not None])
        return (value - sc["centre"]) / sc["spread"]

    def test_a_skipped_cell_leaves_a_hole_rather_than_shifting(self):
        """Compares the max-z series against the two rules explicitly, because
        standardisation erases raw magnitude and a test built on "the big
        numbers land late" would pass under either rule."""
        n = 40
        per_cell = {"late": [None] * 20 + [float(i * i) for i in range(20)],
                    "always": [float((i * 7) % 23) for i in range(n)]}
        real = {"late": 0.0, "always": 0.0}
        mz = rm.max_z_correction(per_cell, real)

        # The rule the module must follow: cell k speaks for draw i only when
        # it actually produced an edge at draw i.
        aligned = []
        for i in range(n):
            zs = [self._z_of(per_cell, k, per_cell[k][i]) for k in per_cell
                  if per_cell[k][i] is not None]
            aligned.append(max(zs))
        # The rule an append-only list would have produced: "late" slides its
        # 20 edges onto draws 0-19 and is silent afterwards.
        compact = {k: [x for x in v if x is not None]
                   for k, v in per_cell.items()}
        shifted = []
        for i in range(n):
            zs = [self._z_of(per_cell, k, compact[k][i]) for k in compact
                  if i < len(compact[k])]
            shifted.append(max(zs))

        self.assertEqual(len(mz["max_z"]), n)
        for got, want in zip(mz["max_z"], aligned):
            self.assertAlmostEqual(got, want, places=9)
        # Without this the test would pass on a module that never fixed the
        # bug, because the two rules would agree.
        self.assertNotEqual([round(x, 6) for x in aligned],
                            [round(x, 6) for x in shifted])

    def test_min_p_only_counts_cells_present_in_that_draw(self):
        n = 40
        per_cell = {"late": [None] * 20 + [float(i) for i in range(20)],
                    "always": [float(i % 7) for i in range(n)]}
        real = {"late": 50.0, "always": 50.0}
        wy = rm.westfall_young_minp(per_cell, real)
        self.assertEqual(wy["cells"], 2)
        self.assertEqual(len(wy["min_p"]), n)

    def test_a_ragged_bench_still_produces_usable_corrections(self):
        """1900 draws in one cell against 2000 in another - the shape a shorter
        candidate or a raised MIN_OBS would produce."""
        per_cell = {"a": [float(i % 11) for i in range(2000)],
                    "b": [None] * 100 + [float(i % 13) for i in range(1900)]}
        real = {"a": 5.0, "b": 5.0}
        wy = rm.westfall_young_minp(per_cell, real)
        mz = rm.max_z_correction(per_cell, real)
        for k in ("a", "b"):
            self.assertGreater(wy["adjusted"][k], 0.0)
            self.assertLessEqual(wy["adjusted"][k], 1.0)
            self.assertGreaterEqual(mz["adjusted"][k], 0.0)

    def _skippable_index(self):
        """A bench where a cell really does drop in and out between draws.

        The top band is one tight cluster of 40 days parked at the very end of
        the signal, past where the 90-day forward return still exists. Rotating
        it into the covered stretch gives the cell its 40 observations;
        rotating it back out leaves fewer than MIN_OBS and the cell is skipped.
        That is the only shape in which the alignment bug can bite, so it is
        the shape the producer has to be tested on.
        """
        ds = days(400)
        px = {d: 100.0 + (i % 17) for i, d in enumerate(ds)}
        fwds = {"eth_btc": {h: fs.forward_map(px, h) for h in rm.HORIZONS}}
        pct = {d: (90.0 if i >= 360 else float(i % 70))
               for i, d in enumerate(ds)}
        return ds, rm.build_index(ds, pct, fwds)

    def test_the_bench_really_can_skip_a_cell(self):
        """Guards the guard: if this stops holding, the padding tests below go
        quiet without failing."""
        _, ix = self._skippable_index()
        seen = set()
        for frac in (i / 40.0 for i in range(40)):
            seen.add(("sig", "eth_btc", 90) in rm.matrix_edges({"sig": ix},
                                                               frac))
        self.assertEqual(seen, {True, False})

    def test_null_matrix_pads_the_draws_a_cell_sat_out(self):
        """The producer side of the invariant: every cell comes back with
        exactly one entry per draw - a value, or a hole holding its place."""
        _, ix = self._skippable_index()
        nm = rm.null_matrix({"sig": ix}, random.Random(2), draws=60)
        self.assertEqual(nm["draws"], 60)
        for vals in nm["per_cell"].values():
            self.assertEqual(len(vals), 60)
        holed = [k for k, v in nm["per_cell"].items() if None in v]
        self.assertTrue(holed, "aucune cellule sautee : le test ne teste rien")
        for key in holed:
            self.assertTrue(any(x is not None for x in nm["per_cell"][key]))

    def test_a_hole_stays_at_the_draw_it_belongs_to(self):
        """The bug was silent because a compacted list is still a plausible
        list. This pins each entry to the draw that produced it by replaying
        the same offsets through the single-draw path."""
        _, ix = self._skippable_index()
        nm = rm.null_matrix({"sig": ix}, random.Random(2), draws=60)
        replay = random.Random(2)
        for i in range(60):
            m = rm.matrix_edges({"sig": ix}, replay.random())
            for key, vals in nm["per_cell"].items():
                if key in m:
                    self.assertAlmostEqual(vals[i], m[key], places=9)
                else:
                    self.assertIsNone(vals[i])


class TestStructuralChecksSurviveOptimisation(unittest.TestCase):
    """Two real controls used to be bare `assert` statements. `python -O`
    deletes those, so the module would have carried on with an incommensurable
    reference series, or with a null answering a different question than the
    descriptive table - the control its own docstring calls the important one.
    """

    def _source(self):
        with io.open(rm.__file__.replace(".pyc", ".py"),
                     encoding="utf-8") as f:
            return f.read()

    def test_no_bare_assert_carries_a_control_in_this_module(self):
        offenders = [ln.strip() for ln in self._source().splitlines()
                     if ln.strip().startswith("assert ")]
        self.assertEqual(offenders, [])

    def test_both_controls_raise_with_their_measured_value(self):
        src = self._source()
        self.assertIn("incommensurable", src)
        self.assertIn("table descriptive et chemin du null divergent", src)

    def test_the_commensurability_thresholds_are_named_not_inline(self):
        self.assertGreater(rm.REF_MIN_CORR, 0.9)
        self.assertGreater(rm.REF_MAX_DIFF, 0.0)
        self.assertGreater(rm.IDENTITY_TOL, 0.0)


class TestAltBasketCaveat(unittest.TestCase):
    """The SOL/SUI/HYPE exclusion must survive an edit that is not thinking
    about it.

    Two of the three targets are built on a basket that leaves out three of the
    assets a human would actually rotate into. The marker was correct in the
    rendered report and guarded by nothing, so any future edit could have
    dropped it silently and the report would still have looked finished. A
    number quoted out of this table without its footnote is a claim about the
    alt market that the data cannot support.
    """

    def test_the_caveat_names_all_three_missing_assets(self):
        for asset in ("SOL", "SUI", "HYPE"):
            self.assertIn(asset, rm.ALT_BASKET_CAVEAT)

    def test_alt_targets_are_marked_and_eth_btc_is_not(self):
        self.assertEqual(rm._tmark("alt_eth"), "alt_eth" + rm.ALT_MARK)
        self.assertEqual(rm._tmark("alt_btc"), "alt_btc" + rm.ALT_MARK)
        self.assertEqual(rm._tmark("eth_btc"), "eth_btc")

    def test_the_marker_is_not_empty(self):
        """A blank ALT_MARK would satisfy every other test in this class while
        removing the marking from the whole report."""
        self.assertTrue(rm.ALT_MARK.strip())

    def test_every_alt_line_of_a_rendered_report_carries_its_footnote(self):
        """Renders the WHOLE report on injected data and checks the invariant
        line by line. The bench is deliberately run end to end rather than
        line-formatted in the test, because the risk being guarded is a new
        `out(...)` call somewhere in 700 lines of rendering, not a broken
        helper."""
        text = _render_on_synthetic_data()
        self.assertIn("alt_eth", text)
        offenders = [ln for ln in text.splitlines()
                     if ("alt_eth" in ln or "alt_btc" in ln)
                     and rm.ALT_MARK not in ln
                     and rm.ALT_BASKET_CAVEAT not in ln]
        self.assertEqual(offenders, [], "lignes alt non marquees : %r"
                         % offenders[:5])

    def test_the_report_states_it_is_entirely_in_sample(self):
        """forward_study.py says so in its own docstring; this bench holds no
        period back either, and the walk-forward is not a hold-out. Saying it
        is the difference between describing and claiming."""
        text = _render_on_synthetic_data()
        self.assertIn("IN-SAMPLE", text)
        # The out-of-sample failure oos_test.py established on eth_btc was
        # never replayed on the alt targets, so the report has to name that
        # gap rather than let the walk-forward read as a hold-out.
        self.assertIn("oos_test.py", text)
        self.assertIn("n est PAS un test hors echantillon", text)

    def test_the_report_declares_the_two_baseline_conventions(self):
        text = _render_on_synthetic_data()
        self.assertIn("e90 tir", text)
        self.assertIn("PLUS LARGE", text)

    def test_the_report_reconciles_its_folds_with_walkforward(self):
        text = _render_on_synthetic_data()
        self.assertIn("Reconciliation avec walkforward.py", text)


class TestCommensurabilityIsEnforcedNotAssumed(unittest.TestCase):
    """The eth_btc rows of this bench are only comparable with the rest of the
    project while rotations.json and ethbtc.json describe the same trade. That
    was checked by a bare `assert`, which `python -O` removes."""

    def test_an_incommensurable_reference_stops_the_run(self):
        with self.assertRaises(ValueError) as ctx:
            _render_on_synthetic_data(break_reference=True)
        self.assertIn("incommensurable", str(ctx.exception))

    def test_the_message_carries_the_measured_correlation(self):
        with self.assertRaises(ValueError) as ctx:
            _render_on_synthetic_data(break_reference=True)
        self.assertIn("correlation", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
