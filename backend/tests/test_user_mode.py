"""Item 1: modo padrao socratico e alteracao exclusiva do admin."""

from app.database import SessionLocal
from app.models import FeedbackGroup, User

from .conftest import ADMIN_EMAIL


def test_cadastro_cria_usuario_socratico(client, register):
    # Varios cadastros: antes era sorteio 50/50, entao um so poderia passar por sorte.
    for _ in range(6):
        headers, _ = register()
        me = client.get("/auth/me", headers=headers).json()
        assert me["group"] == "socratico"


def test_usuario_criado_direto_no_banco_nasce_socratico(client):
    with SessionLocal() as db:
        user = User(email="direto@teste.com", hashed_password="x")
        db.add(user)
        db.commit()
        db.refresh(user)
        assert user.group == FeedbackGroup.SOCRATICO


def test_admin_do_seed_nasce_socratico(client):
    with SessionLocal() as db:
        admin = db.query(User).filter(User.email == ADMIN_EMAIL).one()
        assert admin.is_admin
        assert admin.group == FeedbackGroup.SOCRATICO


def _student_id(client, admin_headers, email: str) -> int:
    students = client.get("/admin/students", headers=admin_headers).json()
    return next(s["id"] for s in students if s["email"] == email)


def test_aluno_nao_altera_modo(client, register, admin_headers):
    headers, email = register()
    student_id = _student_id(client, admin_headers, email)

    res = client.patch(
        f"/admin/students/{student_id}/group", json={"group": "diretivo"}, headers=headers
    )
    assert res.status_code == 403
    assert client.get("/auth/me", headers=headers).json()["group"] == "socratico"


def test_sem_login_nao_altera_modo(client, register, admin_headers):
    _, email = register()
    student_id = _student_id(client, admin_headers, email)

    res = client.patch(f"/admin/students/{student_id}/group", json={"group": "diretivo"})
    assert res.status_code == 401


def test_admin_altera_modo(client, register, admin_headers):
    headers, email = register()
    student_id = _student_id(client, admin_headers, email)

    res = client.patch(
        f"/admin/students/{student_id}/group", json={"group": "diretivo"}, headers=admin_headers
    )
    assert res.status_code == 200
    assert res.json()["group"] == "diretivo"
    assert client.get("/auth/me", headers=headers).json()["group"] == "diretivo"

    res = client.patch(
        f"/admin/students/{student_id}/group", json={"group": "socratico"}, headers=admin_headers
    )
    assert res.status_code == 200
    assert client.get("/auth/me", headers=headers).json()["group"] == "socratico"
