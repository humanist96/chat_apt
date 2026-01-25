"""Tests for the price adjustment module.

Tests cover:
- FloorAdjuster: Floor-based price normalization
- TimeWeightedPriceCalculator: Time-weighted reference prices
- ReferenceQualityValidator: Reference quality validation
"""
import pytest
from datetime import date, timedelta

from app.analysis.price_adjustment import (
    FloorAdjuster,
    FloorCategory,
    FloorAdjustedPrice,
    TimeWeightedPriceCalculator,
    TransactionData,
    WeightedReferencePrice,
    ReferenceQualityValidator,
    ReferenceQuality,
)


class TestFloorAdjuster:
    """Tests for FloorAdjuster class."""

    @pytest.fixture
    def adjuster(self):
        return FloorAdjuster()

    def test_get_category_ground(self, adjuster):
        """Floor 1 should be categorized as ground."""
        assert adjuster.get_category(1) == FloorCategory.GROUND

    def test_get_category_low(self, adjuster):
        """Floors 2-4 should be categorized as low."""
        assert adjuster.get_category(2) == FloorCategory.LOW
        assert adjuster.get_category(4) == FloorCategory.LOW

    def test_get_category_mid(self, adjuster):
        """Floors 5-9 should be categorized as mid."""
        assert adjuster.get_category(5) == FloorCategory.MID
        assert adjuster.get_category(9) == FloorCategory.MID

    def test_get_category_royal(self, adjuster):
        """Floors 10-15 should be categorized as royal."""
        assert adjuster.get_category(10) == FloorCategory.ROYAL
        assert adjuster.get_category(15) == FloorCategory.ROYAL

    def test_get_category_high(self, adjuster):
        """Floors 16+ should be categorized as high."""
        assert adjuster.get_category(16) == FloorCategory.HIGH
        assert adjuster.get_category(30) == FloorCategory.HIGH

    def test_get_category_invalid(self, adjuster):
        """Invalid floors should default to mid."""
        assert adjuster.get_category(0) == FloorCategory.MID
        assert adjuster.get_category(-1) == FloorCategory.MID

    def test_get_premium_factor(self, adjuster):
        """Premium factors should match expected values."""
        assert adjuster.get_premium_factor(1) == 0.95  # Ground
        assert adjuster.get_premium_factor(3) == 0.97  # Low
        assert adjuster.get_premium_factor(7) == 1.00  # Mid
        assert adjuster.get_premium_factor(12) == 1.05  # Royal
        assert adjuster.get_premium_factor(20) == 1.03  # High

    def test_normalize_price_ground(self, adjuster):
        """Ground floor price should be adjusted up."""
        result = adjuster.normalize_price(10000, 1)
        assert isinstance(result, FloorAdjustedPrice)
        assert result.original_price == 10000
        assert result.original_floor == 1
        # Ground floor (0.95) → Mid floor (1.00)
        assert result.adjusted_price > 10000
        assert result.category == FloorCategory.GROUND

    def test_normalize_price_royal(self, adjuster):
        """Royal floor price should be adjusted down."""
        result = adjuster.normalize_price(10000, 12)
        # Royal floor (1.05) → Mid floor (1.00)
        assert result.adjusted_price < 10000
        assert result.category == FloorCategory.ROYAL

    def test_normalize_price_mid(self, adjuster):
        """Mid floor price should remain unchanged."""
        result = adjuster.normalize_price(10000, 7)
        assert result.adjusted_price == 10000
        assert result.adjustment_factor == 1.0

    def test_denormalize_price(self, adjuster):
        """Denormalization should reverse normalization."""
        # Normalize a royal floor price
        normalized = adjuster.normalize_price(10500, 12)

        # Denormalize back to royal floor
        denormalized = adjuster.denormalize_price(
            normalized.adjusted_price, 12
        )

        # Should be close to original
        assert abs(denormalized - 10500) < 100


