"""Fixtures dos testes.

Cada execucao usa um SQLite temporario e roda SEM chave do Gemini: nada sai
para a rede. As variaveis de ambiente precisam estar definidas antes do
primeiro import de `app`, porque `app.config.settings` e lido no import.
"""

import os
import sys
import tempfile
from pathlib import Path

_TMP_DIR = tempfile.mkdtemp(prefix="tcc-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP_DIR) / 'test.db'}"
os.environ["GEMINI_API_KEY"] = ""
os.environ["ADMIN_EMAIL"] = "admin@teste.com"
os.environ["ADMIN_PASSWORD"] = "senha-admin-teste"
os.environ["JWT_SECRET_KEY"] = "segredo-de-teste"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import itertools  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

_counter = itertools.count()


@pytest.fixture(scope="session")
def client():
    # O `with` dispara o lifespan: cria tabelas, migra e popula (seed).
    with TestClient(app) as c:
        yield c


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def register(client):
    """Cria um aluno novo e devolve (headers, email)."""

    def _register() -> tuple[dict[str, str], str]:
        email = f"aluno{next(_counter)}@teste.com"
        res = client.post("/auth/register", json={"email": email, "password": "senha123"})
        assert res.status_code == 201, res.text
        return _auth(res.json()["access_token"]), email

    return _register


@pytest.fixture
def admin_headers(client):
    res = client.post("/auth/login", data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert res.status_code == 200, res.text
    return _auth(res.json()["access_token"])
