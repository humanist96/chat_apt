"""Data collection using PublicDataReader library.

This script uses PublicDataReader to fetch real estate transaction data
from the Korean government's open data portal.

Usage:
    python scripts/collect_with_pdr.py

Requirements:
    - pip install PublicDataReader
    - API key from data.go.kr (set in .env file or pass as argument)
    - IP must be registered on data.go.kr or run from local machine
"""
import asyncio
import sys
from datetime import date, datetime
from typing import List, Optional
import logging
import os
from pathlib import Path

# Add backend directory to path dynamically
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

import pandas as pd
from PublicDataReader import TransactionPrice
import PublicDataReader as pdr

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.models.apartment import Apartment, Transaction, Listing
from app.config import get_settings
from sqlalchemy.orm import DeclarativeBase

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database URL (from environment variable, defaults to SQLite for local testing)
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./chat_apt.db")

# Convert PostgreSQL URL to async format (postgresql:// → postgresql+asyncpg://)
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


# Create a local Base for SQLite-compatible tables only
class LocalBase(DeclarativeBase):
    pass


async def init_database(engine):
    """Create only apartment-related tables (SQLite compatible)."""
    async with engine.begin() as conn:
        # Only create apartment-related tables, not user tables with UUID
        await conn.run_sync(lambda sync_conn: Apartment.__table__.create(sync_conn, checkfirst=True))
        await conn.run_sync(lambda sync_conn: Transaction.__table__.create(sync_conn, checkfirst=True))
        await conn.run_sync(lambda sync_conn: Listing.__table__.create(sync_conn, checkfirst=True))
    logger.info("Database tables created (apartments, transactions, listings)")


def get_api_client() -> TransactionPrice:
    """Get TransactionPrice API client."""
    settings = get_settings()
    api_key = settings.public_data_api_key

    if not api_key:
        # Try environment variable
        api_key = os.environ.get('PUBLIC_DATA_API_KEY', '')

    if not api_key:
        raise ValueError("API key not found. Set PUBLIC_DATA_API_KEY in .env or environment")

    return TransactionPrice(api_key)


def get_region_codes() -> dict:
    """Get region codes for major areas."""
    code_df = pdr.code_bdong()

    regions = {
        "서울특별시 강남구": None,
        "서울특별시 서초구": None,
        "서울특별시 송파구": None,
        "서울특별시 강동구": None,
        "서울특별시 마포구": None,
        "서울특별시 용산구": None,
    }

    for region_name in regions.keys():
        parts = region_name.split()
        sido = parts[0]
        sigungu = parts[1] if len(parts) > 1 else ""

        match = code_df.loc[
            (code_df['시도명'] == sido) &
            (code_df['시군구명'] == sigungu) &
            (code_df['읍면동명'] == '')
        ]

        if not match.empty:
            regions[region_name] = str(match.iloc[0]['시군구코드'])

    return {k: v for k, v in regions.items() if v is not None}


async def get_or_create_apartment(
    session: AsyncSession,
    apt_name: str,
    dong_name: str,
    dong_code: str,
    built_year: int,
    jibun: str
) -> Apartment:
    """Get existing apartment or create new one."""
    result = await session.execute(
        select(Apartment).where(
            Apartment.name == apt_name,
            Apartment.dong_code == dong_code
        )
    )
    apartment = result.scalar_one_or_none()

    if apartment:
        return apartment

    apartment = Apartment(
        name=apt_name,
        address=f"{dong_name} {jibun}",
        dong_code=dong_code,
        built_year=built_year,
    )
    session.add(apartment)
    await session.flush()
    logger.info(f"Created apartment: {apt_name}")
    return apartment


