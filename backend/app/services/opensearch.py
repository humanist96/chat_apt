"""OpenSearch client for search and analytics.

This module provides:
- Full-text search for apartments and listings
- Real-time aggregations for price analytics
- Vector search for similar apartments (future)
"""
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import logging
import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class OpenSearchConfig:
    """OpenSearch connection configuration."""
    host: str = ""
    port: int = 9200
    username: str = ""
    password: str = ""
    use_ssl: bool = False
    verify_certs: bool = False

    def __post_init__(self):
        """Load defaults from settings if not provided."""
        if not self.host or not self.username:
            settings = get_settings()
            self.host = self.host or settings.opensearch_host
            self.port = self.port or settings.opensearch_port
            self.username = self.username or settings.opensearch_username
            self.password = self.password or settings.opensearch_password

    @property
    def base_url(self) -> str:
        protocol = "https" if self.use_ssl else "http"
        return f"{protocol}://{self.host}:{self.port}"


@dataclass
class SearchResult:
    """Search result wrapper."""
    total: int
    hits: List[Dict[str, Any]]
    aggregations: Optional[Dict[str, Any]] = None
    took_ms: int = 0


@dataclass
class IndexMapping:
    """Index mapping definition."""
    name: str
    mappings: Dict[str, Any]
    settings: Dict[str, Any] = field(default_factory=dict)


# Index definitions
APARTMENTS_INDEX = IndexMapping(
    name="apartments",
    settings={
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "korean_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "trim"]
                }
            }
        }
    },
    mappings={
        "properties": {
            "id": {"type": "integer"},
            "name": {
                "type": "text",
                "analyzer": "korean_analyzer",
                "fields": {"keyword": {"type": "keyword"}}
            },
            "address": {
                "type": "text",
                "analyzer": "korean_analyzer",
                "fields": {"keyword": {"type": "keyword"}}
            },
            "dong_code": {"type": "keyword"},
            "complex_no": {"type": "keyword"},
            "location": {"type": "geo_point"},
            "total_units": {"type": "integer"},
            "built_year": {"type": "integer"},
            "avg_area": {"type": "float"},
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"}
        }
    }
)

LISTINGS_INDEX = IndexMapping(
    name="listings",
    settings={
        "number_of_shards": 1,
        "number_of_replicas": 0
    },
    mappings={
        "properties": {
            "id": {"type": "integer"},
            "apartment_id": {"type": "integer"},
            "apartment_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "article_no": {"type": "keyword"},
            "trade_type": {"type": "keyword"},
            "price": {"type": "integer"},
            "rent_price": {"type": "integer"},
            "area": {"type": "float"},
            "floor": {"type": "integer"},
            "direction": {"type": "keyword"},
            "description": {"type": "text"},
            "dong_code": {"type": "keyword"},
            "location": {"type": "geo_point"},
            "is_active": {"type": "boolean"},
            "discount_rate": {"type": "float"},
            "recommendation_score": {"type": "float"},
            "first_seen_at": {"type": "date"},
            "last_seen_at": {"type": "date"},
            "created_at": {"type": "date"}
        }
    }
)

TRANSACTIONS_INDEX = IndexMapping(
    name="transactions",
    settings={
        "number_of_shards": 1,
        "number_of_replicas": 0
    },
    mappings={
        "properties": {
            "id": {"type": "integer"},
            "apartment_id": {"type": "integer"},
            "apartment_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "dong_code": {"type": "keyword"},
            "deal_amount": {"type": "integer"},
            "area": {"type": "float"},
            "floor": {"type": "integer"},
            "deal_date": {"type": "date"},
            "deal_year": {"type": "integer"},
            "deal_month": {"type": "integer"},
            "deal_day": {"type": "integer"},
            "created_at": {"type": "date"}
        }
    }
)


