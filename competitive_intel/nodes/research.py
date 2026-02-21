"""
Research node — one competitor. Uses Perplexity Sonar as the primary research tool
(real-time web synthesis), with Tavily web search as fallback when Perplexity is
not configured. No direct URL scraping and no news search — Perplexity handles
web retrieval internally and produces a richer synthesis.
Produces a ResearchDossier via structured output. Called in parallel via Send.
"""

import json
import logging
import re
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, Field
from anthropic import InternalServerError, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from competitive_intel.callbacks import UsageTracker
from competitive_intel.config import (
    ANTHROPIC_API_KEY,
    MODEL_FAST,
    PERPLEXITY_API_KEY,
    TAVILY_API_KEY,
    RESEARCH_DIR,
    today_str,
)
from competitive_intel.state import PipelineState, ResearchDossier
from competitive_intel.tools import perplexity_search_tool, web_search_tool

log = logging.getLogger(__name__)

# ── Module-level LLM singletons (constructed once, reused across parallel calls) ──
_LLM_BASE = ChatAnthropic(
    model=MODEL_FAST,
    api_key=ANTHROPIC_API_KEY,
    max_tokens=4096,
)

# ── Tool registry ─────────────────────────────────────────────────────────────
# Priority: Perplexity Sonar (primary — AI-synthesised live web, no scraping needed)
#           Tavily web search (fallback — only when PERPLEXITY_API_KEY is not set)
# News search and URL scraping are intentionally excluded.
TOOL_MAP: dict[str, Any] = {}

if PERPLEXITY_API_KEY:
    TOOL_MAP["perplexity_search_tool"] = perplexity_search_tool
    log.debug("Perplexity search tool enabled (primary)")
elif TAVILY_API_KEY:
    TOOL_MAP["web_search_tool"] = web_search_tool
    log.debug("Tavily web search enabled (fallback — PERPLEXITY_API_KEY not set)")
else:
    log.warning("No search tool available: set PERPLEXITY_API_KEY or TAVILY_API_KEY")


class ResearchDossierSchema(BaseModel):
    company: str
    date: str
    summary: str
    recent_news: list[str] = Field(default_factory=list)
    product_updates: list[str] = Field(default_factory=list)
    strategic_moves: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    sentiment: str = "neutral"
    confidence: str = "medium"
    sources: list[str] = Field(default_factory=list)


_primary_tool_hint = (
    "Use perplexity_search_tool as your primary (and only) research tool. It synthesizes "
    "live web results and will give you the most comprehensive, up-to-date picture. "
    "Run multiple targeted queries to cover news, products, strategy, and financials."
    if PERPLEXITY_API_KEY
    else
    "Use web_search_tool to find recent information. Run multiple targeted queries to "
    "cover news, products, strategy, and financials."
)

SYSTEM_PROMPT = f"""\
You are a competitive intelligence research analyst. Your job is to produce
a structured research dossier on a given company using live data.

{_primary_tool_hint}

Focus on finding:
- Recent news, press releases, and announcements
- New products, contracts, or partnerships
- Strategic moves (acquisitions, expansions, leadership changes)
- Financial signals (revenue, guidance, layoffs, investments)

Then synthesize your findings into a dossier. Be specific and factual.
If you are uncertain, mark confidence as "low" or "medium".
Cite sources by including URLs from your search results in the "sources" field.
"""


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=5, max=60),
    retry=retry_if_exception_type((InternalServerError, RateLimitError, Exception)),
    reraise=True,
)
def _invoke_llm(llm: Any, messages: list) -> Any:
    return llm.invoke(messages, config={"callbacks": [UsageTracker()]})


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=5, max=60),
    retry=retry_if_exception_type((InternalServerError, RateLimitError, Exception)),
    reraise=True,
)
def _invoke_structured(llm: Any, messages: list) -> Any:
    return llm.invoke(messages, config={"callbacks": [UsageTracker()]})


