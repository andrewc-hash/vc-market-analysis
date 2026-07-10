"""Adversarial, token-free probe of the scope path. Mirrors the sys.modules stub
preamble from test_scope.py (incl. pydantic.model_validator). Goal: prove that no
branch RAISES and every return shape is well-formed under malformed inputs.
"""
import os, sys, tempfile, types, traceback
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
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""))

def no_raise(name, fn):
    """Run fn(); record PASS if it does not raise, return its value (or None)."""
    try:
        v = fn()
        _results.append((name + " [no raise]", True))
        print(f"  [PASS] {name} [no raise]")
        return v
    except BaseException as e:
        _results.append((name + " [no raise]", False))
        print(f"  [FAIL] {name} [no raise] -- RAISED {type(e).__name__}: {e}")
        traceback.print_exc()
        return "<<RAISED>>"

_settings = types.SimpleNamespace(judge_model="x")
N._make_llm = lambda *a, **k: None

WELLFORMED_KEYS = {"market_prompt", "sector", "rationale", "autoderived", "source"}
def wellformed_infer(r):
    return isinstance(r, dict) and set(r.keys()) == WELLFORMED_KEYS and isinstance(r["autoderived"], bool) \
        and all(isinstance(r[k], str) for k in ("market_prompt", "sector", "rationale", "source"))

# ============================================================ #
print("=" * 72); print("1) derive_scope vs MALFORMED model output (must return None, never raise)"); print("=" * 72)

def set_content(x):
    N._invoke_llm_with_retry = lambda *a, **k: types.SimpleNamespace(content=x)

cases_none = {
    "non-JSON prose":            "This is not JSON at all, just prose about a startup.",
    "truncated/partial JSON":    '{"sector":"AI","market_prompt":',
    "JSON list (non-dict)":      "[1, 2, 3]",
    "JSON bare string":          '"just a string"',
    "JSON bare number":          "42",
    "empty string":              "",
    "whitespace only":           "   \n\t  ",
    "empty object {}":           "{}",
    "dict w/o market_prompt":    '{"sector":"x","rationale":"y"}',
    "market_prompt whitespace":  '{"market_prompt":"   "}',
    "market_prompt null":        '{"market_prompt": null}',
    "market_prompt is a dict":   '{"market_prompt": {"nested":"obj"}}',
    "python-repr dict (bad JSON)": "{'market_prompt': 'x'}",
    "None content":              None,
    "list-of-blocks no text":    [{"type": "image"}, {"foo": "bar"}],
}
for label, payload in cases_none.items():
    set_content(payload)
    r = no_raise(f"derive_scope({label})", lambda: N.derive_scope("Acme", "ctx", _settings))
    if r != "<<RAISED>>":
        check(f"   -> None for {label}", r is None, f"got {r!r}")

# result object with no .content attribute at all
N._invoke_llm_with_retry = lambda *a, **k: 12345
r = no_raise("derive_scope(result has no .content)", lambda: N.derive_scope("Acme", "ctx", _settings))
if r != "<<RAISED>>":
    check("   -> None when result lacks .content", r is None, f"got {r!r}")

# _invoke itself raises (e.g. exhausted retries)
def _boom(*a, **k): raise RuntimeError("rate-limit exhausted")
N._invoke_llm_with_retry = _boom
r = no_raise("derive_scope(_invoke raises)", lambda: N.derive_scope("Acme", "ctx", _settings))
if r != "<<RAISED>>":
    check("   -> None when _invoke raises", r is None, f"got {r!r}")

# well-formed cases (sanity that it still works + last-wins + claude list content + prose wrap)
set_content('{"sector":"AI Scribes","market_prompt":"Analyze the ambient clinical documentation market.","rationale":"r"}')
r = N.derive_scope("Acme", "ctx", _settings)
check("valid JSON -> dict with 3 keys", isinstance(r, dict) and set(r.keys()) == {"sector","market_prompt","rationale"}, f"got {r!r}")
set_content('Sure! {"market_prompt":"FIRST"} ... and {"market_prompt":"SECOND last wins"} done')
r = N.derive_scope("Acme", "ctx", _settings)
check("prose-wrapped + last-object-wins", r and r["market_prompt"] == "SECOND last wins", f"got {r!r}")
set_content([{"type":"text","text":'{"market_prompt":"PCLAUDE","sector":"S"}'}])
r = N.derive_scope("Acme", "ctx", _settings)
check("claude list-content normalized + parsed", r and r["market_prompt"] == "PCLAUDE", f"got {r!r}")
# no focal AND no context -> None without ever invoking llm
N._invoke_llm_with_retry = _boom  # would raise if called
r = no_raise("derive_scope('','')", lambda: N.derive_scope("", "", _settings))
check("no focal + no ctx -> None (llm not called)", r is None, f"got {r!r}")

# ============================================================ #
print("=" * 72); print("2) infer_scope vs bad upload / empty inputs (always well-formed dict)"); print("=" * 72)