async def save_transactions_from_df(
    session: AsyncSession,
    df: pd.DataFrame,
    dong_code: str
) -> int:
    """Save transactions from DataFrame to database."""
    if df.empty:
        return 0

    count = 0
    for _, row in df.iterrows():
        try:
            # Parse data from DataFrame
            apt_name = str(row.get('aptNm', '') or row.get('아파트', ''))
            dong_name = str(row.get('umdNm', '') or row.get('법정동', ''))
            jibun = str(row.get('jibun', '') or row.get('지번', ''))

            # Parse built year
            built_year_str = row.get('buildYear', '') or row.get('건축년도', '')
            built_year = int(built_year_str) if built_year_str else 2000

            # Parse deal info
            deal_year = int(row.get('dealYear', '') or row.get('년', 2024))
            deal_month = int(row.get('dealMonth', '') or row.get('월', 1))
            deal_day_str = row.get('dealDay', '') or row.get('일', '1')
            deal_day = int(str(deal_day_str).strip()) if deal_day_str else 1

            # Parse price (remove commas)
            deal_amount_str = str(row.get('dealAmount', '') or row.get('거래금액', '0'))
            deal_amount = int(deal_amount_str.replace(',', '').strip())

            # Parse area
            area_str = row.get('excluUseAr', '') or row.get('전용면적', '0')
            area = float(area_str) if area_str else 0.0

            # Parse floor
            floor_str = row.get('floor', '') or row.get('층', '1')
            floor = int(floor_str) if floor_str else 1

            # Get or create apartment
            apartment = await get_or_create_apartment(
                session=session,
                apt_name=apt_name,
                dong_name=dong_name,
                dong_code=dong_code,
                built_year=built_year,
                jibun=jibun
            )

            # Create deal_date
            try:
                deal_date = date(deal_year, deal_month, deal_day)
            except ValueError:
                deal_date = date(deal_year, deal_month, 1)

            # Check for duplicate
            result = await session.execute(
                select(Transaction).where(
                    Transaction.apartment_id == apartment.id,
                    Transaction.deal_date == deal_date,
                    Transaction.deal_amount == deal_amount,
                    Transaction.area == area
                )
            )
            if result.scalar_one_or_none():
                continue

            # Create transaction
            txn = Transaction(
                apartment_id=apartment.id,
                deal_amount=deal_amount,
                area=area,
                floor=floor,
                deal_date=deal_date,
            )
            session.add(txn)
            count += 1

        except Exception as e:
            logger.warning(f"Error processing row: {e}")
            continue

    return count


async def collect_data(
    api: TransactionPrice,
    session: AsyncSession,
    regions: dict,
    start_year_month: str,
    end_year_month: str
) -> int:
    """Collect transaction data for all regions."""
    total_count = 0

    for region_name, sigungu_code in regions.items():
        logger.info(f"Collecting data for {region_name} ({sigungu_code})...")

        try:
            df = api.get_data(
                property_type="아파트",
                trade_type="매매",
                sigungu_code=sigungu_code,
                start_year_month=start_year_month,
                end_year_month=end_year_month,
            )

            if df.empty:
                logger.warning(f"No data returned for {region_name}")
                continue

            logger.info(f"Fetched {len(df)} transactions for {region_name}")

            # Save to database
            count = await save_transactions_from_df(session, df, sigungu_code)
            total_count += count

            logger.info(f"Saved {count} new transactions for {region_name}")

        except Exception as e:
            logger.error(f"Error collecting data for {region_name}: {e}")
            continue

    await session.commit()
    return total_count


async def main():
    """Main collection job."""
    logger.info("=" * 60)
    logger.info("Starting data collection with PublicDataReader")
    logger.info("=" * 60)

    # Initialize database
    engine = create_async_engine(DATABASE_URL, echo=False)
    await init_database(engine)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Get API client
    try:
        api = get_api_client()
        logger.info("API client initialized")
    except ValueError as e:
        logger.error(str(e))
        return

    # Get region codes
    logger.info("Getting region codes...")
    regions = get_region_codes()
    logger.info(f"Found {len(regions)} regions: {list(regions.keys())}")

    # Calculate date range (last 6 months)
    today = date.today()
    end_month = today.replace(day=1)

    start_month = today.month - 6
    start_year = today.year
    while start_month <= 0:
        start_month += 12
        start_year -= 1

    start_year_month = f"{start_year}{start_month:02d}"
    end_year_month = f"{today.year}{today.month:02d}"

    logger.info(f"Collecting data from {start_year_month} to {end_year_month}")

    # Collect data
    async with session_maker() as session:
        total = await collect_data(
            api=api,
            session=session,
            regions=regions,
            start_year_month=start_year_month,
            end_year_month=end_year_month
        )

    # Show stats
    async with session_maker() as session:
        apt_count = await session.execute(text("SELECT COUNT(*) FROM apartments"))
        txn_count = await session.execute(text("SELECT COUNT(*) FROM transactions"))

        logger.info("=" * 60)
        logger.info(f"Collection complete!")
        logger.info(f"  - Total new transactions: {total}")
        logger.info(f"  - Total apartments: {apt_count.scalar()}")
        logger.info(f"  - Total transactions: {txn_count.scalar()}")
        logger.info("=" * 60)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
