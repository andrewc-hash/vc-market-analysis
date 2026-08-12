"""Token-free tests for the researcher PROTOCOL GUARD (in-code search-floor enforcement).

Confirms WITHOUT any API call:
  - PROTOCOL_MIN_TOOL_CALLS is 30 and matches the prompt's stated floor
  - a compliant first attempt (>=30 calls) runs the agent exactly once, protocol_retries=0
  - a short first attempt triggers ONE corrective re-run whose message carries the
    PROTOCOL VIOLATION NOTICE, and the better attempt (by call count) is kept
  - a retry that is still short keeps the original attempt and logs it; the
    PROTOCOL SHORTFALL flag still fires on the final audit line
  - the retry is disclosed in the manifest (protocol_retries)

What this CANNOT prove (needs tokens): that a live Gemini retry actually searches.

Run:  python3 backend/tests/test_protocol_guard.py
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
from app.graph.prompts import TOOL_CHOREOGRAPHY_INSTRUCTIONS

_results = []
def check(name, cond, detail=""):
    _results.append((name, bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


def _ai(tool_calls):
    return types.SimpleNamespace(type="ai", tool_calls=tool_calls, content="")

def _toolmsg(content):
    return types.SimpleNamespace(type="tool", tool_calls=None, content=content)

def _transcript(n_calls, brief="THE BRIEF"):
    """A minimal ReAct transcript with n_calls tool calls then a final AI message."""
    msgs = []
    for i in range(n_calls):
        msgs.append(_ai([{"name": "search_market_data", "args": {"query": f"q{i}"}}]))
        msgs.append(_toolmsg("## Tavily Answer\nfacts\n\n## Sources\n[Src](https://s.example/a)\nsnippet"))
    msgs.append(types.SimpleNamespace(type="ai", tool_calls=None, content=brief))
    return msgs


N._make_llm = lambda *a, **k: None
N.get_settings = lambda: types.SimpleNamespace(
    researcher_model="gemini-2.5-pro", compiler_model="x", judge_model="x",
    analyst_a_model="x", analyst_b_model="x", uploads_dir="/tmp",
)

class Runner:
    """Scripted _run_agent_with_retry: returns queued transcripts, records messages."""
    def __init__(self, transcripts):
        self.transcripts = list(transcripts)
        self.calls = []
    def __call__(self, agent, payload):
        self.calls.append(payload["messages"][0][1])
        return {"messages": self.transcripts.pop(0)}


print("=" * 72); print("Constant + prompt agreement"); print("=" * 72)
check("PROTOCOL_MIN_TOOL_CALLS == 30", N.PROTOCOL_MIN_TOOL_CALLS == 30)
check("prompt floor matches the code floor",
      f"AT LEAST {N.PROTOCOL_MIN_TOOL_CALLS} search tool calls" in TOOL_CHOREOGRAPHY_INSTRUCTIONS)


print("=" * 72); print("Compliant first attempt: no retry"); print("=" * 72)
r = Runner([_transcript(32)])
N._run_agent_with_retry = r
out = N.researcher_node({"market_prompt": "agent IAM"})
mf = out["research_manifest"]
check("agent invoked exactly once", len(r.calls) == 1, f"got {len(r.calls)}")
check("32 calls counted", mf["total"] == 32)
check("protocol_retries == 0", mf.get("protocol_retries") == 0)
check("no guard log lines", not any("PROTOCOL GUARD" in l for l in out["agent_logs"]))
check("no CALL-COUNT shortfall at 32 calls (other shortfalls may fire — single-tool transcript)",
      "only 32 calls" not in out["agent_logs"][-1])


print("=" * 72); print("Zero-call first attempt: corrective re-run, better attempt kept"); print("=" * 72)
r = Runner([_transcript(0, brief="memory brief"), _transcript(34, brief="searched brief")])
N._run_agent_with_retry = r
out = N.researcher_node({"market_prompt": "agent IAM"})
mf = out["research_manifest"]
check("agent invoked twice", len(r.calls) == 2, f"got {len(r.calls)}")
check("retry message carries the violation notice",
      "PROTOCOL VIOLATION NOTICE" in r.calls[1] and "mandatory minimum of 30" in r.calls[1])
check("retry message includes the original protocol (appended, not replaced)",
      r.calls[1].startswith(r.calls[0][:60]))
check("better attempt kept (34 calls)", mf["total"] == 34)
check("kept brief is the retry's brief", "searched brief" in out["research_data"])
check("protocol_retries == 1 (disclosed)", mf.get("protocol_retries") == 1)
check("guard log announces the re-run",
      any("PROTOCOL GUARD" in l and "only 0 tool call(s)" in l for l in out["agent_logs"]))
check("no CALL-COUNT shortfall after a compliant retry", "only 34 calls" not in out["agent_logs"][-1])


print("=" * 72); print("Retry still short: keep the original, shortfall stands"); print("=" * 72)
r = Runner([_transcript(5, brief="first brief"), _transcript(3, brief="worse brief")])
N._run_agent_with_retry = r
out = N.researcher_node({"market_prompt": "agent IAM"})
mf = out["research_manifest"]
check("agent invoked twice", len(r.calls) == 2)
check("original kept when retry is worse (5 > 3)", mf["total"] == 5)
check("kept brief is the original's", "first brief" in out["research_data"])
check("keep-original guard line logged",
      any("keeping the original attempt" in l for l in out["agent_logs"]))
check("protocol_retries == 1 even when retry lost", mf.get("protocol_retries") == 1)
check("PROTOCOL SHORTFALL still flagged on the final line",
      "PROTOCOL SHORTFALL" in out["agent_logs"][-1] and "only 5 calls (<30)" in out["agent_logs"][-1])


print("=" * 72); print("Tie goes to the original (no churn on equal attempts)"); print("=" * 72)
r = Runner([_transcript(4, brief="first brief"), _transcript(4, brief="second brief")])
N._run_agent_with_retry = r
out = N.researcher_node({"market_prompt": "agent IAM"})
check("equal call counts keep the original brief", "first brief" in out["research_data"])


print()
passed = sum(1 for _, ok in _results if ok)
total = len(_results)
print(f"RESULT: {passed}/{total} passed")
if passed == total:
    print("ALL PROTOCOL-GUARD TESTS PASS (zero API tokens used).")
else:
    sys.exit(1)
