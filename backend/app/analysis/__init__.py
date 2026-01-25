"""Analysis module for property recommendations."""
from app.analysis.similarity import SimilarApartmentFinder, SimilarityScore
from app.analysis.comparison import ComparisonAnalyzer, ComparisonReport
from app.analysis.recommendation import RecommendationEngine, RecommendationScore
from app.analysis.fire_sale import FireSaleDetector, FireSaleAnalysis
from app.analysis.price_adjustment import (
    FloorAdjuster,
    FloorAdjustedPrice,
    FloorCategory,
    TimeWeightedPriceCalculator,
    WeightedReferencePrice,
    TransactionData,
    ReferenceQualityValidator,
    ReferenceQuality,
    ReferenceQualityResult,
)

__all__ = [
    "SimilarApartmentFinder",
    "SimilarityScore",
    "ComparisonAnalyzer",
    "ComparisonReport",
    "RecommendationEngine",
    "RecommendationScore",
    "FireSaleDetector",
    "FireSaleAnalysis",
    "FloorAdjuster",
    "FloorAdjustedPrice",
    "FloorCategory",
    "TimeWeightedPriceCalculator",
    "WeightedReferencePrice",
    "TransactionData",
    "ReferenceQualityValidator",
    "ReferenceQuality",
    "ReferenceQualityResult",
]
