"""Recommendations API endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.auth import get_current_user, AuthenticatedUser, check_rate_limit
from app.models.apartment import Apartment, Listing, AnalysisResult


router = APIRouter()


class RecommendationResponse(BaseModel):
    """Response schema for recommendations."""
    listing_id: int
    apartment_id: int
    apartment_name: str
    listing_price: int
    area: float
    price_per_pyeong: int
    recommendation_score: float
    discount_percent: float
    rank: int


class TopRecommendationsResponse(BaseModel):
    """Response schema for top recommendations."""
    recommendations: List[RecommendationResponse]
    total_count: int
    filters_applied: dict


@router.get("/top", response_model=TopRecommendationsResponse)
async def get_top_recommendations(
    dong_code: Optional[str] = Query(None, description="Filter by region"),
    min_price: Optional[int] = Query(None, description="Minimum price (만원)"),
    max_price: Optional[int] = Query(None, description="Maximum price (만원)"),
    min_area: Optional[float] = Query(None, description="Minimum area (m²)"),
    max_area: Optional[float] = Query(None, description="Maximum area (m²)"),
    min_score: float = Query(60.0, ge=0, le=100, description="Minimum recommendation score"),
    limit: int = Query(20, ge=1, le=100),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get top recommended listings.

    Requires authentication with basic tier or higher.
    Returns listings sorted by recommendation score.
    """
    # Check rate limit
    await check_rate_limit(user.id, user.membership_tier, "report")

    # Build query for listings with analysis results
    query = (
        select(Listing, Apartment, AnalysisResult)
        .join(Apartment, Listing.apartment_id == Apartment.id)
        .join(AnalysisResult, AnalysisResult.listing_id == Listing.id)
        .where(Listing.is_active.is_(True))
        .where(AnalysisResult.recommendation_score >= min_score)
    )

    # Apply filters
    if dong_code:
        query = query.where(Apartment.dong_code == dong_code)
    if min_price:
        query = query.where(Listing.price >= min_price)
    if max_price:
        query = query.where(Listing.price <= max_price)
    if min_area:
        query = query.where(Listing.area >= min_area)
    if max_area:
        query = query.where(Listing.area <= max_area)

    # Order by recommendation score
    query = query.order_by(AnalysisResult.recommendation_score.desc())

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply limit
    query = query.limit(limit)

    result = await db.execute(query)
    rows = result.all()

    # Build response
    from app.analysis.comparison import ComparisonAnalyzer
    analyzer = ComparisonAnalyzer()

    recommendations = []
    for rank, (listing, apartment, analysis) in enumerate(rows, 1):
        area_m2 = float(listing.area) if listing.area else 84.95
        price_per_pyeong = analyzer.calculate_price_per_pyeong(
            int(listing.price),
            area_m2,
        )

        discount = float(analysis.discount_rate) if analysis.discount_rate else 0.0

        recommendations.append(RecommendationResponse(
            listing_id=listing.id,
            apartment_id=apartment.id,
            apartment_name=apartment.name,
            listing_price=int(listing.price),
            area=area_m2,
            price_per_pyeong=price_per_pyeong,
            recommendation_score=float(analysis.recommendation_score or 0),
            discount_percent=discount,
            rank=rank,
        ))

    return TopRecommendationsResponse(
        recommendations=recommendations,
        total_count=total_count,
        filters_applied={
            "dong_code": dong_code,
            "min_price": min_price,
            "max_price": max_price,
            "min_area": min_area,
            "max_area": max_area,
            "min_score": min_score,
        },
    )


@router.get("/undervalued", response_model=List[RecommendationResponse])
async def get_undervalued_listings(
    dong_code: Optional[str] = Query(None, description="Filter by region"),
    max_gap_percent: float = Query(-5.0, description="Maximum price gap (negative = undervalued)"),
    limit: int = Query(20, ge=1, le=100),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get undervalued listings (price below similar apartments).

    Requires authentication with basic tier or higher.
    """
    # Check rate limit
    await check_rate_limit(user.id, user.membership_tier, "report")

    # Query listings with negative discount rate (undervalued)
    query = (
        select(Listing, Apartment, AnalysisResult)
        .join(Apartment, Listing.apartment_id == Apartment.id)
        .join(AnalysisResult, AnalysisResult.listing_id == Listing.id)
        .where(Listing.is_active.is_(True))
        .where(AnalysisResult.discount_rate <= max_gap_percent)
    )

    if dong_code:
        query = query.where(Apartment.dong_code == dong_code)

    query = query.order_by(AnalysisResult.discount_rate.asc())
    query = query.limit(limit)

    result = await db.execute(query)
    rows = result.all()

    from app.analysis.comparison import ComparisonAnalyzer
    analyzer = ComparisonAnalyzer()

    recommendations = []
    for rank, (listing, apartment, analysis) in enumerate(rows, 1):
        area_m2 = float(listing.area) if listing.area else 84.95
        price_per_pyeong = analyzer.calculate_price_per_pyeong(
            int(listing.price),
            area_m2,
        )

        recommendations.append(RecommendationResponse(
            listing_id=listing.id,
            apartment_id=apartment.id,
            apartment_name=apartment.name,
            listing_price=int(listing.price),
            area=area_m2,
            price_per_pyeong=price_per_pyeong,
            recommendation_score=float(analysis.recommendation_score or 0),
            discount_percent=float(analysis.discount_rate or 0),
            rank=rank,
        ))

    return recommendations


@router.get("/by-region/{dong_code}", response_model=List[RecommendationResponse])
async def get_recommendations_by_region(
    dong_code: str,
    limit: int = Query(20, ge=1, le=100),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get top recommendations for a specific region.

    Requires authentication.
    """
    await check_rate_limit(user.id, user.membership_tier, "listings")

    query = (
        select(Listing, Apartment, AnalysisResult)
        .join(Apartment, Listing.apartment_id == Apartment.id)
        .join(AnalysisResult, AnalysisResult.listing_id == Listing.id)
        .where(Listing.is_active.is_(True))
        .where(Apartment.dong_code == dong_code)
        .order_by(AnalysisResult.recommendation_score.desc())
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.all()

    from app.analysis.comparison import ComparisonAnalyzer
    analyzer = ComparisonAnalyzer()

    recommendations = []
    for rank, (listing, apartment, analysis) in enumerate(rows, 1):
        area_m2 = float(listing.area) if listing.area else 84.95
        price_per_pyeong = analyzer.calculate_price_per_pyeong(
            int(listing.price),
            area_m2,
        )

        recommendations.append(RecommendationResponse(
            listing_id=listing.id,
            apartment_id=apartment.id,
            apartment_name=apartment.name,
            listing_price=int(listing.price),
            area=area_m2,
            price_per_pyeong=price_per_pyeong,
            recommendation_score=float(analysis.recommendation_score or 0) if analysis else 0,
            discount_percent=float(analysis.discount_rate or 0) if analysis else 0,
            rank=rank,
        ))

    return recommendations
