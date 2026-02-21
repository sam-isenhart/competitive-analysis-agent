"""Web search tool using Tavily API. Returns list of {title, url, snippet, content}."""

from langchain_core.tools import tool

from competitive_intel.config import TAVILY_API_KEY


@tool
def web_search_tool(query: str, max_results: int = 8) -> list[dict]:
    """
    Search the web for current information. Use this to find recent news,
    product updates, and company information. Returns a list of results
    with title, url, snippet, and content.
    """
    if not TAVILY_API_KEY:
        return [{"title": "N/A", "url": "", "snippet": "TAVILY_API_KEY not set.", "content": ""}]
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=TAVILY_API_KEY)
        response = client.search(
            query=query,
            max_results=min(max_results, 20),
            search_depth="basic",
        )
        results = []
        for r in response.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": (r.get("content") or "")[:500],
                "content": r.get("content", ""),
            })
        return results
    except Exception as e:
        return [{"title": "Error", "url": "", "snippet": str(e), "content": ""}]
