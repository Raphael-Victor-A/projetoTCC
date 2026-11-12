"""Carga inicial do banco.

Roda no startup e e idempotente: sincroniza a grade BNCC, insere as questoes
que ainda nao existem (casadas por hash do enunciado) e garante a conta admin.
Rodar de novo depois de editar `bncc.py` ou `diagnostic_bank.py` atualiza o
conteudo sem duplicar nada nem apagar progresso de aluno.
"""

import logging

from sqlalchemy.orm import Session

from app.config import settings
from app.curriculum import sync_curriculum
from app.database import Base, SessionLocal, engine
from app.diagnostic_bank import DIAGNOSTIC_BANK
from app.migrations import run_additive_migrations
from app.models import FeedbackGroup, Level, Module, Question, User
from app.security import hash_password
from app.text_utils import statement_hash

logger = logging.getLogger(__name__)

# Acervo de reserva usado quando a geracao por IA esta indisponivel.
# Sao questoes de pratica/reforco (nao entram no diagnostico).
RESERVE_QUESTIONS = [
    dict(
        module_slug="mat-conjuntos-numericos",
        level=Level.BASICO,
        topic="Aritmetica",
        statement="Qual e o resultado de 9 - 3 x 2?",
        alternatives=[
            {"id": "a", "text": "12"},
            {"id": "b", "text": "3"},
            {"id": "c", "text": "6"},
            {"id": "d", "text": "0"},
        ],
        correct_alternative_id="b",
        directive_explanation="Multiplicacao primeiro: 3x2=6. Depois 9-6=3.",
        is_remedial=False,
    ),
    dict(
        module_slug="mat-conjuntos-numericos",
        level=Level.BASICO,
        topic="Ordem das operacoes (reforco)",
        statement="Em uma expressao com soma e multiplicacao e sem parenteses, qual operacao deve ser feita primeiro?",
        alternatives=[
            {"id": "a", "text": "A que aparece primeiro da esquerda para a direita"},
            {"id": "b", "text": "A multiplicacao"},
            {"id": "c", "text": "A soma"},
            {"id": "d", "text": "Nao ha ordem definida"},
        ],
        correct_alternative_id="b",
        directive_explanation="Na ordem das operacoes, multiplicacao e divisao tem precedencia sobre soma e subtracao.",
        is_remedial=True,
    ),
    dict(
        module_slug="mat-razao-proporcao-porcentagem",
        level=Level.BASICO,
        topic="Porcentagem",
        statement="Quanto e 15% de 200?",
        alternatives=[
            {"id": "a", "text": "15"},
            {"id": "b", "text": "20"},
            {"id": "c", "text": "30"},
            {"id": "d", "text": "35"},
        ],
        correct_alternative_id="c",
        directive_explanation="15% = 0,15. Entao 0,15 x 200 = 30.",
        is_remedial=False,
    ),
    dict(
        module_slug="mat-equacoes-1-grau",
        level=Level.BASICO,
        topic="Equacao do 1o grau",
        statement="Se 3x - 4 = 8, qual e o valor de x?",
        alternatives=[
            {"id": "a", "text": "2"},
            {"id": "b", "text": "3"},
            {"id": "c", "text": "4"},
            {"id": "d", "text": "12"},
        ],
        correct_alternative_id="c",
        directive_explanation="3x = 8 + 4 = 12, logo x = 12/3 = 4.",
        is_remedial=False,
    ),
    dict(
        module_slug="mat-equacoes-1-grau",
        level=Level.BASICO,
        topic="Equacao do 1o grau (reforco)",
        statement="Para isolar x em 'x + 5 = 9', qual operacao aplicar dos dois lados da igualdade?",
        alternatives=[
            {"id": "a", "text": "Somar 5"},
            {"id": "b", "text": "Subtrair 5"},
            {"id": "c", "text": "Multiplicar por 5"},
            {"id": "d", "text": "Dividir por 5"},
        ],
        correct_alternative_id="b",
        directive_explanation="Para cancelar o +5 do lado esquerdo, subtrai-se 5 dos dois lados: x = 9 - 5 = 4.",
        is_remedial=True,
    ),
    dict(
        module_slug="mat-funcao-afim",
        level=Level.INTERMEDIARIO,
        topic="Funcao afim",
        statement="Na funcao f(x) = 3x + 1, qual e o valor de f(2)?",
        alternatives=[
            {"id": "a", "text": "5"},
            {"id": "b", "text": "6"},
            {"id": "c", "text": "7"},
            {"id": "d", "text": "9"},
        ],
        correct_alternative_id="c",
        directive_explanation="f(2) = 3 x 2 + 1 = 6 + 1 = 7.",
        is_remedial=False,
    ),
    dict(
        module_slug="mat-funcao-quadratica",
        level=Level.INTERMEDIARIO,
        topic="Equacao do 2o grau (reforco)",
        statement="Na formula de Bhaskara, o que representa o discriminante (delta)?",
        alternatives=[
            {"id": "a", "text": "O numero de variaveis da equacao"},
            {"id": "b", "text": "b^2 - 4ac, que indica quantas raizes reais existem"},
            {"id": "c", "text": "A soma das raizes"},
            {"id": "d", "text": "O produto das raizes"},
        ],
        correct_alternative_id="b",
        directive_explanation="Delta = b^2 - 4ac. Se delta>0, duas raizes reais distintas; se =0, uma raiz; se <0, nenhuma raiz real.",
        is_remedial=True,
    ),
    dict(
        module_slug="mat-sistemas-lineares",
        level=Level.INTERMEDIARIO,
        topic="Sistemas lineares",
        statement="No sistema x + y = 12 e x - y = 4, qual e o valor de y?",
        alternatives=[
            {"id": "a", "text": "2"},
            {"id": "b", "text": "4"},
            {"id": "c", "text": "6"},
            {"id": "d", "text": "8"},
        ],
        correct_alternative_id="b",
        directive_explanation="Subtraindo as equacoes: 2y = 8, logo y = 4.",
        is_remedial=False,
    ),
    dict(
        module_slug="mat-funcao-exponencial-logaritmo",
        level=Level.AVANCADO,
        topic="Funcao exponencial",
        statement="Se f(x) = 2^x, qual e o valor de f(5)?",
        alternatives=[
            {"id": "a", "text": "10"},
            {"id": "b", "text": "16"},
            {"id": "c", "text": "32"},
            {"id": "d", "text": "25"},
        ],
        correct_alternative_id="c",
        directive_explanation="2^5 = 2x2x2x2x2 = 32.",
        is_remedial=False,
    ),
    dict(
        module_slug="mat-sequencias-progressoes",
        level=Level.AVANCADO,
        topic="Progressao aritmetica (reforco)",
        statement="Em uma progressao aritmetica, o que e a razao?",
        alternatives=[
            {"id": "a", "text": "O primeiro termo da sequencia"},
            {"id": "b", "text": "A diferenca constante entre um termo e o anterior"},
            {"id": "c", "text": "O quociente entre um termo e o anterior"},
            {"id": "d", "text": "A soma de todos os termos"},
        ],
        correct_alternative_id="b",
        directive_explanation="Na PA cada termo e obtido somando a razao ao anterior: r = an - a(n-1). O quociente constante caracteriza a PG.",
        is_remedial=True,
    ),
]


