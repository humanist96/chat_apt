"""Fire sale detection for property listings.

This module detects potential fire sales by comparing current asking prices
against historical all-time high transaction prices.

Enhanced features:
- Floor-based price normalization
- Time-weighted reference prices
- Reference quality validation
"""
from typing import List, Optional
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.apartment import Apartment, Transaction, Listing
from app.analysis.price_adjustment import (
    FloorAdjuster,
    TimeWeightedPriceCalculator,
    ReferenceQualityValidator,
    ReferenceQuality,
    TransactionData,
)


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
    # New fields for enhanced analysis
    reference_quality: str = "unknown"  # "high" | "medium" | "low" | "insufficient"
    weighted_reference_price: Optional[int] = None  # Time-weighted reference
    floor_adjusted_price: Optional[int] = None  # Floor-normalized asking price
    transaction_count: int = 0  # Number of reference transactions


class FireSaleDetector:
    """Detects potential fire sale listings.

    Enhanced with:
    - Floor-based price normalization (로열층 vs 저층)
    - Time-weighted reference prices (최근 거래 높은 가중치)
    - Reference quality validation (거래 데이터 신뢰도)
    """

    # Discount rate thresholds for urgency levels
    HIGH_THRESHOLD = 20.0  # 20% or more discount
    MEDIUM_THRESHOLD = 15.0  # 15% or more discount
    LOW_THRESHOLD = 10.0  # 10% or more discount

    def __init__(
        self,
        area_tolerance: float = 1.0,
        high_threshold: float = 20.0,
        medium_threshold: float = 15.0,
        use_floor_adjustment: bool = True,
        use_time_weighting: bool = True,
        min_reference_quality: ReferenceQuality = ReferenceQuality.LOW,
    ):
        """Initialize the detector.

        Args:
            area_tolerance: Allowed area difference in m² for matching same type (typically within 1㎡)
            high_threshold: Discount rate for HIGH urgency
            medium_threshold: Discount rate for MEDIUM urgency
            use_floor_adjustment: Whether to normalize prices by floor
            use_time_weighting: Whether to weight transactions by time
            min_reference_quality: Minimum quality for valid analysis
        """
        self.area_tolerance = area_tolerance
        self.HIGH_THRESHOLD = high_threshold
        self.MEDIUM_THRESHOLD = medium_threshold
        self.use_floor_adjustment = use_floor_adjustment
        self.use_time_weighting = use_time_weighting
        self.min_reference_quality = min_reference_quality

        # Initialize helpers
        self.floor_adjuster = FloorAdjuster() if use_floor_adjustment else None
        self.time_calculator = TimeWeightedPriceCalculator(
            floor_adjuster=self.floor_adjuster
        ) if use_time_weighting else None
        self.quality_validator = ReferenceQualityValidator()

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

    async def get_reference_transactions(
        self,
        db: AsyncSession,
        apartment_id: int,
        area: float,
        months: int = 24,
    ) -> List[TransactionData]:
        """Get reference transactions for an apartment/area.

        Args:
            db: Database session
            apartment_id: Apartment ID
            area: Target area in m²
            months: Number of months to look back

        Returns:
            List of TransactionData for reference calculation
        """
        from datetime import timedelta

        cutoff_date = date.today() - timedelta(days=months * 30)

        query = (
            select(
                Transaction.deal_amount,
                Transaction.deal_date,
                Transaction.floor,
                Transaction.area,
            )
            .where(
                and_(
                    Transaction.apartment_id == apartment_id,
                    func.abs(Transaction.area - area) < self.area_tolerance,
                    Transaction.deal_date >= cutoff_date,
                )
            )
            .order_by(Transaction.deal_date.desc())
        )

        result = await db.execute(query)
        rows = result.all()

        return [
            TransactionData(
                deal_amount=row.deal_amount,
                deal_date=row.deal_date,
                floor=row.floor,
                area=float(row.area) if row.area else None,
            )
            for row in rows
        ]

    async def analyze_listing_enhanced(
        self,
        db: AsyncSession,
        listing_id: int,
    ) -> Optional[FireSaleAnalysis]:
        """Enhanced analysis with floor adjustment and time weighting.

        Args:
            db: Database session
            listing_id: Listing ID to analyze

        Returns:
            FireSaleAnalysis with enhanced metrics or None if not applicable
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

        # Get reference transactions
        transactions = await self.get_reference_transactions(
            db,
            apartment.id,
            float(listing.area),
        )

        # Validate reference quality
        quality_result = self.quality_validator.validate(transactions)

        if quality_result.quality.value == "insufficient":
            return None

        # Skip if below minimum quality threshold
        quality_order = {
            "high": 3,
            "medium": 2,
            "low": 1,
            "insufficient": 0,
        }
        if quality_order.get(quality_result.quality.value, 0) < quality_order.get(
            self.min_reference_quality.value, 0
        ):
            return None

        # Get all-time high (for backwards compatibility)
        ath = await self.get_all_time_high(
            db,
            apartment.id,
            float(listing.area),
        )

        if not ath:
            return None

        # Calculate weighted reference price
        weighted_ref = None
        if self.time_calculator and transactions:
            weighted_result = self.time_calculator.calculate_weighted_reference(
                transactions,
                normalize_floor=self.use_floor_adjustment,
            )
            weighted_ref = weighted_result.weighted_avg_price

        # Normalize listing price by floor
        floor_adjusted = None
        if self.floor_adjuster and listing.floor:
            adjusted = self.floor_adjuster.normalize_price(
                listing.price, listing.floor
            )
            floor_adjusted = adjusted.adjusted_price

        # Use weighted reference or ATH for comparison
        reference_price = weighted_ref if weighted_ref else ath["max_price"]
        compare_price = floor_adjusted if floor_adjusted else listing.price

        if reference_price <= compare_price:
            return None

        # Calculate discount rate
        discount_rate = (
            (reference_price - compare_price) / reference_price
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
            reference_quality=quality_result.quality.value,
            weighted_reference_price=weighted_ref,
            floor_adjusted_price=floor_adjusted,
            transaction_count=quality_result.transaction_count,
        )

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
                    Listing.is_active.is_(True),
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

        # Collect apartment/price pairs that need ATH dates
        ath_lookup_keys = []
        for listing, apartment, max_price in rows:
            if max_price and max_price > listing.price:
                discount_rate = ((max_price - listing.price) / max_price) * 100
                if discount_rate >= min_discount_rate:
                    ath_lookup_keys.append((apartment.id, max_price))

        # Batch load ATH dates for all qualifying listings (fixes N+1 query)
        ath_dates: dict[tuple[int, int], date] = {}
        if ath_lookup_keys:
            # Build a query to get dates for all apartment/price combinations
            # Create conditions for each apartment/price pair
            conditions = [
                and_(
                    Transaction.apartment_id == apt_id,
                    Transaction.deal_amount == price,
                )
                for apt_id, price in set(ath_lookup_keys)
            ]

            if conditions:
                from sqlalchemy import or_
                date_query = (
                    select(
                        Transaction.apartment_id,
                        Transaction.deal_amount,
                        func.max(Transaction.deal_date).label("max_date"),
                    )
                    .where(or_(*conditions))
                    .group_by(Transaction.apartment_id, Transaction.deal_amount)
                )

                date_result = await db.execute(date_query)
                for apt_id, amount, deal_date in date_result.all():
                    ath_dates[(apt_id, amount)] = deal_date

        # Calculate discount rates and build results
        fire_sales = []

        for listing, apartment, max_price in rows:
            if not max_price or max_price <= listing.price:
                continue

            discount_rate = ((max_price - listing.price) / max_price) * 100

            if discount_rate < min_discount_rate:
                continue

            urgency = self._determine_urgency(discount_rate)

            # Get ATH date from batch-loaded cache
            ath_date = ath_dates.get((apartment.id, max_price))

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
