"""Tests for the matching module.

Tests cover:
- NameMatcher: Korean apartment name normalization and similarity
- AddressMatcher: Address parsing and dong_code matching
- AreaMatcher: Pyeong group-based area matching
- MatchingService: Combined matching with configurable weights
"""
import pytest
from app.matching import (
    NameMatcher,
    AddressMatcher,
    AreaMatcher,
    MatchingService,
    MatchResult,
)
from app.matching.service import MatchingConfig, MatchConfidence


class TestNameMatcher:
    """Tests for NameMatcher class."""

    @pytest.fixture
    def matcher(self):
        return NameMatcher()

    def test_normalize_name_removes_parentheses(self, matcher):
        """Parenthetical content should be removed."""
        assert matcher.normalize_name("래미안(강남)") == "래미안"
        assert matcher.normalize_name("힐스테이트[푸르지오]") == "힐스테이트"

    def test_normalize_name_removes_suffixes(self, matcher):
        """Common suffixes should be removed."""
        assert matcher.normalize_name("삼성래미안아파트") == "삼성래미안"
        assert matcher.normalize_name("현대단지") == "현대"
        assert matcher.normalize_name("롯데캐슬주상복합") == "롯데캐슬"

    def test_normalize_name_removes_numeric_suffix(self, matcher):
        """Numeric suffixes like '1차' should be removed."""
        assert matcher.normalize_name("힐스테이트1차") == "힐스테이트"
        assert matcher.normalize_name("래미안2단지") == "래미안"

    def test_normalize_name_lowercase(self, matcher):
        """Names should be lowercased."""
        result = matcher.normalize_name("ABC아파트")
        assert result == result.lower()

    def test_calculate_similarity_exact_match(self, matcher):
        """Identical names should have score 1.0."""
        score = matcher.calculate_similarity("래미안", "래미안")
        assert score == 1.0

    def test_calculate_similarity_with_suffixes(self, matcher):
        """Names differing only in suffixes should match."""
        score = matcher.calculate_similarity("래미안아파트", "래미안")
        assert score == 1.0

    def test_calculate_similarity_different_names(self, matcher):
        """Different names should have low score."""
        score = matcher.calculate_similarity("래미안", "힐스테이트")
        assert score < 0.5

    def test_calculate_similarity_similar_names(self, matcher):
        """Similar names should have high score."""
        score = matcher.calculate_similarity("래미안대치", "래미안대치팰리스")
        assert score > 0.7

    def test_extract_phase_number(self, matcher):
        """Phase numbers should be extracted correctly."""
        assert matcher.extract_phase_number("래미안1차") == 1
        assert matcher.extract_phase_number("래미안2차") == 2
        assert matcher.extract_phase_number("제3단지") == 3
        assert matcher.extract_phase_number("래미안") is None

    def test_check_phase_compatibility_same_phase(self, matcher):
        """Same phase numbers should be compatible."""
        assert matcher.check_phase_compatibility("래미안1차", "래미안1차") is True

    def test_check_phase_compatibility_different_phases(self, matcher):
        """Different phase numbers should not be compatible."""
        assert matcher.check_phase_compatibility("래미안1차", "래미안2차") is False

    def test_check_phase_compatibility_no_phase(self, matcher):
        """Names without phases should be compatible."""
        assert matcher.check_phase_compatibility("래미안", "래미안아파트") is True

    def test_match_returns_name_match_result(self, matcher):
        """match() should return NameMatchResult."""
        result = matcher.match("래미안아파트", "래미안")
        assert result.original_name == "래미안아파트"
        assert result.target_name == "래미안"
        assert result.similarity_score == 1.0
        assert result.match_method == "normalized"

    def test_find_best_match(self, matcher):
        """find_best_match should return best candidate."""
        candidates = [
            (1, "힐스테이트"),
            (2, "래미안대치"),
            (3, "롯데캐슬"),
        ]
        result = matcher.find_best_match("래미안대치팰리스", candidates)
        assert result is not None
        assert result[0] == 2  # ID of 래미안대치


