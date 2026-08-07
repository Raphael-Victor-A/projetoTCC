"""Mini aula entre questionarios.

Duas formas de consumo, propositalmente diferentes:

- `generate_lesson`: saida estruturada (secoes, conceitos, exemplos,
  diagrama, resumo). E o que fica persistido em `Lesson` e reaproveitado
  por outros alunos — custo amortizado.
- `stream_explanation`: texto corrido em markdown, streaming. Usado quando o
  aluno pede "explique de novo/de outro jeito" e quer ver a resposta nascendo.
"""

from __future__ import annotations

import hashlib
import logging
from typing import AsyncIterator

from app.ai import cache, client, prompts
from app.ai.client import AIUnavailable
from app.ai.schemas import GeneratedLesson
from app.models import Level

logger = logging.getLogger(__name__)


def lesson_cache_key(
    *,
    topic: str,
    level: Level,
    module_slug: str | None,
    focus_errors: list[str] | None = None,
) -> str:
    """Chave estavel da mini aula.

    Os erros do aluno entram na chave porque mudam o conteudo da aula; sao
    normalizados e truncados para que turmas com as mesmas lacunas caiam na
    mesma aula em vez de gerar uma copia por aluno.
    """

    focus = ",".join(sorted((e.strip().lower()[:60] for e in (focus_errors or [])))[:5])
    payload = f"{module_slug or ''}|{topic.lower()}|{level.value}|{focus}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _user_content(
    *,
    topic: str,
    level: Level,
    subject: str,
    objectives: list[str],
    contents: list[str],
    focus_errors: list[str],
) -> str:
    lines = [
        f"Disciplina: {subject}",
        f"Assunto da mini aula: {topic}",
        f"Nivel do aluno: {level.value}",
    ]
    if objectives:
        lines.append("Objetivos de aprendizagem a atingir:")
        lines.extend(f"- {o}" for o in objectives)
    if contents:
        lines.append("Conteudos relacionados:")
        lines.extend(f"- {c}" for c in contents)
    if focus_errors:
        lines.append(
            "O aluno acabou de errar os pontos abaixo. A aula precisa atacar "
            "exatamente essas lacunas:"
        )
        lines.extend(f"- {e}" for e in focus_errors[:6])
    return "\n".join(lines)


async def generate_lesson(
    *,
    topic: str,
    level: Level,
    subject: str = "Matematica",
    objectives: list[str] | None = None,
    contents: list[str] | None = None,
    focus_errors: list[str] | None = None,
) -> GeneratedLesson | None:
    """Mini aula estruturada. None quando a geracao esta indisponivel."""

    if not client.is_configured():
        return None

    user_content = _user_content(
        topic=topic,
        level=level,
        subject=subject,
        objectives=objectives or [],
        contents=contents or [],
        focus_errors=focus_errors or [],
    )
    key = "lesson:" + hashlib.sha256(user_content.encode("utf-8")).hexdigest()[:24]

    async def _call() -> GeneratedLesson:
        parsed, latency_ms = await client.generate_structured(
            contents=user_content,
            system_instruction=prompts.LESSON_SYSTEM_PROMPT,
            response_schema=GeneratedLesson,
            temperature=0.4,
            timeout=45.0,
        )
        logger.info("Mini aula '%s' gerada em %.0f ms", topic, latency_ms)
        return parsed

    try:
        return await cache.get_or_create(key, _call)
    except AIUnavailable as exc:
        logger.warning("Geracao de mini aula indisponivel: %s", exc)
        return None


async def stream_explanation(
    *,
    topic: str,
    level: Level,
    subject: str = "Matematica",
    focus_errors: list[str] | None = None,
) -> AsyncIterator[str]:
    """Explicacao em markdown, em streaming."""

    context = prompts.student_context_block(
        subject=subject, level=level.value, recent_errors=focus_errors
    )
    contents = f"Assunto da mini aula: {topic}\n\n{context}"
    async for piece in client.stream_text(
        contents=contents,
        system_instruction=prompts.LESSON_STREAM_SYSTEM_PROMPT,
        temperature=0.4,
    ):
        yield piece


def fallback_lesson(topic: str, objectives: list[str], contents: list[str]) -> GeneratedLesson:
    """Aula minima montada com os dados da propria grade.

    Serve para que o fluxo questionario -> aula -> questionario continue de pe
    sem chave de API ou com o Gemini fora do ar: o aluno ve os objetivos e os
    conteudos do modulo em vez de uma tela de erro.
    """

    from app.ai.schemas import LessonSection

    sections = [
        LessonSection(
            heading="O que voce vai estudar",
            body="\n".join(f"- {c}" for c in contents) or topic,
        ),
        LessonSection(
            heading="Onde focar",
            body=(
                "Retome os objetivos deste modulo antes do proximo questionario. "
                "Se algum item ainda parecer confuso, comece por ele."
            ),
        ),
    ]
    return GeneratedLesson(
        title=topic,
        intro=(
            "Esta e uma versao resumida da mini aula, montada a partir do plano "
            "do modulo. O conteudo completo volta assim que o tutor de IA estiver "
            "disponivel."
        ),
        sections=sections,
        key_concepts=objectives[:6] or contents[:6],
        examples=[],
        diagram="",
        summary="Revise os conceitos acima e siga para o proximo questionario.",
    )
