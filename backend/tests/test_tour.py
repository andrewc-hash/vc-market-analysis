"""Token-free tests for the guided-tour artifact (frontend step-through presentation).

Confirms WITHOUT any API call that the tour is assembled with in-code guarantees:
  - _split_report_sections keys `## N. Name` headers as floats (incl. the founder-only
    `## 0.5`, tolerant of `## 0.` vs `## 0 `), missing sections simply absent
  - _tour_fallback_summary extracts the first 1-2 PROSE sentences (headers/tables/
    bullets/bold stripped, ~300-char cap), never empty when the section has prose
  - _validate_tour_summary is the honesty guardrail: every numeric token in a summary
    must appear (comma-stripped) in the section text — no number is born in a summary
  - _beliefs_subsection slices ONLY the "WHAT WE MUST BELIEVE" subsection of §12
  - _generate_tour: beats in coded order, beat skipping, one stubbed LLM call
    (good JSON / bad JSON / raising), per-beat llm-vs-fallback sourcing,
    generated flag semantics, graceful empty tour, JSON-safe output

Run:  python3 backend/tests/test_tour.py
"""
import json
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


# ---------------------------------------------------------------- fixtures
FOUNDER_REPORT = """## 0. Investment Take — Conditional BUILD

**Founder call:** KEEP GOING. Alpha leads the field with $12M ARR and the sector drew $4.5B in 2025.
This third sentence must NOT appear in a two-sentence fallback.

## 0.5 Strategic Repositioning — What to Change, What to Keep

Reposition toward the enterprise wedge; the weakest dimension is regulatory alignment at 48.

## 2. Market Inflection & Bottoms-Up Sizing

| TAM | SAM |
| --- | --- |
| $9B | $2B |

The market inflected in 2025 when mandates landed. Bottoms-up SOM reaches $400M.

## 3. Competitive & Incumbent Encroachment

### Incumbent posture

- BigCo bundles a lookalike.

Three incumbents encroach from adjacent suites. **Alpha** wins on depth.

## 6. Financial Health & Valuation Stress-Test

Alpha carries a $1,200M valuation on $12M ARR, a 100x multiple.

## 7. Weighted Underwriting Index & Scorecard

Alpha ranks first at 74.2 weighted; Beta trails at 61.

## 11. Risk Factors & Mitigants

Platform risk is EXISTENTIAL: a bundled incumbent feature could cap ACVs. Mitigant: depth moat.

## 12. Return Math & Exit Pathways

Expected gross return is 3.5x on a $120M entry post-money.

| Scenario | Multiple |
| --- | --- |
| Base | 4x |

### WHAT WE MUST BELIEVE

We must believe NRR holds above 120% and the mandate wave persists through 2027.

### Conditions Precedent

- Dated condition one.

## 13. Visual Coordinate Market Map

```
(ascii map)
```
"""

VC_REPORT = """## 0. Investment Take

Invest in Alpha below $150M. The binary variable is mandate enforcement.

## 2. Market Inflection & Bottoms-Up Sizing

Sizing prose reaching $400M SOM.

## 3. Competitive & Incumbent Encroachment

Field prose about three incumbents.

## 7. Weighted Underwriting Index & Scorecard

Alpha ranks first at 74.2 weighted.

## 12. Return Math & Exit Pathways

Expected gross return is 3.5x. No beliefs subsection here.
"""


class _FakeSettings:
    judge_model = "stub-judge"

_llm_calls = []

def _patch_llm(content=None, exc=None):
    """Route _generate_tour's single LLM call to a stub; records each call."""
    _llm_calls.clear()
    N.get_settings = lambda: _FakeSettings()
    N._make_llm = lambda model, temperature=0.2, max_tokens=8192: {"model": model}
    def _invoke(llm, messages, max_retries=8):
        _llm_calls.append(messages)
        if exc is not None:
            raise exc
        return types.SimpleNamespace(content=content)
    N._invoke_llm_with_retry = _invoke


print("=" * 72); print("_split_report_sections: float-keyed canonical headers"); print("=" * 72)
secs = N._split_report_sections(FOUNDER_REPORT)
check("keys incl. 0, 0.5, 2, 3, 6, 7, 11, 12, 13",
      {0.0, 0.5, 2.0, 3.0, 6.0, 7.0, 11.0, 12.0, 13.0} <= set(secs), sorted(secs))
check("§0 body is §0's (not §0.5's)",
      "Founder call" in secs[0.0] and "Strategic Repositioning" not in secs[0.0])
check("§0.5 keyed separately", "Strategic Repositioning" in secs[0.5])
check("section bounded before the next header", "Scorecard" not in secs[6.0] and "$1,200M" in secs[6.0])
check("missing section absent (no §9)", 9.0 not in secs)
check("tolerates `## 0 ` without the dot",
      "no dot" in N._split_report_sections("## 0 Take\n\nno dot here.\n").get(0.0, ""))
