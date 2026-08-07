"""Trilha personalizada e painel do aluno.

Este modulo e o cerebro do dashboard: transforma respostas em prioridade de
estudo. A regra central e simples e auditavel — quanto pior o desempenho no
modulo, menor o numero de prioridade (0 = estudar primeiro) — para que o
aluno e o professor consigam explicar por que um conteudo apareceu no topo.

Tambem concentra o sorteio do Questionario Diagnostico, que precisa ser
aleatorio mas equilibrado entre disciplinas e niveis de dificuldade.
"""

from __future__ import annotations

import logging
import random
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    MODULE_STEPS,
    Attempt,
    Level,
    Module,
    ModuleStatus,
    Question,
    StepKind,
    Subject,
    User,
    UserModuleProgress,
)

logger = logging.getLogger(__name__)

# Proporcao alvo de dificuldade no diagnostico. Facil demais nao discrimina
# nivel; dificil demais desanima e tambem nao discrimina.
DIAGNOSTIC_LEVEL_MIX: dict[Level, float] = {
    Level.BASICO: 0.4,
    Level.INTERMEDIARIO: 0.4,
    Level.AVANCADO: 0.2,
}

# Acima disso o modulo conta como dominado; abaixo, como lacuna.
MASTERY_THRESHOLD = 0.7


# ---------------------------------------------------------------------------
# Sorteio do diagnostico
# ---------------------------------------------------------------------------


def _level_quota(size: int) -> dict[Level, int]:
    quota = {level: int(size * ratio) for level, ratio in DIAGNOSTIC_LEVEL_MIX.items()}
    remaining = size - sum(quota.values())
    for level, _ in sorted(DIAGNOSTIC_LEVEL_MIX.items(), key=lambda kv: kv[1], reverse=True):
        if remaining <= 0:
            break
        quota[level] += 1
        remaining -= 1
    return quota


def sample_diagnostic(db: Session, user: User, size: int | None = None) -> list[Question]:
    """Sorteia as questoes do diagnostico.

    Tres criterios ao mesmo tempo:
    - cobertura: distribui as questoes entre as disciplinas, em rodizio;
    - equilibrio: respeita a cota de dificuldade de DIAGNOSTIC_LEVEL_MIX;
    - variedade: embaralha tudo e evita repetir o que o aluno ja respondeu
      em diagnosticos anteriores (so reutiliza se faltar questao nova).
    """

    size = size or settings.diagnostic_size
    candidates = (
        db.query(Question)
        .filter(Question.is_diagnostic.is_(True), Question.active.is_(True))
        .all()
    )
    if not candidates:
        return []

    seen_ids = {
        row[0]
        for row in db.query(Attempt.question_id)
        .filter(Attempt.user_id == user.id, Attempt.is_diagnostic.is_(True))
        .all()
    }

    # Questoes ineditas primeiro; as ja vistas ficam como reserva.
    fresh = [q for q in candidates if q.id not in seen_ids]
    reserve = [q for q in candidates if q.id in seen_ids]
    random.shuffle(fresh)
    random.shuffle(reserve)
    pool = fresh + reserve

    by_subject: dict[int | None, list[Question]] = defaultdict(list)
    for question in pool:
        by_subject[question.subject_id].append(question)

    subjects = list(by_subject)
    random.shuffle(subjects)

    quota = _level_quota(size)
    selected: list[Question] = []
    selected_ids: set[int] = set()

    def take(question: Question) -> None:
        selected.append(question)
        selected_ids.add(question.id)
        if quota.get(question.level, 0) > 0:
            quota[question.level] -= 1

    # Rodizio entre disciplinas, respeitando a cota de dificuldade.
    exhausted = False
    while len(selected) < size and not exhausted:
        exhausted = True
        for subject_id in subjects:
            if len(selected) >= size:
                break
            bucket = by_subject[subject_id]
            pick = next(
                (q for q in bucket if q.id not in selected_ids and quota.get(q.level, 0) > 0),
                None,
            )
            if pick is None:
                continue
            take(pick)
            exhausted = False

    # Se a cota travou o preenchimento (banco desbalanceado), completa livre.
    if len(selected) < size:
        for question in pool:
            if len(selected) >= size:
                break
            if question.id not in selected_ids:
                take(question)

    random.shuffle(selected)
    return selected


def shuffled_alternatives(question: Question) -> list[dict]:
    """Alternativas em ordem aleatoria, mantendo o par id/texto intacto.

    Muda so a ordem de exibicao: o gabarito continua amarrado ao id, entao a
    correcao no servidor nao e afetada — e o aluno nao decora posicao.
    """

    alternatives = list(question.alternatives or [])
    random.shuffle(alternatives)
    return alternatives


# ---------------------------------------------------------------------------
# Trilha personalizada
# ---------------------------------------------------------------------------


@dataclass
class ModuleScore:
    module: Module
    total: int
    correct: int

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0


