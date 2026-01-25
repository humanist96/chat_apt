"""Fire sale detection for property listings.

This module detects potential fire sales by comparing current asking prices
against historical all-time high transaction prices.
"""
from typing import List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.apartment import Apartment, Transaction, Listing


@dataclass
class FireSaleAnalysis:
    """Analysis result for a potential fire sale."""
    listing_id: int
    apartment_id: int
    apartment_name: str
    dong_code: str
    area: float
    floor: Optional[int]
    asking_price: int  # Current asking price (만원)
    all_time_high: int  # All-time high transaction price (만원)
    all_time_high_date: str  # Date of all-time high (YYYY-MM-DD)
    discount_rate: float  # Discount percentage from ATH
    urgency_level: str  # "HIGH" | "MEDIUM" | "LOW"
    article_no: Optional[str] = None  # Naver article number
    naver_complex_no: Optional[str] = None  # Naver complex number
    latitude: Optional[float] = None  # Apartment latitude
    longitude: Optional[float] = None  # Apartment longitude


class FireSaleDetector:
    """Detects potential fire sale listings."""

    # Discount rate thresholds for urgency levels
    HIGH_THRESHOLD = 20.0  # 20% or more discount
    MEDIUM_THRESHOLD = 15.0  # 15% or more discount
    LOW_THRESHOLD = 10.0  # 10% or more discount

    def __init__(
        self,
        area_tolerance: float = 1.0,
        high_threshold: float = 20.0,
        medium_threshold: float = 15.0,
    ):
        """Initialize the detector.

        Args:
            area_tolerance: Allowed area difference in m² for matching same type (typically within 1㎡)
            high_threshold: Discount rate for HIGH urgency
            medium_threshold: Discount rate for MEDIUM urgency
        """
        self.area_tolerance = area_tolerance
        self.HIGH_THRESHOLD = high_threshold
        self.MEDIUM_THRESHOLD = medium_threshold

    def _determine_urgency(self, discount_rate: float) -> str:
        """Determine urgency level based on discount rate."""
        if discount_rate >= self.HIGH_THRESHOLD:
            return "HIGH"
        elif discount_rate >= self.MEDIUM_THRESHOLD:
            return "MEDIUM"
        elif discount_rate >= self.LOW_THRESHOLD:
            return "LOW"
        return "NONE"

    async def get_all_time_high(
        self,
        db: AsyncSession,
        apartment_id: int,
        area: float,
    ) -> Optional[dict]:
        """Get all-time high transaction for an apartment/area combination.

        Args:
            db: Database session
            apartment_id: Apartment ID
            area: Target area in m²

        Returns:
            Dict with max_price and deal_date, or None if no transactions found
        """
        # Find the maximum transaction price for similar area
        query = (
            select(
                func.max(Transaction.deal_amount).label("max_price"),
                Transaction.deal_date,
            )
            .where(
                and_(
                    Transaction.apartment_id == apartment_id,
                    func.abs(Transaction.area - area) < self.area_tolerance,
                )
            )
            .group_by(Transaction.apartment_id)
        )

        result = await db.execute(query)
        row = result.first()

        if not row or not row.max_price:
            return None

        # Get the date of the all-time high transaction
        date_query = (
            select(Transaction.deal_date)
            .where(
                and_(
                    Transaction.apartment_id == apartment_id,
                    Transaction.deal_amount == row.max_price,
                    func.abs(Transaction.area - area) < self.area_tolerance,
                )
            )
            .order_by(Transaction.deal_date.desc())
            .limit(1)
        )

        date_result = await db.execute(date_query)
        date_row = date_result.scalar_one_or_none()

        return {
            "max_price": row.max_price,
            "deal_date": date_row.isoformat() if date_row else None,
        }

    async def analyze_listing(
        self,
        db: AsyncSession,
        listing_id: int,
    ) -> Optional[FireSaleAnalysis]:
        """Analyze a single listing for fire sale potential.

        Args:
            db: Database session
            listing_id: Listing ID to analyze

        Returns:
            FireSaleAnalysis or None if not applicable
        """
        # Get listing with apartment info
        query = (
            select(Listing, Apartment)
            .join(Apartment, Listing.apartment_id == Apartment.id)
            .where(Listing.id == listing_id)
        )

        result = await db.execute(query)
        row = result.first()

        if not row:
            return None

        listing, apartment = row

        if not listing.area or not listing.price:
            return None

        # Get all-time high for this apartment/area
        ath = await self.get_all_time_high(
            db,
            apartment.id,
            float(listing.area),
        )

        if not ath or ath["max_price"] <= listing.price:
            return None

        # Calculate discount rate
        discount_rate = (
            (ath["max_price"] - listing.price) / ath["max_price"]
        ) * 100

        urgency = self._determine_urgency(discount_rate)

        if urgency == "NONE":
            return None

        return FireSaleAnalysis(
            listing_id=listing.id,
            apartment_id=apartment.id,
            apartment_name=apartment.name,
            dong_code=apartment.dong_code or "",
            area=float(listing.area),
            floor=listing.floor,
            asking_price=listing.price,
            all_time_high=ath["max_price"],
            all_time_high_date=ath["deal_date"] or "",
            discount_rate=round(discount_rate, 1),
            urgency_level=urgency,
        )

    async def find_fire_sales(
        self,
        db: AsyncSession,
        dong_code: Optional[str] = None,
        min_discount_rate: float = 15.0,
        limit: int = 50,
    ) -> List[FireSaleAnalysis]:
        """Find potential fire sale listings.

        Args:
            db: Database session
            dong_code: Optional filter by dong_code
            min_discount_rate: Minimum discount rate to include
            limit: Maximum results to return

        Returns:
            List of FireSaleAnalysis sorted by discount rate descending
        """
        # Build subquery for all-time highs per apartment/area
        # This groups transactions by apartment and rounded area
        ath_subquery = (
            select(
                Transaction.apartment_id,
                func.round(Transaction.area, 0).label("area_group"),
                func.max(Transaction.deal_amount).label("max_price"),
            )
            .group_by(
                Transaction.apartment_id,
                func.round(Transaction.area, 0),
            )
            .subquery()
        )

        # Main query: join listings with ATH data
        query = (
            select(
                Listing,
                Apartment,
                ath_subquery.c.max_price,
            )
            .join(Apartment, Listing.apartment_id == Apartment.id)
            .join(
                ath_subquery,
                and_(
                    Listing.apartment_id == ath_subquery.c.apartment_id,
                    func.abs(
                        func.round(Listing.area, 0) - ath_subquery.c.area_group
                    ) < self.area_tolerance,
                ),
            )
            .where(
                and_(
                    Listing.is_active == True,
                    Listing.area.isnot(None),
                    Listing.price.isnot(None),
                    ath_subquery.c.max_price > Listing.price,
                )
            )
        )

        # Filter by dong_code if specified
        if dong_code:
            query = query.where(Apartment.dong_code == dong_code)

        result = await db.execute(query)
        rows = result.all()

        # Calculate discount rates and filter
        fire_sales = []

        for listing, apartment, max_price in rows:
            if not max_price or max_price <= listing.price:
                continue

            discount_rate = ((max_price - listing.price) / max_price) * 100

            if discount_rate < min_discount_rate:
                continue

            urgency = self._determine_urgency(discount_rate)

            # Get the date of ATH
            date_query = (
                select(Transaction.deal_date)
                .where(
                    and_(
                        Transaction.apartment_id == apartment.id,
                        Transaction.deal_amount == max_price,
                    )
                )
                .order_by(Transaction.deal_date.desc())
                .limit(1)
            )

            date_result = await db.execute(date_query)
            ath_date = date_result.scalar_one_or_none()

            # Get naver_complex_no from listing or apartment
            naver_complex_no = listing.naver_complex_no or apartment.naver_complex_no

            fire_sales.append(
                FireSaleAnalysis(
                    listing_id=listing.id,
                    apartment_id=apartment.id,
                    apartment_name=apartment.name,
                    dong_code=apartment.dong_code or "",
                    area=float(listing.area) if listing.area else 0,
                    floor=listing.floor,
                    asking_price=listing.price,
                    all_time_high=max_price,
                    all_time_high_date=ath_date.isoformat() if ath_date else "",
                    discount_rate=round(discount_rate, 1),
                    urgency_level=urgency,
                    article_no=listing.article_no,
                    naver_complex_no=naver_complex_no,
                    latitude=float(apartment.latitude) if apartment.latitude else None,
                    longitude=float(apartment.longitude) if apartment.longitude else None,
                )
            )

        # Sort by discount rate descending and limit
        fire_sales.sort(key=lambda x: x.discount_rate, reverse=True)

        return fire_sales[:limit]
