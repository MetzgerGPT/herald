#!/bin/bash
# Herald — start local dev server
# Prerequisites: bash scripts/setup.sh has been run
set -euo pipefail

HERALD_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERALD_ROOT"

VENV_DIR="$HERALD_ROOT/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "ERROR: .venv not found. Run: bash scripts/setup.sh"
    exit 1
fi

if [ ! -f "$HERALD_ROOT/.env" ]; then
    echo "ERROR: .env not found. Copy .env.example → .env and set HERALD_AUTH_TOKEN."
    exit 1
fi

# Validate token is set
# shellcheck disable=SC1091
source "$HERALD_ROOT/.env"
if [ -z "${HERALD_AUTH_TOKEN:-}" ]; then
    echo "ERROR: HERALD_AUTH_TOKEN is not set in .env"
    echo "Generate: openssl rand -hex 32"
    exit 1
fi

# Start Ollama if not running
if ! pgrep -x ollama &>/dev/null; then
    echo "→ Starting Ollama..."
    ollama serve &>/tmp/ollama.log &
    sleep 2
fi

echo "→ Starting Herald server..."
echo "   Mode: ${HERALD_ENV:-development}"
echo "   LLM:  ${HERALD_LOCAL_LLM_MODEL:-llama3.3} (local)"
echo ""

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# Load .env into environment
set -o allexport
# shellcheck disable=SC1091
source "$HERALD_ROOT/.env"
set +o allexport

exec uvicorn server.main:app \
    --host 0.0.0.0 \
    --port 8765 \
    --reload \
    --log-level info
