"""Diagnostico, exercicios avulsos e streaming de feedback."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import adaptive_engine, study_plan
from app.ai import sse
from app.ai.feedback import FeedbackResult, stream_feedback
from app.database import SessionLocal, get_db
from app.models import (
    Attempt,
    DiagnosticSession,
    FeedbackGroup,
    InteractionLog,
    Module,
    ModuleStatus,
    Question,
    Subject,
    User,
    UserModuleProgress,
)
from app.rate_limit import enforce_gemini_rate_limit
from app.schemas import (
    AnswerIn,
    AnswerResultOut,
    DiagnosticOut,
    DiagnosticResultOut,
    DiagnosticSubmitIn,
    FeedbackOut,
    FocusAreaOut,
    ProgressOut,
    QuestionOut,
    WrongAnswerOut,
)
from app.security import get_current_user

router = APIRouter(tags=["exercises"])
logger = logging.getLogger(__name__)


def _question_out(question: Question, shuffle: bool = True) -> QuestionOut:
    alternatives = (
        study_plan.shuffled_alternatives(question) if shuffle else list(question.alternatives or [])
    )
    return QuestionOut(
        id=question.id,
        level=question.level,
        topic=question.topic,
        statement=question.statement,
        alternatives=alternatives,
        is_remedial=question.is_remedial,
        is_diagnostic=question.is_diagnostic,
        module_id=question.module_id,
        subject_id=question.subject_id,
    )


# ---------------------------------------------------------------------------
# Questionario Diagnostico
# ---------------------------------------------------------------------------


@router.get("/diagnostic", response_model=DiagnosticOut)
def get_diagnostic(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sorteia um diagnostico novo para o aluno.

    Cada chamada cria uma sessao com o conjunto sorteado; a submissao e
    corrigida contra essa sessao, e nao contra o banco inteiro.
    """

    if current_user.diagnostic_completed:
        # Impede reabrir o diagnostico depois de concluido — parte da correcao
        # do fluxo de primeiro acesso.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Diagnostico ja realizado")

    questions = study_plan.sample_diagnostic(db, current_user)
    if not questions:
        raise HTTPException(status_code=500, detail="Teste de nivelamento nao configurado")

    session = DiagnosticSession(user_id=current_user.id, question_ids=[q.id for q in questions])
    db.add(session)
    db.commit()
    db.refresh(session)

    return DiagnosticOut(
        session_id=session.id,
        questions=[_question_out(q) for q in questions],
    )


