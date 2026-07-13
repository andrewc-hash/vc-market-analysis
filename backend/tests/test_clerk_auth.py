"""Token-free tests for Clerk JWT verification (services/clerk_auth.py).

Stubs `jwt` (PyJWT) in sys.modules so no crypto/network happens — exercises the real
orchestration: the enabled flag, JWKS-URL derivation, owner (=sub) extraction, and the
PermissionError paths (missing token, bad signature/issuer/expiry, subject-less token,
dependency unavailable). Mirrors the LLM-stubbing philosophy of the other suites.

Run:  python3 backend/tests/test_clerk_auth.py
"""
import sys, types

_results = []
def check(name, cond, detail=""):
    _results.append((name, bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the module under test WITHOUT any jwt installed first, to prove it imports cleanly
# (the lazy-import guarantee — the API must load even when PyJWT is absent / the flag is off).
sys.modules.pop("jwt", None)
from app.services import clerk_auth as C

S_off = types.SimpleNamespace(clerk_issuer="", clerk_jwks_url="")
S_on = types.SimpleNamespace(clerk_issuer="https://clerk.example.com", clerk_jwks_url="")
S_on_explicit = types.SimpleNamespace(clerk_issuer="https://clerk.example.com", clerk_jwks_url="https://x/jwks")

print("=" * 72); print("clerk_enabled flag + jwks url"); print("=" * 72)
check("module imports with NO jwt installed (lazy import)", "jwt" not in sys.modules)
check("disabled when issuer empty", C.clerk_enabled(S_off) is False)
check("enabled when issuer set", C.clerk_enabled(S_on) is True)
check("jwks url defaults to <issuer>/.well-known/jwks.json",
      C._jwks_url(S_on) == "https://clerk.example.com/.well-known/jwks.json")
check("explicit jwks url wins", C._jwks_url(S_on_explicit) == "https://x/jwks")

print("=" * 72); print("verify_clerk_token (jwt stubbed)"); print("=" * 72)

# ---- stub the PyJWT surface the module uses: jwt.decode + jwt.PyJWKClient ----
class _FakeSigningKey:
    key = "PUBLIC_KEY"
class _FakePyJWKClient:
    def __init__(self, url): self.url = url
    def get_signing_key_from_jwt(self, token): return _FakeSigningKey()

_state = {"decode": None}
def _decode(token, key, **kwargs):
    return _state["decode"](token, key, kwargs)

_jwt = types.ModuleType("jwt")
_jwt.decode = _decode
_jwt.PyJWKClient = _FakePyJWKClient
sys.modules["jwt"] = _jwt

# missing token -> PermissionError, and jwt is never even imported/used
try:
    C.verify_clerk_token("", S_on); check("empty token -> PermissionError", False)
except PermissionError:
    check("empty token -> PermissionError", True)

# valid token -> returns the sub claim as the owner
_state["decode"] = lambda t, k, kw: {"sub": "user_2abc", "iss": S_on.clerk_issuer, "exp": 9999999999}
check("valid token -> owner = sub", C.verify_clerk_token("tok", S_on) == "user_2abc")

# decode enforces issuer/expiry via PyJWT; simulate its rejection -> PermissionError
def _raise(*a):
    raise ValueError("invalid issuer/expired signature")
_state["decode"] = lambda t, k, kw: _raise()
try:
    C.verify_clerk_token("tok", S_on); check("bad issuer/expiry -> PermissionError", False)
except PermissionError:
    check("bad issuer/expiry -> PermissionError", True)

# token with no subject -> PermissionError (never returns an empty owner)
_state["decode"] = lambda t, k, kw: {"iss": S_on.clerk_issuer, "exp": 9999999999}
try:
    C.verify_clerk_token("tok", S_on); check("subject-less token -> PermissionError", False)
except PermissionError:
    check("subject-less token -> PermissionError", True)

# non-str subject -> PermissionError
_state["decode"] = lambda t, k, kw: {"sub": 123, "exp": 1}
try:
    C.verify_clerk_token("tok", S_on); check("non-str subject -> PermissionError", False)
except PermissionError:
    check("non-str subject -> PermissionError", True)

# the require-options are passed to jwt.decode (exp/iss/sub required, RS256 only)
_captured = {}
def _decode_capture(t, k, kw):
    _captured.update(kw); return {"sub": "u1", "exp": 1, "iss": S_on.clerk_issuer}
_state["decode"] = _decode_capture
C.verify_clerk_token("tok", S_on)
check("RS256 enforced", _captured.get("algorithms") == ["RS256"])
check("issuer checked", _captured.get("issuer") == S_on.clerk_issuer)
check("exp/iss/sub required", set(_captured.get("options", {}).get("require", [])) == {"exp", "iss", "sub"})

# dependency unavailable -> PermissionError (never a 500): remove the stub
sys.modules.pop("jwt", None)
_orig = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__
import builtins
def _blocked_import(name, *a, **k):
    if name == "jwt":
        raise ImportError("no jwt")
    return _orig(name, *a, **k)
builtins.__import__ = _blocked_import
try:
    C.verify_clerk_token("tok", S_on); check("PyJWT missing -> PermissionError (not 500)", False)
except PermissionError:
    check("PyJWT missing -> PermissionError (not 500)", True)
finally:
    builtins.__import__ = _orig

print("=" * 72)
passed = sum(1 for _, ok in _results if ok); total = len(_results)
print(f"RESULT: {passed}/{total} passed")
if passed != total:
    print("FAILURES:", [n for n, ok in _results if not ok]); sys.exit(1)
print("ALL CLERK-AUTH TESTS PASS (zero API tokens used).")