check("empty/None md -> {}", N._split_report_sections("") == {} and N._split_report_sections(None) == {})
check("prose with no headers -> {}", N._split_report_sections("Just prose. No sections.") == {})


print("=" * 72); print("_tour_fallback_summary: prose-only, 1-2 sentences, capped"); print("=" * 72)
fs = N._tour_fallback_summary(secs[0.0])
check("skips the header line", "Investment Take" not in fs)
check("bold markers stripped", "**" not in fs and "Founder call:" in fs)
check("stops at two sentences", "third sentence" not in fs and "$12M ARR" in fs)
fs2 = N._tour_fallback_summary(secs[2.0])
check("table lines stripped (§2)", "|" not in fs2 and "inflected in 2025" in fs2)
fs3 = N._tour_fallback_summary(secs[3.0])
check("bullets + h3 stripped (§3)", "BigCo bundles" not in fs3 and "Incumbent posture" not in fs3
      and "Three incumbents" in fs3)
check("table/header-only section -> empty",
      N._tour_fallback_summary("## 5. Map\n\n| a | b |\n| --- | --- |\n") == "")
long = "## 1. X\n\nOne single sprawling sentence " + ("that keeps qualifying itself " * 15) + "until it ends."
capped = N._tour_fallback_summary(long)
check("capped ~300 chars with ellipsis", len(capped) <= 300 and capped.endswith("…"), len(capped))
check("None/empty -> empty string", N._tour_fallback_summary(None) == "" and N._tour_fallback_summary("") == "")


print("=" * 72); print("_validate_tour_summary: the number guardrail"); print("=" * 72)
sec = secs[6.0]  # "$1,200M valuation on $12M ARR, a 100x multiple"
check("no-number summary accepted", N._validate_tour_summary("The valuation looks rich.", sec))
check("present number accepted (12)", N._validate_tour_summary("ARR sits at $12M.", sec))
check("comma form matches comma-stripped ('1,200' vs $1,200M)",
      N._validate_tour_summary("Valued at $1,200M.", sec))
check("bare 1200 matches $1,200M after comma-strip", N._validate_tour_summary("Valued near 1200.", sec))
check("sentence-final number tolerated ('...a 100x multiple grew in 2025.' style)",
      N._validate_tour_summary("The multiple is 100.", sec))
check("fabricated number rejected", not N._validate_tour_summary("ARR sits at $37M.", sec))
check("decimal accepted when present (3.5)", N._validate_tour_summary("Returns 3.5x gross.", secs[12.0]))
check("decimal rejected when absent (9.9)", not N._validate_tour_summary("Returns 9.9x gross.", secs[12.0]))
check("empty summary rejected", not N._validate_tour_summary("", sec) and not N._validate_tour_summary(None, sec))
check(">420 chars rejected", not N._validate_tour_summary("y" * 421, sec))
check("420 chars exactly accepted", N._validate_tour_summary("y" * 420, sec))


print("=" * 72); print("_beliefs_subsection: §12 subsection slicing"); print("=" * 72)
bel = N._beliefs_subsection(secs[12.0])
check("finds the subsection (case-insensitive)", "NRR holds above 120%" in bel)
check("stops before the next heading", "Conditions Precedent" not in bel and "Dated condition" not in bel)
check("excludes §12's own prose above it", "3.5x" not in bel)
check("mixed-case phrase found",
      "yes" in N._beliefs_subsection("prose\n\n### What we must believe\n\nyes.\n"))
check("absent phrase -> empty", N._beliefs_subsection("## 12. Return Math\n\nNo beliefs here.") == "")
check("None -> empty", N._beliefs_subsection(None) == "")


print("=" * 72); print("_generate_tour: good LLM JSON (founder report)"); print("=" * 72)
GOOD = {
    "verdict": "The call is to keep going, led by Alpha at $12M ARR.",
    "repositioning": "Reposition toward the enterprise wedge to fix the weakest dimension.",
    "why_now": "Mandates landed in 2025 and the bottoms-up SOM reaches $400M.",
    "field": "Three incumbents encroach while Alpha wins on depth.",
    "scores": "Alpha ranks first at 74.2 weighted, ahead of Beta.",
    "money": "Alpha is valued at $9,999M.",  # fabricated number -> must fall back
    "risks": "Platform risk is existential but mitigated by the depth moat.",
    "returns": "Expected gross return is 3.5x on the stated entry.",
    "beliefs": "The thesis needs NRR above 120% and a persistent mandate wave.",
}
_patch_llm(content="Here you go:\n" + json.dumps(GOOD))
tour = N._generate_tour(FOUNDER_REPORT, "founder")
ids = [s["id"] for s in tour["steps"]]
check("generated=True on parseable JSON", tour["generated"] is True)
check("one LLM call made", len(_llm_calls) == 1)
check("all 9 beats, coded order (money §6 after scores §7)",
      ids == ["verdict", "repositioning", "why_now", "field", "scores",
              "money", "risks", "returns", "beliefs"], ids)
