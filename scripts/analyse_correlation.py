#!/usr/bin/env python3
"""
Measures how independent the Tier A signals actually are, and what threshold
that implies.

Why this exists
---------------
The spec set 5-of-9 as "proportionally similar to the old 4/7" (56% vs 57%).
That reasoning assumes both bases are equally correlated. They are not - the
whole point of the MECE rework was to remove correlation. This script measures
the correlation instead of assuming it.

Method
------
1. Pull multi-year daily history for every Tier A signal that has one.
2. Align on common dates, correlate the DAILY CHANGES rather than levels.
   Levels of trending series are spuriously correlated (both drift with price);
   changes measure whether signals move together for real reasons.
3. Compute the effective number of independent signals via the participation
   ratio of the correlation matrix eigenvalues:

       N_eff = (Σλ)² / Σλ²

   For perfectly independent signals N_eff = N. For perfectly correlated
   signals N_eff = 1. This is the standard measure of how many genuinely
   distinct things you are actually observing.
4. Convert a threshold into the independent-evidence it demands, so 4/9 and
   5/9 can be compared on a common scale.

Run: python scripts/analyse_correlation.py
Uses 5 BGeometrics requests (10/hour budget) - do not run beside a pipeline run.
"""

import json
import math
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

UA = {"User-Agent": "signal-pipeline/4.0 (personal use)"}
BG = "https://bitcoin-data.com/api/v1"


CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "analysis", ".cache")


