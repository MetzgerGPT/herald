#!/bin/bash
# Herald — smoke test the local voice pipeline
# Tests: health check, WebSocket auth, context loading
# Requires: server running (bash scripts/dev.sh), wscat (npm i -g wscat), jq
set -euo pipefail

HERALD_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVER_URL="${HERALD_SERVER_URL:-http://localhost:8765}"
WS_URL="${HERALD_WS_URL:-ws://localhost:8765}"

# Load .env for token
if [ -f "$HERALD_ROOT/.env" ]; then
    # shellcheck disable=SC1091
    set -o allexport; source "$HERALD_ROOT/.env"; set +o allexport
fi

TOKEN="${HERALD_AUTH_TOKEN:-}"
if [ -z "$TOKEN" ]; then
    echo "ERROR: HERALD_AUTH_TOKEN not set"
    exit 1
fi

PASS=0; FAIL=0

check() {
    local name="$1"; local result="$2"
    if [ "$result" = "ok" ]; then
        echo "  ✓ $name"; ((PASS++)) || true
    else
        echo "  ✗ $name: $result"; ((FAIL++)) || true
    fi
}

echo "=== Herald pipeline smoke test ==="
echo "Server: $SERVER_URL"
echo ""

# ── 1. Health check ───────────────────────────────────────────────────────────
echo "→ Health check..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$SERVER_URL/health" 2>/dev/null || echo "000")
[ "$HTTP_STATUS" = "200" ] && check "GET /health → 200" "ok" || check "GET /health" "HTTP $HTTP_STATUS (server not running?)"

# ── 2. Auth rejection ─────────────────────────────────────────────────────────
echo ""
echo "→ Auth checks..."
# WS with no token should be rejected (FastAPI returns 403 before upgrade in our impl)
NOAUTH=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Upgrade: websocket" \
    "$SERVER_URL/voice?mode=freeform" 2>/dev/null || echo "000")
[ "$NOAUTH" = "403" ] && check "WS without token → 403" "ok" || check "WS without token" "HTTP $NOAUTH (expected 403)"

# ── 3. Ollama reachability ────────────────────────────────────────────────────
echo ""
echo "→ Ollama reachability..."
OLLAMA_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
OLLAMA_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$OLLAMA_URL/api/tags" 2>/dev/null || echo "000")
[ "$OLLAMA_STATUS" = "200" ] && check "Ollama /api/tags → 200" "ok" || check "Ollama" "HTTP $OLLAMA_STATUS (ollama not running?)"

# ── 4. Context loader (unit-level) ────────────────────────────────────────────
echo ""
echo "→ Context loader..."
VENV_DIR="$HERALD_ROOT/.venv"
if [ -d "$VENV_DIR" ]; then
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    LOADER_RESULT=$(python3 -c "
import sys, json
sys.path.insert(0, '$(pwd)')
from server.context_loader import ContextLoader
import tempfile, os
data = {'user': {'name': 'Alex'}, 'session_id': 'test-001', 'date': '2026-06-09',
        'priorities': [{'title': 'Herald Phase 0', 'status': 'active'}],
        'next_action': {'title': 'Initial commit', 'due': '2026-06-09'}}
with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
    json.dump(data, f); fname = f.name
try:
    loader = ContextLoader('context/schemas')
    ctx = loader.load('talky', fname)
    assert ctx['_mode'] == 'talky'
    assert 'Alex' in ctx['_system_context_tier1']
    assert ctx['_raw']['session_id'] == 'test-001'
    print('ok')
except Exception as e:
    print(str(e))
finally:
    os.unlink(fname)
" 2>&1)
    check "ContextLoader.load (talky)" "$LOADER_RESULT"
else
    check "ContextLoader.load" "skipped (.venv not found)"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