by_id = {s["id"]: s for s in tour["steps"]}
check("visuals per contract",
      by_id["field"]["visual"] == "map" and by_id["scores"]["visual"] == "scorecard"
      and by_id["money"]["visual"] == "ledger" and by_id["returns"]["visual"] == "fundfit"
      and all(by_id[k]["visual"] == "none" for k in ("verdict", "repositioning", "why_now", "risks", "beliefs")))
check("section floats per contract",
      by_id["verdict"]["section"] == 0.0 and by_id["repositioning"]["section"] == 0.5
      and by_id["returns"]["section"] == 12.0 and by_id["beliefs"]["section"] == 12.0
      and isinstance(by_id["why_now"]["section"], float))
check("titles per contract", by_id["verdict"]["title"] == "The Verdict"
      and by_id["beliefs"]["title"] == "What We Must Believe")
check("valid LLM summaries kept as source=llm",
      by_id["verdict"]["source"] == "llm" and by_id["verdict"]["summary"] == GOOD["verdict"])
check("fabricated-number summary demoted to fallback (money)",
      by_id["money"]["source"] == "fallback" and "$9,999M" not in by_id["money"]["summary"]
      and by_id["money"]["summary"] != "")
check("beliefs summary validated against the SLICE (120 present there)",
      by_id["beliefs"]["source"] == "llm")
check("step schema keys exact",
      all(set(s) == {"id", "title", "summary", "section", "visual", "source"} for s in tour["steps"]))
check("tour is JSON-serializable", json.dumps(tour) is not None)

# a number valid in §12 overall but ABSENT from the beliefs slice must not pass for beliefs
_patch_llm(content=json.dumps({**GOOD, "beliefs": "We must believe the 3.5x holds."}))
tour_b = N._generate_tour(FOUNDER_REPORT, "founder")
check("beliefs guardrail uses the sliced text (3.5 not in slice -> fallback)",
      {s["id"]: s for s in tour_b["steps"]}["beliefs"]["source"] == "fallback")

_patch_llm(content=json.dumps({**GOOD, "risks": "x" * 421}))
tour_c = N._generate_tour(FOUNDER_REPORT, "founder")
check("over-length LLM summary demoted to fallback",
      {s["id"]: s for s in tour_c["steps"]}["risks"]["source"] == "fallback")


print("=" * 72); print("_generate_tour: beat skipping (VC report)"); print("=" * 72)
_patch_llm(content=json.dumps({k: "Plain restatement." for k in
                               ("verdict", "why_now", "field", "scores", "returns")}))
vc = N._generate_tour(VC_REPORT, "vc")
vids = [s["id"] for s in vc["steps"]]
check("no §0.5 -> no repositioning beat", "repositioning" not in vids)
check("no §6/§11 -> money and risks skipped", "money" not in vids and "risks" not in vids)
check("no WHAT WE MUST BELIEVE -> beliefs skipped", "beliefs" not in vids)
check("remaining beats keep coded order", vids == ["verdict", "why_now", "field", "scores", "returns"], vids)


print("=" * 72); print("_generate_tour: bad JSON / raising LLM / no sections"); print("=" * 72)
_patch_llm(content="I refuse to emit JSON, sorry.")
bad = N._generate_tour(FOUNDER_REPORT, "founder")
check("unparseable JSON -> generated=False", bad["generated"] is False)
check("unparseable JSON -> full tour of fallbacks",
      len(bad["steps"]) == 9 and all(s["source"] == "fallback" for s in bad["steps"]))
check("fallback summaries are non-empty prose", all(s["summary"] for s in bad["steps"]))

_patch_llm(exc=RuntimeError("provider down"))
boom = N._generate_tour(FOUNDER_REPORT, "founder")
check("raising LLM -> no exception, generated=False", boom["generated"] is False)
check("raising LLM -> full tour of fallbacks",
      len(boom["steps"]) == 9 and all(s["source"] == "fallback" for s in boom["steps"]))

_patch_llm(content=json.dumps(GOOD))
empty = N._generate_tour("Just prose. No recognizable sections at all.", "vc")
check("no recognizable sections -> empty graceful tour",
      empty == {"steps": [], "generated": False})
check("no sections -> LLM never called", len(_llm_calls) == 0)
none_tour = N._generate_tour("", "vc")
check("empty report -> empty graceful tour", none_tour == {"steps": [], "generated": False})
check("empty tour JSON-serializable", json.dumps(empty) is not None)


print("=" * 72)
passed = sum(1 for _, ok in _results if ok); total = len(_results)
print(f"RESULT: {passed}/{total} passed")
if passed != total:
    print("FAILURES:", [n for n, ok in _results if not ok]); sys.exit(1)
print("ALL TOUR TESTS PASS (zero API tokens used).")
