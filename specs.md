# Especificações do Projeto — Plataforma Adaptativa de Matemática com IA (TCC)

Documento de referência gerado a partir da análise do código em `master`
(commit `4039a8d`, 2026-11-12). Descreve o que o sistema **faz hoje**, não o
que se pretende fazer.

---

## 1. Visão geral

Plataforma web de estudo adaptativo de **Matemática do 1º ano do Ensino Médio
(BNCC)**, com mediação pedagógica por IA (Google Gemini). Serve também de
instrumento de pesquisa: cada aluno pertence a um de dois grupos
experimentais — mediação **diretiva** ou **socrática** — e a plataforma registra
telemetria para comparação entre os grupos.

Arquitetura em 3 camadas:

1. **Frontend** — SPA React + TypeScript (Vite).
2. **Backend** — API REST FastAPI + SQLAlchemy.
3. **Orquestrador de IA** — pacote `backend/app/ai/`, única porta de saída
   para o Gemini (assíncrono, com cache, timeout, rate limit e fallback).

---

## 2. Stack técnica

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.12, FastAPI 0.115, Uvicorn, SQLAlchemy 2.0, Pydantic 2.9, pydantic-settings |
| Auth | JWT (`python-jose`, HS256), hash de senha com `passlib` + `bcrypt` |
| IA | `google-genai` 0.8 (Gemini), saída estruturada, streaming, ferramenta `google_search` |
| Banco | SQLite (padrão, zero setup) ou PostgreSQL (`psycopg2-binary`) — Neon em produção |
| Frontend | React 18, React Router 6, TypeScript 5.6, Vite 5 |
| Deploy | Render (blueprint `render.yaml`): API Python + site estático; Postgres no Neon (`neon.ts`) |

Sem dependências de UI externas no frontend (CSS próprio em `src/styles.css`).

---

## 3. Domínio pedagógico

### 3.1 Grade curricular (`app/curriculum/bncc.py`)

Uma disciplina (Matemática) com **14 módulos**, cada um com ordem recomendada,
nível, objetivos, conteúdos e códigos EM13MAT:

1. Conjuntos numéricos e operações
2. Razão, proporção e porcentagem
3. Equações e inequações do 1º grau
4. Sistemas de equações do 1º grau
5. Funções: conceito e representação
6. Função afim
7. Função quadrática
8. Função exponencial e logaritmos
9. Sequências, PA e PG
10. Geometria plana: ângulos e triângulos
11. Áreas, perímetros e semelhança
12. Trigonometria no triângulo retângulo
13. Estatística básica
14. Contagem e probabilidade

O seed é idempotente (casa módulos por `slug` e questões por hash do
enunciado). Módulos removidos da grade não são apagados: suas questões ficam
com `active = False`, preservando o histórico de tentativas.

### 3.2 Níveis

`basico → intermediario → avancado` (`LEVEL_ORDER` em `models.py`).

### 3.3 Grupos experimentais

- `diretivo`: feedback explica o erro e a resolução.
- `socratico`: feedback conduz por perguntas, sem entregar a resposta.
- Todo usuário novo nasce **socrático** (cadastro, seed do admin ou criação
  direta: default do modelo). Só admin altera o modo
  (`PATCH /admin/students/{id}/group`; demais usuários recebem 403).

---

## 4. Fluxo do aluno

1. **Cadastro / login** (`/login`). Admin é redirecionado para `/admin`.
2. **Questionário diagnóstico** (`/diagnostic`), obrigatório e único.
3. **Dashboard / trilha** (`/dashboard`) com recomendações justificadas.
4. **Módulo de estudo**: sequência fixa `MODULE_STEPS` =
   `quiz → mini aula → quiz → mini aula → quiz`. Concluir a última etapa marca
   o módulo como `concluido`.
5. Recursos extras: **Tutor** (`/tutor`, chat com IA + Live Search) e
   **Prática livre** (`/exercise`, exercícios avulsos com motor adaptativo).
6. Durante quizzes/exercícios: **dicas graduais** ("Preciso de ajuda") e
   **botão Pausar** (volta à trilha; o progresso já está salvo).

