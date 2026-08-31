#!/usr/bin/env python3
"""
Live source contract tests. Opt-in: set RUN_LIVE_TESTS=1.

Why these exist
---------------
Both bugs found during development were silent field-name mismatches that
returned HTTP 200 and looked healthy:

  - BGeometrics SSR returns `ssrStablecoin`, not `ssr`
  - CoinGecko's keyless tier accepts price_change_percentage=90d, returns 200,
    and omits the field entirely

Neither raised an error. Both produced a plausible-looking degraded run. These
tests assert the exact field each source must return, so the next such change
fails loudly instead of quietly emptying a signal.

Opt-in because BGeometrics allows only 10 requests/hour per IP and the
pipeline itself uses 7. Running these on every push would starve the pipeline.

Run: RUN_LIVE_TESTS=1 python -m unittest tests.test_sources -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))

import fetch_signals as fs

LIVE = os.environ.get("RUN_LIVE_TESTS") == "1"
requires_live = unittest.skipUnless(LIVE, "set RUN_LIVE_TESTS=1 to run")


@requires_live
class TestKeylessSources(unittest.TestCase):
    """One assertion per source: the field we depend on is present and numeric."""

    def test_fear_greed_shape(self):
        d = fs._get("https://api.alternative.me/fng/?limit=1&format=json")
        entry = d["data"][0]
        self.assertIn("value", entry)
        self.assertIn("value_classification", entry)
        self.assertTrue(0 <= int(entry["value"]) <= 100)

    def test_coingecko_global_dominance_shape(self):
        d = fs._get("https://api.coingecko.com/api/v3/global")
        mcap = d["data"]["market_cap_percentage"]
        self.assertIn("btc", mcap)
        self.assertTrue(0 < float(mcap["btc"]) < 100)

    def test_coingecko_eth_btc_history_shape(self):
        d = fs._get("https://api.coingecko.com/api/v3/coins/ethereum/"
                    "market_chart?vs_currency=btc&days=14")
        self.assertIn("prices", d)
        self.assertGreater(len(d["prices"]), 1)

    def test_coinmetrics_mvrv_field(self):
        s = fs._coinmetrics("btc", "CapMVRVCur")
        self.assertIn("btc", s)
        self.assertGreater(s["btc"][-1][1], 0)

    def test_coinmetrics_exchange_supply_field(self):
        s = fs._coinmetrics("btc,eth", "SplyExNtv")
        self.assertIn("eth", s)
        self.assertGreaterEqual(len(s["eth"]), 8,
                                "need 8+ days for the 7d netflow window")


@requires_live
class TestBGeometricsContracts(unittest.TestCase):
    """Exact field names. This is the class that would have caught the SSR bug.

    Five requests against a 10/hour budget - do not run alongside a pipeline run.
    """

    CONTRACTS = [
        ("mvrv-zscore/last", "mvrvZscore"),
        ("nvt/last", "nvt"),
        ("ssr/last", "ssrStablecoin"),       # NOT "ssr" - the bug
        ("sth-realized-price/last", "sthRealizedPrice"),
        ("puell-multiple/last", "puellMultiple"),
    ]

    def test_field_names_are_stable(self):
        for endpoint, field in self.CONTRACTS:
            with self.subTest(endpoint=endpoint):
                d = fs._bg(endpoint)
                self.assertIn(field, d,
                              "%s no longer returns '%s' - parser needs updating"
                              % (endpoint, field))
                self.assertIsNotNone(float(d[field]))
                self.assertIn("d", d, "missing as_of date - staleness check blind")


@requires_live
class TestFundingChain(unittest.TestCase):
    """At least one venue must answer, whatever the runner's IP.

    Binance (451) and Bybit (403) are expected to fail from GitHub runners;
    that is the whole reason the chain exists. The contract is that the chain
    as a whole resolves, not that any particular venue does.
    """

    def test_chain_resolves_from_this_ip(self):
        result = fs.fetch_funding_rates(previous=None)
        self.assertIsNotNone(result["signal"])
        self.assertIn("per_symbol", result)
        self.assertGreater(len(result["per_symbol"]), 0)

    def test_apr_uses_per_venue_settlement_frequency(self):
        """Hyperliquid settles hourly, CEXes 8-hourly. Annualising both at 3/day
        understated Hyperliquid's APR by 8x before this was fixed."""
        result = fs.fetch_funding_rates(previous=None)
        for sym, data in result["per_symbol"].items():
            with self.subTest(symbol=sym):
                self.assertIn(data["settlements_per_day"], (3, 24))


@requires_live
class TestEndToEnd(unittest.TestCase):

    def test_pipeline_produces_a_usable_snapshot(self):
        """Whatever fails, the run must still yield a valid, honest snapshot."""
        import report
        signals = {"fear_greed": fs.safe_fetch(fs.fetch_fear_greed)}
        snap = {"date": "2026-01-01", "fetched_at": "x", "schema_version": 4,
                "signals": signals, "health": {"degraded": False, "failed": 0,
                                               "stale": 0},
                "gate_legacy": {"fired": 0, "checkable_today": 1,
                                "fired_signals": []},
                "gate_new": {"authoritative": False, "fired": 0, "checkable": 1,
                             "threshold": 5, "would_fire": False,
                             "unavailable": []}}
        md = report.render_markdown(snap)
        self.assertIn("Signal snapshot", md)


if __name__ == "__main__":
    unittest.main(verbosity=2)
