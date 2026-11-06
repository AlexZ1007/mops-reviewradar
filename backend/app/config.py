from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    supabase_url: str = "http://127.0.0.1:64321"
    supabase_jwt_secret: str = ""  # only for legacy HS256 projects
    database_url: str = "postgresql+psycopg://postgres:postgres@127.0.0.1:64322/postgres"
    admin_email: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
