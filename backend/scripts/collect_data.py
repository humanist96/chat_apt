"""Data collection script for real estate transactions.

This script:
1. Fetches real transaction data from 국토교통부 API
2. Stores it in the database
3. Syncs to OpenSearch
"""
import asyncio
import sys
from datetime import date, datetime
from typing import List
import logging

# Add parent directory to path
sys.path.insert(0, '/home/user/chat_apt/backend')

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.services.public_data_api import PublicDataAPIClient, TransactionData, REGION_CODES
from app.models.apartment import Apartment, Transaction
from app.database import Base

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Use SQLite for local testing (no PostgreSQL server needed)
DATABASE_URL = "sqlite+aiosqlite:///./chat_apt.db"


async def init_database(engine):
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")


async def get_or_create_apartment(
    session: AsyncSession,
    name: str,
    dong: str,
    dong_code: str,
    built_year: int,
    jibun: str
) -> Apartment:
    """Get existing apartment or create new one."""
    # Try to find existing apartment
    result = await session.execute(
        select(Apartment).where(
            Apartment.name == name,
            Apartment.dong_code == dong_code
        )
    )
    apartment = result.scalar_one_or_none()

    if apartment:
        return apartment

    # Create new apartment
    apartment = Apartment(
        name=name,
        address=f"{dong} {jibun}",
        dong_code=dong_code,
        built_year=built_year,
    )
    session.add(apartment)
    await session.flush()  # Get the ID
    logger.info(f"Created apartment: {name} ({dong_code})")
    return apartment


async def save_transaction(
    session: AsyncSession,
    apartment: Apartment,
    txn_data: TransactionData
) -> Transaction:
    """Save a transaction to database."""
    # Check for duplicate
    result = await session.execute(
        select(Transaction).where(
            Transaction.apartment_id == apartment.id,
            Transaction.deal_year == txn_data.deal_year,
            Transaction.deal_month == txn_data.deal_month,
            Transaction.deal_day == txn_data.deal_day,
            Transaction.area == txn_data.area,
            Transaction.floor == txn_data.floor
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        return existing

    transaction = Transaction(
        apartment_id=apartment.id,
        deal_amount=txn_data.deal_amount,
        area=txn_data.area,
        floor=txn_data.floor,
        deal_year=txn_data.deal_year,
        deal_month=txn_data.deal_month,
        deal_day=txn_data.deal_day,
    )
    session.add(transaction)
    return transaction


async def collect_and_store(
    session: AsyncSession,
    api_client: PublicDataAPIClient,
    region_name: str,
    region_code: str,
    deal_ymd: str
) -> int:
    """Collect transactions for a region/month and store in DB."""
    logger.info(f"Collecting data for {region_name} ({region_code}), {deal_ymd}...")

    try:
        transactions = await api_client.get_transactions(
            lawd_cd=region_code,
            deal_ymd=deal_ymd
        )
    except Exception as e:
        logger.error(f"API error for {region_name}: {e}")
        return 0

    logger.info(f"Fetched {len(transactions)} transactions")

    saved_count = 0
    for txn_data in transactions:
        try:
            # Get or create apartment
            apartment = await get_or_create_apartment(
                session=session,
                name=txn_data.apartment_name,
                dong=txn_data.dong,
                dong_code=txn_data.dong_code,
                built_year=txn_data.built_year,
                jibun=txn_data.jibun
            )

            # Save transaction
            await save_transaction(session, apartment, txn_data)
            saved_count += 1

        except Exception as e:
            logger.error(f"Error saving transaction: {e}")
            continue

    await session.commit()
    logger.info(f"Saved {saved_count} transactions for {region_name}")
    return saved_count


async def main():
    """Main collection job."""
    logger.info("=" * 60)
    logger.info("Starting data collection")
    logger.info("=" * 60)

    # Create engine and session
    engine = create_async_engine(DATABASE_URL, echo=False)
    await init_database(engine)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Regions to collect (subset for initial test)
    regions_to_collect = {
        "서울특별시 강남구": "11680",
        "서울특별시 서초구": "11650",
        "서울특별시 송파구": "11710",
    }

    # Months to collect (recent 3 months)
    today = date.today()
    months_to_collect = []
    for i in range(3):
        month = today.month - i
        year = today.year
        if month <= 0:
            month += 12
            year -= 1
        months_to_collect.append(f"{year}{month:02d}")

    logger.info(f"Collecting data for regions: {list(regions_to_collect.keys())}")
    logger.info(f"Collecting data for months: {months_to_collect}")

    total_saved = 0

    async with PublicDataAPIClient() as api_client:
        async with session_maker() as session:
            for region_name, region_code in regions_to_collect.items():
                for deal_ymd in months_to_collect:
                    count = await collect_and_store(
                        session=session,
                        api_client=api_client,
                        region_name=region_name,
                        region_code=region_code,
                        deal_ymd=deal_ymd
                    )
                    total_saved += count

                    # Small delay to avoid rate limiting
                    await asyncio.sleep(0.5)

    # Print summary
    logger.info("=" * 60)
    logger.info(f"Collection complete! Total transactions saved: {total_saved}")
    logger.info("=" * 60)

    # Show database stats
    async with session_maker() as session:
        apt_count = await session.execute(text("SELECT COUNT(*) FROM apartments"))
        txn_count = await session.execute(text("SELECT COUNT(*) FROM transactions"))

        logger.info(f"Database stats:")
        logger.info(f"  - Apartments: {apt_count.scalar()}")
        logger.info(f"  - Transactions: {txn_count.scalar()}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