def _get(url):
    """Cached fetch. BGeometrics allows 10 requests/hour, and re-running an
    analysis should not cost budget - the histories are daily and immutable."""
    os.makedirs(CACHE, exist_ok=True)
    key = "".join(c if c.isalnum() else "_" for c in url)[-120:]
    path = os.path.join(CACHE, key + ".json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        data = json.loads(r.read())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return data


# -- data collection ---------------------------------------------------------

def bg_series(endpoint, field):
    """Full daily history from BGeometrics -> {date: value}."""
    rows = _get(f"{BG}/{endpoint}")
    out = {}
    for r in rows:
        d, v = r.get("d"), r.get(field)
        if d and v is not None:
            try:
                out[d] = float(v)
            except (TypeError, ValueError):
                pass
    return out


def fear_greed_series():
    """alternative.me full history. limit=0 returns everything."""
    import datetime
    data = _get("https://api.alternative.me/fng/?limit=0&format=json")
    out = {}
    for e in data.get("data", []):
        try:
            ts = int(e["timestamp"])
            d = datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
            out[d] = float(e["value"])
        except (KeyError, TypeError, ValueError):
            pass
    return out


# -- statistics (pure python) ------------------------------------------------

def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = math.sqrt(sum((a - mx) ** 2 for a in xs))
    dy = math.sqrt(sum((b - my) ** 2 for b in ys))
    return num / (dx * dy) if dx and dy else 0.0


def jacobi_eigenvalues(m, iterations=100):
    """Eigenvalues of a small symmetric matrix. Enough for a 6-9 signal matrix."""
    n = len(m)
    a = [row[:] for row in m]
    for _ in range(iterations):
        off = 0.0
        p = q = 0
        best = 0.0
        for i in range(n):
            for j in range(i + 1, n):
                off += a[i][j] ** 2
                if abs(a[i][j]) > best:
                    best, p, q = abs(a[i][j]), i, j
        if off < 1e-12:
            break
        app, aqq, apq = a[p][p], a[q][q], a[p][q]
        if abs(apq) < 1e-15:
            break
        theta = 0.5 * math.atan2(2 * apq, app - aqq)
        c, s = math.cos(theta), math.sin(theta)
        for k in range(n):
            akp, akq = a[k][p], a[k][q]
            a[k][p] = c * akp + s * akq
            a[k][q] = -s * akp + c * akq
        for k in range(n):
            apk, aqk = a[p][k], a[q][k]
            a[p][k] = c * apk + s * aqk
            a[q][k] = -s * apk + c * aqk
    return sorted((a[i][i] for i in range(n)), reverse=True)


def effective_independent_count(corr):
    """Participation ratio: how many genuinely distinct signals are present."""
    eig = [max(e, 0.0) for e in jacobi_eigenvalues(corr)]
    total = sum(eig)
    sq = sum(e * e for e in eig)
    return (total * total / sq) if sq else float(len(corr)), eig


def daily_changes(series, dates):
    """Correlate changes, not levels - levels of trending series correlate
    spuriously because both drift with price."""
    out = []
    for i in range(1, len(dates)):
        prev, cur = series[dates[i - 1]], series[dates[i]]
        out.append(cur - prev)
    return out


def main():
    print("Fetching histories...")
    sources = {}
    specs = [
        ("mvrv_z_score", lambda: bg_series("mvrv-zscore", "mvrvZscore")),
        ("nvt", lambda: bg_series("nvt", "nvt")),
        ("stablecoin_supply_ratio", lambda: bg_series("ssr", "ssrStablecoin")),
        ("sth_realized_price", lambda: bg_series("sth-realized-price",
                                                 "sthRealizedPrice")),
        ("puell_multiple", lambda: bg_series("puell-multiple", "puellMultiple")),
        ("fear_greed", fear_greed_series),
    ]
    for name, fn in specs:
        try:
            s = fn()
            sources[name] = s
            print("  %-24s %d points" % (name, len(s)))
        except Exception as e:
            print("  %-24s FAILED: %s" % (name, str(e)[:70]))

    if len(sources) < 3:
        print("\nInsufficient sources fetched - likely rate limited. Retry later.")
        return 1

    names = sorted(sources)
    common = set(sources[names[0]])
    for n in names[1:]:
        common &= set(sources[n])
    dates = sorted(common)
    print("\nCommon dates: %d  (%s -> %s)" % (len(dates), dates[0], dates[-1]))

    changes = {n: daily_changes(sources[n], dates) for n in names}

    print("\n=== Correlation of DAILY CHANGES ===\n")
    hdr = "%-24s" % ""
    for n in names:
        hdr += "%9s" % n[:8]
    print(hdr)
    corr = []
    for a in names:
        row = []
        line = "%-24s" % a[:24]
        for b in names:
            c = 1.0 if a == b else pearson(changes[a], changes[b])
            row.append(c)
            line += "%9.2f" % c
        corr.append(row)
        print(line)

    n = len(names)
    offdiag = [corr[i][j] for i in range(n) for j in range(i + 1, n)]
    avg_abs = sum(abs(c) for c in offdiag) / len(offdiag)
    n_eff, eig = effective_independent_count(corr)

    print("\n=== Independence ===\n")
    print("  signals measured          : %d" % n)
    print("  mean |correlation|        : %.3f" % avg_abs)
    print("  max  |correlation|        : %.3f" % max(abs(c) for c in offdiag))
    print("  eigenvalues               : %s" % ", ".join("%.2f" % e for e in eig))
    print("  EFFECTIVE independent     : %.2f of %d  (%.0f%%)"
          % (n_eff, n, n_eff / n * 100))

    ratio = n_eff / n
    print("\n=== Threshold implication ===\n")
    print("  Each vote carries ~%.2f independent observations." % ratio)
    for thr in (4, 5, 6):
        print("    %d of 9  ->  %.2f independent observations required"
              % (thr, thr * ratio))
    print("\n  Old gate: 4 of 7, where dominance/ASI/TOTAL3 were ~1 observation")
    print("  in 3 slots, so 7 slots held roughly 5 independent signals.")
    print("  4 of 7 therefore demanded ~%.2f independent observations." % (4 * 5 / 7))

    try:
        backtest(sources, dates)
    except KeyError as e:
        print("\nBacktest skipped, missing series: %s" % e)
    return 0


if __name__ == "__main__":
    sys.exit(main())


# -- historical dry run ------------------------------------------------------

def backtest(sources, dates):
    """How often would each threshold have fired historically?

    Only the Tier A signals with retrievable history are testable: MVRV Z,
    NVT, F&G, SSR. A threshold that never fires is useless; one that fires
    constantly is noise. This bounds the sensible range.
    """
    print("\n\n=== HISTORICAL DRY RUN ===\n")
    mvrv, nvt, fg, ssr = (sources["mvrv_z_score"], sources["nvt"],
                          sources["fear_greed"],
                          sources["stablecoin_supply_ratio"])

    nvt_hist, ssr_hist, fired_counts, rows = [], [], {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}, []
    for i, d in enumerate(dates):
        nvt_hist.append(nvt[d])
        ssr_hist.append(ssr[d])
        if i < 90:
            continue
        votes = 0
        votes += 1 if mvrv[d] > 3.0 else 0
        votes += 1 if nvt[d] > sum(nvt_hist[-90:]) / 90 else 0
        votes += 1 if fg[d] > 60 else 0
        votes += 1 if ssr[d] < ssr_hist[-31] else 0
        fired_counts[votes] += 1
        rows.append((d, votes))

    total = len(rows)
    print("  Testable Tier A signals: 4 (MVRV Z, NVT, F&G, SSR)")
    print("  Days evaluated: %d  (%s -> %s)\n" % (total, rows[0][0], rows[-1][0]))
    print("  votes   days     %% of history")
    for v in sorted(fired_counts):
        pct = fired_counts[v] / total * 100
        print("    %d   %6d   %5.1f%%  %s" % (v, fired_counts[v], pct,
                                              "#" * int(pct / 2)))
    print("\n  Cumulative 'would fire at >= N of 4':")
    for thr in (1, 2, 3, 4):
        n = sum(c for v, c in fired_counts.items() if v >= thr)
        print("    >=%d of 4 : %5.1f%% of days" % (thr, n / total * 100))
    print("\n  Scaled to the 9-signal gate (same per-signal hit rate):")
    for thr in (4, 5, 6):
        equiv = thr * 4 / 9
        n = sum(c for v, c in fired_counts.items() if v >= math.ceil(equiv))
        print("    %d of 9 ~ %.1f of 4 -> would fire ~%.1f%% of days"
              % (thr, equiv, n / total * 100))
