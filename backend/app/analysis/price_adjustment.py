"""Price adjustment utilities for fire sale detection and comparison analysis.

This module provides:
- FloorAdjuster: Normalizes prices based on floor level
- TimeWeightedPriceCalculator: Calculates reference prices with time decay
- ReferenceQualityValidator: Validates reference price reliability
"""
from dataclasses import dataclass
from datetime import date
from typing import List, Optional
from enum import Enum


class FloorCategory(Enum):
    """Floor categories for price adjustment."""
    GROUND = "ground"      # 1층
    LOW = "low"            # 2-4층
    MID = "mid"            # 5-9층 (기준)
    ROYAL = "royal"        # 10-15층
    HIGH = "high"          # 16층 이상


@dataclass
class FloorAdjustment:
    """Floor adjustment configuration."""
    category: FloorCategory
    min_floor: int
    max_floor: Optional[int]  # None for unlimited
    premium_factor: float  # 1.0 = no adjustment, > 1.0 = premium


@dataclass
class FloorAdjustedPrice:
    """Result of floor-based price adjustment."""
    original_price: int
    original_floor: int
    adjusted_price: int  # Normalized to mid-floor
    category: FloorCategory
    adjustment_factor: float


class FloorAdjuster:
    """Adjusts prices based on floor level.

    Korean apartments typically have floor-based price premiums:
    - 1층 (ground): -5% (privacy concerns, noise)
    - 2-4층 (low): -3%
    - 5-9층 (mid): 0% (reference)
    - 10-15층 (royal): +5% (best views, less dust)
    - 16층+ (high): +3% (very high, some view concerns)
    """

    DEFAULT_ADJUSTMENTS = [
        FloorAdjustment(FloorCategory.GROUND, 1, 1, 0.95),
        FloorAdjustment(FloorCategory.LOW, 2, 4, 0.97),
        FloorAdjustment(FloorCategory.MID, 5, 9, 1.00),
        FloorAdjustment(FloorCategory.ROYAL, 10, 15, 1.05),
        FloorAdjustment(FloorCategory.HIGH, 16, None, 1.03),
    ]

    def __init__(
        self,
        adjustments: Optional[List[FloorAdjustment]] = None,
        reference_category: FloorCategory = FloorCategory.MID,
    ):
        """Initialize the floor adjuster.

        Args:
            adjustments: Custom floor adjustments, or use defaults
            reference_category: Category to normalize prices to
        """
        self.adjustments = adjustments or self.DEFAULT_ADJUSTMENTS
        self.reference_category = reference_category
        self._adjustment_map = {adj.category: adj for adj in self.adjustments}

    def get_category(self, floor: int) -> FloorCategory:
        """Determine floor category.

        Args:
            floor: Floor number

        Returns:
            FloorCategory for the given floor
        """
        if floor is None or floor <= 0:
            return FloorCategory.MID  # Default for unknown

        for adj in self.adjustments:
            if adj.min_floor <= floor:
                if adj.max_floor is None or floor <= adj.max_floor:
                    return adj.category

        return FloorCategory.HIGH

    def get_premium_factor(self, floor: int) -> float:
        """Get premium factor for a floor.

        Args:
            floor: Floor number

        Returns:
            Premium factor (1.0 = no premium)
        """
        category = self.get_category(floor)
        return self._adjustment_map[category].premium_factor

    def normalize_price(
        self,
        price: int,
        floor: int,
    ) -> FloorAdjustedPrice:
        """Normalize a price to mid-floor equivalent.

        Args:
            price: Original price
            floor: Floor number

        Returns:
            FloorAdjustedPrice with normalized price
        """
        category = self.get_category(floor)
        premium = self._adjustment_map[category].premium_factor
        reference_premium = self._adjustment_map[self.reference_category].premium_factor

        # Adjust: if original has +5% premium, divide by 1.05 to get reference
        adjustment_factor = premium / reference_premium
        adjusted_price = int(price / adjustment_factor)

        return FloorAdjustedPrice(
            original_price=price,
            original_floor=floor,
            adjusted_price=adjusted_price,
            category=category,
            adjustment_factor=round(adjustment_factor, 3),
        )

    def denormalize_price(
        self,
        normalized_price: int,
        target_floor: int,
    ) -> int:
        """Convert a normalized price to target floor price.

        Args:
            normalized_price: Price normalized to reference floor
            target_floor: Target floor

        Returns:
            Expected price at target floor
        """
        target_premium = self.get_premium_factor(target_floor)
        reference_premium = self._adjustment_map[self.reference_category].premium_factor
        adjustment = target_premium / reference_premium
        return int(normalized_price * adjustment)


