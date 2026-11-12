"""Mini aulas: obtencao, persistencia e conclusao.

A aula e gravada em `lessons` com uma `cache_key` deterministica (modulo +
nivel + lacunas atacadas). Consequencia pratica: a segunda vez que alguem
chega naquele ponto da trilha — o mesmo aluno revisando ou um colega da
mesma turma — a aula vem do banco, sem nova chamada a API.
"""

from __future__ import annotations

import logging

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai import lessons as ai_lessons
from app.config import settings
from app.models import Lesson, LessonView, Module, User

logger = logging.getLogger(__name__)


async def get_or_create_lesson(
    db: Session,
    module: Module,
    *,
    focus_errors: list[str] | None = None,
) -> Lesson:
    cache_key = ai_lessons.lesson_cache_key(
        topic=module.title,
        level=module.level,
        module_slug=module.slug,
        focus_errors=focus_errors,
    )

    existing = db.query(Lesson).filter(Lesson.cache_key == cache_key).first()
    if existing is not None:
        return existing

    subject_name = module.subject.name if module.subject is not None else "Matematica"
    generated = await ai_lessons.generate_lesson(
        topic=module.title,
        level=module.level,
        subject=subject_name,
        objectives=list(module.objectives or []),
        contents=list(module.contents or []),
        focus_errors=focus_errors,
    )
    used_fallback = generated is None
    if generated is None:
        generated = ai_lessons.fallback_lesson(
            module.title, list(module.objectives or []), list(module.contents or [])
        )

    lesson = Lesson(
        cache_key=cache_key,
        module_id=module.id,
        topic=module.title,
        level=module.level,
        title=generated.title[:200],
        intro=generated.intro,
        sections=[s.model_dump() for s in generated.sections],
        key_concepts=list(generated.key_concepts),
        examples=[e.model_dump() for e in generated.examples],
        diagram=(generated.diagram or "").strip() or None,
        summary=generated.summary,
        generated=not used_fallback,
    )
    db.add(lesson)
    db.flush()
    logger.info(
        "Mini aula criada para o modulo %s (%s)",
        module.slug,
        "fallback estatico" if used_fallback else "gerada por IA",
    )
    return lesson


def mark_completed(db: Session, user: User, lesson: Lesson) -> LessonView:
    view = (
        db.query(LessonView)
        .filter(LessonView.user_id == user.id, LessonView.lesson_id == lesson.id)
        .first()
    )
    if view is None:
        view = LessonView(user_id=user.id, lesson_id=lesson.id)
        db.add(view)
    view.completed = True
    db.flush()
    return view


# ---------------------------------------------------------------------------
# Limite de reexplicacao ("explicar de outro jeito")
# ---------------------------------------------------------------------------


def get_view(db: Session, user: User, lesson: Lesson) -> LessonView | None:
    return (
        db.query(LessonView)
        .filter(LessonView.user_id == user.id, LessonView.lesson_id == lesson.id)
        .first()
    )


def _get_or_create_view(db: Session, user: User, lesson: Lesson) -> LessonView:
    view = get_view(db, user, lesson)
    if view is not None:
        return view
    view = LessonView(user_id=user.id, lesson_id=lesson.id)
    db.add(view)
    try:
        db.commit()
    except IntegrityError:
        # Outra requisicao do mesmo aluno criou a linha ao mesmo tempo
        # (uq_user_lesson): usa a que ficou gravada.
        db.rollback()
        view = get_view(db, user, lesson)
        assert view is not None
    return view


def reexplain_remaining(view: LessonView | None) -> int:
    used = (view.reexplain_count or 0) if view is not None else 0
    return max(0, settings.lesson_reexplain_limit - used)


def reserve_reexplain(db: Session, user: User, lesson: Lesson) -> LessonView | None:
    """Consome uma reexplicacao do aluno nesta aula, de forma atomica.

    O incremento so acontece se ainda houver saldo (UPDATE ... WHERE
    reexplain_count < limite), entao duas requisicoes simultaneas nao passam
    as duas. Devolve a linha de LessonView, ou None se o limite ja foi usado.
    """

    view = _get_or_create_view(db, user, lesson)
    count = func.coalesce(LessonView.reexplain_count, 0)
    updated = (
        db.query(LessonView)
        .filter(LessonView.id == view.id, count < settings.lesson_reexplain_limit)
        .update({LessonView.reexplain_count: count + 1}, synchronize_session=False)
    )
    db.commit()
    if updated != 1:
        return None
    db.refresh(view)
    return view


def refund_reexplain(db: Session, view_id: int) -> None:
    """Devolve a reexplicacao quando a IA falhou (o aluno nao recebeu nada)."""

    count = func.coalesce(LessonView.reexplain_count, 0)
    db.query(LessonView).filter(LessonView.id == view_id, count > 0).update(
        {LessonView.reexplain_count: count - 1}, synchronize_session=False
    )
    db.commit()


def save_reexplain_text(db: Session, view_id: int, text: str) -> None:
    view = db.get(LessonView, view_id)
    if view is not None:
        view.reexplain_text = text
        db.commit()