class TestTimeWeightedPriceCalculator:
    """Tests for TimeWeightedPriceCalculator class."""

    @pytest.fixture
    def calculator(self):
        return TimeWeightedPriceCalculator(decay_factor=0.85, max_months=24)

    def test_calculate_age_weight_current(self, calculator):
        """Current month should have weight 1.0."""
        today = date.today()
        weight = calculator.calculate_age_weight(today, today)
        assert weight == 1.0

    def test_calculate_age_weight_6_months(self, calculator):
        """6 months old should have ~38% weight (0.85^6)."""
        today = date.today()
        six_months_ago = today - timedelta(days=180)
        weight = calculator.calculate_age_weight(six_months_ago, today)
        # 0.85^6 ≈ 0.377
        assert 0.3 < weight < 0.5

    def test_calculate_age_weight_12_months(self, calculator):
        """12 months old should have ~20% weight."""
        today = date.today()
        twelve_months_ago = today - timedelta(days=365)
        weight = calculator.calculate_age_weight(twelve_months_ago, today)
        assert 0.1 < weight < 0.3

    def test_calculate_age_weight_beyond_max(self, calculator):
        """Beyond max_months should have 0 weight."""
        today = date.today()
        three_years_ago = today - timedelta(days=1095)
        weight = calculator.calculate_age_weight(three_years_ago, today)
        assert weight == 0.0

    def test_calculate_weighted_reference_empty(self, calculator):
        """Empty transactions should return 0."""
        result = calculator.calculate_weighted_reference([])
        assert result.reference_price == 0
        assert result.transaction_count == 0

    def test_calculate_weighted_reference_single(self, calculator):
        """Single transaction should return its price."""
        today = date.today()
        transactions = [
            TransactionData(deal_amount=10000, deal_date=today)
        ]
        result = calculator.calculate_weighted_reference(transactions)
        assert result.reference_price == 10000
        assert result.transaction_count == 1

    def test_calculate_weighted_reference_recent_weighted_more(self, calculator):
        """Recent transactions should be weighted more."""
        today = date.today()
        six_months_ago = today - timedelta(days=180)

        transactions = [
            TransactionData(deal_amount=12000, deal_date=today),
            TransactionData(deal_amount=10000, deal_date=six_months_ago),
        ]

        result = calculator.calculate_weighted_reference(transactions)

        # Weighted average should be closer to 12000 (recent) than 10000 (old)
        assert result.weighted_avg_price > 11000

    def test_calculate_weighted_reference_with_floor_adjustment(self):
        """Floor adjustment should be applied when enabled."""
        floor_adjuster = FloorAdjuster()
        calculator = TimeWeightedPriceCalculator(
            floor_adjuster=floor_adjuster
        )

        today = date.today()
        transactions = [
            TransactionData(deal_amount=10000, deal_date=today, floor=12),  # Royal
        ]

        result_with_floor = calculator.calculate_weighted_reference(
            transactions, normalize_floor=True
        )
        result_without_floor = calculator.calculate_weighted_reference(
            transactions, normalize_floor=False
        )

        # With floor normalization, royal floor price should be lower
        assert result_with_floor.reference_price < result_without_floor.reference_price