Guards de rota no frontend (`App.tsx`): aluno sem diagnóstico vai para
`/diagnostic`; diagnóstico concluído nunca reabre; `/admin` só para admin.

---

## 5. Regras de negócio

### 5.1 Diagnóstico (`study_plan.py`, `diagnostic_bank.py`)

- Banco estático de **57 questões** (4 alternativas cada) cobrindo os 14 módulos.
- Sorteio de `DIAGNOSTIC_SIZE` (padrão 12) questões por sessão:
  - rodízio entre módulos (cobertura);
  - cota de dificuldade 40% básico / 40% intermediário / 20% avançado;
  - prioridade a questões que o aluno ainda não viu.
- Alternativas embaralhadas na exibição; gabarito amarrado ao `id`.
- `DiagnosticSession` guarda os ids servidos; a submissão é corrigida contra
  essa sessão.
- Nível inicial (`assign_initial_level`): ≥80% avançado, ≥50% intermediário,
  senão básico.
- Conclusão atômica (nível, flags, fechamento da sessão e montagem da trilha
  em uma transação). Reabrir ou reenviar retorna **409**.
- Dicas são bloqueadas em questões diagnósticas (distorceriam o nivelamento).
- Opcional: `DIAGNOSTIC_AI_AUGMENT=true` mistura questões geradas por IA.

### 5.2 Trilha personalizada (`study_plan.build_study_plan`)

- `priority = base × 10 + order_index` (menor = estudar primeiro).
- `base` = acerto no módulo durante o diagnóstico (0–100).
- Módulos não medidos usam a média da disciplina (ou 0,5) e recebem +5, para
  ficar atrás de módulos medidos com o mesmo desempenho.
- Limiar de domínio: `MASTERY_THRESHOLD = 0.7`.
- Aluno pode escolher um módulo (`POST /modules/{id}/select`), que vai para a
  frente sem apagar as prioridades dos demais.

### 5.3 Questionários (`quiz_service.py`)

- Tipos: `diagnostico`, `reforco`, `pratica`. Tamanho: `QUIZ_SIZE` (padrão 5).
- **No máximo uma chamada à API por questionário.** Ordem de montagem:
  1. reaproveitar questões do banco que o aluno não viu;
  2. uma chamada em lote ao Gemini para o que faltar;
  3. acervo estático de reserva se a IA falhar.
- O questionário inteiro existe no banco antes da primeira questão ser servida.
- `/quiz/{id}/finish` avança a etapa do módulo uma única vez (idempotente).

### 5.4 Motor adaptativo da prática livre (`adaptive_engine.py`)

- Janela de `WINDOW_SIZE = 5` exercícios, sem sobreposição (contadores zeram
  ao fechar o bloco).
  - 5/5 corretas: promove de nível.
  - ≤ 1 correta (`WINDOW_SIZE // 3`): ativa reforço (`needs_remediation`).
  - Caso intermediário: mantém nível, sem reforço.
- Questão nova: banco primeiro; se não houver, gera lote de 3
  (`PREFETCH_BATCH_SIZE`) e guarda as excedentes; fallback no acervo.

### 5.5 Mini aulas (`lesson_service.py`, `ai/lessons.py`)

- Conteúdo: título, introdução, seções, conceitos-chave, exemplos resolvidos,
  diagrama Mermaid opcional, resumo — focado nos erros recentes do aluno.
- Persistidas por `cache_key` e reaproveitadas entre alunos na mesma situação.
- "Explicar de outro jeito" via streaming (`POST /lessons/{id}/reexplain`),
  limitado a `LESSON_REEXPLAIN_LIMIT` (padrão 1) por aluno e por aula. O uso
  fica em `lesson_views.reexplain_count` (reserva atômica; devolvido se nada
  foi gerado) e o texto em `lesson_views.reexplain_text`. Acima do limite: 409.
- Sem IA: aula de reserva montada com objetivos e conteúdos do módulo.
- `POST /lessons/{id}/complete` registra `LessonView` e avança a trilha.

### 5.6 Correção e feedback (`routers/exercises.py`, `ai/feedback.py`)

- Correção é **100% no servidor**; `QuestionOut` nunca expõe
  `correct_alternative_id`.
