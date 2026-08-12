"""Token-free tests for the glass-box debate log (published multi-agent debate history).

Confirms WITHOUT any API call that the debate log is pure bookkeeping IN CODE:
  - judge_node appends one entry per round with correct 1-based round numbers
  - the RAW judge verdict is recorded (converged), and the final-round cap that
    forces judge_agreed=true is flagged separately (forced) — routing unchanged
  - disagreements are sanitized in code: 4 fields coerced to strings, each field
    truncated to <=600 chars, <=10 per round, malformed entries dropped
  - the no-parse fallback still appends a truthful empty-disagreements round
  - _validate_debate_log re-validates defensively at compile time (garbage -> [])
  - compile_report emits final_report["debate_log"] on BOTH compile paths; [] when absent

Run:  python3 backend/tests/test_debate_log.py
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


N._make_llm = lambda *a, **k: None
N.get_settings = lambda: types.SimpleNamespace(
    judge_model="x", max_debate_iterations=3, compiler_model="x",
    analyst_a_model="x", analyst_b_model="x", researcher_model="x", uploads_dir="/tmp",
)

_verdicts = {}
def _fake_invoke_judge(llm, messages, max_retries=8):
    return types.SimpleNamespace(content=_verdicts["next"])
N._invoke_llm_with_retry = _fake_invoke_judge


print("=" * 72); print("judge_node: one entry per round across a full 3-round loop"); print("=" * 72)
DIS = '{"point": "TAM", "analyst_a": "$4B", "analyst_b": "$9B", "reconsider": "re-derive bottoms-up"}'
state = {"agent_a_report": "A", "agent_b_report": "B", "iterations": 0}
_verdicts["next"] = '{"converged": false, "disagreements": [' + DIS + ']}'
out1 = N.judge_node(state)
check("round 1: entry appended", len(out1["debate_log"]) == 1)
check("round 1: 1-based round number", out1["debate_log"][0]["round"] == 1)
check("round 1: raw converged=false recorded, not forced",
      out1["debate_log"][0]["converged"] is False and out1["debate_log"][0]["forced"] is False)
check("round 1: disagreement carried with all 4 fields",
      out1["debate_log"][0]["disagreements"] == [{"point": "TAM", "analyst_a": "$4B",
                                                  "analyst_b": "$9B", "reconsider": "re-derive bottoms-up"}])
check("round 1: routing untouched (judge_agreed=false, critique non-empty)",
      out1["judge_agreed"] is False and "TAM" in out1["judge_critique"])

state.update(out1)
out2 = N.judge_node(state)
check("round 2: appended after round 1 (chronological)",
      [e["round"] for e in out2["debate_log"]] == [1, 2])

state.update(out2)
_verdicts["next"] = '{"converged": false, "disagreements": [' + DIS + ']}'
out3 = N.judge_node(state)  # iteration 3 of 3 — the cap forces agreement
check("round 3 (capped): judge_agreed FORCED true (behavior unchanged)", out3["judge_agreed"] is True)
check("round 3 (capped): RAW converged=false preserved in the log",
      out3["debate_log"][2]["converged"] is False)
check("round 3 (capped): forced=true flagged", out3["debate_log"][2]["forced"] is True)
check("round 3: remaining disagreements still recorded for the record",
      out3["debate_log"][2]["disagreements"][0]["point"] == "TAM")
check("3 rounds -> 3 entries, rounds [1,2,3]",
      [e["round"] for e in out3["debate_log"]] == [1, 2, 3])

_verdicts["next"] = '{"converged": true, "disagreements": []}'
outc = N.judge_node({"agent_a_report": "A", "agent_b_report": "B", "iterations": 0})
check("genuine convergence: converged=true, forced=false, no disagreements",
      outc["debate_log"][0]["converged"] is True and outc["debate_log"][0]["forced"] is False
      and outc["debate_log"][0]["disagreements"] == [] and outc["judge_agreed"] is True)


print("=" * 72); print("judge_node: sanitization (truncation, <=10 cap, malformed dropped)"); print("=" * 72)
import json
long_txt = "x" * 1000
raw_dis = ([{"point": long_txt, "analyst_a": 42, "analyst_b": None, "reconsider": ["a", "b"]}]
           + ["junk-string", 7, ["nested"]]                      # malformed — dropped
           + [{"point": "", "analyst_a": "", "analyst_b": "", "reconsider": ""}]  # empty — dropped
           + [{"point": f"p{i}"} for i in range(14)])            # overflow past the cap
_verdicts["next"] = json.dumps({"converged": False, "disagreements": raw_dis})
outs = N.judge_node({"agent_a_report": "A", "agent_b_report": "B", "iterations": 0})
dis = outs["debate_log"][0]["disagreements"]
check("capped at <=10 disagreements per round", len(dis) == 10, f"got {len(dis)}")
check("long field truncated to 600 chars", len(dis[0]["point"]) == 600)
check("non-string fields coerced to strings (int, None, list)",
      dis[0]["analyst_a"] == "42" and dis[0]["analyst_b"] == "" and isinstance(dis[0]["reconsider"], str))
check("malformed entries dropped, well-formed kept in order",
      dis[1]["point"] == "p0" and dis[9]["point"] == "p8")
check("missing fields coerced to empty strings", dis[1]["analyst_a"] == "" and dis[1]["reconsider"] == "")

check("disagreements NOT a list -> sanitized to []",
      (lambda: (_verdicts.__setitem__("next", '{"converged": false, "disagreements": "nope"}'),
                N.judge_node({"agent_a_report": "A", "agent_b_report": "B", "iterations": 0}))[1]
       )()["debate_log"][0]["disagreements"] == [])


print("=" * 72); print("judge_node: no-parse fallback still appends a truthful round"); print("=" * 72)
_verdicts["next"] = "The analysts basically agree, no JSON for you today."
outnp = N.judge_node({"agent_a_report": "A", "agent_b_report": "B", "iterations": 0})
check("no-parse: judge_agreed=false (existing fallback behavior unchanged)",
      outnp["judge_agreed"] is False)
check("no-parse: round entry still appended (round count stays truthful)",
      len(outnp["debate_log"]) == 1 and outnp["debate_log"][0]["round"] == 1)
check("no-parse: converged=false, forced=false, disagreements=[]",
      outnp["debate_log"][0] == {"round": 1, "converged": False, "forced": False, "disagreements": []})


print("=" * 72); print("_validate_debate_log: coercion + garbage -> []"); print("=" * 72)
GOOD = [{"round": 1, "converged": False, "forced": False,
         "disagreements": [{"point": "TAM", "analyst_a": "$4B", "analyst_b": "$9B", "reconsider": "redo"}]},
        {"round": 2, "converged": False, "forced": True, "disagreements": []}]
check("clean log passes through intact", N._validate_debate_log(GOOD) == GOOD)
co = N._validate_debate_log([{"round": "2", "converged": 1, "forced": "yes",
                              "disagreements": [{"point": 5}]}])
check("coercion: round '2'->int 2, truthy->bool, field 5->'5'",
      co == [{"round": 2, "converged": True, "forced": True,
              "disagreements": [{"point": "5", "analyst_a": "", "analyst_b": "", "reconsider": ""}]}])
check("non-int round dropped, valid sibling kept",
      N._validate_debate_log([{"round": "abc"}, {"round": None}, {"round": 0},
                              {"round": 3, "converged": True}])
      == [{"round": 3, "converged": True, "forced": False, "disagreements": []}])
check("non-dict entries dropped", N._validate_debate_log(["x", 1, GOOD[1]]) == [GOOD[1]])
check("garbage -> []: None / dict / string / int",
      N._validate_debate_log(None) == [] and N._validate_debate_log({"round": 1}) == []
      and N._validate_debate_log("log") == [] and N._validate_debate_log(7) == [])
check("nested disagreement garbage sanitized, not fatal",
      N._validate_debate_log([{"round": 1, "disagreements": {"point": "x"}}])
      == [{"round": 1, "converged": False, "forced": False, "disagreements": []}])
check("oversized/malformed disagreements re-sanitized at compile time",
      len(N._validate_debate_log([{"round": 1, "disagreements":
                                   [{"point": "y" * 900}] + ["junk"] * 3
                                   + [{"point": f"p{i}"} for i in range(12)]}])[0]["disagreements"]) == 10)


print("=" * 72); print("compile_report: debate_log emitted on BOTH paths (LLM stubbed)"); print("=" * 72)
def _fake_invoke(llm, messages, max_retries=8):
    if messages[0][1] is N.TOUR_SUMMARY_SYSTEM:  # the tour's summarizer call, not the compiler's
        return types.SimpleNamespace(content="{}")
    return types.SimpleNamespace(content="## 0. Investment Take\nstub")
def _fail_invoke(llm, messages, max_retries=8):
    raise RuntimeError("compile down")
N._extract_structured_artifacts = lambda *a, **k: (None, None, None)
N._extract_resolved_scores = lambda a, b, s, focal="": ({}, [], None, {}, [], "", None)

N._invoke_llm_with_retry = _fake_invoke
LOG = [{"round": 1, "converged": False, "forced": False, "disagreements": []},
       {"round": 2, "converged": True, "forced": False, "disagreements": []}]
fr = N.compile_report({"agent_a_report": "A", "agent_b_report": "B", "dimension_weights": None,
                       "debate_log": LOG, "iterations": 2})["final_report"]
check("success path: debate_log emitted, validated, 2 rounds", fr.get("debate_log") == LOG)
check("success path: agrees with iterations_to_consensus",
      len(fr["debate_log"]) == fr["iterations_to_consensus"] == 2)
check("JSON-safe plain types only", json.dumps(fr["debate_log"]) is not None)

fr_dirty = N.compile_report({"agent_a_report": "A", "agent_b_report": "B", "dimension_weights": None,
                             "debate_log": ["junk", {"round": 1, "converged": "y"}]})["final_report"]
check("success path: corrupted state re-validated in code (junk dropped)",
      fr_dirty["debate_log"] == [{"round": 1, "converged": True, "forced": False, "disagreements": []}])

fr_absent = N.compile_report({"agent_a_report": "A", "agent_b_report": "B",
                              "dimension_weights": None})["final_report"]
check("absent state key -> [] (never a crash, never None)", fr_absent["debate_log"] == [])

N._invoke_llm_with_retry = _fail_invoke
fr_fb = N.compile_report({"agent_a_report": "A", "agent_b_report": "B", "dimension_weights": None,
                          "debate_log": LOG})["final_report"]
check("compile-FALLBACK path: debate_log still emitted (like the disclaimer)",
      fr_fb.get("debate_log") == LOG and "NOT investment advice" in fr_fb["merged_report"])
fr_fb2 = N.compile_report({"agent_a_report": "A", "agent_b_report": "B",
                           "dimension_weights": None})["final_report"]
check("compile-FALLBACK path: absent key -> []", fr_fb2["debate_log"] == [])


print("=" * 72)
passed = sum(1 for _, ok in _results if ok); total = len(_results)
print(f"RESULT: {passed}/{total} passed")
if passed != total:
    print("FAILURES:", [n for n, ok in _results if not ok]); sys.exit(1)
print("ALL DEBATE-LOG TESTS PASS (zero API tokens used).")