@dataclass
class TransactionData:
    """Transaction data for price calculation."""
    deal_amount: int  # 거래가 (만원)
    deal_date: date
    floor: Optional[int] = None
    area: Optional[float] = None


@dataclass
class WeightedReferencePrice:
    """Result of time-weighted price calculation."""
    reference_price: int
    weighted_avg_price: int
    transaction_count: int
    oldest_date: Optional[date]
    newest_date: Optional[date]
    effective_weight: float  # Total weight used


class TimeWeightedPriceCalculator:
    """Calculates reference prices with time-based weighting.

    More recent transactions receive higher weights:
    - Month 0 (current): 100%
    - Month 6: ~50%
    - Month 12: ~20%

    Uses exponential decay for smooth weighting.
    """

    def __init__(
        self,
        decay_factor: float = 0.85,
        max_months: int = 24,
        floor_adjuster: Optional[FloorAdjuster] = None,
    ):
        """Initialize the calculator.

        Args:
            decay_factor: Monthly decay factor (0.85 = 15% decay per month)
            max_months: Maximum months to consider
            floor_adjuster: Optional floor adjuster for price normalization
        """
        self.decay_factor = decay_factor
        self.max_months = max_months
        self.floor_adjuster = floor_adjuster

    def calculate_age_weight(
        self,
        transaction_date: date,
        reference_date: Optional[date] = None,
    ) -> float:
        """Calculate time-based weight for a transaction.

        Args:
            transaction_date: Date of the transaction
            reference_date: Reference date (defaults to today)

        Returns:
            Weight between 0.0 and 1.0
        """
        if reference_date is None:
            reference_date = date.today()

        # Calculate months difference
        months_diff = (
            (reference_date.year - transaction_date.year) * 12
            + (reference_date.month - transaction_date.month)
        )

        if months_diff < 0:
            months_diff = 0

        if months_diff > self.max_months:
            return 0.0

        # Exponential decay
        return self.decay_factor ** months_diff

    def calculate_weighted_reference(
        self,
        transactions: List[TransactionData],
        reference_date: Optional[date] = None,
        normalize_floor: bool = True,
    ) -> WeightedReferencePrice:
        """Calculate time-weighted reference price.

        Args:
            transactions: List of transaction data
            reference_date: Reference date for weighting
            normalize_floor: Whether to apply floor normalization

        Returns:
            WeightedReferencePrice with calculated values
        """
        if not transactions:
            return WeightedReferencePrice(
                reference_price=0,
                weighted_avg_price=0,
                transaction_count=0,
                oldest_date=None,
                newest_date=None,
                effective_weight=0.0,
            )

        if reference_date is None:
            reference_date = date.today()

        weighted_sum = 0.0
        total_weight = 0.0
        dates = []

        for tx in transactions:
            weight = self.calculate_age_weight(tx.deal_date, reference_date)

            if weight <= 0:
                continue

            # Get price (normalize by floor if requested)
            price = tx.deal_amount
            if normalize_floor and self.floor_adjuster and tx.floor:
                adjusted = self.floor_adjuster.normalize_price(price, tx.floor)
                price = adjusted.adjusted_price

            weighted_sum += price * weight
            total_weight += weight
            dates.append(tx.deal_date)

        if total_weight == 0:
            return WeightedReferencePrice(
                reference_price=0,
                weighted_avg_price=0,
                transaction_count=len(transactions),
                oldest_date=min(dates) if dates else None,
                newest_date=max(dates) if dates else None,
                effective_weight=0.0,
            )

        weighted_avg = int(weighted_sum / total_weight)

        return WeightedReferencePrice(
            reference_price=weighted_avg,
            weighted_avg_price=weighted_avg,
            transaction_count=len(transactions),
            oldest_date=min(dates) if dates else None,
            newest_date=max(dates) if dates else None,
            effective_weight=round(total_weight, 3),
        )