- Submissão responde na hora, sem chamar IA. O feedback chega depois por SSE
  (`GET /feedback/{attempt_id}/stream`) e fica salvo em
  `attempts.feedback_text` (recarregar não gera nova chamada).
- Grupo diretivo: streaming token a token.
- Grupo socrático: **sem streaming** — o filtro anti-vazamento precisa do
  texto completo; a resposta chega de uma vez, já filtrada.
- Aviso de IA indisponível não é gravado em `feedback_text`, para que o
  feedback real seja gerado quando a API voltar.

### 5.7 Anti-vazamento do gabarito

- Feedback socrático, duas camadas:
  1. auto-relato do Gemini via saída estruturada (`contains_final_answer`);
  2. heurística: texto/letra da alternativa correta na saída normalizada.
- Dicas (`ai/hints.py`), três camadas, aplicadas aos **dois** grupos:
  1. auto-relato do Gemini;
  2. texto da alternativa correta presente;
  3. número que só existe na resposta (não no enunciado) aparece na dica, ou
     menção a alternativa específica ("alternativa b", "letra c").
- Se qualquer camada disparar: texto descartado, substituído por scaffold
  de reserva, evento registrado (`leak_detected`).

### 5.8 Dicas durante a questão (`routers/hints.py`, `ai/hints.py`)

- Até `MAX_HINTS = 3` por questão, graduais: (1) o que a questão pede,
  (2) primeiro passo, (3) quase lá.
- A resolução do professor vai ao prompt como material confidencial.
- Reuso entre alunos: dica válida (sem vazamento, sem fallback) da mesma
  ordem e mesma questão é reaproveitada sem chamar a API (`reused = True`).
- IA indisponível: devolve dica de reserva **sem consumir** a cota de dicas
  do aluno (`degraded = True`).
- Exige diagnóstico concluído.

### 5.9 Tutor com Live Search (`routers/tutor.py`, `ai/search.py`)

- `POST /tutor/ask` responde por SSE.
- Ferramenta `google_search` habilitada por heurística (pergunta depende de
  informação atual) ou override manual na interface; requer
  `LIVE_SEARCH_ENABLED=true`.
- Fontes retornam no evento `sources`.

### 5.10 Segurança contra prompt injection

Conteúdo vindo do aluno é delimitado (`<<<CONTEXTO_ALUNO>>>` e similares) e o
system prompt manda tratá-lo como dado, nunca como instrução.

---

## 6. Modelo de dados (`models.py`)

| Tabela | Propósito / campos-chave |
|---|---|
| `users` | email, senha (hash), `group`, `is_admin`, `level`, `diagnostic_completed(_at)`, contadores da janela (`window_count`, `window_correct`, `needs_remediation`) |
| `subjects` | disciplina (slug, nome, área, cor, ordem) |
| `modules` | módulo da grade: slug, título, ordem, nível, `objectives`, `contents`, `bncc_codes` (JSON) |
| `user_module_progress` | trilha: `priority`, `status` (nao_iniciado/em_andamento/concluido), `step_index`, acertos totais e do diagnóstico. Único por (user, module) |
| `questions` | enunciado, `alternatives` (JSON), `correct_alternative_id` (nunca serializado), explicação diretiva, flags `is_remedial`/`is_diagnostic`/`generated`/`active`, `statement_hash`, vínculo a módulo |
| `diagnostic_sessions` | ids sorteados para o diagnóstico do aluno |
| `quizzes` | questionário completo: tipo, nível, `question_ids`, índice atual, acertos |
| `lessons` | mini aula persistida por `cache_key` |
| `lesson_views` | conclusão de mini aula por aluno |
| `attempts` | resposta: alternativa, acerto, nível no momento, `feedback_text` |
| `interaction_logs` | telemetria do feedback: modo, latência Gemini, `leak_detected`, `fallback_used`, trecho da saída |
| `hint_requests` | dica pedida: ordem, conteúdo, modo, latência, `leak_detected`, `fallback_used`, `reused` |

Migração: `create_all` cria tabelas novas; `migrations.py` adiciona colunas a
bancos antigos (nunca remove).

---

## 7. API REST

Autenticação por Bearer JWT (exceto register/login/health). Docs em `/docs`.

