"""Unified matching service combining name, address, and area matchers.

Provides a single interface for apartment and listing matching with:
- Configurable weights for each matching component
- Logging support for match quality monitoring
- Integration with database for candidate lookup
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Any
from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.matching.name_matcher import NameMatcher, NameMatchResult
from app.matching.address_matcher import AddressMatcher, AddressMatchResult
from app.matching.area_matcher import AreaMatcher, AreaMatchResult
from app.models.apartment import Apartment


class MatchConfidence(Enum):
    """Confidence level for matches."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


@dataclass
class MatchResult:
    """Combined result from all matching components."""
    apartment_id: Optional[int]
    source_name: str
    source_address: Optional[str]
    source_area: Optional[float]

    # Individual scores
    name_score: float = 0.0
    address_score: float = 0.0
    area_score: float = 0.0

    # Combined score
    total_score: float = 0.0
    confidence: MatchConfidence = MatchConfidence.NONE

    # Match details
    name_result: Optional[NameMatchResult] = None
    address_result: Optional[AddressMatchResult] = None
    area_result: Optional[AreaMatchResult] = None

    # Target apartment info
    target_name: Optional[str] = None
    target_address: Optional[str] = None
    target_dong_code: Optional[str] = None

    # Metadata
    matched_at: datetime = field(default_factory=datetime.utcnow)
    match_method: str = "combined"


