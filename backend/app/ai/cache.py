"""Cache TTL em memoria para conteudo gerado por IA.

Motivacao: mini aula de "Funcao afim / basico" e um lote de questoes de
reforco do mesmo modulo sao identicos para qualquer aluno na mesma situacao.
Guardar o resultado por alguns minutos elimina a maior parte das chamadas
repetidas — que sao justamente as mais caras em latencia percebida.

Tambem serve de "single flight": duas requisicoes simultaneas para a mesma
chave compartilham uma unica chamada a API em vez de disparar duas.

Processo unico e suficiente para o escopo do TCC; com varias instancias,
trocar por Redis mantendo esta mesma interface.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, TypeVar

from app.config import settings

T = TypeVar("T")

_store: dict[str, tuple[float, Any]] = {}
_inflight: dict[str, asyncio.Future] = {}


def _now() -> float:
    return time.monotonic()


def _evict_if_needed() -> None:
    if len(_store) <= settings.ai_cache_max_entries:
        return
    # Descarta primeiro o que ja expirou; se ainda estiver cheio, o mais antigo.
    now = _now()
    for key in [k for k, (exp, _) in _store.items() if exp <= now]:
        _store.pop(key, None)
    while len(_store) > settings.ai_cache_max_entries:
        oldest = min(_store, key=lambda k: _store[k][0])
        _store.pop(oldest, None)


def get(key: str) -> Any | None:
    entry = _store.get(key)
    if entry is None:
        return None
    expires_at, value = entry
    if expires_at <= _now():
        _store.pop(key, None)
        return None
    return value


def set(key: str, value: Any, ttl_seconds: int | None = None) -> None:
    ttl = settings.ai_cache_ttl_seconds if ttl_seconds is None else ttl_seconds
    _store[key] = (_now() + ttl, value)
    _evict_if_needed()


def invalidate(prefix: str = "") -> None:
    for key in [k for k in _store if k.startswith(prefix)]:
        _store.pop(key, None)


async def get_or_create(
    key: str,
    factory: Callable[[], Awaitable[T]],
    ttl_seconds: int | None = None,
) -> T:
    """Devolve o valor em cache ou executa `factory` uma unica vez.

    Chamadas concorrentes com a mesma chave aguardam o mesmo resultado em vez
    de disparar chamadas duplicadas a API.
    """

    cached = get(key)
    if cached is not None:
        return cached

    inflight = _inflight.get(key)
    if inflight is not None:
        return await asyncio.shield(inflight)

    loop = asyncio.get_running_loop()
    future: asyncio.Future = loop.create_future()
    _inflight[key] = future
    try:
        value = await factory()
    except BaseException as exc:
        if not future.done():
            future.set_exception(exc)
        # Evita "exception never retrieved" quando ninguem mais esperava.
        future.exception()
        raise
    else:
        set(key, value, ttl_seconds)
        if not future.done():
            future.set_result(value)
        return value
    finally:
        _inflight.pop(key, None)


def stats() -> dict[str, int]:
    now = _now()
    return {
        "entries": len(_store),
        "expired": sum(1 for exp, _ in _store.values() if exp <= now),
        "inflight": len(_inflight),
    }
