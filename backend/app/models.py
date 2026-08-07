import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Level(str, enum.Enum):
    BASICO = "basico"
    INTERMEDIARIO = "intermediario"
    AVANCADO = "avancado"


LEVEL_ORDER = [Level.BASICO, Level.INTERMEDIARIO, Level.AVANCADO]


class FeedbackGroup(str, enum.Enum):
    DIRETIVO = "diretivo"
    SOCRATICO = "socratico"


class ModuleStatus(str, enum.Enum):
    NAO_INICIADO = "nao_iniciado"
    EM_ANDAMENTO = "em_andamento"
    CONCLUIDO = "concluido"


class QuizKind(str, enum.Enum):
    DIAGNOSTICO = "diagnostico"
    REFORCO = "reforco"
    PRATICA = "pratica"


class StepKind(str, enum.Enum):
    """Etapas do modulo de estudo. A trilha alterna avaliacao e aprendizagem
    (questionario -> mini aula -> questionario -> mini aula -> questionario),
    ver MODULE_STEPS."""

    QUIZ = "quiz"
    LESSON = "lesson"


# Sequencia fixa de etapas de um modulo. Trocar esta lista muda o fluxo
# inteiro do aluno; nada mais no codigo assume o tamanho dela.
MODULE_STEPS: list[StepKind] = [
    StepKind.QUIZ,
    StepKind.LESSON,
    StepKind.QUIZ,
    StepKind.LESSON,
    StepKind.QUIZ,
]


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # Grupo experimental sorteado no cadastro (mediacao diretiva vs socratica).
    # Nulo para contas admin, que nao participam do experimento.
    group: Mapped[FeedbackGroup | None] = mapped_column(Enum(FeedbackGroup), nullable=True)

    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)

    level: Mapped[Level] = mapped_column(Enum(Level), default=Level.BASICO, nullable=False)
    diagnostic_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    diagnostic_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Contadores da janela movel de exercicios avulsos, sem sobreposicao de
    # margens: resetados a zero toda vez que um bloco e avaliado
    # (ver adaptive_engine.py)
    window_count: Mapped[int] = mapped_column(Integer, default=0)
    window_correct: Mapped[int] = mapped_column(Integer, default=0)
    needs_remediation: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    attempts: Mapped[list["Attempt"]] = relationship(back_populates="user")
    module_progress: Mapped[list["UserModuleProgress"]] = relationship(back_populates="user")


class Subject(Base):
    """Disciplina da grade (BNCC). Populada por app/curriculum/bncc.py."""

    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    area: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    color: Mapped[str] = mapped_column(String(20), nullable=False, default="#6366f1")
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    modules: Mapped[list["Module"]] = relationship(
        back_populates="subject", order_by="Module.order_index"
    )


class Module(Base):
    """Modulo da grade: unidade minima de estudo, com objetivos de
    aprendizagem e conteudos relacionados (BNCC, 1o ano do Ensino Medio)."""

    __tablename__ = "modules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Ordem recomendada dentro da disciplina.
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[Level] = mapped_column(Enum(Level), default=Level.BASICO, nullable=False)

    objectives: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    contents: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    bncc_codes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    subject: Mapped["Subject"] = relationship(back_populates="modules")


