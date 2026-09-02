"""
RawProvider — returns the input verbatim as "gathered raw data".

Used only when TIMPS_LLM_MODE=raw (e.g. when the host is opencode, which
cannot provide MCP sampling). In this mode the timps-swarm server does the
deterministic data-gathering (scans, run commands) but does NOT call an LLM;
it returns the raw context so the *host model* (the user's LLM) does the
analysis and report writing via a native sub-agent.

This provider deliberately has is_available()==True and sits FIRST in the
priority chain so that, when enabled, it always wins over any cloud key.
"""
from __future__ import annotations

from typing import Optional

from src.providers.base import ProviderInterface


class RawProvider(ProviderInterface):
    description = "Raw data passthrough (TIMPS_LLM_MODE=raw) — let host model analyse"
    default_model = "raw"

    def is_available(self) -> bool:
        return True

    def chat(
        self,
        user: str,
        system: str = "",
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 8192,
        format_json: bool = False,
    ) -> str:
        import json as _json
        body = user[:12000]
        if format_json:
            # JSON-returning agents do `json.loads(raw[start:end])`. Give them a
            # single object they can parse and pass through intact.
            return _json.dumps({
                "raw_data": body,
                "_mode": "raw",
                "_note": "Host sub-agent: this is the gathered data — write the analysis yourself.",
            })
        preamble = (
            "[RAW DATA — no server-side LLM. Host sub-agent: analyse the "
            "gathered data below and write the report yourself.]\n\n"
        )
        return preamble + body
