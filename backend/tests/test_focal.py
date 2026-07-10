"""Token-free tests for the focal-startup feature's deterministic plumbing.

Confirms WITHOUT any API call:
  - the researcher prompt force-includes the focal startup + injects uploaded materials
    (mode-aware: vc vs founder)
  - the ingest node parses an upload dir into focal_materials (text path) and is a
    pass-through when there's no focal startup
  - compile_report threads the focal startup all the way into final_report (it survives
    into resolved/weighted/ranking, carries focal_confidence, and the compiler gets the
    right mode-aware framing) — LLM calls are stubbed
  - the pipeline wires ingest_focal BEFORE the researcher

What this CANNOT prove (needs tokens): that the live LLMs actually comply — i.e. write
the focal startup into their generated reports, and the real vision transcription of a deck.

Run:  python3 backend/tests/test_focal.py
"""
import os, sys, tempfile, types
from pathlib import Path

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


print("=" * 72); print("Researcher prompt: focal force-include + materials (mode-aware)"); print("=" * 72)
vc_block = N._focal_research_block({"focal_startup": "NeuroScribe AI", "analysis_mode": "vc",
                                    "focal_materials": "Pre-seed $2M. ICU acoustic model."})
fnd_block = N._focal_research_block({"focal_startup": "NeuroScribe AI", "analysis_mode": "founder",
                                     "focal_materials": "Pre-seed $2M. ICU acoustic model."})
check("focal name injected", "NeuroScribe AI" in vc_block)
check("uploaded materials injected as PRIMARY SOURCE", "ICU acoustic model" in vc_block and "FOCAL MATERIALS" in vc_block)
check("VC mode = include in the field", "required member of the competitive field" in vc_block)
check("Founder mode = centered on the startup", "centered on" in fnd_block)
check("empty when no focal + no materials", N._focal_research_block({}) == "")
# materials are clipped so a huge deck can't blow the context budget
big = N._focal_research_block({"focal_startup": "X", "focal_materials": "y" * 50000})
check("oversized materials are truncated", "materials truncated" in big and len(big) < 30000)

# A focal startup whose research is built into the full researcher message
msg = N._build_researcher_user_message({"market_prompt": "ambient scribes", "focal_startup": "NeuroScribe AI",
                                        "analysis_mode": "vc", "focal_materials": "deck text"})
check("focal block reaches the full researcher message", "NeuroScribe AI" in msg and "FOCAL STARTUP" in msg)


print("=" * 72); print("Ingest node: parses uploads -> focal_materials (text path, no tokens)"); print("=" * 72)
with tempfile.TemporaryDirectory() as parent:
    upid = "abc123"
    Path(parent, upid).mkdir()
    Path(parent, upid, "deck.txt").write_text("NeuroScribe: stealth ICU scribe, ex-Abridge founder.")
    N.get_settings = lambda: types.SimpleNamespace(uploads_dir=parent)  # point ingest at our temp volume
    out = N.ingest_focal_materials({"focal_startup": "NeuroScribe AI", "focal_upload_id": upid})
    check("node returns extracted focal_materials", "ex-Abridge founder" in out.get("focal_materials", ""))
    check("node emits a progress log", any("Ingest" in s for s in out.get("agent_logs", [])))
check("pure pass-through when no focal startup", N.ingest_focal_materials({}) == {})


print("=" * 72); print("compile_report: focal threads into final_report (LLM stubbed)"); print("=" * 72)
FOCAL = "NeuroScribe AI"
RESOLVED = {FOCAL: {"financial_health": 60, "defensibility": 55, "market_urgency": 70,
                    "founder_market_fit": 65, "regulatory_alignment": 50},
            "Abridge": {"financial_health": 80, "defensibility": 78, "market_urgency": 85,
                        "founder_market_fit": 82, "regulatory_alignment": 70}}

captured = {}
def _fake_extract_scores(a, b, settings, focal=""):
    # focal kept + tagged low confidence (simulates the real reconciler honoring the exception)
    return RESOLVED, [], None, {}, [], "low", None
