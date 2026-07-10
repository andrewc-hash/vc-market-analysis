"""Token-free tests for the deterministic fund-math engine (_compute_fund_math).

Encodes the 8 expert-panel-verified worked test vectors verbatim: each was computed
from scratch by four independent adversarial verifiers and cross-checked, so these
pin every output. The engine answers "does THIS deal return MY fund?" by monetizing
the SHIPPED net-of-dilution invariant (net = gross x stage_retention) through ownership
and dollars — it is structurally impossible for it to contradict the shipped net range.

Run:  python3 backend/tests/test_fund_math.py
"""
import math, os, sys, types

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

def approx(a, b, tol=0.01):
    """None-aware tolerance compare (MoIC/turns to 0.01, $M/% the panel rounds to ~0.1)."""
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= tol

def seq(a, b, tol=0.01):
    return a is not None and len(a) == len(b) and all(approx(x, y, tol) for x, y in zip(a, b))

# The shared scenarios (gross MoIC on the modelled entry).
SCEN_V1 = {"startup": "X", "scenarios": [
    {"label": "downside", "probability": 0.25, "multiple_low": 1.0, "multiple_high": 1.0},
    {"label": "base",     "probability": 0.60, "multiple_low": 6.0, "multiple_high": 6.0},
    {"label": "outlier",  "probability": 0.15, "multiple_low": 15.0, "multiple_high": 15.0},
]}
BASE_FE = {"fund_size_musd": 50, "check_size_musd": 2, "entry_post_money_musd": 20, "holding_years": 7}


print("=" * 72); print("V1 — shared worked example (fund 50 / check 2 / seed post 20 / 7y)"); print("=" * 72)
fm = N._compute_fund_math(SCEN_V1, BASE_FE, "Seed", 0.65)
a = fm["assumptions"]; rows = fm["scenarios"]; exp = fm["expected"]; req = fm["requirements"]; ver = fm["verdicts"]
check("entry ownership 10.0%, at-exit 6.5%",
      approx(a["entry_ownership_pct"], 10.0) and approx(a["ownership_at_exit_pct"], 6.5))
check("implied exit values [20,120,300]$M",
      seq([r["implied_exit_value_musd"] for r in rows], [20, 120, 300], 0.1))
check("gross proceeds [2,12,30]$M", seq([r["gross_proceeds_musd"] for r in rows], [2.0, 12.0, 30.0]))
check("net MoIC [0.65,3.90,9.75]", seq([r["net_MoIC"] for r in rows], [0.65, 3.90, 9.75]))
check("net proceeds [1.30,7.80,19.50]$M", seq([r["net_proceeds_musd"] for r in rows], [1.30, 7.80, 19.50]))
check("net turns [0.026,0.156,0.390]", seq([r["net_turns"] for r in rows], [0.026, 0.156, 0.390]))
check("E[gross]=6.10, E[net_MoIC]=3.965", approx(exp["expected_gross_MoIC"], 6.10) and approx(exp["expected_net_MoIC"], 3.965))
check("E[net proceeds]=7.93$M, E[net turns]=0.1586",
      approx(exp["expected_net_proceeds_musd"], 7.93) and approx(exp["expected_net_turns"], 0.1586))
check("required exit=769.23$M, net 25.0x, gross 38.46x, preserved-ref 500$M",
      approx(req["required_exit_value_musd"], 769.23, 0.1) and approx(req["required_net_MoIC"], 25.0)
      and approx(req["required_gross_MoIC"], 38.46) and approx(req["preserved_ownership_ref_musd"], 500, 0.1))
check("net IRR [-5.97,+21.46,+38.45]%", seq([r["net_irr_pct"] for r in rows], [-5.97, 21.46, 38.45], 0.05))
check("primary E[IRR]=+21.75%, secondary IRR_pw=+17.15%",
      approx(exp["expected_net_irr_pct"], 21.75, 0.05) and approx(exp["expected_net_irr_pw_pct"], 17.15, 0.05))
check("returns_fund all False, can_return_fund False, best turns 0.390",
      [r["returns_fund"] for r in rows] == [False, False, False] and ver["can_return_fund"] is False
      and approx(ver["best_case_net_turns"], 0.390))
check("expected_returns_fund False, is_fund_maker False (all)",
      ver["expected_returns_fund"] is False and ver["is_fund_maker"] is False)
check("no flags on the clean case", fm["flags"] == [])


print("=" * 72); print("V2 — tiny fund ($19M) flips the returner boolean"); print("=" * 72)
fm2 = N._compute_fund_math(SCEN_V1, {**BASE_FE, "fund_size_musd": 19}, "Seed", 0.65)
r2 = fm2["scenarios"]; v2 = fm2["verdicts"]; e2 = fm2["expected"]; q2 = fm2["requirements"]
check("net MoIC unchanged by fund size", seq([r["net_MoIC"] for r in r2], [0.65, 3.90, 9.75]))
check("net turns [0.0684,0.4105,1.0263]", seq([r["net_turns"] for r in r2], [0.068421, 0.410526, 1.026316], 0.001))
check("returns_fund [F,F,T] (19.50>=19), can_return_fund True",
      [r["returns_fund"] for r in r2] == [False, False, True] and v2["can_return_fund"] is True)