@router.post("/diagnostic/submit", response_model=DiagnosticResultOut)
def submit_diagnostic(
    payload: DiagnosticSubmitIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Corrige o diagnostico, marca a conclusao e monta a trilha do aluno.

    Tudo em uma unica transacao: nivel, flag `diagnostic_completed`, sessao
    fechada e prioridades dos modulos. Ou grava tudo, ou nada — assim o
    usuario nunca fica no estado intermediario que fazia o app devolve-lo ao
    diagnostico.
    """

    if current_user.diagnostic_completed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Diagnostico ja realizado")

    session = None
    if payload.session_id is not None:
        session = db.get(DiagnosticSession, payload.session_id)
        if session is None or session.user_id != current_user.id:
            raise HTTPException(status_code=400, detail="Sessao de diagnostico invalida")

    expected_ids = list(session.question_ids or []) if session else None
    answers = {a.question_id: a.alternative_id for a in payload.answers}

    if expected_ids is not None:
        missing = [qid for qid in expected_ids if qid not in answers]
        if missing:
            raise HTTPException(
                status_code=400, detail="Respostas incompletas para o teste de nivelamento"
            )
        question_ids = expected_ids
    else:
        question_ids = list(answers)

    questions = {
        q.id: q for q in db.query(Question).filter(Question.id.in_(question_ids)).all()
    }
    if len(questions) != len(question_ids):
        raise HTTPException(status_code=400, detail="Questao invalida no envio do diagnostico")

    results: list[tuple[Question, bool]] = []
    correct_count = 0
    for question_id in question_ids:
        question = questions[question_id]
        # Validacao 100% server-side contra o gabarito armazenado no banco.
        is_correct = answers.get(question_id) == question.correct_alternative_id
        correct_count += 1 if is_correct else 0
        results.append((question, is_correct))

        db.add(
            Attempt(
                user_id=current_user.id,
                question_id=question.id,
                alternative_chosen=answers.get(question_id, ""),
                correct=is_correct,
                level_at_time=current_user.level,
                is_diagnostic=True,
            )
        )

    total = len(question_ids)
    current_user.level = study_plan.assign_initial_level(correct_count, total)
    current_user.diagnostic_completed = True
    current_user.diagnostic_completed_at = datetime.utcnow()
    if session is not None:
        session.completed_at = datetime.utcnow()

    scores = study_plan.apply_diagnostic_results(db, current_user, results)
    db.commit()

    subjects = {s.id: s for s in db.query(Subject).all()}

    def to_out(score: study_plan.ModuleScore) -> FocusAreaOut:
        subject = subjects.get(score.module.subject_id)
        return FocusAreaOut(
            module_id=score.module.id,
            module_title=score.module.title,
            subject_name=subject.name if subject else "",
            correct=score.correct,
            total=score.total,
            accuracy=int(round(score.accuracy * 100)),
        )

    ordered = sorted(scores.values(), key=lambda s: (s.accuracy, s.module.order_index))
    focus_areas = [to_out(s) for s in ordered if s.accuracy < study_plan.MASTERY_THRESHOLD][:5]
    strengths = [to_out(s) for s in reversed(ordered) if s.accuracy >= study_plan.MASTERY_THRESHOLD][:3]

    current = study_plan.current_progress(db, current_user)

    # Questoes erradas, na ordem em que foram apresentadas. Os dados vem do
    # que acabou de ser gravado em `attempts` (alternative_chosen) e da
    # propria questao; o texto e buscado pelo id da alternativa, entao o
    # embaralhamento da exibicao nao interfere.
    module_titles = {
        m.id: m.title
        for m in db.query(Module)
        .filter(Module.id.in_({q.module_id for q, _ in results if q.module_id}))
        .all()
    }

    def alt_text(question: Question, alternative_id: str) -> str:
        for alt in question.alternatives or []:
            if alt.get("id") == alternative_id:
                return alt.get("text", "")
        return ""

    wrong_answers = [
        WrongAnswerOut(
            question_id=question.id,
            statement=question.statement,
            chosen_text=alt_text(question, answers.get(question.id, "")) or "(sem resposta)",
            correct_text=alt_text(question, question.correct_alternative_id),
            module_title=module_titles.get(question.module_id, "") if question.module_id else "",
            topic=question.topic,
        )
        for question, is_correct in results
        if not is_correct
    ]

    return DiagnosticResultOut(
        correct_count=correct_count,
        total=total,
        assigned_level=current_user.level,
        focus_areas=focus_areas,
        strengths=strengths,
        wrong_answers=wrong_answers,
        next_module_id=current.module_id if current else None,
    )


# ---------------------------------------------------------------------------
# Exercicios avulsos
# ---------------------------------------------------------------------------


@router.get("/exercises/next", response_model=QuestionOut)
async def get_next_exercise(
    module_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.diagnostic_completed:
        raise HTTPException(status_code=400, detail="Complete o diagnostico inicial primeiro")

    module = db.get(Module, module_id) if module_id else None
    question = await adaptive_engine.get_or_generate_question(current_user, db, module)
    if question is None:
        raise HTTPException(status_code=404, detail="Nenhuma questao disponivel para o nivel atual")
    db.commit()
    return _question_out(question)


@router.post("/exercises/submit", response_model=AnswerResultOut)
def submit_exercise(
    payload: AnswerIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Corrige a resposta e devolve na hora.

    Este endpoint NAO chama o Gemini: o feedback pedagogico vem depois, em
    streaming, por GET /feedback/{attempt_id}/stream. E o que faz a correcao
    aparecer instantaneamente em vez de esperar a IA escrever a explicacao.
    """

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

    promoted, _entered_remediation = adaptive_engine.record_attempt(current_user, is_correct)
    level_changed = promoted or (current_user.level != level_before)

    _update_module_progress(db, current_user, question, is_correct)
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
        attempt_id=attempt.id,
        feedback_available=not is_correct,
    )


def _update_module_progress(db: Session, user: User, question: Question, is_correct: bool) -> None:
    """Mantem o painel coerente com exercicios avulsos tambem."""

    if question.module_id is None:
        return
    progress = (
        db.query(UserModuleProgress)
        .filter(
            UserModuleProgress.user_id == user.id,
            UserModuleProgress.module_id == question.module_id,
        )
        .first()
    )
    if progress is None:
        return
    progress.total_answers += 1
    if is_correct:
        progress.correct_answers += 1
    if progress.status == ModuleStatus.NAO_INICIADO:
        progress.status = ModuleStatus.EM_ANDAMENTO


# ---------------------------------------------------------------------------
# Feedback em streaming
# ---------------------------------------------------------------------------


