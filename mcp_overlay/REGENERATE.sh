#!/usr/bin/env bash
# Recreate mcp_overlay from git history if Docker build reports missing mcp_server skills.
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf mcp_overlay
mkdir -p mcp_overlay
git archive 77665bcc backend/mcp_server | tar -x -C mcp_overlay
find mcp_overlay -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find mcp_overlay -name '*.pyc' -delete 2>/dev/null || true
echo "mcp_overlay ready ($(ls mcp_overlay/backend/mcp_server/skills/*.py 2>/dev/null | wc -l) skill modules)"
