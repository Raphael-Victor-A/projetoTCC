import logging
import random

from sqlalchemy.orm import Session

from app import gemini_orchestrator
from app.models import LEVEL_ORDER, Attempt, Level, Question, User
from app.rate_limit import enforce_gemini_rate_limit

logger = logging.getLogger(__name__)

WINDOW_SIZE = 5

# Reforco dispara com desempenho bem fraco no bloco (proximo de um terco de
# acerto, mesma proporcao da regra original pensada pra janela de 3).
REMEDIATION_MAX_CORRECT = WINDOW_SIZE // 3

# Quantas perguntas recentes do aluno sao lembradas pra pedir ao Gemini que
# nao repita (e para o fallback estatico escolher algo ainda nao visto).
RECENT_HISTORY_SIZE = 20


def evaluate_window(user: User) -> tuple[bool, bool]:
    """Avalia o bloco de WINDOW_SIZE exercicios (janela movel, sem
    sobreposicao de margens: os contadores so resetam quando o bloco fecha).

      100% corretas -> promove de nivel
      <= REMEDIATION_MAX_CORRECT corretas -> aciona bloco de reforco conceitual
      qualquer coisa no meio -> mantem nivel, sem reforco (banda de transicao)

    Retorna (promoted, entered_remediation).
    """
    correct = user.window_correct
    promoted = False
    entered_remediation = False

    if correct == WINDOW_SIZE:
        idx = LEVEL_ORDER.index(user.level)
        if idx < len(LEVEL_ORDER) - 1:
            user.level = LEVEL_ORDER[idx + 1]
            promoted = True
        user.needs_remediation = False
    elif correct <= REMEDIATION_MAX_CORRECT:
        user.needs_remediation = True
        entered_remediation = True
    else:
        user.needs_remediation = False

    user.window_count = 0
    user.window_correct = 0
    return promoted, entered_remediation


def record_attempt(user: User, correct: bool) -> tuple[bool, bool]:
    """Registra resultado no contador da janela atual. So avalia o bloco
    quando ele fecha em WINDOW_SIZE exercicios (sem sobreposicao)."""
    user.window_count += 1
    if correct:
        user.window_correct += 1

    if user.window_count >= WINDOW_SIZE:
        return evaluate_window(user)
    return False, False


def _recent_statements(user: User, db: Session) -> list[str]:
    rows = (
        db.query(Question.statement)
        .join(Attempt, Attempt.question_id == Question.id)
        .filter(Attempt.user_id == user.id, Attempt.is_diagnostic.is_(False))
        .order_by(Attempt.created_at.desc())
        .limit(RECENT_HISTORY_SIZE)
        .all()
    )
    return [r[0] for r in rows]


def _fallback_static_question(user: User, db: Session, seen_statements: set[str]) -> Question | None:
    """Banco de reserva (seed.py): usado quando o Gemini falha, devolve
    schema invalido, ou insiste em repetir uma pergunta ja vista."""
    query = db.query(Question).filter(
        Question.level == user.level,
        Question.is_diagnostic.is_(False),
        Question.generated.is_(False),
        Question.is_remedial.is_(user.needs_remediation),
    )
    candidates = query.all()
    unseen = [q for q in candidates if q.statement not in seen_statements]
    if unseen:
        return random.choice(unseen)
    if candidates:
        return random.choice(candidates)

    # Ultimo recurso: qualquer questao de reserva do nivel, remedial ou nao.
    any_question = db.query(Question).filter(
        Question.level == user.level, Question.is_diagnostic.is_(False), Question.generated.is_(False)
    ).all()
    return random.choice(any_question) if any_question else None


def get_or_generate_question(user: User, db: Session) -> Question | None:
    """Fonte principal de exercicios: pede ao Gemini para escrever uma
    questao inedita para o nivel/estagio atual do aluno, evitando repetir
    o que ele ja respondeu. Se a IA falhar, devolver algo mal formado, ou
    insistir em repetir, cai no banco de reserva estatico (seed.py) —
    disponibilidade da atividade importa mais do que novidade."""
    seen = set(_recent_statements(user, db))

    try:
        enforce_gemini_rate_limit(user.id)
        generated = gemini_orchestrator.generate_question(
            level=user.level,
            is_remedial=user.needs_remediation,
            avoid_statements=list(seen),
        )
        if generated.statement in seen:
            logger.warning("Gemini repetiu uma pergunta ja vista, usando banco de reserva")
            raise ValueError("pergunta repetida")

        question = Question(
            level=user.level,
            topic=generated.topic,
            statement=generated.statement,
            alternatives=[a.model_dump() for a in generated.alternatives],
            correct_alternative_id=generated.correct_alternative_id,
            directive_explanation=generated.directive_explanation,
            is_remedial=user.needs_remediation,
            is_diagnostic=False,
            generated=True,
            owner_user_id=user.id,
        )
        db.add(question)
        db.flush()
        return question
    except Exception:
        logger.exception("Falha ao gerar questao via Gemini, usando banco de reserva")
        return _fallback_static_question(user, db, seen)


def assign_initial_level(correct_count: int, total: int) -> Level:
    """Passo 1: assinatura inicial de proficiencia a partir do teste de 3
    problemas de nivelamento basico. Amostra pequena (n=3) — ver ressalva
    metodologica no README — entao o mapeamento e conservador."""
    if total <= 0:
        return Level.BASICO
    ratio = correct_count / total
    if ratio == 1.0:
        return Level.INTERMEDIARIO
    return Level.BASICO
