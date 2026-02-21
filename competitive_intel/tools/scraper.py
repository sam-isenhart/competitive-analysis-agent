"""URL content extraction tool. Fetches a URL and returns main text content."""

import logging

import httpx
from langchain_core.tools import tool

log = logging.getLogger(__name__)


@tool
def scrape_url_tool(url: str) -> str:
    """
    Fetch a URL and extract the main text content. Use this to read
    full articles or pages when you have a specific URL from search results.
    """
    if not url.startswith(("http://", "https://")):
        return "Error: URL must start with http:// or https://"

    # Primary: trafilatura for clean article extraction
    try:
        import trafilatura

        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=True,
                no_fallback=False,
            )
            if text:
                return text[:15000]
        log.debug("trafilatura returned no content for %s, using httpx fallback", url)
    except Exception as e:
        log.debug("trafilatura failed for %s: %s", url, e)

    # Fallback: raw fetch with basic tag stripping
    try:
        import re

        with httpx.Client(follow_redirects=True, timeout=15.0) as client:
            resp = client.get(url)
            resp.raise_for_status()
        html = resp.text
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:15000] if text else "No text content extracted."
    except Exception as e:
        return f"Error fetching URL: {e}"
