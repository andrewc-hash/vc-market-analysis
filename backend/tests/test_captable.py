"""Token-free tests for the cap-table CSV parser (services/captable.py).

Pure code — no LLM deps, no API calls. Run:  python3 backend/tests/test_captable.py
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services import captable as C

_results = []
def check(name, cond, detail=""):
    _results.append((name, bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))

print("=" * 72); print("_money_musd normalization"); print("=" * 72)
check("'$5M' -> 5", C._money_musd("$5M") == 5)
check("'5,000,000' raw dollars -> 5", C._money_musd("5,000,000") == 5)
check("'1.2B' -> 1200", C._money_musd("1.2B") == 1200)
check("'750K' -> 0.75", C._money_musd("750K") == 0.75)
check("bare '5' stays $M", C._money_musd("5") == 5)
check("bare 20 (numeric) stays $M", C._money_musd(20) == 20)
check("'~$12.5m' -> 12.5", C._money_musd("~$12.5m") == 12.5)
check("empty -> None", C._money_musd("") is None)
check("'Not Disclosed' -> None", C._money_musd("Not Disclosed") is None)
check("zero -> None", C._money_musd("0") is None)
check("bool -> None", C._money_musd(True) is None)

print("=" * 72); print("parse_cap_table_csv"); print("=" * 72)

CSV = """Round,Date,Amount Raised,Pre-Money,Post-Money Valuation,Lead Investors
Pre-Seed,2023-06,$750K,$4M,,Angels
Seed,2024-03,"$3,000,000",$12M,$15M,Pear VC
Series A,2025-01,$12M,,$60M,Index Ventures
"""
ct = C.parse_cap_table_csv(CSV, source_file="rounds.csv")
check("parses a well-formed CSV", ct is not None)
check("3 rounds", ct and len(ct["rounds"]) == 3)
check("pre+raised derives missing post (4+0.75)", ct and ct["rounds"][0]["post_money_musd"] == 4.75)
check("raw-dollar cell normalized ($3,000,000 -> 3)", ct and ct["rounds"][1]["raised_musd"] == 3)
check("total raised = 15.75", ct and ct["total_raised_musd"] == 15.75)
check("latest post = 60 (Series A)", ct and ct["latest_post_money_musd"] == 60)
check("latest round named", ct and ct["latest_round"] == "Series A")
check("investors captured", ct and ct["rounds"][2]["investors"] == "Index Ventures")
check("source file recorded", ct and ct["source_file"] == "rounds.csv")

# Header flexibility: different aliases still map.
ALT = "Stage,Close Date,Investment Size,Valuation (Post)\nSeed,2024,$2M,$10M\n"
alt = C.parse_cap_table_csv(ALT)
check("alias headers map (stage/size/valuation)", alt is not None and alt["latest_post_money_musd"] == 10)

check("random CSV rejected", C.parse_cap_table_csv("a,b,c\n1,2,3\n") is None)
check("header-only rejected", C.parse_cap_table_csv("Round,Amount\n") is None)
check("empty rejected", C.parse_cap_table_csv("") is None)

print("=" * 72); print("is_cap_table_csv + find_cap_table"); print("=" * 72)
check("sniff accepts a cap table", C.is_cap_table_csv(CSV))
check("sniff rejects a random CSV", not C.is_cap_table_csv("name,email\nbob,b@x.com\n"))
check("sniff survives garbage", not C.is_cap_table_csv("\x00\x01binary"))

with tempfile.TemporaryDirectory() as d:
    Path(d, "notes.csv").write_text("name,email\nbob,b@x.com\n")   # not a cap table
    Path(d, "rounds.csv").write_text(CSV)
    Path(d, "_cache.csv").write_text(CSV)                          # underscore-reserved: skipped
    found = C.find_cap_table(d)
    check("find_cap_table picks the cap-table CSV", found is not None and found["source_file"] == "rounds.csv")

with tempfile.TemporaryDirectory() as d:
    Path(d, "deck.txt").write_text("no csv here")
    check("no CSV -> None", C.find_cap_table(d) is None)
check("missing dir -> None", C.find_cap_table("/no/such/dir") is None)

print("=" * 72)
passed = sum(1 for _, ok in _results if ok); total = len(_results)
print(f"RESULT: {passed}/{total} passed")
if passed != total:
    print("FAILURES:", [n for n, ok in _results if not ok]); sys.exit(1)
print("ALL CAP-TABLE TESTS PASS (zero API tokens used).")
