"""Public Data API client for real estate transaction data.

This module provides a client for Korea's Open Data Portal API
to fetch apartment real transaction data (실거래가).

API Documentation: https://www.data.go.kr/data/15057511/openapi.do
"""
import xml.etree.ElementTree as ET
from datetime import date
from typing import Optional, List
from dataclasses import dataclass

import httpx

from app.config import get_settings


@dataclass
class TransactionData:
    """Real transaction data from API."""
    deal_amount: int  # 거래금액 (만원)
    built_year: int  # 건축년도
    deal_year: int  # 거래년도
    deal_month: int  # 거래월
    deal_day: int  # 거래일
    dong: str  # 법정동
    apartment_name: str  # 아파트명
    area: float  # 전용면적 (m2)
    jibun: str  # 지번
    floor: int  # 층
    dong_code: str  # 법정동코드


class PublicDataAPIClient:
    """Client for Korea's Open Data Portal apartment transaction API."""

    BASE_URL = "http://openapi.molit.go.kr/OpenAPI_ToolInstall498/service/rest/RTMSOBJSvc/getRTMSDataSvcAptTradeDev"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the API client.

        Args:
            api_key: The API key for authentication. If not provided,
                     it will be loaded from settings.
        """
        settings = get_settings()
        self.api_key = api_key or settings.public_data_api_key
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def get_transactions(
        self,
        lawd_cd: str,
        deal_ymd: str,
        num_of_rows: int = 1000,
        page_no: int = 1,
    ) -> List[TransactionData]:
        """Fetch apartment transactions for a specific region and month.

        Args:
            lawd_cd: Region code (법정동코드 앞 5자리)
            deal_ymd: Deal year-month in YYYYMM format
            num_of_rows: Number of rows per page (max 1000)
            page_no: Page number

        Returns:
            List of transaction data

        Raises:
            PublicDataAPIError: If API request fails
        """
        params = {
            "serviceKey": self.api_key,
            "LAWD_CD": lawd_cd,
            "DEAL_YMD": deal_ymd,
            "numOfRows": num_of_rows,
            "pageNo": page_no,
        }

        try:
            response = await self.client.get(self.BASE_URL, params=params)
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise PublicDataAPIError(f"HTTP error: {e}") from e

        return self._parse_response(response.text, lawd_cd)

    def _parse_response(self, xml_text: str, dong_code: str) -> List[TransactionData]:
        """Parse XML response from API.

        Args:
            xml_text: Raw XML response
            dong_code: Region code for reference

        Returns:
            List of parsed transaction data
        """
        transactions = []

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            raise PublicDataAPIError(f"Failed to parse XML: {e}") from e

        # Check for error response
        result_code = root.find(".//resultCode")
        if result_code is not None and result_code.text != "00":
            result_msg = root.find(".//resultMsg")
            msg = result_msg.text if result_msg is not None else "Unknown error"
            raise PublicDataAPIError(f"API error: {msg}")

        # Parse items
        items = root.findall(".//item")

        for item in items:
            try:
                transaction = self._parse_item(item, dong_code)
                transactions.append(transaction)
            except (ValueError, TypeError) as e:
                # Skip invalid records but log them
                continue

        return transactions

    def _parse_item(self, item: ET.Element, dong_code: str) -> TransactionData:
        """Parse a single transaction item.

        Args:
            item: XML element for a transaction
            dong_code: Region code

        Returns:
            Parsed transaction data
        """
        def get_text(tag: str, default: str = "") -> str:
            elem = item.find(tag)
            return elem.text.strip() if elem is not None and elem.text else default

        def get_int(tag: str, default: int = 0) -> int:
            text = get_text(tag)
            if not text:
                return default
            # Remove commas from numbers like "10,000"
            return int(text.replace(",", ""))

        def get_float(tag: str, default: float = 0.0) -> float:
            text = get_text(tag)
            if not text:
                return default
            return float(text)

        return TransactionData(
            deal_amount=get_int("거래금액"),
            built_year=get_int("건축년도"),
            deal_year=get_int("년"),
            deal_month=get_int("월"),
            deal_day=get_int("일"),
            dong=get_text("법정동"),
            apartment_name=get_text("아파트"),
            area=get_float("전용면적"),
            jibun=get_text("지번"),
            floor=get_int("층"),
            dong_code=dong_code,
        )

    async def get_all_transactions_for_period(
        self,
        lawd_cd: str,
        start_date: date,
        end_date: date,
    ) -> List[TransactionData]:
        """Fetch all transactions for a region within a date range.

        Args:
            lawd_cd: Region code
            start_date: Start date
            end_date: End date

        Returns:
            List of all transactions in the period
        """
        all_transactions = []
        current = start_date

        while current <= end_date:
            deal_ymd = current.strftime("%Y%m")

            # Fetch all pages for this month
            page_no = 1
            while True:
                transactions = await self.get_transactions(
                    lawd_cd=lawd_cd,
                    deal_ymd=deal_ymd,
                    num_of_rows=1000,
                    page_no=page_no,
                )

                if not transactions:
                    break

                all_transactions.extend(transactions)

                if len(transactions) < 1000:
                    break

                page_no += 1

            # Move to next month
            if current.month == 12:
                current = date(current.year + 1, 1, 1)
            else:
                current = date(current.year, current.month + 1, 1)

        return all_transactions


class PublicDataAPIError(Exception):
    """Exception raised for Public Data API errors."""
    pass


# Region codes for major areas (법정동코드 앞 5자리)
REGION_CODES = {
    # Seoul
    "서울특별시 강남구": "11680",
    "서울특별시 서초구": "11650",
    "서울특별시 송파구": "11710",
    "서울특별시 강동구": "11740",
    "서울특별시 마포구": "11440",
    "서울특별시 용산구": "11170",
    "서울특별시 성동구": "11200",
    "서울특별시 광진구": "11215",
    "서울특별시 동작구": "11590",
    "서울특별시 영등포구": "11560",
    # Gyeonggi
    "경기도 성남시 분당구": "41135",
    "경기도 수원시 영통구": "41117",
    "경기도 용인시 수지구": "41465",
    "경기도 하남시": "41450",
    "경기도 과천시": "41290",
}
