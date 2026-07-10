"""Pilot-grade API-key auth for a hosted deployment.

Design (backward-compatible by default):
- `API_KEYS` env unset/empty  -> auth DISABLED: every request is the anonymous
  single-operator (owner=None), exactly the pre-auth behavior. Local dev unchanged.
- `API_KEYS="alice:k1,bob:k2"` -> every /api request must present a known key in the
  `X-API-Key` header; the mapped owner name tags saved reports, and History list/get
  are filtered per owner (legacy owner-less reports stay visible to all authed users).
- A bare key with no name ("k1") maps to owner "default".

Pure python (no FastAPI imports) so the token-free test suite can exercise it.
This is pilot auth — not a substitute for SSO/RBAC when confidential data is in scope.
"""

from __future__ import annotations

import hmac


def parse_api_keys(raw: str | None) -> dict[str, str]:
    """'alice:k1,bob:k2' -> {'k1': 'alice', 'k2': 'bob'}; bare keys map to 'default'.
    Empty/None -> {} (auth disabled). Malformed entries are skipped, never crash."""
    out: dict[str, str] = {}
    for entry in (raw or "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        if ":" in entry:
            owner, key = entry.split(":", 1)
            owner, key = owner.strip(), key.strip()
        else:
            owner, key = "default", entry
        if key:
            out[key] = owner or "default"
    return out


def resolve_owner(raw_keys: str | None, presented: str | None) -> str | None:
    """The owner for a request, or raise-worthy None-sentinel semantics:
    - auth disabled (no keys configured) -> None  (anonymous single-operator mode)
    - auth enabled + valid key           -> owner name (str)
    - auth enabled + missing/unknown key -> raises PermissionError
    Constant-time key comparison (hmac.compare_digest) against each configured key."""
    keys = parse_api_keys(raw_keys)
    if not keys:
        return None
    # Compare BYTES: compare_digest on str raises TypeError for non-ASCII input
    # (headers are attacker-controlled) — that must be a 401, never a 500.
    candidate = (presented or "").strip().encode("utf-8")
    for key, owner in keys.items():
        if hmac.compare_digest(candidate, key.encode("utf-8")):
            return owner
    raise PermissionError("Invalid or missing API key")
