from pydantic import BaseModel, EmailStr, Field

from app.models import FeedbackGroup, Level, ModuleStatus, QuizKind


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: EmailStr
    group: FeedbackGroup | None
    level: Level
    diagnostic_completed: bool
    is_admin: bool

    model_config = {"from_attributes": True}


class AlternativeOut(BaseModel):
    id: str
    text: str


class QuestionOut(BaseModel):
    """Serializacao para o cliente. NAO inclui correct_alternative_id nem
    directive_explanation — o gabarito nunca sai do backend antes da submissao."""

    id: int
    level: Level
    topic: str
    statement: str
    alternatives: list[AlternativeOut]
    is_remedial: bool
    is_diagnostic: bool
    module_id: int | None = None
    subject_id: int | None = None

    model_config = {"from_attributes": True}


class AnswerIn(BaseModel):
    question_id: int
    alternative_id: str


# ---------------------------------------------------------------------------
# Diagnostico
# ---------------------------------------------------------------------------


class DiagnosticOut(BaseModel):
    """O diagnostico agora e sorteado por sessao: o cliente devolve o
    session_id na submissao para que o servidor corrija exatamente o
    conjunto que apresentou."""

    session_id: int
    questions: list[QuestionOut]


class DiagnosticSubmitIn(BaseModel):
    session_id: int | None = None
    answers: list[AnswerIn]


class FocusAreaOut(BaseModel):
    module_id: int
    module_title: str
    subject_name: str
    correct: int
    total: int
    accuracy: int


class WrongAnswerOut(BaseModel):
    """Questao que o aluno errou no diagnostico. So e devolvida DEPOIS da
    submissao, quando o gabarito ja nao influencia mais nada."""

    question_id: int
    statement: str
    chosen_text: str
    correct_text: str
    module_title: str
    topic: str


class DiagnosticResultOut(BaseModel):
    correct_count: int
    total: int
    assigned_level: Level
    focus_areas: list[FocusAreaOut] = []
    strengths: list[FocusAreaOut] = []
    wrong_answers: list[WrongAnswerOut] = []
    next_module_id: int | None = None


# ---------------------------------------------------------------------------
# Grade / trilha
# ---------------------------------------------------------------------------


class QuizSummaryOut(BaseModel):
    """Questionario ja concluido de um modulo (para a trilha mostrar o selo
    de desempenho e a barrinha acerto/erro de cada etapa)."""

    quiz_id: int
    correct_count: int
    total: int
    results: list[bool | None] = []


class ModuleOut(BaseModel):
    id: int
    slug: str
    title: str
    summary: str
    level: Level
    order_index: int
    objectives: list[str]
    contents: list[str]
    bncc_codes: list[str]
    status: ModuleStatus
    completion: int
    performance: int | None = None
    priority: int
    next_step: str | None = None
    # Posicao do aluno dentro de MODULE_STEPS (0 = nao comecou; == total = concluido).
    step_index: int = 0
    # Etapas do modulo, na ordem ("quiz" | "lesson"); a trilha desenha uma
    # bolinha por item, entao o front nao precisa conhecer MODULE_STEPS.
    steps: list[str] = []
    # Questionarios concluidos nesta passada pelo modulo, em ordem
    # (o 1o corresponde a 1a etapa "quiz", e assim por diante).
    quiz_results: list[QuizSummaryOut] = []


class SubjectOut(BaseModel):
    id: int
    slug: str
    name: str
    area: str
    color: str
    description: str
    completion: int
    performance: int | None = None
    modules: list[ModuleOut]


class RecommendationOut(BaseModel):
    module_id: int
    module_title: str
    subject_name: str
    subject_color: str
    reason: str
    next_step: str | None = None
    completion: int
    performance: int | None = None


class StudyPlanOut(BaseModel):
    level: Level
    diagnostic_completed: bool
    total_attempts: int
    total_correct: int
    accuracy: int
    modules_completed: int
    modules_total: int
    overall_completion: int
    current_module_id: int | None = None
    recommendations: list[RecommendationOut]
    weak_topics: list[str]
    subjects: list[SubjectOut]


# ---------------------------------------------------------------------------
# Questionarios
# ---------------------------------------------------------------------------


class QuizOut(BaseModel):
    """Questionario ja completo: todas as questoes vem nesta resposta, geradas
    em uma unica chamada a API."""

    id: int
    kind: QuizKind
    level: Level
    module_id: int | None
    module_title: str | None
    subject_name: str | None
    current_index: int
    total: int
    correct_count: int
    completed: bool
    questions: list[QuestionOut]
    # Resultado de cada questao, na mesma ordem de `questions`:
    # true = acertou, false = errou, null = ainda nao respondida.
    # Permite a barra de progresso mostrar acerto/erro (inclusive ao retomar).
    results: list[bool | None] = []


