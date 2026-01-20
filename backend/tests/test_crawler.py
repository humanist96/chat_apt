"""Tests for crawler module."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from app.crawler.anti_abuse import (
    RequestDelay,
    ProxyManager,
    AntiAbuseManager,
    ExponentialBackoff,
    USER_AGENTS,
)
from app.crawler.naver import (
    NaverRealEstateCrawler,
    NaverListing,
    NaverComplex,
    TRADE_TYPES,
)


class TestRequestDelay:
    """Tests for RequestDelay."""

    def test_default_delay(self):
        """Test default delay configuration."""
        delay = RequestDelay()

        assert delay.min_delay == 1.0
        assert delay.max_delay == 3.0
        assert delay.use_gaussian is True

    def test_get_delay_range(self):
        """Test delay is within configured range."""
        delay = RequestDelay(min_delay=1.0, max_delay=3.0, use_gaussian=False)

        for _ in range(100):
            d = delay.get_delay()
            assert 1.0 <= d <= 3.0

    def test_get_delay_gaussian(self):
        """Test Gaussian delay distribution."""
        delay = RequestDelay(
            min_delay=0.5,
            max_delay=5.0,
            use_gaussian=True,
            mean=2.0,
            std_dev=0.5,
        )

        delays = [delay.get_delay() for _ in range(100)]

        # Check delays are clamped to range
        assert all(0.5 <= d <= 5.0 for d in delays)

        # Mean should be roughly around 2.0
        avg = sum(delays) / len(delays)
        assert 1.5 < avg < 2.5

    @pytest.mark.asyncio
    async def test_wait(self):
        """Test wait method."""
        delay = RequestDelay(min_delay=0.01, max_delay=0.02)

        start = asyncio.get_event_loop().time()
        actual_delay = await delay.wait()
        elapsed = asyncio.get_event_loop().time() - start

        assert 0.01 <= actual_delay <= 0.02
        assert elapsed >= 0.01


class TestProxyManager:
    """Tests for ProxyManager."""

    def test_no_proxies(self):
        """Test with no proxies configured."""
        manager = ProxyManager([])
        assert manager.get_proxy() is None

    def test_round_robin(self):
        """Test round-robin proxy selection."""
        proxies = ["http://proxy1:8080", "http://proxy2:8080", "http://proxy3:8080"]
        manager = ProxyManager(proxies)

        selected = [manager.get_proxy() for _ in range(6)]

        # Should cycle through all proxies
        assert selected == proxies + proxies

    def test_mark_failed(self):
        """Test marking proxy as failed."""
        proxies = ["http://proxy1:8080", "http://proxy2:8080"]
        manager = ProxyManager(proxies)
        manager._cooldown_seconds = 10  # Short cooldown for testing

        manager.mark_failed("http://proxy1:8080")

        # Failed proxy should be skipped
        selected = [manager.get_proxy() for _ in range(3)]
        assert all(p == "http://proxy2:8080" for p in selected)

    def test_mark_success_clears_failure(self):
        """Test marking proxy as success clears failure."""
        proxies = ["http://proxy1:8080", "http://proxy2:8080"]
        manager = ProxyManager(proxies)

        manager.mark_failed("http://proxy1:8080")
        manager.mark_success("http://proxy1:8080")

        # Proxy should be available again
        assert "http://proxy1:8080" not in manager._failed_proxies


class TestAntiAbuseManager:
    """Tests for AntiAbuseManager."""

    def test_get_random_user_agent(self):
        """Test random user agent selection."""
        manager = AntiAbuseManager()

        ua = manager.get_random_user_agent()
        assert ua in USER_AGENTS

    def test_get_headers(self):
        """Test headers generation."""
        manager = AntiAbuseManager()

        headers = manager.get_headers()

        assert "User-Agent" in headers
        assert headers["User-Agent"] in USER_AGENTS
        assert "Accept" in headers
        assert "Accept-Language" in headers

    @pytest.mark.asyncio
    async def test_pre_request(self):
        """Test pre-request configuration."""
        delay = RequestDelay(min_delay=0.01, max_delay=0.02)
        manager = AntiAbuseManager(request_delay=delay)

        config = await manager.pre_request()

        assert "headers" in config
        assert "proxy" in config
        assert "User-Agent" in config["headers"]

    def test_is_blocked_response_status_codes(self):
        """Test blocked response detection by status code."""
        assert AntiAbuseManager.is_blocked_response(403) is True
        assert AntiAbuseManager.is_blocked_response(429) is True
        assert AntiAbuseManager.is_blocked_response(503) is True
        assert AntiAbuseManager.is_blocked_response(200) is False

    def test_is_blocked_response_keywords(self):
        """Test blocked response detection by content."""
        assert AntiAbuseManager.is_blocked_response(200, "Please complete CAPTCHA") is True
        assert AntiAbuseManager.is_blocked_response(200, "rate limit exceeded") is True
        assert AntiAbuseManager.is_blocked_response(200, "보안 문자를 입력하세요") is True
        assert AntiAbuseManager.is_blocked_response(200, "Normal content here") is False

    def test_on_request_failure_increases_delay(self):
        """Test that blocking increases delays."""
        manager = AntiAbuseManager()
        original_min = manager.delay.min_delay

        manager.on_request_failure(is_blocked=True)

        assert manager.delay.min_delay > original_min


class TestExponentialBackoff:
    """Tests for ExponentialBackoff."""

    def test_initial_delay(self):
        """Test initial delay value."""
        backoff = ExponentialBackoff(initial_delay=1.0)

        delay = backoff.get_delay()
        assert 0.9 <= delay <= 1.1  # ±10% jitter

    def test_exponential_increase(self):
        """Test delays increase exponentially."""
        backoff = ExponentialBackoff(initial_delay=1.0, multiplier=2.0)

        delays = []
        for i in range(4):
            delays.append(backoff.get_delay())
            backoff._current_retry += 1

        # Each delay should be roughly double the previous
        assert delays[1] > delays[0] * 1.5
        assert delays[2] > delays[1] * 1.5

    def test_max_delay_cap(self):
        """Test maximum delay is capped."""
        backoff = ExponentialBackoff(
            initial_delay=1.0,
            max_delay=10.0,
            multiplier=10.0,  # Would exceed max quickly
        )

        backoff._current_retry = 10  # Many retries

        delay = backoff.get_delay()
        assert delay <= 11.0  # max_delay + jitter

    @pytest.mark.asyncio
    async def test_wait_max_retries(self):
        """Test wait returns False after max retries."""
        backoff = ExponentialBackoff(
            initial_delay=0.001,
            max_retries=3,
        )

        results = []
        for _ in range(5):
            results.append(await backoff.wait())

        assert results == [True, True, True, False, False]

    def test_reset(self):
        """Test reset clears retry counter."""
        backoff = ExponentialBackoff(max_retries=3)
        backoff._current_retry = 5

        backoff.reset()

        assert backoff._current_retry == 0
        assert backoff.retries_remaining == 3


class TestNaverRealEstateCrawler:
    """Tests for NaverRealEstateCrawler."""

    def test_trade_types_defined(self):
        """Test trade type codes are defined."""
        assert TRADE_TYPES["매매"] == "A1"
        assert TRADE_TYPES["전세"] == "B1"
        assert TRADE_TYPES["월세"] == "B2"

    def test_parse_price_simple(self):
        """Test parsing simple price values."""
        assert NaverRealEstateCrawler._parse_price("3,000") == 3000
        assert NaverRealEstateCrawler._parse_price("5000") == 5000
        assert NaverRealEstateCrawler._parse_price("") == 0
        assert NaverRealEstateCrawler._parse_price(None) == 0

    def test_parse_price_billion(self):
        """Test parsing prices with 억 unit."""
        assert NaverRealEstateCrawler._parse_price("15억") == 150000
        assert NaverRealEstateCrawler._parse_price("15억 5,000") == 155000
        assert NaverRealEstateCrawler._parse_price("8억 5,000") == 85000
        assert NaverRealEstateCrawler._parse_price("1억") == 10000

    def test_parse_year(self):
        """Test parsing year from date string."""
        assert NaverRealEstateCrawler._parse_year("20201215") == 2020
        assert NaverRealEstateCrawler._parse_year("2015") == 2015
        assert NaverRealEstateCrawler._parse_year("") is None
        assert NaverRealEstateCrawler._parse_year(None) is None

    def test_parse_trade_type(self):
        """Test parsing trade type names."""
        assert NaverRealEstateCrawler._parse_trade_type("매매") == "매매"
        assert NaverRealEstateCrawler._parse_trade_type("전세") == "전세"
        assert NaverRealEstateCrawler._parse_trade_type("월세") == "월세"
        assert NaverRealEstateCrawler._parse_trade_type(None) == "매매"

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test using crawler as context manager."""
        async with NaverRealEstateCrawler() as crawler:
            assert crawler is not None

    @pytest.mark.asyncio
    async def test_get_listings_mocked(self):
        """Test get_listings with mocked response."""
        crawler = NaverRealEstateCrawler()

        mock_response = {
            "articleList": [
                {
                    "articleNo": "123456",
                    "articleName": "래미안아파트",
                    "tradeTypeName": "매매",
                    "dealOrWarrantPrc": "15억",
                    "area1": 84.95,
                    "floorInfo": "10/20",
                    "direction": "남향",
                }
            ]
        }

        with patch.object(crawler, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            listings = await crawler.get_listings("12345")

            assert len(listings) == 1
            assert listings[0].article_no == "123456"
            assert listings[0].price == 150000
            assert listings[0].trade_type == "매매"

        await crawler.close()


class TestNaverListing:
    """Tests for NaverListing dataclass."""

    def test_listing_creation(self):
        """Test creating a NaverListing."""
        listing = NaverListing(
            article_no="123456",
            complex_no="78910",
            complex_name="테스트아파트",
            trade_type="매매",
            price=150000,
        )

        assert listing.article_no == "123456"
        assert listing.price == 150000
        assert listing.rent_price is None


class TestNaverComplex:
    """Tests for NaverComplex dataclass."""

    def test_complex_creation(self):
        """Test creating a NaverComplex."""
        complex_info = NaverComplex(
            complex_no="12345",
            complex_name="테스트아파트",
            address="서울시 강남구",
            total_units=500,
            built_year=2020,
        )

        assert complex_info.complex_no == "12345"
        assert complex_info.built_year == 2020
