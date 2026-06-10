"""
Herald pipeline — Pipecat-based voice AI pipeline.
Handles: VAD → STT → LLM → TTS → audio output.

LLM routing: LiteLLM (Ollama local → cloud fallback with explicit consent).
STT: whisper.cpp (local) or Deepgram (cloud, requires consent).
TTS: Kokoro (local, always).
"""

import os
import structlog
from typing import Any

log = structlog.get_logger()

# Pipecat imports — installed via: pip install "pipecat-ai[silero,kokoro,ollama,whisper]"
try:
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.worker import PipelineWorker, PipelineParams
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.aggregators.llm_response_universal import (
        LLMContextAggregatorPair,
        LLMUserAggregatorParams,
    )
    from pipecat.serializers.protobuf import ProtobufFrameSerializer
    from pipecat.services.kokoro.tts import KokoroTTSService
    from pipecat.services.ollama.llm import OLLamaLLMService
    from pipecat.services.whisper import WhisperSTTService
    from pipecat.transports.websocket.fastapi import (
        FastAPIWebsocketTransport,
        FastAPIWebsocketParams,
    )
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    PIPECAT_AVAILABLE = True
except ImportError:
    PIPECAT_AVAILABLE = False
    log.warning(
        "pipeline.pipecat_not_installed",
        hint="Run: pip install 'pipecat-ai[silero,kokoro,ollama,whisper]'",
    )

# LiteLLM for cloud routing (Phase 3)
try:
    import litellm
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False


HERALD_ENV = os.getenv("HERALD_ENV", "development")
LOCAL_LLM_MODEL = os.getenv("HERALD_LOCAL_LLM_MODEL", "llama3.3")
CLOUD_LLM_MODEL = os.getenv("HERALD_CLOUD_LLM_MODEL", "claude-opus-4-7")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
WHISPER_MODEL = os.getenv("HERALD_WHISPER_MODEL", "base.en")


def _build_system_prompt(mode: str, context: dict | None) -> str:
    """Build the system prompt from mode + loaded context (Tier 1 — max 400 tokens)."""
    base = {
        "talky": (
            "You are Herald, Alex's voice briefing assistant. "
            "Deliver concise, actionable briefings. Ask clarifying questions when needed. "
            "Never fabricate data — if context is missing, say so."
        ),
        "family_interview": (
            "You are Herald, conducting a guided family interview. "
            "Ask open-ended questions. Be warm, curious, and patient. "
            "Preserve exact quotes when the subject shares something significant."
        ),
        "freeform": (
            "You are Herald, a personal AI assistant. "
            "Be direct and useful. No filler. No sycophancy."
        ),
    }.get(mode, "You are Herald, a personal AI assistant.")

    if not context:
        return base

    # Tier 1: inject condensed context (top priorities, next action, session note)
    context_block = context.get("_system_context_tier1", "")
    if context_block:
        return f"{base}\n\n<context>\n{context_block}\n</context>"

    return base


class HeraldPipeline:
    """
    Wraps Pipecat pipeline for a single WebSocket voice session.

    Phase 1: local STT + local LLM + local TTS.
    Wire protocol: ProtobufFrameSerializer (required — transport silently drops
    all frames if no serializer is set).
    Cloud fallback in Phase 3.
    """

    def __init__(self, mode: str = "freeform", context: dict | None = None):
        self.mode = mode
        self.context = context
        self.system_prompt = _build_system_prompt(mode, context)
        self._worker: Any = None

    async def run(self, websocket: Any) -> None:
        if not PIPECAT_AVAILABLE:
            await websocket.send_json({
                "type": "error",
                "message": "Pipecat not installed. Run: pip install 'pipecat-ai[silero,kokoro,ollama,whisper]'",
            })
            return

        # Serializer is mandatory — without it, _receive_messages silently drops
        # every incoming frame and _write_frame sends nothing back.
        transport = FastAPIWebsocketTransport(
            websocket=websocket,
            params=FastAPIWebsocketParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                serializer=ProtobufFrameSerializer(),
            ),
        )

        # STT: local whisper.cpp (Phase 1)
        # TODO Phase 3: add Deepgram cloud path with consent gate
        stt = WhisperSTTService(model=WHISPER_MODEL)

        # LLM: Ollama local (Phase 1)
        # TODO Phase 3: wire LiteLLM routing with cloud fallback + consent prompt
        llm = OLLamaLLMService(
            model=LOCAL_LLM_MODEL,
            base_url=OLLAMA_BASE_URL,
        )

        # TTS: Kokoro local (always local — no cloud path for TTS)
        tts = KokoroTTSService()

        llm_context = LLMContext(
            messages=[{"role": "system", "content": self.system_prompt}]
        )
        # Tier 2: full context stored, retrievable via tool call (Phase 4)
        if self.context:
            llm_context.set_tools([])  # tool registration added in Phase 4

        # VAD lives in LLMUserAggregatorParams, not as a separate pipeline stage
        user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
            llm_context,
            user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
        )

        pipeline = Pipeline([
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ])

        self._worker = PipelineWorker(pipeline, params=PipelineParams())
        runner = PipelineRunner()
        await runner.run(self._worker)

    async def cleanup(self) -> None:
        if self._worker:
            try:
                await self._worker.cancel()
            except Exception:
                pass
