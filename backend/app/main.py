import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai import cache, client
from app.config import settings
from app.routers import admin, auth, exercises, learning, quiz, tutor
from app.seed import seed_if_empty

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_if_empty()
    if not client.is_configured():
        logger.warning(
            "GEMINI_API_KEY nao configurada: a plataforma roda com o acervo "
            "estatico e as mini aulas de reserva."
        )
    yield
    cache.invalidate()


app = FastAPI(title="Plataforma Adaptativa - TCC", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(exercises.router)
app.include_router(learning.router)
app.include_router(quiz.router)
app.include_router(tutor.router)
app.include_router(admin.router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "ai_configured": client.is_configured(),
        "ai_model": settings.gemini_model,
        # > 0 significa que a cota da API estourou e as chamadas estao
        # falhando rapido de proposito ate esse tempo passar.
        "ai_quota_blocked_for": round(client.quota_blocked_for(), 1),
        "cache": cache.stats(),
    }
