"""Recommendation engine for property listings.

This module generates recommendation scores based on multiple factors
to identify the best value properties.
"""
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RecommendationScore:
    """Recommendation score for a listing."""
    listing_id: int
    apartment_id: int
    apartment_name: str

    # Score components (0-100)
    price_score: float  # Based on discount vs similar apartments
    trend_score: float  # Based on price trend direction
    liquidity_score: float  # Based on transaction volume
    quality_score: float  # Based on apartment quality factors

    # Final scores
    total_score: float  # Weighted average (0-100)
    rank: int = 0

    # Additional info
    discount_percent: float = 0.0
    monthly_transactions: int = 0
    calculated_at: datetime = field(default_factory=datetime.utcnow)


class RecommendationEngine:
    """Generates property recommendations based on multiple factors."""

    DEFAULT_WEIGHTS = {
        "price": 0.40,  # Most important - value for money
        "trend": 0.25,  # Price trend direction
        "liquidity": 0.15,  # Transaction activity
        "quality": 0.20,  # Overall quality
    }

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
    ):
        """Initialize the recommendation engine.

        Args:
            weights: Custom weights for scoring components
        """
        self.weights = weights or self.DEFAULT_WEIGHTS

        # Normalize weights
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.01:
            self.weights = {k: v / total for k, v in self.weights.items()}

    def calculate_price_score(
        self,
        discount_percent: float,
    ) -> float:
        """Calculate price score based on discount vs similar apartments.

        Args:
            discount_percent: Percentage below similar apartment prices
                             (negative = cheaper, positive = more expensive)

        Returns:
            Score from 0 to 100 (higher = better value)
        """
        # Best score at -20% discount, worst at +20% premium
        # Map from [-20, +20] to [100, 0]

        if discount_percent <= -20:
            return 100.0
        elif discount_percent >= 20:
            return 0.0
        else:
            # Linear mapping: -20% -> 100, +20% -> 0
            return 100.0 - (discount_percent + 20) * 2.5

    def calculate_trend_score(
        self,
        price_changes: List[float],  # Recent monthly price changes (%)
    ) -> float:
        """Calculate trend score based on price direction.

        Args:
            price_changes: List of monthly price change percentages

        Returns:
            Score from 0 to 100 (higher = better/improving trend)
        """
        if not price_changes:
            return 50.0

        # Calculate average recent change
        avg_change = sum(price_changes) / len(price_changes)

        # Rising market (positive change) = good time to buy if undervalued
        # Falling market (negative change) = might fall further

        # Map from [-10%, +10%] to [0, 100]
        if avg_change <= -10:
            return 0.0
        elif avg_change >= 10:
            return 100.0
        else:
            return 50.0 + avg_change * 5

    def calculate_liquidity_score(
        self,
        monthly_transactions: int,
        area_avg_transactions: int = 5,
    ) -> float:
        """Calculate liquidity score based on transaction volume.

        Args:
            monthly_transactions: Average monthly transactions for this complex
            area_avg_transactions: Average for the area

        Returns:
            Score from 0 to 100 (higher = more liquid market)
        """
        if area_avg_transactions <= 0:
            area_avg_transactions = 5

        if monthly_transactions <= 0:
            return 20.0

        # Ratio of complex to area average
        ratio = monthly_transactions / area_avg_transactions

        # Score based on ratio: 0.5x = 50, 1x = 75, 2x+ = 100
        if ratio <= 0.5:
            return ratio * 100  # 0 to 50
        elif ratio <= 2.0:
            return 50 + (ratio - 0.5) * 33.3  # 50 to 100
        else:
            return 100.0

    def calculate_quality_score(
        self,
        built_year: Optional[int],
        total_units: Optional[int],
        has_amenities: bool = False,
    ) -> float:
        """Calculate quality score based on apartment characteristics.

        Args:
            built_year: Year the building was constructed
            total_units: Number of units in the complex
            has_amenities: Whether complex has good amenities

        Returns:
            Score from 0 to 100
        """
        score = 50.0  # Base score

        # Age factor (newer = better, up to 30 points)
        if built_year:
            current_year = datetime.now().year
            age = current_year - built_year

            if age <= 5:
                score += 30
            elif age <= 10:
                score += 25
            elif age <= 15:
                score += 20
            elif age <= 20:
                score += 10
            else:
                score += 0

        # Scale factor (larger complexes = better, up to 20 points)
        if total_units:
            if total_units >= 1000:
                score += 20
            elif total_units >= 500:
                score += 15
            elif total_units >= 300:
                score += 10
            elif total_units >= 100:
                score += 5

        # Amenities bonus
        if has_amenities:
            score += 10

        return min(100.0, score)

    def calculate_recommendation(
        self,
        listing: dict,
        discount_percent: float,
        price_changes: List[float],
        monthly_transactions: int,
        area_avg_transactions: int = 5,
    ) -> RecommendationScore:
        """Calculate recommendation score for a listing.

        Args:
            listing: Listing data including apartment info
            discount_percent: Discount vs similar apartments
            price_changes: Recent monthly price changes
            monthly_transactions: Transaction volume
            area_avg_transactions: Area average transactions

        Returns:
            RecommendationScore with all components
        """
        # Calculate component scores
        price_score = self.calculate_price_score(discount_percent)
        trend_score = self.calculate_trend_score(price_changes)
        liquidity_score = self.calculate_liquidity_score(
            monthly_transactions,
            area_avg_transactions,
        )
        quality_score = self.calculate_quality_score(
            listing.get("built_year"),
            listing.get("total_units"),
            listing.get("has_amenities", False),
        )

        # Calculate weighted total
        total_score = (
            self.weights["price"] * price_score +
            self.weights["trend"] * trend_score +
            self.weights["liquidity"] * liquidity_score +
            self.weights["quality"] * quality_score
        )

        return RecommendationScore(
            listing_id=listing["id"],
            apartment_id=listing.get("apartment_id", 0),
            apartment_name=listing.get("apartment_name", ""),
            price_score=round(price_score, 2),
            trend_score=round(trend_score, 2),
            liquidity_score=round(liquidity_score, 2),
            quality_score=round(quality_score, 2),
            total_score=round(total_score, 2),
            discount_percent=round(discount_percent, 2),
            monthly_transactions=monthly_transactions,
        )

    def rank_listings(
        self,
        recommendations: List[RecommendationScore],
    ) -> List[RecommendationScore]:
        """Rank listings by recommendation score.

        Args:
            recommendations: List of recommendation scores

        Returns:
            Sorted list with rank assigned
        """
        # Sort by total score descending
        sorted_recs = sorted(
            recommendations,
            key=lambda r: r.total_score,
            reverse=True,
        )

        # Assign ranks
        for i, rec in enumerate(sorted_recs, 1):
            rec.rank = i

        return sorted_recs

    def get_top_recommendations(
        self,
        recommendations: List[RecommendationScore],
        top_n: int = 10,
        min_score: float = 60.0,
    ) -> List[RecommendationScore]:
        """Get top N recommendations above minimum score.

        Args:
            recommendations: List of recommendation scores
            top_n: Maximum number of results
            min_score: Minimum total score threshold

        Returns:
            Top recommendations
        """
        ranked = self.rank_listings(recommendations)

        return [r for r in ranked if r.total_score >= min_score][:top_n]
