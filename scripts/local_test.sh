#!/bin/bash
# Herald — run local voice pipeline (Phase 1 test, no server/WebSocket)
# Prerequisites: bash scripts/setup.sh && ollama pull llama3.3
set -euo pipefail

HERALD_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERALD_ROOT"

VENV_DIR="$HERALD_ROOT/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "ERROR: .venv not found. Run: bash scripts/setup.sh"
    exit 1
fi

# Load .env if present
if [ -f "$HERALD_ROOT/.env" ]; then
    set -o allexport
    # shellcheck disable=SC1091
    source "$HERALD_ROOT/.env"
    set +o allexport
fi

# Verify Ollama is reachable
OLLAMA_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
if ! curl -s --max-time 3 "$OLLAMA_URL/api/tags" > /dev/null 2>&1; then
    echo "WARNING: Ollama not responding at $OLLAMA_URL"
    echo "  Start it with: ollama serve"
    echo "  Then: ollama pull ${HERALD_LOCAL_LLM_MODEL:-llama3.3}"
    read -rp "Continue anyway? [y/N] " reply
    [[ "$reply" =~ ^[Yy]$ ]] || exit 1
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

MODE="${1:-freeform}"
CONTEXT_FILE="${2:-}"

echo "=== Herald local voice pipeline ==="
echo "Mode: $MODE"
[ -n "$CONTEXT_FILE" ] && echo "Context: $CONTEXT_FILE"
echo ""

if [ -n "$CONTEXT_FILE" ]; then
    python -m server.local_pipeline --mode "$MODE" --context "$CONTEXT_FILE"
else
    python -m server.local_pipeline --mode "$MODE"
fi
