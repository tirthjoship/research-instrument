"""Local Ollama narrator adapter (NarratorPort). On ANY error (Ollama not running,
timeout, bad response) it falls back to the deterministic template — never raises,
never blocks the scheduled run. Zero API cost, on-device: holdings context never
leaves the machine. Narrates an already-computed verdict; cannot influence it."""

from __future__ import annotations

import json
import urllib.request

from application.narrator import template_narration

_SYSTEM = (
    "You explain a stock position's ALREADY-DECIDED risk verdict in 2-3 plain sentences. "
    "You do NOT predict prices or pick stocks. Use only the numbers given."
)


class OllamaNarratorAdapter:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "llama3.1:8b",
        timeout: float = 20.0,
    ) -> None:
        self._url = base_url.rstrip("/") + "/api/generate"
        self._model = model
        self._timeout = timeout

    def _call(self, prompt: str) -> str:
        body = json.dumps(
            {"model": self._model, "prompt": prompt, "system": _SYSTEM, "stream": False}
        ).encode()
        req = urllib.request.Request(
            self._url, data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            data = json.loads(resp.read().decode())
        return str(data.get("response", "")).strip()

    def narrate(self, context: dict[str, object]) -> str:
        fallback = template_narration(context)
        try:
            prompt = (
                f"Position context (JSON): {json.dumps(context)}\nExplain the verdict."
            )
            text = self._call(prompt)
            return text or fallback
        except Exception:
            from loguru import logger

            logger.warning("Ollama narrator unavailable; using template fallback")
            return fallback
