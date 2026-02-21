"""News search tool. Uses Tavily with topic=news when TAVILY_API_KEY is set; else optional NewsAPI."""

from langchain_core.tools import tool

from competitive_intel.config import NEWS_API_KEY, TAVILY_API_KEY


@tool
def news_search_tool(query: str, days_back: int = 7) -> list[dict]:
    """
    Search for recent news articles. Use for company news, announcements,
    and industry updates. Returns list of {headline, source, date, url, summary}.
    """
    if TAVILY_API_KEY:
        return _news_via_tavily(query, days_back)
    if NEWS_API_KEY:
        return _news_via_newsapi(query, days_back)
    return [{"headline": "N/A", "source": "", "date": "", "url": "", "summary": "No news API key set."}]


def _news_via_tavily(query: str, days_back: int) -> list[dict]:
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=TAVILY_API_KEY)
        time_range = "week" if days_back >= 7 else "day"
        response = client.search(
            query=query,
            topic="news",
            time_range=time_range,
            max_results=10,
        )
        out = []
        for r in response.get("results", []):
            out.append({
                "headline": r.get("title", ""),
                "source": r.get("url", "").split("/")[2] if r.get("url") else "",
                "date": r.get("published_date", ""),
                "url": r.get("url", ""),
                "summary": (r.get("content") or "")[:400],
            })
        return out
    except Exception as e:
        return [{"headline": "Error", "source": "", "date": "", "url": "", "summary": str(e)}]


def _news_via_newsapi(query: str, days_back: int) -> list[dict]:
    try:
        import httpx
        from datetime import datetime, timezone, timedelta
        to_date = datetime.now(timezone.utc)
        from_date = to_date - timedelta(days=days_back)
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "apiKey": NEWS_API_KEY,
            "from": from_date.strftime("%Y-%m-%d"),
            "to": to_date.strftime("%Y-%m-%d"),
            "pageSize": 10,
            "sortBy": "publishedAt",
        }
        with httpx.Client() as client:
            resp = client.get(url, params=params, timeout=15.0)
            resp.raise_for_status()
        data = resp.json()
        out = []
        for a in data.get("articles", []):
            out.append({
                "headline": a.get("title", ""),
                "source": a.get("source", {}).get("name", ""),
                "date": a.get("publishedAt", "")[:10],
                "url": a.get("url", ""),
                "summary": (a.get("description") or "")[:400],
            })
        return out
    except Exception as e:
        return [{"headline": "Error", "source": "", "date": "", "url": "", "summary": str(e)}]
