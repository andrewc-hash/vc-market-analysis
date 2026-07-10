#!/usr/bin/env python3
"""Export a VC-analysis report (raw API JSON) into a clean, readable Markdown file.

Usage:
    python3 scripts/format_report.py <input.json> <output.md>

<input.json> may be either the full API response ({"final_report": {...}}) or a bare
final_report object. Produces: a metadata header + the full narrative report + appendix
tables (weighted scorecard, financial ledger, return scenarios) rendered from the
structured, code-computed data.
"""
import json
import sys

DIMS = [
    ("financial_health", "Financial"),
    ("defensibility", "Defensibility"),
    ("market_urgency", "Mkt Urgency"),
    ("founder_market_fit", "Founder Fit"),
    ("regulatory_alignment", "Regulatory"),
]
LEDGER_COLS = [
    ("startup", "Startup"), ("stage", "Stage"), ("total_raised", "Raised"),
    ("valuation", "Valuation"), ("arr", "ARR"), ("implied_arr_multiple", "Val/ARR"),
    ("yoy_growth", "YoY"), ("ltv_cac", "LTV/CAC"), ("nrr", "NRR"),
    ("burn_multiple", "Burn"), ("rule_of_40", "Rule of 40"),
]


def _md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def format_report(fr: dict) -> str:
    L = []
    sector = (fr.get("sector") or "").strip()
    ranking = fr.get("ranking") or []
    ws = fr.get("weighted_scores") or {}
    mode = (fr.get("analysis_mode") or "vc").upper()
    focal = fr.get("focal_startup") or ""

    # ── Header ──
    L.append("# VC Market Analysis" + (f" — {sector}" if sector else "") + "\n")
    meta = [f"**Mode:** {mode}"]
    if ranking:
        pick = fr.get("recommended_pick") or ranking[0]
        meta.append(f"**Top pick:** {pick}")
    if fr.get("expected_return") is not None:
        lo, hi = fr.get("expected_return_low"), fr.get("expected_return_high")
        if lo is not None and hi is not None and lo != hi:
            meta.append(f"**Prob-weighted return:** {lo}x\u2013{hi}x (gross, mid {fr['expected_return']}x)")
        else:
            meta.append(f"**Prob-weighted return:** {fr['expected_return']}x (gross)")
    if fr.get("thesis_bias"):
        meta.append(f"**Thesis bias:** {fr['thesis_bias']}")
    if fr.get("iterations_to_consensus") is not None:
        meta.append(f"**Consensus in:** {fr['iterations_to_consensus']} round(s)")
    L.append(" · ".join(meta))
    if focal:
        conf = fr.get("focal_confidence")
        label = "Subject" if mode == "FOUNDER" else "Focal"
        L.append(f"\n> **{label} startup:** {focal}" + (f" — _{conf} data confidence_" if conf else ""))
    if fr.get("scope_autoderived"):
        L.append("> _Sector auto-identified from the startup._")
    L.append("\n---\n")

    # ── Narrative ──
    L.append(fr.get("merged_report") or "_(no narrative report)_")

    # ── Appendix A: Scorecard ──
    if ws:
        L.append("\n\n---\n\n## Appendix A — Weighted Underwriting Scorecard\n")
        L.append("_Per-dimension raw scores (0–100) and the code-computed weighted index._\n")
        names = [n for n in ranking if n in ws] or list(ws)
        headers = ["Startup"] + [lbl for _, lbl in DIMS] + ["**Weighted**"]
        rows = []
        for n in names:
            row = ws[n]
            rows.append([n] + [row.get(k, "—") for k, _ in DIMS] + [f"**{row.get('weighted_score', '—')}**"])
        L.append(_md_table(headers, rows))

    # ── Appendix B: Financial Ledger ──
    led = fr.get("financial_ledger") or {}
    if led.get("rows"):
        L.append("\n\n## Appendix B — Financial Ledger\n")
        L.append("_Val/ARR multiple computed in code; incumbents marked `(ref)`._\n")
        headers = [lbl for _, lbl in LEDGER_COLS]
        rows = []
        for r in led["rows"]:
            name = r.get("startup", "")
            if r.get("is_incumbent"):
                name += " (ref)"
            rows.append([name] + [r.get(k, "—") for k, _ in LEDGER_COLS[1:]])
        L.append(_md_table(headers, rows))

    # ── Appendix C: Return Scenarios ──
    sc = fr.get("scenarios") or {}
    if sc.get("scenarios"):
        L.append("\n\n## Appendix C — Probability-Weighted Return\n")
        who = sc.get("startup") or (ranking[0] if ranking else "top pick")
        _lo, _hi = sc.get("expected_return_low"), sc.get("expected_return_high")
        if _lo is not None and _hi is not None and _lo != _hi:
            _val = f"{_lo}x\u2013{_hi}x (gross, mid {sc.get('expected_return')}x)"
        else:
            _val = f"{sc.get('expected_return')}x (gross)"
        L.append(f"_For **{who}**. Expected return (code-computed, before dilution/ownership/fees/time-value): **{_val}**._\n")
        rows = []
        for s in sc["scenarios"]:
            lo, hi = s.get("multiple_low"), s.get("multiple_high")
            mult = "—" if lo is None and hi is None else (f"{lo}x" if lo == hi else f"{lo}x–{hi}x")
            rows.append([str(s.get("label", "")).title(), f"{round((s.get('probability') or 0) * 100)}%", mult])
        L.append(_md_table(["Scenario", "Probability", "Return"], rows))

    return "\n".join(L) + "\n"


def main():
    if len(sys.argv) != 3:
        print("usage: format_report.py <input.json> <output.md>", file=sys.stderr)
        sys.exit(2)
    data = json.load(open(sys.argv[1]))
    fr = data.get("final_report", data) if isinstance(data, dict) else {}
    md = format_report(fr or {})
    with open(sys.argv[2], "w") as f:
        f.write(md)
    print(f"wrote {sys.argv[2]} ({len(md)} chars)")


if __name__ == "__main__":
    main()