class TestAddressMatcher:
    """Tests for AddressMatcher class."""

    @pytest.fixture
    def matcher(self):
        return AddressMatcher()

    def test_normalize_address_seoul(self, matcher):
        """Seoul addresses should be parsed correctly."""
        result = matcher.normalize_address("서울 강남구 대치동 123-4")
        assert result.sido == "서울특별시"
        assert result.sigungu == "강남구"
        assert result.dong == "대치동"
        assert result.jibeon == "123-4"

    def test_normalize_address_short_sido(self, matcher):
        """Short sido names should be normalized."""
        result = matcher.normalize_address("서울특별시 강남구 역삼동")
        assert result.sido == "서울특별시"

    def test_normalize_address_road_name(self, matcher):
        """Road name addresses should be parsed."""
        result = matcher.normalize_address("서울 강남구 테헤란로 123")
        assert result.sigungu == "강남구"
        assert result.road_name == "테헤란로"
        assert result.building_num == "123"

    def test_match_by_dong_code_exact(self, matcher):
        """Exact dong_code match should return 'exact_dong'."""
        level = matcher.match_by_dong_code("1168010100", "1168010100")
        assert level == "exact_dong"

    def test_match_by_dong_code_same_gu(self, matcher):
        """Same gu (first 5 digits) should return 'same_gu'."""
        level = matcher.match_by_dong_code("1168010100", "1168020100")
        assert level == "same_gu"

    def test_match_by_dong_code_same_city(self, matcher):
        """Same city (first 2 digits) should return 'same_city'."""
        level = matcher.match_by_dong_code("1168010100", "1165010100")
        assert level == "same_city"

    def test_match_by_dong_code_different(self, matcher):
        """Different cities should return 'none'."""
        level = matcher.match_by_dong_code("1168010100", "2650010100")
        assert level == "none"

    def test_match_returns_address_match_result(self, matcher):
        """match() should return AddressMatchResult."""
        result = matcher.match(
            "서울 강남구 대치동",
            "서울 강남구 역삼동",
        )
        assert result.match_level == "same_gu"
        assert result.similarity_score == 0.7

    def test_calculate_distance_score(self, matcher):
        """Distance-based score should decay with distance."""
        # Same location
        score1 = matcher.calculate_distance_score(37.5, 127.0, 37.5, 127.0)
        assert score1 == 1.0

        # 2.5km away (half of max)
        score2 = matcher.calculate_distance_score(37.5, 127.0, 37.5225, 127.0)
        assert 0.4 < score2 < 0.6

        # 5km+ away
        score3 = matcher.calculate_distance_score(37.5, 127.0, 37.55, 127.05)
        assert score3 == 0.0

    def test_get_dong_code_prefix(self, matcher):
        """Seoul gu codes should be returned correctly."""
        code = matcher.get_dong_code_prefix("서울특별시", "강남구")
        assert code == "11680"


class TestAreaMatcher:
    """Tests for AreaMatcher class."""

    @pytest.fixture
    def matcher(self):
        return AreaMatcher()

    def test_get_area_group_25pyeong(self, matcher):
        """84m² should be in 25평형 group."""
        assert matcher.get_area_group(84.0) == 25

    def test_get_area_group_34pyeong(self, matcher):
        """114m² should be in 34평형 group."""
        assert matcher.get_area_group(114.0) == 34

    def test_get_area_group_boundary(self, matcher):
        """Boundary values should map correctly."""
        assert matcher.get_area_group(80.0) == 24  # 80m² is at the edge of 24평형
        assert matcher.get_area_group(84.0) == 25  # 84m² is clearly 25평형

    def test_areas_match_same_group(self, matcher):
        """Areas in same group should match."""
        assert matcher.areas_match(84.0, 85.5) is True
        assert matcher.areas_match(84.0, 84.95) is True

    def test_areas_match_different_groups(self, matcher):
        """Areas in different groups should not match."""
        assert matcher.areas_match(84.0, 114.0) is False

    def test_areas_match_with_adjacent(self, matcher):
        """Adjacent groups should match when allowed."""
        # 25평 (84m²) and adjacent groups
        assert matcher.areas_match(84.0, 76.0, allow_adjacent=True) is True
        assert matcher.areas_match(84.0, 99.0, allow_adjacent=True) is True

    def test_match_returns_area_match_result(self, matcher):
        """match() should return AreaMatchResult."""
        result = matcher.match(84.0, 85.5)
        assert result.source_area == 84.0
        assert result.target_area == 85.5
        assert result.is_match is True
        assert result.match_type == "same_group"

    def test_match_exact_tolerance(self, matcher):
        """Exact match within 1m² should be 'exact'."""
        result = matcher.match(84.0, 84.5)
        assert result.match_type == "exact"

    def test_calculate_similarity_score(self, matcher):
        """Similarity score should reflect match type."""
        # Same group
        score1 = matcher.calculate_similarity_score(84.0, 85.0)
        assert score1 == 1.0

        # Adjacent group
        score2 = matcher.calculate_similarity_score(84.0, 76.0)
        assert score2 == 0.7

        # Different group
        score3 = matcher.calculate_similarity_score(84.0, 114.0)
        assert score3 < 0.5

    def test_m2_to_pyeong_conversion(self, matcher):
        """m² to pyeong conversion should be accurate."""
        pyeong = matcher.m2_to_pyeong(84.0)
        assert 25.0 < pyeong < 26.0

    def test_get_group_info(self, matcher):
        """get_group_info should return detailed info."""
        info = matcher.get_group_info(84.0)
        assert info is not None
        assert info["pyeong"] == 25
        assert info["typical_m2"] == 84

    def test_normalize_to_typical(self, matcher):
        """normalize_to_typical should return group's typical value."""
        typical = matcher.normalize_to_typical(85.5)
        assert typical == 84  # 25평형의 typical


