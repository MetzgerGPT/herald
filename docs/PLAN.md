# Herald — Execution Plan

This document is the canonical phase-by-phase plan. It survives context resets.
Last updated: 2026-06-10.

---

## Current state: Phase 0 complete, Phase 1 ready to run

All scaffold files committed. Core API bugs corrected against Pipecat 1.3.0 live source.

---

## Phase 0 — Scaffold ✅ DONE

**Commit:** `5ac1116` (2026-06-10)

**What's in place:**
- `server/main.py` — FastAPI app, Bearer auth, WebSocket `/voice` endpoint
- `server/pipeline.py` — Pipecat pipeline: Whisper STT → Ollama LLM → Kokoro TTS
- `server/local_pipeline.py` — Standalone local voice loop for Phase 1 testing (no WebSocket)
- `server/context_loader.py` — Two-tier JSON context (TALKY + family interview)
- `server/auth.py` — `hmac.compare_digest` constant-time Bearer token verification
- `context/schemas/talky_session.schema.json`
- `context/schemas/family_interview.schema.json`
- `scripts/setup.sh` — Windows PC setup (Homebrew, Ollama, faster-whisper, Python venv)
- `scripts/dev.sh` — Start dev server
- `scripts/test_pipeline.sh` — Smoke tests (health, auth, Ollama, context loader)
- `scripts/local_test.sh` — Run `server/local_pipeline.py`
- `docs/architecture.md`, `docs/security.md`
- `ios/README.md` — Phase 2 placeholder

**API correctness fixes applied (vs Pipecat 1.3.0 live source):**
| Bug | Fix |
|-----|-----|
| `OpenAILLMContext` renamed | → `LLMContext` (`pipecat.processors.aggregators.llm_context`) |
| `OllamaLLMService` wrong name/path | → `OLLamaLLMService` (`pipecat.services.ollama.llm`) |
| `fastapi_websocket` module renamed | → `pipecat.transports.websocket.fastapi` |
| `pipecat.vad.silero` moved | → `pipecat.audio.vad.silero` |
| `VADProcessor` wrong placement | VAD lives in `LLMUserAggregatorParams`, not as pipeline stage |
| `llm.create_context_aggregator()` old API | → `LLMContextAggregatorPair` + `LLMUserAggregatorParams` |
| No serializer — silently drops all frames | → `ProtobufFrameSerializer()` required |
| `KokoroTTSService` import path | → `pipecat.services.kokoro.tts` |
| `allow_interruptions` removed in 1.3.0 | → `PipelineParams()` no args |
| `FastAPIWebsocketParams` missing audio flags | → `audio_in_enabled=True, audio_out_enabled=True` |

---

## Phase 1 — Local voice loop ← CURRENT

**Goal:** Confirm the full voice pipeline works on the Windows PC before adding any networking.

**No iPhone. No WebSocket server. Mic + speaker direct.**

### Steps

1. `git clone https://github.com/MetzgerGPT/herald` (PowerShell)
2. Elevated PowerShell: `.\scripts\setup.ps1` — installs all deps including faster-whisper + PyAudio
3. Set `HERALD_AUTH_TOKEN` in `.env`
4. Confirm Ollama running: start Ollama from system tray or `ollama serve`
5. Confirm model pulled: `ollama pull llama3.3`
6. `.\scripts\local_test.ps1` — runs `server/local_pipeline.py`
7. Speak into mic → wait for Herald to respond

**Success criteria:**
- [ ] Mic audio captured without errors
- [ ] Whisper transcribes speech to text (see logs)
- [ ] Ollama responds with a completion
- [ ] Kokoro generates audio
- [ ] Response plays through speaker

**With TALKY context:**
```bash
python -m server.local_pipeline --mode talky --context ~/talky/output/latest.json
```

### Troubleshooting checkpoints

| Symptom | Likely cause |
|---------|-------------|
| PyAudio import error | `pipecat-ai[local]` not installed, or Microsoft C++ Build Tools missing |
| Whisper import error | `pipecat-ai[whisper]` extra not installed |
| Ollama timeout | Ollama not running — start from system tray or `ollama serve` |
| Kokoro error | `pipecat-ai[kokoro]` extra not installed, or espeak-ng not installed/on PATH |
| No mic input | Windows mic permissions — Settings → Privacy → Microphone → allow app access |

