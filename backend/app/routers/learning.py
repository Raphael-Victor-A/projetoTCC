"""Trilha de estudos: plano, grade, proxima etapa e mini aulas."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import lesson_service, study_plan
from app.ai import sse
from app.ai.client import AIUnavailable
from app.ai.lessons import stream_explanation
from app.database import get_db
from app.models import (
    MODULE_STEPS,
    Attempt,
    Lesson,
    Module,
    ModuleStatus,
    StepKind,
    Subject,
    User,
    UserModuleProgress,
)
from app.rate_limit import enforce_gemini_rate_limit
from app.schemas import (
    LessonOut,
    NextStepOut,
    RecommendationOut,
    StudyPlanOut,
    SubjectOut,
)
from app.security import get_current_user

router = APIRouter(tags=["learning"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Proxima etapa da trilha
# ---------------------------------------------------------------------------


def next_step_payload(db: Session, user: User) -> NextStepOut:
    """Decide o que o aluno deve fazer agora.

    A alternancia questionario -> mini aula -> questionario e definida por
    `MODULE_STEPS`; aqui so lemos em que ponto dessa sequencia o modulo atual
    esta. Usado tanto pelo dashboard quanto pelo fim de cada questionario.
    """

    if not user.diagnostic_completed:
        return NextStepOut(
            kind="diagnostic",
            total_steps=len(MODULE_STEPS),
            message="Comece pelo Questionario Diagnostico para montarmos sua trilha.",
        )

    study_plan.ensure_plan(db, user)
    progress = study_plan.current_progress(db, user)
    if progress is None:
        return NextStepOut(
            kind="module_completed",
            total_steps=len(MODULE_STEPS),
            message="Voce concluiu todos os modulos da sua trilha. Parabens!",
        )

    module = db.get(Module, progress.module_id)
    subject = db.get(Subject, module.subject_id) if module else None
    step = study_plan.next_step(progress)

    if step is None:
        return NextStepOut(
            kind="module_completed",
            module_id=progress.module_id,
            module_title=module.title if module else None,
            subject_name=subject.name if subject else None,
            step_index=progress.step_index,
            total_steps=len(MODULE_STEPS),
            message="Modulo concluido. Escolha o proximo na sua trilha.",
        )

    lesson_id = None
    if step == StepKind.LESSON and module is not None:
        existing = (
            db.query(Lesson)
            .filter(Lesson.module_id == module.id)
            .order_by(Lesson.id.desc())
            .first()
        )
        lesson_id = existing.id if existing else None

    message = (
        "Hora de praticar o que voce viu."
        if step == StepKind.QUIZ
        else "Antes do proximo questionario, uma mini aula rapida."
    )
    return NextStepOut(
        kind=step.value,
        module_id=progress.module_id,
        module_title=module.title if module else None,
        subject_name=subject.name if subject else None,
        lesson_id=lesson_id,
        step_index=progress.step_index,
        total_steps=len(MODULE_STEPS),
        message=message,
    )


@router.get("/next-step", response_model=NextStepOut)
def get_next_step(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return next_step_payload(db, current_user)


# ---------------------------------------------------------------------------
# Dashboard / plano de estudos
# ---------------------------------------------------------------------------


def _reason_for(progress: UserModuleProgress) -> str:
    performance = study_plan.module_performance(progress)
    if progress.diagnostic_total and performance is not None and performance < 50:
        return f"Voce acertou {performance}% deste conteudo no diagnostico"
    if performance is not None and performance < 70:
        return f"Desempenho atual de {performance}% — vale reforcar"
    if progress.status == ModuleStatus.EM_ANDAMENTO:
        return "Voce comecou este modulo e ainda nao terminou"
    return "Proximo na ordem recomendada da sua trilha"


@router.get("/study-plan", response_model=StudyPlanOut)
def get_study_plan(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Painel do aluno: grade, progresso, desempenho e recomendacoes.

    Monta tudo com poucas consultas agregadas (uma por tabela envolvida) em
    vez de uma consulta por modulo.
    """

    study_plan.ensure_plan(db, current_user)

    attempts = (
        db.query(Attempt.correct)
        .filter(Attempt.user_id == current_user.id, Attempt.is_diagnostic.is_(False))
        .all()
    )
    total_attempts = len(attempts)
    total_correct = sum(1 for (correct,) in attempts if correct)

    progresses = (
        db.query(UserModuleProgress)
        .filter(UserModuleProgress.user_id == current_user.id)
        .all()
    )
    modules_total = len(progresses)
    modules_completed = sum(1 for p in progresses if p.status == ModuleStatus.CONCLUIDO)
    overall_completion = (
        int(round(sum(study_plan.completion_percent(p) for p in progresses) / modules_total))
        if modules_total
        else 0
    )

    modules_by_id = {m.id: m for m in db.query(Module).all()}
    subjects_by_id = {s.id: s for s in db.query(Subject).all()}

    recommendations: list[RecommendationOut] = []
    for progress in study_plan.recommended_progress(db, current_user, limit=4):
        module = modules_by_id.get(progress.module_id)
        if module is None:
            continue
        subject = subjects_by_id.get(module.subject_id)
        step = study_plan.next_step(progress)
        recommendations.append(
            RecommendationOut(
                module_id=module.id,
                module_title=module.title,
                subject_name=subject.name if subject else "",
                subject_color=subject.color if subject else "#6366f1",
                reason=_reason_for(progress),
                next_step=step.value if step else None,
                completion=study_plan.completion_percent(progress),
                performance=study_plan.module_performance(progress),
            )
        )

    current = study_plan.current_progress(db, current_user)

    return StudyPlanOut(
        level=current_user.level,
        diagnostic_completed=current_user.diagnostic_completed,
        total_attempts=total_attempts,
        total_correct=total_correct,
        accuracy=int(round(total_correct / total_attempts * 100)) if total_attempts else 0,
        modules_completed=modules_completed,
        modules_total=modules_total,
        overall_completion=overall_completion,
        current_module_id=current.module_id if current else None,
        recommendations=recommendations,
        weak_topics=study_plan.weak_topics(db, current_user),
        subjects=[SubjectOut(**data) for data in study_plan.subject_overview(db, current_user)],
    )


