"""Banco de questoes do Questionario Diagnostico — Matematica, 1o ano do EM.

Por que um banco grande e estatico:

1. Variedade — o diagnostico sorteia um subconjunto a cada execucao
   (ver study_plan.sample_diagnostic), entao duas pessoas (ou duas
   tentativas) dificilmente veem o mesmo teste.
2. Cobertura — cada questao e marcada com o modulo da grade que avalia, o que
   permite medir conteudo por conteudo e alimentar a trilha personalizada com
   dados reais.
3. Velocidade — o primeiro acesso do aluno nao espera nenhuma chamada de API.
   A geracao por IA existe como complemento opcional
   (`DIAGNOSTIC_AI_AUGMENT`), nao como caminho critico.

Cada item declara o nivel de dificuldade, usado para manter o teste
equilibrado entre facil / medio / dificil.
"""

from app.models import Level

ALT_IDS = ["a", "b", "c", "d"]


def q(
    module: str,
    level: Level,
    topic: str,
    statement: str,
    alternatives: list[str],
    correct_index: int,
    explanation: str,
) -> dict:
    """Monta um item do banco.

    `correct_index` e a posicao (0-3) da alternativa correta na lista — mais
    dificil de errar do que repetir a letra, e o sorteio embaralha as
    alternativas na hora de servir mesmo assim.
    """

    if len(alternatives) != 4:
        raise ValueError(f"Questao '{statement[:40]}...' precisa de 4 alternativas")
    return dict(
        module_slug=module,
        level=level,
        topic=topic,
        statement=statement,
        alternatives=[{"id": ALT_IDS[i], "text": text} for i, text in enumerate(alternatives)],
        correct_alternative_id=ALT_IDS[correct_index],
        directive_explanation=explanation,
        is_diagnostic=True,
    )


B, I, A = Level.BASICO, Level.INTERMEDIARIO, Level.AVANCADO

