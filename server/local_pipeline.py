"""
Herald local pipeline — Phase 1 test harness.

Runs a full voice loop directly on the Mac using system audio (mic + speaker).
No WebSocket, no server, no serializer needed.
Flow: mic → SileroVAD → whisper.cpp STT → Ollama LLM → Kokoro TTS → speaker

Prerequisites:
  - bash scripts/setup.sh (installs whisper.cpp, Ollama, PyAudio)
  - Ollama running: ollama serve
  - .env populated with HERALD_AUTH_TOKEN (not required for local, but loaded anyway)

Run:
  python -m server.local_pipeline
  python -m server.local_pipeline --mode talky --context ~/talky/output/session.json
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

import structlog
from dotenv import load_dotenv

load_dotenv()

log = structlog.get_logger()

try:
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.worker import PipelineWorker, PipelineParams
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.aggregators.llm_response_universal import (
        LLMContextAggregatorPair,
        LLMUserAggregatorParams,
    )
    from pipecat.services.kokoro.tts import KokoroTTSService
    from pipecat.services.ollama.llm import OLLamaLLMService
    from pipecat.services.whisper import WhisperSTTService
    from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams
    PIPECAT_AVAILABLE = True
except ImportError as e:
    PIPECAT_AVAILABLE = False
    log.error("local_pipeline.import_failed", error=str(e),
              hint="Run: pip install 'pipecat-ai[silero,kokoro,ollama,whisper,local]'")

LOCAL_LLM_MODEL = os.getenv("HERALD_LOCAL_LLM_MODEL", "llama3.3")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
WHISPER_MODEL = os.getenv("HERALD_WHISPER_MODEL", "base.en")


def _system_prompt(mode: str, context_data: dict | None) -> str:
    base = {
        "talky": (
            "You are Herald, Alex's voice briefing assistant. "
            "Deliver concise, actionable briefings. Keep responses brief for voice — two sentences max. "
            "Never fabricate data."
        ),
        "family_interview": (
            "You are Herald, conducting a guided family interview. "
            "Ask open-ended questions. Be warm, curious, and patient."
        ),
        "freeform": (
            "You are Herald, a personal AI assistant. "
            "Be direct and useful. Keep responses brief for voice."
        ),
    }.get(mode, "You are Herald, a personal AI assistant.")

    if context_data:
        tier1 = context_data.get("_system_context_tier1", "")
        if tier1:
            return f"{base}\n\n<context>\n{tier1}\n</context>"
    return base


async def run(mode: str = "freeform", context_file: str | None = None) -> None:
    if not PIPECAT_AVAILABLE:
        print("ERROR: Pipecat not installed. Run: pip install 'pipecat-ai[silero,kokoro,ollama,whisper,local]'")
        sys.exit(1)

    context_data = None
    if context_file:
        from server.context_loader import ContextLoader
        loader = ContextLoader(
            schemas_dir=str(Path(__file__).parent.parent / "context" / "schemas")
        )
        try:
            context_data = loader.load(mode=mode, file_path=context_file)
            log.info("local_pipeline.context_loaded", file=context_file)
        except Exception as e:
            log.warning("local_pipeline.context_load_failed", error=str(e))

    transport = LocalAudioTransport(
        params=LocalAudioTransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
        )
    )

    stt = WhisperSTTService(model=WHISPER_MODEL)

    llm = OLLamaLLMService(
        model=LOCAL_LLM_MODEL,
        base_url=OLLAMA_BASE_URL,
    )

    tts = KokoroTTSService()

    llm_context = LLMContext(
        messages=[{"role": "system", "content": _system_prompt(mode, context_data)}]
    )

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

    worker = PipelineWorker(pipeline, params=PipelineParams())
    runner = PipelineRunner()

    print(f"\n=== Herald local voice loop ===")
    print(f"Mode:    {mode}")
    print(f"LLM:     {LOCAL_LLM_MODEL} via Ollama ({OLLAMA_BASE_URL})")
    print(f"STT:     whisper.cpp [{WHISPER_MODEL}]")
    print(f"TTS:     Kokoro (local)")
    if context_file:
        print(f"Context: {context_file}")
    print("\nSpeak into your microphone. Press Ctrl+C to stop.\n")

    await runner.run(worker)


def main() -> None:
    parser = argparse.ArgumentParser(description="Herald local voice pipeline (Phase 1)")
    parser.add_argument("--mode", default="freeform",
                        choices=["freeform", "talky", "family_interview"],
                        help="Session mode")
    parser.add_argument("--context", default=None,
                        help="Path to context JSON file (TALKY output or interview profile)")
    args = parser.parse_args()
    asyncio.run(run(mode=args.mode, context_file=args.context))


if __name__ == "__main__":
    main()
