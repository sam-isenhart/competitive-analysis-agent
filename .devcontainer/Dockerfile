FROM mcr.microsoft.com/devcontainers/python:3.12

# Install procps so Cursor server install and tools (e.g. ps) work
RUN apt-get update && apt-get install -y --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Configure uv to use the project's .venv
ENV UV_PROJECT_ENVIRONMENT="/workspaces/competitive-analysis-agent/.venv"
