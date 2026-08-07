"""Mini aulas: obtencao, persistencia e conclusao.

A aula e gravada em `lessons` com uma `cache_key` deterministica (modulo +
nivel + lacunas atacadas). Consequencia pratica: a segunda vez que alguem
chega naquele ponto da trilha — o mesmo aluno revisando ou um colega da
mesma turma — a aula vem do banco, sem nova chamada a API.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.ai import lessons as ai_lessons
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