def _module_index(db: Session) -> dict[str, Module]:
    return {m.slug: m for m in db.query(Module).all()}


def _fill_missing_hashes(db: Session) -> None:
    """Bancos criados antes de `statement_hash` existir: preenche o hash das
    linhas antigas para que a deduplicacao valha para elas tambem."""

    for question in db.query(Question).filter(Question.statement_hash.is_(None)).all():
        question.statement_hash = statement_hash(question.statement)
    db.flush()


def _upsert_questions(db: Session, rows: list[dict], modules: dict[str, Module]) -> tuple[int, int]:
    """Sincroniza o banco com as questoes declaradas em codigo.

    Casadas por hash do enunciado. Alem de inserir o que falta, ATUALIZA o
    vinculo com a grade das que ja existem — sem isso, uma questao inserida
    por uma versao antiga do arquivo ficaria presa ao modulo antigo, mesmo
    depois de o arquivo ser reorganizado.

    Retorna (inseridas, atualizadas).
    """

    existing = {
        q.statement_hash: q
        for q in db.query(Question).filter(Question.statement_hash.isnot(None)).all()
    }

    inserted = 0
    updated = 0
    for row in rows:
        data = dict(row)
        module = modules.get(data.pop("module_slug", "") or "")
        digest = statement_hash(data["statement"])

        question = existing.get(digest)
        if question is None:
            question = Question(
                **data,
                statement_hash=digest,
                module_id=module.id if module else None,
                subject_id=module.subject_id if module else None,
            )
            db.add(question)
            existing[digest] = question
            inserted += 1
            continue

        question.level = data["level"]
        question.topic = data["topic"]
        question.alternatives = data["alternatives"]
        question.correct_alternative_id = data["correct_alternative_id"]
        question.directive_explanation = data["directive_explanation"]
        question.is_diagnostic = bool(data.get("is_diagnostic", False))
        question.is_remedial = bool(data.get("is_remedial", False))
        question.module_id = module.id if module else None
        question.subject_id = module.subject_id if module else None
        question.active = True
        updated += 1

    db.flush()
    return inserted, updated


def _retire_superseded(db: Session, curated_hashes: set[str]) -> int:
    """Aposenta questoes estaticas que nao existem mais nos arquivos de dados.

    Sao restos de versoes anteriores do seed (por exemplo, conteudo fora do
    programa do 1o ano). Ficam `active=False` — o historico de tentativas
    continua valido, mas elas nunca mais sao sorteadas. Questoes geradas por
    IA nao entram aqui: elas nao vem de arquivo nenhum.
    """

    retired = 0
    for question in db.query(Question).filter(Question.generated.is_(False)).all():
        if question.statement_hash in curated_hashes:
            continue
        if not question.active:
            continue
        question.active = False
        question.is_diagnostic = False
        retired += 1
    db.flush()
    return retired


def seed_if_empty() -> None:
    Base.metadata.create_all(bind=engine)
    run_additive_migrations()

    db = SessionLocal()
    try:
        sync_curriculum(db)
        modules = _module_index(db)
        _fill_missing_hashes(db)

        curated = DIAGNOSTIC_BANK + RESERVE_QUESTIONS
        inserted, updated = _upsert_questions(db, curated, modules)
        retired = _retire_superseded(db, {statement_hash(r["statement"]) for r in curated})
        db.commit()

        logger.info(
            "Seed: %d questao(oes) inserida(s), %d atualizada(s), %d aposentada(s)",
            inserted,
            updated,
            retired,
        )

        if db.query(User).filter(User.is_admin.is_(True)).first() is None:
            db.add(
                User(
                    email=settings.admin_email,
                    hashed_password=hash_password(settings.admin_password),
                    group=FeedbackGroup.SOCRATICO,
                    is_admin=True,
                    diagnostic_completed=True,
                )
            )
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_if_empty()
    print("Banco populado com a grade BNCC, banco de questoes e admin padrao.")