def _get_or_create_progress(db: Session, user: User, module: Module) -> UserModuleProgress:
    progress = (
        db.query(UserModuleProgress)
        .filter(
            UserModuleProgress.user_id == user.id,
            UserModuleProgress.module_id == module.id,
        )
        .first()
    )
    if progress is None:
        progress = UserModuleProgress(user_id=user.id, module_id=module.id)
        db.add(progress)
    return progress


def build_study_plan(db: Session, user: User, scores: dict[int, ModuleScore]) -> None:
    """(Re)monta a trilha do aluno a partir do desempenho por modulo.

    Prioridade final = desempenho medido (peso maior) + ordem pedagogica da
    grade (desempate). Assim um modulo mal avaliado sobe, mas dentro do mesmo
    desempenho a sequencia recomendada da BNCC e preservada.
    """

    modules = db.query(Module).order_by(Module.subject_id, Module.order_index).all()
    if not modules:
        return

    # Media por disciplina, usada para estimar modulos que o diagnostico nao
    # chegou a cobrir (o teste e curto, a grade e grande).
    subject_totals: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for score in scores.values():
        bucket = subject_totals[score.module.subject_id]
        bucket[0] += score.total
        bucket[1] += score.correct

    for module in modules:
        progress = _get_or_create_progress(db, user, module)
        score = scores.get(module.id)

        if score is not None and score.total:
            accuracy = score.accuracy
            measured = True
            progress.diagnostic_total = score.total
            progress.diagnostic_correct = score.correct
        else:
            totals = subject_totals.get(module.subject_id)
            accuracy = (totals[1] / totals[0]) if totals and totals[0] else 0.5
            measured = False

        # 0..100, menor = mais urgente. Modulos nao medidos ficam levemente
        # atras dos medidos com o mesmo desempenho (+5) para que a trilha
        # comece pelo que temos evidencia de que o aluno errou.
        base = int(round(accuracy * 100))
        if not measured:
            base += 5
        progress.priority = base * 10 + module.order_index

        if progress.status == ModuleStatus.NAO_INICIADO and progress.total_answers > 0:
            progress.status = ModuleStatus.EM_ANDAMENTO

    db.flush()


def apply_diagnostic_results(
    db: Session,
    user: User,
    results: list[tuple[Question, bool]],
) -> dict[int, ModuleScore]:
    """Converte as respostas do diagnostico em desempenho por modulo."""

    scores: dict[int, ModuleScore] = {}
    modules_by_id = {
        m.id: m
        for m in db.query(Module)
        .filter(Module.id.in_([q.module_id for q, _ in results if q.module_id]))
        .all()
    }

    for question, correct in results:
        module = modules_by_id.get(question.module_id) if question.module_id else None
        if module is None:
            continue
        score = scores.get(module.id)
        if score is None:
            score = ModuleScore(module=module, total=0, correct=0)
            scores[module.id] = score
        score.total += 1
        score.correct += 1 if correct else 0

    build_study_plan(db, user, scores)
    return scores


def assign_initial_level(correct_count: int, total: int) -> Level:
    """Nivel inicial a partir do desempenho global no diagnostico.

    Com um teste maior (12 questoes por padrao, contra 3 na versao anterior)
    da para usar tres faixas em vez de duas — a amostra ja sustenta essa
    distincao. Ver ressalva metodologica no README.
    """

    if total <= 0:
        return Level.BASICO
    ratio = correct_count / total
    if ratio >= 0.8:
        return Level.AVANCADO
    if ratio >= 0.5:
        return Level.INTERMEDIARIO
    return Level.BASICO


# ---------------------------------------------------------------------------
# Progresso e proximos passos
# ---------------------------------------------------------------------------


def next_step(progress: UserModuleProgress) -> StepKind | None:
    """Proxima etapa do modulo, ou None quando o modulo terminou."""

    if progress.step_index >= len(MODULE_STEPS):
        return None
    return MODULE_STEPS[progress.step_index]


def advance_step(db: Session, progress: UserModuleProgress) -> StepKind | None:
    progress.step_index += 1
    if progress.step_index >= len(MODULE_STEPS):
        progress.status = ModuleStatus.CONCLUIDO
    else:
        progress.status = ModuleStatus.EM_ANDAMENTO
    db.flush()
    return next_step(progress)


def completion_percent(progress: UserModuleProgress) -> int:
    steps = len(MODULE_STEPS)
    if steps == 0:
        return 100
    return min(100, int(round(progress.step_index / steps * 100)))


def module_performance(progress: UserModuleProgress) -> int | None:
    if not progress.total_answers:
        if progress.diagnostic_total:
            return int(round(progress.diagnostic_correct / progress.diagnostic_total * 100))
        return None
    return int(round(progress.correct_answers / progress.total_answers * 100))


