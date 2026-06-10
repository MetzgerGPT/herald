"""
Herald context loader — ingests JSON context files (TALKY, family interview, etc.)
and prepares a two-tier context object for the pipeline.

Tier 1 (system prompt pre-load): max 400 tokens — name, top priorities, next action.
Tier 2 (tool-callable): full JSON stored in memory, retrieved on demand by the LLM.
"""

import json
import os
import structlog
from pathlib import Path
from typing import Any

log = structlog.get_logger()

# Tier 1 token budget (approximate: 1 token ≈ 4 chars)
TIER1_CHAR_BUDGET = 1600


def _build_talky_tier1(data: dict) -> str:
    """Condense a TALKY session JSON to a Tier 1 system context string."""
    lines = []

    if name := data.get("user", {}).get("name"):
        lines.append(f"User: {name}")

    if priorities := data.get("priorities", []):
        top = priorities[:3]
        lines.append("Top priorities:")
        for p in top:
            status = p.get("status", "")
            lines.append(f"  - {p.get('title', '')} [{status}]")

    if next_action := data.get("next_action"):
        lines.append(f"Next action: {next_action.get('title', '')} — due {next_action.get('due', 'TBD')}")

    if session_note := data.get("session_note"):
        lines.append(f"Session note: {session_note}")

    result = "\n".join(lines)
    if len(result) > TIER1_CHAR_BUDGET:
        result = result[:TIER1_CHAR_BUDGET] + "..."
    return result


def _build_family_interview_tier1(data: dict) -> str:
    """Condense a family interview profile JSON to a Tier 1 system context string."""
    lines = []

    if subject := data.get("subject"):
        lines.append(f"Interview subject: {subject.get('name', 'Unknown')}, {subject.get('relationship', '')}")
        if born := subject.get("born"):
            lines.append(f"Born: {born}")

    if focus_areas := data.get("focus_areas", []):
        lines.append("Focus areas:")
        for f in focus_areas[:4]:
            lines.append(f"  - {f}")

    if opening_question := data.get("opening_question"):
        lines.append(f"Suggested opener: {opening_question}")

    result = "\n".join(lines)
    if len(result) > TIER1_CHAR_BUDGET:
        result = result[:TIER1_CHAR_BUDGET] + "..."
    return result


_TIER1_BUILDERS = {
    "talky": _build_talky_tier1,
    "family_interview": _build_family_interview_tier1,
}


class ContextLoader:
    def __init__(self, schemas_dir: str):
        self.schemas_dir = Path(schemas_dir)

    def load(self, mode: str, file_path: str) -> dict[str, Any]:
        """
        Load a JSON context file, validate it against the mode schema,
        and return a dict with:
          - "_raw": full parsed JSON (Tier 2 — tool-callable)
          - "_system_context_tier1": condensed string for system prompt (Tier 1)
          - "_mode": the mode string
          - "_source_file": path to loaded file
        """
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Context file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        log.info("context.loaded", mode=mode, file=str(path), keys=list(data.keys()))

        tier1_builder = _TIER1_BUILDERS.get(mode)
        tier1 = tier1_builder(data) if tier1_builder else json.dumps(data, indent=2)[:TIER1_CHAR_BUDGET]

        return {
            "_raw": data,
            "_system_context_tier1": tier1,
            "_mode": mode,
            "_source_file": str(path),
        }

    def load_latest_talky(self, talky_output_dir: str) -> dict[str, Any] | None:
        """
        Convenience: auto-load the most recent TALKY .json from its output directory.
        Watches for the newest file by mtime.
        """
        output_dir = Path(talky_output_dir).expanduser().resolve()
        if not output_dir.exists():
            log.warning("context.talky_dir_not_found", dir=str(output_dir))
            return None

        json_files = sorted(output_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not json_files:
            log.warning("context.no_talky_files", dir=str(output_dir))
            return None

        latest = json_files[0]
        log.info("context.talky_auto_load", file=str(latest))
        return self.load(mode="talky", file_path=str(latest))
