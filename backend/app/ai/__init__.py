"""Orquestrador de IA.

Organizacao do pacote:

- `client`   — unica porta de saida para a API do Gemini (async, timeout,
               limite de concorrencia).
- `cache`    — cache TTL com single-flight, evita chamadas repetidas.
- `prompts`  — todo o texto de instrucao em um lugar so.
- `schemas`  — formatos de saida estruturada.
- `feedback` — mediacao pos-erro (diretiva x socratica) e filtro anti-vazamento.
- `questions`— autoria de questionarios inteiros em uma chamada.
- `lessons`  — mini aulas entre questionarios.
- `search`   — tutor com Live Search (grounding do Google).
- `sse`      — formatacao dos eventos de streaming.
"""

from app.ai import cache, client, feedback, lessons, prompts, questions, schemas, search, sse
from app.ai.client import AIQuotaExceeded, AIUnavailable

__all__ = [
    "AIQuotaExceeded",
    "AIUnavailable",
    "cache",
    "client",
    "feedback",
    "lessons",
    "prompts",
    "questions",
    "schemas",
    "search",
    "sse",
]
