#!/usr/bin/env python3
"""
Regenerates the rotation series - versioned, so they can be rebuilt.

Why this file exists at all
---------------------------
analysis/dominance.json and analysis/rotations.json were first built by ad-hoc
shell heredocs during exploration. Every rotation finding rests on them and
nobody could regenerate them, which quietly made a third of the analysis
unauditable. That is the defect this closes.

The bias it also fixes
----------------------
The first basket was a FIXED list of 25 assets chosen because they existed in
2019. That list excludes SOL, SUI and HYPE - the winners of this cycle - while
keeping the losers. So "alts fell 82% against ETH" was substantially a
statement about a basket built from survivors of the previous cycle, not a
fact about the alt market.

This version reconstitutes the basket AT EACH DATE: the top N assets by market
cap on that day, excluding BTC, ETH and stablecoins. An asset enters the index
when it becomes large enough and leaves when it does not, which is what an
index is supposed to do.

Two honest limits remain:
- CoinMetrics community covers 135 assets. Genuinely new tokens appear there
  late or never, so the index still lags the real frontier of the alt market.
- Reconstituting by rank introduces its own turnover effect: an asset that
  enters after rising contributes its subsequent path, not the rise that got
  it in. That biases the index DOWN relative to a buy-and-hold of the same
  names, which is the opposite direction to survivorship bias and does not
  cancel it.

Outputs (all committed, all regenerable by running this file):
  analysis/dominance.json  btc_dom, eth_dom, alt_dom per date
  analysis/rotations.json  eth_btc, alt_eth, alt_btc per date
  analysis/basket_log.txt  which assets were in the index, and when

Run: python scripts/build_rotations.py
"""

import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.join(HERE, "..", "analysis")
UA = {"User-Agent": "signal-pipeline/4.0 (personal use)"}
CM = "https://community-api.coinmetrics.io/v4"

TOP_N = 15          # alts in the index at any date
START = "2019-01-01"
END = "2026-08-31"

# Excluded from the alt index by construction, never by judgement about the
# asset. Stablecoins are not a rotation destination on the beta curve - moving
# into them is the risk axis, which belongs to the sell gate.
STABLE_HINTS = ("usdt", "usdc", "dai", "busd", "tusd", "fdusd", "pyusd",
                "usde", "frax", "gusd", "usdp", "eurc", "eurs", "crvusd",
                "buidl")

# Wrapped BTC and ETH are NOT alts - they are BTC and ETH in another envelope.
# The first reconstituted basket admitted wbtc and weth into the top 15, which
# diluted the alt index with exactly the two assets it is measured against.
WRAPPERS = ("wbtc", "weth", "steth", "wsteth", "cbeth", "reth", "wbeth")


def _get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def is_stable(asset):
    a = asset.lower()
    return any(h in a for h in STABLE_HINTS)


def is_wrapper(asset):
    a = asset.lower()
    return any(a == w or a.startswith(w + "_") for w in WRAPPERS)


def fetch_market_caps():
    """Daily market cap for every asset the community tier publishes."""
    cat = _get(CM + "/catalog-v2/asset-metrics?metrics=CapMrktCurUSD&page_size=10000")
    assets = sorted({d["asset"] for d in cat.get("data", [])})
    print("  actifs disponibles : %d" % len(assets))

    caps = {}
    # batched: the API caps the asset list length per request
    batch = 30
    for i in range(0, len(assets), batch):
        chunk = assets[i:i + batch]
        url = (CM + "/timeseries/asset-metrics?assets=" + ",".join(chunk) +
               "&metrics=CapMrktCurUSD&frequency=1d"
               "&start_time=%s&end_time=%s&sort=time&page_size=10000" % (START, END))
        nxt = url
        while nxt:
            d = _get(nxt)
            for r in d.get("data", []):
                v = r.get("CapMrktCurUSD")
                if v:
                    caps.setdefault(r["time"][:10], {})[r["asset"]] = float(v)
            nxt = d.get("next_page_url")
        print("    lot %d-%d : %d dates cumulees"
              % (i, min(i + batch, len(assets)), len(caps)))
    return caps


def build(caps):
    dominance, rotations = {}, {"eth_btc": {}, "alt_eth": {}, "alt_btc": {}}
    basket_log = []
    prev_names = None

    for date in sorted(caps):
        m = caps[date]
        if "btc" not in m or "eth" not in m:
            continue

        # reconstitute: top N alts BY MARKET CAP ON THIS DATE
        alts = {k: v for k, v in m.items()
                if k not in ("btc", "eth")
                and not is_stable(k) and not is_wrapper(k)}
        if len(alts) < 8:
            continue
        top = sorted(alts.items(), key=lambda kv: -kv[1])[:TOP_N]
        names = tuple(sorted(k for k, _ in top))
        alt_cap = sum(v for _, v in top)

        total = sum(m.values())          # includes stablecoins, as dominance does
        dominance[date] = {
            "btc_dom": m["btc"] / total * 100,
            "eth_dom": m["eth"] / total * 100,
            "alt_dom": alt_cap / total * 100,
            "n_assets": len(m),
        }
        rotations["eth_btc"][date] = m["eth"] / m["btc"]
        rotations["alt_eth"][date] = alt_cap / m["eth"]
        rotations["alt_btc"][date] = alt_cap / m["btc"]

        if names != prev_names:
            basket_log.append((date, names))
            prev_names = names

    return dominance, rotations, basket_log


def main():
    os.makedirs(ANALYSIS, exist_ok=True)
    print("Reconstruction des series de rotation")
    caps = fetch_market_caps()
    dominance, rotations, log = build(caps)

    dates = sorted(dominance)
    print("\n  jours produits : %d  (%s -> %s)" % (len(dates), dates[0], dates[-1]))
    print("  recompositions du panier : %d" % len(log))

    with open(os.path.join(ANALYSIS, "dominance.json"), "w", encoding="utf-8") as f:
        json.dump(dominance, f)
    with open(os.path.join(ANALYSIS, "rotations.json"), "w", encoding="utf-8") as f:
        json.dump(rotations, f)

    lines = ["Journal du panier alt - top %d par capitalisation, a chaque date" % TOP_N,
             "Une ligne par changement de composition.", ""]
    for date, names in log:
        lines.append("%s  %s" % (date, ", ".join(names)))
    with open(os.path.join(ANALYSIS, "basket_log.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    for key in ("eth_btc", "alt_eth", "alt_btc"):
        s = rotations[key]
        a, b = s[dates[0]], s[dates[-1]]
        print("  %-9s %.4f -> %.4f   (x%.2f)" % (key, a, b, b / a))

    print("\n  composition finale : %s" % ", ".join(log[-1][1]) if log else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
