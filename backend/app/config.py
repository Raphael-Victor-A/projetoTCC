from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_temperature: float = 0.1
    gemini_rate_limit_per_minute: int = 30

    jwt_secret_key: str = "troque-este-valor"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 120

    database_url: str = "sqlite:///./tcc.db"

    admin_email: str = "admin@tccadmin.com"
    admin_password: str = "admin123"


settings = Settings()
