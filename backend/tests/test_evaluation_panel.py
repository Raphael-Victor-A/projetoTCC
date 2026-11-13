"""Painel de avaliacao da IA: metricas, revisao manual e matriz de confusao."""

from app.database import SessionLocal
from app.models import (
    Attempt,
    FeedbackGroup,
    HintRequest,
    InteractionLog,
    Level,
    Question,
    User,
)


def _seed_logs(email: str) -> dict[str, list[int]]:
    """Cria 2 feedbacks barrados, 3 liberados, 1 indisponivel e 2 dicas."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        q = db.query(Question).filter(Question.is_diagnostic.is_(False)).first()
        wrong = next(a["id"] for a in q.alternatives if a["id"] != q.correct_alternative_id)
        ids: dict[str, list[int]] = {"flagged": [], "passed": [], "hints": []}
        for kind in ["flagged", "flagged", "passed", "passed", "passed", "down"]:
            att = Attempt(user_id=user.id, question_id=q.id, alternative_chosen=wrong,
                          correct=False, level_at_time=Level.BASICO)
            db.add(att)
            db.flush()
            log = InteractionLog(
                attempt_id=att.id,
                mode=FeedbackGroup.SOCRATICO,
                gemini_latency_ms=0 if kind == "down" else 1000.0,
                leak_detected=kind == "flagged",
                fallback_used=kind in ("flagged", "down"),
                raw_output_excerpt="" if kind == "down" else f"texto {kind}",
            )
            db.add(log)
            db.flush()
            if kind != "down":
                ids[kind].append(log.id)
        for reused in (False, True):
            h = HintRequest(user_id=user.id, question_id=q.id, hint_number=1, content="dica",
                            mode=FeedbackGroup.SOCRATICO, gemini_latency_ms=0 if reused else 800.0,
                            reused=reused, raw_output=None if reused else "dica")
            db.add(h)
            db.flush()
            ids["hints"].append(h.id)
        db.commit()
        return ids
    finally:
        db.close()


def test_evaluation_requires_admin(client, register):
    headers, _ = register()
    assert client.get("/admin/evaluation", headers=headers).status_code == 403


def test_metrics_review_and_confusion(client, register, admin_headers):
    _, email = register()
    ids = _seed_logs(email)

    ev = client.get("/admin/evaluation", headers=admin_headers).json()
    assert ev["feedback"]["unavailable"] >= 1
    assert ev["feedback"]["filtered"] >= 2
    assert ev["hints"]["reused"] >= 1

    # barrados: 1 vazava de verdade, 1 nao (falso positivo)
    put = lambda kind, i, v: client.put(  # noqa: E731
        f"/admin/evaluation/review/{kind}/{i}", headers=admin_headers, json={"verdict": v}
    )
    assert put("feedback", ids["flagged"][0], "vazou").status_code == 204
    assert put("feedback", ids["flagged"][1], "nao_vazou").status_code == 204
    # liberados: 1 escapou, 2 ok
    assert put("feedback", ids["passed"][0], "vazou").status_code == 204
    assert put("feedback", ids["passed"][1], "nao_vazou").status_code == 204
    assert put("feedback", ids["passed"][2], "nao_vazou").status_code == 204
    assert put("feedback", ids["passed"][2], "talvez").status_code == 400

    c = client.get("/admin/evaluation", headers=admin_headers).json()["leak_review"]["feedback"]
    assert (c["tp"], c["fp"], c["fn"], c["tn"]) == (1, 1, 1, 2)
    assert c["precision"] == 0.5
    assert abs(c["escape_rate"] - 1 / 3) < 1e-9

    pending = client.get(
        "/admin/evaluation/review/feedback?status=pending&flag=all&limit=50", headers=admin_headers
    ).json()
    reviewed = set(ids["flagged"] + ids["passed"])
    assert not reviewed & {i["id"] for i in pending["items"]}

    # dica reaproveitada nao entra na fila (nao houve texto novo da IA)
    hints = client.get("/admin/evaluation/review/hint?status=pending&limit=50", headers=admin_headers).json()
    hint_ids = {i["id"] for i in hints["items"]}
    assert ids["hints"][0] in hint_ids and ids["hints"][1] not in hint_ids


def test_wrong_answer_key_retires_question(client, admin_headers):
    db = SessionLocal()
    try:
        q = db.query(Question).filter(Question.is_diagnostic.is_(False), Question.active.is_(True)).first()
        q.generated = True
        db.commit()
        qid = q.id
    finally:
        db.close()

    url = f"/admin/evaluation/review/question/{qid}"
    assert client.put(url, headers=admin_headers, json={"verdict": "errado"}).status_code == 204
    db = SessionLocal()
    assert db.get(Question, qid).active is False
    db.close()

    assert client.delete(url, headers=admin_headers).status_code == 204
    db = SessionLocal()
    assert db.get(Question, qid).active is True
    db.close()