| Método | Rota | Descrição |
|---|---|---|
| POST | `/auth/register` | cadastro; sorteia grupo; retorna token |
| POST | `/auth/login` | form OAuth2 (username = email); retorna token |
| GET | `/auth/me` | usuário atual |
| GET | `/diagnostic` | sorteia/serve diagnóstico (409 se concluído) |
| POST | `/diagnostic/submit` | corrige, define nível, monta trilha (409 se concluído) |
| GET | `/exercises/next` | próxima questão da prática livre |
| POST | `/exercises/submit` | corrige e atualiza janela adaptativa |
| GET | `/feedback/{attempt_id}/stream` | feedback por SSE |
| GET | `/feedback/{attempt_id}` | feedback completo (não streaming) |
| GET | `/progress` | progresso do aluno |
| GET | `/next-step` | próxima etapa da trilha |
| GET | `/study-plan` | painel: nível, aproveitamento, recomendações justificadas, grade com status |
| GET | `/subjects` | grade curricular |
| POST | `/modules/{id}/select` | aluno escolhe módulo |
| GET | `/modules/{id}/lesson` | mini aula do módulo |
| POST | `/lessons/{id}/reexplain` | explicação alternativa por SSE (limitada por aula) |
| GET | `/lessons/{id}` | mini aula por id |
| POST | `/lessons/{id}/complete` | conclui aula e avança trilha |
| POST | `/quiz/start` | cria questionário completo (201) |
| GET | `/quiz` | lista questionários do aluno (`limit` ≤ 50) |
| GET | `/quiz/{id}` | questionário |
| POST | `/quiz/{id}/answer` | responde questão (correção imediata) |
| POST | `/quiz/{id}/finish` | fecha e avança trilha (idempotente) |
| GET | `/questions/{id}/hints` | dicas já recebidas |
| POST | `/questions/{id}/hint` | pede próxima dica (body opcional `quiz_id`) |
| POST | `/tutor/ask` | pergunta ao tutor (SSE, Live Search) |
| GET | `/admin/stats` | estatísticas por grupo (admin) |
| GET | `/admin/students` | lista alunos (admin) |
| PATCH | `/admin/students/{id}/group` | altera grupo do aluno (admin) |
| GET | `/health` | status, IA configurada, modelo, `ai_quota_blocked_for`, stats do cache |

`/admin/stats` por grupo: total de alunos, tentativas, acurácia (sem
diagnóstico), distribuição de nível, latência média do Gemini, contagem/taxa
de vazamento detectado, contagem de fallback.

---

## 8. Orquestrador de IA (`backend/app/ai/`)

| Arquivo | Responsabilidade |
|---|---|
| `client.py` | cliente assíncrono (`client.aio`), timeout, semáforo de concorrência, `generate_structured`, `stream_text`, fontes de grounding; erro 429 vira `AIQuotaExceeded` com bloqueio temporário (falha rápida) |
| `cache.py` | cache TTL em memória com *single-flight* |
| `prompts.py` | todos os system prompts |
| `schemas.py` | formatos de saída estruturada (ex.: `GeminiHint`) |
| `feedback.py` | feedback diretivo/socrático + anti-vazamento |
| `questions.py` | geração de questões em lote, validação estrutural (4 alternativas, ids únicos, gabarito entre elas) |
| `lessons.py` | mini aulas |
| `hints.py` | dicas graduais + filtro de 3 camadas |
| `search.py` | tutor com Live Search |
| `sse.py` | formatação de eventos SSE |

Temperaturas: feedback `GEMINI_TEMPERATURE` (0,1), questões 0,6, aulas 0,4,
dicas 0,3. `gemini_orchestrator.py` é camada de compatibilidade que reexporta
`app.ai`.

Degradação sem chave ou sem cota: questões do acervo estático, aula de
reserva, dica/feedback genéricos; nada trava a requisição.

---

## 9. Frontend (`frontend/src/`)

- `api/client.ts`: chamadas HTTP com JWT; `streamSSE` usa `fetch` + reader
  (porque `EventSource` não envia header `Authorization`).