class OpenSearchClient:
    """Async OpenSearch client for search and analytics."""

    def __init__(self, config: Optional[OpenSearchConfig] = None):
        self.config = config or OpenSearchConfig()
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "OpenSearchClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def connect(self) -> None:
        """Initialize the HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url,
            auth=(self.config.username, self.config.password),
            timeout=30.0,
            verify=self.config.verify_certs
        )
        logger.info(f"Connected to OpenSearch at {self.config.base_url}")

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if not self._client:
            raise RuntimeError("OpenSearch client not connected. Call connect() first.")
        return self._client

    async def health_check(self) -> Dict[str, Any]:
        """Check cluster health."""
        response = await self.client.get("/_cluster/health")
        response.raise_for_status()
        return response.json()

    async def index_exists(self, index_name: str) -> bool:
        """Check if an index exists."""
        response = await self.client.head(f"/{index_name}")
        return response.status_code == 200

    async def create_index(self, mapping: IndexMapping, delete_if_exists: bool = False) -> bool:
        """Create an index with mapping."""
        if await self.index_exists(mapping.name):
            if delete_if_exists:
                await self.delete_index(mapping.name)
            else:
                logger.info(f"Index {mapping.name} already exists")
                return False

        body = {
            "settings": mapping.settings,
            "mappings": mapping.mappings
        }

        response = await self.client.put(
            f"/{mapping.name}",
            json=body
        )
        response.raise_for_status()
        logger.info(f"Created index {mapping.name}")
        return True

    async def delete_index(self, index_name: str) -> bool:
        """Delete an index."""
        response = await self.client.delete(f"/{index_name}")
        if response.status_code == 404:
            return False
        response.raise_for_status()
        logger.info(f"Deleted index {index_name}")
        return True

    async def index_document(
        self,
        index_name: str,
        doc_id: str,
        document: Dict[str, Any],
        refresh: bool = False
    ) -> Dict[str, Any]:
        """Index a single document."""
        url = f"/{index_name}/_doc/{doc_id}"
        if refresh:
            url += "?refresh=true"

        response = await self.client.put(url, json=document)
        response.raise_for_status()
        return response.json()

    async def bulk_index(
        self,
        index_name: str,
        documents: List[Tuple[str, Dict[str, Any]]],
        refresh: bool = True
    ) -> Dict[str, Any]:
        """Bulk index multiple documents.

        Args:
            index_name: Target index
            documents: List of (doc_id, document) tuples
            refresh: Whether to refresh after indexing
        """
        if not documents:
            return {"indexed": 0}

        # Build NDJSON bulk request body
        lines = []
        for doc_id, document in documents:
            action = {"index": {"_index": index_name, "_id": doc_id}}
            lines.append(action)
            lines.append(document)

        # Convert to NDJSON format
        import json
        body = "\n".join(json.dumps(line) for line in lines) + "\n"

        url = "/_bulk"
        if refresh:
            url += "?refresh=true"

        response = await self.client.post(
            url,
            content=body,
            headers={"Content-Type": "application/x-ndjson"}
        )
        response.raise_for_status()
        result = response.json()

        indexed = sum(1 for item in result.get("items", [])
                     if item.get("index", {}).get("status") in [200, 201])

        logger.info(f"Bulk indexed {indexed}/{len(documents)} documents to {index_name}")
        return {"indexed": indexed, "errors": result.get("errors", False)}

    async def search(
        self,
        index_name: str,
        query: Optional[Dict[str, Any]] = None,
        size: int = 10,
        from_: int = 0,
        sort: Optional[List[Dict[str, Any]]] = None,
        aggs: Optional[Dict[str, Any]] = None,
        source: Optional[List[str]] = None
    ) -> SearchResult:
        """Execute a search query.

        Args:
            index_name: Index to search
            query: OpenSearch query DSL
            size: Number of results
            from_: Offset for pagination
            sort: Sort specification
            aggs: Aggregations
            source: Fields to include in results
        """
        body: Dict[str, Any] = {
            "size": size,
            "from": from_
        }

        if query:
            body["query"] = query

        if sort:
            body["sort"] = sort

        if aggs:
            body["aggs"] = aggs

        if source:
            body["_source"] = source

        response = await self.client.post(
            f"/{index_name}/_search",
            json=body
        )
        response.raise_for_status()
        result = response.json()

        hits = result.get("hits", {})
        total = hits.get("total", {})
        total_count = total.get("value", 0) if isinstance(total, dict) else total

        return SearchResult(
            total=total_count,
            hits=[hit.get("_source", {}) for hit in hits.get("hits", [])],
            aggregations=result.get("aggregations"),
            took_ms=result.get("took", 0)
        )

    async def delete_document(self, index_name: str, doc_id: str) -> bool:
        """Delete a document by ID."""
        response = await self.client.delete(f"/{index_name}/_doc/{doc_id}")
        return response.status_code == 200

    async def delete_by_query(
        self,
        index_name: str,
        query: Dict[str, Any]
    ) -> int:
        """Delete documents matching a query."""
        response = await self.client.post(
            f"/{index_name}/_delete_by_query",
            json={"query": query}
        )
        response.raise_for_status()
        result = response.json()
        return result.get("deleted", 0)


class ApartmentSearchService:
    """Search service for apartments."""

    def __init__(self, client: OpenSearchClient):
        self.client = client
        self.index_name = APARTMENTS_INDEX.name

    async def search_by_name(
        self,
        name: str,
        dong_code: Optional[str] = None,
        size: int = 20
    ) -> SearchResult:
        """Search apartments by name."""
        must = [
            {"match": {"name": {"query": name, "fuzziness": "AUTO"}}}
        ]

        if dong_code:
            must.append({"term": {"dong_code": dong_code}})

        return await self.client.search(
            index_name=self.index_name,
            query={"bool": {"must": must}},
            size=size
        )

    async def search_by_location(
        self,
        lat: float,
        lon: float,
        distance_km: float = 1.0,
        size: int = 20
    ) -> SearchResult:
        """Search apartments near a location."""
        return await self.client.search(
            index_name=self.index_name,
            query={
                "bool": {
                    "filter": {
                        "geo_distance": {
                            "distance": f"{distance_km}km",
                            "location": {"lat": lat, "lon": lon}
                        }
                    }
                }
            },
            size=size,
            sort=[
                {
                    "_geo_distance": {
                        "location": {"lat": lat, "lon": lon},
                        "order": "asc",
                        "unit": "km"
                    }
                }
            ]
        )

    async def get_region_stats(self, dong_code: str) -> Dict[str, Any]:
        """Get statistics for a region."""
        result = await self.client.search(
            index_name=self.index_name,
            query={"term": {"dong_code": dong_code}},
            size=0,
            aggs={
                "total_apartments": {"value_count": {"field": "id"}},
                "avg_built_year": {"avg": {"field": "built_year"}},
                "total_units": {"sum": {"field": "total_units"}},
                "area_stats": {"stats": {"field": "avg_area"}}
            }
        )

        return result.aggregations or {}


class ListingSearchService:
    """Search service for listings."""

    def __init__(self, client: OpenSearchClient):
        self.client = client
        self.index_name = LISTINGS_INDEX.name

    async def search_listings(
        self,
        dong_code: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        min_area: Optional[float] = None,
        max_area: Optional[float] = None,
        trade_type: Optional[str] = None,
        only_active: bool = True,
        min_discount_rate: Optional[float] = None,
        size: int = 20,
        from_: int = 0,
        sort_by: str = "recommendation_score"
    ) -> SearchResult:
        """Search listings with filters."""
        must = []
        filter_ = []

        if only_active:
            filter_.append({"term": {"is_active": True}})

        if dong_code:
            filter_.append({"term": {"dong_code": dong_code}})

        if trade_type:
            filter_.append({"term": {"trade_type": trade_type}})

        if min_price is not None or max_price is not None:
            price_range: Dict[str, Any] = {}
            if min_price is not None:
                price_range["gte"] = min_price
            if max_price is not None:
                price_range["lte"] = max_price
            filter_.append({"range": {"price": price_range}})

        if min_area is not None or max_area is not None:
            area_range: Dict[str, Any] = {}
            if min_area is not None:
                area_range["gte"] = min_area
            if max_area is not None:
                area_range["lte"] = max_area
            filter_.append({"range": {"area": area_range}})

        if min_discount_rate is not None:
            filter_.append({"range": {"discount_rate": {"lte": min_discount_rate}}})

        query: Dict[str, Any] = {"bool": {}}
        if must:
            query["bool"]["must"] = must
        if filter_:
            query["bool"]["filter"] = filter_

        if not must and not filter_:
            query = {"match_all": {}}

        # Sort configuration
        sort_config = []
        if sort_by == "recommendation_score":
            sort_config.append({"recommendation_score": {"order": "desc"}})
        elif sort_by == "price_asc":
            sort_config.append({"price": {"order": "asc"}})
        elif sort_by == "price_desc":
            sort_config.append({"price": {"order": "desc"}})
        elif sort_by == "discount_rate":
            sort_config.append({"discount_rate": {"order": "asc"}})
        elif sort_by == "newest":
            sort_config.append({"first_seen_at": {"order": "desc"}})

        return await self.client.search(
            index_name=self.index_name,
            query=query,
            size=size,
            from_=from_,
            sort=sort_config if sort_config else None
        )

    async def get_undervalued_listings(
        self,
        dong_code: Optional[str] = None,
        min_discount_rate: float = -5.0,
        size: int = 20
    ) -> SearchResult:
        """Get undervalued listings (discount below threshold)."""
        return await self.search_listings(
            dong_code=dong_code,
            min_discount_rate=min_discount_rate,
            size=size,
            sort_by="discount_rate"
        )

    async def get_price_distribution(
        self,
        dong_code: str,
        interval: int = 10000  # 1억 단위
    ) -> Dict[str, Any]:
        """Get price distribution histogram."""
        result = await self.client.search(
            index_name=self.index_name,
            query={
                "bool": {
                    "filter": [
                        {"term": {"dong_code": dong_code}},
                        {"term": {"is_active": True}}
                    ]
                }
            },
            size=0,
            aggs={
                "price_histogram": {
                    "histogram": {
                        "field": "price",
                        "interval": interval
                    }
                },
                "price_stats": {
                    "stats": {"field": "price"}
                }
            }
        )

        return result.aggregations or {}


class TransactionAnalyticsService:
    """Analytics service for transactions."""

    def __init__(self, client: OpenSearchClient):
        self.client = client
        self.index_name = TRANSACTIONS_INDEX.name

    async def get_price_trend(
        self,
        apartment_id: int,
        years: int = 5
    ) -> Dict[str, Any]:
        """Get price trend for an apartment over time."""
        from_year = datetime.now().year - years

        result = await self.client.search(
            index_name=self.index_name,
            query={
                "bool": {
                    "filter": [
                        {"term": {"apartment_id": apartment_id}},
                        {"range": {"deal_year": {"gte": from_year}}}
                    ]
                }
            },
            size=0,
            aggs={
                "yearly_trend": {
                    "terms": {
                        "field": "deal_year",
                        "order": {"_key": "asc"}
                    },
                    "aggs": {
                        "avg_price": {"avg": {"field": "deal_amount"}},
                        "max_price": {"max": {"field": "deal_amount"}},
                        "min_price": {"min": {"field": "deal_amount"}},
                        "count": {"value_count": {"field": "id"}}
                    }
                },
                "monthly_trend": {
                    "date_histogram": {
                        "field": "deal_date",
                        "calendar_interval": "month",
                        "format": "yyyy-MM"
                    },
                    "aggs": {
                        "avg_price": {"avg": {"field": "deal_amount"}}
                    }
                }
            }
        )

        return result.aggregations or {}

    async def get_region_price_stats(
        self,
        dong_code: str,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get price statistics for a region."""
        filter_conditions = [{"term": {"dong_code": dong_code}}]

        if year:
            filter_conditions.append({"term": {"deal_year": year}})

        result = await self.client.search(
            index_name=self.index_name,
            query={"bool": {"filter": filter_conditions}},
            size=0,
            aggs={
                "price_stats": {"extended_stats": {"field": "deal_amount"}},
                "by_area": {
                    "range": {
                        "field": "area",
                        "ranges": [
                            {"to": 60},
                            {"from": 60, "to": 85},
                            {"from": 85, "to": 115},
                            {"from": 115}
                        ]
                    },
                    "aggs": {
                        "avg_price": {"avg": {"field": "deal_amount"}}
                    }
                },
                "top_apartments": {
                    "terms": {
                        "field": "apartment_name.keyword",
                        "size": 10
                    },
                    "aggs": {
                        "avg_price": {"avg": {"field": "deal_amount"}},
                        "count": {"value_count": {"field": "id"}}
                    }
                }
            }
        )

        return result.aggregations or {}

    async def compare_similar_apartments(
        self,
        apartment_ids: List[int],
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """Compare transaction data for similar apartments."""
        filter_conditions: List[Dict[str, Any]] = [
            {"terms": {"apartment_id": apartment_ids}}
        ]

        if year:
            filter_conditions.append({"term": {"deal_year": year}})

        result = await self.client.search(
            index_name=self.index_name,
            query={"bool": {"filter": filter_conditions}},
            size=0,
            aggs={
                "by_apartment": {
                    "terms": {
                        "field": "apartment_id",
                        "size": len(apartment_ids)
                    },
                    "aggs": {
                        "price_stats": {"stats": {"field": "deal_amount"}},
                        "recent_price": {
                            "top_hits": {
                                "size": 1,
                                "sort": [{"deal_date": {"order": "desc"}}],
                                "_source": ["deal_amount", "deal_date", "area"]
                            }
                        }
                    }
                }
            }
        )

        return result.aggregations or {}


async def setup_indices(client: OpenSearchClient) -> None:
    """Set up all required indices."""
    indices = [APARTMENTS_INDEX, LISTINGS_INDEX, TRANSACTIONS_INDEX]

    for index in indices:
        try:
            created = await client.create_index(index)
            if created:
                logger.info(f"Created index: {index.name}")
        except Exception as e:
            logger.error(f"Failed to create index {index.name}: {e}")


# Singleton instance
_opensearch_client: Optional[OpenSearchClient] = None


def get_opensearch_client() -> OpenSearchClient:
    """Get or create the OpenSearch client singleton."""
    global _opensearch_client
    if _opensearch_client is None:
        _opensearch_client = OpenSearchClient()
    return _opensearch_client