DIAGNOSTIC_BANK: list[dict] = [
    # ------------------------------------------- Conjuntos numericos e operacoes
    q("mat-conjuntos-numericos", B, "Ordem das operacoes",
      "Qual e o resultado de 12 - 3 x 2 + 4?",
      ["22", "10", "14", "6"], 1,
      "Multiplicacao primeiro: 3x2=6. Depois, da esquerda para a direita: 12-6=6 e 6+4=10."),
    q("mat-conjuntos-numericos", B, "Fracoes",
      "Quanto e 1/2 + 1/4?",
      ["2/6", "3/4", "1/3", "2/4"], 1,
      "Reduzindo ao denominador comum 4: 2/4 + 1/4 = 3/4."),
    q("mat-conjuntos-numericos", B, "Fracao de uma quantidade",
      "Quanto vale 2/3 de 90?",
      ["30", "45", "60", "180"], 2,
      "Divide-se 90 por 3 (obtendo 30) e multiplica-se por 2: 60."),
    q("mat-conjuntos-numericos", I, "Notacao cientifica",
      "Como se escreve 0,000045 em notacao cientifica?",
      ["4,5 x 10^-5", "4,5 x 10^-4", "45 x 10^-5", "4,5 x 10^5"], 0,
      "Deslocamos a virgula 5 casas para a direita para obter 4,5; como o numero e menor que 1, o expoente e negativo: 4,5 x 10^-5."),
    q("mat-conjuntos-numericos", I, "Propriedades das potencias",
      "Qual e o valor de (2^3) x (2^2)?",
      ["2^6", "32", "64", "2^1"], 1,
      "Na multiplicacao de potencias de mesma base somam-se os expoentes: 2^(3+2) = 2^5 = 32."),

    # ------------------------------------- Razao, proporcao e porcentagem
    q("mat-razao-proporcao-porcentagem", B, "Porcentagem",
      "Quanto e 20% de 150?",
      ["20", "30", "35", "45"], 1,
      "20% = 0,20. Entao 0,20 x 150 = 30."),
    q("mat-razao-proporcao-porcentagem", I, "Acrescimo percentual",
      "Um produto custa R$ 80,00 e sofre um aumento de 25%. Qual passa a ser o preco?",
      ["R$ 96,00", "R$ 100,00", "R$ 105,00", "R$ 120,00"], 1,
      "25% de 80 = 20. Novo preco: 80 + 20 = R$ 100,00."),
    q("mat-razao-proporcao-porcentagem", I, "Grandezas inversamente proporcionais",
      "Se 4 operarios levam 12 dias para fazer uma obra, quantos dias levam 6 operarios no mesmo ritmo?",
      ["18 dias", "10 dias", "8 dias", "6 dias"], 2,
      "Mais operarios, menos dias: grandezas inversamente proporcionais. 4 x 12 = 6 x d, logo d = 48/6 = 8 dias."),
    q("mat-razao-proporcao-porcentagem", A, "Variacoes sucessivas",
      "Um preco sofre um aumento de 10% e, depois, um desconto de 10%. Em relacao ao preco inicial, o preco final fica:",
      ["igual ao inicial", "1% menor", "1% maior", "10% menor"], 1,
      "Multiplicando os fatores: 1,10 x 0,90 = 0,99. O preco final e 99% do inicial, ou seja, 1% menor."),

    # ------------------------------------------ Equacoes do 1o grau
    q("mat-equacoes-1-grau", B, "Equacao do 1o grau",
      "Se 2x + 3 = 11, qual e o valor de x?",
      ["3", "4", "5", "7"], 1,
      "2x = 11 - 3 = 8, logo x = 8/2 = 4."),
    q("mat-equacoes-1-grau", B, "Equacao do 1o grau",
      "Se 3x - 4 = 8, qual e o valor de x?",
      ["2", "3", "4", "12"], 2,
      "3x = 8 + 4 = 12, logo x = 12/3 = 4."),
    q("mat-equacoes-1-grau", I, "Problema modelado por equacao",
      "O dobro de um numero somado a 7 resulta 31. Qual e esse numero?",
      ["10", "12", "14", "19"], 1,
      "2n + 7 = 31, entao 2n = 24 e n = 12."),
    q("mat-equacoes-1-grau", I, "Inequacao do 1o grau",
      "Qual e a solucao da inequacao 2x - 6 > 0?",
      ["x > 3", "x < 3", "x > -3", "x > 6"], 0,
      "2x > 6, logo x > 3. Como dividimos por um numero positivo, a desigualdade nao muda de sentido."),

    # ------------------------------------------------ Sistemas lineares
    q("mat-sistemas-lineares", B, "Sistema por adicao",
      "No sistema x + y = 10 e x - y = 2, qual e o valor de x?",
      ["4", "5", "6", "8"], 2,
      "Somando as duas equacoes: 2x = 12, logo x = 6."),
    q("mat-sistemas-lineares", I, "Sistema por subtracao",
      "No sistema x + y = 12 e x - y = 4, qual e o valor de y?",
      ["2", "4", "6", "8"], 1,
      "Subtraindo a segunda da primeira: 2y = 8, logo y = 4."),
    q("mat-sistemas-lineares", I, "Problema com duas incognitas",
      "Dois refrigerantes e tres salgados custam R$ 26,00. Um refrigerante e um salgado custam R$ 10,00. Quanto custa o refrigerante?",
      ["R$ 4,00", "R$ 5,00", "R$ 6,00", "R$ 7,00"], 0,
      "De r + s = 10 vem s = 10 - r. Substituindo: 2r + 3(10 - r) = 26, ou seja, 30 - r = 26 e r = 4."),
    q("mat-sistemas-lineares", A, "Interpretacao grafica",
      "Um sistema de duas equacoes do 1o grau cujas retas sao paralelas e distintas tem:",
      ["uma unica solucao", "nenhuma solucao", "infinitas solucoes", "exatamente duas solucoes"], 1,
      "Retas paralelas distintas nunca se cruzam, entao nao existe par (x, y) que satisfaca as duas equacoes: sistema impossivel."),

    # ------------------------------------------------ Funcoes: conceito
    q("mat-funcoes-conceito", B, "Valor numerico de funcao",
      "Na funcao f(x) = x^2 - 1, qual e o valor de f(3)?",
      ["5", "8", "9", "10"], 1,
      "f(3) = 3^2 - 1 = 9 - 1 = 8."),
    q("mat-funcoes-conceito", I, "Dominio de funcao",
      "Qual e o dominio da funcao f(x) = 1/(x - 2)?",
      ["Todos os reais", "Todos os reais, exceto 2", "Apenas x > 2", "Apenas x diferente de 0"], 1,
      "O denominador nao pode ser zero: x - 2 diferente de 0, ou seja, x diferente de 2."),
    q("mat-funcoes-conceito", I, "Definicao de funcao",
      "Uma relacao entre dois conjuntos e uma funcao quando:",
      ["cada elemento do dominio se associa a exatamente um elemento do contradominio",
       "todo elemento do contradominio e usado",
       "os dois conjuntos tem o mesmo numero de elementos",
       "existe pelo menos uma associacao entre eles"], 0,
      "A definicao exige que cada elemento do dominio tenha uma e apenas uma imagem."),
    q("mat-funcoes-conceito", I, "Leitura de grafico",
      "Se o grafico de uma funcao corta o eixo x em dois pontos, isso significa que a funcao tem:",
      ["duas raizes reais", "duas imagens", "dominio com dois elementos", "valor maximo igual a 2"], 0,
      "Os pontos em que o grafico cruza o eixo x sao aqueles em que f(x) = 0, ou seja, as raizes."),

    # ------------------------------------------------------- Funcao afim
    q("mat-funcao-afim", I, "Valor numerico",
      "Na funcao f(x) = 2x - 3, qual e o valor de f(4)?",
      ["5", "8", "1", "11"], 0,
      "f(4) = 2 x 4 - 3 = 8 - 3 = 5."),
    q("mat-funcao-afim", I, "Coeficiente angular",
      "Na funcao f(x) = -3x + 7, o que o coeficiente -3 indica?",
      ["O valor de f(0)", "A raiz da funcao", "Que a funcao e decrescente", "Que o grafico e uma parabola"], 2,
      "O coeficiente angular negativo indica funcao decrescente; o valor 7 e que corresponde a f(0)."),
    q("mat-funcao-afim", I, "Raiz da funcao afim",
      "Qual e a raiz da funcao f(x) = 2x - 8?",
      ["x = 2", "x = 4", "x = 8", "x = -4"], 1,
      "A raiz e o valor que zera a funcao: 2x - 8 = 0, entao x = 4."),
    q("mat-funcao-afim", A, "Taxa de variacao",
      "Qual e a taxa de variacao media da funcao f(x) = 5x + 2 entre x = 1 e x = 4?",
      ["3", "5", "15", "17"], 1,
      "Na funcao afim a taxa de variacao e constante e igual ao coeficiente angular: 5. Conferindo: (f(4)-f(1))/(4-1) = (22-7)/3 = 5."),

    # ------------------------------------------------- Funcao quadratica
    q("mat-funcao-quadratica", I, "Raizes da equacao do 2o grau",
      "Quais sao as raizes de x^2 - 5x + 6 = 0?",
      ["x = 1 e x = 6", "x = 2 e x = 3", "x = -2 e x = -3", "x = 2 e x = -3"], 1,
      "Fatorando: (x-2)(x-3) = 0, entao x = 2 ou x = 3."),
    q("mat-funcao-quadratica", A, "Vertice da parabola",
      "Qual e o vertice da parabola f(x) = x^2 - 4x + 3?",
      ["(2, -1)", "(-2, -1)", "(2, 3)", "(4, 3)"], 0,
      "xv = -b/2a = 4/2 = 2. f(2) = 4 - 8 + 3 = -1. Vertice: (2, -1)."),
    q("mat-funcao-quadratica", I, "Discriminante",
      "Quantas raizes reais tem a equacao x^2 + 2x + 5 = 0?",
      ["Duas raizes distintas", "Uma raiz dupla", "Nenhuma raiz real", "Infinitas raizes"], 2,
      "Delta = 2^2 - 4(1)(5) = 4 - 20 = -16. Delta negativo significa nenhuma raiz real."),
    q("mat-funcao-quadratica", I, "Concavidade",
      "O grafico da funcao f(x) = -2x^2 + 3x - 1 tem concavidade voltada para:",
      ["cima, porque a > 0", "baixo, porque a < 0", "cima, porque c < 0", "baixo, porque b > 0"], 1,
      "A concavidade depende do sinal de a. Aqui a = -2 < 0, entao a parabola abre para baixo."),

    # ------------------------------------- Funcao exponencial e logaritmos
    q("mat-funcao-exponencial-logaritmo", I, "Equacao exponencial",
      "Qual e o valor de x na equacao 2^x = 32?",
      ["4", "5", "6", "16"], 1,
      "32 = 2^5. Igualando as bases: x = 5."),
    q("mat-funcao-exponencial-logaritmo", I, "Funcao exponencial",
      "Se f(x) = 3^x, qual e o valor de f(4)?",
      ["12", "27", "64", "81"], 3,
      "3^4 = 3x3x3x3 = 81."),
    q("mat-funcao-exponencial-logaritmo", A, "Definicao de logaritmo",
      "Qual e o valor de log na base 2 de 8?",
      ["2", "3", "4", "8"], 1,
      "Procuramos o expoente que aplicado a 2 resulta 8. Como 2^3 = 8, o logaritmo vale 3."),
    q("mat-funcao-exponencial-logaritmo", A, "Propriedades dos logaritmos",
      "A expressao log(a x b), com a e b positivos, e igual a:",
      ["log(a) x log(b)", "log(a) + log(b)", "log(a) - log(b)", "log(a) / log(b)"], 1,
      "O logaritmo de um produto e a soma dos logaritmos dos fatores."),

    # ------------------------------------------- Sequencias, PA e PG
    q("mat-sequencias-progressoes", B, "Razao da PA",
      "Na sequencia 2, 5, 8, 11, ... qual e a razao da progressao aritmetica?",
      ["2", "3", "4", "5"], 1,
      "A razao e a diferenca entre um termo e o anterior: 5 - 2 = 3."),
    q("mat-sequencias-progressoes", I, "Termo geral da PA",
      "Em uma PA de primeiro termo 3 e razao 4, qual e o 10o termo?",
      ["39", "40", "43", "36"], 0,
      "a10 = a1 + 9r = 3 + 9 x 4 = 3 + 36 = 39."),
    q("mat-sequencias-progressoes", I, "Soma dos termos da PA",
      "Qual e a soma dos 10 primeiros termos da PA 1, 3, 5, 7, ...?",
      ["55", "90", "100", "110"], 2,
      "a10 = 1 + 9 x 2 = 19. S10 = 10 x (1 + 19)/2 = 10 x 10 = 100."),
    q("mat-sequencias-progressoes", A, "Termo geral da PG",
      "Em uma PG de primeiro termo 2 e razao 3, qual e o 5o termo?",
      ["54", "96", "162", "486"], 2,
      "a5 = a1 x q^4 = 2 x 81 = 162."),

    # --------------------------------- Geometria plana: angulos e triangulos
    q("mat-geometria-plana", B, "Soma dos angulos do triangulo",
      "Quanto vale a soma dos angulos internos de qualquer triangulo?",
      ["90 graus", "180 graus", "270 graus", "360 graus"], 1,
      "A soma dos angulos internos de um triangulo e sempre 180 graus."),
    q("mat-geometria-plana", B, "Angulos complementares",
      "Qual e o complemento de um angulo de 35 graus?",
      ["45 graus", "55 graus", "65 graus", "145 graus"], 1,
      "Angulos complementares somam 90 graus: 90 - 35 = 55 graus."),
    q("mat-geometria-plana", I, "Teorema de Pitagoras",
      "Um triangulo retangulo tem catetos de 3 cm e 4 cm. Quanto mede a hipotenusa?",
      ["5 cm", "6 cm", "7 cm", "12 cm"], 0,
      "h^2 = 3^2 + 4^2 = 9 + 16 = 25, logo h = 5 cm."),
    q("mat-geometria-plana", I, "Angulos internos de poligonos",
      "Quanto vale a soma dos angulos internos de um hexagono?",
      ["540 graus", "620 graus", "720 graus", "1080 graus"], 2,
      "Soma = (n - 2) x 180 = (6 - 2) x 180 = 720 graus."),

    # ------------------------------------- Areas, perimetros e semelhanca
    q("mat-areas-semelhanca", B, "Area do triangulo",
      "Qual e a area de um triangulo de base 10 cm e altura 6 cm?",
      ["60 cm2", "30 cm2", "16 cm2", "80 cm2"], 1,
      "Area = (base x altura)/2 = (10 x 6)/2 = 30 cm2."),
    q("mat-areas-semelhanca", I, "Area do circulo",
      "Qual e a area aproximada de um circulo de raio 5 cm (use pi = 3,14)?",
      ["31,4 cm2", "62,8 cm2", "78,5 cm2", "157 cm2"], 2,
      "Area = pi x r^2 = 3,14 x 25 = 78,5 cm2."),
    q("mat-areas-semelhanca", I, "Razao entre areas",
      "Dois triangulos sao semelhantes com razao de semelhanca 1:3. Qual e a razao entre suas areas?",
      ["1:3", "1:6", "1:9", "1:12"], 2,
      "A razao entre areas e o quadrado da razao de semelhanca: (1/3)^2 = 1/9."),
    q("mat-areas-semelhanca", I, "Teorema de Tales",
      "Um feixe de retas paralelas determina segmentos proporcionais. Se 3 esta para 6 assim como x esta para 8, quanto vale x?",
      ["2", "4", "5", "16"], 1,
      "3/6 = x/8, entao 6x = 24 e x = 4."),

    # ------------------------------ Trigonometria no triangulo retangulo
    q("mat-trigonometria-triangulo", I, "Angulos notaveis",
      "Qual e o valor de seno de 30 graus?",
      ["1/2", "raiz(2)/2", "raiz(3)/2", "1"], 0,
      "Entre os valores notaveis, sen(30) = 1/2."),
    q("mat-trigonometria-triangulo", I, "Razoes trigonometricas",
      "Em um triangulo retangulo, o cateto oposto a um angulo mede 6 e a hipotenusa mede 10. Qual e o seno desse angulo?",
      ["0,6", "0,8", "1,25", "1,67"], 0,
      "Seno = cateto oposto / hipotenusa = 6/10 = 0,6."),
    q("mat-trigonometria-triangulo", I, "Tangente",
      "Qual e o valor da tangente de 45 graus?",
      ["1/2", "raiz(2)/2", "1", "raiz(3)"], 2,
      "Em 45 graus os catetos sao iguais, entao tangente = cateto oposto / cateto adjacente = 1."),
    q("mat-trigonometria-triangulo", A, "Aplicacao",
      "Uma rampa de 20 m de comprimento forma 30 graus com o chao. Qual e a altura atingida?",
      ["5 m", "10 m", "15 m", "20 m"], 1,
      "A altura e o cateto oposto: h = 20 x sen(30) = 20 x 0,5 = 10 m."),

    # ------------------------------------------------ Estatistica basica
    q("mat-estatistica-basica", B, "Media aritmetica",
      "Qual e a media aritmetica dos numeros 4, 7, 9 e 8?",
      ["7", "6", "8", "7,5"], 0,
      "(4 + 7 + 9 + 8)/4 = 28/4 = 7."),
    q("mat-estatistica-basica", B, "Mediana",
      "Qual e a mediana do conjunto 3, 5, 7, 9, 11?",
      ["5", "7", "8", "9"], 1,
      "Com os dados em ordem e quantidade impar de valores, a mediana e o valor central: 7."),
    q("mat-estatistica-basica", I, "Moda",
      "Qual e a moda do conjunto 2, 3, 3, 5, 7?",
      ["2", "3", "4", "5"], 1,
      "A moda e o valor que mais se repete: o 3 aparece duas vezes."),
    q("mat-estatistica-basica", I, "Amplitude",
      "Qual e a amplitude do conjunto 4, 8, 15, 16?",
      ["4", "11", "12", "16"], 2,
      "Amplitude = maior valor - menor valor = 16 - 4 = 12."),

    # --------------------------------------- Contagem e probabilidade
    q("mat-probabilidade-contagem", B, "Probabilidade simples",
      "Ao lancar um dado comum de 6 faces, qual e a probabilidade de sair um numero par?",
      ["1/2", "1/3", "1/6", "2/3"], 0,
      "Casos favoraveis: 2, 4 e 6 (tres casos) em 6 possiveis. 3/6 = 1/2."),
    q("mat-probabilidade-contagem", I, "Principio multiplicativo",
      "Com 3 camisas e 4 calcas diferentes, quantos conjuntos distintos podem ser formados?",
      ["7", "12", "16", "24"], 1,
      "Pelo principio fundamental da contagem: 3 x 4 = 12 conjuntos."),
    q("mat-probabilidade-contagem", I, "Probabilidade em baralho",
      "Em um baralho de 52 cartas, qual e a probabilidade de sortear um rei?",
      ["1/4", "1/13", "1/26", "4/13"], 1,
      "Sao 4 reis em 52 cartas: 4/52 = 1/13."),
    q("mat-probabilidade-contagem", A, "Evento complementar",
      "Qual e a probabilidade de NAO sair a face 6 no lancamento de um dado comum?",
      ["1/6", "1/2", "2/3", "5/6"], 3,
      "P(sair 6) = 1/6. O complementar e 1 - 1/6 = 5/6."),
]


def bank_stats() -> dict[str, int]:
    """Contagem por nivel — util para conferir o equilibrio do banco."""

    stats: dict[str, int] = {}
    for item in DIAGNOSTIC_BANK:
        key = item["level"].value
        stats[key] = stats.get(key, 0) + 1
    stats["total"] = len(DIAGNOSTIC_BANK)
    return stats