- `context/AuthContext.tsx`: sessão, `refresh()` relê `/auth/me`.
- Páginas: `Login`, `Diagnostic`, `Dashboard`, `Quiz`, `Lesson`, `Tutor`,
  `Exercise`, `Admin`.
- Componentes: `QuestionCard`, `AiFeedback` (streaming com placeholder),
  `HintSheet` (dicas), `PauseButton`, `Markdown`, `Loading` (skeleton +
  mensagens rotativas), `Progress`, `Icons`.
- Base da API via `VITE_API_BASE`.
- Título da aplicação no cabeçalho: "Meu Tutor".

---

## 10. Configuração (variáveis de ambiente)

| Variável | Padrão (`.env.example`) | Função |
|---|---|---|
| `GEMINI_API_KEY` | vazio | chave do Gemini; vazio = modo degradado |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | modelo (default no código: `gemini-2.5-flash`) |
| `GEMINI_TEMPERATURE` | 0.1 | temperatura do feedback |
| `GEMINI_RATE_LIMIT_PER_MINUTE` | 30 | chamadas por usuário/minuto (429 ao estourar) |
| `GEMINI_TIMEOUT_SECONDS` | 25 | timeout por chamada |
| `GEMINI_MAX_CONCURRENCY` | 8 | chamadas simultâneas por processo |
| `AI_CACHE_TTL_SECONDS` / `AI_CACHE_MAX_ENTRIES` | 1800 / 512 | cache em memória |
| `QUIZ_SIZE` | 5 | questões por questionário |
| `DIAGNOSTIC_SIZE` | 12 | questões do diagnóstico |
| `DIAGNOSTIC_AI_AUGMENT` | false | mistura questões geradas no diagnóstico |
| `LIVE_SEARCH_ENABLED` | true | busca Google no tutor |
| `JWT_SECRET_KEY` / `JWT_ALGORITHM` / `JWT_EXPIRE_MINUTES` | — / HS256 / 120 | tokens |
| `DATABASE_URL` | `sqlite:///./tcc.db` | conexão do banco |
| `CORS_ORIGINS` | localhost:5173 | origens permitidas |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | `admin@tccadmin.com` / `admin123` | conta admin criada no start |

---

## 11. Execução e deploy

- Backend: `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000`
  (ou `backend/start.sh`). Seed automático no primeiro start.
- Frontend: `cd frontend && npm install && npm run dev` (porta 5173);
  build: `tsc -b && vite build`.
- Produção (Render, região Ohio):
  - `tcc-mat-adaptativa-api` — Python, health check `/health`;
  - `tcc-mat-adaptativa` — site estático `dist/`, rewrite SPA `/* → /index.html`;
  - Postgres no Neon (`DATABASE_URL` no painel).

---

## 12. Limitações conhecidas

- Rate limit e cache em memória, por processo (trocar por Redis se escalar).
- Sessões SQLAlchemy síncronas dentro de endpoints assíncronos.
- Gabarito gerado pela IA validado só estruturalmente, sem verificação
  matemática formal.
- Cota do free tier do Gemini é o gargalo prático (`/health` mostra bloqueio).
- Testes em `backend/tests` (pytest) cobrem modo padrão/permissão, limite de
  reexplicação, questões erradas do diagnóstico e o filtro com LaTeX. Ainda
  sem cobertura: `adaptive_engine`,
  `study_plan.sample_diagnostic`, filtros anti-vazamento (`httpx` necessário
  para `TestClient`).
- Contas que fizeram o diagnóstico antigo (3 questões) não refazem o novo;
  recebem trilha em ordem pedagógica pura.
- Senha admin padrão fraca: trocar antes de expor.

## 13. Inconsistências encontradas na documentação

- README cita banco diagnóstico "de ~90" em um trecho e "57 questões" em
  outro; o código tem **57**.
- Default de `GEMINI_MODEL` difere entre `config.py` (`gemini-2.5-flash`) e
  `.env.example`/`render.yaml` (`gemini-3.5-flash-lite`).
- README não documenta as dicas (`/questions/{id}/hint`, tabela
  `hint_requests`) nem o botão Pausar, adicionados no último commit; a seção
  "Estrutura" também omite `routers/hints.py` e `ai/hints.py`.
