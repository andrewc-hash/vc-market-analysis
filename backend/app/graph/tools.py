"""Real-time web-search tools for the Researcher agent.

These Tavily-backed tools are bound ONLY to the Researcher node
(`app.graph.nodes.researcher_node`). The Analyst, Judge, and Compiler agents
run WITHOUT tools — they reason purely over the research brief the Researcher
produces. (Earlier revisions claimed both analysts shared this toolkit; that is
no longer true.)
"""

from __future__ import annotations

import logging
from datetime import datetime

from langchain_core.tools import tool
from tavily import TavilyClient

from app.config import get_settings

logger = logging.getLogger(__name__)


def _years() -> str:
    """Current + next year, so search queries stay current instead of hard-coded."""
    y = datetime.now().year
    return f"{y} {y + 1}"


def _get_tavily() -> TavilyClient:
    return TavilyClient(api_key=get_settings().tavily_api_key)


# Per-source cap on raw page text. 6 results x ~2.5K chars x 6-8 startups adds
# ~100-120K chars to the researcher context — fine for gemini's window, and it's
# where paragraph-level facts (e.g. "post-money valuation of ~$700M") live that
# never make it into a snippet.
_RAW_CONTENT_CHARS = 2500


def _tavily_search(
    query: str,
    header: str,
    *,
    search_depth: str = "advanced",
    max_results: int = 8,
    topic: str = "general",
    days: int | None = None,
    raw_content: bool = False,
) -> str:
    """Run a Tavily search and format the answer + sources as markdown.

    Network/quota errors and malformed result items degrade gracefully to a
    short note instead of raising, so one bad search never aborts the whole
    research phase. Source URLs are always emitted under a `## Sources` block so
    they can propagate into the analysts' reports and the final Works Cited.
    Each source carries its PUBLICATION DATE when Tavily returns one (always for
    topic="news") — the researcher uses these to arbitrate conflicting figures
    by recency and to tag facts with an as-of date. With raw_content=True each
    source also carries a page-body excerpt (capped) — snippets alone miss
    paragraph-level financials.
    """
    params: dict = dict(
        query=query,
        search_depth=search_depth,
        max_results=max_results,
        include_answer=True,
    )
    if topic != "general":
        params["topic"] = topic
    if days is not None:
        params["days"] = days
    if raw_content:
        params["include_raw_content"] = True
    logger.info("🔎 Tavily [%s|%s%s]: %s", topic, search_depth,
                "+raw" if raw_content else "", query[:140])
    try:
        results = _get_tavily().search(**params)
    except Exception as exc:  # noqa: BLE001 - report to the agent, never crash the run
        # Matched by name so a tavily-python import path change can't break the guard.
        if type(exc).__name__ == "UsageLimitExceededError":
            return (
                f"{header}\n[TAVILY QUOTA EXHAUSTED — the monthly search limit is spent. "
                f"Do not keep retrying other searches; write the brief from what you have and "
                f"state PROMINENTLY that live research was unavailable for the missing parts.]"
            )
        return f"{header}\n[Search failed: {exc}]"

    def _fmt(r: dict) -> str:
        date = str(r.get("published_date") or "").strip()
        tag = f" (published: {date})" if date else ""
        out = f"[{r.get('title', 'Untitled')}]({r.get('url', '')}){tag}\n{r.get('content', '')}"
        raw = str(r.get("raw_content") or "").strip()
        if raw_content and raw:
            clip = raw[:_RAW_CONTENT_CHARS]
            if len(raw) > _RAW_CONTENT_CHARS:
                clip += " …[page excerpt truncated]"
            out += f"\n[Page excerpt]\n{clip}"
        return out

    answer = results.get("answer", "")
    snippets = "\n\n".join(_fmt(r) for r in results.get("results", []))
    return f"{header}\n{answer}\n\n## Sources\n{snippets}"


@tool
def search_market_data(query: str) -> str:
    """Search the web for real-time market data, funding rounds, ARR figures,
    competitive landscapes, and sector-specific intelligence."""
    return _tavily_search(query, "## Tavily Answer", max_results=8)


@tool
def search_startup_financials(startup_name: str) -> str:
    """Look up a specific startup's financial metrics: funding stage, total
    capital raised, valuation, ARR, YoY growth, LTV/CAC, NRR, burn multiple.
    Sources include page-body excerpts — read them: precise terms (post-money
    valuation, round composition) live in article bodies, not snippets."""
    return _tavily_search(
        f"{startup_name} startup funding round lead investors valuation ARR revenue growth "
        f"net revenue retention burn rate gross margin profitability go-to-market moat technology {_years()}",
        f"## Financial Data for {startup_name}",
        max_results=6,
        raw_content=True,
    )


@tool
def search_regulatory_landscape(regulation: str) -> str:
    """Search for regulatory frameworks, enforcement deadlines, and compliance
    requirements (e.g., EU AI Act, GDPR, SOC2, FedRAMP)."""
    return _tavily_search(
        f"{regulation} compliance requirements obligations articles enforcement deadline {datetime.now().year}",
        f"## Regulatory Intel: {regulation}",
        max_results=6,
    )