class QuizStartIn(BaseModel):
    module_id: int | None = None
    kind: QuizKind = QuizKind.REFORCO
    size: int | None = Field(default=None, ge=1, le=20)


class QuizAnswerOut(BaseModel):
    correct: bool
    correct_alternative_id: str | None = None
    explanation: str | None = None
    attempt_id: int
    answered_index: int
    total: int
    correct_count: int
    finished: bool
    # O feedback nao vem aqui: e transmitido em streaming por
    # GET /feedback/{attempt_id}/stream, para a correcao aparecer na hora.
    feedback_available: bool = False


class QuizResultOut(BaseModel):
    quiz_id: int
    correct_count: int
    total: int
    accuracy: int
    next_step: "NextStepOut"


# ---------------------------------------------------------------------------
# Mini aula
# ---------------------------------------------------------------------------


class LessonSectionOut(BaseModel):
    heading: str
    body: str


class LessonExampleOut(BaseModel):
    title: str
    statement: str
    solution: str


class LessonOut(BaseModel):
    id: int
    module_id: int | None
    topic: str
    level: Level
    title: str
    intro: str
    sections: list[LessonSectionOut]
    key_concepts: list[str]
    examples: list[LessonExampleOut]
    diagram: str | None = None
    summary: str
    generated: bool
    # Limite de "explicar de outro jeito" por aluno nesta aula.
    reexplain_limit: int = 0
    reexplain_remaining: int = 0
    # Reexplicacao ja gerada para este aluno (reexibida ao recarregar).
    reexplain_text: str | None = None


class NextStepOut(BaseModel):
    """Proxima etapa da trilha: questionario, mini aula ou modulo concluido."""

    kind: str  # "quiz" | "lesson" | "module_completed" | "diagnostic"
    module_id: int | None = None
    module_title: str | None = None
    subject_name: str | None = None
    lesson_id: int | None = None
    step_index: int = 0
    total_steps: int = 0
    message: str = ""


QuizResultOut.model_rebuild()


# ---------------------------------------------------------------------------
# Tutor
# ---------------------------------------------------------------------------


class TutorAskIn(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    module_id: int | None = None
    # None = o servidor decide pela heuristica de atualidade da pergunta.
    use_search: bool | None = None


class TutorSourceOut(BaseModel):
    title: str
    uri: str


# ---------------------------------------------------------------------------
# Exercicios avulsos (fluxo legado, mantido)
# ---------------------------------------------------------------------------


class FeedbackOut(BaseModel):
    mode: FeedbackGroup
    content: str


class HintIn(BaseModel):
    # Opcional: liga a dica ao questionario em andamento (telemetria).
    quiz_id: int | None = None


class HintOut(BaseModel):
    number: int
    content: str


class HintsOut(BaseModel):
    """Sempre devolve TODAS as dicas que o aluno ja recebeu nesta questao,
    para a tela se reconstruir mesmo depois de recarregar a pagina."""

    hints: list[HintOut]
    max_hints: int
    remaining: int
    # True quando a ultima dica e a de reserva por indisponibilidade da IA
    # (nao foi contada; o aluno pode pedir de novo depois).
    degraded: bool = False


class AnswerResultOut(BaseModel):
    correct: bool
    correct_alternative_id: str | None = None
    level: Level
    level_changed: bool
    needs_remediation: bool
    attempt_id: int | None = None
    feedback: FeedbackOut | None = None
    feedback_available: bool = False


class ProgressOut(BaseModel):
    level: Level
    window_count: int
    window_correct: int
    # Acerto/erro de cada exercicio do bloco atual, em ordem (tamanho = window_count).
    window_results: list[bool] = []
    needs_remediation: bool
    total_attempts: int
    total_correct: int


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------


class GroupStatsOut(BaseModel):
    group: FeedbackGroup
    total_users: int
    total_attempts: int
    correct_attempts: int
    accuracy: float
    level_distribution: dict[str, int]
    avg_gemini_latency_ms: float
    leak_detected_count: int
    leak_detected_rate: float
    fallback_used_count: int


class AdminStatsOut(BaseModel):
    total_students: int
    groups: list[GroupStatsOut]


class StudentOut(BaseModel):
    id: int
    email: EmailStr
    group: FeedbackGroup
    level: Level
    diagnostic_completed: bool

    model_config = {"from_attributes": True}


class StudentGroupIn(BaseModel):
    group: FeedbackGroup
