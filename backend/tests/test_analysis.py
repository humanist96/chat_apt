"""Tests for analysis module."""
import pytest
from datetime import datetime

from app.analysis.similarity import SimilarApartmentFinder, SimilarityScore
from app.analysis.comparison import ComparisonAnalyzer, ComparisonReport
from app.analysis.recommendation import RecommendationEngine, RecommendationScore


class TestSimilarApartmentFinder:
    """Tests for SimilarApartmentFinder."""

    def test_haversine_distance_same_point(self):
        """Test Haversine distance for same point."""
        dist = SimilarApartmentFinder._haversine_distance(
            37.5172, 127.0473,  # Gangnam
            37.5172, 127.0473,
        )
        assert dist == 0.0

    def test_haversine_distance_known_distance(self):
        """Test Haversine distance for known cities."""
        # Seoul to Busan is approximately 325 km
        dist = SimilarApartmentFinder._haversine_distance(
            37.5665, 126.9780,  # Seoul
            35.1796, 129.0756,  # Busan
        )
        assert 320 < dist < 330

    def test_location_score_same_location(self):
        """Test location score for same location."""
        finder = SimilarApartmentFinder()
        score = finder._calculate_location_score(
            37.5172, 127.0473,
            37.5172, 127.0473,
        )
        assert score == 100.0

    def test_location_score_far_away(self):
        """Test location score for distant locations."""
        finder = SimilarApartmentFinder(max_distance_km=5.0)
        score = finder._calculate_location_score(
            37.5172, 127.0473,  # Gangnam
            37.3945, 127.1112,  # Bundang (about 15km)
        )
        assert score == 0.0

    def test_location_score_missing_data(self):
        """Test location score with missing data."""
        finder = SimilarApartmentFinder()
        score = finder._calculate_location_score(None, None, 37.5, 127.0)
        assert score == 50.0

    def test_area_score_same_area(self):
        """Test area score for identical areas."""
        finder = SimilarApartmentFinder()
        score = finder._calculate_area_score(84.95, 84.95)
        assert score == 100.0

    def test_area_score_within_tolerance(self):
        """Test area score within tolerance."""
        finder = SimilarApartmentFinder()
        # 10% difference should give partial score
        score = finder._calculate_area_score(84.95, 76.45)  # ~10% diff
        assert 40 < score < 60

    def test_area_score_outside_tolerance(self):
        """Test area score outside tolerance."""
        finder = SimilarApartmentFinder()
        # 25% difference should give 0
        score = finder._calculate_area_score(84.95, 63.71)  # 25% diff
        assert score == 0.0

    def test_correlation_score_perfect_correlation(self):
        """Test correlation score with perfectly correlated prices."""
        finder = SimilarApartmentFinder()

        prices1 = [("2024-01", 100), ("2024-02", 110), ("2024-03", 120)]
        prices2 = [("2024-01", 200), ("2024-02", 220), ("2024-03", 240)]

        score = finder._calculate_correlation_score(prices1, prices2)
        assert score >= 99.9  # Perfect positive correlation (allowing for float precision)

    def test_correlation_score_no_correlation(self):
        """Test correlation score with no data."""
        finder = SimilarApartmentFinder()

        score = finder._calculate_correlation_score([], [])
        assert score == 50.0  # Default for insufficient data

    def test_scale_score_same_scale(self):
        """Test scale score for same unit count."""
        finder = SimilarApartmentFinder()
        score = finder._calculate_scale_score(500, 500)
        assert score == 100.0

    def test_scale_score_different_scales(self):
        """Test scale score for different unit counts."""
        finder = SimilarApartmentFinder()
        # 250 / 500 = 0.5 ratio -> 50% score
        score = finder._calculate_scale_score(500, 250)
        assert score == 50.0

    def test_age_score_same_year(self):
        """Test age score for same building year."""
        finder = SimilarApartmentFinder()
        score = finder._calculate_age_score(2020, 2020)
        assert score == 100.0

    def test_age_score_old_difference(self):
        """Test age score for large year difference."""
        finder = SimilarApartmentFinder()
        # 15 year difference (> 10) -> 0
        score = finder._calculate_age_score(2020, 2005)
        assert score == 0.0

    def test_calculate_similarity_full(self):
        """Test complete similarity calculation."""
        finder = SimilarApartmentFinder()

        target = {
            "id": 1,
            "latitude": 37.5172,
            "longitude": 127.0473,
            "avg_area": 84.95,
            "total_units": 500,
            "built_year": 2020,
        }
        candidate = {
            "id": 2,
            "latitude": 37.5200,
            "longitude": 127.0500,
            "avg_area": 84.95,
            "total_units": 500,
            "built_year": 2020,
        }

        prices = [("2024-01", 100), ("2024-02", 110), ("2024-03", 120)]

        score = finder.calculate_similarity(
            target, candidate,
            prices, prices,
        )

        assert isinstance(score, SimilarityScore)
        assert score.apartment_id == 1
        assert score.similar_apartment_id == 2
        assert 80 < score.total_score <= 100  # Should be very similar

    def test_find_similar_apartments(self):
        """Test finding similar apartments."""
        finder = SimilarApartmentFinder()

        target = {
            "id": 1,
            "latitude": 37.5172,
            "longitude": 127.0473,
            "avg_area": 84.95,
            "total_units": 500,
            "built_year": 2020,
        }

        candidates = [
            {"id": 2, "latitude": 37.518, "longitude": 127.048,
             "avg_area": 84.95, "total_units": 500, "built_year": 2020},
            {"id": 3, "latitude": 37.600, "longitude": 127.100,
             "avg_area": 60.0, "total_units": 100, "built_year": 2000},
        ]

        prices = [("2024-01", 100), ("2024-02", 110), ("2024-03", 120)]
        candidates_prices = {2: prices, 3: prices}

        results = finder.find_similar_apartments(
            target, candidates, prices, candidates_prices,
            min_score=0,  # Low threshold to get all results
        )

        assert len(results) >= 1
        # First result should be the most similar
        assert results[0].similar_apartment_id == 2


