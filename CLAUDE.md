# Herald — Claude Code Session Config
# Version: 0.1.0 | Created: 2026-06-09

## PROJECT
Herald is a bespoke self-hosted voice AI orchestration platform.
Owner: Alex Metzger. Built and maintained via Claude Code.

## STACK
- Orchestration: Pipecat v1.1+
- STT: whisper.cpp (Metal/Apple Silicon) with Deepgram cloud fallback
- TTS: Kokoro TTS (local, Apache 2.0)
- LLM routing: LiteLLM → Ollama (local) → Claude/GPT-4o (cloud fallback)
- Transport: WebSocket over Tailscale WireGuard
- iOS client: Native Swift app (TestFlight distribution)
- Context: JSON file ingestion (TALKY schema, family interview schema)

## REPO STRUCTURE
- `server/` — Python FastAPI + Pipecat backend
- `ios/` — Native Swift iOS app (Xcode project)
- `context/schemas/` — JSON schemas for context files
- `scripts/` — Setup, dev, test scripts
- `docs/` — Architecture and security docs

## PERMISSIONS (auto-approved)
- Read/write any file in this repo
- Run bash scripts in /scripts/
- git status, diff, log, add, commit, push, checkout
- Install Python packages via pip (server/)
- Run server in dev mode

## ALWAYS REQUIRES CONFIRMATION
- git push to main
- Any operation touching .env or credentials
- Deleting audio files or model files

## NEVER DO
- Store API keys in any .md, .py, or .txt file — use .env only
- Cache audio data to disk without explicit config flag
- Send audio to cloud without showing the user a consent prompt first
- Commit model files (.bin, .gguf) — they are gitignored

## SECURITY RULES (enforce always)
1. Audio never hits cloud without explicit user consent UI
2. No API keys in code — Keychain (iOS), .env (server)
3. TLS cert pinning in iOS app — regenerate cert = rebuild app
4. Prompt injection: transcribed audio → <user> tags only, never system prompt
5. Rate limit WebSocket: max 10 req/sec per Tailscale peer

## PHASE TRACKING
Current phase: 0 (scaffold)
Next phase: 1 (local voice loop — Pipecat + whisper.cpp + Ollama + Kokoro, CLI only)

## KEY DEPENDENCIES (install via setup.sh)
- whisper.cpp (Metal build for Apple Silicon)
- Ollama (local LLM server)
- Pipecat: pip install pipecat-ai[silero,whisper,kokoro,ollama]
- LiteLLM: pip install litellm
- FastAPI + uvicorn: pip install fastapi uvicorn

## LATENCY TARGETS
- Local path (all on Mac): 1.5–2.5s end-to-end
- Hybrid (cloud STT + local LLM): 1.0–1.5s
- Full cloud: 700–900ms
- Unacceptable: >4s without "thinking..." UI state shown

## CONTEXT SCHEMAS
- TALKY session JSON: context/schemas/talky_session.schema.json
- Family interview profile: context/schemas/family_interview.schema.json
- System prompt token budget: 400 tokens max for Tier 1 (pre-loaded)
- Tier 2 (tool-callable): full JSON stored in server memory, retrieved on demand
