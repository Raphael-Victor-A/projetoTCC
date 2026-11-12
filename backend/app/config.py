from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECT_DIR = _BACKEND_DIR.parent


class Settings(BaseSettings):
    # Ordem de prioridade (maior primeiro): variaveis de ambiente reais (Render)
    # > backend/.env > .env.local da raiz (gerado por `neon env pull`/`neon deploy`,
    # contem DATABASE_URL do Neon). Arquivos ausentes sao ignorados.
    model_config = SettingsConfigDict(
        env_file=(_PROJECT_DIR / ".env.local", _BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_temperature: float = 0.1
    gemini_rate_limit_per_minute: int = 30

    # Timeout (segundos) aplicado a qualquer chamada ao Gemini. Impede que uma
    # chamada travada segure a requisicao do aluno indefinidamente: estourou,
    # cai no banco de reserva estatico.
    gemini_timeout_seconds: float = 25.0

    # Numero maximo de chamadas simultaneas ao Gemini no processo inteiro.
    # Protege contra rajadas de paralelismo (geracao em lote + prefetch).
    gemini_max_concurrency: int = 8

    # Cache em memoria de conteudo gerado (questoes em lote e mini aulas).
    # Conteudo didatico nao muda a cada segundo, entao reaproveitar por alguns
    # minutos elimina a maior parte das chamadas repetidas a API.
    ai_cache_ttl_seconds: int = 1800
    ai_cache_max_entries: int = 512

    # Quantas questoes um questionario de reforco/pratica traz. Todas sao
    # geradas em UMA unica chamada ao Gemini (ver app/ai/questions.py).
    quiz_size: int = 5

    # Quantas questoes o Questionario Diagnostico apresenta, sorteadas de um
    # banco grande com equilibrio entre disciplinas e niveis de dificuldade.
    diagnostic_size: int = 12

    # Quando ligado, o diagnostico mistura questoes ineditas geradas por IA ao
    # banco estatico (1 unica chamada em lote, com cache). Desligado por padrao
    # para que o primeiro acesso seja instantaneo.
    diagnostic_ai_augment: bool = False

    # Quantas vezes cada aluno pode pedir "explicar de outro jeito" em uma
    # mesma mini aula. Validado no backend (lesson_views.reexplain_count).
    lesson_reexplain_limit: int = 1

    # Live Search: permite que o tutor consulte a busca do Google via
    # grounding do Gemini quando a pergunta pede informacao atual.
    live_search_enabled: bool = True

    jwt_secret_key: str = "troque-este-valor"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 120

    database_url: str = "sqlite:///./tcc.db"

    # Origens autorizadas a chamar a API (CORS), separadas por virgula.
    # Em producao, inclua a URL publica do frontend.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]

    admin_email: str = "admin@tccadmin.com"
    admin_password: str = "admin123"


settings = Settings()
