"""Tools for research agents: Perplexity search (primary) and Tavily web search (fallback)."""

from competitive_intel.tools.web_search import web_search_tool
from competitive_intel.tools.perplexity_search import perplexity_search_tool

__all__ = ["web_search_tool", "perplexity_search_tool"]
