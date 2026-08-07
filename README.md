# Plataforma Adaptativa com Gemini — implementação de referência

Implementação da arquitetura de 3 camadas descrita na especificação do TCC
(React SPA / FastAPI / Orquestrador Gemini), com os ajustes da revisão
técnica aplicados. Banco padrão é SQLite (zero setup); trocar para
Postgres é so mudar `DATABASE_URL` — o código usa SQLAlchemy.

## Como rodar

### Backend

```bash
cd backend
python -m venv venv
./venv/Scripts/activate        # Windows (PowerShell: venv\Scripts\Activate.ps1)
pip install -r requirements.txt
cp .env.example .env            # preencher GEMINI_API_KEY
uvicorn app.main:app --reload --port 8000
```

Docs interativas em `http://localhost:8000/docs`. O banco é populado
automaticamente com questões de exemplo no primeiro start (`app/seed.py`).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Abre em `http://localhost:5173`. Já testado: `tsc -b` e `vite build` passam
sem erros; fluxo completo (registro → diagnóstico → exercícios → promoção/
remediação → feedback) validado via curl contra o backend rodando.

### Login de admin

Uma conta admin é criada automaticamente no primeiro start, com as
credenciais de `ADMIN_EMAIL` / `ADMIN_PASSWORD` do `.env` (padrão:
`admin@tccadmin.com` / `admin123` — **troque a senha** antes de expor a
aplicação fora da sua máquina). Login de admin usa o mesmo formulário de
login do aluno; a aplicação detecta `is_admin` e redireciona para
`/admin` automaticamente. Alunos se cadastram normalmente pela aba
"Criar conta" do login (`/auth/register`).

## Onde cada ajuste da revisão foi aplicado

| Problema apontado na revisão | Onde foi corrigido |
|---|---|
| Threshold da janela móvel inconsistente (66% descrito como "2 erros em 3", que na verdade é 33%) | `backend/app/adaptive_engine.py::evaluate_window` — regra de 3 faixas explícita (100% promove, 66% mantém nível, 0-33% aciona reforço), com o cálculo e a justificativa documentados no docstring |
| Gap: o que acontece entre "básico→intermediário" e os demais níveis | `LEVEL_ORDER` genérico em `models.py`, promoção percorre a lista (básico→intermediário→avançado) |
| Gabarito não podia vazar para o client antes da submissão | `schemas.py::QuestionOut` nunca inclui `correct_alternative_id`; toda comparação ocorre em `routers/exercises.py` no servidor, contra o valor armazenado no banco |
| Filtro anti-vazamento do modo socrático era vago | `app/ai/feedback.py` (antes `gemini_orchestrator.py`) — dupla camada: (1) saída estruturada (`response_schema`) força o próprio Gemini a se auto-reportar (`contains_final_answer`); (2) filtro heurístico (`_heuristic_leak_detected`) compara a saída normalizada contra o texto/letra do gabarito. Se qualquer um disparar, a resposta é descartada e substituída por um scaffold genérico pré-definido, e o evento fica registrado (`leak_detected`) para análise |
| Prompt injection não endereçado | Conteúdo vindo do aluno é delimitado explicitamente (`<<<CONTEXTO_ALUNO>>>`) e o system prompt instrui a tratá-lo como dado, nunca como instrução, mesmo se o aluno alegar ser professor/admin ou pedir para ignorar as regras |
| Falta de logging/telemetria para o experimento | Tabela `InteractionLog` (`models.py`) grava, por tentativa: modo (diretivo/socrático), latência do Gemini, se houve vazamento detectado, se caiu no fallback |
| Sem controle de custo/rate limit do Gemini | `rate_limit.py` — limite configurável de chamadas por usuário por minuto (`GEMINI_RATE_LIMIT_PER_MINUTE`), retorna 429 ao estourar |
| "Latência garantida < 3s" era forte demais para dependência externa | Chamada ao Gemini isolada em `app/ai/client.py`, com timeout explícito (`GEMINI_TIMEOUT_SECONDS`) e degradação para o acervo estático — se a API falhar ou demorar, o sistema não trava a requisição |
| n=3 no diagnóstico é amostra fraca | Resolvido na segunda rodada: o diagnóstico passou a ter 12 questões (`DIAGNOSTIC_SIZE`) sorteadas de um banco de ~90, o que sustenta as três faixas de `assign_initial_level`. Ver a seção "Questionário Diagnóstico" abaixo |
| Faltava visão agregada pra análise do experimento (diretivo vs socrático) | `routers/admin.py::/admin/stats` — acurácia, distribuição de nível, latência média do Gemini e taxa de vazamento detectado, por grupo. Protegido por `is_admin` (`security.py::get_current_admin`) |

