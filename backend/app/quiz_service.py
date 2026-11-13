"""Montagem e correcao de questionarios.

Regra de ouro: **um questionario custa no maximo uma chamada a API**.

A ordem de tentativa ao montar um questionario e:

1. reaproveitar questoes que ja existem no banco e que o aluno ainda nao viu
   (custo zero, latencia de um SELECT);
2. se ainda faltar questao, UMA chamada em lote ao Gemini traz o restante;
3. se a IA estiver indisponivel, completa com o acervo de reserva.

Nada disso acontece no meio do questionario: quando o aluno recebe a
primeira questao, todas as outras ja estao gravadas.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.ai.questions import QuestionBatchSpec, generate_batch, parse_difficulty
from app.config import settings
from app.models import (
    Attempt,
    Level,
    Module,
    ModuleStatus,
    Question,
    Quiz,
    QuizKind,
    Subject,
    User,
    UserModuleProgress,
)
from app.text_utils import statement_hash

logger = logging.getLogger(__name__)

# Quantas questoes recentes do aluno entram no "nao repita isto" do prompt.
RECENT_HISTORY_SIZE = 20


def _seen_question_ids(db: Session, user: User) -> set[int]:
    return {
        row[0]
        for row in db.query(Attempt.question_id).filter(Attempt.user_id == user.id).all()
    }


def _recent_statements(db: Session, user: User, limit: int = RECENT_HISTORY_SIZE) -> list[str]:
    rows = (
        db.query(Question.statement)
        .join(Attempt, Attempt.question_id == Question.id)
        .filter(Attempt.user_id == user.id)
        .order_by(Attempt.created_at.desc())
        .limit(limit)
        .all()
    )
    return [row[0] for row in rows]


def _reusable_questions(
    db: Session,
    user: User,
    module: Module | None,
    level: Level,
    is_remedial: bool,
    limit: int,
    seen_ids: set[int],
) -> list[Question]:
    """Questoes que ja existem e que o aluno ainda nao respondeu.

    E o caminho mais barato de todos: elimina a chamada a API sempre que o
    acervo do modulo ja da conta do questionario.
    """

    if limit <= 0:
        return []

    query = db.query(Question).filter(
        Question.is_diagnostic.is_(False), Question.active.is_(True)
    )
    if module is not None:
        query = query.filter(Question.module_id == module.id)
    else:
        query = query.filter(Question.level == level)

    candidates = [q for q in query.all() if q.id not in seen_ids]
    # Prioriza a dificuldade certa, mas aceita as demais antes de gastar API.
    candidates.sort(
        key=lambda q: (
            0 if q.is_remedial == is_remedial else 1,
            0 if q.level == level else 1,
            -(q.id or 0),
        )
    )
    return candidates[:limit]


def _fallback_questions(
    db: Session,
    module: Module | None,
    level: Level,
    limit: int,
    exclude_ids: set[int],
) -> list[Question]:
    """Ultimo recurso: qualquer questao utilizavel, ainda que repetida.

    Disponibilidade da atividade importa mais do que novidade — melhor o
    aluno revisar uma questao ja vista do que encarar uma tela de erro.
    """

    if limit <= 0:
        return []

    base = db.query(Question).filter(Question.active.is_(True))
    tiers = []
    if module is not None:
        tiers.append(base.filter(Question.module_id == module.id, Question.is_diagnostic.is_(False)))
        # Questoes do diagnostico do mesmo modulo servem de pratica depois que
        # o diagnostico ja foi feito.
        tiers.append(base.filter(Question.module_id == module.id))
    tiers.append(base.filter(Question.level == level, Question.is_diagnostic.is_(False)))
    tiers.append(base.filter(Question.is_diagnostic.is_(False)))

    picked: list[Question] = []
    used = set(exclude_ids)
    for tier in tiers:
        for question in tier.all():
            if question.id in used:
                continue
            picked.append(question)
            used.add(question.id)
            if len(picked) >= limit:
                return picked
    return picked


def _persist_generated(
    db: Session,
    user: User,
    module: Module | None,
    generated_questions: list,
    default_level: Level,
    is_remedial: bool,
) -> list[Question]:
    """Grava o lote gerado, reaproveitando linhas identicas ja existentes."""

    saved: list[Question] = []
    for generated in generated_questions:
        digest = statement_hash(generated.statement)
        existing = db.query(Question).filter(Question.statement_hash == digest).first()
        if existing is not None:
            saved.append(existing)
            continue

        question = Question(
            level=parse_difficulty(generated.difficulty, default_level),
            topic=generated.topic[:120],
            statement=generated.statement,
            alternatives=[a.model_dump() for a in generated.alternatives],
            correct_alternative_id=generated.correct_alternative_id,
            directive_explanation=generated.directive_explanation,
            is_remedial=is_remedial,
            is_diagnostic=False,
            module_id=module.id if module else None,
            subject_id=module.subject_id if module else None,
            generated=True,
            owner_user_id=user.id,
            statement_hash=digest,
        )
        db.add(question)
        saved.append(question)

    db.flush()
    return saved


async def build_quiz(
    db: Session,
    user: User,
    *,
    module: Module | None,
    kind: QuizKind,
    size: int | None = None,
    focus_errors: list[str] | None = None,
) -> Quiz:
    """Monta o questionario completo e o persiste. Nunca levanta por falha de IA."""

    size = size or settings.quiz_size
    level = module.level if module is not None else user.level
    is_remedial = kind == QuizKind.REFORCO

    seen_ids = _seen_question_ids(db, user)
    questions = _reusable_questions(db, user, module, level, is_remedial, size, seen_ids)
    reused = len(questions)

    missing = size - len(questions)
    if missing > 0:
        subject: Subject | None = module.subject if module is not None else None
        spec = QuestionBatchSpec(
            kind=kind.value if kind != QuizKind.DIAGNOSTICO else "diagnostico",
            count=missing,
            level=level,
            subject=subject.name if subject else "Matematica",
            module_title=module.title if module else "",
            contents=list(module.contents or []) if module else [],
            objectives=list(module.objectives or []) if module else [],
            focus_errors=focus_errors or [],
        )
        generated = await generate_batch(spec, _recent_statements(db, user))
        if generated:
            questions.extend(
                _persist_generated(db, user, module, generated, level, is_remedial)
            )

    # Deduplica preservando a ordem (uma questao reaproveitada pode coincidir
    # com uma gerada ja existente no banco).
    unique: list[Question] = []
    used_ids: set[int] = set()
    for question in questions:
        if question.id in used_ids:
            continue
        unique.append(question)
        used_ids.add(question.id)
    questions = unique[:size]

    if len(questions) < size:
        questions.extend(
            _fallback_questions(db, module, level, size - len(questions), used_ids)
        )

    if not questions:
        raise RuntimeError("Nenhuma questao disponivel para montar o questionario")

    quiz = Quiz(
        user_id=user.id,
        module_id=module.id if module else None,
        kind=kind,
        level=level,
        question_ids=[q.id for q in questions],
    )
    db.add(quiz)
    db.flush()

    logger.info(
        "Questionario %s montado: %d questao(oes) (%d reaproveitadas do banco, 1 chamada de IA no maximo)",
        kind.value,
        len(questions),
        reused,
    )
    return quiz


def quiz_questions(db: Session, quiz: Quiz) -> list[Question]:
    """Questoes do quiz na ordem em que foram sorteadas (uma unica consulta)."""

    ids = list(quiz.question_ids or [])
    if not ids:
        return []
    rows = {q.id: q for q in db.query(Question).filter(Question.id.in_(ids)).all()}
    return [rows[qid] for qid in ids if qid in rows]


def find_open_quiz(db: Session, user: User, module: Module | None, kind: QuizKind) -> Quiz | None:
    """Questionario que o aluno comecou e nao terminou (pausou/saiu no meio).

    Retomar este em vez de montar outro e o que torna o botao "Pausar" real:
    as respostas ja dadas continuam valendo e o aluno volta na questao em que
    parou, sem gastar outra chamada de IA.
    """

    query = db.query(Quiz).filter(
        Quiz.user_id == user.id,
        Quiz.kind == kind,
        Quiz.completed_at.is_(None),
        Quiz.retake_of.is_(None),  # tentativas de "Refazer" tem o fluxo proprio
    )
    if module is not None:
        query = query.filter(Quiz.module_id == module.id)
    else:
        query = query.filter(Quiz.module_id.is_(None))
    return query.order_by(Quiz.created_at.desc()).first()


def existing_answer(db: Session, quiz: Quiz, question: Question) -> Attempt | None:
    """Tentativa ja registrada para esta questao dentro deste questionario."""

    return (
        db.query(Attempt)
        .filter(Attempt.quiz_id == quiz.id, Attempt.question_id == question.id)
        .first()
    )


def register_answer(
    db: Session,
    user: User,
    quiz: Quiz,
    question: Question,
    alternative_id: str,
) -> tuple[Attempt, bool]:
    """Corrige a resposta no servidor e atualiza os contadores.

    Retorna (attempt, acertou). O gabarito nunca sai do servidor antes daqui.
    Reenviar a mesma questao nao conta pontos de novo (ver rota /answer).
    """

    is_correct = alternative_id == question.correct_alternative_id

    attempt = Attempt(
        user_id=user.id,
        question_id=question.id,
        quiz_id=quiz.id,
        alternative_chosen=alternative_id,
        correct=is_correct,
        level_at_time=user.level,
        is_diagnostic=False,
    )
    db.add(attempt)

    quiz.current_index = max(quiz.current_index, list(quiz.question_ids or []).index(question.id) + 1)
    if is_correct:
        quiz.correct_count += 1

    if quiz.module_id is not None:
        progress = (
            db.query(UserModuleProgress)
            .filter(
                UserModuleProgress.user_id == user.id,
                UserModuleProgress.module_id == quiz.module_id,
            )
            .first()
        )
        if progress is not None:
            progress.total_answers += 1
            if is_correct:
                progress.correct_answers += 1
            if progress.status == ModuleStatus.NAO_INICIADO:
                progress.status = ModuleStatus.EM_ANDAMENTO

    db.flush()
    return attempt, is_correct


def complete_quiz(db: Session, quiz: Quiz) -> None:
    if quiz.completed_at is None:
        quiz.completed_at = datetime.utcnow()
    db.flush()


def is_finished(quiz: Quiz) -> bool:
    return quiz.current_index >= len(quiz.question_ids or [])
