"""Item 4: limite de reexplicacao por aluno e por mini aula."""

import itertools

import pytest

from app.ai.client import AIUnavailable
from app.config import settings
from app.database import SessionLocal
from app.models import Lesson, Level
from app.routers import learning

_keys = itertools.count()


@pytest.fixture
def lesson_id(client):
    with SessionLocal() as db:
        lesson = Lesson(
            cache_key=f"teste-reexplicacao-{next(_keys)}",
            topic="Funcao afim",
            level=Level.BASICO,
            title="Funcao afim",
            intro="Intro",
            sections=[],
            key_concepts=[],
            examples=[],
            summary="Resumo",
        )
        db.add(lesson)
        db.commit()
        return lesson.id


@pytest.fixture
def fake_ai(monkeypatch):
    """Troca a chamada ao Gemini por um gerador local."""

    calls = {"n": 0}

    async def ok(**_kwargs):
        calls["n"] += 1
        yield "Outra "
        yield "explicacao."

    monkeypatch.setattr(learning, "stream_explanation", ok)
    return calls


def _reexplain(client, headers, lesson_id):
    return client.post(f"/lessons/{lesson_id}/reexplain", headers=headers)


def test_primeira_reexplicacao_funciona_e_segunda_e_bloqueada(client, register, lesson_id, fake_ai):
    headers, _ = register()

    before = client.get(f"/lessons/{lesson_id}", headers=headers).json()
    assert before["reexplain_limit"] == 1
    assert before["reexplain_remaining"] == 1
    assert before["reexplain_text"] is None

    first = _reexplain(client, headers, lesson_id)
    assert first.status_code == 200
    assert "Outra " in first.text

    second = _reexplain(client, headers, lesson_id)
    assert second.status_code == 409
    assert fake_ai["n"] == 1  # a segunda nem chegou a chamar a IA

    after = client.get(f"/lessons/{lesson_id}", headers=headers).json()
    assert after["reexplain_remaining"] == 0
    # Texto salvo: recarregar a pagina mostra a mesma explicacao sem nova chamada.
    assert after["reexplain_text"] == "Outra explicacao."


def test_limite_e_por_aluno(client, register, lesson_id, fake_ai):
    a, _ = register()
    b, _ = register()
    assert _reexplain(client, a, lesson_id).status_code == 200
    assert _reexplain(client, a, lesson_id).status_code == 409
    assert _reexplain(client, b, lesson_id).status_code == 200


def test_limite_e_por_mini_aula(client, register, fake_ai):
    headers, _ = register()
    with SessionLocal() as db:
        ids = []
        for _ in range(2):
            lesson = Lesson(
                cache_key=f"teste-reexplicacao-{next(_keys)}",
                topic="T",
                level=Level.BASICO,
                title="T",
            )
            db.add(lesson)
            db.commit()
            ids.append(lesson.id)
    assert _reexplain(client, headers, ids[0]).status_code == 200
    assert _reexplain(client, headers, ids[1]).status_code == 200


def test_falha_da_ia_devolve_o_uso(client, register, lesson_id, monkeypatch):
    headers, _ = register()

    async def broken(**_kwargs):
        raise AIUnavailable("fora do ar")
        yield  # pragma: no cover - torna a funcao um gerador

    monkeypatch.setattr(learning, "stream_explanation", broken)
    res = _reexplain(client, headers, lesson_id)
    assert res.status_code == 200
    assert "event: error" in res.text

    lesson = client.get(f"/lessons/{lesson_id}", headers=headers).json()
    assert lesson["reexplain_remaining"] == 1


def test_limite_configuravel(client, register, lesson_id, fake_ai, monkeypatch):
    monkeypatch.setattr(settings, "lesson_reexplain_limit", 2)
    headers, _ = register()
    assert _reexplain(client, headers, lesson_id).status_code == 200
    assert _reexplain(client, headers, lesson_id).status_code == 200
    assert _reexplain(client, headers, lesson_id).status_code == 409


def test_rota_antiga_sem_limite_foi_removida(client, register):
    headers, _ = register()
    res = client.get("/modules/1/lesson/stream", headers=headers)
    assert res.status_code in (404, 405)


def test_aula_inexistente(client, register):
    headers, _ = register()
    assert _reexplain(client, headers, 999999).status_code == 404
