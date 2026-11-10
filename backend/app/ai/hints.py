"""Dica durante a questao (botao "Preciso de ajuda").

Diferente do feedback pos-erro (feedback.py), a dica acontece ANTES da
resposta: o aluno ainda vai escolher uma alternativa. Por isso a regra e a
mesma para os dois grupos do experimento — nenhuma dica pode revelar a
resposta, nem no grupo diretivo.

Dicas sao graduais (1 = o que a questao pede, 2 = primeiro passo, 3 = quase
la), com no maximo MAX_HINTS por questao.

Filtro anti-vazamento, em tres camadas (qualquer uma descarta a dica e usa a
de reserva):
1. o proprio Gemini se auto-reporta (contains_final_answer);
2. o texto da alternativa correta aparece na dica (mesmo filtro do feedback);
3. EXCLUSIVO da dica: o numero da resposta aparece na dica sem estar no
   enunciado. Necessario porque "12% de 8000 da 960" nao contem o texto
   "960 eleitores", mas entrega a resposta do mesmo jeito. Tambem barra a
   dica que fala de alternativas especificas ("a alternativa b..."), ja que
   eliminar opcoes e uma forma de entregar a resposta.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.ai import client, prompts
from app.ai.client import AIUnavailable
from app.ai.feedback import _alternative_text, _heuristic_leak_detected, _normalize
from app.ai.schemas import GeminiHint
from app.models import Question

logger = logging.getLogger(__name__)

MAX_HINTS = 3

_FALLBACK_HINTS = [
    "Vamos com calma: releia o enunciado e tente dizer, com suas palavras, o "
    "que exatamente a questao quer descobrir. Esta questao e sobre {topic}. "
    "Que ideia ou formula desse assunto pode ajudar aqui?",
    "Separe os dados que o enunciado te da e o que ele pede. Qual desses "
    "dados voce usaria primeiro? Tente escrever a primeira conta ou relacao "
    "antes de olhar as alternativas.",
    "Faca a resolucao inteira no papel, passo a passo, sem olhar as "
    "alternativas. So no final compare o seu resultado com as opcoes. Se "
    "nenhuma bater, confira cada passo de novo.",
]

_QUOTA_NOTE = (
    "(O tutor de IA esta no limite de uso agora, entao esta e uma dica geral. "
    "Tente pedir de novo em alguns instantes.)"
)

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
_ALTERNATIVE_MENTION_RE = re.compile(r"\b(alternativa|letra|opcao)\s*[a-e]\b")


@dataclass
class HintResult:
    content: str
    leak_detected: bool
    fallback_used: bool
    latency_ms: float
    # True quando a IA estava indisponivel: a dica de reserva e devolvida ao
    # aluno, mas NAO conta como uma das dicas dele (assim ele pode pedir a dica
    # de verdade quando a API voltar).
    degraded: bool = False


def _numbers(text: str) -> set[str]:
    return {n.replace(",", ".") for n in _NUMBER_RE.findall(text or "")}


def _answer_number_leaked(hint: str, correct_text: str, statement: str) -> bool:
    """O numero que so existe na resposta correta apareceu na dica?"""

    answer_numbers = _numbers(correct_text) - _numbers(statement)
    if not answer_numbers:
        return False
    return answer_numbers <= _numbers(hint)


def leak_detected(question: Question, hint: str) -> bool:
    correct_text = _alternative_text(question, question.correct_alternative_id)
    if _heuristic_leak_detected(hint, correct_text, question.correct_alternative_id):
        return True
    if _answer_number_leaked(hint, correct_text, question.statement):
        return True
    return bool(_ALTERNATIVE_MENTION_RE.search(_normalize(hint)))


def fallback_hint(question: Question, hint_number: int) -> str:
    template = _FALLBACK_HINTS[min(hint_number, len(_FALLBACK_HINTS)) - 1]
    return template.format(topic=question.topic or "este conteudo")


def _contents(question: Question, hint_number: int, previous: list[str]) -> str:
    alternatives = "\n".join(
        f"{a.get('id')}) {a.get('text')}" for a in (question.alternatives or [])
    )
    previous_block = (
        "\n".join(f"Dica {i}: {text}" for i, text in enumerate(previous, start=1))
        if previous
        else "Nenhuma dica dada ainda."
    )
    # A resolucao vai como material do professor: ajuda a IA a orientar na
    # direcao certa (sem ela, um modelo pequeno pode errar a conta e dar uma
    # dica que leva ao lugar errado). O filtro acima e o que garante que ela
    # nao vaze para o aluno.
    return f"""Questao que o aluno esta resolvendo:
<<<ENUNCIADO>>>
{question.statement}
<<<FIM_ENUNCIADO>>>

Alternativas apresentadas ao aluno:
<<<ALTERNATIVAS>>>
{alternatives}
<<<FIM_ALTERNATIVAS>>>

Material do professor (CONFIDENCIAL, nunca revele ao aluno; use so para
orientar na direcao certa):
<<<RESOLUCAO>>>
{question.directive_explanation}
<<<FIM_RESOLUCAO>>>

Dicas ja dadas a este aluno nesta questao. Ele so as LEU e pediu mais ajuda;
nao respondeu nada, entao nao assuma que entendeu ou fez algum passo:
<<<DICAS_ANTERIORES>>>
{previous_block}
<<<FIM_DICAS_ANTERIORES>>>

Escreva agora a DICA {hint_number} de {MAX_HINTS}.
"""


async def generate_hint(question: Question, hint_number: int, previous: list[str]) -> HintResult:
    """Gera a dica ja filtrada. Nunca levanta: falha vira dica de reserva."""

    try:
        parsed, latency_ms = await client.generate_structured(
            contents=_contents(question, hint_number, previous),
            system_instruction=prompts.HINT_SYSTEM_PROMPT,
            response_schema=GeminiHint,
            temperature=0.3,
        )
    except AIUnavailable as exc:
        logger.warning("Dica indisponivel: %s", exc)
        content = fallback_hint(question, hint_number)
        if isinstance(exc, client.AIQuotaExceeded):
            content = f"{content}\n\n{_QUOTA_NOTE}"
        return HintResult(content, False, True, 0.0, degraded=True)

    content = (parsed.content or "").strip()
    if not content:
        return HintResult(fallback_hint(question, hint_number), False, True, latency_ms)

    if parsed.contains_final_answer or leak_detected(question, content):
        logger.info("Dica descartada pelo filtro anti-vazamento (questao %s)", question.id)
        return HintResult(fallback_hint(question, hint_number), True, True, latency_ms)

    return HintResult(content, False, False, latency_ms)
