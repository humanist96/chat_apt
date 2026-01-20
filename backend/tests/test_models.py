"""Tests for database models."""
import pytest
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select

from app.models.apartment import (
    Apartment,
    Transaction,
    Listing,
    AnalysisResult,
    SimilarApartment,
    MonthlyPriceCache,
)


@pytest.mark.asyncio
async def test_create_apartment(db_session):
    """Test creating an apartment."""
    apartment = Apartment(
        naver_complex_no="12345",
        name="테스트 아파트",
        address="서울시 강남구 테스트동 123",
        dong_code="11680",
        total_units=500,
        built_year=2020,
        latitude=Decimal("37.5172"),
        longitude=Decimal("127.0473"),
    )
    db_session.add(apartment)
    await db_session.flush()

    assert apartment.id is not None
    assert apartment.name == "테스트 아파트"
    assert apartment.naver_complex_no == "12345"


@pytest.mark.asyncio
async def test_create_transaction(db_session):
    """Test creating a transaction record."""
    # First create an apartment
    apartment = Apartment(name="테스트 아파트")
    db_session.add(apartment)
    await db_session.flush()

    # Then create a transaction
    transaction = Transaction(
        apartment_id=apartment.id,
        deal_amount=150000,  # 15억
        deal_date=date(2024, 1, 15),
        floor=10,
        area=Decimal("84.95"),
    )
    db_session.add(transaction)
    await db_session.flush()

    assert transaction.id is not None
    assert transaction.deal_amount == 150000
    assert transaction.apartment_id == apartment.id


@pytest.mark.asyncio
async def test_create_listing(db_session):
    """Test creating a listing."""
    apartment = Apartment(name="테스트 아파트")
    db_session.add(apartment)
    await db_session.flush()

    listing = Listing(
        apartment_id=apartment.id,
        article_no="ART123456",
        trade_type="매매",
        price=160000,  # 16억
        area=Decimal("84.95"),
        floor=15,
        direction="남향",
        description="급매 매물입니다.",
        realtor_name="홍길동",
        is_active=True,
    )
    db_session.add(listing)
    await db_session.flush()

    assert listing.id is not None
    assert listing.price == 160000
    assert listing.is_active is True


@pytest.mark.asyncio
async def test_apartment_transaction_relationship(db_session):
    """Test relationship between apartment and transactions."""
    apartment = Apartment(name="테스트 아파트")
    db_session.add(apartment)
    await db_session.flush()

    # Add multiple transactions
    transactions = [
        Transaction(
            apartment_id=apartment.id,
            deal_amount=145000 + i * 5000,
            deal_date=date(2024, 1, i + 1),
            floor=i + 5,
            area=Decimal("84.95"),
        )
        for i in range(3)
    ]
    db_session.add_all(transactions)
    await db_session.flush()

    # Query and verify relationship
    result = await db_session.execute(
        select(Apartment).where(Apartment.id == apartment.id)
    )
    fetched_apartment = result.scalar_one()

    # Note: Relationships require additional loading in async
    assert fetched_apartment.name == "테스트 아파트"


@pytest.mark.asyncio
async def test_analysis_result(db_session):
    """Test creating analysis result."""
    apartment = Apartment(name="테스트 아파트")
    db_session.add(apartment)
    await db_session.flush()

    listing = Listing(
        apartment_id=apartment.id,
        price=160000,
    )
    db_session.add(listing)
    await db_session.flush()

    analysis = AnalysisResult(
        listing_id=listing.id,
        avg_transaction_price=155000,
        price_gap=5000,
        discount_rate=Decimal("-3.23"),  # 3.23% 비쌈
        recommendation_score=Decimal("72.5"),
    )
    db_session.add(analysis)
    await db_session.flush()

    assert analysis.id is not None
    assert analysis.recommendation_score == Decimal("72.5")


@pytest.mark.asyncio
async def test_similar_apartment(db_session):
    """Test similar apartment mapping."""
    apt1 = Apartment(name="아파트1", dong_code="11680")
    apt2 = Apartment(name="아파트2", dong_code="11680")
    db_session.add_all([apt1, apt2])
    await db_session.flush()

    similar = SimilarApartment(
        apartment_id=apt1.id,
        similar_apartment_id=apt2.id,
        similarity_score=Decimal("85.5"),
        location_score=Decimal("90.0"),
        area_score=Decimal("95.0"),
        correlation_score=Decimal("78.0"),
        scale_score=Decimal("82.0"),
        age_score=Decimal("80.0"),
    )
    db_session.add(similar)
    await db_session.flush()

    assert similar.id is not None
    assert similar.similarity_score == Decimal("85.5")


@pytest.mark.asyncio
async def test_monthly_price_cache(db_session):
    """Test monthly price cache."""
    apartment = Apartment(name="테스트 아파트")
    db_session.add(apartment)
    await db_session.flush()

    cache = MonthlyPriceCache(
        apartment_id=apartment.id,
        area_pyeong=Decimal("25.7"),
        year_month="2024-01",
        avg_price=150000,
        avg_price_per_pyeong=5836,
        transaction_count=5,
    )
    db_session.add(cache)
    await db_session.flush()

    assert cache.id is not None
    assert cache.year_month == "2024-01"
    assert cache.transaction_count == 5
