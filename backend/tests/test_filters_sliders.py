"""Token-free tests that the sliders and filters actually work.

These test the REAL functions from app.graph.nodes / app.graph.prompts by stubbing
the heavy LLM deps (langchain/langgraph/tavily/pydantic) so nothing is installed or
called — ZERO API tokens. They verify the *wiring*:

  SLIDERS  — dimension weights deterministically drive the ranking (computed in code),
             are relative/normalized, and reach the analyst + judge as context.
  FILTERS  — stage & geography scope the researcher's search instructions and reach
             the analysts; thesis_bias swaps the judge persona.

Run:  python3 backend/tests/test_filters_sliders.py
"""
import os, sys, types

# --------------------------------------------------------------------------- #
#  Stub the heavy imports so the real app modules import with no deps / no calls
# --------------------------------------------------------------------------- #
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
_lg = _stub("langgraph")
_lg.prebuilt = _stub("langgraph.prebuilt", create_react_agent=lambda *a, **k: None)
_lc = _stub("langchain_core")
_lc.tools = _stub("langchain_core.tools", tool=lambda f=None, **k: (f if f else (lambda g: g)))
_stub("tavily", TavilyClient=object)
_stub("pydantic_settings", BaseSettings=object)
_stub("pydantic", BaseModel=object, Field=lambda default=None, **k: default)

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BACKEND)
sys.path.insert(0, BACKEND)

from app.graph import nodes as N
from app.graph import prompts as P

DIMS = ["financial_health", "defensibility", "market_urgency", "founder_market_fit", "regulatory_alignment"]
RESOLVED = {  # the judge's raw 0-100 per-dimension scores
    "FortifyAI":   {"financial_health": 95, "defensibility": 30, "market_urgency": 60, "founder_market_fit": 40, "regulatory_alignment": 20},
    "KernelGuard": {"financial_health": 55, "defensibility": 95, "market_urgency": 90, "founder_market_fit": 95, "regulatory_alignment": 85},
    "MidMoat":     {"financial_health": 75, "defensibility": 60, "market_urgency": 75, "founder_market_fit": 65, "regulatory_alignment": 50},
    "RegShield":   {"financial_health": 50, "defensibility": 55, "market_urgency": 88, "founder_market_fit": 90, "regulatory_alignment": 95},
}
W_DEFAULT = {"financial_health": 20, "defensibility": 30, "market_urgency": 20, "founder_market_fit": 15, "regulatory_alignment": 15}
W_FIN     = {"financial_health": 60, "defensibility": 10, "market_urgency": 10, "founder_market_fit": 10, "regulatory_alignment": 10}
W_DEF     = {"financial_health": 10, "defensibility": 60, "market_urgency": 10, "founder_market_fit": 10, "regulatory_alignment": 10}

_results = []
def check(name, cond, detail=""):
    _results.append((name, bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))

def base_state(**over):
    s = {"market_prompt": "Analyze the runtime security sector for AI agents.",
         "sector": "Runtime Security", "stage": "All Stages", "geography": "Global",
         "thesis_bias": "Base", "dimension_weights": dict(W_DEFAULT)}
    s.update(over)
    return s

print("=" * 72)
print("SLIDERS — dimension weights")
print("=" * 72)

# S1: weights deterministically change the RANKING
_, r_def = N._compute_weighted_scores(RESOLVED, W_DEFAULT)
_, r_fin = N._compute_weighted_scores(RESOLVED, W_FIN)
_, r_dfn = N._compute_weighted_scores(RESOLVED, W_DEF)
print(f"   default -> {r_def}")
print(f"   fin_hvy -> {r_fin}")
print(f"   def_hvy -> {r_dfn}")
check("S1 financial-heavy weights make FortifyAI #1", r_fin[0] == "FortifyAI", f"#1={r_fin[0]}")
check("S1 defensibility-heavy keeps KernelGuard #1", r_dfn[0] == "KernelGuard", f"#1={r_dfn[0]}")
check("S1 changing weights changes the ranking", r_fin != r_dfn)

# S1b: the weighted SCORES actually differ across profiles (not just labels)
sd, _ = N._compute_weighted_scores(RESOLVED, W_DEFAULT)
sf, _ = N._compute_weighted_scores(RESOLVED, W_FIN)
check("S1b weighted score for FortifyAI moves with weights",
      sd["FortifyAI"]["weighted_score"] != sf["FortifyAI"]["weighted_score"],
      f"{sd['FortifyAI']['weighted_score']} vs {sf['FortifyAI']['weighted_score']}")

# S2: weights are RELATIVE / normalized
check("S2 scale-invariant ({10..} == {20..})",
      N._normalize_weights({k: 10 for k in DIMS}) == N._normalize_weights({k: 20 for k in DIMS}))
