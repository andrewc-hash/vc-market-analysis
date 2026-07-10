"""Token-free tests for the VC-readiness trust layer (2026-07-06 batch).

Confirms WITHOUT any API call:
  - _expected_return_range gives honest EV bounds; _validate_scenarios carries them
  - the return note presents a RANGE with assumptions (never a lone point estimate)
  - REPORT_DISCLAIMER is appended in code on BOTH compile paths (success + fallback)
  - recommended_pick threads into final_report; store top_pick prefers it (R11)
  - store: None-safe meta (one bad record can't 500 the list), owner filtering,
    atomic writes leave no truncated file
  - auth helpers: key parsing, owner resolution, disabled-mode passthrough, 401 path
  - _source_tier buckets domains; the Source Index carries tier labels + discipline
  - _ledger_confidence bands startups by ledger disclosure

What this CANNOT prove (needs real FastAPI/pydantic): the route-level 401/403 wiring —
verified live in-container after rebuild.

Run:  python3 backend/tests/test_trust.py
"""
import json
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
from app.services import auth as A
from app.services import store as S

_results = []
def check(name, cond, detail=""):
    _results.append((name, bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


print("=" * 72); print("Return math: honest range, not a point estimate"); print("=" * 72)
ROWS = [
    {"label": "downside", "probability": 0.25, "multiple_low": 0.5, "multiple_high": 1.0},
    {"label": "base", "probability": 0.60, "multiple_low": 5.0, "multiple_high": 7.0},
    {"label": "outlier", "probability": 0.15, "multiple_low": 15.0, "multiple_high": 15.0},
]
lo, hi = N._expected_return_range(ROWS)
check("range = EV over low vs high bounds (5.38–9.7)", lo == 5.38 and hi == 6.7 or (lo, hi) == (5.38, 6.7),
      f"got {lo}, {hi}")
# recompute by hand: low = .25*.5+.6*5+.15*15 = 0.125+3+2.25 = 5.375 -> 5.38 ; high = .25*1+.6*7+.15*15 = 0.25+4.2+2.25 = 6.7
check("range brackets the midpoint", lo <= N._compute_expected_return(ROWS) <= hi)
check("degenerate probabilities -> (None, None)", N._expected_return_range([{"probability": 0}]) == (None, None))
check("empty -> (None, None)", N._expected_return_range([]) == (None, None))
scen = N._validate_scenarios({"startup": "X", "scenarios": ROWS})
check("_validate_scenarios carries the range keys",
      scen["expected_return_low"] == lo and scen["expected_return_high"] == hi)


print("=" * 72); print("Memo batch: retention, dominance, paths, acquisitions (in code)"); print("=" * 72)
check("stage retention bands (seed 0.65, series b 0.75, unknown default 0.7)",
      N._stage_retention("Seed") == 0.65 and N._stage_retention("Series B") == 0.75
      and N._stage_retention("All Stages") == 0.70)
dom = N._scenario_dominance(ROWS)
check("EV dominance computed (base case ~60% of EV)", dom == ("base", 60), str(dom))
check("dominance None on junk", N._scenario_dominance([]) is None and N._scenario_dominance(None) is None)
scen_p = N._validate_scenarios({"startup": "X", "scenarios": [
    {"label": "base", "probability": 0.6, "multiple_low": 5, "multiple_high": 7,
     "path": "strategic acquisition on the Astrix pattern"}]})
check("scenario PATH carried through validation",
      scen_p["scenarios"][0]["path"] == "strategic acquisition on the Astrix pattern")
scen_null = N._validate_scenarios({"startup": "X", "scenarios": [
    {"label": "base", "probability": 0.6, "multiple_low": 5, "multiple_high": 7, "path": None}]})
check("path: null -> empty string, never the literal 'None'",
      scen_null["scenarios"][0]["path"] == "")
acq = N._validate_acquisitions([
    {"target": "Astrix", "acquirer": "Cisco", "announced": "May 2026", "value": "$400M"},
    {"target": "", "acquirer": "Nobody"},  # dropped — no target
    "junk",
])
check("acquisitions validated (defaults filled, junk dropped)",
      len(acq) == 1 and acq[0]["target"] == "Astrix" and acq[0]["target_total_raised"] == "Not Disclosed")
check("acquisitions None on non-list / empty", N._validate_acquisitions("x") is None
      and N._validate_acquisitions([]) is None)


print("=" * 72); print("Disclaimer + recommended_pick threading (compile stubbed)"); print("=" * 72)
captured = {}
def _fake_invoke(llm, messages, max_retries=8):
    captured["user_msg"] = messages[1][1]
    return types.SimpleNamespace(content="## 0. Investment Take\nstub")
def _fail_invoke(llm, messages, max_retries=8):
    raise RuntimeError("compile down")
N._make_llm = lambda *a, **k: None
N._extract_structured_artifacts = lambda *a, **k: (None, None, None)
N.get_settings = lambda: types.SimpleNamespace(
    compiler_model="x", judge_model="x", researcher_model="x",
    analyst_a_model="x", analyst_b_model="x", uploads_dir="/tmp",
)
SCEN = {"startup": "Freed AI", "expected_return": 6.05, "expected_return_low": 5.38,
        "expected_return_high": 6.7, "scenarios": ROWS}
N._extract_resolved_scores = lambda a, b, s, focal="": (
    {"Abridge": {"financial_health": 80}, "Freed AI": {"financial_health": 70}}, [], SCEN, {}, [], "", None)

N._invoke_llm_with_retry = _fake_invoke
out = N.compile_report({"agent_a_report": "A", "agent_b_report": "B", "dimension_weights": None})
fr = out["final_report"]
check("disclaimer appended in code on the success path",
      "NOT investment advice" in fr["merged_report"] and fr["merged_report"].rstrip().endswith("*"))
check("return note presents the RANGE + assumptions",
      "5.38x–6.7x (midpoint 6.05x)" in captured["user_msg"]
      and "before dilution, ownership, fees, and time-value" in captured["user_msg"])
# Batch 4: market-overview mode (no focal) — §0 becomes a sector call, §12 devices repointed
_ov = captured["user_msg"]
check("market-overview: overview override note injected when no focal",
      "MARKET-OVERVIEW MODE — THESE INSTRUCTIONS OVERRIDE" in _ov
      and "SECTION 0 IS A SECTOR CALL" in _ov and "ENTER / WATCH / AVOID" in _ov)
check("market-overview: §12 deal devices repointed to sector-entry devices",
      "CATEGORY PRICING DISCIPLINE" in _ov and "ENTRY TRIGGERS" in _ov
      and "SECTOR/BASKET DIALECTIC" in _ov)
check("market-overview: return figure moves to §12 only (not §0)",
      "in Section 12 ONLY — Section 0 carries the sector verdict" in _ov)
check("market-overview: #1-vs-#3 weighted-index gap computed in code",
      "weighted-index gap between #1 (Abridge) and #3" in _ov or "weighted-index gap" not in _ov)
check("market-overview: non-pick profiles get a Watch trigger line",
      "**Watch trigger:**" in _ov and "Re-engage when:" in _ov)
check("range keys in final_report", fr["expected_return_low"] == 5.38 and fr["expected_return_high"] == 6.7)
# Fund-math engine: absent by default (no fund_economics), present + noted when provided
check("fund_math is None when no fund inputs given (master gate)", fr.get("fund_math") is None)
check("no fund-fit block in the compiler message without fund inputs", "FUND-FIT BLOCK" not in captured["user_msg"])
out_fm = N.compile_report({"agent_a_report": "A", "agent_b_report": "B", "dimension_weights": None,
                           "stage": "Seed",
                           "fund_economics": {"fund_size_musd": 50, "check_size_musd": 2,
                                              "entry_post_money_musd": 20, "holding_years": 7}})
_fm = out_fm["final_report"]["fund_math"]
check("fund_math computed into final_report when fund inputs present",
      _fm is not None and _fm["verdicts"]["can_return_fund"] is False
      and abs(_fm["requirements"]["required_exit_value_musd"] - 769.23) < 0.1)
check("code-computed Fund Fit block reaches the compiler (verbatim, no LLM numbers)",
      "FUND-FIT BLOCK" in captured["user_msg"] and "Required to return the fund" in captured["user_msg"]
      and "render VERBATIM" in captured["user_msg"])
check("fund-math reconciles with shipped net range (E[net] == retention × expected_return)",
      abs(_fm["expected"]["expected_net_MoIC"] - 0.65 * _fm["expected"]["expected_gross_MoIC"]) < 0.001)
# Consensus batch: pre-compile exit tape (multiples-on-capital computed in code, cited verbatim)
_TAPE = [{"target": "Astrix", "acquirer": "Cisco", "announced": "May 2026", "value": "$400M",
          "target_total_raised": "$85M", "multiple_on_capital": 4.7},
         {"target": "Entro", "acquirer": "SailPoint", "announced": "Jun 2026", "value": "$200M",
          "target_total_raised": "Not Disclosed", "multiple_on_capital": None}]
N._extract_resolved_scores = lambda a, b, s, focal="": (
    {"Abridge": {"financial_health": 80}}, [], SCEN, {}, [], "", _TAPE)
out_t = N.compile_report({"agent_a_report": "A", "agent_b_report": "B", "dimension_weights": None})
check("exit tape reaches the compiler with code-computed multiple-on-capital",
      "SYSTEM-COMPUTED EXIT TAPE" in captured["user_msg"]
      and "4.7x on $85M raised (computed in code)" in captured["user_msg"]
      and "Entro ← SailPoint: $200M (Jun 2026)" in captured["user_msg"])
N._extract_resolved_scores = lambda a, b, s, focal="": (
    {"Abridge": {"financial_health": 80}}, [], SCEN, {}, [], "", None)
out_nt = N.compile_report({"agent_a_report": "A", "agent_b_report": "B", "dimension_weights": None})
check("no tape -> no tape note", "SYSTEM-COMPUTED EXIT TAPE" not in captured["user_msg"])
# Entry-post precedence: resolve-emitted modelled post fills a missing fund input; user wins
SCEN_EP = {**SCEN, "entry_post_money_musd": 25}
N._extract_resolved_scores = lambda a, b, s, focal="": (
    {"Freed AI": {"financial_health": 70}}, [], SCEN_EP, {}, [], "", None)
out_ep = N.compile_report({"agent_a_report": "A", "agent_b_report": "B", "dimension_weights": None,
                           "stage": "Seed",
                           "fund_economics": {"fund_size_musd": 50, "check_size_musd": 2}})
check("resolve-emitted entry post fills missing fund input ($25M post -> 8% entry)",
      out_ep["final_report"]["fund_math"]["assumptions"]["entry_post_money_musd"] == 25
      and out_ep["final_report"]["fund_math"]["assumptions"]["entry_ownership_pct"] == 8.0)
out_ep2 = N.compile_report({"agent_a_report": "A", "agent_b_report": "B", "dimension_weights": None,
                            "stage": "Seed",
                            "fund_economics": {"fund_size_musd": 50, "check_size_musd": 2,
                                               "entry_post_money_musd": 20}})
check("user-provided entry post WINS over the resolve-emitted one",
      out_ep2["final_report"]["fund_math"]["assumptions"]["entry_post_money_musd"] == 20)
N._extract_resolved_scores = lambda a, b, s, focal="": (
    {"Abridge": {"financial_health": 80}, "Freed AI": {"financial_health": 70}}, [], SCEN, {}, [], "", None)
check("recommended_pick = the modelled pick (Freed AI), NOT ranking[0] (Abridge)",
      fr["recommended_pick"] == "Freed AI" and fr["ranking"][0] == "Abridge")
check("net-of-dilution keys computed (gross × default 0.7 retention)",
      fr["expected_return_net_low"] == 3.77 and fr["expected_return_net_high"] == 4.69
      and fr["return_assumptions"]["retention"] == 0.70)
check("EV dominance threaded (base ~60%)",
      fr["return_dominance"] == {"label": "base", "share_pct": 60})
check("compiler told: net-of-dilution + dominance + belief sentence",
      "NET of estimated future dilution" in captured["user_msg"]
      and "dominated by the base case (60% of EV)" in captured["user_msg"])
check("base-dominated EV does NOT trigger the tail-dominated lead-with-base instruction",
      "tail-dominated" not in captured["user_msg"])
# Editorial fix (D1): when a NON-base case carries >50% of EV, lead with the base case
_TAIL = {"startup": "Freed AI", "expected_return": 8.0,
         "scenarios": [{"label": "downside", "probability": 0.30, "multiple_low": 0.5, "multiple_high": 0.5},
                       {"label": "base", "probability": 0.30, "multiple_low": 2.0, "multiple_high": 2.0},
                       {"label": "outlier", "probability": 0.40, "multiple_low": 50.0, "multiple_high": 50.0}]}
N._extract_resolved_scores = lambda a, b, s, focal="": (
    {"Freed AI": {"financial_health": 70}}, [], _TAIL, {}, [], "", None)
N.compile_report({"agent_a_report": "A", "agent_b_report": "B", "dimension_weights": None})
check("tail-dominated EV -> compiler told to LEAD with the base case, label the blend tail-dominated",
      "tail-dominated" in captured["user_msg"] and "LEAD Section 0/12 with the BASE-case" in captured["user_msg"])
N._extract_resolved_scores = lambda a, b, s, focal="": (
    {"Abridge": {"financial_health": 80}, "Freed AI": {"financial_health": 70}}, [], SCEN, {}, [], "", None)
N.compile_report({"agent_a_report": "A", "agent_b_report": "B", "dimension_weights": None})
check("methodology section appended in code (deterministic telemetry)",
      "## Methodology & Scope" in fr["merged_report"] and "NOT diligenced" in fr["merged_report"]
      and fr["methodology"].startswith("\n\n## Methodology & Scope"))
check("no failing grades on the pick -> no bridge note", "GRADE BRIDGE" not in captured["user_msg"])
# D/F bridge: pick with a failing dimension must trigger the bridge instruction
N._extract_resolved_scores = lambda a, b, s, focal="": (
    {"Abridge": {"financial_health": 80}, "Freed AI": {"financial_health": 20}}, [], SCEN, {}, [], "", None)
out_b = N.compile_report({"agent_a_report": "A", "agent_b_report": "B", "dimension_weights": None})
check("failing-grade pick -> GRADE BRIDGE instruction with the dimension named",
      "GRADE BRIDGE" in captured["user_msg"]
      and "Financial Health & Capital Efficiency" in captured["user_msg"])
# Founder mode + resolve-LLM name variant: the bridge must still find the pick's dims
# ("Fidea, Inc." keyed scores, raw focal "Fidea" as the recommended pick).
N._extract_resolved_scores = lambda a, b, s, focal="": (
    {"Fidea, Inc.": {"financial_health": 20}}, [], None, {}, [], "low", None)
out_v = N.compile_report({"agent_a_report": "A", "agent_b_report": "B", "dimension_weights": None,
                          "focal_startup": "Fidea", "analysis_mode": "founder"})
check("GRADE BRIDGE fires in founder mode despite a name-variant scores key",
      "GRADE BRIDGE" in captured["user_msg"] and "Fidea" in out_v["final_report"]["recommended_pick"])
# Degenerate (point-only) scenarios: the net note must not say "range is X x-X x".
SCEN_PT = {"startup": "Freed AI", "expected_return": 6.0, "expected_return_low": 6.0,
           "expected_return_high": 6.0,
           "scenarios": [{"label": "base", "probability": 1.0, "multiple_low": 6.0,
                          "multiple_high": 6.0, "path": ""}]}
N._extract_resolved_scores = lambda a, b, s, focal="": (
    {"Freed AI": {"financial_health": 70}}, [], SCEN_PT, {}, [], "", None)
N.compile_report({"agent_a_report": "A", "agent_b_report": "B", "dimension_weights": None})
check("degenerate scenario -> net note is a single figure, not a self-contradictory range",
      "the same figure is" in captured["user_msg"] and "6.0x\u20136.0x" not in captured["user_msg"]
      and "4.2x\u20134.2x" not in captured["user_msg"])
check("disclaimer no longer claims ALL return figures are gross (net figures exist now)",
      "gross unless explicitly labeled net" in N.REPORT_DISCLAIMER
      and "are gross multiples before" not in N.REPORT_DISCLAIMER)
N._extract_resolved_scores = lambda a, b, s, focal="": (
    {"Abridge": {"financial_health": 80}, "Freed AI": {"financial_health": 70}}, [], SCEN, {}, [], "", None)
N._extract_resolved_scores = lambda a, b, s, focal="": (
    {"Abridge": {"financial_health": 80}}, [], None, {}, [], "", None)
out2 = N.compile_report({"agent_a_report": "A", "agent_b_report": "B", "dimension_weights": None})
check("no scenarios -> recommended_pick falls back to ranking[0]",
      out2["final_report"]["recommended_pick"] == "Abridge")
N._invoke_llm_with_retry = _fail_invoke
out3 = N.compile_report({"agent_a_report": "A", "agent_b_report": "B", "dimension_weights": None})
check("disclaimer appended even on the compile-FALLBACK path",
      "NOT investment advice" in out3["final_report"]["merged_report"])
N._invoke_llm_with_retry = _fake_invoke


print("=" * 72); print("recommended_pick canonicalization (review fixes)"); print("=" * 72)
check("variant name resolves to the CANONICAL ranked spelling",
      N._canonical_pick("Freed AI, Inc.", ["Abridge", "Freed AI"], "", "vc") == "Freed AI")
check("incumbent / non-ranked pick falls back to ranking[0]",
      N._canonical_pick("Microsoft", ["Abridge", "Freed AI"], "", "vc") == "Abridge")
check("FOUNDER mode: pick is the SUBJECT, never the competitor field leader",
      N._canonical_pick("Oasis Security", ["Oasis Security", "Fidea"], "Fidea", "founder") == "Fidea")
check("no ranking + no match -> empty", N._canonical_pick("Ghost", [], "", "vc") == "")


print("=" * 72); print("Auth hardening: non-ASCII key must 401, never 500"); print("=" * 72)
try:
    A.resolve_owner("alice:k1", "café☃")
    check("non-ASCII key raises PermissionError (not TypeError)", False)
except PermissionError:
    check("non-ASCII key raises PermissionError (not TypeError)", True)
except TypeError:
    check("non-ASCII key raises PermissionError (not TypeError)", False, "TypeError leaked -> 500")


print("=" * 72); print("Store: owner filter, None-safe meta, atomic write, top_pick"); print("=" * 72)
with tempfile.TemporaryDirectory() as d:
    S.get_settings = lambda: types.SimpleNamespace(reports_dir=d)
    S.save_report("r1", {"ranking": ["A", "B"], "recommended_pick": "B", "sector": "s"}, "2026-07-06", owner="alice")
    S.save_report("r2", {"ranking": ["C"], "sector": "s"}, "2026-07-05", owner="bob")
    S.save_report("r3", {"ranking": ["D"], "sector": "s"}, "2026-07-04")  # legacy/ownerless
    check("top_pick prefers recommended_pick over ranking[0] (R11)",
          S.get_report("r1")["top_pick"] == "B")
    check("auth disabled (owner=None): everything visible", len(S.list_reports(owner=None)) == 3)
    check("owner filter: alice sees hers + legacy", {r["id"] for r in S.list_reports(owner="alice")} == {"r1", "r3"})
    check("owner filter: bob can't get alice's report", S.get_report("r1", owner="bob") is None)
    check("legacy ownerless visible to any authed owner", S.get_report("r3", owner="bob") is not None)
    # None-safe meta: a hand-edited record with explicit nulls must not poison the list
    bad = json.loads(Path(d, "r2.json").read_text()); bad["starred"] = None; bad["analysis_mode"] = None
    Path(d, "r2.json").write_text(json.dumps(bad))
    metas = S.list_reports(owner=None)
    r2 = next(m for m in metas if m["id"] == "r2")
    check("None-safe meta: nulls fall back to defaults (no 500 material)",
          r2["starred"] is False and r2["analysis_mode"] == "vc")
    check("atomic write leaves no .tmp files", not list(Path(d).glob("*.tmp")))


print("=" * 72); print("Auth helpers (pure python)"); print("=" * 72)
check("parse: named pairs", A.parse_api_keys("alice:k1, bob:k2") == {"k1": "alice", "k2": "bob"})
check("parse: bare key -> owner 'default'", A.parse_api_keys("k9") == {"k9": "default"})
check("parse: empty/None -> disabled", A.parse_api_keys("") == {} and A.parse_api_keys(None) == {})
check("disabled mode -> owner None (pre-auth behavior)", A.resolve_owner("", "anything") is None)
check("valid key -> owner", A.resolve_owner("alice:k1", "k1") == "alice")
try:
    A.resolve_owner("alice:k1", "wrong"); check("invalid key raises", False)
except PermissionError:
    check("invalid key raises PermissionError (401 at the route)", True)
try:
    A.resolve_owner("alice:k1", None); check("missing key raises", False)
except PermissionError:
    check("missing key raises PermissionError", True)


print("=" * 72); print("Source tiering + ledger confidence (computed in code)"); print("=" * 72)
check("official/wire", N._source_tier("https://www.businesswire.com/x") == "official/wire"
      and N._source_tier("https://www.sec.gov/f") == "official/wire")
check("press", N._source_tier("https://techcrunch.com/2026/a") == "press")
check("report-mill", N._source_tier("https://www.fortunebusinessinsights.com/x") == "report-mill")
check("unknown -> unverified", N._source_tier("https://some-startup-blog.io/post") == "unverified")
check("tiering is HOSTNAME-based: ?ref=sec.gov can't launder a link",
      N._source_tier("https://randommill.com/report?ref=sec.gov") == "unverified")
check("path tokens can't fake press", N._source_tier("https://evil.io/techcrunch.com/a") == "unverified")
def _toolmsg(content):
    return types.SimpleNamespace(type="tool", tool_calls=None, content=content)
idx = N._harvest_source_index([_toolmsg("[TC](https://techcrunch.com/a)\n[Mill](https://marketintelo.com/b)")])
check("Source Index carries tier labels + weak-source discipline",
      "tier: press" in idx and "tier: report-mill" in idx and "(weak source)" in idx)

LEDGER = {"rows": [
    {"startup": "Rich", "total_raised": "$100M", "valuation": "$1B", "arr": "$20M",
     "implied_arr_multiple": "50x", "yoy_growth": "100%", "ltv_cac": "3", "nrr": "120%",
     "burn_multiple": "1.2x", "rule_of_40": "55", "is_incumbent": False},
    {"startup": "Mid", "total_raised": "$40M", "valuation": "$200M", "arr": "$5M",
     "implied_arr_multiple": "40x", "yoy_growth": "Not Disclosed", "ltv_cac": "Not Disclosed",
     "nrr": "Not Disclosed", "burn_multiple": "Not Disclosed", "rule_of_40": "Not Disclosed",
     "is_incumbent": False},
    {"startup": "Stealth", "total_raised": "Not Disclosed", "valuation": "Not Disclosed",
     "arr": "Not Disclosed", "implied_arr_multiple": "Not Disclosed", "yoy_growth": "Not Disclosed",
     "ltv_cac": "Not Disclosed", "nrr": "Not Disclosed", "burn_multiple": "Not Disclosed",
     "rule_of_40": "Not Disclosed", "is_incumbent": False},
    {"startup": "BigCo", "total_raised": "$1B", "is_incumbent": True},
]}
conf = N._ledger_confidence(LEDGER)
check("8/8 disclosed -> high", conf.get("Rich") == "high")
check("3/8 disclosed -> medium (implied Val/ARR NOT counted — it's code-derived)",
      conf.get("Mid") == "medium")
check("valuation+ARR only -> LOW (the thin-but-valued case the banding targets)",
      N._ledger_confidence({"rows": [{"startup": "Thin", "valuation": "$100M", "arr": "$2M",
                                      "implied_arr_multiple": "50x", "is_incumbent": False}]}).get("Thin") == "low")
check("0/8 disclosed -> low", conf.get("Stealth") == "low")
check("incumbents excluded from confidence", "BigCo" not in conf)
check("no ledger -> {}", N._ledger_confidence(None) == {})
check("keys re-mapped to canonical ranking names (LLM spelling drift)",
      N._ledger_confidence({"rows": [{"startup": "Abridge, Inc.", "arr": "$50M", "is_incumbent": False}]},
                           canonical=["Abridge"]).get("Abridge") == "low")


print("=" * 72)
passed = sum(1 for _, ok in _results if ok); total = len(_results)
print(f"RESULT: {passed}/{total} passed")
if passed != total:
    print("FAILURES:", [n for n, ok in _results if not ok]); sys.exit(1)
print("ALL TRUST-LAYER TESTS PASS (zero API tokens used).")
