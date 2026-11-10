"""Dicas durante a questao (botao "Preciso de ajuda").

    GET  /questions/{id}/hints -> dicas que o aluno ja recebeu nesta questao
    POST /questions/{id}/hint  -> pede a proxima dica (no maximo MAX_HINTS)

Economia de API: a dica nao depende do aluno (nao usa a alternativa que ele
marcou), so da questao e da ordem da dica. Entao, se outro aluno ja recebeu
uma dica valida de mesma ordem para a mesma questao, ela e reaproveitada sem
nova chamada ao Gemini.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai import hints as ai_hints
from app.database import get_db
from app.models import HintRequest, Question, Quiz, User
from app.rate_limit import enforce_gemini_rate_limit
from app.schemas import HintIn, HintOut, HintsOut
from app.security import get_current_user

router = APIRouter(tags=["hints"])
logger = logging.getLogger(__name__)


def _get_question(db: Session, question_id: int) -> Question:
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Questao nao encontrada")
    if question.is_diagnostic:
        # O diagnostico mede o que o aluno ja sabe; dica distorceria o nivelamento.
        raise HTTPException(
            status_code=400, detail="Dicas nao estao disponiveis no teste de nivelamento"
        )
    return question


def _user_hints(db: Session, user: User, question: Question) -> list[HintRequest]:
    return (
        db.query(HintRequest)
        .filter(HintRequest.user_id == user.id, HintRequest.question_id == question.id)
        .order_by(HintRequest.hint_number)
        .all()
    )


def _out(rows: list[HintRequest], extra: HintOut | None = None, degraded: bool = False) -> HintsOut:
    hints = [HintOut(number=r.hint_number, content=r.content) for r in rows]
    if extra is not None:
        hints.append(extra)
    used = len(rows)
    return HintsOut(
        hints=hints,
        max_hints=ai_hints.MAX_HINTS,
        remaining=max(0, ai_hints.MAX_HINTS - used),
        degraded=degraded,
    )


def _shared_hint(db: Session, question: Question, hint_number: int) -> HintRequest | None:
    """Dica valida da mesma ordem, ja gerada para outro aluno."""

    return (
        db.query(HintRequest)
        .filter(
            HintRequest.question_id == question.id,
            HintRequest.hint_number == hint_number,
            HintRequest.fallback_used.is_(False),
            HintRequest.leak_detected.is_(False),
        )
        .order_by(HintRequest.id)
        .first()
    )


@router.get("/questions/{question_id}/hints", response_model=HintsOut)
def list_hints(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    question = _get_question(db, question_id)
    return _out(_user_hints(db, current_user, question))


@router.post("/questions/{question_id}/hint", response_model=HintsOut)
async def request_hint(
    question_id: int,
    payload: HintIn | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.diagnostic_completed:
        raise HTTPException(status_code=400, detail="Complete o diagnostico inicial primeiro")

    question = _get_question(db, question_id)
    rows = _user_hints(db, current_user, question)
    if len(rows) >= ai_hints.MAX_HINTS:
        # Ja usou todas: devolve as que tem, sem erro (a tela so mostra).
        return _out(rows)

    quiz_id = payload.quiz_id if payload else None
    if quiz_id is not None:
        quiz = db.get(Quiz, quiz_id)
        if quiz is None or quiz.user_id != current_user.id:
            quiz_id = None

    hint_number = len(rows) + 1
    shared = _shared_hint(db, question, hint_number)

    if shared is not None:
        content, latency, leak, fallback, reused = shared.content, 0.0, False, False, True
    else:
        enforce_gemini_rate_limit(current_user.id)
        result = await ai_hints.generate_hint(question, hint_number, [r.content for r in rows])
        if result.degraded:
            # IA fora do ar: mostra a dica de reserva, mas nao gasta uma das
            # dicas do aluno.
            return _out(rows, HintOut(number=hint_number, content=result.content), degraded=True)
        content, latency = result.content, result.latency_ms
        leak, fallback, reused = result.leak_detected, result.fallback_used, False

    row = HintRequest(
        user_id=current_user.id,
        question_id=question.id,
        quiz_id=quiz_id,
        hint_number=hint_number,
        content=content,
        mode=current_user.group,
        gemini_latency_ms=latency,
        leak_detected=leak,
        fallback_used=fallback,
        reused=reused,
    )
    db.add(row)
    db.commit()
    return _out(rows + [row])
