"""Similar apartment finder using multiple similarity metrics.

This module implements the algorithm to find similar apartments based on:
- Geographic proximity (Haversine distance)
- Area similarity
- Price trend correlation (Pearson)
- Complex scale similarity
- Building age similarity
"""
import math
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass

from scipy import stats


@dataclass
class SimilarityScore:
    """Similarity score breakdown between two apartments."""
    apartment_id: int
    similar_apartment_id: int
    total_score: float  # Weighted average (0-100)
    location_score: float  # Geographic proximity (0-100)
    area_score: float  # Area similarity (0-100)
    correlation_score: float  # Price trend correlation (0-100)
    scale_score: float  # Complex scale similarity (0-100)
    age_score: float  # Building age similarity (0-100)


class SimilarApartmentFinder:
    """Finds similar apartments using multiple weighted metrics."""

    # Default weights for similarity calculation
    DEFAULT_WEIGHTS = {
        "location": 0.25,  # Geographic proximity
        "area": 0.20,  # Area similarity
        "correlation": 0.30,  # Price trend correlation (most important)
        "scale": 0.10,  # Complex scale
        "age": 0.15,  # Building age
    }

    # Maximum distance in km to consider as similar
    MAX_DISTANCE_KM = 5.0

    # Area tolerance percentage
    AREA_TOLERANCE = 0.20  # 20%

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        max_distance_km: float = 5.0,
    ):
        """Initialize the finder.

        Args:
            weights: Custom weights for each metric
            max_distance_km: Maximum distance to consider
        """
        self.weights = weights or self.DEFAULT_WEIGHTS
        self.max_distance_km = max_distance_km

        # Validate weights sum to 1
        total_weight = sum(self.weights.values())
        if abs(total_weight - 1.0) > 0.01:
            # Normalize weights
            self.weights = {k: v / total_weight for k, v in self.weights.items()}

    def calculate_similarity(
        self,
        target: dict,
        candidate: dict,
        target_prices: List[Tuple[str, float]],  # (year_month, avg_price)
        candidate_prices: List[Tuple[str, float]],
    ) -> SimilarityScore:
        """Calculate similarity score between two apartments.

        Args:
            target: Target apartment data
            candidate: Candidate apartment data
            target_prices: Monthly price history for target
            candidate_prices: Monthly price history for candidate

        Returns:
            SimilarityScore with all metrics
        """
        # Calculate individual scores
        location_score = self._calculate_location_score(
            target.get("latitude"),
            target.get("longitude"),
            candidate.get("latitude"),
            candidate.get("longitude"),
        )

        area_score = self._calculate_area_score(
            target.get("avg_area"),
            candidate.get("avg_area"),
        )

        correlation_score = self._calculate_correlation_score(
            target_prices,
            candidate_prices,
        )

        scale_score = self._calculate_scale_score(
            target.get("total_units"),
            candidate.get("total_units"),
        )

        age_score = self._calculate_age_score(
            target.get("built_year"),
            candidate.get("built_year"),
        )

        # Calculate weighted total
        total_score = (
            self.weights["location"] * location_score +
            self.weights["area"] * area_score +
            self.weights["correlation"] * correlation_score +
            self.weights["scale"] * scale_score +
            self.weights["age"] * age_score
        )

        return SimilarityScore(
            apartment_id=target["id"],
            similar_apartment_id=candidate["id"],
            total_score=round(total_score, 2),
            location_score=round(location_score, 2),
            area_score=round(area_score, 2),
            correlation_score=round(correlation_score, 2),
            scale_score=round(scale_score, 2),
            age_score=round(age_score, 2),
        )

    def _calculate_location_score(
        self,
        lat1: Optional[float],
        lon1: Optional[float],
        lat2: Optional[float],
        lon2: Optional[float],
    ) -> float:
        """Calculate location similarity score using Haversine distance.

        Returns:
            Score from 0 to 100 (100 = same location)
        """
        if None in (lat1, lon1, lat2, lon2):
            return 50.0  # Default score for missing data

        distance = self._haversine_distance(lat1, lon1, lat2, lon2)

        if distance >= self.max_distance_km:
            return 0.0

        # Linear decay from 100 to 0 over max_distance_km
        return 100.0 * (1.0 - distance / self.max_distance_km)

    @staticmethod
    def _haversine_distance(
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """Calculate distance between two points using Haversine formula.

        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates

        Returns:
            Distance in kilometers
        """
        R = 6371  # Earth's radius in km

        lat1_rad = math.radians(float(lat1))
        lat2_rad = math.radians(float(lat2))
        delta_lat = math.radians(float(lat2) - float(lat1))
        delta_lon = math.radians(float(lon2) - float(lon1))

        a = (
            math.sin(delta_lat / 2) ** 2 +
            math.cos(lat1_rad) * math.cos(lat2_rad) *
            math.sin(delta_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def _calculate_area_score(
        self,
        area1: Optional[float],
        area2: Optional[float],
    ) -> float:
        """Calculate area similarity score.

        Returns:
            Score from 0 to 100 (100 = same area)
        """
        if area1 is None or area2 is None or area1 <= 0 or area2 <= 0:
            return 50.0

        area1 = float(area1)
        area2 = float(area2)

        # Calculate percentage difference
        diff_percent = abs(area1 - area2) / max(area1, area2)

        if diff_percent >= self.AREA_TOLERANCE:
            return 0.0

        # Linear decay from 100 to 0 over tolerance
        return 100.0 * (1.0 - diff_percent / self.AREA_TOLERANCE)

    def _calculate_correlation_score(
        self,
        prices1: List[Tuple[str, float]],
        prices2: List[Tuple[str, float]],
    ) -> float:
        """Calculate price trend correlation using Pearson coefficient.

        Returns:
            Score from 0 to 100 (100 = perfect positive correlation)
        """
        if not prices1 or not prices2:
            return 50.0

        # Create dict for easier lookup
        prices1_dict = {ym: price for ym, price in prices1}
        prices2_dict = {ym: price for ym, price in prices2}

        # Find common months
        common_months = set(prices1_dict.keys()) & set(prices2_dict.keys())

        if len(common_months) < 3:  # Need at least 3 data points
            return 50.0

        # Extract aligned price series
        sorted_months = sorted(common_months)
        series1 = [prices1_dict[m] for m in sorted_months]
        series2 = [prices2_dict[m] for m in sorted_months]

        try:
            # Calculate Pearson correlation coefficient
            correlation, _ = stats.pearsonr(series1, series2)

            # Convert correlation (-1 to 1) to score (0 to 100)
            # -1 -> 0, 0 -> 50, 1 -> 100
            return 50.0 * (1.0 + correlation)
        except (ValueError, RuntimeWarning):
            return 50.0

    def _calculate_scale_score(
        self,
        units1: Optional[int],
        units2: Optional[int],
    ) -> float:
        """Calculate complex scale similarity score.

        Returns:
            Score from 0 to 100 (100 = same scale)
        """
        if units1 is None or units2 is None or units1 <= 0 or units2 <= 0:
            return 50.0

        # Calculate ratio (smaller / larger)
        ratio = min(units1, units2) / max(units1, units2)

        # Score is proportional to ratio
        return 100.0 * ratio

    def _calculate_age_score(
        self,
        year1: Optional[int],
        year2: Optional[int],
    ) -> float:
        """Calculate building age similarity score.

        Returns:
            Score from 0 to 100 (100 = same year)
        """
        if year1 is None or year2 is None:
            return 50.0

        # Max age difference to consider (10 years)
        max_diff = 10

        diff = abs(year1 - year2)

        if diff >= max_diff:
            return 0.0

        return 100.0 * (1.0 - diff / max_diff)

    def find_similar_apartments(
        self,
        target: dict,
        candidates: List[dict],
        target_prices: List[Tuple[str, float]],
        candidates_prices: Dict[int, List[Tuple[str, float]]],
        top_n: int = 10,
        min_score: float = 60.0,
    ) -> List[SimilarityScore]:
        """Find most similar apartments to target.

        Args:
            target: Target apartment data
            candidates: List of candidate apartments
            target_prices: Price history for target
            candidates_prices: Dict mapping apartment_id to price history
            top_n: Maximum number of results
            min_score: Minimum similarity score threshold

        Returns:
            List of SimilarityScore sorted by total_score descending
        """
        scores = []

        for candidate in candidates:
            if candidate["id"] == target["id"]:
                continue

            candidate_prices = candidates_prices.get(candidate["id"], [])

            score = self.calculate_similarity(
                target,
                candidate,
                target_prices,
                candidate_prices,
            )

            if score.total_score >= min_score:
                scores.append(score)

        # Sort by total score descending
        scores.sort(key=lambda s: s.total_score, reverse=True)

        return scores[:top_n]
