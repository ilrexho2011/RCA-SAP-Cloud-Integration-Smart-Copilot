"""Async SQLAlchemy engine + session. SQLite by default, Postgres via DATABASE_URL."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from ..config import get_settings

_settings = get_settings()

# Ensure the instance dir exists for the default sqlite file.
if _settings.database_url.startswith("sqlite"):
    (Path(__file__).resolve().parents[2] / "instance").mkdir(exist_ok=True)

engine = create_async_engine(_settings.database_url, echo=False, future=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    """Create tables on startup (dev). Use Alembic for production migrations."""
    from . import models  # noqa: F401  (register models)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:  # FastAPI dependency
    async with async_session() as session:
        yield session