def _persist_feedback(attempt_id: int, mode: FeedbackGroup, result: FeedbackResult) -> None:
    """Grava o feedback e sua telemetria em sessao propria.

    O gerador do streaming vive alem do escopo da dependencia `get_db`, entao
    abrir uma sessao curta aqui e mais seguro do que carregar a original.
    """

    db = SessionLocal()
    try:
        attempt = db.get(Attempt, attempt_id)
        # Aviso de indisponibilidade nao vira o feedback da tentativa: se
        # gravasse, o aluno veria a mensagem de erro para sempre naquela
        # questao, mesmo depois de a IA voltar.
        if attempt is not None and not result.degraded:
            attempt.feedback_text = result.content
        db.add(
            InteractionLog(
                attempt_id=attempt_id,
                mode=mode,
                gemini_latency_ms=result.latency_ms,
                leak_detected=result.leak_detected,
                fallback_used=result.fallback_used,
                raw_output_excerpt=result.raw_excerpt,
            )
        )
        db.commit()
    except Exception:
        logger.exception("Falha ao registrar o feedback")
        db.rollback()
    finally:
        db.close()


@router.get("/feedback/{attempt_id}/stream")
async def stream_attempt_feedback(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Transmite o feedback pedagogico do erro, token a token (SSE).

    Se o feedback daquela tentativa ja foi gerado antes (o aluno recarregou a
    pagina), o texto salvo e devolvido direto — sem nova chamada a API.
    """

    attempt = db.get(Attempt, attempt_id)
    if attempt is None or attempt.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Tentativa nao encontrada")
    if attempt.correct:
        raise HTTPException(status_code=400, detail="Nao ha feedback para uma resposta correta")

    question = db.get(Question, attempt.question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Questao nao encontrada")

    mode = current_user.group or FeedbackGroup.DIRETIVO

    if attempt.feedback_text:
        cached_text = attempt.feedback_text

        async def replay():
            yield sse.event("meta", {"mode": mode.value, "cached": True})
            yield sse.chunk(cached_text)
            yield sse.done({"mode": mode.value})

        return StreamingResponse(replay(), media_type=sse.MEDIA_TYPE, headers=sse.SSE_HEADERS)

    enforce_gemini_rate_limit(current_user.id)
    chosen = attempt.alternative_chosen

    async def generate():
        yield sse.event("meta", {"mode": mode.value, "cached": False})
        result: FeedbackResult | None = None
        try:
            async for kind, payload in stream_feedback(question, chosen, mode):
                if kind == "chunk":
                    yield sse.chunk(str(payload))
                elif kind == "done":
                    result = payload  # type: ignore[assignment]
        except Exception:
            logger.exception("Falha no streaming de feedback")
            yield sse.error("Nao foi possivel gerar o feedback agora.")
        if result is not None:
            _persist_feedback(attempt.id, mode, result)
        yield sse.done({"mode": mode.value})

    return StreamingResponse(generate(), media_type=sse.MEDIA_TYPE, headers=sse.SSE_HEADERS)


@router.get("/feedback/{attempt_id}", response_model=FeedbackOut)
async def get_attempt_feedback(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Versao nao-streaming do feedback, para clientes que nao consomem SSE."""

    attempt = db.get(Attempt, attempt_id)
    if attempt is None or attempt.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Tentativa nao encontrada")
    if attempt.correct:
        raise HTTPException(status_code=400, detail="Nao ha feedback para uma resposta correta")

    mode = current_user.group or FeedbackGroup.DIRETIVO
    if attempt.feedback_text:
        return FeedbackOut(mode=mode, content=attempt.feedback_text)

    question = db.get(Question, attempt.question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Questao nao encontrada")

    enforce_gemini_rate_limit(current_user.id)
    from app.ai.feedback import generate_feedback

    result = await generate_feedback(question, attempt.alternative_chosen, mode)
    _persist_feedback(attempt.id, mode, result)
    return FeedbackOut(mode=mode, content=result.content)


@router.get("/progress", response_model=ProgressOut)
def get_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attempts = db.query(Attempt).filter(
        Attempt.user_id == current_user.id, Attempt.is_diagnostic.is_(False)
    ).all()

    # O bloco da janela movel so conta exercicios avulsos (POST
    # /exercises/submit chama adaptive_engine.record_attempt; questionarios
    # nao). Entao o bloco atual sao as ultimas `window_count` tentativas
    # avulsas, em ordem.
    window_results: list[bool] = []
    if current_user.window_count > 0:
        recent = (
            db.query(Attempt)
            .filter(
                Attempt.user_id == current_user.id,
                Attempt.is_diagnostic.is_(False),
                Attempt.quiz_id.is_(None),
            )
            .order_by(Attempt.id.desc())
            .limit(current_user.window_count)
            .all()
        )
        window_results = [a.correct for a in reversed(recent)]

    return ProgressOut(
        level=current_user.level,
        window_count=current_user.window_count,
        window_correct=current_user.window_correct,
        window_results=window_results,
        needs_remediation=current_user.needs_remediation,
        total_attempts=len(attempts),
        total_correct=sum(1 for a in attempts if a.correct),
    )