@dataclass
class MatchingConfig:
    """Configuration for matching weights and thresholds."""
    # Component weights (must sum to 1.0)
    name_weight: float = 0.5
    address_weight: float = 0.3
    area_weight: float = 0.2

    # Thresholds
    high_confidence_threshold: float = 0.85
    medium_confidence_threshold: float = 0.7
    min_match_threshold: float = 0.6

    # Name matching
    name_min_score: float = 0.6

    # Area matching
    allow_adjacent_groups: bool = True

    def __post_init__(self):
        """Validate configuration."""
        total_weight = self.name_weight + self.address_weight + self.area_weight
        if abs(total_weight - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {total_weight}")


class MatchingService:
    """Unified matching service for apartments and listings."""

    def __init__(
        self,
        config: Optional[MatchingConfig] = None,
        name_matcher: Optional[NameMatcher] = None,
        address_matcher: Optional[AddressMatcher] = None,
        area_matcher: Optional[AreaMatcher] = None,
    ):
        """Initialize the matching service.

        Args:
            config: Matching configuration
            name_matcher: Custom name matcher instance
            address_matcher: Custom address matcher instance
            area_matcher: Custom area matcher instance
        """
        self.config = config or MatchingConfig()
        self.name_matcher = name_matcher or NameMatcher()
        self.address_matcher = address_matcher or AddressMatcher()
        self.area_matcher = area_matcher or AreaMatcher()

    def _determine_confidence(self, score: float) -> MatchConfidence:
        """Determine confidence level from score.

        Args:
            score: Combined match score

        Returns:
            MatchConfidence level
        """
        if score >= self.config.high_confidence_threshold:
            return MatchConfidence.HIGH
        elif score >= self.config.medium_confidence_threshold:
            return MatchConfidence.MEDIUM
        elif score >= self.config.min_match_threshold:
            return MatchConfidence.LOW
        return MatchConfidence.NONE

    def match(
        self,
        source_name: str,
        target_name: str,
        source_address: Optional[str] = None,
        target_address: Optional[str] = None,
        source_dong_code: Optional[str] = None,
        target_dong_code: Optional[str] = None,
        source_area: Optional[float] = None,
        target_area: Optional[float] = None,
        target_apartment_id: Optional[int] = None,
    ) -> MatchResult:
        """Match source data against a target apartment.

        Args:
            source_name: Source apartment name
            target_name: Target apartment name
            source_address: Source address (optional)
            target_address: Target address (optional)
            source_dong_code: Source dong_code (optional)
            target_dong_code: Target dong_code (optional)
            source_area: Source area in m² (optional)
            target_area: Target area in m² (optional)
            target_apartment_id: Target apartment ID

        Returns:
            MatchResult with combined scores
        """
        # Name matching (required)
        name_result = self.name_matcher.match(source_name, target_name)
        name_score = name_result.similarity_score

        # Address matching (optional but improves accuracy)
        address_result = None
        address_score = 0.0
        if source_address or target_address or source_dong_code or target_dong_code:
            address_result = self.address_matcher.match(
                source_address or "",
                target_address or "",
                source_dong_code,
                target_dong_code,
            )
            address_score = address_result.similarity_score

        # Area matching (optional)
        area_result = None
        area_score = 0.0
        if source_area is not None and target_area is not None:
            area_result = self.area_matcher.match(source_area, target_area)
            area_score = self.area_matcher.calculate_similarity_score(
                source_area, target_area
            )

        # Calculate weighted score
        # Adjust weights based on available data
        available_weight = self.config.name_weight  # Name is always available

        if address_result:
            available_weight += self.config.address_weight
        if area_result:
            available_weight += self.config.area_weight

        # Normalize weights
        name_weight_adj = self.config.name_weight / available_weight
        address_weight_adj = (
            self.config.address_weight / available_weight if address_result else 0
        )
        area_weight_adj = (
            self.config.area_weight / available_weight if area_result else 0
        )

        total_score = (
            name_score * name_weight_adj
            + address_score * address_weight_adj
            + area_score * area_weight_adj
        )

        confidence = self._determine_confidence(total_score)

        return MatchResult(
            apartment_id=target_apartment_id,
            source_name=source_name,
            source_address=source_address,
            source_area=source_area,
            name_score=round(name_score, 3),
            address_score=round(address_score, 3),
            area_score=round(area_score, 3),
            total_score=round(total_score, 3),
            confidence=confidence,
            name_result=name_result,
            address_result=address_result,
            area_result=area_result,
            target_name=target_name,
            target_address=target_address,
            target_dong_code=target_dong_code,
            match_method="combined",
        )

    async def find_best_match(
        self,
        db: AsyncSession,
        source_name: str,
        source_address: Optional[str] = None,
        source_dong_code: Optional[str] = None,
        source_area: Optional[float] = None,
        limit_candidates: int = 100,
    ) -> Optional[MatchResult]:
        """Find the best matching apartment from the database.

        Args:
            db: Database session
            source_name: Source apartment name
            source_address: Source address (optional)
            source_dong_code: Source dong_code for filtering (optional)
            source_area: Source area in m² (optional)
            limit_candidates: Maximum candidates to consider

        Returns:
            Best MatchResult or None if no match found
        """
        # Build query for candidates
        query = select(Apartment)

        # Filter by dong_code if available (more efficient)
        if source_dong_code:
            # Match same gu (first 5 digits)
            query = query.where(
                Apartment.dong_code.like(f"{source_dong_code[:5]}%")
            )

        query = query.limit(limit_candidates)

        result = await db.execute(query)
        candidates = result.scalars().all()

        if not candidates:
            return None

        best_match: Optional[MatchResult] = None
        best_score = 0.0

        for apartment in candidates:
            match_result = self.match(
                source_name=source_name,
                target_name=apartment.name,
                source_address=source_address,
                target_address=apartment.address,
                source_dong_code=source_dong_code,
                target_dong_code=apartment.dong_code,
                source_area=source_area,
                target_area=None,  # We don't have listing area in apartment table
                target_apartment_id=apartment.id,
            )

            if match_result.total_score > best_score:
                best_score = match_result.total_score
                best_match = match_result

        # Check minimum threshold
        if best_match and best_match.total_score >= self.config.min_match_threshold:
            return best_match

        return None

    async def find_matches(
        self,
        db: AsyncSession,
        source_name: str,
        source_address: Optional[str] = None,
        source_dong_code: Optional[str] = None,
        source_area: Optional[float] = None,
        min_score: Optional[float] = None,
        limit: int = 10,
    ) -> List[MatchResult]:
        """Find all matching apartments above threshold.

        Args:
            db: Database session
            source_name: Source apartment name
            source_address: Source address (optional)
            source_dong_code: Source dong_code for filtering (optional)
            source_area: Source area in m² (optional)
            min_score: Minimum score threshold
            limit: Maximum results to return

        Returns:
            List of MatchResults sorted by score descending
        """
        if min_score is None:
            min_score = self.config.min_match_threshold

        # Build query for candidates
        query = select(Apartment)

        if source_dong_code:
            query = query.where(
                Apartment.dong_code.like(f"{source_dong_code[:5]}%")
            )

        # Get more candidates than limit for filtering
        query = query.limit(limit * 5)

        result = await db.execute(query)
        candidates = result.scalars().all()

        matches = []

        for apartment in candidates:
            match_result = self.match(
                source_name=source_name,
                target_name=apartment.name,
                source_address=source_address,
                target_address=apartment.address,
                source_dong_code=source_dong_code,
                target_dong_code=apartment.dong_code,
                source_area=source_area,
                target_area=None,
                target_apartment_id=apartment.id,
            )

            if match_result.total_score >= min_score:
                matches.append(match_result)

        # Sort by score and limit
        matches.sort(key=lambda x: x.total_score, reverse=True)
        return matches[:limit]

    def validate_match(
        self,
        match_result: MatchResult,
    ) -> Tuple[bool, List[str]]:
        """Validate a match result and return issues.

        Args:
            match_result: Match result to validate

        Returns:
            Tuple of (is_valid, list of issues)
        """
        issues = []

        # Check name score
        if match_result.name_score < self.config.name_min_score:
            issues.append(
                f"Name score {match_result.name_score:.2f} below minimum {self.config.name_min_score}"
            )

        # Check for phase mismatch
        if match_result.name_result and match_result.target_name:
            if not self.name_matcher.check_phase_compatibility(
                match_result.source_name,
                match_result.target_name,
            ):
                issues.append("Phase number mismatch (e.g., 1차 vs 2차)")

        # Check area compatibility
        if match_result.area_result and not match_result.area_result.is_match:
            issues.append(
                f"Area mismatch: {match_result.area_result.difference_m2}m² difference"
            )

        # Check address compatibility
        if match_result.address_result:
            if match_result.address_result.match_level == "none":
                issues.append("Address location mismatch")

        is_valid = len(issues) == 0 and match_result.confidence != MatchConfidence.NONE

        return (is_valid, issues)

    def to_log_dict(self, match_result: MatchResult) -> Dict[str, Any]:
        """Convert match result to a dictionary for logging.

        Args:
            match_result: Match result to convert

        Returns:
            Dictionary suitable for database logging
        """
        return {
            "apartment_id": match_result.apartment_id,
            "source_name": match_result.source_name,
            "target_name": match_result.target_name,
            "source_address": match_result.source_address,
            "target_address": match_result.target_address,
            "source_area": match_result.source_area,
            "name_score": match_result.name_score,
            "address_score": match_result.address_score,
            "area_score": match_result.area_score,
            "total_score": match_result.total_score,
            "confidence": match_result.confidence.value,
            "match_method": match_result.match_method,
            "matched_at": match_result.matched_at.isoformat(),
        }
