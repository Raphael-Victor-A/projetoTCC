"""Painel de avaliacao da IA (somente admin).

Duas partes:

1. Metricas do uso real (GET /admin/evaluation): tudo sai da telemetria que o
   sistema ja grava — `interaction_logs` (feedback pos-erro) e
   `hint_requests` (dicas). Nenhuma chamada nova ao Gemini.

2. Revisao manual (GET/PUT/DELETE /admin/evaluation/review/...): o admin le o
   texto ORIGINAL da IA e marca se ele entregava a resposta, ou confere o
   gabarito de uma questao gerada. Comparando as marcacoes com a decisao
   automatica do filtro, o painel calcula precisao e revocacao do filtro
   anti-vazamento e a taxa de gabaritos errados.

Sobre a amostragem: textos barrados e textos liberados pelo filtro sao
estratos de tamanhos muito diferentes. Por isso as taxas sao calculadas por
estrato (precisao = entre os barrados revisados; escape = entre os liberados
revisados) e a revocacao e estimada projetando cada taxa no total do estrato.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Attempt,
    FeedbackGroup,
    HintRequest,
    InteractionLog,
    Lesson,
    LessonView,
    Module,
    Question,
    ReviewLabel,
    User,
)
from app.security import get_current_admin

router = APIRouter(prefix="/admin/evaluation", tags=["admin"])

ReviewKind = Literal["feedback", "hint", "question"]
LEAK_VERDICTS = {"vazou", "nao_vazou"}
QUESTION_VERDICTS = {"correto", "errado", "ambiguo"}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class LatencyOut(BaseModel):
    n: int
    avg_ms: float
    p50_ms: float
    p95_ms: float


class ChannelOut(BaseModel):
    """Feedback pos-erro ou dica: como a IA se comportou no uso real."""

    total: int  # textos entregues ao aluno
    ai_calls: int  # chamadas que a IA respondeu
    unavailable: int  # IA fora do ar / cota: texto de reserva
    filtered: int  # barrados pelo filtro anti-vazamento
    filter_scope: int  # chamadas sujeitas ao filtro (base da taxa)
    filtered_rate: float
    reused: int  # entregues sem chamada nova (reaproveitamento)
    latency: LatencyOut


class ConfusionOut(BaseModel):
    reviewed: int
    reviewable: int
    flagged_total: int
    passed_total: int
    tp: int  # barrado e vazava
    fp: int  # barrado sem vazar
    fn: int  # liberado e vazava (chegou ao aluno)
    tn: int  # liberado e nao vazava
    precision: float | None
    escape_rate: float | None  # entre os liberados revisados, quantos vazavam
    recall_estimate: float | None
    leaks_reaching_students_estimate: float | None


class QuestionReviewOut(BaseModel):
    generated_total: int
    reviewed: int
    correct: int
    wrong: int
    ambiguous: int
    wrong_rate: float | None


class ContentOut(BaseModel):
    generated_questions: int
    bank_questions: int
    retired_questions: int
    lessons_generated: int
    lesson_views: int
    lesson_calls_saved: int


class DailyOut(BaseModel):
    date: str
    feedback: int
    hints: int


class EvaluationOut(BaseModel):
    since: datetime | None
    feedback: ChannelOut
    hints: ChannelOut
    feedback_by_mode: dict[str, int]
    content: ContentOut
    daily: list[DailyOut]
    leak_review: dict[str, ConfusionOut]  # "feedback", "hint", "total"
    question_review: QuestionReviewOut


class ReviewQuestionOut(BaseModel):
    id: int
    topic: str
    module_title: str | None
    statement: str
    alternatives: list[dict]
    correct_alternative_id: str
    explanation: str
    active: bool


class ReviewItemOut(BaseModel):
    kind: ReviewKind
    id: int
    created_at: datetime
    question: ReviewQuestionOut
    ai_text: str | None = None  # texto original da IA
    shown_text: str | None = None  # o que o aluno viu
    filter_flagged: bool | None = None
    mode: str | None = None
    hint_number: int | None = None
    chosen_alternative_id: str | None = None
    verdict: str | None = None
    note: str | None = None


class ReviewPageOut(BaseModel):
    items: list[ReviewItemOut]
    total: int


class ReviewIn(BaseModel):
    verdict: str
    note: str | None = Field(default=None, max_length=2000)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (k - lo)


def _latency(values: list[float]) -> LatencyOut:
    vals = sorted(v for v in values if v and v > 0)
    if not vals:
        return LatencyOut(n=0, avg_ms=0, p50_ms=0, p95_ms=0)
    return LatencyOut(
        n=len(vals),
        avg_ms=sum(vals) / len(vals),
        p50_ms=_percentile(vals, 0.5),
        p95_ms=_percentile(vals, 0.95),
    )


def _rate(num: int, den: int) -> float | None:
    return num / den if den else None


def _labels(db: Session, kind: str) -> dict[int, ReviewLabel]:
    rows = db.query(ReviewLabel).filter(ReviewLabel.item_type == kind).all()
    return {r.item_id: r for r in rows}


def _is_unavailable_log(log: InteractionLog) -> bool:
    # Feedback degradado: IA nao respondeu, texto de reserva sem chamada valida.
    return bool(log.fallback_used and not log.leak_detected and not log.raw_output_excerpt)


def _reviewable_feedback(db: Session):
    """Feedbacks socraticos que a IA respondeu (so eles passam pelo filtro)."""
    return db.query(InteractionLog).filter(
        InteractionLog.mode == FeedbackGroup.SOCRATICO,
        InteractionLog.raw_output_excerpt.isnot(None),
        InteractionLog.raw_output_excerpt != "",
    )


def _reviewable_hints(db: Session):
    """Dicas geradas (nao reaproveitadas) cujo texto original e conhecido:
    as liberadas (o texto mostrado e o original) e as barradas que ja
    gravaram o original em `raw_output`."""
    return db.query(HintRequest).filter(
        HintRequest.reused.is_(False),
        or_(HintRequest.raw_output.isnot(None), HintRequest.fallback_used.is_(False)),
    )


def _confusion(flags: dict[int, bool], labels: dict[int, ReviewLabel]) -> ConfusionOut:
    tp = fp = fn = tn = 0
    for item_id, label in labels.items():
        if item_id not in flags or label.verdict not in LEAK_VERDICTS:
            continue
        leaked = label.verdict == "vazou"
        if flags[item_id]:
            tp += leaked
            fp += not leaked
        else:
            fn += leaked
            tn += not leaked
    flagged_total = sum(1 for f in flags.values() if f)
    passed_total = len(flags) - flagged_total
    precision = _rate(tp, tp + fp)
    escape = _rate(fn, fn + tn)

    recall = None
    reaching = None
    if escape is not None:
        reaching = escape * passed_total
    if precision is not None and escape is not None:
        est_tp = precision * flagged_total
        est_fn = escape * passed_total
        recall = est_tp / (est_tp + est_fn) if (est_tp + est_fn) else None

    return ConfusionOut(
        reviewed=tp + fp + fn + tn,
        reviewable=len(flags),
        flagged_total=flagged_total,
        passed_total=passed_total,
        tp=tp,
        fp=fp,
        fn=fn,
        tn=tn,
        precision=precision,
        escape_rate=escape,
        recall_estimate=recall,
        leaks_reaching_students_estimate=reaching,
    )


def _sum_confusions(a: ConfusionOut, b: ConfusionOut) -> ConfusionOut:
    tp, fp, fn, tn = a.tp + b.tp, a.fp + b.fp, a.fn + b.fn, a.tn + b.tn
    flagged, passed = a.flagged_total + b.flagged_total, a.passed_total + b.passed_total
    precision, escape = _rate(tp, tp + fp), _rate(fn, fn + tn)
    recall = None
    if precision is not None and escape is not None:
        est_tp, est_fn = precision * flagged, escape * passed
        recall = est_tp / (est_tp + est_fn) if (est_tp + est_fn) else None
    return ConfusionOut(
        reviewed=a.reviewed + b.reviewed,
        reviewable=a.reviewable + b.reviewable,
        flagged_total=flagged,
        passed_total=passed,
        tp=tp,
        fp=fp,
        fn=fn,
        tn=tn,
        precision=precision,
        escape_rate=escape,
        recall_estimate=recall,
        leaks_reaching_students_estimate=escape * passed if escape is not None else None,
    )


def _question_out(q: Question, module_titles: dict[int, str]) -> ReviewQuestionOut:
    return ReviewQuestionOut(
        id=q.id,
        topic=q.topic,
        module_title=module_titles.get(q.module_id) if q.module_id else None,
        statement=q.statement,
        alternatives=list(q.alternatives or []),
        correct_alternative_id=q.correct_alternative_id,
        explanation=q.directive_explanation,
        active=q.active,
    )


# ---------------------------------------------------------------------------
# Metricas
# ---------------------------------------------------------------------------


@router.get("", response_model=EvaluationOut)
def get_evaluation(db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    student_ids = {uid for (uid,) in db.query(User.id).filter(User.is_admin.is_(False))}

    # Feedback pos-erro (so de alunos: o admin testando nao entra na conta)
    logs = (
        db.query(InteractionLog, Attempt.user_id)
        .join(Attempt, InteractionLog.attempt_id == Attempt.id)
        .all()
    )
    logs = [log for log, uid in logs if uid in student_ids]
    fb_unavailable = [l for l in logs if _is_unavailable_log(l)]
    fb_answered = [l for l in logs if not _is_unavailable_log(l)]
    fb_scope = [l for l in fb_answered if l.mode == FeedbackGroup.SOCRATICO]
    fb_filtered = sum(1 for l in fb_scope if l.leak_detected)
    feedback = ChannelOut(
        total=len(logs),
        ai_calls=len(fb_answered),
        unavailable=len(fb_unavailable),
        filtered=fb_filtered,
        filter_scope=len(fb_scope),
        filtered_rate=fb_filtered / len(fb_scope) if fb_scope else 0.0,
        reused=0,
        latency=_latency([l.gemini_latency_ms for l in fb_answered]),
    )
    by_mode: dict[str, int] = defaultdict(int)
    for l in logs:
        by_mode[l.mode.value] += 1

    # Dicas (as degradadas nao sao gravadas: o aluno nao gasta a dica)
    hints = [h for h in db.query(HintRequest).all() if h.user_id in student_ids]
    h_generated = [h for h in hints if not h.reused]
    h_answered = [h for h in h_generated if h.gemini_latency_ms > 0]
    h_filtered = sum(1 for h in h_answered if h.leak_detected)
    hints_out = ChannelOut(
        total=len(hints),
        ai_calls=len(h_answered),
        unavailable=len(h_generated) - len(h_answered),
        filtered=h_filtered,
        filter_scope=len(h_answered),
        filtered_rate=h_filtered / len(h_answered) if h_answered else 0.0,
        reused=len(hints) - len(h_generated),
        latency=_latency([h.gemini_latency_ms for h in h_answered]),
    )

    # Conteudo gerado e reaproveitamento das mini aulas
    generated_q = db.query(Question).filter(Question.generated.is_(True)).count()
    bank_q = db.query(Question).filter(Question.generated.is_(False)).count()
    retired_q = db.query(Question).filter(Question.active.is_(False)).count()
    lessons = db.query(Lesson).count()
    views = db.query(LessonView).count()
    content = ContentOut(
        generated_questions=generated_q,
        bank_questions=bank_q,
        retired_questions=retired_q,
        lessons_generated=lessons,
        lesson_views=views,
        lesson_calls_saved=max(0, views - lessons),
    )

    # Uso diario nos ultimos 14 dias
    today = datetime.utcnow().date()
    days = [today - timedelta(days=i) for i in range(13, -1, -1)]
    fb_count: dict = defaultdict(int)
    h_count: dict = defaultdict(int)
    for l in logs:
        fb_count[l.created_at.date()] += 1
    for h in hints:
        h_count[h.created_at.date()] += 1
    daily = [DailyOut(date=d.isoformat(), feedback=fb_count[d], hints=h_count[d]) for d in days]

    dates = [l.created_at for l in logs] + [h.created_at for h in hints]

    # Revisao manual
    fb_flags = {l.id: bool(l.leak_detected) for l in _reviewable_feedback(db).all()}
    h_flags = {h.id: bool(h.leak_detected) for h in _reviewable_hints(db).all()}
    conf_fb = _confusion(fb_flags, _labels(db, "feedback"))
    conf_h = _confusion(h_flags, _labels(db, "hint"))

    q_labels = _labels(db, "question")
    q_verdicts = [l.verdict for l in q_labels.values() if l.verdict in QUESTION_VERDICTS]
    wrong = q_verdicts.count("errado")
    question_review = QuestionReviewOut(
        generated_total=generated_q,
        reviewed=len(q_verdicts),
        correct=q_verdicts.count("correto"),
        wrong=wrong,
        ambiguous=q_verdicts.count("ambiguo"),
        wrong_rate=_rate(wrong, len(q_verdicts)),
    )

    return EvaluationOut(
        since=min(dates) if dates else None,
        feedback=feedback,
        hints=hints_out,
        feedback_by_mode=dict(by_mode),
        content=content,
        daily=daily,
        leak_review={"feedback": conf_fb, "hint": conf_h, "total": _sum_confusions(conf_fb, conf_h)},
        question_review=question_review,
    )


# ---------------------------------------------------------------------------
# Revisao manual
# ---------------------------------------------------------------------------


def _module_titles(db: Session) -> dict[int, str]:
    return {m.id: m.title for m in db.query(Module).all()}


@router.get("/review/{kind}", response_model=ReviewPageOut)
def list_review(
    kind: ReviewKind,
    status: Literal["pending", "done"] = "pending",
    flag: Literal["all", "flagged", "passed"] = "all",
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    labels = _labels(db, kind)
    labeled_ids = list(labels)

    if kind == "feedback":
        query = _reviewable_feedback(db)
        model = InteractionLog
        flag_col = InteractionLog.leak_detected
    elif kind == "hint":
        query = _reviewable_hints(db)
        model = HintRequest
        flag_col = HintRequest.leak_detected
    else:
        query = db.query(Question).filter(Question.generated.is_(True))
        model = Question
        flag_col = None

    if flag_col is not None and flag != "all":
        query = query.filter(flag_col.is_(flag == "flagged"))

    if status == "pending":
        if labeled_ids:
            query = query.filter(model.id.notin_(labeled_ids))
        query = query.order_by(model.id.asc())
    else:
        query = query.filter(model.id.in_(labeled_ids or [-1])).order_by(model.id.desc())

    total = query.count()
    rows = query.offset(offset).limit(limit).all()
    titles = _module_titles(db)
    items: list[ReviewItemOut] = []

    for row in rows:
        label = labels.get(row.id)
        if kind == "feedback":
            attempt = db.get(Attempt, row.attempt_id)
            question = db.get(Question, attempt.question_id) if attempt else None
            if question is None:
                continue
            items.append(
                ReviewItemOut(
                    kind=kind,
                    id=row.id,
                    created_at=row.created_at,
                    question=_question_out(question, titles),
                    ai_text=row.raw_output_excerpt,
                    shown_text=attempt.feedback_text if attempt else None,
                    filter_flagged=bool(row.leak_detected),
                    mode=row.mode.value,
                    chosen_alternative_id=attempt.alternative_chosen if attempt else None,
                    verdict=label.verdict if label else None,
                    note=label.note if label else None,
                )
            )
        elif kind == "hint":
            question = db.get(Question, row.question_id)
            if question is None:
                continue
            items.append(
                ReviewItemOut(
                    kind=kind,
                    id=row.id,
                    created_at=row.created_at,
                    question=_question_out(question, titles),
                    ai_text=row.raw_output or row.content,
                    shown_text=row.content,
                    filter_flagged=bool(row.leak_detected),
                    mode=row.mode.value if row.mode else None,
                    hint_number=row.hint_number,
                    verdict=label.verdict if label else None,
                    note=label.note if label else None,
                )
            )
        else:
            items.append(
                ReviewItemOut(
                    kind=kind,
                    id=row.id,
                    created_at=row.created_at,
                    question=_question_out(row, titles),
                    verdict=label.verdict if label else None,
                    note=label.note if label else None,
                )
            )

    return ReviewPageOut(items=items, total=total)


def _check_item(db: Session, kind: str, item_id: int):
    model = {"feedback": InteractionLog, "hint": HintRequest, "question": Question}[kind]
    item = db.get(model, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item nao encontrado")
    return item


@router.put("/review/{kind}/{item_id}", status_code=204)
def save_review(
    kind: ReviewKind,
    item_id: int,
    payload: ReviewIn,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    allowed = QUESTION_VERDICTS if kind == "question" else LEAK_VERDICTS
    if payload.verdict not in allowed:
        raise HTTPException(status_code=400, detail="Marcacao invalida")
    item = _check_item(db, kind, item_id)

    label = (
        db.query(ReviewLabel)
        .filter(ReviewLabel.item_type == kind, ReviewLabel.item_id == item_id)
        .first()
    )
    previous = label.verdict if label else None
    if label is None:
        label = ReviewLabel(item_type=kind, item_id=item_id, verdict=payload.verdict)
        db.add(label)
    label.verdict = payload.verdict
    label.note = (payload.note or "").strip() or None
    label.reviewer_id = admin.id

    # Gabarito errado nao pode continuar chegando aos alunos: a questao sai
    # de circulacao (aposentadoria suave, o historico continua valido). Se a
    # marcacao deixar de ser "errado", ela volta.
    if kind == "question":
        if payload.verdict == "errado":
            item.active = False
        elif previous == "errado":
            item.active = True

    db.commit()


@router.delete("/review/{kind}/{item_id}", status_code=204)
def delete_review(
    kind: ReviewKind,
    item_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    item = _check_item(db, kind, item_id)
    label = (
        db.query(ReviewLabel)
        .filter(ReviewLabel.item_type == kind, ReviewLabel.item_id == item_id)
        .first()
    )
    if label is None:
        return
    if kind == "question" and label.verdict == "errado":
        item.active = True
    db.delete(label)
    db.commit()