@router.get("/subjects", response_model=list[SubjectOut])
def list_subjects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study_plan.ensure_plan(db, current_user)
    return [SubjectOut(**data) for data in study_plan.subject_overview(db, current_user)]


@router.post("/modules/{module_id}/select", response_model=NextStepOut)
def select_module(
    module_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aluno escolhe estudar um modulo agora.

    Personalizar a grade e um requisito: a trilha sugere, o aluno decide. O
    modulo escolhido vai para o topo da fila sem apagar as prioridades
    calculadas dos demais.
    """

    module = db.get(Module, module_id)
    if module is None:
        raise HTTPException(status_code=404, detail="Modulo nao encontrado")

    study_plan.ensure_plan(db, current_user)
    progress = study_plan._get_or_create_progress(db, current_user, module)  # noqa: SLF001
    if progress.status == ModuleStatus.CONCLUIDO:
        # Reabre o modulo para revisao, do inicio da sequencia.
        progress.step_index = 0
    progress.status = ModuleStatus.EM_ANDAMENTO

    # Fica a frente de tudo que ja existe, inclusive de escolhas anteriores do
    # proprio aluno — a ultima escolha e a que vale.
    lowest = (
        db.query(func.min(UserModuleProgress.priority))
        .filter(UserModuleProgress.user_id == current_user.id)
        .scalar()
    )
    progress.priority = (lowest if lowest is not None else 0) - 1
    db.commit()

    return next_step_payload(db, current_user)


# ---------------------------------------------------------------------------
# Mini aulas
# ---------------------------------------------------------------------------


def _lesson_out(lesson: Lesson) -> LessonOut:
    return LessonOut(
        id=lesson.id,
        module_id=lesson.module_id,
        topic=lesson.topic,
        level=lesson.level,
        title=lesson.title,
        intro=lesson.intro,
        sections=lesson.sections or [],
        key_concepts=lesson.key_concepts or [],
        examples=lesson.examples or [],
        diagram=lesson.diagram,
        summary=lesson.summary,
        generated=lesson.generated,
    )


@router.get("/modules/{module_id}/lesson", response_model=LessonOut)
async def get_module_lesson(
    module_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mini aula do modulo. Reaproveita a aula ja gravada quando existe."""

    module = db.get(Module, module_id)
    if module is None:
        raise HTTPException(status_code=404, detail="Modulo nao encontrado")

    focus = study_plan.weak_topics(db, current_user, limit=5)
    lesson = await lesson_service.get_or_create_lesson(db, module, focus_errors=focus)
    db.commit()
    db.refresh(lesson)
    return _lesson_out(lesson)


@router.get("/lessons/{lesson_id}", response_model=LessonOut)
def get_lesson(
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Mini aula nao encontrada")
    return _lesson_out(lesson)


@router.post("/lessons/{lesson_id}/complete", response_model=NextStepOut)
def complete_lesson(
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Marca a mini aula como concluida e avanca para o proximo questionario."""

    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Mini aula nao encontrada")

    lesson_service.mark_completed(db, current_user, lesson)

    if lesson.module_id is not None:
        module = db.get(Module, lesson.module_id)
        if module is not None:
            progress = study_plan._get_or_create_progress(db, current_user, module)  # noqa: SLF001
            # So avanca se a etapa atual for de fato a mini aula: evita pular
            # um questionario caso o aluno reabra a aula depois.
            if study_plan.next_step(progress) == StepKind.LESSON:
                study_plan.advance_step(db, progress)

    db.commit()
    return next_step_payload(db, current_user)


@router.get("/modules/{module_id}/lesson/stream")
async def stream_module_lesson(
    module_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Explicacao do modulo em streaming (markdown), para leitura imediata."""

    module = db.get(Module, module_id)
    if module is None:
        raise HTTPException(status_code=404, detail="Modulo nao encontrado")

    enforce_gemini_rate_limit(current_user.id)
    subject = db.get(Subject, module.subject_id)
    focus = study_plan.weak_topics(db, current_user, limit=5)
    topic = module.title
    level = module.level
    subject_name = subject.name if subject else "Matematica"

    async def generate():
        yield sse.event("meta", {"topic": topic, "level": level.value})
        try:
            async for piece in stream_explanation(
                topic=topic, level=level, subject=subject_name, focus_errors=focus
            ):
                yield sse.chunk(piece)
        except AIUnavailable as exc:
            logger.warning("Streaming de mini aula indisponivel: %s", exc)
            yield sse.error("Nao foi possivel gerar a explicacao agora.")
        yield sse.done({"topic": topic})

    return StreamingResponse(generate(), media_type=sse.MEDIA_TYPE, headers=sse.SSE_HEADERS)