def _fake_invoke(llm, messages, max_retries=8):
    captured["user_msg"] = messages[1][1]  # ("user", <text>)
    return types.SimpleNamespace(content="## 0. Investment Take\nstub\n## 7. Scorecard\nstub")
N._extract_resolved_scores = _fake_extract_scores
N._make_llm = lambda *a, **k: None
N._invoke_llm_with_retry = _fake_invoke
N._extract_structured_artifacts = lambda *a, **k: (None, None, None)
# compile_report reads settings.compiler_model before _make_llm (which we stub); give it one.
N.get_settings = lambda: types.SimpleNamespace(
    compiler_model="x", judge_model="x", researcher_model="x",
    analyst_a_model="x", analyst_b_model="x", uploads_dir="/tmp",
)

def run(mode):
    captured.clear()
    out = N.compile_report({
        "agent_a_report": "A", "agent_b_report": "B", "dimension_weights": None,
        "focal_startup": FOCAL, "analysis_mode": mode, "iterations": 2,
    })
    return out["final_report"], captured["user_msg"]

fr_vc, msg_vc = run("vc")
check("focal survives into final_report.focal_startup", fr_vc.get("focal_startup") == FOCAL)
check("focal_confidence carried through", fr_vc.get("focal_confidence") == "low")
check("analysis_mode carried through", fr_vc.get("analysis_mode") == "vc")
check("focal is in the computed ranking", FOCAL in (fr_vc.get("ranking") or []))
check("focal has a weighted score", (fr_vc.get("weighted_scores") or {}).get(FOCAL, {}).get("weighted_score") is not None)
check("VC mode framing reaches the compiler", "user REQUIRES" in msg_vc and FOCAL in msg_vc)
check("confidence caveat reaches the compiler", "confidence" in msg_vc.lower())
# Batch 5: VC-focal deal-centered override (§0/§12 re-centered on the focal deal)
check("VC-focal: deal-centered override note injected",
      "VC-FOCAL MODE — THESE INSTRUCTIONS OVERRIDE" in msg_vc
      and f"Deal verdict: {FOCAL}" in msg_vc and "DEAL UNDER EVALUATION" in msg_vc)
check("VC-focal: §12 devices re-pointed at the focal, leader as benchmark",
      "devices apply to " + FOCAL in msg_vc and "opportunity-cost benchmark" in msg_vc)
check("VC-focal: DEAL PATH closer present (WATCH/PASS)",
      f"Deal Path for {FOCAL}" in msg_vc)
check("VC-focal: field position computed in code and injected",
      "SYSTEM-COMPUTED field position" in msg_vc and f"{FOCAL} ranks #" in msg_vc)
check("VC-focal: focal_rank computed into final_report",
      isinstance(fr_vc.get("focal_rank"), int) and fr_vc["focal_rank"] >= 1)

fr_fn, msg_fn = run("founder")
check("Founder mode framing reaches the compiler", "FOUNDER MODE" in msg_fn and "verdict" in msg_fn.lower())
check("Founder final_report mode is founder", fr_fn.get("analysis_mode") == "founder")


print("=" * 72); print("Pipeline wiring: ingest_focal runs BEFORE the researcher"); print("=" * 72)
_pipe_src = Path(__file__).resolve().parents[1].joinpath("app/graph/pipeline.py").read_text()
check("ingest_focal node registered", 'add_node("ingest_focal"' in _pipe_src)
check("START -> ingest_focal", 'add_edge(START, "ingest_focal")' in _pipe_src)
check("ingest_focal -> researcher", 'add_edge("ingest_focal", "researcher")' in _pipe_src)


print("=" * 72)
passed = sum(1 for _, ok in _results if ok); total = len(_results)
print(f"RESULT: {passed}/{total} passed")
if passed != total:
    print("FAILURES:", [n for n, ok in _results if not ok]); sys.exit(1)
print("ALL FOCAL-STARTUP PLUMBING TESTS PASS (zero API tokens used).")