@tool
def search_founder_background(founder_name: str, company: str) -> str:
    """Research a founder's background: prior exits, technical achievements,
    domain origins (e.g., Unit 8200, kernel engineering, FAANG security)."""
    return _tavily_search(
        f"{founder_name} {company} founder background technical pedigree prior startups exits experience",
        f"## Founder Profile: {founder_name}",
        search_depth="basic",
        max_results=5,
    )


@tool
def search_competitor_landscape(sector: str) -> str:
    """Identify and compare competitors in a given sector: market positioning,
    funding, technical differentiation, and incumbent threats."""
    return _tavily_search(
        f"{sector} startups competitors market map landscape {_years()}",
        f"## Competitive Landscape: {sector}",
        max_results=8,
    )


def _make_grounded_llm(settings):
    """Factory for the nested Gemini call behind search_google_live (separate fn so
    token-free tests can stub it). Imported lazily — tools.py must stay importable
    when langchain_google_genai is absent/stubbed."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=settings.researcher_model,
        google_api_key=settings.google_api_key,
        temperature=0.1,
        max_output_tokens=2048,
    )


def _resolve_redirect(uri: str, timeout: float = 3.0) -> str:
    """Grounding sources arrive as Google redirect URLs — resolve to the real URL
    so Works Cited carries clickable, honest citations. Falls back to the redirect."""
    if "grounding-api-redirect" not in uri:
        return uri
    try:
        import urllib.request

        req = urllib.request.Request(uri, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.geturl() or uri
    except Exception:  # noqa: BLE001 - a redirect link still works when clicked
        return uri


def _grounded_search(query: str, header: str) -> str:
    """One standalone Gemini call with server-side Google Search grounding.

    Deliberately a NESTED call (not a tool binding on the researcher agent itself):
    the Gemini API does not reliably mix the built-in google_search tool with
    client-side function declarations in a single request. The ReAct researcher
    sees this as just another markdown-returning tool.
    """
    settings = get_settings()
    if not settings.grounded_search:
        return f"{header}\n[Grounded search disabled (GROUNDED_SEARCH=false) — use the Tavily tools.]"
    if not str(settings.researcher_model).startswith("gemini"):
        return f"{header}\n[Grounded search unavailable: researcher model is not Gemini — use the Tavily tools.]"
    logger.info("🌐 Google-grounded: %s", query[:140])
    try:
        llm = _make_grounded_llm(settings)
        resp = llm.invoke(query, tools=[{"google_search": {}}])
        text = resp.content if isinstance(resp.content, str) else str(resp.content)
        gm = (getattr(resp, "response_metadata", None) or {}).get("grounding_metadata") \
            or (getattr(resp, "additional_kwargs", None) or {}).get("grounding_metadata") or {}
        lines = []
        for c in gm.get("grounding_chunks", []) or []:
            web = c.get("web") or {}
            uri = str(web.get("uri") or "").strip()
            if uri:
                lines.append(f"[{web.get('title', 'source')}]({_resolve_redirect(uri)})")
        sources = "\n".join(lines) if lines else "[no grounded sources returned]"
        return f"{header}\n{text}\n\n## Sources\n{sources}"
    except Exception as exc:  # noqa: BLE001 - degrade like _tavily_search, never crash the run
        return f"{header}\n[Grounded search failed: {exc}]"


@tool
def search_google_live(query: str) -> str:
    """Google-grounded LIVE search (server-side, full-page depth — the freshest
    source available). Use for PRECISION freshness questions on a NAMED company:
    exact latest round + post-money valuation, current ARR, acquisition/M&A status.
    One focused question per call. When a Tavily result and this tool disagree on
    a time-sensitive figure, THIS tool's answer wins on recency."""
    return _grounded_search(query, "## Google Live Search")


@tool
def search_latest_news(startup_name: str) -> str:
    """Fetch the LATEST news (past 12 months only) for one startup: its newest
    funding round / valuation, product launches, pivots, partnerships, layoffs,
    or acquisition activity. Call this ONCE for EVERY deep-dived startup — it is
    the freshness guard against stale figures from older sources."""
    # basic depth: news snippets don't benefit from advanced extraction, and advanced
    # costs 2 Tavily credits vs 1 — this pass runs 6-8 times per run.
    return _tavily_search(
        f"{startup_name} startup funding round valuation acquisition acquired merger "
        f"product launch announcement",
        f"## Latest News (past 12 months): {startup_name}",
        search_depth="basic",
        topic="news",
        days=365,
        max_results=6,
    )


# Canonical toolkit — bound to the Researcher agent only (see app.graph.nodes).
RESEARCH_TOOLS = [
    search_market_data,
    search_startup_financials,
    search_regulatory_landscape,
    search_founder_background,
    search_competitor_landscape,
    search_latest_news,
    search_google_live,
]
