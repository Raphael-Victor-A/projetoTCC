import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text
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

    # Contadores da janela movel de 3 exercicios, sem sobreposicao de margens:
    # resetados a zero toda vez que um bloco de 3 e avaliado (ver adaptive_engine.py)
    window_count: Mapped[int] = mapped_column(Integer, default=0)
    window_correct: Mapped[int] = mapped_column(Integer, default=0)
    needs_remediation: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    attempts: Mapped[list["Attempt"]] = relationship(back_populates="user")


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

    # Questoes geradas pelo Gemini (owner_user_id preenchido) x banco de
    # reserva estatico do seed.py (generated=False, owner_user_id nulo),
    # usado como fallback quando a geracao falha ou repete algo ja visto.
    generated: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    alternative_chosen: Mapped[str] = mapped_column(String(10), nullable=False)
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    level_at_time: Mapped[Level] = mapped_column(Enum(Level), nullable=False)
    is_diagnostic: Mapped[bool] = mapped_column(Boolean, default=False)
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
