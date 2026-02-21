#!/usr/bin/env bash
# Verify competitive intelligence pipeline (LangGraph) setup.

set -e
# Load .env from project root so vars are available without exporting manually
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi
echo "Checking environment..."
test -n "$ANTHROPIC_API_KEY" || { echo "ANTHROPIC_API_KEY not set"; exit 1; }
test -n "$COMPETITORS" || { echo "COMPETITORS not set (comma-separated list)"; exit 1; }

echo "Checking Python and package..."
python3 -c "
from competitive_intel.graph import build_graph
from competitive_intel.config import COMPETITORS
g = build_graph()
assert COMPETITORS, 'COMPETITORS empty'
print('Graph built OK, competitors:', COMPETITORS)
"

echo "Checking output directories..."
test -d files/research && test -d files/drafts && test -d files/final || { echo "files/{research,drafts,final} missing"; exit 1; }
echo "Verify OK."
