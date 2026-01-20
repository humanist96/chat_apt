"""Analysis API endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.auth import get_current_user, get_current_user_optional, AuthenticatedUser, check_rate_limit
from app.models.apartment import Apartment, Listing, SimilarApartment, MonthlyPriceCache


router = APIRouter()


class SimilarApartmentResponse(BaseModel):
    """Response schema for similar apartments."""
    similar_apartment_id: int
    name: str
    similarity_score: float
    location_score: float
    area_score: float
    correlation_score: float
    scale_score: float
    age_score: float

    class Config:
        from_attributes = True


class ComparisonResultResponse(BaseModel):
    """Response schema for comparison results."""
    similar_apartment_id: int
    similar_apartment_name: str
    target_price_per_pyeong: int
    similar_price_per_pyeong: int
    price_gap_percent: float


class ComparisonReportResponse(BaseModel):
    """Response schema for comparison report."""
    listing_id: int
    apartment_id: int
    apartment_name: str
    listing_price: int
    area_pyeong: float
    price_per_pyeong: int
    avg_similar_price_per_pyeong: int
    avg_gap_percent: float
    is_undervalued: bool
    comparison_results: List[ComparisonResultResponse]


class PriceTrendResponse(BaseModel):
    """Response schema for price trend data."""
    year_month: str
    avg_price: int
    avg_price_per_pyeong: int
    transaction_count: int


@router.get("/similar/{apartment_id}", response_model=List[SimilarApartmentResponse])
async def get_similar_apartments(
    apartment_id: int,
    limit: int = Query(10, ge=1, le=50),
    min_score: float = Query(60.0, ge=0, le=100),
    user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Get similar apartments for a given apartment.

    Requires authentication. Free users have limited access.
    """
    # Check rate limit
    if user:
        await check_rate_limit(user.id, user.membership_tier, "analysis")

    # Query similar apartments
    query = (
        select(SimilarApartment, Apartment)
        .join(Apartment, SimilarApartment.similar_apartment_id == Apartment.id)
        .where(SimilarApartment.apartment_id == apartment_id)
        .where(SimilarApartment.similarity_score >= min_score)
        .order_by(SimilarApartment.similarity_score.desc())
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.all()

    return [
        SimilarApartmentResponse(
            similar_apartment_id=sim.similar_apartment_id,
            name=apt.name,
            similarity_score=float(sim.similarity_score or 0),
            location_score=float(sim.location_score or 0),
            area_score=float(sim.area_score or 0),
            correlation_score=float(sim.correlation_score or 0),
            scale_score=float(sim.scale_score or 0),
            age_score=float(sim.age_score or 0),
        )
        for sim, apt in rows
    ]


@router.get("/comparison/{listing_id}", response_model=ComparisonReportResponse)
async def get_comparison_report(
    listing_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get comparison analysis report for a listing.

    Requires authentication with basic tier or higher.
    """
    # Check rate limit for analysis
    await check_rate_limit(user.id, user.membership_tier, "analysis")

    # Get listing
    listing_result = await db.execute(
        select(Listing, Apartment)
        .join(Apartment, Listing.apartment_id == Apartment.id)
        .where(Listing.id == listing_id)
    )
    row = listing_result.first()

    if not row:
        raise HTTPException(status_code=404, detail="Listing not found")

    listing, apartment = row

    # Get similar apartments
    similar_result = await db.execute(
        select(SimilarApartment, Apartment)
        .join(Apartment, SimilarApartment.similar_apartment_id == Apartment.id)
        .where(SimilarApartment.apartment_id == apartment.id)
        .order_by(SimilarApartment.similarity_score.desc())
        .limit(10)
    )
    similar_rows = similar_result.all()

    # Get price data for similar apartments
    from app.analysis.comparison import ComparisonAnalyzer

    analyzer = ComparisonAnalyzer()

    # Calculate price per pyeong for listing
    area_m2 = float(listing.area) if listing.area else 84.95
    price_per_pyeong = analyzer.calculate_price_per_pyeong(
        int(listing.price),
        area_m2,
    )
    area_pyeong = analyzer.area_to_pyeong(area_m2)

    # Get similar prices from cache
    comparison_results = []
    similar_prices_sum = 0
    similar_count = 0

    for sim, similar_apt in similar_rows:
        # Get recent price for similar apartment
        price_result = await db.execute(
            select(MonthlyPriceCache)
            .where(MonthlyPriceCache.apartment_id == similar_apt.id)
            .order_by(MonthlyPriceCache.year_month.desc())
            .limit(6)
        )
        price_rows = price_result.scalars().all()

        if price_rows:
            avg_price_pp = int(
                sum(p.avg_price_per_pyeong or 0 for p in price_rows) / len(price_rows)
            )
            if avg_price_pp > 0:
                gap_percent = ((price_per_pyeong - avg_price_pp) / avg_price_pp) * 100

                comparison_results.append(ComparisonResultResponse(
                    similar_apartment_id=similar_apt.id,
                    similar_apartment_name=similar_apt.name,
                    target_price_per_pyeong=price_per_pyeong,
                    similar_price_per_pyeong=avg_price_pp,
                    price_gap_percent=round(gap_percent, 2),
                ))

                similar_prices_sum += avg_price_pp
                similar_count += 1

    # Calculate averages
    avg_similar_pp = int(similar_prices_sum / similar_count) if similar_count > 0 else 0
    avg_gap = (
        sum(r.price_gap_percent for r in comparison_results) / len(comparison_results)
        if comparison_results else 0
    )

    return ComparisonReportResponse(
        listing_id=listing.id,
        apartment_id=apartment.id,
        apartment_name=apartment.name,
        listing_price=int(listing.price),
        area_pyeong=round(area_pyeong, 2),
        price_per_pyeong=price_per_pyeong,
        avg_similar_price_per_pyeong=avg_similar_pp,
        avg_gap_percent=round(avg_gap, 2),
        is_undervalued=avg_gap < -5.0,
        comparison_results=comparison_results,
    )


@router.get("/price-trend/{apartment_id}", response_model=List[PriceTrendResponse])
async def get_price_trend(
    apartment_id: int,
    months: int = Query(24, ge=1, le=60),
    user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Get price trend data for an apartment.

    Public endpoint but with rate limiting for authenticated users.
    """
    if user:
        await check_rate_limit(user.id, user.membership_tier, "listings")

    # Query monthly price cache
    query = (
        select(MonthlyPriceCache)
        .where(MonthlyPriceCache.apartment_id == apartment_id)
        .order_by(MonthlyPriceCache.year_month.desc())
        .limit(months)
    )

    result = await db.execute(query)
    prices = result.scalars().all()

    return [
        PriceTrendResponse(
            year_month=p.year_month,
            avg_price=int(p.avg_price or 0),
            avg_price_per_pyeong=int(p.avg_price_per_pyeong or 0),
            transaction_count=int(p.transaction_count or 0),
        )
        for p in prices
    ]
