# Herald iOS App

**Status: Phase 1 placeholder** — iOS client is Phase 2 / Phase 3 work.

Phase 1 uses a CLI test harness to validate the server pipeline. The iOS app scaffolds here once the server is stable.

## Planned stack

- Swift + SwiftUI
- `AVAudioEngine` for low-latency audio capture (not AVAudioRecorder — need raw PCM)
- URLSessionWebSocketTask for WebSocket transport (cert-pinned)
- No audio buffered to disk — PCM frames piped directly to WebSocket
- TestFlight distribution (not App Store for personal use)

## Connection model

```
iPhone (Herald.app)
    │
    │  WebSocket / TLS
    │  Auth: Bearer token in header
    ▼
Mac mini (herald-server, Tailscale IP)
```

- Tailscale handles peer-to-peer encryption — no traffic through Tailscale servers
- TLS cert pinned to server's cert (protects against rogue Tailscale nodes)
- No mDNS/Bonjour — use fixed Tailscale IP or hostname (`server.tail-xxxxx.ts.net`)

## Phase 2 checklist

- [ ] Xcode project init (SwiftUI, iOS 17+)
- [ ] AVAudioEngine capture → PCM frames
- [ ] WebSocket client with auth header
- [ ] Reconnect / keep-alive logic
- [ ] Playback: streaming PCM from server → AVAudioPlayerNode
- [ ] UI: push-to-talk / VAD mode toggle, session mode picker, context file picker
- [ ] TLS cert pinning
- [ ] TestFlight build + distribute
