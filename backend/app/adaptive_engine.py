"""Motor adaptativo dos exercicios avulsos (/exercises/next).

O que mudou em relacao a versao anterior, e por que:

- a busca por uma questao nova comeca no banco. Se ja existe questao do nivel
  que o aluno nunca viu, ela e servida sem tocar na API;
- quando precisa gerar, gera um LOTE (PREFETCH_BATCH_SIZE) em vez de uma
  questao. As excedentes ficam no banco e alimentam os proximos exercicios de
  graca — uma chamada passa a cobrir varios exercicios;
- a chamada e assincrona, entao esperar o Gemini nao bloqueia o worker.

A regra pedagogica da janela movel nao mudou.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.ai.questions import QuestionBatchSpec, generate_batch
from app.models import LEVEL_ORDER, Module, Question, User
from app.quiz_service import (
    _fallback_questions,
    _persist_generated,
    _recent_statements,
    _reusable_questions,
    _seen_question_ids,
)
from app.study_plan import assign_initial_level  # noqa: F401  (reexport compativel)

logger = logging.getLogger(__name__)

WINDOW_SIZE = 5

# Reforco dispara com desempenho bem fraco no bloco (proximo de um terco de
# acerto, mesma proporcao da regra original pensada pra janela de 3).
REMEDIATION_MAX_CORRECT = WINDOW_SIZE // 3

# Quantas questoes sao geradas de uma vez quando o banco nao tem novidade.
# Amortiza o custo/latencia da chamada entre varios exercicios seguintes.
PREFETCH_BATCH_SIZE = 3


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


async def get_or_generate_question(
    user: User,
    db: Session,
    module: Module | None = None,
) -> Question | None:
    """Proxima questao do aluno, na ordem mais barata possivel."""

    seen_ids = _seen_question_ids(db, user)

    reusable = _reusable_questions(
        db,
        user,
        module,
        user.level,
        user.needs_remediation,
        limit=1,
        seen_ids=seen_ids,
    )
    if reusable:
        return reusable[0]

    spec = QuestionBatchSpec(
        kind="reforco" if user.needs_remediation else "pratica",
        count=PREFETCH_BATCH_SIZE,
        level=user.level,
        subject=module.subject.name if module is not None and module.subject else "Matematica",
        module_title=module.title if module else "",
        contents=list(module.contents or []) if module else [],
        objectives=list(module.objectives or []) if module else [],
    )
    generated = await generate_batch(spec, _recent_statements(db, user))
    if generated:
        saved = _persist_generated(db, user, module, generated, user.level, user.needs_remediation)
        fresh = [q for q in saved if q.id not in seen_ids]
        if fresh:
            return fresh[0]
        if saved:
            return saved[0]

    logger.warning("Geracao indisponivel; usando acervo de reserva")
    fallback = _fallback_questions(db, module, user.level, limit=1, exclude_ids=set())
    return fallback[0] if fallback else None
