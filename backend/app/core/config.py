from functools import lru_cache

from pydantic import AnyUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MavuFlow Studio"
    app_version: str = "0.1.0"
    app_env: str = "development"
    app_debug: bool = True
    secret_key: str = "change-me-in-production"
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    database_url: str = "sqlite:///./mavuflow.db"
    redis_host: str = "redis"
    redis_port: int = 6379
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/0"
    storage_root: str = "./storage"
    storage_provider: str = "local"
    max_upload_size_mb: int = 100
    allowed_upload_extensions: list[str] = [".csv", ".xlsx"]
    rate_limit_per_minute: int = 60

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
