from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models import FeedbackGroup, Level


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

    model_config = {"from_attributes": True}


class AnswerIn(BaseModel):
    question_id: int
    alternative_id: str


class DiagnosticSubmitIn(BaseModel):
    answers: list[AnswerIn]


class DiagnosticResultOut(BaseModel):
    correct_count: int
    total: int
    assigned_level: Level


class FeedbackOut(BaseModel):
    mode: FeedbackGroup
    content: str


class AnswerResultOut(BaseModel):
    correct: bool
    correct_alternative_id: str | None = None
    level: Level
    level_changed: bool
    needs_remediation: bool
    feedback: FeedbackOut | None = None


class ProgressOut(BaseModel):
    level: Level
    window_count: int
    window_correct: int
    needs_remediation: bool
    total_attempts: int
    total_correct: int


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
