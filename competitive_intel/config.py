"""
Settings and constants loaded from environment.

Env vars: ANTHROPIC_API_KEY, COMPETITORS, NOTIFY_EMAIL, NOTION_API_KEY,
TAVILY_API_KEY, PERPLEXITY_API_KEY, DATABASE_URL (optional, for postgres checkpointer),
LOG_LEVEL (optional, e.g. DEBUG).

Observability (optional, picked up automatically by LangChain):
  LANGCHAIN_TRACING_V2=true
  LANGCHAIN_API_KEY=ls__...
  LANGCHAIN_PROJECT=competitive-intel
"""

import os
import re
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── API & model ─────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
# Models are overridable via .env (e.g. MODEL_QUALITY=claude-sonnet-4-5-20250929 to avoid Opus 529s)
MODEL_FAST = os.environ.get("MODEL_FAST", "claude-sonnet-4-5-20250929")     # Research + Critic
MODEL_QUALITY = os.environ.get("MODEL_QUALITY", "claude-sonnet-4-5-20250929")  # Writer (Opus when available)


def today_str() -> str:
    """Current date in UTC as YYYY-MM-DD (shared across nodes)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ── Competitors ─────────────────────────────────────────────────────────────
def _sanitize_competitor(name: str) -> str:
    """
    Strip characters that could cause path traversal or prompt injection.
    Removes path separators, null bytes, and dangerous shell/template characters.
    Enforces a max length of 100 chars.
    """
    # Remove null bytes and path separators
    name = name.replace("\x00", "").replace("/", "").replace("\\", "")
    # Strip leading/trailing dots (prevent ../ traversal)
    name = name.strip(".")
    # Allow letters, digits, spaces, hyphens, ampersands, dots, commas, parentheses
    name = re.sub(r"[^\w\s\-&.,()]", "", name)
    # Collapse whitespace
    name = " ".join(name.split())
    return name[:100]


def _get_competitors() -> list[str]:
    raw = os.environ.get("COMPETITORS", "")
    return [_sanitize_competitor(c) for c in raw.split(",") if c.strip()]


COMPETITORS = _get_competitors()

# ── Delivery ───────────────────────────────────────────────────────────────
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", "")
NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "")

# ── Tools (optional) ───────────────────────────────────────────────────────
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")

# ── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
FILES_DIR = BASE_DIR / "files"
RESEARCH_DIR = FILES_DIR / "research"
DRAFTS_DIR = FILES_DIR / "drafts"
FINAL_DIR = FILES_DIR / "final"

for d in (RESEARCH_DIR, DRAFTS_DIR, FINAL_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ── Pipeline ───────────────────────────────────────────────────────────────
# MAX_REVISIONS = number of revision *cycles* (critic → writer loops).
# The writer always runs once for the initial draft (not counted).
# E.g. MAX_REVISIONS=3 means up to 3 additional revision passes after the initial draft.
MAX_REVISIONS = 3

# ── Persistence ───────────────────────────────────────────────────────────
# Leave unset for local runs (MemorySaver); set in Docker or .env for Postgres.
DATABASE_URL = os.environ.get("DATABASE_URL", "")
