"""Token-free tests for the in-code letter gradesheet (visual Grades tab).

Confirms WITHOUT any API call that grades are COMPUTED IN CODE (never LLM-graded):
  - _to_grade maps 0-100 -> letter via the coded GRADE_BANDS rubric (boundaries)
  - _grade_cell returns NR (not F) for an unscored/undisclosed metric
  - _capital_efficiency_score is a coded rubric over Rule-of-40 + burn multiple
  - _compute_gradesheet builds the per-startup gradesheet from the reconciled data:
    ranked order, focal flagged, incumbents excluded, defensibility note names the
    strongest/weakest moat sub-score, capital efficiency = NR when financials undisclosed

Run:  python3 backend/tests/test_gradesheet.py
"""
import os, sys, types

def _stub(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m

_stub("langchain_anthropic", ChatAnthropic=object)
_stub("langchain_google_genai", ChatGoogleGenerativeAI=object)
_stub("langchain_groq", ChatGroq=object)
_stub("langchain_openai", ChatOpenAI=object)
_lg = _stub("langgraph"); _lg.prebuilt = _stub("langgraph.prebuilt", create_react_agent=lambda *a, **k: None)
_lc = _stub("langchain_core"); _lc.tools = _stub("langchain_core.tools", tool=lambda f=None, **k: (f if f else (lambda g: g)))
_stub("tavily", TavilyClient=object)
_stub("pydantic_settings", BaseSettings=object)
_stub("pydantic", BaseModel=object, Field=lambda default=None, **k: default)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.graph import nodes as N

_results = []
def check(name, cond, detail=""):
    _results.append((name, bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


print("=" * 72); print("_to_grade: coded band mapping"); print("=" * 72)
for score, want in [(100, "A+"), (90, "A+"), (89, "A"), (85, "A"), (80, "A-"),
                    (74, "B"), (70, "B"), (55, "C"), (40, "D"), (34, "F"), (0, "F")]:
    check(f"{score} -> {want}", N._to_grade(score) == want, N._to_grade(score))
check("None -> None (unscored)", N._to_grade(None) is None)
check("numeric string coerced ('88' -> A)", N._to_grade("88") == "A")
check("out-of-range clamped (150 -> A+, -5 -> F)", N._to_grade(150) == "A+" and N._to_grade(-5) == "F")


print("=" * 72); print("_grade_cell: NR for unscored, never F"); print("=" * 72)
c = N._grade_cell(72)
check("scored cell has letter+score+note", c["letter"] == "B" and c["score"] == 72.0 and "72" in c["note"])
nr = N._grade_cell(None)
check("unscored -> NR, not F", nr["letter"] == "NR" and nr["score"] is None)


print("=" * 72); print("_capital_efficiency_score: coded R40 + burn rubric"); print("=" * 72)
check("R40=45 (>=40 -> 100) + burn 2.0x (->60) => avg 80",
      N._capital_efficiency_score({"rule_of_40": "45", "burn_multiple": "2.0x"}) == 80.0)
check("R40 only (20 -> 50)", N._capital_efficiency_score({"rule_of_40": "20"}) == 50.0)
check("burn only (0.8x -> 100)", N._capital_efficiency_score({"burn_multiple": "0.8x"}) == 100.0)
check("burn worst (>3.5x -> 20)", N._capital_efficiency_score({"burn_multiple": "4.0x"}) == 20.0)
check("neither disclosed -> None (NR, not F)",
      N._capital_efficiency_score({"rule_of_40": "Not Disclosed", "burn_multiple": "Not Disclosed"}) is None)
check("no row -> None", N._capital_efficiency_score(None) is None)


print("=" * 72); print("_financial_health_grade: reconciled FH + ledger capital-efficiency"); print("=" * 72)
check("FH dim + ledger R40/burn averaged (80 & eff 80 -> 80 -> A-)",
      N._financial_health_grade({"financial_health": 80}, {"rule_of_40": "45", "burn_multiple": "2.0x"})["letter"] == "A-")
check("degrades to the FH dimension when ledger undisclosed (45 -> D+)",
      N._financial_health_grade({"financial_health": 45}, None)["letter"] == "D+")
check("NR only when both FH and ledger absent",
      N._financial_health_grade({}, None)["letter"] == "NR")


print("=" * 72); print("_traction_score: stage-adjusted ledger rubric"); print("=" * 72)
s, z = N._traction_score({"stage": "Series B", "yoy_growth": "100%", "nrr": "110%", "arr": "$10M"})
check("Series B: growth 100/target100=100, NRR 110->80, rev-exists 100 -> ~93",
      not z and 92 <= s <= 94)
check("affirmative $0 ARR -> disclosed_zero (-> F)", N._traction_score({"arr": "$0"})[1] is True)
check("'pre-revenue' text -> disclosed_zero", N._traction_score({"stage": "Seed, pre-revenue"})[1] is True)
check("all traction undisclosed -> (None, False) => NR not F",
      N._traction_score({"stage": "Series A", "arr": "Not Disclosed", "yoy_growth": "Not Disclosed"}) == (None, False))
sa, _ = N._traction_score({"stage": "Series A", "yoy_growth": "175%"})
check("stage-normalized growth (175% at Series A target 175 -> 100 -> A+)", N._to_grade(sa) == "A+")


print("=" * 72); print("_compute_gradesheet: 6 screenshot cards, in code"); print("=" * 72)
RESOLVED = {
    "Alpha": {"financial_health": 80, "defensibility": 70, "market_urgency": 90,
              "founder_market_fit": 60, "regulatory_alignment": 50},
    "Beta": {"financial_health": 45, "defensibility": 40, "market_urgency": 55,
             "founder_market_fit": 50, "regulatory_alignment": 45},
}
MOATS = {"Alpha": {"economies_of_scale": 40, "differentiated_technology": 90,
                   "network_effects": 50, "brand_power": 100}}
WEIGHTED = {"Alpha": {"weighted_score": 74.0}, "Beta": {"weighted_score": 45.0}}
LEDGER = {"rows": [
    {"startup": "Alpha", "stage": "Series B", "rule_of_40": "45", "burn_multiple": "2.0x",
     "yoy_growth": "100%", "nrr": "110%", "arr": "$10M", "is_incumbent": False},
    {"startup": "BigCo Inc", "is_incumbent": True},  # incumbent — must be excluded
]}
gs = N._compute_gradesheet(RESOLVED, MOATS, WEIGHTED, LEDGER, ["Alpha", "Beta"], focal="Beta")

EXPECT_KEYS = ["market_urgency", "product_depth", "regulatory_alignment",
               "financial_health", "traction_gtm", "founder_market_fit"]
check("6 cards = the honest screenshot set", [c["key"] for c in gs["criteria"]] == EXPECT_KEYS)
check("no repo-only cards leaked (no capital_efficiency/defensibility keys)",
      not any(c["key"] in ("capital_efficiency", "defensibility") for c in gs["criteria"]))
check("labels renamed honestly (Product & Tech Depth, Regulatory & Compliance)",
      any(c["label"] == "Product & Tech Depth" for c in gs["criteria"])
      and any(c["label"] == "Regulatory & Compliance" for c in gs["criteria"]))
check("every criterion carries its coded calculation", all(c.get("calculation") for c in gs["criteria"]))
names = [s["name"] for s in gs["startups"]]
check("ranked order (Alpha first), incumbent BigCo excluded", names == ["Alpha", "Beta"])
alpha = gs["startups"][0]
check("Alpha Market & Timing = market_urgency 90 -> A+", alpha["cells"]["market_urgency"]["letter"] == "A+")
check("Alpha Product & Tech Depth = differentiated_technology 90 -> A+",
      alpha["cells"]["product_depth"]["letter"] == "A+" and "diff-tech" in alpha["cells"]["product_depth"]["note"])
check("Alpha Regulatory & Compliance = regulatory_alignment 50 -> C-",
      alpha["cells"]["regulatory_alignment"]["letter"] == "C-")
check("Alpha Financial Health & Cap Eff (FH 80 + eff 80 -> 80 -> A-)",
      alpha["cells"]["financial_health"]["letter"] == "A-")
check("Alpha Traction graded from ledger (not NR/F)",
      alpha["cells"]["traction_gtm"]["letter"] not in ("NR", "F"))
check("Alpha Founder-Market Fit = 60 -> C+", alpha["cells"]["founder_market_fit"]["letter"] == "C+")
beta = gs["startups"][1]
check("Beta Financial Health degrades to FH dim (45, no ledger -> D+)",
      beta["cells"]["financial_health"]["letter"] == "D+")
check("Beta Traction = NR (no ledger row, undisclosed != F)",
      beta["cells"]["traction_gtm"]["letter"] == "NR")
check("focal flagged (Beta), non-focal not",
      beta["is_focal"] is True and alpha["is_focal"] is False)
check("empty inputs -> empty startups, no crash",
      N._compute_gradesheet({}, {}, {}, None, [], "")["startups"] == [])


print("=" * 72)
passed = sum(1 for _, ok in _results if ok); total = len(_results)
print(f"RESULT: {passed}/{total} passed")
if passed != total:
    print("FAILURES:", [n for n, ok in _results if not ok]); sys.exit(1)
print("ALL GRADESHEET TESTS PASS (zero API tokens used).")
