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
| Filtro anti-vazamento do modo socrático era vago | `gemini_orchestrator.py` — dupla camada: (1) saída estruturada (`response_schema`) força o próprio Gemini a se auto-reportar (`contains_final_answer`); (2) filtro heurístico (`_heuristic_leak_detected`) compara a saída normalizada contra o texto/letra do gabarito. Se qualquer um disparar, a resposta é descartada e substituída por um scaffold genérico pré-definido, e o evento fica registrado (`leak_detected`) para análise |
| Prompt injection não endereçado | Conteúdo vindo do aluno é delimitado explicitamente (`<<<CONTEXTO_ALUNO>>>`) e o system prompt instrui a tratá-lo como dado, nunca como instrução, mesmo se o aluno alegar ser professor/admin ou pedir para ignorar as regras |
| Falta de logging/telemetria para o experimento | Tabela `InteractionLog` (`models.py`) grava, por tentativa: modo (diretivo/socrático), latência do Gemini, se houve vazamento detectado, se caiu no fallback |
| Sem controle de custo/rate limit do Gemini | `rate_limit.py` — limite configurável de chamadas por usuário por minuto (`GEMINI_RATE_LIMIT_PER_MINUTE`), retorna 429 ao estourar |
| "Latência garantida < 3s" era forte demais para dependência externa | Chamada ao Gemini isolada em `gemini_orchestrator.py` com try/except em `routers/exercises.py` — se a API falhar ou demorar, o sistema não quebra: cai em mensagem de fallback genérica e loga o evento, em vez de travar a requisição |
| n=3 no diagnóstico é amostra fraca | Mantido conforme a spec (é decisão de desenho do experimento, não um bug), mas o mapeamento em `assign_initial_level` é conservador de propósito (só promove direto para intermediário com 100% de acerto) e a ressalva metodológica fica documentada aqui e no docstring da função |
| Faltava visão agregada pra análise do experimento (diretivo vs socrático) | `routers/admin.py::/admin/stats` — acurácia, distribuição de nível, latência média do Gemini e taxa de vazamento detectado, por grupo. Protegido por `is_admin` (`security.py::get_current_admin`) |

## Estrutura

```
backend/
  app/
    config.py              variáveis de ambiente
    database.py             engine/session SQLAlchemy
    models.py                User, Question, Attempt, InteractionLog
    schemas.py                Pydantic (separa o que pode ir pro client)
    security.py               hash de senha, JWT
    adaptive_engine.py        janela móvel + seleção de próxima questão
    gemini_orchestrator.py    prompts diretivo/socrático, filtro anti-vazamento
    rate_limit.py              limite de chamadas ao Gemini
    seed.py                    banco de questões de exemplo
    routers/
      auth.py                  /auth/register /auth/login /auth/me
      exercises.py             /diagnostic, /exercises/*, /progress
      admin.py                 /admin/stats (protegido por is_admin)
frontend/
  src/
    api/client.ts              chamadas HTTP + JWT
    context/AuthContext.tsx    estado de sessão
    pages/                     Login, Diagnostic, Exercise, Dashboard, Admin
```

## Limitações conhecidas / próximos passos

- Rate limit é em memória (por processo) — ok para TCC/demo, trocar por
  Redis se for rodar múltiplas instâncias.
- `google-genai` precisa de `GEMINI_API_KEY` real em `.env` para gerar
  feedback de fato; sem a chave, o sistema cai no fallback gracioso (já
  testado) em vez de quebrar.
- Sem testes automatizados ainda (o fluxo foi validado manualmente via
  curl neste ambiente); vale adicionar pytest cobrindo `adaptive_engine`
  e o filtro anti-vazamento antes de usar em coleta de dados real.