## Segunda rodada de melhorias

Esta seção descreve o que mudou depois da primeira versão, e por quê.

### 1. Desempenho da geração de conteúdo

| Gargalo | O que foi feito |
|---|---|
| Chamadas ao Gemini eram **síncronas** dentro do request, serializando alunos no mesmo worker | Toda a camada de IA virou assíncrona (`app/ai/client.py`, usando `client.aio`), com timeout e limite de concorrência por processo |
| **Uma chamada por questão** | Geração em lote: um questionário inteiro sai de uma única chamada (`app/ai/questions.py`). Nos exercícios avulsos, `adaptive_engine` gera um lote de 3 e guarda as excedentes, então uma chamada cobre vários exercícios |
| Conteúdo idêntico era regerado para cada aluno | Cache TTL em memória com *single-flight* (`app/ai/cache.py`) + reaproveitamento no banco: antes de chamar a API, o sistema procura questões que o aluno ainda não viu. Mini aulas ficam persistidas por `cache_key` e são reusadas por qualquer aluno na mesma situação |
| O aluno esperava a IA escrever a explicação inteira antes de saber se acertou | `POST /exercises/submit` e `POST /quiz/{id}/answer` **não chamam mais o Gemini**: devolvem a correção na hora. O feedback chega depois por SSE (`GET /feedback/{attempt_id}/stream`) e aparece token a token |
| Feedback regerado ao recarregar a página | O texto fica salvo em `attempts.feedback_text` e o stream replica do banco, sem nova chamada |
| Espera sem sinal de progresso | `components/Loading.tsx` (skeleton + mensagens rotativas), cursor de digitação e `<AiFeedback>` com placeholder |

### 2. Questionário Diagnóstico

- Banco de 57 questões de Matemática (`app/diagnostic_bank.py`) cobrindo os 14
  módulos da grade, cada uma marcada com o módulo que avalia.
- Sorteio por sessão (`study_plan.sample_diagnostic`): rodízio entre os
  conteúdos, cota de dificuldade (40% básico / 40% intermediário / 20%
  avançado) e prioridade para questões que o aluno ainda não viu.
- Alternativas embaralhadas na exibição (o gabarito continua amarrado ao `id`,
  então a correção no servidor não muda).
- `DiagnosticSession` guarda o conjunto servido; a submissão é corrigida
  contra essa sessão, e não contra o banco inteiro.
- Com 12 questões em vez de 3, `assign_initial_level` passou a usar três
  faixas (≥80% avançado, ≥50% intermediário, senão básico).
- Geração por IA em lote existe como complemento opcional
  (`DIAGNOSTIC_AI_AUGMENT`), fora do caminho crítico do primeiro acesso.

### 3. Fluxo do primeiro login (bug corrigido)

A causa era no frontend: `Diagnostic.tsx` navegava para a próxima tela **sem
atualizar o usuário em memória**, que continuava com `diagnostic_completed:
false`; o guard de rota então devolvia o aluno ao mesmo questionário.

O que mudou:

- `Diagnostic.tsx` chama `refresh()` (que relê `/auth/me`) e só então navega,
  agora para `/dashboard`.
- `/diagnostic` e `/diagnostic/submit` retornam **409** se o diagnóstico já foi
  concluído — não dá para reabrir nem reenviar.
- A conclusão é atômica: nível, `diagnostic_completed`, `diagnostic_completed_at`,
  fechamento da sessão e montagem da trilha em uma única transação.
- `DiagnosticRoute` redireciona para `/dashboard` quando já concluído, e
  `defaultRouteFor` passou a apontar para o dashboard.

### 4. Questionário de reforço completo

`POST /quiz/start` devolve o questionário inteiro. A ordem de montagem
(`app/quiz_service.py`) é: reaproveitar questões do banco que o aluno não viu →
uma chamada em lote para o que faltar → acervo de reserva se a IA falhar.
Nenhuma questão é gerada no meio do questionário.

