"""Token-free tests for the in-code validation of market_map + financial_ledger.

Stubs the heavy LLM deps and tests the REAL validators from app.graph.nodes — no
API calls. Confirms the UI always gets a well-formed shape (or None), never raw
LLM output.

Run:  python3 backend/tests/test_structured_artifacts.py
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

print("=" * 72); print("market_map validator"); print("=" * 72)

VALID_MAP = {
    "axes": {"x": {"label": "Control", "low": "Deterministic", "high": "Probabilistic"},
             "y": {"label": "Depth", "low": "App", "high": "Kernel"}},
    "quadrants": [{"name": "White space", "x": "low", "y": "high"}, {"x": "low"}],  # 2nd dropped (no name)
    "white_space": {"x": 30, "y": 85, "label": "WS"},
    "companies": [
        {"name": "KernelGuard", "x": 150, "y": -5, "segment": "RT", "stage": "Series A",
         "raised_usd_m": "18", "weighted_score": 50, "rationale": "eBPF"},   # x/y clamped, raised coerced
        {"name": "", "x": 50, "y": 50},          # dropped: no name
        {"name": "NoPos", "segment": "x"},        # dropped: no position
    ],
}
WS = {"KernelGuard": {"weighted_score": 84}}     # authoritative — must override the LLM's 50
mm = N._validate_market_map(VALID_MAP, WS)
check("returns a dict for valid input", mm is not None)
check("axes preserved", mm and mm["axes"]["x"]["label"] == "Control" and mm["axes"]["y"]["high"] == "Kernel")
check("only well-formed companies kept (1 of 3)", mm and len(mm["companies"]) == 1)
kg = mm["companies"][0] if mm else {}
check("x/y clamped into [0,100]", kg.get("x") == 100 and kg.get("y") == 0, f"x={kg.get('x')} y={kg.get('y')}")
check("raised_usd_m coerced from string", kg.get("raised_usd_m") == 18.0)
check("weighted_score backfilled from AUTHORITATIVE scores (84, not LLM's 50)", kg.get("weighted_score") == 84)
check("quadrant without a name dropped (1 kept)", mm and len(mm["quadrants"]) == 1)
check("white_space coerced", mm and mm["white_space"]["x"] == 30 and mm["white_space"]["y"] == 85)

check("None when axes missing", N._validate_market_map({"companies": [{"name": "X", "x": 1, "y": 1}]}, {}) is None)
check("None when no valid companies",
      N._validate_market_map({"axes": VALID_MAP["axes"], "companies": []}, {}) is None)
check("None for non-dict input", N._validate_market_map("nope", {}) is None)
check("numeric-string x/y accepted",
      (N._validate_market_map({"axes": VALID_MAP["axes"],
                               "companies": [{"name": "Q", "x": "40", "y": "60"}]}, {}) or {}).get("companies", [{}])[0].get("x") == 40.0)

# crash-safety: a truthy non-list for companies/quadrants must NOT raise (was a TypeError)
check("companies as non-list scalar -> None, no crash",
      N._validate_market_map({"axes": VALID_MAP["axes"], "companies": 7}, {}) is None)
check("quadrants as non-list scalar -> dropped, no crash",
      (N._validate_market_map({"axes": VALID_MAP["axes"], "quadrants": 4,
                               "companies": [{"name": "Q", "x": 1, "y": 1}]}, {}) or {}).get("quadrants") == [])
check("quadrant x/y coerced to the low/high enum",
      (N._validate_market_map({"axes": VALID_MAP["axes"],
                               "quadrants": [{"name": "Q1", "x": "HIGH", "y": "garbage"}],
                               "companies": [{"name": "C", "x": 1, "y": 1}]}, {}) or {})["quadrants"][0]
      == {"name": "Q1", "x": "high", "y": "low"})
check("is_incumbent passthrough",
      (N._validate_market_map({"axes": VALID_MAP["axes"],
                               "companies": [{"name": "Inc", "x": 50, "y": 50, "is_incumbent": True}]}, {}) or {})["companies"][0]["is_incumbent"] is True)
check("white_space (0,0) rejected -> None (degenerate default)",
      (N._validate_market_map({"axes": VALID_MAP["axes"], "white_space": {"x": 0, "y": 0},
                               "companies": [{"name": "C", "x": 1, "y": 1}]}, {}) or {}).get("white_space") is None)
check("white_space non-(0,0) kept",
      ((N._validate_market_map({"axes": VALID_MAP["axes"], "white_space": {"x": 30, "y": 80},
                                "companies": [{"name": "C", "x": 1, "y": 1}]}, {}) or {}).get("white_space") or {}).get("x") == 30)

print("=" * 72); print("_validate_resolved_scores (analyst reconciliation)"); print("=" * 72)
rs = N._validate_resolved_scores({
    "Alpha": {"financial_health": 80, "defensibility": "70", "market_urgency": 60, "founder_market_fit": 50, "regulatory_alignment": 150},
    "Beta": {"financial_health": 40},   # partial — keep present dims
    "": {"financial_health": 50},        # dropped: no name
    "Gamma": "nope",                     # dropped: not a dict
})
check("valid startup coerced (numeric string)", rs.get("Alpha", {}).get("defensibility") == 70.0)
check("out-of-range clamped to 100", rs.get("Alpha", {}).get("regulatory_alignment") == 100.0)
check("partial startup kept with present dims", rs.get("Beta") == {"financial_health": 40.0})
check("nameless / non-dict startups dropped", "" not in rs and "Gamma" not in rs)
check("non-dict input -> {}", N._validate_resolved_scores(7) == {})

print("=" * 72); print("financial_ledger validator"); print("=" * 72)

LED = {"rows": [
    {"startup": "KG", "stage": "Series A", "arr": "$6M",
     "flags": {"burn_multiple": "warn", "arr": "bogus", "not_a_col": "ok"}},
    {"name": "RS", "valuation": "$55M"},    # 'name' fallback for startup
    {"foo": "bar"},                          # dropped: no startup/name
]}
led = N._validate_financial_ledger(LED)
check("returns a dict for valid rows", led is not None)
check("rows without a name dropped (2 of 3)", led and len(led["rows"]) == 2)
r0 = led["rows"][0] if led else {}
check("present value kept", r0.get("arr") == "$6M")
check("missing value -> 'Not Disclosed'", r0.get("total_raised") == "Not Disclosed")
check("flags filtered to ok/warn/bad on real columns only", r0.get("flags") == {"burn_multiple": "warn"},
      f"flags={r0.get('flags')}")
check("'name' falls back to startup", led and led["rows"][1]["startup"] == "RS")
check("columns + stage_banded present", led and led.get("columns") and led.get("stage_banded") is True)
check("accepts a bare list of rows", N._validate_financial_ledger([{"startup": "Z"}]) is not None)
check("None for empty rows", N._validate_financial_ledger({"rows": []}) is None)
check("None for non-dict/list", N._validate_financial_ledger(42) is None)

print("=" * 72); print("_last_balanced_json (shared JSON extractor)"); print("=" * 72)
check("extracts the LAST top-level object", N._last_balanced_json('a {"a":1} b {"b":2} c') == {"b": 2})
check("keeps NESTED objects whole (not an inner fragment)", N._last_balanced_json('x {"k":{"n":3}} y') == {"k": {"n": 3}})
check("verdict-shaped nested object kept whole (judge path)",
      N._last_balanced_json('verdict: {"agreed":true,"resolved_scores":{"KG":{"financial_health":84}}}')
      == {"agreed": True, "resolved_scores": {"KG": {"financial_health": 84}}})
check("None when no JSON", N._last_balanced_json("just prose, no braces") is None)
check("STRING-AWARE: brace inside a string value doesn't corrupt the parse",
      N._last_balanced_json('{"synthesis":"score is high }{ weird","agreed":true}')
      == {"synthesis": "score is high }{ weird", "agreed": True})

print("=" * 72); print("_parse_money"); print("=" * 72)
check("'$850M' -> 850", N._parse_money("$850M") == 850.0)
check("'1.2B' scaled to millions -> 1200", N._parse_money("1.2B") == 1200.0)
check("'$900K' scaled to millions -> 0.9 (field_stats sum can't inflate 1000x)",
      N._parse_money("$900K") == 0.9)
check("'750 thousand' -> 0.75", N._parse_money("750 thousand") == 0.75)
check("unit letter must be ATTACHED to the number: '45 (weak)' -> 45, not billions",
      N._parse_money("45 (weak)") == 45.0)

print("=" * 72); print("Exit tape: multiple-on-capital computed in code"); print("=" * 72)
check("$400M / $85M -> 4.7x", N._acq_multiple_on_capital("$400M", "$85M") == 4.7)
check(">$1B / $195M -> 5.1x ('>' stripped by the money parser)",
      N._acq_multiple_on_capital(">$1B", "$195M") == 5.1)
check("Not Disclosed on either side -> None",
      N._acq_multiple_on_capital("$400M", "Not Disclosed") is None
      and N._acq_multiple_on_capital("Not Disclosed", "$85M") is None)
check("zero/negative raised -> None", N._acq_multiple_on_capital("$400M", "$0M") is None)
_acq2 = N._validate_acquisitions([
    {"target": "Astrix", "acquirer": "Cisco", "value": "$400M", "target_total_raised": "$85M"},
    {"target": "Entro", "acquirer": "SailPoint", "value": "$200M"},
])
check("_validate_acquisitions computes multiple_on_capital per row (None when raised absent)",
      _acq2[0]["multiple_on_capital"] == 4.7 and _acq2[1]["multiple_on_capital"] is None)

print("=" * 72); print("Exit-dollar-derived scenario multiples (computed in code)"); print("=" * 72)
_sc = N._validate_scenarios({"startup": "X", "entry_post_money_musd": 20, "scenarios": [
    # stated 50x vs exit $300M on $20M entry = 15x -> >25% off -> exit-derived override
    {"label": "outlier", "probability": 0.2, "multiple_low": 50, "multiple_high": 50,
     "exit_value_low_musd": 300, "exit_value_high_musd": 300},
    # no stated multiple, exit $120M -> derived 6x fills it
    {"label": "base", "probability": 0.6, "exit_value_low_musd": 120, "exit_value_high_musd": 140},
    # stated 1x vs exit $22M/$20M = 1.1x -> within 25% -> stated kept
    {"label": "down", "probability": 0.2, "multiple_low": 1.0, "multiple_high": 1.0,
     "exit_value_low_musd": 22, "exit_value_high_musd": 22},
]})
check("inflated stated multiple overridden by exit÷entry (50x -> 15x, tagged)",
      _sc["scenarios"][0]["multiple_low"] == 15.0 and _sc["scenarios"][0]["multiple_source"] == "exit-derived")
check("missing multiple filled from exit dollars (6x-7x, tagged)",
      _sc["scenarios"][1]["multiple_low"] == 6.0 and _sc["scenarios"][1]["multiple_high"] == 7.0
      and _sc["scenarios"][1]["multiple_source"] == "exit-derived")
check("stated multiple within 25% of derived is KEPT (stated)",
      _sc["scenarios"][2]["multiple_low"] == 1.0 and _sc["scenarios"][2]["multiple_source"] == "stated")
check("entry post + exit values carried through",
      _sc["entry_post_money_musd"] == 20 and _sc["scenarios"][0]["exit_value_low_musd"] == 300)
_sc2 = N._validate_scenarios({"startup": "X", "scenarios": [
    {"label": "base", "probability": 1.0, "multiple_low": 5, "multiple_high": 5,
     "exit_value_low_musd": 300, "exit_value_high_musd": 300}]})
check("no entry post -> stated multiples untouched, no derivation",
      _sc2["scenarios"][0]["multiple_low"] == 5 and _sc2["scenarios"][0]["multiple_source"] == "stated"
      and "entry_post_money_musd" not in _sc2)

print("=" * 72); print("Arithmetic lint: stated products must compute"); print("=" * 72)
_bad = "## 2. Sizing\n\nWe size the market as 50,000 accounts × $40k ACV = $200M SAM.\n\n## 3. Next\nok"
_good = "## 2. Sizing\n\nWe size the market as 50,000 accounts × $40k ACV = $2.0B SAM.\n\n## 3. Next\nok"
_f = N._lint_arithmetic(_bad)
check("10x sizing error detected, located in §2",
      len(_f) == 1 and _f[0]["section"] == 2 and _f[0]["computed"] == 2000.0 and _f[0]["stated"] == 200.0)
check("correct product passes", N._lint_arithmetic(_good) == [])
check("percent factors handled (50% × $10M = $5M passes)",
      N._lint_arithmetic("## 2. S\n50% × $10M = $5M") == [])
check("approx claims get 15% tolerance",
      N._lint_arithmetic("## 2. S\n~3,000 × $120k = ~$380M") == []
      and len(N._lint_arithmetic("## 2. S\n~3,000 × $120k = ~$500M")) == 1)
check("range first-half cannot bind as a factor (no false positive)",
      N._lint_arithmetic("## 2. S\nraises of $1M-$1.5M × 5 deals = $7M total") == [])
check("empty/None input safe", N._lint_arithmetic("") == [] and N._lint_arithmetic(None) == [])

print("=" * 72); print("Arithmetic repair: bounded, invariant-guarded splice"); print("=" * 72)
_SET = types.SimpleNamespace(compiler_model="x")
_orig_invoke = N._invoke_llm_with_retry
_orig_make = N._make_llm
N._make_llm = lambda *a, **k: None
N._invoke_llm_with_retry = lambda llm, messages, max_retries=8: types.SimpleNamespace(
    content="## 2. Sizing\n\nWe size the market as 50,000 accounts × $40k ACV = $2.0B SAM.")
_rep = N._repair_arithmetic(_bad, _SET)
check("failing section repaired and spliced; rest of report intact",
      "= $2.0B SAM" in _rep and "= $200M SAM" not in _rep and "## 3. Next" in _rep)
check("repaired report passes re-lint", N._lint_arithmetic(_rep) == [])
# A repair that still fails lint must be DISCARDED (original kept)
N._invoke_llm_with_retry = lambda llm, messages, max_retries=8: types.SimpleNamespace(
    content="## 2. Sizing\n\nStill wrong: 50,000 accounts × $40k ACV = $300M SAM.")
check("bad repair (fails re-lint) discarded — original kept",
      "= $200M SAM" in N._repair_arithmetic(_bad, _SET))
# A repair that drops the canonical header must be discarded
N._invoke_llm_with_retry = lambda llm, messages, max_retries=8: types.SimpleNamespace(
    content="Sizing prose without a header 50,000 × $40k = $2.0B")
check("repair without the canonical header discarded",
      "= $200M SAM" in N._repair_arithmetic(_bad, _SET))
check("clean report never triggers a repair call", N._repair_arithmetic(_good, _SET) == _good)
N._invoke_llm_with_retry = _orig_invoke
N._make_llm = _orig_make
check("bare '30' -> 30", N._parse_money("30") == 30.0)
check("'110%' -> 110 (unit-free ratio side)", N._parse_money("110%") == 110.0)
check("'Not Disclosed' -> None", N._parse_money("Not Disclosed") is None)
check("bool rejected", N._parse_money(True) is None)
check("non-finite numbers rejected (inf/nan)",
      N._parse_money(float("inf")) is None and N._as_score(float("nan")) is None
      and N._as_score(float("inf")) is None)

print("=" * 72); print("_sanitize_citations: dead Works Cited placeholders -> honest unverified"); print("=" * 72)
_wc = ("## Works Cited\n"
       "[34] Unspecified source from Analyst B report.\n"
       "[35] [Real](https://x.com) — good source\n"
       "36. Analyst A report\n"
       "[37] [SEC](https://sec.gov) filing\n")
_san = N._sanitize_citations(_wc)
check("placeholder 'Unspecified source' entry relabeled, number preserved",
      "Unspecified source" not in _san and "[34] (analyst estimate — unverified" in _san)
check("bare 'Analyst A report' placeholder relabeled too", "36. (analyst estimate — unverified" in _san)
check("real citations with URLs are untouched",
      "[35] [Real](https://x.com) — good source" in _san and "[37] [SEC](https://sec.gov) filing" in _san)
check("both placeholders relabeled (count)", _san.count("unverified; no source URL") == 2)
check("empty/None input is safe", N._sanitize_citations("") == "" and N._sanitize_citations(None) is None)
check("a real 'source' word in prose is not mangled",
      N._sanitize_citations("The primary source confirms growth.") == "The primary source confirms growth.")

print("=" * 72); print("R1: incumbents dropped from resolved scores"); print("=" * 72)
_rs = N._validate_resolved_scores(
    {"Abridge": {"financial_health": 80}, "Nuance DAX": {"financial_health": 90}},
    incumbents=["nuance dax"],   # case/space-insensitive match
)
check("incumbent dropped from scorecard", "Nuance DAX" not in _rs and "Abridge" in _rs)
check("no incumbents arg -> nothing dropped",
      set(N._validate_resolved_scores({"Abridge": {"financial_health": 80}, "Nuance DAX": {"defensibility": 90}}))
      == {"Abridge", "Nuance DAX"})

print("=" * 72); print("R7/R3: ledger implied multiple + canonical backfill + incumbent sort"); print("=" * 72)
_l = N._validate_financial_ledger(
    {"rows": [
        {"startup": "Abridge", "valuation": "$850M", "arr": "$30M"},   # 850/30 = 28.3x
        {"startup": "Nuance", "valuation": "Not Disclosed", "arr": "Not Disclosed"},
    ]},
    canonical=["Abridge", "Nabla"],     # Nabla missing -> backfilled
    incumbents=["Nuance"],
)
_by = {r["startup"]: r for r in _l["rows"]}
check("implied_arr_multiple computed in code (28.3x)", _by["Abridge"]["implied_arr_multiple"] == "28.3x")
check("implied multiple 'Not Disclosed' when inputs missing", _by["Nuance"]["implied_arr_multiple"] == "Not Disclosed")
check("R3 backfills missing ranked startup (Nabla)", "Nabla" in _by and _by["Nabla"]["arr"] == "Not Disclosed")
check("incumbent flagged from incumbents list", _by["Nuance"]["is_incumbent"] is True)
check("incumbent sorted LAST", _l["rows"][-1]["startup"] == "Nuance")
check("implied_arr_multiple is a column", "implied_arr_multiple" in _l["columns"])

print("=" * 72); print("R1: market_map forces is_incumbent + nulls its score"); print("=" * 72)
_mm = N._validate_market_map(
    {"axes": VALID_MAP["axes"], "companies": [{"name": "Nuance", "x": 60, "y": 70, "weighted_score": 88}]},
    {"Nuance": {"weighted_score": 88}},   # even with a score present...
    incumbents=["Nuance"],
)
_c = _mm["companies"][0] if _mm else {}
check("incumbent flag forced from list", _c.get("is_incumbent") is True)
check("incumbent weighted_score nulled (reference only)", _c.get("weighted_score") is None)

print("=" * 72); print("R6: probability-weighted return computed in code"); print("=" * 72)
_sc = N._validate_scenarios({"startup": "Abridge", "scenarios": [
    {"label": "downside", "probability": 0.25, "multiple_low": 0.5, "multiple_high": 1.0},
    {"label": "base", "probability": 0.60, "multiple_low": 5, "multiple_high": 7},
    {"label": "outlier", "probability": 0.15, "multiple_low": 15, "multiple_high": 15},
]})
# 0.25*0.75 + 0.6*6 + 0.15*15 = 6.0375 -> 6.04
check("expected return = Σ p × midpoint (6.04)", _sc["expected_return"] == 6.04, f"got {_sc['expected_return']}")
check("scenario startup carried", _sc["startup"] == "Abridge")
check("percent probabilities (>1) normalized to fractions",
      N._validate_scenarios({"scenarios": [{"label": "a", "probability": 50, "multiple": 2},
                                            {"label": "b", "probability": 50, "multiple": 4}]})["expected_return"] == 3.0)
check("probabilities renormalized when they don't sum to 1",
      N._compute_expected_return([{"probability": 0.55, "multiple_low": 2, "multiple_high": 2},
                                  {"probability": 0.55, "multiple_low": 4, "multiple_high": 4}]) == 3.0)
check("None when no usable scenarios", N._validate_scenarios({"scenarios": []}) is None)
check("None for non-dict", N._validate_scenarios(7) is None)
check("non-finite scenario multiples -> None EV",
      N._compute_expected_return([{"probability": 0.5, "multiple_low": float("inf"), "multiple_high": float("inf")}]) is None)
check("malformed scenario rows don't raise (missing prob / non-dict)",
      N._compute_expected_return([{"multiple_low": 2, "multiple_high": 4}, "junk", {"probability": 1.0, "multiple_low": 3, "multiple_high": 3}]) == 3.0)

print("=" * 72); print("R10: Defensibility = mean of 4 moat sub-scores (in code)"); print("=" * 72)
_subs_in = {"Abridge": {"economies_of_scale": 60, "differentiated_technology": 80,
                        "network_effects": 90, "brand_power": 70},
            "Ghost": {"economies_of_scale": 50}}   # Ghost not in valid_names -> dropped
_ms = N._validate_moat_subscores(_subs_in, ["Abridge"])
check("moat subs kept only for valid scored startups", set(_ms) == {"Abridge"})
check("4 sub-scores coerced", _ms["Abridge"]["network_effects"] == 90.0)
_rs2 = {"Abridge": {"defensibility": 65.0, "financial_health": 70.0}}
N._apply_moat_reconciliation(_rs2, _ms)
check("Defensibility overwritten to mean(60,80,90,70)=75.0", _rs2["Abridge"]["defensibility"] == 75.0,
      f"got {_rs2['Abridge']['defensibility']}")
check("other dimensions untouched", _rs2["Abridge"]["financial_health"] == 70.0)
# name-insensitive match + partial sub-scores
_rs3 = {"Abridge AI": {"defensibility": 40.0}}
N._apply_moat_reconciliation(_rs3, {"abridge ai": {"economies_of_scale": 20, "brand_power": 40}})
check("name-insensitive match + mean of PRESENT subs (20,40)=30.0", _rs3["Abridge AI"]["defensibility"] == 30.0,
      f"got {_rs3['Abridge AI']['defensibility']}")

print("=" * 72); print("R13: pre-PMF startups dropped from scoring"); print("=" * 72)
_rs4 = N._validate_resolved_scores(
    {"Abridge": {"financial_health": 80}, "Tali": {"financial_health": 50}},
    incumbents=[], pre_pmf=["tali"],
)
check("pre-PMF startup dropped from scorecard", "Tali" not in _rs4 and "Abridge" in _rs4)
check("incumbent + pre-PMF both drop together",
      set(N._validate_resolved_scores(
          {"Abridge": {"defensibility": 70}, "Nuance": {"defensibility": 90}, "Tali": {"defensibility": 40}},
          incumbents=["Nuance"], pre_pmf=["Tali"])) == {"Abridge"})

print("=" * 72); print("Focal startup: protected from R1/R13 exclusion"); print("=" * 72)
# A user's focal startup is force-kept even if the LLM mislabels it incumbent/pre-PMF.
_rsf = N._validate_resolved_scores(
    {"MyCo": {"financial_health": 60}, "Nuance": {"financial_health": 90}, "Tali": {"financial_health": 40}},
    incumbents=["Nuance"], pre_pmf=["MyCo", "Tali"], protect="myco",  # case-insensitive
)
check("focal kept despite being in pre_pmf", "MyCo" in _rsf)
check("non-focal pre_pmf + incumbent still dropped", "Tali" not in _rsf and "Nuance" not in _rsf)
check("no protect -> focal would drop (baseline)",
      "MyCo" not in N._validate_resolved_scores({"MyCo": {"financial_health": 60}}, pre_pmf=["MyCo"]))

print("=" * 72)
passed = sum(1 for _, ok in _results if ok); total = len(_results)
print(f"RESULT: {passed}/{total} passed")
if passed != total:
    print("FAILURES:", [n for n, ok in _results if not ok]); sys.exit(1)
print("ALL STRUCTURED-ARTIFACT VALIDATOR TESTS PASS (zero API tokens used).")
