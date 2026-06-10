"""
Herald — main server entry point.
Runs FastAPI app with WebSocket endpoint for voice pipeline.
"""

import os
import logging
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .pipeline import HeraldPipeline
from .context_loader import ContextLoader
from .auth import verify_token

load_dotenv()

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("herald.startup", version="0.1.0")
    app.state.context_loader = ContextLoader(
        schemas_dir=os.path.join(os.path.dirname(__file__), "..", "context", "schemas")
    )
    yield
    log.info("herald.shutdown")


app = FastAPI(
    title="Herald",
    description="Bespoke voice AI orchestration platform",
    version="0.1.0",
    lifespan=lifespan,
    # Disable docs in production — no need to expose
    docs_url=None if os.getenv("HERALD_ENV") == "production" else "/docs",
    redoc_url=None,
)

# CORS: only allow local + Tailscale IPs (not wildcard)
ALLOWED_ORIGINS = os.getenv("HERALD_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.websocket("/voice")
async def voice_endpoint(
    websocket: WebSocket,
    mode: str = "freeform",
    context_file: str | None = None,
):
    """
    Main voice WebSocket endpoint.

    Client sends: OPUS audio frames (20ms chunks, 48kHz, framed as:
        | 2 bytes big-endian length | OPUS frame bytes |)
    Server sends: JSON messages:
        {"type": "transcript", "text": "...", "final": bool}
        {"type": "response_audio", "data": "<base64 OPUS>"}
        {"type": "response_text", "text": "..."}
        {"type": "error", "message": "..."}

    Auth: Bearer token in Authorization header on upgrade.
    Rate limit: 10 frames/sec per connection enforced server-side.
    """
    # Auth check — reject before accepting connection
    auth_header = websocket.headers.get("authorization", "")
    if not verify_token(auth_header):
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    log.info("herald.voice.connected", mode=mode, context_file=context_file)

    # Load context for this session
    context = None
    if context_file:
        try:
            context = app.state.context_loader.load(mode=mode, file_path=context_file)
        except Exception as e:
            await websocket.send_json({"type": "error", "message": f"Context load failed: {e}"})
            log.warning("herald.context.load_failed", error=str(e))

    pipeline = HeraldPipeline(mode=mode, context=context)

    try:
        await pipeline.run(websocket)
    except WebSocketDisconnect:
        log.info("herald.voice.disconnected")
    except Exception as e:
        log.error("herald.voice.error", error=str(e))
        try:
            await websocket.send_json({"type": "error", "message": "Pipeline error"})
        except Exception:
            pass
    finally:
        await pipeline.cleanup()
