"""Compatibilidade: o Orquestrador de IA virou o pacote `app.ai`.

Este modulo existe so para nao quebrar imports antigos
(`from app import gemini_orchestrator`). Codigo novo deve importar
diretamente de `app.ai`.

Atencao: as funcoes agora sao ASSINCRONAS. A troca foi deliberada — o
gargalo do fluxo era esperar o Gemini de forma bloqueante dentro do request,
serializando alunos no mesmo worker.
"""

from app.ai import cache, client, feedback, lessons, questions, search  # noqa: F401
from app.ai.client import AIUnavailable  # noqa: F401
from app.ai.feedback import generate_feedback  # noqa: F401
from app.ai.questions import QuestionBatchSpec, generate_batch  # noqa: F401
from app.ai.schemas import GeneratedQuestion, GeneratedQuestionBatch  # noqa: F401

__all__ = [
    "AIUnavailable",
    "GeneratedQuestion",
    "GeneratedQuestionBatch",
    "QuestionBatchSpec",
    "cache",
    "client",
    "feedback",
    "generate_batch",
    "generate_feedback",
    "lessons",
    "questions",
    "search",
]
