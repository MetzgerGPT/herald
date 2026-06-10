# Herald — Architecture

## Overview

Herald is a bespoke voice AI orchestration platform. It runs a persistent server on a Windows PC, connects via WebSocket to a mobile client (iOS, Phase 2+), and routes audio through a local-first pipeline: faster-whisper → Ollama → Kokoro TTS.

Cloud LLM / STT paths exist but are opt-in (Phase 3), never silent fallbacks.

## System diagram

```
┌─────────────────────────────────────────────────────────────┐
│  iPhone (Herald.app — Phase 2)                              │
│                                                             │
│  AVAudioEngine → PCM frames                                 │
│  URLSession WebSocket (TLS + cert-pinned)                   │
│  Bearer auth header                                         │
└───────────────────┬─────────────────────────────────────────┘
                    │ Tailscale WireGuard mesh
                    │ ws://server.tail-xxxxx.ts.net:8765/voice
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  Windows PC (herald-server)                                 │
│                                                             │
│  FastAPI + Uvicorn                                          │
│  ├─ GET  /health                                            │
│  └─ WS   /voice?mode=<talky|family_interview|freeform>      │
│           &context_file=<path>                              │
│                                                             │
│  Auth layer (hmac.compare_digest, hard fail if no token)    │
│                                                             │
│  Pipecat pipeline (per session):                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Transport (FastAPIWebsocket)                        │   │
│  │    └→ VAD (SileroVAD)                                │   │
│  │         └→ STT (faster-whisper local)                 │   │
│  │              └→ LLM context aggregator               │   │
│  │                   └→ LLM (Ollama / LiteLLM)          │   │
│  │                        └→ TTS (Kokoro local)         │   │
│  │                             └→ Transport output      │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  Context loader (two-tier):                                 │
│  ├─ Tier 1: ~400-token condensed string → system prompt     │
│  └─ Tier 2: full JSON in memory → LLM tool-callable         │
└─────────────────────────────────────────────────────────────┘
```

## Component breakdown

### Transport layer
- **WebSocket** over Tailscale (WireGuard mesh) — peer-to-peer, no data through Tailscale relays
- **TLS cert pinning** (Phase 2) — protects against rogue nodes even inside Tailscale
- **Auth**: Bearer token verified before WebSocket upgrade, using `hmac.compare_digest` (constant-time)

### Voice pipeline (Pipecat)
| Stage | Component | Notes |
|-------|-----------|-------|
| VAD | SileroVAD | Filters silence before STT |
| STT | faster-whisper | CUDA-accelerated on NVIDIA GPU; CPU fallback if no GPU |
| LLM | Ollama (local) | Llama 3.3 default; LiteLLM routing in Phase 3 |
| TTS | Kokoro | Apache 2.0, <300ms, CPU-only |

### Context system (two-tier)
- **Tier 1**: condensed JSON → string, injected into system prompt as `<context>` block, max ~400 tokens
- **Tier 2**: full raw JSON stored in `LLMContext`; LLM retrieves via tool call (Phase 4)
- Context files loaded once per session at WebSocket connect time

### LLM routing (Phase 3)
- LiteLLM as unified routing layer
- Primary: Ollama local (always attempted first)
- Fallback: cloud LLM (Claude/GPT-4o) — requires explicit consent flag in session params, never silent
- Same applies to STT: faster-whisper local → Deepgram cloud (opt-in only)

## Phase roadmap

| Phase | Milestone | Status |
|-------|-----------|--------|
| 0 | Scaffold — server files, schemas, scripts | ✅ Done |
| 1 | Local voice loop — CLI test (no iPhone) | ✅ Done |
| 2 | iOS client — TestFlight, cert pinning | ⬜ |
| 3 | Cloud fallback — LiteLLM routing + consent gate | ⬜ |
| 4 | Tier 2 context — tool-callable full JSON retrieval | ⬜ |
| 5 | Multi-mode sessions — TALKY + Family Interview + Freeform | ⬜ |

## Network model

```
Windows PC (herald-server)
    Tailscale IP: 100.x.x.x (or hostname: desktop.tail-xxxxx.ts.net)
    Port: 8765 (not exposed to internet — Tailscale only)

iPhone (herald-client)
    Connects via Tailscale — works on cellular, home WiFi, external WiFi
    TLS cert pinned to server cert (Phase 2)
```

No port forwarding, no ngrok, no Cloudflare tunnel needed. Tailscale handles NAT traversal.

## Latency targets

| Mode | Target | Notes |
|------|--------|-------|
| Local only | 1.5–2.5s | VAD → faster-whisper → Ollama → Kokoro |
| Hybrid (local STT + cloud LLM) | 1.0–1.5s | Faster LLM inference |
| Full cloud | 700–900ms | Deepgram + Claude/GPT-4o |
