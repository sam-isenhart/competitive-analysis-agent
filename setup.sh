#!/usr/bin/env bash
# Competitive Intelligence (LangGraph) — local setup. No n8n.

set -euo pipefail
echo "Competitive Intelligence — Setup"
echo ""

# Prerequisites
for cmd in python3 pip; do
    command -v "$cmd" &>/dev/null || { echo "Need $cmd"; exit 1; }
done

if [ ! -f .env ]; then
    echo "Create .env with ANTHROPIC_API_KEY and COMPETITORS (comma-separated)."
    exit 1
fi

mkdir -p files/research files/drafts files/final
pip install -e . -q
echo "Setup OK. Run: python -m competitive_intel.main"
echo "Verify: ./verify.sh"
