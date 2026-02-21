# Competitive Intelligence Agent

A **LangGraph** pipeline that runs a daily competitive intelligence cycle: research competitors with live web search, synthesize an executive brief, critique and revise it, then deliver outputs to the filesystem and optionally to email or Notion.

---

## What It Does

1. **Research** — For each competitor (in parallel), the research node uses **Perplexity Sonar** (primary) or **Tavily** (fallback) to gather recent news, product updates, and strategic moves, and produces a structured dossier.
2. **Write** — The writer node turns all dossiers into a single executive intelligence brief (Markdown).
3. **Critique** — The critic node scores the brief and may request revisions (up to 3 revision cycles).
4. **Deliver** — Final brief and metadata are written to `files/final/`; optional email and Notion delivery are supported.

**Outputs:**

| Path | Description |
|------|-------------|
| `files/research/{date}_{company_slug}.json` | Per-competitor research dossiers |
| `files/drafts/{date}_brief.md` | Draft brief (before delivery) |
| `files/final/{date}_intelligence_brief.md` | Final executive brief |
| `files/final/{date}_metadata.json` | Quality score, approval, delivery status |

---

## Quick Start

### Prerequisites

- **Python 3.12+**
- **Anthropic API key** (required)
- **At least one search provider** (recommended): **Perplexity** or **Tavily** — without one, research runs but with no live web data.

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/competitive-analysis-agent.git
cd competitive-analysis-agent
```

Using **uv** (recommended):

```bash
uv sync
```

Or with pip:

```bash
pip install -e .
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with at least:

```bash
ANTHROPIC_API_KEY=sk-ant-...
COMPETITORS=Company1,Company2,Company3
```

For live research, set **one** of:

- `PERPLEXITY_API_KEY=pplx-...` (recommended; uses Sonar API)
- `TAVILY_API_KEY=tvly-...` (fallback)

See [Environment variables](#environment-variables) for all options.

### 3. Verify

```bash
chmod +x verify.sh
./verify.sh
```

### 4. Run

```bash
python -m competitive_intel.main
```

Inspect outputs under `files/research/`, `files/drafts/`, and `files/final/`.

---

## Workflow (Graph)

The pipeline is a **StateGraph** with parallel research, then a single writer → critic → (optional) revision loop → deliver.

```
START
  → route_research (fan-out: one branch per competitor)
  → research_node (parallel)
  → writer_node
  → critic_node
  → should_revise
       → writer_node (if not approved and revisions left) or deliver_node
  → deliver_node
  → END
```

- **research_node** uses `perplexity_search_tool` (if `PERPLEXITY_API_KEY` is set) or `web_search_tool` (Tavily). It produces one research dossier per competitor and writes JSON to `files/research/`.
- **writer_node** builds the executive brief from all dossiers and writes a draft to `files/drafts/`.
- **critic_node** returns structured feedback (score, approved flag, revision instructions).
- **should_revise** routes to the writer again (up to `MAX_REVISIONS=3`) or to deliver.
- **deliver_node** writes the final brief and metadata to `files/final/` and optionally sends email or creates a Notion page.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key for research, critic, and writer models |
| `COMPETITORS` | Yes | Comma-separated list of competitor names (e.g. `Company A,Company B`) |
| `NOTIFY_EMAIL` | No | Email address for optional delivery notifications |
| `PERPLEXITY_API_KEY` | No* | Perplexity API key (Sonar); primary research tool when set |
| `TAVILY_API_KEY` | No* | Tavily API key; used when Perplexity is not set |
| `MODEL_FAST` | No | Override for research + critic model (default: `claude-sonnet-4-5-20250929`) |
| `MODEL_QUALITY` | No | Override for writer model (default: `claude-sonnet-4-5-20250929`) |
| `NOTION_API_KEY` | No | Notion integration secret |
| `NOTION_DATABASE_ID` | No | Notion database ID for briefs |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | No | SMTP for optional email delivery |
| `POSTGRES_PASSWORD` | No | Used by Docker Compose for Postgres checkpointer |
| `DATABASE_URL` | No | Postgres connection string (set automatically in Docker) |
| `LOG_LEVEL` | No | e.g. `DEBUG` for verbose logs |
| `LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT` | No | LangSmith tracing |

\* At least one of `PERPLEXITY_API_KEY` or `TAVILY_API_KEY` is recommended so research has live web data.

---

## Production

### Cron (host)

Run daily at 7 AM:

```bash
0 7 * * * cd /path/to/competitive-analysis-agent && python -m competitive_intel.main >> /var/log/competitive-intel.log 2>&1
```

Install: `crontab crontab` (after editing the path in `crontab`).

### Docker Compose

Optional Postgres checkpointer + agent:

```bash
docker compose up -d postgres
docker compose run --rm agent
```

Ensure the agent image runs `python -m competitive_intel.main` (see `Dockerfile` CMD). Output directories are mounted at `./files`.

---

## Development

```bash
uv sync --extra dev
# or: pip install -e ".[dev]"

ruff check .
uv run pytest
# or: python -m pytest
```

Set `LOG_LEVEL=DEBUG` in `.env` for verbose logs.

### LangSmith

To trace runs in LangSmith, add to `.env`:

```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_PROJECT=competitive-intel
```

No code changes required; LangChain reads these automatically.

---

## Project Layout

```
competitive-intel/
├── competitive_intel/
│   ├── main.py          # Entrypoint: python -m competitive_intel.main
│   ├── graph.py         # StateGraph, routing, checkpointer
│   ├── state.py         # PipelineState, ResearchDossier, CriticFeedback
│   ├── config.py       # Env loading, COMPETITORS, paths, model names
│   ├── callbacks.py     # Token usage logging
│   ├── nodes/
│   │   ├── research.py  # Per-competitor research (Perplexity/Tavily)
│   │   ├── writer.py    # Brief generation
│   │   ├── critic.py    # Quality scoring and revision feedback
│   │   └── deliver.py   # Final write + optional email/Notion
│   └── tools/
│       ├── perplexity_search.py  # Sonar API (primary)
│       └── web_search.py         # Tavily (fallback)
├── files/
│   ├── research/        # Dossier JSON per competitor
│   ├── drafts/         # Draft briefs
│   └── final/          # Final brief + metadata
├── tests/
├── .env.example
├── verify.sh
├── Dockerfile
├── docker-compose.yml
├── crontab
└── pyproject.toml
```

---

## Models

| Role | Default model | Env override |
|------|----------------|--------------|
| Research + Critic | `claude-sonnet-4-5-20250929` | `MODEL_FAST` |
| Writer | `claude-sonnet-4-5-20250929` | `MODEL_QUALITY` |
| Research tool (when used) | Perplexity Sonar | `PERPLEXITY_API_KEY` |

You can set `MODEL_QUALITY=claude-opus-4-6` (or another model) for higher-quality briefs when available.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ANTHROPIC_API_KEY not set` | Add your key to `.env` |
| `COMPETITORS not set` | Set `COMPETITORS=Name1,Name2` in `.env` |
| No search results / “No search tool configured” | Set `PERPLEXITY_API_KEY` or `TAVILY_API_KEY` in `.env` |
| Checkpointer errors | Leave `DATABASE_URL` unset for in-memory mode; or run Postgres and set it in Docker |
| Tests fail | Install dev deps: `uv sync --extra dev` or `pip install -e ".[dev]"` |

---

## License

See repository license file.