check("E[net turns]=0.4174, expected_returns_fund False (7.93<19)",
      approx(e2["expected_net_turns"], 0.417368, 0.001) and v2["expected_returns_fund"] is False)
check("required exit=292.31$M, net 9.5x, gross 14.62x",
      approx(q2["required_exit_value_musd"], 292.31, 0.1) and approx(q2["required_net_MoIC"], 9.5)
      and approx(q2["required_gross_MoIC"], 14.62))
check("is_fund_maker False (max 1.03<3.0)", v2["is_fund_maker"] is False)


print("=" * 72); print("V3 — master gate: no fund_size => fund_math is None"); print("=" * 72)
check("fund_size None -> None", N._compute_fund_math(SCEN_V1, {"check_size_musd": 2, "entry_post_money_musd": 20}, "Seed", 0.65) is None)
check("fund_size 0 -> None", N._compute_fund_math(SCEN_V1, {"fund_size_musd": 0}, "Seed", 0.65) is None)
check("fund_size NaN -> None", N._compute_fund_math(SCEN_V1, {"fund_size_musd": float("nan")}, "Seed", 0.65) is None)
check("no ownership path (no check, no ownership) -> None",
      N._compute_fund_math(SCEN_V1, {"fund_size_musd": 50, "entry_post_money_musd": 20}, "Seed", 0.65) is None)


print("=" * 72); print("V4 — ownership infeasible (check 25 > post 20): clamp is DISPLAY-only"); print("=" * 72)
fm4 = N._compute_fund_math(SCEN_V1, {"fund_size_musd": 50, "check_size_musd": 25, "entry_post_money_musd": 20, "holding_years": 7}, "Seed", 0.65)
a4 = fm4["assumptions"]; r4 = fm4["scenarios"]; v4 = fm4["verdicts"]; q4 = fm4["requirements"]; e4 = fm4["expected"]
check("display ownership clamped to 100%, flag set",
      approx(a4["entry_ownership_pct"], 100.0) and "ownership_infeasible" in fm4["flags"])
check("internal math uses UNCLAMPED ratio: net proceeds [16.25,97.5,243.75]$M",
      seq([r["net_proceeds_musd"] for r in r4], [16.25, 97.5, 243.75], 0.01))
check("net turns [0.325,1.95,4.875]", seq([r["net_turns"] for r in r4], [0.325, 1.95, 4.875]))
check("returns_fund [F,T,T], can_return_fund True", [r["returns_fund"] for r in r4] == [False, True, True] and v4["can_return_fund"] is True)
check("is_fund_maker [F,F,T] deal-level True", [r["is_fund_maker"] for r in r4] == [False, False, True] and v4["is_fund_maker"] is True)
check("E[net proceeds]=99.125, expected_returns_fund True", approx(e4["expected_net_proceeds_musd"], 99.125, 0.01) and v4["expected_returns_fund"] is True)
check("required exit=61.54$M (oversized check already near-returns)", approx(q4["required_exit_value_musd"], 61.54, 0.1))
check("net IRR unchanged (check-independent) [-5.97,+21.46,+38.45]", seq([r["net_irr_pct"] for r in r4], [-5.97, 21.46, 38.45], 0.05))


print("=" * 72); print("V5 — partial degrade: no post, unknown stage -> retention 0.70, H 6"); print("=" * 72)
fm5 = N._compute_fund_math(SCEN_V1, {"fund_size_musd": 50, "check_size_musd": 2}, "Unknownia", 0.70)
a5 = fm5["assumptions"]; r5 = fm5["scenarios"]; e5 = fm5["expected"]; q5 = fm5["requirements"]
check("no post -> entry ownership / exit value / required exit all None",
      a5["entry_ownership_pct"] is None and r5[0]["implied_exit_value_musd"] is None
      and q5["required_exit_value_musd"] is None)
check("net MoIC uses 0.70 [0.70,4.20,10.50]", seq([r["net_MoIC"] for r in r5], [0.70, 4.20, 10.50]))
check("net proceeds [1.40,8.40,21.00]$M", seq([r["net_proceeds_musd"] for r in r5], [1.40, 8.40, 21.00]))
check("E[net MoIC]=4.27, E[net proceeds]=8.54", approx(e5["expected_net_MoIC"], 4.27) and approx(e5["expected_net_proceeds_musd"], 8.54, 0.02))
check("required net 25.0x, gross 35.71x (computable without post)",
      approx(q5["required_net_MoIC"], 25.0) and approx(q5["required_gross_MoIC"], 35.71))
check("net IRR at H=6 [-5.77,+27.02,+47.98]%", seq([r["net_irr_pct"] for r in r5], [-5.77, 27.02, 47.98], 0.05))
check("flag retention_defaulted set", "retention_defaulted" in fm5["flags"])