class TestComparisonAnalyzer:
    """Tests for ComparisonAnalyzer."""

    def test_area_to_pyeong(self):
        """Test area conversion to pyeong."""
        analyzer = ComparisonAnalyzer()
        # 84.95 m² ≈ 25.7 평
        pyeong = analyzer.area_to_pyeong(84.95)
        assert 25.5 < pyeong < 26.0

    def test_price_per_pyeong(self):
        """Test price per pyeong calculation."""
        analyzer = ComparisonAnalyzer()
        # 15억 (150000만원) / 25.7평 ≈ 5836만원/평
        pp = analyzer.calculate_price_per_pyeong(150000, 84.95)
        assert 5800 < pp < 5900

    def test_get_recent_price(self):
        """Test getting recent price average."""
        analyzer = ComparisonAnalyzer()

        prices = [
            ("2024-01", 5000),
            ("2024-02", 5100),
            ("2024-03", 5200),
            ("2024-04", 5300),
        ]

        avg = analyzer.get_recent_price_per_pyeong(prices, months=3)
        # Average of last 3: (5200 + 5300 + 5100) / 3 = 5200
        # But sorted by date desc: 5300, 5200, 5100 -> avg = 5200
        assert 5100 < avg < 5300

    def test_generate_report(self):
        """Test generating comparison report."""
        analyzer = ComparisonAnalyzer(undervalued_threshold=-5.0)

        listing = {
            "id": 1,
            "apartment_id": 100,
            "apartment_name": "테스트아파트",
            "price": 140000,  # 14억
            "area": 84.95,
        }

        similar_apts = [
            {"id": 2, "name": "비교아파트1", "similarity_score": 85.0},
            {"id": 3, "name": "비교아파트2", "similarity_score": 80.0},
        ]

        # Similar apartments have higher prices
        similar_prices = {
            2: [("2024-01", 5800), ("2024-02", 5900), ("2024-03", 6000)],
            3: [("2024-01", 5700), ("2024-02", 5800), ("2024-03", 5900)],
        }

        report = analyzer.generate_report(listing, similar_apts, similar_prices)

        assert isinstance(report, ComparisonReport)
        assert report.listing_id == 1
        assert report.listing_price == 140000
        assert len(report.comparison_results) == 2
        # Target is cheaper than similar -> negative gap -> undervalued
        assert report.avg_gap_percent < 0

    def test_find_undervalued_listings(self):
        """Test finding undervalued listings."""
        analyzer = ComparisonAnalyzer(undervalued_threshold=-5.0)

        listings = [
            {"id": 1, "price": 140000, "area": 84.95},  # Undervalued
            {"id": 2, "price": 180000, "area": 84.95},  # Overvalued
        ]

        # Similar data: listing 1 is cheaper, listing 2 is expensive
        similar_data = {
            1: (
                [{"id": 10, "name": "Similar1"}],
                {10: [("2024-01", 6000), ("2024-02", 6100), ("2024-03", 6200)]},
            ),
            2: (
                [{"id": 20, "name": "Similar2"}],
                {20: [("2024-01", 5500), ("2024-02", 5600), ("2024-03", 5700)]},
            ),
        }

        undervalued = analyzer.find_undervalued_listings(listings, similar_data)

        # Only listing 1 should be undervalued
        assert len(undervalued) == 1
        assert undervalued[0].listing_id == 1


