"""Async SQLAlchemy engine, session factory, and declarative base.

The engine is configured per-database: SQLite URLs skip ``pool_size`` /
``max_overflow`` (unsupported by the SQLite driver), while PostgreSQL and
others use a bounded connection pool.

A module-level :data:`engine` and :data:`async_session_factory` are shared
across the FastAPI app and the Celery worker. The worker wraps each task
body in its own :func:`asyncio.run` call, which creates a fresh event loop
per task; this is safe because asyncpg connections are checked out per
transaction and released back to the pool on session close.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# SQLite does not support pool_size/max_overflow, so only pass them for non-SQLite
_db_args: dict = {"echo": False}
if not settings.database_url.startswith("sqlite"):
    _db_args.update(pool_size=10, max_overflow=20)

engine = create_async_engine(
    settings.database_url,
    **_db_args,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models. Tables are created on startup
    via :func:`create_tables` (no Alembic migrations yet)."""
    pass


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """FastAPI dependency: yield a session, commit on success, rollback on error.

    The commit happens unconditionally after the handler returns — including
    read-only handlers — which is wasteful but harmless. Handlers that need
    to control transaction boundaries should manage their own session via
    :data:`async_session_factory` instead.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_tables() -> None:
    """Create all tables registered on :class:`Base`.

    Called from the FastAPI lifespan on startup. This bypasses Alembic —
    once migrations are introduced, replace this with ``alembic upgrade head``.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
