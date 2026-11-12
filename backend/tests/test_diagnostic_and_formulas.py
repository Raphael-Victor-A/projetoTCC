"""Itens 2 e 3: questoes erradas no resultado do diagnostico e filtro
anti-vazamento diante de formulas em LaTeX."""

from app.ai.feedback import _heuristic_leak_detected
from app.ai.prompts import (
    DIRETIVO_SYSTEM_PROMPT,
    LESSON_STREAM_SYSTEM_PROMPT,
    LESSON_SYSTEM_PROMPT,
    SOCRATICO_SYSTEM_PROMPT,
)
from app.database import SessionLocal
from app.models import Question


def test_resultado_do_diagnostico_lista_questoes_erradas(client, register):
    headers, _ = register()
    diag = client.get("/diagnostic", headers=headers).json()

    with SessionLocal() as db:
        gabarito = {
            q.id: q.correct_alternative_id
            for q in db.query(Question).filter(Question.id.in_([q["id"] for q in diag["questions"]]))
        }

    # Erra de proposito as duas primeiras, acerta o resto.
    answers = []
    for i, q in enumerate(diag["questions"]):
        correct = gabarito[q["id"]]
        wrong = next(a["id"] for a in q["alternatives"] if a["id"] != correct)
        answers.append({"question_id": q["id"], "alternative_id": wrong if i < 2 else correct})

    res = client.post(
        "/diagnostic/submit",
        json={"session_id": diag["session_id"], "answers": answers},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["correct_count"] == body["total"] - 2
    assert len(body["wrong_answers"]) == 2
    assert body["focus_areas"] or body["strengths"]  # desempenho por conteudo continua

    first_q = diag["questions"][0]
    item = body["wrong_answers"][0]
    texts = {a["id"]: a["text"] for a in first_q["alternatives"]}
    assert item["question_id"] == first_q["id"]
    assert item["statement"] == first_q["statement"]
    assert item["chosen_text"] == texts[answers[0]["alternative_id"]]
    assert item["correct_text"] == texts[gabarito[first_q["id"]]]
    assert item["chosen_text"] != item["correct_text"]
    assert item["module_title"]


def test_filtro_anti_vazamento_enxerga_resposta_em_latex():
    assert _heuristic_leak_detected(r"Logo $c = 62{,}8\text{ cm}$.", "62,8 cm", "b")
    assert _heuristic_leak_detected(r"$$c = 20 \cdot 3{,}14 = 62{,}8$$", "62,8", "b")
    assert not _heuristic_leak_detected(r"Quanto vale $2 \pi r$ aqui?", "62,8 cm", "b")


def test_prompts_pedem_delimitadores_e_virgula_decimal():
    for prompt in (
        DIRETIVO_SYSTEM_PROMPT,
        SOCRATICO_SYSTEM_PROMPT,
        LESSON_SYSTEM_PROMPT,
        LESSON_STREAM_SYSTEM_PROMPT,
    ):
        assert "$$...$$" in prompt
        assert "{,}" in prompt
        assert "texto simples" not in prompt.lower()
