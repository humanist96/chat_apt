"""Address matching for Korean addresses.

Handles Korean address parsing and matching:
- Parses "서울 강남구 대치동 123-4" format
- Supports dong_code based matching
- Handles various address formats (road name, jibeon)
"""
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class NormalizedAddress:
    """Normalized Korean address components."""
    sido: Optional[str] = None  # 시/도 (e.g., "서울", "경기")
    sigungu: Optional[str] = None  # 시/군/구 (e.g., "강남구")
    dong: Optional[str] = None  # 동/읍/면 (e.g., "대치동")
    jibeon: Optional[str] = None  # 지번 (e.g., "123-4")
    road_name: Optional[str] = None  # 도로명 (e.g., "테헤란로")
    building_num: Optional[str] = None  # 건물번호 (e.g., "123")
    dong_code: Optional[str] = None  # 법정동코드


@dataclass
class AddressMatchResult:
    """Result of address matching operation."""
    source_address: str
    target_address: str
    source_normalized: NormalizedAddress
    target_normalized: NormalizedAddress
    similarity_score: float
    match_level: str  # 'exact_dong', 'same_gu', 'same_city', 'none'


class AddressMatcher:
    """Korean address matcher with dong_code support."""

    # Common sido abbreviations
    SIDO_ALIASES = {
        "서울": "서울특별시",
        "서울시": "서울특별시",
        "부산": "부산광역시",
        "대구": "대구광역시",
        "인천": "인천광역시",
        "광주": "광주광역시",
        "대전": "대전광역시",
        "울산": "울산광역시",
        "세종": "세종특별자치시",
        "경기": "경기도",
        "강원": "강원도",
        "충북": "충청북도",
        "충남": "충청남도",
        "전북": "전라북도",
        "전남": "전라남도",
        "경북": "경상북도",
        "경남": "경상남도",
        "제주": "제주특별자치도",
    }

    # Pattern for parsing address components
    SIDO_PATTERN = re.compile(
        r"^(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)"
        r"(?:특별시|광역시|특별자치시|특별자치도|도|시)?\s*"
    )

    SIGUNGU_PATTERN = re.compile(r"([가-힣]+(?:시|군|구))\s*")

    DONG_PATTERN = re.compile(r"([가-힣]+(?:동|읍|면|리|가))\s*")

    JIBEON_PATTERN = re.compile(r"(\d+(?:-\d+)?)\s*")

    ROAD_PATTERN = re.compile(r"([가-힣]+(?:로|길|대로))\s*")

    BUILDING_NUM_PATTERN = re.compile(r"(\d+(?:-\d+)?)")

    # Seoul gu to dong_code prefix mapping (first 5 digits)
    SEOUL_GU_CODES = {
        "종로구": "11110",
        "중구": "11140",
        "용산구": "11170",
        "성동구": "11200",
        "광진구": "11215",
        "동대문구": "11230",
        "중랑구": "11260",
        "성북구": "11290",
        "강북구": "11305",
        "도봉구": "11320",
        "노원구": "11350",
        "은평구": "11380",
        "서대문구": "11410",
        "마포구": "11440",
        "양천구": "11470",
        "강서구": "11500",
        "구로구": "11530",
        "금천구": "11545",
        "영등포구": "11560",
        "동작구": "11590",
        "관악구": "11620",
        "서초구": "11650",
        "강남구": "11680",
        "송파구": "11710",
        "강동구": "11740",
    }

    def __init__(
        self,
        exact_dong_score: float = 1.0,
        same_gu_score: float = 0.7,
        same_city_score: float = 0.4,
    ):
        """Initialize the address matcher.

        Args:
            exact_dong_score: Score for exact dong match
            same_gu_score: Score for same gu but different dong
            same_city_score: Score for same city but different gu
        """
        self.exact_dong_score = exact_dong_score
        self.same_gu_score = same_gu_score
        self.same_city_score = same_city_score

    def normalize_address(self, address: str) -> NormalizedAddress:
        """Normalize a Korean address into components.

        Args:
            address: Raw address string

        Returns:
            NormalizedAddress with parsed components
        """
        if not address:
            return NormalizedAddress()

        result = NormalizedAddress()
        remaining = address.strip()

        # Extract sido
        sido_match = self.SIDO_PATTERN.match(remaining)
        if sido_match:
            sido = sido_match.group(1)
            result.sido = self.SIDO_ALIASES.get(sido, sido)
            remaining = remaining[sido_match.end():]

        # Extract sigungu
        sigungu_match = self.SIGUNGU_PATTERN.match(remaining)
        if sigungu_match:
            result.sigungu = sigungu_match.group(1)
            remaining = remaining[sigungu_match.end():]

        # Check for road name address (도로명 주소)
        road_match = self.ROAD_PATTERN.match(remaining)
        if road_match:
            result.road_name = road_match.group(1)
            remaining = remaining[road_match.end():]
            # Extract building number
            building_match = self.BUILDING_NUM_PATTERN.match(remaining)
            if building_match:
                result.building_num = building_match.group(1)
        else:
            # Extract dong (지번 주소)
            dong_match = self.DONG_PATTERN.match(remaining)
            if dong_match:
                result.dong = dong_match.group(1)
                remaining = remaining[dong_match.end():]

            # Extract jibeon
            jibeon_match = self.JIBEON_PATTERN.match(remaining)
            if jibeon_match:
                result.jibeon = jibeon_match.group(1)

        return result

    def get_dong_code_prefix(
        self,
        sido: Optional[str],
        sigungu: Optional[str],
    ) -> Optional[str]:
        """Get dong_code prefix from sido and sigungu.

        Args:
            sido: Sido component
            sigungu: Sigungu component

        Returns:
            5-digit dong_code prefix or None
        """
        if not sido or not sigungu:
            return None

        # Handle Seoul
        if sido in ("서울", "서울특별시"):
            return self.SEOUL_GU_CODES.get(sigungu)

        return None

    def match_by_dong_code(
        self,
        dong_code1: Optional[str],
        dong_code2: Optional[str],
    ) -> str:
        """Match two dong_codes and return match level.

        Args:
            dong_code1: First dong code
            dong_code2: Second dong code

        Returns:
            Match level: 'exact_dong', 'same_gu', 'same_city', 'none'
        """
        if not dong_code1 or not dong_code2:
            return "none"

        # Exact match (full 10 digits)
        if dong_code1 == dong_code2:
            return "exact_dong"

        # Same gu (first 5 digits)
        if dong_code1[:5] == dong_code2[:5]:
            return "same_gu"

        # Same city (first 2 digits for sido)
        if dong_code1[:2] == dong_code2[:2]:
            return "same_city"

        return "none"

    def match(
        self,
        source_address: str,
        target_address: str,
        source_dong_code: Optional[str] = None,
        target_dong_code: Optional[str] = None,
    ) -> AddressMatchResult:
        """Match two addresses and return detailed result.

        Args:
            source_address: Source address string
            target_address: Target address string
            source_dong_code: Optional pre-parsed dong_code for source
            target_dong_code: Optional pre-parsed dong_code for target

        Returns:
            AddressMatchResult with similarity score and match level
        """
        source_norm = self.normalize_address(source_address)
        target_norm = self.normalize_address(target_address)

        # Prefer dong_code matching if available
        if source_dong_code and target_dong_code:
            match_level = self.match_by_dong_code(source_dong_code, target_dong_code)
        else:
            # Fall back to component matching
            match_level = self._match_components(source_norm, target_norm)

        # Calculate score based on match level
        score_map = {
            "exact_dong": self.exact_dong_score,
            "same_gu": self.same_gu_score,
            "same_city": self.same_city_score,
            "none": 0.0,
        }
        score = score_map.get(match_level, 0.0)

        return AddressMatchResult(
            source_address=source_address,
            target_address=target_address,
            source_normalized=source_norm,
            target_normalized=target_norm,
            similarity_score=score,
            match_level=match_level,
        )

    def _match_components(
        self,
        addr1: NormalizedAddress,
        addr2: NormalizedAddress,
    ) -> str:
        """Match two normalized addresses by components.

        Args:
            addr1: First normalized address
            addr2: Second normalized address

        Returns:
            Match level string
        """
        # Check dong match
        if addr1.dong and addr2.dong and addr1.dong == addr2.dong:
            # Also check sigungu matches
            if addr1.sigungu == addr2.sigungu:
                return "exact_dong"

        # Check sigungu match
        if addr1.sigungu and addr2.sigungu and addr1.sigungu == addr2.sigungu:
            return "same_gu"

        # Check sido match
        if addr1.sido and addr2.sido:
            sido1 = self.SIDO_ALIASES.get(addr1.sido, addr1.sido)
            sido2 = self.SIDO_ALIASES.get(addr2.sido, addr2.sido)
            if sido1 == sido2:
                return "same_city"

        return "none"

    def calculate_distance_score(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
        max_distance_km: float = 5.0,
    ) -> float:
        """Calculate similarity score based on distance.

        Uses Haversine formula for distance calculation.

        Args:
            lat1, lon1: First location coordinates
            lat2, lon2: Second location coordinates
            max_distance_km: Maximum distance for positive score

        Returns:
            Score from 0.0 to 1.0 based on distance
        """
        import math

        R = 6371  # Earth's radius in km

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c

        if distance >= max_distance_km:
            return 0.0

        # Linear decay from 1.0 at distance=0 to 0.0 at max_distance
        return 1.0 - (distance / max_distance_km)
