"""Questionarios completos (reforco e pratica).

Contrato do fluxo, do ponto de vista do cliente:

    POST /quiz/start    -> devolve o questionario INTEIRO (1 chamada de IA)
    POST /quiz/{id}/answer -> corrige uma questao (0 chamadas de IA)
    POST /quiz/{id}/finish -> fecha o questionario e diz qual e a proxima etapa

Nenhuma questao e gerada no meio do caminho.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import quiz_service, study_plan
from app.database import get_db
from app.models import Attempt, Module, Question, Quiz, QuizKind, User
from app.rate_limit import enforce_gemini_rate_limit
from app.routers.learning import next_step_payload
from app.schemas import (
    AnswerIn,
    QuizAnswerOut,
    QuizOut,
    QuizResultOut,
    QuizStartIn,
)
from app.security import get_current_user

router = APIRouter(prefix="/quiz", tags=["quiz"])
logger = logging.getLogger(__name__)


def _quiz_out(db: Session, quiz: Quiz) -> QuizOut:
    from app.routers.exercises import _question_out

    questions = quiz_service.quiz_questions(db, quiz)
    module = db.get(Module, quiz.module_id) if quiz.module_id else None
    answered = {
        a.question_id: a.correct
        for a in db.query(Attempt).filter(Attempt.quiz_id == quiz.id).all()
    }
    return QuizOut(
        id=quiz.id,
        kind=quiz.kind,
        level=quiz.level,
        module_id=quiz.module_id,
        module_title=module.title if module else None,
        subject_name=module.subject.name if module is not None and module.subject else None,
        current_index=quiz.current_index,
        total=len(questions),
        correct_count=quiz.correct_count,
        completed=quiz.completed_at is not None,
        questions=[_question_out(q) for q in questions],
        results=[answered.get(q.id) for q in questions],
    )


def _get_owned_quiz(db: Session, quiz_id: int, user: User) -> Quiz:
    quiz = db.get(Quiz, quiz_id)
    if quiz is None or quiz.user_id != user.id:
        raise HTTPException(status_code=404, detail="Questionario nao encontrado")
    return quiz


@router.post("/start", response_model=QuizOut, status_code=status.HTTP_201_CREATED)
async def start_quiz(
    payload: QuizStartIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Monta e devolve o questionario completo."""

    if not current_user.diagnostic_completed:
        raise HTTPException(status_code=400, detail="Complete o diagnostico inicial primeiro")

    study_plan.ensure_plan(db, current_user)

    module: Module | None = None
    if payload.module_id is not None:
        module = db.get(Module, payload.module_id)
        if module is None:
            raise HTTPException(status_code=404, detail="Modulo nao encontrado")
    else:
        current = study_plan.current_progress(db, current_user)
        module = db.get(Module, current.module_id) if current else None

    # Aluno que pausou no meio volta para o mesmo questionario.
    open_quiz = quiz_service.find_open_quiz(db, current_user, module, payload.kind)
    if open_quiz is not None and open_quiz.question_ids:
        return _quiz_out(db, open_quiz)

    # Um questionario = no maximo uma chamada de IA, entao o rate limit e
    # cobrado uma vez, aqui.
    enforce_gemini_rate_limit(current_user.id)

    try:
        quiz = await quiz_service.build_quiz(
            db,
            current_user,
            module=module,
            kind=payload.kind,
            size=payload.size,
            focus_errors=study_plan.weak_topics(db, current_user),
        )
    except RuntimeError as exc:
        logger.error("Falha ao montar questionario: %s", exc)
        raise HTTPException(status_code=503, detail="Nao foi possivel montar o questionario agora")

    db.commit()
    db.refresh(quiz)
    return _quiz_out(db, quiz)


@router.get("/{quiz_id}", response_model=QuizOut)
def get_quiz(
    quiz_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _quiz_out(db, _get_owned_quiz(db, quiz_id, current_user))


@router.post("/{quiz_id}/answer", response_model=QuizAnswerOut)
def answer_quiz(
    quiz_id: int,
    payload: AnswerIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Corrige uma questao do questionario. Nao chama a API.

    O feedback do erro fica disponivel em
    GET /feedback/{attempt_id}/stream, consumido em paralelo pelo cliente.
    """

    quiz = _get_owned_quiz(db, quiz_id, current_user)
    if quiz.completed_at is not None:
        raise HTTPException(status_code=409, detail="Questionario ja finalizado")

    if payload.question_id not in (quiz.question_ids or []):
        raise HTTPException(status_code=400, detail="Questao nao pertence a este questionario")

    question = db.get(Question, payload.question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Questao nao encontrada")

    # Reenvio da mesma questao (duplo clique, refresh) devolve o resultado ja
    # registrado em vez de contar acerto duas vezes.
    previous = quiz_service.existing_answer(db, quiz, question)
    if previous is not None:
        return QuizAnswerOut(
            correct=previous.correct,
            correct_alternative_id=question.correct_alternative_id,
            explanation=question.directive_explanation if previous.correct else None,
            attempt_id=previous.id,
            answered_index=quiz.current_index,
            total=len(quiz.question_ids or []),
            correct_count=quiz.correct_count,
            finished=quiz_service.is_finished(quiz),
            feedback_available=not previous.correct,
        )

    attempt, is_correct = quiz_service.register_answer(
        db, current_user, quiz, question, payload.alternative_id
    )
    finished = quiz_service.is_finished(quiz)
    db.commit()

    return QuizAnswerOut(
        correct=is_correct,
        # No questionario o gabarito e revelado apos a resposta para os dois
        # grupos: aqui a alternativa correta ja fica visivel na revisao, e o
        # que diferencia os grupos e o TIPO de feedback (ver ai/feedback.py).
        correct_alternative_id=question.correct_alternative_id,
        explanation=question.directive_explanation if is_correct else None,
        attempt_id=attempt.id,
        answered_index=quiz.current_index,
        total=len(quiz.question_ids or []),
        correct_count=quiz.correct_count,
        finished=finished,
        feedback_available=not is_correct,
    )


@router.post("/{quiz_id}/finish", response_model=QuizResultOut)
def finish_quiz(
    quiz_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fecha o questionario e avanca a trilha para a proxima etapa."""

    quiz = _get_owned_quiz(db, quiz_id, current_user)
    total = len(quiz.question_ids or [])

    first_time = quiz.completed_at is None
    quiz_service.complete_quiz(db, quiz)

    progress = None
    if quiz.module_id is not None:
        progress = study_plan._get_or_create_progress(  # noqa: SLF001 - helper interno do modulo
            db, current_user, db.get(Module, quiz.module_id)
        )
        # So avanca a etapa uma vez, mesmo que o cliente chame /finish de novo.
        if first_time and study_plan.next_step(progress) is not None:
            study_plan.advance_step(db, progress)

    db.commit()

    accuracy = int(round(quiz.correct_count / total * 100)) if total else 0
    return QuizResultOut(
        quiz_id=quiz.id,
        correct_count=quiz.correct_count,
        total=total,
        accuracy=accuracy,
        next_step=next_step_payload(db, current_user),
    )


@router.get("", response_model=list[QuizOut])
def list_quizzes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 10,
):
    quizzes = (
        db.query(Quiz)
        .filter(Quiz.user_id == current_user.id)
        .order_by(Quiz.created_at.desc())
        .limit(min(limit, 50))
        .all()
    )
    return [_quiz_out(db, q) for q in quizzes]


__all__ = ["router", "QuizKind"]
