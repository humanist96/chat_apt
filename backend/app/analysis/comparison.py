"""Comparison analysis for property listings.

This module compares a listing's price against similar apartments
to determine if it's undervalued or overvalued.
"""
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ComparisonResult:
    """Comparison result for a single similar apartment."""
    similar_apartment_id: int
    similar_apartment_name: str
    target_price_per_pyeong: int  # 대상 매물 평당가
    similar_price_per_pyeong: int  # 비교 아파트 최근 평당가
    price_gap_amount: int  # 가격 차이 (원)
    price_gap_percent: float  # 가격 차이 (%)
    similarity_score: float


@dataclass
class ComparisonReport:
    """Complete comparison analysis report."""
    listing_id: int
    apartment_id: int
    apartment_name: str
    listing_price: int
    area_pyeong: float
    price_per_pyeong: int
    avg_similar_price_per_pyeong: int  # 유사 매물 평균 평당가
    avg_gap_percent: float  # 평균 가격 차이
    is_undervalued: bool
    comparison_results: List[ComparisonResult] = field(default_factory=list)
    analyzed_at: datetime = field(default_factory=datetime.utcnow)


class ComparisonAnalyzer:
    """Analyzes listing prices against similar apartments."""

    # Conversion factor: 1평 = 3.3058 m²
    M2_TO_PYEONG = 3.3058

    def __init__(self, undervalued_threshold: float = -5.0):
        """Initialize the analyzer.

        Args:
            undervalued_threshold: Percentage below which listing is
                                   considered undervalued (negative number)
        """
        self.undervalued_threshold = undervalued_threshold

    def area_to_pyeong(self, area_m2: float) -> float:
        """Convert area from m² to 평.

        Args:
            area_m2: Area in square meters

        Returns:
            Area in pyeong
        """
        return area_m2 / self.M2_TO_PYEONG

    def calculate_price_per_pyeong(
        self,
        price: int,
        area_m2: float,
    ) -> int:
        """Calculate price per pyeong.

        Args:
            price: Price in 만원
            area_m2: Area in m²

        Returns:
            Price per pyeong in 만원
        """
        area_pyeong = self.area_to_pyeong(area_m2)
        if area_pyeong <= 0:
            return 0
        return int(price / area_pyeong)

    def get_recent_price_per_pyeong(
        self,
        monthly_prices: List[Tuple[str, int]],  # (year_month, avg_price_per_pyeong)
        months: int = 6,
    ) -> int:
        """Get average price per pyeong from recent months.

        Args:
            monthly_prices: List of (year_month, price_per_pyeong) tuples
            months: Number of recent months to consider

        Returns:
            Average price per pyeong
        """
        if not monthly_prices:
            return 0

        # Sort by year_month descending and take recent months
        sorted_prices = sorted(monthly_prices, key=lambda x: x[0], reverse=True)
        recent = sorted_prices[:months]

        if not recent:
            return 0

        return int(sum(p[1] for p in recent) / len(recent))

    def compare_with_similar(
        self,
        listing: dict,
        similar_apartments: List[dict],
        similar_prices: Dict[int, List[Tuple[str, int]]],
    ) -> List[ComparisonResult]:
        """Compare listing against similar apartments.

        Args:
            listing: Listing data with price and area
            similar_apartments: List of similar apartment data
            similar_prices: Dict mapping apartment_id to price history

        Returns:
            List of comparison results
        """
        # Calculate target listing's price per pyeong
        target_price_pp = self.calculate_price_per_pyeong(
            listing["price"],
            listing["area"],
        )

        results = []

        for apt in similar_apartments:
            apt_id = apt["id"]
            prices = similar_prices.get(apt_id, [])

            if not prices:
                continue

            similar_price_pp = self.get_recent_price_per_pyeong(prices)

            if similar_price_pp <= 0:
                continue

            # Calculate gap
            gap_amount = target_price_pp - similar_price_pp
            gap_percent = (gap_amount / similar_price_pp) * 100

            result = ComparisonResult(
                similar_apartment_id=apt_id,
                similar_apartment_name=apt.get("name", ""),
                target_price_per_pyeong=target_price_pp,
                similar_price_per_pyeong=similar_price_pp,
                price_gap_amount=gap_amount,
                price_gap_percent=round(gap_percent, 2),
                similarity_score=apt.get("similarity_score", 0),
            )
            results.append(result)

        return results

    def generate_report(
        self,
        listing: dict,
        similar_apartments: List[dict],
        similar_prices: Dict[int, List[Tuple[str, int]]],
    ) -> ComparisonReport:
        """Generate a complete comparison analysis report.

        Args:
            listing: Listing data
            similar_apartments: List of similar apartment data with similarity_score
            similar_prices: Dict mapping apartment_id to price history

        Returns:
            ComparisonReport with all analysis
        """
        # Compare with each similar apartment
        comparison_results = self.compare_with_similar(
            listing,
            similar_apartments,
            similar_prices,
        )

        # Calculate averages
        if comparison_results:
            avg_similar_pp = int(
                sum(r.similar_price_per_pyeong for r in comparison_results) /
                len(comparison_results)
            )
            avg_gap = sum(r.price_gap_percent for r in comparison_results) / len(comparison_results)
        else:
            avg_similar_pp = 0
            avg_gap = 0

        # Calculate target metrics
        target_price_pp = self.calculate_price_per_pyeong(
            listing["price"],
            listing["area"],
        )
        area_pyeong = self.area_to_pyeong(listing["area"])

        # Determine if undervalued
        is_undervalued = avg_gap <= self.undervalued_threshold

        return ComparisonReport(
            listing_id=listing["id"],
            apartment_id=listing.get("apartment_id", 0),
            apartment_name=listing.get("apartment_name", ""),
            listing_price=listing["price"],
            area_pyeong=round(area_pyeong, 2),
            price_per_pyeong=target_price_pp,
            avg_similar_price_per_pyeong=avg_similar_pp,
            avg_gap_percent=round(avg_gap, 2),
            is_undervalued=is_undervalued,
            comparison_results=comparison_results,
        )

    def find_undervalued_listings(
        self,
        listings: List[dict],
        similar_data: Dict[int, Tuple[List[dict], Dict[int, List[Tuple[str, int]]]]],
        threshold: Optional[float] = None,
    ) -> List[ComparisonReport]:
        """Find undervalued listings from a list.

        Args:
            listings: List of listing data
            similar_data: Dict mapping listing_id to (similar_apts, similar_prices)
            threshold: Override undervalued threshold

        Returns:
            List of ComparisonReports for undervalued listings, sorted by gap
        """
        if threshold is None:
            threshold = self.undervalued_threshold

        undervalued = []

        for listing in listings:
            listing_id = listing["id"]

            if listing_id not in similar_data:
                continue

            similar_apts, similar_prices = similar_data[listing_id]

            report = self.generate_report(listing, similar_apts, similar_prices)

            if report.avg_gap_percent <= threshold:
                undervalued.append(report)

        # Sort by most undervalued first
        undervalued.sort(key=lambda r: r.avg_gap_percent)

        return undervalued