with tempfile.TemporaryDirectory() as parent:
    S.get_settings = lambda: types.SimpleNamespace(uploads_dir=parent)
    # make derive_scope deterministic + succeed
    N.derive_scope = lambda focal, ctx, settings: {"sector": "S", "market_prompt": "P" * 40, "rationale": "r"}
    import app.graph.tools as T
    T._tavily_search = lambda *a, **k: "Search snippet about the startup."

    r = no_raise("infer_scope(focal, NONEXISTENT upload)", lambda: S.infer_scope("Acme", "does-not-exist"))
    check("   well-formed shape", wellformed_infer(r), f"got {r!r}")
    check("   nonexistent upload falls back to search", r["source"] == "search", f"source={r.get('source')}")

    r = no_raise("infer_scope(focal='', valid upload)", lambda: S.infer_scope("", "up-empty-name"))
    # 'up-empty-name' doesn't exist -> no materials, no focal -> no search -> derive with empty ctx
    check("   well-formed shape", wellformed_infer(r), f"got {r!r}")

    # both empty
    r = no_raise("infer_scope('','')", lambda: S.infer_scope("", ""))
    check("   well-formed shape", wellformed_infer(r), f"got {r!r}")
    check("   both-empty -> source 'none'", r["source"] == "none", f"source={r.get('source')}")

    # valid upload with real materials -> source 'materials'
    Path(parent, "up1").mkdir()
    Path(parent, "up1", "deck.txt").write_text("Acme builds ambient ICU scribes.")
    r = no_raise("infer_scope(focal, valid upload w/ materials)", lambda: S.infer_scope("Acme", "up1"))
    check("   well-formed shape", wellformed_infer(r), f"got {r!r}")
    check("   materials present -> source 'materials'", r["source"] == "materials", f"source={r.get('source')}")

    # derive_scope returns None -> autoderived False, empty prompt
    N.derive_scope = lambda focal, ctx, settings: None
    r = no_raise("infer_scope(derive returns None)", lambda: S.infer_scope("Acme", "up1"))
    check("   autoderived False + empty prompt", r["autoderived"] is False and r["market_prompt"] == "", f"got {r!r}")
    check("   still well-formed", wellformed_infer(r), f"got {r!r}")

    # derive_scope RAISES inside infer_scope -> infer_scope must swallow + return well-formed
    def _draise(*a, **k): raise RuntimeError("derive boom")
    N.derive_scope = _draise
    r = no_raise("infer_scope(derive RAISES)", lambda: S.infer_scope("Acme", "up1"))
    check("   autoderived False after derive raise", isinstance(r, dict) and r["autoderived"] is False, f"got {r!r}")
    check("   still well-formed", wellformed_infer(r), f"got {r!r}")

    # tavily search RAISES on name-only path -> swallowed
    N.derive_scope = lambda focal, ctx, settings: None
    T._tavily_search = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("tavily down"))
    r = no_raise("infer_scope(tavily raises, name-only)", lambda: S.infer_scope("Acme", ""))
    check("   well-formed after tavily raise", wellformed_infer(r), f"got {r!r}")

    # get_settings raises -> infer_scope itself NOT wrapped at line 29; document behavior
    S.get_settings = lambda: (_ for _ in ()).throw(RuntimeError("settings boom"))
    r = no_raise("infer_scope(get_settings raises) -- UNWRAPPED line 29", lambda: S.infer_scope("Acme", "up1"))
    check("   note: shape if it returned", (r == "<<RAISED>>") or wellformed_infer(r), f"got {r!r}")
    S.get_settings = lambda: types.SimpleNamespace(uploads_dir=parent)

# ============================================================ #
print("=" * 72); print("3) extract_materials_cached vs missing/corrupt cache (never raise, never self-ingest)"); print("=" * 72)

# missing dir
r = no_raise("extract_materials_cached(MISSING dir)", lambda: I.extract_materials_cached("/no/such/dir/xyz", vision=False))
check("   -> '' for missing dir", r == "", f"got {r!r}")

with tempfile.TemporaryDirectory() as d2:
    Path(d2, "a.txt").write_text("alpha facts")
    first = no_raise("extract_materials_cached(first call)", lambda: I.extract_materials_cached(d2, vision=False))
    check("   first extracts + writes cache", "alpha facts" in (first or "") and Path(d2, "_extracted.txt").is_file())
    Path(d2, "a.txt").write_text("CHANGED")
    second = I.extract_materials_cached(d2, vision=False)
    check("   second reuses cache (no re-parse)", second == first and "CHANGED" not in second, f"got {second!r}")
    raw = I.extract_materials(d2, vision=False)
    check("   _extracted.txt skipped by extract_materials", "_extracted.txt" not in raw and "alpha facts" not in raw and "CHANGED" in raw, f"got {raw!r}")

