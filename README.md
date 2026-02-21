# Competitive Intelligence Agent

LangGraph pipeline that performs competitor research with live tools, writes an executive brief, critiques it, and delivers results to files plus optional email/Notion.

## Purpose

The agent runs a daily competitive intelligence cycle:
1. Research each competitor in parallel with web/news/Perplexity/scrape tools.
2. Synthesize findings into one executive brief.
3. Critique the draft and request revisions if needed.
4. Deliver final outputs for leadership.

Primary outputs:
- `files/final/{YYYY-MM-DD}_intelligence_brief.md`
- `files/final/{YYYY-MM-DD}_metadata.json`

## Agentic Workflow (Step-by-Step)

This is the exact workflow the graph executes:

1. `START` receives initial state (`competitors`, empty `research`, empty `brief`).
2. `route_research` fans out one `Send` per competitor.
3. `research_node` runs per competitor:
   - Uses `web_search_tool`, `news_search_tool`, `scrape_url_tool`, and optionally `perplexity_search_tool`.
   - Produces one structured research dossier.
   - Writes dossier JSON to `files/research/`.
4. Fan-in reducer (`operator.add`) merges all dossiers into `state["research"]`.
5. `writer_node` generates the executive brief from all dossiers.
   - Writes draft markdown to `files/drafts/`.
6. `critic_node` scores the brief and returns structured feedback.
7. `should_revise` routes:
   - to `writer_node` if not approved and revision cycles remain (max `MAX_REVISIONS=3`);
   - to `deliver_node` if approved or max revisions reached.
8. `deliver_node` writes final brief + metadata and optionally sends email / creates Notion page.
9. `END` returns final state with delivery metadata.

How to run this workflow manually:

1. Set `.env` (minimum: `ANTHROPIC_API_KEY`, `COMPETITORS`).
2. Run `python -m competitive_intel.main`.
3. Inspect outputs in `files/research/`, `files/drafts/`, and `files/final/`.
4. Use `files/final/*_metadata.json` to confirm quality score and delivery status.

## Architecture

```text
cron (daily 7 AM)
  -> python -m competitive_intel.main
  -> StateGraph:
       START
        -> route_research (fan-out)
        -> research_node (parallel per competitor)
        -> writer_node
        -> critic_node
        -> should_revise
             -> writer_node (loop, max 3 revision cycles) OR deliver_node
        -> END
```

## Prerequisites

- Python `3.12+`
- Anthropic API key
- Optional integration keys:
  - Tavily (`TAVILY_API_KEY`) for web/news enrichment
  - Perplexity (`PERPLEXITY_API_KEY`) for deep synthesis via Sonar model
  - News API (`NEWS_API_KEY`) fallback for news
  - Notion (`NOTION_API_KEY`, `NOTION_DATABASE_ID`)
  - SMTP (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`)

## Setup

1. Install package.

```bash
pip install -e .
```

2. Create environment file.

```bash
cp .env.example .env
```

3. Edit `.env` minimum values:

```bash
ANTHROPIC_API_KEY=sk-ant-...
COMPETITORS=Company1,Company2,Company3
```

4. Verify baseline configuration.

```bash
chmod +x verify.sh
./verify.sh
```

5. Run once.

```bash
python -m competitive_intel.main
```

## Production Runbook

### Cron (host Python)

```bash
0 7 * * * cd /path/to/competitive-analysis-agent && python -m competitive_intel.main >> /var/log/competitive-intel.log 2>&1
```

### Docker Compose

```bash
docker compose up -d postgres
docker compose run --rm agent
```

## Development

Install dev dependencies and run checks:

```bash
pip install -e ".[dev]"
ruff check .
python -m pytest
```

Set `LOG_LEVEL=DEBUG` in `.env` for verbose logs.

### Observability (LangSmith)

To trace pipeline runs in LangSmith, add to `.env`:

```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_PROJECT=competitive-intel
```

No code changes are needed — LangChain picks these up automatically.

## Project Layout

```text
competitive_intel/
  main.py            # Entrypoint
  graph.py           # Graph routing + checkpointer
  state.py           # Typed state schema
  config.py          # Env/config/constants
  callbacks.py       # Token usage logging callback
  nodes/
    research.py
    writer.py
    critic.py
    deliver.py
  tools/
    web_search.py
    news.py
    scraper.py
    perplexity_search.py
files/
  research/
  drafts/
  final/
tests/
```

## Models

- Research + Critic: `claude-sonnet-4-5-20250929`
- Writer: `claude-opus-4-6`
- Perplexity research (optional): `sonar`

## Troubleshooting

- `ANTHROPIC_API_KEY not set`: add key to `.env`.
- `No competitors configured`: set `COMPETITORS=Name1,Name2`.
- Checkpointer issues: leave `DATABASE_URL` empty for local memory mode.
- Missing test runner: install dev deps with `pip install -e ".[dev]"`.