class TestReferenceQualityValidator:
    """Tests for ReferenceQualityValidator class."""

    @pytest.fixture
    def validator(self):
        return ReferenceQualityValidator()

    def test_validate_empty(self, validator):
        """Empty transactions should be insufficient."""
        result = validator.validate([])
        assert result.quality == ReferenceQuality.INSUFFICIENT
        assert result.transaction_count == 0

    def test_validate_high_quality(self, validator):
        """High quality criteria should be met."""
        today = date.today()
        transactions = [
            TransactionData(deal_amount=10000, deal_date=today),
            TransactionData(deal_amount=10500, deal_date=today - timedelta(days=90)),
            TransactionData(deal_amount=9800, deal_date=today - timedelta(days=180)),
            TransactionData(deal_amount=9500, deal_date=today - timedelta(days=365)),
        ]

        result = validator.validate(transactions)
        assert result.quality == ReferenceQuality.HIGH
        assert result.transaction_count == 4
        assert result.recent_transaction_count >= 1

    def test_validate_medium_quality(self, validator):
        """Medium quality with fewer transactions."""
        today = date.today()
        transactions = [
            TransactionData(deal_amount=10000, deal_date=today - timedelta(days=90)),
            TransactionData(deal_amount=10500, deal_date=today - timedelta(days=180)),
        ]

        result = validator.validate(transactions)
        assert result.quality == ReferenceQuality.MEDIUM
        assert len(result.issues) > 0

    def test_validate_low_quality(self, validator):
        """Low quality with old single transaction."""
        today = date.today()
        transactions = [
            TransactionData(deal_amount=10000, deal_date=today - timedelta(days=400)),
        ]

        result = validator.validate(transactions)
        assert result.quality == ReferenceQuality.LOW
        assert result.transaction_count == 1

    def test_validate_months_covered(self, validator):
        """months_covered should be calculated correctly."""
        today = date.today()
        old_date = today - timedelta(days=365)
        transactions = [
            TransactionData(deal_amount=10000, deal_date=today),
            TransactionData(deal_amount=9500, deal_date=old_date),
        ]

        result = validator.validate(transactions, reference_date=today)
        assert result.months_covered >= 11  # ~12 months


class TestPriceAdjustmentIntegration:
    """Integration tests for price adjustment components."""

    def test_fire_sale_detection_scenario(self):
        """Test realistic fire sale detection with adjustments."""
        floor_adjuster = FloorAdjuster()
        calculator = TimeWeightedPriceCalculator(floor_adjuster=floor_adjuster)
        validator = ReferenceQualityValidator()

        today = date.today()

        # Historical transactions (all-time high was 15000 on royal floor)
        transactions = [
            TransactionData(deal_amount=15000, deal_date=today - timedelta(days=180), floor=12),
            TransactionData(deal_amount=14500, deal_date=today - timedelta(days=270), floor=10),
            TransactionData(deal_amount=14000, deal_date=today - timedelta(days=365), floor=8),
        ]

        # Validate quality
        quality = validator.validate(transactions)
        assert quality.quality in (ReferenceQuality.HIGH, ReferenceQuality.MEDIUM)

        # Calculate weighted reference
        reference = calculator.calculate_weighted_reference(
            transactions, normalize_floor=True
        )

        # Current listing: 12000 on low floor
        listing_price = 12000
        listing_floor = 3

        # Normalize listing price
        normalized_listing = floor_adjuster.normalize_price(listing_price, listing_floor)

        # Calculate discount
        if reference.reference_price > 0:
            discount_rate = (
                (reference.reference_price - normalized_listing.adjusted_price)
                / reference.reference_price
            ) * 100
        else:
            discount_rate = 0

        # Should show significant discount due to:
        # 1. Lower price than reference
        # 2. Low floor means actual value is even lower
        assert discount_rate > 10  # At least 10% discount

    def test_comparison_with_floor_normalization(self):
        """Test that floor normalization improves comparison accuracy."""
        floor_adjuster = FloorAdjuster()

        # Two listings: same price, different floors
        royal_floor = floor_adjuster.normalize_price(15000, 12)
        ground_floor = floor_adjuster.normalize_price(15000, 1)

        # Ground floor should have higher normalized price
        # (since we're adjusting to mid-floor equivalent)
        assert ground_floor.adjusted_price > royal_floor.adjusted_price

        # The difference should reflect the floor premium gap
        # Royal: 1.05, Ground: 0.95 → difference ~10%
        ratio = ground_floor.adjusted_price / royal_floor.adjusted_price
        assert 1.08 < ratio < 1.12
