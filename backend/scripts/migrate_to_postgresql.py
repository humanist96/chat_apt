"""SQLite → PostgreSQL 마이그레이션 스크립트.

로컬 SQLite에 수집된 데이터를 배포 환경 PostgreSQL로 마이그레이션합니다.

Usage:
    export DATABASE_URL="postgresql://user:pass@host:5432/dbname"
    python scripts/migrate_to_postgresql.py

또는 .env 파일에서 DATABASE_URL 설정 후:
    python scripts/migrate_to_postgresql.py
"""
import asyncio
import sqlite3
import os
import sys
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from typing import List, Tuple, Any
import logging

# Add backend directory to path
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Source: SQLite (로컬)
SQLITE_PATH = BACKEND_DIR / "chat_apt.db"

# Target: PostgreSQL (환경 변수에서)
def get_postgres_url() -> str:
    """Get PostgreSQL URL from environment variable (not .env file).

    Note: We explicitly do NOT read from .env file because it contains SQLite URL.
    The PostgreSQL URL must be set via environment variable.
    """
    url = os.environ.get("DATABASE_URL", "")

    # Check if it's a SQLite URL (invalid for this migration)
    if not url or "sqlite" in url.lower():
        raise ValueError(
            "PostgreSQL DATABASE_URL not found or SQLite URL detected.\n"
            "Please set a PostgreSQL URL as environment variable:\n\n"
            "  export DATABASE_URL='postgresql://user:pass@host:5432/dbname'\n"
            "  python scripts/migrate_to_postgresql.py\n\n"
            "Example for Supabase:\n"
            "  export DATABASE_URL='postgresql://postgres.xxx:password@aws-0-region.pooler.supabase.com:6543/postgres'"
        )

    # Convert to async format
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)

    return url


