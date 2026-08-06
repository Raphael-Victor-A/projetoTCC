from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import Level, Question, User
from app.security import hash_password

DIAGNOSTIC_QUESTIONS = [
    dict(
        level=Level.BASICO,
        topic="Aritmetica",
        statement="Qual e o resultado de 7 + 5 x 2?",
        alternatives=[
            {"id": "a", "text": "24"},
            {"id": "b", "text": "17"},
            {"id": "c", "text": "19"},
            {"id": "d", "text": "22"},
        ],
        correct_alternative_id="b",
        directive_explanation="Ordem das operacoes: multiplicacao antes da soma. 5x2=10, depois 7+10=17.",
        is_diagnostic=True,
    ),
    dict(
        level=Level.BASICO,
        topic="Fracoes",
        statement="Quanto e 1/2 + 1/4?",
        alternatives=[
            {"id": "a", "text": "2/6"},
            {"id": "b", "text": "1/3"},
            {"id": "c", "text": "3/4"},
            {"id": "d", "text": "2/4"},
        ],
        correct_alternative_id="c",
        directive_explanation="Colocando em denominador comum 4: 2/4 + 1/4 = 3/4.",
        is_diagnostic=True,
    ),
    dict(
        level=Level.BASICO,
        topic="Equacao do 1o grau",
        statement="Se 2x + 3 = 11, qual e o valor de x?",
        alternatives=[
            {"id": "a", "text": "3"},
            {"id": "b", "text": "4"},
            {"id": "c", "text": "5"},
            {"id": "d", "text": "7"},
        ],
        correct_alternative_id="b",
        directive_explanation="2x = 11 - 3 = 8, logo x = 8/2 = 4.",
        is_diagnostic=True,
    ),
]

REGULAR_AND_REMEDIAL_QUESTIONS = [
    # BASICO - regulares
    dict(
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
        level=Level.BASICO,
        topic="Porcentagem",
        statement="Quanto e 20% de 150?",
        alternatives=[
            {"id": "a", "text": "20"},
            {"id": "b", "text": "30"},
            {"id": "c", "text": "35"},
            {"id": "d", "text": "45"},
        ],
        correct_alternative_id="b",
        directive_explanation="20% = 0,20. 0,20 x 150 = 30.",
        is_remedial=False,
    ),
    dict(
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
    # BASICO - reforco (mais guiadas, conceito isolado)
    dict(
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
    # INTERMEDIARIO - regulares
    dict(
        level=Level.INTERMEDIARIO,
        topic="Equacao do 2o grau",
        statement="Quais as raizes de x^2 - 5x + 6 = 0?",
        alternatives=[
            {"id": "a", "text": "x=1 e x=6"},
            {"id": "b", "text": "x=2 e x=3"},
            {"id": "c", "text": "x=-2 e x=-3"},
            {"id": "d", "text": "x=2 e x=-3"},
        ],
        correct_alternative_id="b",
        directive_explanation="Fatorando: (x-2)(x-3)=0, entao x=2 ou x=3.",
        is_remedial=False,
    ),
    dict(
        level=Level.INTERMEDIARIO,
        topic="Sistemas lineares",
        statement="No sistema x+y=10 e x-y=2, qual e o valor de x?",
        alternatives=[
            {"id": "a", "text": "4"},
            {"id": "b", "text": "5"},
            {"id": "c", "text": "6"},
            {"id": "d", "text": "8"},
        ],
        correct_alternative_id="c",
        directive_explanation="Somando as equacoes: 2x=12, x=6.",
        is_remedial=False,
    ),
    dict(
        level=Level.INTERMEDIARIO,
        topic="Funcao afim",
        statement="Na funcao f(x) = 2x - 3, qual e o valor de f(4)?",
        alternatives=[
            {"id": "a", "text": "5"},
            {"id": "b", "text": "8"},
            {"id": "c", "text": "1"},
            {"id": "d", "text": "11"},
        ],
        correct_alternative_id="a",
        directive_explanation="f(4) = 2(4) - 3 = 8 - 3 = 5.",
        is_remedial=False,
    ),
    # INTERMEDIARIO - reforco
    dict(
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
    # AVANCADO - regulares
    dict(
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
        level=Level.AVANCADO,
        topic="Derivadas",
        statement="Qual e a derivada de f(x) = 3x^2 + 2x?",
        alternatives=[
            {"id": "a", "text": "6x + 2"},
            {"id": "b", "text": "3x + 2"},
            {"id": "c", "text": "6x^2"},
            {"id": "d", "text": "x^2 + 2"},
        ],
        correct_alternative_id="a",
        directive_explanation="Regra do tombo: d/dx(3x^2)=6x, d/dx(2x)=2. Soma: 6x+2.",
        is_remedial=False,
    ),
    # AVANCADO - reforco
    dict(
        level=Level.AVANCADO,
        topic="Derivadas (reforco)",
        statement="Na regra do tombo para d/dx(x^n), qual e o resultado geral?",
        alternatives=[
            {"id": "a", "text": "n*x^(n-1)"},
            {"id": "b", "text": "x^(n+1)/(n+1)"},
            {"id": "c", "text": "n*x^n"},
            {"id": "d", "text": "x^n / n"},
        ],
        correct_alternative_id="a",
        directive_explanation="A regra do tombo (regra da potencia) diz que d/dx(x^n) = n*x^(n-1).",
        is_remedial=True,
    ),
]


def seed_if_empty() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Question).count() == 0:
            for data in DIAGNOSTIC_QUESTIONS + REGULAR_AND_REMEDIAL_QUESTIONS:
                db.add(Question(**data))
            db.commit()

        if db.query(User).filter(User.is_admin.is_(True)).first() is None:
            db.add(
                User(
                    email=settings.admin_email,
                    hashed_password=hash_password(settings.admin_password),
                    group=None,
                    is_admin=True,
                    diagnostic_completed=True,
                )
            )
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed_if_empty()
    print("Banco populado com questoes de exemplo e admin padrao.")
