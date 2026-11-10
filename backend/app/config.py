from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./data/tagado.db"
    app_url: str = "http://localhost:8000"
    session_secret: str = "dev-only-change-me"
    cron_secret: str = "dev-only-cron-secret"
    demo_email: str = "demo@tagado.app"
    demo_password: str = "tagado-demo-2026"
    demo_owner_name: str = "Priya"
    demo_business_name: str = "Pixelcraft Studio"
    data_dir: Path = BACKEND_ROOT / "data"


@lru_cache
def get_settings() -> Settings:
    return Settings()