class TestRecommendationEngine:
    """Tests for RecommendationEngine."""

    def test_price_score_big_discount(self):
        """Test price score for big discount."""
        engine = RecommendationEngine()
        score = engine.calculate_price_score(-20.0)  # 20% discount
        assert score == 100.0

    def test_price_score_big_premium(self):
        """Test price score for big premium."""
        engine = RecommendationEngine()
        score = engine.calculate_price_score(20.0)  # 20% premium
        assert score == 0.0

    def test_price_score_neutral(self):
        """Test price score for average price."""
        engine = RecommendationEngine()
        score = engine.calculate_price_score(0.0)  # Same price
        assert score == 50.0

    def test_trend_score_rising(self):
        """Test trend score for rising market."""
        engine = RecommendationEngine()
        score = engine.calculate_trend_score([5.0, 3.0, 4.0])  # ~4% avg increase
        assert score > 50  # Should be above neutral

    def test_trend_score_falling(self):
        """Test trend score for falling market."""
        engine = RecommendationEngine()
        score = engine.calculate_trend_score([-5.0, -3.0, -4.0])  # ~4% avg decrease
        assert score < 50  # Should be below neutral

    def test_liquidity_score_high_volume(self):
        """Test liquidity score for high volume."""
        engine = RecommendationEngine()
        score = engine.calculate_liquidity_score(10, area_avg_transactions=5)
        assert score > 75  # High liquidity

    def test_liquidity_score_low_volume(self):
        """Test liquidity score for low volume."""
        engine = RecommendationEngine()
        score = engine.calculate_liquidity_score(1, area_avg_transactions=5)
        assert score < 50  # Low liquidity

    def test_quality_score_new_large(self):
        """Test quality score for new large complex."""
        engine = RecommendationEngine()
        score = engine.calculate_quality_score(
            built_year=2022,  # Very new
            total_units=1000,  # Large
            has_amenities=True,
        )
        assert score >= 90  # High quality

    def test_quality_score_old_small(self):
        """Test quality score for old small complex."""
        engine = RecommendationEngine()
        score = engine.calculate_quality_score(
            built_year=1990,  # Old
            total_units=50,  # Small
            has_amenities=False,
        )
        assert score <= 60  # Lower quality

    def test_calculate_recommendation(self):
        """Test complete recommendation calculation."""
        engine = RecommendationEngine()

        listing = {
            "id": 1,
            "apartment_id": 100,
            "apartment_name": "테스트아파트",
            "built_year": 2020,
            "total_units": 500,
        }

        rec = engine.calculate_recommendation(
            listing=listing,
            discount_percent=-10.0,  # 10% below similar
            price_changes=[2.0, 3.0, 2.5],  # Rising market
            monthly_transactions=8,
            area_avg_transactions=5,
        )

        assert isinstance(rec, RecommendationScore)
        assert rec.listing_id == 1
        assert rec.total_score > 60  # Should be decent score
        assert rec.discount_percent == -10.0

    def test_rank_listings(self):
        """Test ranking listings by score."""
        engine = RecommendationEngine()

        recs = [
            RecommendationScore(
                listing_id=1, apartment_id=1, apartment_name="A",
                price_score=80, trend_score=70, liquidity_score=60, quality_score=70,
                total_score=70,
            ),
            RecommendationScore(
                listing_id=2, apartment_id=2, apartment_name="B",
                price_score=90, trend_score=80, liquidity_score=70, quality_score=80,
                total_score=80,
            ),
            RecommendationScore(
                listing_id=3, apartment_id=3, apartment_name="C",
                price_score=70, trend_score=60, liquidity_score=50, quality_score=60,
                total_score=60,
            ),
        ]

        ranked = engine.rank_listings(recs)

        assert ranked[0].listing_id == 2  # Highest score
        assert ranked[0].rank == 1
        assert ranked[1].listing_id == 1
        assert ranked[1].rank == 2
        assert ranked[2].listing_id == 3
        assert ranked[2].rank == 3

    def test_get_top_recommendations(self):
        """Test getting top recommendations."""
        engine = RecommendationEngine()

        recs = [
            RecommendationScore(
                listing_id=i, apartment_id=i, apartment_name=f"Apt{i}",
                price_score=50+i*5, trend_score=50+i*5,
                liquidity_score=50+i*5, quality_score=50+i*5,
                total_score=50+i*5,
            )
            for i in range(1, 11)
        ]

        top = engine.get_top_recommendations(recs, top_n=5, min_score=70)

        # Should only get listings with score >= 70
        assert all(r.total_score >= 70 for r in top)
        assert len(top) <= 5