---

## Phase 2 — iOS client (TestFlight)

**Goal:** iPhone app connects to Windows PC server over Tailscale.

**Prerequisites:** Phase 1 voice loop working.

### Steps
1. Set up Tailscale on Windows PC mini and iPhone
2. Generate TLS cert for Tailscale hostname
3. Fix WebSocket server for iOS client:
   - iOS uses `URLSessionWebSocketTask` (native Swift)
   - Must implement `ProtobufFrameSerializer` wire protocol client-side
   - OR switch server to `add_wav_header=True` with raw PCM protocol (simpler for Swift)
4. Xcode project: `ios/Herald.xcodeproj`
   - SwiftUI UI: mode picker, connect/disconnect, VAD status indicator
   - `AVAudioEngine` for raw PCM capture
   - WebSocket with Bearer auth header
   - TLS cert pinning
5. TestFlight distribution

**Key decision — serializer:**
- `ProtobufFrameSerializer`: requires Swift Protobuf codegen; client must have `frames_pb2` equivalent
- Raw PCM with WAV header: simpler Swift implementation, set `add_wav_header=True` in server
- **Recommendation:** Build a thin server-side `RawPCMSerializer` that accepts raw PCM binary messages; remove Protobuf dependency for the iOS path

---

## Phase 3 — Cloud fallback + consent gate

**Goal:** Optional cloud LLM/STT when local is too slow or unavailable.

**Security requirement:** No silent fallback. Cloud requires explicit `allow_cloud=true` in WebSocket session params.

### Changes
- `server/pipeline.py`: LiteLLM routing — Ollama primary, Claude/GPT-4o fallback
- `server/main.py`: accept `allow_cloud` query param, validate and pass to pipeline
- Deepgram STT path (gated on `allow_cloud`)
- Rate limiting on `/voice` endpoint (slowapi or custom)
- Session isolation — per-connection pipeline instances already exist; add resource limits

---

## Phase 4 — Tier 2 context (tool-callable full JSON)

**Goal:** LLM can request full context JSON on demand, not just the 400-token Tier 1 summary.

### Changes
- Register a `get_full_context` tool on the LLM in `pipeline.py`
- Tool handler returns `context["_raw"]` as JSON
- Scope the tool — LLM can call it once per session, not in a loop
- Add logging when Tier 2 is accessed

---

## Phase 5 — Multi-mode session management

**Goal:** Clean session handoff between modes (TALKY → family interview → freeform).

### Changes
- Session state persisted in Supabase (or local SQLite for pure-local operation)
- `/voice` endpoint accepts `session_id` to resume a session
- Context hot-reload — update context mid-session without reconnecting
- Webhook from TALKY output dir watcher → triggers context reload

---

## Key architectural decisions (locked)

| Decision | Choice | Reason |
|----------|--------|--------|
| Transport | WebSocket over Tailscale | Simpler than WebRTC for client-server; no NAT traversal needed |
| STT | faster-whisper (local) | Metal-accelerated on Apple Silicon; ~10× real-time; no cloud dependency |
| LLM | Ollama (local-first) | Full data sovereignty; cloud is opt-in |
| TTS | Kokoro | Apache 2.0; <300ms; CPU-only; no API key |
| Auth | Bearer token + hmac.compare_digest | Simple, secure, no external auth service |
| Serializer | ProtobufFrameSerializer (server↔CLI) | Pipecat's native format; required by FastAPIWebsocketTransport |
| iOS protocol | TBD Phase 2 | Protobuf vs raw PCM — decide at Phase 2 start |
| Network | Tailscale | Peer-to-peer WireGuard; no relay; works on cellular |

---

## What is NOT in scope

- Multi-user / multi-tenant — this is Alex's personal tool
- Web browser client — iOS app only
- Persistent conversation history across sessions — sessions are stateless for now
- Wake word detection — push-to-talk or VAD-triggered only
- Any always-on audio recording — no passive listening