check("S2 normalized weights sum to 1.0", abs(sum(N._normalize_weights(W_DEFAULT).values()) - 1.0) < 1e-9)
check("S2 all-zero weights -> equal fallback (no crash)",
      abs(sum(N._normalize_weights({k: 0 for k in DIMS}).values()) - 1.0) < 1e-9)

# S3: weights reach the ANALYST and the JUDGE as context
amsg = N._build_analyst_user_message(base_state())
check("S3 analyst message contains the (normalized) weight block",
      "Defensibility & IP Moat: 30%" in amsg and "Financial Health & Capital Efficiency: 20%" in amsg)
check("S3 analyst told NOT to compute the weighted total",
      "do NOT compute the weighted" in amsg)
nodes_src = open(os.path.join(BACKEND, "app/graph/nodes.py")).read()
check("S3 judge_node injects the weight block (_format_weights_block in judge msg)",
      "_format_weights_block(state.get('dimension_weights'))" in nodes_src)
check("S3 weighting is applied in code (compile_report reconciles analysts -> _compute_weighted_scores)",
      "_compute_weighted_scores(resolved_scores, weights)" in nodes_src
      and "_extract_resolved_scores(analyst_a, analyst_b" in nodes_src)

# S4: default weights identical across the 3 sources
def read(p): return open(os.path.join(ROOT, p)).read()
schema_src = read("backend/app/models/schemas.py")
form_src = read("frontend/src/components/ResearchForm.tsx")
for dim, val in [("financial_health", 20), ("defensibility", 30), ("market_urgency", 20),
                 ("founder_market_fit", 15), ("regulatory_alignment", 15)]:
    in_schema = f"{dim}: int = Field(default={val}" in schema_src
    in_nodes = N.DEFAULT_WEIGHTS[dim] == val
    in_form = f"{dim}: {val}" in form_src
    check(f"S4 default {dim}={val} consistent (schema/nodes/frontend)",
          in_schema and in_nodes and in_form,
          f"schema={in_schema} nodes={in_nodes} frontend={in_form}")

print("=" * 72)
print("FILTERS — stage")
print("=" * 72)
rmsg_seed = N._build_researcher_user_message(base_state(stage="Seed"))
rmsg_all = N._build_researcher_user_message(base_state(stage="All Stages"))
check("F1 stage=Seed adds SCOPE BY STAGE to researcher queries",
      "SCOPE BY STAGE" in rmsg_seed and "Seed" in rmsg_seed)
check("F1 stage=All Stages adds NO stage scoping (correct no-op)",
      "SCOPE BY STAGE" not in rmsg_all)
check("F2 stage reaches the analyst assignment",
      "Series B" in N._build_analyst_user_message(base_state(stage="Series B")))

print("=" * 72)
print("FILTERS — geography")
print("=" * 72)
rmsg_eu = N._build_researcher_user_message(base_state(geography="EU-Only"))
rmsg_glob = N._build_researcher_user_message(base_state(geography="Global"))
check("F3 geography=EU-Only adds SCOPE BY GEOGRAPHY",
      "SCOPE BY GEOGRAPHY" in rmsg_eu and "EU-Only" in rmsg_eu)
check("F3 geography=Global adds NO geo scoping (correct no-op)",
      "SCOPE BY GEOGRAPHY" not in rmsg_glob)
check("F4 geography reaches the analyst assignment",
      "Asia-Pacific" in N._build_analyst_user_message(base_state(geography="Asia-Pacific")))

print("=" * 72)
print("FILTERS — thesis bias")
print("=" * 72)
bear = P.get_judge_system_prompt("Bear")
base = P.get_judge_system_prompt("Base")
bull = P.get_judge_system_prompt("Bull")
junk = P.get_judge_system_prompt("garbage")
_BASE_PERSONA = "objective, realistic institutional partner"
check("F5 Bear/Base/Bull judge personas are all different", len({bear, base, bull}) == 3)
check("F5 Bear persona = Red-Team auditor", "Red-Team" in bear and "Bear Case" in bear)
check("F5 Bull persona = high-conviction optimist", "high-conviction" in bull and "Bull Case" in bull)
check("F5 invalid bias falls back to the Base PERSONA",
      _BASE_PERSONA in junk and _BASE_PERSONA in base and _BASE_PERSONA not in bull)
check("F6 thesis_bias reaches the analyst assignment",
      "**Thesis Bias:** Bull" in N._build_analyst_user_message(base_state(thesis_bias="Bull")))

print("=" * 72)
passed = sum(1 for _, ok in _results if ok)
total = len(_results)
print(f"RESULT: {passed}/{total} passed")
if passed != total:
    print("FAILURES:", [n for n, ok in _results if not ok])
    sys.exit(1)
print("ALL FILTER/SLIDER WIRING TESTS PASS (zero API tokens used).")
