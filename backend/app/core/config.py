"""Application settings. Every secret comes from the environment — nothing is hardcoded."""
import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(BASE_DIR / ".env", BASE_DIR.parent / ".env"), extra="ignore")

    app_name: str = "HealthMate AI"
    environment: str = "development"  # development | production | test
    api_prefix: str = "/api"
    frontend_origin: str = "http://localhost:3000"

    # Database
    database_url: str = "postgresql+psycopg://healthmate:healthmate@localhost:5432/healthmate"

    # Auth
    jwt_secret: str = Field(default="dev-only-change-me-please-32-bytes-min", min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 24 * 7
    cookie_secure: bool = False

    # Encryption at rest (Fernet key, urlsafe base64 32 bytes). Generated into .data/ in dev if absent.
    encryption_key: str | None = None

    # Storage: "local" = encrypted files on disk; "db" = encrypted blobs in Postgres (for hosts without
    # persistent disks, e.g. Render's free tier)
    storage_backend: str = "local"
    data_dir: Path = BASE_DIR / ".data"
    max_upload_mb: int = 15

    # AI providers: "openai" | "gemini" | "demo"
    llm_provider: str = "demo"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_base_url: str = "https://api.openai.com/v1"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "text-embedding-004"
    llm_timeout_seconds: int = 60

    # OCR
    tesseract_cmd: str | None = None
    ocr_languages: str = "eng+hin"

    # Web push (VAPID). If unset, push is disabled and only in-app notifications are created.
    vapid_public_key: str | None = None
    vapid_private_key: str | None = None
    vapid_subject: str = "mailto:admin@healthmate.local"

    # Background reminder engine
    reminder_engine_enabled: bool = True
    reminder_tick_seconds: int = 60
    default_timezone: str = "Asia/Kolkata"

    # Agent harness
    agent_max_steps: int = 6
    agent_max_context_chars: int = 24000

    @field_validator("database_url")
    @classmethod
    def normalise_db_url(cls, v: str) -> str:
        """Hosting providers hand out postgres:// or postgresql:// URLs; SQLAlchemy needs the psycopg driver."""
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    @model_validator(mode="after")
    def hosted_defaults(self):  # noqa: ANN201
        external = os.environ.get("RENDER_EXTERNAL_URL")
        if external and self.frontend_origin == "http://localhost:3000":
            self.frontend_origin = external.rstrip("/")
        return self

    @property
    def llm_enabled(self) -> bool:
        if self.llm_provider == "openai":
            return bool(self.openai_api_key)
        if self.llm_provider == "gemini":
            return bool(self.gemini_api_key)
        return False

    @property
    def push_enabled(self) -> bool:
        return bool(self.vapid_public_key and self.vapid_private_key)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    return s
