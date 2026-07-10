"""Token-free tests for the research-freshness layer (stale-competitor fix).

Confirms WITHOUT any API call:
  - _tavily_search emits "(published: <date>)" per source when Tavily returns one,
    omits the tag otherwise, passes topic/days params only when set, and still
    degrades gracefully on search failure
  - search_latest_news is a news-topic, past-365-days query and is in RESEARCH_TOOLS (6 tools)
  - the researcher / analyst / compiler user messages are date-grounded ("Today's date: ...")
    with the recency-arbitration instruction (compile_report LLM stubbed)
  - the prompts carry the freshness protocol: >=20 calls, the per-startup latest-news pass,
    RECENCY DISCIPLINE (researcher) and the RECENCY sourcing rule (analysts + compiler)

What this CANNOT prove (needs tokens): that live searches return dated sources and that
the LLMs actually arbitrate by recency.

Run:  python3 backend/tests/test_freshness.py
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
from app.graph import tools as T
from app.graph.prompts import (
    REPORT_TEMPLATE_INSTRUCTIONS,
    RESEARCHER_SYSTEM,
    TOOL_CHOREOGRAPHY_INSTRUCTIONS,
)

_results = []
def check(name, cond, detail=""):
    _results.append((name, bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


class FakeTavily:
    def __init__(self, results=None, raise_exc=False):
        self.kwargs = None
        self.results = results or []
        self.raise_exc = raise_exc
    def search(self, **kwargs):
        self.kwargs = kwargs
        if self.raise_exc:
            raise RuntimeError("quota exceeded")
        return {"answer": "the answer", "results": self.results}


print("=" * 72); print("_tavily_search: publication dates + recency params"); print("=" * 72)
fake = FakeTavily(results=[
    {"title": "Fresh", "url": "https://a", "content": "new round", "published_date": "2026-05-14"},
    {"title": "Undated", "url": "https://b", "content": "old page"},
])
T._get_tavily = lambda: fake
out = T._tavily_search("q", "## H")
check("dated source carries (published: ...) tag", "[Fresh](https://a) (published: 2026-05-14)" in out)
check("undated source has NO published tag", "[Undated](https://b)\n" in out and "[Undated](https://b) (" not in out)
check("general search sends no topic/days params",
      "topic" not in fake.kwargs and "days" not in fake.kwargs)
check("answer + sources block still present", "the answer" in out and "## Sources" in out)

out_news = T._tavily_search("q", "## H", topic="news", days=365)
check("news search passes topic + days to Tavily",
      fake.kwargs.get("topic") == "news" and fake.kwargs.get("days") == 365)

T._get_tavily = lambda: FakeTavily(raise_exc=True)
check("search failure degrades to a note, never raises", "[Search failed" in T._tavily_search("q", "## H"))

class UsageLimitExceededError(Exception):
    pass
class QuotaFake:
    def search(self, **k):
        raise UsageLimitExceededError("monthly limit")
T._get_tavily = lambda: QuotaFake()
check("quota exhaustion returns the distinctive stop-retrying marker",
      "TAVILY QUOTA EXHAUSTED" in T._tavily_search("q", "## H"))


print("=" * 72); print("search_latest_news: the freshness tool"); print("=" * 72)
fake2 = FakeTavily()
T._get_tavily = lambda: fake2
out = T.search_latest_news("Fidea")
check("query targets the startup's latest funding/product news",
      "Fidea" in fake2.kwargs["query"] and "funding" in fake2.kwargs["query"])
check("query covers the M&A surface (acquisition/acquired/merger)",
      "acquisition" in fake2.kwargs["query"] and "acquired" in fake2.kwargs["query"])
check("restricted to news topic, past 365 days",
      fake2.kwargs.get("topic") == "news" and fake2.kwargs.get("days") == 365)
check("news pass runs at basic depth (1 credit, not 2)",
      fake2.kwargs.get("search_depth") == "basic")
check("header marks it as the freshness result", "Latest News (past 12 months): Fidea" in out)
check("RESEARCH_TOOLS now has 7 tools incl. latest-news + google-live",
      len(T.RESEARCH_TOOLS) == 7 and T.search_latest_news in T.RESEARCH_TOOLS
      and T.search_google_live in T.RESEARCH_TOOLS)


print("=" * 72); print("search_startup_financials: page bodies, not just snippets"); print("=" * 72)
fake3 = FakeTavily(results=[
    {"title": "Round story", "url": "https://a", "content": "snippet",
     "raw_content": "Deep in paragraph six: post-money valuation of approximately $700 million. " + "x" * 3000},
    {"title": "No body", "url": "https://b", "content": "snippet only"},
])
T._get_tavily = lambda: fake3
out = T.search_startup_financials("Oasis Security")
check("financial search requests raw page content", fake3.kwargs.get("include_raw_content") is True)
check("page excerpt surfaces body-level facts", "[Page excerpt]" in out and "$700 million" in out)
check("page excerpt is capped", "…[page excerpt truncated]" in out)
check("source without a body gets no excerpt block", out.count("[Page excerpt]") == 1)
fake4 = FakeTavily()
T._get_tavily = lambda: fake4
T.search_market_data("q")
check("non-financial searches do NOT request raw content", "include_raw_content" not in fake4.kwargs)


print("=" * 72); print("search_google_live: Gemini server-side grounding tool"); print("=" * 72)
class FakeGroundedLLM:
    def __init__(self, raise_exc=False):
        self.kwargs = None
        self.raise_exc = raise_exc
    def invoke(self, query, **kwargs):
        self.kwargs = {"query": query, **kwargs}
        if self.raise_exc:
            raise RuntimeError("grounding down")
        return types.SimpleNamespace(
            content="Oasis raised a $120M Series B in March 2026.",
            response_metadata={"grounding_metadata": {"grounding_chunks": [
                {"web": {"title": "securityweek.com",
                         "uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc"}},
                {"web": {"title": "undated.com", "uri": ""}},
            ]}},
            additional_kwargs={},
        )

_SETTINGS = types.SimpleNamespace(grounded_search=True, researcher_model="gemini-2.5-pro",
                                  google_api_key="k", tavily_api_key="k")
T.get_settings = lambda: _SETTINGS
check("_resolve_redirect passes ordinary URLs through untouched",
      T._resolve_redirect("https://example.com/a") == "https://example.com/a")
fake_llm = FakeGroundedLLM()
T._make_grounded_llm = lambda s: fake_llm
T._resolve_redirect = lambda uri, timeout=3.0: "https://securityweek.com/real-article"
out = T.search_google_live("Oasis Security latest round")
check("grounded call enables the server-side google_search tool",
      fake_llm.kwargs.get("tools") == [{"google_search": {}}])
check("grounded answer + resolved source URL in output",
      "$120M Series B" in out and "https://securityweek.com/real-article" in out)
check("empty-uri chunks are skipped", "undated.com" not in out)
T._make_grounded_llm = lambda s: FakeGroundedLLM(raise_exc=True)
check("grounding failure degrades to a note", "[Grounded search failed" in T.search_google_live("q"))
_SETTINGS.grounded_search = False
check("flag off -> disabled note, no call", "Grounded search disabled" in T.search_google_live("q"))
_SETTINGS.grounded_search = True
_SETTINGS.researcher_model = "gpt-5"
check("non-Gemini researcher -> unavailable note", "not Gemini" in T.search_google_live("q"))
_SETTINGS.researcher_model = "gemini-2.5-pro"


print("=" * 72); print("Researcher agent: recursion limit covers the >=20-call protocol"); print("=" * 72)
class FakeAgent:
    def __init__(self):
        self.config = None
    def invoke(self, messages, config=None):
        self.config = config
        return {"messages": []}
fa = FakeAgent()
N._run_agent_with_retry(fa, {"messages": []})
check("agent invoked with a raised recursion_limit (default 25 would kill a 20+-call run)",
      (fa.config or {}).get("recursion_limit", 0) >= 60,
      f"got {fa.config}")


print("=" * 72); print("researcher_node: transcript manifest + Source Index"); print("=" * 72)
def _ai(tool_calls):
    return types.SimpleNamespace(type="ai", tool_calls=tool_calls, content="")
def _toolmsg(content):
    return types.SimpleNamespace(type="tool", tool_calls=None, content=content)
TRANSCRIPT = [
    _ai([{"name": "search_market_data", "args": {"query": "sizing " + "y" * 300}},
         {"name": "search_competitor_landscape", "args": {"sector": "agent IAM"}}]),
    _toolmsg("## Tavily Answer\nfacts\n\n## Sources\n[TechCrunch](https://tc.com/a) (published: 2026-01-02)\nsnippet"),
    _ai([{"name": "search_latest_news", "args": {"startup_name": "Oasis"}}]),
    _toolmsg("## Latest News\n[Globes](https://globes.il/b)\nmore\n[TechCrunch](https://tc.com/a)\ndup"),
    _ai([{"name": "search_google_live", "args": {"query": "precision"}}]),
    _toolmsg("## Google Live Search\n[Search failed: boom]"),
    types.SimpleNamespace(type="ai", tool_calls=None, content="THE BRIEF (no urls in prose)"),
]
N._make_llm = lambda *a, **k: None
N.get_settings = lambda: types.SimpleNamespace(
    researcher_model="gemini-2.5-pro", compiler_model="x", judge_model="x",
    analyst_a_model="x", analyst_b_model="x", uploads_dir="/tmp",
)
N._run_agent_with_retry = lambda agent, msgs: {"messages": TRANSCRIPT}
out = N.researcher_node({"market_prompt": "agent IAM"})
mf = out["research_manifest"]
check("manifest counts every tool call incl. parallel batches", mf["total"] == 4)
check("manifest tallies by tool",
      mf["by_tool"].get("search_latest_news") == 1 and mf["by_tool"].get("search_google_live") == 1
      and mf["by_tool"].get("search_market_data") == 1)
check("failed searches counted from tool-message markers", mf["failed"] == 1)
check("call args are truncated", all(len(v) <= 200 for c in mf["calls"] for v in c["args"].values()))
check("Source Index appended with real transcript URLs",
      "## Source Index" in out["research_data"] and "https://globes.il/b" in out["research_data"])
check("Source Index dedupes URLs", out["research_data"].count("https://tc.com/a") == 1)
check("audit log line with counts + shortfall flag",
      "4 searches (1 latest-news, 1 grounded, 1 failed)" in out["agent_logs"][0]
      and "PROTOCOL SHORTFALL" in out["agent_logs"][0]
      and "only 4 calls" in out["agent_logs"][0]
      and "no source URLs" in out["agent_logs"][0])


print("=" * 72); print("_data_freshness: in-code report freshness audit"); print("=" * 72)
MD = ("Oasis raised $120M in March 2026 (source published: 2026-01-02). "
      "Q2 2025 saw consolidation. Teleport's $1.1B is as of Apr 2022. "
      "We predict a winner by 2027.")
fresh = N._data_freshness(MD)
check("newest dated mention wins (bare years ignored)", fresh["newest_dated_mention"] == "2026-03")
check("oldest dated mention tracked", fresh["oldest_dated_mention"] == "2022-04")
check("counts month-year + ISO + quarter mentions only", fresh["dated_mentions"] == 4)
check("lag vs today computed", isinstance(fresh["months_since_newest"], int))
check("no dated mentions -> None (a red flag, not a crash)",
      N._data_freshness("no dates here, maybe by 2027") is None and N._data_freshness("") is None)
check("future-dated predictions are NOT evidence (newest stays past-bounded)",
      N._data_freshness("raised in March 2026; we predict a winner by October 2077")["newest_dated_mention"] == "2026-03")
check("all-future mentions -> None", N._data_freshness("enforcement lands Q4 2088") is None)


print("=" * 72); print("Date grounding: researcher / analyst / compiler messages"); print("=" * 72)
r_msg = N._build_researcher_user_message({"market_prompt": "ambient scribes"})
check("researcher message is date-grounded", "Today's date: 20" in r_msg)
check("researcher told: search results only, never memory", "NOT from memory" in r_msg)
check("researcher told: 20+ calls incl. the freshness pass",
      "at least 20 tool calls" in r_msg and "search_latest_news" in r_msg)
check("as-of dates are conditional — '(date not stated)' fallback, never invented",
      "(date not stated)" in r_msg and "NEVER invent a date" in r_msg)

a_msg = N._build_analyst_user_message({"market_prompt": "ambient scribes", "research_data": "d",
                                       "dimension_weights": None})
check("analyst message is date-grounded", "Today's date: 20" in a_msg)
check("analyst told: newest figure wins on conflict", "most RECENT" in a_msg)

captured = {}
def _fake_invoke(llm, messages, max_retries=8):
    captured["user_msg"] = messages[1][1]
    return types.SimpleNamespace(content="## 0. Investment Take\nstub")
N._make_llm = lambda *a, **k: None
N._invoke_llm_with_retry = _fake_invoke
N._extract_structured_artifacts = lambda *a, **k: (None, None, None)
N._extract_resolved_scores = lambda a, b, s, focal="": ({}, [], None, {}, [], "", None)
N.get_settings = lambda: types.SimpleNamespace(
    compiler_model="x", judge_model="x", researcher_model="x",
    analyst_a_model="x", analyst_b_model="x", uploads_dir="/tmp",
)
_cr = N.compile_report({"agent_a_report": "A", "agent_b_report": "B", "dimension_weights": None,
                        "research_manifest": {"total": 4, "by_tool": {}, "failed": 1}})
check("compiler message is date-grounded", "Today's date: 20" in captured["user_msg"])
check("compiler told: newest figure wins on conflict", "most RECENT" in captured["user_msg"])
check("compiler variant references the analyst reports (not research data it never gets)",
      "analyst reports" in captured["user_msg"])
check("compiler told: dates in prose, never in table cells", "never" in captured["user_msg"] and "table cells" in captured["user_msg"])
check("compiler told: data-as-of stamp + never invent URLs",
      "Research data as of 20" in captured["user_msg"] and "NEVER invent or reconstruct a URL" in captured["user_msg"])
_fr = _cr["final_report"]
check("research_manifest threaded into final_report", (_fr.get("research_manifest") or {}).get("total") == 4)
check("data_freshness computed on the merged report (None on undated stub)",
      "data_freshness" in _fr and _fr["data_freshness"] is None)

_judge_cap = {}
def _fake_invoke_judge(llm, messages, max_retries=8):
    _judge_cap["user_msg"] = messages[1][1]
    return types.SimpleNamespace(content='{"converged": true, "disagreements": []}')
N._invoke_llm_with_retry = _fake_invoke_judge
N.get_settings = lambda: types.SimpleNamespace(
    judge_model="x", max_debate_iterations=3, compiler_model="x",
    analyst_a_model="x", analyst_b_model="x", researcher_model="x", uploads_dir="/tmp",
)
N.judge_node({"agent_a_report": "A", "agent_b_report": "B", "iterations": 0})
check("judge message is date-grounded (recency arbitration, no memory figures)",
      "Today's date: 20" in _judge_cap["user_msg"] and "NEVER arbitrate" in _judge_cap["user_msg"])


print("=" * 72); print("Prompts: freshness protocol wired in"); print("=" * 72)
check("choreography demands >=20 calls", "AT LEAST 20 search tool calls" in TOOL_CHOREOGRAPHY_INSTRUCTIONS)
check("choreography mandates the per-startup freshness pass",
      "FRESHNESS PASS" in TOOL_CHOREOGRAPHY_INSTRUCTIONS
      and "search_latest_news" in TOOL_CHOREOGRAPHY_INSTRUCTIONS)
check("choreography carries RECENCY DISCIPLINE (newest wins, no memory figures)",
      "RECENCY DISCIPLINE" in TOOL_CHOREOGRAPHY_INSTRUCTIONS
      and "MOST RECENT source wins" in TOOL_CHOREOGRAPHY_INSTRUCTIONS)
check("choreography: '(date not stated)' fallback + phase minimums override the 20 floor",
      "(date not stated)" in TOOL_CHOREOGRAPHY_INSTRUCTIONS
      and "OVERRIDE the 20-call floor" in TOOL_CHOREOGRAPHY_INSTRUCTIONS)
check("shared RECENCY rule scopes dates to prose, never table cells",
      "NEVER inside Section 6" in REPORT_TEMPLATE_INSTRUCTIONS)
check("coverage checklist includes freshness + as-of dates",
      "one search_latest_news result per deep-dived startup" in TOOL_CHOREOGRAPHY_INSTRUCTIONS)
check("choreography mandates the per-startup grounded PRECISION CHECK",
      "PRECISION CHECK" in TOOL_CHOREOGRAPHY_INSTRUCTIONS
      and "one search_google_live check per deep-dived startup" in TOOL_CHOREOGRAPHY_INSTRUCTIONS)
check("choreography adds the Phase 4 consolidation sweep + grounded-wins routing",
      "CONSOLIDATION SWEEP" in TOOL_CHOREOGRAPHY_INSTRUCTIONS
      and "WINS on recency" in TOOL_CHOREOGRAPHY_INSTRUCTIONS)
check("choreography mandates the per-incumbent acquisition sweep",
      "PER-INCUMBENT SWEEP" in TOOL_CHOREOGRAPHY_INSTRUCTIONS
      and "one per-incumbent acquisition sweep" in TOOL_CHOREOGRAPHY_INSTRUCTIONS)
check("researcher rules: as-of dates + no-memory-figures",
      "as-of/publication date" in RESEARCHER_SYSTEM and "training knowledge is STALE" in RESEARCHER_SYSTEM)
check("shared sourcing block (analysts+compiler) has the RECENCY rule",
      "RECENCY:" in REPORT_TEMPLATE_INSTRUCTIONS
      and "use the most RECENT" in REPORT_TEMPLATE_INSTRUCTIONS
      and "never average them" in REPORT_TEMPLATE_INSTRUCTIONS)


print("=" * 72)
passed = sum(1 for _, ok in _results if ok); total = len(_results)
print(f"RESULT: {passed}/{total} passed")
if passed != total:
    print("FAILURES:", [n for n, ok in _results if not ok]); sys.exit(1)
print("ALL FRESHNESS-LAYER TESTS PASS (zero API tokens used).")
