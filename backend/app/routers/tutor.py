"""Tutor de IA: resposta em streaming com Live Search."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import study_plan
from app.ai import sse
from app.ai.search import stream_tutor_answer
from app.database import get_db
from app.models import Module, Subject, User
from app.rate_limit import enforce_gemini_rate_limit
from app.schemas import TutorAskIn
from app.security import get_current_user

router = APIRouter(prefix="/tutor", tags=["tutor"])
logger = logging.getLogger(__name__)


@router.post("/ask")
async def ask_tutor(
    payload: TutorAskIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Responde a duvida do aluno em streaming (SSE).

    A resposta combina tres fontes: o contexto de estudo do proprio aluno
    (disciplina, modulo e erros recentes), o conhecimento do modelo e — quando
    a pergunta depende de informacao atual — a busca ao vivo, cujas fontes
    voltam no evento `sources`.
    """

    enforce_gemini_rate_limit(current_user.id)

    module = db.get(Module, payload.module_id) if payload.module_id else None
    if payload.module_id is not None and module is None:
        raise HTTPException(status_code=404, detail="Modulo nao encontrado")

    if module is None:
        current = study_plan.current_progress(db, current_user)
        module = db.get(Module, current.module_id) if current else None

    subject: Subject | None = db.get(Subject, module.subject_id) if module else None
    recent_errors = study_plan.weak_topics(db, current_user, limit=6)

    question = payload.question
    subject_name = subject.name if subject else None
    module_title = module.title if module else None
    level = current_user.level.value
    use_search = payload.use_search

    async def generate():
        try:
            async for kind, data in stream_tutor_answer(
                question=question,
                subject=subject_name,
                module=module_title,
                level=level,
                recent_errors=recent_errors,
                use_search=use_search,
            ):
                if kind == "chunk":
                    yield sse.chunk(str(data))
                elif kind == "meta":
                    yield sse.event("meta", data)
                elif kind == "sources":
                    yield sse.event("sources", {"sources": data})
                elif kind == "error":
                    yield sse.error(str(data))
        except Exception:
            logger.exception("Falha no tutor")
            yield sse.error("Nao foi possivel responder agora.")
        yield sse.done({})

    return StreamingResponse(generate(), media_type=sse.MEDIA_TYPE, headers=sse.SSE_HEADERS)
