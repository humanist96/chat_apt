"""Sample data collection script for testing.

This script creates sample data for testing the system
when the real API is not accessible.
"""
import asyncio
import sys
import random
from datetime import date, datetime
from typing import List
import logging

sys.path.insert(0, '/home/user/chat_apt/backend')

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.models.apartment import Apartment, Transaction, Listing
from app.database import Base

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATABASE_URL = "sqlite+aiosqlite:///./chat_apt.db"

# Sample apartment data for Seoul Gangnam
SAMPLE_APARTMENTS = [
    {"name": "래미안퍼스티지", "address": "서울특별시 강남구 개포동 12-1", "dong_code": "11680", "built_year": 2009, "total_units": 1612, "lat": 37.4847, "lon": 127.0671},
    {"name": "디에이치아너힐즈", "address": "서울특별시 강남구 개포동 660", "dong_code": "11680", "built_year": 2021, "total_units": 789, "lat": 37.4789, "lon": 127.0612},
    {"name": "아크로리버파크", "address": "서울특별시 서초구 반포동 1-1", "dong_code": "11650", "built_year": 2016, "total_units": 1612, "lat": 37.5082, "lon": 126.9957},
    {"name": "반포자이", "address": "서울특별시 서초구 반포동 18", "dong_code": "11650", "built_year": 2019, "total_units": 2990, "lat": 37.5058, "lon": 126.9923},
    {"name": "헬리오시티", "address": "서울특별시 송파구 가락동 482", "dong_code": "11710", "built_year": 2018, "total_units": 9510, "lat": 37.4967, "lon": 127.1182},
    {"name": "파크리오", "address": "서울특별시 송파구 잠실동 40-1", "dong_code": "11710", "built_year": 2008, "total_units": 6864, "lat": 37.5154, "lon": 127.0961},
    {"name": "잠실엘스", "address": "서울특별시 송파구 잠실동 13", "dong_code": "11710", "built_year": 2008, "total_units": 5678, "lat": 37.5112, "lon": 127.0833},
    {"name": "타워팰리스1차", "address": "서울특별시 강남구 도곡동 467", "dong_code": "11680", "built_year": 2002, "total_units": 1346, "lat": 37.4930, "lon": 127.0553},
    {"name": "은마아파트", "address": "서울특별시 강남구 대치동 508", "dong_code": "11680", "built_year": 1979, "total_units": 4424, "lat": 37.4984, "lon": 127.0628},
    {"name": "래미안대치팰리스", "address": "서울특별시 강남구 대치동 316", "dong_code": "11680", "built_year": 2015, "total_units": 1608, "lat": 37.4923, "lon": 127.0642},
]

# Price ranges by area (만원)
PRICE_RANGES = {
    "11680": {"min": 150000, "max": 500000},  # 강남구: 15억 ~ 50억
    "11650": {"min": 180000, "max": 450000},  # 서초구: 18억 ~ 45억
    "11710": {"min": 120000, "max": 350000},  # 송파구: 12억 ~ 35억
}


async def init_database(engine):
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")


