"""Runtime settings for Health Assessment v2."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings.

    Paths should point to de-identified local outputs, never raw private source files.
    """

    model_config = SettingsConfigDict(env_prefix="HEALTH_", env_file=".env", extra="ignore")

    wiki_root: Path | None = None
    data_dir: Path = Path("data")
    duckdb_path: Path = Path("data/health.duckdb")


def get_settings() -> Settings:
    return Settings()
