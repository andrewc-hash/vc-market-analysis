"""Scope inference for a focal startup.

Given a focal startup (a name and/or uploaded materials), derive the SECTOR and a rich
MARKET-ANALYSIS PROMPT so the user doesn't have to type them. Strategy:

  - uploaded materials present  -> infer from the materials (PRIMARY), sharpened by 1-2
    quick Tavily searches on the name (SECONDARY, clearly labeled so a same-name
    collision can't hijack a materials-grounded scope)
  - name only, no materials     -> ground with 1-2 Tavily searches, then infer

Used by POST /api/derive-scope (confirm-first UI) and, as a fallback, by the pipeline's
ingest node when a request arrives with no market_prompt.
"""

from __future__ import annotations

import logging
import os

from app.config import get_settings

logger = logging.getLogger(__name__)


def infer_scope(focal_startup: str, focal_upload_id: str = "") -> dict:
    """Return {market_prompt, sector, rationale, autoderived: bool, source}.

    source is 'materials+search' | 'materials' | 'search' | 'none'. autoderived is False
    if inference failed (caller then keeps whatever the user typed).
    """
    settings = get_settings()
    focal = (focal_startup or "").strip()
    upload_id = (focal_upload_id or "").strip()
    context = ""
    source = "none"

    # 1) Prefer uploaded materials (cached so we never re-parse a deck the pipeline will reuse).
    if upload_id:
        try:
            from app.services.ingest import extract_materials_cached
            context = extract_materials_cached(os.path.join(settings.uploads_dir, upload_id))
            if context.strip():
                source = "materials"
        except Exception as e:  # noqa: BLE001
            logger.warning("Scope: material extraction failed: %s", e)

    # 2) Ground with a couple of quick web searches on the name. With materials present
    #    the snippets are a SECONDARY freshness/reality check (clearly labeled so a
    #    same-name collision can't hijack a materials-grounded scope); with no materials
    #    they are the only grounding.
    if focal:
        try:
            from app.graph.tools import _tavily_search
            parts = [
                _tavily_search(f"{focal} startup what does it do sector market", "## What it is", max_results=6),
                _tavily_search(f"{focal} competitors market category why now", "## Market", max_results=6),
            ]
            search_ctx = "\n\n".join(p for p in parts if p)
            if search_ctx.strip():
                if source == "materials":
                    context += (
                        "\n\n=== SECONDARY CONTEXT: LIVE WEB SEARCH ON THE NAME ===\n"
                        "The materials above are the PRIMARY source. The snippets below may "
                        "describe a DIFFERENT company with a similar name — use them only to "
                        "sharpen or update the market framing, and ignore anything "
                        "inconsistent with the materials.\n\n" + search_ctx
                    )
                    source = "materials+search"
                else:
                    context = search_ctx
                    source = "search"
        except Exception as e:  # noqa: BLE001
            logger.warning("Scope: grounding search failed: %s", e)

    # 3) Infer the market from whatever context we have.
    try:
        from app.graph.nodes import derive_scope
        derived = derive_scope(focal, context, settings)
    except Exception as e:  # noqa: BLE001
        logger.error("Scope: derive_scope raised: %s", e)
        derived = None

    if not derived or not derived.get("market_prompt"):
        return {"market_prompt": "", "sector": "", "rationale": "", "autoderived": False, "source": source}
    return {
        "market_prompt": derived["market_prompt"],
        "sector": derived.get("sector", ""),
        "rationale": derived.get("rationale", ""),
        "autoderived": True,
        "source": source,
    }
