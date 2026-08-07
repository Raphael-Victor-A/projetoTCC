"""Formatacao de Server-Sent Events.

Um unico lugar decide como um evento vira bytes na conexao, para que todos
os endpoints de streaming falem exatamente o mesmo protocolo com o front.
"""

from __future__ import annotations

import json
from typing import Any

# Cabecalhos necessarios para SSE atravessar proxies sem buffer intermediario.
SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

MEDIA_TYPE = "text/event-stream"


def event(name: str, data: Any) -> str:
    """Serializa um evento nomeado. `data` sempre trafega como JSON."""

    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {name}\ndata: {payload}\n\n"


def chunk(text: str) -> str:
    return event("chunk", {"text": text})


def error(message: str) -> str:
    return event("error", {"message": message})


def done(data: Any = None) -> str:
    return event("done", data if data is not None else {})
