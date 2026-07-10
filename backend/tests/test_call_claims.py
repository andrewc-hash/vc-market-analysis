"""Token-free tests for the founder-call ingest + claim-audit validators.

Covers: subtitle parsing (.vtt/.srt) with [mm:ss] flattening, transcript tagging +
split_transcripts (services/ingest), and the claim validators in app.graph.nodes
(_validate_call_claims / _validate_claim_audit) with the LLM deps stubbed.

Run:  python3 backend/tests/test_call_claims.py
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
from app.services import ingest as I
from app.graph import nodes as N

_results = []
def check(name, cond, detail=""):
    _results.append((name, bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))

print("=" * 72); print("subtitle parsing (.vtt/.srt)"); print("=" * 72)

VTT = """WEBVTT

NOTE created by test

00:00:05.000 --> 00:00:08.000
<v Founder>We're at two million in ARR today.

00:01:15.500 --> 00:01:18.000
We have twelve hospital pilots live.

00:01:18.000 --> 00:01:20.000
We have twelve hospital pilots live.
"""
out = I._parse_subtitles(VTT)
check("WEBVTT header dropped", "WEBVTT" not in out)
check("timestamps flattened to [mm:ss]", "[00:05]" in out and "[01:15]" in out)
check("cue markup stripped", "<v Founder>" not in out and "two million in ARR" in out)
check("rolling duplicate collapsed", out.count("twelve hospital pilots") == 1)

SRT = """1
00:00:05,000 --> 00:00:08,000
Raised a 3M seed from Pear.

2
01:02:03,000 --> 01:02:06,000
Hour-mark line.
"""
out2 = I._parse_subtitles(SRT)
check("SRT indices dropped", not any(line.strip() == "1" for line in out2.splitlines()))
check("SRT comma-millis parsed", "[00:05] Raised a 3M seed" in out2)
check("hours fold into minutes (1:02:03 -> [62:03])", "[62:03]" in out2)

print("=" * 72); print("transcript tagging + split"); print("=" * 72)

with tempfile.TemporaryDirectory() as d:
    Path(d, "deck_notes.txt").write_text("Ambient AI scribe deck. TAM $12B.")
    Path(d, "call_transcript.txt").write_text("[00:10] We closed five design partners.")
    Path(d, "meeting.vtt").write_text(VTT)
    blob = I.extract_materials(d, vision=False)
    check("plain doc NOT transcript-tagged",
          "### Source file: deck_notes.txt\n" in blob and
          f"deck_notes.txt {I.TRANSCRIPT_TAG}" not in blob)
    check("name-hinted .txt tagged", f"call_transcript.txt {I.TRANSCRIPT_TAG}" in blob)
    check(".vtt tagged", f"meeting.vtt {I.TRANSCRIPT_TAG}" in blob)
    calls, docs = I.split_transcripts(blob)
    check("split: transcripts side has both calls",
          "five design partners" in calls and "two million in ARR" in calls)
    check("split: docs side keeps the deck", "TAM $12B" in docs and "design partners" not in docs)

check("split of empty blob", I.split_transcripts("") == ("", ""))

print("=" * 72); print("_validate_call_claims"); print("=" * 72)

raw = {"claims": [
    {"claim": "ARR is $2M", "quote": "we're at two million in ARR", "timestamp": "[00:05]", "category": "financial"},
    {"claim": "", "quote": "x"},                                # dropped: empty claim
    {"claim": "Team built auth at Okta", "category": "PEDIGREE"},  # bad category -> other
    "not-a-dict",
] + [{"claim": f"filler {i}"} for i in range(15)]}
claims = N._validate_call_claims(raw)
check("keeps valid rows, drops empties/non-dicts", len(claims) == N._MAX_CLAIMS)
check("first claim intact", claims[0]["claim"] == "ARR is $2M" and claims[0]["timestamp"] == "[00:05]")
check("bad category coerced to 'other'", claims[1]["category"] == "other")
check("non-dict raw -> []", N._validate_call_claims(None) == [] and N._validate_call_claims({"claims": "x"}) == [])

print("=" * 72); print("_validate_claim_audit"); print("=" * 72)

base = [
    {"claim": "ARR is $2M", "quote": "q1", "timestamp": "[00:05]", "category": "financial"},
    {"claim": "12 hospital pilots live", "quote": "q2", "timestamp": "[01:15]", "category": "traction"},
    {"claim": "Team built auth at Okta", "quote": "q3", "timestamp": "", "category": "team"},
]
audit_raw = {"claims": [
    {"claim": "ARR is $2M", "status": "vendor-only", "evidence": "only the founder states it", "deck_conflict": ""},
    {"claim": "12 hospital pilots live", "status": "contradicted",
     "evidence": "press release (2026-05) says five pilots", "deck_conflict": "deck slide 9 says 5 pilots"},
    {"claim": "Team built auth at Okta", "status": "NONSENSE", "evidence": ""},
]}
audit = N._validate_claim_audit(audit_raw, base)
check("audit joins all 3 claims", audit and len(audit["claims"]) == 3)
check("original quote/timestamp preserved through join",
      audit and audit["claims"][0]["quote"] == "q1" and audit["claims"][1]["timestamp"] == "[01:15]")
check("statuses kept", audit and audit["claims"][0]["status"] == "vendor-only"
      and audit["claims"][1]["status"] == "contradicted")
check("bad status coerced to unsupported", audit and audit["claims"][2]["status"] == "unsupported")
check("deck conflict carried", audit and audit["claims"][1]["deck_conflict"].startswith("deck slide 9"))
check("counts computed in code", audit and audit["counts"]["contradicted"] == 1
      and audit["counts"]["vendor-only"] == 1 and audit["counts"]["unsupported"] == 1
      and audit["counts"]["verified"] == 0 and audit["counts"]["deck_conflicts"] == 1)

# Order fallback: the audit LLM rephrased claim text -> join by position, not text.
rephrased = {"claims": [
    {"claim": "The company's ARR is two million dollars", "status": "verified", "evidence": "e"},
    {"claim": "A dozen pilots", "status": "unsupported", "evidence": ""},
]}
a2 = N._validate_claim_audit(rephrased, base)
check("order fallback maps rephrased rows onto real claims",
      a2 and a2["claims"][0]["claim"] == "ARR is $2M" and a2["claims"][0]["status"] == "verified")

# A hallucinated 4th row (beyond the real claims) must be dropped.
extra = {"claims": audit_raw["claims"] + [{"claim": "invented claim", "status": "verified", "evidence": "x"}]}
a3 = N._validate_claim_audit(extra, base)
check("hallucinated extra row dropped", a3 and len(a3["claims"]) == 3)

check("empty inputs -> None", N._validate_claim_audit({}, base) is None
      and N._validate_claim_audit(audit_raw, []) is None)

print("=" * 72)
passed = sum(1 for _, ok in _results if ok); total = len(_results)
print(f"RESULT: {passed}/{total} passed")
if passed != total:
    print("FAILURES:", [n for n, ok in _results if not ok]); sys.exit(1)
print("ALL CALL-CLAIM TESTS PASS (zero API tokens used).")
