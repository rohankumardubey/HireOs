from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    project_name: str = "HireOS AI"
    api_v1_prefix: str = "/api/v1"
    public_app_url: str = "http://localhost:3000"
    database_url: str = "sqlite:///./hireos.db"
    jwt_secret: str = "change-me"
    access_token_expire_minutes: int = 60 * 24
    session_cookie_name: str = "hireos_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"
    llm_provider: str = "mock"
    openai_api_key: str | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_auth_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"
    google_oauth_redirect_uri: str = "http://localhost:8000/api/v1/integrations/google/callback"
    ollama_base_url: str = "http://localhost:11434"
    qdrant_url: str = "http://localhost:6333"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    redis_url: str = "redis://localhost:6379/0"
    kafka_bootstrap_servers: str = "localhost:9092"
    enable_kafka: bool = False
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://localhost:3010",
            "http://127.0.0.1:3010",
        ]
    )
    uploads_dir: Path = ROOT_DIR / "backend" / "uploads"
    events_dir: Path = ROOT_DIR / "data" / "events"
    lakehouse_dir: Path = ROOT_DIR / "data" / "lakehouse"


settings = Settings()
settings.uploads_dir.mkdir(parents=True, exist_ok=True)
settings.events_dir.mkdir(parents=True, exist_ok=True)
settings.lakehouse_dir.mkdir(parents=True, exist_ok=True)
