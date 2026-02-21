FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY pyproject.toml .
# Create a minimal package so pip install works without source code present
RUN mkdir -p competitive_intel && \
    echo '"""Competitive intelligence pipeline."""' > competitive_intel/__init__.py && \
    pip install --no-cache-dir . && \
    rm -rf competitive_intel

# Copy actual source
COPY competitive_intel/ competitive_intel/

CMD ["python", "-m", "competitive_intel"]
