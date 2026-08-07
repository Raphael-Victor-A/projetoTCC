"""Autoria de questoes: um questionario inteiro por chamada.

Antes, cada questao custava uma requisicao ao Gemini — um questionario de 5
questoes eram 5 chamadas, 5 latencias somadas e 5 cobrancas. Aqui o
questionario inteiro sai de UMA chamada com `GeneratedQuestionBatch`.

Questoes invalidas nao derrubam o lote: sao descartadas individualmente e o
chamador completa o que faltar com o acervo do banco.
"""

from __future__ import annotations

import hashlib
import logging
import random
from dataclasses import dataclass, field

from app.ai import cache, client, prompts
from app.ai.client import AIUnavailable
from app.ai.schemas import GeneratedQuestion, GeneratedQuestionBatch
from app.models import Level

logger = logging.getLogger(__name__)

ALTERNATIVE_IDS = ["a", "b", "c", "d"]

# Mistura de dificuldade por tipo de questionario. Reforco puxa para baixo
# (o aluno acabou de tropecar); pratica e diagnostico espalham.
DIFFICULTY_MIX: dict[str, dict[Level, float]] = {
    "reforco": {Level.BASICO: 0.6, Level.INTERMEDIARIO: 0.4, Level.AVANCADO: 0.0},
    "pratica": {Level.BASICO: 0.25, Level.INTERMEDIARIO: 0.5, Level.AVANCADO: 0.25},
    "diagnostico": {Level.BASICO: 0.4, Level.INTERMEDIARIO: 0.4, Level.AVANCADO: 0.2},
}


@dataclass
class QuestionBatchSpec:
    """Tudo que descreve o lote pedido. Serve tambem de chave de cache."""

    kind: str  # "reforco" | "pratica" | "diagnostico"
    count: int
    level: Level
    subject: str = "Matematica"
    module_title: str = ""
    contents: list[str] = field(default_factory=list)
    objectives: list[str] = field(default_factory=list)
    focus_errors: list[str] = field(default_factory=list)

    def cache_key(self, avoid_statements: list[str]) -> str:
        payload = "|".join(
            [
                self.kind,
                str(self.count),
                self.level.value,
                self.subject,
                self.module_title,
                ",".join(self.contents),
                ",".join(self.focus_errors),
                ",".join(sorted(avoid_statements)[:20]),
            ]
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
        return f"questions:{digest}"


def difficulty_plan(count: int, kind: str) -> dict[Level, int]:
    """Converte a proporcao de dificuldade em contagem inteira que soma `count`."""

    mix = DIFFICULTY_MIX.get(kind, DIFFICULTY_MIX["pratica"])
    plan = {level: int(count * ratio) for level, ratio in mix.items()}
    remainder = count - sum(plan.values())
    # Sobra vai para os niveis de maior peso, do maior para o menor.
    for level, _ in sorted(mix.items(), key=lambda kv: kv[1], reverse=True):
        if remainder <= 0:
            break
        plan[level] += 1
        remainder -= 1
    return {level: n for level, n in plan.items() if n > 0}


def _describe_plan(plan: dict[Level, int]) -> str:
    return ", ".join(f"{n} questao(oes) de nivel {level.value}" for level, n in plan.items())


def _build_user_content(spec: QuestionBatchSpec, avoid_statements: list[str]) -> str:
    plan = difficulty_plan(spec.count, spec.kind)
    lines = [
        f"Disciplina: {spec.subject}",
        f"Quantidade de questoes: {spec.count}",
        f"Distribuicao de dificuldade obrigatoria: {_describe_plan(plan)}",
    ]
    if spec.module_title:
        lines.append(f"Modulo: {spec.module_title}")
    if spec.contents:
        lines.append("Conteudos que devem ser cobertos (distribua entre eles):")
        lines.extend(f"- {c}" for c in spec.contents)
    if spec.objectives:
        lines.append("Objetivos de aprendizagem do modulo:")
        lines.extend(f"- {o}" for o in spec.objectives)
    if spec.focus_errors:
        lines.append(
            "O aluno errou recentemente os pontos abaixo. Priorize-os, sem "
            "repetir os enunciados:"
        )
        lines.extend(f"- {e}" for e in spec.focus_errors[:8])
    if spec.kind == "reforco":
        lines.append(
            "Este e um QUESTIONARIO DE REFORCO: questoes mais guiadas, focadas "
            "em um conceito de base por vez, e nao em problemas aplicados longos."
        )
    lines.append("")
    lines.append(prompts.avoid_block(avoid_statements))
    # Semente textual: empurra o modelo para contextos diferentes a cada lote,
    # mesmo com temperatura baixa e o mesmo modulo.
    lines.append(f"\nSemente de variacao (use contextos diferentes): {random.randint(1000, 9999)}")
    return "\n".join(lines)


def validate(question: GeneratedQuestion) -> bool:
    ids = [a.id for a in question.alternatives]
    if len(question.alternatives) != 4 or sorted(ids) != ALTERNATIVE_IDS:
        return False
    if question.correct_alternative_id not in ids:
        return False
    if not question.statement.strip() or not question.directive_explanation.strip():
        return False
    texts = {a.text.strip().lower() for a in question.alternatives}
    if len(texts) != 4 or "" in texts:
        return False
    return True


def parse_difficulty(raw: str, default: Level) -> Level:
    try:
        return Level(raw.strip().lower())
    except (ValueError, AttributeError):
        return default


async def generate_batch(
    spec: QuestionBatchSpec,
    avoid_statements: list[str] | None = None,
) -> list[GeneratedQuestion]:
    """Gera o lote inteiro em uma chamada. Lista vazia = geracao indisponivel.

    Passa pelo cache com single-flight: requisicoes simultaneas identicas
    (dois alunos abrindo o mesmo reforco) compartilham uma unica chamada.
    """

    avoid = avoid_statements or []
    if not client.is_configured():
        return []

    system_prompt = (
        prompts.DIAGNOSTIC_BATCH_SYSTEM_PROMPT
        if spec.kind == "diagnostico"
        else prompts.QUESTION_BATCH_SYSTEM_PROMPT
    )
    user_content = _build_user_content(spec, avoid)

    async def _call() -> list[GeneratedQuestion]:
        parsed, latency_ms = await client.generate_structured(
            contents=user_content,
            system_instruction=system_prompt,
            response_schema=GeneratedQuestionBatch,
            # Um pouco acima da temperatura de feedback: variedade e requisito
            # do questionario, mas nao a ponto de baguncar o gabarito.
            temperature=0.6,
            # Lote grande gera resposta grande: o timeout acompanha.
            timeout=max(30.0, 6.0 * spec.count),
        )
        valid = [q for q in parsed.questions if validate(q)]
        discarded = len(parsed.questions) - len(valid)
        if discarded:
            logger.warning("Lote de questoes: %d questao(oes) invalida(s) descartada(s)", discarded)
        logger.info(
            "Lote de %d questao(oes) gerado em %.0f ms (%s/%s)",
            len(valid),
            latency_ms,
            spec.kind,
            spec.module_title or spec.subject,
        )
        return valid

    try:
        return await cache.get_or_create(spec.cache_key(avoid), _call)
    except AIUnavailable as exc:
        logger.warning("Geracao de questoes indisponivel: %s", exc)
        return []
