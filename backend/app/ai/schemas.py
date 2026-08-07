"""Schemas de saida estruturada do Gemini (`response_schema`).

Sao propositalmente simples (so str/bool/list de modelos): o schema vira
JSON Schema enviado a API, e tipos exoticos degradam a qualidade da
aderencia do modelo ao formato.
"""

from pydantic import BaseModel


class GeminiFeedback(BaseModel):
    """O campo contains_final_answer e o modelo se auto-reportando se revelou
    a resposta certa — usado junto com o filtro heuristico como segunda camada
    de checagem (defesa em profundidade, ver leak filter em feedback.py)."""

    content: str
    contains_final_answer: bool


class GeneratedAlternative(BaseModel):
    id: str
    text: str


class GeneratedQuestion(BaseModel):
    """Validada estruturalmente apos o parse (4 alternativas com ids a/b/c/d
    unicos, gabarito entre elas) — nao ha verificacao matematica formal do
    gabarito, so estrutural; ver ressalva no README."""

    topic: str
    difficulty: str  # "basico" | "intermediario" | "avancado"
    statement: str
    alternatives: list[GeneratedAlternative]
    correct_alternative_id: str
    directive_explanation: str


class GeneratedQuestionBatch(BaseModel):
    """Questionario inteiro em uma unica resposta — o formato que permite
    trocar N chamadas a API por 1 (ver questions.generate_quiz_questions)."""

    questions: list[GeneratedQuestion]


class LessonSection(BaseModel):
    heading: str
    body: str


class LessonExample(BaseModel):
    title: str
    statement: str
    solution: str


class GeneratedLesson(BaseModel):
    title: str
    intro: str
    sections: list[LessonSection]
    key_concepts: list[str]
    examples: list[LessonExample]
    # Diagrama em sintaxe Mermaid (ou string vazia quando nao fizer sentido).
    diagram: str
    summary: str