class TestMatchingService:
    """Tests for MatchingService class."""

    @pytest.fixture
    def service(self):
        config = MatchingConfig(
            name_weight=0.5,
            address_weight=0.3,
            area_weight=0.2,
            min_match_threshold=0.6,
        )
        return MatchingService(config=config)

    def test_match_with_all_components(self, service):
        """Match with all components should work."""
        result = service.match(
            source_name="래미안대치팰리스",
            target_name="래미안대치팰리스",
            source_dong_code="1168010100",
            target_dong_code="1168010100",
            source_area=84.0,
            target_area=84.5,
            target_apartment_id=1,
        )
        assert result.apartment_id == 1
        assert result.total_score > 0.9
        assert result.confidence == MatchConfidence.HIGH

    def test_match_name_only(self, service):
        """Match with name only should work."""
        result = service.match(
            source_name="래미안대치팰리스",
            target_name="래미안대치팰리스",
            target_apartment_id=1,
        )
        assert result.total_score > 0.9
        assert result.name_score > 0.9
        assert result.address_score == 0.0

    def test_match_low_confidence(self, service):
        """Low similarity should result in low confidence."""
        result = service.match(
            source_name="래미안",
            target_name="힐스테이트",
            target_apartment_id=1,
        )
        assert result.total_score < 0.6
        assert result.confidence == MatchConfidence.NONE

    def test_match_medium_confidence(self, service):
        """Medium similarity should result in medium confidence."""
        result = service.match(
            source_name="래미안대치",
            target_name="래미안대치팰리스",
            source_dong_code="1168010100",
            target_dong_code="1168020100",  # Same gu, different dong
            target_apartment_id=1,
        )
        assert 0.7 <= result.total_score < 0.85
        assert result.confidence == MatchConfidence.MEDIUM

    def test_validate_match_success(self, service):
        """Valid matches should pass validation."""
        result = service.match(
            source_name="래미안대치팰리스",
            target_name="래미안대치팰리스",
            source_area=84.0,
            target_area=84.5,
            target_apartment_id=1,
        )
        is_valid, issues = service.validate_match(result)
        assert is_valid is True
        assert len(issues) == 0

    def test_validate_match_phase_mismatch(self, service):
        """Phase mismatch should be flagged."""
        result = service.match(
            source_name="래미안1차",
            target_name="래미안2차",
            target_apartment_id=1,
        )
        is_valid, issues = service.validate_match(result)
        assert "Phase number mismatch" in " ".join(issues)

    def test_to_log_dict(self, service):
        """to_log_dict should return proper dictionary."""
        result = service.match(
            source_name="래미안",
            target_name="래미안아파트",
            target_apartment_id=1,
        )
        log_dict = service.to_log_dict(result)
        assert "apartment_id" in log_dict
        assert "total_score" in log_dict
        assert "confidence" in log_dict
        assert log_dict["apartment_id"] == 1

    def test_config_weight_validation(self):
        """Config with invalid weights should raise error."""
        with pytest.raises(ValueError, match="sum to 1.0"):
            MatchingConfig(
                name_weight=0.5,
                address_weight=0.5,
                area_weight=0.5,  # Total = 1.5
            )


class TestMatchingIntegration:
    """Integration tests for matching module."""

    def test_realistic_naver_matching(self):
        """Test realistic Naver listing matching scenario."""
        service = MatchingService()

        # Simulate matching a Naver listing to database apartments
        naver_name = "래미안대치팰리스(대치동)"
        db_apartments = [
            {"id": 1, "name": "래미안대치팰리스", "dong_code": "1168010100"},
            {"id": 2, "name": "래미안대치2차", "dong_code": "1168010100"},
            {"id": 3, "name": "힐스테이트대치", "dong_code": "1168010100"},
        ]

        best_match = None
        best_score = 0

        for apt in db_apartments:
            result = service.match(
                source_name=naver_name,
                target_name=apt["name"],
                source_dong_code="1168010100",
                target_dong_code=apt["dong_code"],
                target_apartment_id=apt["id"],
            )
            if result.total_score > best_score:
                best_score = result.total_score
                best_match = result

        assert best_match is not None
        assert best_match.apartment_id == 1  # 래미안대치팰리스
        assert best_match.total_score > 0.8

    def test_area_disambiguation(self):
        """Test that area helps disambiguate similar apartments."""
        service = MatchingService()

        # Two similar apartments with different typical areas
        result1 = service.match(
            source_name="래미안대치",
            target_name="래미안대치",
            source_area=84.0,
            target_area=85.0,
            target_apartment_id=1,
        )

        result2 = service.match(
            source_name="래미안대치",
            target_name="래미안대치",
            source_area=84.0,
            target_area=114.0,  # Different area group
            target_apartment_id=2,
        )

        # Same name but area mismatch should score lower
        assert result1.total_score > result2.total_score