def ensure_plan(db: Session, user: User) -> None:
    """Garante que a trilha do aluno cubra a grade atual.

    Cobre dois casos: aluno sem trilha nenhuma (conta criada antes da grade
    existir) e modulos novos adicionados a grade depois que a trilha do aluno
    ja tinha sido montada. Nos dois, os modulos faltantes entram na ordem
    pedagogica pura, sem mexer nas prioridades ja calculadas dos outros.
    """

    module_ids = {row[0] for row in db.query(Module.id).all()}
    if not module_ids:
        return

    covered = {
        row[0]
        for row in db.query(UserModuleProgress.module_id)
        .filter(UserModuleProgress.user_id == user.id)
        .all()
    }
    missing = module_ids - covered
    if not missing:
        return

    if not covered:
        # Nenhuma trilha ainda: monta a grade inteira de uma vez.
        build_study_plan(db, user, {})
        db.commit()
        return

    for module in db.query(Module).filter(Module.id.in_(missing)).all():
        progress = _get_or_create_progress(db, user, module)
        # Sem desempenho medido, entra como "meio" (50%) com o desempate da
        # ordem recomendada — nem na frente nem no fim da fila.
        progress.priority = 55 * 10 + module.order_index
    db.commit()


def recommended_progress(db: Session, user: User, limit: int = 5) -> list[UserModuleProgress]:
    """Proximos modulos recomendados: maior prioridade, ainda nao concluidos."""

    return (
        db.query(UserModuleProgress)
        .filter(
            UserModuleProgress.user_id == user.id,
            UserModuleProgress.status != ModuleStatus.CONCLUIDO,
        )
        .order_by(UserModuleProgress.priority.asc(), UserModuleProgress.module_id.asc())
        .limit(limit)
        .all()
    )


def current_progress(db: Session, user: User) -> UserModuleProgress | None:
    """Modulo em que o aluno deve continuar agora."""

    in_progress = (
        db.query(UserModuleProgress)
        .filter(
            UserModuleProgress.user_id == user.id,
            UserModuleProgress.status == ModuleStatus.EM_ANDAMENTO,
        )
        .order_by(UserModuleProgress.priority.asc())
        .first()
    )
    if in_progress is not None:
        return in_progress
    recommended = recommended_progress(db, user, limit=1)
    return recommended[0] if recommended else None


def weak_topics(db: Session, user: User, limit: int = 8) -> list[str]:
    """Assuntos em que o aluno errou recentemente.

    Alimenta os prompts de reforco e de mini aula: e o que faz o conteudo
    gerado atacar a lacuna real em vez de repetir a teoria inteira.
    """

    rows = (
        db.query(Question.topic)
        .join(Attempt, Attempt.question_id == Question.id)
        .filter(Attempt.user_id == user.id, Attempt.correct.is_(False))
        .order_by(Attempt.created_at.desc())
        .limit(40)
        .all()
    )
    topics: list[str] = []
    for (topic,) in rows:
        if topic and topic not in topics:
            topics.append(topic)
        if len(topics) >= limit:
            break
    return topics


def subject_overview(db: Session, user: User) -> list[dict]:
    """Resumo por disciplina para o dashboard (uma consulta por tabela)."""

    subjects = db.query(Subject).order_by(Subject.order_index).all()
    modules = db.query(Module).order_by(Module.subject_id, Module.order_index).all()
    progresses = {
        p.module_id: p
        for p in db.query(UserModuleProgress).filter(UserModuleProgress.user_id == user.id).all()
    }

    modules_by_subject: dict[int, list[Module]] = defaultdict(list)
    for module in modules:
        modules_by_subject[module.subject_id].append(module)

    overview: list[dict] = []
    for subject in subjects:
        subject_modules = modules_by_subject.get(subject.id, [])
        if not subject_modules:
            continue

        module_rows = []
        completion_sum = 0
        performance_values: list[int] = []
        for module in subject_modules:
            progress = progresses.get(module.id)
            completion = completion_percent(progress) if progress else 0
            performance = module_performance(progress) if progress else None
            completion_sum += completion
            if performance is not None:
                performance_values.append(performance)
            module_rows.append(
                {
                    "id": module.id,
                    "slug": module.slug,
                    "title": module.title,
                    "summary": module.summary,
                    "level": module.level,
                    "order_index": module.order_index,
                    "objectives": module.objectives,
                    "contents": module.contents,
                    "bncc_codes": module.bncc_codes,
                    "status": progress.status if progress else ModuleStatus.NAO_INICIADO,
                    "completion": completion,
                    "performance": performance,
                    "priority": progress.priority if progress else 999,
                    "next_step": (next_step(progress).value if progress and next_step(progress) else None),
                }
            )

        overview.append(
            {
                "id": subject.id,
                "slug": subject.slug,
                "name": subject.name,
                "area": subject.area,
                "color": subject.color,
                "description": subject.description,
                "completion": int(round(completion_sum / len(subject_modules))),
                "performance": (
                    int(round(sum(performance_values) / len(performance_values)))
                    if performance_values
                    else None
                ),
                "modules": module_rows,
            }
        )
    return overview
