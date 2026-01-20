"""Database connection and session management."""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker, AsyncEngine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


# Global engine and session maker (lazy initialization)
_engine: Optional[AsyncEngine] = None
_async_session_maker: Optional[async_sessionmaker] = None


def get_engine() -> AsyncEngine:
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        from app.config import get_settings
        settings = get_settings()

        database_url = settings.database_url
        if database_url:
            # Convert postgresql:// to postgresql+asyncpg://
            if database_url.startswith("postgresql://"):
                database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        else:
            database_url = "postgresql+asyncpg://localhost/chat_apt"

        _engine = create_async_engine(
            database_url,
            echo=settings.debug,
            future=True,
        )
    return _engine


def get_session_maker() -> async_sessionmaker:
    """Get or create the session maker."""
    global _async_session_maker
    if _async_session_maker is None:
        _async_session_maker = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_maker


async def get_db() -> AsyncSession:
    """Dependency to get database session."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def reset_engine():
    """Reset the engine (useful for testing)."""
    global _engine, _async_session_maker
    _engine = None
    _async_session_maker = None
