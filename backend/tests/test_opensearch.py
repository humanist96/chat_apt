"""Tests for OpenSearch service."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.opensearch import (
    OpenSearchConfig,
    OpenSearchClient,
    SearchResult,
    IndexMapping,
    ApartmentSearchService,
    ListingSearchService,
    TransactionAnalyticsService,
    APARTMENTS_INDEX,
    LISTINGS_INDEX,
    TRANSACTIONS_INDEX,
    get_opensearch_client,
)


class TestOpenSearchConfig:
    """Tests for OpenSearchConfig."""

    def test_default_config(self):
        """Test default configuration loads from settings."""
        config = OpenSearchConfig()

        # Should load from settings (which defaults to 49.247.172.187)
        assert config.host is not None
        assert config.port == 9200
        assert config.use_ssl is False

    def test_base_url_http(self):
        """Test base URL generation for HTTP."""
        config = OpenSearchConfig(
            host="test.local",
            username="user",
            password="pass",
            use_ssl=False
        )
        assert config.base_url == "http://test.local:9200"

    def test_base_url_https(self):
        """Test base URL generation for HTTPS."""
        config = OpenSearchConfig(
            host="test.local",
            username="user",
            password="pass",
            use_ssl=True
        )
        assert config.base_url == "https://test.local:9200"

    def test_custom_config(self):
        """Test custom configuration."""
        config = OpenSearchConfig(
            host="localhost",
            port=9201,
            username="custom",
            password="secret"
        )

        assert config.host == "localhost"
        assert config.port == 9201
        assert config.base_url == "http://localhost:9201"


class TestSearchResult:
    """Tests for SearchResult."""

    def test_search_result_creation(self):
        """Test creating a search result."""
        result = SearchResult(
            total=100,
            hits=[{"id": 1}, {"id": 2}],
            aggregations={"count": {"value": 100}},
            took_ms=15
        )

        assert result.total == 100
        assert len(result.hits) == 2
        assert result.aggregations is not None
        assert result.took_ms == 15

    def test_search_result_minimal(self):
        """Test minimal search result."""
        result = SearchResult(total=0, hits=[])

        assert result.total == 0
        assert result.hits == []
        assert result.aggregations is None


class TestIndexMappings:
    """Tests for index mappings."""

    def test_apartments_index(self):
        """Test apartments index mapping."""
        assert APARTMENTS_INDEX.name == "apartments"
        assert "properties" in APARTMENTS_INDEX.mappings
        assert "name" in APARTMENTS_INDEX.mappings["properties"]
        assert "location" in APARTMENTS_INDEX.mappings["properties"]

    def test_listings_index(self):
        """Test listings index mapping."""
        assert LISTINGS_INDEX.name == "listings"
        props = LISTINGS_INDEX.mappings["properties"]
        assert "price" in props
        assert "recommendation_score" in props
        assert "discount_rate" in props

    def test_transactions_index(self):
        """Test transactions index mapping."""
        assert TRANSACTIONS_INDEX.name == "transactions"
        props = TRANSACTIONS_INDEX.mappings["properties"]
        assert "deal_amount" in props
        assert "deal_date" in props


class TestOpenSearchClient:
    """Tests for OpenSearchClient."""

    def test_client_creation(self):
        """Test client creation."""
        client = OpenSearchClient()
        assert client.config is not None
        assert client._client is None

    def test_client_with_custom_config(self):
        """Test client with custom config."""
        config = OpenSearchConfig(host="test.local")
        client = OpenSearchClient(config)
        assert client.config.host == "test.local"

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        with patch.object(OpenSearchClient, 'connect', new_callable=AsyncMock):
            with patch.object(OpenSearchClient, 'close', new_callable=AsyncMock):
                async with OpenSearchClient() as client:
                    assert client is not None

    @pytest.mark.asyncio
    async def test_health_check_mocked(self):
        """Test health check with mocked response."""
        client = OpenSearchClient()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "cluster_name": "opensearch-cluster",
            "status": "green"
        }
        mock_response.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.get.return_value = mock_response
        client._client = mock_http

        result = await client.health_check()

        assert result["status"] == "green"
        mock_http.get.assert_called_once_with("/_cluster/health")

    @pytest.mark.asyncio
    async def test_index_exists_true(self):
        """Test index exists returns True."""
        client = OpenSearchClient()

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_http = AsyncMock()
        mock_http.head.return_value = mock_response
        client._client = mock_http

        result = await client.index_exists("test_index")

        assert result is True

    @pytest.mark.asyncio
    async def test_index_exists_false(self):
        """Test index exists returns False."""
        client = OpenSearchClient()

        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_http = AsyncMock()
        mock_http.head.return_value = mock_response
        client._client = mock_http

        result = await client.index_exists("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_search_mocked(self):
        """Test search with mocked response."""
        client = OpenSearchClient()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "took": 5,
            "hits": {
                "total": {"value": 2},
                "hits": [
                    {"_source": {"id": 1, "name": "Apt1"}},
                    {"_source": {"id": 2, "name": "Apt2"}}
                ]
            },
            "aggregations": {"count": {"value": 2}}
        }
        mock_response.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.post.return_value = mock_response
        client._client = mock_http

        result = await client.search(
            index_name="apartments",
            query={"match_all": {}},
            size=10
        )

        assert result.total == 2
        assert len(result.hits) == 2
        assert result.took_ms == 5

    @pytest.mark.asyncio
    async def test_bulk_index_mocked(self):
        """Test bulk indexing with mocked response."""
        client = OpenSearchClient()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "took": 30,
            "errors": False,
            "items": [
                {"index": {"_id": "1", "status": 201}},
                {"index": {"_id": "2", "status": 201}}
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.post.return_value = mock_response
        client._client = mock_http

        documents = [
            ("1", {"id": 1, "name": "Apt1"}),
            ("2", {"id": 2, "name": "Apt2"})
        ]

        result = await client.bulk_index("apartments", documents)

        assert result["indexed"] == 2
        assert result["errors"] is False


class TestApartmentSearchService:
    """Tests for ApartmentSearchService."""

    @pytest.mark.asyncio
    async def test_search_by_name(self):
        """Test searching apartments by name."""
        mock_client = MagicMock(spec=OpenSearchClient)
        mock_client.search = AsyncMock(return_value=SearchResult(
            total=1,
            hits=[{"id": 1, "name": "래미안"}]
        ))

        service = ApartmentSearchService(mock_client)
        result = await service.search_by_name("래미안")

        assert result.total == 1
        mock_client.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_by_name_with_dong_code(self):
        """Test searching with dong code filter."""
        mock_client = MagicMock(spec=OpenSearchClient)
        mock_client.search = AsyncMock(return_value=SearchResult(
            total=1, hits=[{"id": 1}]
        ))

        service = ApartmentSearchService(mock_client)
        await service.search_by_name("래미안", dong_code="11680")

        call_args = mock_client.search.call_args
        query = call_args.kwargs.get("query", {})
        assert "bool" in query
        assert len(query["bool"]["must"]) == 2

    @pytest.mark.asyncio
    async def test_search_by_location(self):
        """Test searching by location."""
        mock_client = MagicMock(spec=OpenSearchClient)
        mock_client.search = AsyncMock(return_value=SearchResult(
            total=5, hits=[]
        ))

        service = ApartmentSearchService(mock_client)
        result = await service.search_by_location(37.5, 127.0, distance_km=2.0)

        assert result.total == 5
        call_args = mock_client.search.call_args
        assert call_args.kwargs.get("sort") is not None


class TestListingSearchService:
    """Tests for ListingSearchService."""

    @pytest.mark.asyncio
    async def test_search_listings_basic(self):
        """Test basic listing search."""
        mock_client = MagicMock(spec=OpenSearchClient)
        mock_client.search = AsyncMock(return_value=SearchResult(
            total=10, hits=[]
        ))

        service = ListingSearchService(mock_client)
        result = await service.search_listings()

        assert result.total == 10

    @pytest.mark.asyncio
    async def test_search_listings_with_filters(self):
        """Test listing search with filters."""
        mock_client = MagicMock(spec=OpenSearchClient)
        mock_client.search = AsyncMock(return_value=SearchResult(
            total=3, hits=[]
        ))

        service = ListingSearchService(mock_client)
        result = await service.search_listings(
            dong_code="11680",
            min_price=100000,
            max_price=200000,
            min_area=60.0,
            max_area=100.0,
            trade_type="A1"
        )

        assert result.total == 3
        call_args = mock_client.search.call_args
        query = call_args.kwargs.get("query", {})
        # Should have multiple filters
        assert "bool" in query
        assert "filter" in query["bool"]

    @pytest.mark.asyncio
    async def test_get_undervalued_listings(self):
        """Test getting undervalued listings."""
        mock_client = MagicMock(spec=OpenSearchClient)
        mock_client.search = AsyncMock(return_value=SearchResult(
            total=5, hits=[
                {"id": 1, "discount_rate": -10.0},
                {"id": 2, "discount_rate": -8.0}
            ]
        ))

        service = ListingSearchService(mock_client)
        result = await service.get_undervalued_listings(
            dong_code="11680",
            min_discount_rate=-5.0
        )

        assert result.total == 5

    @pytest.mark.asyncio
    async def test_get_price_distribution(self):
        """Test getting price distribution."""
        mock_client = MagicMock(spec=OpenSearchClient)
        mock_client.search = AsyncMock(return_value=SearchResult(
            total=0,
            hits=[],
            aggregations={
                "price_histogram": {
                    "buckets": [
                        {"key": 100000, "doc_count": 5},
                        {"key": 200000, "doc_count": 10}
                    ]
                }
            }
        ))

        service = ListingSearchService(mock_client)
        result = await service.get_price_distribution("11680")

        assert "price_histogram" in result


class TestTransactionAnalyticsService:
    """Tests for TransactionAnalyticsService."""

    @pytest.mark.asyncio
    async def test_get_price_trend(self):
        """Test getting price trend."""
        mock_client = MagicMock(spec=OpenSearchClient)
        mock_client.search = AsyncMock(return_value=SearchResult(
            total=0,
            hits=[],
            aggregations={
                "yearly_trend": {
                    "buckets": [
                        {"key": 2023, "avg_price": {"value": 150000}},
                        {"key": 2024, "avg_price": {"value": 160000}}
                    ]
                }
            }
        ))

        service = TransactionAnalyticsService(mock_client)
        result = await service.get_price_trend(apartment_id=1)

        assert "yearly_trend" in result

    @pytest.mark.asyncio
    async def test_get_region_price_stats(self):
        """Test getting region price stats."""
        mock_client = MagicMock(spec=OpenSearchClient)
        mock_client.search = AsyncMock(return_value=SearchResult(
            total=0,
            hits=[],
            aggregations={
                "price_stats": {
                    "avg": 150000,
                    "min": 100000,
                    "max": 200000
                }
            }
        ))

        service = TransactionAnalyticsService(mock_client)
        result = await service.get_region_price_stats("11680", year=2024)

        assert "price_stats" in result

    @pytest.mark.asyncio
    async def test_compare_similar_apartments(self):
        """Test comparing similar apartments."""
        mock_client = MagicMock(spec=OpenSearchClient)
        mock_client.search = AsyncMock(return_value=SearchResult(
            total=0,
            hits=[],
            aggregations={
                "by_apartment": {
                    "buckets": [
                        {"key": 1, "price_stats": {"avg": 150000}},
                        {"key": 2, "price_stats": {"avg": 155000}}
                    ]
                }
            }
        ))

        service = TransactionAnalyticsService(mock_client)
        result = await service.compare_similar_apartments([1, 2, 3])

        assert "by_apartment" in result


class TestSingleton:
    """Test singleton pattern."""

    def test_get_opensearch_client(self):
        """Test getting OpenSearch client singleton."""
        client1 = get_opensearch_client()
        client2 = get_opensearch_client()

        assert client1 is client2
