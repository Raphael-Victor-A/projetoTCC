import time
from collections import defaultdict, deque

from fastapi import HTTPException, status

from app.config import settings

# Rate limit simples em memoria (por processo). Suficiente para o escopo do
# TCC / protege custo de API; em producao com multiplas instancias trocar
# por um contador compartilhado (ex: Redis).
_calls_by_user: dict[int, deque] = defaultdict(deque)


def enforce_gemini_rate_limit(user_id: int) -> None:
    now = time.monotonic()
    window_start = now - 60
    calls = _calls_by_user[user_id]

    while calls and calls[0] < window_start:
        calls.popleft()

    if len(calls) >= settings.gemini_rate_limit_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Limite de chamadas de IA por minuto atingido. Tente novamente em instantes.",
        )

    calls.append(now)