class ReferenceQuality(Enum):
    """Quality level of reference price."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INSUFFICIENT = "insufficient"


@dataclass
class ReferenceQualityResult:
    """Result of reference quality validation."""
    quality: ReferenceQuality
    transaction_count: int
    months_covered: int
    recent_transaction_count: int  # Within 6 months
    issues: List[str]


class ReferenceQualityValidator:
    """Validates the reliability of reference prices.

    High quality requires:
    - Minimum 3 transactions in the period
    - At least 1 transaction within 6 months
    - Coverage of at least 12 months

    Medium quality:
    - 2+ transactions
    - At least 1 transaction within 12 months

    Low quality:
    - 1+ transaction
    - Transaction within 24 months
    """

    def __init__(
        self,
        min_transactions_high: int = 3,
        min_transactions_medium: int = 2,
        min_transactions_low: int = 1,
        recent_months_high: int = 6,
        recent_months_medium: int = 12,
        coverage_months_high: int = 12,
    ):
        """Initialize the validator.

        Args:
            min_transactions_high: Minimum transactions for HIGH quality
            min_transactions_medium: Minimum transactions for MEDIUM quality
            min_transactions_low: Minimum transactions for LOW quality
            recent_months_high: Recent transaction required for HIGH
            recent_months_medium: Recent transaction required for MEDIUM
            coverage_months_high: Coverage months required for HIGH
        """
        self.min_transactions_high = min_transactions_high
        self.min_transactions_medium = min_transactions_medium
        self.min_transactions_low = min_transactions_low
        self.recent_months_high = recent_months_high
        self.recent_months_medium = recent_months_medium
        self.coverage_months_high = coverage_months_high

    def validate(
        self,
        transactions: List[TransactionData],
        reference_date: Optional[date] = None,
    ) -> ReferenceQualityResult:
        """Validate reference price quality.

        Args:
            transactions: List of transactions
            reference_date: Reference date

        Returns:
            ReferenceQualityResult with quality level and details
        """
        if reference_date is None:
            reference_date = date.today()

        issues = []
        tx_count = len(transactions)

        if tx_count == 0:
            return ReferenceQualityResult(
                quality=ReferenceQuality.INSUFFICIENT,
                transaction_count=0,
                months_covered=0,
                recent_transaction_count=0,
                issues=["No transactions found"],
            )

        # Calculate date ranges
        dates = [tx.deal_date for tx in transactions]
        oldest = min(dates)
        newest = max(dates)

        months_covered = (
            (reference_date.year - oldest.year) * 12
            + (reference_date.month - oldest.month)
        )

        months_since_newest = (
            (reference_date.year - newest.year) * 12
            + (reference_date.month - newest.month)
        )

        # Count recent transactions
        recent_count = sum(
            1 for tx in transactions
            if (reference_date.year - tx.deal_date.year) * 12
               + (reference_date.month - tx.deal_date.month)
               <= self.recent_months_high
        )

        # Determine quality
        if (
            tx_count >= self.min_transactions_high
            and months_since_newest <= self.recent_months_high
            and months_covered >= self.coverage_months_high
        ):
            quality = ReferenceQuality.HIGH
        elif (
            tx_count >= self.min_transactions_medium
            and months_since_newest <= self.recent_months_medium
        ):
            quality = ReferenceQuality.MEDIUM
            if tx_count < self.min_transactions_high:
                issues.append(f"Only {tx_count} transactions (need {self.min_transactions_high} for HIGH)")
            if months_since_newest > self.recent_months_high:
                issues.append(f"Most recent transaction is {months_since_newest} months old")
        elif tx_count >= self.min_transactions_low:
            quality = ReferenceQuality.LOW
            issues.append(f"Only {tx_count} transaction(s)")
            if months_since_newest > self.recent_months_medium:
                issues.append(f"Most recent transaction is {months_since_newest} months old")
        else:
            quality = ReferenceQuality.INSUFFICIENT
            issues.append("No valid transactions found")

        return ReferenceQualityResult(
            quality=quality,
            transaction_count=tx_count,
            months_covered=months_covered,
            recent_transaction_count=recent_count,
            issues=issues,
        )
