"""Name matching for Korean apartment names.

Handles Korean-specific naming conventions:
- Removes parenthetical content: "래미안(강남)" → "래미안"
- Removes suffixes: 아파트, 단지, 차, 동, 주상복합
- Handles numeric suffixes: "힐스테이트1차" → "힐스테이트"
- Normalizes whitespace and Korean jamo
"""
import re
import unicodedata
from difflib import SequenceMatcher
from dataclasses import dataclass
from typing import Optional, List, Tuple


@dataclass
class NameMatchResult:
    """Result of name matching operation."""
    original_name: str
    normalized_name: str
    target_name: str
    target_normalized: str
    similarity_score: float
    match_method: str  # 'exact', 'normalized', 'fuzzy'


class NameMatcher:
    """Korean apartment name matcher with normalization."""

    # Common suffixes to remove (order matters - longer first)
    SUFFIXES_TO_REMOVE = [
        "주상복합",
        "아파트",
        "오피스텔",
        "빌라",
        "타운",
        "단지",
        "차",
        "동",
        "호",
    ]

    # Pattern for removing parenthetical content
    PAREN_PATTERN = re.compile(r"[\(\)\[\]【】（）\(\)].*?[\)\]\】）\)\)]|[\(\[\【（\(][^\)\]\】）\)]*$")

    # Pattern for numeric suffix (e.g., "1차", "2단지", "3차")
    NUMERIC_SUFFIX_PATTERN = re.compile(r"\d+[차단지동호]?$")

    # Pattern for Roman numerals
    ROMAN_NUMERAL_PATTERN = re.compile(r"\s*[IVX]+$", re.IGNORECASE)

    # Pattern for whitespace normalization
    WHITESPACE_PATTERN = re.compile(r"\s+")

    def __init__(
        self,
        exact_match_threshold: float = 1.0,
        high_confidence_threshold: float = 0.85,
        min_match_threshold: float = 0.6,
    ):
        """Initialize the name matcher.

        Args:
            exact_match_threshold: Score for exact matches
            high_confidence_threshold: Score above which match is high confidence
            min_match_threshold: Minimum score to consider a match
        """
        self.exact_match_threshold = exact_match_threshold
        self.high_confidence_threshold = high_confidence_threshold
        self.min_match_threshold = min_match_threshold

    def normalize_name(self, name: str) -> str:
        """Normalize Korean apartment name for matching.

        Args:
            name: Original apartment name

        Returns:
            Normalized name with suffixes and parentheticals removed
        """
        if not name:
            return ""

        # Strip whitespace
        result = name.strip()

        # Normalize Unicode (NFC form)
        result = unicodedata.normalize("NFC", result)

        # Remove parenthetical content
        result = self.PAREN_PATTERN.sub("", result)

        # Remove suffixes (order matters)
        for suffix in self.SUFFIXES_TO_REMOVE:
            if result.endswith(suffix):
                result = result[: -len(suffix)]

        # Remove numeric suffix patterns
        result = self.NUMERIC_SUFFIX_PATTERN.sub("", result)

        # Remove Roman numeral suffixes
        result = self.ROMAN_NUMERAL_PATTERN.sub("", result)

        # Normalize whitespace
        result = self.WHITESPACE_PATTERN.sub(" ", result).strip()

        # Convert to lowercase for comparison
        result = result.lower()

        return result

    def extract_phase_number(self, name: str) -> Optional[int]:
        """Extract phase/차수 number from apartment name.

        Args:
            name: Apartment name

        Returns:
            Phase number if found, None otherwise
        """
        if not name:
            return None

        # Look for patterns like "1차", "2차", "제1단지"
        patterns = [
            re.compile(r"(\d+)\s*차"),
            re.compile(r"제?\s*(\d+)\s*단지"),
            re.compile(r"(\d+)\s*블록"),
        ]

        for pattern in patterns:
            match = pattern.search(name)
            if match:
                return int(match.group(1))

        # Roman numerals
        roman_map = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5}
        roman_match = self.ROMAN_NUMERAL_PATTERN.search(name)
        if roman_match:
            roman = roman_match.group().strip().lower()
            return roman_map.get(roman)

        return None

    def calculate_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity score between two names.

        Args:
            name1: First name
            name2: Second name

        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not name1 or not name2:
            return 0.0

        # Normalize both names
        norm1 = self.normalize_name(name1)
        norm2 = self.normalize_name(name2)

        if not norm1 or not norm2:
            return 0.0

        # Exact match after normalization
        if norm1 == norm2:
            return self.exact_match_threshold

        # Use SequenceMatcher for fuzzy matching
        return SequenceMatcher(None, norm1, norm2).ratio()

    def match(self, source_name: str, target_name: str) -> NameMatchResult:
        """Match two apartment names and return detailed result.

        Args:
            source_name: Source apartment name (e.g., from Naver)
            target_name: Target apartment name (e.g., from database)

        Returns:
            NameMatchResult with similarity score and method
        """
        source_norm = self.normalize_name(source_name)
        target_norm = self.normalize_name(target_name)

        # Determine match method
        if source_name.strip().lower() == target_name.strip().lower():
            method = "exact"
            score = self.exact_match_threshold
        elif source_norm == target_norm:
            method = "normalized"
            score = self.exact_match_threshold
        else:
            method = "fuzzy"
            score = SequenceMatcher(None, source_norm, target_norm).ratio()

        return NameMatchResult(
            original_name=source_name,
            normalized_name=source_norm,
            target_name=target_name,
            target_normalized=target_norm,
            similarity_score=score,
            match_method=method,
        )

    def find_best_match(
        self,
        source_name: str,
        candidates: List[Tuple[int, str]],
        min_score: Optional[float] = None,
    ) -> Optional[Tuple[int, NameMatchResult]]:
        """Find the best matching candidate for a source name.

        Args:
            source_name: Name to match
            candidates: List of (id, name) tuples to match against
            min_score: Minimum score to consider (defaults to min_match_threshold)

        Returns:
            Tuple of (candidate_id, NameMatchResult) or None if no match found
        """
        if not source_name or not candidates:
            return None

        if min_score is None:
            min_score = self.min_match_threshold

        best_match = None
        best_score = 0.0
        best_id = None

        for candidate_id, candidate_name in candidates:
            result = self.match(source_name, candidate_name)
            if result.similarity_score > best_score:
                best_score = result.similarity_score
                best_match = result
                best_id = candidate_id

        if best_match and best_match.similarity_score >= min_score:
            return (best_id, best_match)

        return None

    def is_high_confidence_match(self, score: float) -> bool:
        """Check if a match score indicates high confidence.

        Args:
            score: Similarity score

        Returns:
            True if score indicates high confidence match
        """
        return score >= self.high_confidence_threshold

    def check_phase_compatibility(
        self,
        name1: str,
        name2: str,
    ) -> bool:
        """Check if two names have compatible phase numbers.

        Different phases of the same complex should not match.

        Args:
            name1: First apartment name
            name2: Second apartment name

        Returns:
            True if phases are compatible (same or both None)
        """
        phase1 = self.extract_phase_number(name1)
        phase2 = self.extract_phase_number(name2)

        # If either has no phase, they're compatible
        if phase1 is None or phase2 is None:
            return True

        # If both have phases, they must match
        return phase1 == phase2
