"""Acesso ao Gemini: um unico ponto de entrada assincrono.

Tudo que fala com a API passa por aqui, o que concentra em um lugar so:
timeout, limite de concorrencia do processo, medicao de latencia e log de
erro. Os modulos de dominio (`questions`, `lessons`, `feedback`, `search`)
cuidam apenas de prompt e validacao da resposta.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import AsyncIterator, Type, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_client: genai.Client | None = None
_semaphore: asyncio.Semaphore | None = None


class AIUnavailable(RuntimeError):
    """Falha ao obter conteudo do Gemini (chave ausente, timeout, erro de
    rede, schema invalido). Quem chama deve degradar para o acervo estatico."""


class AIQuotaExceeded(AIUnavailable):
    """Cota da API estourada (HTTP 429).

    Merece um tipo proprio porque a acao correta e diferente das demais
    falhas: nao adianta tentar de novo agora, e a mensagem para o aluno
    precisa dizer o que realmente aconteceu em vez de um erro generico.
    """


# Enquanto a cota estiver estourada, novas chamadas falham na hora em vez de
# gastar rede e segundos para receber outro 429. O instante e reaproveitado do
# retryDelay que a propria API devolve.
_quota_blocked_until: float = 0.0


def quota_blocked_for() -> float:
    """Segundos restantes de bloqueio por cota (0 = liberado)."""

    return max(0.0, _quota_blocked_until - time.monotonic())


def _translate_error(exc: Exception, context: str) -> AIUnavailable:
    """Converte a excecao crua do SDK no erro de dominio correspondente."""

    global _quota_blocked_until
    message = str(exc)
    if "429" in message or "RESOURCE_EXHAUSTED" in message:
        match = re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s", message)
        delay = float(match.group(1)) if match else 60.0
        _quota_blocked_until = time.monotonic() + delay
        logger.warning(
            "Cota da API do Gemini estourada (%s). Novas chamadas bloqueadas por %.0fs. "
            "Troque GEMINI_MODEL por um modelo com cota disponivel ou habilite faturamento.",
            context,
            delay,
        )
        return AIQuotaExceeded(
            f"cota da API do Gemini esgotada; tente novamente em {delay:.0f}s"
        )
    logger.warning("Falha na chamada ao Gemini (%s): %s", context, message[:300])
    return AIUnavailable(f"falha na chamada ao Gemini: {message}")


def _check_quota_block() -> None:
    remaining = quota_blocked_for()
    if remaining > 0:
        raise AIQuotaExceeded(
            f"cota da API do Gemini esgotada; tente novamente em {remaining:.0f}s"
        )


def get_client() -> genai.Client:
    global _client
    if _client is None:
        if not settings.gemini_api_key:
            raise AIUnavailable("GEMINI_API_KEY nao configurada (.env)")
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def is_configured() -> bool:
    return bool(settings.gemini_api_key)


def _get_semaphore() -> asyncio.Semaphore:
    # Criado sob demanda: precisa nascer dentro do event loop em execucao.
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.gemini_max_concurrency)
    return _semaphore


def build_config(
    *,
    system_instruction: str,
    temperature: float | None = None,
    response_schema: Type[BaseModel] | None = None,
    tools: list[types.Tool] | None = None,
    max_output_tokens: int | None = None,
) -> types.GenerateContentConfig:
    kwargs: dict = {
        "system_instruction": system_instruction,
        "temperature": settings.gemini_temperature if temperature is None else temperature,
    }
    if response_schema is not None:
        kwargs["response_mime_type"] = "application/json"
        kwargs["response_schema"] = response_schema
    if tools:
        kwargs["tools"] = tools
    if max_output_tokens:
        kwargs["max_output_tokens"] = max_output_tokens
    return types.GenerateContentConfig(**kwargs)


async def generate_structured(
    *,
    contents: str,
    system_instruction: str,
    response_schema: Type[T],
    temperature: float | None = None,
    timeout: float | None = None,
) -> tuple[T, float]:
    """Chamada com saida estruturada (JSON validado contra `response_schema`).

    Retorna (objeto, latencia_ms). Levanta AIUnavailable em qualquer falha.
    """

    _check_quota_block()
    client = get_client()
    config = build_config(
        system_instruction=system_instruction,
        temperature=temperature,
        response_schema=response_schema,
    )
    start = time.perf_counter()
    try:
        async with _get_semaphore():
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=settings.gemini_model,
                    contents=contents,
                    config=config,
                ),
                timeout=timeout or settings.gemini_timeout_seconds,
            )
    except asyncio.TimeoutError as exc:
        logger.warning("Timeout (%.0fs) na chamada ao Gemini", timeout or settings.gemini_timeout_seconds)
        raise AIUnavailable("timeout na chamada ao Gemini") from exc
    except AIUnavailable:
        raise
    except Exception as exc:  # erro de rede, quota, chave invalida...
        raise _translate_error(exc, "generate_content") from exc

    latency_ms = (time.perf_counter() - start) * 1000
    parsed = response.parsed
    if parsed is None:
        raise AIUnavailable("Gemini devolveu resposta fora do schema esperado")
    return parsed, latency_ms


async def stream_raw(
    *,
    contents: str,
    system_instruction: str,
    temperature: float | None = None,
    tools: list[types.Tool] | None = None,
    timeout: float | None = None,
) -> AsyncIterator[object]:
    """Streaming cru: entrega o objeto de resposta de cada pedaco.

    Necessario quando o chamador precisa de mais do que texto — no Live
    Search, por exemplo, as fontes vem no grounding_metadata do chunk.
    """

    client = get_client()
    config = build_config(
        system_instruction=system_instruction,
        temperature=temperature,
        tools=tools,
    )
    _check_quota_block()
    async with _get_semaphore():
        try:
            stream = await asyncio.wait_for(
                client.aio.models.generate_content_stream(
                    model=settings.gemini_model,
                    contents=contents,
                    config=config,
                ),
                timeout=timeout or settings.gemini_timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            logger.warning("Timeout ao abrir o streaming do Gemini")
            raise AIUnavailable("timeout ao abrir o streaming do Gemini") from exc
        except Exception as exc:
            raise _translate_error(exc, "generate_content_stream") from exc

        try:
            async for chunk in stream:
                yield chunk
        except Exception as exc:
            raise _translate_error(exc, "streaming") from exc


async def stream_text(
    *,
    contents: str,
    system_instruction: str,
    temperature: float | None = None,
    tools: list[types.Tool] | None = None,
    timeout: float | None = None,
) -> AsyncIterator[str]:
    """Gera texto em streaming, pedaco a pedaco.

    Cada `yield` e um trecho novo do texto (nao acumulado), pronto para ser
    empurrado para a tela do aluno.
    """

    async for chunk in stream_raw(
        contents=contents,
        system_instruction=system_instruction,
        temperature=temperature,
        tools=tools,
        timeout=timeout,
    ):
        text = getattr(chunk, "text", None)
        if text:
            yield text


def grounding_sources(response) -> list[dict[str, str]]:
    """Extrai as fontes usadas pelo grounding (Live Search) de uma resposta.

    A estrutura do metadata varia entre versoes do SDK, entao cada acesso e
    defensivo: sem fontes reconheciveis, devolve lista vazia.
    """

    sources: list[dict[str, str]] = []
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        metadata = getattr(candidate, "grounding_metadata", None)
        if metadata is None:
            continue
        for chunk in getattr(metadata, "grounding_chunks", None) or []:
            web = getattr(chunk, "web", None)
            if web is None:
                continue
            uri = getattr(web, "uri", None)
            if not uri:
                continue
            sources.append({"title": getattr(web, "title", None) or uri, "uri": uri})
    # Deduplica preservando ordem de relevancia devolvida pela API.
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for source in sources:
        if source["uri"] in seen:
            continue
        seen.add(source["uri"])
        unique.append(source)
    return unique