async def create_sample_apartments(session: AsyncSession) -> List[Apartment]:
    """Create sample apartments."""
    apartments = []

    for data in SAMPLE_APARTMENTS:
        # Check if already exists
        result = await session.execute(
            select(Apartment).where(
                Apartment.name == data["name"],
                Apartment.dong_code == data["dong_code"]
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            apartments.append(existing)
            continue

        apt = Apartment(
            name=data["name"],
            address=data["address"],
            dong_code=data["dong_code"],
            built_year=data["built_year"],
            total_units=data["total_units"],
            latitude=data["lat"],
            longitude=data["lon"],
        )
        session.add(apt)
        apartments.append(apt)
        logger.info(f"Created apartment: {data['name']}")

    await session.flush()
    return apartments


async def create_sample_transactions(
    session: AsyncSession,
    apartments: List[Apartment],
    months: int = 12
) -> int:
    """Create sample transaction data."""
    count = 0
    today = date.today()

    for apt in apartments:
        price_range = PRICE_RANGES.get(apt.dong_code, {"min": 100000, "max": 300000})
        base_price = random.randint(price_range["min"], price_range["max"])

        # Generate transactions for each month
        for month_offset in range(months):
            year = today.year
            month = today.month - month_offset

            while month <= 0:
                month += 12
                year -= 1

            # 2-5 transactions per month
            num_transactions = random.randint(2, 5)

            for _ in range(num_transactions):
                # Price variation (+/- 10%)
                price = int(base_price * random.uniform(0.9, 1.1))

                # Different unit sizes
                area = random.choice([59.96, 84.97, 101.82, 114.55, 135.23])
                floor = random.randint(1, 35)
                day = random.randint(1, 28)

                # Create deal_date
                deal_date = date(year, month, day)

                # Check for duplicate
                result = await session.execute(
                    select(Transaction).where(
                        Transaction.apartment_id == apt.id,
                        Transaction.deal_date == deal_date,
                        Transaction.area == area,
                        Transaction.floor == floor
                    )
                )
                if result.scalar_one_or_none():
                    continue

                txn = Transaction(
                    apartment_id=apt.id,
                    deal_amount=price,
                    area=area,
                    floor=floor,
                    deal_date=deal_date,
                )
                session.add(txn)
                count += 1

        # Gradually increase base price (market trend)
        base_price = int(base_price * 1.005)

    await session.flush()
    return count


async def create_sample_listings(
    session: AsyncSession,
    apartments: List[Apartment]
) -> int:
    """Create sample active listings."""
    count = 0

    for apt in apartments:
        price_range = PRICE_RANGES.get(apt.dong_code, {"min": 100000, "max": 300000})

        # 3-8 active listings per apartment
        num_listings = random.randint(3, 8)

        for i in range(num_listings):
            base_price = random.randint(price_range["min"], price_range["max"])
            area = random.choice([59.96, 84.97, 101.82, 114.55, 135.23])
            floor = random.randint(1, 35)

            # Some listings are undervalued (good deals)
            if random.random() < 0.2:
                price = int(base_price * random.uniform(0.85, 0.95))
            else:
                price = int(base_price * random.uniform(0.98, 1.05))

            article_no = f"ART{apt.id:04d}{i:03d}"

            # Check for duplicate
            result = await session.execute(
                select(Listing).where(Listing.article_no == article_no)
            )
            if result.scalar_one_or_none():
                continue

            listing = Listing(
                apartment_id=apt.id,
                article_no=article_no,
                trade_type="A1",  # 매매
                price=price,
                area=area,
                floor=floor,
                direction=random.choice(["남향", "동향", "서향", "남동향", "남서향"]),
                description=f"{apt.name} {area}㎡ {floor}층",
                is_active=True,
            )
            session.add(listing)
            count += 1

    await session.flush()
    return count


async def main():
    """Main function to create sample data."""
    logger.info("=" * 60)
    logger.info("Creating sample data for testing")
    logger.info("=" * 60)

    # Create engine and session
    engine = create_async_engine(DATABASE_URL, echo=False)
    await init_database(engine)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        # Create sample apartments
        logger.info("Creating sample apartments...")
        apartments = await create_sample_apartments(session)
        logger.info(f"Created {len(apartments)} apartments")

        # Create sample transactions
        logger.info("Creating sample transactions...")
        txn_count = await create_sample_transactions(session, apartments, months=24)
        logger.info(f"Created {txn_count} transactions")

        # Create sample listings
        logger.info("Creating sample listings...")
        listing_count = await create_sample_listings(session, apartments)
        logger.info(f"Created {listing_count} listings")

        # Commit all changes
        await session.commit()

    # Show final stats
    async with session_maker() as session:
        apt_count = await session.execute(text("SELECT COUNT(*) FROM apartments"))
        txn_count = await session.execute(text("SELECT COUNT(*) FROM transactions"))
        listing_count = await session.execute(text("SELECT COUNT(*) FROM listings"))

        logger.info("=" * 60)
        logger.info("Sample data creation complete!")
        logger.info(f"  - Apartments: {apt_count.scalar()}")
        logger.info(f"  - Transactions: {txn_count.scalar()}")
        logger.info(f"  - Listings: {listing_count.scalar()}")
        logger.info("=" * 60)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
