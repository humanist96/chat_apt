"""Tests for Public Data API client."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import date

from app.services.public_data_api import (
    PublicDataAPIClient,
    TransactionData,
    PublicDataAPIError,
    REGION_CODES,
)


# Sample XML response from API
SAMPLE_XML_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<response>
    <header>
        <resultCode>00</resultCode>
        <resultMsg>NORMAL SERVICE.</resultMsg>
    </header>
    <body>
        <items>
            <item>
                <거래금액> 150,000</거래금액>
                <건축년도>2020</건축년도>
                <년>2024</년>
                <월>1</월>
                <일>15</일>
                <법정동>역삼동</법정동>
                <아파트>래미안역삼</아파트>
                <전용면적>84.95</전용면적>
                <지번>123</지번>
                <층>10</층>
            </item>
            <item>
                <거래금액> 155,000</거래금액>
                <건축년도>2020</건축년도>
                <년>2024</년>
                <월>1</월>
                <일>20</일>
                <법정동>역삼동</법정동>
                <아파트>래미안역삼</아파트>
                <전용면적>84.95</전용면적>
                <지번>123</지번>
                <층>15</층>
            </item>
        </items>
    </body>
</response>
"""

ERROR_XML_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<response>
    <header>
        <resultCode>99</resultCode>
        <resultMsg>SERVICE ERROR</resultMsg>
    </header>
</response>
"""


class TestTransactionData:
    """Tests for TransactionData dataclass."""

    def test_transaction_data_creation(self):
        """Test creating TransactionData."""
        data = TransactionData(
            deal_amount=150000,
            built_year=2020,
            deal_year=2024,
            deal_month=1,
            deal_day=15,
            dong="역삼동",
            apartment_name="래미안역삼",
            area=84.95,
            jibun="123",
            floor=10,
            dong_code="11680",
        )

        assert data.deal_amount == 150000
        assert data.apartment_name == "래미안역삼"
        assert data.area == 84.95


class TestPublicDataAPIClient:
    """Tests for PublicDataAPIClient."""

    def test_region_codes(self):
        """Test region codes are defined."""
        assert "서울특별시 강남구" in REGION_CODES
        assert REGION_CODES["서울특별시 강남구"] == "11680"

    @pytest.mark.asyncio
    async def test_parse_response_success(self):
        """Test parsing successful API response."""
        client = PublicDataAPIClient(api_key="test_key")

        transactions = client._parse_response(SAMPLE_XML_RESPONSE, "11680")

        assert len(transactions) == 2
        assert transactions[0].deal_amount == 150000
        assert transactions[0].apartment_name == "래미안역삼"
        assert transactions[0].area == 84.95
        assert transactions[0].floor == 10
        assert transactions[1].deal_amount == 155000
        assert transactions[1].floor == 15

        await client.close()

    @pytest.mark.asyncio
    async def test_parse_response_error(self):
        """Test parsing error API response."""
        client = PublicDataAPIClient(api_key="test_key")

        with pytest.raises(PublicDataAPIError) as exc_info:
            client._parse_response(ERROR_XML_RESPONSE, "11680")

        assert "API error: SERVICE ERROR" in str(exc_info.value)

        await client.close()

    @pytest.mark.asyncio
    async def test_parse_response_invalid_xml(self):
        """Test parsing invalid XML."""
        client = PublicDataAPIClient(api_key="test_key")

        with pytest.raises(PublicDataAPIError) as exc_info:
            client._parse_response("not valid xml", "11680")

        assert "Failed to parse XML" in str(exc_info.value)

        await client.close()

    @pytest.mark.asyncio
    async def test_get_transactions_mock(self):
        """Test get_transactions with mocked HTTP response."""
        client = PublicDataAPIClient(api_key="test_key")

        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.text = SAMPLE_XML_RESPONSE
        mock_response.raise_for_status = MagicMock()

        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            transactions = await client.get_transactions(
                lawd_cd="11680",
                deal_ymd="202401",
            )

            assert len(transactions) == 2
            assert transactions[0].apartment_name == "래미안역삼"

            # Verify API was called with correct URL params
            mock_get.assert_called_once()
            call_url = mock_get.call_args[0][0]
            assert "LAWD_CD=11680" in call_url
            assert "DEAL_YMD=202401" in call_url

        await client.close()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test using client as context manager."""
        async with PublicDataAPIClient(api_key="test_key") as client:
            assert client.api_key == "test_key"
            # Client should be usable inside context


class TestParseItem:
    """Tests for parsing individual items."""

    @pytest.mark.asyncio
    async def test_parse_item_with_missing_fields(self):
        """Test parsing item with missing optional fields."""
        import xml.etree.ElementTree as ET

        xml_str = """
        <item>
            <거래금액>100,000</거래금액>
            <건축년도>2015</건축년도>
            <년>2024</년>
            <월>2</월>
            <일>1</일>
            <아파트>테스트아파트</아파트>
            <전용면적>59.99</전용면적>
        </item>
        """
        item = ET.fromstring(xml_str)

        client = PublicDataAPIClient(api_key="test_key")
        transaction = client._parse_item(item, "11680")

        assert transaction.deal_amount == 100000
        assert transaction.apartment_name == "테스트아파트"
        assert transaction.dong == ""  # Missing field defaults to empty string
        assert transaction.jibun == ""
        assert transaction.floor == 0  # Missing field defaults to 0

        await client.close()

    @pytest.mark.asyncio
    async def test_parse_item_with_whitespace(self):
        """Test parsing item with whitespace in values."""
        import xml.etree.ElementTree as ET

        xml_str = """
        <item>
            <거래금액>  200,000  </거래금액>
            <건축년도>  2018  </건축년도>
            <년>2024</년>
            <월>3</월>
            <일>5</일>
            <법정동>  삼성동  </법정동>
            <아파트>  아이파크  </아파트>
            <전용면적>  114.50  </전용면적>
            <지번>  456  </지번>
            <층>  20  </층>
        </item>
        """
        item = ET.fromstring(xml_str)

        client = PublicDataAPIClient(api_key="test_key")
        transaction = client._parse_item(item, "11680")

        assert transaction.deal_amount == 200000
        assert transaction.dong == "삼성동"
        assert transaction.apartment_name == "아이파크"
        assert transaction.area == 114.50
        assert transaction.floor == 20

        await client.close()
