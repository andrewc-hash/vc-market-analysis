"""Token-free tests for the longitudinal run-delta engine (services/delta.py).

compute_run_delta is PURE CODE; validate_prediction_audit enforces the deadline
logic in code over the grading LLM's output. No LLM deps imported at module scope.

Run:  python3 backend/tests/test_delta.py
"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services import delta as D

_results = []
def check(name, cond, detail=""):
    _results.append((name, bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))

print("=" * 72); print("compute_run_delta"); print("=" * 72)

PREV = {
    "ranking": ["Abridge", "Freed AI", "DeepScribe", "Astrix"],
    "weighted_scores": {
        "Abridge": {"weighted_score": 71.2}, "Freed AI": {"weighted_score": 65.0},
        "DeepScribe": {"weighted_score": 58.4}, "Astrix": {"weighted_score": 55.1},
    },
    "financial_ledger": {"rows": [
        {"startup": "Abridge", "valuation": "$850M", "total_raised": "$210M"},
        {"startup": "Freed AI", "valuation": "Not Disclosed", "total_raised": "$14M"},
    ]},
    "acquisitions": [{"target": "Nabla", "acquirer": "Epic", "value": "$300M"}],
    "recommended_pick": "Abridge",
    "expected_return": 6.4,
}
NEW = {
    "ranking": ["Freed AI", "Abridge", "Tali AI"],   # Freed up, DeepScribe+Astrix out, Tali in
    "weighted_scores": {
        "Freed AI": {"weighted_score": 70.5}, "Abridge": {"weighted_score": 70.8},
        "Tali AI": {"weighted_score": 51.0},
    },
    "financial_ledger": {"rows": [
        {"startup": "Abridge", "valuation": "$1.2B", "total_raised": "$460M"},
        {"startup": "Freed AI", "valuation": "$120M", "total_raised": "$14M"},
    ]},
    "acquisitions": [
        {"target": "Nabla", "acquirer": "Epic", "value": "$300M"},
        {"target": "Astrix", "acquirer": "Cisco", "value": "$400M"},
    ],
    "recommended_pick": "Freed AI",
    "expected_return": 7.1,
}
d = D.compute_run_delta(PREV, NEW)
check("returns a delta dict", d is not None)
check("entered = Tali AI", d and d["entered"] == ["Tali AI"])
check("exited = DeepScribe + Astrix", d and set(d["exited"]) == {"DeepScribe", "Astrix"})
mv = {m["startup"]: m for m in (d["movers"] if d else [])}
check("Freed rank 2->1 with +5.5 score delta",
      "Freed AI" in mv and mv["Freed AI"]["prev_rank"] == 2 and mv["Freed AI"]["new_rank"] == 1
      and mv["Freed AI"]["score_delta"] == 5.5)
check("biggest score mover sorts first", d and d["movers"][0]["startup"] == "Freed AI")
lc = {(c["startup"], c["field"]): c for c in (d["ledger_changes"] if d else [])}
check("Abridge valuation 850->1200 caught",
      ("Abridge", "valuation") in lc and lc[("Abridge", "valuation")]["new_musd"] == 1200.0)
check("unchanged raised (Freed 14->14) not flagged", ("Freed AI", "total_raised") not in lc)
check("Not-Disclosed -> disclosed NOT flagged as a change (no prev value)",
      ("Freed AI", "valuation") not in lc)
check("new acquisition = Astrix<-Cisco only",
      d and len(d["new_acquisitions"]) == 1 and d["new_acquisitions"][0]["target"] == "Astrix")
check("pick change detected", d and d["pick_changed"] and d["new_pick"] == "Freed AI")
check("EV carried", d and d["prev_expected_return"] == 6.4 and d["new_expected_return"] == 7.1)

check("both sides empty -> None", D.compute_run_delta({}, {}) is None)
check("non-dict -> None", D.compute_run_delta(None, NEW) is None)
d2 = D.compute_run_delta({"ranking": ["A"], "weighted_scores": {"A": {"weighted_score": 50}}},
                         {"ranking": ["A"], "weighted_scores": {"A": {"weighted_score": 50}}})
check("no-change run yields empty movers", d2 is not None and d2["movers"] == [] and not d2["pick_changed"])

# Name normalization: "Freed AI" vs "Freed, AI Inc." must match, not double-count.
d3 = D.compute_run_delta(
    {"ranking": ["Freed AI"], "weighted_scores": {"Freed AI": {"weighted_score": 60}}},
    {"ranking": ["Freed, AI Inc."], "weighted_scores": {"Freed, AI Inc.": {"weighted_score": 62}}})
check("norm-name matching (no false enter/exit)", d3 and d3["entered"] == [] and d3["exited"] == [])

print("=" * 72); print("validate_prediction_audit (deadline logic in code)"); print("=" * 72)

TODAY = date(2026, 7, 9)
raw = {"predictions": [
    {"prediction": "Signs 5 hospital pilots", "metric": "pilots", "deadline": "2026-03",
     "status": "broken", "evidence": "no pilot announcements found"},
    {"prediction": "Series A by Q1", "metric": "round", "deadline": "2027-01",
     "status": "broken", "evidence": ""},           # future deadline: broken -> pending
    {"prediction": "Epic ships native scribe", "metric": "GA", "deadline": "2026-01",
     "status": "pending", "evidence": ""},           # passed deadline: pending -> unresolved
    {"prediction": "NRR above 110%", "metric": "NRR", "deadline": "",
     "status": "WEIRD", "evidence": ""},              # bad status -> unresolved (no deadline)
    {"prediction": "", "status": "validated"},        # dropped: empty
    "not-a-dict",
]}
rows = D.validate_prediction_audit(raw, TODAY)
check("keeps 4 valid rows", rows is not None and len(rows) == 4)
by = {r["prediction"]: r for r in rows or []}
check("passed-deadline broken stays broken", by.get("Signs 5 hospital pilots", {}).get("status") == "broken")
check("future-deadline 'broken' overridden to pending", by.get("Series A by Q1", {}).get("status") == "pending")
check("passed-deadline 'pending' overridden to unresolved",
      by.get("Epic ships native scribe", {}).get("status") == "unresolved")
check("bad status coerced to unresolved", by.get("NRR above 110%", {}).get("status") == "unresolved")
check("validated survives regardless of deadline",
      (D.validate_prediction_audit({"predictions": [
          {"prediction": "p", "deadline": "2027-05", "status": "validated", "evidence": "e"}]}, TODAY)
       or [{}])[0].get("status") == "validated")
check("cap at %d rows" % D._MAX_PREDICTIONS,
      len(D.validate_prediction_audit(
          {"predictions": [{"prediction": f"p{i}", "status": "pending"} for i in range(20)]}, TODAY) or []) == D._MAX_PREDICTIONS)
check("None on junk", D.validate_prediction_audit(None, TODAY) is None
      and D.validate_prediction_audit({"predictions": "x"}, TODAY) is None)

check("_deadline_passed: 2026-06 passed vs 2026-07", D._deadline_passed("2026-06", TODAY) is True)
check("_deadline_passed: same month NOT passed", D._deadline_passed("2026-07", TODAY) is False)
check("_deadline_passed: garbage -> None", D._deadline_passed("soon", TODAY) is None
      and D._deadline_passed("2026-13", TODAY) is None)

print("=" * 72); print("_slice_sections"); print("=" * 72)
MD = "## 0. Take\nbluf\n\n## 4. Thesis\npredict\n\n## 11. Risks\nkill\n\n## 12. Returns\nmath\n\n## 13. Map\nascii"
sl = D._slice_sections(MD, (0, 4, 11, 12))
check("keeps wanted sections", all(s in sl for s in ("bluf", "predict", "kill", "math")))
check("drops others", "ascii" not in sl)
check("empty md -> empty", D._slice_sections("", (0,)) == "")

print("=" * 72)
passed = sum(1 for _, ok in _results if ok); total = len(_results)
print(f"RESULT: {passed}/{total} passed")
if passed != total:
    print("FAILURES:", [n for n, ok in _results if not ok]); sys.exit(1)
print("ALL DELTA TESTS PASS (zero API tokens used).")
