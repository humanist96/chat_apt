"""Naver Real Estate crawler.

This module provides a crawler for collecting property listing data
from Naver Real Estate (land.naver.com) using their internal API endpoints.
"""
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

import httpx

from app.crawler.anti_abuse import AntiAbuseManager, ExponentialBackoff


@dataclass
class NaverListing:
    """Listing data from Naver Real Estate."""
    article_no: str
    complex_no: str
    complex_name: str
    trade_type: str  # 매매, 전세, 월세
    price: int  # In 만원 (10,000 KRW)
    rent_price: Optional[int] = None  # Monthly rent for 월세
    area_exclusive: Optional[float] = None  # 전용면적 (m2)
    area_supply: Optional[float] = None  # 공급면적 (m2)
    floor: Optional[str] = None
    direction: Optional[str] = None
    description: Optional[str] = None
    realtor_name: Optional[str] = None
    realtor_phone: Optional[str] = None
    confirm_date: Optional[str] = None  # 확인일자
    article_confirm_ymd: Optional[str] = None


@dataclass
class NaverComplex:
    """Apartment complex data from Naver Real Estate."""
    complex_no: str
    complex_name: str
    address: Optional[str] = None
    dong_code: Optional[str] = None
    total_units: Optional[int] = None
    built_year: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class NaverRealEstateCrawler:
    """Crawler for Naver Real Estate data.

    Uses Naver's internal API endpoints for data collection.
    """

    # API endpoints (discovered through network analysis)
    BASE_URL = "https://new.land.naver.com"
    API_BASE = "https://new.land.naver.com/api"
    MOBILE_BASE = "https://m.land.naver.com"

    # Endpoint patterns
    COMPLEX_LIST_URL = f"{API_BASE}/regions/complexes"
    COMPLEX_DETAIL_URL = f"{API_BASE}/complexes/{{complex_no}}"
    ARTICLE_LIST_URL = f"{API_BASE}/articles/complex/{{complex_no}}"
    ARTICLE_DETAIL_URL = f"{API_BASE}/articles/{{article_no}}"

    # Mobile API - more reliable, less rate limiting
    MOBILE_ARTICLE_LIST_URL = f"{MOBILE_BASE}/cluster/ajax/articleList"

    def __init__(
        self,
        anti_abuse: Optional[AntiAbuseManager] = None,
        timeout: float = 30.0,
    ):
        """Initialize the crawler.

        Args:
            anti_abuse: Custom anti-abuse manager
            timeout: Request timeout in seconds
        """
        self.anti_abuse = anti_abuse or AntiAbuseManager()
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._session_initialized = False

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def init_session(self) -> bool:
        """Initialize session by visiting mobile site to get cookies.

        This helps avoid rate limiting by appearing as a real browser session.

        Returns:
            True if session initialized successfully
        """
        if self._session_initialized:
            return True

        import asyncio
        import logging
        logger = logging.getLogger(__name__)

        client = await self._get_client()
        headers = self.anti_abuse.get_headers()

        try:
            # Visit mobile landing page to get session cookies
            logger.info("세션 초기화 중 (쿠키 획득)...")
            response = await client.get(
                f"{self.MOBILE_BASE}/",
                headers=headers,
                follow_redirects=True,
            )

            if response.status_code == 200:
                self._session_initialized = True
                logger.info("세션 초기화 완료")
                # Wait a bit to appear more natural
                await asyncio.sleep(2)
                return True
            else:
                logger.warning(f"세션 초기화 실패: {response.status_code}")
                return False

        except httpx.HTTPError as e:
            logger.error(f"세션 초기화 오류: {e}")
            return False

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _make_request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        retries: int = 3,
    ) -> Optional[Dict[str, Any]]:
        """Make an API request with anti-abuse measures.

        Args:
            url: Request URL
            params: Query parameters
            retries: Number of retries

        Returns:
            JSON response or None if failed
        """
        client = await self._get_client()
        backoff = ExponentialBackoff(max_retries=retries)

        while True:
            # Prepare request with anti-abuse measures
            config = await self.anti_abuse.pre_request()

            # Add Naver-specific headers
            headers = config["headers"]
            headers.update({
                "Referer": self.BASE_URL,
                "Origin": self.BASE_URL,
            })

            try:
                response = await client.get(
                    url,
                    params=params,
                    headers=headers,
                )

                # Check for blocking
                if self.anti_abuse.is_blocked_response(
                    response.status_code,
                    response.text,
                ):
                    self.anti_abuse.on_request_failure(
                        proxy=config.get("proxy"),
                        is_blocked=True,
                    )
                    if not await backoff.wait():
                        return None
                    continue

                if response.status_code == 200:
                    self.anti_abuse.on_request_success(config.get("proxy"))
                    return response.json()
                else:
                    self.anti_abuse.on_request_failure(config.get("proxy"))
                    if not await backoff.wait():
                        return None

            except httpx.HTTPError:
                self.anti_abuse.on_request_failure(config.get("proxy"))
                if not await backoff.wait():
                    return None

        return None

    async def get_complexes_in_region(
        self,
        cortarNo: str,
        page: int = 1,
        count: int = 20,
    ) -> List[NaverComplex]:
        """Get apartment complexes in a region.

        Args:
            cortarNo: Region code (법정동코드)
            page: Page number
            count: Items per page

        Returns:
            List of complexes
        """
        params = {
            "cortarNo": cortarNo,
            "realEstateType": "APT",  # 아파트
            "order": "rank",
            "page": page,
            "sameAddressGroup": "true",
        }

        url = self.COMPLEX_LIST_URL
        data = await self._make_request(url, params)

        if not data:
            return []

        complexes = []
        for item in data.get("complexList", []):
            try:
                complex_info = NaverComplex(
                    complex_no=str(item.get("complexNo", "")),
                    complex_name=item.get("complexName", ""),
                    address=item.get("address"),
                    dong_code=cortarNo,
                    total_units=item.get("totalHouseholdCount"),
                    built_year=self._parse_year(item.get("useApproveYmd")),
                    latitude=item.get("latitude"),
                    longitude=item.get("longitude"),
                )
                complexes.append(complex_info)
            except (KeyError, ValueError):
                continue

        return complexes

    async def get_complex_detail(self, complex_no: str) -> Optional[NaverComplex]:
        """Get detailed information about a complex.

        Args:
            complex_no: Complex ID

        Returns:
            Complex details or None
        """
        url = self.COMPLEX_DETAIL_URL.format(complex_no=complex_no)
        data = await self._make_request(url)

        if not data:
            return None

        complex_info = data.get("complexDetail", {})
        try:
            return NaverComplex(
                complex_no=str(complex_no),
                complex_name=complex_info.get("complexName", ""),
                address=complex_info.get("address"),
                dong_code=complex_info.get("cortarNo"),
                total_units=complex_info.get("totalHouseholdCount"),
                built_year=self._parse_year(complex_info.get("useApproveYmd")),
                latitude=complex_info.get("latitude"),
                longitude=complex_info.get("longitude"),
            )
        except (KeyError, ValueError):
            return None

    async def get_listings(
        self,
        complex_no: str,
        trade_type: str = "A1",  # A1: 매매, B1: 전세, B2: 월세
        page: int = 1,
        count: int = 20,
    ) -> List[NaverListing]:
        """Get property listings for a complex.

        Args:
            complex_no: Complex ID
            trade_type: Trade type code
            page: Page number
            count: Items per page

        Returns:
            List of listings
        """
        url = self.ARTICLE_LIST_URL.format(complex_no=complex_no)
        params = {
            "realEstateType": "APT",
            "tradeType": trade_type,
            "page": page,
            "sameAddressGroup": "true",
            "order": "rank",
        }

        data = await self._make_request(url, params)

        if not data:
            return []

        listings = []
        for item in data.get("articleList", []):
            try:
                listing = self._parse_listing(item, complex_no)
                listings.append(listing)
            except (KeyError, ValueError):
                continue

        return listings

    async def get_listing_detail(
        self,
        article_no: str,
    ) -> Optional[NaverListing]:
        """Get detailed information about a listing.

        Args:
            article_no: Article ID

        Returns:
            Listing details or None
        """
        url = self.ARTICLE_DETAIL_URL.format(article_no=article_no)
        data = await self._make_request(url)

        if not data:
            return None

        article = data.get("articleDetail", {})
        try:
            return NaverListing(
                article_no=str(article_no),
                complex_no=str(article.get("complexNo", "")),
                complex_name=article.get("complexName", ""),
                trade_type=self._parse_trade_type(article.get("tradeTypeName")),
                price=self._parse_price(article.get("dealOrWarrantPrc")),
                rent_price=self._parse_price(article.get("rentPrc")),
                area_exclusive=article.get("area1"),
                area_supply=article.get("area2"),
                floor=article.get("floorInfo"),
                direction=article.get("direction"),
                description=article.get("articleFeatureDesc"),
                realtor_name=article.get("realtorName"),
                confirm_date=article.get("articleConfirmYmd"),
            )
        except (KeyError, ValueError):
            return None

    async def get_all_listings_for_complex(
        self,
        complex_no: str,
        trade_types: Optional[List[str]] = None,
        delay: float = 1.5,
    ) -> List[NaverListing]:
        """Get all listings for a complex across all trade types.

        Args:
            complex_no: Complex ID
            trade_types: List of trade type codes (default: all)
            delay: Delay between requests in seconds

        Returns:
            List of all listings
        """
        import asyncio

        if trade_types is None:
            trade_types = ["A1", "B1", "B2"]  # 매매, 전세, 월세

        all_listings = []

        for trade_type in trade_types:
            page = 1
            while True:
                listings = await self.get_listings(
                    complex_no=complex_no,
                    trade_type=trade_type,
                    page=page,
                )

                if not listings:
                    break

                all_listings.extend(listings)

                if len(listings) < 20:
                    break

                page += 1

                # Rate limiting between pages
                await asyncio.sleep(delay)

            # Rate limiting between trade types
            await asyncio.sleep(delay)

        return all_listings

    def _parse_listing(self, item: Dict, complex_no: str) -> NaverListing:
        """Parse a listing from API response."""
        return NaverListing(
            article_no=str(item.get("articleNo", "")),
            complex_no=complex_no,
            complex_name=item.get("articleName", ""),
            trade_type=self._parse_trade_type(item.get("tradeTypeName")),
            price=self._parse_price(item.get("dealOrWarrantPrc")),
            rent_price=self._parse_price(item.get("rentPrc")),
            area_exclusive=item.get("area1"),
            area_supply=item.get("area2"),
            floor=item.get("floorInfo"),
            direction=item.get("direction"),
            description=item.get("articleFeatureDesc"),
            realtor_name=item.get("realtorName"),
            confirm_date=item.get("articleConfirmYmd"),
        )

    @staticmethod
    def _parse_trade_type(trade_type_name: Optional[str]) -> str:
        """Parse trade type from Korean name."""
        if not trade_type_name:
            return "매매"

        if "매매" in trade_type_name:
            return "매매"
        elif "전세" in trade_type_name:
            return "전세"
        elif "월세" in trade_type_name:
            return "월세"
        else:
            return trade_type_name

    @staticmethod
    def _parse_price(price_str: Optional[str]) -> int:
        """Parse price string to integer (만원).

        Examples:
            "15억" -> 150000
            "8억 5,000" -> 135000
            "3,000" -> 3000
        """
        if not price_str:
            return 0

        price_str = str(price_str).strip()

        # Handle "억" unit
        total = 0
        if "억" in price_str:
            parts = price_str.split("억")
            billion_part = parts[0].replace(",", "").strip()
            total += int(billion_part) * 10000

            if len(parts) > 1 and parts[1].strip():
                remainder = parts[1].replace(",", "").replace(" ", "").strip()
                if remainder:
                    total += int(remainder)
        else:
            # Just 만원 units
            total = int(price_str.replace(",", "").replace(" ", ""))

        return total

    @staticmethod
    def _parse_year(date_str: Optional[str]) -> Optional[int]:
        """Extract year from date string (YYYYMMDD)."""
        if not date_str or len(str(date_str)) < 4:
            return None
        try:
            return int(str(date_str)[:4])
        except ValueError:
            return None

    async def get_listings_by_region_mobile(
        self,
        cortarNo: str,
        trade_types: str = "A1",  # A1:B1:B2 for multiple types
        bounds: Optional[Dict[str, float]] = None,
        page: int = 1,
    ) -> List[NaverListing]:
        """Get listings using mobile API (more reliable).

        Args:
            cortarNo: Region code (법정동코드), e.g. "1168000000" for 강남구
            trade_types: Trade type codes separated by colon
            bounds: Map bounds {btm, lft, top, rgt}. If None, uses defaults for Seoul
            page: Page number

        Returns:
            List of listings
        """
        # Default bounds for Seoul area
        if bounds is None:
            bounds = {
                "btm": 37.4,
                "lft": 126.8,
                "top": 37.7,
                "rgt": 127.2,
            }

        params = {
            "rletTpCd": "APT",
            "tradTpCd": trade_types,
            "z": 13,
            "btm": bounds["btm"],
            "lft": bounds["lft"],
            "top": bounds["top"],
            "rgt": bounds["rgt"],
            "cortarNo": cortarNo,
            "sort": "rank",
            "page": page,
        }

        client = await self._get_client()
        config = await self.anti_abuse.pre_request()

        # Mobile-specific headers
        headers = config["headers"]
        headers.update({
            "Referer": f"{self.MOBILE_BASE}/map/{bounds['btm']}:{bounds['lft']}:13:0:0:0:APT::{trade_types}",
            "Origin": self.MOBILE_BASE,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        })

        try:
            response = await client.get(
                self.MOBILE_ARTICLE_LIST_URL,
                params=params,
                headers=headers,
            )

            if response.status_code == 429:
                self.anti_abuse.on_request_failure(is_blocked=True)
                return []

            if response.status_code == 200:
                data = response.json()
                self.anti_abuse.on_request_success()
                return self._parse_mobile_listings(data)
            else:
                self.anti_abuse.on_request_failure()
                return []

        except httpx.HTTPError:
            self.anti_abuse.on_request_failure()
            return []

    def _parse_mobile_listings(self, data: Dict) -> List[NaverListing]:
        """Parse listings from mobile API response."""
        listings = []

        if data.get("code") != "success":
            return listings

        for item in data.get("body", []):
            try:
                # hscpNo is the apartment complex number, cortarNo is region code
                complex_no = item.get("hscpNo") or item.get("complexNo") or ""
                listing = NaverListing(
                    article_no=str(item.get("atclNo", "")),
                    complex_no=str(complex_no),
                    complex_name=item.get("atclNm", ""),
                    trade_type=self._parse_trade_type(item.get("tradTpNm")),
                    price=item.get("prc", 0),
                    rent_price=item.get("rentPrc"),
                    area_exclusive=float(item.get("spc2", 0)) if item.get("spc2") else None,
                    area_supply=float(item.get("spc1", 0)) if item.get("spc1") else None,
                    floor=item.get("flrInfo"),
                    direction=item.get("direction"),
                    description=item.get("atclFetrDesc"),
                    realtor_name=item.get("rltrNm"),
                    confirm_date=item.get("atclCfmYmd"),
                )
                listings.append(listing)
            except (KeyError, ValueError, TypeError):
                continue

        return listings

    async def get_all_listings_by_region_mobile(
        self,
        cortarNo: str,
        trade_types: str = "A1",
        bounds: Optional[Dict[str, float]] = None,
        max_pages: int = 20,
        delay: float = 3.0,
    ) -> List[NaverListing]:
        """Get all listings for a region using mobile API with pagination.

        Args:
            cortarNo: Region code
            trade_types: Trade type codes
            bounds: Map bounds
            max_pages: Maximum pages to fetch
            delay: Delay between requests

        Returns:
            List of all listings
        """
        import asyncio

        all_listings = []
        page = 1

        while page <= max_pages:
            listings = await self.get_listings_by_region_mobile(
                cortarNo=cortarNo,
                trade_types=trade_types,
                bounds=bounds,
                page=page,
            )

            if not listings:
                break

            all_listings.extend(listings)

            # Check if more pages
            if len(listings) < 20:
                break

            page += 1
            await asyncio.sleep(delay)

        return all_listings


# Trade type codes for Naver API
TRADE_TYPES = {
    "매매": "A1",
    "전세": "B1",
    "월세": "B2",
    "단기임대": "B3",
}
