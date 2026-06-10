#!/bin/bash
# Herald Phase 1 local dev setup
# Run once on a new Mac to install all dependencies.
# Requires: Homebrew, Python 3.11+, Xcode Command Line Tools (for whisper.cpp Metal build)
set -euo pipefail

HERALD_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERALD_ROOT"

echo "=== Herald setup ==="
echo "Root: $HERALD_ROOT"

# ── 1. Homebrew dependencies ──────────────────────────────────────────────────
echo ""
echo "→ Checking Homebrew..."
if ! command -v brew &>/dev/null; then
    echo "ERROR: Homebrew not found. Install from https://brew.sh then re-run."
    exit 1
fi

brew install cmake ffmpeg portaudio 2>/dev/null || true

# ── 2. Ollama ─────────────────────────────────────────────────────────────────
echo ""
echo "→ Checking Ollama..."
if ! command -v ollama &>/dev/null; then
    echo "Installing Ollama..."
    brew install ollama
fi
echo "   Pulling llama3.3 (this takes a while on first run)..."
ollama pull llama3.3

# ── 3. whisper.cpp ────────────────────────────────────────────────────────────
echo ""
echo "→ Building whisper.cpp..."
WHISPER_DIR="$HERALD_ROOT/vendor/whisper.cpp"
if [ ! -d "$WHISPER_DIR" ]; then
    git clone https://github.com/ggerganov/whisper.cpp.git "$WHISPER_DIR"
fi
cd "$WHISPER_DIR"
git pull --ff-only 2>/dev/null || true
# Build with Metal acceleration (Apple Silicon)
cmake -B build -DWHISPER_METAL=ON
cmake --build build --config Release -j"$(sysctl -n hw.ncpu)"
# Download base.en model
bash models/download-ggml-model.sh base.en
cd "$HERALD_ROOT"

# ── 4. Python venv + dependencies ─────────────────────────────────────────────
echo ""
echo "→ Setting up Python venv..."
VENV_DIR="$HERALD_ROOT/.venv"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$HERALD_ROOT/server/requirements.txt"
# Kokoro requires espeak-ng on macOS
if ! command -v espeak-ng &>/dev/null; then
    brew install espeak-ng 2>/dev/null || echo "WARN: espeak-ng install failed — Kokoro TTS may not work"
fi

# ── 5. .env check ─────────────────────────────────────────────────────────────
echo ""
if [ ! -f "$HERALD_ROOT/.env" ]; then
    cp "$HERALD_ROOT/.env.example" "$HERALD_ROOT/.env"
    echo "→ Created .env from .env.example"
    echo "  IMPORTANT: Set HERALD_AUTH_TOKEN in .env before running the server."
    echo "  Generate: openssl rand -hex 32"
else
    echo "→ .env already exists — skipping"
fi

echo ""
echo "=== Setup complete ==="
echo "Next: bash scripts/dev.sh"
