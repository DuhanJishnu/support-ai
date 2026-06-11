"""Async database engine and session helpers."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
async_session_factory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Yield an async SQLAlchemy session for FastAPI dependencies."""
    async with async_session_factory() as session:
        yield session
