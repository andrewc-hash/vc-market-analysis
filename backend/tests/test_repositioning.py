"""Token-free tests for the Founder-mode §0.5 Strategic Repositioning feature.

Confirms WITHOUT any API call:
  - _focal_weak_spots computes the 2 weakest dimensions + 2 weakest moat sub-scores
    from the reconciled scorecard (name-matched, label-mapped, None-safe, verbatim
    1-decimal rendering, "" fallback)
  - FOUNDER_REPOSITIONING_SECTION formats safely (only {focal} braces) and carries the spec
  - the analyst user message gains the founder block + FORMATTED spec ONLY in founder mode
    with a focal
  - the judge user message gets the "divergent 0.5 proposals are not disagreements" guard
    ONLY in founder mode
  - compile_report threads the §0.5 instruction + code-computed weak-spot anchor into the
    compiler message in founder mode, with BOTH fallbacks (focal missing from a good
    scorecard vs nothing reconciled), and keeps VC mode untouched — LLM calls are stubbed
  - _extract_resolved_scores strips the focal from the emitted incumbents/pre_pmf name
    lists (R1/R13 exception applies to the lists, not just the drop-sets)
  - _report_sections does not key `## 0.5` as section 0

What this CANNOT prove (needs tokens / real deps): that the live analysts/compiler write a
compliant §0.5, and the schemas.py founder-requires-name validator (needs real pydantic —
exercised in the Docker image, not here).

Run:  python3 backend/tests/test_repositioning.py
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
from app.graph.prompts import FOUNDER_REPOSITIONING_SECTION

_results = []
def check(name, cond, detail=""):
    _results.append((name, bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


FOCAL = "NeuroScribe AI"
RESOLVED = {
    FOCAL: {"financial_health": 60, "defensibility": 55, "market_urgency": 70,
            "founder_market_fit": 65, "regulatory_alignment": 50},
    "Abridge": {"financial_health": 80, "defensibility": 78, "market_urgency": 85,
                "founder_market_fit": 82, "regulatory_alignment": 70},
}
MOATS = {FOCAL: {"economies_of_scale": 40, "differentiated_technology": 75,
                 "network_effects": 30, "brand_power": 35}}


print("=" * 72); print("_focal_weak_spots: code-computed §0.5 anchors"); print("=" * 72)
ws = N._focal_weak_spots(RESOLVED, MOATS, FOCAL)
check("names the 2 weakest dimensions with labels + scores",
      "Regulatory Alignment (50/100)" in ws and "Defensibility & IP Moat (55/100)" in ws)
check("does not include a non-weakest dimension", "Market Urgency" not in ws)
check("names the 2 weakest moat sub-scores",
      "Network Effects (30/100)" in ws and "Brand/Direct Power (35/100)" in ws)
check("weakest dimension listed first (ascending)",
      ws.index("Regulatory Alignment") < ws.index("Defensibility"))
check("name matching is case/punctuation-insensitive",
      "Regulatory Alignment" in N._focal_weak_spots(RESOLVED, MOATS, "neuroscribe-ai"))
check("empty when focal is blank", N._focal_weak_spots(RESOLVED, MOATS, "") == "")
check("empty when focal not in the scorecard", N._focal_weak_spots(RESOLVED, MOATS, "Ghost Co") == "")
check("empty when the focal has no usable scores",
      N._focal_weak_spots({FOCAL: {"financial_health": None}}, {}, FOCAL) == "")
check("dims-only when moat sub-scores are missing",
      "weakest moat" not in N._focal_weak_spots(RESOLVED, {}, FOCAL)
      and "Regulatory Alignment" in N._focal_weak_spots(RESOLVED, {}, FOCAL))
check("non-numeric scores are skipped, numeric strings accepted",
      "Financial Health & Capital Efficiency (10/100)" in N._focal_weak_spots(
          {FOCAL: {"financial_health": "10", "defensibility": "n/a"}}, {}, FOCAL))
# 1-decimal values (the stored precision after moat reconciliation) render VERBATIM —
# an integer-rounded anchor would contradict the resolved-scores JSON in the same message.
check("1-decimal scores rendered verbatim, not integer-rounded",
      "Defensibility & IP Moat (62.5/100)" in N._focal_weak_spots(
          {FOCAL: {"defensibility": 62.5, "financial_health": 90}}, {}, FOCAL))


print("=" * 72); print("_report_sections: `## 0.5` is not keyed as section 0"); print("=" * 72)
_md = "## 0. Investment Take\n\nBLUF\n\n## 0.5 Strategic Repositioning — X\n\nmoves\n\n## 1. Sector\n\nshift"
_secs = N._report_sections(_md)
check("section 0 still starts with the Investment Take", _secs.get(0, "").lstrip().startswith("Investment Take"))
check("section 1 parsed normally", "shift" in _secs.get(1, ""))


print("=" * 72); print("_extract_resolved_scores: focal stripped from incumbents/pre_pmf lists"); print("=" * 72)
_RAW = ('{"resolved_scores": {"NeuroScribe AI": {"financial_health": 60}, "Abridge": {"financial_health": 80}},'
        ' "moat_subscores": {}, "incumbents": ["Epic", "neuroscribe-ai"], "pre_pmf": ["NeuroScribe AI", "GhostCo"],'
        ' "focal_confidence": "low"}')
N._make_llm = lambda *a, **k: None
N._invoke_llm_with_retry = lambda llm, messages, max_retries=8: types.SimpleNamespace(content=_RAW)
_settings = types.SimpleNamespace(judge_model="x")
_res, _inc, _scen, _moats, _pmf, _fc, _tape = N._extract_resolved_scores("A", "B", _settings, focal=FOCAL)
check("focal stripped from incumbents (norm-name match)", _inc == ["Epic"])
check("focal stripped from pre_pmf, others kept", _pmf == ["GhostCo"])
check("focal still scored (protect intact)", FOCAL in _res)


print("=" * 72); print("FOUNDER_REPOSITIONING_SECTION: format-safe, carries the spec"); print("=" * 72)
spec = FOUNDER_REPOSITIONING_SECTION.format(focal=FOCAL)  # raises if stray braces exist
check("spec formats with only {focal} braces", FOCAL in spec and "{focal}" not in spec)
check("spec pins the exact h2 heading", "## 0.5 Strategic Repositioning — What to Change, What to Keep" in spec)
check("spec carries the paste test + banned-phrase list", "PASTE TEST" in spec and "narrow the ICP" in spec)
check("spec restates the scoring contract", "NO new scores" in spec and "revised ranking or verdict" in spec)
check("spec caps the structure (2-4 moves + one keep)", "2-4" in spec and "What NOT to change" in spec)


print("=" * 72); print("Analyst message: founder block + spec, founder mode only"); print("=" * 72)
base = {"market_prompt": "ambient scribes", "research_data": "data", "dimension_weights": None}
msg_fn = N._build_analyst_user_message({**base, "analysis_mode": "founder", "focal_startup": FOCAL})
msg_vc = N._build_analyst_user_message({**base, "analysis_mode": "vc", "focal_startup": FOCAL})
msg_nf = N._build_analyst_user_message({**base, "analysis_mode": "founder"})
check("founder mode: block + formatted spec present",
      "FOUNDER MODE — ADDITIONAL REQUIRED SECTION (0.5)" in msg_fn and "PASTE TEST" in msg_fn)
check("founder mode: spec is FORMATTED at the call site (no literal {focal})",
      "{focal}" not in msg_fn and f"how should {FOCAL} be TWEAKED" in msg_fn)
check("founder mode: R1/R13 waiver present (never incumbent / pre-PMF exempt)",
      "NEVER an incumbent" in msg_fn and "PRE-PMF" in msg_fn)
check("vc mode: no §0.5 block", "0.5" not in msg_vc)
check("founder mode without a focal startup: no §0.5 block", "0.5" not in msg_nf)
# Batch 5: VC-focal analyst block gets BOTH analysts to debate the focal AS the deal
check("vc-focal: analyst block names the focal as the DEAL UNDER EVALUATION",
      "VC-FOCAL MODE" in msg_vc and "DEAL UNDER EVALUATION" in msg_vc
      and "model " + FOCAL + "'s OWN probability-weighted outcome scenarios" in msg_vc)
check("vc-focal analyst block: no §0.5 leakage (no literal '0.5')", "0.5" not in msg_vc)
check("no-focal vc run gets NO vc-focal block", "DEAL UNDER EVALUATION" not in msg_nf)
crit = N._build_analyst_user_message({**base, "analysis_mode": "founder", "focal_startup": FOCAL,
                                      "judge_critique": "fix X", "iterations": 1})
check("judge critique still appended AFTER the founder block",
      crit.index("DISAGREEMENTS THE JUDGE FLAGGED") > crit.index("SECTION 0.5 SPEC"))


print("=" * 72); print("Judge message: §0.5 divergence guard, founder mode only"); print("=" * 72)
_judge_captured = {}
def _fake_invoke_judge(llm, messages, max_retries=8):
    _judge_captured["user_msg"] = messages[1][1]
    return types.SimpleNamespace(content='{"converged": true, "disagreements": []}')
N._make_llm = lambda *a, **k: None
N._invoke_llm_with_retry = _fake_invoke_judge
N.get_settings = lambda: types.SimpleNamespace(
    judge_model="x", max_debate_iterations=3, compiler_model="x",
    analyst_a_model="x", analyst_b_model="x", researcher_model="x", uploads_dir="/tmp",
)
N.judge_node({"agent_a_report": "A", "agent_b_report": "B", "analysis_mode": "founder",
              "focal_startup": FOCAL, "iterations": 0})
check("founder mode: judge told §0.5 divergence is expected",
      "FOUNDER MODE NOTE" in _judge_captured["user_msg"] and "0.5" in _judge_captured["user_msg"])
N.judge_node({"agent_a_report": "A", "agent_b_report": "B", "analysis_mode": "vc",
              "focal_startup": FOCAL, "iterations": 0})
check("vc mode: no judge §0.5 note", "FOUNDER MODE NOTE" not in _judge_captured["user_msg"])


print("=" * 72); print("compile_report: §0.5 instruction + weak-spot anchor (LLM stubbed)"); print("=" * 72)
captured = {}
def _fake_invoke(llm, messages, max_retries=8):
    captured["user_msg"] = messages[1][1]
    return types.SimpleNamespace(content="## 0. Investment Take\nstub")
N._invoke_llm_with_retry = _fake_invoke
N._extract_structured_artifacts = lambda *a, **k: (None, None, None)

def run_compile(mode, resolved=RESOLVED, moats=MOATS, scenarios=None, materials="", focal=FOCAL):
    captured.clear()
    N._extract_resolved_scores = lambda a, b, s, focal="": (resolved, [], scenarios, moats, [], "low", None)
    state = {"agent_a_report": "A", "agent_b_report": "B", "dimension_weights": None,
             "focal_startup": focal, "analysis_mode": mode, "iterations": 2}
    if materials:
        state["focal_materials"] = materials
    out = N.compile_report(state)
    return out["final_report"], captured["user_msg"]

fr_fn, msg_fn = run_compile("founder")
check("founder mode: §0.5 render instruction reaches the compiler",
      "## 0.5 Strategic Repositioning" in msg_fn and "IMMEDIATELY after Section 0" in msg_fn)
check("founder mode: code-computed weak spots injected",
      "SYSTEM-COMPUTED weak spots" in msg_fn and "Regulatory Alignment (50/100)" in msg_fn
      and "Network Effects (30/100)" in msg_fn)
check("founder mode: full spec appended for the compiler", "PASTE TEST" in msg_fn)
check("founder mode: spec FORMATTED at the compiler call site (no literal {focal})",
      "{focal}" not in msg_fn and f"how should {FOCAL} be TWEAKED" in msg_fn)
check("founder mode: synthesis + anchor-mismatch fallback present",
      "RAW MATERIAL" in msg_fn and "RE-ANCHOR" in msg_fn)
check("founder §0 reframed to a focal verdict (investor check + founder call)",
      "Investor check (today)" in msg_fn and "BUILD / KEEP GOING / PIVOT / STOP" in msg_fn)
check("founder §0 ban is behavior-based (no rec/valuation/MoIC for any non-focal company)",
      "NO MoIC/return multiple for ANY company other than" in msg_fn
      and "NO buy/INVEST recommendation" in msg_fn)
check("founder mode: explicit supersede-the-framework clause present",
      "THESE INSTRUCTIONS OVERRIDE YOUR FRAMEWORK" in msg_fn and "COMPILATION INSTRUCTION 2" in msg_fn)
check("founder §12 reframed to the focal's fundraise (round-sizing, not competitor MoIC)",
      "SECTION 12 (Return Math) IS ABOUT" in msg_fn and "raise-size range" in msg_fn
      and "dilution" in msg_fn and "SUBORDINATE 'Exit comparable'" in msg_fn)
# Batch 1 (memo critique): founder §12 fundraise discipline + deal-verdict founder-variants
check("founder §12: implied-dilution reconcile rule (15-25% seed norm)",
      "IMPLIED DILUTION = raise" in msg_fn and "15–25% seed norm" in msg_fn
      and "43% dilution) is INCOHERENT" in msg_fn)
check("founder §12: (assumed; no formal ask) tag carried into founder mode",
      "(assumed; no formal ask)" in msg_fn)
check("founder §12: comp only to §6 ledger or acquisitions, never below-press/Unspecified",
      "NEVER to a figure whose source" in msg_fn and "NEVER treat an amount RAISED as a" in msg_fn)
check("founder §12: CONDITIONS-TO-CLOSE founder variant (milestones = dated conditions)",
      "Conditions to close the round" in msg_fn and "how a lead verifies it" in msg_fn)
check("founder §12: RUNWAY-TO-MILESTONE check (editorial fix — raise ÷ burn vs months-to-milestone)",
      "RUNWAY-TO-MILESTONE" in msg_fn and "reach the next-round milestones" in msg_fn)
check("founder §12: WHY-NOT-STOP / WHY-NOT-RAISE-MORE founder dialectic",
      "Why not stop — and why not raise more" in msg_fn
      and "PRICED-BY-STAGE" in msg_fn and "CUTS-BOTH-WAYS" in msg_fn)
# Batch 1: binary-variable coherence chain
check("founder §0: first line is the Investor check, binary variable named in founder voice",
      "FIRST LINE under the" in msg_fn and "**Binary variable:**" in msg_fn
      and "kill-condition voice" in msg_fn)
check("founder §0: TRIPWIRE COHERENCE binds §0 binary = §11 top risk = §0.5 quit signal",
      "TRIPWIRE COHERENCE" in msg_fn and "EXACTLY TWICE" in msg_fn
      and "Fastest signal to quit" in msg_fn)

fr_vc, msg_vc = run_compile("vc")
check("vc mode: no §0.5 instruction", "0.5 Strategic Repositioning" not in msg_vc)
check("vc mode: no weak-spot anchor", "SYSTEM-COMPUTED weak spots" not in msg_vc)
# Market-overview note is gated on NO focal — a VC-focal or founder run must never see it.
check("vc-FOCAL mode: market-overview note NOT injected (a focal deal is on the table)",
      "MARKET-OVERVIEW MODE" not in msg_vc)
check("founder mode: market-overview note NOT injected", "MARKET-OVERVIEW MODE" not in msg_fn)

# Focal missing from an otherwise-good scorecard: the anchor must NOT claim the whole
# scorecard was unavailable (it is authoritative in the same message).
fr_mf, msg_mf = run_compile("founder", resolved={"Abridge": RESOLVED["Abridge"]}, moats={})
check("founder mode + focal missing from good scorecard: honest fallback",
      "no usable entry" in msg_mf and "analyst-asserted" in msg_mf)
check("founder mode + focal missing: does NOT claim scorecard unavailable",
      "scorecard was unavailable" not in msg_mf)

fr_nr, msg_nr = run_compile("founder", resolved={}, moats={})
check("founder mode + no reconciled scores: fallback anchor, no crash",
      "No system-computed weak spots" in msg_nr and "BOTH analysts agree" in msg_nr)
check("founder mode + no reconciled scores: §0.5 still required", "## 0.5 Strategic Repositioning" in msg_nr)


print("=" * 72); print("Change A — founder deck reaches analysts + compiler (not VC/no-materials)"); print("=" * 72)
DECK = "Fidea founded by ex-CISO Jane Roe. Runtime authz engine for AI agents. 3 design partners."
a_fn = N._build_analyst_user_message({**base, "analysis_mode": "founder", "focal_startup": FOCAL,
                                      "focal_materials": DECK})
check("analyst (founder+deck): materials injected as primary source",
      "FOUNDER-PROVIDED MATERIALS" in a_fn and "ex-CISO Jane Roe" in a_fn
      and "(per founder materials)" in a_fn)
check("analyst (founder+deck): told NOT to write 'unknown' for stated facts",
      'Do NOT write "unknown"' in a_fn)
a_vc = N._build_analyst_user_message({**base, "analysis_mode": "vc", "focal_startup": FOCAL,
                                      "focal_materials": DECK})
check("analyst (VC mode): deck NOT injected", "FOUNDER-PROVIDED MATERIALS" not in a_vc)
a_nm = N._build_analyst_user_message({**base, "analysis_mode": "founder", "focal_startup": FOCAL})
check("analyst (founder, no deck): no materials block", "FOUNDER-PROVIDED MATERIALS" not in a_nm)
_fr, c_fn = run_compile("founder", materials=DECK)
check("compiler (founder+deck): materials injected", "FOUNDER-PROVIDED MATERIALS" in c_fn and "Jane Roe" in c_fn)
_fr, c_vc = run_compile("vc", materials=DECK)
check("compiler (VC mode): deck NOT injected", "FOUNDER-PROVIDED MATERIALS" not in c_vc)
check("digest is founder-mode-gated at the helper level",
      N._focal_materials_digest({"focal_startup": FOCAL, "focal_materials": DECK, "analysis_mode": "vc"}) == ""
      and N._focal_materials_digest({"focal_startup": FOCAL, "analysis_mode": "founder"}) == "")


print("=" * 72); print("Change B — §12 return math: competitor MoIC relabeled in founder mode"); print("=" * 72)
COMP_SCEN = {"startup": "Oasis Security", "expected_return": 3.5,
             "scenarios": [{"label": "base", "probability": 0.6, "multiple_low": 3.0, "multiple_high": 5.0}]}
_fr, msg_comp = run_compile("founder", scenarios=COMP_SCEN)
check("founder + competitor scenarios: MoIC labeled the competitor's, NOT the focal's headline",
      "is for **Oasis Security** — a COMPETITOR" in msg_comp
      and "do NOT headline it as" in msg_comp and "exit-comp context" in msg_comp)
FOCAL_SCEN = {"startup": FOCAL, "expected_return": 4.2,
              "scenarios": [{"label": "base", "probability": 0.6, "multiple_low": 4.0, "multiple_high": 5.0}]}
_fr, msg_focal = run_compile("founder", scenarios=FOCAL_SCEN)
check("founder + focal-IS-the-modelled-pick: verbatim-in-§0/§12 contract holds (point-only fixture)",
      "Present it as this single expected multiple" in msg_focal
      and "in Sections 0 and 12" in msg_focal)
check("founder + focal-IS-pick: §12 lets the focal headline its own return (no self-conflict)",
      "IS {}'s own".format(FOCAL) in msg_focal or "return IS" in msg_focal
      and "never as {}'s headline return".format(FOCAL) not in msg_focal)
# suffix-tolerant focal match: "NeuroScribe AI, Inc." should still count as the focal
SUFFIX_SCEN = {"startup": FOCAL + ", Inc.", "expected_return": 4.0,
               "scenarios": [{"label": "base", "probability": 0.6, "multiple_low": 4.0, "multiple_high": 4.0}]}
_fr, msg_suffix = run_compile("founder", scenarios=SUFFIX_SCEN)
check("founder + focal-with-suffix: matched as focal, NOT flagged its own competitor",
      "a COMPETITOR" not in msg_suffix)
_fr, msg_vc_scen = run_compile("vc", scenarios=COMP_SCEN)
check("vc mode + scenarios: original verbatim contract (no competitor-relabel)",
      "Present it as this single expected multiple" in msg_vc_scen
      and "a COMPETITOR" not in msg_vc_scen)


print("=" * 72); print("Change C — §0.5 spec: sequencing + kill-gate"); print("=" * 72)
check("spec carries the Sequenced 90-day plan (do-first/defer, cost, conflict flag)",
      "Sequenced 90-day plan" in spec and "do-FIRST" in spec and "CONTRADICTORY constraints" in spec)
check("spec carries the Fastest signal to quit gate", "Fastest signal to quit" in spec)


print("=" * 72)
passed = sum(1 for _, ok in _results if ok); total = len(_results)
print(f"RESULT: {passed}/{total} passed")
if passed != total:
    print("FAILURES:", [n for n, ok in _results if not ok]); sys.exit(1)
print("ALL FOUNDER-§0.5 REPOSITIONING TESTS PASS (zero API tokens used).")
