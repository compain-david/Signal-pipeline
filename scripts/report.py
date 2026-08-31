#!/usr/bin/env python3
"""
Renders the snapshot into forms something else can actually consume.

The pipeline's biggest weakness was that nothing read it. Dated filenames are
part of that problem: a consumer has to know today's date, construct the path,
and handle the case where today's run has not happened yet. So this writes:

  data/latest.json  - the most recent snapshot at a FIXED path
  data/latest.md    - the same values rendered for the weekly brief

`latest.md` is deliberately shaped around the brief's composite dimensions
rather than this pipeline's internal structure, so it can be pasted or read
directly without translation. Values the brief previously carried as frozen
estimates (Puell, MVRV Z, STH-RP) are the ones surfaced first.
"""

import json

# brief composite dimension -> (signal key, label, formatter)
BRIEF_ROWS = [
    ("sth_realized_price", "Regime · STH-RP", "${:,.0f}"),
    ("mvrv_z_score", "Valuation · MVRV Z", "{:.4f}"),
    ("puell_multiple", "Miners · Puell", "{:.4f}"),
    ("fear_greed", "Sentiment · F&G", "{:.0f}"),
    ("exchange_netflows", "Supply · ETH netflow 7d", "{:,.0f}"),
    ("btc_dominance", "BTC dominance %", "{:.2f}"),
]


def _fmt(payload, spec):
    if not isinstance(payload, dict):
        return "—"
    val = payload.get("signal")
    if val is None:
        return "—"
    try:
        return spec.format(float(val))
    except (TypeError, ValueError):
        return str(val)


def _flag(payload):
    """Never let a stale or missing number read as a live one."""
    if not isinstance(payload, dict):
        return "missing"
    status = payload.get("status")
    if status == "ok":
        return "live"
    if status in ("carried_forward", "stale"):
        return "STALE (%s)" % status
    if status in ("no_api", "no_key", "needs_key", "not_implemented"):
        return "not automated"
    return "FAILED (%s)" % status


def render_markdown(snapshot):
    """Brief-ready summary. Exact values, with provenance on every line."""
    sig = snapshot.get("signals", {})
    h = snapshot.get("health", {})
    gl = snapshot.get("gate_legacy", {})
    gn = snapshot.get("gate_new", {})

    out = []
    out.append("# Signal snapshot — %s" % snapshot.get("date", "?"))
    out.append("")
    out.append("Generated %s · schema v%s"
               % (snapshot.get("fetched_at", "?"), snapshot.get("schema_version", "?")))
    out.append("")

    if h.get("degraded"):
        out.append("> **DEGRADED RUN** — %d failed, %d stale. "
                   "Check provenance before using these numbers."
                   % (h.get("failed", 0), h.get("stale", 0)))
        out.append("")

    out.append("## For the weekly brief composite")
    out.append("")
    out.append("| Dimension | Value | Provenance |")
    out.append("|---|---|---|")
    for key, label, spec in BRIEF_ROWS:
        p = sig.get(key)
        out.append("| %s | %s | %s |" % (label, _fmt(p, spec), _flag(p)))
    out.append("")
    out.append("Not automatable: ETF net flows (no public API), "
               "LTH supply (no free source found).")
    out.append("")

    out.append("## Gates")
    out.append("")
    out.append("- **Legacy (authoritative):** %s of %s — %s"
               % (gl.get("fired"), gl.get("checkable_today"),
                  ", ".join(gl.get("fired_signals") or []) or "none"))
    mode = "AUTHORITATIVE" if gn.get("authoritative") else "shadow"
    out.append("- **10-dimension (%s):** %s of %s fired, threshold %s → %s"
               % (mode, gn.get("fired"), gn.get("checkable"), gn.get("threshold"),
                  "WOULD FIRE" if gn.get("would_fire") else "would not fire"))
    if gn.get("unavailable"):
        out.append("  - not counted: %s" % ", ".join(gn["unavailable"]))
    out.append("")

    out.append("## All signals")
    out.append("")
    out.append("| Signal | Dim | Tier | Value | Vote | Provenance |")
    out.append("|---|---|---|---|---|---|")
    for key, p in sig.items():
        if not isinstance(p, dict):
            continue
        val = p.get("signal")
        out.append("| %s | %s | %s | %s | %s | %s |" % (
            key, p.get("dimension", "—"), p.get("tier", "—"),
            "—" if val is None else val,
            {True: "YES", False: "no", None: "—"}.get(p.get("vote"), "—"),
            _flag(p)))
    out.append("")
    return "\n".join(out)


def write_all(snapshot, data_dir="data"):
    """Write the fixed-path artefacts a consumer can rely on."""
    with open(data_dir + "/latest.json", "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)
    with open(data_dir + "/latest.md", "w", encoding="utf-8") as f:
        f.write(render_markdown(snapshot))