def research_node(state: PipelineState) -> dict[str, Any]:
    """
    Run research for one competitor. State should contain "competitor" (from Send).
    Returns {"research": [ResearchDossier]} for reducer fan-in.
    """
    competitor = state.get("competitor") or ""
    if not competitor:
        return {"research": []}

    # Defense-in-depth: sanitize even though config already sanitizes at startup
    competitor = re.sub(r"[^\w\s\-&.,()]", "", competitor).strip()[:100]
    if not competitor:
        return {"research": []}

    date = today_str()
    log.info("Researching: %s", competitor)

    if not TOOL_MAP:
        log.error("No search tools configured for %s — skipping research", competitor)
        return {"research": [{
            "company": competitor, "date": date,
            "summary": "No search tool configured (set PERPLEXITY_API_KEY or TAVILY_API_KEY).",
            "recent_news": [], "product_updates": [], "strategic_moves": [],
            "strengths": [], "weaknesses": [], "sentiment": "neutral",
            "confidence": "low", "sources": [],
        }]}

    tools = list(TOOL_MAP.values())
    llm_with_tools = _LLM_BASE.bind_tools(tools)
    structured_llm = _LLM_BASE.with_structured_output(ResearchDossierSchema)

    messages: list = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"Produce a competitive intelligence dossier on: {competitor}\n"
                f"Today's date: {date}\n\n"
                "Run multiple search queries to cover recent news, product updates, "
                "strategic moves, and financial signals. Then synthesize into the dossier."
            )
        ),
    ]
    sources_used: list[str] = []

    def _run_tool(name: str, args: dict) -> str:
        tool_fn = TOOL_MAP.get(name)
        if tool_fn is None:
            return f"Unknown tool: {name}"
        out = tool_fn.invoke(args)
        # Track source URLs from search results
        if isinstance(out, list):
            for r in out:
                if isinstance(r, dict) and r.get("url"):
                    sources_used.append(r["url"])
        result = out if isinstance(out, str) else str(out)
        return result[:8000]

    # Tool-use loop (max 6 steps)
    for _step in range(6):
        response = _invoke_llm(llm_with_tools, messages)
        if not getattr(response, "tool_calls", None):
            break
        messages.append(response)
        for tc in response.tool_calls:
            name = tc.get("name", "")
            args = tc.get("args", {}) or {}
            tc_id = tc.get("id", "")
            log.info("  [%s] tool call: %s", competitor, name)
            content = _run_tool(name, args)
            messages.append(ToolMessage(content=content, tool_call_id=tc_id))

    # Structured output: dossier from conversation context
    messages.append(
        HumanMessage(
            content=(
                f"Based on all the search results above, produce the final "
                f"research dossier for {competitor}. Today's date: {date}. "
                f"Include the source URLs from your search results in the 'sources' field."
            )
        )
    )
    try:
        dossier_obj = _invoke_structured(structured_llm, messages)
        dossier: ResearchDossier = {
            "company": dossier_obj.company,
            "date": dossier_obj.date,
            "summary": dossier_obj.summary,
            "recent_news": dossier_obj.recent_news,
            "product_updates": dossier_obj.product_updates,
            "strategic_moves": dossier_obj.strategic_moves,
            "strengths": dossier_obj.strengths,
            "weaknesses": dossier_obj.weaknesses,
            "sentiment": dossier_obj.sentiment,
            "confidence": dossier_obj.confidence,
            "sources": list(set(sources_used)) or dossier_obj.sources,
        }
        log.info("Research complete: %s (confidence=%s)", competitor, dossier["confidence"])
    except Exception as exc:
        log.warning("Structured output failed for %s: %s", competitor, exc)
        dossier = {
            "company": competitor,
            "date": date,
            "summary": "Research failed — could not produce structured dossier.",
            "recent_news": [],
            "product_updates": [],
            "strategic_moves": [],
            "strengths": [],
            "weaknesses": [],
            "sentiment": "neutral",
            "confidence": "low",
            "sources": list(set(sources_used)),
        }

    # Persist dossier to disk for debugging / audit
    try:
        slug = re.sub(r"[^\w]", "_", competitor.lower())
        path = RESEARCH_DIR / f"{date}_{slug}.json"
        path.write_text(json.dumps(dossier, indent=2), encoding="utf-8")
    except Exception as exc:
        log.warning("Failed to write research file for %s: %s", competitor, exc)

    return {"research": [dossier]}