# corrupt/binary cache: must read (errors ignored) without raising
with tempfile.TemporaryDirectory() as d3:
    Path(d3, "a.txt").write_text("source text")
    Path(d3, "_extracted.txt").write_bytes(b"\xff\xfe\x00\x80\x81 corrupt\xc3\x28 bytes")
    r = no_raise("extract_materials_cached(corrupt binary cache)", lambda: I.extract_materials_cached(d3, vision=False))
    check("   returns a str (errors ignored), no raise", isinstance(r, str), f"type={type(r)}")

# cache path is a DIRECTORY (is_file False) -> must fall back to extract, no raise
with tempfile.TemporaryDirectory() as d4:
    Path(d4, "a.txt").write_text("dir-cache fallback text")
    (Path(d4, "_extracted.txt")).mkdir()  # _extracted.txt is a dir
    r = no_raise("extract_materials_cached(_extracted.txt is a DIR)", lambda: I.extract_materials_cached(d4, vision=False))
    check("   falls back to live extract", isinstance(r, str) and "dir-cache fallback" in (r or ""), f"got {r!r}")
    check("   dir-cache not ingested as source", "_extracted.txt" not in (r or ""), f"got {r!r}")

# extract_materials_cached when extract yields '' but dir exists (no parsable files) -> no cache written, no raise
with tempfile.TemporaryDirectory() as d5:
    Path(d5, "weird.xyz").write_text("unsupported ext")
    r = no_raise("extract_materials_cached(only unsupported files)", lambda: I.extract_materials_cached(d5, vision=False))
    check("   -> '' and no cache file written", r == "" and not Path(d5, "_extracted.txt").exists(), f"got {r!r} cache={Path(d5,'_extracted.txt').exists()}")

# ============================================================ #
print("=" * 72); print("4) ingest_focal_materials self-heal (infer_scope raises/None -> node must not crash)"); print("=" * 72)

# focal-only (no upload) so the settings/extract path is skipped; market_prompt empty -> self-heal triggers
def run_ingest(state):
    return N.ingest_focal_materials(state)

# infer_scope RAISES
S.infer_scope = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("infer boom"))
out = no_raise("ingest self-heal (infer_scope RAISES)", lambda: run_ingest({"focal_startup": "Acme", "market_prompt": ""}))
if out != "<<RAISED>>":
    check("   returns dict, no market_prompt injected", isinstance(out, dict) and "market_prompt" not in out, f"got {out!r}")
    check("   agent_logs present + is list", isinstance(out.get("agent_logs"), list))

# infer_scope returns None (defensive: scope.get on None)
S.infer_scope = lambda *a, **k: None
out = no_raise("ingest self-heal (infer_scope returns None)", lambda: run_ingest({"focal_startup": "Acme", "market_prompt": ""}))
if out != "<<RAISED>>":
    check("   returns dict, no crash on None.get", isinstance(out, dict) and "market_prompt" not in out, f"got {out!r}")

# infer_scope returns malformed (missing keys) -> .get tolerates
S.infer_scope = lambda *a, **k: {"market_prompt": "Pheal"}  # no sector key
out = no_raise("ingest self-heal (infer_scope missing 'sector')", lambda: run_ingest({"focal_startup": "Acme", "market_prompt": ""}))
if out != "<<RAISED>>":
    check("   injects market_prompt + defaults sector ''", out.get("market_prompt") == "Pheal" and out.get("sector") == "" and out.get("scope_autoderived") is True, f"got {out!r}")

# happy path self-heal
S.infer_scope = lambda *a, **k: {"market_prompt": "Pgood", "sector": "Sgood", "rationale": "r", "autoderived": True, "source": "search"}
out = no_raise("ingest self-heal (happy)", lambda: run_ingest({"focal_startup": "Acme", "market_prompt": ""}))
if out != "<<RAISED>>":
    check("   market_prompt + sector + flag set", out.get("market_prompt") == "Pgood" and out.get("sector") == "Sgood" and out.get("scope_autoderived") is True, f"got {out!r}")

# market_prompt ALREADY present -> self-heal must NOT run (infer_scope would raise if called)
S.infer_scope = lambda *a, **k: (_ for _ in ()).throw(AssertionError("self-heal ran when it shouldn't"))
out = no_raise("ingest no self-heal when market_prompt present", lambda: run_ingest({"focal_startup": "Acme", "market_prompt": "user typed this"}))
if out != "<<RAISED>>":
    check("   no market_prompt override", "market_prompt" not in out and isinstance(out.get("agent_logs"), list), f"got {out!r}")

# no focal AND no upload -> pure pass-through {}
out = no_raise("ingest pass-through (no focal/upload)", lambda: run_ingest({"market_prompt": ""}))
if out != "<<RAISED>>":
    check("   returns {} pass-through", out == {}, f"got {out!r}")

# ============================================================ #
print("=" * 72)
passed = sum(1 for _, ok in _results if ok); total = len(_results)
print(f"RESULT: {passed}/{total} passed")
if passed != total:
    print("FAILURES:", [n for n, ok in _results if not ok]); sys.exit(1)
print("ALL ADVERSARIAL PROBES PASS (zero API tokens used).")
