"""Grade de estudos pre-configurada — Matematica, 1o ano do Ensino Medio (BNCC).

A plataforma trabalha com UMA disciplina, dividida em modulos de conteudo na
ORDEM RECOMENDADA de estudo. Cada modulo traz objetivos de aprendizagem,
conteudos relacionados e o nivel de dificuldade esperado. E daqui que sai a
trilha do aluno: o diagnostico so reordena e prioriza estes modulos
(ver app/study_plan.py), nunca inventa conteudo do nada.

Os codigos EM13MAT* sao as habilidades de Matematica do Ensino Medio na BNCC
e servem de rastreabilidade para o professor; a plataforma nao depende deles
para funcionar.

Para adicionar, remover ou reordenar modulos, edite este arquivo: o seed e
idempotente (casa por slug) e o que sair daqui e desativado no banco sem
apagar historico de aluno (ver `sync_curriculum`).
"""

from app.models import Level

CURRICULUM: list[dict] = [
    {
        "slug": "matematica",
        "name": "Matematica",
        "area": "Matematica e suas Tecnologias",
        "color": "#6366f1",
        "description": (
            "Conteudo programatico de Matematica do 1o ano do Ensino Medio: "
            "numeros, algebra, funcoes, geometria, trigonometria, estatistica "
            "e probabilidade."
        ),
        "modules": [
            {
                "slug": "mat-conjuntos-numericos",
                "title": "Conjuntos numericos e operacoes",
                "level": Level.BASICO,
                "summary": "Naturais, inteiros, racionais e reais; operacoes, potencias e raizes.",
                "objectives": [
                    "Classificar numeros nos conjuntos N, Z, Q e R",
                    "Operar com fracoes, decimais e potencias sem calculadora",
                    "Aplicar a ordem correta das operacoes",
                    "Usar notacao cientifica em numeros muito grandes ou pequenos",
                ],
                "contents": [
                    "Conjuntos N, Z, Q, I e R",
                    "Operacoes com fracoes e numeros decimais",
                    "Potenciacao e propriedades das potencias",
                    "Radiciacao e racionalizacao simples",
                    "Ordem das operacoes e uso de parenteses",
                    "Notacao cientifica e ordem de grandeza",
                ],
                "bncc_codes": ["EM13MAT104", "EM13MAT305"],
            },
            {
                "slug": "mat-razao-proporcao-porcentagem",
                "title": "Razao, proporcao e porcentagem",
                "level": Level.BASICO,
                "summary": "Grandezas proporcionais, regra de tres e matematica financeira inicial.",
                "objectives": [
                    "Resolver problemas com regra de tres simples e composta",
                    "Distinguir grandezas direta e inversamente proporcionais",
                    "Calcular acrescimos, descontos e variacoes percentuais",
                    "Aplicar juros simples em situacoes do cotidiano",
                ],
                "contents": [
                    "Razao e proporcao",
                    "Grandezas direta e inversamente proporcionais",
                    "Regra de tres simples e composta",
                    "Porcentagem, acrescimo e desconto",
                    "Variacao percentual e aumentos sucessivos",
                    "Juros simples",
                ],
                "bncc_codes": ["EM13MAT203", "EM13MAT303", "EM13MAT304"],
            },
            {
                "slug": "mat-equacoes-1-grau",
                "title": "Equacoes e inequacoes do 1o grau",
                "level": Level.BASICO,
                "summary": "Traducao de problemas em linguagem algebrica e resolucao.",
                "objectives": [
                    "Traduzir enunciados em linguagem algebrica",
                    "Resolver equacoes do 1o grau isolando a incognita",
                    "Resolver e representar inequacoes do 1o grau",
                    "Validar a solucao encontrada no contexto do problema",
                ],
                "contents": [
                    "Expressoes algebricas e valor numerico",
                    "Equacao do 1o grau",
                    "Problemas modelados por equacao do 1o grau",
                    "Inequacao do 1o grau e representacao na reta",
                ],
                "bncc_codes": ["EM13MAT301", "EM13MAT302"],
            },
            {
                "slug": "mat-sistemas-lineares",
                "title": "Sistemas de equacoes do 1o grau",
                "level": Level.BASICO,
                "summary": "Sistemas 2x2 por substituicao, adicao e interpretacao grafica.",
                "objectives": [
                    "Resolver sistemas 2x2 por substituicao e por adicao",
                    "Modelar problemas com duas incognitas",
                    "Relacionar a solucao do sistema ao encontro de duas retas",
                    "Reconhecer sistemas sem solucao ou com infinitas solucoes",
                ],
                "contents": [
                    "Sistemas lineares 2x2",
                    "Metodo da substituicao",
                    "Metodo da adicao",
                    "Interpretacao grafica da solucao",
                    "Problemas com duas incognitas",
                ],
                "bncc_codes": ["EM13MAT301", "EM13MAT510"],
            },
            {
                "slug": "mat-funcoes-conceito",
                "title": "Funcoes: conceito e representacao",
                "level": Level.INTERMEDIARIO,
                "summary": "Ideia de funcao, dominio, imagem e leitura de graficos.",
                "objectives": [
                    "Reconhecer quando uma relacao e funcao",
                    "Identificar dominio, contradominio e imagem",
                    "Ler e interpretar graficos de funcoes",
                    "Determinar zeros, crescimento e decrescimento pelo grafico",
                ],
                "contents": [
                    "Conceito de funcao e notacao f(x)",
                    "Dominio, contradominio e imagem",
                    "Representacoes: tabela, grafico e lei de formacao",
                    "Zeros da funcao e estudo do sinal",
                    "Crescimento e decrescimento",
                ],
                "bncc_codes": ["EM13MAT302", "EM13MAT401"],
            },
            {
                "slug": "mat-funcao-afim",
                "title": "Funcao afim",
                "level": Level.INTERMEDIARIO,
                "summary": "Modelagem linear, grafico, coeficientes e taxa de variacao.",
                "objectives": [
                    "Construir e interpretar o grafico da funcao afim",
                    "Explicar o papel dos coeficientes angular e linear",
                    "Calcular a raiz da funcao afim",
                    "Modelar situacoes reais com funcao do 1o grau",
                ],
                "contents": [
                    "Funcao afim f(x) = ax + b",
                    "Coeficiente angular e coeficiente linear",
                    "Grafico, raiz e estudo do sinal",
                    "Taxa de variacao media",
                    "Funcao linear e proporcionalidade",
                ],
                "bncc_codes": ["EM13MAT302", "EM13MAT401"],
            },
            {
                "slug": "mat-funcao-quadratica",
                "title": "Funcao quadratica",
                "level": Level.INTERMEDIARIO,
                "summary": "Equacao do 2o grau, parabola, vertice e problemas de otimizacao.",
                "objectives": [
                    "Resolver equacoes do 2o grau por fatoracao e por Bhaskara",
                    "Relacionar o discriminante ao numero de raizes",
                    "Determinar o vertice e usar em problemas de maximo e minimo",
                    "Esbocar a parabola a partir dos coeficientes",
                ],
                "contents": [
                    "Equacao do 2o grau e formula de Bhaskara",
                    "Discriminante (delta) e numero de raizes",
                    "Soma e produto das raizes",
                    "Grafico da parabola: concavidade, raizes e vertice",
                    "Problemas de maximo e minimo",
                ],
                "bncc_codes": ["EM13MAT302", "EM13MAT402"],
            },
            {
                "slug": "mat-funcao-exponencial-logaritmo",
                "title": "Funcao exponencial e logaritmos",
                "level": Level.AVANCADO,
                "summary": "Crescimento exponencial, equacoes exponenciais e logaritmos.",
                "objectives": [
                    "Reconhecer situacoes de crescimento e decaimento exponencial",
                    "Resolver equacoes exponenciais simples igualando as bases",
                    "Aplicar a definicao de logaritmo",
                    "Usar as propriedades operatorias dos logaritmos",
                ],
                "contents": [
                    "Funcao exponencial e seu grafico",
                    "Equacoes exponenciais",
                    "Definicao de logaritmo",
                    "Propriedades dos logaritmos",
                    "Aplicacoes: juros compostos e meia-vida",
                ],
                "bncc_codes": ["EM13MAT304", "EM13MAT403"],
            },
            {
                "slug": "mat-sequencias-progressoes",
                "title": "Sequencias, PA e PG",
                "level": Level.INTERMEDIARIO,
                "summary": "Padroes numericos, termo geral e soma de progressoes.",
                "objectives": [
                    "Identificar padroes e escrever a lei de formacao",
                    "Aplicar o termo geral e a soma da PA",
                    "Aplicar o termo geral e a soma da PG",
                    "Relacionar PA a funcao afim e PG a funcao exponencial",
                ],
                "contents": [
                    "Sequencias numericas e lei de formacao",
                    "Progressao aritmetica: termo geral e soma",
                    "Progressao geometrica: termo geral e soma",
                    "Aplicacoes em crescimento populacional e juros",
                ],
                "bncc_codes": ["EM13MAT507", "EM13MAT508"],
            },
            {
                "slug": "mat-geometria-plana",
                "title": "Geometria plana: angulos e triangulos",
                "level": Level.BASICO,
                "summary": "Angulos, classificacao de triangulos e teorema de Pitagoras.",
                "objectives": [
                    "Classificar angulos e usar relacoes entre retas paralelas",
                    "Classificar triangulos quanto a lados e angulos",
                    "Aplicar a soma dos angulos internos de poligonos",
                    "Resolver problemas com o teorema de Pitagoras",
                ],
                "contents": [
                    "Angulos: complementares, suplementares e opostos pelo vertice",
                    "Retas paralelas cortadas por transversal",
                    "Classificacao de triangulos",
                    "Soma dos angulos internos",
                    "Teorema de Pitagoras",
                ],
                "bncc_codes": ["EM13MAT308", "EM13MAT309"],
            },
            {
                "slug": "mat-areas-semelhanca",
                "title": "Areas, perimetros e semelhanca",
                "level": Level.INTERMEDIARIO,
                "summary": "Areas de figuras planas, teorema de Tales e semelhanca de triangulos.",
                "objectives": [
                    "Calcular area e perimetro de poligonos e do circulo",
                    "Aplicar o teorema de Tales",
                    "Reconhecer e usar semelhanca de triangulos",
                    "Relacionar razao de semelhanca e razao entre areas",
                ],
                "contents": [
                    "Perimetro e area de poligonos",
                    "Circunferencia e area do circulo",
                    "Teorema de Tales",
                    "Semelhanca de triangulos",
                    "Razao de semelhanca e razao entre areas",
                ],
                "bncc_codes": ["EM13MAT308", "EM13MAT509"],
            },
            {
                "slug": "mat-trigonometria-triangulo",
                "title": "Trigonometria no triangulo retangulo",
                "level": Level.INTERMEDIARIO,
                "summary": "Seno, cosseno e tangente e suas aplicacoes.",
                "objectives": [
                    "Identificar cateto oposto, adjacente e hipotenusa",
                    "Aplicar seno, cosseno e tangente na resolucao de problemas",
                    "Usar os valores notaveis de 30, 45 e 60 graus",
                    "Modelar situacoes de altura e distancia",
                ],
                "contents": [
                    "Razoes trigonometricas no triangulo retangulo",
                    "Angulos notaveis (30, 45 e 60 graus)",
                    "Relacao fundamental da trigonometria",
                    "Aplicacoes: rampas, sombras e alturas inacessiveis",
                ],
                "bncc_codes": ["EM13MAT308", "EM13MAT309"],
            },
            {
                "slug": "mat-estatistica-basica",
                "title": "Estatistica basica",
                "level": Level.BASICO,
                "summary": "Leitura de dados, medidas de tendencia central e de dispersao.",
                "objectives": [
                    "Ler e interpretar tabelas e graficos",
                    "Calcular media, moda e mediana",
                    "Interpretar amplitude e desvio como medidas de dispersao",
                    "Identificar usos enganosos de graficos e estatisticas",
                ],
                "contents": [
                    "Populacao, amostra e variaveis",
                    "Tabelas de frequencia",
                    "Graficos de barras, linhas, setores e histograma",
                    "Media, moda e mediana",
                    "Amplitude e nocao de desvio",
                ],
                "bncc_codes": ["EM13MAT102", "EM13MAT202", "EM13MAT406"],
            },
            {
                "slug": "mat-probabilidade-contagem",
                "title": "Contagem e probabilidade",
                "level": Level.INTERMEDIARIO,
                "summary": "Principio multiplicativo, arranjos simples e probabilidade.",
                "objectives": [
                    "Aplicar o principio fundamental da contagem",
                    "Diferenciar situacoes que dependem ou nao da ordem",
                    "Calcular probabilidade em espacos equiprovaveis",
                    "Calcular probabilidade de eventos complementares e da uniao",
                ],
                "contents": [
                    "Principio fundamental da contagem",
                    "Permutacoes e arranjos simples",
                    "Espaco amostral e eventos",
                    "Probabilidade em espacos equiprovaveis",
                    "Evento complementar e probabilidade da uniao",
                ],
                "bncc_codes": ["EM13MAT106", "EM13MAT310", "EM13MAT311"],
            },
        ],
    },
]


def all_module_slugs() -> list[str]:
    return [m["slug"] for subject in CURRICULUM for m in subject["modules"]]


def all_subject_slugs() -> list[str]:
    return [subject["slug"] for subject in CURRICULUM]
