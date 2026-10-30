"""Application configuration loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    # App
    rca_env: str = "demo"  # "demo" | "live"
    rca_master_key: str = ""  # base64 32-byte key for AES-256-GCM (optional in demo)

    # Persistence & auth
    database_url: str = "sqlite+aiosqlite:///./instance/rca.db"  # postgres: postgresql+asyncpg://...
    jwt_secret: str = ""            # HS256 secret; generated + persisted if empty
    jwt_expire_minutes: int = 1440  # 24h

    # SAP CPI design-time service key
    cpi_base_url: str = ""
    cpi_token_url: str = ""
    cpi_client_id: str = ""
    cpi_client_secret: str = ""

    @property
    def is_live(self) -> bool:
        return self.rca_env.lower() == "live" and bool(self.cpi_base_url and self.cpi_client_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()