### 5. Dashboard inteligente

`GET /study-plan` devolve, em poucas consultas agregadas: nível, aproveitamento,
módulos concluídos, conclusão geral, recomendações **com justificativa**
("você acertou 0% deste conteúdo no diagnóstico"), conteúdos a reforçar e a
grade inteira com status, % de conclusão e desempenho por módulo.

A prioridade é explicável de propósito: `priority = desempenho × 10 + ordem
pedagógica` — pior desempenho sobe, e empates preservam a sequência da BNCC.
O aluno pode assumir o controle: `POST /modules/{id}/select` põe o módulo
escolhido na frente sem apagar o cálculo dos demais.

### 6. Grade pré-configurada (BNCC) — Matemática

`app/curriculum/bncc.py`: **Matemática do 1º ano do Ensino Médio, dividida em
14 módulos de conteúdo**, cada um com ordem recomendada, objetivos de
aprendizagem, conteúdos relacionados, nível e códigos EM13MAT:

1. Conjuntos numéricos e operações · 2. Razão, proporção e porcentagem ·
3. Equações e inequações do 1º grau · 4. Sistemas de equações do 1º grau ·
5. Funções: conceito e representação · 6. Função afim · 7. Função quadrática ·
8. Função exponencial e logaritmos · 9. Sequências, PA e PG ·
10. Geometria plana: ângulos e triângulos · 11. Áreas, perímetros e semelhança ·
12. Trigonometria no triângulo retângulo · 13. Estatística básica ·
14. Contagem e probabilidade

O seed é idempotente e casado por hash do enunciado: editar `bncc.py` ou
`diagnostic_bank.py` e reiniciar reorganiza a grade **e** realinha as questões
já gravadas ao módulo correto, sem duplicar nada.

O que sai da grade não é apagado — é aposentado. Módulos removidos somem, mas
suas questões viram `active = False` (`Question.active`), de modo que o
histórico de tentativas do aluno continua íntegro enquanto a questão nunca mais
é sorteada. Foi assim que a plataforma passou de 9 disciplinas para só
Matemática sem perder dados.

### 7. Mini aula entre questionários

O fluxo de um módulo agora é `questionário → mini aula → questionário → mini
aula → questionário`, definido em `MODULE_STEPS` (`models.py`) — mudar essa
lista muda o fluxo inteiro, nada mais no código assume o tamanho dela.

A mini aula (`GET /modules/{id}/lesson`) traz explicação, conceitos-chave,
exemplos resolvidos, diagrama opcional (Mermaid) e resumo, focados nos erros
recentes do aluno. `POST /lessons/{id}/complete` avança a trilha e já aponta o
próximo questionário.

### 8. Streaming + Live Search

- Streaming: feedback do erro, explicação alternativa da mini aula e respostas
  do tutor, todos por SSE. O front consome com `fetch` + reader
  (`api/client.ts::streamSSE`) porque `EventSource` não permite header
  `Authorization`.
- Live Search: `POST /tutor/ask` habilita a ferramenta `google_search` do
  Gemini quando a pergunta depende de informação atual (heurística em
  `app/ai/search.py`, com override manual na interface). As fontes usadas
  voltam no evento `sources` e aparecem na resposta.
- **Por que o modo socrático não faz streaming:** o filtro anti-vazamento
  precisa do texto inteiro para decidir. Transmitir token a token exibiria o
  gabarito por uma fração de segundo antes do filtro agir. Esse grupo recebe o
  texto de uma vez, já filtrado — e a responsividade vem de a correção não
  esperar mais a IA.

## Estrutura

