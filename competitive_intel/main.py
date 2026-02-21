"""
Entry point: build graph, invoke with competitors from config, exit.

Run via: python -m competitive_intel.main
Or cron: 0 7 * * * cd /path && python -m competitive_intel.main
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone

from competitive_intel.config import ANTHROPIC_API_KEY, COMPETITORS
from competitive_intel.graph import build_graph

_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(name)-18s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


async def main() -> int:
    if not ANTHROPIC_API_KEY:
        log.error("ANTHROPIC_API_KEY not set.")
        return 1

    if not COMPETITORS:
        log.error("No competitors configured. Set COMPETITORS env var (comma-separated).")
        return 1

    log.info("Starting pipeline for %d competitors: %s", len(COMPETITORS), ", ".join(COMPETITORS))

    graph = build_graph()

    # Use date-based thread_id so each daily run gets its own checkpoint
    thread_id = f"competitive-intel-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"

    initial = {
        "competitors": COMPETITORS,
        "research": [],
        "brief": "",
        "feedback": None,
        "revision_count": 0,
        "final_brief": "",
        "metadata": {},
    }
    config = {"configurable": {"thread_id": thread_id}}

    try:
        result = await graph.ainvoke(initial, config=config)
    except Exception as exc:
        log.error("Pipeline failed: %s", exc, exc_info=True)
        return 1

    score = result.get("metadata", {}).get("quality_score", "N/A")
    approved = result.get("metadata", {}).get("approved", False)
    log.info("Pipeline complete. Quality score: %s, Approved: %s", score, approved)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
