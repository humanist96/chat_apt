"""Area matching for Korean apartment sizes.

Handles Korean apartment area groups:
- 18평 (59m²): 50-65 m²
- 25평 (84m²): 75-90 m²
- 30평 (101m²): 95-110 m²
- 34평 (114m²): 110-125 m²
- 40평 (140m²): 130-150 m²

Provides group-based matching that understands:
- 84A vs 84B variants are the same group
- Similar pyeong groups should match
"""
from dataclasses import dataclass
from typing import Optional, Dict, List


@dataclass
class AreaGroup:
    """Korean apartment area group definition."""
    pyeong: int  # 평형 (e.g., 18, 25, 30, 34, 40)
    min_m2: float  # Minimum area in m²
    max_m2: float  # Maximum area in m²
    typical_m2: float  # Typical/standard area in m²


@dataclass
class AreaMatchResult:
    """Result of area matching operation."""
    source_area: float
    target_area: float
    source_group: Optional[int]  # pyeong group
    target_group: Optional[int]  # pyeong group
    is_match: bool
    match_type: str  # 'exact', 'same_group', 'adjacent', 'none'
    difference_m2: float
    difference_percent: float


class AreaMatcher:
    """Korean apartment area matcher using pyeong groups."""

    # Standard Korean apartment area groups
    # Based on common construction standards
    AREA_GROUPS: Dict[int, AreaGroup] = {
        10: AreaGroup(pyeong=10, min_m2=30, max_m2=40, typical_m2=33),
        15: AreaGroup(pyeong=15, min_m2=45, max_m2=55, typical_m2=49),
        18: AreaGroup(pyeong=18, min_m2=55, max_m2=65, typical_m2=59),
        20: AreaGroup(pyeong=20, min_m2=63, max_m2=72, typical_m2=66),
        24: AreaGroup(pyeong=24, min_m2=72, max_m2=80, typical_m2=76),
        25: AreaGroup(pyeong=25, min_m2=80, max_m2=90, typical_m2=84),
        30: AreaGroup(pyeong=30, min_m2=95, max_m2=105, typical_m2=99),
        32: AreaGroup(pyeong=32, min_m2=100, max_m2=110, typical_m2=105),
        34: AreaGroup(pyeong=34, min_m2=110, max_m2=120, typical_m2=114),
        40: AreaGroup(pyeong=40, min_m2=130, max_m2=145, typical_m2=136),
        45: AreaGroup(pyeong=45, min_m2=145, max_m2=160, typical_m2=151),
        50: AreaGroup(pyeong=50, min_m2=160, max_m2=180, typical_m2=169),
        60: AreaGroup(pyeong=60, min_m2=195, max_m2=215, typical_m2=203),
    }

    # Conversion factor: 1평 = 3.3058 m²
    PYEONG_TO_M2 = 3.3058

    def __init__(
        self,
        exact_tolerance_m2: float = 1.0,
        group_match_score: float = 1.0,
        adjacent_group_score: float = 0.7,
    ):
        """Initialize the area matcher.

        Args:
            exact_tolerance_m2: Tolerance for exact area match in m²
            group_match_score: Score for same group match
            adjacent_group_score: Score for adjacent group match
        """
        self.exact_tolerance_m2 = exact_tolerance_m2
        self.group_match_score = group_match_score
        self.adjacent_group_score = adjacent_group_score

    def m2_to_pyeong(self, area_m2: float) -> float:
        """Convert square meters to pyeong.

        Args:
            area_m2: Area in square meters

        Returns:
            Area in pyeong
        """
        return area_m2 / self.PYEONG_TO_M2

    def pyeong_to_m2(self, pyeong: float) -> float:
        """Convert pyeong to square meters.

        Args:
            pyeong: Area in pyeong

        Returns:
            Area in square meters
        """
        return pyeong * self.PYEONG_TO_M2

    def get_area_group(self, area_m2: float) -> Optional[int]:
        """Determine the pyeong group for a given area.

        Args:
            area_m2: Area in square meters

        Returns:
            Pyeong group number or None if no match
        """
        if area_m2 <= 0:
            return None

        for pyeong, group in self.AREA_GROUPS.items():
            if group.min_m2 <= area_m2 <= group.max_m2:
                return pyeong

        # Fall back to nearest group for areas outside defined ranges
        return self._find_nearest_group(area_m2)

    def _find_nearest_group(self, area_m2: float) -> Optional[int]:
        """Find the nearest pyeong group for an area.

        Args:
            area_m2: Area in square meters

        Returns:
            Nearest pyeong group or None
        """
        if area_m2 <= 0:
            return None

        min_distance = float("inf")
        nearest_group = None

        for pyeong, group in self.AREA_GROUPS.items():
            distance = abs(area_m2 - group.typical_m2)
            if distance < min_distance:
                min_distance = distance
                nearest_group = pyeong

        return nearest_group

    def get_adjacent_groups(self, pyeong: int) -> List[int]:
        """Get adjacent pyeong groups.

        Args:
            pyeong: Current pyeong group

        Returns:
            List of adjacent pyeong groups
        """
        sorted_groups = sorted(self.AREA_GROUPS.keys())
        try:
            idx = sorted_groups.index(pyeong)
        except ValueError:
            return []

        adjacent = []
        if idx > 0:
            adjacent.append(sorted_groups[idx - 1])
        if idx < len(sorted_groups) - 1:
            adjacent.append(sorted_groups[idx + 1])

        return adjacent

    def areas_match(
        self,
        area1_m2: float,
        area2_m2: float,
        allow_adjacent: bool = False,
    ) -> bool:
        """Check if two areas match (same group).

        Args:
            area1_m2: First area in m²
            area2_m2: Second area in m²
            allow_adjacent: Also match adjacent groups

        Returns:
            True if areas are in the same (or adjacent) group
        """
        group1 = self.get_area_group(area1_m2)
        group2 = self.get_area_group(area2_m2)

        if group1 is None or group2 is None:
            # Fall back to absolute tolerance
            return abs(area1_m2 - area2_m2) <= self.exact_tolerance_m2

        if group1 == group2:
            return True

        if allow_adjacent:
            return group2 in self.get_adjacent_groups(group1)

        return False

    def match(
        self,
        source_area: float,
        target_area: float,
    ) -> AreaMatchResult:
        """Match two areas and return detailed result.

        Args:
            source_area: Source area in m²
            target_area: Target area in m²

        Returns:
            AreaMatchResult with match details
        """
        source_group = self.get_area_group(source_area)
        target_group = self.get_area_group(target_area)

        difference_m2 = abs(source_area - target_area)
        difference_percent = (
            (difference_m2 / source_area * 100) if source_area > 0 else 0
        )

        # Determine match type
        if difference_m2 <= self.exact_tolerance_m2:
            match_type = "exact"
            is_match = True
        elif source_group is not None and source_group == target_group:
            match_type = "same_group"
            is_match = True
        elif (
            source_group is not None
            and target_group is not None
            and target_group in self.get_adjacent_groups(source_group)
        ):
            match_type = "adjacent"
            is_match = True
        else:
            match_type = "none"
            is_match = False

        return AreaMatchResult(
            source_area=source_area,
            target_area=target_area,
            source_group=source_group,
            target_group=target_group,
            is_match=is_match,
            match_type=match_type,
            difference_m2=round(difference_m2, 2),
            difference_percent=round(difference_percent, 2),
        )

    def calculate_similarity_score(
        self,
        area1_m2: float,
        area2_m2: float,
    ) -> float:
        """Calculate similarity score between two areas.

        Args:
            area1_m2: First area in m²
            area2_m2: Second area in m²

        Returns:
            Similarity score from 0.0 to 1.0
        """
        result = self.match(area1_m2, area2_m2)

        if result.match_type == "exact":
            return 1.0
        elif result.match_type == "same_group":
            return self.group_match_score
        elif result.match_type == "adjacent":
            return self.adjacent_group_score
        else:
            # Exponential decay based on percent difference
            # 20% difference = 0.5 score, 50% difference ≈ 0.1 score
            return max(0.0, 1.0 - (result.difference_percent / 20) ** 1.5)

    def get_group_info(self, area_m2: float) -> Optional[Dict]:
        """Get detailed information about an area's group.

        Args:
            area_m2: Area in m²

        Returns:
            Dict with group information or None
        """
        group = self.get_area_group(area_m2)
        if group is None:
            return None

        area_group = self.AREA_GROUPS.get(group)
        if area_group is None:
            return None

        return {
            "pyeong": group,
            "min_m2": area_group.min_m2,
            "max_m2": area_group.max_m2,
            "typical_m2": area_group.typical_m2,
            "current_m2": area_m2,
            "pyeong_value": round(self.m2_to_pyeong(area_m2), 1),
        }

    def normalize_to_typical(self, area_m2: float) -> float:
        """Normalize an area to its group's typical value.

        Useful for comparisons where minor area variations
        should be treated as equivalent.

        Args:
            area_m2: Area in m²

        Returns:
            Typical area for the group, or original if no group found
        """
        group = self.get_area_group(area_m2)
        if group is None:
            return area_m2

        area_group = self.AREA_GROUPS.get(group)
        if area_group is None:
            return area_m2

        return area_group.typical_m2
