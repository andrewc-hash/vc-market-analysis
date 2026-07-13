"""Clerk JWT verification for hosted multi-user sign-in (Google / email magic-link).

Enabled ONLY when `settings.clerk_issuer` is set. When enabled, /api endpoints accept a
Clerk session token as `Authorization: Bearer <jwt>`; the verified `sub` claim (the stable
Clerk user id) becomes the request owner — the SAME owner string that tags saved reports and
filters History, so the existing per-user isolation is reused unchanged. Empty `clerk_issuer`
=> Clerk disabled, zero behavior change (the static X-API-Key path stays in force).

Verification: RS256 signature against Clerk's JWKS (fetched + cached by PyJWT's PyJWKClient),
plus issuer + expiry checks. `jwt` (PyJWT) is imported LAZILY inside the verify function so
this module — and therefore the whole API — imports cleanly even when the dependency isn't
installed or the flag is off, and so the token-free test suite can stub `jwt`.

Contract mirrors services.auth.resolve_owner: return the owner string on success, raise
PermissionError on any invalid/missing token (the route converts that to a 401).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# jwks_url -> PyJWKClient (each client caches the fetched signing keys internally).
_jwk_clients: dict[str, object] = {}


def clerk_enabled(settings) -> bool:
    """True when hosted Clerk auth is configured (a non-empty issuer)."""
    return bool((getattr(settings, "clerk_issuer", "") or "").strip())


def _jwks_url(settings) -> str:
    """Explicit clerk_jwks_url, else Clerk's conventional <issuer>/.well-known/jwks.json."""
    url = (getattr(settings, "clerk_jwks_url", "") or "").strip()
    if url:
        return url
    return (settings.clerk_issuer or "").rstrip("/") + "/.well-known/jwks.json"


def verify_clerk_token(token: str, settings) -> str:
    """Return the owner (Clerk user id — the `sub` claim) for a valid session token.

    Raises PermissionError on a missing/expired/wrong-issuer/malformed token, or if the
    auth backend (PyJWT) is unavailable — the caller maps that to HTTP 401.
    """
    token = (token or "").strip()
    if not token:
        raise PermissionError("missing bearer token")

    try:  # lazy import: only required once Clerk is actually enabled
        import jwt
        from jwt import PyJWKClient
    except Exception as e:  # noqa: BLE001 — dependency not installed
        logger.error("Clerk auth enabled but PyJWT is unavailable: %s", e)
        raise PermissionError("auth backend unavailable")

    url = _jwks_url(settings)
    client = _jwk_clients.get(url)
    if client is None:
        client = PyJWKClient(url)
        _jwk_clients[url] = client

    try:
        signing_key = client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            getattr(signing_key, "key", signing_key),
            algorithms=["RS256"],
            issuer=settings.clerk_issuer,
            options={"require": ["exp", "iss", "sub"]},
        )
    except Exception as e:  # noqa: BLE001 — any verification failure is a 401, not a 500
        logger.info("Clerk token rejected: %s", e)
        raise PermissionError("invalid token")

    sub = claims.get("sub") if isinstance(claims, dict) else None
    if not sub or not isinstance(sub, str):
        raise PermissionError("token missing subject")
    return sub
