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
    gov = snapshot.get("governance")
    if gov:
        out.append("")
        out.append("**v%s — instrument qui gouverne : `%s`**"
                   % (gov.get("version"), gov.get("governing")))
        out.append("")
        out.append("| Instrument | Statut | Rôle |")
        out.append("|---|---|---|")
        for i in gov.get("instruments", []):
            out.append("| `%s` | %s | %s |"
                       % (i["name"],
                          "**GOUVERNE**" if i["governs"] else "ombre",
                          i["role"]))
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

    lad = snapshot.get("ladder_shadow") or {}
    grd = snapshot.get("gate_grade") or {}

    out.append("## Rotation ladder (shadow — governs nothing)")
    out.append("")
    if lad:
        out.append("| | |")
        out.append("|---|---|")
        out.append("| State | **%s** |" % lad.get("state", "?"))
        out.append("| T | **%s** |" % ("—" if lad.get("t") is None else lad["t"]))
        out.append("| Coverage | %.2f%% (floor %.0f%%) |"
                   % ((lad.get("coverage") or 0) * 100,
                      (lad.get("coverage_floor") or 0) * 100))
        out.append("| Measurable | %s |" % ("yes" if lad.get("measurable") else "**no**"))
        out.append("| Reason | %s |" % lad.get("reason", "—"))
        out.append("")
        # The case that matters: frozen while T already clears the next rung.
        # Without this line a reader sees "state: BTC" and assumes no signal.
        if not lad.get("measurable") and lad.get("t") is not None:
            out.append("> Frozen on coverage, **not** on T. T = %s — read the "
                       "reason above before concluding there is no signal."
                       % lad["t"])
            out.append("")
        out.append("Unsigned strategy update: this ladder does not govern. "
                   "Pending: %s" % "; ".join(lad.get("pending_decisions") or []))
    else:
        out.append("_not computed this run_")
    out.append("")

    out.append("## Gates")
    out.append("")
    mode = "AUTHORITATIVE" if gn.get("authoritative") else "shadow"
    out.append("- **10-dimension (%s):** %s of %s fired, threshold %s → %s"
               % (mode, gn.get("fired"), gn.get("checkable"), gn.get("threshold"),
                  "WOULD FIRE" if gn.get("would_fire") else "would not fire"))
    if grd:
        out.append("  - grade **%s** — %s (%s of %s achievable this run)"
                   % (grd.get("grade"), grd.get("label"), grd.get("score"),
                      grd.get("possible_this_run")))
        if grd.get("capped_for_froth_majority"):
            out.append("  - **capped**: most evidence is froth, so this is a "
                       "sell-side warning, not a rotation call")
    sem = gn.get("semantic") or {}
    if sem.get("reading"):
        out.append("  - reading: %s" % sem["reading"])
    if gn.get("unavailable"):
        out.append("  - not counted: %s" % ", ".join(gn["unavailable"]))
    out.append("- **Legacy (retained for continuity):** %s of %s — %s"
               % (gl.get("fired"), gl.get("checkable_today"),
                  ", ".join(gl.get("fired_signals") or []) or "none"))
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
