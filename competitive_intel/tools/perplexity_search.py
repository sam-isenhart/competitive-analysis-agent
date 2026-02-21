"""
Perplexity search tool using the Sonar API (web-grounded chat).

Uses the Sonar API (https://docs.perplexity.ai/docs/sonar/quickstart) for
web-grounded AI responses: one synthesized answer plus search results.
Supports search_recency_filter per https://docs.perplexity.ai/docs/sonar/filters.

Returns the same schema as other search tools for consistency:
  {headline, source, url, date, summary}
"""

import logging

from langchain_core.tools import tool

from competitive_intel.config import PERPLEXITY_API_KEY

log = logging.getLogger(__name__)


def _days_to_recency(days_back: int) -> str:
    """Map days_back to Sonar search_recency_filter: day, week, month, year."""
    if days_back <= 1:
        return "day"
    if days_back <= 7:
        return "week"
    if days_back <= 30:
        return "month"
    return "year"


def _collect_search_results(completion) -> list:
    """Extract search result entries from a Sonar chat completion."""
    results = []
    try:
        choice = completion.choices[0] if completion.choices else None
        if not choice:
            return results
        msg = choice.message
        # Top-level search_results on message (if API returns it)
        raw = getattr(msg, "search_results", None) or []
        if raw:
            results.extend(raw)
            return results
        # Otherwise collect from reasoning_steps (web_search.search_results)
        steps = getattr(msg, "reasoning_steps", None) or []
        for step in steps:
            web = getattr(step, "web_search", None)
            if web:
                sr = getattr(web, "search_results", None) or []
                results.extend(sr)
    except Exception:
        pass
    return results


@tool
def perplexity_search_tool(query: str, days_back: int = 7) -> list[dict]:
    """
    Search for current information using Perplexity's Sonar API (web-grounded AI).
    Returns one synthesis plus source results. Best for competitive research.
    Returns list of {headline, source, url, date, summary}.
    """
    if not PERPLEXITY_API_KEY:
        return [
            {
                "headline": "N/A",
                "source": "",
                "url": "",
                "date": "",
                "summary": "PERPLEXITY_API_KEY not set.",
            }
        ]
    try:
        from perplexity import Perplexity

        client = Perplexity(api_key=PERPLEXITY_API_KEY)
        recency = _days_to_recency(days_back)

        completion = client.chat.completions.create(
            model="sonar-pro",
            messages=[{"role": "user", "content": query}],
            search_recency_filter=recency,
        )

        answer = ""
        if completion.choices:
            msg = completion.choices[0].message
            content = getattr(msg, "content", None)
            answer = (content or "")[:1000] if content else ""

        raw_results = _collect_search_results(completion)

        results = []
        for r in raw_results:
            title = getattr(r, "title", "") or (r.get("title", "") if isinstance(r, dict) else "")
            url = getattr(r, "url", "") or (r.get("url", "") if isinstance(r, dict) else "")
            snippet = getattr(r, "snippet", "") or (r.get("snippet", "") if isinstance(r, dict) else "")
            date = getattr(r, "date", "") or (r.get("date", "") if isinstance(r, dict) else "")
            domain = url.split("/")[2] if url.startswith("http") else ""
            results.append(
                {
                    "headline": title or query,
                    "source": domain,
                    "url": url,
                    "date": date or "",
                    "summary": (snippet or "")[:2000],
                }
            )

        # Prepend synthesis as first item (same shape as before)
        results.insert(
            0,
            {
                "headline": f"Perplexity synthesis: {query}",
                "source": "perplexity.ai",
                "url": "",
                "date": "",
                "summary": answer,
            },
        )

        log.info(
            "Perplexity search: '%s' → %d source(s), recency=%s",
            query,
            len(raw_results),
            recency,
        )
        return results
    except Exception as e:
        log.warning("Perplexity search failed: %s", e)
        return [{"headline": "Error", "source": "", "url": "", "date": "", "summary": str(e)}]