class UserModuleProgress(Base):
    """Trilha personalizada do aluno: uma linha por (aluno, modulo), com
    prioridade derivada do diagnostico e progresso dentro de MODULE_STEPS."""

    __tablename__ = "user_module_progress"
    __table_args__ = (UniqueConstraint("user_id", "module_id", name="uq_user_module"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id"), nullable=False, index=True)

    # 0 = maior prioridade. Calculado em study_plan.py a partir do desempenho
    # do diagnostico e atualizado conforme o aluno responde.
    priority: Mapped[int] = mapped_column(Integer, default=100)
    status: Mapped[ModuleStatus] = mapped_column(
        Enum(ModuleStatus), default=ModuleStatus.NAO_INICIADO, nullable=False
    )

    # Indice da proxima etapa dentro de MODULE_STEPS.
    step_index: Mapped[int] = mapped_column(Integer, default=0)

    total_answers: Mapped[int] = mapped_column(Integer, default=0)
    correct_answers: Mapped[int] = mapped_column(Integer, default=0)
    diagnostic_total: Mapped[int] = mapped_column(Integer, default=0)
    diagnostic_correct: Mapped[int] = mapped_column(Integer, default=0)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped["User"] = relationship(back_populates="module_progress")
    module: Mapped["Module"] = relationship()


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[Level] = mapped_column(Enum(Level), nullable=False)
    topic: Mapped[str] = mapped_column(String(120), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)

    # Lista de alternativas: [{"id": "a", "text": "..."}, ...]
    alternatives: Mapped[list] = mapped_column(JSON, nullable=False)

    # Gabarito - NUNCA e serializado em resposta HTTP para o cliente.
    # Ver schemas.py (QuestionOut nao inclui este campo) e routers/exercises.py
    # (validacao roda 100% no servidor contra este valor).
    correct_alternative_id: Mapped[str] = mapped_column(String(10), nullable=False)

    directive_explanation: Mapped[str] = mapped_column(Text, nullable=False)

    is_remedial: Mapped[bool] = mapped_column(Boolean, default=False)
    is_diagnostic: Mapped[bool] = mapped_column(Boolean, default=False)

    # Vinculo com a grade BNCC (nulo para o acervo legado / exercicios avulsos).
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True, index=True)
    module_id: Mapped[int | None] = mapped_column(ForeignKey("modules.id"), nullable=True, index=True)

    # Questoes geradas pelo Gemini (owner_user_id preenchido) x banco de
    # reserva estatico do seed.py (generated=False, owner_user_id nulo),
    # usado como fallback quando a geracao falha ou repete algo ja visto.
    generated: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Hash do enunciado normalizado: deduplicacao barata de questoes geradas,
    # evitando gravar (e reapresentar) a mesma questao varias vezes.
    statement_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # Aposentadoria suave. Quando um modulo sai da grade, suas questoes viram
    # active=False em vez de serem apagadas: as tentativas ja registradas
    # continuam validas para o historico do aluno, mas a questao nunca mais e
    # sorteada. Toda selecao de questao filtra por este campo.
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DiagnosticSession(Base):
    """Sorteio do Questionario Diagnostico daquele aluno. Guardar os ids
    servidos e o que permite validar a submissao (o banco tem muito mais
    questoes do que as apresentadas) e garantir variedade entre execucoes."""

    __tablename__ = "diagnostic_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    question_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Quiz(Base):
    """Questionario completo, gerado de uma vez so. Todas as questoes ja
    existem no banco quando o aluno recebe a primeira - nenhuma chamada a
    API acontece no meio do questionario."""

    __tablename__ = "quizzes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    module_id: Mapped[int | None] = mapped_column(ForeignKey("modules.id"), nullable=True, index=True)
    kind: Mapped[QuizKind] = mapped_column(Enum(QuizKind), default=QuizKind.REFORCO, nullable=False)
    level: Mapped[Level] = mapped_column(Enum(Level), nullable=False)

    question_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    current_index: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Lesson(Base):
    """Mini aula exibida entre questionarios. Persistida e reaproveitada por
    cache_key: dois alunos no mesmo modulo/nivel nao geram duas chamadas."""

    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cache_key: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    module_id: Mapped[int | None] = mapped_column(ForeignKey("modules.id"), nullable=True, index=True)
    topic: Mapped[str] = mapped_column(String(160), nullable=False)
    level: Mapped[Level] = mapped_column(Enum(Level), nullable=False)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    intro: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # [{"heading": str, "body": str}]
    sections: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    key_concepts: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # [{"title": str, "statement": str, "solution": str}]
    examples: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Diagrama textual (mermaid) opcional, renderizado no front quando existe.
    diagram: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")

    generated: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LessonView(Base):
    """Registro de que o aluno concluiu uma mini aula (para progresso)."""

    __tablename__ = "lesson_views"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id", name="uq_user_lesson"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"), nullable=False, index=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    quiz_id: Mapped[int | None] = mapped_column(ForeignKey("quizzes.id"), nullable=True, index=True)
    alternative_chosen: Mapped[str] = mapped_column(String(10), nullable=False)
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    level_at_time: Mapped[Level] = mapped_column(Enum(Level), nullable=False)
    is_diagnostic: Mapped[bool] = mapped_column(Boolean, default=False)

    # Feedback pedagogico ja gerado para esta tentativa. Guardar o texto
    # completo permite reexibi-lo (recarregar a pagina, rever o historico)
    # sem gastar uma nova chamada a API.
    feedback_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="attempts")
    interaction_log: Mapped["InteractionLog | None"] = relationship(back_populates="attempt", uselist=False)


class InteractionLog(Base):
    """Telemetria das chamadas ao Orquestrador de IA, para analise estatistica do
    experimento (grupo diretivo vs socratico): latencia, modo, e se o filtro
    anti-vazamento precisou intervir."""

    __tablename__ = "interaction_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id"), nullable=False)
    mode: Mapped[FeedbackGroup] = mapped_column(Enum(FeedbackGroup), nullable=False)
    gemini_latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    leak_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_output_excerpt: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    attempt: Mapped["Attempt"] = relationship(back_populates="interaction_log")
