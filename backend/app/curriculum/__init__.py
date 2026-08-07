"""Grade de estudos pre-configurada e sua carga no banco."""

import logging

from sqlalchemy.orm import Session

from app.curriculum.bncc import CURRICULUM
from app.models import Lesson, Module, Question, Quiz, Subject, UserModuleProgress

logger = logging.getLogger(__name__)

__all__ = ["CURRICULUM", "sync_curriculum"]


def sync_curriculum(db: Session) -> tuple[int, int]:
    """Carrega/atualiza a grade a partir de `CURRICULUM` e remove o que saiu.

    Idempotente e casado por slug: rodar de novo depois de editar bncc.py
    atualiza titulo, objetivos, conteudos e ordem sem duplicar nada e sem
    perder o progresso ja registrado dos alunos (que aponta para module.id).
    """

    subjects_touched = 0
    modules_touched = 0

    existing_subjects = {s.slug: s for s in db.query(Subject).all()}
    existing_modules = {m.slug: m for m in db.query(Module).all()}

    for subject_index, subject_data in enumerate(CURRICULUM):
        subject = existing_subjects.get(subject_data["slug"])
        if subject is None:
            subject = Subject(slug=subject_data["slug"])
            db.add(subject)
            existing_subjects[subject.slug] = subject

        subject.name = subject_data["name"]
        subject.area = subject_data["area"]
        subject.description = subject_data.get("description", "")
        subject.color = subject_data.get("color", "#6366f1")
        subject.order_index = subject_index
        subjects_touched += 1

        # flush garante subject.id antes de vincular os modulos.
        db.flush()

        for module_index, module_data in enumerate(subject_data["modules"]):
            module = existing_modules.get(module_data["slug"])
            if module is None:
                module = Module(slug=module_data["slug"])
                db.add(module)
                existing_modules[module.slug] = module

            module.subject_id = subject.id
            module.title = module_data["title"]
            module.summary = module_data.get("summary", "")
            module.level = module_data["level"]
            module.order_index = module_index
            module.objectives = list(module_data.get("objectives", []))
            module.contents = list(module_data.get("contents", []))
            module.bncc_codes = list(module_data.get("bncc_codes", []))
            modules_touched += 1

    db.flush()
    _purge_removed(db)
    db.commit()

    logger.info(
        "Grade sincronizada: %d disciplina(s), %d modulo(s)", subjects_touched, modules_touched
    )
    return subjects_touched, modules_touched


def _purge_removed(db: Session) -> None:
    """Remove disciplinas e modulos que sairam de `CURRICULUM`.

    Historico de aluno nao e apagado: as questoes dos modulos removidos apenas
    viram `active=False` (e perdem o vinculo com a grade), de modo que as
    tentativas ja registradas continuam validas mas a questao nunca mais e
    sorteada. Isso tambem evita referencia pendente ao apagar o modulo.
    """

    valid_subject_slugs = {s["slug"] for s in CURRICULUM}
    valid_module_slugs = {m["slug"] for s in CURRICULUM for m in s["modules"]}

    obsolete_subjects = [s for s in db.query(Subject).all() if s.slug not in valid_subject_slugs]
    obsolete_modules = [m for m in db.query(Module).all() if m.slug not in valid_module_slugs]

    if not obsolete_subjects and not obsolete_modules:
        return

    subject_ids = {s.id for s in obsolete_subjects}
    module_ids = {m.id for m in obsolete_modules}
    # Modulos que pertenciam a uma disciplina removida tambem saem.
    for module in db.query(Module).all():
        if module.subject_id in subject_ids:
            module_ids.add(module.id)

    retired_questions = 0
    for question in db.query(Question).all():
        if question.module_id in module_ids or question.subject_id in subject_ids:
            question.active = False
            question.is_diagnostic = False
            question.module_id = None
            question.subject_id = None
            retired_questions += 1

    for progress in db.query(UserModuleProgress).all():
        if progress.module_id in module_ids:
            db.delete(progress)

    for lesson in db.query(Lesson).all():
        if lesson.module_id in module_ids:
            db.delete(lesson)

    for quiz in db.query(Quiz).all():
        if quiz.module_id in module_ids:
            quiz.module_id = None

    db.flush()

    for module in db.query(Module).all():
        if module.id in module_ids:
            db.delete(module)
    for subject in obsolete_subjects:
        db.delete(subject)

    db.flush()
    logger.info(
        "Grade: %d modulo(s) e %d disciplina(s) removidos; %d questao(oes) aposentada(s)",
        len(module_ids),
        len(obsolete_subjects),
        retired_questions,
    )
