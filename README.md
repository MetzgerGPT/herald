# HERALD
**Bespoke voice AI orchestration platform**
*Owner: Alex Metzger | Built with Claude Code*

Herald is a self-hosted conversational voice AI system designed for personal use across multiple projects. It runs on a local Mac (always-on server) with an iPhone client, supports both local and cloud LLMs, and ingests structured JSON context files (TALKY output, Family Interview profiles, etc.).

---

## What it does

- Two-way voice conversation with an AI agent
- Context-aware: loads TALKY session JSON, interview subject profiles, or freeform briefs at session start
- Multi-LLM routing: Ollama (local, private) → Claude/GPT-4o (cloud, with explicit consent)
- All audio stays local by default — no data leaves your Mac without user approval
- iPhone app connects over Tailscale (WireGuard VPN) for secure remote access

## Projects it powers

| Project | Mode | Context Source |
|---------|------|---------------|
| TALKY | `talky` | TALKY session .json |
| Family Interview Series | `family_interview` | Subject profile .json |
| Freeform | `freeform` | Manual system prompt |

---

## Architecture

```
iPhone (iOS native app)
    │  Tailscale WireGuard + TLS cert pinning
    ▼
Mac Server (always-on)
    ├── Pipecat v1.1 — pipeline orchestrator
    ├── whisper.cpp — local STT (Metal/Apple Silicon)
    ├── Kokoro TTS — local voice synthesis
    ├── LiteLLM — LLM routing layer
    │       ├── Ollama (local: Llama 3.3, Qwen, Mistral)
    │       └── Cloud fallback (Claude, GPT-4o)
    └── Context Loader — JSON ingestion (TALKY + Interview schemas)
```

**Latency targets:**
- Local path (Whisper + Ollama + Kokoro): ~1.5–2.5s
- Hybrid (Deepgram + Ollama + Kokoro): ~1.0–1.5s
- Full cloud fallback: ~700–900ms

---

## Phases

- [x] Phase 0: Repo scaffold
- [ ] Phase 1: Local voice loop (Mac only, CLI test)
- [ ] Phase 2: iPhone client (TestFlight)
- [ ] Phase 3: Multi-LLM routing + security hardening
- [ ] Phase 4: Project integrations (TALKY, Family Interview)

---

## Setup

See [docs/setup.md](docs/setup.md) for full installation instructions.

Quick start (Mac, Apple Silicon):
```bash
bash scripts/setup.sh
bash scripts/dev.sh
```

---

## Security model

Herald is built security-first. See [docs/security.md](docs/security.md) for the full threat model. Key controls:

- Tailscale WireGuard for all remote transport
- TLS cert pinning in iOS app
- No audio cached on device
- No silent cloud fallback — explicit user consent required
- Prompt injection defense (transcribed audio in `<user>` tags only)

---

## Status

Active development. Not production-ready. Personal use only.
