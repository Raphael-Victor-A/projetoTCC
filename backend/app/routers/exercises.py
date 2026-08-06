import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import adaptive_engine, gemini_orchestrator
from app.database import get_db
from app.models import Attempt, FeedbackGroup, InteractionLog, Question, User
from app.rate_limit import enforce_gemini_rate_limit
from app.schemas import (
    AnswerIn,
    AnswerResultOut,
    DiagnosticResultOut,
    DiagnosticSubmitIn,
    FeedbackOut,
    ProgressOut,
    QuestionOut,
)
from app.security import get_current_user

router = APIRouter(tags=["exercises"])
logger = logging.getLogger(__name__)


@router.get("/diagnostic", response_model=list[QuestionOut])
def get_diagnostic(db: Session = Depends(get_db)):
    questions = db.query(Question).filter(Question.is_diagnostic.is_(True)).all()
    if not questions:
        raise HTTPException(status_code=500, detail="Teste de nivelamento nao configurado")
    return questions


@router.post("/diagnostic/submit", response_model=DiagnosticResultOut)
def submit_diagnostic(
    payload: DiagnosticSubmitIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.diagnostic_completed:
        raise HTTPException(status_code=400, detail="Diagnostico ja realizado")

    questions = {
        q.id: q
        for q in db.query(Question).filter(Question.is_diagnostic.is_(True)).all()
    }
    if not questions or len(payload.answers) != len(questions):
        raise HTTPException(status_code=400, detail="Respostas incompletas para o teste de nivelamento")

    correct_count = 0
    for answer in payload.answers:
        question = questions.get(answer.question_id)
        if question is None:
            raise HTTPException(status_code=400, detail=f"Questao {answer.question_id} invalida")

        # Validacao 100% server-side contra o gabarito armazenado no banco.
        is_correct = answer.alternative_id == question.correct_alternative_id
        if is_correct:
            correct_count += 1

        db.add(
            Attempt(
                user_id=current_user.id,
                question_id=question.id,
                alternative_chosen=answer.alternative_id,
                correct=is_correct,
                level_at_time=current_user.level,
                is_diagnostic=True,
            )
        )

    assigned_level = adaptive_engine.assign_initial_level(correct_count, len(questions))
    current_user.level = assigned_level
    current_user.diagnostic_completed = True
    db.commit()

    return DiagnosticResultOut(correct_count=correct_count, total=len(questions), assigned_level=assigned_level)


@router.get("/exercises/next", response_model=QuestionOut)
def get_next_exercise(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.diagnostic_completed:
        raise HTTPException(status_code=400, detail="Complete o diagnostico inicial primeiro")

    question = adaptive_engine.get_or_generate_question(current_user, db)
    if question is None:
        raise HTTPException(status_code=404, detail="Nenhuma questao disponivel para o nivel atual")
    db.commit()
    return question


@router.post("/exercises/submit", response_model=AnswerResultOut)
def submit_exercise(
    payload: AnswerIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.diagnostic_completed:
        raise HTTPException(status_code=400, detail="Complete o diagnostico inicial primeiro")

    question = db.get(Question, payload.question_id)
    if question is None or question.is_diagnostic:
        raise HTTPException(status_code=404, detail="Questao invalida")

    # Validacao 100% server-side: gabarito nunca trafega para o cliente antes disso.
    is_correct = payload.alternative_id == question.correct_alternative_id
    level_before = current_user.level

    attempt = Attempt(
        user_id=current_user.id,
        question_id=question.id,
        alternative_chosen=payload.alternative_id,
        correct=is_correct,
        level_at_time=level_before,
        is_diagnostic=False,
    )
    db.add(attempt)
    db.flush()

    promoted, entered_remediation = adaptive_engine.record_attempt(current_user, is_correct)
    level_changed = promoted or (current_user.level != level_before)

    feedback_out = None
    if not is_correct:
        try:
            enforce_gemini_rate_limit(current_user.id)
            content, leak_detected, fallback_used, raw_excerpt, latency_ms = gemini_orchestrator.generate_feedback(
                question=question,
                chosen_alternative_id=payload.alternative_id,
                mode=current_user.group,
            )
        except Exception:
            logger.exception("Falha ao chamar o Orquestrador de IA (Gemini)")
            content = (
                "Nao foi possivel gerar o feedback pedagogico agora. "
                "Releia o enunciado com atencao e tente identificar onde o raciocinio pode ter divergido."
            )
            leak_detected, fallback_used, raw_excerpt, latency_ms = False, True, "", 0.0

        db.add(
            InteractionLog(
                attempt_id=attempt.id,
                mode=current_user.group,
                gemini_latency_ms=latency_ms,
                leak_detected=leak_detected,
                fallback_used=fallback_used,
                raw_output_excerpt=raw_excerpt,
            )
        )
        feedback_out = FeedbackOut(mode=current_user.group, content=content)

    db.commit()

    # No modo socratico a resposta pronta nunca e revelada, nem por este campo
    # de "gabarito pos-submissao" - so o feedback socratico (perguntas
    # orientadoras) e devolvido, senao o vazamento acontece aqui em vez de
    # no texto do Gemini.
    reveal_answer = not is_correct and current_user.group == FeedbackGroup.DIRETIVO

    return AnswerResultOut(
        correct=is_correct,
        correct_alternative_id=question.correct_alternative_id if reveal_answer else None,
        level=current_user.level,
        level_changed=level_changed,
        needs_remediation=current_user.needs_remediation,
        feedback=feedback_out,
    )


@router.get("/progress", response_model=ProgressOut)
def get_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attempts = db.query(Attempt).filter(
        Attempt.user_id == current_user.id, Attempt.is_diagnostic.is_(False)
    ).all()
    return ProgressOut(
        level=current_user.level,
        window_count=current_user.window_count,
        window_correct=current_user.window_correct,
        needs_remediation=current_user.needs_remediation,
        total_attempts=len(attempts),
        total_correct=sum(1 for a in attempts if a.correct),
    )