print("=" * 72); print("V6 — total-loss floor: 0x downside -> -100% IRR, not NaN"); print("=" * 72)
SCEN6 = {"scenarios": [{"label": "down", "probability": 0.5, "multiple_low": 0.0, "multiple_high": 0.0},
                       {"label": "up", "probability": 0.5, "multiple_low": 10.0, "multiple_high": 10.0}]}
fm6 = N._compute_fund_math(SCEN6, BASE_FE, "Seed", 0.65)
r6 = fm6["scenarios"]; e6 = fm6["expected"]
check("net MoIC [0.0,6.5], net proceeds [0.0,13.0]$M",
      seq([r["net_MoIC"] for r in r6], [0.0, 6.5]) and seq([r["net_proceeds_musd"] for r in r6], [0.0, 13.0]))
check("net IRR [-100.0, +30.66]% (floor, finite)", seq([r["net_irr_pct"] for r in r6], [-100.0, 30.66], 0.05))
check("E[gross]=5.0, E[net_MoIC]=3.25, E[net proceeds]=6.50",
      approx(e6["expected_gross_MoIC"], 5.0) and approx(e6["expected_net_MoIC"], 3.25) and approx(e6["expected_net_proceeds_musd"], 6.50))
check("primary E[IRR]=+18.34%, secondary IRR_pw=-34.67%",
      approx(e6["expected_net_irr_pct"], 18.34, 0.05) and approx(e6["expected_net_irr_pw_pct"], -34.67, 0.05))
check("no NaN/complex anywhere", all(r["net_irr_pct"] is None or math.isfinite(r["net_irr_pct"]) for r in r6))


print("=" * 72); print("V7 — sub-quarter horizon suppresses IRR only"); print("=" * 72)
fm7 = N._compute_fund_math(SCEN_V1, {**BASE_FE, "holding_years": 0.1}, "Seed", 0.65)
r7 = fm7["scenarios"]
check("MoIC/turns/booleans identical to V1", seq([r["net_MoIC"] for r in r7], [0.65, 3.90, 9.75])
      and fm7["verdicts"]["can_return_fund"] is False and approx(fm7["requirements"]["required_exit_value_musd"], 769.23, 0.1))
check("all IRR None (per-scenario + expected)",
      all(r["net_irr_pct"] is None for r in r7) and fm7["expected"]["expected_net_irr_pct"] is None
      and fm7["expected"]["expected_net_irr_pw_pct"] is None)
check("flag holding_too_short set", "holding_too_short" in fm7["flags"])


print("=" * 72); print("V8 — probability renormalization (psum=1.10)"); print("=" * 72)
SCEN8 = {"scenarios": [{"label": "down", "probability": 0.30, "multiple_low": 1.0, "multiple_high": 1.0},
                       {"label": "base", "probability": 0.60, "multiple_low": 6.0, "multiple_high": 6.0},
                       {"label": "out", "probability": 0.20, "multiple_low": 15.0, "multiple_high": 15.0}]}
fm8 = N._compute_fund_math(SCEN8, BASE_FE, "Seed", 0.65)
e8 = fm8["expected"]; r8 = fm8["scenarios"]
check("E[gross]=6.2727 (renormalized by 1.10, == _compute_expected_return)",
      approx(e8["expected_gross_MoIC"], 6.2727, 0.001) and approx(N._compute_expected_return(SCEN8["scenarios"]), e8["expected_gross_MoIC"], 0.01))
check("E[net_MoIC]=4.0773, E[net proceeds]=8.1545$M, E[net turns]=0.16309",
      approx(e8["expected_net_MoIC"], 4.0773, 0.001) and approx(e8["expected_net_proceeds_musd"], 8.1545, 0.01)
      and approx(e8["expected_net_turns"], 0.16309, 0.001))
check("primary E[IRR]=+22.24%", approx(e8["expected_net_irr_pct"], 22.24, 0.05))
check("per-scenario rows unchanged from V1", seq([r["net_MoIC"] for r in r8], [0.65, 3.90, 9.75]))


print("=" * 72); print("RECONCILIATION — engine's expected net == shipped net range midpoint"); print("=" * 72)
# The whole point: E[net_MoIC] must equal retention x expected_return (the shipped invariant).
_er = N._compute_expected_return(SCEN_V1["scenarios"])
check("E[net_MoIC] == retention x expected_return (byte-identical to shipped)",
      approx(exp["expected_net_MoIC"], 0.65 * _er, 0.001))
lo, hi = N._expected_return_range(SCEN_V1["scenarios"])
check("shipped net range midpoint == engine expected net MoIC",
      approx((lo + hi) / 2 * 0.65, exp["expected_net_MoIC"], 0.001))


print("=" * 72)
passed = sum(1 for _, ok in _results if ok); total = len(_results)
print(f"RESULT: {passed}/{total} passed")
if passed != total:
    print("FAILURES:", [n for n, ok in _results if not ok]); sys.exit(1)
print("ALL FUND-MATH TESTS PASS (8 verified vectors + reconciliation; zero API tokens).")
