"""Token-free tests for focal-startup SCOPE INFERENCE (derive_scope + infer_scope).

Stubs the LLM + search boundary so no API call happens; exercises the real orchestration:
  - derive_scope: parses the model's JSON into {sector, market_prompt, rationale}, None when empty
  - infer_scope: materials path (source='materials'), search-grounding path (source='search'),
    and graceful failure (autoderived=False) when the model can't infer
  - extract_materials_cached: writes/reads the _extracted.txt cache, and the cache file is NOT
    re-ingested as a source

Run:  python3 backend/tests/test_scope.py
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
_stub("pydantic", BaseModel=object, Field=lambda default=None, **k: default, model_validator=lambda **k: (lambda f: f))

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.graph import nodes as N
from app.services import scope as S
from app.services import ingest as I

_results = []
def check(name, cond, detail=""):
    _results.append((name, bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))

_settings = types.SimpleNamespace(judge_model="x")

print("=" * 72); print("derive_scope (LLM stubbed)"); print("=" * 72)
N._make_llm = lambda *a, **k: None
N._invoke_llm_with_retry = lambda llm, msgs, **k: types.SimpleNamespace(
    content='{"sector":"AI Medical Scribes","market_prompt":"Analyze the ambient clinical documentation sector and its competitors thoroughly.","rationale":"materials describe an ICU scribe"}')
d = N.derive_scope("NeuroScribe", "ICU ambient scribe, ex-Abridge founder", _settings)
check("returns sector", d and d["sector"] == "AI Medical Scribes")
check("returns a market_prompt", d and "ambient clinical documentation" in d["market_prompt"])
check("returns rationale", d and "ICU scribe" in d["rationale"])
N._invoke_llm_with_retry = lambda *a, **k: types.SimpleNamespace(content='{"sector":"x"}')  # no market_prompt
check("None when no market_prompt produced", N.derive_scope("X", "ctx", _settings) is None)
check("None when no focal and no context", N.derive_scope("", "", _settings) is None)
# SCOPE-1: a non-string market_prompt (null / object) must NOT coerce to a garbage prompt
N._invoke_llm_with_retry = lambda *a, **k: types.SimpleNamespace(content='{"market_prompt": null, "sector": "x"}')
check("non-string market_prompt (null) -> None (not 'None')", N.derive_scope("X", "ctx", _settings) is None)
N._invoke_llm_with_retry = lambda *a, **k: types.SimpleNamespace(content='{"market_prompt": {"a": 1}}')
check("object market_prompt -> None", N.derive_scope("X", "ctx", _settings) is None)
# non-string sector/rationale alongside a valid prompt -> coerced to "" not "None"
N._invoke_llm_with_retry = lambda *a, **k: types.SimpleNamespace(
    content='{"market_prompt":"Analyze the sector thoroughly please.","sector":null,"rationale":42}')
_d2 = N.derive_scope("X", "ctx", _settings)
check("non-string sector/rationale coerced to '' (not 'None'/'42')", _d2 and _d2["sector"] == "" and _d2["rationale"] == "")

print("=" * 72); print("infer_scope orchestration"); print("=" * 72)
with tempfile.TemporaryDirectory() as parent:
    Path(parent, "up1").mkdir()
    Path(parent, "up1", "deck.txt").write_text("NeuroScribe: stealth ICU ambient scribe.")
    S.get_settings = lambda: types.SimpleNamespace(uploads_dir=parent)
    N.derive_scope = lambda focal, ctx, settings: {"sector": "AI Medical Scribes", "market_prompt": "P" * 30, "rationale": "r"}

    r_mat = S.infer_scope("NeuroScribe", "up1")
    check("materials path -> source='materials'", r_mat["source"] == "materials", f"got {r_mat['source']}")
    check("materials path -> autoderived True + prompt set", r_mat["autoderived"] and len(r_mat["market_prompt"]) >= 30)

    # no upload -> grounding search path (stub tools._tavily_search)
    import app.graph.tools as T
    T._tavily_search = lambda *a, **k: "Search snippet: NeuroScribe builds AI scribes."
    r_srch = S.infer_scope("NeuroScribe", "")
    check("name-only path -> source='search'", r_srch["source"] == "search", f"got {r_srch['source']}")
    check("search path -> autoderived True", r_srch["autoderived"])

    # derive fails -> autoderived False, empty prompt (caller keeps user text)
    N.derive_scope = lambda focal, ctx, settings: None
    r_none = S.infer_scope("NeuroScribe", "up1")
    check("failed derive -> autoderived False", r_none["autoderived"] is False and r_none["market_prompt"] == "")

print("=" * 72); print("extract_materials_cached"); print("=" * 72)
with tempfile.TemporaryDirectory() as d2:
    Path(d2, "a.txt").write_text("alpha facts")
    first = I.extract_materials_cached(d2, vision=False)
    check("first call extracts + writes cache", "alpha facts" in first and Path(d2, "_extracted.txt").is_file())
    Path(d2, "a.txt").write_text("CHANGED")  # change source; cache should win
    second = I.extract_materials_cached(d2, vision=False)
    check("second call reuses cache (no re-parse)", second == first and "CHANGED" not in second)
    # a fresh extract must NOT ingest the _extracted.txt cache file as a source
    raw = I.extract_materials(d2, vision=False)
    check("cache file (_-prefixed) skipped by extract_materials", "_extracted.txt" not in raw and "alpha facts" not in raw and "CHANGED" in raw)

print("=" * 72)
passed = sum(1 for _, ok in _results if ok); total = len(_results)
print(f"RESULT: {passed}/{total} passed")
if passed != total:
    print("FAILURES:", [n for n, ok in _results if not ok]); sys.exit(1)
print("ALL SCOPE TESTS PASS (zero API tokens used).")
