"""Matching module for apartment and listing matching.

This module provides improved matching algorithms for:
- Apartment name normalization and fuzzy matching
- Address-based matching with dong_code support
- Area group-based matching for Korean apartment sizes
"""
from app.matching.name_matcher import NameMatcher
from app.matching.address_matcher import AddressMatcher
from app.matching.area_matcher import AreaMatcher
from app.matching.service import MatchingService, MatchResult

__all__ = [
    "NameMatcher",
    "AddressMatcher",
    "AreaMatcher",
    "MatchingService",
    "MatchResult",
]
