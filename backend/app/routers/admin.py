from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Attempt, FeedbackGroup, InteractionLog, Level, User
from app.schemas import AdminStatsOut, GroupStatsOut, StudentGroupIn, StudentOut
from app.security import get_current_admin

router = APIRouter(prefix="/admin", tags=["admin"])


def _group_stats(db: Session, group: FeedbackGroup) -> GroupStatsOut:
    users = db.query(User).filter(User.group == group, User.is_admin.is_(False)).all()
    user_ids = [u.id for u in users]

    level_distribution = {level.value: 0 for level in Level}
    for u in users:
        level_distribution[u.level.value] += 1

    attempts_query = db.query(Attempt).filter(Attempt.user_id.in_(user_ids), Attempt.is_diagnostic.is_(False))
    total_attempts = attempts_query.count()
    correct_attempts = attempts_query.filter(Attempt.correct.is_(True)).count()
    accuracy = correct_attempts / total_attempts if total_attempts else 0.0

    logs_query = (
        db.query(InteractionLog)
        .join(Attempt, InteractionLog.attempt_id == Attempt.id)
        .filter(Attempt.user_id.in_(user_ids))
    )
    total_logs = logs_query.count()
    avg_latency = db.query(func.avg(InteractionLog.gemini_latency_ms)).filter(
        InteractionLog.attempt_id.in_(
            db.query(Attempt.id).filter(Attempt.user_id.in_(user_ids))
        )
    ).scalar() or 0.0
    leak_count = logs_query.filter(InteractionLog.leak_detected.is_(True)).count()
    fallback_count = logs_query.filter(InteractionLog.fallback_used.is_(True)).count()
    leak_rate = leak_count / total_logs if total_logs else 0.0

    return GroupStatsOut(
        group=group,
        total_users=len(users),
        total_attempts=total_attempts,
        correct_attempts=correct_attempts,
        accuracy=accuracy,
        level_distribution=level_distribution,
        avg_gemini_latency_ms=avg_latency,
        leak_detected_count=leak_count,
        leak_detected_rate=leak_rate,
        fallback_used_count=fallback_count,
    )


@router.get("/stats", response_model=AdminStatsOut)
def get_admin_stats(db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    total_students = db.query(User).filter(User.is_admin.is_(False)).count()
    groups = [_group_stats(db, group) for group in FeedbackGroup]
    return AdminStatsOut(total_students=total_students, groups=groups)


@router.get("/students", response_model=list[StudentOut])
def list_students(db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    return (
        db.query(User)
        .filter(User.is_admin.is_(False))
        .order_by(User.email)
        .all()
    )


@router.patch("/students/{student_id}/group", response_model=StudentOut)
def set_student_group(
    student_id: int,
    payload: StudentGroupIn,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """Sobrescreve manualmente o grupo (diretivo/socratico) sorteado no
    cadastro do aluno — permite ao professor/pesquisador controlar a
    mediacao aplicada a um aluno especifico a qualquer momento."""
    student = db.query(User).filter(User.id == student_id, User.is_admin.is_(False)).first()
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aluno nao encontrado")

    student.group = payload.group
    db.commit()
    db.refresh(student)
    return student
