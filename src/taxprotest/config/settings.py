from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment.

    Environment variables are prefixed with ``TAXPROTEST_``. Example:
        set TAXPROTEST_SECRET_KEY=supersecret
    """

    SECRET_KEY: str = "dev-key-change-in-production"
    DATABASE_PATH: Path = (
        Path(__file__).resolve().parent.parent.parent.parent / "data" / "database.sqlite"
    )
    CACHE_MAX_ENTRIES: int = 10_000

    # pydantic-settings v2 configuration
    model_config = SettingsConfigDict(env_prefix="TAXPROTEST_", case_sensitive=False)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


settings = get_settings()
