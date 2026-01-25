"""Database connection and session management."""
from typing import Optional
import uuid

from sqlalchemy import TypeDecorator, String
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker, AsyncEngine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.dialects.postgresql import UUID as PGUUID


class GUID(TypeDecorator):
    """Platform-independent UUID type.

    Uses PostgreSQL's UUID type when available, otherwise uses CHAR(36).
    """
    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PGUUID(as_uuid=True))
        else:
            return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return value
        if isinstance(value, uuid.UUID):
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


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

    # Check if using SQLite (which doesn't support UUID type)
    is_sqlite = "sqlite" in str(engine.url)

    async with engine.begin() as conn:
        if is_sqlite:
            # For SQLite, only create tables that don't use PostgreSQL-specific types
            from app.models.apartment import (
                Apartment, Transaction, Listing, AnalysisResult,
                SimilarApartment, ComparisonAnalysis, MonthlyPriceCache
            )
            tables_to_create = [
                Apartment.__table__,
                Transaction.__table__,
                Listing.__table__,
                AnalysisResult.__table__,
                SimilarApartment.__table__,
                ComparisonAnalysis.__table__,
                MonthlyPriceCache.__table__,
            ]
            for table in tables_to_create:
                await conn.run_sync(
                    lambda sync_conn, t=table: t.create(sync_conn, checkfirst=True)
                )
        else:
            # For PostgreSQL, create all tables
            await conn.run_sync(Base.metadata.create_all)


def reset_engine():
    """Reset the engine (useful for testing)."""
    global _engine, _async_session_maker
    _engine = None
    _async_session_maker = None
