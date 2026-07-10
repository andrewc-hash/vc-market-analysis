"""Token-free tests for the focal-startup document ingest (text path only).

Exercises the REAL extract_materials over a temp dir of text/markdown files with
vision DISABLED, so no PDF libs and no API calls are needed. The vision fallback and
PDF/docx parsers are integration-tested separately (they need optional deps + a model).

Run:  python3 backend/tests/test_ingest.py
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services import ingest as I

_results = []
def check(name, cond, detail=""):
    _results.append((name, bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))

print("=" * 72); print("extract_materials (text path, vision off)"); print("=" * 72)

with tempfile.TemporaryDirectory() as d:
    Path(d, "founding.txt").write_text("Founded 2024 by ex-Stripe engineers. Pre-seed.")
    Path(d, "idea.md").write_text("# Thesis\n\nAmbient AI scribe for veterinary clinics.")
    Path(d, "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n_fake_")  # vision off -> ignored
    out = I.extract_materials(d, vision=False)
    check("returns a non-empty blob", bool(out.strip()))
    check("includes the .txt content", "ex-Stripe" in out)
    check("includes the .md content", "veterinary clinics" in out)
    check("labels each source file", "### Source file: founding.txt" in out and "### Source file: idea.md" in out)
    check("image skipped when vision is off", "logo.png" not in out)

with tempfile.TemporaryDirectory() as d:
    check("empty dir -> empty string", I.extract_materials(d, vision=False) == "")

check("missing dir -> empty string", I.extract_materials("/no/such/dir/xyz", vision=False) == "")

# A single unreadable/odd file must not sink the rest.
with tempfile.TemporaryDirectory() as d:
    Path(d, "good.txt").write_text("usable text here")
    Path(d, "weird.xyz").write_text("unsupported type")  # skipped, not fatal
    out = I.extract_materials(d, vision=False)
    check("unsupported type skipped, good file kept", "usable text here" in out and "weird.xyz" not in out)

print("=" * 72)
passed = sum(1 for _, ok in _results if ok); total = len(_results)
print(f"RESULT: {passed}/{total} passed")
if passed != total:
    print("FAILURES:", [n for n, ok in _results if not ok]); sys.exit(1)
print("ALL INGEST TESTS PASS (zero API tokens used).")