def read_sqlite_data() -> Tuple[List[dict], List[dict]]:
    """Read all data from SQLite database."""
    if not SQLITE_PATH.exists():
        raise FileNotFoundError(f"SQLite database not found: {SQLITE_PATH}")

    conn = sqlite3.connect(str(SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Read apartments
    cursor.execute("SELECT * FROM apartments ORDER BY id")
    apartments = [dict(row) for row in cursor.fetchall()]
    logger.info(f"Read {len(apartments)} apartments from SQLite")

    # Read transactions
    cursor.execute("SELECT * FROM transactions ORDER BY id")
    transactions = [dict(row) for row in cursor.fetchall()]
    logger.info(f"Read {len(transactions)} transactions from SQLite")

    conn.close()
    return apartments, transactions


async def create_tables(engine):
    """Create tables in PostgreSQL if they don't exist."""
    async with engine.begin() as conn:
        # Create apartments table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS apartments (
                id SERIAL PRIMARY KEY,
                naver_complex_no VARCHAR(20) UNIQUE,
                name VARCHAR(100) NOT NULL,
                address VARCHAR(200),
                dong_code VARCHAR(10),
                total_units INTEGER,
                built_year INTEGER,
                latitude DECIMAL(10, 7),
                longitude DECIMAL(10, 7),
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))

        # Create indexes for apartments
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_apartments_dong_code ON apartments (dong_code)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_apartments_name ON apartments (name)
        """))

        # Create transactions table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                apartment_id INTEGER NOT NULL REFERENCES apartments(id),
                deal_amount BIGINT NOT NULL,
                deal_date DATE NOT NULL,
                floor INTEGER,
                area DECIMAL(10, 2),
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_transactions_unique_deal
                    UNIQUE (apartment_id, deal_date, floor, area, deal_amount)
            )
        """))

        # Create indexes for transactions
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_transactions_deal_date ON transactions (deal_date)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_transactions_area ON transactions (area)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_transactions_apartment_id ON transactions (apartment_id)
        """))

    logger.info("PostgreSQL tables created/verified")


async def clear_existing_data(engine):
    """Clear existing data from PostgreSQL tables."""
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM transactions"))
        await conn.execute(text("DELETE FROM apartments"))
        # Reset sequences
        await conn.execute(text("ALTER SEQUENCE apartments_id_seq RESTART WITH 1"))
        await conn.execute(text("ALTER SEQUENCE transactions_id_seq RESTART WITH 1"))
    logger.info("Cleared existing data from PostgreSQL")


async def insert_apartments(session: AsyncSession, apartments: List[dict]) -> dict:
    """Insert apartments and return old_id -> new_id mapping."""
    id_mapping = {}

    for apt in apartments:
        old_id = apt['id']

        # Parse datetime fields
        created_at = apt.get('created_at')
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        elif created_at is None:
            created_at = datetime.utcnow()

        updated_at = apt.get('updated_at')
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
        elif updated_at is None:
            updated_at = datetime.utcnow()

        result = await session.execute(
            text("""
                INSERT INTO apartments
                (naver_complex_no, name, address, dong_code, total_units,
                 built_year, latitude, longitude, created_at, updated_at)
                VALUES (:naver_complex_no, :name, :address, :dong_code, :total_units,
                        :built_year, :latitude, :longitude, :created_at, :updated_at)
                RETURNING id
            """),
            {
                "naver_complex_no": apt.get('naver_complex_no'),
                "name": apt['name'],
                "address": apt.get('address'),
                "dong_code": apt.get('dong_code'),
                "total_units": apt.get('total_units'),
                "built_year": apt.get('built_year'),
                "latitude": apt.get('latitude'),
                "longitude": apt.get('longitude'),
                "created_at": created_at,
                "updated_at": updated_at,
            }
        )
        new_id = result.scalar_one()
        id_mapping[old_id] = new_id

    await session.commit()
    logger.info(f"Inserted {len(apartments)} apartments")
    return id_mapping


async def insert_transactions(
    session: AsyncSession,
    transactions: List[dict],
    id_mapping: dict
) -> int:
    """Insert transactions with mapped apartment IDs."""
    count = 0
    batch_size = 500

    for i in range(0, len(transactions), batch_size):
        batch = transactions[i:i + batch_size]

        for txn in batch:
            old_apt_id = txn['apartment_id']
            new_apt_id = id_mapping.get(old_apt_id)

            if new_apt_id is None:
                logger.warning(f"Skipping transaction: apartment_id {old_apt_id} not found")
                continue

            # Parse datetime fields
            created_at = txn.get('created_at')
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            elif created_at is None:
                created_at = datetime.utcnow()

            # Parse deal_date
            deal_date = txn['deal_date']
            if isinstance(deal_date, str):
                deal_date = date.fromisoformat(deal_date)

            try:
                await session.execute(
                    text("""
                        INSERT INTO transactions
                        (apartment_id, deal_amount, deal_date, floor, area, created_at)
                        VALUES (:apartment_id, :deal_amount, :deal_date, :floor, :area, :created_at)
                        ON CONFLICT (apartment_id, deal_date, floor, area, deal_amount) DO NOTHING
                    """),
                    {
                        "apartment_id": new_apt_id,
                        "deal_amount": txn['deal_amount'],
                        "deal_date": deal_date,
                        "floor": txn.get('floor'),
                        "area": txn.get('area'),
                        "created_at": created_at,
                    }
                )
                count += 1
            except Exception as e:
                logger.warning(f"Error inserting transaction: {e}")
                continue

        await session.commit()
        logger.info(f"Inserted batch {i // batch_size + 1} ({min(i + batch_size, len(transactions))}/{len(transactions)})")

    return count


async def verify_migration(engine) -> Tuple[int, int]:
    """Verify data was migrated correctly."""
    async with engine.begin() as conn:
        apt_result = await conn.execute(text("SELECT COUNT(*) FROM apartments"))
        apt_count = apt_result.scalar()

        txn_result = await conn.execute(text("SELECT COUNT(*) FROM transactions"))
        txn_count = txn_result.scalar()

    return apt_count, txn_count


async def main():
    """Run the migration."""
    logger.info("=" * 60)
    logger.info("SQLite → PostgreSQL Migration")
    logger.info("=" * 60)

    # Get PostgreSQL URL
    try:
        postgres_url = get_postgres_url()
        # Mask password in log
        masked_url = postgres_url.split("@")[-1] if "@" in postgres_url else postgres_url
        logger.info(f"Target PostgreSQL: ...@{masked_url}")
    except ValueError as e:
        logger.error(str(e))
        return

    # Read SQLite data
    logger.info(f"Reading from SQLite: {SQLITE_PATH}")
    try:
        apartments, transactions = read_sqlite_data()
    except FileNotFoundError as e:
        logger.error(str(e))
        return

    # Connect to PostgreSQL
    engine = create_async_engine(postgres_url, echo=False)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        # Create tables
        await create_tables(engine)

        # Clear existing data (optional - comment out if you want to append)
        await clear_existing_data(engine)

        # Insert data
        async with session_maker() as session:
            # Insert apartments first (to get ID mapping)
            id_mapping = await insert_apartments(session, apartments)

            # Insert transactions with mapped IDs
            txn_count = await insert_transactions(session, transactions, id_mapping)

        # Verify
        apt_count, final_txn_count = await verify_migration(engine)

        logger.info("=" * 60)
        logger.info("Migration complete!")
        logger.info(f"  - Apartments: {apt_count}")
        logger.info(f"  - Transactions: {final_txn_count}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