```
backend/
  app/
    config.py                  variáveis de ambiente
    database.py                engine/session SQLAlchemy
    models.py                  User, Subject, Module, UserModuleProgress,
                               Question, Quiz, Lesson, Attempt, InteractionLog
    migrations.py              migração aditiva (colunas novas em bancos antigos)
    schemas.py                 Pydantic (separa o que pode ir pro client)
    security.py                hash de senha, JWT
    text_utils.py              normalização/hash de enunciado (deduplicação)
    adaptive_engine.py         janela móvel + próxima questão (com prefetch)
    study_plan.py              sorteio do diagnóstico, prioridades, painel
    quiz_service.py            montagem e correção de questionários
    lesson_service.py          obtenção e conclusão de mini aulas
    diagnostic_bank.py         banco de questões do diagnóstico
    curriculum/bncc.py         grades pré-configuradas (BNCC, 1º ano EM)
    ai/
      client.py                única porta de saída para o Gemini (async)
      cache.py                 cache TTL com single-flight
      prompts.py               todos os prompts
      schemas.py               formatos de saída estruturada
      feedback.py              mediação diretiva/socrática + anti-vazamento
      questions.py             autoria de questionários em lote
      lessons.py               mini aulas
      search.py                tutor com Live Search
      sse.py                   formatação dos eventos de streaming
    rate_limit.py              limite de chamadas ao Gemini
    seed.py                    carga inicial idempotente
    routers/
      auth.py                  /auth/register /auth/login /auth/me
      exercises.py             /diagnostic, /exercises/*, /feedback/*, /progress
      learning.py              /study-plan, /subjects, /next-step, mini aulas
      quiz.py                  /quiz/start, /quiz/{id}/answer, /quiz/{id}/finish
      tutor.py                 /tutor/ask (SSE + Live Search)
      admin.py                 /admin/stats (protegido por is_admin)
frontend/
  src/
    api/client.ts              chamadas HTTP + JWT + consumo de SSE
    context/AuthContext.tsx    estado de sessão
    components/                QuestionCard, AiFeedback, Markdown, Loading,
                               Progress, Icons
    pages/                     Login, Diagnostic, Dashboard, Quiz, Lesson,
                               Tutor, Exercise, Admin
```

`app/gemini_orchestrator.py` continua existindo como camada de compatibilidade
para imports antigos, reexportando o pacote `app.ai`.

## Limitações conhecidas / próximos passos

- Rate limit e cache são em memória (por processo) — ok para TCC/demo, trocar
  por Redis se for rodar múltiplas instâncias.
- Bancos criados pela versão anterior são migrados automaticamente no start
  (`app/migrations.py` adiciona só colunas, nunca remove). Contas que já tinham
  concluído o diagnóstico antigo (de 3 questões) **não** repetem o novo: elas
  recebem a trilha na ordem pedagógica pura, sem priorização por desempenho.
  Para reavaliá-las, basta zerar `users.diagnostic_completed`.
- As sessões do SQLAlchemy são síncronas dentro de endpoints assíncronos.
  Com SQLite local as consultas são curtas o bastante para isso não pesar; ao
  migrar para Postgres sob carga real, vale trocar por driver assíncrono.
- Sem `GEMINI_API_KEY` (ou com a cota estourada) o sistema degrada em vez de
  quebrar: questões vêm do acervo estático e a mini aula cai na versão de
  reserva montada com os objetivos e conteúdos do próprio módulo.
- **Cota da API é o gargalo prático do free tier.** O `gemini-2.5-flash` tem
  limite de 20 requisições/dia; estourado ele, *todo* feedback caía no texto
  genérico de falha. Três providências: o erro 429 virou um tipo próprio
  (`AIQuotaExceeded`), com log explícito e mensagem honesta para o aluno; um
  bloqueio temporário faz as chamadas seguintes falharem na hora, em vez de
  gastar segundos para receber outro 429 (`GET /health` mostra
  `ai_quota_blocked_for`); e o aviso de indisponibilidade **não** é gravado em
  `attempts.feedback_text`, para que o feedback real seja gerado quando a API
  voltar. Se o feedback parar de sair, cheque `/health` e troque
  `GEMINI_MODEL` por um modelo com cota disponível.
- O gabarito gerado pela IA é validado apenas **estruturalmente** (4
  alternativas com ids únicos, gabarito entre elas). Não há verificação
  matemática formal; o prompt pede autoconferência, o que reduz mas não elimina
  erro de gabarito.
- Sem testes automatizados ainda. O fluxo completo (registro → diagnóstico →
  trilha → questionário → mini aula → questionário) foi validado manualmente
  contra o backend rodando, incluindo o replay de feedback pelo cache; vale
  adicionar pytest cobrindo `adaptive_engine`, `study_plan.sample_diagnostic` e
  o filtro anti-vazamento antes de usar em coleta de dados real.
  Para usar `fastapi.testclient` é preciso instalar `httpx` (não é dependência
  de execução).
