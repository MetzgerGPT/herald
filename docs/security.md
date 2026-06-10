# Herald — Security Model

## Threat model

Herald processes personal audio and context data (TALKY sessions, family interview profiles) and routes it to local or cloud LLMs. The attack surface includes:

1. Unauthorized server access (unauthenticated WebSocket connections)
2. Prompt injection via transcribed audio
3. Credential leakage (API keys, auth tokens in logs or storage)
4. Silent cloud data exfiltration (cloud fallback without consent)
5. MITM on the WebSocket transport
6. Unencrypted audio persisted on device

## Controls

### 1. Authentication
- Bearer token required before WebSocket upgrade is accepted
- Token read from `HERALD_AUTH_TOKEN` env var (never hardcoded)
- Comparison via `hmac.compare_digest` — constant-time, prevents timing oracle attacks
- Hard fail if `HERALD_AUTH_TOKEN` is not configured — server rejects all connections rather than running open
- Token generation: `openssl rand -hex 32` (32 bytes = 256-bit entropy)

### 2. Prompt injection defense
- All transcribed audio content is placed in `<user>` tags in the LLM context
- System prompt is constructed server-side from validated context files — never from user audio
- Context files are loaded from trusted local paths (no URL-based loading)
- LLM is instructed not to follow instructions in `<user>` content that contradict the system prompt
- Pipecat's `OpenAILLMContext` enforces role separation (system vs. user messages)

### 3. Credential security
- `.env` is in `.gitignore` — never committed
- No API keys or tokens in any `.md`, `.txt`, or `.json` file
- Log redaction: structlog used throughout; auth headers and API keys must not appear in log output
- Cloud API keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) are optional and only loaded when cloud fallback is enabled

### 4. No silent cloud fallback
- Cloud LLM and cloud STT paths are **opt-in only**, controlled by explicit session parameters
- No automatic fallback to cloud if local LLM fails — the pipeline errors rather than silently sending audio to a cloud provider
- Phase 3 will add a consent gate that requires an explicit `allow_cloud=true` session flag

### 5. Transport security
- Server runs behind Tailscale (WireGuard mesh) — not exposed to the public internet
- Tailscale traffic is peer-to-peer encrypted; does not transit Tailscale servers for direct connections
- Phase 2: TLS cert pinning on iOS client — protects against compromise of Tailscale PKI
- CORS policy: explicit allowlist from env (`HERALD_CORS_ORIGINS`), never `*` in production

### 6. Audio data handling
- Audio is processed in-memory through the Pipecat pipeline — not written to disk on the server
- Phase 2 (iOS): raw PCM frames piped directly to WebSocket, not buffered to device storage
- No audio cache, no conversation history written to the filesystem between sessions
- Session state is in-process only — restarting the server clears all session data

## Known limitations (Phase 0)

| Limitation | Phase |
|------------|-------|
| No TLS cert pinning (iOS) | Phase 2 |
| No session isolation (concurrent sessions share process) | Phase 3 |
| No rate limiting on `/voice` endpoint | Phase 3 |
| Cloud fallback not yet gated (LiteLLM routing not wired) | Phase 3 |
| Tier 2 context tool not yet scoped — LLM could theoretically retrieve full raw context | Phase 4 |

## Security checklist (Phase 0 complete)

- [x] Bearer token auth with constant-time comparison
- [x] Hard fail if no token configured
- [x] `.env` in `.gitignore`
- [x] No credentials in committed files
- [x] CORS allowlist (not wildcard)
- [x] Transcribed audio in user role only (system prompt is server-controlled)
- [x] structlog for structured logs (no accidental credential interpolation)
- [x] Audio not written to disk (in-process pipeline)
- [x] No silent cloud fallback (explicit opt-in path)
- [ ] TLS cert pinning (Phase 2)
- [ ] Rate limiting (Phase 3)
- [ ] Session isolation (Phase 3)
